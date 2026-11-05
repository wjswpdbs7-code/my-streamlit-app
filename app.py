from demo_support import due_read as _due_read, UnknownDue
import os
import base64
import json
import requests
import io
import streamlit as st
from openai import OpenAI

class DeferredOpenAI:

    def __init__(self):
        self._client = None

    def __getattr__(self, attr):
        try:
            token = st.secrets.get('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY', ''))
        except (FileNotFoundError, KeyError):
            token = os.getenv('OPENAI_API_KEY', '')
        if not token:
            raise ValueError('OpenAI API 키가 없습니다. Streamlit Secrets에 OPENAI_API_KEY를 설정하세요.')
        if self._client is None:
            self._client = OpenAI(api_key=token, timeout=120, max_retries=0)
        return getattr(self._client, attr)
client = DeferredOpenAI()
st.set_page_config(page_title='음성 AI 서비스', page_icon='🤖', layout='wide')
sys_role = "\n당신은 마케팅팀의 우수 직원 '김 대리(Marketing Data Analyst)'를 밀착 보조하는 전문 AI 개인 비서 '에이블'입니다.\n다음과 같은 역할을 수행합니다:\n1. 마케팅 회의록을 분석하고 핵심 업무 지시사항을 정확하게 추출합니다.\n2. 데이터 기반의 마케팅 전략 수립과 콘텐츠 기획을 적극적으로 지원합니다.\n3. 사용자의 질문에 항상 정중하고 전문적인 어조로 친절하게 응대합니다.\n"
if 'messages' not in st.session_state:
    st.session_state.messages = []
import hashlib
import re
import smtplib
import uuid
from datetime import date, datetime, timedelta
from email.message import EmailMessage
import pandas as pd
ss = st.session_state
from zoneinfo import ZoneInfo
TODAY = datetime.now(ZoneInfo('Asia/Seoul')).date()
MODEL_MAP = {'Luna 6': 'gpt-4o-mini', 'GPT-4': 'gpt-4', 'GPT-4o': 'gpt-4o', 'GPT-4o mini': 'gpt-4o-mini', 'GPT-4.1': 'gpt-4.1', 'GPT-4.1 mini': 'gpt-4.1-mini'}
LEGACY_MODELS = {'gpt-4'}
TTS_MODEL = 'gpt-4o-mini-tts'
VOICES = ['alloy', 'nova', 'shimmer', 'coral', 'echo', 'onyx', 'fable']
MENUS = ['🏠 홈', '💬 채팅', '📁 자료실', '✅ 내 작업', '👥 팀 업무 현황', '📧 이메일 관리', '⚙️ 설정']
QUICK_PROMPTS = ['📝 회의록 요약해줘', '📋 회의록에서 업무 뽑아서 내 작업에 추가해줘', '📅 오늘 일정 정리해줘', '✅ 우선순위 높은 업무 알려줘', '📊 캠페인 성과 분석 방법 알려줘']
CHAT_TYPES = ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'txt', 'md', 'csv', 'docx']
IMG_MIME = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp'}
INTENT_LABEL = {'chat': '💬 일반 대화', 'email': '📧 이메일 작성·발송', 'calendar': '📅 캘린더 일정', 'task': '✅ 업무 등록', 'translate': '🌐 번역'}
EMAIL_RE = re.compile('[\\w.+-]+@[\\w-]+(\\.[\\w-]+)+')
DATA_FILE = 'able_final_demo_settings.json'
SAVE_KEYS = ['settings', 'contacts', 'sent']
LIB_DIR = 'library'
KEY_FILE = 'api_key.txt'
CONFIRM_RE = re.compile('(보내|발송|전송|ㅇㅇ|^응|^네|^예|^좋아|^그래)')

def _defaults():
    return {'menu': MENUS[0], 'settings': {'name': '김 대리', 'team': '마케팅팀', 'role': 'Marketing Data Analyst', 'model': 'Luna 6', 'common_prompt': '', 'voice': 'alloy', 'tts_on': False, 'autoplay': False, 'stt_lang': 'ko', 'auto_send': False}, 'contacts': [], 'tasks': [], 'schedule': [], 'inbox': [], 'sent': [], 'smtp': {}, 'library': [], 'suggestions': [], 'pending_prompt': None, 'attach_ids': [], 'chat_key': 0, 'lib_key': 0, 'last_audio': None, 'briefing': '', 'open_tools': False, 'mail_to': '', 'mail_subject': '', 'mail_body': '', 'notice': ''}

def load_data():
    try:
        with open(DATA_FILE, encoding='utf-8') as fp:
            return json.load(fp)
    except Exception:
        return {}

def save_data():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as fp:
            json.dump({k: ss[k] for k in SAVE_KEYS}, fp, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        st.sidebar.caption(f'⚠️ 저장 실패: {e}')
for _k, _v in _defaults().items():
    if _k not in ss:
        ss[_k] = _v
if 'data_loaded' not in ss:
    _saved = load_data()
    if isinstance(_saved.get('settings'), dict):
        ss.settings.update(_saved['settings'])
    for _k in ('contacts', 'sent'):
        if isinstance(_saved.get(_k), list):
            ss[_k] = _saved[_k]
    if ss.settings.get('model') not in MODEL_MAP:
        ss.settings['model'] = 'Luna 6'
    ss.data_loaded = True

def model_id():
    return MODEL_MAP.get(ss.settings['model'], 'gpt-4o-mini')

def to_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return TODAY

def dday(d):
    n = (d - TODAY).days
    return 'D-day' if n == 0 else f'D-{n}' if n > 0 else f'D+{-n}'

def show_notice():
    if ss.notice:
        (st.warning if ss.notice.startswith('⚠️') else st.success)(ss.notice)
        ss.notice = ''

def contacts_text():
    return '\n'.join((f"- {c['이름']} ({c.get('직책', '')}) <{c['이메일']}>" for c in ss.contacts)) or '- 없음'

def base_system():
    s = ss.settings
    today_sch = '\n'.join((f"- {e['시간']} {e['일정']}" for e in sorted(ss.schedule, key=lambda x: x['시간']) if e['일자'] == TODAY)) or '- 없음'
    my_open = '\n'.join((f"- {t['업무']} (마감 {_due_read(t)}, {t['상태']}, 우선순위 {t['우선순위']})" for t in ss.tasks if t['담당자'] == s['name'] and t['상태'] != '완료')) or '- 없음'
    prompt = sys_role + f"\n사용자: {s['name']} ({s['team']}, {s['role']})\n오늘 날짜: {TODAY}\n\n[오늘 일정]\n{today_sch}\n\n[사용자의 미완료 업무]\n{my_open}\n\n[팀 연락처]\n{contacts_text()}"
    if s['common_prompt']:
        prompt += f"\n\n[공통 지침]\n{s['common_prompt']}"
    return prompt

def parse_json(textval):
    m = re.search('\\{.*\\}', textval, re.S)
    return json.loads(m.group() if m else textval)

def llm(messages, json_mode=False):
    kwargs = {'model': model_id(), 'input': messages}
    if json_mode and model_id() not in LEGACY_MODELS:
        kwargs['text'] = {'format': {'type': 'json_object'}}
    return client.responses.create(**kwargs).output_text

def stream_llm(messages):
    stream = client.responses.create(model=model_id(), input=messages, stream=True)
    for event in stream:
        if event.type == 'response.output_text.delta':
            yield event.delta

def speak(text_, force=False):
    s = ss.settings
    if not text_ or (not s['tts_on'] and (not force)):
        return
    try:
        sp = client.audio.speech.create(model=TTS_MODEL, voice=s['voice'], input=text_[:4000])
        st.audio(sp.content, format='audio/mp3', autoplay=s['autoplay'] or force)
    except Exception as e:
        st.caption(f'🔇 음성 변환 실패: {e}')

def stt(audio_bytes):
    r = client.audio.transcriptions.create(model='whisper-1', file=('audio.wav', audio_bytes, 'audio/wav'), language=ss.settings['stt_lang'])
    return r.text

def find_contact(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    for c in ss.contacts:
        if raw.lower() == c['이메일'].lower() or raw == c['이름']:
            return c
    key = raw.replace(' ', '').replace('님', '').replace('에게', '').replace('한테', '')
    for c in ss.contacts:
        name = c['이름'].replace(' ', '')
        if key and name and (name in key or key in name):
            return c
    return None

def upsert_contact(name, email, title=''):
    for c in ss.contacts:
        if c['이메일'].lower() == email.lower():
            c['이름'] = name or c['이름']
            if title:
                c['직책'] = title
            return
    ss.contacts.append({'이름': name or email.split('@')[0], '이메일': email, '직책': title})

def read_key_file(path=KEY_FILE):
    user = pw = ''
    try:
        with open(path, encoding='utf-8') as fp:
            lines = fp.read().splitlines()
    except Exception:
        return (user, pw)
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        k, v = ('', line)
        if not EMAIL_RE.fullmatch(line):
            for sep in ('=', ':'):
                if sep in line:
                    k, v = line.split(sep, 1)
                    break
        k, v = (k.strip().lower(), v.strip().strip('"').strip("'"))
        if 'openai' in k or v.startswith('sk-'):
            continue
        if not user and EMAIL_RE.fullmatch(v):
            user = v
        elif not pw and (any((w in k for w in ('pass', 'pw', '비밀번호', 'app'))) or not k):
            pw = v.replace(' ', '')
    return (user, pw)

def smtp_conf():
    file_user, file_pw = read_key_file()
    user = ss.smtp.get('user') or os.environ.get('SMTP_USER', '') or file_user
    pw = ss.smtp.get('password') or os.environ.get('SMTP_PASSWORD', '') or file_pw
    host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    port = int(os.environ.get('SMTP_PORT', '465'))
    return (user, pw, host, port)

def deliver(to_addr, subject, body, name=None):
    user, pw, host, port = smtp_conf()
    mode = '모의 발송'
    if user and pw:
        msg = EmailMessage()
        msg['From'], msg['To'], msg['Subject'] = (user, to_addr, subject)
        msg.set_content(body)
        with smtplib.SMTP_SSL(host, port, timeout=20) as server:
            server.login(user, pw)
            server.send_message(msg)
        mode = '실제 발송'
    rec = {'받는 사람': f'{name} <{to_addr}>' if name else to_addr, '제목': subject, '본문': body, '발송 시각': datetime.now().strftime('%Y-%m-%d %H:%M'), '방식': mode}
    ss.sent.append(rec)
    if not any((c['이메일'].lower() == to_addr.lower() for c in ss.contacts)):
        upsert_contact(name, to_addr)
    return rec

def extract_text(name, data):
    ext = name.rsplit('.', 1)[-1].lower()
    try:
        if ext in ('txt', 'md', 'csv', 'json'):
            return data.decode('utf-8', errors='ignore')
        if ext == 'pdf':
            from pypdf import PdfReader
            return '\n'.join((p.extract_text() or '' for p in PdfReader(io.BytesIO(data)).pages))
        if ext == 'docx':
            import docx
            return '\n'.join((p.text for p in docx.Document(io.BytesIO(data)).paragraphs))
    except Exception:
        pass
    return ''

def add_to_library(name, data, source):
    for f in ss.library:
        if f['name'] == name and f['size'] == len(data):
            return f
    text_ = extract_text(name, data)
    rec = {'id': uuid.uuid4().hex[:8], 'name': name, 'data': data, 'text': text_, 'source': source, 'size': len(data), 'created': datetime.now().strftime('%Y-%m-%d %H:%M'), 'rag': bool(text_)}
    ss.library.append(rec)
    return rec

def rag_context(query):
    words = [w for w in query.split() if len(w) >= 2]
    chunks = []
    for f in ss.library:
        if not (f['rag'] and f['text']):
            continue
        for i in range(0, len(f['text']), 500):
            c = f['text'][i:i + 500]
            score = sum((c.count(w) for w in words))
            if score:
                chunks.append((score, f['name'], c))
    chunks.sort(reverse=True)
    top = chunks[:3]
    return ('\n\n'.join((f'[출처: {n}]\n{c}' for _, n, c in top)), [n for _, n, _ in top])

def file_parts(f, vision=True):
    ext = f['name'].rsplit('.', 1)[-1].lower()
    b64 = base64.b64encode(f['data']).decode()
    if vision and ext in IMG_MIME:
        return [{'type': 'input_image', 'image_url': f'data:{IMG_MIME[ext]};base64,{b64}'}]
    if vision and ext == 'pdf':
        return [{'type': 'input_file', 'filename': f['name'], 'file_data': f'data:application/pdf;base64,{b64}'}]
    if f['text']:
        return [{'type': 'input_text', 'text': f"[첨부: {f['name']}]\n{f['text'][:15000]}"}]
    return [{'type': 'input_text', 'text': f"[첨부: {f['name']}] (현재 모델은 이 파일을 직접 읽을 수 없음)"}]
ROUTER_PROMPT = '너는 업무 비서의 라우터다. 사용자 요청을 분석해 JSON으로만 답하라.\nintent는 chat | email | calendar | task | translate 중 하나.\n- email: 이메일 작성/발송 요청. args: {"to": 받는 사람 이름 또는 이메일 주소(연락처 이름 그대로), "subject": 제목, "body": 정중한 업무 메일 본문(끝에 \'{sender}\' 서명)}\n- calendar: 일정 추가/조율. args: {"date": "YYYY-MM-DD", "time": "HH:MM", "title": 일정명}\n- task: 업무 등록. args: {"title": 업무명, "owner": 담당자, "due": "YYYY-MM-DD", "priority": "높음|보통|낮음"}\n- translate: 번역 요청. args: {"target_lang": 언어}\n- chat: 그 외 대화·요약·분석. args: {}\n오늘 날짜: {today}\n등록된 연락처:\n{contacts}\n형식: {"intent": "...", "args": {...}}'

def route(prompt):
    s = ss.settings
    sysmsg = ROUTER_PROMPT.replace('{today}', str(TODAY)).replace('{contacts}', contacts_text()).replace('{sender}', f"{s['team']} {s['name']}")
    try:
        r = parse_json(llm([{'role': 'system', 'content': sysmsg}, {'role': 'user', 'content': prompt}], json_mode=True))
        if r.get('intent') in INTENT_LABEL:
            r.setdefault('args', {})
            return r
    except Exception:
        pass
    rules = {'email': ['메일'], 'calendar': ['일정 추가', '일정 잡', '캘린더'], 'task': ['업무 등록', '할 일 추가'], 'translate': ['번역']}
    for intent, words in rules.items():
        if any((w in prompt for w in words)):
            return {'intent': intent, 'args': {}}
    return {'intent': 'chat', 'args': {}}

def tool_email(a):
    raw = str(a.get('to') or '')
    c = find_contact(raw)
    m = EMAIL_RE.search(raw)
    if c:
        addr, name = (c['이메일'], c['이름'])
    elif m:
        addr, name = (m.group(), None)
    else:
        return (f"'{raw or '받는 사람'}'의 이메일 주소를 연락처에서 찾지 못해 보내지 않았다. 사용자에게 이메일 주소를 알려 달라고 하거나 '이메일 관리 > 연락처'에 등록하라고 안내하라.", None)
    draft = {'to': addr, 'name': name, 'subject': a.get('subject') or '(제목 없음)', 'body': a.get('body') or ''}
    ss['_draft'] = draft
    who = f'{name or addr} <{addr}>'
    if ss.settings.get('auto_send', True) and (not a.get('_draft_only')):
        try:
            rec = deliver(addr, draft['subject'], draft['body'], name)
            draft['sent'] = f"{rec['방식']} 완료 · {rec['발송 시각']}"
            return (f"이메일 {rec['방식']} 완료 → 받는 사람: {who}, 제목: {draft['subject']}. 보냈다고 짧게 보고하라. 본문은 다시 쓰지 마라.", None)
        except Exception as e:
            draft['error'] = str(e)
            return (f"이메일 발송 실패 → {who}: {e}. 아래 '📤 이 메일 보내기' 버튼으로 다시 시도하거나 설정의 Gmail 정보를 확인하라고 안내하라.", None)
    return (f"이메일 초안 작성 완료 → 받는 사람: {who}, 제목: {draft['subject']}. 아직 발송 전이며, 사용자가 '보내줘'라고 답하거나 아래 '📤 이 메일 보내기' 버튼을 누르면 발송된다. 본문을 다시 쓰지 말고 짧게 안내하라.", None)

def tool_calendar(a):
    d = to_date(a.get('date'))
    t = a.get('time') or '10:00'
    try:
        datetime.strptime(t, '%H:%M')
    except Exception:
        t = '10:00'
    busy = {e['시간'] for e in ss.schedule if e['일자'] == d}
    note = ''
    while t in busy:
        h, m = map(int, t.split(':'))
        t, note = (f'{(h + 1) % 24:02d}:{m:02d}', ' (기존 일정과 겹쳐 시간을 자동 조정함)')
    ss.schedule.append({'일자': d, '시간': t, '일정': a.get('title') or '새 일정'})
    day = sorted([e for e in ss.schedule if e['일자'] == d], key=lambda x: x['시간'])
    return (f"{d} {t} '{a.get('title') or '새 일정'}' 일정 등록 완료{note}", day)

def tool_task(a):
    t = {'id': uuid.uuid4().hex[:8], '업무': a.get('title') or '새 업무', '담당자': a.get('owner') or ss.settings['name'], '마감일': to_date(a.get('due')), '상태': '대기', '우선순위': a.get('priority') if a.get('priority') in ('높음', '보통', '낮음') else '보통'}
    ss.tasks.append(t)
    rows = [{k: v for k, v in x.items() if k != 'id'} for x in ss.tasks if x['담당자'] == t['담당자']]
    return (f"업무 등록 완료: {t['업무']} (담당 {t['담당자']}, 마감 {_due_read(t)})", rows)
TOOLS = {'email': ('📧 이메일 도구', tool_email), 'calendar': ('📅 캘린더 도구', tool_calendar), 'task': ('✅ 업무 관리 도구', tool_task)}

def make_suggestions(q, a):
    try:
        out = llm([{'role': 'system', 'content': '대화 흐름에 이어서 사용자가 물어볼 만한 짧은 후속 질문 3개를 JSON으로만 만들어라. 형식: {"questions": ["...", "...", "..."]}'}, {'role': 'user', 'content': f'질문: {q}\n답변: {a[:2000]}'}], json_mode=True)
        return parse_json(out).get('questions', [])[:3]
    except Exception:
        return []

def go(page, prompt=None, open_tools=False):
    ss.menu = page
    ss.open_tools = open_tools
    if prompt:
        ss.pending_prompt = prompt

def set_prompt(q):
    ss.pending_prompt = q

def new_chat():
    ss.messages = []
    ss.suggestions = []
    ss.attach_ids = []
    ss.chat_key += 1
    ss.menu = '💬 채팅'

def toggle_task(tid):
    for t in ss.tasks:
        if t['id'] == tid:
            t['상태'] = '완료' if ss[f'chk_{tid}'] else '진행 중'

def change_model():
    ss.settings['model'] = ss.sb_model

def send_draft(i):
    d = ss.messages[i]['draft']
    try:
        rec = deliver(d['to'], d['subject'], d['body'], d['name'])
        d['sent'] = f"{rec['방식']} 완료 · {rec['발송 시각']}"
        d.pop('error', None)
    except Exception as e:
        d['error'] = str(e)

def edit_draft(i):
    d = ss.messages[i]['draft']
    ss.mail_to, ss.mail_subject, ss.mail_body = (d['to'], d['subject'], d['body'])
    ss.menu = '📧 이메일 관리'
    ss.notice = "✏️ 초안을 '메일 작성' 탭에 옮겼습니다. 수정한 뒤 보내세요."

def render_draft(i, d):
    with st.container(border=True):
        st.markdown(f"**📧 받는 사람:** {d['name'] or ''} <{d['to']}>  \n**제목:** {d['subject']}")
        st.text(d['body'])
        if d.get('sent'):
            st.success(f"✅ {d['sent']}")
            return
        if d.get('error'):
            st.error(f"⚠️ 발송 실패: {d['error']}")
        c1, c2 = st.columns(2)
        c1.button('📤 이 메일 보내기', key=f'send_{i}', on_click=send_draft, args=(i,), type='primary')
        c2.button('✏️ 수정해서 보내기', key=f'edit_{i}', on_click=edit_draft, args=(i,))

def render_extras(i, m):
    if m.get('draft'):
        render_draft(i, m['draft'])
    if m.get('table'):
        st.dataframe(pd.DataFrame(m['table']), hide_index=True)
    if m.get('model'):
        st.caption(f"🧠 {m['model']}")
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.download_button('⬇️ 다운로드', m['content'], file_name=f'able_answer_{i}.md', key=f'dl_{i}')
    with c2:
        if st.button('💾 자료실 저장', key=f'save_{i}'):
            add_to_library(f'AI답변_{datetime.now():%m%d_%H%M%S}.md', m['content'].encode('utf-8'), '생성')
            st.toast('자료실에 저장했습니다.')
    with c3:
        st.feedback('thumbs', key=f'fb_{i}')
    with st.expander('📋 복사하기'):
        st.code(m['content'], language='markdown')

def handle_turn(prompt, files):
    if '_draft' in ss:
        del ss['_draft']
    with st.chat_message('user'):
        st.markdown(prompt)
        if files:
            st.caption('📎 ' + ', '.join((f['name'] for f in files)))
    history = [{'role': m['role'], 'content': m['content']} for m in ss.messages[-20:]]
    ss.messages.append({'role': 'user', 'content': prompt, 'files': [f['name'] for f in files]})
    with st.chat_message('assistant'):
        try:
            with st.status('에이블이 생각하는 중...', expanded=True) as status:
                st.write(f"🧠 사용 모델: {ss.settings['model']} ({model_id()})")
                st.write('🔍 1단계: 요청 의도 파악')
                sys_c, table = (base_system(), None)
                j = len(ss.messages) - 2
                last_draft = ss.messages[j].get('draft') if j >= 0 and ss.messages[j]['role'] == 'assistant' else None
                if last_draft and (not last_draft.get('sent')) and (len(prompt) <= 25) and CONFIRM_RE.search(prompt.strip()) and ('초안' not in prompt):
                    intent = 'confirm'
                    st.write('➡️ 판독 결과: **📤 메일 발송 확인**')
                    send_draft(j)
                    result = f"이메일 {last_draft['sent']} → {last_draft['name'] or ''} <{last_draft['to']}>" if last_draft.get('sent') else f"이메일 발송 실패: {last_draft.get('error')}"
                    st.write(('✅ ' if last_draft.get('sent') else '⚠️ ') + result)
                    sys_c += f'\n\n[도구 실행 결과]\n{result}\n위 결과를 사용자에게 한두 문장으로 보고하라.'
                    r = {'args': {}}
                else:
                    recent = '\n'.join((f"{m['role']}: {m['content'][:200]}" for m in history[-4:]))
                    r = route(f'[최근 대화]\n{recent}\n\n[현재 요청]\n{prompt}')
                    intent = r['intent']
                    st.write(f'➡️ 판독 결과: **{INTENT_LABEL[intent]}**')
                args = r['args']
                if intent == 'email' and any((w in prompt for w in ('초안', '작성만', '보내지 마'))):
                    args['_draft_only'] = True
                if intent in TOOLS:
                    name, fn = TOOLS[intent]
                    st.write(f'🛠️ 2단계: {name} 실행')
                    result, table = fn(args)
                    st.write(f'✅ {result.splitlines()[0][:120]}')
                    sys_c += f'\n\n[도구 실행 결과]\n{result}\n위 결과를 사용자에게 간결하게 보고하라.'
                elif intent == 'translate':
                    sys_c += f"\n\n사용자가 번역을 요청했다. 대상 언어: {args.get('target_lang', '영어')}. 번역문을 먼저 제시하라."
                st.write('📚 3단계: 자료실(RAG) 검색')
                ctx, srcs = rag_context(prompt)
                if ctx:
                    sys_c += f'\n\n[자료실 참고 자료]\n{ctx}\n참고한 경우 출처 파일명을 밝혀라.'
                    st.write('참고 문서: ' + ', '.join(sorted(set(srcs))))
                else:
                    st.write('관련 자료 없음')
                if files:
                    st.write(f'📎 첨부 파일 {len(files)}개 분석')
                status.update(label='분석 완료! 답변을 작성합니다.', state='complete', expanded=False)
            vision = model_id() not in LEGACY_MODELS
            content = [{'type': 'input_text', 'text': prompt}]
            for f in files:
                content += file_parts(f, vision)
            msgs = [{'role': 'system', 'content': sys_c}] + history + [{'role': 'user', 'content': content}]
            answer_ = st.write_stream(stream_llm(msgs))
        except Exception as e:
            ss.messages.pop()
            st.error(f'⚠️ 답변 생성 중 문제가 발생했습니다. 잠시 후 다시 시도하거나 다른 모델을 선택해 주세요.\n\n`{e}`')
            st.button('🔄 다시 시도', on_click=set_prompt, args=(prompt,), key='retry')
            return
        msg = {'role': 'assistant', 'content': answer_ or '', 'table': table, 'model': ss.settings['model'], 'draft': ss.get('_draft')}
        ss.messages.append(msg)
        render_extras(len(ss.messages) - 1, msg)
        speak(answer_)
    ss.suggestions = make_suggestions(prompt, answer_ or '')
    ss.attach_ids = []
    ss.chat_key += 1

def page_home():
    s = ss.settings
    st.header(f"🏠 {s['name']}님, 좋은 하루입니다!")
    st.caption(TODAY.strftime('%Y년 %m월 %d일'))
    total = len(ss.tasks)
    done = sum((t['상태'] == '완료' for t in ss.tasks))
    doing = sum((t['상태'] == '진행 중' for t in ss.tasks))
    urgent = [t for t in ss.tasks if t['상태'] != '완료' and _due_read(t) <= TODAY + timedelta(days=2)]
    c = st.columns(4)
    c[0].metric('📋 전체 업무', total)
    c[1].metric('✅ 완료 업무', done)
    c[2].metric('🔄 진행 중', doing)
    c[3].metric('⏰ 마감 임박', len(urgent))
    st.progress(done / total if total else 0, text=f'완료율 {done / total * 100:.0f}%' if total else '업무 없음')
    left, right = st.columns(2)
    with left:
        st.subheader('📅 오늘의 일정')
        now = datetime.now().strftime('%H:%M')
        today = sorted([e for e in ss.schedule if e['일자'] == TODAY], key=lambda x: x['시간'])
        for e in today:
            mark = '✔️' if e['시간'] < now else '🕒'
            st.markdown(f"{mark} **{e['시간']}** {e['일정']}")
        if not today:
            st.caption('오늘 일정이 없습니다.')
    with right:
        st.subheader('⏰ 마감 임박 업무')
        order = {'높음': 0, '보통': 1, '낮음': 2}
        for t in sorted(urgent, key=lambda x: (_due_read(x), order[x['우선순위']])):
            st.markdown(f"**[{dday(_due_read(t))}]** {t['업무']} · {t['담당자']} · 우선순위 {t['우선순위']}")
        if not urgent:
            st.caption('마감 임박 업무가 없습니다.')
    if ss.tasks:
        st.subheader('📊 상태별 업무')
        st.bar_chart(pd.DataFrame(ss.tasks)['상태'].value_counts())
    st.subheader('🤖 AI 업무 브리핑')
    if st.button('오늘의 브리핑 받기'):
        with st.spinner('오늘의 우선순위를 분석하고 있습니다...'):
            try:
                ss.briefing = llm([{'role': 'system', 'content': base_system()}, {'role': 'user', 'content': '오늘 일정과 내 미완료 업무를 보고 마감일·우선순위를 고려해 가장 효율적인 업무 순서를 번호 목록으로 제안하고, 업무마다 한 줄 가이드를 붙여줘.'}])
            except Exception as e:
                ss.briefing = f'⚠️ 브리핑 생성 중 오류가 발생했습니다. 다시 시도해 주세요. ({e})'
    if ss.briefing:
        st.info(ss.briefing)
    st.subheader('⚡ 빠른 실행')
    q = st.columns(4)
    q[0].button('🎤 음성 비서', on_click=go, args=('💬 채팅', None, True))
    q[1].button('📝 회의록 요약', on_click=go, args=('💬 채팅', None, True))
    q[2].button('📧 이메일 작성', on_click=go, args=('📧 이메일 관리',))
    q[3].button('📅 일정 정리', on_click=go, args=('💬 채팅', '오늘 일정과 마감 임박 업무를 시간순으로 정리해줘'))

def page_chat():
    st.header('💬 채팅')
    for i, m in enumerate(ss.messages):
        with st.chat_message(m['role']):
            st.markdown(m['content'])
            if m['role'] == 'assistant':
                render_extras(i, m)
            elif m.get('files'):
                st.caption('📎 ' + ', '.join(m['files']))
    chat_area = st.container()
    with st.expander('📎 파일 첨부 · 🎤 음성 입력', expanded=ss.open_tools):
        ups = st.file_uploader('PDF, 이미지, 문서 파일을 끌어다 놓으세요', type=CHAT_TYPES, accept_multiple_files=True, key=f'chat_up_{ss.chat_key}')
        audio = st.audio_input('마이크로 말씀하세요', key=f'chat_audio_{ss.chat_key}')
    attached = [f for f in ss.library if f['id'] in ss.attach_ids]
    if attached:
        st.caption('📁 자료실에서 첨부됨: ' + ', '.join((f['name'] for f in attached)))
    st.caption('⚡ 자주 쓰는 질문')
    cols = st.columns(len(QUICK_PROMPTS))
    for col, qp in zip(cols, QUICK_PROMPTS):
        col.button(qp, key=f'qp_{qp}', on_click=set_prompt, args=(qp,))
    prompt = st.chat_input('에이블에게 무엇이든 요청하세요 (예: 최 팀장님께 회의 일정 변경 메일 보내줘)')
    if ss.pending_prompt:
        prompt, ss.pending_prompt = (ss.pending_prompt, None)
    if audio is not None:
        audio_bytes = audio.getvalue()
        h = hashlib.md5(audio_bytes).hexdigest()
        if h != ss.last_audio:
            ss.last_audio = h
            try:
                prompt = stt(audio_bytes)
            except Exception as e:
                st.error(f'음성 인식에 실패했습니다. 다시 녹음해 주세요. ({e})')
    if prompt:
        files = [add_to_library(u.name, u.getvalue(), '업로드') for u in ups or []]
        files += [f for f in attached if f not in files]
        ss.open_tools = False
        with chat_area:
            handle_turn(prompt, files)
    if ss.suggestions:
        st.caption('💡 이어서 물어보기')
        for j, sq in enumerate(ss.suggestions):
            st.button(sq, key=f'sg_{j}', on_click=set_prompt, args=(sq,))

def lib_upload():
    for u in ss.get(f'lib_up_{ss.lib_key}') or []:
        add_to_library(u.name, u.getvalue(), '업로드')
    ss.lib_key += 1

def lib_delete(fid):
    ss.library = [f for f in ss.library if f['id'] != fid]
    ss.attach_ids = [x for x in ss.attach_ids if x != fid]

def lib_rag(fid):
    for f in ss.library:
        if f['id'] == fid:
            f['rag'] = ss[f'rag_{fid}']

def lib_attach(fid):
    if fid not in ss.attach_ids:
        ss.attach_ids.append(fid)
    ss.menu = '💬 채팅'

def lib_import_folder():
    os.makedirs(LIB_DIR, exist_ok=True)
    n = 0
    for fn in sorted(os.listdir(LIB_DIR)):
        if fn.rsplit('.', 1)[-1].lower() in CHAT_TYPES:
            with open(os.path.join(LIB_DIR, fn), 'rb') as fp:
                add_to_library(fn, fp.read(), '폴더')
            n += 1
    ss.notice = f'📂 폴더에서 {n}개 파일을 불러왔습니다.' if n else f"⚠️ '{LIB_DIR}' 폴더에 파일이 없습니다."

def lib_add_text():
    body = ss.get('lib_text_body', '')
    if not body.strip():
        ss.notice = '⚠️ 내용을 입력해 주세요.'
        return
    name = ss.get('lib_text_name', '').strip() or f'메모_{datetime.now():%m%d_%H%M%S}'
    if not name.endswith('.txt'):
        name += '.txt'
    add_to_library(name, body.encode('utf-8'), '직접 입력')
    ss.lib_text_name = ''
    ss.lib_text_body = ''
    ss.notice = f"✍️ '{name}'을(를) 자료실에 추가했습니다."

def page_library():
    st.header('📁 자료실')
    show_notice()
    tab1, tab3 = st.tabs(['⬆️ 파일 업로드', '✍️ 텍스트 붙여넣기'])
    with tab1:
        st.file_uploader('자료 추가', type=CHAT_TYPES, accept_multiple_files=True, key=f'lib_up_{ss.lib_key}')
        st.button('➕ 자료실에 추가', on_click=lib_upload)
        st.caption("업로드 오류가 나면 '텍스트 붙여넣기'를 사용하세요.")
    with tab3:
        st.text_input('파일 이름', key='lib_text_name', placeholder='예: 11월_마케팅회의록')
        st.text_area('내용', key='lib_text_body', height=200, placeholder='회의록이나 참고 자료를 붙여 넣으세요.')
        st.button('✍️ 자료실에 저장', on_click=lib_add_text)
    query = st.text_input('🔍 파일명·내용 검색')
    files = [f for f in ss.library if not query or query in f['name'] or query in f['text']]
    st.caption(f"총 {len(files)}개 · RAG 사용 {sum((f['rag'] for f in files))}개")
    for f in files:
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([4, 1.3, 1.3, 1.5, 0.8])
            c1.markdown(f"**{f['name']}**  \n{f['source']} · {f['created']} · {f['size'] / 1024:.1f}KB")
            c2.checkbox('RAG', value=f['rag'], key=f"rag_{f['id']}", on_change=lib_rag, args=(f['id'],), disabled=not f['text'], help='텍스트를 읽을 수 있는 파일만 검색에 사용됩니다.')
            c3.download_button('⬇️', f['data'], file_name=f['name'], key=f"ldl_{f['id']}")
            c4.button('💬 대화에 활용', key=f"use_{f['id']}", on_click=lib_attach, args=(f['id'],))
            c5.button('🗑️', key=f"del_{f['id']}", on_click=lib_delete, args=(f['id'],))
    if not files:
        st.info('자료가 없습니다. 위의 세 가지 방법 중 하나로 자료를 추가해 보세요.')

def set_task_pct(tid, key):
    t = next((x for x in ss.tasks if x['id'] == tid), None)
    if t:
        new = int(ss[key])
        record_change(t, '진행률', t.get('진행률', 0), new)
        t['진행률'] = new
        if new == 100:
            record_change(t, '상태', t['상태'], '완료')
            t['상태'] = '완료'
            ss.pop(f'chk_{tid}', None)

def page_my_tasks():
    me = ss.settings['name']
    st.header('✅ 내 작업')
    view = st.radio('보기', ['전체', '미완료', '완료'], horizontal=True)
    mine = sorted([t for t in ss.tasks if t['담당자'] == me], key=lambda x: _due_read(x))
    if view == '미완료':
        mine = [t for t in mine if t['상태'] != '완료']
    elif view == '완료':
        mine = [t for t in mine if t['상태'] == '완료']
    for t in mine:
        c1, c2, c3, c4 = st.columns([5, 1.5, 1.5, 0.5])
        c1.checkbox(t['업무'], value=t['상태'] == '완료', key=f"chk_{t['id']}", on_change=toggle_task, args=(t['id'],))
        c2.markdown(f'`{dday(_due_read(t))}` {_due_read(t)}')
        c3.markdown(f"{t['상태']} · {t['우선순위']}")
        if t['상태'] == '진행 중':
            pct = int(t.get('진행률', 0))
            c3.slider('완료율', 0, 100, pct, step=5, format='%d%%', key=f"pct_{t['id']}_{pct}", on_change=set_task_pct, args=(t['id'], f"pct_{t['id']}_{pct}"))
        c4.button('🗑️', key=f"del_now_{t['id']}", on_click=delete_task_now, args=(t['id'],), help='바로 삭제', type='tertiary')
    if not mine:
        st.caption('해당하는 업무가 없습니다.')
    with st.form('add_task', clear_on_submit=True):
        st.subheader('➕ 업무 추가')
        c1, c2, c3 = st.columns([3, 1.5, 1.5])
        title = c1.text_input('업무명')
        due = c2.date_input('마감일', TODAY)
        pr = c3.selectbox('우선순위', ['높음', '보통', '낮음'], index=1)
        if st.form_submit_button('추가') and title:
            ss.tasks.append({'id': uuid.uuid4().hex[:8], '업무': title, '담당자': me, '마감일': due, '상태': '대기', '우선순위': pr})
            st.rerun()

def page_team():
    st.header('👥 팀 업무 현황')
    if not ss.tasks:
        st.info('등록된 업무가 없습니다.')
        return
    df = pd.DataFrame(ss.tasks).drop(columns='id')
    owners = sorted(df['담당자'].unique())
    c1, c2 = st.columns(2)
    sel = c1.multiselect('담당자', owners, default=owners)
    status_ = c2.selectbox('상태', ['전체', '대기', '진행 중', '완료'])
    view = df[df['담당자'].isin(sel)]
    if status_ != '전체':
        view = view[view['상태'] == status_]
    st.dataframe(view.sort_values('마감일'), hide_index=True)
    st.subheader('📊 담당자별 업무 상태')
    if not view.empty:
        st.bar_chart(pd.crosstab(view['담당자'], view['상태']))

def draft_reply(mid):
    m = next((x for x in ss.inbox if x['id'] == mid))
    try:
        body = llm([{'role': 'system', 'content': base_system() + '\n받은 이메일에 대한 정중한 답장 본문만 작성하라.'}, {'role': 'user', 'content': f"보낸 사람: {m['from']}\n제목: {m['subject']}\n\n{m['body']}"}])
    except Exception as e:
        body = f'(초안 생성 실패: {e})'
    ss.mail_to, ss.mail_subject, ss.mail_body = (m['addr'], 'RE: ' + m['subject'], body)
    ss.notice = "✍️ 답장 초안이 '메일 작성' 탭에 준비되었습니다."

def mail_to_task(mid):
    m = next((x for x in ss.inbox if x['id'] == mid))
    ss.tasks.append({'id': uuid.uuid4().hex[:8], '업무': f"[메일] {m['subject']}", '담당자': ss.settings['name'], '마감일': TODAY + timedelta(days=2), '상태': '대기', '우선순위': '보통'})
    ss.notice = "📌 '내 작업'에 업무로 등록했습니다."

def ai_compose():
    try:
        ss.mail_body = llm([{'role': 'system', 'content': base_system() + '\n주어진 제목과 메모로 정중한 업무 메일 본문을 작성하라.'}, {'role': 'user', 'content': f'받는 사람: {ss.mail_to}\n제목: {ss.mail_subject}\n메모: {ss.mail_body}'}])
    except Exception as e:
        ss.notice = f'⚠️ AI 작성 실패: {e}'

def pick_contact():
    v = ss.mail_pick
    if v != '직접 입력':
        ss.mail_to = v.split('<')[-1].rstrip('>')

def send_mail():
    raw = ss.mail_to.strip()
    c = find_contact(raw)
    if c:
        addr, name = (c['이메일'], c['이름'])
    elif EMAIL_RE.fullmatch(raw):
        addr, name = (raw, None)
    else:
        ss.notice = '⚠️ 받는 사람을 연락처 이름이나 올바른 이메일 주소로 입력해 주세요.'
        return
    if not ss.mail_subject.strip():
        ss.notice = '⚠️ 제목을 입력해 주세요.'
        return
    try:
        rec = deliver(addr, ss.mail_subject, ss.mail_body, name)
    except Exception as e:
        ss.notice = f'⚠️ 발송 실패: {e}'
        return
    ss.mail_to = ss.mail_subject = ss.mail_body = ''
    ss.notice = f"📤 {name or addr} <{addr}>에게 메일을 보냈습니다. ({rec['방식']})"

def add_contact():
    name, email = (ss.ct_name.strip(), ss.ct_email.strip())
    if not name or not EMAIL_RE.fullmatch(email):
        ss.notice = '⚠️ 이름과 올바른 이메일 주소를 입력해 주세요.'
        return
    upsert_contact(name, email, ss.ct_title.strip())
    ss.ct_name = ss.ct_email = ss.ct_title = ''
    ss.notice = f"📇 '{name}' 연락처를 저장했습니다."

def delete_contact():
    addr = ss.del_pick.split('<')[-1].rstrip('>')
    ss.contacts = [c for c in ss.contacts if c['이메일'] != addr]
    ss.notice = '🗑️ 연락처를 삭제했습니다.'

def page_email():
    st.header('📧 이메일 관리')
    show_notice()
    user, pw, _, _ = smtp_conf()
    st.caption('📮 발송 방식: ' + (f'실제 발송 ({user})' if user and pw else '모의 발송 (설정 > 메일 발송에서 Gmail 연결 가능)'))
    tab1, tab2, tab3, tab4 = st.tabs([f'📥 받은편지함 ({len(ss.inbox)})', '✍️ 메일 작성', f'📤 보낸편지함 ({len(ss.sent)})', f'📇 연락처 ({len(ss.contacts)})'])
    with tab1:
        for m in ss.inbox:
            with st.expander(f"**{m['subject']}** — {m['from']} · {m['date']}"):
                st.write(m['body'])
                c1, c2 = st.columns(2)
                c1.button('🤖 AI 답장 초안', key=f"rep_{m['id']}", on_click=draft_reply, args=(m['id'],))
                c2.button('📌 업무로 등록', key=f"tsk_{m['id']}", on_click=mail_to_task, args=(m['id'],))
    with tab2:
        picks = ['직접 입력'] + [f"{c['이름']} <{c['이메일']}>" for c in ss.contacts]
        st.selectbox('📇 연락처에서 선택', picks, key='mail_pick', on_change=pick_contact)
        st.text_input('받는 사람 (이메일 주소 또는 연락처 이름)', key='mail_to')
        st.text_input('제목', key='mail_subject')
        st.text_area('본문 (메모만 적고 AI 작성 도움을 눌러도 됩니다)', key='mail_body', height=250)
        c1, c2 = st.columns(2)
        c1.button('🤖 AI 작성 도움', on_click=ai_compose)
        c2.button('📤 보내기', on_click=send_mail, type='primary')
    with tab3:
        if ss.sent:
            st.dataframe(pd.DataFrame(ss.sent[::-1]), hide_index=True)
        else:
            st.caption('보낸 메일이 없습니다.')
    with tab4:
        if ss.contacts:
            st.dataframe(pd.DataFrame(ss.contacts), hide_index=True)
        st.markdown('**➕ 연락처 추가 / 수정** (같은 이메일이면 정보가 수정됩니다)')
        c1, c2, c3 = st.columns(3)
        c1.text_input('이름', key='ct_name', placeholder='예: 한 대리')
        c2.text_input('이메일', key='ct_email', placeholder='예: han@company.com')
        c3.text_input('직책', key='ct_title', placeholder='예: 대리')
        st.button('📇 연락처 저장', on_click=add_contact)
        if ss.contacts:
            c4, c5 = st.columns([3, 1])
            c4.selectbox('삭제할 연락처', [f"{c['이름']} <{c['이메일']}>" for c in ss.contacts], key='del_pick')
            c5.button('🗑️ 삭제', on_click=delete_contact)

def page_settings():
    s = ss.settings
    st.header('⚙️ 설정')
    show_notice()
    models = list(MODEL_MAP)
    with st.form('settings_form'):
        st.subheader('👤 사용자 정보')
        c1, c2, c3 = st.columns(3)
        name = c1.text_input('이름', s['name'])
        team = c2.text_input('소속', s['team'])
        role = c3.text_input('직무', s['role'])
        st.subheader('🧠 AI 모델')
        model = st.selectbox('모델', models, index=models.index(s['model']), format_func=lambda k: f'{k}  ({MODEL_MAP[k]})')
        st.caption('선택한 모델은 저장되어 다음에 접속해도 그대로 사용됩니다. GPT-4는 이미지·PDF를 직접 읽지 못하고 긴 대화에서 오류가 날 수 있습니다.')
        common = st.text_area('공통 프롬프트 (모든 답변에 적용)', s['common_prompt'], placeholder='예: 답변은 항상 3줄 요약으로 시작해 주세요.')
        st.subheader('🔊 음성 설정')
        c4, c5, c6, c7 = st.columns(4)
        voice = c4.selectbox('TTS 목소리', VOICES, index=VOICES.index(s['voice']))
        tts_on = c5.toggle('답변 음성 재생', s['tts_on'])
        autoplay = c6.toggle('자동 재생', s['autoplay'])
        langs = {'한국어': 'ko'}
        lang = '한국어'
        c7.markdown('**음성 입력 언어**  \n한국어')
        st.subheader('📮 메일 발송 (Gmail)')
        file_user, file_pw = read_key_file()
        if file_user and file_pw:
            st.caption(f'✅ {KEY_FILE}에서 Gmail 정보를 읽었습니다: {file_user} (아래 칸은 비워 둬도 됩니다)')
        else:
            st.caption(f'{KEY_FILE}에 Gmail 정보가 없으면 아래에 입력하세요. 모두 비어 있으면 모의 발송합니다. 입력한 비밀번호는 저장 파일에 남지 않습니다.')
        c8, c9 = st.columns(2)
        smtp_user = c8.text_input('보내는 Gmail 주소', ss.smtp.get('user', ''))
        smtp_pw = c9.text_input('Gmail 앱 비밀번호 (16자리)', ss.smtp.get('password', ''), type='password')
        auto_send = st.toggle('채팅에서 메일을 요청하면 바로 발송', s.get('auto_send', True), help="끄면 채팅에서는 초안만 만들고, '보내줘'라고 답하거나 버튼을 눌러야 발송합니다.")
        if st.form_submit_button('💾 저장'):
            s.update({'name': name, 'team': team, 'role': role, 'model': model, 'common_prompt': common, 'voice': voice, 'tts_on': tts_on, 'autoplay': autoplay, 'stt_lang': langs[lang], 'auto_send': auto_send})
            ss.smtp = {'user': smtp_user.strip(), 'password': smtp_pw.replace(' ', '')}
            ss.notice = '설정이 저장되었습니다.'
            save_data()
            st.rerun()
    if st.button('🔊 목소리 미리 듣기'):
        speak(f"안녕하세요, {s['name']}님. 에이블입니다. 오늘도 함께 하겠습니다.", force=True)
import sqlite3
import imaplib
import email as email_lib
from email.header import decode_header, make_header
from email.utils import parseaddr
import calendar as calendar_lib
import html as html_lib
import zipfile
import hmac
st.markdown('<style>\n:root{--bg:#F2F7F7;--ink:#0F292A;--muted:#527072;--line:#E2ECEC;--accent:#0E7490}\n.stApp{background:var(--bg);color:var(--ink)}\n[data-testid="stSidebar"]{background:#EDF4F3;border-right:1px solid var(--line)}\n[data-testid="stChatMessage"]{background:#FFFFFF;border:1px solid var(--line);border-radius:14px;padding:1rem}\n[data-testid="stChatInput"]{border:1px solid #CBDDDD;border-radius:18px;background:white}\n.stButton>button,.stDownloadButton>button{border-radius:8px}\n.stButton>button[kind="primary"]{background:var(--accent);border-color:var(--accent)}\n.able-cal{width:100%;border-collapse:collapse;background:#FFFFFF;table-layout:fixed}\n.able-cal th{padding:.5rem;color:#527072;font-weight:500}\n.able-cal td{vertical-align:top;height:80px;padding:.4rem;border:1px solid #E2ECEC}\n.able-cal small{display:block;font-size:.72rem;color:#0E7490;overflow-wrap:anywhere}\n.able-cal .today{background:#DDF0ED}\n</style>', unsafe_allow_html=True)

def get_secret(key, default=''):
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    if os.environ.get(key):
        return os.environ[key]
    try:
        with open(KEY_FILE, encoding='utf-8') as fp:
            for line in fp:
                if '=' in line and line.split('=', 1)[0].strip() == key:
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return default
ACCESS_PW = get_secret('ABLE_ACCESS_PASSWORD')
if ACCESS_PW and (not ss.get('authenticated')):
    st.subheader('🔒 에이블 작업공간')
    st.caption('대화·업무·메일을 보호하기 위해 비밀번호를 입력해 주세요.')
    with st.form('able_login'):
        _pw_in = st.text_input('작업공간 비밀번호', type='password')
        if st.form_submit_button('들어가기'):
            if hmac.compare_digest(_pw_in, ACCESS_PW):
                ss.authenticated = True
                st.rerun()
            else:
                st.error('비밀번호를 확인하세요.')
    st.stop()
DB_FILE = get_secret('ABLE_DB', 'able_final_demo.sqlite3')
WS_KEYS = ['tasks', 'schedule', 'messages', 'conversations', 'conv_id', 'library', 'candidates', 'changes', 'mail_drafts', 'contacts', 'sent']
DB_URL = get_secret('DATABASE_URL') or get_secret('SUPABASE_DB_URL')
DB_KIND = 'Supabase(PostgreSQL)' if DB_URL else 'SQLite 파일'

def _enc(o):
    if isinstance(o, UnknownDue):
        return {'__unknown_due__': True}
    if isinstance(o, (bytes, bytearray)):
        return {'__b64__': base64.b64encode(bytes(o)).decode()}
    if isinstance(o, datetime):
        return {'__dt__': o.isoformat()}
    if isinstance(o, date):
        return {'__date__': o.isoformat()}
    return str(o)

def _dec(d):
    if '__unknown_due__' in d:
        return None
    if '__b64__' in d:
        return base64.b64decode(d['__b64__'])
    if '__date__' in d:
        return date.fromisoformat(d['__date__'])
    if '__dt__' in d:
        return datetime.fromisoformat(d['__dt__'])
    return d

@st.cache_resource(show_spinner=False)
def _pg_connect(url):
    import psycopg
    con = psycopg.connect(url, autocommit=True, prepare_threshold=None, connect_timeout=15)
    con.execute('CREATE TABLE IF NOT EXISTS able_final_demo_state (k TEXT PRIMARY KEY, v TEXT NOT NULL, updated TEXT)')
    return con

class _PgDB:

    def __init__(self, con):
        self.con = con

    def execute(self, sql, args=()):
        return self.con.execute(sql.replace('?', '%s'), args)

    def commit(self):
        pass

    def close(self):
        pass

def ws_db():
    if DB_URL:
        con = _pg_connect(DB_URL)
        if con.closed or con.broken:
            _pg_connect.clear()
            con = _pg_connect(DB_URL)
        return _PgDB(con)
    con = sqlite3.connect(DB_FILE, timeout=15)
    con.execute('CREATE TABLE IF NOT EXISTS able_final_demo_state (k TEXT PRIMARY KEY, v TEXT NOT NULL, updated TEXT)')
    return con

def ws_load():
    try:
        con = ws_db()
        rows = con.execute('SELECT k, v FROM able_final_demo_state').fetchall()
        con.close()
        return {k: json.loads(v, object_hook=_dec) for k, v in rows}
    except Exception:
        return {}

def ws_save():
    try:
        last = ss.setdefault('_ws_last', {})
        con = ws_db()
        for k in WS_KEYS:
            if k not in ss:
                continue
            raw = json.dumps(ss[k], ensure_ascii=False, default=_enc)
            if last.get(k) == raw:
                continue
            con.execute('INSERT INTO able_final_demo_state(k, v, updated) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v, updated=excluded.updated', (k, raw, datetime.now().isoformat()))
            last[k] = raw
        con.commit()
        con.close()
    except Exception as e:
        st.sidebar.caption(f'⚠️ 작업공간 저장 실패: {e}')
for _k, _v in {'conversations': [], 'conv_id': uuid.uuid4().hex, 'candidates': [], 'changes': [], 'mail_drafts': [], 'last_error': None, 'analysis_mode': '검색'}.items():
    if _k not in ss:
        ss[_k] = _v
if 'ws_loaded' not in ss:
    _ws = ws_load()
    for _k in WS_KEYS:
        if _k in _ws:
            ss[_k] = _ws[_k]
    ss.ws_loaded = True
for _k, _v in {'custom_model': '', 'image_model': 'gpt-image-1', 'max_output': 4000, 'reasoning': '자동', 'voice_mode': '선택 재생'}.items():
    ss.settings.setdefault(_k, _v)
MODEL_MAP['✏️ 직접 입력'] = ''
if ss.settings.get('model') not in MODEL_MAP:
    ss.settings['model'] = 'Luna 6'
_base_model_id = model_id

def model_id():
    if ss.settings.get('model') == '✏️ 직접 입력' and ss.settings.get('custom_model'):
        return ss.settings['custom_model']
    return _base_model_id() or 'gpt-4o-mini'

def gen_options():
    opts = {'max_output_tokens': int(ss.settings.get('max_output', 4000))}
    if ss.settings.get('reasoning', '자동') != '자동':
        opts['reasoning'] = {'effort': ss.settings['reasoning']}
    return opts

def diagnostic(exc, stage='요청 처리'):
    body = getattr(exc, 'body', None)
    msg, code, param = (str(exc), None, None)
    if isinstance(body, dict):
        b = body.get('error') if isinstance(body.get('error'), dict) else body
        msg, code, param = (b.get('message', msg), b.get('code'), b.get('param'))
    msg = re.sub('sk-[A-Za-z0-9_\\-]+', '[키 숨김]', str(msg))
    hints = {'invalid_api_key': 'OpenAI API 키를 확인하세요.', 'model_not_found': '모델 이름과 이 계정의 모델 사용 권한을 확인하세요.', 'context_length_exceeded': "새 대화를 시작하거나 분석 범위를 '검색'으로 바꿔 주세요.", 'insufficient_quota': 'API 결제·사용 한도를 확인하세요.', 'unsupported_parameter': '선택한 모델이 이 옵션을 지원하지 않습니다. 다른 모델을 골라 다시 시도해 주세요.'}
    status = getattr(exc, 'status_code', None)
    hint = hints.get(code, '')
    if status == 400 and (not hint):
        hint = '아래 param·message가 실제 실패 원인을 알려 줍니다.'
    return {'stage': stage, 'type': type(exc).__name__, 'status': status, 'code': code, 'param': param, 'message': msg[:1800], 'hint': hint, 'request_id': getattr(exc, 'request_id', None)}

def error_ui(info):
    st.error(f"{info['stage']} · {info['type']}")
    if info.get('hint'):
        st.info(info['hint'])
    with st.expander('상세 원인 보기', expanded=True):
        st.write(info['message'])
        st.caption(' · '.join((f'{k}: {info[k]}' for k in ['status', 'code', 'param', 'request_id'] if info.get(k))))

def stream_llm(messages):
    try:
        stream = client.responses.create(model=model_id(), input=messages, stream=True, **gen_options())
        for event in stream:
            if event.type in ('response.output_text.delta', 'response.refusal.delta'):
                yield event.delta
            elif event.type in ('response.failed', 'response.incomplete'):
                raise ValueError('응답이 완료되지 않았습니다.')
    except Exception as e:
        ss.last_error = diagnostic(e, '답변 생성')
        raise
_base_speak = speak

def speak(text_, force=False):
    if ss.settings.get('voice_mode') == '선택 재생' and (not force):
        return
    _base_speak(text_, force)
AUDIO_EXT = ['mp3', 'wav', 'm4a', 'webm', 'ogg']
for _ext in ['pptx', 'xlsx', 'tsv', 'json', 'log'] + AUDIO_EXT:
    if _ext not in CHAT_TYPES:
        CHAT_TYPES.append(_ext)
_base_extract = extract_text

def extract_text(name, data):
    ext = name.rsplit('.', 1)[-1].lower()
    try:
        if ext == 'pptx':
            from pptx import Presentation
            lines = []
            for i, slide in enumerate(Presentation(io.BytesIO(data)).slides):
                lines.append(f'[슬라이드 {i + 1}]')
                for sh in slide.shapes:
                    if getattr(sh, 'has_text_frame', False):
                        lines.append(sh.text_frame.text)
                    if getattr(sh, 'has_table', False):
                        lines += [' | '.join((c.text for c in row.cells)) for row in sh.table.rows]
            return '\n'.join(lines)
        if ext in ('xlsx', 'csv', 'tsv'):
            if ext == 'xlsx':
                tables = pd.read_excel(io.BytesIO(data), sheet_name=None)
            else:
                tables = {'표': pd.read_csv(io.BytesIO(data), sep='\t' if ext == 'tsv' else ',')}
            out = ''
            for sheet, df in tables.items():
                out += f'\n[시트 {sheet}, {len(df)}행]\n' + df.to_csv(index=False)
                num = df.select_dtypes(include='number')
                if not num.empty:
                    out += '\n[기초 통계]\n' + num.describe().to_string()
            return out
        if ext == 'log':
            return data.decode('utf-8', errors='ignore')
        if ext in AUDIO_EXT:
            return client.audio.transcriptions.create(model='whisper-1', file=(name, data)).text
    except Exception:
        pass
    return _base_extract(name, data)
_base_rag = rag_context

def rag_context(query):
    if ss.get('analysis_mode') == '전체':
        docs = [f for f in ss.library if f['rag'] and f['text']]
        if docs:
            text_ = '\n\n'.join((f"[출처: {f['name']}]\n{f['text']}" for f in docs))
            return (text_[:45000], [f['name'] for f in docs])
    return _base_rag(query)

def archive_current():
    if not ss.messages:
        return
    title = next((m['content'][:26] for m in ss.messages if m['role'] == 'user'), '대화')
    for c in ss.conversations:
        if c['id'] == ss.conv_id:
            c.update(title=title, messages=ss.messages)
            return
    ss.conversations.append({'id': ss.conv_id, 'title': title, 'messages': ss.messages, 'created': datetime.now().strftime('%m-%d %H:%M')})
_base_new_chat = new_chat

def new_chat():
    archive_current()
    _base_new_chat()
    ss.conv_id = uuid.uuid4().hex

def open_conv(cid):
    archive_current()
    c = next((x for x in ss.conversations if x['id'] == cid))
    ss.messages, ss.conv_id = (c['messages'], cid)
    ss.suggestions = []
    ss.menu = '💬 채팅'

def delete_conv(cid):
    ss.conversations = [c for c in ss.conversations if c['id'] != cid]
    if ss.conv_id == cid:
        _base_new_chat()
        ss.conv_id = uuid.uuid4().hex
STATUS_LIST = ['대기', '진행 중', '완료']

def record_change(task, field, before, after):
    if before != after:
        ss.changes.append({'시각': datetime.now().strftime('%Y-%m-%d %H:%M'), '업무': task['업무'], '항목': field, '이전': str(before), '이후': str(after)})
_base_toggle = toggle_task

def toggle_task(tid):
    t = next((x for x in ss.tasks if x['id'] == tid), None)
    before = t['상태'] if t else None
    _base_toggle(tid)
    if t:
        record_change(t, '상태', before, t['상태'])

def board_set(tid, field, key):
    t = next((x for x in ss.tasks if x['id'] == tid), None)
    if t:
        before = t[field]
        t[field] = ss[key]
        record_change(t, field, before, t[field])

def board_delete(tid):
    t = next((x for x in ss.tasks if x['id'] == tid), None)
    if t:
        record_change(t, '삭제', t['업무'], '삭제됨')
        ss.tasks = [x for x in ss.tasks if x['id'] != tid]

def task_board(tasks, prefix):
    cols = st.columns(3)
    for col, group in zip(cols, [['대기'], ['진행 중'], ['완료']]):
        with col:
            st.markdown(f"**{' / '.join(group)}**")
            for t in [x for x in tasks if x['상태'] in group]:
                with st.container(border=True):
                    st.markdown(f"**{t['업무']}**")
                    st.caption(f"{t['담당자']} · {_due_read(t)} ({dday(_due_read(t))}) · {t['우선순위']}")
                    k, kd, kp = (f"{prefix}_st_{t['id']}", f"{prefix}_due_{t['id']}", f"{prefix}_pr_{t['id']}")
                    ss[k], ss[kd], ss[kp] = (t['상태'], _due_read(t), t['우선순위'])
                    st.selectbox('상태', status_options(t), key=k, on_change=board_set, args=(t['id'], '상태', k), label_visibility='collapsed')
                    if t['상태'] == '진행 중':
                        pct = int(t.get('진행률', 0))
                        kpct = f"{prefix}_pct_{t['id']}_{pct}"
                        st.slider('완료율', 0, 100, pct, step=5, format='%d%%', key=kpct, on_change=set_task_pct, args=(t['id'], kpct))
                    with st.expander('✏️ 수정'):
                        st.date_input('마감일', key=kd, on_change=board_set, args=(t['id'], '마감일', kd))
                        st.selectbox('우선순위', ['높음', '보통', '낮음'], key=kp, on_change=board_set, args=(t['id'], '우선순위', kp))
                        st.button('🗑️ 업무 삭제', key=f"{prefix}_del_{t['id']}", on_click=board_delete, args=(t['id'],))
                        st.button('💬 이 업무로 대화하기', key=f"{prefix}_chat_{t['id']}", on_click=go, args=('💬 채팅', f"'{t['업무']}' 업무(담당 {t['담당자']}, 마감 {_due_read(t)})를 어떻게 진행하면 좋을지 단계별로 알려줘"))

def extract_candidates(prompt, files):
    docs = list(files) + [f for f in ss.library if f['rag'] and f['text'] and (f not in files)]
    sources = {f['name']: f['text'] for f in docs if f.get('text')}
    if not sources:
        return 0
    context = '\n\n'.join((f'[파일 {n}]\n{t}' for n, t in sources.items()))[:30000]
    sysmsg = '자료에서 담당자에게 배정된 업무를 모두 찾아 JSON으로만 답하라. 없는 담당자·날짜를 만들지 마라. 기한이 불확실하면 due는 빈 문자열. quote는 근거가 되는 원문을 그대로 짧게 인용. 형식: {"tasks": [{"title": "", "owner": "", "due": "YYYY-MM-DD 또는 빈 문자열", "priority": "높음|보통|낮음", "source": "파일명", "quote": ""}]}'
    try:
        out = parse_json(llm([{'role': 'system', 'content': sysmsg + f'\n오늘 날짜: {TODAY}'}, {'role': 'user', 'content': f'요청: {prompt}\n\n{context}'}], json_mode=True))
    except Exception:
        return 0
    norm = lambda x: re.sub('\\s+', '', str(x))
    n = 0
    for t in out.get('tasks', [])[:30]:
        if not t.get('title'):
            continue
        raw = sources.get(t.get('source', ''), ' '.join(sources.values()))
        t.update(id=uuid.uuid4().hex[:8], verified=bool(t.get('quote') and norm(t['quote']) in norm(raw)))
        ss.candidates.append(t)
        n += 1
    return n

def accept_candidate(cid):
    c = next((x for x in ss.candidates if x['id'] == cid))
    has_due = bool(re.fullmatch('\\d{4}-\\d{2}-\\d{2}', str(c.get('due', ''))))
    t = {'id': uuid.uuid4().hex[:8], '업무': c['title'] + ('' if has_due else ' (기한 미정)'), '담당자': c.get('owner') or ss.settings['name'], '마감일': to_date(c['due']) if has_due else None, '상태': '대기', '우선순위': c.get('priority') if c.get('priority') in ('높음', '보통', '낮음') else '보통'}
    ss.tasks.append(t)
    record_change(t, '등록', '-', f"검토함에서 반영 (근거: {c.get('source', '')})")
    ss.candidates = [x for x in ss.candidates if x['id'] != cid]

def reject_candidate(cid):
    ss.candidates = [x for x in ss.candidates if x['id'] != cid]

def candidates_ui():
    if not ss.candidates:
        st.caption("검토할 업무가 없습니다. 채팅에서 회의록을 첨부하고 '담당자별 업무 정리해줘'라고 요청해 보세요.")
    for c in ss.candidates:
        with st.expander(f"{c['title']} · {c.get('owner') or '담당자 미정'}"):
            st.caption(f"기한: {c.get('due') or '미정'} · 우선순위: {c.get('priority', '보통')} · 근거 파일: {c.get('source', '')}")
            st.code(c.get('quote', ''), language=None)
            st.caption('✅ 원문과 일치하는 근거 확인됨' if c.get('verified') else '⚠️ 원문 일치 미확인 · 자료를 직접 확인해 주세요.')
            ok = st.checkbox('원문과 담당자·기한을 확인했습니다', key=f"cand_ok_{c['id']}")
            a, b = st.columns(2)
            a.button('✅ 업무에 반영', key=f"cand_acc_{c['id']}", on_click=accept_candidate, args=(c['id'],), disabled=not ok)
            b.button('❌ 제외', key=f"cand_rej_{c['id']}", on_click=reject_candidate, args=(c['id'],))

def changes_ui():
    if ss.changes:
        st.dataframe(pd.DataFrame(ss.changes[::-1][:50]), hide_index=True)
    else:
        st.caption('아직 변경 기록이 없습니다.')
_base_page_my_tasks = page_my_tasks

def page_my_tasks():
    for t in ss.tasks:
        if f"chk_{t['id']}" in ss and ss[f"chk_{t['id']}"] != (t['상태'] == '완료'):
            del ss[f"chk_{t['id']}"]
    _base_page_my_tasks()
    st.divider()
    mine = [t for t in ss.tasks if t['담당자'] == ss.settings['name']]
    t1, t3 = st.tabs(['📋 상태 보드', '🕘 변경 기록'])
    with t1:
        task_board(mine, 'my')
    with t3:
        changes_ui()
_base_page_team = page_team

def page_team():
    _base_page_team()
    if not ss.tasks:
        return
    st.divider()
    st.subheader('📋 담당자별 상태 보드')
    owner = st.selectbox('보드에 표시할 담당자', ['전체'] + sorted({t['담당자'] for t in ss.tasks}), key='team_board_owner')
    task_board([t for t in ss.tasks if owner == '전체' or t['담당자'] == owner], 'team')

def _minutes(hhmm):
    h, m = map(int, hhmm.split(':'))
    return h * 60 + m

def find_conflicts(day, start, dur, skip_idx=None):
    s, e = (_minutes(start), _minutes(start) + dur)
    out = []
    for i, ev in enumerate(ss.schedule):
        if i == skip_idx or ev['일자'] != day:
            continue
        es = _minutes(ev['시간'])
        if es < e and es + int(ev.get('소요', 60)) > s:
            out.append(ev['일정'])
    return out

def calendar_ui():
    st.subheader('🗓️ 월간 달력 (일정 + 업무 기한)')
    anchor = st.date_input('표시할 월', TODAY.replace(day=1), key='cal_month')
    cells = {}
    for t in ss.tasks:
        if t['상태'] not in ('완료', '취소'):
            cells.setdefault(_due_read(t), []).append('⏰ ' + t['업무'])
    for ev in ss.schedule:
        cells.setdefault(ev['일자'], []).append(f"{ev['시간']} {ev['일정']}")
    table = '<table class="able-cal"><thead><tr>' + ''.join((f'<th>{d}</th>' for d in '월화수목금토일')) + '</tr></thead><tbody>'
    for week in calendar_lib.Calendar().monthdatescalendar(anchor.year, anchor.month):
        table += '<tr>'
        for d in week:
            items = ''.join((f'<small>{html_lib.escape(x)}</small>' for x in cells.get(d, [])[:3]))
            more = f'<small>+{len(cells[d]) - 3}건</small>' if len(cells.get(d, [])) > 3 else ''
            table += f'''<td class="{('today' if d == TODAY else '')}"><b>{d.day}</b>{items}{more}</td>'''
        table += '</tr>'
    st.markdown(table + '</tbody></table>', unsafe_allow_html=True)

def save_event():
    title, day = (ss.ev_title.strip(), ss.ev_day)
    start, dur = (ss.ev_time.strftime('%H:%M'), int(ss.ev_dur))
    idx = None if ss.ev_pick == '새 일정' else int(ss.ev_pick.split(':')[0])
    if not title:
        ss.notice = '⚠️ 일정 제목을 입력하세요.'
        return
    clash = find_conflicts(day, start, dur, idx)
    if clash and (not ss.ev_allow):
        ss.notice = f"⚠️ 겹치는 일정: {', '.join(clash)}. 시간을 바꾸거나 '겹쳐도 저장'을 선택하세요."
        return
    ev = {'일자': day, '시간': start, '일정': title, '소요': dur}
    if idx is None:
        ss.schedule.append(ev)
    else:
        ss.schedule[idx] = ev
    ss.notice = f"📅 '{title}' 일정을 저장했습니다."

def delete_event():
    if ss.ev_pick != '새 일정':
        ev = ss.schedule.pop(int(ss.ev_pick.split(':')[0]))
        ss.notice = f"🗑️ '{ev['일정']}' 일정을 삭제했습니다."
        ss.ev_pick = '새 일정'

def load_event():
    if ss.ev_pick == '새 일정':
        ss.ev_title, ss.ev_day, ss.ev_dur = ('', TODAY, 60)
        return
    ev = ss.schedule[int(ss.ev_pick.split(':')[0])]
    ss.ev_title, ss.ev_day = (ev['일정'], ev['일자'])
    ss.ev_time = datetime.strptime(ev['시간'], '%H:%M').time()
    ss.ev_dur = int(ev.get('소요', 60))

def event_editor():
    st.subheader('✏️ 일정 편집')
    picks = ['새 일정'] + [f"{i}: {e['일자']} {e['시간']} {e['일정']}" for i, e in enumerate(ss.schedule)]
    if ss.get('ev_pick') not in picks:
        ss.ev_pick = '새 일정'
    st.selectbox('편집할 일정', picks, key='ev_pick', on_change=load_event)
    ss.setdefault('ev_title', '')
    ss.setdefault('ev_day', TODAY)
    ss.setdefault('ev_time', datetime.strptime('10:00', '%H:%M').time())
    ss.setdefault('ev_dur', 60)
    st.text_input('일정 제목', key='ev_title')
    a, b, c = st.columns(3)
    a.date_input('날짜', key='ev_day')
    b.time_input('시작', key='ev_time', step=1800)
    c.number_input('소요 시간(분)', min_value=15, max_value=720, step=15, key='ev_dur')
    st.checkbox('시간이 겹치는 일정이 있어도 저장', key='ev_allow')
    x, y = st.columns(2)
    x.button('💾 일정 저장', on_click=save_event, type='primary')
    y.button('🗑️ 선택한 일정 삭제', on_click=delete_event, disabled=ss.ev_pick == '새 일정')
_base_page_home = page_home

def page_home():
    _base_page_home()
    overdue = [t for t in ss.tasks if t['상태'] not in ('완료', '취소') and _due_read(t) < TODAY]
    st.divider()
    show_notice()
    if overdue:
        st.subheader(f'⚠️ 기한 초과 업무 {len(overdue)}건')
        for t in sorted(overdue, key=lambda x: _due_read(x)):
            st.markdown(f"**[{dday(_due_read(t))}]** {t['업무']} · {t['담당자']} · {t['상태']}")
    calendar_ui()
    event_editor()
FILE_FORMATS = ['txt', 'md', 'json', 'csv', 'xlsx', 'docx', 'pptx', 'pdf', 'png', 'mp3']
WANTS_FILE_RE = re.compile('(파일|엑셀|xlsx|csv|pdf|ppt|pptx|docx|워드|문서|보고서|이미지|그림|mp3|음성 ?파일|표).{0,15}(만들|생성|저장|뽑|그려|변환|작성|내보내)|(만들|생성|그려).{0,6}(파일|이미지|그림)', re.I)
PLAN_PROMPT = '사용자가 실제로 파일 생성을 원할 때만 files에 넣어 JSON으로만 답하라. 최대 3개.\nformat은 txt|md|json|csv|xlsx|docx|pptx|pdf|png|mp3 중 하나. content는 문자열.\n- txt/md/docx/pdf: 본문(제목 줄은 \'# \'로 시작)\n- json: 올바른 JSON 문자열\n- csv/xlsx: {"columns": ["열"], "rows": [["값"]]} 형태의 JSON 문자열\n- pptx: {"slides": [{"title": "제목", "bullets": ["요점"]}]} 형태의 JSON 문자열\n- png: 이미지 생성용 프롬프트 / mp3: 읽을 원고(4000자 이내)\n형식: {"files": [{"name": "파일이름", "format": "xlsx", "content": "..."}]}'

def _table_df(content):
    data = json.loads(content)
    df = pd.DataFrame(data['rows'], columns=data['columns'])
    return df.map(lambda v: "'" + v if isinstance(v, str) and v[:1] in '=+-@' else v)

def _pdf_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    for p in ['/usr/share/fonts/truetype/nanum/NanumGothic.ttf', 'C:/Windows/Fonts/malgun.ttf']:
        if os.path.isfile(p):
            if 'AbleKorean' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('AbleKorean', p))
            return 'AbleKorean'
    pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
    return 'HYSMyeongJo-Medium'

def make_file(item):
    fmt = item.get('format', 'txt')
    content = str(item.get('content', ''))
    stem = re.sub('[\\\\/:*?"<>|\\x00-\\x1f]', '_', str(item.get('name') or 'result')).rsplit('.', 1)[0][:60] or 'result'
    if fmt not in FILE_FORMATS or not content.strip():
        raise ValueError('만들 내용이 비어 있거나 지원하지 않는 형식입니다.')
    buf = io.BytesIO()
    if fmt in ('txt', 'md'):
        buf.write(content.encode('utf-8'))
    elif fmt == 'json':
        buf.write(json.dumps(json.loads(content), ensure_ascii=False, indent=2).encode('utf-8'))
    elif fmt == 'csv':
        buf.write(_table_df(content).to_csv(index=False).encode('utf-8-sig'))
    elif fmt == 'xlsx':
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            _table_df(content).to_excel(w, index=False, sheet_name='결과')
    elif fmt == 'docx':
        import docx
        d = docx.Document()
        for line in content.splitlines():
            if line.startswith('# '):
                d.add_heading(line[2:], level=1)
            elif line.startswith('## '):
                d.add_heading(line[3:], level=2)
            else:
                d.add_paragraph(line)
        d.save(buf)
    elif fmt == 'pptx':
        from pptx import Presentation
        from pptx.util import Inches, Pt
        prs = Presentation()
        prs.slide_width, prs.slide_height = (Inches(13.333), Inches(7.5))
        for spec in json.loads(content)['slides']:
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            head = slide.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(12), Inches(1.2)).text_frame
            head.word_wrap, head.text = (True, str(spec.get('title', '')))
            head.paragraphs[0].font.size, head.paragraphs[0].font.bold = (Pt(28), True)
            body = slide.shapes.add_textbox(Inches(0.7), Inches(1.8), Inches(12), Inches(5)).text_frame
            body.word_wrap = True
            for j, bullet in enumerate(spec.get('bullets', [])[:6]):
                p = body.paragraphs[0] if j == 0 else body.add_paragraph()
                p.text, p.font.size = ('• ' + str(bullet), Pt(18))
        prs.save(buf)
    elif fmt == 'pdf':
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import ParagraphStyle
        font = _pdf_font()
        body = ParagraphStyle('b', fontName=font, fontSize=11, leading=18, wordWrap='CJK')
        head = ParagraphStyle('h', parent=body, fontSize=17, leading=24, spaceAfter=10)
        story = [Paragraph(html_lib.escape(l.lstrip('# ')), head if l.startswith('#') else body) if l.strip() else Spacer(1, 8) for l in content.splitlines()]
        SimpleDocTemplate(buf).build(story)
    elif fmt == 'png':
        r = client.images.generate(model=ss.settings.get('image_model') or 'gpt-image-1', prompt=content, size='1024x1024', n=1)
        buf.write(base64.b64decode(r.data[0].b64_json))
    elif fmt == 'mp3':
        buf.write(client.audio.speech.create(model=TTS_MODEL, voice=ss.settings['voice'], input=content[:4000]).content)
    return (f'{stem}.{fmt}', buf.getvalue())

def create_files(prompt, answer_):
    made, errors = ([], [])
    try:
        plan = parse_json(llm([{'role': 'system', 'content': PLAN_PROMPT}, {'role': 'user', 'content': f'요청: {prompt}\n\n답변: {answer_[:6000]}'}], json_mode=True))
    except Exception as e:
        return (made, [f'파일 계획 실패: {e}'])
    for item in plan.get('files', [])[:3]:
        try:
            name, data = make_file(item)
            made.append(add_to_library(name, data, '생성')['id'])
        except Exception as e:
            errors.append(f"{item.get('name', '파일')}.{item.get('format', '')} 생성 실패: {e}")
    return (made, errors)

def to_mail(i):
    m = ss.messages[i]
    ss.mail_subject = '[에이블] 업무 처리 결과'
    ss.mail_body = m['content']
    ss.mail_attach = list(m.get('outputs', []))
    ss.menu = '📧 이메일 관리'
    ss.notice = "📧 답변을 메일 초안으로 옮겼습니다. 아래 '자료실 파일 첨부해서 보내기'에서 첨부도 고를 수 있습니다."

def render_more(i, m):
    for fid in m.get('outputs', []):
        f = next((x for x in ss.library if x['id'] == fid), None)
        if not f:
            continue
        if f['name'].lower().endswith('.png'):
            st.image(f['data'])
        st.download_button(f"📄 {f['name']}", f['data'], file_name=f['name'], key=f'out_{i}_{fid}')
    for w in m.get('warnings', []):
        (st.success if w.startswith('✅') else st.warning)(w)
    a, b = st.columns(2)
    if a.button('🔊 음성으로 듣기', key=f'listen_{i}'):
        speak(m['content'], force=True)
    b.button('📧 메일 초안으로', key=f'tomail_{i}', on_click=to_mail, args=(i,))

def page_chat():
    st.header('💬 채팅')
    st.radio('자료 분석 범위', ['검색', '전체'], horizontal=True, key='analysis_mode', help='검색: 질문과 관련된 부분만 참고 / 전체: RAG에 켜 둔 자료 전체(최대 4만 5천 자)를 참고')
    for i, m in enumerate(ss.messages):
        with st.chat_message(m['role']):
            st.markdown(m['content'])
            if m['role'] == 'assistant':
                render_extras(i, m)
                render_more(i, m)
            elif m.get('files'):
                st.caption('📎 ' + ', '.join(m['files']))
    chat_area = st.container()
    with st.expander('📎 파일 첨부 · 🎤 음성 입력', expanded=ss.open_tools):
        ups = st.file_uploader('PDF, 이미지, 문서 파일을 끌어다 놓으세요', type=CHAT_TYPES, accept_multiple_files=True, key=f'chat_up_{ss.chat_key}')
        audio = st.audio_input('마이크로 말씀하세요', key=f'chat_audio_{ss.chat_key}')
    attached = [f for f in ss.library if f['id'] in ss.attach_ids]
    if attached:
        st.caption('📁 자료실에서 첨부됨: ' + ', '.join((f['name'] for f in attached)))
    st.caption('⚡ 자주 쓰는 질문')
    cols = st.columns(len(QUICK_PROMPTS))
    for col, qp in zip(cols, QUICK_PROMPTS):
        col.button(qp, key=f'qp_{qp}', on_click=set_prompt, args=(qp,))
    sub = st.chat_input('메시지 입력 · ＋ 파일 첨부 · 🎤 음성 입력', accept_file='multiple', file_type=CHAT_TYPES, accept_audio=True)
    prompt, sub_files, sub_audio = ('', [], None)
    if isinstance(sub, str):
        prompt = sub
    elif sub is not None:
        prompt = sub.text or ''
        sub_files = list(sub.files or [])
        sub_audio = getattr(sub, 'audio', None)
    if ss.pending_prompt and (not prompt):
        prompt, ss.pending_prompt = (ss.pending_prompt, None)
    for au in [x for x in (sub_audio, audio) if x is not None]:
        audio_bytes = au.getvalue()
        h = hashlib.md5(audio_bytes).hexdigest()
        if h != ss.last_audio:
            ss.last_audio = h
            try:
                prompt = (prompt + '\n' + stt(audio_bytes)).strip()
            except Exception as e:
                error_ui(diagnostic(e, '음성 인식'))
    if not prompt and sub_files:
        prompt = '첨부 자료의 주요 내용과 확인할 사항을 정리해줘.'
    if prompt:
        files = [add_to_library(u.name, u.getvalue(), '업로드') for u in list(ups or []) + sub_files]
        files += [f for f in attached if f not in files]
        ss.open_tools = False
        ss.last_error = None
        n_before = len(ss.messages)
        with chat_area:
            handle_turn(prompt, files)
            if ss.last_error:
                error_ui(ss.last_error)
            last = ss.messages[-1] if len(ss.messages) == n_before + 2 else None
            if last and ss.last_error is None:
                warnings = []
                if WANTS_FILE_RE.search(prompt):
                    with st.spinner('요청한 결과 파일을 만들고 있습니다...'):
                        last['outputs'], errs = create_files(prompt, last['content'])
                    warnings += errs
                if re.search('회의|업무|할 ?일|담당|기한', prompt):
                    with st.spinner('자료에서 업무 후보를 찾고 있습니다...'):
                        n = extract_candidates(prompt, files)
                    if n:
                        warnings.append(f"업무 후보 {n}건을 '내 작업 > 📥 검토함'에 저장했습니다. 근거를 확인한 뒤 반영하세요.")
                last['warnings'] = warnings
                if last.get('outputs') or warnings:
                    render_more(len(ss.messages) - 1, last)
        archive_current()
    if ss.suggestions:
        st.caption('💡 이어서 물어보기')
        for j, sq in enumerate(ss.suggestions):
            st.button(sq, key=f'sg_{j}', on_click=set_prompt, args=(sq,))
_base_page_library = page_library

def page_library():
    _base_page_library()
    if not ss.library:
        return
    st.divider()
    st.subheader('👀 자료 미리보기')
    kind = st.radio('자료 종류', ['전체', '첨부 원본', '생성 결과'], horizontal=True, key='lib_kind')
    items = [f for f in ss.library if kind == '전체' or (kind == '생성 결과') == (f['source'] == '생성')]
    if items:
        pick = st.selectbox('자료 선택', [f['id'] for f in items], key='lib_preview', format_func=lambda x: next((f['name'] for f in items if f['id'] == x)))
        f = next((x for x in items if x['id'] == pick))
        render_summary(f)
        ext = f['name'].rsplit('.', 1)[-1].lower()
        if ext in IMG_MIME:
            st.image(f['data'])
        elif ext in ('csv', 'xlsx', 'tsv'):
            try:
                df = pd.read_excel(io.BytesIO(f['data'])) if ext == 'xlsx' else pd.read_csv(io.BytesIO(f['data']), sep='\t' if ext == 'tsv' else ',')
                st.dataframe(df.head(100), hide_index=True)
                st.caption('처음 100행만 보여 줍니다.')
            except Exception:
                st.info('표 미리보기를 열지 못했습니다. 원본을 다운로드해 주세요.')
        elif ext in AUDIO_EXT:
            st.audio(f['data'])
            if f['text']:
                st.text(f['text'][:3000])
        elif f['text']:
            st.text(f['text'][:6000])
            st.caption('최대 6,000자까지 보여 줍니다.')
        else:
            st.caption('이 형식은 미리보기가 없습니다. 원본을 다운로드해 주세요.')
    else:
        st.caption('해당 종류의 자료가 없습니다.')

def _decode(v):
    try:
        return str(make_header(decode_header(v or '')))
    except Exception:
        return v or ''

def fetch_gmail(limit=10):
    user, pw, _, _ = smtp_conf()
    if not (user and pw):
        ss.notice = '⚠️ Gmail 주소와 앱 비밀번호가 필요합니다. (api_key.txt 또는 설정)'
        return
    try:
        box = imaplib.IMAP4_SSL('imap.gmail.com', timeout=20)
        box.login(user, pw)
        box.select('INBOX', readonly=True)
        _, data = box.search(None, 'ALL')
        rows = []
        for uid in data[0].split()[-limit:][::-1]:
            _, msg_data = box.fetch(uid, '(RFC822)')
            msg = email_lib.message_from_bytes(msg_data[0][1])
            body = ''
            for part in msg.walk() if msg.is_multipart() else [msg]:
                if part.get_content_type() == 'text/plain' and (not part.get_filename()):
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                    break
            frm = _decode(msg.get('From'))
            addr = parseaddr(frm)[1]
            rows.append({'id': 'g' + uid.decode(), 'from': frm.split('<')[0].strip(' "') or addr, 'addr': addr, 'date': _decode(msg.get('Date'))[:25], 'subject': _decode(msg.get('Subject')) or '(제목 없음)', 'body': body[:5000] or '(본문 없음)'})
        box.logout()
        ss.inbox = rows + [m for m in ss.inbox if not m['id'].startswith('g')]
        ss.notice = f'📥 Gmail에서 최근 메일 {len(rows)}통을 불러왔습니다.'
    except Exception as e:
        ss.notice = f'⚠️ Gmail 조회 실패: {e} (Gmail 설정에서 IMAP 사용이 켜져 있는지 확인하세요)'

def send_with_files():
    raw = ss.mail_to.strip()
    c = find_contact(raw)
    addr, name = (c['이메일'], c['이름']) if c else (raw, None)
    if not EMAIL_RE.fullmatch(addr or ''):
        ss.notice = '⚠️ 받는 사람을 연락처 이름이나 올바른 이메일 주소로 입력해 주세요.'
        return
    if not ss.mail_subject.strip():
        ss.notice = '⚠️ 제목을 입력해 주세요.'
        return
    files = [f for f in ss.library if f['id'] in ss.get('mail_attach', [])]
    if sum((f['size'] for f in files)) > 15 * 1024 * 1024:
        ss.notice = '⚠️ 첨부파일 합계는 15MB 이하만 보낼 수 있습니다.'
        return
    user, pw, host, port = smtp_conf()
    mode = '모의 발송'
    try:
        if user and pw:
            msg = EmailMessage()
            msg['From'], msg['To'], msg['Subject'] = (user, addr, ss.mail_subject)
            msg.set_content(ss.mail_body)
            for f in files:
                import mimetypes
                major, minor = (mimetypes.guess_type(f['name'])[0] or 'application/octet-stream').split('/', 1)
                msg.add_attachment(f['data'], maintype=major, subtype=minor, filename=f['name'])
            with smtplib.SMTP_SSL(host, port, timeout=30) as server:
                server.login(user, pw)
                server.send_message(msg)
            mode = '실제 발송'
    except Exception as e:
        ss.notice = f'⚠️ 발송 실패: {e}'
        return
    ss.sent.append({'받는 사람': f'{name} <{addr}>' if name else addr, '제목': ss.mail_subject, '본문': ss.mail_body, '발송 시각': datetime.now().strftime('%Y-%m-%d %H:%M'), '방식': mode + (f' · 첨부 {len(files)}개' if files else '')})
    if not any((x['이메일'].lower() == addr.lower() for x in ss.contacts)):
        upsert_contact(name, addr)
    ss.mail_to = ss.mail_subject = ss.mail_body = ''
    ss.mail_attach = []
    ss.notice = f'📤 {name or addr}에게 첨부 {len(files)}개와 함께 메일을 보냈습니다. ({mode})'

def save_mail_draft():
    if not (ss.mail_subject.strip() or ss.mail_body.strip()):
        ss.notice = '⚠️ 저장할 제목이나 본문이 없습니다.'
        return
    ss.mail_drafts.append({'id': uuid.uuid4().hex[:8], 'to': ss.mail_to, 'subject': ss.mail_subject or '(제목 없음)', 'body': ss.mail_body, 'attach': list(ss.get('mail_attach', [])), 'saved': datetime.now().strftime('%m-%d %H:%M')})
    ss.notice = '💾 메일 초안을 저장했습니다.'

def load_mail_draft():
    d = next((x for x in ss.mail_drafts if x['id'] == ss.get('draft_pick')), None)
    if d:
        ss.mail_to, ss.mail_subject, ss.mail_body = (d['to'], d['subject'], d['body'])
        ss.mail_attach = [x for x in d['attach'] if any((f['id'] == x for f in ss.library))]
        ss.notice = "📂 초안을 불러왔습니다. '메일 작성' 탭에서 확인하세요."
_base_page_email = page_email

def page_email():
    _base_page_email()
    st.divider()
    with st.expander('📥 Gmail 받은편지함 불러오기'):
        st.caption("api_key.txt(또는 설정)의 Gmail 주소·앱 비밀번호로 실제 받은편지함 최근 메일을 읽어 와 '받은편지함' 탭에 보여 줍니다.")
        st.button('📥 최근 메일 10통 불러오기', on_click=fetch_gmail)
    with st.expander('📎 자료실 파일 첨부해서 보내기', expanded=bool(ss.get('mail_attach'))):
        st.caption("'메일 작성' 탭에 적은 받는 사람·제목·본문에 자료실 파일을 붙여 보냅니다.")
        valid = [f['id'] for f in ss.library]
        ss.mail_attach = [x for x in ss.get('mail_attach', []) if x in valid]
        st.multiselect('첨부할 파일', valid, key='mail_attach', format_func=lambda x: next((f['name'] for f in ss.library if f['id'] == x)))
        st.button('📤 첨부해서 보내기', on_click=send_with_files, type='primary')
    with st.expander(f'💾 메일 초안 저장·불러오기 ({len(ss.mail_drafts)})'):
        st.button('💾 지금 작성 중인 메일을 초안으로 저장', on_click=save_mail_draft)
        if ss.mail_drafts:
            st.selectbox('저장된 초안', [d['id'] for d in ss.mail_drafts][::-1], key='draft_pick', format_func=lambda x: next((f"{d['saved']} · {d['subject']}" for d in ss.mail_drafts if d['id'] == x)))
            st.button('📂 초안 불러오기', on_click=load_mail_draft)

def backup_bytes():
    data = {k: ss[k] for k in WS_KEYS + SAVE_KEYS if k in ss}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('workspace.json', json.dumps(data, ensure_ascii=False, default=_enc))
    return buf.getvalue()

def restore_backup():
    up = ss.get('backup_up')
    if not up:
        ss.notice = '⚠️ 복원할 백업 ZIP을 먼저 선택하세요.'
        return
    try:
        with zipfile.ZipFile(io.BytesIO(up.getvalue())) as z:
            data = json.loads(z.read('workspace.json'), object_hook=_dec)
        for k, v in data.items():
            if k in WS_KEYS + SAVE_KEYS:
                ss[k] = v
        ss.notice = '♻️ 백업을 복원했습니다.'
    except Exception as e:
        ss.notice = f'⚠️ 복원 실패: {e}'
_base_page_settings = page_settings

def page_settings():
    _base_page_settings()
    s = ss.settings
    st.divider()
    with st.expander('💾 작업공간 백업·복원'):
        st.download_button('⬇️ 백업 ZIP 다운로드', backup_bytes(), file_name='able_backup.zip')
        st.file_uploader('백업 ZIP 선택', type=['zip'], key='backup_up')
        st.button('♻️ 백업에서 복원', on_click=restore_backup)
        st.caption('백업에는 대화·업무·일정·자료·연락처가 들어갑니다. API 키와 비밀번호는 들어가지 않습니다.')
    with st.expander('ℹ️ 저장 방식 안내'):
        if DB_URL:
            st.success('🗄️ Supabase(PostgreSQL)에 저장 중입니다. 재배포·재시작해도 계정·업무·대화가 유지됩니다.')
        else:
            st.write(f'작업공간 저장 파일: `{os.path.abspath(DB_FILE)}` (SQLite)')
            st.caption('같은 서버에서는 새로고침·재접속해도 유지됩니다. Streamlit Cloud는 재배포·재시작 때 파일이 지워질 수 있으니 Secrets에 DATABASE_URL(Supabase 연결 주소)을 넣거나 백업 ZIP을 받아 두세요.')

def extract_candidates(prompt, files):
    docs = list(files) + [f for f in ss.library if f['rag'] and f['text'] and (f not in files)]
    sources = {f['name']: f['text'] for f in docs if f.get('text')}
    if not sources:
        return 0
    context = '\n\n'.join((f'[파일 {n}]\n{t}' for n, t in sources.items()))[:30000]
    sysmsg = '자료에서 담당자에게 배정된 업무를 모두 찾아 JSON으로만 답하라. 없는 담당자·날짜를 만들지 마라. 중간 점검과 최종 기한을 구분하라. 기한이 불확실하면 due는 빈 문자열. quote는 근거가 되는 원문을 그대로 짧게 인용. 해당 내용이 없으면 빈 문자열. 형식: {"tasks": [{"title": "", "owner": "", "details": "업무 내용 2~3문장", "deadline_text": "원문 표현 그대로의 기한", "due": "YYYY-MM-DD 또는 빈 문자열", "checkpoint": "중간 점검", "deliverable": "결과물", "dependency": "선행 조건", "priority": "높음|보통|낮음", "source": "파일명", "quote": ""}]}'
    try:
        out = parse_json(llm([{'role': 'system', 'content': sysmsg + f'\n오늘 날짜: {TODAY}'}, {'role': 'user', 'content': f'요청: {prompt}\n\n{context}'}], json_mode=True))
    except Exception:
        return 0
    norm = lambda x: re.sub('\\s+', '', str(x))
    n = 0
    for t in out.get('tasks', [])[:30]:
        if not t.get('title'):
            continue
        raw = sources.get(t.get('source', ''), ' '.join(sources.values()))
        t.update(id=uuid.uuid4().hex[:8], verified=bool(t.get('quote') and norm(t['quote']) in norm(raw)))
        ss.candidates.append(t)
        n += 1
    return n

def accept_candidate(cid):
    c = next((x for x in ss.candidates if x['id'] == cid))
    has_due = bool(re.fullmatch('\\d{4}-\\d{2}-\\d{2}', str(c.get('due', ''))))
    t = {'id': uuid.uuid4().hex[:8], '업무': c['title'], '담당자': c.get('owner') or ss.settings['name'], '마감일': to_date(c['due']) if has_due else None, '상태': '대기', '우선순위': c.get('priority') if c.get('priority') in ('높음', '보통', '낮음') else '보통', '상세': c.get('details', ''), '기한 설명': c.get('deadline_text') or ('' if has_due else '미정'), '중간 점검': c.get('checkpoint', ''), '결과물': c.get('deliverable', ''), '선행 조건': c.get('dependency', ''), '근거': c.get('source', ''), '인용': c.get('quote', '')}
    ss.tasks.append(t)
    record_change(t, '등록', '-', f"검토함에서 반영 (근거: {c.get('source', '')})")
    ss.candidates = [x for x in ss.candidates if x['id'] != cid]

def candidates_ui():
    if not ss.candidates:
        st.caption("검토할 업무가 없습니다. 채팅에서 회의록을 첨부하고 '담당자별 업무 정리해줘'라고 요청해 보세요.")
    for c in ss.candidates:
        with st.expander(f"{c['title']} · {c.get('owner') or '담당자 미정'}"):
            if c.get('details'):
                st.write(c['details'])
            st.caption(f"기한 {c.get('deadline_text') or c.get('due') or '미정'} / 중간 점검 {c.get('checkpoint') or '없음'}")
            if c.get('deliverable') or c.get('dependency'):
                st.caption(f"결과물 {c.get('deliverable') or '-'} / 선행 조건 {c.get('dependency') or '-'}")
            st.caption(f"근거 · {c.get('source', '')}")
            st.code(c.get('quote', ''), language=None)
            st.caption('✅ 원문과 일치하는 근거 확인됨' if c.get('verified') else '⚠️ 원문 일치 미확인 · 자료를 직접 확인해 주세요.')
            ok = st.checkbox('원문과 담당자·기한을 확인했습니다', key=f"cand_ok_{c['id']}")
            a, b = st.columns(2)
            a.button('✅ 업무에 반영', key=f"cand_acc_{c['id']}", on_click=accept_candidate, args=(c['id'],), disabled=not ok)
            b.button('❌ 제외', key=f"cand_rej_{c['id']}", on_click=reject_candidate, args=(c['id'],))

def task_detail(t, prefix):
    with st.expander(f"{t['업무']} · {t['담당자']} · {t['상태']}"):
        st.write(t.get('상세') or '상세 내용이 없습니다. 아래에서 직접 적을 수 있습니다.')
        st.caption(f"기한 {t.get('기한 설명') or _due_read(t)} ({dday(_due_read(t))}) / 중간 점검 {t.get('중간 점검') or '없음'}")
        if t.get('결과물') or t.get('선행 조건'):
            st.caption(f"결과물 {t.get('결과물') or '-'} / 선행 조건 {t.get('선행 조건') or '-'}")
        st.caption(f"근거 · {t.get('근거') or '직접 등록'}")
        if t.get('인용'):
            st.code(t['인용'], language=None)
        ver = f"{t['id']}_{t['상태']}_{_due_read(t)}_{t.get('진행률', 0)}"
        with st.form(f'{prefix}_form_{ver}'):
            opts = status_options(t)
            status = st.selectbox('진행 상태', opts, index=opts.index(t['상태']) if t['상태'] in opts else 0, help='진행 중인 업무는 완료율이 100%가 되면 완료로 넘어갑니다.')
            desc = st.text_input('기한 설명', value=t.get('기한 설명', ''), placeholder=f'예: {_due_read(t)} 10:00')
            iso = st.text_input('달력 날짜 YYYY-MM-DD · 미정이면 비움', value='' if t.get('마감일') is None else str(_due_read(t)))
            detail = st.text_area('상세 내용', value=t.get('상세', ''), height=90)
            pct = st.slider('완료율 (진행 중일 때 표시)', 0, 100, int(t.get('진행률', 0)), step=5, format='%d%%')
            if st.form_submit_button('변경 저장'):
                try:
                    new_due = date.fromisoformat(iso.strip()) if iso.strip() else None
                except ValueError:
                    st.error('날짜를 YYYY-MM-DD 형식으로 입력하세요. 예: 2026-11-10')
                else:
                    if not iso.strip():
                        desc = '미정'
                    if pct == 100 and status == '진행 중':
                        status = '완료'
                    for field, value in [('상태', status), ('마감일', new_due), ('기한 설명', desc), ('상세', detail), ('진행률', pct)]:
                        record_change(t, field, t.get(field, ''), value)
                        t[field] = value
                    st.rerun()
        st.button('🗑️ 업무 삭제', key=f"{prefix}_rm_{t['id']}", on_click=delete_task_now, args=(t['id'],))
        st.button('💬 이 업무로 대화하기', key=f"{prefix}_talk_{t['id']}", on_click=go, args=('💬 채팅', f"'{t['업무']}' 업무(담당 {t['담당자']}, 기한 {t.get('기한 설명') or _due_read(t)}, 내용: {t.get('상세', '')})를 어떻게 진행하면 좋을지 단계별로 알려줘"))
_v4_page_my_tasks = page_my_tasks

def page_my_tasks():
    _v4_page_my_tasks()
    st.divider()
    st.subheader('📂 업무 상세 보기')
    mine = sorted([t for t in ss.tasks if t['담당자'] == ss.settings['name']], key=lambda x: _due_read(x))
    for t in mine:
        task_detail(t, 'mydet')
    if not mine:
        st.caption('내 업무가 없습니다.')
_v4_page_team = page_team

def page_team():
    _v4_page_team()
    if not ss.tasks:
        return
    st.divider()
    st.subheader('📂 담당자별 업무 상세')
    owner = st.selectbox('상세를 볼 담당자', ['전체'] + sorted({t['담당자'] for t in ss.tasks}), key='team_detail_owner')
    for t in sorted([t for t in ss.tasks if owner == '전체' or t['담당자'] == owner], key=lambda x: _due_read(x)):
        task_detail(t, 'teamdet')
_base_smtp_conf = smtp_conf
_TO_KEY = re.compile('(^|[._])(to|recipient|receiver|받는)($|[._])', re.I)
_PW_KEY = re.compile('pass|pw|pwd|비밀번호|app_?key|app_?code', re.I)

def _secret_items():
    items = []
    try:
        for k, v in st.secrets.items():
            if hasattr(v, 'items'):
                items += [(f'{k}.{k2}', v2) for k2, v2 in v.items()]
            else:
                items.append((k, v))
    except Exception:
        pass
    return [(str(k), str(v).strip()) for k, v in items]

def smtp_conf():
    user, pw, host, port = _base_smtp_conf()
    items = _secret_items()
    if not user:
        user = next((v for k, v in items if EMAIL_RE.fullmatch(v) and (not _TO_KEY.search(k))), '')
    if not pw:
        pw = next((v for k, v in items if _PW_KEY.search(k) and 'ACCESS' not in k.upper() and ('OPENAI' not in k.upper()) and (not v.startswith('sk-'))), '')
    return (user, pw.replace(' ', ''), host, port)
from email.mime.text import MIMEText
from email.header import Header

def send_email(to, subject, body):
    sender, password, _, _ = smtp_conf()
    sender = sender or os.getenv('GMAIL_ADDRESS', '')
    password = (password or os.getenv('GMAIL_APP_PASSWORD', '')).replace(' ', '')
    if not sender or not password:
        return {'status': 'skipped', 'error': 'Gmail 계정 정보(GMAIL_ADDRESS·GMAIL_APP_PASSWORD)가 없습니다.'}
    msg = MIMEText(body, _charset='utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = sender
    msg['To'] = to
    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as s:
            s.starttls()
            s.login(sender, password)
            s.sendmail(sender, [to], msg.as_string())
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'failed', 'error': str(e)}

def deliver(to_addr, subject, body, name=None):
    r = send_email(to_addr, subject, body)
    if r['status'] == 'failed':
        raise RuntimeError(r['error'])
    rec = {'받는 사람': f'{name} <{to_addr}>' if name else to_addr, '제목': subject, '본문': body, '발송 시각': datetime.now().strftime('%Y-%m-%d %H:%M'), '방식': '실제 발송' if r['status'] == 'success' else '모의 발송'}
    ss.sent.append(rec)
    if not any((c['이메일'].lower() == to_addr.lower() for c in ss.contacts)):
        upsert_contact(name, to_addr)
    return rec
st.markdown('<style>\n[data-testid="stElementContainer"]:has(h1#ai),\n[data-testid="stElementContainer"]:has(h1#ai) + *,\n[data-testid="stElementContainer"]:has(h1#ai) + * + * {display:none !important}\n.able-attach-title{font-weight:600;margin-bottom:.2rem}\n[data-testid="stPopoverBody"] button[kind="tertiary"]{justify-content:flex-start !important;font-size:1rem;padding:.55rem .8rem;border-radius:8px}\n[data-testid="stPopoverBody"] button[kind="tertiary"] > div,[data-testid="stPopoverBody"] button[kind="tertiary"] p{justify-content:flex-start !important;text-align:left !important;width:100%}\n[data-testid="stPopoverBody"] button[kind="tertiary"]:hover{background:#EDF4F3}\n</style>', unsafe_allow_html=True)

def show_notice():
    box = st.container()
    if ss.notice:
        with box:
            (st.warning if ss.notice.startswith('⚠️') else st.success)(ss.notice)
        ss.notice = ''
_v16_smtp_conf = smtp_conf

def smtp_conf():
    user, pw, host, port = _v16_smtp_conf()
    user = user or get_secret('GMAIL_ADDRESS') or get_secret('SMTP_USER')
    pw = pw or get_secret('GMAIL_APP_PASSWORD') or get_secret('SMTP_PASSWORD')
    return (user, pw.replace(' ', ''), host, port)
ATTACH_MENU = [('file', '📎 파일 업로드'), ('image', '🖼️ 이미지 첨부'), ('audio', '🎙️ 음성 파일 첨부'), ('camera', '📷 카메라 촬영')]
IMAGE_TYPES = ['png', 'jpg', 'jpeg', 'webp']
if 'attach_mode' not in ss:
    ss.attach_mode = None

def set_attach_mode(mode):
    ss.attach_mode = mode

def attach_panel():
    files, rec = ([], None)
    mode = ss.attach_mode
    if not mode:
        return (files, rec)
    k = ss.chat_key
    with st.container(border=True):
        a, b = st.columns([6, 1])
        a.markdown(f'<div class="able-attach-title">{dict(ATTACH_MENU)[mode]}</div>', unsafe_allow_html=True)
        b.button('✕ 닫기', key=f'att_close_{k}', on_click=set_attach_mode, args=(None,))
        if mode == 'file':
            files = st.file_uploader('파일을 선택하거나 끌어다 놓으세요', type=CHAT_TYPES, accept_multiple_files=True, key=f'att_file_{k}', label_visibility='collapsed') or []
        elif mode == 'image':
            files = st.file_uploader('이미지를 선택하세요', type=IMAGE_TYPES, accept_multiple_files=True, key=f'att_img_{k}', label_visibility='collapsed') or []
        elif mode == 'audio':
            files = st.file_uploader('음성 파일(mp3·wav·m4a 등)을 선택하세요', type=AUDIO_EXT, accept_multiple_files=True, key=f'att_aud_{k}') or []
            rec = st.audio_input('또는 바로 녹음하기', key=f'att_rec_{k}')
        elif mode == 'camera':
            shot = st.camera_input('카메라로 촬영하세요', key=f'att_cam_{k}')
            if shot is not None:
                shot.name = f'카메라_{hashlib.md5(shot.getvalue()).hexdigest()[:6]}.jpg'
                files = [shot]
        if files:
            st.caption('첨부됨: ' + ', '.join((f.name for f in files)) + ' · 메시지를 입력하고 보내면 함께 전달됩니다.')
    return (list(files), rec)

def page_chat():
    st.header('💬 채팅')
    st.radio('자료 분석 범위', ['검색', '전체'], horizontal=True, key='analysis_mode', help='검색: 질문과 관련된 부분만 참고 / 전체: RAG에 켜 둔 자료 전체(최대 4만 5천 자)를 참고')
    for i, m in enumerate(ss.messages):
        with st.chat_message(m['role']):
            st.markdown(m['content'])
            if m['role'] == 'assistant':
                render_extras(i, m)
                render_more(i, m)
            elif m.get('files'):
                st.caption('📎 ' + ', '.join(m['files']))
    chat_area = st.container()
    with st.expander('📎 파일 첨부 · 🎤 음성 입력', expanded=ss.open_tools):
        ups = st.file_uploader('PDF, 이미지, 문서 파일을 끌어다 놓으세요', type=CHAT_TYPES, accept_multiple_files=True, key=f'chat_up_{ss.chat_key}')
        audio = st.audio_input('마이크로 말씀하세요', key=f'chat_audio_{ss.chat_key}')
    attached = [f for f in ss.library if f['id'] in ss.attach_ids]
    if attached:
        st.caption('📁 자료실에서 첨부됨: ' + ', '.join((f['name'] for f in attached)))
    st.caption('⚡ 자주 쓰는 질문')
    cols = st.columns(len(QUICK_PROMPTS))
    for col, qp in zip(cols, QUICK_PROMPTS):
        col.button(qp, key=f'qp_{qp}', on_click=set_prompt, args=(qp,))
    bottom = getattr(st, 'bottom', None) or getattr(st, '_bottom', None) or st.container()
    with bottom:
        panel_files, panel_rec = attach_panel()
        plus, box = st.columns([1, 14], vertical_alignment='bottom')
        with plus:
            with st.popover('＋'):
                for mode, label in ATTACH_MENU:
                    st.button(label, key=f'att_menu_{mode}', on_click=set_attach_mode, args=(mode,), type='tertiary', width='stretch')
        with box:
            sub = st.chat_input('메시지를 입력하세요...', accept_audio=True)
    prompt, sub_audio = ('', None)
    if isinstance(sub, str):
        prompt = sub
    elif sub is not None:
        prompt = sub.text or ''
        sub_audio = getattr(sub, 'audio', None)
    if ss.pending_prompt and (not prompt):
        prompt, ss.pending_prompt = (ss.pending_prompt, None)
    if sub is not None or prompt:
        for au in [x for x in (sub_audio, panel_rec, audio) if x is not None]:
            audio_bytes = au.getvalue()
            h = hashlib.md5(audio_bytes).hexdigest()
            if h != ss.last_audio:
                ss.last_audio = h
                try:
                    prompt = (prompt + '\n' + stt(audio_bytes)).strip()
                except Exception as e:
                    error_ui(diagnostic(e, '음성 인식'))
    elif audio is not None and hashlib.md5(audio.getvalue()).hexdigest() != ss.last_audio:
        ss.last_audio = hashlib.md5(audio.getvalue()).hexdigest()
        try:
            prompt = stt(audio.getvalue())
        except Exception as e:
            error_ui(diagnostic(e, '음성 인식'))
    if not prompt and sub is not None and panel_files:
        prompt = '첨부 자료의 주요 내용과 확인할 사항을 정리해줘.'
    if prompt:
        files = [add_to_library(u.name, u.getvalue(), '업로드') for u in list(ups or []) + panel_files]
        files += [f for f in attached if f not in files]
        ss.open_tools = False
        ss.attach_mode = None
        ss.last_error = None
        n_before = len(ss.messages)
        with chat_area:
            handle_turn(prompt, files)
            if ss.last_error:
                error_ui(ss.last_error)
            last = ss.messages[-1] if len(ss.messages) == n_before + 2 else None
            if last and ss.last_error is None:
                warnings = []
                if WANTS_FILE_RE.search(prompt):
                    with st.spinner('요청한 결과 파일을 만들고 있습니다...'):
                        last['outputs'], errs = create_files(prompt, last['content'])
                    warnings += errs
                if TASK_PULL_RE.search(prompt) and registration_requested(prompt):
                    with st.spinner('자료에서 업무를 찾아 바로 추가하고 있습니다...'):
                        added = add_tasks_from_docs(prompt, files)
                    warnings.append(added)
                last['warnings'] = warnings
                render_more(len(ss.messages) - 1, last)
        archive_current()
    if ss.suggestions:
        st.caption('💡 이어서 물어보기')
        for j, sq in enumerate(ss.suggestions):
            st.button(sq, key=f'sg_{j}', on_click=set_prompt, args=(sq,))
import altair as alt

def _static_chart(mark):

    def draw(data=None, **kwargs):
        df = data.to_frame() if isinstance(data, pd.Series) else pd.DataFrame(data)
        df = df.reset_index()
        idx = str(df.columns[0])
        df.columns = [str(c) for c in df.columns]
        long = df.melt(id_vars=idx, var_name='항목', value_name='값')
        enc = {'x': alt.X(field=idx, type='nominal', title=None, sort=None, axis=alt.Axis(labelAngle=0)), 'y': alt.Y(field='값', type='quantitative', title=None), 'tooltip': [alt.Tooltip(field=idx, type='nominal'), alt.Tooltip(field='항목', type='nominal'), alt.Tooltip(field='값', type='quantitative')]}
        if long['항목'].nunique() > 1:
            enc['color'] = alt.Color(field='항목', type='nominal', legend=alt.Legend(title=None, orient='bottom'))
        style = {} if 'color' in enc else {'color': '#0E7490'}
        chart = getattr(alt.Chart(long), mark)(**style).encode(**enc)
        return st.altair_chart(chart, width='stretch')
    return draw
st.bar_chart = _static_chart('mark_bar')
st.line_chart = _static_chart('mark_line')
st.area_chart = _static_chart('mark_area')

def ws_sync():
    try:
        con = ws_db()
        rows = dict(con.execute('SELECT k, v FROM able_final_demo_state').fetchall())
        con.close()
    except Exception:
        return
    last = ss.setdefault('_ws_last', {})
    for k, raw in rows.items():
        if k not in WS_KEYS or k == 'conv_id' or k == 'messages' or (k == 'conversations'):
            continue
        mine = json.dumps(ss.get(k), ensure_ascii=False, default=_enc)
        if raw != last.get(k) and (k not in last or mine == last.get(k)):
            ss[k] = json.loads(raw, object_hook=_dec)
            last[k] = raw
import secrets as _secrets
if 'users' not in WS_KEYS:
    WS_KEYS.append('users')
PER_USER_KEYS = ['messages', 'conversations', 'conv_id', 'settings']
for _k in PER_USER_KEYS:
    if _k in WS_KEYS:
        WS_KEYS.remove(_k)
_v4_ws_save = ws_save

def ws_save():
    _v4_ws_save()
    if not ss.get('user'):
        return
    try:
        last = ss.setdefault('_ws_last', {})
        con = ws_db()
        for k in PER_USER_KEYS:
            key = f'{k}::{ss.user}'
            raw = json.dumps(ss.get(k), ensure_ascii=False, default=_enc)
            if last.get(key) != raw:
                con.execute('INSERT INTO able_final_demo_state(k, v, updated) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v, updated=excluded.updated', (key, raw, datetime.now().isoformat()))
                last[key] = raw
        con.commit()
        con.close()
    except Exception as e:
        st.sidebar.caption(f'⚠️ 대화 저장 실패: {e}')
if 'users' not in ss:
    ss.users = ws_load().get('users', [])

def _hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), bytes.fromhex(salt), 120000).hex()

def find_user(name):
    return next((u for u in ss.users if u['name'] == name.strip()), None)

def sign_up():
    name, pw, pw2 = (ss.su_name.strip(), ss.su_pw, ss.su_pw2)
    if not name or not pw:
        ss.login_msg = '⚠️ 이름과 비밀번호를 입력해 주세요.'
    elif len(pw) < 4:
        ss.login_msg = '⚠️ 비밀번호는 4자 이상으로 정해 주세요.'
    elif pw != pw2:
        ss.login_msg = '⚠️ 비밀번호 확인이 일치하지 않습니다.'
    elif find_user(name):
        ss.login_msg = f"⚠️ '{name}' 계정이 이미 있습니다. 로그인해 주세요."
    else:
        salt = _secrets.token_hex(16)
        ss.users.append({'name': name, 'role': ss.su_role.strip(), 'team': ss.su_team.strip() or '마케팅팀', 'email': ss.su_email.strip(), 'salt': salt, 'pw': _hash_pw(pw, salt), 'created': datetime.now().strftime('%Y-%m-%d %H:%M')})
        if ss.su_email.strip() and EMAIL_RE.fullmatch(ss.su_email.strip()):
            upsert_contact(name, ss.su_email.strip(), ss.su_role.strip())
        ws_save()
        ss.login_msg = f"✅ '{name}' 계정을 만들었습니다. 로그인해 주세요."

def log_in():
    u = find_user(ss.li_name)
    if not u or not hmac.compare_digest(_hash_pw(ss.li_pw, u['salt']), u['pw']):
        ss.login_msg = '⚠️ 이름 또는 비밀번호가 맞지 않습니다.'
        return
    ss.user = u['name']
    data = ws_load()
    ss.messages = data.get(f"messages::{u['name']}", [])
    ss.conversations = data.get(f"conversations::{u['name']}", [])
    ss.conv_id = data.get(f"conv_id::{u['name']}", uuid.uuid4().hex)
    if isinstance(data.get(f"settings::{u['name']}"), dict):
        ss.settings.update(data[f"settings::{u['name']}"])
    ss.suggestions = []
    ss.settings.update({'name': u['name'], 'role': u.get('role') or ss.settings['role'], 'team': u.get('team') or ss.settings['team']})
    ss.menu = MENUS[0]
    ss.login_msg = ''

def log_out():
    for k in ['user', 'suggestions']:
        ss.pop(k, None)
    ss.messages, ss.conversations, ss.attach_ids = ([], [], [])
    ss.conv_id = uuid.uuid4().hex
ss.users = ws_load().get('users', ss.users) if not ss.get('user') else ss.users
if not ss.get('user'):
    st.markdown('## 🔐 에이블 로그인')
    st.caption("팀원별 계정으로 로그인하면 '내 작업'이 내 업무로 바뀌고, 팀 업무를 함께 관리할 수 있습니다.")
    msg_box = st.container()
    msg = ss.get('login_msg', '')
    if msg:
        with msg_box:
            (st.warning if msg.startswith('⚠️') else st.success)(msg)
    t_in, t_up = st.tabs(['🔑 로그인', '📝 회원가입'])
    with t_in:
        if ss.users:
            with st.form('able_login_form'):
                st.selectbox('이름', [u['name'] for u in ss.users], key='li_name')
                st.text_input('비밀번호', type='password', key='li_pw')
                st.form_submit_button('로그인', type='primary', on_click=log_in)
        else:
            st.info("아직 계정이 없습니다. '📝 회원가입' 탭에서 첫 계정을 만들어 주세요.")
    with t_up:
        with st.form('able_signup_form'):
            a, b = st.columns(2)
            a.text_input('이름', key='su_name', placeholder='예: 김 대리')
            b.text_input('직책', key='su_role', placeholder='예: 대리')
            a.text_input('소속', key='su_team', placeholder='예: 마케팅팀')
            b.text_input('이메일 (연락처에 자동 등록)', key='su_email', placeholder='예: kim@company.com')
            a.text_input('비밀번호', type='password', key='su_pw')
            b.text_input('비밀번호 확인', type='password', key='su_pw2')
            st.form_submit_button('회원가입', on_click=sign_up)
    st.stop()
ws_sync()

def team_members():
    names = {u['name'] for u in ss.users} | {c['이름'] for c in ss.contacts} | {t['담당자'] for t in ss.tasks}
    names.add(ss.settings['name'])
    return sorted((n for n in names if n))

def task_pct(t):
    return 100 if t['상태'] == '완료' else int(t.get('진행률', 0)) if t['상태'] == '진행 중' else 0

def team_status_table():
    members = sorted({t['담당자'] for t in ss.tasks} | {u['name'] for u in ss.users})
    rows = []
    for m in members:
        ts = [t for t in ss.tasks if t['담당자'] == m]
        open_ = [t for t in ts if t['상태'] not in ('완료', '취소')]
        nxt = min(open_, key=lambda x: _due_read(x)) if open_ else None
        done = sum((t['상태'] == '완료' for t in ts))
        rows.append({'담당자': m, '전체': len(ts), '대기': sum((t['상태'] == '대기' for t in ts)), '진행 중': sum((t['상태'] == '진행 중' for t in ts)), '완료': done, '기한 초과': sum((_due_read(t) < TODAY for t in open_)), '마감 임박(2일)': sum((TODAY <= _due_read(t) <= TODAY + timedelta(days=2) for t in open_)), '완료율': round(done / len(ts) * 100) if ts else 0, '가장 급한 업무': f"{nxt['업무']} ({dday(_due_read(nxt))})" if nxt else '-'})
    df = pd.DataFrame(rows)
    total = len(ss.tasks)
    done_all = sum((t['상태'] == '완료' for t in ss.tasks))
    c = st.columns(4)
    c[0].metric('팀 전체 업무', total)
    c[1].metric('팀 완료율', f'{(round(done_all / total * 100) if total else 0)}%')
    c[2].metric('기한 초과', int(df['기한 초과'].sum()) if not df.empty else 0)
    c[3].metric('마감 임박(2일)', int(df['마감 임박(2일)'].sum()) if not df.empty else 0)
    if not df.empty:
        st.dataframe(df, hide_index=True, width='stretch', column_config={'완료율': st.column_config.ProgressColumn('완료율', format='%d%%', min_value=0, max_value=100)})
    st.markdown('**📋 팀 업무 한눈에 보기** (담당자 → 마감일 순)')
    if ss.tasks:
        allv = pd.DataFrame([{'담당자': t['담당자'], '업무': t['업무'], '상태': t['상태'], '마감일': _due_read(t), 'D-day': dday(_due_read(t)), '우선순위': t['우선순위'], '완료율': task_pct(t)} for t in ss.tasks])
        st.dataframe(allv.sort_values(['담당자', '마감일']), hide_index=True, width='stretch', column_config={'완료율': st.column_config.ProgressColumn('완료율', format='%d%%', min_value=0, max_value=100)})

def add_team_task():
    owner = ss.tt_owner_new.strip() if ss.tt_owner == '✏️ 직접 입력' else ss.tt_owner
    title = ss.tt_title.strip()
    if not owner or not title:
        ss.notice = '⚠️ 담당자와 업무명을 입력해 주세요.'
        return
    t = {'id': uuid.uuid4().hex[:8], '업무': title, '담당자': owner, '마감일': ss.tt_due, '상태': '대기', '우선순위': ss.tt_pr, '상세': ss.tt_detail.strip(), '결과물': ss.tt_out.strip(), '근거': f'{ss.user} 님이 팀 업무 현황에서 등록'}
    ss.tasks.append(t)
    record_change(t, '등록', '-', f'{owner}에게 배정 (등록: {ss.user})')
    for k in ['tt_title', 'tt_detail', 'tt_out', 'tt_owner_new']:
        ss[k] = ''
    ss.notice = f"✅ {owner} 님에게 '{title}' 업무를 추가했습니다."

def team_task_form():
    with st.expander('➕ 팀원에게 업무 추가', expanded=False):
        a, b = st.columns(2)
        a.selectbox('담당자', team_members() + ['✏️ 직접 입력'], key='tt_owner')
        if ss.get('tt_owner') == '✏️ 직접 입력':
            b.text_input('담당자 이름', key='tt_owner_new')
        st.text_input('업무명', key='tt_title', placeholder='예: 11월 SNS 콘텐츠 일정표 작성')
        c, d = st.columns(2)
        c.date_input('마감일', TODAY + timedelta(days=3), key='tt_due')
        d.selectbox('우선순위', ['높음', '보통', '낮음'], index=1, key='tt_pr')
        st.text_area('상세 내용', key='tt_detail', height=80)
        st.text_input('결과물', key='tt_out', placeholder='예: 일정표 XLSX')
        st.button('업무 추가', type='primary', on_click=add_team_task)
_v15_page_team = page_team

def page_team():
    st.header('👥 팀 업무 현황')
    show_notice()
    st.subheader('📊 팀 업무 현황표')
    team_status_table()
    team_task_form()
    st.divider()
    _h = st.header
    st.header = lambda *a, **k: None
    try:
        _v15_page_team()
    finally:
        st.header = _h
st.markdown('<style>\n:root{--ink:#1C1C1C;--muted:#77756F;--line:#E8E6E1;--soft:#F6F5F2;--hover:#EEECE8;--pick:#E7E4DE}\n.stApp{background:#FFFFFF;color:var(--ink)}\nheader[data-testid="stHeader"]{background:transparent}\n[data-testid="stMainBlockContainer"]{padding-top:2.2rem;max-width:1180px}\n[data-testid="stSidebar"]{background:var(--soft);border-right:1px solid var(--line)}\n[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{padding-top:1rem}\n/* 메뉴: 동그라미 없이, 선택된 항목은 배경 강조 */\n[data-testid="stSidebar"] [role="radiogroup"]{gap:2px}\n[data-testid="stSidebar"] [role="radiogroup"] label{width:100%;padding:.42rem .65rem;border-radius:8px;margin:0}\n[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:var(--hover)}\n[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"]{background:var(--pick);font-weight:600}\n[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child{display:none}\n[data-testid="stSidebar"] .stButton button[kind="tertiary"]{justify-content:flex-start;color:#3F3E3B;padding:.25rem .4rem;min-height:2rem}\n[data-testid="stSidebar"] .stButton button[kind="tertiary"] p{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:190px}\n.able-logo{display:flex;align-items:center;gap:.5rem;font-size:1.05rem;font-weight:600;margin:.1rem 0 .8rem}\n.able-logo b{font-family:Georgia,serif;font-size:1.6rem;font-weight:700;line-height:1}\n.able-side-h{font-size:.78rem;color:var(--muted);margin:.9rem 0 .2rem .2rem}\n.able-crumb{font-size:.8rem;color:var(--muted);margin-bottom:.4rem}\n.able-title{font-size:2rem;font-weight:700;letter-spacing:-.03em;line-height:1.25}\n.able-sub{color:var(--muted);font-size:.9rem;margin-top:.2rem}\n.able-card-h{font-weight:700;font-size:1.02rem;margin-bottom:.4rem}\n/* 버튼·카드·입력창 */\n.stButton>button,.stDownloadButton>button,[data-testid="stPopover"] button{border-radius:8px;border-color:var(--line)}\n.stButton>button[kind="primary"],[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]{background:#1C1C1C !important;border-color:#1C1C1C !important;color:#fff}\n[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--line) !important;border-radius:12px !important}\n[data-testid="stChatMessage"]{background:#FFFFFF;border:none;border-bottom:1px solid var(--line);border-radius:0;padding:1rem .2rem}\n[data-testid="stChatInput"]{border:1px solid var(--line);border-radius:14px;background:#fff}\nh2{font-size:1.55rem !important;letter-spacing:-.02em}\n/* 홈 미니 달력 */\n.able-mini{width:100%;border-collapse:collapse;text-align:center;font-size:.86rem;border:none !important}\n.able-mini tr,.able-mini th,.able-mini td{border:none !important;background:transparent !important}\n.able-task{font-size:.92rem;padding-top:.15rem}\n[class*="st-key-home_chk_"] [data-testid="stCheckbox"] label{align-items:center}\n[class*="st-key-home_chk_"] [data-testid="stCheckbox"] label > span + div{width:1.05rem !important;height:1.05rem !important;min-height:0 !important;flex:none !important;border-radius:4px !important}\n.able-mini th{color:var(--muted);font-weight:500;padding:.25rem 0}\n.able-mini td{padding:.28rem 0;color:#3F3E3B}\n.able-mini td.out{color:#C9C6C0}\n.able-mini td span{display:inline-block;width:1.8rem;height:1.8rem;line-height:1.8rem;border-radius:50%}\n.able-mini td.today span{background:#1C1C1C;color:#fff;font-weight:600}\n.able-mini td.has span{box-shadow:inset 0 -2px 0 #B9B5AD}\n.able-day-h{font-weight:700;margin-bottom:.3rem}\n.able-row{display:flex;gap:1rem;padding:.55rem 0;border-bottom:1px solid var(--line);font-size:.92rem}\n.able-row .t{color:#3F3E3B;min-width:3.2rem}\n.able-pill{display:inline-block;font-size:.72rem;padding:.08rem .5rem;border-radius:999px;background:#EFEDE9;color:#55534E;border:1px solid #E2DFD9;white-space:nowrap}\n.able-pill.p{background:#E8EEF6;color:#3B5677;border-color:#D6E0EC}\n.able-pill.d{background:#E9F3EC;color:#3C6B4A;border-color:#D5E8DA}\n.able-due{color:var(--muted);font-size:.85rem;text-align:right;white-space:nowrap}\n.able-file{display:flex;align-items:center;gap:.7rem;font-size:.92rem}\n.able-file i{font-style:normal;display:inline-block;width:1.6rem;text-align:center;border:1px solid #CFCBC4;border-radius:4px;font-size:.7rem;color:#55534E;padding:.05rem 0}\n.able-meta{color:var(--muted);font-size:.84rem;white-space:nowrap}\n</style>', unsafe_allow_html=True)
MENU_ICONS = {'🏠 홈': ':material/home: 홈', '💬 채팅': ':material/chat_bubble: 채팅', '📁 자료실': ':material/folder: 자료실', '✅ 내 작업': ':material/check_box: 내 작업', '👥 팀 업무 현황': ':material/bar_chart: 팀 업무 현황', '📧 이메일 관리': ':material/mail: 이메일 관리', '⚙️ 설정': ':material/settings: 설정'}
WEEKDAYS = '월화수목금토일'

def due_label(d):
    n = (d - TODAY).days
    return {0: '오늘', 1: '내일', -1: '어제'}.get(n, f'{d.month}월 {d.day}일')

def status_pill(s):
    cls = {'진행 중': 'p', '완료': 'd'}.get(s, '')
    return f'<span class="able-pill {cls}">{html_lib.escape(s)}</span>'

def home_toggle(tid):
    t = next((x for x in ss.tasks if x['id'] == tid), None)
    if t:
        before = t['상태']
        t['상태'] = '완료' if ss[f'home_chk_{tid}'] else '진행 중'
        record_change(t, '상태', before, t['상태'])

def quick_add_task():
    title = ss.qt_title.strip()
    if not title:
        ss.notice = '⚠️ 업무명을 입력해 주세요.'
        return
    t = {'id': uuid.uuid4().hex[:8], '업무': title, '담당자': ss.qt_owner, '마감일': ss.qt_due, '상태': '대기', '우선순위': ss.qt_pr, '근거': f"{ss.settings['name']} 님이 홈에서 등록"}
    ss.tasks.append(t)
    record_change(t, '등록', '-', f"{t['담당자']}에게 배정")
    ss.qt_title = ''
    ss.notice = f"✅ '{title}' 업무를 추가했습니다."

def quick_add_event():
    title, start, dur = (ss.qe_title.strip(), ss.qe_time.strftime('%H:%M'), int(ss.qe_dur))
    if not title:
        ss.notice = '⚠️ 일정 제목을 입력해 주세요.'
        return
    clash = find_conflicts(ss.qe_day, start, dur)
    ss.schedule.append({'일자': ss.qe_day, '시간': start, '일정': title, '소요': dur})
    ss.qe_title = ''
    ss.notice = f"📅 '{title}' 일정을 추가했습니다." + (f" (겹치는 일정: {', '.join(clash)})" if clash else '')

def move_month(step):
    m = ss.get('home_month', TODAY.replace(day=1))
    y, mo = (m.year + (m.month - 1 + step) // 12, (m.month - 1 + step) % 12 + 1)
    ss.home_month = date(y, mo, 1)

def mini_calendar(month):
    days_with = {e['일자'] for e in ss.schedule}
    html_ = '<table class="able-mini"><tr>' + ''.join((f'<th>{d}</th>' for d in '일월화수목금토')) + '</tr>'
    for week in calendar_lib.Calendar(firstweekday=6).monthdatescalendar(month.year, month.month):
        html_ += '<tr>'
        for d in week:
            cls = ' '.join((c for c in ['out' if d.month != month.month else '', 'today' if d == TODAY else '', 'has' if d in days_with else ''] if c))
            html_ += f'<td class="{cls}"><span>{d.day}</span></td>'
        html_ += '</tr>'
    st.markdown(html_ + '</table>', unsafe_allow_html=True)

def file_badge(name):
    ext = name.rsplit('.', 1)[-1].lower()
    return {'docx': 'W', 'doc': 'W', 'xlsx': 'X', 'csv': 'X', 'tsv': 'X', 'pdf': 'PDF', 'pptx': 'P', 'png': 'IMG', 'jpg': 'IMG', 'jpeg': 'IMG', 'webp': 'IMG', 'mp3': '♪', 'wav': '♪', 'm4a': '♪'}.get(ext, 'T')
_v4_page_home = page_home

def page_home():
    s = ss.settings
    top_l, top_r = st.columns([3, 2], vertical_alignment='bottom')
    with top_l:
        st.markdown('<div class="able-title">오늘의 업무를 차분하게.</div>', unsafe_allow_html=True)
        st.markdown(f"""<div class="able-sub">{TODAY.month}월 {TODAY.day}일 {WEEKDAYS[TODAY.weekday()]}요일 · {html_lib.escape(s['name'])}님의 작업공간</div>""", unsafe_allow_html=True)
    with top_r:
        b1, b2 = st.columns(2)
        with b1.popover('＋ 새 업무', width='stretch'):
            st.text_input('업무명', key='qt_title', placeholder='예: 주간 보고서 작성')
            members = team_members()
            ss.setdefault('qt_owner', s['name'] if s['name'] in members else members[0])
            st.selectbox('담당자', members, key='qt_owner')
            st.date_input('마감일', TODAY + timedelta(days=1), key='qt_due')
            st.selectbox('우선순위', ['높음', '보통', '낮음'], index=1, key='qt_pr')
            st.button('추가', type='primary', on_click=quick_add_task, key='qt_add')
        with b2.popover(':material/calendar_month: 일정 추가', width='stretch'):
            st.text_input('일정 제목', key='qe_title', placeholder='예: 팀 회의')
            st.date_input('날짜', TODAY, key='qe_day')
            st.time_input('시작', datetime.strptime('10:00', '%H:%M').time(), key='qe_time', step=1800)
            st.number_input('소요 시간(분)', 15, 720, 60, 15, key='qe_dur')
            st.button('추가', type='primary', on_click=quick_add_event, key='qe_add')
    show_notice()
    left, right = st.columns([1.35, 1])
    with left, st.container(border=True):
        st.markdown('<div class="able-card-h">이번 주 일정</div>', unsafe_allow_html=True)
        cal, day = st.columns([1.15, 1])
        with cal:
            month = ss.get('home_month', TODAY.replace(day=1))
            p, m, n = st.columns([1, 4, 1], vertical_alignment='center')
            p.button('‹', key='m_prev', on_click=move_month, args=(-1,), type='tertiary')
            m.markdown(f"<div style='text-align:center;font-weight:600'>{month.year}년 {month.month}월</div>", unsafe_allow_html=True)
            n.button('›', key='m_next', on_click=move_month, args=(1,), type='tertiary')
            mini_calendar(month)
        with day:
            st.markdown(f'<div class="able-day-h">{TODAY.month}월 {TODAY.day}일 {WEEKDAYS[TODAY.weekday()]}요일</div>', unsafe_allow_html=True)
            todays = sorted([e for e in ss.schedule if e['일자'] == TODAY], key=lambda x: x['시간'])
            if todays:
                st.markdown(''.join((f"""<div class="able-row"><span class="t">{e['시간']}</span><span>{html_lib.escape(e['일정'])}</span></div>""" for e in todays)), unsafe_allow_html=True)
            else:
                st.caption('오늘 일정이 없습니다.')
    with right, st.container(border=True):
        st.markdown('<div class="able-card-h">우선 확인할 업무</div>', unsafe_allow_html=True)
        order = {'높음': 0, '보통': 1, '낮음': 2}
        mine = sorted([t for t in ss.tasks if t['담당자'] == s['name'] and t['상태'] not in ('완료', '취소')], key=lambda x: (_due_read(x), order.get(x['우선순위'], 1)))[:5]
        for t in mine:
            z, a, b, c = st.columns([0.5, 4.5, 1.6, 1.4])
            ss[f"home_chk_{t['id']}"] = False
            z.checkbox(t['업무'], key=f"home_chk_{t['id']}", on_change=home_toggle, args=(t['id'],), label_visibility='collapsed', help='체크하면 완료로 바뀝니다')
            a.markdown(f"""<div class="able-task">{html_lib.escape(t['업무'])}</div>""", unsafe_allow_html=True)
            b.markdown(status_pill(t['상태']), unsafe_allow_html=True)
            c.markdown(f'<div class="able-due">{due_label(_due_read(t))}</div>', unsafe_allow_html=True)
        if not mine:
            st.caption("확인할 업무가 없습니다. 오른쪽 위 '＋ 새 업무'로 추가해 보세요.")
    with st.container(border=True):
        st.markdown('<div class="able-card-h">최근 자료</div>', unsafe_allow_html=True)
        recent = sorted(ss.library, key=lambda f: f.get('created', ''), reverse=True)[:5]
        for f in recent:
            a, b, c = st.columns([6, 3, 0.7], vertical_alignment='center')
            a.markdown(f"""<div class="able-file"><i>{file_badge(f['name'])}</i>{html_lib.escape(f['name'])}</div>""", unsafe_allow_html=True)
            b.markdown(f"""<div class="able-meta">수정일 {f.get('created', '')}</div>""", unsafe_allow_html=True)
            with c.popover('⋯'):
                st.download_button('다운로드', f['data'], file_name=f['name'], key=f"rd_{f['id']}")
                st.button('대화에 활용', key=f"ru_{f['id']}", on_click=lib_attach, args=(f['id'],))
        if not recent:
            st.caption('아직 자료가 없습니다. 채팅이나 자료실에서 파일을 올리면 여기에 보입니다.')
    with st.expander('📊 전체 대시보드 · AI 브리핑 · 빠른 실행 · 월간 달력 · 일정 편집'):
        _h = st.header
        st.header = lambda *a, **k: None
        try:
            _v4_page_home()
        finally:
            st.header = _h

def parse_due(text_):
    text_ = str(text_).strip()
    for word, n in (('오늘', 0), ('내일', 1), ('모레', 2)):
        if word in text_:
            return TODAY + timedelta(days=n)
    m = re.search('(\\d{4})-(\\d{1,2})-(\\d{1,2})', text_) or None
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search('(\\d{1,2})\\s*[월/.]\\s*(\\d{1,2})', text_)
    if m:
        d = date(TODAY.year, int(m.group(1)), int(m.group(2)))
        return d if d >= TODAY - timedelta(days=30) else date(TODAY.year + 1, d.month, d.day)
    return UnknownDue()

def table_tasks(md):
    lines = [l.strip() for l in md.splitlines() if l.strip().startswith('|')]
    if len(lines) < 3:
        return []
    head = [c.strip() for c in lines[0].strip('|').split('|')]
    find = lambda *names: next((i for i, h in enumerate(head) if any((n in h for n in names))), None)
    ti, oi, di = (find('업무', '할 일', '작업'), find('담당'), find('기한', '마감', '날짜'))
    if ti is None:
        return []
    rows = []
    for l in lines[2:]:
        cells = [c.strip() for c in l.strip('|').split('|')]
        if ti < len(cells) and cells[ti]:
            rows.append({'title': cells[ti], 'owner': cells[oi] if oi is not None and oi < len(cells) and cells[oi] else ss.settings['name'], 'due': parse_due(cells[di]) if di is not None and di < len(cells) else None})
    return rows

def add_table_tasks(i):
    m = ss.messages[i]
    for r in table_tasks(m['content']):
        t = {'id': uuid.uuid4().hex[:8], '업무': r['title'], '담당자': r['owner'], '마감일': r['due'], '상태': '대기', '우선순위': '보통', '근거': '채팅 답변의 표에서 추가'}
        ss.tasks.append(t)
        record_change(t, '등록', '-', '채팅 답변에서 추가')
    m['tasks_added'] = True
_v22_render_more = render_more

def render_more(i, m):
    rows = table_tasks(m.get('content', ''))
    if rows:
        if m.get('tasks_added'):
            st.caption(f'✅ 업무 {len(rows)}건을 내 작업에 추가했습니다.')
        else:
            st.button(f'＋ 내 작업에 추가 ({len(rows)}건)', key=f'tbl_add_{i}', on_click=add_table_tasks, args=(i,))
    if m.get('files_ref'):
        st.caption('참고 자료 · ' + ', '.join(m['files_ref']))
    _v22_render_more(i, m)

def chat_model_changed():
    ss.settings['model'] = ss.chat_model
_v22_page_chat = page_chat
AVATARS = {'user': ':material/person:', 'assistant': ':material/auto_awesome:'}

def page_chat():
    title = next((x['content'][:30] for x in ss.messages if x['role'] == 'user'), '새 대화')
    a, b = st.columns([4, 1.3], vertical_alignment='bottom')
    a.markdown(f'<div class="able-title" style="font-size:1.6rem">{html_lib.escape(title)}</div>', unsafe_allow_html=True)
    ss.chat_model = ss.settings['model']
    b.selectbox('모델', list(MODEL_MAP), key='chat_model', on_change=chat_model_changed, label_visibility='collapsed')
    _h, _cm = (st.header, st.chat_message)
    st.header = lambda *a_, **k_: None
    st.chat_message = lambda role, **k_: _cm(role, avatar=AVATARS.get(role, k_.get('avatar')))
    try:
        _v22_page_chat()
    finally:
        st.header, st.chat_message = (_h, _cm)
IMAGE_RE = re.compile('(그림|이미지|일러스트|로고|포스터|사진|아이콘|캐릭터|배너|썸네일|삽화).{0,15}(만들|생성|그려|그리|제작|뽑아|디자인)|그려\\s*줘|그려\\s*주|draw|image of', re.I)
_v27_wants = WANTS_FILE_RE

class _FileOrImage:

    def search(self, text_):
        return IMAGE_RE.search(text_) or _v27_wants.search(text_)
WANTS_FILE_RE = _FileOrImage()

def gen_image(prompt):
    model = ss.settings.get('image_model') or 'gpt-image-1'
    try:
        r = client.images.generate(model=model, prompt=prompt, size='1024x1024', n=1)
    except Exception:
        if model == 'dall-e-3':
            raise
        r = client.images.generate(model='dall-e-3', prompt=prompt, size='1024x1024', n=1, response_format='b64_json')
    d = r.data[0]
    if getattr(d, 'b64_json', None):
        return base64.b64decode(d.b64_json)
    if getattr(d, 'url', None):
        return requests.get(d.url, timeout=60).content
    raise ValueError('이미지 생성 결과가 비어 있습니다.')
_v27_create_files = create_files

def create_files(prompt, answer_):
    if IMAGE_RE.search(prompt) and (not re.search('엑셀|xlsx|csv|pdf|ppt|docx|워드|mp3|보고서 파일', prompt, re.I)):
        try:
            data = gen_image(prompt)
            f = add_to_library(f'이미지_{datetime.now():%m%d_%H%M%S}_{uuid.uuid4().hex[:4]}.png', data, '생성')
            return ([f['id']], [])
        except Exception as e:
            return ([], ['이미지 생성 실패: ' + diagnostic(e, '이미지 생성')['message'] + ''])
    return _v27_create_files(prompt, answer_)
_v27_base_system = base_system

def base_system():
    return _v27_base_system() + "\n\n[이미지 요청 안내] 사용자가 그림·이미지·포스터 등을 만들어 달라고 하면, 앱이 이미지를 따로 만들어 답변 아래에 보여 준다. '그릴 수 없다'고 하지 말고, 어떤 이미지를 만들지 1~2문장으로 짧게 설명하라."
LUNA_ID = 'gpt-6-luna'
FALLBACK_MODEL = 'gpt-4o-mini'
_rest = {k: v for k, v in MODEL_MAP.items() if k != 'Luna 6'}
MODEL_MAP.clear()
MODEL_MAP.update({'Luna 6': LUNA_ID, 'GPT-4o mini': FALLBACK_MODEL})
MODEL_MAP.update({k: v for k, v in _rest.items() if k != 'GPT-4o mini'})
NO_PDF_MODELS = {LUNA_ID}

def _access_error(e):
    body = getattr(e, 'body', None)
    code = getattr(e, 'code', None) or (body.get('code') if isinstance(body, dict) else None)
    return getattr(e, 'status_code', None) in (403, 404) or code in ('model_not_found', 'permission_denied')

def _out_tokens(model):
    n = int(ss.settings.get('max_output', 4000))
    return max(n, 16000) if model == LUNA_ID else n

def _call(model, messages, fmt):
    kw = {'model': model, 'input': messages}
    if fmt:
        kw['text'] = {'format': {'type': 'json_object'}}
    return client.responses.create(**kw).output_text
NO_JSON_MODELS = set()
NO_ACCESS_MODELS = set()

def _usable(model):
    if model in NO_ACCESS_MODELS:
        ss.model_note = f'⚠️ 이 API 키로는 {model} 모델을 쓸 수 없어 {FALLBACK_MODEL}로 대신 답했습니다.'
        return FALLBACK_MODEL
    return model

def llm(messages, json_mode=False):
    model = _usable(model_id())
    use_fmt = json_mode and model not in LEGACY_MODELS and (model not in NO_JSON_MODELS)
    try:
        return _call(model, messages, use_fmt)
    except Exception as e:
        if _access_error(e) and model != FALLBACK_MODEL:
            NO_ACCESS_MODELS.add(model)
            ss.model_note = f'⚠️ 이 API 키로는 {model} 모델을 쓸 수 없어 {FALLBACK_MODEL}로 대신 답했습니다.'
            return _call(FALLBACK_MODEL, messages, json_mode)
        if use_fmt:
            NO_JSON_MODELS.add(model)
            return _call(model, messages, False)
        raise

def _stream(model, messages, with_reasoning):
    kw = {'model': model, 'input': messages, 'stream': True, 'max_output_tokens': _out_tokens(model)}
    if with_reasoning and ss.settings.get('reasoning', '자동') != '자동':
        kw['reasoning'] = {'effort': ss.settings['reasoning']}
    for event in client.responses.create(**kw):
        if event.type in ('response.output_text.delta', 'response.refusal.delta'):
            yield event.delta
        elif event.type in ('response.failed', 'response.incomplete'):
            raise ValueError('응답이 완료되지 않았습니다. 질문을 나눠서 다시 요청해 보세요.')

def stream_llm(messages):
    model = _usable(model_id())
    try:
        yield from _stream(model, messages, model != FALLBACK_MODEL or model_id() == FALLBACK_MODEL)
    except Exception as e:
        if _access_error(e) and model != FALLBACK_MODEL:
            NO_ACCESS_MODELS.add(model)
            ss.model_note = f'⚠️ 이 API 키로는 {model} 모델을 쓸 수 없어 {FALLBACK_MODEL}로 대신 답했습니다.'
            try:
                yield from _stream(FALLBACK_MODEL, messages, False)
                return
            except Exception as e2:
                e = e2
        ss.last_error = diagnostic(e, '답변 생성')
        raise
_v29_file_parts = file_parts

def file_parts(f, vision=True):
    if model_id() in NO_PDF_MODELS and f['name'].lower().endswith('.pdf'):
        if f['text']:
            return [{'type': 'input_text', 'text': f"[첨부: {f['name']}]\n" + f['text'][:15000]}]
        return [{'type': 'input_text', 'text': f"[첨부: {f['name']}] (글자를 읽을 수 없는 PDF입니다. 스캔본이면 이미지로 첨부해 주세요)"}]
    return _v29_file_parts(f, vision)
_v29_render_more = render_more

def render_more(i, m):
    if ss.get('model_note') and i == len(ss.messages) - 1 and (m.get('role') == 'assistant'):
        m['model_note'] = ss.pop('model_note')
    if m.get('model_note'):
        st.caption(m['model_note'])
    _v29_render_more(i, m)
_seen_models = {}
for _name in list(MODEL_MAP):
    _mid = MODEL_MAP[_name]
    if _mid and _mid in _seen_models:
        del MODEL_MAP[_name]
        if ss.settings.get('model') == _name:
            ss.settings['model'] = _seen_models[_mid]
    elif _mid:
        _seen_models[_mid] = _name
if ss.settings.get('model') not in MODEL_MAP:
    ss.settings['model'] = 'Luna 6'
ALL_TEAM_RE = re.compile('팀원\\s*(전체|모두|전원|다)|(전체|모든)\\s*팀원|팀\\s*전체|팀원들|모두에게|전원에게')

def team_directory():
    d = {c['이름']: {'이름': c['이름'], '이메일': c['이메일'], '직책': c.get('직책', '')} for c in ss.contacts}
    for u in ss.get('users', []):
        if u.get('email') and EMAIL_RE.fullmatch(u['email']):
            d[u['name']] = {'이름': u['name'], '이메일': u['email'], '직책': u.get('role', '')}
    return list(d.values())
_v31_find_contact = find_contact

def find_contact(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    key = re.sub('\\s|님|에게|한테|께', '', raw)
    directory = team_directory()
    for p in directory:
        if raw.lower() == p['이메일'].lower() or key == p['이름'].replace(' ', ''):
            return p
    for p in directory:
        name = p['이름'].replace(' ', '')
        if key and name and (name in key or key in name):
            return p
    return _v31_find_contact(raw)

def contacts_text():
    return '\n'.join((f"- {p['이름']} ({p['직책']}) <{p['이메일']}>" for p in team_directory())) or '- 없음'
ROUTER_PROMPT = ROUTER_PROMPT + '\n받는 사람이 여러 명이면 to에 이름을 쉼표로 나열하라(예: "최 팀장, 이 과장").\n팀원 전체·모두에게 보내라는 요청이면 to는 "팀원 전체"로 하라.'

def resolve_recipients(raw):
    if ALL_TEAM_RE.search(raw):
        me = ss.settings['name']
        team = {u['name'] for u in ss.get('users', [])} | {t['담당자'] for t in ss.tasks}
        return ([p for p in team_directory() if p['이름'] in team and p['이름'] != me], [])
    found, missing, seen = ([], [], set())
    for part in re.split('\\s*(?:,|，|/|;|및|그리고|이랑|하고|랑|와\\s|과\\s)\\s*', raw):
        part = part.strip()
        if not part:
            continue
        p = find_contact(part)
        if not p and EMAIL_RE.fullmatch(part):
            p = {'이름': part, '이메일': part}
        if p and p['이메일'].lower() not in seen:
            seen.add(p['이메일'].lower())
            found.append(p)
        elif not p:
            missing.append(part)
    return (found, missing)

def _send_many(recipients, subject, body):
    ok, fail = ([], [])
    for addr, name in recipients:
        try:
            deliver(addr, subject, body, name)
            ok.append(name or addr)
        except Exception as e:
            fail.append(f'{name or addr}: {e}')
    return (ok, fail)
_v31_tool_email = tool_email

def tool_email(a):
    raw = str(a.get('to') or '')
    found, missing = resolve_recipients(raw)
    if len(found) <= 1 and (not missing) and (not ALL_TEAM_RE.search(raw)):
        return _v31_tool_email(a)
    if not found:
        return (f"'{raw or '받는 사람'}'의 이메일 주소를 팀원 목록·연락처에서 찾지 못해 보내지 않았다. '팀 업무 현황 > 팀원 이메일 목록'에 이메일을 등록하라고 안내하라.", None)
    draft = {'to': ', '.join((p['이메일'] for p in found)), 'name': ', '.join((p['이름'] for p in found)), 'subject': a.get('subject') or '(제목 없음)', 'body': a.get('body') or '', 'recipients': [(p['이메일'], p['이름']) for p in found]}
    ss['_draft'] = draft
    miss = f" 이메일이 없어 빠진 사람: {', '.join(missing)}." if missing else ''
    if ss.settings.get('auto_send', True) and (not a.get('_draft_only')):
        ok, fail = _send_many(draft['recipients'], draft['subject'], draft['body'])
        draft['sent'] = f'{len(ok)}명에게 발송 완료 · {datetime.now():%Y-%m-%d %H:%M}'
        if fail:
            draft['error'] = '; '.join(fail)
        rows = [{'이름': p['이름'], '이메일': p['이메일'], '결과': '발송' if p['이름'] in ok else '실패'} for p in found]
        return (f"이메일 발송 완료 → {', '.join(ok)} ({len(ok)}명).{miss}" + (f" 실패: {'; '.join(fail)}." if fail else '') + ' 짧게 보고하라. 본문은 다시 쓰지 마라.', rows)
    return (f"이메일 초안 작성 완료 → 받는 사람 {len(found)}명: {draft['name']}.{miss} 아직 발송 전이며, 사용자가 '보내줘'라고 답하거나 '📤 이 메일 보내기' 버튼을 누르면 발송된다. 짧게 안내하라.", None)
TOOLS['email'] = ('📧 이메일 도구', tool_email)
_v31_send_draft = send_draft

def send_draft(i):
    d = ss.messages[i]['draft']
    if not d.get('recipients'):
        return _v31_send_draft(i)
    ok, fail = _send_many(d['recipients'], d['subject'], d['body'])
    d['sent'] = f'{len(ok)}명에게 발송 완료 · {datetime.now():%Y-%m-%d %H:%M}'
    d.pop('error', None)
    if fail:
        d['error'] = '; '.join(fail)
_v31_send_mail = send_mail

def send_mail():
    raw = ss.mail_to.strip()
    if not (',' in raw or ALL_TEAM_RE.search(raw)):
        return _v31_send_mail()
    found, missing = resolve_recipients(raw)
    if not found or not ss.mail_subject.strip():
        ss.notice = '⚠️ 받는 사람(팀원 이름·이메일)과 제목을 확인해 주세요.'
        return
    ok, fail = _send_many([(p['이메일'], p['이름']) for p in found], ss.mail_subject, ss.mail_body)
    ss.mail_to = ss.mail_subject = ss.mail_body = ''
    ss.notice = f"📤 {len(ok)}명에게 메일을 보냈습니다: {', '.join(ok)}" + (f" · 실패: {'; '.join(fail)}" if fail else '') + (f" · 이메일이 없어 빠진 사람: {', '.join(missing)}" if missing else '')
    if fail:
        ss.notice = '⚠️ ' + ss.notice

def save_member_email():
    name = ss.tm_name if ss.tm_name != '✏️ 직접 입력' else ss.tm_name_new.strip()
    email = ss.tm_email.strip()
    if not name or not EMAIL_RE.fullmatch(email):
        ss.notice = '⚠️ 팀원 이름과 올바른 이메일 주소를 입력해 주세요.'
        return
    upsert_contact(name, email, ss.tm_role.strip())
    ss.tm_email = ss.tm_role = ss.tm_name_new = ''
    ss.notice = f'📇 {name} 님의 이메일을 팀원 목록에 저장했습니다.'
_v31_page_team = page_team

def page_team():
    _v31_page_team()
    st.divider()
    with st.expander(f"📇 팀원 이메일 목록 ({len(team_directory())}명) · 채팅에서 '이름에게 메일 보내줘'로 발송", expanded=False):
        directory = team_directory()
        if directory:
            st.dataframe(pd.DataFrame(directory), hide_index=True, width='stretch')
        no_mail = [m for m in team_members() if m not in {p['이름'] for p in directory}]
        if no_mail:
            st.caption('이메일이 없는 팀원: ' + ', '.join(no_mail) + ' → 아래에서 등록하면 채팅으로 메일을 보낼 수 있습니다.')
        a, b = st.columns(2)
        a.selectbox('팀원', (no_mail or []) + [p['이름'] for p in directory] + ['✏️ 직접 입력'], key='tm_name')
        if ss.get('tm_name') == '✏️ 직접 입력':
            b.text_input('이름', key='tm_name_new')
        c, d = st.columns(2)
        c.text_input('이메일', key='tm_email', placeholder='예: lee@company.com')
        d.text_input('직책', key='tm_role', placeholder='예: 과장')
        st.button('📇 이메일 저장', on_click=save_member_email)
        st.caption("채팅 예시: '이 과장에게 회의 변경 메일 보내줘' · '최 팀장이랑 이 과장에게 보고 메일 보내줘' · '팀원 전체에게 공지 메일 보내줘'")

def delete_task_now(tid):
    t = next((x for x in ss.tasks if x['id'] == tid), None)
    if t:
        record_change(t, '삭제', t['업무'], '삭제됨')
        ss.tasks = [x for x in ss.tasks if x['id'] != tid]
        for k in [f'chk_{tid}', f'home_chk_{tid}']:
            ss.pop(k, None)
SUMMARY_PROMPT = "다음 자료를 한국어로 요약하라. 형식: 첫 줄에 '한 줄 요약: ...', 이어서 핵심 내용 3~5개를 '- '로 시작하는 짧은 문장으로. 담당자·기한·금액·수치가 있으면 반드시 포함하고, 자료에 없는 내용은 만들지 마라."

def summarize_file(f):
    ext = f['name'].rsplit('.', 1)[-1].lower()
    if ext in IMG_MIME:
        b64 = base64.b64encode(f['data']).decode()
        content = [{'type': 'input_text', 'text': '이 이미지의 내용을 요약해줘.'}, {'type': 'input_image', 'image_url': f'data:{IMG_MIME[ext]};base64,{b64}'}]
    else:
        content = f"[자료: {f['name']}]\n{f['text'][:20000]}"
    return llm([{'role': 'system', 'content': SUMMARY_PROMPT}, {'role': 'user', 'content': content}])

def clear_summary(fid):
    for x in ss.library:
        if x['id'] == fid:
            x.pop('summary', None)

def render_summary(f):
    ext = f['name'].rsplit('.', 1)[-1].lower()
    with st.container(border=True):
        st.markdown('**📝 AI 요약**')
        if not f.get('summary'):
            if not (f.get('text') or ext in IMG_MIME):
                st.caption('글자를 읽을 수 없는 자료라 요약할 수 없습니다.')
                return
            with st.spinner('자료를 요약하고 있습니다...'):
                try:
                    f['summary'] = summarize_file(f)
                except Exception as e:
                    st.caption('요약 실패: ' + diagnostic(e, '자료 요약')['message'])
                    return
        st.markdown(f['summary'])
        st.button('🔄 다시 요약', key=f"resum_{f['id']}", on_click=clear_summary, args=(f['id'],), type='tertiary')
INTENT_LABEL['task_edit'] = '✏️ 업무 편집'
EDIT_FIELDS = ['업무', '담당자', '마감일', '상태', '우선순위', '진행률', '상세', '기한 설명', '중간 점검', '결과물', '선행 조건']
ROUTER_PROMPT = ROUTER_PROMPT.replace('intent는 chat | email | calendar | task | translate 중 하나.', 'intent는 chat | email | calendar | task | task_edit | translate 중 하나.') + '\n- task_edit: 이미 있는 업무를 고치거나 지우는 요청(예: "보고서 업무 마감 금요일로 바꿔줘", "광고 업무 완료로 해줘", "회의록 정리 업무 삭제해줘").\n  args: {"target": [업무 목록]에 있는 업무명 그대로, "changes": {바꿀 항목만: "업무"(새 업무명), "담당자", "마감일"("YYYY-MM-DD"),\n  "상태"("대기|진행 중|완료"), "우선순위"("높음|보통|낮음"), "진행률"(완료율 0~100 숫자, 예: "60% 했어"→60), "상세", "중간 점검", "결과물"}, "delete": 지우라는 요청이면 true}\n  새 업무를 만드는 요청이면 task_edit이 아니라 task다.'

def tasks_text():
    me = ss.settings['name']
    mine = [t for t in ss.tasks if t['담당자'] == me] + [t for t in ss.tasks if t['담당자'] != me]
    return '\n'.join((f"- {t['업무']} (담당 {t['담당자']}, 마감 {_due_read(t)}, {t['상태']}, {t['우선순위']})" for t in mine[:60])) or '- 없음'
_v35_route = route

def route(prompt):
    r = _v35_route(f'[업무 목록]\n{tasks_text()}\n\n{prompt}')
    if r['intent'] in ('chat', 'task') and (not r['args'].get('title')) and re.search('(업무|작업|할 ?일).*(수정|변경|바꿔|바꾸|고쳐|편집|삭제|지워|완료로|미뤄|당겨)', prompt):
        r = {'intent': 'task_edit', 'args': r['args']}
    return r

def find_tasks(name):
    key = re.sub('\\s+', '', str(name or '')).lower()
    if not key:
        return []
    norm = lambda t: re.sub('\\s+', '', t['업무']).lower()
    exact = [t for t in ss.tasks if norm(t) == key]
    hits = exact or [t for t in ss.tasks if key in norm(t) or norm(t) in key]
    me = ss.settings['name']
    mine = [t for t in hits if t['담당자'] == me]
    return mine if len(hits) > 1 and len(mine) == 1 else hits

def tool_task_edit(a):
    hits = find_tasks(a.get('target'))
    if not hits:
        return (f"'{a.get('target') or '업무'}'와 맞는 업무를 내 작업에서 찾지 못했다. 업무 이름을 다시 알려 달라고 안내하라.", None)
    if len(hits) > 1:
        rows = [{'업무': t['업무'], '담당자': t['담당자'], '마감일': _due_read(t), '상태': t['상태']} for t in hits]
        return ('이름이 비슷한 업무가 여러 개라 고치지 않았다. 아래 표에서 어느 업무인지 정확한 이름을 물어보라.', rows)
    t = hits[0]
    if a.get('delete'):
        delete_task_now(t['id'])
        return (f"업무 삭제 완료: {t['업무']} (담당 {t['담당자']}). 짧게 보고하라.", None)
    done = []
    for field, value in (a.get('changes') or {}).items():
        if field not in EDIT_FIELDS or value in (None, ''):
            continue
        if field == '마감일':
            value = to_date(value)
        elif field == '상태' and value not in STATUS_LIST:
            continue
        elif field == '우선순위' and value not in ('높음', '보통', '낮음'):
            continue
        elif field == '진행률':
            m = re.search('\\d+', str(value))
            if not m:
                continue
            value = max(0, min(100, int(m.group())))
        before = t.get(field, '')
        if before != value:
            record_change(t, field, before, value)
            t[field] = value
            done.append(f"{field}: {before or '없음'} → {value}")
    if '진행률' in (a.get('changes') or {}) and t['상태'] != '완료':
        new = '완료' if t.get('진행률') == 100 else '진행 중'
        if t['상태'] != new:
            record_change(t, '상태', t['상태'], new)
            t['상태'] = new
            done.append(f'상태: → {new}')
    for k in [f"chk_{t['id']}", f"home_chk_{t['id']}"]:
        ss.pop(k, None)
    if not done:
        return (f"'{t['업무']}' 업무에서 바꿀 내용을 알아듣지 못했다. 무엇을 바꿀지 물어보라.", None)
    row = {k: t.get(k, '') for k in ['업무', '담당자', '마감일', '상태', '우선순위']}
    row['완료율'] = f'{task_pct(t)}%'
    return (f"업무 수정 완료 ({t['업무']}): " + '; '.join(done) + ". '내 작업'과 '팀 업무 현황'에 바로 반영되었다. 바뀐 내용을 짧게 보고하라.", [row])
TOOLS['task_edit'] = ('✏️ 업무 편집 도구', tool_task_edit)
_v36_attach_panel = attach_panel
_v36_page_chat = page_chat

def attach_panel():
    files, rec = _v36_attach_panel()
    ss['_drop_box'] = files
    return (files, rec)

def page_chat():
    _ci = st.chat_input

    def chat_input_drop(placeholder, **kw):
        kw.setdefault('accept_file', 'multiple')
        kw.setdefault('file_type', CHAT_TYPES)
        kw.setdefault('key', 'chat_box')
        if ss.get('_mic_text'):
            ss['chat_box'] = ss.pop('_mic_text')
        sub = _ci('메시지를 입력하거나 파일을 끌어다 놓으세요...', **kw)
        dropped = list(getattr(sub, 'files', None) or []) if sub is not None and (not isinstance(sub, str)) else []
        mic = getattr(sub, 'audio', None) if sub is not None and (not isinstance(sub, str)) else None
        if mic is not None and (not (sub.text or '').strip()) and (not dropped):
            try:
                with st.spinner('말씀하신 내용을 글자로 바꾸는 중...'):
                    ss['_mic_text'] = stt(mic.getvalue())
                ss.last_audio = hashlib.md5(mic.getvalue()).hexdigest()
            except Exception as e:
                st.toast('음성 인식 실패: ' + diagnostic(e, '음성 인식')['message'])
                return None
            st.rerun()
        if dropped:
            ss.setdefault('_drop_box', []).extend(dropped)
        return sub
    _ai = st.audio_input

    def audio_to_box(label, **kw):
        rec = _ai(label, **kw)
        if rec is not None:
            h = hashlib.md5(rec.getvalue()).hexdigest()
            if h != ss.last_audio:
                ss.last_audio = h
                try:
                    with st.spinner('말씀하신 내용을 글자로 바꾸는 중...'):
                        ss['_mic_text'] = stt(rec.getvalue())
                except Exception as e:
                    st.toast('음성 인식 실패: ' + diagnostic(e, '음성 인식')['message'])
                    return None
                st.rerun()
        return None
    st.chat_input, st.audio_input = (chat_input_drop, audio_to_box)
    try:
        _v36_page_chat()
    finally:
        st.chat_input, st.audio_input = (_ci, _ai)
MODEL_MAP.pop('✏️ 직접 입력', None)
if ss.settings.get('model') not in MODEL_MAP:
    ss.settings['model'] = next(iter(MODEL_MAP))
for _t in ss.tasks:
    if _t.get('상태') == '취소':
        _t['상태'] = '대기'

def blocks_done(t):
    return t.get('상태') == '진행 중' and int(t.get('진행률', 0)) < 100

def status_options(t):
    return [s for s in STATUS_LIST if not (s == '완료' and blocks_done(t))]

def _keep_in_progress(t, before):
    if before == '진행 중' and t['상태'] == '완료' and (int(t.get('진행률', 0)) < 100):
        t['상태'] = '진행 중'
        for i in range(len(ss.changes) - 1, -1, -1):
            c = ss.changes[i]
            if c['업무'] == t['업무'] and c['항목'] == '상태' and (c['이후'] == '완료'):
                del ss.changes[i]
                break
        for k in [f"chk_{t['id']}", f"home_chk_{t['id']}"]:
            ss.pop(k, None)
        st.toast(f"'{t['업무']}'은(는) 완료율이 {int(t.get('진행률', 0))}%라 진행 중으로 둡니다. 100%가 되면 완료로 넘어갑니다.")
        return True
    return False

def _guard(fn):

    def wrapped(tid, *a):
        t = next((x for x in ss.tasks if x['id'] == tid), None)
        before = t['상태'] if t else None
        fn(tid, *a)
        if t:
            _keep_in_progress(t, before)
    return wrapped
toggle_task = _guard(toggle_task)
home_toggle = _guard(home_toggle)
board_set = _guard(board_set)
_v40_tool_task_edit = tool_task_edit

def tool_task_edit(a):
    hits = find_tasks(a.get('target'))
    t = hits[0] if len(hits) == 1 else None
    before = t['상태'] if t else None
    result, rows = _v40_tool_task_edit(a)
    if t and _keep_in_progress(t, before):
        result += f" 단, 완료율이 {int(t.get('진행률', 0))}%라 상태는 진행 중으로 유지했다. 완료율을 100%로 하면 완료로 넘어간다고 안내하라."
        if rows:
            rows[0]['상태'] = t['상태']
    return (result, rows)
TOOLS['task_edit'] = ('✏️ 업무 편집 도구', tool_task_edit)
SAMPLE_TASK_IDS = {f't{i}' for i in range(1, 9)}
SAMPLE_EMAILS = {'choi@company.com', 'lee@company.com', 'park@company.com', 'jung@agency.com'}
SAMPLE_EVENTS = {('09:30', '주간 마케팅 회의'), ('11:00', '광고대행사 미팅'), ('14:00', '캠페인 데이터 리뷰'), ('16:30', '팀장님 주간 보고'), ('10:00', '신제품 기획 회의')}

def purge_samples():
    ss.tasks = [t for t in ss.tasks if t.get('id') not in SAMPLE_TASK_IDS]
    ss.contacts = [c for c in ss.contacts if c.get('이메일', '').lower() not in SAMPLE_EMAILS]
    ss.schedule = [e for e in ss.schedule if (e.get('시간'), e.get('일정')) not in SAMPLE_EVENTS]
    ss.inbox = [m for m in ss.get('inbox', []) if m.get('id') not in ('m1', 'm2', 'm3')]
RESET_KEYS = {'tasks': [], 'schedule': [], 'library': [], 'candidates': [], 'changes': [], 'mail_drafts': [], 'contacts': [], 'sent': [], 'inbox': [], 'messages': [], 'conversations': [], 'attach_ids': [], 'suggestions': []}

def reset_workspace():
    if not ss.get('reset_ok'):
        ss.notice = "⚠️ '모든 데이터를 지우는 것에 동의합니다'를 먼저 체크해 주세요."
        return
    with_accounts = ss.get('reset_accounts', False)
    try:
        con = ws_db()
        if with_accounts:
            con.execute('DELETE FROM able_final_demo_state')
        else:
            con.execute('DELETE FROM able_final_demo_state WHERE k <> ? AND k NOT LIKE ?', ('users', 'settings::%'))
        con.commit()
        con.close()
    except Exception as e:
        ss.notice = f'⚠️ 초기화 실패: {e}'
        return
    for k, v in RESET_KEYS.items():
        ss[k] = list(v)
    ss.conv_id = uuid.uuid4().hex
    ss['_ws_last'] = {}
    ss.reset_ok = False
    if with_accounts:
        ss.users = []
        log_out()
        ss.login_msg = '🧹 작업공간과 계정을 모두 지웠습니다. 회원가입부터 다시 시작하세요.'
    else:
        ss.notice = '🧹 작업공간을 초기화했습니다. 업무·일정·자료·연락처·메일·대화가 모두 비었습니다.'
_v41_page_settings = page_settings

def page_settings():
    _v41_page_settings()
    with st.expander('🧹 작업공간 초기화 (시연 준비)'):
        st.caption("팀 전체의 업무·일정·자료실·연락처·보낸 메일·초안·변경 기록·대화를 모두 지웁니다. 되돌릴 수 없으니 필요하면 위의 '백업 ZIP 다운로드'를 먼저 받아 두세요.")
        st.checkbox('로그인 계정도 모두 지우기', key='reset_accounts')
        st.checkbox('모든 데이터를 지우는 것에 동의합니다', key='reset_ok')
        st.button('🧹 지금 초기화', on_click=reset_workspace, type='primary')
ss.settings['stt_lang'] = 'ko'

def stt(audio_bytes):
    r = client.audio.transcriptions.create(model='whisper-1', file=('audio.wav', audio_bytes, 'audio/wav'), language='ko', prompt='다음은 한국어로 말한 업무 요청입니다.')
    return r.text

def clear_in_progress():
    gone = [t for t in ss.tasks if t['상태'] == '진행 중']
    for t in gone:
        record_change(t, '삭제', t['업무'], '삭제됨')
        for k in [f"chk_{t['id']}", f"home_chk_{t['id']}"]:
            ss.pop(k, None)
    ss.tasks = [t for t in ss.tasks if t['상태'] != '진행 중']
    ss.notice = f'🧹 진행 중인 업무 {len(gone)}건을 비웠습니다.'
_v43_page_team = page_team

def page_team():
    _v43_page_team()
    n = sum((t['상태'] == '진행 중' for t in ss.tasks))
    with st.expander(f'🧹 진행 중인 업무 모두 비우기 ({n}건)'):
        st.caption("팀 전체에서 상태가 '진행 중'인 업무를 모두 지웁니다. 대기·완료 업무는 그대로 둡니다.")
        st.button('🧹 진행 중 업무 비우기', on_click=clear_in_progress, disabled=n == 0, key='clear_prog')
TASK_PULL_RE = re.compile('(업무|할 ?일|작업|액션 ?아이템).{0,15}(뽑|추출|찾아|정리|추가|등록|넣어|반영)|담당자별')
ROUTER_PROMPT = ROUTER_PROMPT + '\n- 자료·회의록에서 업무를 뽑아 추가/정리해 달라는 요청(예: "회의록에서 업무 뽑아서 내 작업에 추가해줘")은 task가 아니라 chat이다.'

def add_tasks_from_docs(prompt, files):
    before = len(ss.candidates)
    n = extract_candidates(prompt, files)
    if not n:
        if not ([f for f in files if f.get('text')] or [f for f in ss.library if f['rag'] and f['text']]):
            return '업무를 뽑을 자료가 없습니다. 회의록을 첨부하거나 자료실에 올린 뒤 다시 요청해 주세요.'
        return '자료에서 담당자가 정해진 업무를 찾지 못했습니다.'
    new = ss.candidates[before:]
    have = {(re.sub('\\s+', '', t['업무']), t['담당자']) for t in ss.tasks}
    me, mine, others, skipped = (ss.settings['name'], [], [], 0)
    for c in new:
        key = (re.sub('\\s+', '', c['title']), c.get('owner') or me)
        if key in have:
            skipped += 1
            ss.candidates = [x for x in ss.candidates if x['id'] != c['id']]
            continue
        have.add(key)
        accept_candidate(c['id'])
        t = ss.tasks[-1]
        ss.changes[-1]['이후'] = f"채팅에서 바로 추가 (근거: {c.get('source', '')})"
        (mine if t['담당자'] == me else others).append(t)
    if not (mine or others):
        return f'새로 추가할 업무가 없습니다. 자료의 업무 {skipped}건은 이미 등록되어 있습니다.'
    msg = f'✅ 업무 {len(mine) + len(others)}건을 바로 추가했습니다'
    if mine:
        msg += f' · 내 작업 {len(mine)}건: ' + ', '.join((t['업무'] for t in mine[:5]))
    if others:
        msg += f' · 다른 팀원 {len(others)}건(팀 업무 현황에서 확인): ' + ', '.join((f"{t['담당자']}-{t['업무']}" for t in others[:5]))
    if skipped:
        msg += f' · 이미 있는 업무 {skipped}건은 건너뜀'
    return msg
ss.candidates = []
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
MAX_ATTACH = 15 * 1024 * 1024
ROUTER_PROMPT = ROUTER_PROMPT + '\n- email에서 자료실 파일을 첨부해 달라고 하면(예: "보고서.pdf 첨부해서 보내줘", "그 파일 같이 보내줘")\n  args에 "attach": [자료실 파일 목록]에 있는 파일명 그대로 를 넣어라. 첨부 요청이 없으면 넣지 마라.'
_v38_send_email = send_email

def send_email(to, subject, body):
    files = ss.get('_mail_files') or []
    if not files:
        return _v38_send_email(to, subject, body)
    sender, password, _, _ = smtp_conf()
    sender = sender or os.getenv('GMAIL_ADDRESS', '')
    password = (password or os.getenv('GMAIL_APP_PASSWORD', '')).replace(' ', '')
    if not sender or not password:
        return {'status': 'skipped', 'error': 'Gmail 계정 정보(GMAIL_ADDRESS·GMAIL_APP_PASSWORD)가 없습니다.'}
    msg = MIMEMultipart()
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = sender
    msg['To'] = to
    msg.attach(MIMEText(body, _charset='utf-8'))
    for f in files:
        major, minor = (mimetypes.guess_type(f['name'])[0] or 'application/octet-stream').split('/', 1)
        part = MIMEApplication(f['data'], _subtype=minor)
        part.add_header('Content-Disposition', 'attachment', filename=('utf-8', '', f['name']))
        msg.attach(part)
    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as s:
            s.starttls()
            s.login(sender, password)
            s.sendmail(sender, [to], msg.as_string())
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'failed', 'error': str(e)}
_v38_deliver = deliver

def deliver(to_addr, subject, body, name=None):
    rec = _v38_deliver(to_addr, subject, body, name)
    files = ss.get('_mail_files') or []
    if files:
        rec['방식'] += f' · 첨부 {len(files)}개'
    return rec

def files_by_ids(ids):
    return [f for f in ss.library if f['id'] in (ids or [])]

def mail_files_for(a):
    files = list(ss.get('_turn_files') or [])
    names = a.get('attach') or []
    if isinstance(names, str):
        names = [names]
    for n in names:
        key = re.sub('\\s+', '', str(n)).lower()
        hit = next((f for f in ss.library if re.sub('\\s+', '', f['name']).lower() == key), None) or next((f for f in ss.library if key and key in re.sub('\\s+', '', f['name']).lower()), None)
        if hit and hit not in files:
            files.append(hit)
    return files
_v38_route = route

def route(prompt):
    lib = '\n'.join((f"- {f['name']}" for f in ss.library[-40:])) or '- 없음'
    return _v38_route(f'[자료실 파일 목록]\n{lib}\n\n{prompt}')
_v38_handle_turn = handle_turn

def handle_turn(prompt, files):
    ss['_turn_files'] = list(files)
    try:
        return _v38_handle_turn(prompt, files)
    finally:
        ss.pop('_turn_files', None)
_v38_tool_email = tool_email

def tool_email(a):
    files = mail_files_for(a)
    if sum((f['size'] for f in files)) > MAX_ATTACH:
        return ('첨부파일 합계가 15MB를 넘어 보내지 않았다. 파일을 줄여 달라고 안내하라.', None)
    ss['_mail_files'] = files
    try:
        result, rows = _v38_tool_email(a)
    finally:
        ss.pop('_mail_files', None)
    d = ss.get('_draft')
    if files and d is not None:
        d['attach'] = [f['id'] for f in files]
        result += f" 첨부파일 {len(files)}개: {', '.join((f['name'] for f in files))}."
    return (result, rows)
TOOLS['email'] = ('📧 이메일 도구', tool_email)
_v38_send_draft = send_draft

def send_draft(i):
    ss['_mail_files'] = files_by_ids(ss.messages[i]['draft'].get('attach'))
    try:
        _v38_send_draft(i)
    finally:
        ss.pop('_mail_files', None)
_v38_render_draft = render_draft

def render_draft(i, d):
    _v38_render_draft(i, d)
    names = [f['name'] for f in files_by_ids(d.get('attach'))]
    if names:
        st.caption('📎 첨부파일: ' + ', '.join(names))
_v38_send_with_files = send_with_files

def send_with_files():
    raw = ss.mail_to.strip()
    if not (',' in raw or ALL_TEAM_RE.search(raw)):
        return _v38_send_with_files()
    files = files_by_ids(ss.get('mail_attach'))
    if sum((f['size'] for f in files)) > MAX_ATTACH:
        ss.notice = '⚠️ 첨부파일 합계는 15MB 이하만 보낼 수 있습니다.'
        return
    ss['_mail_files'] = files
    try:
        send_mail()
    finally:
        ss.pop('_mail_files', None)
    if files and (not ss.notice.startswith('⚠️')):
        ss.mail_attach = []
        ss.notice += f' · 첨부 {len(files)}개'
from demo_support import install_demo_support
install_demo_support(globals())
ss.sb_model = ss.settings['model']

def change_team():
    ss.settings['team'] = ss.sb_team
with st.sidebar:
    st.markdown('<div class="able-logo"><b>A</b> 에이블 Able</div>', unsafe_allow_html=True)
    teams = sorted({u.get('team') for u in ss.get('users', []) if u.get('team')} | {ss.settings['team']})
    ss.sb_team = ss.settings['team']
    st.selectbox('팀', teams, key='sb_team', on_change=change_team, label_visibility='collapsed')
    st.button('＋ 새 대화', on_click=new_chat, width='stretch')
    st.radio('메뉴', MENUS, key='menu', label_visibility='collapsed', format_func=lambda x: MENU_ICONS.get(x, x))
    st.markdown('<div class="able-side-h">최근 대화</div>', unsafe_allow_html=True)
    for c in ss.conversations[::-1][:8]:
        a, b = st.columns([6, 1], gap=None)
        a.button(f":material/chat_bubble_outline: {c['title']}", key=f"conv_{c['id']}", on_click=open_conv, args=(c['id'],), type='tertiary')
        b.button('✕', key=f"convdel_{c['id']}", on_click=delete_conv, args=(c['id'],), type='tertiary', help='대화 삭제')
    if not ss.conversations:
        st.caption('새 대화를 누르면 지금 대화가 여기에 저장됩니다.')
    st.divider()
    u1, u2 = st.columns([1, 1.2], vertical_alignment='center')
    u1.markdown(f":material/person: **{ss.settings['name']}**")
    u2.selectbox('AI 모델', list(MODEL_MAP), key='sb_model', on_change=change_model, label_visibility='collapsed')
    if ss.get('user'):
        st.button(':material/logout: 로그아웃', on_click=log_out, key='logout_btn', type='tertiary')
    st.caption(f'🗄️ 저장소: {DB_KIND} · 📁 자료 {len(ss.library)} · 📇 연락처 {len(ss.contacts)}')
    st.caption('최종 시연본 · 2026-11-05 · 업무 직접 등록')
    if ACCESS_PW and st.button('🔒 잠금'):
        ss.authenticated = False
        st.rerun()
PAGES = {'🏠 홈': page_home, '💬 채팅': page_chat, '📁 자료실': page_library, '✅ 내 작업': page_my_tasks, '👥 팀 업무 현황': page_team, '📧 이메일 관리': page_email, '⚙️ 설정': page_settings}
st.markdown(f"""<div class="able-crumb">작업공간 / {html_lib.escape(ss.menu.split(' ', 1)[-1])}</div>""", unsafe_allow_html=True)
if ss.menu == '✅ 내 작업':
    st.markdown('<style>[data-testid="stStatusWidget"]{display:none !important}</style>', unsafe_allow_html=True)
PAGES[ss.menu]()
save_data()
ws_save()
