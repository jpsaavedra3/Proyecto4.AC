import json,itertools,math,statistics
from pathlib import Path
from research_p4 import PRICES
from select_p4 import scenarios

def run(prices,h=8,margin=1,slow=8,fast=5,band=2,rev=4,fee=32):
    cash=10000; shares=0; order=0; orders=0; peak=wealth=10000; dd=0
    e=es=0; signals=[0]*4; fills=[0]*4; scores=[0]*4; selected=0; prev=prices[0]
    for n,p in enumerate(prices):
        if order>>6==1:
            q=min(63,max(0,(cash-5)//p))
            if q:cash-=q*p+5;shares+=q;orders+=1
        elif order>>6==2:
            q=min(63,shares)
            if q and cash+q*p>=5:cash+=q*p-5;shares-=q;orders+=1
        wealth=cash+shares*p;peak=max(peak,wealth);dd=max(dd,peak-wealth)
        delta=(p-prev)<<16
        for j in range(1,4):
            reward=fills[j]*delta
            if signals[j]!=fills[j]:reward-=fee<<8
            scores[j]+=(reward-scores[j])>>h
            fills[j]=signals[j]
        x=p<<8
        if n==0:e=es=x
        e+=(x-e)>>fast;es+=(x-es)>>slow
        dev=x-e;trend=e-es
        signals[1]=1 # buy and hold expert
        if trend>band*256:signals[2]=1
        elif trend < -band*256:signals[2]=0
        if dev < -rev*256:signals[3]=1
        elif dev>0:signals[3]=0
        best=max(range(4),key=lambda j:scores[j])
        if scores[best]>scores[selected]+margin*256:selected=best
        target=signals[selected] if n>=32 else 0
        order=(64 if target else 128)|63
        prev=p
    return dict(wealth=wealth,orders=orders,dd=dd)

def metrics(c,blocks):
    rr=[run(p,**c) for p in blocks]
    score=statistics.mean(math.log(r['wealth']/10000) for r in rr)-.3*statistics.mean(r['dd']/10000 for r in rr)+.2*min(math.log(r['wealth']/10000) for r in rr)
    return dict(score=score,wealths=[r['wealth'] for r in rr],orders=sum(r['orders'] for r in rr),dd=max(r['dd'] for r in rr))

if __name__=='__main__':
    train=[PRICES[i:i+3000] for i in range(0,12000,3000)]
    rows=[]
    for h,margin,slow,band in itertools.product((7,8,9),(1,4),(7,9),(1,3)):
        c=dict(h=h,margin=margin,slow=slow,band=band)
        rows.append({'config':c,**metrics(c,train)})
    rows.sort(key=lambda x:x['score'],reverse=True)
    finalists=[{**r,'validation':metrics(r['config'],[PRICES[12000:14000],PRICES[14000:16000]])} for r in rows[:4]]
    print(json.dumps(finalists,indent=2))
    Path(__file__).with_name('research_ensemble.json').write_text(json.dumps({'all':rows,'finalists':finalists},indent=2))
