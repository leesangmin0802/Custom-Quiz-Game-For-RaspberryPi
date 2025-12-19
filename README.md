# 🕹️ Arcade Quiz Console (Raspberry Pi)

> **Python 기반의 아케이드 퀴즈 시스템**입니다. 라즈베리파이의 GPIO를 활용한 하드웨어 연동(릴레이 제어)을 제공하며, 개발 및 테스트를 위한 환경도 완벽하게 지원합니다.

---

## ✨ 주요 기능 (Key Features)

* **동적 카테고리 시스템:** `images` 폴더 내의 하위 폴더를 자동으로 인식하여 메뉴 버튼을 생성합니다.
* **스마트 정답 파싱:** 별도의 DB 없이 파일명 규칙(예: `quiz_ns3.jpg`)만으로 정답(3번)을 자동 인식합니다.
* **하드웨어 연동:** 오답이나 시간 초과 시 라즈베리파이 GPIO에 연결된 **릴레이를 1초간 작동**시킵니다.
* **공정한 시간 관리:** 페널티(릴레이 작동)가 진행되는 동안에는 **전체 게임 시간이 일시 정지**됩니다.
* **랭킹 시스템:** 5자리 숫자 코드를 이용한 기록 저장 및 실시간 스크롤 명예의 전당 기능.

---

## 🛠️ 기술 스택 (Tech Stack)

* **Language:** Python 3.x
* **Graphics:** Pygame
* **Hardware Control:** gpiozero (Raspberry Pi 전용)
* **Storage:** JSON (Ranking 데이터 저장)

---

## 🚀 시작하기 (Getting Started)

### 1. 필수 라이브러리 설치
일반 PC(Windows) 환경에서 테스트하려면 아래 명령어로 Pygame을 설치하세요.
```bash
pip install pygame

### 2. 해당 폴더로 로직을 구성
project/
├── main.py
├── fonts/
│   └── NanumGothic.ttf
├── images/
│   ├── 카테고리 1/
│   │   └── category1_set1(문제의 세트)_no01(문제번호)_ns3(5지선다 중 문제 정답번호).jpg
│   └── 카테고리 2/
│       └── quiz_ns5.png
└── rank.json                  # 게임 실행 시 자동 생성
