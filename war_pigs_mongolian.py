import pygame
import math
import random
import sys

# ==============================================================================
# CONFIGURATION & DISPLAY
# ==============================================================================
WIDTH, HEIGHT = 960, 540
FPS = 60
SONG_DURATION_SEC = 213.0  # 3 minutes 33 seconds

COLOR_BLACK = (8, 8, 12)
COLOR_DEEP_RED = (90, 10, 15)
COLOR_AMBER = (230, 125, 25)
COLOR_YELLOW = (255, 220, 90)
COLOR_SMOKE = (35, 30, 35)
COLOR_SEARCHLIGHT = (255, 245, 200)
COLOR_EMBER = (255, 140, 30)
COLOR_SILHOUETTE = (10, 10, 14)
COLOR_FLASH = (245, 240, 230)

# ==============================================================================
# PROCEDURAL PARTICLE & ACTOR SYSTEMS
# ==============================================================================
class Explosion:
    def __init__(self, x, y, max_radius=45):
        self.x = int(x)
        self.y = int(y)
        self.radius = 4.0
        self.max_radius = max_radius
        self.growth = random.uniform(2.5, 4.5)
        self.alpha = 255
        self.shockwave_r = 6.0

    def update(self):
        if self.radius < self.max_radius:
            self.radius += self.growth
        else:
            self.alpha = max(0, self.alpha - 12)
        self.shockwave_r += 6.0

    def draw(self, surface):
        if self.alpha > 0:
            r = int(self.radius)
            # Outer Fire
            fire_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(fire_surf, (*COLOR_AMBER, int(self.alpha * 0.8)), (r + 2, r + 2), r)
            # Inner White-Hot Core
            if self.radius < self.max_radius * 0.7:
                pygame.draw.circle(fire_surf, (*COLOR_YELLOW, self.alpha), (r + 2, r + 2), int(r * 0.5))
            surface.blit(fire_surf, (self.x - r - 2, self.y - r - 2))

            # Shockwave Ring
            if self.shockwave_r < self.max_radius * 2.2:
                sw_r = int(self.shockwave_r)
                sw_surf = pygame.Surface((sw_r * 2 + 4, sw_r * 2 + 4), pygame.SRCALPHA)
                sw_alpha = max(0, int(200 * (1.0 - sw_r / (self.max_radius * 2.2))))
                pygame.draw.circle(sw_surf, (*COLOR_FLASH, sw_alpha), (sw_r + 2, sw_r + 2), sw_r, 2)
                surface.blit(sw_surf, (self.x - sw_r - 2, self.y - sw_r - 2))

class FlakBurst:
    def __init__(self, x, y):
        self.x = int(x)
        self.y = int(y)
        self.radius = random.uniform(8, 16)
        self.max_radius = random.uniform(24, 40)
        self.alpha = 240

    def update(self):
        self.radius += 0.8
        self.alpha -= 6

    def draw(self, surface):
        if self.alpha > 0:
            r = int(self.radius)
            s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*COLOR_SMOKE, int(self.alpha * 0.7)), (r + 2, r + 2), r)
            if self.radius < self.max_radius * 0.5:
                pygame.draw.circle(s, (*COLOR_AMBER, int(self.alpha)), (r + 2, r + 2), int(r * 0.4))
            surface.blit(s, (self.x - r - 2, self.y - r - 2))

class Bomb:
    def __init__(self, x, y, target_y=HEIGHT - 60):
        self.x = x
        self.y = y
        self.vx = random.uniform(2.5, 4.0)
        self.vy = 1.0
        self.gravity = 0.22
        self.target_y = target_y
        self.exploded = False

    def update(self):
        self.x += self.vx
        self.vy += self.gravity
        self.y += self.vy
        if self.y >= self.target_y:
            self.exploded = True

    def draw(self, surface):
        angle = math.atan2(self.vy, self.vx)
        end_x = self.x - math.cos(angle) * 7
        end_y = self.y - math.sin(angle) * 7
        pygame.draw.line(surface, COLOR_SILHOUETTE, (int(self.x), int(self.y)), (int(end_x), int(end_y)), 3)

class Plane:
    def __init__(self, x, y, speed, plane_type="bomber"):
        self.x = x
        self.y = y
        self.speed = speed
        self.plane_type = plane_type
        self.drop_timer = random.randint(20, 60)

    def update(self, bombs_list):
        self.x += self.speed
        if self.plane_type == "bomber":
            self.drop_timer -= 1
            if self.drop_timer <= 0:
                bombs_list.append(Bomb(self.x, self.y + 10))
                self.drop_timer = random.randint(45, 90)

    def draw(self, surface):
        px, py = int(self.x), int(self.y)
        if self.plane_type == "bomber":
            # Heavy Bomber Silhouette
            pygame.draw.polygon(surface, COLOR_SILHOUETTE, [
                (px + 35, py), (px - 25, py - 4), (px - 35, py - 12),
                (px - 30, py), (px - 25, py + 4)
            ])
            # Main Wing Span
            pygame.draw.polygon(surface, COLOR_SILHOUETTE, [
                (px - 4, py - 20), (px + 10, py), (px - 4, py + 20), (px - 10, py)
            ])
            # Engine Nacelles
            pygame.draw.rect(surface, COLOR_SILHOUETTE, (px - 2, py - 14, 8, 4))
            pygame.draw.rect(surface, COLOR_SILHOUETTE, (px - 2, py + 10, 8, 4))
        else:
            # Fast Sleek Fighter
            pygame.draw.polygon(surface, COLOR_SILHOUETTE, [
                (px + 22, py), (px - 14, py - 3), (px - 20, py - 7),
                (px - 16, py), (px - 14, py + 3)
            ])
            pygame.draw.polygon(surface, COLOR_SILHOUETTE, [
                (px + 2, py - 12), (px + 8, py), (px + 2, py + 12), (px - 4, py)
            ])

# ==============================================================================
# PROCEDURAL SCENE DRAWING ROUTINES
# ==============================================================================
def draw_gradient_sky(surface, top_color, bottom_color):
    for y in range(0, HEIGHT, 2):
        ratio = y / HEIGHT
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        pygame.draw.line(surface, (r, g, b), (0, y), (WIDTH, y), 2)

def draw_war_table_scene(surface, current_sec):
    """Scene: Shadowy generals leaning over a strategy map."""
    draw_gradient_sky(surface, (12, 8, 12), (35, 15, 18))
    
    # Swinging Ceiling Light
    light_angle = math.sin(current_sec * 2.2) * 0.35
    lamp_x = WIDTH // 2 + math.sin(light_angle) * 90
    lamp_y = 60 + math.cos(light_angle) * 15
    pygame.draw.line(surface, (40, 40, 40), (WIDTH // 2, 0), (int(lamp_x), int(lamp_y)), 2)

    # Overhead Light Cone
    cone_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    p1 = (lamp_x, lamp_y)
    p2 = (lamp_x - 240 + math.sin(light_angle) * 60, HEIGHT)
    p3 = (lamp_x + 240 + math.sin(light_angle) * 60, HEIGHT)
    pygame.draw.polygon(cone_surf, (255, 230, 160, 45), [p1, p2, p3])
    surface.blit(cone_surf, (0, 0))

    # The Strategic Table
    table_y = HEIGHT - 130
    pygame.draw.polygon(surface, (18, 14, 18), [
        (160, HEIGHT), (220, table_y), (WIDTH - 220, table_y), (WIDTH - 160, HEIGHT)
    ])
    # Glowing Map Grid & Battle Markers
    for gx in range(260, WIDTH - 240, 50):
        pygame.draw.line(surface, (90, 30, 30), (gx, table_y + 10), (gx - 30, HEIGHT - 15), 1)
    for gy in range(table_y + 20, HEIGHT - 10, 25):
        pygame.draw.line(surface, (90, 30, 30), (200 + (gy - table_y), gy), (WIDTH - 200 - (gy - table_y), gy), 1)

    # Chess / War Tokens
    tokens = [(380, table_y + 35), (450, table_y + 55), (540, table_y + 40), (590, table_y + 65)]
    for tx, ty in tokens:
        pygame.draw.circle(surface, COLOR_AMBER, (tx, ty), 4)

    # General Left (Puffing cigar)
    pygame.draw.polygon(surface, COLOR_SILHOUETTE, [
        (130, HEIGHT), (170, table_y - 40), (220, table_y + 20), (260, HEIGHT)
    ])
    pygame.draw.circle(surface, COLOR_SILHOUETTE, (195, table_y - 55), 20)
    pygame.draw.polygon(surface, COLOR_SILHOUETTE, [(180, table_y - 75), (225, table_y - 65), (175, table_y - 60)])
    pygame.draw.circle(surface, (255, 80, 20), (218, table_y - 48), 2)

    # General Right (Pointing at map)
    pygame.draw.polygon(surface, COLOR_SILHOUETTE, [
        (WIDTH - 140, HEIGHT), (WIDTH - 190, table_y - 35), (WIDTH - 240, table_y + 30), (WIDTH - 280, HEIGHT)
    ])
    pygame.draw.circle(surface, COLOR_SILHOUETTE, (WIDTH - 210, table_y - 50), 22)
    pygame.draw.polygon(surface, COLOR_SILHOUETTE, [(WIDTH - 190, table_y - 70), (WIDTH - 235, table_y - 62), (WIDTH - 185, table_y - 56)])
    pygame.draw.line(surface, COLOR_SILHOUETTE, (WIDTH - 230, table_y - 20), (WIDTH - 360, table_y + 45), 9)

def draw_tank_and_artillery(surface, x, y, cycle):
    """Draws a heavy tracked tank firing artillery recoils."""
    # Tracks
    pygame.draw.polygon(surface, COLOR_SILHOUETTE, [
        (x - 60, y), (x + 60, y), (x + 50, y - 22), (x - 50, y - 22)
    ])
    # Hull & Turret
    pygame.draw.rect(surface, COLOR_SILHOUETTE, (x - 45, y - 38, 90, 18))
    pygame.draw.arc(surface, COLOR_SILHOUETTE, (x - 30, y - 56, 55, 35), 0, math.pi, 16)
    
    # Recoiling Gun Barrel
    recoil = math.sin(cycle * 6.0)
    barrel_offset = 6 if recoil > 0.8 else 0
    barrel_start = (x + 15 - barrel_offset, y - 44)
    barrel_end = (x + 85 - barrel_offset, y - 56)
    pygame.draw.line(surface, COLOR_SILHOUETTE, barrel_start, barrel_end, 6)

    # Muzzle Flash
    if recoil > 0.85:
        flash_x, flash_y = barrel_end[0] + 8, barrel_end[1] - 2
        pygame.draw.circle(surface, COLOR_YELLOW, (int(flash_x), int(flash_y)), 18)
        pygame.draw.circle(surface, COLOR_AMBER, (int(flash_x), int(flash_y)), 28, 2)

def draw_soldier(surface, x, y, cycle_time, scale=1.0):
    h = 55 * scale
    leg_swing = math.sin(cycle_time) * 16 * scale
    head_r = int(6 * scale)
    head_center = (int(x), int(y - h + head_r))
    pygame.draw.circle(surface, COLOR_SILHOUETTE, head_center, head_r)
    pygame.draw.line(surface, COLOR_SILHOUETTE, (head_center[0] - 8 * scale, head_center[1] + 1), 
                     (head_center[0] + 8 * scale, head_center[1] + 1), int(3 * scale))
    torso_top = (int(x), int(y - h + head_r * 2))
    torso_bottom = (int(x), int(y - h * 0.45))
    pygame.draw.line(surface, COLOR_SILHOUETTE, torso_top, torso_bottom, int(7 * scale))
    pygame.draw.line(surface, COLOR_SILHOUETTE, torso_bottom, (int(x + leg_swing), int(y)), int(4 * scale))
    pygame.draw.line(surface, COLOR_SILHOUETTE, torso_bottom, (int(x - leg_swing), int(y)), int(4 * scale))
    
    # Arm & Shoulder (Fixed)
    shoulder = (int(x), int(y - h * 0.75))
    hand = (int(x + 12 * scale), int(y - h * 0.55))
    pygame.draw.line(surface, COLOR_SILHOUETTE, shoulder, hand, int(3 * scale))
    
    # Rifle & Bayonet
    rifle_start = (int(hand[0] - 10 * scale), int(hand[1] + 6 * scale))
    rifle_end = (int(hand[0] + 20 * scale), int(hand[1] - 22 * scale))
    pygame.draw.line(surface, COLOR_SILHOUETTE, rifle_start, rifle_end, int(2 * scale))
    pygame.draw.line(surface, (180, 180, 180), rifle_end, (int(rifle_end[0] + 4 * scale), int(rifle_end[1] - 7 * scale)), 1)

# ==============================================================================
# MAIN ENGINE & TIMELINE
# ==============================================================================
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Black Sabbath - War Pigs (Dynamic Cinematic Cut)")
    clock = pygame.time.Clock()

    has_audio = False
    try:
        pygame.mixer.init()
        pygame.mixer.music.load("war_pigs.mp3")
        pygame.mixer.music.play()
        has_audio = True
    except Exception:
        pass

    # Scene Simulation Pools
    planes = []
    bombs = []
    explosions = []
    flak_bursts = []
    
    # Pre-populate plane squads
    for i in range(4):
        planes.append(Plane(WIDTH + i * 220, 90 + (i % 2) * 45, speed=-3.2, plane_type="bomber"))

    start_ticks = pygame.time.get_ticks()
    time_offset = 0.0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RIGHT:
                    time_offset += 15.0
                elif event.key == pygame.K_LEFT:
                    time_offset = max(0.0, time_offset - 15.0)

        raw_sec = (pygame.mixer.music.get_pos() / 1000.0) if has_audio else ((pygame.time.get_ticks() - start_ticks) / 1000.0)
        current_sec = min(SONG_DURATION_SEC, raw_sec + time_offset)

        # ----------------------------------------------------------------------
        # SCENE CUT CONTROLLER
        # ----------------------------------------------------------------------
        scene_id = 0
        if 22.0 <= current_sec < 46.0: scene_id = 1
        elif 46.0 <= current_sec < 75.0: scene_id = 2
        elif 75.0 <= current_sec < 105.0: scene_id = 3
        elif 105.0 <= current_sec < 135.0: scene_id = 4
        elif 135.0 <= current_sec < 175.0: scene_id = 5
        elif current_sec >= 175.0: scene_id = 6

        frame = pygame.Surface((WIDTH, HEIGHT))
        shake_amp = 0

        # --- SCENE 0: RED AIR RAID SIREN ---
        if scene_id == 0:
            siren = (math.sin(current_sec * 4.0) + 1) * 0.5
            draw_gradient_sky(frame, (int(25 + siren * 65), 6, 10), (int(70 + siren * 100), 20, 10))
            beam_x = WIDTH // 2 + math.sin(current_sec * 1.5) * 350
            sl_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(sl_surf, (255, 240, 190, 45), [(WIDTH // 2, HEIGHT), (beam_x - 50, 0), (beam_x + 50, 0)])
            frame.blit(sl_surf, (0, 0))
            pygame.draw.rect(frame, COLOR_SILHOUETTE, (0, HEIGHT - 50, WIDTH, 50))
            for i in range(0, WIDTH, 120):
                pygame.draw.rect(frame, COLOR_SILHOUETTE, (i, HEIGHT - 110 - (i % 70), 55, 120))

        # --- SCENE 1: BOMBER FLEET & FLAK SKY ---
        elif scene_id == 1:
            draw_gradient_sky(frame, (10, 10, 18), (80, 25, 20))
            if random.random() < 0.12:
                flak_bursts.append(FlakBurst(random.randint(60, WIDTH - 60), random.randint(60, 260)))
            for p in planes:
                p.update(bombs)
                p.draw(frame)
                if p.x < -100: p.x = WIDTH + 100

        # --- SCENE 2: HEAVY RIFF (TROOPS + TANKS) ---
        elif scene_id == 2:
            beat = (math.sin(current_sec * 10.0) + 1) * 0.5
            shake_amp = 3 if beat > 0.8 else 0
            draw_gradient_sky(frame, (45, 10, 15), (140 + int(beat * 40), 40, 20))
            ground_y = HEIGHT - 65
            pygame.draw.rect(frame, COLOR_SILHOUETTE, (0, ground_y, WIDTH, 65))
            for i in range(8):
                sx = (i * 125 - int(current_sec * 90)) % (WIDTH + 100) - 50
                draw_soldier(frame, sx, ground_y + 12, cycle_time=current_sec * 9.0 + i, scale=1.0)
            draw_tank_and_artillery(frame, 780, ground_y + 10, cycle=current_sec)

        # --- SCENE 3: THE WAR TABLE (PUPPETEERS) ---
        elif scene_id == 3:
            draw_war_table_scene(frame, current_sec)

        # --- SCENE 4: FRONTLINE CARPET BOMBING ---
        elif scene_id == 4:
            draw_gradient_sky(frame, (20, 8, 12), (110, 35, 20))
            if random.random() < 0.08:
                planes.append(Plane(-60, random.randint(50, 160), speed=random.uniform(5.5, 8.5), plane_type="fighter"))
            for p in planes[:]:
                p.update(bombs)
                p.draw(frame)
                if p.x > WIDTH + 120 or p.x < -150:
                    planes.remove(p)
            ground_y = HEIGHT - 50
            pygame.draw.rect(frame, COLOR_SILHOUETTE, (0, ground_y, WIDTH, 50))
            for b in bombs[:]:
                b.update()
                b.draw(frame)
                if b.exploded:
                    explosions.append(Explosion(b.x, ground_y + 5, max_radius=random.randint(40, 75)))
                    shake_amp = 6
                    bombs.remove(b)

        # --- SCENE 5: GUITAR SOLO CATACLYSM ---
        elif scene_id == 5:
            strobe = (int(current_sec * 16) % 2 == 0)
            shake_amp = random.randint(4, 9)
            if strobe:
                draw_gradient_sky(frame, (220, 180, 60), (180, 20, 20))
            else:
                draw_gradient_sky(frame, (10, 6, 8), (70, 10, 15))
            
            ground_y = HEIGHT - 50
            pygame.draw.rect(frame, COLOR_SILHOUETTE, (0, ground_y, WIDTH, 50))

            if random.random() < 0.4:
                explosions.append(Explosion(random.randint(40, WIDTH - 40), ground_y + random.randint(-10, 10), max_radius=80))

            if random.random() < 0.15:
                planes.append(Plane(WIDTH + 50, random.randint(120, 240), speed=-11.0, plane_type="fighter"))
            for p in planes[:]:
                p.update(bombs)
                p.draw(frame)
                if p.x < -100: planes.remove(p)

        # --- SCENE 6: DESOLATE AFTERMATH & OUTRO ---
        elif scene_id == 6:
            fade = max(0.0, 1.0 - (current_sec - 175.0) / 38.0)
            draw_gradient_sky(frame, (int(12 * fade), int(10 * fade), int(14 * fade)), (int(45 * fade), int(20 * fade), int(15 * fade)))
            ground_y = HEIGHT - 50
            pygame.draw.rect(frame, (int(10 * fade), int(10 * fade), int(14 * fade)), (0, ground_y, WIDTH, 50))
            grave_x = WIDTH // 2
            pygame.draw.line(frame, COLOR_SILHOUETTE, (grave_x, ground_y - 65), (grave_x, ground_y), 5)
            pygame.draw.line(frame, COLOR_SILHOUETTE, (grave_x - 18, ground_y - 48), (grave_x + 18, ground_y - 48), 4)
            pygame.draw.circle(frame, COLOR_SILHOUETTE, (grave_x, ground_y - 65), 10)

        # ----------------------------------------------------------------------
        # UNIVERSAL PARTICLE UPDATES & DRAW
        # ----------------------------------------------------------------------
        for exp in explosions[:]:
            exp.update()
            exp.draw(frame)
            if exp.alpha <= 0: explosions.remove(exp)

        for flak in flak_bursts[:]:
            flak.update()
            flak.draw(frame)
            if flak.alpha <= 0: flak_bursts.remove(flak)

        # ----------------------------------------------------------------------
        # POST-PROCESSING: CINEMATIC LETTERBOX & CAMERA SHAKE
        # ----------------------------------------------------------------------
        screen.fill(COLOR_BLACK)
        sx = random.randint(-shake_amp, shake_amp) if shake_amp > 0 else 0
        sy = random.randint(-shake_amp, shake_amp) if shake_amp > 0 else 0
        screen.blit(frame, (sx, sy))

        # Letterbox Bars
        bar_height = 42
        pygame.draw.rect(screen, (0, 0, 0), (0, 0, WIDTH, bar_height))
        pygame.draw.rect(screen, (0, 0, 0), (0, HEIGHT - bar_height, WIDTH, bar_height))

        # Scene Tracker & HUD
        mins = int(current_sec // 60)
        secs = int(current_sec % 60)
        scene_names = ["AIR RAID SIREN", "BOMBERS INBOUND", "HEAVY RIFF BATTALION", "WAR TABLE / GENERALS", "CARPET BOMBING", "SOLO CATACLYSM", "DESOLATE AFTERMATH"]
        font = pygame.font.SysFont("monospace", 13, bold=True)
        hud_text = font.render(f"[{mins:02d}:{secs:02d} / 03:33] SCENE: {scene_names[scene_id]} | [<-/-> Seek]", True, (160, 140, 140))
        screen.blit(hud_text, (20, 14))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
