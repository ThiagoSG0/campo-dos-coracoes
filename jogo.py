"""
Campo dos Coracoes: expansao do exemplo "Acerte o alvo".

Executar no ambiente cgcourse: python jogo.py
WASD/setas: mover | Z: golpe de espada | X: projetil com mira automatica
Enter ou clique: iniciar, retomar ou reiniciar apos a derrota
1/2/3 (ou A/D + Enter): escolher melhoria | P/Tab: pausa | R: reiniciar
V: liga/desliga vsync | Esc: sair
"""
import glfw
import moderngl
import numpy as np
from numpy import arctan2 as atan2, cos, hypot, pi, sin

WIDTH, HEIGHT = 1120, 760
MAX_DT, SPEED = 0.05, 220.0
BOUNDS = (30.0, 1090.0, 32.0, 650.0)
ROOT = __file__.replace("\\", "/").rpartition("/")[0] or "."
INK = (0.055, 0.105, 0.12)
WHITE = (0.95, 0.97, 0.85)
RED = (0.96, 0.26, 0.36)
BLUE = (0.26, 0.75, 0.97)
GOLD = (1.0, 0.79, 0.28)
PURPLE = (0.73, 0.34, 0.96)
ENEMY_COLORS = (RED, (1.0, 0.59, 0.24), (0.50, 0.79, 0.45))


def unit(x, y):
    length = hypot(x, y)
    return (x / length, y / length) if length > 1e-9 else (0.0, 0.0)


def segment_hit(ax, ay, bx, by, cx, cy, radius):
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((cx - ax) * dx + (cy - ay) * dy) / length2)) if length2 else 0.0
    return (ax + t * dx - cx) ** 2 + (ay + t * dy - cy) ** 2 <= radius * radius


class Player:
    def __init__(self):
        self.x = WIDTH / 2
        self.y = 360.0
        self.radius = 14.0
        self.hp = 100.0
        self.max_hp = 100.0
        self.mana = 80.0
        self.max_mana = 80.0
        self.damage = 22.0
        self.regen = 9.0
        self.immune = 0.0
        self.facing = (0.0, 1.0)


class Enemy:
    def __init__(self, x, y, radius, speed, hp, max_hp, kind=0, boss=False, shot=2.4, flash=0.0):
        self.x, self.y = x, y
        self.radius, self.speed = radius, speed
        self.hp, self.max_hp = hp, max_hp
        self.kind, self.boss = kind, boss
        self.shot, self.flash = shot, flash


class Bullet:
    def __init__(self, x, y, vx, vy, damage, hostile=False, life=3.0):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.damage, self.hostile, self.life = damage, hostile, life


class Gem:
    def __init__(self, x, y, value, phase):
        self.x, self.y = x, y
        self.value, self.phase = value, phase


class Game:
    def __init__(self, seed=None):
        self.seed = seed
        self.reset(intro=True)

    def reset(self, intro=False):
        self.rng = np.random.default_rng(self.seed)
        self.player = Player()
        self.enemies, self.bullets, self.gems = [], [], []
        self.clock = self.score = self.xp = 0
        self.level, self.needed, self.selected = 1, 6, 0
        self.spawn_timer, self.boss_at = 0.9, 60.0
        self.swing_timer = self.slash = self.fire_timer = 0.0
        self.swing_angle = pi / 2
        self.state, self.resume_state = ("INTRO" if intro else "PLAY"), "PLAY"

    def pause(self):
        if self.state in ("PLAY", "LEVEL"):
            self.resume_state, self.state = self.state, "PAUSE"
        elif self.state == "PAUSE":
            self.state = self.resume_state

    def spawn(self, boss=False):
        p = self.player
        # Sorteia a borda mais de 300 unidades longe do jogador.
        candidates = []
        for _ in range(16):
            side = int(self.rng.integers(4))
            x = self.rng.uniform(55, WIDTH - 55)
            y = self.rng.uniform(60, 620)
            x, y = ((40 if side == 0 else WIDTH - 40), y) if side < 2 else (x, 45 if side == 2 else 635)
            candidates.append((x, y))
        safe = [q for q in candidates if hypot(q[0] - p.x, q[1] - p.y) > 300]
        x, y = self.rng.choice(safe) if safe else max(candidates, key=lambda q: hypot(q[0] - p.x, q[1] - p.y))
        kind = int(self.rng.integers(3)) if self.clock >= 12 else 0
        growth = 1.0 + self.clock / 95.0
        hp = (26.0, 19.0, 49.0)[kind] * growth
        radius, speed = (17.0, 14.0, 21.0)[kind], (56.0, 91.0, 39.0)[kind]
        if boss:
            radius, speed, hp = 43.0, 37.0, 460.0 * growth
        self.enemies.append(Enemy(x, y, radius, speed, hp, hp, kind, boss))

    def damage_enemy(self, enemy, amount):
        if enemy.hp <= 0:
            return
        enemy.hp -= amount
        enemy.flash = 0.12
        if enemy.hp <= 0:
            self.score += 1
            value = 20 if enemy.boss else (3 if enemy.kind == 2 else 2)
            self.gems.append(Gem(enemy.x, enemy.y, value, self.rng.uniform(0, 2 * pi)))

    def hurt(self, amount):
        p = self.player
        if self.state != "PLAY" or p.immune > 0:
            return
        p.hp = max(0.0, p.hp - amount)
        p.immune = 0.7
        if p.hp <= 0:
            self.state = "DEAD"

    def shoot(self):
        p = self.player
        if self.state != "PLAY" or p.mana < 16 or self.fire_timer > 0:
            return False
        target = min((e for e in self.enemies if e.hp > 0),
                     key=lambda e: hypot(e.x - p.x, e.y - p.y), default=None)
        dx, dy = p.facing
        if target is not None:
            ux, uy = unit(target.x - p.x, target.y - p.y)
            if ux or uy:
                dx, dy = ux, uy
        self.bullets.append(Bullet(p.x + dx * 20, p.y + dy * 20,
                                   dx * 520, dy * 520, p.damage * 1.9))
        p.mana -= 16
        self.fire_timer = 0.18
        return True

    def swing(self):
        if self.state != "PLAY" or self.swing_timer > 0:
            return False
        p = self.player
        fx, fy = p.facing
        self.swing_angle = atan2(fy, fx)
        self.swing_timer, self.slash = 0.42, 0.18
        # Golpe frontal de 120 graus, aplicado somente ao pressionar Z.
        for e in self.enemies:
            dx, dy = e.x - p.x, e.y - p.y
            distance = hypot(dx, dy)
            if distance <= 76 + e.radius and (distance <= e.radius or dx * fx + dy * fy >= distance * 0.5):
                self.damage_enemy(e, p.damage)
        self.enemies = [e for e in self.enemies if e.hp > 0]
        return True

    def check_level(self):
        if self.xp >= self.needed:
            self.xp -= self.needed
            self.level += 1
            self.needed += 4
            self.state, self.selected = "LEVEL", 0

    def choose(self, choice):
        if self.state != "LEVEL" or choice not in (0, 1, 2):
            return
        p = self.player
        if choice == 0:
            p.max_hp += 25
            p.hp = min(p.max_hp, p.hp + 40)
        elif choice == 1:
            p.damage += 7
        else:
            p.max_mana += 24
            p.mana = p.max_mana
            p.regen += 2.5
        self.state = "PLAY"
        self.check_level()

    def update(self, dt, direction=(0.0, 0.0)):
        if self.state != "PLAY":
            return
        dt = max(0.0, min(dt, MAX_DT))
        if not dt:
            return
        self.clock += dt
        p = self.player
        dx, dy = unit(*direction)
        if dx or dy:
            p.facing = dx, dy
        p.x = max(BOUNDS[0] + p.radius, min(BOUNDS[1] - p.radius, p.x + dx * SPEED * dt))
        p.y = max(BOUNDS[2] + p.radius, min(BOUNDS[3] - p.radius, p.y + dy * SPEED * dt))
        p.mana = min(p.max_mana, p.mana + p.regen * dt)
        p.immune = max(0.0, p.immune - dt)
        self.fire_timer = max(0.0, self.fire_timer - dt)
        self.swing_timer = max(0.0, self.swing_timer - dt)
        self.slash = max(0.0, self.slash - dt)
        self.spawn_timer -= dt
        while self.spawn_timer <= 0:
            if len(self.enemies) < 180:
                self.spawn()
            self.spawn_timer += max(0.20, 1.1 / (1.0 + self.clock / 28.0))
        if self.clock >= self.boss_at:
            self.spawn(boss=True)
            self.boss_at += 60.0
        self.move_enemies(dt)
        if self.state != "PLAY":
            return
        self.move_bullets(dt)
        if self.state != "PLAY":
            return
        for gem in self.gems[:]:
            distance = hypot(gem.x - p.x, gem.y - p.y)
            if distance < 115:
                ux, uy = unit(p.x - gem.x, p.y - gem.y)
                step = min(distance, 290 * dt)
                gem.x += ux * step
                gem.y += uy * step
            if hypot(gem.x - p.x, gem.y - p.y) < p.radius + 9:
                self.gems.remove(gem)
                self.xp += gem.value
                self.check_level()
                if self.state == "LEVEL":
                    return

    def move_enemies(self, dt):
        p = self.player
        grid = {}
        for e in self.enemies:
            ux, uy = unit(p.x - e.x, p.y - e.y)
            e.x += ux * e.speed * dt
            e.y += uy * e.speed * dt
            cell = int(e.x // 64), int(e.y // 64)
            # Vizinhos na grade evitam comparar todos os pares da horda.
            for gx in range(cell[0] - 1, cell[0] + 2):
                for gy in range(cell[1] - 1, cell[1] + 2):
                    for other in grid.get((gx, gy), ()):
                        gap = hypot(e.x - other.x, e.y - other.y)
                        if 0 < gap < e.radius + other.radius:
                            vx, vy = unit(e.x - other.x, e.y - other.y)
                            push = min((e.radius + other.radius - gap) / 2, 45 * dt)
                            e.x += vx * push
                            e.y += vy * push
            grid.setdefault(cell, []).append(e)
            e.flash = max(0.0, e.flash - dt)
            if hypot(e.x - p.x, e.y - p.y) < e.radius + p.radius:
                self.hurt(24 if e.boss else 12)
                if self.state == "DEAD":
                    return
            if e.boss:
                e.shot -= dt
                if e.shot <= 0:
                    e.shot += 2.4
                    a = atan2(p.y - e.y, p.x - e.x)
                    for i in range(-3, 4):
                        angle, speed = a + i * 0.24, 155.0 + self.clock * 0.12
                        self.bullets.append(Bullet(e.x, e.y, cos(angle) * speed,
                                                   sin(angle) * speed, 18, True, 6.0))

    def move_bullets(self, dt):
        p = self.player
        for b in self.bullets:
            ox, oy = b.x, b.y
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.life -= dt
            if b.hostile:
                if segment_hit(ox, oy, b.x, b.y, p.x, p.y, p.radius + 5):
                    b.life = 0
                    self.hurt(b.damage)
                    if self.state == "DEAD":
                        break
            else:
                hits = [e for e in self.enemies if e.hp > 0 and
                        segment_hit(ox, oy, b.x, b.y, e.x, e.y, e.radius + 5)]
                if hits:
                    e = min(hits, key=lambda e: hypot(e.x - ox, e.y - oy))
                    self.damage_enemy(e, b.damage)
                    b.life = 0
            if not (-25 < b.x < WIDTH + 25 and -25 < b.y < HEIGHT + 25):
                b.life = 0
        self.bullets = [b for b in self.bullets if b.life > 0]
        self.enemies = [e for e in self.enemies if e.hp > 0]


def fan(x, y):
    points = np.column_stack((x, y))
    return np.vstack(((0, 0), points, points[:1])).astype("f4")


def geometries():
    t = np.linspace(0, 2 * pi, 180, endpoint=False)
    x = 16 * np.sin(t) ** 3
    y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
    y -= (y.max() + y.min()) / 2
    heart = fan(x / 17, y / 17)
    t = np.linspace(0, 2 * pi, 48, endpoint=False)
    circle = fan(np.cos(t), np.sin(t))
    t = np.linspace(0, 2 * pi, 14, endpoint=False) + pi / 2
    r = np.array([1.0, 0.43] * 7)
    star = fan(r * np.cos(t), r * np.sin(t))
    return {"heart": heart, "circle": circle, "star": star,
            "square": np.array([(-1, -1), (1, -1), (1, 1), (-1, 1)], dtype="f4"),
            "triangle": np.array([(-1, -1), (1, 0), (-1, 1)], dtype="f4")}


class Renderer:
    def __init__(self, ctx):
        self.ctx, self.resources, self.forms = ctx, [], {}
        with open(ROOT + "/shaders/jogo.vert", encoding="utf-8") as vertex_file:
            vertex_source = vertex_file.read()
        with open(ROOT + "/shaders/jogo.frag", encoding="utf-8") as fragment_file:
            fragment_source = fragment_file.read()
        self.program = ctx.program(vertex_shader=vertex_source, fragment_shader=fragment_source)
        self.resources.append(self.program)
        for name, xy in geometries().items():
            # Cores dos quatro cantos do 04_quadrado.py, estendidas ao coracao.
            x, y = (xy[:, 0] + 1) / 2, (xy[:, 1] + 1) / 2
            colors = np.column_stack((1 - x, np.abs(x - y), np.minimum(x, y), np.ones(len(xy))))
            positions = np.column_stack((xy, np.zeros(len(xy)), np.ones(len(xy))))
            vbo = ctx.buffer(np.column_stack((positions, colors)).astype("f4").tobytes())
            self.resources.append(vbo)
            ebo = None
            if name == "square":
                ebo = ctx.buffer(np.array([0, 1, 2, 2, 3, 0], dtype="u4").tobytes())
                self.resources.append(ebo)
            vao = ctx.vertex_array(self.program, [(vbo, "4f 4f", "vPosition", "vColors")], index_buffer=ebo)
            self.resources.append(vao)
            mode = moderngl.TRIANGLES if name in ("square", "triangle") else moderngl.TRIANGLE_FAN
            self.forms[name] = vao, mode
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.program["u_canvas"].value = WIDTH, HEIGHT

    def shape(self, name, x, y, sx, sy, color, angle=0.0, alpha=1.0, rainbow=False):
        prog = self.program
        prog["u_position"].value = float(x), float(y)
        prog["u_scale"].value = float(sx), float(sy)
        prog["u_angle"].value = float(angle)
        prog["u_color"].value = (*color, alpha)
        prog["u_rainbow"].value = float(rainbow)
        vao, mode = self.forms["circle" if name in ("ring", "swing") else name]
        if name == "ring":
            vao.render(moderngl.LINE_LOOP, vertices=48, first=1)
        elif name == "swing":
            vao.render(moderngl.LINE_STRIP, vertices=17, first=1)
        else:
            vao.render(mode)

    def rect(self, x, y, w, h, color, alpha=1.0):
        self.shape("square", x, y, w / 2, h / 2, color, alpha=alpha)

    def heart(self, x, y, radius, color, target=None, rainbow=False, flash=False):
        self.shape("heart", x, y, radius, radius, WHITE if flash else color, rainbow=rainbow and not flash)
        for side in (-1, 1):
            ex, ey = x + side * radius * 0.27, y + radius * 0.32
            ux, uy = unit(target[0] - ex, target[1] - ey) if target else (0, 0)
            self.shape("circle", ex, ey, radius * 0.19, radius * 0.19, WHITE)
            self.shape("circle", ex + ux * radius * 0.08, ey + uy * radius * 0.08,
                       radius * 0.095, radius * 0.095, INK)

    def bar(self, x, y, width, height, fraction, color):
        fraction = max(0.0, min(1.0, fraction))
        self.rect(x + width / 2, y, width + 4, height + 4, INK)
        self.rect(x + width / 2, y, width, height, (0.13, 0.23, 0.24))
        if fraction:
            self.rect(x + width * fraction / 2, y, width * fraction, height, color)

    def hero(self, game):
        p = game.player
        self.rect(p.x, p.y, 30, 30, INK)
        self.rect(p.x, p.y + 1, 24, 25, WHITE if p.immune > 0 else BLUE)
        for side in (-1, 1):
            self.rect(p.x + side * 5, p.y + 4, 4, 5, INK)
        self.rect(p.x, p.y - 6, 15, 4, GOLD)
        if game.slash:
            progress = 1 - game.slash / 0.18
            angle = game.swing_angle - pi / 3 + progress * 2 * pi / 3
            self.shape("swing", p.x, p.y, 76, 76, GOLD,
                       angle=game.swing_angle - pi / 3, alpha=game.slash / 0.18)
            self.shape("square", p.x + cos(angle) * 47, p.y + sin(angle) * 47,
                       28, 3, WHITE, angle=angle)

    def hud(self, g):
        p = g.player
        self.rect(WIDTH / 2, 711, WIDTH, 98, INK)
        self.rect(WIDTH / 2, 663, WIDTH, 2, GOLD, 0.65)
        self.shape("heart", 37, 722, 12, 12, RED)
        self.bar(61, 722, 225, 13, p.hp / p.max_hp, RED)
        self.shape("circle", 326, 722, 10, 10, BLUE)
        self.bar(350, 722, 190, 13, p.mana / p.max_mana, BLUE)
        self.shape("star", 583, 722, 13, 13, GOLD)
        for i in range(min(10, 1 + round((p.damage - 22) / 7))):
            self.rect(607 + i * 12, 722, 7, 12, GOLD)
        self.shape("square", 37, 684, 6, 6, GOLD, angle=pi / 4)
        self.bar(61, 684, 661, 7, g.xp / g.needed, GOLD)
        # Cada grupo de pontos representa uma casa decimal do placar.
        digits = [int(digit) for digit in str(g.score).zfill(4)]
        spacing = min(52, 270 / len(digits))
        for column, digit in enumerate(digits):
            for i in range(9):
                self.shape("circle", 795 + column * spacing + i % 3 * 10,
                           730 - i // 3 * 10, 2.8, 2.8, GOLD if i < digit else (0.18, 0.29, 0.29))
        self.shape("heart", 763, 720, 9, 9, RED)
        self.bar(795, 684, 270, 5, (g.clock % 60) / 60, PURPLE)
        bosses = [e for e in g.enemies if e.boss]
        if bosses:
            boss = bosses[0]
            self.shape("heart", 364, 639, 12, 12, PURPLE, rainbow=True)
            self.bar(388, 639, 370, 8, boss.hp / boss.max_hp, PURPLE)

    def overlay(self, g):
        if g.state == "PLAY":
            return
        self.rect(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT, INK, 0.72)
        if g.state == "LEVEL":
            for i, (name, color) in enumerate((("heart", RED), ("star", GOLD), ("circle", BLUE))):
                x = 330 + i * 230
                self.rect(x, 371, 204, 252, color if i == g.selected else (0.21, 0.32, 0.32))
                self.rect(x, 371, 196, 244, INK)
                self.shape(name, x, 371, 43, 43, color)
            return
        self.rect(560, 384, 456, 292, GOLD if g.state == "INTRO" else (0.26, 0.45, 0.44))
        self.rect(560, 384, 450, 286, INK)
        if g.state == "INTRO":
            self.heart(560, 428, 53, RED, (600, 407), rainbow=True)
            self.shape("triangle", 560, 319, 17, 21, WHITE)
        elif g.state == "PAUSE":
            for x in (542, 578):
                self.rect(x, 384, 19, 70, GOLD)
        elif g.state == "DEAD":
            self.shape("heart", 560, 384, 43, 43, (0.39, 0.32, 0.35))
            self.rect(560, 384, 7, 74, INK)

    def draw(self, game, framebuffer):
        fw, fh = framebuffer
        if fw <= 0 or fh <= 0:
            return
        self.ctx.clear(0.035, 0.07, 0.08, 1)
        scale = min(fw / WIDTH, fh / HEIGHT)
        vw, vh = round(WIDTH * scale), round(HEIGHT * scale)
        self.ctx.viewport = ((fw - vw) // 2, (fh - vh) // 2, vw, vh)
        self.rect(560, 342, 1108, 640, (0.15, 0.30, 0.24))
        self.rect(560, 342, 1080, 616, (0.25, 0.43, 0.31))
        for gem in game.gems:
            glow = 1 + 0.15 * sin(game.clock * 4 + gem.phase)
            self.shape("square", gem.x, gem.y, 5 * glow, 5 * glow, GOLD, angle=pi / 4 + game.clock)
        p = game.player
        for e in sorted(game.enemies, key=lambda e: -e.y):
            pulse = 1 + 0.045 * sin(game.clock * 4 + e.x)
            r = e.radius * pulse
            self.heart(e.x, e.y, r, ENEMY_COLORS[e.kind], (p.x, p.y), e.boss, e.flash > 0)
            if e.boss and e.shot < 0.65:
                self.shape("ring", e.x, e.y, r + 7, r + 7, PURPLE)
            if e.hp < e.max_hp and not e.boss:
                self.bar(e.x - r, e.y + r + 6, r * 2, 3, e.hp / e.max_hp, RED)
        self.hero(game)
        for b in game.bullets:
            color = PURPLE if b.hostile else BLUE
            self.shape("circle", b.x, b.y, 5, 5, color)
        self.hud(game)
        self.overlay(game)

    def release(self):
        for resource in reversed(self.resources):
            resource.release()


class App:
    def __init__(self, visible=True):
        self.window = self.ctx = self.renderer = None
        self.vsync, self.discard_dt = True, True
        glfw.set_error_callback(lambda code, message: print(f"GLFW {code}: {message}"))
        if not glfw.init():
            raise RuntimeError("GLFW nao inicializou.")
        try:
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 0)
            glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
            glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
            glfw.window_hint(glfw.SAMPLES, 4)
            glfw.window_hint(glfw.VISIBLE, visible)
            self.window = glfw.create_window(WIDTH, HEIGHT, "Campo dos Coracoes | FPS: -- | VSync ON", None, None)
            if not self.window:
                raise RuntimeError("Nao foi possivel criar OpenGL 4.0 Core.")
            glfw.make_context_current(self.window)
            glfw.swap_interval(1)
            self.ctx = moderngl.create_context(require=400)
            self.renderer, self.game = Renderer(self.ctx), Game()
            glfw.set_key_callback(self.window, self.key)
            glfw.set_mouse_button_callback(self.window, self.mouse)
            glfw.set_window_focus_callback(self.window, self.focus)
            self.last = self.fps_since = glfw.get_time()
            self.frames = 0
        except Exception:
            self.close()
            raise

    def key(self, window, key, scancode, action, mods):
        if action != glfw.PRESS:
            return
        g, previous = self.game, self.game.state
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)
        elif key == glfw.KEY_V:
            self.vsync = not self.vsync
            glfw.swap_interval(1 if self.vsync else 0)
        elif key == glfw.KEY_R:
            g.reset()
            self.discard_dt = True
        elif key in (glfw.KEY_P, glfw.KEY_TAB):
            g.pause()
        elif key in (glfw.KEY_ENTER, glfw.KEY_KP_ENTER):
            if g.state in ("INTRO", "DEAD"):
                g.reset()
            elif g.state == "PAUSE":
                g.pause()
            elif g.state == "LEVEL":
                g.choose(g.selected)
        elif key == glfw.KEY_X:
            g.shoot()
        elif key == glfw.KEY_Z:
            g.swing()
        elif g.state == "LEVEL":
            if glfw.KEY_1 <= key <= glfw.KEY_3:
                g.choose(key - glfw.KEY_1)
            elif key in (glfw.KEY_LEFT, glfw.KEY_A):
                g.selected = (g.selected - 1) % 3
            elif key in (glfw.KEY_RIGHT, glfw.KEY_D):
                g.selected = (g.selected + 1) % 3
        if previous != g.state:
            self.discard_dt = True

    def pointer(self):
        x, y = glfw.get_cursor_pos(self.window)
        w, h = glfw.get_window_size(self.window)
        scale = min(w / WIDTH, h / HEIGHT)
        if scale <= 0:
            return -1.0, -1.0
        return (x - (w - WIDTH * scale) / 2) / scale, (h - y - (h - HEIGHT * scale) / 2) / scale

    def mouse(self, window, button, action, mods):
        if button != glfw.MOUSE_BUTTON_LEFT or action != glfw.PRESS:
            return
        g, previous = self.game, self.game.state
        x, y = self.pointer()
        if not (0 <= x <= WIDTH and 0 <= y <= HEIGHT):
            return
        if g.state in ("INTRO", "DEAD"):
            g.reset()
        elif g.state == "PAUSE":
            g.pause()
        elif g.state == "LEVEL" and 245 <= y <= 497:
            for i in range(3):
                if abs(x - (330 + i * 230)) <= 102:
                    g.choose(i)
                    break
        if previous != g.state:
            self.discard_dt = True

    def focus(self, window, focused):
        if not focused:
            if self.game.state in ("PLAY", "LEVEL"):
                self.game.pause()
            self.discard_dt = True

    def held_direction(self):
        def held(*keys):
            return any(glfw.get_key(self.window, key) == glfw.PRESS for key in keys)
        return (int(held(glfw.KEY_D, glfw.KEY_RIGHT)) - int(held(glfw.KEY_A, glfw.KEY_LEFT)),
                int(held(glfw.KEY_W, glfw.KEY_UP)) - int(held(glfw.KEY_S, glfw.KEY_DOWN)))

    def frame(self):
        glfw.poll_events()
        now = glfw.get_time()
        dt = min(MAX_DT, max(0.0, now - self.last))
        self.last = now  # Atualizado tambem durante pausa e telas de escolha.
        if self.discard_dt:
            dt, self.discard_dt = 0.0, False
        self.game.update(dt, self.held_direction())
        self.renderer.draw(self.game, glfw.get_framebuffer_size(self.window))
        glfw.swap_buffers(self.window)
        self.frames += 1
        elapsed = now - self.fps_since
        if elapsed >= 0.5:
            glfw.set_window_title(self.window, f"Campo dos Coracoes | FPS: {self.frames / elapsed:.0f} | "
                                  f"VSync {'ON' if self.vsync else 'OFF'}")
            self.frames, self.fps_since = 0, now

    def run(self):
        print("WASD/setas: mover | Z: swing frontal | X: projetil com mira automatica")
        print("Enter: iniciar/confirmar | 1/2/3: melhoria | P/Tab: pausa | R: reiniciar | V: vsync | Esc: sair")
        print(f"OpenGL: {self.ctx.info['GL_VERSION']} | GPU: {self.ctx.info['GL_RENDERER']}")
        while not glfw.window_should_close(self.window):
            self.frame()

    def close(self):
        if self.renderer:
            self.renderer.release()
        if self.ctx:
            self.ctx.release()
        if self.window:
            glfw.destroy_window(self.window)
        glfw.terminate()


if __name__ == "__main__":
    app = App()
    try:
        app.run()
    finally:
        app.close()
