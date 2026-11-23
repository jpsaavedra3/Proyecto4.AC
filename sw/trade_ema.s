# Breakout causal: EMA Q8 alpha=1/256; enter D>8, exit D<-1.
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
    add  x11, x10, x10
    add  x11, x11, x11
    add  x11, x11, x11
    add  x11, x11, x11
    add  x11, x11, x11
    add  x11, x11, x11
    add  x11, x11, x11
    add  x11, x11, x11
    bne  x3, x0, media
    addi x3, x11, 0
media:
    ema  x3, x3, x11, 8
    sub  x11, x11, x3
    beq  x5, x0, enfriar
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
