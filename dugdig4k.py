# dig_dug_one_shot.py
# Single-file Dig Dug-inspired game — 60 FPS, no files, retro vibes.
# Requires: pip install pygame
# Run: python dig_dug_one_shot.py

import pygame as pg
import random, math, sys, threading

# ---------- Beeps/boops (winsound on Windows; safe fallback elsewhere) ----------
def _noop(*a, **k): pass
try:
    import winsound
    def tone(freq=440, ms=60):
        try: winsound.Beep(int(freq), int(ms))
        except Exception: pass
    def play_seq(seq):
        def run():
            for f, d in seq:
                tone(f, d)
        threading.Thread(target=run, daemon=True).start()
except Exception:
    tone = _noop
    play_seq = lambda seq: None

def sfx(tag):
    if tag == 'dig':      tone(140, 18)
    elif tag == 'pump':   tone(320, 35)
    elif tag == 'pop':    play_seq([(660, 80), (880, 120)])
    elif tag == 'rock':   play_seq([(200, 70), (180, 70), (160, 120)])
    elif tag == 'crush':  tone(120, 200)
    elif tag == 'death':  play_seq([(200, 200), (160, 200), (120, 240)])
    elif tag == 'level':  play_seq([(520, 110), (660, 110), (780, 160)])
    elif tag == 'bonus':  play_seq([(900, 90), (760, 90), (900, 120)])
    elif tag == 'fire':   tone(520, 80)

# ---------- Config ----------
RENDER_W, RENDER_H = 224, 288
SCALE = 3
WIN_W, WIN_H = RENDER_W * SCALE, RENDER_H * SCALE
FPS = 60

TILE = 8
GRID_W, GRID_H = RENDER_W // TILE, RENDER_H // TILE

BG = (16, 18, 20)
LAYER_COLORS = [(60,48,32),(52,40,30),(46,36,28),(40,32,26)]
TUNNEL = (20, 22, 24)
PLAYER_COL = (230, 230, 230)
POOKA_COL = (240, 60, 60)
FYGAR_COL = (60, 200, 90)
GHOST_COL = (170, 170, 220)
ROCK_COL = (90, 90, 110)
FIRE_COL = (255, 180, 70)
BONUS_COL = (230, 210, 80)
UI = (180, 210, 190)

PLAYER_SPEED = 6.5
ENEMY_BASE_SPEED = 2.6
PUMP_TICKS_TO_POP = 4
FYGAR_FIRE_TIME = 0.9
FYGAR_FIRE_LEN = 6
ROCK_JIGGLE_TIME = 0.6
ROCK_FALL_SPEED = 14
ROCK_MIN_FALL_FOR_SCORE = 2
START_LIVES = 3

def clamp(v, lo, hi): return max(lo, min(hi, v))
def sgn(v): return -1 if v < 0 else 1 if v > 0 else 0
def dist_sq(x1, y1, x2, y2): return (x1-x2)**2 + (y1-y2)**2
def ps1_jitter(t, phase=0.0, amp=0.6): return math.sin(t * 7.3 + phase) * amp

# ---------- World ----------
class World:
    def __init__(self):
        self.level = 1
        self.score = 0
        self.lives = START_LIVES
        self.rocks_dropped = 0
        self.bonus = None
        self.grid = [[1 for _ in range(GRID_W)] for _ in range(GRID_H)]  # 1=dirt, 0=tunnel, 2=rock
        self.rocks = []
        self.enemies = []
        self.player = None
        self.state = 'playing'   # 'playing','dead','level_cleared','game_over','paused'
        self.state_timer = 0.0

    def reset_level(self):
        self.grid = [[1 for _ in range(GRID_W)] for _ in range(GRID_H)]
        for y in range(2):
            for x in range(GRID_W):
                self.grid[y][x] = 0
        px, py = GRID_W // 2, 1
        self.player = Player(px + 0.5, py + 0.5)

        self.rocks = []
        rock_count = clamp(4 + self.level // 2, 4, 14)
        trials = 0
        while len(self.rocks) < rock_count and trials < 1000:
            trials += 1
            x = random.randint(2, GRID_W-3)
            y = random.randint(5, GRID_H-3)
            if self.grid[y][x] == 1:
                self.rocks.append({'x': x, 'y': y, 'fall': False, 'jiggle': 0.0, 'fall_dist': 0})
                self.grid[y][x] = 2

        self.enemies = []
        n_enemies = clamp(5 + (self.level-1), 5, 18)
        fygar_ratio = clamp(0.2 + 0.02*self.level, 0.2, 0.45)
        for _ in range(n_enemies):
            t = 'fygar' if random.random() < fygar_ratio else 'pooka'
            spawn_tries = 0
            while spawn_tries < 1000:
                spawn_tries += 1
                x = random.choice([random.randint(2, 6), random.randint(GRID_W-7, GRID_W-3)])
                y = random.randint(GRID_H//2, GRID_H-4)
                if self.grid[y][x] == 1 and all((e.tx != x or e.ty != y) for e in self.enemies):
                    break
            e = Enemy(t, x + 0.5, y + 0.5)
            self.grid[y][x] = 0
            self.enemies.append(e)

        self.rocks_dropped = 0
        self.bonus = None
        self.state = 'playing'
        self.state_timer = 0.0
        sfx('level')

    def carve_at(self, cx, cy):
        gx, gy = int(cx), int(cy)
        if 0 <= gy < GRID_H and 0 <= gx < GRID_W and self.grid[gy][gx] == 1:
            self.grid[gy][gx] = 0
            sfx('dig')

    def is_tunnel(self, gx, gy):
        return 0 <= gy < GRID_H and 0 <= gx < GRID_W and self.grid[gy][gx] == 0

    def rock_at(self, gx, gy):
        for r in self.rocks:
            if int(r['x']) == gx and int(r['y']) == gy:
                return r
        return None

# ---------- Player ----------
class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.dx, self.dy = 1, 0
        self.pumping = False
        self.pump_target = None
        self.pump_tick_timer = 0.0

# ---------- Enemy ----------
class Enemy:
    def __init__(self, typ, x, y):
        self.typ = typ
        self.x, self.y = x, y
        self.dx, self.dy = -1, 0
        self.ghost = False
        self.inflate = 0
        self.alive = True
        self.fire_timer = 0.0
        self.fire_dir = 0
        self.ghost_cooldown = random.uniform(1.0, 2.4)
        self.turn_timer = 0.0

    @property
    def tx(self): return int(self.x)
    @property
    def ty(self): return int(self.y)

# ---------- Game setup/helpers ----------
def reset_game(world):
    world.level = 1
    world.score = 0
    world.lives = START_LIVES
    world.reset_level()

def dir_from_keys():
    keys = pg.key.get_pressed()
    dx = (keys[pg.K_RIGHT] or keys[pg.K_d]) - (keys[pg.K_LEFT] or keys[pg.K_a])
    dy = (keys[pg.K_DOWN] or keys[pg.K_s]) - (keys[pg.K_UP] or keys[pg.K_w])
    if abs(dx) > abs(dy): return sgn(dx), 0
    if abs(dy) > 0: return 0, sgn(dy)
    return 0, 0

def line_of_sight(world, sx, sy, dx, dy, max_len=6):
    cx, cy = int(sx), int(sy)
    for _ in range(1, max_len+1):
        cx += dx; cy += dy
        if cx < 0 or cy < 0 or cx >= GRID_W or cy >= GRID_H:
            return None, 0
        if world.grid[cy][cx] != 0:
            return None, 0
        for e in world.enemies:
            if e.alive and not e.ghost and int(e.x) == cx and int(e.y) == cy:
                return e, 1
    return None, 0

def player_die(world):
    if world.state != 'playing': return
    world.lives -= 1
    world.state = 'dead'
    world.state_timer = 1.2
    sfx('death')

# ---------- Update ----------
def update_player(world, dt):
    p = world.player
    if world.state != 'playing': return

    mdx, mdy = dir_from_keys()
    if mdx or mdy:
        p.dx, p.dy = mdx, mdy
        speed = PLAYER_SPEED * dt
        nx = p.x + mdx * speed
        ny = p.y + mdy * speed
        world.carve_at(p.x, p.y)
        world.carve_at(nx, ny)
        if world.rock_at(int(nx), int(ny)) is None:
            p.x, p.y = nx, ny

    keys = pg.key.get_pressed()
    if keys[pg.K_SPACE]:
        if not p.pumping:
            enemy, _ = line_of_sight(world, p.x, p.y, p.dx, p.dy)
            if enemy:
                p.pumping = True
                p.pump_target = enemy
                p.pump_tick_timer = 0.0
        else:
            e, _ = line_of_sight(world, p.x, p.y, p.dx, p.dy)
            if e is p.pump_target:
                p.pump_tick_timer += dt
                if p.pump_tick_timer >= 0.18:
                    p.pump_tick_timer = 0.0
                    e.inflate += 1
                    sfx('pump')
                    if e.inflate >= PUMP_TICKS_TO_POP:
                        e.alive = False
                        world.score += 200
                        sfx('pop')
                        p.pumping = False
                        p.pump_target = None
            else:
                p.pumping = False
                p.pump_target = None
    else:
        p.pumping = False
        p.pump_target = None

def update_enemies(world, dt):
    if world.state != 'playing': return
    px, py = world.player.x, world.player.y
    base_speed = ENEMY_BASE_SPEED + 0.15*(world.level-1)

    for e in world.enemies:
        if not e.alive: continue

        if e.inflate > 0 and (world.player.pump_target is not e):
            e.inflate = max(0, e.inflate - dt * 1.2)

        if e.typ == 'fygar' and not e.ghost and e.fire_timer <= 0:
            if int(e.y) == int(py) and 0 <= int(e.y) < GRID_H:
                direction = sgn(px - e.x)
                if direction != 0:
                    clear = True
                    cx = int(e.x)
                    for _ in range(FYGAR_FIRE_LEN):
                        cx += direction
                        if cx < 0 or cx >= GRID_W: break
                        if not (0 <= cx < GRID_W and 0 <= int(e.y) < GRID_H and world.grid[int(e.y)][cx] == 0):
                            clear = False; break
                    if clear and random.random() < 0.006 + 0.001 * world.level:
                        e.fire_timer = FYGAR_FIRE_TIME
                        e.fire_dir = direction
                        sfx('fire')

        if e.fire_timer > 0:
            e.fire_timer -= dt
            if int(e.y) == int(py):
                left = min(int(e.x), int(e.x) + e.fire_dir * FYGAR_FIRE_LEN)
                right = max(int(e.x), int(e.x) + e.fire_dir * FYGAR_FIRE_LEN)
                if left <= int(px) <= right:
                    player_die(world)
            continue

        e.ghost_cooldown -= dt
        if e.ghost:
            speed = base_speed * 1.05
            vx = clamp(px - e.x, -1, 1)
            vy = clamp(py - e.y, -1, 1)
            if abs(px - e.x) > abs(py - e.y):
                e.x += sgn(vx) * speed * dt
            else:
                e.y += sgn(vy) * speed * dt
            if 0 <= int(e.x) < GRID_W and 0 <= int(e.y) < GRID_H and world.grid[int(e.y)][int(e.x)] == 0:
                e.ghost = False
                e.ghost_cooldown = random.uniform(1.0, 2.0)
        else:
            if e.ghost_cooldown <= 0 and random.random() < clamp(0.002 + 0.0007*world.level, 0.002, 0.02):
                e.ghost = True
                e.ghost_cooldown = random.uniform(1.2, 2.2)
                continue

            speed = base_speed * (1.0 + 0.05*random.random())
            e.turn_timer -= dt
            if e.turn_timer <= 0:
                candidates = []
                for (dx, dy) in [(1,0),(-1,0),(0,1),(0,-1)]:
                    nx, ny = int(e.x + dx), int(e.y + dy)
                    if 0 <= nx < GRID_W and 0 <= ny < GRID_H and world.grid[ny][nx] == 0:
                        candidates.append((dx, dy))
                if candidates:
                    candidates.sort(key=lambda d: abs((e.x + d[0]) - px) + abs((e.y + d[1]) - py))
                    if len(candidates) > 1 and random.random() < 0.2:
                        random.shuffle(candidates)
                    e.dx, e.dy = candidates[0]
                    e.turn_timer = 0.2 + random.random()*0.6

            nx = e.x + e.dx * speed * dt
            ny = e.y + e.dy * speed * dt
            gx, gy = int(nx), int(ny)
            if 0 <= gx < GRID_W and 0 <= gy < GRID_H and world.grid[gy][gx] == 0:
                e.x, e.y = nx, ny
            else:
                e.dx, e.dy = -e.dx, -e.dy

        if e.alive and dist_sq(e.x, e.y, px, py) < 0.40 and not world.player.pumping:
            player_die(world)

def update_rocks(world, dt):
    if world.state != 'playing': return
    for r in world.rocks:
        gx, gy = int(r['x']), int(r['y'])
        if not r['fall']:
            below = gy+1
            if below >= GRID_H: continue
            supported = (world.grid[below][gx] in (1,2))
            if not supported:
                r['jiggle'] += dt
                if r['jiggle'] >= ROCK_JIGGLE_TIME:
                    r['fall'] = True
                    r['jiggle'] = 0.0
                    sfx('rock')
            else:
                r['jiggle'] = 0.0
        else:
            r['y'] += ROCK_FALL_SPEED * dt
            top = int(r['y'])
            for e in world.enemies:
                if e.alive and int(e.x) == gx and int(e.y) == top:
                    e.alive = False
                    sfx('crush')
                    pts = 500 if r['fall_dist'] >= ROCK_MIN_FALL_FOR_SCORE else 100
                    world.score += pts
            if int(world.player.x) == gx and int(world.player.y) == top:
                player_die(world)

            gy2 = int(r['y'])
            if gy2+1 >= GRID_H or world.grid[gy2+1][gx] in (1,2):
                r['y'] = float(gy2)
                if r['fall_dist'] >= 2:
                    world.rocks_dropped += 1
                r['fall'] = False
                world.grid[gy2][gx] = 2
                sfx('rock')
            else:
                r['fall_dist'] += 1
                if 0 <= gy2 < GRID_H:
                    world.grid[gy2][gx] = 0

def maybe_spawn_bonus(world):
    if world.bonus is not None or world.rocks_dropped < 2: return
    cx, cy = GRID_W//2, GRID_H//2 + random.randint(-3, 3)
    if world.grid[cy][cx] == 1:
        world.grid[cy][cx] = 0
    world.bonus = {'x': cx, 'y': cy, 'timer': 10.0}
    sfx('bonus')

def update_bonus(world, dt):
    if world.bonus is None: return
    world.bonus['timer'] -= dt
    if world.bonus['timer'] <= 0:
        world.bonus = None
        return
    if int(world.player.x) == world.bonus['x'] and int(world.player.y) == world.bonus['y']:
        world.score += 1000
        world.bonus = None
        sfx('bonus')

def step_world(world, dt):
    if world.state == 'paused': return

    if world.state == 'dead':
        world.state_timer -= dt
        if world.state_timer <= 0:
            if world.lives < 0:
                world.state = 'game_over'
            else:
                world.reset_level()
        return

    if world.state == 'level_cleared':
        world.state_timer -= dt
        if world.state_timer <= 0:
            world.level += 1
            world.reset_level()
        return

    if world.state == 'game_over': return

    update_player(world, dt)
    update_enemies(world, dt)
    update_rocks(world, dt)
    maybe_spawn_bonus(world)
    update_bonus(world, dt)

    if all((not e.alive) for e in world.enemies):
        world.state = 'level_cleared'
        world.state_timer = 1.5

# ---------- Render ----------
def draw_world(surf, world, t):
    surf.fill(BG)
    layer_h = GRID_H // len(LAYER_COLORS)
    for y in range(GRID_H):
        for x in range(GRID_W):
            rect = pg.Rect(x*TILE, y*TILE, TILE, TILE)
            if world.grid[y][x] == 1:
                layer_idx = clamp(y // layer_h, 0, len(LAYER_COLORS)-1)
                pg.draw.rect(surf, LAYER_COLORS[layer_idx], rect)
            else:
                pg.draw.rect(surf, TUNNEL, rect)

    for r in world.rocks:
        rx = int(r['x']*TILE); ry = int(r['y']*TILE)
        if not r['fall'] and r['jiggle'] > 0:
            rx += int(2*math.sin(28*r['jiggle']))
        pg.draw.rect(surf, ROCK_COL, (rx, ry, TILE, TILE))
        pg.draw.rect(surf, (130,130,150), (rx+2, ry+2, TILE-4, TILE-4), 1)

    for e in world.enemies:
        if not e.alive: continue
        col = GHOST_COL if e.ghost else (FYGAR_COL if e.typ=='fygar' else POOKA_COL)
        ex = int(e.x*TILE); ey = int(e.y*TILE)
        size = TILE-1 + int(e.inflate)
        jitter = int(ps1_jitter(t, 0.5, 0.4))
        rect = pg.Rect(ex - size//2 + jitter, ey - size//2, size, size)
        pg.draw.rect(surf, col, rect)
        pg.draw.rect(surf, (0,0,0), rect, 1)
        if e.fire_timer > 0:
            for i in range(1, FYGAR_FIRE_LEN+1):
                xx = int((e.x + e.fire_dir*i)*TILE)
                rr = pg.Rect(xx - TILE//2, ey - TILE//2, TILE, TILE)
                pg.draw.rect(surf, FIRE_COL, rr)

    p = world.player
    if p.pumping and p.pump_target and p.pump_target.alive:
        hx, hy = int(p.x), int(p.y)
        tx, ty = int(p.pump_target.x), int(p.pump_target.y)
        cx, cy = hx, hy
        for _ in range(12):
            cx += p.dx; cy += p.dy
            if cx == tx and cy == ty: break
            pg.draw.rect(surf, (230,200,200), (cx*TILE+TILE//4, cy*TILE+TILE//4, TILE//2, TILE//2))

    px = int(world.player.x*TILE); py = int(world.player.y*TILE)
    jitter = int(ps1_jitter(t, 0.8, 0.4))
    p_rect = pg.Rect(px - TILE//2 + jitter, py - TILE//2, TILE, TILE)
    pg.draw.rect(surf, PLAYER_COL, p_rect)
    pg.draw.rect(surf, (0,0,0), p_rect, 1)

    if world.bonus:
        bx, by = world.bonus['x'], world.bonus['y']
        rect = pg.Rect(bx*TILE, by*TILE, TILE, TILE)
        pg.draw.rect(surf, BONUS_COL, rect)
        pg.draw.rect(surf, (120,80,20), rect, 1)

def draw_ui(surf, world, font, bigfont):
    hud = f"SCORE {world.score:06d}   LIVES {max(0, world.lives)}   LEVEL {world.level}"
    text = font.render(hud, True, UI)
    surf.blit(text, (6, 4))
    if world.state in ('paused','game_over','level_cleared','dead'):
        overlay = pg.Surface((RENDER_W, RENDER_H), pg.SRCALPHA)
        overlay.fill((0,0,0,160))
        surf.blit(overlay, (0,0))
        if world.state == 'paused':
            t1 = bigfont.render("PAUSED", True, (230,230,230))
            t2 = font.render("Press P to resume", True, (200,200,200))
            surf.blit(t1, center_text(t1, RENDER_W, RENDER_H, -12))
            surf.blit(t2, center_text(t2, RENDER_W, RENDER_H, 12))
        elif world.state == 'game_over':
            t1 = bigfont.render("GAME OVER", True, (230,230,230))
            t2 = font.render("Press Enter to restart", True, (200,200,200))
            surf.blit(t1, center_text(t1, RENDER_W, RENDER_H, -12))
            surf.blit(t2, center_text(t2, RENDER_W, RENDER_H, 12))
        elif world.state == 'level_cleared':
            t1 = bigfont.render("LEVEL CLEAR!", True, (230,230,230))
            surf.blit(t1, center_text(t1, RENDER_W, RENDER_H, 0))
        elif world.state == 'dead':
            t1 = bigfont.render("Ouch!", True, (230,230,230))
            surf.blit(t1, center_text(t1, RENDER_W, RENDER_H, 0))

def center_text(text_surf, w, h, dy=0):
    return ((w - text_surf.get_width())//2, (h - text_surf.get_height())//2 + dy)

def draw_scanlines(surf):
    sl = pg.Surface((RENDER_W, 1), pg.SRCALPHA)
    sl.fill((0, 0, 0, 26))
    for y in range(0, RENDER_H, 2):
        surf.blit(sl, (0, y))

# ---------- Main ----------
def main():
    pg.init()
    pg.display.set_caption("Dig Dug — one shot | 60 FPS | no files")
    window = pg.display.set_mode((WIN_W, WIN_H))
    clock = pg.time.Clock()
    canvas = pg.Surface((RENDER_W, RENDER_H))

    font = pg.font.SysFont(None, 16)
    bigfont = pg.font.SysFont(None, 28)

    world = World()
    reset_game(world)

    t = 0.0
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt
        for e in pg.event.get():
            if e.type == pg.QUIT:
                running = False
            elif e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE:
                    running = False
                elif e.key == pg.K_p and world.state != 'game_over':
                    world.state = 'paused' if world.state != 'paused' else 'playing'
                elif e.key == pg.K_RETURN and world.state == 'game_over':
                    reset_game(world)

        step_world(world, dt)

        canvas.fill(BG)
        draw_world(canvas, world, t)
        draw_ui(canvas, world, font, bigfont)
        draw_scanlines(canvas)

        jitter_x = int(ps1_jitter(t, 0.3, 1.0))
        jitter_y = int(ps1_jitter(t, 1.1, 1.0))
        surf = pg.transform.scale(canvas, (WIN_W, WIN_H))
        window.fill((0,0,0))
        window.blit(surf, (jitter_x, jitter_y))
        pg.display.flip()

    pg.quit()
    sys.exit()

if __name__ == "__main__":
    main()
