"""Verificacao das regras, callbacks e renderizacao real; fora do jogo."""
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from math import cos, hypot, sin
from pathlib import Path
import pickle
import sys
import time
import tokenize
from io import StringIO
from unittest.mock import patch

import glfw
import moderngl
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DETAILED = ROOT / "versao_comentada" / "jogo.py"
sys.path.insert(0, str(ROOT))
from jogo import App, Game, Enemy, Bullet, Gem, MAX_DT, SPEED, WIDTH, HEIGHT, geometries, segment_hit

OUT = ROOT / "validacao"
checks, metrics = [], {}


def check(condition, name):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


def trial():
    g = Game(seed=123)
    g.reset()
    g.spawn_timer = 1e6
    return g


def enemy(x, y, hp=22, boss=False):
    return Enemy(x, y, 43 if boss else 17, 0, hp, hp, boss=boss)


def rules():
    for state in ("INTRO", "PAUSE", "LEVEL", "DEAD"):
        g = trial()
        g.enemies = [enemy(50, 80)]
        g.bullets = [Bullet(500, 200, 100, 100, 10)]
        g.gems = [Gem(550, 350, 10, 1)]
        g.state = state
        before = pickle.dumps(g.__dict__)
        for _ in range(20):
            g.update(8.0, (1, 1))
        check(not g.swing() and not g.shoot(), f"Estado {state} bloqueia ambos os ataques")
        check(before == pickle.dumps(g.__dict__), f"Estado {state} congela todo o modelo, inclusive RNG")
    results = []
    for fps in (30, 60, 144, 240):
        for direction in ((1, 0), (1, 1)):
            g = trial()
            x, y = g.player.x, g.player.y
            for _ in range(fps):
                g.update(1 / fps, direction)
            distance = hypot(g.player.x - x, g.player.y - y)
            results.append({"fps": fps, "direction": direction, "distance": distance})
            check(abs(distance - SPEED) < 1e-7, f"Velocidade constante: {fps} FPS, direcao {direction}")
    metrics["movimento"] = results
    g = trial()
    x = g.player.x
    g.update(5, (1, 0))
    check(abs(g.player.x - x - SPEED * MAX_DT) < 1e-8, "Travada de cinco segundos limitada a 0,05 s")
    before = pickle.dumps(g.__dict__)
    g.update(-1, (1, 0))
    check(before == pickle.dumps(g.__dict__), "Intervalo negativo nao movimenta nem inverte relogio")
    for _ in range(200):
        g.update(MAX_DT, (1, 1))
    check(g.player.x <= 1076 and g.player.y <= 636, "Colisao com limites preserva o jogador no campo")

    g = trial()
    p = g.player
    p.facing = (1, 0)
    e = enemy(p.x + 60, p.y)
    back = enemy(p.x - 55, p.y)
    side = enemy(p.x + 20, p.y + 60)
    far = enemy(p.x + 110, p.y)
    g.enemies = [e, back, side, far]
    for _ in range(150):
        g.update(1 / 60)
    check(all(target.hp == 22 for target in g.enemies) and not g.gems and not g.bullets and not g.slash,
          "Sem pressionar ataque, inimigos no alcance nao recebem dano nem surgem projeteis")
    check(g.swing() and g.score == 1 and len(g.gems) == 1 and e not in g.enemies and p.hp == 100,
          "Swing manual derrota alvo frontal, soma um ponto e concede XP")
    check(all(target.hp == 22 for target in (back, side, far)), "Swing nao acerta atras, fora do arco ou fora do alcance")
    later = enemy(p.x + 58, p.y)
    g.enemies.append(later)
    check(not g.swing() and later.hp == 22, "Cooldown bloqueia outro swing imediato")
    for _ in range(60):
        g.update(1 / 60)
    check(later.hp == 22 and not g.slash, "Animacao e fim do cooldown nao causam dano por conta propria")
    check(g.swing() and later.hp <= 0, "Novo pressionamento apos o cooldown aplica outro swing")
    gems_before = g.gems[:]
    g.damage_enemy(e, 999)
    check(g.gems == gems_before and g.score == 2, "Acertar inimigo morto nao duplica o ponto nem a gema")
    g = trial()
    g.enemies = [enemy(g.player.x, g.player.y, 999)]
    g.update(1 / 60)
    hp = g.player.hp
    for _ in range(20):
        g.update(1 / 60)
    check(hp == 88 and g.player.hp == hp, "Contato causa dano com intervalo de invulnerabilidade")
    g.player.immune, g.player.hp = 0, 5
    g.update(1 / 60)
    check(g.state == "DEAD" and g.player.hp == 0, "Contato letal encerra a partida e limita vida a zero")

    g = trial()
    p = g.player
    near, far = enemy(p.x + 43, p.y), enemy(p.x + 75, p.y)
    g.enemies = [far, near]
    g.bullets = [Bullet(p.x, p.y, 2400, 0, 50)]
    g.update(MAX_DT)
    check(near.hp <= 0 and far.hp > 0 and not g.bullets and len(g.gems) == 1 and g.score == 1,
          "Colisao varrida impede atravessamento e atinge somente o primeiro alvo")
    check(segment_hit(0, 0, 0, 0, 0, 0, 1) and not segment_hit(0, 0, 0, 0, 5, 0, 1),
          "Colisao de segmento degenerado e segura")
    g = trial()
    p = g.player
    g.bullets = [Bullet(p.x - 60, p.y, 2400, 0, 18, True)]
    g.update(MAX_DT)
    check(p.hp == 82 and not g.bullets, "Ponto roxo acerta o protagonista e desaparece")
    g = trial()
    g.player.mana = 16
    check(g.shoot() and g.player.mana == 0, "Magia consome exatamente 16 de mana")
    check(not g.shoot() and len(g.bullets) == 1, "Sem mana nao dispara nem cria projetil extra")
    for _ in range(120):
        g.update(1 / 60)
    check(abs(g.player.mana - 18) < 1e-7, "Mana regenera por segundo")
    g.player.mana = g.player.max_mana
    g.update(MAX_DT)
    check(g.player.mana == g.player.max_mana, "Mana regenerada respeita capacidade maxima")

    g = trial()
    g.gems = [Gem(g.player.x + 30, g.player.y, 6, 0)]
    for _ in range(30):
        g.update(1 / 60)
    check(not g.gems and g.state == "LEVEL" and g.level == 2 and g.xp == 0,
          "XP e atraido, coletado e abre escolha ao atingir o limiar")
    for choice in range(3):
        g = trial()
        g.state = "LEVEL"
        g.player.hp, g.player.mana = 70, 10
        g.choose(choice)
        p = g.player
        expected = ((125, 110, 22, 80, 10, 9), (100, 70, 29, 80, 10, 9), (100, 70, 22, 104, 104, 11.5))[choice]
        check((p.max_hp, p.hp, p.damage, p.max_mana, p.mana, p.regen) == expected,
              f"Melhoria {choice + 1} altera somente os atributos previstos")
        before = pickle.dumps(g.__dict__)
        g.choose(choice)
        check(before == pickle.dumps(g.__dict__), f"Melhoria {choice + 1} nao pode ser aplicada duas vezes")
    g = trial()
    g.xp = 40
    g.check_level()
    choices = 0
    while g.state == "LEVEL":
        g.choose(1)
        choices += 1
    check(choices == 3 and g.level == 4 and g.xp == 10 and g.needed == 18,
          "XP excedente preservado e cada nivel exige uma escolha")
    g.state, g.selected = "LEVEL", 2
    g.pause()
    g.pause()
    check(g.state == "LEVEL" and g.selected == 2, "Pausar escolha retoma exatamente a mesma escolha")

    g = trial()
    g.spawn()
    early_hp = g.enemies[-1].max_hp
    g.clock = 120
    g.spawn()
    check(g.enemies[-1].max_hp > early_hp, "Inimigos tardios tem mais vida mesmo na variante mais fragil")
    counts = []
    for start in (0, 120):
        g = trial()
        g.clock, g.spawn_timer, g.boss_at = start, 0, 1e6
        g.player.immune = 1e6
        for _ in range(300):
            g.update(1 / 60)
        counts.append(len(g.enemies))
    check(counts[1] > counts[0], "Frequencia de spawn aumenta com o tempo")
    metrics["spawns_em_5s"] = counts
    g = trial()
    g.clock = 59.99
    g.update(0.02)
    bosses = [e for e in g.enemies if e.boss]
    check(len(bosses) == 1 and g.boss_at == 120, "Chefe aparece aos 60 segundos sem duplicar no quadro seguinte")
    boss = bosses[0]
    boss.shot = 0
    g.update(0.02)
    check(len(g.bullets) == 7 and all(b.hostile for b in g.bullets), "Chefe dispara leque de sete pontos roxos")
    g = trial()
    boss = enemy(g.player.x + 200, g.player.y, 70, boss=True)
    g.enemies = [boss]
    for _ in range(90):
        g.shoot()
        g.update(1 / 120)
    check(boss.hp <= 0 and g.score == 1 and not g.enemies and sum(gem.value for gem in g.gems) == 20,
          "Derrotar o chefe com magia soma um ponto e concede uma gema de 20 XP")
    g.player.mana, g.player.hp, g.player.damage, g.xp = 0, 1, 200, 5
    g.reset()
    check(g.state == "PLAY" and g.player.hp == 100 and g.player.mana == 80 and g.player.damage == 22
          and g.clock == 0 and g.xp == 0 and g.level == 1 and not g.enemies and not g.bullets,
          "Reinicio limpa inimigos, projeteis, efeitos, tempo, XP e melhorias")


def code_audit():
    source = (ROOT / "jogo.py").read_text(encoding="utf-8")
    sources = {"essencial": source}
    if DETAILED.is_file():
        detailed = DETAILED.read_text(encoding="utf-8")
        check(ast.dump(ast.parse(source)) == ast.dump(ast.parse(detailed)), "Versoes Python tem AST identica")
        sources["comentada"] = detailed
    counts = {}
    for label, text in sources.items():
        lines = set()
        ignored = {tokenize.ENCODING, tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                   tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}
        for token in tokenize.generate_tokens(StringIO(text).readline):
            if token.type not in ignored:
                lines.update(range(token.start[0], token.end[0] + 1))
        counts[label] = len(lines)
        check(len(lines) <= 1000, f"Versao {label} tem no maximo 1000 linhas sem comentarios")
    metrics["linhas_python_sem_comentarios"] = counts
    shader_lines = 0
    for name in ("jogo.vert", "jogo.frag"):
        basic_shader = (ROOT / "shaders" / name).read_text(encoding="utf-8")
        clean = lambda text: [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("//")]
        if DETAILED.is_file():
            commented_shader = (DETAILED.parent / "shaders" / name).read_text(encoding="utf-8")
            check(clean(basic_shader) == clean(commented_shader), f"Shader {name} tem instrucoes identicas nas duas versoes")
        shader_lines += len(clean(basic_shader))
    metrics["linhas_python_e_glsl_sem_comentarios"] = counts["essencial"] + shader_lines
    check(counts["essencial"] + shader_lines <= 1000, "Python e ambos os shaders juntos ficam abaixo de 1000 linhas")
    allowed = {"glfw", "moderngl", "numpy", "glm", "PIL"}
    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module.split(".")[0])
    check(imports <= allowed, "Runtime importa apenas bibliotecas permitidas pelo enunciado")
    metrics["imports_do_jogo"] = sorted(imports)
    radii = np.linalg.norm(geometries()["star"][1:-1], axis=1)
    check(len(radii) == 14 and np.allclose(radii[::2], 1) and np.allclose(radii[1::2], 0.43),
          "Estrela de dano tem exatamente sete pontas alternadas com sete vales")
    reference = ROOT.parent / "codigos-aula" / "06_senhor_coracao.py"
    if reference.exists():
        tree = ast.parse(reference.read_text(encoding="utf-8"))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("leque", "curva_coracao")]
        namespace = {"np": np}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(reference), "exec"), namespace)
        check(np.allclose(namespace["curva_coracao"]()[:, :2], geometries()["heart"]),
              "Curva do Senhor Coracao e numericamente igual a referencia original")


def snapshot(app, name=None):
    app.renderer.draw(app.game, glfw.get_framebuffer_size(app.window))
    app.ctx.finish()
    w, h = glfw.get_framebuffer_size(app.window)
    data = app.ctx.screen.read(viewport=(0, 0, w, h), components=3, alignment=1)
    result = Image.frombytes("RGB", (w, h), data).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if name:
        result.save(OUT / f"{name}.png")
    return result


def scene():
    g = trial()
    g.clock, g.score, g.xp, g.needed = 82.3, 137, 11, 22
    g.boss_at = 120
    g.player.hp, g.player.mana = 72, 49
    layout = [(255, 470, 0), (870, 410, 1), (790, 210, 2), (343, 230, 2)]
    for x, y, kind in layout:
        e = Enemy(x, y, (17, 14, 21)[kind], 56, 35, 35, kind)
        g.enemies.append(e)
    g.enemies.append(Enemy(760, 430, 43, 37, 480, 720, boss=True, shot=0.4))
    for i in range(7):
        g.bullets.append(Bullet(697 - i * 12, 395 - i * 16, -150, -60, 18, True))
    g.bullets.append(Bullet(650, 392, 400, 180, 50))
    g.gems = [Gem(x, y, 2, i) for i, (x, y) in enumerate(((470, 300), (620, 300), (730, 320)))]
    return g


def graphics():
    app = App(visible=False)
    expected_pixels = None
    try:
        check(app.ctx.version_code >= 400, "Contexto real OpenGL 4.0 Core e shaders compilados")
        metrics["opengl"] = {key: app.ctx.info[key] for key in ("GL_VERSION", "GL_RENDERER", "GL_VENDOR")}
        buffers = [r for r in app.renderer.resources if isinstance(r, moderngl.Buffer)]
        hashes = [hashlib.sha256(b.read()).hexdigest() for b in buffers]
        check(len(buffers) == 6, "Cinco VBOs e um EBO criados na inicializacao")
        square_colors = np.frombuffer(buffers[3].read(), dtype="f4").reshape(-1, 8)[:, 4:]
        check(np.array_equal(square_colors, [[1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 1], [1, 1, 0, 1]]),
              "Atributos RGBA dos quatro cantos iguais a 04_quadrado.py")
        snapshot(app, "inicio")
        app.game = scene()
        app.game.player.facing = (1, 0)
        app.game.swing()
        app.game.update(MAX_DT)
        snapshot(app, "swing")
        app.game = scene()
        expected_pixels = snapshot(app, "partida").tobytes()
        app.game.pause()
        before = snapshot(app, "pausa")
        for _ in range(15):
            app.game.update(MAX_DT, (1, 1))
        after = snapshot(app, "pausa_depois")
        check(before.tobytes() == after.tobytes(), "Pixels da pausa sao identicos apos 15 atualizacoes")
        app.game.state = "LEVEL"
        snapshot(app, "melhorias")
        app.game.state, app.game.player.hp = "DEAD", 0
        snapshot(app, "derrota")
        app.game = trial()
        app.game.enemies = [enemy(750, 400)]
        before = snapshot(app, "animacao_antes")
        for _ in range(10):
            app.game.update(MAX_DT)
        after = snapshot(app, "animacao_depois")
        crop = (725, 335, 775, 385)
        check(before.crop(crop).tobytes() != after.crop(crop).tobytes(), "Coracao pulsa autonomamente sem entrada")
        crop = (485, 325, 635, 475)
        check(before.crop(crop).tobytes() == after.crop(crop).tobytes(), "Heroi parado fica sem orbita ou ataque automatico visivel")

        eye_centroids = []
        for target in ((0, 380), (1120, 380)):
            app.ctx.clear(0.25, 0.43, 0.31, 1)
            app.renderer.heart(560, 380, 90, (1, 0, 0), target)
            app.ctx.finish()
            raw = np.frombuffer(app.ctx.screen.read(components=3, alignment=1), dtype=np.uint8).reshape(HEIGHT, WIDTH, 3)
            cx, cy = 560 - 90 * 0.27, 380 + 90 * 0.32
            yy, xx = np.indices((HEIGHT, WIDTH))
            mask = (xx - cx) ** 2 + (yy - cy) ** 2 < 15 ** 2
            mask &= (raw[:, :, 0] < 40) & (raw[:, :, 1] < 50) & (raw[:, :, 2] < 50)
            eye_centroids.append(float(xx[mask].mean()))
        check(eye_centroids[1] - eye_centroids[0] > 7, "Pixels das pupilas acompanham o protagonista nos dois sentidos")
        metrics["centros_pupila_x"] = eye_centroids

        app.game = trial()
        def press(key, action=glfw.PRESS):
            app.key(app.window, key, 0, action, 0)
        press(glfw.KEY_P)
        check(app.game.state == "PAUSE", "Callback P pausa")
        press(glfw.KEY_P, glfw.REPEAT)
        check(app.game.state == "PAUSE", "Repeticao do teclado nao repete acao discreta")
        press(glfw.KEY_P)
        check(app.game.state == "PLAY", "Callback P retoma")
        with patch.object(glfw, "swap_interval", wraps=glfw.swap_interval) as interval:
            press(glfw.KEY_V)
            press(glfw.KEY_V)
            check([c.args[0] for c in interval.call_args_list] == [0, 1], "V alterna glfw.swap_interval entre 0 e 1")
        for key in (glfw.KEY_W, glfw.KEY_UP, glfw.KEY_A, glfw.KEY_LEFT, glfw.KEY_S, glfw.KEY_DOWN, glfw.KEY_D, glfw.KEY_RIGHT):
            with patch.object(glfw, "get_key", side_effect=lambda w, k: glfw.PRESS if k == key else glfw.RELEASE):
                check(app.held_direction() != (0, 0), f"Movimento continuo consulta glfw.get_key: tecla {key}")
        app.game.state, app.game.xp = "LEVEL", 0
        press(glfw.KEY_RIGHT)
        press(glfw.KEY_ENTER)
        check(app.game.state == "PLAY" and app.game.player.damage == 29, "Seta e Enter confirmam melhoria selecionada")
        app.game.state = "LEVEL"
        press(glfw.KEY_3)
        check(app.game.player.max_mana == 104, "Callback 3 escolhe mana")
        app.focus(app.window, False)
        check(app.game.state == "PAUSE", "Perder foco pausa automaticamente")
        press(glfw.KEY_ENTER)
        app.last, app.fps_since = 10.0, 19.5
        clock, px = app.game.clock, app.game.player.x
        with patch.object(glfw, "get_key", return_value=glfw.RELEASE), patch.object(glfw, "get_time", return_value=20.0):
            app.frame()
        check(app.game.clock == clock and app.last == 20, "Retomar descarta tempo pausado e ressincroniza relogio")
        with patch.object(glfw, "get_key", side_effect=lambda w, k: glfw.PRESS if k == glfw.KEY_D else glfw.RELEASE), \
             patch.object(glfw, "get_time", return_value=20.01):
            app.frame()
        check(abs(app.game.player.x - px - 2.2) < 1e-7, "Primeiro movimento apos pausa usa so os 0,01 s novos")
        title = glfw.get_window_title(app.window)
        check("FPS:" in title and "VSync" in title, "Barra de titulo exibe FPS e estado do vsync")
        app.game = scene()
        press(glfw.KEY_R)
        check(app.game.state == "PLAY" and not app.game.enemies and app.game.xp == 0 and app.game.score == 0,
              "R reinicia na mesma janela e zera o placar")
        with patch.object(glfw, "get_cursor_pos", return_value=(560, HEIGHT - 360)):
            app.mouse(app.window, glfw.MOUSE_BUTTON_LEFT, glfw.PRESS, 0)
        press(glfw.KEY_SPACE)
        check(not app.game.bullets and app.game.player.mana == 80, "Clique e Espaco nao atacam durante a partida")
        press(glfw.KEY_X)
        check(len(app.game.bullets) == 1 and app.game.player.mana == 64, "X dispara uma magia e consome mana")
        app.game.fire_timer = 0
        press(glfw.KEY_X, glfw.REPEAT)
        check(len(app.game.bullets) == 1 and app.game.player.mana == 64, "Segurar X nao dispara de novo")
        p = app.game.player
        p.facing = (1, 0)
        app.game.enemies = [enemy(p.x + 55, p.y)]
        press(glfw.KEY_Z)
        check(not app.game.enemies and app.game.slash > 0, "Z aciona swing frontal pela callback")
        app.game.swing_timer = 0
        app.game.enemies = [enemy(p.x + 55, p.y)]
        press(glfw.KEY_Z, glfw.REPEAT)
        check(app.game.enemies[0].hp == 22, "Segurar Z nao aplica outro golpe")
        fps_runs = []
        for vsync in (True, False):
            if app.vsync != vsync:
                press(glfw.KEY_V)
            app.game = trial()
            app.discard_dt = True
            app.last = app.fps_since = glfw.get_time()
            px, frames, start = app.game.player.x, 0, time.perf_counter()
            with patch.object(glfw, "get_key", side_effect=lambda w, k: glfw.PRESS if k == glfw.KEY_D else glfw.RELEASE):
                while time.perf_counter() - start < 0.65:
                    app.frame()
                    frames += 1
            distance, duration = app.game.player.x - px, app.game.clock
            check(abs(distance / duration - SPEED) < 1e-6, f"Laco real com vsync {vsync} conserva 220 unidades/s")
            fps_runs.append({"vsync": vsync, "fps_observado": frames / (time.perf_counter() - start),
                             "velocidade": distance / duration, "tempo_simulado": duration})
        metrics["vsync_laco_real_janela_oculta"] = fps_runs
        glfw.set_window_size(app.window, 900, 900)
        glfw.poll_events()
        app.game = scene()
        snapshot(app, "redimensionado")
        vx, vy, vw, vh = app.ctx.viewport
        check(abs(vw / vh - WIDTH / HEIGHT) < 0.002 and vy > 0 and vx == 0,
              "Redimensionar preserva proporcao com margens no viewport")
        check(hashes == [hashlib.sha256(b.read()).hexdigest() for b in buffers],
              "Conteudo de todos os VBOs e EBO permanece identico apos cenas, callbacks e reinicio")
        press(glfw.KEY_ESCAPE)
        check(glfw.window_should_close(app.window), "Esc encerra pela callback")
    finally:
        app.close()
    if not DETAILED.is_file():
        return
    spec = importlib.util.spec_from_file_location("jogo_comentado", DETAILED)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    detailed = module.App(visible=False)
    try:
        detailed.game = scene()
        detailed_pixels = snapshot(detailed, "comparacao_comentada").tobytes()
        metrics["comparacao_versoes"] = {"bytes_essencial": len(expected_pixels), "bytes_comentada": len(detailed_pixels),
                                         "sha256_essencial": hashlib.sha256(expected_pixels).hexdigest(),
                                         "sha256_comentada": hashlib.sha256(detailed_pixels).hexdigest()}
        difference = np.abs(np.frombuffer(detailed_pixels, dtype=np.uint8).astype(int) -
                            np.frombuffer(expected_pixels, dtype=np.uint8).astype(int))
        metrics["comparacao_versoes"].update({"diferenca_maxima_canal": int(difference.max()),
                                            "canais_diferentes": int(np.count_nonzero(difference))})
        check(difference.max() <= 1,
              "Versao comentada compila shaders proprios e corresponde visualmente com tolerancia de 1/255")
    finally:
        detailed.close()


def playthroughs():
    runs = []
    for seed in (123, 47):
        g = Game(seed=seed)
        g.reset()
        bosses = {}
        steps = 0
        while g.clock < 125 and g.state != "DEAD" and steps < 20000:
            if g.state == "LEVEL":
                g.choose(0 if g.player.hp < g.player.max_hp * 0.65 else (2 if g.level % 4 == 0 else 1))
            else:
                angle = g.clock * 0.42
                tx, ty = 560 + 290 * cos(angle), 350 + 190 * sin(angle)
                direction = tx - g.player.x, ty - g.player.y
                target = min(g.enemies, key=lambda e: hypot(e.x - g.player.x, e.y - g.player.y), default=None)
                attack = target is not None and g.swing_timer <= 0 and hypot(target.x - g.player.x, target.y - g.player.y) < 76
                if attack:
                    direction = target.x - g.player.x, target.y - g.player.y
                g.shoot()
                g.update(1 / 120, direction)
                if attack:
                    g.swing()
                for e in g.enemies:
                    if e.boss:
                        bosses[id(e)] = e
            steps += 1
        check(g.level > 1, f"Partida simulada {seed}: combate, coleta e melhorias sem alterar atributos")
        check(all(e.hp > 0 for e in g.enemies) and g.player.mana >= 0 and g.player.hp >= 0,
              f"Partida simulada {seed}: entidades e barras mantem invariantes")
        runs.append({"seed": seed, "tempo": g.clock, "estado": g.state,
                     "nivel": g.level, "vida": g.player.hp, "chefes_vistos": len(bosses),
                     "chefes_derrotados": sum(e.hp <= 0 for e in bosses.values())})
    metrics["partidas_simuladas_sem_alterar_atributos"] = runs


if __name__ == "__main__":
    rules()
    code_audit()
    graphics()
    playthroughs()
    result = {"aprovado": True, "quantidade": len(checks), "verificacoes": checks, "metricas": metrics}
    (OUT / "resultado.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"aprovado": True, "quantidade": len(checks), "metricas": metrics}, ensure_ascii=False, indent=2))
