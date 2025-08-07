import sys
import math
import random
import pygame

# ---------------------------
# Config
# ---------------------------
SCREEN_W, SCREEN_H = 960, 540
TILE = 32
GRAVITY = 0.6
MOVE_SPEED = 4.2
AIR_ACCEL = 0.5
JUMP_VEL = -12.5
MAX_FALL = 18
FPS = 60

WORLDS = 6
LEVELS_PER_WORLD = 5

# Level generation parameters
LEVEL_LENGTH_TILES = 230  # total width
GROUND_Y_TILES = 13       # baseline ground height (from top, tiles)
MAX_GAP = 4               # max gap width in tiles
HILL_CHANCE = 0.15
PLATFORM_CHANCE = 0.14
BUMP_CHANCE = 0.10

# Colors
SKY = (150, 200, 255)
GROUND = (95, 175, 65)
DIRT = (115, 95, 55)
BLOCK = (220, 170, 80)
PLAYER_COLOR = (235, 60, 60)
UI_COLOR = (20, 20, 20)
FLAG_POLE = (180, 180, 180)
FLAG_RED = (230, 30, 30)
CASTLE_RED = (160, 55, 55)
CASTLE_DARK = (110, 40, 40)

# ---------------------------
# Helpers
# ---------------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def world_level_index(world_idx, level_idx):
    return world_idx * LEVELS_PER_WORLD + level_idx

# ---------------------------
# Tile field
# ---------------------------
class TileField:
    def __init__(self, width_tiles, height_tiles):
        self.w = width_tiles
        self.h = height_tiles
        self.solid = set()   # set of (tx, ty)
        self.semisolid = set()  # for platforms you can jump through (top collision only)

    def add_solid(self, tx, ty):
        if 0 <= tx < self.w and 0 <= ty < self.h:
            self.solid.add((tx, ty))

    def add_platform(self, tx, ty):
        if 0 <= tx < self.w and 0 <= ty < self.h:
            self.semisolid.add((tx, ty))

    def rect_for_tile(self, tx, ty):
        return pygame.Rect(tx * TILE, ty * TILE, TILE, TILE)

    def nearby_tiles(self, rect, include_platforms=True):
        # yield rects intersecting area around given rect
        left = max(int((rect.left // TILE) - 2), 0)
        right = min(int((rect.right // TILE) + 2), self.w - 1)
        top = max(int((rect.top // TILE) - 2), 0)
        bottom = min(int((rect.bottom // TILE) + 2), self.h - 1)

        for ty in range(top, bottom + 1):
            for tx in range(left, right + 1):
                if (tx, ty) in self.solid:
                    yield self.rect_for_tile(tx, ty), 'solid'
                elif include_platforms and (tx, ty) in self.semisolid:
                    yield self.rect_for_tile(tx, ty), 'platform'

# ---------------------------
# Flag and castle visuals
# ---------------------------
class Flag:
    def __init__(self, x, ground_y):
        self.pole_rect = pygame.Rect(x, ground_y - 11 * TILE, 6, 11 * TILE)
        # Flag triangle hangs from the top third
        self.flag_anchor = (self.pole_rect.centerx, self.pole_rect.top + TILE * 2)
        self.flag_points = [
            (self.flag_anchor[0], self.flag_anchor[1]),
            (self.flag_anchor[0] + TILE * 1.5, self.flag_anchor[1] + TILE * 0.5),
            (self.flag_anchor[0], self.flag_anchor[1] + TILE)
        ]
        # Touch zone near base of pole to clear level
        self.goal_rect = pygame.Rect(self.pole_rect.left - 16, self.pole_rect.bottom - 96, 64, 96)

    def draw(self, surf, camx):
        # Pole
        pygame.draw.rect(surf, FLAG_POLE, self.pole_rect.move(-camx, 0))
        # Flag
        pts = [(x - camx, y) for (x, y) in self.flag_points]
        pygame.draw.polygon(surf, FLAG_RED, pts)
        # Goal hint (invisible, but you can uncomment for debugging)
        # pygame.draw.rect(surf, (0, 0, 0), self.goal_rect.move(-camx,0), 1)

class Castle:
    def __init__(self, x, ground_y, scale=1.0):
        self.x = x
        self.ground_y = ground_y
        self.scale = scale

    def draw(self, surf, camx):
        s = self.scale
        base_w = int(8 * TILE * s)
        base_h = int(5 * TILE * s)
        base_rect = pygame.Rect(int(self.x - camx), self.ground_y - base_h, base_w, base_h)
        pygame.draw.rect(surf, CASTLE_RED, base_rect)
        # Battlements
        tooth_w = int(TILE * s)
        tooth_h = int(TILE * 0.7 * s)
        for i in range(0, base_w, tooth_w * 2):
            r = pygame.Rect(base_rect.left + i, base_rect.top - tooth_h, tooth_w, tooth_h)
            pygame.draw.rect(surf, CASTLE_DARK, r)
        # Door
        door_w = int(2 * TILE * s)
        door_h = int(3 * TILE * s)
        door_rect = pygame.Rect(base_rect.centerx - door_w // 2, base_rect.bottom - door_h, door_w, door_h)
        pygame.draw.rect(surf, (40, 25, 15), door_rect)
        # Towers
        tw = int(2 * TILE * s)
        th = int(6 * TILE * s)
        t1 = pygame.Rect(base_rect.left - tw // 2, base_rect.bottom - th, tw, th)
        t2 = pygame.Rect(base_rect.right - tw // 2, base_rect.bottom - th, tw, th)
        pygame.draw.rect(surf, CASTLE_DARK, t1)
        pygame.draw.rect(surf, CASTLE_DARK, t2)
        # Tower tops
        cap_h = int(TILE * 0.7 * s)
        pygame.draw.rect(surf, CASTLE_RED, pygame.Rect(t1.left, t1.top - cap_h, t1.width, cap_h))
        pygame.draw.rect(surf, CASTLE_RED, pygame.Rect(t2.left, t2.top - cap_h, t2.width, cap_h))

# ---------------------------
# Level generation
# ---------------------------
class Level:
    def __init__(self, world_idx, level_idx):
        self.world_idx = world_idx
        self.level_idx = level_idx
        self.width_tiles = LEVEL_LENGTH_TILES
        self.height_tiles = (SCREEN_H // TILE) + 4
        self.tiles = TileField(self.width_tiles, self.height_tiles)
        self.ground_y = GROUND_Y_TILES * TILE
        self.start_pos = pygame.Vector2(64, self.ground_y - TILE - 1)
        self.flag = None
        self.start_castle = None
        self.end_castle = None
        self.finish_x = None

    def generate(self):
        seed = 1337 + self.world_idx * 777 + self.level_idx * 31
        rng = random.Random(seed)

        ground_line = [GROUND_Y_TILES] * self.width_tiles

        # Introduce mild terrain variation (hills)
        for x in range(5, self.width_tiles - 5):
            if rng.random() < HILL_CHANCE:
                hump = rng.choice([1, -1])
                span = rng.randint(3, 9)
                for i in range(span):
                    xi = x + i
                    if 0 < xi < self.width_tiles:
                        ground_line[xi] = clamp(ground_line[xi] - hump, 10, 17)

        # Sprinkle bumps
        for x in range(5, self.width_tiles - 5, rng.randint(6, 12)):
            if rng.random() < BUMP_CHANCE:
                h = rng.randint(1, 2)
                ground_line[x] -= h
                ground_line[x + 1] -= h

        # Carve gaps, limited size
        x = 10
        while x < self.width_tiles - 15:
            if rng.random() < 0.10:
                gap = rng.randint(2, MAX_GAP)
                for g in range(gap):
                    if x + g < self.width_tiles:
                        ground_line[x + g] = 40  # push far down to represent no ground
                x += gap + rng.randint(3, 8)
            else:
                x += 1

        # Build ground and fill dirt
        for tx in range(self.width_tiles):
            gy = ground_line[tx]
            if gy >= self.height_tiles:
                continue
            # top ground
            if gy < self.height_tiles:
                self.tiles.add_solid(tx, gy)
            # below ground (dirt fill)
            for ty in range(gy + 1, self.height_tiles):
                self.tiles.add_solid(tx, ty)

        # Platforms
        for tx in range(8, self.width_tiles - 8):
            if rng.random() < PLATFORM_CHANCE:
                length = rng.randint(2, 5)
                height = rng.randint(4, 7)
                for i in range(length):
                    self.tiles.add_platform(tx + i, ground_line[tx] - height)

        # Start & end, ensure solid start lane
        for tx in range(0, 6):
            gy = ground_line[tx] = min(ground_line[tx], GROUND_Y_TILES)
            self.tiles.add_solid(tx, gy)
            for ty in range(gy + 1, self.height_tiles):
                self.tiles.add_solid(tx, ty)

        end_tx = self.width_tiles - 6
        for tx in range(end_tx, self.width_tiles):
            gy = ground_line[tx] = min(ground_line[tx], GROUND_Y_TILES)
            self.tiles.add_solid(tx, gy)
            for ty in range(gy + 1, self.height_tiles):
                self.tiles.add_solid(tx, ty)

        # Flag near end
        flag_x = (self.width_tiles - 10) * TILE
        self.flag = Flag(flag_x, ground_line[self.width_tiles - 10] * TILE)

        # Castles at both ends (visual only, non-colliding)
        self.start_castle = Castle(2 * TILE, ground_line[2] * TILE, scale=0.9)
        self.end_castle = Castle((self.width_tiles - 4) * TILE, ground_line[self.width_tiles - 4] * TILE, scale=1.1)

        # Starting position on top of ground near the start castle
        self.start_pos = pygame.Vector2(3 * TILE, (ground_line[3] * TILE) - TILE - 2)

        self.finish_x = flag_x

    def draw(self, surf, camx):
        # Sky
        surf.fill(SKY)

        # Draw visible tiles
        left_tile = max((camx // TILE) - 2, 0)
        right_tile = min(((camx + SCREEN_W) // TILE) + 2, self.width_tiles - 1)

        # Ground top and dirt blocks
        for ty in range(self.height_tiles):
            for tx in range(left_tile, right_tile + 1):
                if (tx, ty) in self.tiles.solid:
                    rect = pygame.Rect(tx * TILE - camx, ty * TILE, TILE, TILE)
                    # Top tile shading if it's the top of the ground stack
                    if (tx, ty - 1) not in self.tiles.solid:
                        pygame.draw.rect(surf, GROUND, rect)
                        pygame.draw.rect(surf, (70, 140, 50), rect, 2)
                    else:
                        pygame.draw.rect(surf, DIRT, rect)
                elif (tx, ty) in self.tiles.semisolid:
                    rect = pygame.Rect(tx * TILE - camx, ty * TILE, TILE, TILE // 3)
                    pygame.draw.rect(surf, BLOCK, rect)

        # Castles
        if self.start_castle:
            self.start_castle.draw(surf, camx)
        if self.end_castle:
            self.end_castle.draw(surf, camx)

        # Flag
        if self.flag:
            self.flag.draw(surf, camx)

# ---------------------------
# Player
# ---------------------------
class Player:
    def __init__(self, pos):
        self.rect = pygame.Rect(int(pos.x), int(pos.y), TILE, TILE)
        self.vel = pygame.Vector2(0, 0)
        self.on_ground = False
        self.coyote = 0.0  # short grace period after leaving ground
        self.jump_buffer = 0.0

    def handle_input(self, keys):
        target = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            target -= MOVE_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            target += MOVE_SPEED

        # Smooth horizontal accel in air
        if self.on_ground:
            self.vel.x = target
        else:
            if target == 0:
                self.vel.x *= 0.98
            else:
                if target > 0:
                    self.vel.x = min(target, self.vel.x + AIR_ACCEL)
                else:
                    self.vel.x = max(target, self.vel.x - AIR_ACCEL)

    def start_jump(self):
        self.jump_buffer = 0.12  # seconds

    def physics(self, dt, tiles: TileField):
        # Timers
        self.coyote = max(0.0, self.coyote - dt)
        self.jump_buffer = max(0.0, self.jump_buffer - dt)

        # Jump if possible
        if self.jump_buffer > 0 and (self.on_ground or self.coyote > 0.0):
            self.vel.y = JUMP_VEL
            self.on_ground = False
            self.coyote = 0.0
            self.jump_buffer = 0.0

        # Apply gravity
        self.vel.y = clamp(self.vel.y + GRAVITY, -999, MAX_FALL)

        # Horizontal move and collide
        self.rect.x += int(self.vel.x)
        for tile_rect, ttype in tiles.nearby_tiles(self.rect, include_platforms=False):
            if self.rect.colliderect(tile_rect):
                if self.vel.x > 0:
                    self.rect.right = tile_rect.left
                elif self.vel.x < 0:
                    self.rect.left = tile_rect.right
                self.vel.x = 0

        # Vertical move and collide
        self.rect.y += int(self.vel.y)
        was_on_ground = self.on_ground
        self.on_ground = False
        for tile_rect, ttype in tiles.nearby_tiles(self.rect, include_platforms=True):
            if not self.rect.colliderect(tile_rect):
                continue
            if ttype == 'solid':
                if self.vel.y > 0:
                    self.rect.bottom = tile_rect.top
                    self.vel.y = 0
                    self.on_ground = True
                elif self.vel.y < 0:
                    self.rect.top = tile_rect.bottom
                    self.vel.y = 0
            elif ttype == 'platform':
                # Platform only collides when moving downward and feet are above top
                if self.vel.y > 0 and (self.rect.bottom - self.vel.y) <= tile_rect.top:
                    self.rect.bottom = tile_rect.top
                    self.vel.y = 0
                    self.on_ground = True

        # Coyote time refresh on landing
        if self.on_ground and not was_on_ground:
            self.coyote = 0.08

    def draw(self, surf, camx):
        pygame.draw.rect(surf, PLAYER_COLOR, self.rect.move(-camx, 0))
        # Eye
        eye = pygame.Rect(self.rect.left + 6 - camx, self.rect.top + 8, 6, 6)
        pygame.draw.rect(surf, (255, 255, 255), eye)

# ---------------------------
# Game
# ---------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Mario-like: 6 Worlds x 5 Levels (No assets)")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Consolas", 22)
        self.big = pygame.font.SysFont("Consolas", 42, bold=True)

        self.world_idx = 0
        self.level_idx = 0

        self.level = None
        self.player = None
        self.camx = 0

        self.level_complete = False
        self.complete_timer = 0.0
        self.dead_timer = 0.0
        self.total_levels = WORLDS * LEVELS_PER_WORLD

        self.load_level()

    def load_level(self):
        self.level_complete = False
        self.complete_timer = 0.0
        self.dead_timer = 0.0

        self.level = Level(self.world_idx, self.level_idx)
        self.level.generate()
        self.player = Player(self.level.start_pos)
        self.camx = max(0, self.player.rect.centerx - SCREEN_W // 2)

    def advance(self):
        idx = world_level_index(self.world_idx, self.level_idx) + 1
        if idx >= self.total_levels:
            # Victory; loop back to start
            self.world_idx = 0
            self.level_idx = 0
        else:
            self.world_idx = idx // LEVELS_PER_WORLD
            self.level_idx = idx % LEVELS_PER_WORLD
        self.load_level()

    def reset_level(self):
        self.load_level()

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

            # Events
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        running = False
                    if e.key == pygame.K_SPACE:
                        self.player.start_jump()
                    if e.key == pygame.K_r:
                        self.reset_level()
                    if e.key == pygame.K_RETURN and self.level_complete and self.complete_timer >= 0.3:
                        self.advance()

            keys = pygame.key.get_pressed()

            # Update
            if not self.level_complete and self.dead_timer <= 0.0:
                self.player.handle_input(keys)
                self.player.physics(dt, self.level.tiles)

                # Camera follow with soft clamp
                target_cam = self.player.rect.centerx - SCREEN_W // 2
                self.camx += (target_cam - self.camx) * 0.2
                self.camx = clamp(self.camx, 0, self.level.width_tiles * TILE - SCREEN_W)

                # Check out-of-bounds (fall)
                if self.player.rect.top > self.level.height_tiles * TILE + 100:
                    self.dead_timer = 0.8

                # Check flag collision
                if self.level.flag and self.player.rect.colliderect(self.level.flag.goal_rect):
                    self.level_complete = True
                    self.complete_timer = 0.0

            if self.dead_timer > 0.0:
                self.dead_timer -= dt
                if self.dead_timer <= 0.0:
                    self.reset_level()

            if self.level_complete:
                self.complete_timer += dt
                # Auto-advance after a short delay
                if self.complete_timer > 1.4:
                    self.advance()

            # Draw
            self.level.draw(self.screen, int(self.camx))
            self.player.draw(self.screen, int(self.camx))
            self.draw_ui()

            pygame.display.flip()

        pygame.quit()
        sys.exit(0)

    def draw_ui(self):
        # World and Level
        wl = f"World {self.world_idx + 1}-{self.level_idx + 1}"
        txt = self.font.render(wl, True, UI_COLOR)
        self.screen.blit(txt, (16, 10))

        # Messages
        if self.level_complete:
            msg = "Course Clear!"
            s = self.big.render(msg, True, (255, 255, 255))
            o = self.big.render(msg, True, (0, 0, 0))
            self.screen.blit(o, (SCREEN_W // 2 - o.get_width() // 2 + 2, SCREEN_H // 3 + 2))
            self.screen.blit(s, (SCREEN_W // 2 - s.get_width() // 2, SCREEN_H // 3))
            hint = self.font.render("Advancing...", True, UI_COLOR)
            self.screen.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, SCREEN_H // 3 + 56))
        elif self.dead_timer > 0.0:
            msg = "Ouch! Respawning..."
            s = self.font.render(msg, True, UI_COLOR)
            self.screen.blit(s, (SCREEN_W // 2 - s.get_width() // 2, SCREEN_H // 3 + 20))
        else:
            hint = self.font.render("Arrows/A,D to move • Space to jump • R to restart • Esc to quit", True, UI_COLOR)
            self.screen.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, SCREEN_H - 30))

# ---------------------------
# Main
# ---------------------------
if __name__ == "__main__":
    Game().run()
######## {C Team Flames 2025-26 }
