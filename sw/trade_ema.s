# trade_ema.s - Pochoco Trader, variante 2: Espino con la instruccion custom-0
#   ema rd, rs1, rs2, k   ->   rd = rs1 + ((rs2 - rs1) >>> k)
# Mismo algoritmo y mismas decisiones que trade.s; cada media es una instruccion.
#
# Algoritmo: reversion a la media con bandas normalizadas por volatilidad.
#   X = p * 256                      precio en punto fijo Q8
#   E = E + ((X - E) >> 5)           media exponencial del precio (alfa 1/32)
#   D = X - E                        desviacion
#   comprar si D < -3V (V del tick anterior), vender si D > 0
#   V = V + ((|D| - V) >> 6)         media exponencial de |D| (alfa 1/64)
#
# Registros persistentes:
#   x2 base SPI   x3 E   x4 V   x5 caja   x6 acciones
#   x7 decision
#   x8 ticks de calentamiento   x9 posicion (1 comprado, 0 fuera)
#   x10 precio p   x1, x11-x15 temporales

.section .text
.global _start

_start:
    lui  x2, 0x80010            # x2 = 0x8001_0000 (esclavo SPI)
    addi x3, x0, 0              # E = 0: sin inicializar
    addi x4, x0, 256            # V = 1,0 en Q8
    lui  x5, 2
    addi x5, x5, 1808           # caja = 8192 + 1808 = 10000
    addi x6, x0, 0              # acciones = 0
    addi x7, x0, 0              # decision = mantener
    addi x8, x0, 32             # 32 ticks de calentamiento
    addi x9, x0, 0              # fuera del mercado

espera:
    lw   x11, 0(x2)             # STATUS
    andi x11, x11, 1            # bit 0: precio nuevo
    beq  x11, x0, espera
    lw   x10, 4(x2)             # p = PRICE (borra el bit)

# 1. Contabilidad propia: la maestra ejecuto la decision anterior (x7) a este precio
contabilidad:
    andi x11, x7, 63            # q pedida
    andi x12, x7, 192           # accion
    addi x13, x0, 64
    beq  x12, x13, ejec_compra
    addi x13, x0, 128
    beq  x12, x13, ejec_venta
    jal  x0, indicadores

ejec_compra:
    jal  x1, mul6               # x12 = q * p
    addi x12, x12, 5            # costo = q * p + 5
    bge  x5, x12, compra_ok
    addi x11, x5, -5            # no alcanza: la maestra compra (caja - 5) / p
    blt  x11, x10, indicadores  # cero acciones: no hubo orden
    jal  x1, div6               # x11 = q
    jal  x1, mul6               # x12 = q * p
    addi x12, x12, 5
compra_ok:
    sub  x5, x5, x12            # caja -= q * p + 5
    add  x6, x6, x11            # acciones += q
    jal  x0, indicadores

ejec_venta:
    bge  x6, x11, venta_q
    addi x11, x6, 0             # q = min(q, acciones)
venta_q:
    beq  x11, x0, indicadores
    jal  x1, mul6               # x12 = q * p
    add  x13, x5, x12
    addi x14, x0, 5
    blt  x13, x14, indicadores  # caja + q * p < 5: no hubo orden
    addi x5, x13, -5            # caja += q * p - 5
    sub  x6, x6, x11            # acciones -= q

# 2. Indicadores
indicadores:
    add  x11, x10, x10          # X = p * 256 con 8 sumas
    add  x11, x11, x11
    add  x11, x11, x11
    add  x11, x11, x11
    add  x11, x11, x11
    add  x11, x11, x11
    add  x11, x11, x11
    add  x11, x11, x11
    bne  x3, x0, media
    addi x3, x11, 0             # primer precio: E = X
media:
    ema  x3, x3, x11, 5         # E += (X - E) >> 5
    sub  x11, x11, x3           # D = X - E

# 3. Prediccion: muy bajo la media se espera que suba
    beq  x8, x0, senal
    addi x8, x8, -1             # calentamiento: no se cambia la posicion
    jal  x0, volatilidad
senal:
    add  x12, x4, x4            # 2V
    add  x12, x12, x4           # 3V
    add  x12, x11, x12          # D + 3V
    bge  x12, x0, no_compra
    addi x9, x0, 1              # D < -3V: comprar
    jal  x0, volatilidad
no_compra:
    bge  x0, x11, volatilidad   # D <= 0: se mantiene la posicion
    addi x9, x0, 0              # D > 0: volvio a la media, vender

volatilidad:
    bge  x11, x0, abs_ok
    sub  x11, x0, x11           # |D|
abs_ok:
    ema  x4, x4, x11, 6         # V += (|D| - V) >> 6

# 4. Decision
decision:
    addi x7, x0, 0              # mantener
    beq  x9, x0, decide_venta
    addi x11, x5, -5            # r = caja - 5
    add  x12, x10, x10
    add  x12, x12, x12
    add  x12, x12, x12          # 8p
    blt  x11, x12, escribir     # alcanza para menos de 8: no vale la comision
    jal  x1, div6               # q = min(63, r / p)
    ori  x7, x11, 64            # comprar q
    jal  x0, escribir
decide_venta:
    beq  x6, x0, escribir       # sin acciones: mantener
    addi x11, x6, 0
    addi x12, x0, 63
    bge  x12, x11, venta_ok
    addi x11, x0, 63            # q = min(63, acciones)
venta_ok:
    ori  x7, x11, 128           # vender q

escribir:
    sw   x7, 8(x2)              # DECISION
    jal  x0, espera

# x12 = x11 * x10 (x11 entre 0 y 63) por sumas y duplicaciones.
# No cambia x10 ni x11. Usa x13, x14, x15.
mul6:
    addi x12, x0, 0
    addi x13, x10, 0            # p * 2^i
    addi x14, x0, 1             # 2^i
m6_loop:
    and  x15, x11, x14
    beq  x15, x0, m6_sig
    add  x12, x12, x13
m6_sig:
    add  x13, x13, x13
    add  x14, x14, x14
    bge  x11, x14, m6_loop      # quedan bits de q
    jalr x0, 0(x1)

# x11 = min(63, x11 / x10) con x11 >= 0: division con restauracion de 6 bits
# que duplica el resto en vez de dividir el divisor. Usa x12, x13, x14.
div6:
    add  x12, x10, x10
    add  x12, x12, x12
    add  x12, x12, x12
    add  x12, x12, x12
    add  x12, x12, x12          # d = 32p
    add  x13, x12, x12          # 64p
    blt  x11, x13, d6_div
    addi x11, x0, 63            # el cociente no cabe en 6 bits
    jalr x0, 0(x1)
d6_div:
    addi x13, x0, 0             # q
    addi x14, x0, 6
d6_loop:
    add  x13, x13, x13
    blt  x11, x12, d6_sig
    sub  x11, x11, x12
    addi x13, x13, 1
d6_sig:
    add  x11, x11, x11
    addi x14, x14, -1
    bne  x14, x0, d6_loop
    addi x11, x13, 0
    jalr x0, 0(x1)
