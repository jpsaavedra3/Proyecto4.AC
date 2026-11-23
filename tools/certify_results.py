#!/usr/bin/env python3
"""Validate saved logs/traces and bind them to unchanged, earlier source files."""
import csv,hashlib,json
from pathlib import Path
import run_checks as checks
import trader

def main():
    root=checks.ROOT
    for name in ('shifter','ema'):
        text=(root/'build'/f'unit_{name}.log').read_text()
        assert f'PASS {name}: 30000 casos' in text and 'FAIL' not in text
    text=(root/'build'/'official.log').read_text()
    assert 'Testbenchs aprobados: 4/4' in text and 'FAIL' not in text
    with (root/'tb'/'practica_meta.csv').open() as f:prices=[int(r['price']) for r in csv.DictReader(f)]
    checks.compare(root/'decisiones.csv',prices[:2000])
    assert len(prices)==20000
    proved={}
    for v in range(3):
        binary=root/'build'/f'tb_med_v{v}'
        sources=checks.source_manifest(v)
        assert all((root/p).stat().st_mtime<=binary.stat().st_mtime for p in sources),'Sources modified after compilation'
        checks.compare(root/'build'/f'medicion_v{v}.csv',prices)
        with (root/'build'/f'latencias_v{v}.csv').open() as f:rows=list(csv.DictReader(f))
        assert len(rows)==len(prices)
        ref=trader.Trader()
        for n,(r,p) in enumerate(zip(rows,prices)):
            assert int(r['tick'])==n and int(r['precio'])==p
            assert int(r['decision_calculada'],16)==ref.tick(p)
            assert 0<int(r['ciclos'])<2262 and int(r['instrucciones'])>0
        text=(root/'build'/f'medicion_v{v}.log').read_text()
        assert '20000 ticks: patrimonio final 13291' in text and '$finish called' in text and 'FATAL' not in text
        proved[str(v)]=sources
    out=root/'docs'/'results';out.mkdir(exist_ok=True)
    (out/'validation_sources.json').write_text(json.dumps(proved,indent=2))
    (out/'checks.json').write_text(json.dumps(dict(official_checks='4/4',official_ticks=2000,
        rtl_ticks_per_variant=20000,unit_vectors_per_block=30000,all_reference_rows_match=True,
        compiler_exit_workaround='explicit Windows post-DONE opt-in; simulator exit status and assertions remain mandatory'),indent=2))
    print('PASS: stored unit, official and full RTL results certified against current source files')
if __name__=='__main__':main()
