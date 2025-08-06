# retro_pong_ps1.py
# Single-file Retro Pong with PS1 vibes, AI right paddle, mouse left, win at 5.
# Beeps/boops via winsound on Windows (fallback safe).
# Requires: pip install pygame

import pygame as pg
import math, random, threading, sys

# -------- Beeps 'n boops (Windows winsound if available) --------
def _noop(*a, **k): pass
try:
    import winsound
    def tone(freq=440, ms=60):
        try:
            winsound.Beep(int(freq), int(ms))
        except Exception:
            pass
    def play_seq(seq):
        def run():
            for f, d in seq:
                tone(f, d)
        threading.Thread(target=run, daemon=True).start()
except Exception:
    tone = _noop
    play_seq = lambda seq: None

def sfx(event):
    if event == 'paddle':
        tone(220, 40)      # boop
    elif event == 'wall':
        tone(440, 35)      # beep
    elif event == 'score':
        tone(660, 120)     # brighter beep
    elif event == 'win':
        play_seq([(880, 120), (660, 120), (990, 160)])  # little jingle

# -------- Config --------
RENDER_W, RENDER_H = 320, 240    # low-res render target
SCALE = 3                        # window scale (nearest-neighbor)
WIN_W, WIN_H = RENDER_W * SCALE, RENDER_H * SCALE
FPS = 60

BG = (30, 34, 30)                # PS1-ish dark greenish grey
FG = (220, 220, 220)             # light grey for paddles/ball
ACCENT = (160, 200, 180)         # UI accent
SCANLINE_ALPHA = 28               # scanline darkness (0-255)

PADDLE_W, PADDLE_H = 6, 34
BALL_SIZE = 6
LEFT_X = 14
RIGHT_X = RENDER_W - 14 - PADDLE_W

AI_MAX_SPEED = 120               # px/sec (AI tracking limit)
AI_REACTION = 0.08               # seconds delay (light inertia)
BALL_SPEED_INIT = 130            # px/sec base
BALL_SPEED_GAIN = 1.07           # speedup per paddle hit
BALL_MAX_SPEED = 420

WIN_SCORE = 5

# -------- Helpers --------
def clamp(v, lo, hi): return max(lo, min(hi, v))

def draw_scanlines(surf):
    # Subtle horizontal scanlines
    sl = pg.Surface((RENDER_W, 1), pg.SRCALPHA)
    sl.fill((0, 0, 0, SCANLINE_ALPHA))
    for y in range(0, RENDER_H, 2):
        surf.blit(sl, (0, y))

def ps1_jitter(t, phase=0.0, amp=0.6):
    # Tiny subpixel wobble for PS1-era "shimmer"
    return math.sin(t * 7.3 + phase) * amp

def reset_ball(serving_left=True):
    angle = random.uniform(-0.6, 0.6)
    speed = BALL_SPEED_INIT
    vx = speed * (1 if serving_left else -1)
    vy = speed * math.tan(angle)
    return [RENDER_W/2, RENDER_H/2, vx, vy, speed]

def serve_toward_left(last_scorer):
    # If right scored, serve left; else serve right
    return last_scorer == 'right'

# -------- Main --------
def main():
    pg.init()
    pg.display.set_caption("Retro Pong | vibes=ON | winner winner chicken dinner")
    flags = pg.SCALED  # SDL2 scaled; we still do manual scale for crisp pixels
    window = pg.display.set_mode((WIN_W, WIN_H), flags)
    clock = pg.time.Clock()

    # Offscreen low-res surface
    canvas = pg.Surface((RENDER_W, RENDER_H))

    # State
    left_y = (RENDER_H - PADDLE_H) / 2
    right_y = (RENDER_H - PADDLE_H) / 2
    ai_target_y = right_y
    left_score = 0
    right_score = 0
    last_scorer = None
    bx, by, vx, vy, bspeed = reset_ball(serving_left=True)

    running = True
    game_over = False
    t = 0.0
    ai_timer = 0.0

    # Fonts (use default; low-res)
    font = pg.font.SysFont(None, 16)
    big_font = pg.font.SysFont(None, 28)

    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt
        for e in pg.event.get():
            if e.type == pg.QUIT:
                running = False
            elif e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE:
                    running = False
                if game_over:
                    if e.key == pg.K_y:
                        # Restart
                        left_score = right_score = 0
                        bx, by, vx, vy, bspeed = reset_ball(serving_left=True)
                        game_over = False
                    elif e.key == pg.K_n:
                        running = False

        # Update only if not game over
        if not game_over:
            # Left paddle follows mouse Y
            my = pg.mouse.get_pos()[1]
            # Convert window Y to canvas Y
            canvas_y = my / SCALE
            left_y = clamp(canvas_y - PADDLE_H/2, 0, RENDER_H - PADDLE_H)

            # AI updates with a tiny reaction lag
            ai_timer += dt
            if ai_timer >= AI_REACTION:
                ai_timer = 0.0
                # Predict simple future ball position when moving toward AI
                predict = by
                if vx > 0:
                    # Time until x reaches right paddle
                    time_to_paddle = (RIGHT_X - bx) / max(vx, 1e-6)
                    predict = by + vy * max(0.0, time_to_paddle)
                    # Reflect off top/bottom in prediction domain to stay in bounds
                    # Simulate naive reflections
                    if time_to_paddle > 0:
                        sim = predict
                        period = (RENDER_H - BALL_SIZE)
                        bounces = int(abs(sim) // period)
                        if predict < 0 or predict > RENDER_H - BALL_SIZE:
                            # Mirror to range
                            sim = abs(sim) % (2*period)
                            if sim > period:
                                sim = 2*period - sim
                        predict = clamp(sim, 0, RENDER_H - BALL_SIZE)
                ai_target_y = clamp(predict - PADDLE_H/2, 0, RENDER_H - PADDLE_H)

            # Move AI with capped speed
            if right_y < ai_target_y:
                right_y = min(right_y + AI_MAX_SPEED*dt, ai_target_y)
            elif right_y > ai_target_y:
                right_y = max(right_y - AI_MAX_SPEED*dt, ai_target_y)

            # Move ball
            bx += vx * dt
            by += vy * dt

            # Wall collision
            if by <= 0:
                by = 0
                vy = abs(vy)
                sfx('wall')
            elif by + BALL_SIZE >= RENDER_H:
                by = RENDER_H - BALL_SIZE
                vy = -abs(vy)
                sfx('wall')

            # Paddle rects
            lrect = pg.Rect(LEFT_X, int(left_y), PADDLE_W, PADDLE_H)
            rrect = pg.Rect(RIGHT_X, int(right_y), PADDLE_W, PADDLE_H)
            brect = pg.Rect(int(bx), int(by), BALL_SIZE, BALL_SIZE)

            # Left paddle collision
            if brect.colliderect(lrect) and vx < 0:
                bx = lrect.right
                vx = abs(vx)
                # Add spin based on hit position
                offset = (by + BALL_SIZE/2) - (left_y + PADDLE_H/2)
                vy = vy + offset * 5
                # Speed up
                speed = min(math.hypot(vx, vy) * BALL_SPEED_GAIN, BALL_MAX_SPEED)
                angle = math.atan2(vy, vx)
                vx, vy = math.cos(angle)*speed, math.sin(angle)*speed
                sfx('paddle')

            # Right paddle collision
            if brect.colliderect(rrect) and vx > 0:
                bx = rrect.left - BALL_SIZE
                vx = -abs(vx)
                offset = (by + BALL_SIZE/2) - (right_y + PADDLE_H/2)
                vy = vy + offset * 5
                speed = min(math.hypot(vx, vy) * BALL_SPEED_GAIN, BALL_MAX_SPEED)
                angle = math.atan2(vy, vx)
                vx, vy = math.cos(angle)*speed, math.sin(angle)*speed
                sfx('paddle')

            # Scoring
            scored = None
            if bx + BALL_SIZE < 0:
                right_score += 1
                last_scorer = 'right'
                sfx('score')
                bx, by, vx, vy, bspeed = reset_ball(serving_left=serve_toward_left(last_scorer))
            elif bx > RENDER_W:
                left_score += 1
                last_scorer = 'left'
                sfx('score')
                bx, by, vx, vy, bspeed = reset_ball(serving_left=serve_toward_left(last_scorer))

            # Win condition
            if left_score >= WIN_SCORE or right_score >= WIN_SCORE:
                game_over = True
                sfx('win')

        # -------- Render low-res canvas --------
        canvas.fill(BG)

        # Midline with jitter
        jitter = ps1_jitter(t, phase=0.0, amp=0.4)
        for y in range(0, RENDER_H, 8):
            pg.draw.line(canvas, (70, 90, 80), (RENDER_W//2 + int(jitter), y), (RENDER_W//2 + int(jitter), y+4))

        # Paddles (slight wobble)
        wob_l = int(ps1_jitter(t, phase=0.7, amp=0.6))
        wob_r = int(ps1_jitter(t, phase=1.4, amp=0.6))
        pg.draw.rect(canvas, FG, (LEFT_X + wob_l, int(left_y), PADDLE_W, PADDLE_H))
        pg.draw.rect(canvas, FG, (RIGHT_X + wob_r, int(right_y), PADDLE_W, PADDLE_H))

        # Ball (slight wobble)
        wob_bx = int(ps1_jitter(t, phase=0.3, amp=0.6))
        wob_by = int(ps1_jitter(t, phase=1.1, amp=0.6))
        pg.draw.rect(canvas, FG, (int(bx)+wob_bx, int(by)+wob_by, BALL_SIZE, BALL_SIZE))

        # Scores
        ls = big_font.render(str(left_score), True, ACCENT)
        rs = big_font.render(str(right_score), True, ACCENT)
        canvas.blit(ls, (RENDER_W*0.25 - ls.get_width()/2, 8))
        canvas.blit(rs, (RENDER_W*0.75 - rs.get_width()/2, 8))

        # Header / vibe tag
        tag = font.render("vibes=ON | ai:right  mouse:left | first to 5", True, (120, 150, 130))
        canvas.blit(tag, (8, RENDER_H - 18))

        # Scanlines
        draw_scanlines(canvas)

        # Game over overlay
        if game_over:
            overlay = pg.Surface((RENDER_W, RENDER_H), pg.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            canvas.blit(overlay, (0, 0))

            winner = "LEFT" if left_score > right_score else "RIGHT (AI)"
            line1 = big_font.render("WINNER WINNER CHICKEN DINNER!", True, FG)
            line2 = big_font.render(f"{winner} WINS {max(left_score, right_score)}–{min(left_score, right_score)}", True, ACCENT)
            line3 = font.render("Play again? Y/N", True, (200, 200, 200))
            canvas.blit(line1, ((RENDER_W - line1.get_width())//2, RENDER_H//2 - 30))
            canvas.blit(line2, ((RENDER_W - line2.get_width())//2, RENDER_H//2))
            canvas.blit(line3, ((RENDER_W - line3.get_width())//2, RENDER_H//2 + 24))

        # -------- Scale up with crisp pixels --------
        surf = pg.transform.scale(canvas, (WIN_W, WIN_H))
        window.blit(surf, (0, 0))
        pg.display.flip()

    pg.quit()
    sys.exit()

if __name__ == "__main__":
    main()
