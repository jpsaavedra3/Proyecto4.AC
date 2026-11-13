#!/usr/bin/env python3
"""Tablas del informe a partir de make medir y make sintesis.

Lee build/medicion_v*.csv, build/perfil_v*.csv y los logs de build/v*/, y calcula
IC, ciclos, CPI y tiempo por tick, el perfil de trade.s, Amdahl, Ops/s y el roofline.
"""

import csv
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
sys.path.insert(0, os.path.join(RAIZ, "ref"))
import pochoasm  # noqa: E402
import trader    # noqa: E402

F_HZ = 25e6
SPI_NS = 9500
RONDAS = [("1", 10_000_000), ("2", 1_000_000), ("3", 100_000)]
VARIANTES = [(0, "Solo software", "sw/trade.s"),
             (1, "Shifter", "sw/trade_shifter.s"),
             (2, "Instrucción ema", "sw/trade_ema.s")]

# Operaciones utiles por tick: las del kernel de ref/trader.py (actualizar estado y predecir)
#   X = p << 8, t = X - E, t >> 5, E + (t >> 5), D = X - E          5
#   D + 3V < 0 (producto, suma, comparacion), D > 0                  4
#   |D|, |D| - V, >> 6, V + ...                                      4
OPS_TICK = 13
BYTES_TICK = 12   # lw STATUS + lw PRICE + sw DECISION (todo el estado vive en registros)


def ruta(*partes):
    return os.path.join(RAIZ, *partes)


def leer_medicion(v):
    with open(ruta("build", f"medicion_v{v}.csv")) as f:
        filas = list(csv.DictReader(f))
    ciclos = [int(r["ciclos"]) for r in filas if r["ciclos"]]
    instr = [int(r["instrucciones"]) for r in filas if r["instrucciones"]]
    return filas, ciclos, instr


def comparar_con_referencia(filas):
    precios = [int(r["precio"]) for r in filas]
    tr = trader.Trader()
    caja, acciones, decision = trader.CAJA0, 0, 0
    for n, (r, p) in enumerate(zip(filas, precios)):
        caja, acciones, _ = trader.mercado(caja, acciones, decision, p)
        esperado = (n, p, f"{decision:02x}", caja, acciones, caja + acciones * p)
        obtenido = (int(r["tick"]), int(r["precio"]), r["decision"], int(r["caja"]),
                    int(r["acciones"]), int(r["patrimonio"]))
        if esperado != obtenido:
            return f"DIFIEREN en el tick {n}: {obtenido} vs {esperado}"
        decision = tr.tick(p)
    return f"identicas a la referencia en los {len(filas)} ticks"


def categorias(programa):
    """pc -> bloque del programa, segun la etiqueta en que cae cada instruccion."""
    with open(ruta(programa)) as f:
        etiquetas, instrucciones = pochoasm.preprocess(f.readlines())
    por_pc = sorted((pc, nombre) for nombre, pc in etiquetas.items())
    bloques = {
        "_start": "Inicio",
        "espera": "Espera del precio",
        "contabilidad": "Contabilidad", "ejec_compra": "Contabilidad",
        "compra_ok": "Contabilidad", "ejec_venta": "Contabilidad", "venta_q": "Contabilidad",
        "indicadores": "Medias y señal", "media": "Medias y señal", "senal": "Medias y señal",
        "no_compra": "Medias y señal", "volatilidad": "Medias y señal", "abs_ok": "Medias y señal",
        "decision": "Decisión", "decide_venta": "Decisión", "venta_ok": "Decisión",
        "escribir": "Decisión",
    }
    cat = {}
    textos = {pc: linea for _, pc, linea in instrucciones}
    for _, pc, linea in instrucciones:
        etiqueta = [n for p, n in por_pc if p <= pc][-1]
        if etiqueta.startswith(("sra_sw", "sr_")):
            cat[pc] = "Shift en software (sra_sw)"
        elif etiqueta.startswith(("mul6", "m6_")):
            cat[pc] = "Multiplicación (mul6)"
        elif etiqueta.startswith(("div6", "d6_")):
            cat[pc] = "División (div6)"
        else:
            cat[pc] = bloques[etiqueta]
        # la llamada a sra_sw (addi x12 = 2^k; jal) cuenta como parte del shift
        if "sra_sw" in linea or "sra_sw" in textos.get(pc + 4, ""):
            cat[pc] = "Shift en software (sra_sw)"
    return cat


def perfil(v, programa):
    cat = categorias(programa)
    total = {}
    with open(ruta("build", f"perfil_v{v}.csv")) as f:
        for r in csv.DictReader(f):
            c = cat[int(r["pc"])]
            ciclos, instr = total.get(c, (0, 0))
            total[c] = (ciclos + int(r["ciclos"]), instr + int(r["instrucciones"]))
    return total


def sintesis(v):
    d = os.path.join(RAIZ, "build", f"v{v}")
    res = {"lut": None, "lc": None, "bram": None, "fmax": None, "cabe": False}
    try:
        with open(os.path.join(d, "yosys.log")) as f:
            texto = f.read()
        bloque = texto[texto.rfind("=== pochoco_soc ==="):]
        m = re.search(r"(\d+)\s+(?:cells\s+)?SB_LUT4|SB_LUT4\s+(\d+)", bloque)
        if m:
            res["lut"] = int(m.group(1) or m.group(2))
        m = re.search(r"(\d+)\s+(?:cells\s+)?SB_RAM40_4K|SB_RAM40_4K\s+(\d+)", bloque)
        if m:
            res["bram"] = int(m.group(1) or m.group(2))
    except FileNotFoundError:
        pass
    try:
        with open(os.path.join(d, "nextpnr.log")) as f:
            texto = f.read()
        lcs = re.findall(r"ICESTORM_LC:\s+(\d+)/\s*(\d+)", texto)
        if lcs:
            res["lc"] = (int(lcs[-1][0]), int(lcs[-1][1]))
            res["cabe"] = res["lc"][0] <= res["lc"][1]
        fmax = re.findall(r"Max frequency for clock '[^']*': ([\d.]+) MHz", texto)
        if fmax and os.path.exists(os.path.join(d, "pochoco_soc.asc")):
            res["fmax"] = float(fmax[-1])
    except FileNotFoundError:
        pass
    return res


def main():
    datos = {}
    for v, nombre, programa in VARIANTES:
        filas, ciclos, instr = leer_medicion(v)
        datos[v] = dict(nombre=nombre, programa=programa, ciclos=ciclos, instr=instr,
                        perfil=perfil(v, programa), sint=sintesis(v))
        print(f"Variante {v} ({nombre}): decisiones {comparar_con_referencia(filas)}")

    print("\nPor tick, desde que llega el precio hasta que se escribe DECISION (25 MHz)")
    print(f"{'Variante':18s}{'Caso':>10s}{'IC':>8s}{'Ciclos':>9s}{'CPI':>6s}{'Tiempo us':>11s}")
    for v, d in datos.items():
        c, i = d["ciclos"], d["instr"]
        peor = max(range(len(c)), key=lambda k: c[k])
        d["c_prom"] = sum(c) / len(c)
        d["i_prom"] = sum(i) / len(i)
        for caso, ic, cic in (("promedio", d["i_prom"], d["c_prom"]), ("peor", i[peor], c[peor])):
            print(f"{d['nombre']:18s}{caso:>10s}{ic:8.1f}{cic:9.1f}{cic / ic:6.2f}{cic / F_HZ * 1e6:11.2f}")

    print("\nPresupuesto por ronda (T menos la transaccion SPI) y uso en el peor caso")
    for r, t_ns in RONDAS:
        presupuesto = (t_ns - SPI_NS) // 40
        usos = "  ".join(f"{d['nombre']}: {100 * max(d['ciclos']) / presupuesto:.2f} %"
                         for d in datos.values())
        print(f"Ronda {r}: T = {t_ns / 1e6:g} ms, {presupuesto} ciclos.  {usos}")

    p0 = datos[0]["perfil"]
    total0 = sum(c for c, _ in p0.values())
    ticks = len(datos[0]["ciclos"])          # el perfil suma las mismas ventanas que el CSV
    print("\nPerfil de trade.s (solo software)")
    print(f"{'Bloque':30s}{'Ciclos':>12s}{'%':>7s}{'Instr':>11s}{'CPI':>6s}{'Ciclos/tick':>13s}")
    for bloque, (c, i) in sorted(p0.items(), key=lambda kv: -kv[1][0]):
        print(f"{bloque:30s}{c:12d}{100 * c / total0:7.1f}{i:11d}{c / i:6.2f}{c / ticks:13.1f}")

    # Amdahl con la parte que reemplaza cada variante (ciclos por tick en trade.s)
    shift = p0["Shift en software (sra_sw)"][0] / ticks
    c0 = datos[0]["c_prom"]
    casos = {1: (shift + 16, 6,    # sra_sw y X = p*256 (8 sumas) -> 2 srai + 1 slli
                 "2 llamadas a sra_sw y las 8 sumas de p*256 -> 2 srai y 1 slli"),
             2: (shift + 8, 4,     # sub + sra_sw + add de cada media -> 1 ema
                 "sub + sra_sw + add de cada media -> 1 ema")}
    print(f"\nAmdahl (shift en software: {shift:.1f} ciclos por tick, "
          f"{100 * shift / c0:.1f} % de trade.s)")
    print(f"{'Variante':18s}{'Parte':>8s}{'f':>7s}{'S parte':>9s}{'Predicho':>10s}"
          f"{'Max 1/(1-f)':>13s}{'Medido':>8s}")
    for v, (parte, hw, desc) in casos.items():
        d = datos[v]
        f = parte / c0
        s_parte = parte / hw
        pred = 1 / ((1 - f) + f / s_parte)
        print(f"{d['nombre']:18s}{parte:8.1f}{f:7.3f}{s_parte:9.1f}{pred:10.2f}"
              f"{1 / (1 - f):13.2f}{c0 / d['c_prom']:8.2f}   ({desc})")

    print(f"\nOps/s (operacion util = una de las {OPS_TICK} del kernel por tick) y roofline")
    bw = 4 / 3 * F_HZ                         # un lw de 4 bytes cada 3 ciclos
    inten = OPS_TICK / BYTES_TICK
    print(f"Intensidad: {OPS_TICK} ops / {BYTES_TICK} B = {inten:.2f} ops/B; "
          f"ancho de banda {bw / 1e6:.1f} MB/s")
    print(f"{'Variante':18s}{'Ops/s':>12s}{'Techo comp':>12s}{'Quiebre':>9s}{'Alcanzable':>12s}{'%':>7s}")
    for v, d in datos.items():
        ops = OPS_TICK * F_HZ / d["c_prom"]
        techo = (3 if v == 2 else 1) * F_HZ / 2   # CPI minimo 2; ema hace 3 operaciones
        alcanzable = min(techo, bw * inten)
        d["ops"], d["techo"] = ops, techo
        print(f"{d['nombre']:18s}{ops:12.3e}{techo:12.3e}{techo / bw:9.3f}{alcanzable:12.3e}"
              f"{100 * ops / alcanzable:7.1f}")
    if "--figura" in sys.argv:
        figura_roofline(datos, bw, inten)

    print("\nSintesis (Yosys + nextpnr, iCE40 HX1K)")
    print(f"{'Variante':18s}{'SB_LUT4':>9s}{'LCs':>14s}{'BRAM':>6s}{'fmax MHz':>10s}")
    for v, d in datos.items():
        s = d["sint"]
        lc = f"{s['lc'][0]}/{s['lc'][1]}" if s["lc"] else "-"
        fmax = f"{s['fmax']:.2f}" if s["fmax"] else ("no cabe" if s["lc"] else "-")
        print(f"{d['nombre']:18s}{s['lut'] or '-':>9}{lc:>14s}{s['bram'] or '-':>6}{fmax:>10s}")


def figura_roofline(datos, bw, inten):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    xs = [0.05 * 1.1 ** k for k in range(80)]
    fig, ax = plt.subplots(figsize=(6, 3.8))
    for techo, estilo, nombre in ((F_HZ / 2, "-", "Espino (1 op cada 2 ciclos)"),
                                  (3 * F_HZ / 2, "--", "Con ema (3 ops por instrucción)")):
        ax.loglog(xs, [min(techo, bw * x) for x in xs], estilo, color="gray", lw=1, label=nombre)
    for v, d in datos.items():
        ax.loglog([inten], [d["ops"]], "o", label=f"{d['nombre']}: {d['ops'] / 1e6:.2f} Mops/s")
    ax.axvline(inten, color="lightgray", lw=0.8, zorder=0)
    ax.set_ylim(1e6, 6e7)
    ax.set_xlabel("Intensidad operacional (ops/byte)")
    ax.set_ylabel("Ops/s")
    ax.legend(fontsize=7, loc="lower right")
    ax.grid(True, which="both", lw=0.3)
    fig.tight_layout()
    fig.savefig(ruta("build", "roofline.png"), dpi=200)
    print("Figura en build/roofline.png")


if __name__ == "__main__":
    main()
