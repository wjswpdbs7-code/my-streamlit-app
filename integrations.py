"""Google Workspace OAuth and SMTP connectors. No credentials stored in app DB."""
import json, base64, re, smtplib, ssl, mimetypes
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.parse import quote
import requests

class Google:
    def __init__(self,setting): self.setting=setting;self.token=''
    @property
    def connected(self):return bool(self.setting('GOOGLE_REFRESH_TOKEN') and self.setting('GOOGLE_CLIENT_ID') and self.setting('GOOGLE_CLIENT_SECRET'))
    def call(self,service,path,method='GET',params=None,body=None):
        if not self.connected:raise ValueError('설정의 Google 연동 안내에 따라 OAuth 인증 정보를 등록하세요.')
        if not self.token:
            r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':self.setting('GOOGLE_CLIENT_ID'),'client_secret':self.setting('GOOGLE_CLIENT_SECRET'),'refresh_token':self.setting('GOOGLE_REFRESH_TOKEN'),'grant_type':'refresh_token'},timeout=25)
            if not r.ok:raise ValueError('Google 인증 갱신 실패. 토큰 만료·취소 또는 OAuth 설정을 확인하세요.')
            self.token=r.json()['access_token']
        root='https://gmail.googleapis.com/gmail/v1/users/me/' if service=='gmail' else 'https://www.googleapis.com/calendar/v3/'
        r=requests.request(method,root+path,headers={'Authorization':'Bearer '+self.token},params=params,json=body,timeout=30)
        if not r.ok:
            try:msg=r.json().get('error',{}).get('message','Google API 오류')
            except Exception:msg='Google API 오류'
            raise ValueError(f'Google {r.status_code}: {msg[:300]}')
        return r.json() if r.content else {}
    def messages(self,query='in:inbox',limit=15):
        data=self.call('gmail','messages',params={'q':query,'maxResults':limit})
        rows=[]
        for m in data.get('messages',[]):
            full=self.call('gmail','messages/'+m['id'],params={'format':'full'})
            h={x['name'].lower():x['value'] for x in full.get('payload',{}).get('headers',[])}
            def plain(part):
                data=part.get('body',{}).get('data','')
                if part.get('mimeType')=='text/plain' and data:
                    return base64.urlsafe_b64decode(data+'='*(-len(data)%4)).decode('utf-8',errors='replace')
                return '\n'.join(plain(x) for x in part.get('parts',[]))
            rows.append({'id':m['id'],'subject':h.get('subject','제목 없음'),'from':h.get('from',''),'date':h.get('date',''),'body':plain(full.get('payload',{})) or full.get('snippet','')})
        return rows
    def events(self,start,end):
        cal=quote(self.setting('GOOGLE_CALENDAR_ID','primary'),safe='')
        return self.call('calendar',f'calendars/{cal}/events',params={'timeMin':start,'timeMax':end,'singleEvents':'true','orderBy':'startTime','maxResults':200}).get('items',[])
    def save_event(self,event,event_id=None):
        cal=quote(self.setting('GOOGLE_CALENDAR_ID','primary'),safe='')
        path=f'calendars/{cal}/events'+('/'+quote(event_id,safe='') if event_id else '')
        return self.call('calendar',path,'PATCH' if event_id else 'POST',body=event,params={'sendUpdates':'none'})
    def delete_event(self,event_id):
        cal=quote(self.setting('GOOGLE_CALENDAR_ID','primary'),safe='')
        return self.call('calendar',f'calendars/{cal}/events/'+quote(event_id,safe=''),'DELETE',params={'sendUpdates':'none'})
    def busy(self,ids,start,end):
        return self.call('calendar','freeBusy','POST',body={'timeMin':start,'timeMax':end,'timeZone':'Asia/Seoul','items':[{'id':x} for x in ids]})

def send_mail(setting,google,recipient,subject,body,attachments):
    recipient=recipient.strip()
    address=parseaddr(recipient)[1]
    if '\n' in recipient or '\r' in recipient or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',address):raise ValueError('수신자 이메일 주소를 확인하세요.')
    if any('\n' in x or '\r' in x for x in [subject,setting('GMAIL_ADDRESS')]):raise ValueError('메일 제목·발신자에 줄바꿈을 사용할 수 없습니다.')
    if sum(len(data) for name,data in attachments)>15*1024*1024:raise ValueError('첨부파일 합계는 15MB 이하만 발송할 수 있습니다.')
    msg=EmailMessage();msg['To']=address;msg['Subject']=subject
    sender=setting('GMAIL_ADDRESS');
    if sender:msg['From']=sender
    msg.set_content(body)
    for name,data in attachments:
        major,minor=(mimetypes.guess_type(name)[0] or 'application/octet-stream').split('/',1)
        msg.add_attachment(data,maintype=major,subtype=minor,filename=name)
    if google.connected:
        r=google.call('gmail','messages/send','POST',body={'raw':base64.urlsafe_b64encode(msg.as_bytes()).decode()})
        return 'Gmail 접수 완료 · '+r.get('id','')
    password=setting('GMAIL_APP_PASSWORD').replace(' ','')
    if not sender or not password:raise ValueError('Gmail OAuth 또는 GMAIL_ADDRESS·GMAIL_APP_PASSWORD 설정이 필요합니다.')
    with smtplib.SMTP('smtp.gmail.com',587,timeout=30) as smtp:
        smtp.starttls(context=ssl.create_default_context());smtp.login(sender,password)
        refused=smtp.send_message(msg)
        if refused:raise ValueError('수신 서버가 메일을 거부했습니다.')
    return 'SMTP 접수 완료 · 실제 수신은 수신함에서 확인'
