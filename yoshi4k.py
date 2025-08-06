import os
import tkinter  # requested; not used for UI
import pygame
import random
import math

# --- Config ---
WIDTH, HEIGHT = 960, 540   # DS-era feel, upscaled
FPS = 60
FILES_OFF = True
VIBES_ON_DEFAULT = True

# Pastel crayon palette
PASTEL = {
    "sky1": (182, 235, 255),
    "sky2": (255, 240, 210),
    "sea1": (120, 190, 235),
    "sea2": (80, 160, 210),
    "isle": (250, 235, 160),
    "shore": (240, 215, 120),
    "grass": (140, 210, 110),
    "hill": (190, 230, 150),
    "tree": (90, 170, 95),
    "cloud": (255, 255, 250),
    "crayon": (30, 40, 60),
}

def lerp(a, b, t): return a + (b - a) * t
def clerp(c1, c2, t): return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))

def draw_scanlines(surface, alpha=36, step=2):
    line = pygame.Surface((surface.get_width(), 1), flags=pygame.SRCALPHA)
    line.fill((0, 0, 0, alpha))
    for y in range(0, surface.get_height(), step):
        surface.blit(line, (0, y))

def draw_lcd_shimmer(surface, t, strength=18):
    w, h = surface.get_size()
    shimmer = pygame.Surface((w, h), pygame.SRCALPHA)
    for x in range(0, w, 2):
        a = int((math.sin(t*3 + x*0.02) * 0.5 + 0.5) * strength)
        pygame.draw.line(shimmer, (255, 255, 255, a), (x, 0), (x, h))
    surface.blit(shimmer, (0, 0), special_flags=pygame.BLEND_PREMULTIPLIED)

def crayon_line(surf, color, pts, width=3, jitter=1.2):
    # multi-pass shaky line
    for pass_i in range(2):
        off = pass_i * 0.8
        jpts = []
        for (x, y) in pts:
            jx = x + random.uniform(-jitter, jitter)
            jy = y + random.uniform(-jitter, jitter)
            jpts.append((jx+off, jy+off))
        pygame.draw.lines(surf, color, False, jpts, width)

def crayon_circle(surf, color, center, radius, width=3):
    cx, cy = center
    pts = []
    for i in range(32):
        ang = i/32.0 * 2*math.pi
        r = radius + random.uniform(-1.5, 1.5)
        x = cx + math.cos(ang)*r
        y = cy + math.sin(ang)*r
        pts.append((x, y))
    crayon_line(surf, color, pts + [pts[0]], width)

def paint_gradient(surf, c1, c2):
    w, h = surf.get_size()
    for y in range(h):
        t = y/(h-1)
        col = clerp(c1, c2, t)
        pygame.draw.line(surf, col, (0, y), (w, y))

def make_cloud_layer(w, h, seed, count, speed, amp):
    rng = random.Random(seed)
    clouds = []
    for _ in range(count):
        cx = rng.uniform(0, w)
        cy = rng.uniform(0, h*0.6)
        scale = rng.uniform(0.6, 1.6)
        drift = rng.uniform(0.3, 1.2)
        clouds.append([cx, cy, scale, drift])
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    def draw(s, t, camx):
        s.fill((0,0,0,0))
        for i, (cx, cy, sc, drift) in enumerate(clouds):
            x = (cx - camx*speed + t*10*drift) % (w + 200) - 100
            y = cy + math.sin((x + i*37)*0.01 + t*0.8)*amp
            draw_cloud_blob(s, (x, y), sc)
        return s
    return surf, draw

def draw_cloud_blob(surf, pos, scale):
    x, y = pos
    base = int(24 * scale)
    col = PASTEL["cloud"]
    for i in range(5):
        dx = math.cos(i*1.2) * base
        dy = math.sin(i*0.9) * base*0.4
        r = base * (1.1 - i*0.12)
        pygame.draw.circle(surf, col, (int(x+dx), int(y+dy)), int(r))
    crayon_circle(surf, PASTEL["crayon"], (int(x), int(y)), int(base*1.4), width=2)

def make_horizon(w, h):
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    # sky gradient
    paint_gradient(surf, PASTEL["sky1"], PASTEL["sky2"])
    return surf

def make_sea_layer(w, h, seed, speed):
    rng = random.Random(seed)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    # base gradient
    sea = pygame.Surface((w, h), pygame.SRCALPHA)
    paint_gradient(sea, PASTEL["sea1"], PASTEL["sea2"])
    # waves lines
    waves = []
    for i in range(50):
        y = rng.uniform(h*0.4, h*0.95)
        amp = rng.uniform(3, 10)
        freq = rng.uniform(0.01, 0.03)
        waves.append((y, amp, freq))
    def draw(s, t, camx):
        s.blit(sea, (0, 0))
        for (y0, amp, freq) in waves:
            pts = []
            for x in range(0, w, 8):
                y = y0 + math.sin(x*freq + t*1.5 + camx*0.02)*amp
                pts.append((x, y))
            crayon_line(s, (255,255,255), pts, width=2, jitter=0.6)
        return s
    return surf, draw

def make_island_layer(w, h, seed, speed):
    rng = random.Random(seed)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    blobs = []
    for i in range(3):
        bx = rng.uniform(w*0.2, w*0.8) + i*200
        by = rng.uniform(h*0.5, h*0.75)
        br = rng.uniform(120, 220)
        blobs.append((bx, by, br))
    hills = []
    for i in range(6):
        hx = rng.uniform(w*0.0, w*1.2)
        hy = rng.uniform(h*0.45, h*0.7)
        hr = rng.uniform(60, 120)
        hills.append((hx, hy, hr))
    trees = []
    for i in range(40):
        tx = rng.uniform(-100, w+300)
        ty = rng.uniform(h*0.45, h*0.7)
        ts = rng.uniform(0.6, 1.3)
        trees.append((tx, ty, ts))

    def draw(s, t, camx):
        s.fill((0,0,0,0))
        # island sand blobs
        for (bx, by, br) in blobs:
            x = bx - camx*speed
            pygame.draw.circle(s, PASTEL["isle"], (int(x), int(by)), int(br))
            crayon_circle(s, PASTEL["crayon"], (int(x), int(by)), int(br*1.02), width=3)
            # shore highlight
            pygame.draw.circle(s, PASTEL["shore"], (int(x), int(by+br*0.3)), int(br*0.8))
        # grassy top
        for (hx, hy, hr) in hills:
            x = hx - camx*speed*1.05
            pygame.draw.circle(s, PASTEL["hill"], (int(x), int(hy)), int(hr))
            crayon_circle(s, PASTEL["crayon"], (int(x), int(hy)), int(hr*1.02), width=2)
        # trees
        for (tx, ty, ts) in trees:
            x = tx - camx*speed*1.2
            draw_tree(s, (x, ty), ts)
        return s
    return surf, draw

def draw_tree(surf, pos, sc):
    x, y = pos
    # trunk
    trunk_col = (160, 120, 80)
    pygame.draw.rect(surf, trunk_col, (int(x-3*sc), int(y), int(6*sc), int(20*sc)))
    # crown blobs
    for i in range(3):
        dx = (i-1)*12*sc + random.uniform(-1, 1)
        dy = -10*sc - i*8*sc
        pygame.draw.circle(surf, PASTEL["tree"], (int(x+dx), int(y+dy)), int(14*sc))
        crayon_circle(surf, PASTEL["crayon"], (int(x+dx), int(y+dy)), int(14*sc), width=2)

def make_fg_sparkles(w, h, seed):
    rng = random.Random(seed)
    pts = []
    for _ in range(120):
        x = rng.uniform(0, w)
        y = rng.uniform(h*0.3, h*0.95)
        a = rng.uniform(0.2, 1.0)
        pts.append([x, y, a, rng.uniform(-0.2, 0.2)])
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    def draw(s, t, camx):
        s.fill((0,0,0,0))
        for p in pts:
            x, y, a, drift = p
            x2 = (x - camx*0.3 + math.sin(t + x*0.01)*2) % (w+2)
            y2 = y + math.sin(t*2 + x*0.02)*drift*8
            pygame.draw.circle(s, (255,255,255,int(80*a*(math.sin(t*3+x*0.1)*0.5+0.5)+40)), (int(x2), int(y2)), 1)
        return s
    return surf, draw

def main():
    pygame.init()
    pygame.display.set_caption(f"Yoshi-ish Island • {os.name.upper()} • vibes=on")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    # Layers
    horizon = make_horizon(WIDTH, HEIGHT)
    cloud_surf, draw_clouds_far = make_cloud_layer(WIDTH, HEIGHT, 1234, count=8, speed=0.1, amp=4)
    cloud2_surf, draw_clouds_near = make_cloud_layer(WIDTH, HEIGHT, 5678, count=6, speed=0.2, amp=6)
    sea_surf, draw_sea = make_sea_layer(WIDTH, HEIGHT, 91011, speed=0.3)
    island_surf, draw_island = make_island_layer(WIDTH*2, HEIGHT, 1213, speed=0.35)
    spark_surf, draw_sparks = make_fg_sparkles(WIDTH, HEIGHT, 1415)

    camx = 0.0
    camy = 0.0
    auto = True
    vibes_on = VIBES_ON_DEFAULT
    show_help = False

    t = 0.0
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_v:
                    vibes_on = not vibes_on
                elif event.key == pygame.K_h:
                    show_help = not show_help
                elif event.key == pygame.K_SPACE:
                    auto = not auto

        keys = pygame.key.get_pressed()
        dx = dy = 0.0
        if keys[pygame.K_LEFT]:  dx -= 1
        if keys[pygame.K_RIGHT]: dx += 1
        if keys[pygame.K_UP]:    dy -= 1
        if keys[pygame.K_DOWN]:  dy += 1
        if dx and dy:
            inv = 1/math.sqrt(2); dx*=inv; dy*=inv

        speed = 80.0
        if auto:
            camx += dt * 20.0
        camx += dx * speed * dt
        camy += dy * speed * dt

        # draw
        screen.blit(horizon, (0, 0))
        screen.blit(draw_clouds_far(cloud_surf, t, camx), (0, 0))
        screen.blit(draw_sea(sea_surf, t, camx), (0, 0))
        # island parallax (wider layer)
        ix = - (camx * 0.35) % island_surf.get_width()
        screen.blit(draw_island(island_surf, t, camx), (ix, 0))
        screen.blit(island_surf, (ix - island_surf.get_width(), 0))  # wrap

        screen.blit(draw_clouds_near(cloud2_surf, t, camx), (0, 0))
        screen.blit(draw_sparks(spark_surf, t, camx), (0, 0))

        # UI
        font = pygame.font.SysFont(None, 22)
        small = pygame.font.SysFont(None, 16)
        title = "Yoshi‑ish Island • Arrow keys pan • Space auto‑sail • V vibes • H help"
        s1 = font.render(title, True, (0,0,0)); screen.blit(s1, (11, 9))
        s2 = font.render(title, True, (255,255,255)); screen.blit(s2, (10, 8))

        if show_help:
            bw, bh = int(WIDTH*0.6), int(HEIGHT*0.4)
            bx, by = (WIDTH-bw)//2, (HEIGHT-bh)//2
            pygame.draw.rect(screen, (20, 30, 40), (bx, by, bw, bh))
            pygame.draw.rect(screen, (255,255,255), (bx, by, bw, bh), 2)
            lines = [
                "Controls",
                "Left/Right: pan camera   Up/Down: drift",
                "Space: toggle auto‑sail",
                "V: vibes (scanlines + LCD shimmer)",
                "H: help   Q/Esc: quit",
            ]
            y = by + 10
            for ln in lines:
                s = small.render(ln, True, (255,255,255))
                screen.blit(s, (bx+10, y))
                y += s.get_height() + 4

        if vibes_on:
            draw_scanlines(screen, alpha=26, step=2)
            draw_lcd_shimmer(screen, t, strength=14)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
