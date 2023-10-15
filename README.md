# Buppy 🐶

Buppy는 슬랙에서 동작하는 AI 동반자입니다! Buppy는 사용자의 질문에 대한 답변을 생성하고 반환합니다. 실시간 상호작용으로 질문을 이해하고 대응합니다.

## 목차
- [설치 가이드](#설치-가이드)
- [실행 방법](#실행-방법)
- [사용법](#사용법)
- [문의](#문의)
- [라이선스](#라이선스)
- [기여](#기여)

## 설치 가이드 🚀

### 시스템 요구 사항

- Python 3.8 이상
- 패키지 관리 도구 Poetry
- Slack Workspace
- Slack App 생성

### 패키지 관리 도구 Poetry 설치

Python에서 패키지를 관리하기 위한 도구인 'Poetry'를 설치합니다. Poetry는 패키지 버전 관리를 자동화하여 도와줍니다.

### 패키지 설치

Buppy를 실행하기 위한 라이브러리를 설치합니다. 라이브러리는 Python 패키지 설치 도구인 Poetry를 사용하여 설치합니다. 설치를 진행하려면 터미널에서 프로젝트 위치로 이동한 후 다음 명령어를 입력하세요:

```
poetry install
```

### config.ini 설정

아래 설정 예제와 같이 `config.ini` 파일을 작성해 주세요:

```
[api]
openai_api_key = "OPEN_AI_API_KEY_VALUE"
serpapi_api_key = "SERP_API_KEY_VALUE"
slack_bot_token = "SLACK_BOT_TOKEN_VALUE"
slack_app_token = "SLACK_APP_TOKEN_VALUE"

[settings]
chat_model = "gpt-3"
system_prompt = "You are a helpful assistant."
temperature = "0.5"
```

## 실행 방법 🖥️

### 로컬에서의 실행

Poetry를 사용하여 아래 명령어로 코드를 실행할 수 있습니다:

```
poetry run python main.py
```

### Slack 봇 설정

Buppy를 Slack에 추가하려면 다음의 단계를 따라주세요.

#### Slack 앱 생성

아래의 링크에서 Slack 앱을 생성하세요.

```
https://api.slack.com/apps
```

#### 봇 권한과 스코프 추가

생성한 앱 설정 페이지에서 'OAuth & Permissions' 섹션으로 이동하세요. 'Scopes'에 들어가 'Bot Token Scopes'를 클릭하고 아래에 나열된 권한을 추가하세요:

- `channels:read`: 앱이 public 채널 리스트를 읽을 수 있게 합니다.
- `channels:history`: 앱이 채널의 메시지 기록을 읽을 수 있게 합니다.
- `chat:write`: 앱이 채널에 메시지를 전송할 수 있게 합니다.
- `reactions:write`: 앱이 메시지에 이모티콘을 달 수 있게 합니다.

#### 앱 설치와 봇 토큰 복사

'Install App'을 클릭하여 앱을 워크스페이스에 설치하고, 'Bot User OAuth Access Token'을 복사합니다. 이 토큰을 `config.ini` 파일의 `slack_bot_token`에 붙여넣습니다.

#### Socket Mode 활성화와 App Level 토큰 생성

`Settings` -> `Socket Mode`에 들어가 Socket Mode를 활성화하고 'App Level Tokens'를 생성하세요. 이 토큰을 `config.ini` 파일의 `slack_app_token`에 붙여넣습니다.

#### 이벤트 구독 설정

'Event Subscriptions' 섹션에 들어가 'Enable Events'를 클릭하여 이벤트를 활성화합니다. 'Subscribe to bot events'에서 아래 이벤트를 추가하세요:

- `app_mention`: Buppy 봇이 언급되었을 때에 대한 이벤트를 리스닝합니다.
- `message.channels`: 채널 내의 메세지에 대한 이벤트를 리스닝합니다.

#### 앱을 채널에 추가

앱의 설정을 모두 완료한 후, 워크스페이스로 가서 Buppy가 동작할 채널에 가서 앱을 추가하세요.

이제 Buppy는 설정된 Slack 채널에서 잘 동작할 것입니다. 앱을 언급하거나 직접 질문하면 Buppy가 대답을 생성하여 반환합니다.

## 사용법 📘

Buppy에게 질문하려면, 슬랙에서 `/ask` 명령어를 사용하거나, `@Buppy` 를 멘션하여 질문을 하면 됩니다.

```
/ask What's the weather like today?
```

Buppy는 질문을 처리하고, 결과를 생성하여 반환합니다.

## 문의 💬

프로젝트에 대한 질문이나 이슈가 있다면, 이슈 트래커를 통해 알려주세요.

## 기여 🤝

이 프로젝트는 모든 것이 Open Source에 따라 이루어집니다! 따라서 이 프로젝트에 기여를 환영합니다!

- 새로운 기능을 구현해 보세요.
- 버그를 수정해 보세요.
- 문서를 업데이트 해보세요.

프로젝트에 대한 질문이나 의견, 제안사항이 있으시면 언제든지 이야기해 주세요! 함께 개선해 나갑시다.
