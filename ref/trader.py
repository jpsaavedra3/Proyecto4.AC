#!/usr/bin/env python3
"""Causal breakout reference; compatible with the official master's fill rules."""
import argparse,csv
from pathlib import Path
CAJA0=10000
COMISION=5
K=8
ENTRY=8*256
EXIT=-256
WARMUP=32
COOLDOWN=32

def mercado(caja,acciones,decision,p):
    action=decision>>6; q=decision&63; orden=0
    if action==1:
        q=min(q,max(0,(caja-COMISION)//p))
        if q>0:caja-=q*p+COMISION;acciones+=q;orden=1
    elif action==2:
        q=min(q,acciones)
        if q>0 and caja+q*p>=COMISION:caja+=q*p-COMISION;acciones-=q;orden=1
    return caja,acciones,orden

class Trader:
    def __init__(self):
        self.E=0;self.target=0;self.warmup=WARMUP;self.cooldown=0
    def tick(self,p):
        if not 1<=p<=255:raise ValueError('SPI price must be in 1..255')
        x=p<<8
        if not self.E:self.E=x
        self.E+=(x-self.E)>>K
        d=x-self.E
        if self.warmup:self.warmup-=1
        else:
            if self.cooldown:self.cooldown-=1
            if self.target:
                if d<EXIT:self.target=0;self.cooldown=COOLDOWN
            elif not self.cooldown and d>ENTRY:self.target=1
        return 0x7f if self.target else 0xbf

def simular(precios,trader=None,salida=None,return_rows=False):
    caja=peak=w=CAJA0;acciones=decision=ordenes=dd=0;rows=[]
    for n,p in enumerate(precios):
        caja,acciones,o=mercado(caja,acciones,decision,p)
        ordenes+=o;w=caja+acciones*p;peak=max(peak,w);dd=max(dd,peak-w)
        rows.append((n,p,f'{decision:02x}',caja,acciones,w))
        if trader is not None:decision=trader.tick(p)
    if salida:
        path=Path(salida);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('w',newline='',encoding='utf-8') as f:
            writer=csv.writer(f,lineterminator='\n')
            writer.writerow(['tick','precio','decision','caja','acciones','patrimonio'])
            writer.writerows(rows)
    return rows if return_rows else (w,ordenes,dd)

def comprar_y_mantener(precios):
    q=(CAJA0-COMISION)//precios[0];caja=CAJA0-COMISION-q*precios[0];peak=CAJA0;dd=0
    for p in precios:w=caja+q*p;peak=max(peak,w);dd=max(dd,peak-w)
    return w,1,dd

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--serie',default='tb/practica_meta.csv')
    ap.add_argument('--ticks',type=int,default=20000)
    ap.add_argument('--desde',type=int,default=0)
    ap.add_argument('--csv')
    a=ap.parse_args()
    with open(a.serie) as f:prices=[int(r['price']) for r in csv.DictReader(f)]
    prices=prices[a.desde:a.desde+a.ticks]
    if not prices:ap.error('empty price interval')
    print(f'Serie {a.serie}, {len(prices)} ticks, execution delayed by one tick')
    print(f'{"Strategy":24}{"Wealth":>10}{"Orders":>9}{"Fees":>9}{"Max drawdown":>15}')
    for name,rr in [('Breakout',simular(prices,Trader(),a.csv)),('No operar',simular(precios=prices)),('Comprar y mantener',comprar_y_mantener(prices))]:
        w,o,d=rr;print(f'{name:24}{w:10}{o:9}{o*COMISION:9}{d:15}')
if __name__=='__main__':main()
