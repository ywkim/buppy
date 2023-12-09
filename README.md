# Buppy 🐶

Buppy는 대화형 웹 애플리케이션과 슬랙에서 동작하는 AI 동반자입니다! 사용자가 슬랙과 웹 인터페이스를 통해 Buppy와 상호작용할 수 있습니다. Buppy는 사용자의 질문에 대한 답변을 생성하고 반환하며, 실시간 상호작용으로 질문을 이해하고 대응합니다.

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
- OpenAI API Key

### 패키지 관리 도구 Poetry 설치

Python에서 패키지를 관리하기 위한 도구인 'Poetry'를 설치합니다. Poetry는 패키지 버전 관리를 자동화하여 도와줍니다.

### 패키지 설치

Buppy를 실행하기 위한 라이브러리를 설치합니다. 라이브러리는 Python 패키지 설치 도구인 Poetry를 사용하여 설치합니다. 설치를 진행하려면 터미널에서 프로젝트 위치로 이동한 후 다음 명령어를 입력하세요:

```
poetry install
```

### Google Cloud 사용자 인증

`upload_companion.py` 스크립트를 사용하기 전에, 애플리케이션 기본 인증을 위해 Google Cloud 사용자 인증을 완료해야 합니다. Google Cloud SDK를 설치하고 다음 명령어를 사용하여 인증하세요:

```
gcloud auth application-default login
```

이 명령어는 기본 웹 브라우저를 열고 Google 계정으로 로그인하라는 요청을 합니다. 로그인을 완료하면 애플리케이션에서 필요한 인증 정보가 로컬 시스템에 저장되며, `upload_companion.py` 스크립트에서 해당 인증 정보를 사용할 수 있습니다. Google Cloud SDK에 대한 자세한 정보는 [여기](https://cloud.google.com/sdk/docs/install)에서 확인할 수 있습니다.

### config.ini 설정

아래 설정 예제와 같이 `config.ini` 파일을 작성해 주세요:

```
[api]
openai_api_key = OPEN_AI_API_KEY
slack_bot_token = SLACK_BOT_TOKEN
slack_app_token = SLACK_APP_TOKEN

[settings]
chat_model = gpt-3.5-turbo
system_prompt = You are a helpful assistant.
temperature = 1
vision_enabled = false
```

`vision_enabled` 설정은 이미지 분석 기능을 활성화하며, 이 기능은 `gpt-4-vision-preview` 모델에서만 사용 가능합니다. 해당 모델을 설정하여 Buppy가 Slack 메시지에 포함된 이미지에 대한 분석을 수행할 수 있도록 합니다.

OpenAI의 API Key는 [OpenAI 플랫폼](https://platform.openai.com/account/api-keys)에서 생성할 수 있습니다. 생성한 Key를 위의 설정 예제에 있는 `OPENAI_API_KEY` 위치에 붙여넣으세요.

### Streamlit 설정

Streamlit 웹 인터페이스를 위해, `.streamlit/secrets.toml` 파일에 필요한 설정을 추가합니다. 이 파일은 Streamlit 앱의 설정 정보를 저장하는 데 사용됩니다. 다음은 설정 예제입니다:

```toml
[api]
openai_api_key = "your_openai_api_key_here"

[settings]
temperature = 1
system_prompt = "You are a helpful assistant."
```

## 실행 방법 🖥️

### 로컬에서의 실행

Poetry를 사용하여 아래 명령어로 코드를 실행할 수 있습니다:

#### Buppy 실행 (Slack)

```
poetry run python main.py
```

#### Buppy 실행 (Web Interface)

```
poetry run streamlit run streamlit_app.py
```

#### `upload_companion.py` 스크립트 실행

```
poetry run python upload_companion.py path/to/config.ini
```

여기서 `path/to/config.ini`는 `config.ini` 파일의 경로를 나타냅니다. 이 스크립트는 Firestore에 Companion 및 Bot 데이터를 업로드하는 데 사용됩니다.

### Slack 봇 설정

Buppy를 Slack에 추가하고 활용하기 위한 단계를 아래에 자세히 설명합니다. 이 과정은 두 가지 방법으로 수행할 수 있습니다: 수동 설정 및 앱 매니페스트를 사용한 자동화된 설정.

#### 1. 수동 설정 방법

아래의 링크에서 Slack 앱을 생성하세요.

```
https://api.slack.com/apps
```

##### 봇 권한과 스코프 추가

생성한 앱 설정 페이지에서 'OAuth & Permissions' 섹션으로 이동하세요. 'Scopes'에 들어가 'Bot Token Scopes'를 클릭하고 아래에 나열된 권한을 추가하세요:

- `channels:read`: 앱이 public 채널 리스트를 읽을 수 있게 합니다.
- `channels:history`: 앱이 채널의 메시지 기록을 읽을 수 있게 합니다.
- `chat:write`: 앱이 채널에 메시지를 전송할 수 있게 합니다.
- `reactions:write`: 앱이 메시지에 이모티콘을 달 수 있게 합니다.
- `files:read`: 앱이 Slack에서 공유된 파일의 정보를 읽을 수 있게 합니다.

##### 앱 설치와 봇 토큰 복사

'Install App'을 클릭하여 앱을 워크스페이스에 설치하고, 'Bot User OAuth Token'을 복사합니다. 이 토큰을 `config.ini` 파일의 `slack_bot_token`에 붙여넣습니다.

##### Socket Mode 활성화와 App Level 토큰 생성

'Socket Mode'에 들어가 Socket Mode를 활성화하고 'App Level Tokens'를 생성하세요. 이 토큰을 `config.ini` 파일의 `slack_app_token`에 붙여넣습니다.

##### 이벤트 구독 설정

'Event Subscriptions' 섹션에 들어가 'Enable Events'를 클릭하여 이벤트를 활성화합니다. 'Subscribe to bot events'에서 아래 이벤트를 추가하세요:

- `app_mention`: Buppy 봇이 언급되었을 때에 대한 이벤트를 리스닝합니다.
- `message.channels`: 채널 내의 메세지에 대한 이벤트를 리스닝합니다.

##### 앱을 채널에 추가

앱의 설정을 모두 완료한 후, 워크스페이스로 가서 Buppy가 동작할 채널에 가서 앱을 추가하세요.

이제 Buppy는 설정된 Slack 채널에서 잘 동작할 것입니다. 앱을 언급하거나 직접 질문하면 Buppy가 대답을 생성하여 반환합니다.

#### 2. 앱 매니페스트를 사용한 설정

앱 매니페스트를 사용하면 Buppy 봇 설정을 보다 효율적이고 일관되게 관리할 수 있습니다. 아래 단계를 따라 Slack 앱 매니페스트를 생성하고 적용하는 방법을 안내합니다.

##### 매니페스트 파일 생성

먼저, Buppy의 기능과 권한을 정의하는 YAML 형식의 매니페스트 파일을 생성합니다. 다음은 Buppy 앱을 위한 기본 매니페스트 예제입니다:

```yaml
display_information:
  name: Buppy

features:
  bot_user:
    display_name: Buppy
    always_online: true

oauth_config:
  scopes:
    bot:
      - channels:read
      - channels:history
      - chat:write
      - reactions:write
      - files:read

settings:
  event_subscriptions:
    bot_events:
      - app_mention
      - message.channels

  interactivity:
    is_enabled: true

  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false
```

##### Slack에서 매니페스트 업로드

1. Slack API 웹사이트([api.slack.com](https://api.slack.com))에 접속하여 'Your Apps'로 이동합니다.
2. 'Create New App'을 클릭하고 'From an app manifest' 옵션을 선택합니다.
3. 워크스페이스를 선택하고, 앞서 생성한 매니페스트 파일의 내용을 붙여넣습니다.
4. 'Review'를 클릭하여 매니페스트를 검토한 후, 'Create'를 클릭하여 앱을 생성합니다.

##### 생성된 앱 설정 확인 및 수정

앱이 생성되면, Slack에서 자동으로 설정한 권한과 기능을 확인하고 필요에 따라 추가적인 설정을 할 수 있습니다. 예를 들어, 'Interactivity & Shortcuts' 메뉴에서 인터랙티브 기능을 추가로 설정하거나, 'Event Subscriptions'에서 추가 이벤트를 구독할 수 있습니다.

### Streamlit 웹 인터페이스 설정

웹 인터페이스를 통해 Buppy와 상호작용하기 위해서는 별도의 추가 설정이 필요하지 않습니다. 위의 실행 방법 섹션에서 제공된 명령어를 사용하여 로컬에서 Streamlit 애플리케이션을 실행할 수 있습니다.

또한, Buppy는 [이 링크](https://buppy-chat.streamlit.app/)를 통해 웹에서도 접근 가능합니다. 해당 링크를 클릭하면 Buppy와 바로 상호작용을 시작할 수 있습니다.

## 사용법 📘

### Slack에서 사용하기

Buppy에게 질문하려면, 슬랙에서 `@Buppy` 를 멘션하여 질문을 하면 됩니다.

```
@Buppy What's the weather like today?
```

Buppy는 질문을 처리하고, 결과를 생성하여 반환합니다.

### 웹 인터페이스에서 사용하기

웹 인터페이스에서 Buppy와 상호작용하기 위해, Streamlit 애플리케이션을 실행하고 웹 브라우저에서 해당 URL로 접속하세요. 사용자는 대화 입력 필드에 메시지를 입력하여 Buppy와 대화를 시작할 수 있습니다. Buppy는 실시간으로 사용자의 질문에 답변하고 상호작용합니다.

## 문의 💬

프로젝트에 대한 질문이나 이슈가 있다면, 이슈 트래커를 통해 알려주세요.

## 기여 🤝

이 프로젝트는 모든 것이 Open Source에 따라 이루어집니다! 따라서 이 프로젝트에 기여를 환영합니다!

- 새로운 기능을 구현해 보세요.
- 버그를 수정해 보세요.
- 문서를 업데이트 해보세요.

프로젝트에 대한 질문이나 의견, 제안사항이 있으시면 언제든지 이야기해 주세요! 함께 개선해 나갑시다.
