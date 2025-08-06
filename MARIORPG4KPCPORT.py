import pygame
import sys

# ==========================
# Config
# ==========================
pygame.init()
WIDTH, HEIGHT = 960, 540
FPS = 60
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Brothership Engine - Mario & Luigi")
clock = pygame.time.Clock()
FONT = pygame.font.SysFont(None, 24)
BIG = pygame.font.SysFont(None, 42)

# Colors
SKY = (135, 206, 235)
GRASS = (60, 179, 113)
STONE = (225, 210, 180)
ROOF = (200, 0, 0)
BRICK = (210, 190, 160)
DOOR = (70, 45, 25)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GOLD = (255, 215, 0)
DARK = (30, 30, 40)
SHADOW = (0, 0, 0, 120)

# Physics
GRAVITY = 0.85
MOVE_SPEED = 4.4
AIR_ACCEL = 0.5
FRICTION = 0.8
JUMP_VEL = -12.5
MAX_FALL = 16
COYOTE_FRAMES = 6
JUMP_BUFFER_FRAMES = 6

# Tiles
TILE = 32

# ==========================
# Core engine: scenes
# ==========================
class Scene:
    def __init__(self, engine):
        self.engine = engine
    def enter(self, data=None): pass
    def exit(self): pass
    def handle_event(self, e): pass
    def update(self, dt): pass
    def draw(self, surf): pass

class Engine:
    def __init__(self):
        self.scene = None
        self.next_scene = None
        self.pending_data = None

    def switch(self, scene_cls, data=None):
        self.next_scene = scene_cls
        self.pending_data = data

    def run(self, first_scene_cls):
        self.scene = first_scene_cls(self)
        self.scene.enter()
        paused = False
        pause_flash = 0

        while True:
            dt = clock.tick(FPS) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN and e.key == pygame.K_p:
                    paused = not paused
                    pause_flash = 24
                if not paused:
                    self.scene.handle_event(e)

            if self.next_scene:
                self.scene.exit()
                self.scene = self.next_scene(self)
                self.scene.enter(self.pending_data)
                self.next_scene = None
                self.pending_data = None

            if not paused:
                self.scene.update(dt)

            self.scene.draw(SCREEN)

            if paused:
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 140))
                SCREEN.blit(overlay, (0, 0))
                txt = BIG.render("PAUSED (P to resume)", True, WHITE)
                SCREEN.blit(txt, txt.get_rect(center=(WIDTH//2, HEIGHT//2)))
                if pause_flash > 0:
                    pygame.draw.rect(SCREEN, GOLD, (0, 0, WIDTH, 4))
                    pause_flash -= 1

            pygame.display.flip()

# ==========================
# Entities
# ==========================
class Player:
    def __init__(self, x, y, w, h, color, controls, name):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = color
        self.controls = controls
        self.name = name

        self.vx = 0.0
        self.vy = 0.0
        self.facing = 1
        self.grounded = False
        self.coyote = 0
        self.jump_buffer = 0
        self.jump_held = False
        self.spawn = (x, y)

        # anim
        self.step_time = 0.0

    def reset(self, to_spawn=True):
        if to_spawn:
            self.rect.topleft = self.spawn
        self.vx = 0; self.vy = 0
        self.grounded = False
        self.coyote = 0
        self.jump_buffer = 0
        self.jump_held = False

    def handle_input(self, keys):
        left = keys[self.controls["left"]]
        right = keys[self.controls["right"]]
        jump_pressed = keys[self.controls["jump"]]

        # Horizontal movement
        move = 0
        if left: move -= 1
        if right: move += 1
        if move != 0:
            self.facing = move
            target = MOVE_SPEED * move
            if not self.grounded:
                self.vx += AIR_ACCEL * move
                self.vx = max(min(self.vx, MOVE_SPEED), -MOVE_SPEED)
            else:
                self.vx = target
        else:
            if self.grounded:
                self.vx *= FRICTION
                if abs(self.vx) < 0.05: self.vx = 0

        # Jump buffer + coyote time
        if jump_pressed:
            self.jump_buffer = JUMP_BUFFER_FRAMES
        else:
            if self.jump_held and self.vy < -4.5:
                self.vy = -4.5  # variable jump cutoff
        self.jump_held = jump_pressed

    def step_physics(self, solids, other=None):
        # coyote time countdown
        if self.grounded:
            self.coyote = COYOTE_FRAMES
        elif self.coyote > 0:
            self.coyote -= 1
        if self.jump_buffer > 0: self.jump_buffer -= 1

        # Apply buffered jump if allowed
        if self.jump_buffer > 0 and (self.coyote > 0 or self.grounded):
            self.vy = JUMP_VEL
            self.grounded = False
            self.coyote = 0
            self.jump_buffer = 0

        # Gravity
        self.vy = min(self.vy + GRAVITY, MAX_FALL)

        # Horizontal
        self.rect.x += int(round(self.vx))
        for s in solids:
            if self.rect.colliderect(s):
                if self.vx > 0: self.rect.right = s.left
                elif self.vx < 0: self.rect.left = s.right
                self.vx = 0

        # Vertical
        self.rect.y += int(round(self.vy))
        self.grounded = False
        for s in solids:
            if self.rect.colliderect(s):
                if self.vy > 0:
                    self.rect.bottom = s.top
                    self.vy = 0
                    self.grounded = True
                elif self.vy < 0:
                    self.rect.top = s.bottom
                    self.vy = 0

        # Soft stack on other bro
        if other and self.vy >= 0 and self.rect.colliderect(other.rect):
            top_overlap = other.rect.top - self.rect.bottom
            if -20 <= top_overlap <= 6 and other.rect.left < self.rect.centerx < other.rect.right:
                self.rect.bottom = other.rect.top
                self.vy = 0
                self.grounded = True

        # World bounds (for safety)
        if self.rect.left < 0: self.rect.left = 0; self.vx = 0
        if self.rect.right > WIDTH: self.rect.right = WIDTH; self.vx = 0
        if self.rect.bottom > HEIGHT:
            self.rect.bottom = HEIGHT
            self.vy = 0
            self.grounded = True

        # anim time
        speed = abs(self.vx)
        if speed > 0.1 and self.grounded:
            self.step_time += speed * 0.03
        else:
            self.step_time *= 0.9

class FakeSpriteBro:
    def __init__(self, player, hat_color, overall_color):
        self.p = player
        self.hat_color = hat_color
        self.overall_color = overall_color

    def draw(self, surf, camera=(0,0)):
        r = self.p.rect.move(-camera[0], -camera[1])
        x, y, w, h = r
        facing = self.p.facing

        # shadow
        shadow = pygame.Surface((w, 6), pygame.SRCALPHA)
        shadow.fill((0,0,0,60))
        surf.blit(shadow, (x, y + h - 2))

        # body proportions
        head_h = int(h * 0.30)
        torso_h = int(h * 0.38)
        leg_h = h - head_h - torso_h

        # head
        head = pygame.Rect(x + 4, y, w - 8, head_h)
        pygame.draw.rect(surf, (255, 224, 189), head, border_radius=3)

        # hat
        brim_h = 4
        pygame.draw.rect(surf, self.hat_color, (head.left - 2, head.top - 2, head.width + 4, brim_h), border_radius=2)
        pygame.draw.polygon(surf, self.hat_color,
            [(head.centerx, head.top - 8), (head.left, head.top - 2), (head.right, head.top - 2)])

        # eyes
        eye_w = 3
        ex = head.left + 5 if facing == 1 else head.right - 5 - eye_w
        pygame.draw.rect(surf, BLACK, (ex, head.top + head_h//2 - 2, eye_w, 3), border_radius=1)

        # mustache
        stache_w = w - 22
        stache_x = x + (w - stache_w)//2
        pygame.draw.rect(surf, BLACK, (stache_x, head.bottom - 6, stache_w, 3), border_radius=1)

        # torso/overalls
        torso = pygame.Rect(x + 6, head.bottom, w - 12, torso_h)
        pygame.draw.rect(surf, self.overall_color, torso, border_radius=3)
        # buttons
        pygame.draw.circle(surf, GOLD, (torso.left + 6, torso.top + 6), 3)
        pygame.draw.circle(surf, GOLD, (torso.right - 6, torso.top + 6), 3)

        # simple walk anim swing
        phase = (pygame.time.get_ticks() * 0.02 + self.p.step_time) % 12
        swing = -3 if phase < 6 else 3
        if not self.p.grounded: swing = 0

        # legs/boots
        leg_w = (w - 16) // 2
        left_leg = pygame.Rect(x + 8 + swing, torso.bottom - 2, leg_w, leg_h)
        right_leg = pygame.Rect(x + w - 8 - leg_w - swing, torso.bottom - 2, leg_w, leg_h)
        pygame.draw.rect(surf, (40, 40, 40), left_leg, border_radius=2)
        pygame.draw.rect(surf, (40, 40, 40), right_leg, border_radius=2)

# ==========================
# Castle hub scene
# ==========================
class HubScene(Scene):
    def enter(self, data=None):
        # Platforms
        self.platforms = []
        def add(x,y,w,h):
            r = pygame.Rect(x,y,w,h); self.platforms.append(r); return r
        self.ground = add(0, HEIGHT-40, WIDTH, 40)
        self.porch1 = add(340, 420, 280, 40)
        self.porch2 = add(370, 392, 220, 28)
        self.porch3 = add(400, 372, 160, 20)
        self.landing = add(428, 356, 104, 16)

        self.door_zone = pygame.Rect(440, 300, 80, 56)

        # Players
        self.mario = Player(160, HEIGHT-120, 34, 46, (220, 40, 40), {
            "left": pygame.K_LEFT, "right": pygame.K_RIGHT, "jump": pygame.K_UP
        }, "Mario")
        self.luigi = Player(220, HEIGHT-120, 34, 46, (40, 180, 60), {
            "left": pygame.K_a, "right": pygame.K_d, "jump": pygame.K_w
        }, "Luigi")

        self.mario.spawn = (160, HEIGHT-120)
        self.luigi.spawn = (220, HEIGHT-120)

        self.mario_sprite = FakeSpriteBro(self.mario, (200,0,0), (30,80,220))
        self.luigi_sprite = FakeSpriteBro(self.luigi, (0,150,0), (30,80,220))

        self.flash_enter = 0
        self.need_both = 0

    def both_in_door(self):
        return self.mario.rect.colliderect(self.door_zone) and self.luigi.rect.colliderect(self.door_zone)

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_r:
                self.mario.reset(to_spawn=True); self.luigi.reset(to_spawn=True)
                self.flash_enter = 0; self.need_both = 0
            if e.key == pygame.K_e:
                if self.both_in_door():
                    self.flash_enter = 60
                    # switch to level after flash
                    self.engine.switch(LevelScene, data={"from":"hub"})
                else:
                    self.need_both = 48

    def update(self, dt):
        keys = pygame.key.get_pressed()
        self.mario.handle_input(keys)
        self.luigi.handle_input(keys)

        self.mario.step_physics(self.platforms, other=self.luigi)
        self.luigi.step_physics(self.platforms, other=self.mario)

        if self.flash_enter > 0: self.flash_enter -= 1
        if self.need_both > 0: self.need_both -= 1

    def draw_castle(self, surf):
        # sky and ground
        surf.fill(SKY)
        pygame.draw.rect(surf, GRASS, (0, HEIGHT-40, WIDTH, 40))

        # main keep
        pygame.draw.rect(surf, STONE, (320, 260, 320, 140))
        pygame.draw.polygon(surf, ROOF, [(320, 260), (480, 190), (640, 260)])

        # towers
        pygame.draw.rect(surf, BRICK, (270, 230, 50, 170))
        pygame.draw.polygon(surf, ROOF, [(270, 230), (295, 185), (320, 230)])
        pygame.draw.rect(surf, BRICK, (640, 230, 50, 170))
        pygame.draw.polygon(surf, ROOF, [(640, 230), (665, 185), (690, 230)])

        # windows
        for (x,y) in [(360, 290), (600, 290), (282, 260), (660, 260)]:
            pygame.draw.ellipse(surf, WHITE, (x, y, 28, 28))
            pygame.draw.ellipse(surf, BLACK, (x, y, 28, 28), 2)

        # porch to match platforms
        for rect in [self.porch1, self.porch2, self.porch3, self.landing]:
            pygame.draw.rect(surf, STONE, rect)

        # door aligned with zone
        dz = self.door_zone
        pygame.draw.rect(surf, DOOR, (dz.x, dz.y+8, dz.width, dz.height-8))
        pygame.draw.ellipse(surf, DOOR, (dz.x, dz.y-16, dz.width, 32))
        pygame.draw.rect(surf, BLACK, (dz.x, dz.y+8, dz.width, dz.height-8), 2)
        pygame.draw.ellipse(surf, BLACK, (dz.x, dz.y-16, dz.width, 32), 2)

        if self.both_in_door() and (pygame.time.get_ticks()//300)%2==0:
            pygame.draw.rect(surf, GOLD, self.door_zone, 3)

    def draw_ui(self, surf):
        surf.blit(FONT.render("Mario: ← → move, ↑ jump", True, BLACK), (10, 10))
        surf.blit(FONT.render("Luigi: A D move, W jump", True, BLACK), (10, 32))
        surf.blit(FONT.render("Stand both in the doorway and press E", True, BLACK), (10, 54))
        surf.blit(FONT.render("R: reset, P: pause, ESC: quit", True, BLACK), (10, 76))

        if self.need_both > 0:
            warn = FONT.render("Both bros must be in the doorway!", True, (200,40,40))
            surf.blit(warn, (10, 100))

        if self.flash_enter > 0:
            box = pygame.Surface((WIDTH, 70), pygame.SRCALPHA)
            box.fill((0,0,0,140))
            surf.blit(box, (0, HEIGHT//2 - 35))
            txt = BIG.render("Entering Peach's Castle...", True, WHITE)
            surf.blit(txt, txt.get_rect(center=(WIDTH//2, HEIGHT//2)))

    def draw(self, surf):
        self.draw_castle(surf)
        # players
        self.mario_sprite.draw(surf)
        self.luigi_sprite.draw(surf)
        self.draw_ui(surf)

# ==========================
# Level scene (sample)
# ==========================
LEVEL_DATA = [
    "....................................................................................",
    "....................................................................................",
    "..........................................................E.........................",
    "......................XXX...........................................................",
    "..............................................XXXX.................XXXX..............",
    "...................XXXX.............................................................",
    "...........................................XXXXX....................................",
    "............................XXXXX...................................................",
    "....................XXXX............................................................",
    "..............XXXXX................................................................",
    "....................................................................................",
    "XXXX.....................XXXXX...........................XXXXX......................",
    "XXXX...............................................XXXXXXXXXXXX.....................",
    "XXXX.............................XXXXXXX............................................",
    "XXXXXXXXXXXXXXXXXXXXXXXX..XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
]

def build_solids_from_level():
    solids = []
    exits = []
    for j, row in enumerate(LEVEL_DATA):
        for i, ch in enumerate(row):
            if ch == 'X':
                solids.append(pygame.Rect(i*TILE, j*TILE, TILE, TILE))
            if ch == 'E':
                exits.append(pygame.Rect(i*TILE+8, j*TILE+8, TILE-16, TILE-16))
    return solids, exits

class LevelScene(Scene):
    def enter(self, data=None):
        self.solids, self.exit_zones = build_solids_from_level()
        # players near start
        self.mario = Player(80, 60, 34, 46, (220, 40, 40), {
            "left": pygame.K_LEFT, "right": pygame.K_RIGHT, "jump": pygame.K_UP
        }, "Mario")
        self.luigi = Player(130, 60, 34, 46, (40, 180, 60), {
            "left": pygame.K_a, "right": pygame.K_d, "jump": pygame.K_w
        }, "Luigi")
        self.mario.spawn = (80, 60)
        self.luigi.spawn = (130, 60)
        self.mario_sprite = FakeSpriteBro(self.mario, (200,0,0), (30,80,220))
        self.luigi_sprite = FakeSpriteBro(self.luigi, (0,150,0), (30,80,220))
        self.camera = [0, 0]
        self.level_w = len(LEVEL_DATA[0]) * TILE
        self.level_h = len(LEVEL_DATA) * TILE
        self.enter_flash = 24

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_r:
                self.mario.reset(); self.luigi.reset()
            if e.key == pygame.K_e:
                # If in exit, go back to hub
                if self.in_exit(self.mario) and self.in_exit(self.luigi):
                    self.engine.switch(HubScene)

    def in_exit(self, player):
        return any(player.rect.colliderect(z) for z in self.exit_zones)

    def update(self, dt):
        keys = pygame.key.get_pressed()
        self.mario.handle_input(keys)
        self.luigi.handle_input(keys)

        self.mario.step_physics(self.solids, other=self.luigi)
        self.luigi.step_physics(self.solids, other=self.mario)

        # Camera centers between bros
        midx = (self.mario.rect.centerx + self.luigi.rect.centerx) // 2
        midy = min(self.mario.rect.centery, self.luigi.rect.centery)  # bias up
        target_x = max(0, min(self.level_w - WIDTH, midx - WIDTH//2))
        target_y = max(0, min(self.level_h - HEIGHT, midy - HEIGHT//2))
        # smooth
        self.camera[0] += (target_x - self.camera[0]) * 0.1
        self.camera[1] += (target_y - self.camera[1]) * 0.1

        if self.enter_flash > 0: self.enter_flash -= 1

    def draw_grid(self, surf):
        # optional faint grid
        for x in range(0, self.level_w, TILE):
            sx = x - int(self.camera[0])
            pygame.draw.line(surf, (255,255,255,20), (sx, 0 - int(self.camera[1])), (sx, self.level_h - int(self.camera[1])))
        for y in range(0, self.level_h, TILE):
            sy = y - int(self.camera[1])
            pygame.draw.line(surf, (255,255,255,20), (0 - int(self.camera[0]), sy), (self.level_w - int(self.camera[0]), sy))

    def draw(self, surf):
        # background
        surf.fill(SKY)

        # parallax hills (simple)
        hill_color = (90, 180, 120)
        for i in range(6):
            hx = (i * 300) - int(self.camera[0] * 0.5)
            pygame.draw.ellipse(surf, hill_color, (hx, HEIGHT-180 - int(self.camera[1] * 0.2), 360, 200))

        # solids
        for r in self.solids:
            rr = r.move(-int(self.camera[0]), -int(self.camera[1]))
            pygame.draw.rect(surf, (180,170,160), rr)
            pygame.draw.rect(surf, (120,110,100), rr, 2)

        # exit zones
        for z in self.exit_zones:
            zz = z.move(-int(self.camera[0]), -int(self.camera[1]))
            col = GOLD if (self.in_exit(self.mario) and self.in_exit(self.luigi)) else (200,200,80)
            pygame.draw.rect(surf, col, zz, 3)

        # players
        self.mario_sprite.draw(surf, camera=self.camera)
        self.luigi_sprite.draw(surf, camera=self.camera)

        # UI
        top_panel = pygame.Surface((WIDTH, 24), pygame.SRCALPHA)
        top_panel.fill((0,0,0,80))
        surf.blit(top_panel, (0,0))
        surf.blit(FONT.render("Level: Test   Controls: E to exit if both at the sign  |  R reset  |  P pause  |  ESC quit", True, WHITE), (8, 4))

        # entry flash
        if self.enter_flash > 0:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((255,255,255,40))
            surf.blit(overlay, (0,0))

# ==========================
# Title scene
# ==========================
class TitleScene(Scene):
    def enter(self, data=None):
        self.t = 0

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.engine.switch(HubScene)

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        surf.fill(DARK)
        title = BIG.render("Mario & Luigi: Brothership", True, WHITE)
        sub = FONT.render("No files. 60 FPS. Two-player co-op. Press Enter/Space to start.", True, (220,220,220))
        hint = FONT.render("Controls: Mario ← → ↑   |   Luigi A D W   |   P pause, R reset, ESC quit", True, (200,200,200))
        surf.blit(title, title.get_rect(center=(WIDTH//2, HEIGHT//2 - 40)))
        surf.blit(sub, sub.get_rect(center=(WIDTH//2, HEIGHT//2)))
        surf.blit(hint, hint.get_rect(center=(WIDTH//2, HEIGHT//2 + 32)))

        # little blinking press key bar
        if int(self.t*2)%2==0:
            pygame.draw.rect(surf, GOLD, (WIDTH//2 - 140, HEIGHT//2 + 60, 280, 4))

# ==========================
# Boot
# ==========================
if __name__ == "__main__":
    Engine().run(TitleScene)
