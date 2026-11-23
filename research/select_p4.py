import json,random,math,statistics
from pathlib import Path
from research_p4 import PRICES,evaluate
from research_p4_v2 import run,metrics

def scenarios():
    out={}
    rng=random.Random(20261123)
    for name,drift in [('subida',.025),('bajada',-.025),('lateral',0)]:
        level=140. if drift>=0 else 225.
        pp=[]
        for i in range(3000):
            level+=drift+rng.gauss(0,.42)
            level=min(255.,max(100.,level)); pp.append(round(level))
        out[name]=pp
    level=150.;pp=[]
    for i in range(3000):
        level+=.045 if i<1500 else -.045
        level+=rng.gauss(0,.35)
        pp.append(round(min(255,max(100,level))))
    out['cambio_tendencia']=pp
    out['oscilacion']=[round(175+15*math.sin(i/40)) for i in range(3000)]
    out['constante']=[180]*3000
    return out

def main():
    v2=json.loads(Path(__file__).with_name('research_v2.json').read_text())
    best=next(x['config'] for x in v2['finalists'] if x['config']['kind']=='breakout')
    neighbors=[]
    for k,band in [(7,2048),(8,1536),(8,2048),(8,2560),(9,2048)]:
        c={**best,'k':k,'entry':band}
        neighbors.append({'config':c,'development':metrics(c,[PRICES[i:i+3000] for i in range(0,12000,3000)])})
    # Chosen before reading final interval: best development score in second round,
    # also less severe validation loss than the initial trend/reversion finalists.
    frozen={'config':best,'selection':'best development score in round 2; validation checked at family level; holdout never tuned','split':{'development':[0,12000],'validation':[12000,16000],'holdout':[16000,20000]},'neighbors':neighbors}
    Path(__file__).with_name('frozen_p4.json').write_text(json.dumps(frozen,indent=2))
    results={'frozen':frozen,'stress':{name:run(p,**best) for name,p in scenarios().items()},'holdout':metrics(best,[PRICES[16000:18000],PRICES[18000:20000]]),'full':run(PRICES,**best),'first2000':run(PRICES[:2000],**best),'blocks':[run(PRICES[i:i+2000],**best) for i in range(0,20000,2000)],'sizing':{str(s):run(PRICES,**{**best,'size':s}) for s in (0,1,2)}}
    Path(__file__).with_name('selection_p4.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))

if __name__=="__main__":main()
