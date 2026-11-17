#!/usr/bin/env python3
import argparse
import datetime
import getpass
import math
import os
import sys
sys.path.append(os.path.join(__file__))
import pipeline_diagram

cli = argparse.ArgumentParser()
cli.add_argument("-t","--target_delay", help="Add target target delay ", type=int, action="append", default=[])
cli.add_argument("-r","--range", help="Range of experiments (+- percent) default 50 percent ", type=int, default=50)
cli.add_argument("-s","--step", help="step size within range ( percent) ", type=int, default=5)
cli.add_argument("-b","--buffer_delay", help="Typical buffer delay", type=float, default=9)
cli.add_argument("-m","--mousetrap_delay", help="Delay between req hitting latch D and disabling latch", type=float, default=0)
cli.add_argument("-x","--mux4_delay", help="Delay through mux4 (assuming select preset)", type=float, default=20)
cli.add_argument("-l","--clk2q_latch", help="Delay through mux4 (assuming select preset)", type=float, default=20)
cli.add_argument("-c","--compact", help="Share delay buffer across target_delays", action="store_true",  default=False)



args=cli.parse_args()
delays_required=[]

commandline=sys.argv[0]+" "
for td in args.target_delay:
    commandline+="--target_delay="+str(td)+" "
commandline+="--range="+str(args.range)+" "
commandline+="--step="+str(args.step)+" "
commandline+="--buffer_delay="+str(args.buffer_delay)+" "
commandline+="--mux4_delay="+str(args.mux4_delay)+" "
commandline+="--mousetrap_delay="+str(args.mousetrap_delay)+" "
commandline+="--clk2q_latch="+str(args.clk2q_latch)+" "
commandline+="--compact="+str(args.clk2q_latch)
if args.compact:
    commandline+=" --compact"
total_buffers=0
diagram_lines=[]

for target in args.target_delay:
    for p in range(args.range, -args.range - args.step , -args.step):

        value=target/((p/100.0)+1)
        value=int(value*1000.0)
        value=value/1000.0
        if not args.compact:
            if value not in delays_required:
                delays_required.append(value)
        else:
            delays_required.append(value)

num=0     
if not args.compact:
    delays_required.sort(key=float)     
if not os.path.exists("include"):
    os.makedirs("include")
if not os.path.exists("setup"):    
    os.makedirs("setup")
if not os.path.exists("doc"):    
    os.makedirs("doc")

with open("setup/core.setup","w") as fdelay:
    fdelay.write("export VE_HOME="+os.path.abspath(os.path.dirname(sys.argv[0])+"/..")+"\n")
    fdelay.write("export LOGICAL_PATH=${VE_HOME}/logical\n")
    fdelay.write("export CONSTRAINTS_PATH=\n")
    fdelay.write("export IMPLEMENTATION_DIR=${BASE_DIR}/implementation\n")
    fdelay.write("export INCLUDE_PATH=${BASE_DIR}/include\n")
    fdelay.write("export MMMC_FILE=\n")
    fdelay.write("export LEF_FILES=\"\"\n")
    fdelay.write("export PRIMARY_LIB=\"\"\n")


with open("setup/pipeline.setup","w") as fdelay:
    fdelay.write("#!/usr/bin/env bash\n")
    fdelay.write("# DO NOT MODIFY ---------------------------------------------\n")
    fdelay.write("SOURCE=${BASH_SOURCE[0]}\n")
    fdelay.write("while [ -L \"$SOURCE\" ]; do  # resolve $SOURCE until the file is no longer a symlink\n")
    fdelay.write("  BASE_DIR=$( cd -P \"$( dirname \"$SOURCE\" )\" >/dev/null 2>&1 && pwd )\n")
    fdelay.write("  SOURCE=$(readlink \"$SOURCE\")\n")
    fdelay.write("  [[ $SOURCE != /* ]] && SOURCE=$DIR/$SOURCE # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located\n")
    fdelay.write("done\n")
    fdelay.write("BASE_DIR=$( cd -P \"$( dirname \"$SOURCE\" )\" >/dev/null 2>&1 && pwd )\n")
    fdelay.write("#---------------------------------------------\n")
    fdelay.write("export BASE_DIR=`dirname $BASE_DIR`\n")
    fdelay.write(". ${BASE_DIR}/setup/core.setup\n")
    fdelay.write("export TOP_DESIGN=pipeline\n")

with open("setup/VE_block.setup","w") as fdelay:
    fdelay.write("#!/usr/bin/env bash\n")
    fdelay.write("# DO NOT MODIFY ---------------------------------------------\n")
    fdelay.write("SOURCE=${BASH_SOURCE[0]}\n")
    fdelay.write("while [ -L \"$SOURCE\" ]; do  # resolve $SOURCE until the file is no longer a symlink\n")
    fdelay.write("  BASE_DIR=$( cd -P \"$( dirname \"$SOURCE\" )\" >/dev/null 2>&1 && pwd )\n")
    fdelay.write("  SOURCE=$(readlink \"$SOURCE\")\n")
    fdelay.write("  [[ $SOURCE != /* ]] && SOURCE=$DIR/$SOURCE # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located\n")
    fdelay.write("done\n")
    fdelay.write("BASE_DIR=$( cd -P \"$( dirname \"$SOURCE\" )\" >/dev/null 2>&1 && pwd )\n")
    fdelay.write("#---------------------------------------------\n")
    fdelay.write("export BASE_DIR=`dirname $BASE_DIR`\n")
    fdelay.write(". ${BASE_DIR}/setup/core.setup\n")
    fdelay.write("export TOP_DESIGN=VE_block\n")

with open("setup/required_delays.tcl","w") as fdelay:
    fdelay.write("# This contains the required delay for each part of the experiment\n")
    dl=0
    for value in delays_required:
        fdelay.write("set $required_delay("+str(dl)+") "+str(value)+"\n")
        dl=dl+1
    
    fdelay.close()

with open("include/delays.v","w") as fdelay:
    longest_req = max(args.target_delay) 
    gc=math.ceil((longest_req-args.mux4_delay-args.mousetrap_delay)/args.buffer_delay)
    req_buffers=gc
    tap_delays=sorted(args.target_delay)
    taps = []
    for d in tap_delays:
        taps.append( math.ceil((d - args.mux4_delay)/args.buffer_delay) )
    
    fdelay.write("/**************************************************\n* Generated: "+str(datetime.datetime.now())+"\n* Generated by: "+getpass.getuser()+"\n* COmmand line:\n*    "+commandline+"\n*********************************************/\n\n")
    fdelay.write("(* preserve = \"true\" *) logic ["+str(gc)+":0] intermediate_req;\n")
    fdelay.write("(* preserve = \"true\" *) `LOGIC_BUFFER u_dl_req["+str(gc)+":1] (.Z(intermediate_req["+str(gc )+":1]), .A(intermediate_req["+str(gc-1)+":0]) );\n")
    fdelay.write("(* preserve = \"true\" *) `LOGIC_MUX4  u_mux (.Z(l2_req),\n") 
    fdelay.write("    .D0(intermediate_req["+str(taps[0])+"]), .D1(intermediate_req["+str(taps[1])+"]), .D2(intermediate_req["+str(taps[2])+"]), .D3(intermediate_req["+str(taps[3])+"]),\n") 
    fdelay.write("    .S0(delay_ctrl[0]), .S1(delay_ctrl[1])\n") 
    fdelay.write(");\n\n")


    if(args.compact==False):
        for value in delays_required:
            gc=math.ceil((value-args.mousetrap_delay)/args.buffer_delay)
            total_buffers=total_buffers+gc
            diagram_lines.append(dict(target=value, buffers=gc))
            fdelay.write("// delayline "+str(num)+" Target: "+str(round(value,7))+" num_buffers "+str(gc)+" -> "+str(gc* args.buffer_delay)+"\n")
            fdelay.write("(* preserve = \"true\" *) wire["+str(gc)+":1] delayElement"+str(num)+";\n")
            fdelay.write("(* preserve = \"true\" *) `LOGIC_BUFFER  u_delay"+str(num)+"["+str(gc)+":1] (.Z({delayed_data["+str(num)+"],delayElement"+str(num)+"["+str(gc-1)+":1]}),   .A({delayElement"+str(num)+"["+str(gc-1)+":1],intermediate_data["+str(num)+"]}));\n\n")
            num=num+1
    else:
        num_delaylines = int(((2*args.range) / args.step) + 1)
        print(num_delaylines)
        print(len(delays_required))
        last_tap=len(args.target_delay)-1
        num=0   
        
        for dl in range(num_delaylines):
            tap_delays=[]
            gc=[]
            for tap in range (len(args.target_delay)):
                value=delays_required[(tap*num_delaylines)+dl]
                value=value-args.mux4_delay
                tap_delays.append(value)    
                gc.append(int(((value-args.mousetrap_delay)/args.buffer_delay)+0.5))

            value=delays_required[(last_tap*num_delaylines)+dl]            
            fdelay.write("// delayline "+str(num)+" Target: "+str(round(value,7))+" num_buffers "+str(gc[last_tap])+" -> "+str(gc[last_tap]* args.buffer_delay)+"\n")
            fdelay.write("(* preserve = \"true\" *) wire["+str(gc)+":1] delayElement"+str(num)+";\n")
            fdelay.write("(* preserve = \"true\" *) `LOGIC_BUFFER  u_delay"+str(num)+"["+str(gc[last_tap])+":1] (.Z(delayElement"+str(num)+"["+str(gc[last_tap])+":1]}),   .A({delayElement"+str(num)+"["+str(gc[last_tap]-1)+":1],intermediate_data["+str(num)+"]}));\n")
            fdelay.write("(* preserve = \"true\" *) d`LOGIC_MUX4  u_mux_dl"+str(num)+" (\n    .Z(delayed_data["+str(num)+"]),\n") 
            for d in range(4):
                if ( d< len(tap_delays) ) :
                    fdelay.write("    .D"+str(d)+"(delayElement"+str(num)+"["+str(gc[d])+"]),\n")
                else:
                    fdelay.write("    .D"+str(d)+"(1'b0),\n")
            fdelay.write("    .S0(delay_ctrl[0]),\n    .S1(delay_ctrl[1])\n);\n") 
            num=num+1
            total_buffers=total_buffers+gc[last_tap]
            diagram_lines.append(dict(target=value, buffers=gc[last_tap], taps=list(gc)))
        fdelay.close()

    with open("include/system_defines","w") as fdelay:  
        fdelay.write("/**************************************************\n* Generated: "+str(datetime.datetime.now())+"\n* Generated by: "+getpass.getuser()+"\n* Command line\n*    "+commandline+"\n*********************************************/\n\n")
        fdelay.write("`ifndef SYSTEM_DEFINES\n  `define SYSTEM_DEFINES 1\n")
        fdelay.write("  `define NUM_EXPS 7\n")
        fdelay.write("  `define DELAY_CTRL_BITS 2\n")
        if(args.compact==False):
            delays=len(delays_required)
        else:
            delays=int(len(delays_required)/len(args.target_delay))

        fdelay.write("  `define DATAPATH_WIDTH "+str(delays)+"\n") 
        fdelay.write("  //The following cells can be substituted to technology map to a specific library\n")
        fdelay.write("  `define IP_DRIVER    PAD_DRIVER_I\n")
        fdelay.write("  `define IO_DRIVER    PAD_DRIVER_IO\n")
        fdelay.write("  `define LOGIC_BUFFER BUFFER\n")
        fdelay.write("  `define LOGIC_MUX4   MUX4\n")
        fdelay.write("  `define LOGIC_XNOR2  XNOR2\n")
        fdelay.write("  `define LOGIC_INV    INV\n")
        fdelay.write("`endif\n")
        fdelay.close()
      


pipeline_diagram.write_svg("doc/pipeline.svg", taps=taps, req_buffers=req_buffers, lines=diagram_lines,
    buffer_delay=args.buffer_delay, mux4_delay=args.mux4_delay, mousetrap_delay=args.mousetrap_delay,
    clk2q_latch=args.clk2q_latch, delay_ctrl_bits=2, commandline=commandline, compact=args.compact)
print("Total buffers used "+str(total_buffers))
