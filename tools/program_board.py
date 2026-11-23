#!/usr/bin/env python3
"""Verify source/bitstream provenance. Flash only with the explicit --flash flag."""
import argparse,hashlib,json,subprocess
from pathlib import Path
import run_checks as checks

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--variant',type=int,choices=[0,1,2],default=1)
    ap.add_argument('--toolchain');ap.add_argument('--flash',action='store_true');a=ap.parse_args()
    suite,env=checks.setup(a.toolchain);root=checks.ROOT
    d=root/'build'/f'v{a.variant}';manifest=d/'provenance.json'
    if not manifest.exists():raise SystemExit('Missing provenance. Run synthesis and full simulation first.')
    proof=json.loads(manifest.read_text())
    for path,sha in proof['sources'].items():
        if digest(root/path)!=sha:raise SystemExit(f'Source changed since verification: {path}')
    image=d/'pochoco_soc.bin'
    if digest(image)!=proof['bitstream_sha256']:raise SystemExit('Bitstream hash mismatch')
    sim=root/'docs'/'results'/'validation_sources.json'
    if not sim.exists():raise SystemExit('Missing approved simulation source manifest')
    validated=json.loads(sim.read_text())
    if str(a.variant) not in validated or validated[str(a.variant)]!=proof['sources']:
        raise SystemExit('Sources have not passed full 20,000-price simulation')
    command=[checks.tool('iceprog',env),str(image)]
    print('Verified bitstream:',image)
    print('Command:',' '.join(command))
    if a.flash:subprocess.run(command,env=env,check=True)
    else:print('Validation only. Add --flash to program the connected board.')
if __name__=='__main__':main()
