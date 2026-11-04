from pathlib import Path
import io,json,re,html,base64
FORMATS=["txt","md","json","csv","xlsx","docx","pdf","pptx","png","mp3"]

def load_features():
    global OpenAI, pd, PILImage, ImageOps, Presentation, Inches, Pt, Document, WordPt
    global Font, PatternFill, Alignment, PdfReader, PdfWriter, SimpleDocTemplate, Paragraph, Spacer
    global ParagraphStyle, pdfmetrics, UnicodeCIDFont, TTFont
    print('[ABLE] feature imports start', flush=True)
    from openai import OpenAI
    import pandas as pd
    from PIL import Image as PILImage, ImageOps
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from docx import Document
    from docx.shared import Pt as WordPt
    from openpyxl.styles import Font, PatternFill, Alignment
    from pypdf import PdfReader, PdfWriter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont
    print('[ABLE] feature imports ready', flush=True)

def load_pdf_font():
    name = "AbleKorean"
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    for p in [Path('/usr/share/fonts/truetype/nanum/NanumGothic.ttf'), Path('C:/Windows/Fonts/malgun.ttf')]:
        if p.is_file():
            pdfmetrics.registerFont(TTFont(name, str(p)))
            return name
    raise ValueError('한글 PDF 폰트 없음: packages.txt의 fonts-nanum 설치를 확인하세요.')

def validate_table(text):
    data = json.loads(text)
    columns, rows = data["columns"], data["rows"]
    if not columns or not all(isinstance(c, str) for c in columns):
        raise ValueError("표의 열 이름 형식이 올바르지 않습니다.")
    if len(columns) != len(set(columns)):
        raise ValueError("표에 중복된 열 이름이 있습니다.")
    if not isinstance(rows, list) or any(not isinstance(r,list) or len(r)!=len(columns) for r in rows):
        raise ValueError("표의 열 개수가 일치하지 않습니다.")
    if any(isinstance(v,(dict,list)) for row in rows for v in row):
        raise ValueError("셀에는 단일 값만 사용할 수 있습니다.")
    return pd.DataFrame(rows, columns=columns)

def save_artifact(item, index, directory, client, models):
    load_features()
    request_dir = Path(directory)
    IMAGE_MODEL = models["IMAGE_MODEL"]
    TTS_MODEL = models["TTS_MODEL"]
    fmt = item["format"]
    if fmt not in FORMATS:
        raise ValueError("지원하지 않는 결과 형식")
    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', str(item["name"]))[:70].strip(' .') or 'result'
    stem = Path(stem).stem
    target = request_dir / f"{index:02d}_{stem}.{fmt}"
    content = item["content"]
    if not isinstance(content,str) or not content.strip():
        raise ValueError("생성할 내용이 비어 있습니다.")
    if fmt in ["txt", "md"]:
        target.write_text(content,encoding="utf-8")
    elif fmt == "json":
        target.write_text(json.dumps(json.loads(content),ensure_ascii=False,indent=2),encoding="utf-8")
    elif fmt in ["csv", "xlsx"]:
        df = validate_table(content)
        # 데이터 문자열을 스프레드시트 실행 수식으로 저장하지 않음
        df = df.map(lambda v: "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v)
        if fmt == "csv":
            df.to_csv(target,index=False,encoding="utf-8-sig")
        else:
            with pd.ExcelWriter(target,engine="openpyxl") as writer:
                df.to_excel(writer,index=False,sheet_name="결과")
                ws=writer.sheets["결과"];ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
                for cell in ws[1]:
                    cell.font=Font(color="FFFFFF",bold=True);cell.fill=PatternFill('solid',fgColor='0E7490')
                for col in ws.columns:
                    ws.column_dimensions[col[0].column_letter].width=min(50,max(14,max(len(str(c.value or '')) for c in col)*1.5))
                for row in ws.iter_rows(min_row=2):
                    for cell in row:cell.alignment=Alignment(vertical='top',wrap_text=True)
    elif fmt == "docx":
        doc=Document();doc.styles['Normal'].font.name='맑은 고딕';doc.styles['Normal'].font.size=WordPt(11)
        for line in content.splitlines():
            if line.startswith('# '):doc.add_heading(line[2:],level=1)
            elif line.startswith('## '):doc.add_heading(line[3:],level=2)
            else:doc.add_paragraph(line)
        doc.save(target)
    elif fmt == "pdf":
        font=load_pdf_font()
        style=ParagraphStyle('body',fontName=font,fontSize=11,leading=18,wordWrap='CJK',spaceAfter=8)
        heading=ParagraphStyle('heading',parent=style,fontSize=17,leading=24,spaceAfter=12)
        story=[]
        for line in content.splitlines():
            story.append(Paragraph(html.escape(line.lstrip('# ').strip()),heading if line.startswith('#') else style) if line.strip() else Spacer(1,8))
        SimpleDocTemplate(str(target),rightMargin=42,leftMargin=42,topMargin=42,bottomMargin=42).build(story)
    elif fmt == "pptx":
        data=json.loads(content)
        if not isinstance(data.get('slides'),list) or not data['slides']:raise ValueError('슬라이드 내용이 없습니다.')
        prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
        for spec in data['slides']:
            title=spec['title'];bullets=spec['bullets']
            if not isinstance(title,str) or len(title)>80 or not isinstance(bullets,list) or any(not isinstance(b,str) or len(b)>160 for b in bullets):
                raise ValueError('PPT 제목/요점 길이 또는 형식 오류. 짧은 요점으로 다시 요청하세요.')
            # 긴 슬라이드는 내용을 잘라내지 않고 나누어 작성
            for start in range(0,max(1,len(bullets)),4):
                slide=prs.slides.add_slide(prs.slide_layouts[6])
                head=slide.shapes.add_textbox(Inches(.6),Inches(.4),Inches(12.1),Inches(1.25)).text_frame
                head.word_wrap=True;head.text=title+(' (계속)' if start else '')
                for p in head.paragraphs:p.font.name='맑은 고딕';p.font.size=Pt(28);p.font.bold=True
                body=slide.shapes.add_textbox(Inches(.7),Inches(1.9),Inches(12),Inches(4.9)).text_frame
                body.word_wrap=True
                for j,bullet in enumerate(bullets[start:start+4]):
                    p=body.paragraphs[0] if j==0 else body.add_paragraph()
                    p.text='• '+bullet;p.font.name='맑은 고딕';p.font.size=Pt(18);p.space_after=Pt(18)
        prs.save(target)
    elif fmt == 'png':
        response=client.with_options(timeout=180, max_retries=0).images.generate(model=IMAGE_MODEL,prompt=content,size='1024x1024',quality='low',n=1,output_format='png')
        if not response.data or not response.data[0].b64_json:raise ValueError('이미지 생성 응답 없음')
        data=base64.b64decode(response.data[0].b64_json)
        with PILImage.open(io.BytesIO(data)) as im:im.verify()
        target.write_bytes(data)
    elif fmt == 'mp3':
        if len(content)>4000:raise ValueError('음성 원고를 4000자 이내로 요청하세요.')
        with client.audio.speech.with_streaming_response.create(model=TTS_MODEL,voice='nova',input=content) as response:
            response.stream_to_file(target)
    if not target.is_file() or not target.stat().st_size:raise ValueError('결과 파일 저장 실패')
    return target
