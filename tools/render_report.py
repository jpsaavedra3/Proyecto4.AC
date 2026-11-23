#!/usr/bin/env python3
"""Render with the original GitHub report's structure, fonts and cover.

Requires reportlab, pypdf, and locally installed Arial / Calibri fonts.
Font files are never copied into this repository; only PDF subsets are embedded.
"""
import html
import json
import math
import os
import re
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, LongTable, PageBreak,
    PageTemplate, Paragraph, Spacer, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
PAGE = (596, 842)
WIDTH = 452
TOC_LABELS = [
    ('section1', '1. ALGORITMO DE PREDICCIÓN Y DECISIÓN'),
    ('section2', '2. IMPLEMENTACIÓN EN ASSEMBLY'),
    ('section3', '3. CO-DISEÑO HARDWARE/SOFTWARE'),
    ('figure1', 'Figura 1: Roofline de Espino a 25 MHz con el kernel de las tres variantes'),
]


def fonts():
    directory = Path(os.environ.get('DOC_FONTS_DIR', 'C:/Windows/Fonts'))
    for name, filename in [('Arial', 'arial.ttf'), ('ArialBold', 'arialbd.ttf'),
                           ('CalibriBold', 'calibrib.ttf')]:
        path = directory / filename
        if not path.is_file():
            raise SystemExit(f'Missing original font: {path}. Set DOC_FONTS_DIR to the font directory.')
        pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='ArialBold',
                                  italic='Arial', boldItalic='ArialBold')


def styles():
    return {
        'body': ParagraphStyle('Body', fontName='Arial', fontSize=11,
                               leading=18.975, firstLineIndent=36,
                               alignment=TA_JUSTIFY, spaceAfter=10),
        'main': ParagraphStyle('Main', fontName='CalibriBold', fontSize=12,
                               leading=20, spaceAfter=8, spaceBefore=12,
                               keepWithNext=True),
        'sub': ParagraphStyle('Sub', fontName='CalibriBold', fontSize=11,
                              leading=14, spaceBefore=14, spaceAfter=7,
                              keepWithNext=True),
        'index': ParagraphStyle('Index', fontName='CalibriBold', fontSize=14,
                                leading=18, spaceAfter=12),
        'bullet': ParagraphStyle('Bullet', fontName='Arial', fontSize=11,
                                 leading=18.975, leftIndent=36, bulletIndent=18,
                                 bulletFontName='Arial', bulletFontSize=11,
                                 alignment=TA_JUSTIFY, spaceAfter=4),
        'cell': ParagraphStyle('Cell', fontName='Arial', fontSize=10,
                               leading=11.5, alignment=TA_LEFT),
        'header': ParagraphStyle('Header', fontName='ArialBold', fontSize=10,
                                 leading=11.5, alignment=TA_LEFT),
        'caption': ParagraphStyle('Caption', fontName='Arial', fontSize=10,
                                  leading=12, alignment=TA_CENTER,
                                  spaceBefore=6, spaceAfter=10),
    }


def paragraph(text, style):
    text = html.escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return Paragraph(text, style)


class IndexEntries(Flowable):
    def __init__(self, pages):
        super().__init__()
        self.pages = pages
        self.width, self.height = WIDTH, 76

    def draw(self):
        for i, (key, label) in enumerate(TOC_LABELS):
            y = self.height - 12 - i * 15.6
            self.canv.setFont('ArialBold' if i < 3 else 'Arial', 11 if i < 3 else 10)
            self.canv.drawString(0 if i < 3 else 36, y, label)
            self.canv.setFont('Arial', 10)
            self.canv.drawRightString(WIDTH, y, str(self.pages.get(key, '')))


class ReportDocument(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=PAGE, leftMargin=72, rightMargin=72,
                         topMargin=72, bottomMargin=72, allowSplitting=True,
                         title='Arquitectura de Computadores - Proyecto 4', author='Grupo 15')
        frame = Frame(72, 72, WIDTH, PAGE[1] - 144, id='body',
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='report', frames=frame, onPage=self.page_number))
        self.locations = {}

    @staticmethod
    def page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('Arial', 11)
        canvas.drawRightString(524, PAGE[1] - 45.5, str(doc.page))
        canvas.restoreState()

    def afterFlowable(self, flowable):
        key = getattr(flowable, '_outline_key', None)
        if key:
            self.locations[key] = self.page


def roofline(data):
    d = Drawing(380, 256)
    x0, y0, w, h = 48, 42, 312, 188
    xmin, xmax, ymin, ymax = .01, 100, 1e6, 6e7
    def x(value): return x0 + w * math.log10(value / xmin) / math.log10(xmax / xmin)
    def y(value): return y0 + h * math.log10(value / ymin) / math.log10(ymax / ymin)
    gray = colors.HexColor('#bfbfbf')
    for value in [.01, .1, 1, 10, 100]:
        d.add(Line(x(value), y0, x(value), y0+h, strokeColor=gray,
                   strokeWidth=.4, strokeDashArray=[2, 2]))
        d.add(String(x(value), y0-12, f'{value:g}', textAnchor='middle',
                     fontName='Arial', fontSize=8))
    for value in [1e6, 2e6, 5e6, 1e7, 2e7, 5e7]:
        d.add(Line(x0, y(value), x0+w, y(value), strokeColor=gray,
                   strokeWidth=.4, strokeDashArray=[2, 2]))
        d.add(String(x0-6, y(value)-3, f'{value/1e6:g} M', textAnchor='end',
                     fontName='Arial', fontSize=8))
    for a,b,c,e in [(x0,y0,x0+w,y0),(x0,y0,x0,y0+h),
                     (x0+w,y0,x0+w,y0+h),(x0,y0+h,x0+w,y0+h)]:
        d.add(Line(a,b,c,e,strokeColor=colors.black,strokeWidth=.6))
    for peak,dash in [(12.5e6,None),(37.5e6,[4,2])]:
        points=[]
        start=max(xmin,ymin/50e6)
        for i in range(120):
            xx=start*(xmax/start)**(i/119)
            points.extend([x(xx),y(min(peak,50e6*xx))])
        d.add(PolyLine(points,strokeColor=colors.black,strokeWidth=1,strokeDashArray=dash))
        d.add(String(x(2),y(peak)+4,f'Techo {peak/1e6:g} Mops/s',fontName='Arial',fontSize=8))
    def marker(index, cx, cy, radius):
        # Preserve the original report figure's blue, orange and green palette.
        color=colors.HexColor(['#1f77b4','#ff7f0e','#2ca02c'][index])
        return Circle(cx,cy,radius,fillColor=color,strokeColor=color,strokeWidth=.8)
    for i,variant in enumerate(data['variants']):
        xx,yy=x(variant['intensity_ops_per_byte']),y(variant['ops_per_second'])
        d.add(marker(i,xx,yy,3))
        d.add(String(xx+6,yy+[-1,3,-6][i],str(i),fontName='Arial',fontSize=8))
        ly=y0+16+(2-i)*12
        d.add(marker(i,x0+w-123,ly,2.5))
        label=f'Variante {i}: {variant["ops_per_second"]/1e6:.2f} Mops/s'
        d.add(String(x0+w-116,ly-3,label,fontName='Arial',fontSize=8))
    d.add(String(x0+w/2,10,'Intensidad operacional (ops/byte)',
                 textAnchor='middle',fontName='Arial',fontSize=9))
    d.add(String(10,y0+h/2,'Ops/s',angle=90,textAnchor='middle',fontName='Arial',fontSize=9))
    d.hAlign='CENTER'
    d._outline_key='figure1'
    return d


TABLE_WIDTHS = [
    [63,108,70,47,76,88], [91,361], [81,77,55,64,54,121],
    [45,67,109,148,83], [220,90,80,62], [109,64,148,53,78],
    [94,50,46,48,36,52,63,63],
]


def story_from_markdown(text,data,s,pages):
    story=[]
    lines=text.splitlines()
    i=0
    table_number=0
    pending=[]
    def flush():
        if pending:
            story.append(paragraph(' '.join(pending),s['body']))
            pending.clear()
    while i<len(lines):
        line=lines[i].strip()
        if line=='[[INDICE]]':
            flush()
            story.extend([IndexEntries(pages),PageBreak()])
        elif line=='[[FIGURA_1]]':
            flush()
            story.append(roofline(data))
        elif line.startswith('# '):
            flush()
            title=line[2:]
            if title=='ÍNDICE':
                story.append(paragraph(title,s['index']))
            else:
                p=paragraph(title,s['main'])
                p._outline_key='section'+title[0]
                story.append(p)
        elif line.startswith('## '):
            flush()
            story.append(paragraph(line[3:],s['sub']))
        elif line.startswith('| '):
            flush()
            rows=[]
            while i<len(lines) and lines[i].startswith('| '):
                cells=[c.strip() for c in lines[i].strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',c) for c in cells):
                    rows.append(cells)
                i+=1
            widths=TABLE_WIDTHS[table_number]
            table_number+=1
            cells=[[paragraph(c,s['header' if r==0 else 'cell']) for c in row]
                   for r,row in enumerate(rows)]
            table=LongTable(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([
                ('GRID',(0,0),(-1,-1),.5,colors.black),
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f2f2f2')),
                ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LEFTPADDING',(0,0),(-1,-1),3),
                ('RIGHTPADDING',(0,0),(-1,-1),3),
                ('TOPPADDING',(0,0),(-1,-1),3.375),
                ('BOTTOMPADDING',(0,0),(-1,-1),3.375),
            ]))
            while i<len(lines) and not lines[i].strip(): i+=1
            if i<len(lines) and lines[i].startswith('Tabla '):
                story.append(KeepTogether([table,paragraph(lines[i],s['caption'])]))
                i+=1
            else:
                story.extend([table,Spacer(1,10)])
            continue
        elif line.startswith(('Tabla ','Figura ')):
            flush()
            story.append(paragraph(line,s['caption']))
        elif line.startswith('- '):
            flush()
            p=paragraph(line[2:],s['bullet'])
            p.bulletText='•'
            story.append(p)
        elif not line:
            flush()
        else:
            pending.append(line)
        i+=1
    flush()
    return story


def main():
    fonts()
    s=styles()
    text=(ROOT/'docs'/'Informe_Proyecto4.md').read_text(encoding='utf-8')
    data=json.loads((ROOT/'docs'/'results'/'summary.json').read_text(encoding='utf-8'))
    out=ROOT/'build'/'report'
    out.mkdir(parents=True,exist_ok=True)
    pages={}
    for n in (1,2):
        doc=ReportDocument(out/f'body_pass{n}.pdf')
        doc.build(story_from_markdown(text,data,s,pages))
        if n==2 and doc.locations!=pages:
            raise RuntimeError('Index pagination changed between passes')
        pages=doc.locations
    writer=PdfWriter()
    writer.append(PdfReader(ROOT/'docs'/'style'/'cover_original.pdf'))
    writer.append(PdfReader(out/'body_pass2.pdf'))
    writer.add_metadata({'/Title':'Arquitectura de Computadores - Proyecto 4',
                         '/Author':'Grupo 15',
                         '/Subject':'Resultados actualizados con formato del informe original'})
    path=ROOT/'docs'/'Informe_Proyecto4.pdf'
    with path.open('wb') as f:
        writer.write(f)
    print(f'Wrote {path} ({len(writer.pages)} pages), index: {pages}')


if __name__=='__main__':
    main()
