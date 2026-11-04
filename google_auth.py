from pathlib import Path
import json
from google_auth_oauthlib.flow import InstalledAppFlow
SCOPES=['https://www.googleapis.com/auth/gmail.readonly','https://www.googleapis.com/auth/gmail.send','https://www.googleapis.com/auth/calendar.events','https://www.googleapis.com/auth/calendar.freebusy']
if __name__=='__main__':
    source=Path('client_secret.json')
    if not source.is_file():raise SystemExit('Google Cloud의 데스크톱 앱 OAuth 클라이언트 JSON을 client_secret.json으로 저장하세요.')
    target=Path('google_credentials.private.toml')
    if target.exists():raise SystemExit('기존 인증 파일이 있습니다. 백업 후 파일명을 바꾸고 다시 실행하세요.')
    creds=InstalledAppFlow.from_client_secrets_file(str(source),SCOPES).run_local_server(port=0,access_type='offline',prompt='consent')
    if not creds.refresh_token:raise SystemExit('refresh token을 받지 못했습니다. Google 권한 동의 설정을 확인하세요.')
    values={'GOOGLE_CLIENT_ID':creds.client_id,'GOOGLE_CLIENT_SECRET':creds.client_secret,'GOOGLE_REFRESH_TOKEN':creds.refresh_token,'GOOGLE_CALENDAR_ID':'primary'}
    target.write_text('\n'.join(k+' = '+json.dumps(v) for k,v in values.items()),encoding='utf-8')
    print('google_credentials.private.toml 생성 완료. 내용을 Streamlit Secrets에 복사하세요. GitHub에 업로드하지 마세요.')
