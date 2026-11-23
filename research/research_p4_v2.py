import csv,math,json,itertools,statistics,random
from pathlib import Path
from research_p4 import PRICES

def run(prices,kind='dip',k=6,slow=9,entry=512,out=0,take=0,stop=0,timeout=0,filter=0,size=0,delay=0):
    cash=10000; shares=0; pending=0; orders=0; wealth=peak=10000; dd=0
    e=es=vol=0; target=0; bought=high=age=cool=0; prev=prices[0]
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
        dev=x-e; trend=e-es
        vol+=(abs(x-(prev<<8))-vol)>>5
        threshold=max(256,(vol*entry)>>8) if kind=='voldip' else entry
        old=target
        if cool: cool-=1
        if not target and not cool and n>=32:
            if kind in ('dip','voldip'): signal=dev < -threshold and (filter==0 or trend>filter)
            elif kind=='breakout': signal=dev>threshold and (filter==0 or trend>filter)
            elif kind=='trend': signal=trend>entry
            elif kind=='pullback': signal=trend>entry and dev<out
            elif kind=='shock': signal=p-prev<=-entry
            else: raise ValueError(kind)
            if signal: target=1; bought=p; high=p; age=0
        elif target:
            age+=1; high=max(high,p)
            sell=False
            if kind in ('dip','voldip'): sell=dev>=out
            elif kind=='breakout': sell=dev < -out
            elif kind=='trend': sell=trend < -out
            elif kind=='pullback': sell=dev>=out or trend < -entry
            elif kind=='shock': sell=False
            if take and p>=bought+take: sell=True
            if stop and p<=high-stop: sell=True
            if timeout and age>=timeout: sell=True
            if sell: target=0; cool=delay
        if size==0:
            # repeat q=63; official master clips against cash and shares
            pending=(64 if target else 128)|63
        elif size==1:
            pending=((64 if target else 128)|63) if target!=old else 0
        elif size==2:
            pending=0
            if target:
                q=min(63,max(0,(cash-5)//p))
                if q>=8: pending=64|q
            elif shares: pending=128|min(63,shares)
        prev=p
    return dict(wealth=wealth,orders=orders,dd=dd)

def metrics(c,blocks):
    rr=[run(p,**c) for p in blocks]
    score=statistics.mean(math.log(r['wealth']/10000) for r in rr)-.3*statistics.mean(r['dd']/10000 for r in rr)+.2*min(math.log(r['wealth']/10000) for r in rr)
    return dict(score=score,wealths=[r['wealth'] for r in rr],orders=sum(r['orders'] for r in rr),dd=max(r['dd'] for r in rr))

def grid():
    for k,entry,take,stop in itertools.product((4,6,8),(512,1024,2048),(0,2,4),(0,4,8)):
        yield dict(kind='dip',k=k,entry=entry,take=take,stop=stop,delay=32)
    for k,entry,take,stop in itertools.product((4,6,8),(512,1024,2048),(0,4),(0,6)):
        yield dict(kind='breakout',k=k,entry=entry,take=take,stop=stop,out=256,delay=32)
    for k,entry,take in itertools.product((4,6,8),(256,768,1536),(0,4)):
        yield dict(kind='dip',k=k,entry=entry,take=take,filter=256,slow=9,delay=32)
    for k,slow,band in itertools.product((3,5,7),(7,9,11),(64,256,512)):
        if k<slow: yield dict(kind='pullback',k=k,slow=slow,entry=band,out=0,delay=32)
    for entry,take,timeout in itertools.product((2,4,8),(1,2,4),(32,128,512)):
        yield dict(kind='shock',entry=entry,take=take,timeout=timeout)

if __name__=='__main__':
    train=[PRICES[i:i+3000] for i in range(0,12000,3000)]
    rows=[{'config':c,**metrics(c,train)} for c in grid()]
    rows.sort(key=lambda r:r['score'],reverse=True)
    final=[]
    for kind in ('dip','breakout','pullback','shock'):
        top=next(r for r in rows if r['config']['kind']==kind)
        final.append({**top,'validation':metrics(top['config'],[PRICES[12000:14000],PRICES[14000:16000]])})
    print(json.dumps({'best':rows[:8],'finalists':final},indent=2))
    Path(__file__).with_name('research_v2.json').write_text(json.dumps({'all':rows,'finalists':final},indent=2))
