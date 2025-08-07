import pygame
import math
import os

# Setup
pygame.init()
WIDTH, HEIGHT = 600, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
FPS = 60

# Hexagon parameters
HEX_RADIUS = 150
HEX_CENTER = (WIDTH // 2, HEIGHT // 2)
NUM_BALLS = 5
BALL_RADIUS = 10

# Compute hexagon vertices
def hex_vertices(center, radius):
    return [
        (
            center[0] + radius * math.cos(math.radians(60 * i)),
            center[1] + radius * math.sin(math.radians(60 * i))
        )
        for i in range(6)
    ]

# Ball paths
def ball_position(angle_offset, time):
    angle = (time + angle_offset) % 360
    rad = math.radians(angle)
    x = HEX_CENTER[0] + HEX_RADIUS * math.cos(rad)
    y = HEX_CENTER[1] + HEX_RADIUS * math.sin(rad)
    return int(x), int(y)

# Main loop
running = True
time = 0
while running:
    screen.fill((30, 30, 30))  # Vibes: dark background
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Draw hexagon
    pygame.draw.polygon(screen, (100, 200, 250), hex_vertices(HEX_CENTER, HEX_RADIUS), 3)

    # Draw balls
    for i in range(NUM_BALLS):
        angle_offset = i * (360 // NUM_BALLS)
        pos = ball_position(angle_offset, time)
        pygame.draw.circle(screen, (255, 100, 150), pos, BALL_RADIUS)

    pygame.display.flip()
    time += 2
    clock.tick(FPS)

pygame.quit()
