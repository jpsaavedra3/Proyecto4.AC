#!/usr/bin/env python3
"""Keep the traces and sanitized tool logs used by the delivery report."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def write_text(path,text):
    """Keep evidence portable across Windows/Linux without trailing whitespace."""
    text=text.replace('\r\n','\n').replace('\r','\n')
    text='\n'.join(line.rstrip(' \t') for line in text.split('\n'))
    path.write_text(text,encoding='utf-8',newline='\n')

def main():
    assert (ROOT/'docs'/'results'/'checks.json').exists(),'Certify completed checks first'
    out=ROOT/'docs'/'results'
    files=['official.log','unit_shifter.log','unit_ema.log']
    for v in range(3):
        for kind in ['medicion','latencias','perfil']:
            src=ROOT/'build'/f'{kind}_v{v}.csv'
            write_text(out/src.name,src.read_text(encoding='utf-8'))
        files += [f'medicion_v{v}.log',f'medicion_v{v}_compile.log',f'v{v}/yosys.log',f'v{v}/nextpnr.log']
    for name in files:
        src=ROOT/'build'/name
        text=src.read_text(errors='replace')
        text=text.replace(str(ROOT),'$PROJECT').replace(str(ROOT).replace('\\','/'),'$PROJECT')
        text=text.replace(str(ROOT.parent/'toolchain'/'oss-cad-suite'),'$OSS_CAD_SUITE')
        dest=out/name.replace('/','_');write_text(dest,text)
    for path in out.iterdir():
        if path.is_file() and path.suffix in ('.json','.csv','.log'):
            write_text(path,path.read_text(encoding='utf-8'))
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name!='evidence_hashes.json'}
    write_text(out/'evidence_hashes.json',json.dumps(hashes,indent=2))
    print('Archived measured traces, sanitized logs and SHA-256 hashes in docs/results/')
if __name__=='__main__':main()
