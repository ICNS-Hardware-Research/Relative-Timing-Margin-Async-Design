`timescale 1ps/1ps

//`define  DEBUG_LINES 300
`ifdef DEBUG_LINES
    `define DELAY_CTRL_BITS 2
    `define DATAPATH_WIDTH 6
`else
    `include "system_defines"
`endif


module pipeline 
#(
    parameter DELAY_CTRL_BITS = `DELAY_CTRL_BITS,
    parameter DATAPATH_WIDTH  = `DATAPATH_WIDTH
)
(
	input NRESET,
	input ENABLE_L1,
	input PRIME_L2,
	input CLK,
	input SE,
	input SI,
	output SO
);
    //The following is ctritical to make design use latch with async reset
	//synthesis  asynchro_reset NRESET

	logic [DELAY_CTRL_BITS - 1: 0] delay_ctrl;
	logic [DATAPATH_WIDTH-1:0] word_in;
	logic [DATAPATH_WIDTH-1:0] word_out;
	logic req_in;
	logic req_out;
	logic enable_l1_sync_ff1, enable_l1_sync;

    //All of these need to be preseved 
	logic [DATAPATH_WIDTH-1:0] intermediate_data;
    logic [DATAPATH_WIDTH-1:0] source_data;
    logic [DATAPATH_WIDTH-1:0] delayed_data;

	logic  l2_req ;
	logic last_l2_req, enable_l2;
	logic [DATAPATH_WIDTH + DELAY_CTRL_BITS : 0] scan_chain;
 
   

    //the delays.v file is produced by analysis of the DEBUG output from above
    `include "delays.v"

	assign word_in   = scan_chain[ DATAPATH_WIDTH -1: 0] ;
	assign req_in    = scan_chain[ DATAPATH_WIDTH ];


   assign delay_ctrl = scan_chain[ DATAPATH_WIDTH+ DELAY_CTRL_BITS:DATAPATH_WIDTH+1];

    
	always_latch begin:  l1
		if(NRESET==0) begin
			{intermediate_data,intermediate_req[0]} = 0;
		end else begin
			if(enable_l1_sync)
				{intermediate_data, intermediate_req[0]} = {word_in, req_in};
		end
	end

    // these are the trigger snap of the mousetrap. They are done as standard cells to make the flow easier in balancing enable_l2
	`LOGIC_XNOR2 u_en_l2    (.Z(enable_l2), .A(req_out), .B(last_l2_req))  ;
	`LOGIC_INV   u_l2_fired (.Z(l2_fired), .A(enable_l2)) ;// l2_fired = !enable_l2;
	
	
	always_latch begin: l2
		if(NRESET==0) 
			{word_out, req_out} = 0;
		else if(enable_l2 ) 
			{word_out, req_out} =  {delayed_data, l2_req};
	end

	always_latch begin: lat_l2_req
		if(NRESET==0) 
			last_l2_req = 0;
		else if(PRIME_L2) 
				last_l2_req =  req_out;
	end 

	assign SO = scan_chain[0];

	always_ff @(posedge CLK or negedge NRESET) begin
		if(!NRESET)
			scan_chain<=0;
		else begin
			if (SE)
				scan_chain <= {SI, scan_chain[DATAPATH_WIDTH + DELAY_CTRL_BITS:1]}; 
			else  begin
				scan_chain <=  l2_fired ? {delay_ctrl,req_out, word_out}: scan_chain;
			end
		end
	end

	always_ff @(posedge CLK or negedge NRESET) begin
		if(!NRESET) begin
			enable_l1_sync_ff1 <= 0;
			enable_l1_sync     <= 0;
		end  else begin
			enable_l1_sync_ff1 <= ENABLE_L1;
			enable_l1_sync     <= enable_l1_sync_ff1;			
		end
	end
endmodule