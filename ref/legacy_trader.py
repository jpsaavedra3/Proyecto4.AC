#!/usr/bin/env python3
"""Version de referencia del algoritmo de trade.s y comparacion con las referencias.

Usa la misma aritmetica entera que el assembly (punto fijo Q8 y shifts aritmeticos),
asi que debe tomar exactamente las mismas decisiones que trade.s.

Uso:
  python3 ref/trader.py                     # 2000 ticks, como el testbench
  python3 ref/trader.py --ticks 20000       # serie completa
  python3 ref/trader.py --desde 4000        # tramo de 2000 ticks desde el tick 4000
  python3 ref/trader.py --csv ref.csv       # mismo formato que decisiones.csv
"""

import argparse
import csv

CAJA0 = 10000
COMISION = 5

K = 5          # media del precio: alfa = 1/32
KV = 6         # media de |desviacion|: alfa = 1/64
CALENTAMIENTO = 32
QMIN = 8       # no compra menos de 8 acciones (la comision pesaria demasiado)


def mercado(caja, acciones, decision, p):
    """Ejecuta una decision como la FPGA maestra (tarea ejecutar del testbench)."""
    accion = decision >> 6
    q = decision & 63
    orden = 0
    if accion == 1:
        if q > (caja - COMISION) // p:
            q = (caja - COMISION) // p
        if q > 0:
            caja -= q * p + COMISION
            acciones += q
            orden = 1
    elif accion == 2:
        q = min(q, acciones)
        if q > 0 and caja + q * p >= COMISION:
            caja += q * p - COMISION
            acciones -= q
            orden = 1
    return caja, acciones, orden


class Trader:
    """Reversion a la media con bandas normalizadas por volatilidad."""

    def __init__(self):
        self.E = 0                 # media exponencial del precio, Q8 (0 = sin inicializar)
        self.V = 256               # media exponencial de |D|, Q8 (parte en 1,0)
        self.calentamiento = CALENTAMIENTO
        self.comprado = 0
        self.caja = CAJA0          # copia propia de la contabilidad de la maestra
        self.acciones = 0
        self.decision = 0

    def tick(self, p):
        # La maestra ejecuto la decision anterior a este precio
        self.caja, self.acciones, _ = mercado(self.caja, self.acciones, self.decision, p)

        X = p << 8
        if self.E == 0:
            self.E = X
        t = X - self.E
        self.E += t >> K
        D = X - self.E

        if self.calentamiento > 0:
            self.calentamiento -= 1
        elif D + 3 * self.V < 0:
            self.comprado = 1          # 3 volatilidades bajo la media: se espera que suba
        elif D > 0:
            self.comprado = 0          # volvio sobre la media: se cierra la posicion

        self.V += (abs(D) - self.V) >> KV

        self.decision = 0
        if self.comprado:
            r = self.caja - COMISION
            if r >= QMIN * p:
                self.decision = 0x40 | min(63, r // p)
        elif self.acciones > 0:
            self.decision = 0x80 | min(63, self.acciones)
        return self.decision


def simular(precios, trader=None, salida=None):
    """Contabilidad oficial del testbench. trader=None es 'no operar'."""
    caja, acciones = CAJA0, 0
    w = peak = CAJA0
    max_dd = ordenes = 0
    decision = 0
    filas = []
    for n, p in enumerate(precios):
        caja, acciones, orden = mercado(caja, acciones, decision, p)
        ordenes += orden
        w = caja + acciones * p
        peak = max(peak, w)
        max_dd = max(max_dd, peak - w)
        filas.append(f"{n},{p},{decision:02x},{caja},{acciones},{w}")
        if trader is not None:
            decision = trader.tick(p)      # se ejecuta en el tick siguiente
    if salida:
        with open(salida, "w") as f:
            f.write("tick,precio,decision,caja,acciones,patrimonio\n")
            f.write("\n".join(filas) + "\n")
    return w, ordenes, max_dd


def comprar_y_mantener(precios):
    """Como en el testbench: todo a precio[0], sin el limite de 63 por orden."""
    q = (CAJA0 - COMISION) // precios[0]
    caja = CAJA0 - COMISION - q * precios[0]
    peak = CAJA0
    max_dd = 0
    for p in precios:
        w = caja + q * p
        peak = max(peak, w)
        max_dd = max(max_dd, peak - w)
    return w, 1, max_dd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serie", default="tb/practica.csv")
    ap.add_argument("--ticks", type=int, default=2000)
    ap.add_argument("--desde", type=int, default=0, help="primer tick del tramo")
    ap.add_argument("--csv", help="decisiones por tick (formato de decisiones.csv)")
    args = ap.parse_args()

    with open(args.serie) as f:
        precios = [int(fila["price"]) for fila in csv.DictReader(f)]
    precios = precios[args.desde:args.desde + args.ticks]

    filas = [
        ("Algoritmo", simular(precios, Trader(), args.csv)),
        ("No operar", simular(precios)),
        ("Comprar y mantener", comprar_y_mantener(precios)),
    ]
    print(f"Serie {args.serie}, ticks {args.desde} a {args.desde + len(precios) - 1}")
    print(f"{'':20s}{'Patrimonio':>12s}{'Ordenes':>9s}{'Comisiones':>12s}{'Perdida max':>13s}")
    for nombre, (w, ordenes, max_dd) in filas:
        print(f"{nombre:20s}{w:12d}{ordenes:9d}{ordenes * COMISION:12d}{max_dd:13d}")


if __name__ == "__main__":
    main()
