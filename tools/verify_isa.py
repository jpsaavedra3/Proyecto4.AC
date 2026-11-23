#!/usr/bin/env python3
"""Independent RV32E machine-code interpreter. This is not an RTL timing simulator."""
import csv,json,random,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'ref')]
import pochoasm,trader
PROGRAMS=['trade','trade_shifter','trade_ema']

def signed(x,bits=32):
    return (x&((1<<(bits-1))-1))-(x&(1<<(bits-1)))

def check(name,prices):
    labels,ins=pochoasm.preprocess((ROOT/'sw'/f'{name}.s').read_text().splitlines())
    binary=[int(x,16) for x in (ROOT/'sw'/f'{name}.hex').read_text().split()]
    assert binary==[pochoasm.assemble_instruction(line,pc,labels) for _,pc,line in ins]
    assert len(binary)<=128,'Program exceeds configured RAM'
    reg=[0]*16;pc=n=ic=0;tr=trader.Trader();counts=[];states=[]
    while n<len(prices):
        assert pc%4==0 and 0<=pc//4<len(binary),('PC outside program',pc)
        w=binary[pc//4];op=w&127;f=(w>>12)&7;rd=(w>>7)&31;a=(w>>15)&31;b=(w>>20)&31
        assert rd<16 or op in (0x23,0x63)
        assert a<16 or op in (0x37,0x6f)
        assert b<16 or op not in (0x33,0x0b,0x23,0x63)
        av=reg[a] if a<16 else 0;bv=reg[b] if b<16 else 0
        imm=signed(w>>20,12);nxt=pc+4;value=None;ic+=1
        if op==0x37:value=w&0xfffff000
        elif op==0x13:
            if f==0:value=av+imm
            elif f==7:value=av&imm
            elif f==6:value=av|imm
            elif f==4:value=av^imm
            elif f in (1,5):
                assert name=='trade_shifter' and (b&31)==8
                value=av<<8 if f==1 else (signed(av)>>8 if (w>>30)&1 else av>>8)
            else:raise AssertionError(hex(w))
        elif op==0x33:
            if f==0:value=av-bv if (w>>30)&1 else av+bv
            elif f==7:value=av&bv
            else:raise AssertionError(hex(w))
        elif op==0x0b:
            assert name=='trade_ema' and f==0 and w>>25==0
            assert 0<=av<=65535 and 0<=bv<=65535
            value=av+((bv-av)>>8)
        elif op==0x03:
            addr=(av+imm)&0xffffffff
            assert addr in (0x80010000,0x80010004)
            value=1 if addr==0x80010000 else prices[n]
        elif op==0x23:
            imm=signed(((w>>25)<<5)|((w>>7)&31),12)
            assert ((av+imm)&0xffffffff)==0x80010008
            expected=tr.tick(prices[n])
            assert bv==expected,(name,n,prices[n],bv,expected)
            assert (reg[3],reg[4],reg[5],reg[6])==(tr.E,tr.target,tr.warmup,tr.cooldown),(name,n,'state mismatch')
            counts.append(ic);states.append(bv);ic=0;n+=1
        elif op==0x63:
            imm=signed(((w>>31)<<12)|(((w>>7)&1)<<11)|(((w>>25)&63)<<5)|(((w>>8)&15)<<1),13)
            take={0:av==bv,1:av!=bv,4:signed(av)<signed(bv),5:signed(av)>=signed(bv),6:av<bv,7:av>=bv}[f]
            if take:nxt=pc+imm
        elif op==0x6f:
            imm=signed(((w>>31)<<20)|(((w>>12)&255)<<12)|(((w>>20)&1)<<11)|(((w>>21)&1023)<<1),21)
            value=pc+4;nxt=pc+imm
        elif op==0x67:value=pc+4;nxt=(av+imm)&~1
        else:raise AssertionError(hex(w))
        if value is not None and rd:reg[rd]=value&0xffffffff
        assert reg[0]==0
        pc=nxt
        assert ic<1000,'Unexpected loop'
    return dict(program=name,static_instructions=len(binary),program_bytes=len(binary)*4,ticks=len(prices),functional_ic_mean=statistics.mean(counts),functional_ic_max=max(counts),all_decisions_and_states_match=True)

def main():
    with (ROOT/'tb'/'practica_meta.csv').open() as f:pp=[int(r['price']) for r in csv.DictReader(f)]
    rng=random.Random(42)
    cases={'official_meta':pp,'extremes':[100]*40+[255,100]*300+[rng.randint(100,255) for _ in range(3000)],'constant':[180]*2000,'range_1_255':[1]*40+[1,255]*300+[rng.randint(1,255) for _ in range(3000)]}
    rows=[]
    for label,prices in cases.items():
        for name in PROGRAMS:
            r={'case':label,**check(name,prices)};rows.append(r)
            print('PASS ISA',label,name,f"{r['ticks']} prices",flush=True)
    assert trader.mercado(10000,0,0xbf,255)==(10000,0,0),'Empty sale charged fee'
    assert trader.mercado(100,0,0x7f,255)==(100,0,0),'Unaffordable buy charged fee'
    assert trader.mercado(10000,2,0xbf,255)==(10505,0,1),'Clipped sale wrong'
    bad=False
    try:pochoasm.assemble_instruction('ema x3, x3, x11, 5',0,{})
    except ValueError:bad=True
    assert bad,'Old custom encoding must be rejected'
    out=ROOT/'docs'/'results';out.mkdir(parents=True,exist_ok=True)
    (out/'isa.json').write_text(json.dumps(rows,indent=2))
if __name__=='__main__':main()
