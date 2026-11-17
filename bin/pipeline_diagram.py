#!/usr/bin/env python3
"""
pipeline_diagram.py - schematic (SVG) of the `pipeline` module, drawn from the
numbers generate_pipeline.py has already worked out.

Open the .svg in any browser (zoom / pan / hover for tooltips).  Click the
legend entries at the top to switch the timing arcs, arrival guides and
buffer-count labels on and off.

Horizontal position inside the delay area is TIME: t = 0 is the moment the L1
latch outputs become valid, and every delay-line box is as long as its delay.
So a box that ends left of a dashed "req arrival" guide has its data waiting
at L2 before the request gets there, and one that ends right of it is late.

Call from generate_pipeline.py:

    import pipeline_diagram
    pipeline_diagram.write_svg("include/pipeline.svg", ...)   # see render()
"""
import datetime
import getpass
import html
import math

# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------
WIRE = "#7d838c"
REQ = "#d9570b"          # request path
REQ_FILL = "#fde2d0"
DATA = "#3f6fb0"
DATA_FILL = "#cfe0f5"
L1_FILL = "#e3f1e3"
L1_EDGE = "#3d7f3d"
L2_FILL = "#ece3f7"
L2_EDGE = "#6a4aa0"
SCAN_FILL = "#f5f1e1"
SCAN_EDGE = "#9a8f60"
CTRL_FILL = "#f2f2f2"
TAP_COLOURS = ["#0b7a75", "#6a3d9a", "#b5179e", "#8c6d00", "#2b6cb0", "#a23b00"]


def esc(s):
    return html.escape(str(s), quote=True)


def fmt(v):
    """Compact number: 400.0 -> 400, 266.666 -> 266.7"""
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return ("%.1f" % v).rstrip("0").rstrip(".")


def render(*, taps, req_buffers, lines, buffer_delay, mux4_delay,
           mousetrap_delay=0.0, clk2q_latch=20.0, delay_ctrl_bits=2,
           commandline="", compact=False, generated=None, author=None):
    """
    taps         tap index into intermediate_req for each mux4 input, D0..D3
    req_buffers  number of buffers in the request delay chain (u_dl_req)
    lines        list of dicts, one per data delay line, in index order:
                   {"target": ps, "buffers": N}                (normal mode)
                   {"target": ps, "buffers": N, "taps": [..]}  (compact mode)
    """
    bd = float(buffer_delay)
    mux = float(mux4_delay)
    mt = float(mousetrap_delay)
    c2q = float(clk2q_latch)
    n = len(lines)
    nt = len(taps)
    S = 3.0 / bd                      # px per ps  (one buffer = 3 px)
    ROW, BH = 14, 8

    # ---- timing numbers (ps after the L1 latch output is valid) ----------
    req_arr = [t * bd + mux + mt for t in taps]      # request closes L2 here
    data_ps = [l["buffers"] * bd for l in lines]
    chain_ps = req_buffers * bd
    t_max = max(data_ps + [chain_ps + mux])
    t_axis = int(math.ceil(t_max / 200.0) * 200)

    # ---- geometry --------------------------------------------------------
    x_scan, w_scan = 120, 70
    x_L1 = x_scan + w_scan + 40
    x0 = x_L1 + 16 + 36
    def xt(t):
        return x0 + t * S
    chain_end = xt(chain_ps)
    x_mux = chain_end + 70
    x_L2 = max(xt(t_max), x_mux + 24) + 95
    x_fb = x_L2 + 44
    xX = x_L2 + 110
    x_fl = xX + 92
    W = x_fl + 60

    R = 60 + 20 * nt                  # time ruler y
    Y0 = R + 98                       # request row y
    def Y(i):
        return Y0 + 26 + i * ROW
    Y_last = Y(n - 1)
    y_bot = Y_last + 34
    H = y_bot + 64

    o = []
    def add(s):
        o.append(s)

    def poly(pts, stroke=WIRE, sw=1, cls="", dash=None, extra=""):
        p = " ".join("%.1f,%.1f" % q for q in pts)
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        c = ' class="%s"' % cls if cls else ""
        add('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s"%s%s %s/>'
            % (p, stroke, sw, d, c, extra))

    def rect(x, y, w, h, fill, stroke, sw=1, rx=0, extra=""):
        add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%s" fill="%s" stroke="%s" stroke-width="%s" %s/>'
            % (x, y, w, h, rx, fill, stroke, sw, extra))

    def text(x, y, s, size=8, anchor="start", fill="#333", cls="", weight="normal",
             halo=True, rot=None, extra=""):
        c = ' class="%s"' % ((cls + " halo") if halo else cls) if (cls or halo) else ""
        r = ' transform="rotate(%s %.1f %.1f)"' % (rot, x, y) if rot is not None else ""
        add('<text x="%.1f" y="%.1f" font-size="%s" text-anchor="%s" fill="%s" font-weight="%s"%s%s %s>%s</text>'
            % (x, y, size, anchor, fill, weight, c, r, extra, esc(s)))

    def dot(x, y, c=WIRE):
        add('<circle cx="%.1f" cy="%.1f" r="1.8" fill="%s"/>' % (x, y, c))

    def arrow_head(x, y, c, direction="right"):
        if direction == "right":
            add('<path d="M%.1f,%.1f l-5,-2.6 l0,5.2 z" fill="%s"/>' % (x, y, c))
        elif direction == "down":
            add('<path d="M%.1f,%.1f l-2.6,-5 l5.2,0 z" fill="%s"/>' % (x, y, c))
        else:  # up
            add('<path d="M%.1f,%.1f l-2.6,5 l5.2,0 z" fill="%s"/>' % (x, y, c))

    # ---------------------------------------------------------------- header
    ts = generated or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    who = author or getpass.getuser()
    text(12, 18, "pipeline", 15, fill="#111", weight="bold", halo=False)
    text(80, 18, "%d data delay lines, %d-buffer request chain, mux4 taps at %s   -   generated %s by %s"
         % (n, req_buffers, ", ".join(str(t) for t in taps), ts, who), 9, fill="#555", halo=False)
    # wrapped command line
    cl = commandline.strip()
    parts, cur = [], ""
    for tok in cl.split(" "):
        if len(cur) + len(tok) > 170:
            parts.append(cur)
            cur = ""
        cur += tok + " "
    if cur:
        parts.append(cur)
    for i, p in enumerate(parts[:3]):
        text(12, 31 + 9 * i, p.strip(), 7, fill="#888", halo=False)

    # legend / toggles (clickable)
    lx, ly = W - 330, 14
    add('<g class="legend" font-size="8" fill="#333">')
    for i, (cls, label) in enumerate([("arcs", "timing arcs"), ("guides", "req arrival guides"),
                                      ("lbls", "buffer labels")]):
        x = lx + i * 108
        add('<g style="cursor:pointer" onclick="tg(\'%s\')"><rect x="%d" y="%d" width="9" height="9" fill="#fff" stroke="#555"/>'
            '<path d="M%d,%d l2.5,3 l4,-6" stroke="#222" fill="none"/><text x="%d" y="%d">%s</text></g>'
            % (cls, x, ly - 8, x + 1.5, ly - 3, x + 13, ly, label))
    add("</g>")
    text(lx, ly + 12, "orange = request path   blue = data path   (click items above to toggle, hover boxes for numbers)",
         7, fill="#777", halo=False)

    # ----------------------------------------------------------- time ruler
    step = 200 if t_axis > 1000 else 100
    poly([(x0, R), (xt(t_axis), R)], "#444", 1)
    for t in range(0, t_axis + 1, step):
        major = (t // step) % 2 == 0
        poly([(xt(t), R), (xt(t), R + (5 if major else 3))], "#444", 1)
        if major:
            text(xt(t), R + 14, str(t), 7, "middle", "#444", halo=False)
    text(x0 - 8, R + 4, "ps after L1 Q valid", 7, "end", "#444", halo=False)

    # --------------------------------------- timing arcs + guides (request)
    add('<g class="guides">')
    poly([(x0, R - 22 - 20 * (nt - 1) - 6), (x0, y_bot)], "#999", 0.8, dash="2 3")
    for k in range(nt):
        c = TAP_COLOURS[k % len(TAP_COLOURS)]
        xk = xt(req_arr[k])
        poly([(xk, R - 20 - 20 * k), (xk, y_bot)], c, 0.9, dash="4 3")
        text(xk, y_bot + 11, "D%d  %s" % (k, fmt(req_arr[k])), 7, "middle", c, halo=True)
    add("</g>")
    add('<g class="arcs">')
    for k in range(nt):
        c = TAP_COLOURS[k % len(TAP_COLOURS)]
        xk = xt(req_arr[k])
        yk = R - 20 - 20 * k
        add('<path d="M%.1f,%.1f Q%.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="1.6"/>'
            % (x0, yk, (x0 + xk) / 2, yk - 17, xk, yk, c))
        arrow_head(xk, yk, c)
        lab = "tap%d -> mux D%d:  %d bufs x %s + mux4 %s" % (k, k, taps[k], fmt(bd), fmt(mux))
        if mt:
            lab += " + mousetrap %s" % fmt(mt)
        lab += " = %s ps" % fmt(req_arr[k])
        text(xk + 8, yk + 3, lab, 7.5, fill=c, weight="bold")
    add("</g>")

    # ------------------------------------------------------- scan chain block
    y_s0, y_s1 = Y(0) - 9, Y_last + 9
    add("<g>")
    add("<title>scan_chain[%d:0]: shift register clocked by CLK.\nSE=1: shifts SI -> ... -> SO.\n"
        "SE=0: loads {delay_ctrl, req_out, word_out} when l2_fired.\nbits [%d:0]=word_in, [%d]=req_in, [%d:%d]=delay_ctrl</title>"
        % (n + delay_ctrl_bits, n - 1, n, n + delay_ctrl_bits, n + 1))
    rect(x_scan, y_s0, w_scan, y_s1 - y_s0, SCAN_FILL, SCAN_EDGE, 1.2, 2)
    text(x_scan + w_scan / 2 + 3, (y_s0 + y_s1) / 2,
         "scan_chain[%d:0]  shift register" % (n + delay_ctrl_bits), 9, "middle", "#6b6330", halo=False, rot=-90)
    add("</g>")
    # clock / SE stubs on top edge
    for dx, nm in ((16, "CLK"), (52, "SE")):
        poly([(x_scan + dx, Y0 + 10), (x_scan + dx, y_s0)], "#555", 1)
        arrow_head(x_scan + dx, y_s0, "#555", "down")
        text(x_scan + dx, Y0 + 7, nm, 7.5, "middle", "#333")
    # SO leaves through the top edge (bit 0); SI enters bottom-left
    poly([(x_scan + 34, y_s0), (x_scan + 34, Y0 + 10)], "#555", 1)
    arrow_head(x_scan + 34, Y0 + 10, "#555", "up")
    text(x_scan + 34, Y0 + 7, "SO", 7.5, "middle", "#333")
    poly([(x_scan - 12, y_s1 - 4), (x_scan, y_s1 - 4)], "#555", 1)
    text(x_scan - 14, y_s1 - 1, "SI", 8, "end", "#333")
    # delay_ctrl and req_in leave the top of the left edge and run up the margin
    x_rq, x_ds = x_scan - 24, x_scan - 38
    y_rq, y_ds = y_s0 + 6, y_s0 + 16
    poly([(x_scan, y_rq), (x_rq, y_rq), (x_rq, Y0), (x_L1, Y0)], REQ, 1.4)
    text(x_scan + 3, y_rq + 3, "req_in (bit %d)" % n, 6.5, fill="#6b6330", halo=False)
    y_sel = Y0 - 72
    x_mux_c = x_mux + 12
    poly([(x_scan, y_ds), (x_ds, y_ds), (x_ds, y_sel), (x_mux_c, y_sel), (x_mux_c, Y0 - 53)], REQ, 1.4)
    text(x_scan + 3, y_ds + 3, "delay_ctrl[%d:0]" % (delay_ctrl_bits - 1), 6.5, fill="#6b6330", halo=False)
    text(x_ds + 3, y_sel - 4, "delay_ctrl[%d:0] (S1,S0)" % (delay_ctrl_bits - 1), 7, fill=REQ)

    # ------------------------------------------------- enable_l1 synchroniser
    ffx1, ffx2, ffy = x_scan + 36, x_scan + 76, Y0 - 52
    text(ffx1 - 4, ffy + 12, "ENABLE_L1", 7.5, "end", "#333")
    for fx in (ffx1, ffx2):
        rect(fx, ffy, 26, 18, CTRL_FILL, "#666", 1)
        add('<path d="M%.1f,%.1f l4,-3 l-4,-3" transform="translate(%.1f,%.1f)" fill="none" stroke="#666"/>'
            % (0, 0, fx + 1, ffy + 17))
        text(fx + 13, ffy + 12, "FF", 8, "middle", "#333", halo=False)
    poly([(ffx1 - 3, ffy + 9), (ffx1, ffy + 9)], "#555", 1)
    poly([(ffx1 + 26, ffy + 9), (ffx2, ffy + 9)], "#555", 1)
    text(ffx1 + 13, ffy - 3, "2-FF sync (CLK)", 6.5, "middle", "#555", halo=False)
    xl1e = x_L1 + 8
    poly([(ffx2 + 26, ffy + 9), (xl1e, ffy + 9), (xl1e, Y0 - 9)], "#555", 1.2)
    arrow_head(xl1e, Y0 - 9, "#555", "down")
    text(xl1e + 4, ffy + 6, "enable_l1_sync", 7, fill="#333")

    # ------------------------------------------------------- L1 / L2 columns
    for (xc, fill, edge, nm1, nm2) in (
            (x_L1, L1_FILL, L1_EDGE, "L1 latches", "en = enable_l1_sync"),
            (x_L2, L2_FILL, L2_EDGE, "L2 latches", "en = enable_l2")):
        rect(xc - 4, Y0 - 9, 24, Y_last - Y0 + 18, fill, edge, 1.2, 3, 'opacity="0.55"')
    text(x_L1 + 8, Y_last + 19, "L1 latches", 7.5, "middle", L1_EDGE, halo=False)
    text(x_L1 + 8, Y_last + 28, "(always_latch l1)", 6.5, "middle", L1_EDGE, halo=False)
    text(x_L2 + 8, Y_last + 19, "L2 latches", 7.5, "middle", L2_EDGE, halo=False)
    text(x_L2 + 8, Y_last + 28, "(always_latch l2)", 6.5, "middle", L2_EDGE, halo=False)

    def latch(x, y, label, stroke, fill):
        rect(x, y - 4, 16, 8, fill, stroke, 0.8, 1)
        if label != "":
            text(x + 8, y + 2.6, label, 6, "middle", "#222", halo=False)

    # ------------------------------------------------------------ request row
    latch(x_L1, Y0, "req", L1_EDGE, "#fff")
    poly([(x_L1 + 16, Y0), (x0, Y0)], REQ, 1.4)
    add("<g>")
    add("<title>u_dl_req[%d:1]: request delay chain of %d buffers (%s ps).\nTaps (intermediate_req[]): %s</title>"
        % (req_buffers, req_buffers, fmt(chain_ps), ", ".join(str(t) for t in taps)))
    rect(x0, Y0 - BH / 2, chain_ps * S, BH, REQ_FILL, REQ, 1)
    add('<rect x="%.1f" y="%.1f" width="%.1f" height="%d" fill="url(#bufpat)"/>' % (x0, Y0 - BH / 2, chain_ps * S, BH))
    add("</g>")
    text(x0 + 3, Y0 + BH / 2 + 8, "request chain: %d bufs = %s ps" % (req_buffers, fmt(chain_ps)), 7, fill=REQ)

    # mux4 symbol
    mx0, mx1 = x_mux, x_mux + 24
    add("<g><title>u_mux (mux4): selects tap by delay_ctrl; adds %s ps</title>" % fmt(mux))
    add('<path d="M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f L%.1f,%.1f Z" fill="#fff" stroke="%s" stroke-width="1.4"/>'
        % (mx0, Y0 - 58, mx1, Y0 - 48, mx1, Y0 - 20, mx0, Y0 - 8, REQ))
    text((mx0 + mx1) / 2, Y0 - 30, "mux4", 7, "middle", REQ, halo=False)
    add("</g>")
    lv = [Y0 - 52 + k * (36.0 / max(nt - 1, 1)) for k in range(nt)]
    for k in range(nt):
        c = TAP_COLOURS[k % len(TAP_COLOURS)]
        xk = xt(taps[k] * bd)
        poly([(xk, Y0 - BH / 2), (xk, lv[k]), (mx0, lv[k])], c, 1.2)
        dot(xk, Y0, c)
        text(mx0 - 3, lv[k] - 2, "D%d" % k, 6.5, "end", c, halo=False)
    # mux output -> L2 req latch
    zy = Y0 - 34
    poly([(mx1, zy), (x_L2 - 14, zy), (x_L2 - 14, Y0), (x_L2, Y0)], REQ, 1.4)
    text(mx1 + 4, zy - 3, "l2_req", 7, fill=REQ)
    latch(x_L2, Y0, "req", L2_EDGE, "#fff")

    # ------------------------------------------------------------- data rows
    add('<g class="rows">')
    for i, l in enumerate(lines):
        y = Y(i)
        N = l["buffers"]
        dps = data_ps[i]
        w = dps * S
        tip = ["delayline %d: %s ps target, %d buffers = %s ps" % (i, fmt(l["target"]), N, fmt(dps)),
               "u_delay%d  ->  delayed_data[%d]" % (i, i), ""]
        for k in range(nt):
            m = req_arr[k] - dps
            tip.append("vs req tap D%d (%s ps): data %s by %s ps"
                       % (k, fmt(req_arr[k]), "EARLY" if m >= 0 else "LATE", fmt(abs(m))))
        add('<g class="dl"><title>%s</title>' % esc("\n".join(tip)))
        poly([(x_scan + w_scan, y), (x_L1, y)], WIRE, 0.8)
        latch(x_L1, y, str(i), L1_EDGE, "#fff")
        poly([(x_L1 + 16, y), (x0, y)], DATA, 0.8)
        rect(x0, y - BH / 2, w, BH, DATA_FILL, DATA, 0.9, 1, 'class="box"')
        add('<rect x="%.1f" y="%.1f" width="%.1f" height="%d" fill="url(#bufpat)"/>' % (x0, y - BH / 2, w, BH))
        poly([(x0 + w, y), (x_L2, y)], DATA, 0.8)
        latch(x_L2, y, str(i), L2_EDGE, "#fff")
        if compact and l.get("taps"):
            for k, tp in enumerate(l["taps"]):
                c = TAP_COLOURS[k % len(TAP_COLOURS)]
                poly([(xt(tp * bd), y - BH / 2 - 2), (xt(tp * bd), y + BH / 2 + 2)], c, 1.2)
        add("</g>")
        text(x0 + w + 4, y + 2.5, "%d bufs  %s ps" % (N, fmt(dps)), 6.2, fill="#4a5a70", cls="lbls")
    add("</g>")

    # --------------------------------------------------- control: XNOR etc.
    # req_out from L2 req latch Q
    Jx = x_L2 + 30
    poly([(x_L2 + 16, Y0), (Jx, Y0)], REQ, 1.4)
    # last_l2_req latch
    LLx, LLy = x_L2 + 52, Y0 - 32
    rect(LLx, LLy, 34, 18, CTRL_FILL, "#666", 1.1, 2)
    text(LLx + 17, LLy + 12, "latch", 7.5, "middle", "#333", halo=False)
    text(LLx + 17, LLy + 27, "last_l2_req", 6.5, "middle", "#333", halo=False)
    poly([(Jx, Y0 - 23), (LLx, Y0 - 23)], REQ, 1.2)
    dot(Jx, Y0 - 23, REQ)
    poly([(LLx + 17, LLy + 18 + 7), (LLx + 17, LLy + 18)], "#555", 1)
    text(LLx + 17, LLy + 40, "en = PRIME_L2", 6.5, "middle", "#333", halo=False)
    # XNOR
    yA, yB = Y0 - 60, Y0 - 46
    yX = (yA + yB) / 2
    add("<g><title>u_en_l2: XNOR2(req_out, last_l2_req) = enable_l2.\nHigh while L2 is open (req_out == last_l2_req); "
        "goes low (closing L2) once the new request has passed through L2.</title>")
    add('<path d="M%.1f,%.1f Q%.1f,%.1f %.1f,%.1f Q%.1f,%.1f %.1f,%.1f Q%.1f,%.1f %.1f,%.1f Z" fill="#fff" stroke="#555" stroke-width="1.2"/>'
        % (xX, yX - 11, xX + 9, yX, xX, yX + 11, xX + 22, yX + 11, xX + 30, yX, xX + 22, yX - 11, xX, yX - 11))
    add('<circle cx="%.1f" cy="%.1f" r="2.6" fill="#fff" stroke="#555"/>' % (xX + 33, yX))
    text(xX + 14, yX + 3, "XNOR", 6.5, "middle", "#333", halo=False)
    add("</g>")
    # wires into XNOR: A = req_out, B = last_l2_req
    poly([(Jx, Y0), (Jx, yA), (xX + 2, yA)], REQ, 1.4)
    poly([(LLx + 34, LLy + 9), (LLx + 46, LLy + 9), (LLx + 46, yB), (xX + 2, yB)], REQ, 1.2)
    text(xX - 2, yA - 3, "req_out", 6.5, "end", REQ)
    text(xX - 2, yB + 9, "last_l2_req", 6.5, "end", REQ)
    # XNOR -> enable_l2 -> L2 column enable (top)
    ex = xX + 40
    y_en = Y0 - 80
    poly([(xX + 36, yX), (ex, yX), (ex, y_en), (x_L2 + 8, y_en), (x_L2 + 8, Y0 - 9)], REQ, 1.5)
    arrow_head(x_L2 + 8, Y0 - 9, REQ, "down")
    text(ex + 10, y_en + 14, "enable_l2", 7.5, fill=REQ, weight="bold")
    # INV -> l2_fired
    iy = yX
    dot(ex, iy, REQ)
    add('<g><title>u_l2_fired: l2_fired = !enable_l2\nHigh once L2 has captured, lets scan_chain reload</title>'
        '<path d="M%.1f,%.1f l0,12 l14,-6 z" fill="#fff" stroke="#555" stroke-width="1.2"/>'
        '<circle cx="%.1f" cy="%.1f" r="2.2" fill="#fff" stroke="#555"/></g>'
        % (ex + 8, iy - 6, ex + 25, iy))
    poly([(ex, iy), (ex + 8, iy)], REQ, 1.2)
    poly([(ex + 27, iy), (x_fl, iy), (x_fl, y_bot + 16)], "#555", 1.2)
    text(x_fl + 4, iy - 3, "l2_fired", 7, fill="#333")
    text(ex + 16, iy + 16, "INV", 6.5, "middle", "#333", halo=False)

    # annotated loop arc (mousetrap): the request arriving at the (already open) L2 req latch D
    # goes through the latch (D-Q) and the XNOR; the endpoint is the L2 column, which it closes.
    # Only drawn when mousetrap_delay > 0; at 0 the request delay simply ends at the L2 req latch D.
    lc = "#b00020"
    if mt > 0:
        def bez(p0, c1, c2, p3, t=0.5):
            return tuple(((1 - t) ** 3) * p0[i] + 3 * ((1 - t) ** 2) * t * c1[i]
                         + 3 * (1 - t) * t * t * c2[i] + t ** 3 * p3[i] for i in (0, 1))
        P0 = (x_L2 - 14, Y0 - 16)               # l2_req at the L2 req latch D input
        PA = (xX + 2, yA)                        # XNOR req_out input pin
        PO = (xX + 36, yX)                       # XNOR output pin
        P2 = (x_L2 + 14, Y0 - 24)               # endpoint: the L2 latch column (closes it)
        s1 = (P0, (P0[0], y_en - 40), (PA[0] - 30, y_en - 28), PA)          # 1: latch D -> Q -> XNOR pin
        s3 = (PO, (PO[0] + 30, y_en - 8), (P2[0] + 45, y_en - 68), P2)      # 3: XNOR out -> L2 closed
        add('<g class="arcs" fill="none" stroke="%s" stroke-width="1.7" stroke-dasharray="5 2">' % lc)
        add('<path d="M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f"/>'
            % (s1[0][0], s1[0][1], s1[1][0], s1[1][1], s1[2][0], s1[2][1], s1[3][0], s1[3][1]))
        add('<path d="M%.1f,%.1f Q%.1f,%.1f %.1f,%.1f"/>'                    # 2: across the XNOR
            % (PA[0], PA[1] - 2, (PA[0] + PO[0]) / 2, yA - 24, PO[0], PO[1] - 2))
        add('<path d="M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f"/>'
            % (s3[0][0], s3[0][1] - 2, s3[1][0], s3[1][1], s3[2][0], s3[2][1], s3[3][0], s3[3][1]))
        add("</g>")
        add('<g class="arcs">')
        for q in (P0, PA, PO):
            dot(q[0], q[1], lc)
        arrow_head(P2[0], P2[1], lc, "down")
        m1, m3 = bez(*s1), bez(*s3)
        m2 = ((PA[0] + PO[0]) / 2, yA - 13)
        for (mx, my), num in ((m1, "1"), (m2, "2"), (m3, "3")):
            add('<circle cx="%.1f" cy="%.1f" r="5.5" fill="#fff" stroke="%s" stroke-width="1.2"/>' % (mx, my, lc))
            text(mx, my + 2.7, num, 7.5, "middle", lc, weight="bold", halo=False)
        lx0 = x_L2 - 34
        text(lx0, y_en - 92, "mousetrap loop (L2 is already open; this closes it):", 7.5, "start", lc, weight="bold")
        text(lx0, y_en - 82, "(1) latch D-Q  |  (2) XNOR2  |  (3) enable_l2 -> L2 closed", 7, "start", lc)
        text(lx0, y_en - 73, "whole loop 1+2+3 = mousetrap_delay = %s ps" % fmt(mt), 7, "start", lc)
        add("</g>")
    else:
        add('<g class="arcs">')
        text(x_L2 - 34, y_en - 82, "mousetrap_delay = 0: the request delay ends at the L2 req latch D (no loop arc)",
             7, "start", "#777")
        add("</g>")

    # ------------------------------------------------ feedback to scan chain
    ymid = Y(n // 2)
    xs_fb, xs_fl = x_scan + w_scan * 0.72, x_scan + w_scan * 0.30
    add("<g><title>word_out[%d:0], req_out (and delay_ctrl) are fed back into scan_chain when l2_fired &amp; !SE</title>" % (n - 1))
    poly([(x_L2 + 20, ymid), (x_fb, ymid), (x_fb, y_bot), (xs_fb, y_bot), (xs_fb, y_s1)], "#444", 3)
    arrow_head(xs_fb, y_s1, "#444", "up")
    add("</g>")
    text(x_fb + 6, ymid + 3, "word_out[%d:0], req_out" % (n - 1), 7.5, fill="#444")
    text((x_fb + xs_fb) / 2, y_bot - 4, "recirculate into scan_chain when l2_fired and SE=0", 7.5, "middle", "#444")
    poly([(x_fl, y_bot + 16), (xs_fl, y_bot + 16), (xs_fl, y_s1)], "#555", 1.2)
    arrow_head(xs_fl, y_s1, "#555", "up")
    text((x_fl + xs_fl) / 2, y_bot + 26, "l2_fired (scan load enable)", 7, "middle", "#555")

    # ------------------------------------------------------------- footer
    total = req_buffers + sum(l["buffers"] for l in lines)
    text(12, H - 20,
         "%d buffers in total (%d data, %d request).  Buffer = %s ps, mux4 = %s ps, L1 clk->Q = %s ps, mousetrap loop = %s ps.  "
         "NRESET asynchronously clears every latch and flop (not drawn)."
         % (total, total - req_buffers, req_buffers, fmt(bd), fmt(mux), fmt(c2q), fmt(mt)), 8, fill="#555", halo=False)
    text(12, H - 8, "Box length = delay.  Guides: where each mux4 tap's request reaches the L2 latch; a data box ending left of the guide arrives early.",
         8, fill="#555", halo=False)

    # ----------------------------------------------------------- assemble
    head = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
        'font-family="Helvetica, Arial, sans-serif">\n'
        "<style>\n"
        ".halo{paint-order:stroke;stroke:#fff;stroke-width:2.4px;stroke-linejoin:round}\n"
        ".dl:hover .box{stroke:#000;stroke-width:1.6;fill:#ffe9a8}\n"
        ".dl:hover{cursor:help}\n"
        "</style>\n"
        "<defs><pattern id=\"bufpat\" x=\"%.2f\" y=\"0\" width=\"%.3f\" height=\"%d\" patternUnits=\"userSpaceOnUse\">"
        "<line x1=\"0\" y1=\"0\" x2=\"0\" y2=\"%d\" stroke=\"#000\" stroke-opacity=\"0.35\" stroke-width=\"0.6\"/></pattern></defs>\n"
        '<rect width="100%%" height="100%%" fill="#ffffff"/>\n'
        % (W, H, W, H, x0, bd * S, BH, BH))
    tail = ("\n<script><![CDATA[\nfunction tg(c){document.querySelectorAll('.'+c).forEach(function(e){"
            "e.style.display=(e.style.display==='none')?'':'none';});}\n]]></script>\n</svg>\n")
    return head + "\n".join(o) + tail


def write_svg(path, **kw):
    svg = render(**kw)
    with open(path, "w") as f:
        f.write(svg)
    return path
