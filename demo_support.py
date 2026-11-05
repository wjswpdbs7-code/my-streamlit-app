"""Final demo helpers: isolated reset, onboarding and nullable task dates."""
import json,uuid,re
from pathlib import Path
from datetime import date,datetime,timedelta
import streamlit as st

class UnknownDue(date):
    def __new__(cls):return super().__new__(cls,9999,12,31)
    def __str__(self):return '미정'
    def __format__(self,spec):return '미정'

def due_read(t):
    value=t.get('마감일')
    if value is None or isinstance(value,UnknownDue):return UnknownDue()
    return value

def install_demo_support(n):
    ss=st.session_state
    table='able_final_demo_state'
    reset_keys=['tasks','schedule','library','candidates','changes','mail_drafts','contacts','sent','inbox','messages','conversations','attach_ids','suggestions']
    def epoch():
        con=n['ws_db']()
        row=con.execute(f'SELECT v FROM {table} WHERE k=?',('__demo_epoch',)).fetchone()
        if row:val=json.loads(row[0])
        else:
            val=uuid.uuid4().hex
            con.execute(f'INSERT INTO {table}(k,v,updated) VALUES(?,?,?) ON CONFLICT(k) DO NOTHING',('__demo_epoch',json.dumps(val),datetime.now().isoformat()))
            con.commit()
            row=con.execute(f'SELECT v FROM {table} WHERE k=?',('__demo_epoch',)).fetchone();val=json.loads(row[0])
        con.close();return val
    def sync_epoch():
        current=epoch()
        if ss.get('_demo_epoch') is None:ss['_demo_epoch']=current;return
        if ss['_demo_epoch']==current:return
        data=n['ws_load']()
        for k in reset_keys:ss[k]=data.get(k,[]) if k not in ['messages','conversations'] else data.get(k+'::'+ss.user,[])
        ss.conv_id=data.get('conv_id::'+ss.user,uuid.uuid4().hex)
        ss._ws_last={};ss._demo_epoch=current
        ss.notice='시연 데이터가 초기화되어 최신 빈 작업공간으로 전환했습니다.'
        st.rerun()
    sync_epoch()
    # Registration is an explicit action; a summary request does not change the task list.
    def registration_requested(prompt):
        if re.search(r'(등록|추가|반영).{0,5}(하지\s*마|하지\s*말|금지|하지\s*않)',prompt):return False
        return bool(re.search(r'(등록|추가|반영|넣어).{0,6}(해|줘|주세요|바람)',prompt))
    n['registration_requested']=registration_requested
    old_route=n['route']
    def route(prompt):
        if n['TASK_PULL_RE'].search(prompt) and (n['ss'].library or n['ss'].get('_turn_files')):
            return {'intent':'chat','args':{}}
        return old_route(prompt)
    n['route']=route
    old_save=n['ws_save']
    def save():
        sync_epoch()
        for t in ss.tasks:
            if isinstance(t.get('마감일'),UnknownDue):t['마감일']=None;t['기한 설명']='미정'
        old_save()
    n['ws_save']=save
    def reset():
        if ss.user!=n['get_secret']('DEMO_ADMIN_NAME','김진수'):
            ss.notice='시연 초기화는 지정한 관리자만 실행할 수 있습니다.';return
        if not ss.get('final_reset_ok') or ss.get('final_reset_text')!='시연 초기화':
            ss.notice='확인란과 초기화 문구를 확인하세요.';return
        newepoch=uuid.uuid4().hex
        try:
            con=n['ws_db']()
            con.execute(f'DELETE FROM {table} WHERE k <> ? AND k NOT LIKE ?',('users','settings::%'))
            con.execute(f'INSERT INTO {table}(k,v,updated) VALUES(?,?,?)',('__demo_epoch',json.dumps(newepoch),datetime.now().isoformat()))
            con.commit();con.close()
            Path(n['DATA_FILE']).write_text(json.dumps({'contacts':[],'sent':[]}),encoding='utf-8')
        except Exception as exc:ss.notice='초기화 실패: '+str(exc);return
        keep={k:ss[k] for k in ['user','users','settings','authenticated','smtp'] if k in ss}
        for k in list(ss):del ss[k]
        ss.update(n['_defaults']());ss.update(keep)
        for k in reset_keys:ss[k]=[]
        ss.conv_id=uuid.uuid4().hex;ss._ws_last={};ss._demo_epoch=newepoch;ss.ws_loaded=True;ss.data_loaded=True
        ss.menu='🏠 홈';ss.notice='시연 준비 완료 · 계정은 유지하고 대화·자료·업무를 비웠습니다.'
        save()
    # Override all legacy reset entry points with the isolated reset procedure.
    n['reset_workspace']=reset
    old_home=n['page_home']
    def home():
        done=[bool(ss.library),bool(ss.messages),bool(ss.tasks)]
        st.caption('시연 진행 · '+' → '.join(('✓ ' if done[i] else '')+label for i,label in enumerate(['회의록 업로드','업무 분석','작업 등록'])))
        if not ss.tasks:
            st.info('빈 작업공간입니다. 채팅에서 회의록을 첨부하고 “담당자별 업무를 뽑아서 작업에 등록해줘”라고 요청하세요.')
            if st.button('회의록 업로드하러 가기',type='primary',key='demo_chat'):
                ss.menu='💬 채팅';st.rerun()
        old_home()
    n['page_home']=home
    old_settings=n['page_settings']
    def settings():
        # Reuse settings through the layer before the original broad reset UI.
        n['_v41_page_settings']()
        st.subheader('시연 데이터 초기화')
        st.caption('이 최종본 전용 DB 테이블만 비웁니다. 계정·사용자 설정과 외부 팀 원본 테이블은 유지합니다.')
        if ss.user==n['get_secret']('DEMO_ADMIN_NAME','김진수'):
            st.checkbox('시연 자료·업무·모든 계정의 대화를 삭제합니다',key='final_reset_ok')
            st.text_input('“시연 초기화” 입력',key='final_reset_text')
            st.button('빈 작업공간으로 다시 시작',on_click=reset,type='primary')
        else:st.caption('초기화 관리자: '+n['get_secret']('DEMO_ADMIN_NAME','김진수'))
    n['page_settings']=settings
    # Deduplicate the manual add-table button after automatic document registration.
    def add_table_tasks(i):
        rows=n['table_tasks'](ss.messages[i]['content'])
        have={(re.sub(r'\s+','',t['업무']),t['담당자']) for t in ss.tasks}
        for r in rows:
            key=(re.sub(r'\s+','',r['title']),r['owner'])
            if key in have:continue
            have.add(key);d=r.get('due')
            t={'id':uuid.uuid4().hex[:8],'업무':r['title'],'담당자':r['owner'],'마감일':None if isinstance(d,UnknownDue) else d,'상태':'대기','우선순위':'보통','근거':'채팅 답변 표'}
            ss.tasks.append(t);n['record_change'](t,'등록','-','채팅 표에서 추가')
        ss.messages[i]['tasks_added']=True
    n['add_table_tasks']=add_table_tasks
    old_dday=n['dday'];old_label=n['due_label']
    n['dday']=lambda d:'기한 미정' if d is None or isinstance(d,UnknownDue) else old_dday(d)
    n['due_label']=lambda d:'기한 미정' if d is None or isinstance(d,UnknownDue) else old_label(d)
    with st.sidebar.expander('시연 안내',expanded=not bool(ss.tasks)):
        st.caption('① 회의록 다운로드 → ② 채팅에 첨부 → ③ 업무 등록 요청 → ④ 내 작업·팀 업무 확인')
        folder=Path(__file__).parent/'demo_assets'
        for filename in ['시연_회의록.txt','시연_요청문.txt']:
            p=folder/filename
            if p.is_file():st.download_button(filename,p.read_bytes(),filename,key='demo_'+filename)
        st.caption('시연 계정 이름은 김진수를 권장합니다. 다른 이름이면 회의록 담당자와 맞춰 주세요.')
    # Scalar UnknownDue rendering in old table widgets: no fake 9999-12-31 shown.
    if not hasattr(st,'_final_native_dataframe'):st._final_native_dataframe=st.dataframe
    def dataframe(data=None,*args,**kwargs):
        import pandas as pd
        if isinstance(data,pd.DataFrame):data=data.map(lambda v:'미정' if isinstance(v,UnknownDue) else v)
        return st._final_native_dataframe(data,*args,**kwargs)
    st.dataframe=dataframe
    if not hasattr(st,'_final_native_date_input'):st._final_native_date_input=st.date_input
    def date_input(label,*args,**kwargs):
        key=kwargs.get('key')
        if key and isinstance(ss.get(key),UnknownDue):ss[key]=None
        args=list(args)
        if args and isinstance(args[0],UnknownDue):args[0]=None
        if isinstance(kwargs.get('value'),UnknownDue):kwargs['value']=None
        return st._final_native_date_input(label,*args,**kwargs)
    st.date_input=date_input
