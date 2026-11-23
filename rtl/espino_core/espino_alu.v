// Copyright 2026 Universidad de los Andes.
// Licensed under the Solderpad Hardware License, Version 0.51 (the "License");
// you may not use this file except in compliance with the License.
// SPDX-License-Identifier: SHL-0.51
//
// Course: Arquitectura de Computadores (2026)
// 
// Authors:
// - Nicolás Villegas <navillegas@miuandes.cl>

module espino_alu #(
  parameter Variant = 0   // 1: fixed shifts by 8; other amounts are unsupported
) (
  input  wire [3:0]  operator_i,
  input  wire [31:0] operand_a_i,
  input  wire [31:0] operand_b_i,
  output reg  [31:0] result_o,
  output reg         cmp_result_o
);

  localparam [3:0] ALU_ADD  = 4'd0,
                   ALU_SUB  = 4'd1,
                   ALU_XOR  = 4'd2,
                   ALU_OR   = 4'd3,
                   ALU_AND  = 4'd4,
                   ALU_SLL  = 4'd5,
                   ALU_SRL  = 4'd6,
                   ALU_SRA  = 4'd7,
                   ALU_SLT  = 4'd8,
                   ALU_SLTU = 4'd9,
                   ALU_EQ   = 4'd10,
                   ALU_NE   = 4'd11,
                   ALU_LT   = 4'd12,
                   ALU_GE   = 4'd13,
                   ALU_LTU  = 4'd14,
                   ALU_GEU  = 4'd15;

  wire signed [31:0] a_s;
  wire signed [31:0] b_s;
  assign a_s = operand_a_i;
  assign b_s = operand_b_i;

  wire [4:0] shamt;
  assign shamt = operand_b_i[4:0];

  // The algorithm only shifts by 8. Fixed wiring avoids three barrel shifters.
  wire [31:0] sll_res = {operand_a_i[23:0], 8'b0};
  wire [31:0] srl_res = {8'b0, operand_a_i[31:8]};
  wire [31:0] sra_res = {{8{operand_a_i[31]}}, operand_a_i[31:8]};

  // Comparisons
  wire cmp_eq, cmp_lt, cmp_ltu;
  assign cmp_eq  = (operand_a_i == operand_b_i);
  assign cmp_lt  = (a_s < b_s);
  assign cmp_ltu = (operand_a_i < operand_b_i);

  always @* begin
    case (operator_i)
      ALU_EQ:  cmp_result_o =  cmp_eq;
      ALU_NE:  cmp_result_o = ~cmp_eq;
      ALU_LT:  cmp_result_o =  cmp_lt;
      ALU_GE:  cmp_result_o = ~cmp_lt;
      ALU_LTU: cmp_result_o =  cmp_ltu;
      ALU_GEU: cmp_result_o = ~cmp_ltu;
      default: cmp_result_o = 1'b0;
    endcase
  end

  // Main result
  always @* begin
    case (operator_i)
      ALU_ADD:  result_o = operand_a_i + operand_b_i;
      ALU_SUB:  result_o = operand_a_i - operand_b_i;
      ALU_XOR:  result_o = operand_a_i ^ operand_b_i;
      ALU_OR:   result_o = operand_a_i | operand_b_i;
      ALU_AND:  result_o = operand_a_i & operand_b_i;
      ALU_SLT:  result_o = {31'b0, cmp_lt};
      ALU_SLTU: result_o = {31'b0, cmp_ltu};
      // Shifts disabled to save LUTs (Variant 1 los habilita)
      ALU_SLL:  result_o = (Variant == 1 && shamt == 8) ? sll_res : operand_a_i + operand_b_i;
      ALU_SRL:  result_o = (Variant == 1 && shamt == 8) ? srl_res : operand_a_i + operand_b_i;
      ALU_SRA:  result_o = (Variant == 1 && shamt == 8) ? sra_res : operand_a_i + operand_b_i;
      default:  result_o = operand_a_i + operand_b_i;
    endcase
  end

endmodule
