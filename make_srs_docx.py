from pathlib import Path
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION

root = Path(__file__).parent
source = (root / 'SRS-First-Portion.md').read_text(encoding='utf-8').splitlines()
doc = Document()
sec = doc.sections[0]
sec.top_margin = Inches(.7); sec.bottom_margin = Inches(.7)
sec.left_margin = Inches(.8); sec.right_margin = Inches(.8)
styles = doc.styles
styles['Normal'].font.name = 'Aptos'; styles['Normal'].font.size = Pt(10)
styles['Normal'].font.color.rgb = RGBColor(45, 55, 72)
for name,size,color in [('Heading 1',18,'12304A'),('Heading 2',14,'147D85'),('Heading 3',11,'147D85')]:
    styles[name].font.name='Aptos Display'; styles[name].font.size=Pt(size); styles[name].font.bold=True; styles[name].font.color.rgb=RGBColor.from_string(color)

def add_cell(cell, text, header=False):
    cell.text = text
    for p in cell.paragraphs:
        for r in p.runs:
            r.font.name='Aptos'; r.font.size=Pt(9); r.bold=header

i=0
while i < len(source):
    line=source[i].rstrip()
    if not line:
        i+=1; continue
    if line.startswith('|'):
        rows=[]
        while i<len(source) and source[i].startswith('|'):
            cells=[c.strip() for c in source[i].strip('|').split('|')]
            if not all(re.fullmatch(r'[-: ]+',c or '-') for c in cells): rows.append(cells)
            i+=1
        if rows:
            table=doc.add_table(rows=0, cols=len(rows[0])); table.style='Light Shading Accent 1'
            for ri,row in enumerate(rows):
                cells=table.add_row().cells
                for j,val in enumerate(row): add_cell(cells[j],val,ri==0)
        continue
    if line.startswith('```mermaid'):
        i+=1; diagram=[]
        while i<len(source) and not source[i].startswith('```'):
            diagram.append(source[i]); i+=1
        p=doc.add_paragraph(); r=p.add_run('Use case diagram (text representation)'); r.bold=True
        p=doc.add_paragraph('Actors: Caller; VoIP Provider / PBX; Authorized Alkhidmat Staff; System Administrator.\nSystem use cases: Connect call and audio; speak a query; process speech; search approved FAQs; receive spoken answer; request repetition; request human escalation; maintain FAQs; manage access; review permitted logs and reports.')
        p.paragraph_format.left_indent=Inches(.2)
        i+=1; continue
    if line.startswith('# '):
        p=doc.add_paragraph(style='Title'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run(line[2:]); i+=1; continue
    if line.startswith('## '):
        p=doc.add_paragraph(style='Subtitle'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run(line[3:]); i+=1; continue
    if line.startswith('### '):
        p=doc.add_paragraph(line[4:],style='Heading 1'); i+=1; continue
    if line.startswith('**Version:**'):
        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run(line.replace('  ',' ')); i+=1; continue
    if line.startswith('**') and line.endswith('**'):
        p=doc.add_paragraph(); p.add_run(line.strip('*')).bold=True; i+=1; continue
    if line.startswith('- '):
        p=doc.add_paragraph(style='List Bullet'); p.add_run(line[2:]); i+=1; continue
    m=re.match(r'^(\d+)\.\s+(.*)',line)
    if m:
        p=doc.add_paragraph(style='List Number'); p.add_run(m.group(2)); i+=1; continue
    p=doc.add_paragraph()
    # Preserve requirement IDs in bold.
    parts=re.split(r'(\*\*[^*]+\*\*)',line)
    for part in parts:
        if part.startswith('**') and part.endswith('**'): p.add_run(part[2:-2]).bold=True
        else: p.add_run(part)
    i+=1

for section in doc.sections:
    footer=section.footer.paragraphs[0]
    footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run('Alkhidmat Call Assistance System | SRS 1 working draft').font.size=Pt(8)
output=root/'Alkhidmat-SRS-First-Portion.docx'
doc.save(output)
print(output)
