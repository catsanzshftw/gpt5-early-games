import sys
import random
import pygame

# Optional tiny Tkinter prompt (skippable, defaults applied if it fails)
def get_launch_settings():
    vibes_on = True  # default per request
    speed = 10       # cells per second
    try:
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        # Simple speed prompt; cancel -> defaults
        s = simpledialog.askinteger(
            "Snake Setup",
            "Speed (cells/sec, 5-20):",
            initialvalue=speed,
            minvalue=3,
            maxvalue=30,
            parent=root
        )
        if s is not None:
            speed = int(s)
        root.destroy()
    except Exception:
        pass
    return vibes_on, speed


class SnakeGame:
    def __init__(self, width=600, height=400, cell=20, vibes=True, speed=10):
        pygame.init()
        pygame.display.set_caption(f"Snake — {width}x{height}")
        self.W, self.H = width, height
        self.CELL = cell
        self.COLS = self.W // self.CELL
        self.ROWS = self.H // self.CELL
        self.speed = max(3, min(30, speed))  # cells per second
        self.screen = pygame.display.set_mode((self.W, self.H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Consolas", 20)
        self.big_font = pygame.font.SysFont("Consolas", 36, bold=True)

        # Colors
        self.BG = (8, 8, 12)
        self.GRID = (24, 24, 32)
        self.NEON_SNAKE = (0, 255, 160)
        self.NEON_FOOD = (255, 70, 180)
        self.NEON_HEAD = (80, 220, 255)
        self.WHITE = (230, 230, 240)
        self.YELLOW = (255, 215, 0)
        self.RED = (255, 70, 90)

        self.vibes = vibes
        self.step_accum = 0.0
        self.step_time = 1.0 / self.speed

        # Overlays for vibes
        self.grid_overlay = self._make_grid_overlay()
        self.scanline_overlay = self._make_scanline_overlay()

        self.reset()

    # ---------- Setup helpers ----------
    def reset(self):
        cx, cy = self.COLS // 2, self.ROWS // 2
        self.snake = [(cx - 1, cy), (cx, cy), (cx + 1, cy)]
        self.direction = (1, 0)
        self.next_dir = (1, 0)
        self.grow = 0
        self.score = 0
        self.game_over = False
        self.paused = False
        self.spawn_food()
        self.step_accum = 0.0

    def spawn_food(self):
        free = set((x, y) for x in range(self.COLS) for y in range(self.ROWS)) - set(self.snake)
        if not free:
            self.food = None
            return
        self.food = random.choice(list(free))

    def _make_grid_overlay(self):
        surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        g = self.GRID
        faint = (g[0], g[1], g[2], 55 if self.vibes else 35)
        for x in range(0, self.W, self.CELL):
            pygame.draw.line(surf, faint, (x, 0), (x, self.H))
        for y in range(0, self.H, self.CELL):
            pygame.draw.line(surf, faint, (0, y), (self.W, y))
        return surf

    def _make_scanline_overlay(self):
        surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        # Draw subtle scanlines every 4 px
        for y in range(0, self.H, 4):
            pygame.draw.line(surf, (0, 0, 0, 28), (0, y), (self.W, y))
        return surf

    # ---------- Game loop ----------
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            running = self.handle_events()
            if not self.game_over and not self.paused:
                self.step_accum += dt
                while self.step_accum >= self.step_time:
                    self.step_accum -= self.step_time
                    self.update()
            self.draw()
        pygame.quit()
        sys.exit(0)

    # ---------- Input ----------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE,):
                    return False
                if event.key in (pygame.K_p,):
                    if not self.game_over:
                        self.paused = not self.paused
                if event.key in (pygame.K_r,):
                    self.reset()
                if event.key in (pygame.K_v,):
                    self.vibes = not self.vibes
                if self.game_over and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.reset()

                # Direction handling
                if event.key in (pygame.K_UP, pygame.K_w):
                    self._set_next_dir((0, -1))
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self._set_next_dir((0, 1))
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    self._set_next_dir((-1, 0))
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    self._set_next_dir((1, 0))
        return True

    def _set_next_dir(self, d):
        # Prevent immediate reversal
        if (d[0] == -self.direction[0] and d[1] == -self.direction[1]):
            return
        self.next_dir = d

    # ---------- Update ----------
    def update(self):
        self.direction = self.next_dir
        hx, hy = self.snake[-1]
        nx, ny = hx + self.direction[0], hy + self.direction[1]

        # Collisions with walls
        if nx < 0 or nx >= self.COLS or ny < 0 or ny >= self.ROWS:
            self.game_over = True
            return

        # Collisions with self
        if (nx, ny) in self.snake:
            self.game_over = True
            return

        # Move
        self.snake.append((nx, ny))
        ate = (self.food is not None and (nx, ny) == self.food)
        if ate:
            self.score += 1
            self.grow += 1
            self.spawn_food()

        if self.grow > 0:
            self.grow -= 1
        else:
            self.snake.pop(0)

    # ---------- Draw ----------
    def draw(self):
        self.screen.fill(self.BG)

        if self.vibes:
            self.screen.blit(self.grid_overlay, (0, 0))

        # Food
        if self.food:
            self._draw_cell(self.food, self.NEON_FOOD, glow=True, head=False)

        # Snake
        for i, seg in enumerate(self.snake):
            is_head = (i == len(self.snake) - 1)
            color = self.NEON_HEAD if is_head else self.NEON_SNAKE
            self._draw_cell(seg, color, glow=True, head=is_head)

        # HUD
        left = self.font.render(f"Score: {self.score}", True, self.WHITE)
        right_text = "P Pause  V Vibes  R Restart  Esc Quit"
        right = self.font.render(right_text, True, self.WHITE)
        self.screen.blit(left, (10, 8))
        self.screen.blit(right, (self.W - right.get_width() - 10, 8))

        if self.paused and not self.game_over:
            self._draw_banner("PAUSED", self.YELLOW)

        if self.game_over:
            self._draw_banner("GAME OVER — Space to restart", self.RED)

        if self.vibes:
            self.screen.blit(self.scanline_overlay, (0, 0))

        pygame.display.flip()

    def _cell_rect(self, cell):
        x, y = cell
        return pygame.Rect(x * self.CELL, y * self.CELL, self.CELL, self.CELL)

    def _draw_cell(self, cell, color, glow=True, head=False):
        rect = self._cell_rect(cell)
        # Glow backdrop
        if self.vibes and glow:
            self._glow_rect(rect, color, strength=70 if head else 48, radius=10)
        # Core rect (slightly inset for style)
        inset = 2 if not head else 1
        core = rect.inflate(-inset * 2, -inset * 2)
        pygame.draw.rect(self.screen, color, core, border_radius=6)

        # Head sheen
        if head and self.vibes:
            sheen = core.inflate(-core.w * 0.4, -core.h * 0.4)
            s = pygame.Surface((sheen.w, sheen.h), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (255, 255, 255, 40), s.get_rect())
            self.screen.blit(s, sheen.topleft)

    def _glow_rect(self, rect, color, strength=60, radius=8):
        # Create a soft glow behind the rect
        glow = pygame.Surface((rect.w + radius * 2, rect.h + radius * 2), pygame.SRCALPHA)
        r = pygame.Rect(0, 0, glow.get_width(), glow.get_height())
        c = (color[0], color[1], color[2], strength)
        pygame.draw.rect(glow, c, r, border_radius=radius + 6)
        self.screen.blit(glow, (rect.x - radius, rect.y - radius))

    def _draw_banner(self, text, color):
        shadow_col = (0, 0, 0)
        surf = self.big_font.render(text, True, color)
        shadow = self.big_font.render(text, True, shadow_col)
        x = (self.W - surf.get_width()) // 2
        y = (self.H - surf.get_height()) // 2
        # subtle shadow
        self.screen.blit(shadow, (x + 2, y + 2))
        self.screen.blit(surf, (x, y))


def main():
    vibes_on, speed = get_launch_settings()
    game = SnakeGame(600, 400, cell=20, vibes=vibes_on, speed=speed)
    pygame.display.set_caption(f"Snake — 600x400 — vibes {'on' if vibes_on else 'off'} — speed {speed}")
    game.run()


if __name__ == "__main__":
    main()
