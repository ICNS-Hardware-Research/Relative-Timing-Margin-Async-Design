#!/usr/bin/env python3
"""
pipeline_docs.py - builds the HTML documentation for a run of generate_pipeline.py.

The document is assembled from

  * a SKELETON (doc_templates/pipeline_doc_template.html, plus style.css) that holds all the prose
    and the tables that are the same every run.  This is the file to edit to change the document.
  * FRAGMENTS written to <output_dir>/doc/fragments/ every run for the parts that change:
        cards.html  formulas.html  delay_table.html  delay_lines.html
    and the schematic <output_dir>/doc/pipeline.svg.

The template pulls these in with  {{include:NAME}}  and takes single values with  {{arg.range}},
{{n_lines}} and so on (the full list is in the comment at the top of the template).
The assembled, self-contained result is <output_dir>/doc/pipeline_doc.html.

Files are looked for in doc/fragments/, doc/, the output directory itself (so NAME can be implementation/synthesis.html)
and then the template's folder.

Optional parts:  {{include?:NAME}}  inserts a file only if it exists;  {{if:NAME}} ... {{endif}}  keeps a block of the
template only if NAME exists ({{ifnot:NAME}} the opposite).  Files can be added after a run and the document
re-assembled with   python3 pipeline_docs.py --rebuild <output_dir>
"""
import datetime
import getpass
import argparse
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(HERE, "doc_templates", "pipeline_doc_template.html")

_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.:/?\-]+)\s*\}\}")
_IF = re.compile(r"\{\{\s*(if|ifnot):([A-Za-z0-9_.:/\-]+)\s*\}\}(.*?)\{\{\s*endif\s*\}\}", re.S)
_COMMENT = re.compile(r"<!--.*?-->", re.S)


def esc(s):
    return html.escape(str(s), quote=True)


def fmt(v, dp=3):
    """400.0 -> 400 ; 266.666 -> 266.666 (no trailing zeros)"""
    s = ("%." + str(dp) + "f") % v
    return s.rstrip("0").rstrip(".") if "." in s else s


# --------------------------------------------------------------------------
# fragments: the parts that change from run to run
# --------------------------------------------------------------------------
def frag_cards(*, n_lines, compact, req_buffers, bd, total_buffers, taps):
    cards = (
        ("%d" % n_lines, "data delay lines (%s)" % ("compact, shared by all targets" if compact else "one per distinct delay")),
        ("%d" % req_buffers, "buffers in the request chain (%s ps)" % fmt(req_buffers * bd)),
        ("%d" % total_buffers, "buffers in the data delay lines"),
        (", ".join(str(t) for t in taps), "mux4 tap positions (buffers along the request chain)"),
    )
    o = ['<div class="grid">']
    for big, small in cards:
        o.append('<div class="card"><b>%s</b><span>%s</span></div>' % (esc(big), esc(small)))
    o.append("</div>")
    return "\n".join(o) + "\n"


def frag_formulas(*, compact, n_lines):
    o = ["<ul>",
         "<li><b>Required data delays.</b> For each target <i>T</i> and each offset <i>p</i> from +range to -range in steps of step: "
         "<code>delay = T / (1 + p/100)</code>, truncated to three decimals (table in section 4).</li>"]
    if not compact:
        o.append("<li><b>Delay lines (normal mode).</b> All delays are pooled, duplicates removed and sorted ascending; each becomes one line of "
                 "<code>ceil((delay - mousetrap_delay) / buffer_delay)</code> buffers.</li>")
    else:
        o.append("<li><b>Delay lines (compact mode).</b> The delays are kept in groups of one per target; line <i>k</i> serves the <i>k</i>-th offset of every target. "
                 "It has a tap after <code>round((delay - mux4_delay - mousetrap_delay) / buffer_delay)</code> buffers for each target and a "
                 "<code>mux4</code> choosing between them.</li>")
    o.append("<li><b>Request chain.</b> <code>ceil((longest target - mux4_delay - mousetrap_delay) / buffer_delay)</code> buffers.</li>")
    o.append("<li><b>Request taps.</b> One per target, ascending: <code>ceil((target - mux4_delay - mousetrap_delay) / buffer_delay)</code> buffers "
             "along the chain; the largest target therefore taps the end of the chain.</li>")
    o.append("<li><b>Datapath width.</b> <code>DATAPATH_WIDTH</code> = number of delay lines (%d here); the scan chain is DATAPATH_WIDTH + 3 bits "
             "(data, request, 2 bits of <code>delay_ctrl</code>).</li>" % n_lines)
    o.append("</ul>")
    return "\n".join(o) + "\n"


def frag_delay_table(table):
    if not table:
        return ""
    offsets = [p for p, _ in table[0][1]]
    o = ['<div class="scroll"><table class="tight"><tr><th>Target (ps)</th>']
    for p in offsets:
        o.append('<th class="num%s">%s</th>' % (" mid" if p == 0 else "", ("%+d%%" % p) if p else "0%"))
    o.append("</tr>")
    for target, row in table:
        o.append('<tr><th class="num">%s</th>' % esc(target))
        for p, v in row:
            o.append('<td class="num%s">%s</td>' % (" mid" if p == 0 else "", fmt(v)))
        o.append("</tr>")
    o.append("</table></div>")
    return "\n".join(o) + "\n"


def frag_delay_lines(lines, bd, compact):
    o = ["<details><summary>The %d resulting delay lines (index, delay and buffers)</summary>" % len(lines),
         '<div class="scroll"><table><tr><th class="num">Line</th><th class="num">Required%s (ps)</th><th class="num">Buffers</th>'
         '<th class="num">Delay of buffers (ps)</th>%s</tr>'
         % (" at longest target" if compact else "", "<th>Taps (buffers)</th>" if compact else "")]
    for i, l in enumerate(lines):
        extra = ('<td class="mono">%s</td>' % esc(" / ".join(str(t) for t in l["taps"]))) if compact else ""
        o.append('<tr><td class="num">%d</td><td class="num">%s</td><td class="num">%d</td><td class="num">%s</td>%s</tr>'
                 % (i, fmt(l["target"]), l["buffers"], fmt(l["buffers"] * bd), extra))
    o.append("</table></div></details>")
    return "\n".join(o) + "\n"


# --------------------------------------------------------------------------
# values for {{...}} placeholders
# --------------------------------------------------------------------------
def _value_text(v):
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v) if v else "(none)"
    if v is None:
        return "(none)"
    return str(v)


def make_context(*, parser, args, commandline, table, lines, taps, req_buffers, total_buffers, generated, author):
    bd = float(args.buffer_delay)
    ntarg = len(args.target_delay)
    per_target = int(round((2.0 * args.range) / args.step)) + 1
    n_lines = len(lines)
    ctx = {
        "generated": generated, "author": author, "commandline": commandline,
        "output_dir": args.output_dir, "mode": "compact" if args.compact else "normal",
        "n_lines": n_lines, "req_buffers": req_buffers, "req_ps": fmt(req_buffers * bd),
        "data_buffers": total_buffers, "taps": ", ".join(str(t) for t in taps),
        "n_targets": ntarg, "n_offsets": per_target, "n_delays": ntarg * per_target,
        "lines_note": ("; in compact mode they share %d delay lines, each tapped once per target." % n_lines) if args.compact else
                      ("; after removing duplicates and merging the targets, %d distinct delay lines remain." % n_lines),
    }
    for act in parser._actions:
        if act.dest in ("help",):
            continue
        ctx["arg." + act.dest] = _value_text(getattr(args, act.dest, None))
        ctx["default." + act.dest] = _value_text(act.default)
    return {k: esc(v) for k, v in ctx.items()}


# --------------------------------------------------------------------------
# template assembly
# --------------------------------------------------------------------------
def _read(path):
    with open(path) as f:
        return f.read()


def _find(name, search_dirs, template_path):
    """Path of the first file called `name` in the search folders (then the template's folder), or None."""
    for d in list(search_dirs) + [os.path.dirname(os.path.abspath(template_path))]:
        cand = os.path.join(d, name)
        if os.path.isfile(cand):
            return cand
    return None


def assemble(template_path, ctx, search_dirs, _depth=0, _strip=True):
    text = _read(template_path)
    if _strip:
        text = _COMMENT.sub("", text)
    missing = []

    # {{if:FILE}} ... {{endif}}  keeps the block only if FILE exists;  {{ifnot:FILE}} only if it does not
    def cond(m):
        exists = _find(m.group(2), search_dirs, template_path) is not None
        return m.group(3) if (exists if m.group(1) == "if" else not exists) else ""
    text = _IF.sub(cond, text)

    def sub(m):
        name = m.group(1)
        if name.startswith("include:") or name.startswith("include?:"):
            optional = name.startswith("include?:")
            inc = name.split(":", 1)[1]
            cand = _find(inc, search_dirs, template_path)
            if cand:
                if cand.endswith((".html", ".css")) and _depth < 5:
                    return assemble(cand, ctx, search_dirs, _depth + 1)
                return _read(cand)
            if optional:
                return ""
            missing.append(name)
            return "[missing: %s]" % name
        if name in ctx:
            return str(ctx[name])
        missing.append(name)
        return "[missing: %s]" % name

    out = _PLACEHOLDER.sub(sub, text)
    for n in missing:
        print("pipeline_docs: template placeholder not found: %s (in %s)" % (n, os.path.basename(template_path)), file=sys.stderr)
    return out


def write_html(path, *, parser, args, commandline, table, lines, taps, req_buffers, total_buffers,
               template=None, fragments_dir=None, svg_path=None, generated=None, author=None):
    """Write the fragments, then assemble the template into `path`."""
    template = template or DEFAULT_TEMPLATE
    if not os.path.isfile(template):
        raise SystemExit("pipeline_docs: documentation template not found: %s" % template)
    doc_dir = os.path.dirname(os.path.abspath(path))
    fragments_dir = fragments_dir or os.path.join(doc_dir, "fragments")
    os.makedirs(fragments_dir, exist_ok=True)
    bd = float(args.buffer_delay)
    generated = generated or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    author = author or getpass.getuser()

    frags = {
        "cards.html": frag_cards(n_lines=len(lines), compact=args.compact, req_buffers=req_buffers, bd=bd,
                                 total_buffers=total_buffers, taps=taps),
        "formulas.html": frag_formulas(compact=args.compact, n_lines=len(lines)),
        "delay_table.html": frag_delay_table(table),
        "delay_lines.html": frag_delay_lines(lines, bd, args.compact),
    }
    for name, content in frags.items():
        with open(os.path.join(fragments_dir, name), "w") as f:
            f.write(content)

    ctx = make_context(parser=parser, args=args, commandline=commandline, table=table, lines=lines, taps=taps,
                       req_buffers=req_buffers, total_buffers=total_buffers, generated=generated, author=author)
    # saved so that --rebuild can re-assemble the document later without re-running the generator
    with open(os.path.join(fragments_dir, "context.json"), "w") as f:
        json.dump({"template": os.path.abspath(template), "context": ctx}, f, indent=1)
    with open(path, "w") as f:
        f.write(assemble(template, ctx, [fragments_dir, doc_dir, args.output_dir]))
    return path


def rebuild(output_dir, template=None):
    """Re-assemble <output_dir>/doc/pipeline_doc.html from the saved context, the template and whatever files
    are now in doc/ and doc/fragments/ (e.g. a results.html added after the run)."""
    doc_dir = os.path.join(output_dir, "doc")
    frag_dir = os.path.join(doc_dir, "fragments")
    ctx_file = os.path.join(frag_dir, "context.json")
    if not os.path.isfile(ctx_file):
        raise SystemExit("pipeline_docs: %s not found - run generate_pipeline.py first" % ctx_file)
    with open(ctx_file) as f:
        saved = json.load(f)
    template = template or saved["template"]
    path = os.path.join(doc_dir, "pipeline_doc.html")
    with open(path, "w") as f:
        f.write(assemble(template, saved["context"], [frag_dir, doc_dir, output_dir]))
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Re-assemble the documentation from the template and the files now present, "
                                             "without re-running generate_pipeline.py")
    ap.add_argument("--rebuild", metavar="OUTPUT_DIR", required=True, help="the --output_dir used for the run")
    ap.add_argument("-d", "--doc_template", default=None, help="use this template instead of the one the run used")
    a = ap.parse_args()
    print("wrote " + rebuild(a.rebuild, a.doc_template))
