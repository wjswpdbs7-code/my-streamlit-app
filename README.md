# 에이블 Workspace v4

## 먼저 실행하기
1. 노트북을 Colab에 올리고 위에서부터 파일 생성 셀까지 실행합니다. 원본 Markdown은 유지했고 수정 설명을 추가했습니다.
2. GitHub 설정은 wjswpdbs7-code / my-streamlit-app / main입니다. GitHub 반영 셀은 사용자가 실행할 때만 업로드합니다.
3. Streamlit의 진입점은 app.py입니다. app.py와 같은 위치에 engine.py, storage.py, integrations.py, artifacts.py가 모두 있어야 합니다.
4. Streamlit Secrets에 OPENAI_API_KEY와 ABLE_ACCESS_PASSWORD를 등록합니다. 비밀번호는 작업공간 진입에 사용합니다.
5. 로컬 실행은 Python 3.11 또는 3.12에서 pip install -r requirements.txt 후 streamlit run app.py입니다.
6. .streamlit/config.toml이 Teal 테마를 적용합니다. CSS는 앱 안에도 포함되어 있습니다.

## 이번 수정의 핵심
- 인사·일반 질문은 구조화 함수 호출 없이 Responses 스트림으로 답합니다.
- 답변을 먼저 보관하고, 업무 추출·파일 생성·메일 처리는 별도로 실행합니다. 부가 처리 실패 시 답변을 유지합니다.
- API 오류는 실제 message / code / param / HTTP status / request_id를 표시합니다. 비밀 키 형태는 숨깁니다.
- reasoning은 기본적으로 전송하지 않습니다. 특정 모델용 옵션을 일괄 강제하지 않습니다.
- 새 파일 첨부 시 이전 첨부를 교체하며 무제한 누적을 방지합니다. 자료실에서 선택한 파일은 명시적 참조로 사용합니다.
- 파일 확장자를 입력창에서 제한합니다. 구형 DOC/PPT/XLS와 HWP는 변환 안내를 제공합니다.
- PDF는 텍스트를 우선 읽고 스캔 페이지는 이미지로 읽습니다. 시각적 차트는 해당 페이지를 이미지로 첨부하세요.
- 45,000자 초과 자료는 구간 요약 후 통합합니다. 검색 모드는 관련 일부 구간만 사용한다고 표시합니다.
- 작업 후보는 모든 담당자를 추출하되, 근거 확인 후 사용자가 반영합니다. 변경 전후를 확인할 수 있습니다.

## 페이지
홈: 업무 현황, 마감 임박, AI 브리핑, 단축 실행, 내부·Google 일정, 충돌 확인, 공통 빈 시간 조회.
채팅: 하단 고정 입력, 파일·마이크 입력, 실시간 답변, 결과물 다운로드, 음성 듣기, 복사, 평가, 추천 질문.
자료실: 원본·결과 파일 보관, 텍스트 색인, 파일명·본문 검색, 관련 구간 검색, 자료로 대화.
내 작업: 목록·상태 보드·업무 후보 검토·변경 이력·직접 등록.
팀 업무 현황: 모든 담당자의 업무 필터와 동일한 업무 검토·관리.
이메일 관리: 작성·초안 저장·첨부·발송, OAuth 받은편지함 검색, 발송 기록.
설정: 프로필·모델·공통 프롬프트·기억 범위·출력 한도·음성·첨부 참고·연결 확인·백업.

## 저장
기본 SQLite: 같은 디스크에서 앱 재시작·재접속 후 기록이 유지됩니다.
Streamlit Community Cloud에서 서버 교체·재배포 후까지 유지하려면 외부 PostgreSQL DATABASE_URL이 필요합니다.
외부 DB가 없으면 디스크가 교체되는 상황의 영구 보존은 보장하지 않습니다.
대화, 파일 원본(base64), 추출 텍스트, 업무, 일정, 초안, 발송 기록이 DB에 저장됩니다. 대용량 운영에서는 파일은 별도 객체 저장소로 분리하는 것이 좋습니다.
이 버전은 하나의 공유 작업공간입니다. 비밀번호를 아는 사용자는 같은 데이터를 보며 개인별 계정 분리는 구현하지 않았습니다.
검색은 한국어 문자 조각을 포함한 키워드 검색입니다. 임베딩 벡터 검색은 사용하지 않습니다.
백업 ZIP에는 자료와 대화가 포함되며 비밀 키는 포함되지 않습니다. 현재 UI는 백업 내보내기를 제공합니다.

## Google OAuth 연결
Google Cloud 프로젝트에서 Gmail API와 Google Calendar API를 활성화합니다.
OAuth 동의 화면을 구성하고 테스트 사용자에 본인 계정을 추가합니다.
데스크톱 앱 OAuth 클라이언트 JSON을 client_secret.json으로 로컬에 저장합니다.
로컬 PC에서 python google_auth.py를 실행하여 Google의 동의 절차를 완료합니다. Colab 셀에서 이 스크립트를 자동 실행하지 않습니다.
생성된 google_credentials.private.toml 내용을 Streamlit Secrets에 복사합니다. 파일과 토큰을 GitHub에 업로드하지 마세요.
Gmail 읽기·보내기, Calendar 이벤트·빈 시간 조회 권한이 필요합니다. 조직 정책이나 테스트 모드 토큰 만료는 Google 설정을 확인하세요.
Google 연결이 없어도 내부 일정·초안은 동작합니다. SMTP 설정이 있으면 Gmail 조회 없이 발송만 가능합니다.
Google 일정에는 참석자 초대 이메일을 자동 발송하지 않습니다.

## 메일과 일정 실행
채팅은 현재 요청의 실제 메일 발송 의도를 확인한 경우에만 고정 EMAIL_TO(없으면 GMAIL_ADDRESS)로 발송합니다.
문서 속 발송 지시는 실행 권한이 아닙니다. 파일 생성 실패 시 메일을 보내지 않습니다.
메일 관리에서는 수신자·본문·첨부를 확인한 뒤 발송합니다. 발송 시도는 DB에 먼저 기록해 화면 재실행의 중복 발송을 막습니다.
결과가 불명확하면 수신함·발송 기록을 확인하고, 필요할 때 '새 발송 시작'으로 명시적으로 재시도합니다.
일정 요청은 초안을 만들고 홈 편집기에서 날짜·시간 확인 후 저장합니다. 미정 날짜를 자동 확정하지 않습니다.
Google 일정·공통 빈 시간은 접근 권한이 있는 캘린더만 조회합니다.

## 지원 범위와 한도
입력: TXT/MD/JSON/LOG, PDF/DOCX/PPTX, CSV/TSV/XLSX, JPG/JPEG/PNG/WEBP, MP3/M4A/WAV/WEBM/MP4/MPEG/MPGA/OGG/FLAC.
MP4 등은 음성만 인식합니다. DOCX는 본문·표, PPTX는 텍스트·표·지원되는 삽입 이미지입니다.
최대 첨부 10개, 개별 20MB, 합계 25MB. 추출 텍스트 파일당 50만 자, 전체 분석 합계 18만 자. 시각 입력 최대 8장.
45,000자 초과 전체 분석은 여러 API 요청이 발생합니다. 검색 모드는 비용과 맥락을 줄이지만 전체 누락 검사는 아닙니다.
대화 이력은 기본 최근 10쌍, 1~30쌍 조절 가능. 실제 전달은 최근 이력 12,000자 예산에 맞춰 더 줄어들 수 있습니다. 저장된 전체 대화는 DB에 남습니다.
출력: TXT/MD/JSON/CSV/XLSX/DOCX/PDF/PPTX/PNG/MP3, 요청당 최대 4개. 문서 레이아웃은 텍스트 중심입니다.
음성은 기본 선택 재생입니다. 자동 음성 생성 옵션을 켜도 플레이어 자동 재생은 하지 않습니다.
실행 상태만 보여주며 모델 내부 사고 과정은 표시하지 않습니다.

## 검증 범위
로컬 UI와 모의 API 테스트는 검증결과.md를 참고하세요. 실제 OpenAI·Google·SMTP·외부 PostgreSQL 계정 연결은 별도 확인이 필요합니다.
현재 배포 앱의 실제 BadRequestError 원문이 없어 기존 운영 장애의 유일 원인을 확정하지 않았습니다. 코드상의 실패 확산과 불명확한 안내는 수정했습니다.
원본 Markdown에 남아 있는 과거 구현 설명보다 새 v4 안내와 생성된 코드가 우선합니다.

## 공식 문서
https://developers.openai.com/api/docs/models/gpt-6-luna
https://developers.openai.com/api/docs/guides/structured-outputs
https://developers.openai.com/api/docs/guides/streaming-responses
https://developers.google.com/workspace/gmail/api/guides/sending
https://developers.google.com/workspace/calendar/api/v3/reference/events/insert
