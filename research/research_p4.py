import csv, math, json, itertools, statistics, sys
from pathlib import Path

DATA=Path(__file__).resolve().parents[1]/'tb'/'practica_meta.csv'
PRICES=[int(r['price']) for r in csv.DictReader(DATA.open())]

def evaluate(prices, kind, k=5, slow=8, band=128, exitband=0, stop=0, adapt=8):
    cash=10000; shares=0; pending=0; orders=0; peak=10000; dd=0
    e=es=vol=0; target=0; high=entry=0; prev=prices[0]
    st=sr=0; pt=pr=0; chosen=0; decisions=[]
    for n,p in enumerate(prices):
        action=pending>>6; q=pending&63
        if action==1:
            q=min(q,max(0,(cash-5)//p))
            if q: cash-=q*p+5; shares+=q; orders+=1
        elif action==2:
            q=min(q,shares)
            if q and cash+q*p>=5: cash+=q*p-5; shares-=q; orders+=1
        wealth=cash+shares*p; peak=max(peak,wealth); dd=max(dd,peak-wealth)
        x=p<<8
        if n==0: e=es=x; vol=256
        e+=(x-e)>>k; es+=(x-es)>>slow
        d=x-e; trend=e-es
        vol+=(abs(x-(prev<<8))-vol)>>5
        threshold=max(band,(vol*exitband)>>8) if kind in ('voltrend',) else band
        old=target
        if kind in ('trend','voltrend'):
            if trend>threshold: target=1
            elif trend < -threshold: target=0
        elif kind=='price':
            if d>band: target=1
            elif d < -exitband: target=0
        elif kind=='revert':
            if d < -band: target=1
            elif d>exitband: target=0
        elif kind=='diptrend':
            if trend>band and d<0: target=1
            elif trend < -band or d>exitband: target=0
        elif kind=='adaptive':
            # Two causal virtual experts. Scores track net price points after virtual switch fees.
            delta=(p-prev)<<8
            st+=((pt*delta)-st)>>adapt
            sr+=((pr*delta)-sr)>>adapt
            oldpt,oldpr=pt,pr
            if trend>band: pt=1
            elif trend < -band: pt=0
            if d < -exitband: pr=1
            elif d>0: pr=0
            if oldpt!=pt: st-=32
            if oldpr!=pr: sr-=32
            if st>sr+32: chosen=0
            elif sr>st+32: chosen=1
            target=pt if chosen==0 else pr
        else: raise ValueError(kind)
        if n<32: target=0
        if target and not old: entry=p; high=p
        if target: high=max(high,p)
        if stop and target and p<high-stop: target=0
        pending=0
        if target:
            q=min(63,max(0,(cash-5)//p))
            if q>=8: pending=64|q
        elif shares: pending=128|min(63,shares)
        decisions.append(pending)
        prev=p
    return {'wealth':wealth,'orders':orders,'dd':dd,'decisions':decisions}

def config_grid():
    for k,slow,band in itertools.product((3,5,7),(7,9,11),(64,256,512)):
        if k<slow: yield dict(kind='trend',k=k,slow=slow,band=band)
    for k,band,out in itertools.product((4,6,8),(256,768,1536),(0,256)):
        yield dict(kind='price',k=k,band=band,exitband=out)
        yield dict(kind='revert',k=k,band=band,exitband=out)
    for k,slow,band,rev,adapt in itertools.product((4,6),(8,10),(128,512),(256,1024),(7,9)):
        yield dict(kind='adaptive',k=k,slow=slow,band=band,exitband=rev,adapt=adapt)

def metrics(c,blocks):
    rows=[evaluate(p,**c) for p in blocks]
    returns=[r['wealth']/10000 for r in rows]
    score=statistics.mean(math.log(x) for x in returns)-0.35*statistics.mean(r['dd']/10000 for r in rows)+0.15*min(math.log(x) for x in returns)
    return {'score':score,'wealths':[r['wealth'] for r in rows],'orders':sum(r['orders'] for r in rows),'dd':max(r['dd'] for r in rows)}

if __name__=='__main__':
    train=[PRICES[i:i+3000] for i in range(0,12000,3000)]
    rows=[]
    for c in config_grid(): rows.append({'config':c,**metrics(c,train)})
    rows.sort(key=lambda x:x['score'],reverse=True)
    # Freeze one candidate per family from development data before the next interval.
    finalists=[]
    for kind in ('trend','price','revert','adaptive'):
        top=next(r for r in rows if r['config']['kind']==kind)
        finalists.append({**top,'validation':metrics(top['config'],[PRICES[12000:14000],PRICES[14000:16000]])})
    print(json.dumps({'development_best':rows[:12],'finalists':finalists},indent=2))
    Path(__file__).with_name('research_initial.json').write_text(json.dumps({'all':rows,'finalists':finalists},indent=2))
