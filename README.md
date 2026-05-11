# Discord Club Role Bot

새 멤버가 들어오면 자동으로 역할을 지급하고, 관리자가 한 번 보낸 고정 안내 메시지의 버튼으로 서버별명을 설정하는 Discord 봇입니다.

## 기능

- 새 멤버 입장 시 자동 역할 지급
- 관리자가 입장 안내 채널에 호남지역 대학/동아리 선택 버튼 메시지 전송
- 버튼 클릭 시 이름만 입력해서 서버별명 `(동아리명/이름)` 설정
- `/별명설정 동아리명 이름` 명령어로도 서버별명 설정
- 여러 서버에서 사용 가능하며 서버별 설정 SQLite 저장
- 관리자 명령어:
  - `/입장채널설정 channel:#입장`
  - `/입장메시지보내기`
  - `/입장역할설정 role:@회원`
  - `/동아리역할설정 동아리:국립목포대학교 / SecuMaster role:@SecuMaster`
  - `/동아리역할추가 동아리:국립목포대학교 / SecuMaster role:@호남`
  - `/설정확인`

## 설치

```powershell
cd E:\ofntkd\discord_club_role_bot
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

`.env`를 열고 `DISCORD_TOKEN`에 새 봇 토큰을 넣으세요.

## Discord Developer Portal 설정

1. 새 Application을 만들고 Bot을 생성합니다.
2. Bot 페이지에서 `SERVER MEMBERS INTENT`를 켭니다.
3. OAuth2 URL Generator에서 아래 설정으로 초대 링크를 만듭니다.
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Manage Nicknames`, `Manage Roles`, `Send Messages`, `View Channels`
4. 서버 역할 설정에서 봇의 역할을, 자동 지급할 역할보다 위로 올립니다.

## 실행

```powershell
cd E:\ofntkd\discord_club_role_bot
.\.venv\Scripts\Activate.ps1
py app.py
```

## 최초 설정

봇을 초대한 각 서버에서 서버 관리자 권한이 있는 계정으로 실행하세요.
입장 채널, 입장 역할, 동아리 버튼별 역할은 서버마다 따로 저장됩니다.

```text
/입장채널설정 channel:#입장
/입장역할설정 role:@회원
```

버튼별로 지급할 역할도 설정합니다. `/동아리역할설정`은 기존 버튼 역할을 초기화하고 1개로 설정합니다.

```text
/동아리역할설정 동아리:국립목포대학교 / SecuMaster role:@SecuMaster
/동아리역할설정 동아리:동신대학교 / HawkIS role:@HawkIS
/동아리역할설정 동아리:우석대학교 / APS role:@APS
/동아리역할설정 동아리:조선대학교 / HackerLogin role:@HackerLogin
```

같은 버튼에서 역할을 2개 이상 주고 싶으면 `/동아리역할추가`를 더 실행합니다.

```text
/동아리역할추가 동아리:국립목포대학교 / SecuMaster role:@호남
/동아리역할추가 동아리:동신대학교 / HawkIS role:@호남
```

입장 안내 채널에 버튼 메시지를 한 번 보냅니다.

```text
/입장메시지보내기
```

이 메시지를 Discord에서 고정해두면 새 멤버가 들어올 때마다 새 안내 메시지가 쌓이지 않습니다.

설정 확인:

```text
/설정확인
```

## 멤버 사용법

입장 안내 채널에 올라온 본인 소속 버튼을 누르고 이름을 입력합니다.
설정된 버튼 역할이 있으면 서버별명 변경과 함께 해당 역할도 자동으로 지급됩니다.

호남지역 버튼 목록:

- `국립목포대학교 / SecuMaster`
- `동신대학교 / HawkIS`
- `우석대학교 / APS`
- `조선대학교 / HackerLogin`

명령어로 직접 설정할 수도 있습니다.

```text
/별명설정 동아리명:SecuMaster 이름:홍길동
```

성공하면 서버별명이 `(SecuMaster/홍길동)` 형식으로 바뀝니다.

## 자주 막히는 부분

- 자동 역할이 안 들어가면 봇 역할이 `@회원`보다 위에 있는지 확인하세요.
- 안내 메시지가 안 올라오면 봇이 입장 채널을 볼 수 있고 메시지를 보낼 수 있는지 확인하세요.
- 별명이 안 바뀌면 봇에게 `Manage Nicknames` 권한이 있는지 확인하세요.
- 서버장이나 봇보다 높은 역할을 가진 멤버의 별명은 Discord 정책상 봇이 바꿀 수 없습니다.
