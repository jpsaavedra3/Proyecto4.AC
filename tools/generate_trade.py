#!/usr/bin/env python3
"""Generate equivalent RV32E implementations; no embedded prices or account replica."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HEADER='''# Breakout causal: EMA Q8 alpha=1/256; enter D>8, exit D<-1.
# Warmup=32; cooldown=32, decremented before entry test.
# Target long emits BUY63, flat emits SELL63. Official master clips quantities
# against cash and inventory, charges only nonempty orders, fills at next price.
# x2=SPI, x3=EMA, x4=target, x5=warmup, x6=cooldown, x7=decision,
# x10=price, x1/x11-x15=temporaries. No data RAM, multiplication or division.
.section .text
.global _start
_start:
    lui  x2, 0x80010
    addi x3, x0, 0
    addi x4, x0, 0
    addi x5, x0, 32
    addi x6, x0, 0
espera:
    lw   x11, 0(x2)
    andi x11, x11, 1
    beq  x11, x0, espera
    lw   x10, 4(x2)
indicadores:
'''
SHIFT_SW='    add  x11, x10, x10\n'+'    add  x11, x11, x11\n'*7
MEDIA='''    bne  x3, x0, media
    addi x3, x11, 0
media:
'''
EMA_SW='''    sub  x11, x11, x3
    jal  x1, sra8_sw
    add  x3, x3, x13
    sub  x11, x11, x13
'''
EMA_SHIFT='''    sub  x11, x11, x3
    srai x13, x11, 8
    add  x3, x3, x13
    sub  x11, x11, x13
'''
EMA_CUSTOM='''    ema  x3, x3, x11, 8
    sub  x11, x11, x3
'''
TAIL='''    beq  x5, x0, enfriar
    addi x5, x5, -1
    jal  x0, escribir
enfriar:
    beq  x6, x0, senal
    addi x6, x6, -1
senal:
    beq  x4, x0, entrada
    addi x12, x0, -256
    bge  x11, x12, escribir
    addi x4, x0, 0
    addi x6, x0, 32
    jal  x0, escribir
entrada:
    bne  x6, x0, escribir
    addi x12, x0, 1024
    add  x12, x12, x12
    bge  x12, x11, escribir
    addi x4, x0, 1
escribir:
    addi x7, x0, 191
    beq  x4, x0, emitir
    addi x7, x0, 127
emitir:
    sw   x7, 8(x2)
    jal  x0, espera
'''
SRA='''
# Right shift by 8; signed Q8 difference bounded by +/-65280.
# At most 8 loop iterations. x11 preserved; result x13.
sra8_sw:
    addi x15, x11, 0
    bge  x11, x0, sr_pos
    xori x15, x11, -1
sr_pos:
    addi x13, x0, 0
    addi x12, x0, 256
    addi x14, x0, 1
    bltu x15, x12, sr_fin
sr_loop:
    and  x7, x15, x12
    beq  x7, x0, sr_sig
    add  x13, x13, x14
sr_sig:
    add  x12, x12, x12
    add  x14, x14, x14
    bgeu x15, x12, sr_loop
sr_fin:
    bge  x11, x0, sr_ret
    xori x13, x13, -1
sr_ret:
    jalr x0, 0(x1)
'''
def main():
    for name,kind in [('trade',0),('trade_shifter',1),('trade_ema',2)]:
        text=HEADER+('    slli x11, x10, 8\n' if kind==1 else SHIFT_SW)+MEDIA
        text+=[EMA_SW,EMA_SHIFT,EMA_CUSTOM][kind]+TAIL
        if kind==0:text+=SRA
        (ROOT/'sw'/f'{name}.s').write_text(text,encoding='utf-8')
        print('Generated',name)
if __name__=='__main__':main()
