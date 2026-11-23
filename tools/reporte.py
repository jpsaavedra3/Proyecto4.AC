#!/usr/bin/env python3
"""Generate auditable report tables from real RTL traces, P&R logs and references."""
import csv,hashlib,json,math,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'ref'),str(ROOT/'tools')]
import trader,legacy_trader,pochoasm
F=25_000_000
NAMES=['Software','Shifter fijo de 8 bits','EMA8 Q8 de 16 bits']

def read_csv(path):
    with Path(path).open() as f:return list(csv.DictReader(f))

def strategy(prices,engine):
    w,o,d=trader.simular(prices,engine)
    return dict(wealth=w,orders=o,fees=o*5,max_drawdown=d)

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |',*['| '+' | '.join(str(x) for x in r)+' |' for r in rows]])

def main():
    pp=[int(r['price']) for r in read_csv(ROOT/'tb'/'practica_meta.csv')]
    out=ROOT/'docs'/'results';out.mkdir(parents=True,exist_ok=True)
    synth=json.loads((out/'synth.json').read_text())
    variants=[]
    for v,name in enumerate(NAMES):
        latency=read_csv(ROOT/'build'/f'latencias_v{v}.csv')
        assert len(latency)==20000,'Full 20,000-tick RTL measurements required'
        c=[int(r['ciclos']) for r in latency];ic=[int(r['instrucciones']) for r in latency];bs=[int(r['bytes']) for r in latency]
        assert all(x>0 for x in c+ic+bs)
        ref=trader.Trader()
        for n,r in enumerate(latency):
            assert int(r['tick'])==n and int(r['precio'])==pp[n]
            assert int(r['decision_calculada'],16)==ref.tick(pp[n])
        worst=max(range(len(c)),key=c.__getitem__)
        cm=statistics.mean(c);im=statistics.mean(ic);bm=statistics.mean(bs)
        intensity=5/bm;bw=4/2*F;peak=(3 if v==2 else 1)*F/2
        variants.append(dict(variant=v,name=name,cycles_mean=cm,cycles_max=max(c),instructions_mean=im,
            instructions_at_worst=ic[worst],cpi=sum(c)/sum(ic),cpi_at_worst=c[worst]/ic[worst],
            time_mean_us=cm/F*1e6,time_max_us=max(c)/F*1e6,bytes_mean=bm,
            useful_ops_per_tick=5,ops_per_second=5*F/cm,intensity_ops_per_byte=intensity,
            roofline_peak_ops=peak,roofline_bw_bytes=bw,roofline_upper_bound=min(peak,bw*intensity),
            program_bytes=len((ROOT/'sw'/(['trade','trade_shifter','trade_ema'][v]+'.hex')).read_text().split())*4,
            **{k:x for k,x in synth[v].items() if k!='variant'}))
    labels,ins=pochoasm.preprocess((ROOT/'sw'/'trade.s').read_text().splitlines())
    pc_lines={pc:line for _,pc,line in ins}
    prof=read_csv(ROOT/'build'/'perfil_v0.csv')
    sra_cycles=sum(int(r['ciclos']) for r in prof if int(r['pc'])>=labels['sra8_sw'] or 'sra8_sw' in pc_lines.get(int(r['pc']),''))/len(pp)
    assert sra_cycles>0,'Missing measured kernel profile'
    c0=variants[0]['cycles_mean']
    for v in (1,2):
        part=sra_cycles+(16 if v==1 else 4)
        replacement=4 if v==1 else 2
        variants[v]['amdahl_fraction']=part/c0
        variants[v]['amdahl_predicted']=c0/(c0-part+replacement)
        variants[v]['speedup_measured']=c0/variants[v]['cycles_mean']
    economy={}
    for n in (2000,20000):
        p=pp[:n];bw,bo,bd=trader.comprar_y_mantener(p)
        economy[str(n)]={'new':strategy(p,trader.Trader()),'old':strategy(p,legacy_trader.Trader()),
            'cash':strategy(p,None),'buy_hold':dict(wealth=bw,orders=bo,fees=bo*5,max_drawdown=bd)}
    blocks=[dict(start=i,end=i+1999,**strategy(pp[i:i+2000],trader.Trader())) for i in range(0,20000,2000)]
    result=dict(source_commit='c121d8214fc9687e374ba2d2dcce88ebc4279ee5',
        series_sha256=hashlib.sha256((ROOT/'tb'/'practica_meta.csv').read_bytes()).hexdigest(),
        strategy='EMA8 breakout, entry +8, exit -1, warmup/cooldown 32',economy=economy,blocks=blocks,
        variants=variants,measured_sra_cycles_per_tick=sra_cycles,
        compiler_note='Windows Icarus 14 exited 0xC0000005 after DONE; explicit opt-in accepted fresh output only; vvp, assertions and every reference row must still pass.',
        external_hidden_assets_tested=False,board_programmed=False)
    (out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    econrows=[]
    for n in ('2000','20000'):
        for key,name in [('new','Breakout nuevo'),('old','Reversión anterior'),('cash','No operar'),('buy_hold','Comprar y mantener')]:
            r=economy[n][key];econrows.append([n,name,r['wealth'],r['orders'],r['fees'],r['max_drawdown']])
    from report_structure import build_report
    text=build_report(result,ROOT)
    (ROOT/'docs'/'Informe_Proyecto4.md').write_text(text,encoding='utf-8')
    print('Wrote docs/Informe_Proyecto4.md and docs/results/summary.json')

if __name__=='__main__':main()
