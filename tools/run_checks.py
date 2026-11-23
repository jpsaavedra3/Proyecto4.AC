#!/usr/bin/env python3
"""Portable FPGA checks. All failures are fatal; original course testbench is preserved."""
import argparse,csv,hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ref'))
import trader
PROGRAMS=['trade','trade_shifter','trade_ema']

def source_manifest(v):
    files=[*sorted((ROOT/'rtl').rglob('*.v')),ROOT/'goboard.pcf',
           ROOT/'sw'/f'{PROGRAMS[v]}.s',ROOT/'sw'/f'{PROGRAMS[v]}.hex',
           ROOT/'tools'/'pochoasm.py',ROOT/'tools'/'generate_trade.py',ROOT/'ref'/'trader.py']
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}

def setup(suite=None):
    os.chdir(ROOT)
    suite=Path(suite or os.environ.get('OSS_CAD_SUITE',ROOT.parent/'toolchain'/'oss-cad-suite')).resolve()
    env=os.environ.copy()
    if suite.exists():env['PATH']=str(suite/'bin')+os.pathsep+str(suite/'lib')+os.pathsep+env.get('PATH','')
    tmp=ROOT/'build'/'tmp';tmp.mkdir(parents=True,exist_ok=True)
    env['TMP']=env['TEMP']=env['TMPDIR']=str(tmp)
    env['YOSYSHQ_ROOT']=str(suite)+os.sep
    return suite,env

def tool(name,env):
    value=shutil.which(name,path=env['PATH'])
    if not value:raise RuntimeError(f'{name} missing; set OSS_CAD_SUITE or use --toolchain')
    return value

def command(args,env,log):
    args=list(args)
    compiler=Path(args[0]).stem.lower()=='iverilog'
    workaround=compiler and os.name=='nt' and env.get('IVERILOG_ALLOW_TEARDOWN_CRASH')=='1'
    if workaround:args.insert(1,'-v')
    output=Path(args[args.index('-o')+1]) if compiler and '-o' in args else None
    if output is not None and output.exists():output.unlink() # never accept a stale compiler output
    log=Path(log);log.parent.mkdir(parents=True,exist_ok=True)
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    with log.open('w',encoding='utf-8') as f:
        r=subprocess.run([str(x) for x in args],env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=flags)
    text=log.read_text(errors='replace')
    recovered=False
    if r.returncode in (3221225477,-1073741819) and workaround:
        # Explicit opt-in for an observed Windows compiler crash AFTER "DONE.".
        # The freshly generated program must still execute successfully in vvp,
        # pass all assertions and match every reference row. Other failures stay fatal.
        if 'DONE.' in text and output is not None and output.is_file() and output.stat().st_size>100:
            recovered=True
            note=f'WARNING: Windows Icarus exit crash after code generation; validating fresh {output} in vvp.'
            with log.open('a',encoding='utf-8') as f:f.write('\n'+note+'\n')
            print(note,flush=True)
    if r.returncode and not recovered:
        raise RuntimeError(f'{args[0]} failed ({r.returncode}); {log}\n'+log.read_text(errors='replace')[-4000:])
    return text

def sources(suite):
    cells=suite/'share'/'yosys'/'ice40'/'cells_sim.v'
    if not cells.exists():
        config=shutil.which('yosys-config')
        if config:cells=Path(subprocess.check_output([config,'--datdir'],text=True).strip())/'ice40'/'cells_sim.v'
    if not cells.exists():raise RuntimeError('Cannot locate ice40/cells_sim.v')
    return [cells,*sorted((ROOT/'rtl').glob('*.v')),*sorted((ROOT/'rtl'/'espino_core').glob('*.v'))]

def assemble(env):
    for p in PROGRAMS:
        command([sys.executable,'tools/pochoasm.py',f'sw/{p}.s','-o',f'sw/{p}.hex'],env,f'build/asm_{p}.log')

def units(suite,env):
    for name,src in [('shifter','espino_alu'),('ema','espino_ema')]:
        exe=f'build/tb_{name}'
        command([tool('iverilog',env),'-g2012','-s',f'tb_{name}','-o',exe,f'rtl/espino_core/{src}.v',f'tb/tb_{name}.sv'],env,f'build/unit_{name}_compile.log')
        text=command([tool('vvp',env),'-n',exe],env,f'build/unit_{name}.log')
        if 'PASS' not in text or 'FAIL' in text:raise RuntimeError(text)
        print(text.strip(),flush=True)

def compare(path,prices):
    expected=trader.simular(prices,trader.Trader(),return_rows=True)
    with Path(path).open() as f:actual=list(csv.DictReader(f))
    if len(actual)!=len(expected):raise AssertionError(f'{path}: wrong row count')
    for r,e in zip(actual,expected):
        got=(int(r['tick']),int(r['precio']),r['decision'].lower(),int(r['caja']),int(r['acciones']),int(r['patrimonio']))
        if got!=e:raise AssertionError(f'{path}: tick {e[0]} {got} != {e}')

def official(suite,env,ticks=2000):
    text=(ROOT/'tb'/'tb_proyecto_4.sv').read_text()
    text=text.replace('"tb/practica.csv"','"tb/practica_meta.csv"')
    text=re.sub(r'(NTICKS\s*=\s*)2000;',rf'\g<1>{ticks};',text)
    src=ROOT/'build'/'tb_official_configured.sv';src.write_text(text)
    command([tool('iverilog',env),'-g2012','-s','tb_proyecto_4','-o','build/tb_official',*sources(suite),src],env,'build/official_compile.log')
    out=command([tool('vvp',env),'-n','build/tb_official'],env,'build/official.log')
    if 'Testbenchs aprobados: 4/4' not in out or 'FAIL' in out:raise RuntimeError(out)
    with (ROOT/'tb'/'practica_meta.csv').open() as f:pp=[int(r['price']) for r in csv.DictReader(f)][:ticks]
    compare('decisiones.csv',pp)
    print(f'PASS official testbench: 4/4; {ticks} rows match reference',flush=True)

def sim_variant(v,suite,env,ticks,period):
    initial_sources=source_manifest(v)
    p=PROGRAMS[v];dest=f'build/medicion_v{v}.csv'
    exe=f'build/tb_med_v{v}'
    args=[tool('iverilog',env),'-g2012','-s','tb_medicion','-o',exe,
          f'-Ptb_medicion.VARIANTE={v}',f'-Ptb_medicion.PROGRAMA="sw/{p}.hex"',
          f'-Ptb_medicion.NTICKS={ticks}',f'-Ptb_medicion.PERIODO_NS={period}',
          f'-Ptb_medicion.SALIDA="{dest}"',f'-Ptb_medicion.PERFIL="build/perfil_v{v}.csv"',
          f'-Ptb_medicion.LATENCIAS="build/latencias_v{v}.csv"',
          *sources(suite),'tb/tb_medicion.sv']
    command(args,env,f'build/medicion_v{v}_compile.log')
    command([tool('vvp',env),'-n',exe],env,f'build/medicion_v{v}.log')
    with (ROOT/'tb'/'practica_meta.csv').open() as f:prices=[int(r['price']) for r in csv.DictReader(f)][:ticks]
    compare(dest,prices)
    with open(f'build/latencias_v{v}.csv') as f:rows=list(csv.DictReader(f))
    if len(rows) != ticks:raise AssertionError('Missing latency rows')
    reference=trader.Trader()
    for n,(r,pn) in enumerate(zip(rows,prices)):
        if int(r['tick'])!=n or int(r['precio'])!=pn or int(r['decision_calculada'],16)!=reference.tick(pn):
            raise AssertionError(f'Latency/calculated decision mismatch at {n}')
    counts=[int(r['ciclos']) for r in rows]
    if source_manifest(v)!=initial_sources:raise RuntimeError('Sources changed while simulation was running')
    result=dict(variant=v,ticks=ticks,period_ns=period,cycles_mean=sum(counts)/len(counts),cycles_max=max(counts),reference_match=True)
    print('PASS HDL',json.dumps(result),flush=True)
    return result

def synth(v,suite,env):
    initial_sources=source_manifest(v)
    d=ROOT/'build'/f'v{v}';d.mkdir(parents=True,exist_ok=True)
    files=' '.join(p.as_posix() for p in [*Path('rtl').glob('*.v'),*Path('rtl/espino_core').glob('*.v')])
    ys=f'read_verilog {files}; chparam -set Variant {v} -set MemFile "sw/{PROGRAMS[v]}.hex" pochoco_soc; synth_ice40 -top pochoco_soc -json build/v{v}/pochoco_soc.json; stat'
    command([tool('yosys',env),'-Q','-l',str(d/'yosys.log'),'-p',ys],env,d/'yosys_stdout.log')
    out=command([tool('nextpnr-ice40',env),'--hx1k','--package','vq100','--freq','25','--seed','1','--json',str(d/'pochoco_soc.json'),'--pcf','goboard.pcf','--asc',str(d/'pochoco_soc.asc'),'--report',str(d/'timing.json')],env,d/'nextpnr.log')
    command([tool('icepack',env),str(d/'pochoco_soc.asc'),str(d/'pochoco_soc.bin')],env,d/'icepack.log')
    fmax=re.findall(r'Max frequency for clock .*?: ([\d.]+) MHz',out)
    lc=re.findall(r'ICESTORM_LC:\s+(\d+)/\s*(\d+)',out)
    bram=re.findall(r'ICESTORM_RAM:\s+(\d+)/\s*(\d+)',out)
    text=(d/'yosys.log').read_text(errors='replace')
    last=text[text.rfind('=== pochoco_soc ==='):]
    lut=re.search(r'(\d+)\s+(?:cells\s+)?SB_LUT4|SB_LUT4\s+(\d+)',last)
    result=dict(variant=v,lc=int(lc[-1][0]) if lc else None,lc_total=int(lc[-1][1]) if lc else None,bram=int(bram[-1][0]) if bram else None,lut=int(lut.group(1) or lut.group(2)) if lut else None,fmax_mhz=float(fmax[-1]) if fmax else None,timing_25mhz_pass=True,bitstream_bytes=(d/'pochoco_soc.bin').stat().st_size)
    if source_manifest(v)!=initial_sources:raise RuntimeError('Sources changed during synthesis')
    (d/'provenance.json').write_text(json.dumps(dict(sources=initial_sources,bitstream_sha256=hashlib.sha256((d/'pochoco_soc.bin').read_bytes()).hexdigest()),indent=2))
    print('PASS synthesis',json.dumps(result),flush=True)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['unit','official','sim','synth','all'])
    ap.add_argument('--toolchain');ap.add_argument('--ticks',type=int,default=20000)
    ap.add_argument('--period',type=int,default=100000);ap.add_argument('--variant',type=int,choices=[0,1,2]);ap.add_argument('--jobs',type=int,default=3)
    ap.add_argument('--allow-compiler-exit-crash',action='store_true',help='Windows only: accept fresh output after logged DONE, then require vvp/assertions/reference comparison')
    ap.add_argument('--no-assemble',action='store_true',help='Use already verified HEX files without rewriting them')
    a=ap.parse_args();suite,env=setup(a.toolchain)
    if not a.no_assemble:assemble(env)
    if a.allow_compiler_exit_crash:env['IVERILOG_ALLOW_TEARDOWN_CRASH']='1'
    dest=ROOT/'docs'/'results';dest.mkdir(parents=True,exist_ok=True)
    if a.mode in ('unit','all'):units(suite,env)
    if a.mode in ('official','all'):official(suite,env)
    variants=[a.variant] if a.variant is not None else [0,1,2]
    for mode,fn in [('sim',lambda v:sim_variant(v,suite,env,a.ticks,a.period)),('synth',lambda v:synth(v,suite,env))]:
        if a.mode in (mode,'all'):
            with ThreadPoolExecutor(max_workers=a.jobs) as pool:results=list(pool.map(fn,variants))
            (dest/f'{mode}.json').write_text(json.dumps(results,indent=2))
            if mode=='sim' and a.ticks==20000:
                validation_path=dest/'validation_sources.json'
                proven=json.loads(validation_path.read_text()) if validation_path.exists() else {}
                for v in variants:proven[str(v)]=source_manifest(v)
                validation_path.write_text(json.dumps(proven,indent=2))
if __name__=='__main__':main()
