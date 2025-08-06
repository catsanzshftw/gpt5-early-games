# cavegame_1_0.py
# Single-file "Cave Game 1.0"-style voxel sandbox using Ursina.
# Creative-only, caves, trees, flight, surface-only blocks, no files.
# Install: pip install ursina
# Run: python cavegame_1_0.py

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import math
import random
from collections import defaultdict

# ---------- App / window ----------
app = Ursina()
window.title = 'Cavegame 1.0'
window.borderless = False
window.fullscreen = False
window.vsync = True
try:
    application.target_fps = 60
except Exception:
    pass

# ---------- Global state ----------
random.seed(2009)
paused = True
game_started = False
current_block_type = 'grass'
flying = False

# World dimensions (classic small world)
WORLD_X = 64
WORLD_Y = 32
WORLD_Z = 64
WORLD_ORIGIN = (-WORLD_X // 2, 0, -WORLD_Z // 2)

# Occupancy and entities
solid = None            # 3D boolean array [x][y][z] for solid blocks
block_type = None       # 3D char array for block id
entities = {}           # (x,y,z) world-space -> Voxel entity (only for visible surface)
AIR = '\0'

# ---------- Block palette ----------
BLOCKS = {
    'grass': color.rgb(108, 170, 95),
    'dirt': color.rgb(120, 88, 60),
    'stone': color.rgb(135, 135, 135),
    'wood': color.rgb(102, 74, 50),
    'leaves': color.rgba(70, 130, 70, 220),
    'glass': color.rgba(170, 220, 255, 120),
}

PALETTE_KEYS = ['grass', 'dirt', 'stone', 'wood', 'leaves', 'glass']

# ---------- UI: FPS display ----------
fps_text = Text(text='FPS: --', position=(-.875, .475), origin=(0,0), scale=0.9, color=color.azure, enabled=False)
reticle = Entity(model='quad', color=color.white, parent=camera.ui, scale=.01, rotation_z=45, enabled=False)
palette_text = Text(text='[1]Grass [2]Dirt [3]Stone [4]Wood [5]Leaves [6]Glass | F=Fly', position=(-.88, -.47), origin=(0,0), scale=.8, color=color.white, enabled=False)

def update_fps_label():
    if time.dt > 0:
        fps_text.text = f'FPS: {int(1 / max(time.dt, 1e-6))}'

# ---------- Helpers: index mapping ----------
def in_bounds(ix, iy, iz):
    return 0 <= ix < WORLD_X and 0 <= iy < WORLD_Y and 0 <= iz < WORLD_Z

def to_world(ix, iy, iz):
    ox, oy, oz = WORLD_ORIGIN
    return (ox + ix, oy + iy, oz + iz)

def to_index(wx, wy, wz):
    ox, oy, oz = WORLD_ORIGIN
    return (wx - ox, wy - oy, wz - oz)

# ---------- Density functions ----------
def height_at(x, z):
    # Rolling hills
    h = 8 + 4.0 * math.sin(x * 0.12) + 4.0 * math.cos(z * 0.10) + 2.0 * math.sin((x+z) * 0.07)
    return int(clamp(h, 4, WORLD_Y-3))

def cave_value(x, y, z):
    # Cave-like 3D field, repeatable and cheap
    return (
        math.sin(x * 0.22) + math.cos(z * 0.21) +
        math.sin(y * 0.29) + math.sin((x + z - y) * 0.13)
    )

def is_cave(x, y, z):
    # Threshold carves tunnels; lower -> more caves
    v = cave_value(x, y, z)
    return -0.7 < v < 0.35 and y <= WORLD_Y - 6

# ---------- World generation ----------
def gen_world_arrays():
    global solid, block_type
    solid = [[[False for _ in range(WORLD_Z)] for _ in range(WORLD_Y)] for _ in range(WORLD_X)]
    block_type = [[[AIR for _ in range(WORLD_Z)] for _ in range(WORLD_Y)] for _ in range(WORLD_X)]

    for ix in range(WORLD_X):
        for iz in range(WORLD_Z):
            wx, wz = to_world(ix, 0, iz)[0], to_world(ix, 0, iz)[2]
            h = height_at(wx, wz)
            for iy in range(h):
                wy = iy
                # Stone base, dirt mid, grass top
                if iy == h - 1:
                    t = 'grass'
                elif iy >= h - 3:
                    t = 'dirt'
                else:
                    t = 'stone'
                # Caves below surface
                if iy <= h - 2 and is_cave(wx, wy, wz):
                    continue
                solid[ix][iy][iz] = True
                block_type[ix][iy][iz] = t

    # Sprinkle trees on grass
    tree_count = 0
    rng = random.Random(1337)
    for ix in range(2, WORLD_X - 2):
        for iz in range(2, WORLD_Z - 2):
            # find surface
            top_y = -1
            for iy in reversed(range(WORLD_Y)):
                if solid[ix][iy][iz]:
                    top_y = iy
                    break
            if top_y < 0:
                continue
            if block_type[ix][top_y][iz] != 'grass':
                continue
            if rng.random() < 0.02:  # ~2% chance
                make_tree(ix, top_y + 1, iz, rng)
                tree_count += 1

def make_tree(ix, iy, iz, rng):
    height = rng.randint(3, 5)
    # Trunk
    for dy in range(height):
        place_array(ix, iy + dy, iz, 'wood', overwrite_air_only=True)
    # Leaves blob
    top = iy + height - 1
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            for dy in range(-2, 3):
                if abs(dx) + abs(dy) + abs(dz) <= 4:
                    if rng.random() < 0.92:
                        place_array(ix + dx, top + dy, iz + dz, 'leaves', overwrite_air_only=True)

def place_array(ix, iy, iz, t, overwrite_air_only=True):
    if not in_bounds(ix, iy, iz):
        return
    if overwrite_air_only and solid[ix][iy][iz]:
        return
    solid[ix][iy][iz] = True
    block_type[ix][iy][iz] = t

# ---------- Surface extraction ----------
neighbors = [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]

def is_exposed(ix, iy, iz):
    if not solid[ix][iy][iz]:
        return False
    for dx,dy,dz in neighbors:
        nx, ny, nz = ix+dx, iy+dy, iz+dz
        if not in_bounds(nx, ny, nz) or not solid[nx][ny][nz]:
            return True
    return False

# ---------- Voxel entity ----------
class Voxel(Button):
    def __init__(self, wpos=(0,0,0), btype='stone'):
        super().__init__(
            parent=scene,
            position=wpos,
            model='cube',
            origin_y=0.5,
            texture='white_cube',
            color=BLOCKS.get(btype, color.white),
            highlight_color=color.azure,
            scale=1,
        )
        self.btype = btype
        self.world_pos = tuple(int(v) for v in wpos)

    def input(self, key):
        if paused:
            return
        if not self.hovered:
            return
        if key == 'left mouse down':
            break_block(self.world_pos)
        elif key == 'right mouse down':
            place_adjacent(self.world_pos)

# ---------- World entity management ----------
def spawn_surface_block(ix, iy, iz):
    if not in_bounds(ix, iy, iz):
        return
    if not solid[ix][iy][iz]:
        return
    if not is_exposed(ix, iy, iz):
        return
    wpos = to_world(ix, iy, iz)
    if wpos in entities:
        return
    t = block_type[ix][iy][iz]
    e = Voxel(wpos=wpos, btype=t)
    entities[wpos] = e

def despawn_block_entity(wpos):
    ent = entities.pop(wpos, None)
    if ent:
        destroy(ent)

def refresh_neighbors_surface(ix, iy, iz):
    # After a change, create/destroy surface entities as needed around (ix,iy,iz)
    for dx,dy,dz in neighbors + [(0,0,0)]:
        nx, ny, nz = ix+dx, iy+dy, iz+dz
        if not in_bounds(nx, ny, nz):
            continue
        wpos = to_world(nx, ny, nz)
        if solid[nx][ny][nz]:
            if is_exposed(nx, ny, nz):
                spawn_surface_block(nx, ny, nz)
            else:
                despawn_block_entity(wpos)
        else:
            despawn_block_entity(wpos)

def place_adjacent(wpos):
    global current_block_type
    # Place on the face you're pointing at
    target_pos = Vec3(wpos) + mouse.normal
    wx, wy, wz = int(round(target_pos.x)), int(round(target_pos.y)), int(round(target_pos.z))
    ix, iy, iz = to_index(wx, wy, wz)
    if not in_bounds(ix, iy, iz):
        return
    if solid[ix][iy][iz]:
        return
    # Place block
    solid[ix][iy][iz] = True
    block_type[ix][iy][iz] = current_block_type
    spawn_surface_block(ix, iy, iz)
    # Hide neighbors that became interior; show neighbors that became exposed
    refresh_neighbors_surface(ix, iy, iz)

def break_block(wpos):
    wx, wy, wz = wpos
    ix, iy, iz = to_index(wx, wy, wz)
    if not in_bounds(ix, iy, iz):
        return
    if not solid[ix][iy][iz]:
        return
    # Remove block
    solid[ix][iy][iz] = False
    block_type[ix][iy][iz] = AIR
    despawn_block_entity(wpos)
    # Expose neighbors that were interior
    refresh_neighbors_surface(ix, iy, iz)

# ---------- Build world ----------
def build_world():
    gen_world_arrays()
    # Spawn only exposed blocks
    for ix in range(WORLD_X):
        for iy in range(WORLD_Y):
            for iz in range(WORLD_Z):
                if solid[ix][iy][iz] and is_exposed(ix, iy, iz):
                    spawn_surface_block(ix, iy, iz)

# ---------- Player ----------
player = None

def make_player():
    global player
    # Spawn at highest solid near center
    sx, sz = WORLD_X // 2, WORLD_Z // 2
    sy = WORLD_Y - 1
    for y in reversed(range(WORLD_Y)):
        if solid[sx][y][sz]:
            sy = y + 3
            break
    wx, wy, wz = to_world(sx, sy, sz)
    player = FirstPersonController(x=wx, y=wy, z=wz)
    player.cursor = False
    player.speed = 6
    player.gravity = 1.0
    player.jump_height = 1.2
    player.mouse_sensitivity = Vec2(40, 40)

def set_flying(on: bool):
    global flying
    flying = on
    if player:
        player.gravity = 0.0 if flying else 1.0

# ---------- Menus ----------
menu_panel = Panel(scale=(0.75, 0.65), color=color.rgba(0,0,0,180), enabled=True)
menu_title = Text("Cavegame 1.0", parent=menu_panel, y=.23, scale=2, color=color.azure)
menu_sub = Text("Creative. Caves. Trees. Flight. No files. 60 FPS target.", parent=menu_panel, y=.18, scale=1, color=color.gray)
fps_label_menu = Text("FPS target: 60", parent=menu_panel, y=.13, scale=1, color=color.lime)

start_btn = Button("Start", parent=menu_panel, y=.05, scale=(.3, .08))
fs_btn = Button("Toggle Fullscreen (F11)", parent=menu_panel, y=-.05, scale=(.45, .08))
quit_btn = Button("Quit", parent=menu_panel, y=-.15, scale=(.3, .08))
pause_tip = Text("Paused", parent=menu_panel, y=.23, scale=2, color=color.azure, enabled=False)

def start_game():
    global game_started, paused
    if not game_started:
        build_world()
        make_player()
        game_started = True
    paused = False
    menu_panel.enabled = False
    pause_tip.enabled = False
    fps_text.enabled = True
    palette_text.enabled = True
    reticle.enabled = True
    mouse.locked = True

def toggle_fullscreen():
    window.fullscreen = not window.fullscreen

start_btn.on_click = start_game
fs_btn.on_click = toggle_fullscreen
quit_btn.on_click = application.quit

def show_menu(title="Paused"):
    global paused
    paused = True
    mouse.locked = False
    menu_panel.enabled = True
    pause_tip.text = title
    pause_tip.enabled = True
    fps_text.enabled = True
    palette_text.enabled = False
    reticle.enabled = False

def hide_menu():
    global paused
    paused = False
    mouse.locked = True
    menu_panel.enabled = False
    pause_tip.enabled = False
    fps_text.enabled = True
    palette_text.enabled = True
    reticle.enabled = True

# ---------- Input handling ----------
def input(key):
    global current_block_type
    if key == 'escape':
        if paused:
            hide_menu()
        else:
            show_menu("Paused")
    if key == 'f11':
        toggle_fullscreen()
    if key == 'f':
        set_flying(not flying)

    # Block palette
    if key in ('1','2','3','4','5','6'):
        idx = int(key) - 1
        current_block_type = PALETTE_KEYS[idx]

# ---------- Update loop ----------
def update():
    update_fps_label()
    if not player or paused:
        return

    # Flight vertical movement
    if flying:
        up = held_keys['space'] - held_keys['left control']
        player.y += up * time.dt * 6

    # Keep player within reasonable bounds vertically
    if player.y < -40:
        player.y = 20

# ---------- Start at main menu ----------
show_menu("Cavegame 1.0")
app.run()
