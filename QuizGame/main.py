import pygame
import os
import json
import time
from gpiozero import OutputDevice
from threading import Thread

# --- 1. CONFIGURATION (설정) ---
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FPS = 60

# 색상
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
PRIMARY_BG = (20, 25, 30)   # 깊은 어두운 배경
SECONDARY_BG = (35, 45, 55) # 보조 배경 (버튼/상태 바)
ACCENT_COLOR = (0, 150, 255)  # 산뜻한 파란색 (주요 강조)
ACCENT_LIGHT = (135, 206, 250) # 밝은 파란색 (하이라이트)
DANGER_COLOR = (255, 99, 71)  # 밝은 빨간색 (위험/오류)
WARNING_COLOR = (255, 215, 0) # 금색 (경고)
GRAY_TEXT = (180, 190, 200) # 밝은 회색 텍스트

# GPIO 설정
RELAY_PIN = 17

# 게임 밸런스 및 시간 설정
TOTAL_GAME_TIME = 60    
Q_TIME_LIMIT = 10       
RELAY_PENALTY_TIME = 1.0     # ***수정: 1.0초로 변경***
DISPLAY_PENALTY_TIME = 1.0 

# --- 2. HARDWARE & UTILITIES (하드웨어 및 유틸리티) ---
relay = None
try:
    relay = OutputDevice(RELAY_PIN, active_high=True, initial_value=False)
except Exception as e:
    print(f"GPIO 릴레이 초기화 오류 (테스트 모드): {e}")

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("RPi 퀴즈 콘솔")
clock = pygame.time.Clock()

FONT_PATH = os.path.join("fonts", "NanumGothic.ttf")

def get_font(size):
    try:
        return pygame.font.Font(FONT_PATH, size)
    except:
        return pygame.font.SysFont("NanumGothic", size)

RANK_FILE = "rank.json"

def load_ranks():
    if not os.path.exists(RANK_FILE): return []
    try:
        with open(RANK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_rank(score, code):
    ranks = load_ranks()
    code_str = "".join(map(str, code))
    ranks.append({"score": score, "code": code_str})
    ranks.sort(key=lambda x: x["score"], reverse=True)
    with open(RANK_FILE, "w", encoding="utf-8") as f:
        json.dump(ranks, f, ensure_ascii=False, indent=4)

def parse_answer_from_filename(filename):
    try:
        name_body = os.path.splitext(filename)[0]
        parts = name_body.split('_')
        for part in parts:
            if part.startswith('ns') and part[2:].isdigit():
                return int(part[2:])
    except: pass
    return 1 

def load_questions(category_path):
    questions = []
    if not os.path.exists(category_path): os.makedirs(category_path)

    for root, dirs, files in os.walk(category_path):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                ans = parse_answer_from_filename(file)
                full_path = os.path.join(root, file)
                questions.append({
                    "path": full_path,
                    "filename": file,
                    "answer": ans
                })
    questions.sort(key=lambda x: x["filename"])
    
    if not questions:
        for i in range(1, 51):
            questions.append({
                "path": None, 
                "filename": f"더미 문제 {i}",
                "answer": (i % 5) + 1
            })
    return questions

def trigger_relay():
    if relay:
        def task():
            relay.on()
            time.sleep(RELAY_PENALTY_TIME)
            relay.off()
        Thread(target=task).start()

# --- 3. UI ELEMENTS (UI 요소) ---
class ButtonUI:
    def __init__(self, x, y, w, h, text, action_payload=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.action_payload = action_payload
        self.is_hovered = False
        self.shadow_offset = 5 # 그림자 효과

    def draw(self, surface, idx):
        # 1. 그림자 그리기 (입체감 추가)
        shadow_rect = self.rect.move(self.shadow_offset, self.shadow_offset)
        pygame.draw.rect(surface, (10, 10, 10), shadow_rect, border_radius=15)
        
        # 2. 배경 그리기
        bg_color = ACCENT_COLOR if self.is_hovered else SECONDARY_BG
        pygame.draw.rect(surface, bg_color, self.rect, border_radius=15)
        
        # 3. 테두리 그리기
        border_color = ACCENT_LIGHT if self.is_hovered else GRAY_TEXT
        pygame.draw.rect(surface, border_color, self.rect, 3, border_radius=15)
        
        # 4. 텍스트 그리기
        display_text = f"[{idx}] {self.text}"
        txt_color = BLACK if self.is_hovered else WHITE
        txt_surf = get_font(30).render(display_text, True, txt_color)
        txt_rect = txt_surf.get_rect(center=self.rect.center)
        surface.blit(txt_surf, txt_rect)

# --- 4. GAME STATES & MAIN LOOP (게임 상태 및 메인 루프) ---
def main():
    running = True
    state = "MENU"
    
    current_category = ""
    q_list = []
    current_q_data = None
    current_q_img = None
    
    score = 0
    game_start_ts = 0
    last_penalty_end_ts = 0 # ***추가: 페널티가 끝난 시각을 저장***
    q_start_ts = 0
    
    penalty_mode = False
    penalty_start_ts = 0
    
    rank_codes = [0, 0, 0, 0, 0]
    scroll_y = 0

    base_dir = "images"
    if not os.path.exists(base_dir): os.makedirs(base_dir)
    categories = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    categories.sort()

    while running:
        now = time.time()
        dt = clock.tick(FPS) / 1000.0
        
        # ***로직 수정: 릴레이 작동 중이 아닐 때만 게임 시간 업데이트***
        if not penalty_mode:
            current_game_time = now - game_start_ts
        else:
            # 페널티 중에는 시간을 정지시키고, 페널티 해제 시 정지된 시간만큼 game_start_ts를 조정
            pass

        key_pressed = None
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1: key_pressed = 1
                if event.key == pygame.K_2: key_pressed = 2
                if event.key == pygame.K_3: key_pressed = 3
                if event.key == pygame.K_4: key_pressed = 4
                if event.key == pygame.K_5: key_pressed = 5
                
                if event.key == pygame.K_q:
                    if state == "INPUT_RANK":
                        save_rank(score, rank_codes)
                        state = "RANKING"
                        scroll_y = SCREEN_HEIGHT
                    elif state == "MENU":
                        running = False
                    else:
                        state = "MENU"

        screen.fill(PRIMARY_BG)

        # --- 상태별 로직 ---

        if state == "MENU":
            title = get_font(70).render("촉촉한 스피드 퀴즈게임", True, ACCENT_COLOR)
            sub = get_font(30).render("카테고리를 선택하세요", True, GRAY_TEXT)
            exit_info = get_font(20).render("제한시간 1분안에 주어진 문제를 빠르게 풀고 점수를 획득하세요. 문제를 틀리면 물총이 발사되니 조심하세요!! 한 문제당 10초의 제한시간이 있습니다!", True, GRAY_TEXT)

            screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 150))
            screen.blit(sub, (SCREEN_WIDTH//2 - sub.get_width()//2, 300))
            screen.blit(exit_info, (SCREEN_WIDTH//2 - exit_info.get_width()//2, 600))
            
            if not categories:
                warn = get_font(30).render("'images' 폴더를 찾을 수 없습니다! (카테고리 없음)", True, DANGER_COLOR)
                screen.blit(warn, (SCREEN_WIDTH//2 - warn.get_width()//2, 400))
            else:
                for i, cat in enumerate(categories):
                    if i >= 5: break
                    btn_w = 400
                    btn_h = 60
                    
                    btn = ButtonUI(SCREEN_WIDTH//2 - btn_w//2, 350 + i*(btn_h+25), btn_w, btn_h, cat)
                    
                    if key_pressed == (i + 1):
                        current_category = cat
                        q_list = load_questions(os.path.join(base_dir, cat))
                        
                        score = 0
                        game_start_ts = now # 게임 시작 시각 초기화
                        last_penalty_end_ts = now
                        current_q_data = None
                        state = "GAME"
                    
                    btn.is_hovered = (key_pressed == (i + 1))
                    btn.draw(screen, i+1)

        elif state == "GAME":
            # ***수정: 페널티 중이라면 total_remain 계산을 정지된 시간 기준으로***
            if not penalty_mode:
                total_remain = TOTAL_GAME_TIME - (now - game_start_ts)
            else:
                # 페널티 중에는 현재 진행된 시간(now - game_start_ts)을 사용하여 시간 감소를 멈춤
                # 이 로직은 penalty_mode가 해제될 때 game_start_ts를 조정해야 정확히 작동함.
                # 단순화: 페널티 중에는 total_remain을 고정값으로 설정
                time_elapsed_before_penalty = last_penalty_end_ts - game_start_ts
                total_remain = TOTAL_GAME_TIME - time_elapsed_before_penalty
                
                # Q-time도 정지
                q_start_ts += dt 
                
            if total_remain <= 0: state = "GAMEOVER"; continue
            
            # 1. 다음 문제 로드
            if current_q_data is None:
                if not q_list: state = "GAMEOVER"; continue
                
                current_q_data = q_list.pop(0)
                q_start_ts = now
                penalty_mode = False
                current_q_img = None
                
                if current_q_data["path"]:
                    try:
                        raw_img = pygame.image.load(current_q_data["path"])
                        ih = SCREEN_HEIGHT - 200 
                        scale = ih / raw_img.get_height()
                        iw = int(raw_img.get_width() * scale)
                        current_q_img = pygame.transform.smoothscale(raw_img, (iw, ih))
                    except:
                        print(f"이미지 로드 실패: {current_q_data['path']}")
            
            # 2. 페널티 화면/로직 (릴레이 1초, 화면 1초)
            is_input_blocked = penalty_mode 

            if penalty_mode:
                if now - penalty_start_ts < DISPLAY_PENALTY_TIME:
                    screen.fill(DANGER_COLOR)
                    warn_txt = get_font(80).render("오답입니다!", True, WHITE)
                    screen.blit(warn_txt, (SCREEN_WIDTH//2 - warn_txt.get_width()//2, SCREEN_HEIGHT//2))
                    pygame.display.flip()
                    continue 

                if now - penalty_start_ts >= RELAY_PENALTY_TIME:
                    # 릴레이/페널티 종료 (1.0초 후)
                    
                    # ***핵심 수정: 게임 시간 정지 보정 로직***
                    time_paused = now - penalty_start_ts 
                    game_start_ts += time_paused # 게임 시작 시각을 늦춰 시간을 보정
                    last_penalty_end_ts = now

                    current_q_data = None 
                    penalty_mode = False
                    continue 

            # 3. 문제 시간 초과 체크 (페널티 중이 아닐 때)
            q_remain = Q_TIME_LIMIT - (now - q_start_ts)
            if q_remain <= 0 and not penalty_mode:
                trigger_relay()
                penalty_mode = True
                penalty_start_ts = now
                continue

            # 4. 게임 UI 그리기
            # 상단 상태 바 (디자인 개선)
            pygame.draw.rect(screen, SECONDARY_BG, (0, 0, SCREEN_WIDTH, 90))
            pygame.draw.line(screen, ACCENT_COLOR, (0, 89), (SCREEN_WIDTH, 89), 5) # 구분선

            score_txt = get_font(35).render(f"점수: {score}점", True, WHITE)
            screen.blit(score_txt, (30, 30))
            
            # 전체 타이머 (디자인 개선)
            timer_color = DANGER_COLOR if total_remain < 10 else WARNING_COLOR
            timer_txt = get_font(55).render(f"남은 시간: {int(total_remain)}초", True, timer_color)
            screen.blit(timer_txt, (SCREEN_WIDTH//2 - timer_txt.get_width()//2, 18))
            
            # 문제 제한 타이머
            q_timer_color = DANGER_COLOR if q_remain < 3 else GRAY_TEXT
            q_timer_txt = get_font(30).render(f"문제 제한: {int(q_remain)}초", True, q_timer_color)
            screen.blit(q_timer_txt, (SCREEN_WIDTH - q_timer_txt.get_width() - 30, 35))
            
            # 이미지 영역 또는 빈 화면
            if current_q_img:
                screen.blit(current_q_img, (SCREEN_WIDTH//2 - current_q_img.get_width()//2, 110))
            elif current_q_data:
                box_rect = pygame.Rect(100, 110, SCREEN_WIDTH-200, SCREEN_HEIGHT-220)
                pygame.draw.rect(screen, SECONDARY_BG, box_rect, border_radius=10)
                pygame.draw.rect(screen, GRAY_TEXT, box_rect, 2, border_radius=10)

                dummy_txt = get_font(30).render(f"문제 진행 중 (파일: {current_q_data['filename']})", True, GRAY_TEXT)
                screen.blit(dummy_txt, (SCREEN_WIDTH//2 - dummy_txt.get_width()//2, SCREEN_HEIGHT//2))

            guide = get_font(30).render("정답 입력: [1] ~ [5] 버튼을 누르세요", True, ACCENT_LIGHT)
            screen.blit(guide, (SCREEN_WIDTH//2 - guide.get_width()//2, SCREEN_HEIGHT - 60))

            # 5. 정답 체크
            if key_pressed and not is_input_blocked:
                if key_pressed == current_q_data["answer"]:
                    score += 10
                    current_q_data = None
                else:
                    trigger_relay()
                    penalty_mode = True
                    penalty_start_ts = now
                    # 릴레이 작동 시, Q 타이머 시작 시각을 현재 시각으로 설정하여 Q 타이머도 정지 (1초간)
                    q_start_ts = now 

        elif state == "GAMEOVER":
            screen.fill(PRIMARY_BG)
            t1 = get_font(60).render("게임 종료", True, DANGER_COLOR)
            t2 = get_font(40).render(f"최종 점수: {score}점", True, WHITE)
            t3 = get_font(30).render("코드 등록: [1] 버튼", True, ACCENT_COLOR)
            t4 = get_font(20).render("메인 메뉴: [Q] 버튼", True, GRAY_TEXT)
            
            screen.blit(t1, (SCREEN_WIDTH//2 - t1.get_width()//2, 200))
            screen.blit(t2, (SCREEN_WIDTH//2 - t2.get_width()//2, 300))
            screen.blit(t3, (SCREEN_WIDTH//2 - t3.get_width()//2, 500))
            screen.blit(t4, (SCREEN_WIDTH//2 - t4.get_width()//2, 580))
            
            if key_pressed == 1:
                rank_codes = [0, 0, 0, 0, 0]
                state = "INPUT_RANK"

        elif state == "INPUT_RANK":
            # ... (INPUT_RANK state code remains the same)
            title = get_font(50).render("코드 (5자리 숫자) 입력", True, WHITE)
            screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 100))
            
            box_w, box_h = 120, 160
            gap = 20
            total_w = 5*box_w + 4*gap
            start_x = (SCREEN_WIDTH - total_w) // 2
            
            for i in range(5):
                if key_pressed == (i + 1):
                    rank_codes[i] = (rank_codes[i] + 1) % 10
                
                # UI 개선: 박스 디자인 변경
                rect = pygame.Rect(start_x + i*(box_w+gap), 300, box_w, box_h)
                pygame.draw.rect(screen, SECONDARY_BG, rect, border_radius=10)
                pygame.draw.rect(screen, ACCENT_COLOR, rect, 3, border_radius=10)

                num = get_font(90).render(str(rank_codes[i]), True, WHITE)
                screen.blit(num, (rect.centerx - num.get_width()//2, rect.centery - num.get_height()//2))
                
                btn_lbl = get_font(25).render(f"버튼 {i+1}", True, WARNING_COLOR)
                screen.blit(btn_lbl, (rect.centerx - btn_lbl.get_width()//2, rect.bottom + 15))
            
            save_msg = get_font(30).render("저장 및 랭킹 보기: [Q] 버튼", True, DANGER_COLOR)
            screen.blit(save_msg, (SCREEN_WIDTH//2 - save_msg.get_width()//2, 600))

        elif state == "RANKING":
            screen.fill(PRIMARY_BG)
            title = get_font(50).render("명예의 전당", True, ACCENT_LIGHT)
            pygame.draw.line(screen, ACCENT_COLOR, (SCREEN_WIDTH//2 - title.get_width()//2, 110), (SCREEN_WIDTH//2 + title.get_width()//2, 110), 3) # 구분선
            screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 50))
            
            ranks = load_ranks()
            content_h = len(ranks) * 60
            
            # 스크롤 로직
            if content_h > SCREEN_HEIGHT - 200:
                scroll_y -= 1
                if scroll_y < -(content_h): scroll_y = SCREEN_HEIGHT
            else: scroll_y = 150

            clip_area = pygame.Rect(0, 130, SCREEN_WIDTH, SCREEN_HEIGHT - 130)
            screen.set_clip(clip_area)
            
            # 랭킹 목록 (디자인 개선)
            for i, r in enumerate(ranks):
                y = scroll_y + i*60
                
                c = WHITE
                if i == 0: c = WARNING_COLOR 
                elif i == 1: c = GRAY_TEXT 
                elif i == 2: c = DANGER_COLOR 
                
                row_str = f"#{i+1}위.   코드: [{r['code']}]   점수: {r['score']}점"
                row_surf = get_font(40).render(row_str, True, c)
                
                # 배경 박스로 리스트 구분
                list_bg_rect = pygame.Rect(SCREEN_WIDTH//2 - 350, y - 5, 700, 50)
                pygame.draw.rect(screen, SECONDARY_BG if i % 2 == 0 else PRIMARY_BG, list_bg_rect, border_radius=5)

                screen.blit(row_surf, (SCREEN_WIDTH//2 - row_surf.get_width()//2, y))
            
            screen.set_clip(None)
            
            nav = get_font(20).render("메인 메뉴로: [Q]", True, GRAY_TEXT)
            screen.blit(nav, (20, 20))


        pygame.display.flip()

    pygame.quit() 

if __name__ == "__main__":
    main()