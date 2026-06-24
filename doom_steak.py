# Steak Doom: Wolfensteak 3D
"""
A tiny DOOM/Wolfenstein-style first-person maze game in the terminal.
Pure Python standard library, using curses.

Run:
    python3 doom_steak.py

Controls:
    ↑/↓ or W/S    move forward/back
    ←/→ or Q/E    turn left/right
    A/D           strafe left/right
    Space         throw steak sauce
    M             toggle full/fog minimap
    P             pause
    X             quit
"""

import curses
import locale
import math
import random
import time

locale.setlocale(locale.LC_ALL, "")

MAP = [
    "################",
    "#......#.......#",
    "#.####.#.#####.#",
    "#.#....#.....#.#",
    "#.#.######.#.#.#",
    "#.#........#...#",
    "#.#.####.#####.#",
    "#...#..#.....#.#",
    "###.#..#####.#.#",
    "#...#........#.#",
    "#.##########.#.#",
    "#............#.#",
    "#.############.#",
    "#..............#",
    "################",
]

H = len(MAP)
W = len(MAP[0])
FOV = math.pi / 3
MAX_DEPTH = 16
TICK = 0.035
PLAYER = "🥩"
WOLF = "🐺"
SAUCE = "🔥"
EXIT = "🚪"
MEDKIT = "💚"
AMMO = "🧴"
HOTSAUCE = "🌶️"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Game:
    def __init__(self):
        self.x = 1.5
        self.y = 1.5
        self.a = 0.0
        self.hp = 100
        self.score = 0
        self.ammo = 12
        self.msg = "Find the exit. Arrow keys work. WASD works. Wolves hate steak sauce."
        self.exit = (14, 13)
        self.wolves = [
            {"x": 6.5, "y": 3.5, "hp": 2, "max_hp": 2},
            {"x": 12.5, "y": 5.5, "hp": 2, "max_hp": 2},
            {"x": 4.5, "y": 9.5, "hp": 2, "max_hp": 2},
            {"x": 11.5, "y": 11.5, "hp": 3, "max_hp": 3},
        ]
        self.pickups = [
            {"x": 5.5, "y": 1.5, "kind": "ammo"},
            {"x": 13.5, "y": 3.5, "kind": "med"},
            {"x": 6.5, "y": 9.5, "kind": "ammo"},
            {"x": 8.5, "y": 11.5, "kind": "hot"},
            {"x": 12.5, "y": 13.5, "kind": "med"},
        ]
        self.frame = 0
        self.muzzle_flash = 0
        self.damage_flash = 0
        self.power_timer = 0
        self.shot_cooldown = 0
        self.show_full_map = False
        self.visited = {(int(self.x), int(self.y))}
        self.won = False
        self.dead = False

    def wall(self, x, y):
        ix, iy = int(x), int(y)
        if ix < 0 or iy < 0 or iy >= H or ix >= W:
            return True
        return MAP[iy][ix] == "#"

    def move(self, dx, dy):
        nx, ny = self.x + dx, self.y + dy
        if not self.wall(nx, self.y):
            self.x = nx
        if not self.wall(self.x, ny):
            self.y = ny
        self.visited.add((int(self.x), int(self.y)))

    def cast(self, angle):
        step = 0.035
        depth = step
        while depth < MAX_DEPTH:
            tx = self.x + math.cos(angle) * depth
            ty = self.y + math.sin(angle) * depth
            if self.wall(tx, ty):
                return depth
            depth += step
        return MAX_DEPTH

    def has_line_of_sight(self, x, y, tolerance=0.75):
        dx, dy = x - self.x, y - self.y
        dist = math.hypot(dx, dy)
        if dist < 0.01:
            return True
        angle = math.atan2(dy, dx)
        return self.cast(angle) + tolerance >= dist

    def visible_point(self, x, y, tolerance=0.65):
        dx, dy = x - self.x, y - self.y
        dist = math.hypot(dx, dy)
        ang = math.atan2(dy, dx) - self.a
        while ang < -math.pi:
            ang += math.tau
        while ang > math.pi:
            ang -= math.tau
        if abs(ang) >= FOV / 2 or dist <= 0.25:
            return None
        if self.cast(self.a + ang) + tolerance >= dist:
            return dist, ang
        return None

    def visible_wolves(self):
        visible = []
        for wolf in self.wolves:
            seen = self.visible_point(wolf["x"], wolf["y"], tolerance=0.85)
            if seen:
                dist, ang = seen
                visible.append((dist, ang, wolf))
        return sorted(visible, reverse=True)

    def visible_pickups(self):
        visible = []
        for pickup in self.pickups:
            seen = self.visible_point(pickup["x"], pickup["y"], tolerance=0.35)
            if seen:
                dist, ang = seen
                visible.append((dist, ang, pickup))
        return sorted(visible, reverse=True)

    def shoot(self):
        if self.shot_cooldown:
            return
        if self.ammo <= 0:
            self.msg = "Out of steak sauce!"
            return
        self.ammo -= 1
        self.muzzle_flash = 5
        self.shot_cooldown = 8
        best = None
        for dist, ang, wolf in self.visible_wolves():
            # A slightly wider hit cone makes the terminal shooter feel fair,
            # especially with emoji wolves that are wider than one character.
            if abs(ang) < 0.20:
                if best is None or dist < best[0]:
                    best = (dist, wolf)
        if best:
            _, wolf = best
            damage = 2 if self.power_timer else 1
            wolf["hp"] -= damage
            self.msg = "Inferno sauce hit!" if self.power_timer else "Sauce hit!"
            if wolf["hp"] <= 0:
                self.wolves.remove(wolf)
                self.score += 250
                self.msg = "Wolf defeated! +250"
        else:
            self.msg = "Sauce splattered the wall."

    def update_wolves(self):
        if self.frame % 8:
            return
        for wolf in list(self.wolves):
            dx, dy = self.x - wolf["x"], self.y - wolf["y"]
            dist = math.hypot(dx, dy)
            if dist < 0.65:
                if self.has_line_of_sight(wolf["x"], wolf["y"], tolerance=0.95):
                    bite = 4 if self.power_timer else 7
                    self.hp -= bite
                    self.damage_flash = 5
                    self.msg = "A singed wolf nips you!" if self.power_timer else "A wolf bites the steak!"
                    if self.hp <= 0:
                        self.dead = True
                continue
            if dist < 7 and self.has_line_of_sight(wolf["x"], wolf["y"], tolerance=1.25):
                speed = 0.035 if self.power_timer else 0.055
                # Hot sauce power makes wolves back away instead of charging.
                direction = -1 if self.power_timer and dist < 4.5 else 1
                nx = wolf["x"] + direction * dx / dist * speed
                ny = wolf["y"] + direction * dy / dist * speed
                if not self.wall(nx, wolf["y"]):
                    wolf["x"] = nx
                if not self.wall(wolf["x"], ny):
                    wolf["y"] = ny
            elif random.random() < 0.25:
                ang = random.random() * math.tau
                nx = wolf["x"] + math.cos(ang) * 0.06
                ny = wolf["y"] + math.sin(ang) * 0.06
                if not self.wall(nx, ny):
                    wolf["x"], wolf["y"] = nx, ny

    def collect_pickups(self):
        for pickup in list(self.pickups):
            if math.hypot(pickup["x"] - self.x, pickup["y"] - self.y) < 0.65:
                self.pickups.remove(pickup)
                if pickup["kind"] == "ammo":
                    self.ammo += 6
                    self.score += 50
                    self.msg = "Picked up steak sauce! +6 ammo"
                elif pickup["kind"] == "hot":
                    self.power_timer = 360
                    self.score += 100
                    self.msg = "HOT SAUCE RAGE! Shots hit harder and wolves retreat."
                else:
                    self.hp = min(100, self.hp + 30)
                    self.score += 50
                    self.msg = "Ate garnish. +30 HP"

    def update(self):
        self.frame += 1
        self.collect_pickups()
        self.update_wolves()
        if self.muzzle_flash:
            self.muzzle_flash -= 1
        if self.damage_flash:
            self.damage_flash -= 1
        if self.power_timer:
            self.power_timer -= 1
        if self.shot_cooldown:
            self.shot_cooldown -= 1
        if int(self.x) == self.exit[0] and int(self.y) == self.exit[1]:
            self.won = True
            self.score += self.hp * 10 + self.ammo * 25


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    pairs = [
        curses.COLOR_BLUE,
        curses.COLOR_CYAN,
        curses.COLOR_WHITE,
        curses.COLOR_YELLOW,
        curses.COLOR_RED,
        curses.COLOR_GREEN,
        curses.COLOR_MAGENTA,
    ]
    for i, c in enumerate(pairs, 1):
        curses.init_pair(i, c, -1)


def wall_glyph(dist, row_ratio=0.5):
    # Distance + vertical shading gives walls more depth than a flat block column.
    if row_ratio < 0.12 or row_ratio > 0.88:
        edge = curses.A_BOLD
    else:
        edge = 0
    if dist < 1.5:
        return "█", curses.color_pair(1) | curses.A_BOLD
    if dist < 3:
        return "▓", curses.color_pair(1) | edge
    if dist < 6:
        return "▒", curses.color_pair(2) | edge
    return "░", curses.color_pair(2) | curses.A_DIM


def draw_3d(stdscr, game, top, left, width, height):
    zbuf = []
    horizon = top + height // 2
    for col in range(width):
        ray_a = game.a - FOV / 2 + (col / max(1, width - 1)) * FOV
        dist = game.cast(ray_a)
        # Fish-eye correction.
        dist *= math.cos(ray_a - game.a)
        zbuf.append(dist)
        wall_h = int(height / max(0.1, dist) * 1.25)
        ceiling = horizon - wall_h // 2
        floor = horizon + wall_h // 2
        for row in range(height):
            y = top + row
            if row < ceiling - top:
                # Ceiling gradient.
                if row < height * 0.20:
                    ch, at = "'", curses.color_pair(2) | curses.A_DIM
                elif row < height * 0.38:
                    ch, at = ".", curses.color_pair(2) | curses.A_DIM
                else:
                    ch, at = " ", 0
            elif row <= floor - top:
                ratio = (row - (ceiling - top)) / max(1, wall_h)
                ch, at = wall_glyph(dist, ratio)
                # Draw vertical seams every few projected wall columns for a brick/corridor feel.
                if col % 7 == 0 and dist < 5:
                    ch, at = "▌", curses.color_pair(1) | curses.A_BOLD
            else:
                # Floor gradient.
                depth = row / max(1, height)
                if depth > 0.88:
                    ch, at = "=", curses.color_pair(3) | curses.A_DIM
                elif depth > 0.75:
                    ch, at = "-", curses.color_pair(3) | curses.A_DIM
                else:
                    ch, at = ".", curses.color_pair(3) | curses.A_DIM
            stdscr.addstr(y, left + col, ch, at)

    def billboard(dist, ang, sprite, attr, y_bias=0, occlusion=0.75):
        screen_x = int(left + (ang + FOV / 2) / FOV * width)
        if left <= screen_x < left + width and dist < zbuf[clamp(screen_x - left, 0, width - 1)] + occlusion:
            size = clamp(int(height / max(0.35, dist) * 0.65), 1, 6)
            for i, line in enumerate(sprite):
                y = horizon - size // 2 + i + y_bias
                x = screen_x - len(line) // 2
                if top <= y < top + height and left <= x < left + width:
                    stdscr.addstr(y, x, line, attr)

    # Draw exit beacon, pickups, then wolves as billboards, farthest first.
    exit_seen = game.visible_point(game.exit[0] + 0.5, game.exit[1] + 0.5, tolerance=0.5)
    if exit_seen:
        billboard(exit_seen[0], exit_seen[1], ["🚪", "EXIT"], curses.color_pair(6) | curses.A_BOLD, occlusion=0.5)

    for dist, ang, pickup in game.visible_pickups():
        icon = AMMO if pickup["kind"] == "ammo" else HOTSAUCE if pickup["kind"] == "hot" else MEDKIT
        color = 5 if pickup["kind"] == "hot" else 6 if pickup["kind"] == "med" else 7
        billboard(dist, ang, [icon], curses.color_pair(color) | curses.A_BOLD, y_bias=2, occlusion=0.45)

    for dist, ang, wolf in game.visible_wolves():
        hp_bar = "▰" * wolf["hp"] + "▱" * (wolf["max_hp"] - wolf["hp"])
        if dist < 2.2:
            sprite = [hp_bar, "🐺🐺", " ╱╲ "]
        elif dist < 4.5:
            sprite = [hp_bar, "🐺", "ʬʬ"]
        else:
            sprite = ["🐺"]
        billboard(dist, ang, sprite, curses.color_pair(5) | curses.A_BOLD, occlusion=0.95)

    # Crosshair + simple weapon overlay.
    stdscr.addstr(horizon, left + width // 2, "⊕", curses.color_pair(4) | curses.A_BOLD)
    weapon_y = top + height - 4
    weapon_x = left + width // 2 - 8
    weapon = [
        "      🥩      ",
        "    ╭────╮    ",
        "════╡SAUCE╞════",
        "    ╰────╯    ",
    ]
    if game.muzzle_flash:
        stdscr.addstr(horizon - 1, left + width // 2 - 1, SAUCE, curses.color_pair(7) | curses.A_BOLD)
    for i, line in enumerate(weapon):
        stdscr.addstr(weapon_y + i, weapon_x, line, curses.color_pair(4 if i == 0 else 7) | curses.A_BOLD)
    if game.damage_flash:
        stdscr.addstr(top, left, "!" * width, curses.color_pair(5) | curses.A_BOLD)
        stdscr.addstr(top + height - 1, left, "!" * width, curses.color_pair(5) | curses.A_BOLD)


def draw_minimap(stdscr, game, y0, x0):
    for y, row in enumerate(MAP):
        for x, ch in enumerate(row):
            pos = (x, y)
            known = game.show_full_map or pos in game.visited or math.hypot(game.x - x, game.y - y) < 2.2
            if not known:
                out, attr = " ", 0
            elif int(game.x) == x and int(game.y) == y:
                out, attr = PLAYER, curses.color_pair(4) | curses.A_BOLD
            elif pos == game.exit:
                out, attr = EXIT, curses.color_pair(6) | curses.A_BOLD
            elif any(int(w["x"]) == x and int(w["y"]) == y for w in game.wolves):
                out, attr = WOLF, curses.color_pair(5) | curses.A_BOLD
            elif any(int(p["x"]) == x and int(p["y"]) == y for p in game.pickups):
                pickup = next(p for p in game.pickups if int(p["x"]) == x and int(p["y"]) == y)
                icon = AMMO if pickup["kind"] == "ammo" else HOTSAUCE if pickup["kind"] == "hot" else MEDKIT
                color = 7 if pickup["kind"] == "ammo" else 5 if pickup["kind"] == "hot" else 6
                out, attr = icon, curses.color_pair(color) | curses.A_BOLD
            elif ch == "#":
                out, attr = "█", curses.color_pair(1)
            else:
                out, attr = "·", curses.A_DIM
            stdscr.addstr(y0 + y, x0 + x * 2, out, attr)


def draw(stdscr, game):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    if h < 30 or w < 100:
        stdscr.addstr(0, 0, "Make the terminal at least 100x30 for Steak Doom.")
        stdscr.refresh()
        return

    stdscr.addstr(0, 0, "🥩 STEAK DOOM: WOLFENSTEAK 3D 🐺", curses.color_pair(4) | curses.A_BOLD)
    dirs = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]
    facing = dirs[int(((game.a % math.tau) / math.tau) * 8 + 0.5) % 8]
    exit_dx, exit_dy = game.exit[0] + 0.5 - game.x, game.exit[1] + 0.5 - game.y
    exit_dist = math.hypot(exit_dx, exit_dy)
    nearest_wolf = min((math.hypot(wolf["x"] - game.x, wolf["y"] - game.y) for wolf in game.wolves), default=99)
    danger = "  ⚠️ WOLF CLOSE" if nearest_wolf < 2.5 else ""
    power = f"  HOT {game.power_timer // 10:02d}" if game.power_timer else ""
    hud = f"HP {game.hp:03d}  Sauce {game.ammo:02d}  Wolves {len(game.wolves)}  Pickups {len(game.pickups)}  Facing {facing}  Exit {exit_dist:04.1f}  Score {game.score:05d}{power}{danger}"
    stdscr.addstr(1, 0, hud[:w - 1], curses.color_pair(5 if danger else 6) | curses.A_BOLD)
    stdscr.addstr(2, 0, game.msg[:w - 1], curses.A_DIM)
    draw_3d(stdscr, game, 4, 0, 70, 22)
    draw_minimap(stdscr, game, 4, 73)
    stdscr.addstr(21, 73, "↑/↓ or W/S move", curses.A_DIM)
    stdscr.addstr(22, 73, "←/→ or Q/E turn", curses.A_DIM)
    stdscr.addstr(23, 73, "A/D strafe", curses.A_DIM)
    stdscr.addstr(24, 73, "Space sauce", curses.A_DIM)
    stdscr.addstr(25, 73, "M map • X quit", curses.A_DIM)
    stdscr.addstr(27, 73, f"{AMMO} sauce refill", curses.color_pair(7) | curses.A_BOLD)
    stdscr.addstr(28, 73, f"{MEDKIT} garnish heals", curses.color_pair(6) | curses.A_BOLD)
    stdscr.addstr(29, 73, f"{HOTSAUCE} rage mode", curses.color_pair(5) | curses.A_BOLD)
    stdscr.refresh()


def title(stdscr):
    stdscr.nodelay(False)
    stdscr.erase()
    art = [
        "███████╗████████╗███████╗ █████╗ ██╗  ██╗    ██████╗  ██████╗  ██████╗ ███╗   ███╗",
        "██╔════╝╚══██╔══╝██╔════╝██╔══██╗██║ ██╔╝    ██╔══██╗██╔═══██╗██╔═══██╗████╗ ████║",
        "███████╗   ██║   █████╗  ███████║█████╔╝     ██║  ██║██║   ██║██║   ██║██╔████╔██║",
        "╚════██║   ██║   ██╔══╝  ██╔══██║██╔═██╗     ██║  ██║██║   ██║██║   ██║██║╚██╔╝██║",
        "███████║   ██║   ███████╗██║  ██║██║  ██╗    ██████╔╝╚██████╔╝╚██████╔╝██║ ╚═╝ ██║",
        "╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝    ╚═════╝  ╚═════╝  ╚═════╝ ╚═╝     ╚═╝",
    ]
    for i, line in enumerate(art):
        stdscr.addstr(i + 2, 0, line, curses.color_pair(4) | curses.A_BOLD)
    stdscr.addstr(10, 0, "A first-person terminal maze shooter. You are steak. Wolves are hungry.", curses.color_pair(6))
    stdscr.addstr(12, 0, "Improved controls: arrow keys work; WASD moves/strafe; Q/E turns; M toggles the map.", curses.A_DIM)
    stdscr.addstr(13, 0, "New: fog-of-war minimap, hot sauce rage, wolf proximity warning, fire-rate cooldown.", curses.A_DIM)
    stdscr.addstr(15, 0, "Press any key to start.", curses.color_pair(4) | curses.A_BOLD)
    stdscr.refresh()
    stdscr.getch()
    stdscr.nodelay(True)


def pause(stdscr):
    stdscr.nodelay(False)
    stdscr.addstr(27, 0, "PAUSED — press any key", curses.color_pair(7) | curses.A_BOLD)
    stdscr.refresh()
    stdscr.getch()
    stdscr.nodelay(True)


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.nodelay(True)
    init_colors()
    title(stdscr)
    game = Game()
    last = 0
    while True:
        key = stdscr.getch()
        move_speed = 0.11
        turn_speed = 0.075
        if key in (ord("x"), ord("X")):
            break
        if key in (ord("p"), ord("P")):
            pause(stdscr)
        if key in (ord("m"), ord("M")):
            game.show_full_map = not game.show_full_map
            game.msg = "Full automap enabled." if game.show_full_map else "Fog-of-war minimap enabled."
        if key in (curses.KEY_LEFT, ord("q"), ord("Q")):
            game.a -= turn_speed
        if key in (curses.KEY_RIGHT, ord("e"), ord("E")):
            game.a += turn_speed
        if key in (curses.KEY_UP, ord("w"), ord("W")):
            game.move(math.cos(game.a) * move_speed, math.sin(game.a) * move_speed)
        if key in (curses.KEY_DOWN, ord("s"), ord("S")):
            game.move(-math.cos(game.a) * move_speed, -math.sin(game.a) * move_speed)
        if key in (ord("a"), ord("A")):
            game.move(math.cos(game.a - math.pi / 2) * move_speed, math.sin(game.a - math.pi / 2) * move_speed)
        if key in (ord("d"), ord("D")):
            game.move(math.cos(game.a + math.pi / 2) * move_speed, math.sin(game.a + math.pi / 2) * move_speed)
        if key == ord(" "):
            game.shoot()

        now = time.time()
        if now - last >= TICK:
            game.update()
            draw(stdscr, game)
            last = now
            if game.dead or game.won:
                stdscr.nodelay(False)
                msg = "YOU ESCAPED THE WOLF MAZE!" if game.won else "THE WOLVES ATE THE STEAK."
                stdscr.addstr(27, 0, f"{msg} Final score: {game.score}. Press any key.", curses.color_pair(5 if game.dead else 6) | curses.A_BOLD)
                stdscr.refresh()
                stdscr.getch()
                break
        time.sleep(0.005)


if __name__ == "__main__":
    curses.wrapper(main)
