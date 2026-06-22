# Pac-Man CLI Arcade+
"""
Arcade-ish Pac-Man in the terminal using only Python's standard library.

Run:
    python3 pacman_game.py

Controls:
    Arrow keys or WASD to move
    P to pause
    Q to quit
"""

import curses
import json
import random
import time
from dataclasses import dataclass
from datetime import datetime

WALL = "#"
PELLET = "·"
POWER = "○"
FRUIT = "◆"

RAW_MAP = [
    "#####################",
    "#○······#········○#",
    "#·###·###·###·###·#·#",
    "#···················#",
    "###·#·#####·#####·###",
    "#···#·····#·····#···#",
    "#·#####·#·#·#·#####·#",
    " ·······#···#······· ",  # wraparound tunnel row
    "#·#####·#####·#####·#",
    "#···#···········#···#",
    "###·#·#####·#####·###",
    "#···················#",
    "#·###·###·###·###·#·#",
    "#○······#········○#",
    "#####################",
]

HEIGHT = 15
WIDTH = 21
TICK_SECONDS = 0.10
SCORES_FILE = ".pacman_scores.json"

GAME_MAP = [row if len(row) == WIDTH else row[:-1] + (PELLET * (WIDTH - len(row))) + row[-1] for row in RAW_MAP]

DIRS = {
    curses.KEY_UP: (-1, 0), curses.KEY_DOWN: (1, 0), curses.KEY_LEFT: (0, -1), curses.KEY_RIGHT: (0, 1),
    ord("w"): (-1, 0), ord("W"): (-1, 0), ord("s"): (1, 0), ord("S"): (1, 0),
    ord("a"): (0, -1), ord("A"): (0, -1), ord("d"): (0, 1), ord("D"): (0, 1),
}


@dataclass
class Actor:
    row: int
    col: int
    spawn: tuple[int, int]
    direction: tuple[int, int] = (0, 0)
    symbol: str = "?"
    personality: str = "chaser"

    @property
    def pos(self):
        return (self.row, self.col)

    def move_to(self, pos):
        self.row, self.col = pos

    def reset(self):
        self.row, self.col = self.spawn
        self.direction = (0, 0)


class Game:
    def __init__(self):
        self.level = 1
        self.score = 0
        self.scores = self.load_scores()
        self.high_score = self.scores[0]["score"] if self.scores else 0
        self.lives = 3
        self.message = "Ready! Ghosts now have personalities. Use the tunnel!"
        self.next_dir = (0, 1)
        self.fruit = None
        self.fruit_timer = 0
        self.reset_level()

    @staticmethod
    def load_scores():
        try:
            with open(SCORES_FILE, "r", encoding="utf-8") as f:
                return sorted(json.load(f), key=lambda x: x["score"], reverse=True)[:5]
        except Exception:
            return []

    def save_score(self):
        self.scores.append({"score": self.score, "level": self.level, "date": datetime.now().strftime("%Y-%m-%d %H:%M")})
        self.scores = sorted(self.scores, key=lambda x: x["score"], reverse=True)[:5]
        self.high_score = self.scores[0]["score"] if self.scores else self.score
        try:
            with open(SCORES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.scores, f, indent=2)
        except Exception:
            pass

    def reset_level(self):
        self.board = [list(row) for row in GAME_MAP]
        self.pellets = set()
        self.power_pellets = set()
        for r, row in enumerate(self.board):
            for c, ch in enumerate(row):
                if ch == PELLET:
                    self.pellets.add((r, c))
                elif ch == POWER:
                    self.power_pellets.add((r, c))

        self.pacman = Actor(1, 1, (1, 1), (0, 1), "ᗧ")
        self.ghosts = [
            Actor(1, 18, (1, 18), symbol="ᗣ", personality="blinky"),  # direct chase
            Actor(13, 18, (13, 18), symbol="ᗣ", personality="pinky"),  # ambush ahead
            Actor(7, 10, (7, 10), symbol="ᗣ", personality="inky"),     # unpredictable
            Actor(13, 1, (13, 1), symbol="ᗣ", personality="clyde"),    # shy when close
        ]
        self.frightened = 0
        self.combo = 0
        self.tick = 0
        self.next_dir = (0, 1)
        self.fruit = None
        self.fruit_timer = 0

    def open_cell(self, r, c):
        if r == 7 and (c < 0 or c >= WIDTH):
            return True
        return 0 <= r < HEIGHT and 0 <= c < WIDTH and GAME_MAP[r][c] != WALL

    def wrap(self, r, c):
        if r == 7 and c < 0:
            return (7, WIDTH - 1)
        if r == 7 and c >= WIDTH:
            return (7, 0)
        return (r, c)

    def next_pos(self, pos, direction):
        r, c = pos
        dr, dc = direction
        nr, nc = self.wrap(r + dr, c + dc)
        return (nr, nc) if self.open_cell(nr, nc) else pos

    def buffer_direction(self, direction):
        self.next_dir = direction

    def move_pacman(self):
        # Input buffering: make queued turn as soon as possible.
        if self.next_pos(self.pacman.pos, self.next_dir) != self.pacman.pos:
            self.pacman.direction = self.next_dir
        self.pacman.move_to(self.next_pos(self.pacman.pos, self.pacman.direction))
        self.eat_at_pacman()

    def eat_at_pacman(self):
        p = self.pacman.pos
        if p in self.pellets:
            self.pellets.remove(p)
            self.score += 10
            self.message = "+10 crunch"
        elif p in self.power_pellets:
            self.power_pellets.remove(p)
            self.score += 50
            self.frightened = 85
            self.combo = 0
            self.message = "POWER MODE! Ghosts are edible."
        elif self.fruit == p:
            points = 300 + self.level * 100
            self.score += points
            self.fruit = None
            self.fruit_timer = 0
            self.message = f"Fruit bonus! +{points}"

    def maybe_spawn_fruit(self):
        if self.fruit:
            self.fruit_timer -= 1
            if self.fruit_timer <= 0:
                self.fruit = None
                self.message = "Fruit vanished."
            return
        eaten = 154 - len(self.pellets) - len(self.power_pellets)
        if eaten > 0 and eaten % 35 == 0 and random.random() < 0.12:
            candidates = [(7, 9), (7, 11), (3, 10), (11, 10)]
            self.fruit = random.choice([p for p in candidates if self.open_cell(*p)])
            self.fruit_timer = 90
            self.message = "Bonus fruit appeared!"

    def ghost_move_interval(self):
        return max(1, 3 - self.level // 2)

    def target_for(self, ghost):
        pr, pc = self.pacman.pos
        dr, dc = self.pacman.direction
        dist = abs(ghost.row - pr) + abs(ghost.col - pc)

        if ghost.personality == "blinky":
            return self.pacman.pos
        if ghost.personality == "pinky":
            return (max(0, min(HEIGHT - 1, pr + 4 * dr)), max(0, min(WIDTH - 1, pc + 4 * dc)))
        if ghost.personality == "inky":
            if random.random() < 0.45:
                return random.choice([(1, 1), (1, 19), (13, 1), (13, 19), self.pacman.pos])
            return (max(0, min(HEIGHT - 1, pr + 2 * dr)), max(0, min(WIDTH - 1, pc + 2 * dc)))
        if ghost.personality == "clyde":
            return (13, 1) if dist < 6 else self.pacman.pos
        return self.pacman.pos

    def move_ghosts(self):
        if self.tick % self.ghost_move_interval() != 0:
            return
        for ghost in self.ghosts:
            possible = []
            for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                pos = self.wrap(ghost.row + dr, ghost.col + dc)
                if self.open_cell(*pos):
                    possible.append(pos)
            if not possible:
                continue

            reverse = self.wrap(ghost.row - ghost.direction[0], ghost.col - ghost.direction[1])
            choices = [p for p in possible if p != reverse] or possible
            target = self.target_for(ghost)

            def dist(pos):
                return abs(pos[0] - target[0]) + abs(pos[1] - target[1])

            if self.frightened:
                target_pos = max(choices, key=dist)
            elif random.random() < min(0.68 + self.level * 0.04, 0.90):
                target_pos = min(choices, key=dist)
            else:
                target_pos = random.choice(choices)
            ghost.direction = (target_pos[0] - ghost.row, target_pos[1] - ghost.col)
            ghost.move_to(target_pos)

    def handle_collisions(self):
        for ghost in self.ghosts:
            if ghost.pos != self.pacman.pos:
                continue
            if self.frightened:
                self.combo += 1
                points = 200 * self.combo
                self.score += points
                self.message = f"Ghost eaten! +{points}"
                ghost.reset()
            else:
                self.lives -= 1
                self.message = "Ouch! Ghost collision."
                self.pacman.reset()
                for g in self.ghosts:
                    g.reset()
                time.sleep(0.55)
                if self.lives <= 0:
                    self.save_score()
                    return False
        return True

    def update(self):
        self.tick += 1
        self.maybe_spawn_fruit()
        self.move_pacman()
        if not self.handle_collisions():
            return "gameover"
        self.move_ghosts()
        if not self.handle_collisions():
            return "gameover"
        if self.frightened:
            self.frightened -= 1
        if not self.pellets and not self.power_pellets:
            self.level += 1
            bonus = 500 * self.level
            self.score += bonus
            self.message = f"Level clear! Bonus +{bonus}. Level {self.level}."
            self.reset_level()
            time.sleep(0.8)
        return "running"


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for idx, color in enumerate([curses.COLOR_BLUE, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_GREEN, curses.COLOR_MAGENTA], 1):
        curses.init_pair(idx, color, -1)


def draw(stdscr, game):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    needed_h, needed_w = HEIGHT + 10, WIDTH * 2 + 24
    if h < needed_h or w < needed_w:
        stdscr.addstr(0, 0, f"Terminal too small. Need at least {needed_w}x{needed_h}.")
        stdscr.refresh()
        return

    stdscr.addstr(0, 0, " PAC-MAN CLI ARCADE+ ", curses.color_pair(2) | curses.A_BOLD)
    hud = f" Score {game.score:05d}   High {game.high_score:05d}   Lives {'♥' * game.lives}   Level {game.level}   Power {game.frightened // 10} "
    stdscr.addstr(1, 0, hud, curses.color_pair(6) | curses.A_BOLD)
    stdscr.addstr(2, 0, game.message[:max(1, w - 1)], curses.A_DIM)

    ghost_positions = {g.pos: g for g in game.ghosts}
    for r in range(HEIGHT):
        y = r + 4
        for c in range(WIDTH):
            pos = (r, c)
            text, attr = "  ", 0
            if pos == game.pacman.pos:
                text, attr = "ᗧ ", curses.color_pair(2) | curses.A_BOLD
            elif pos in ghost_positions:
                color = 5 if game.frightened else 3
                text, attr = "ᗣ ", curses.color_pair(color) | curses.A_BOLD
            elif game.fruit == pos:
                text, attr = f"{FRUIT} ", curses.color_pair(7) | curses.A_BOLD
            elif pos in game.power_pellets:
                text, attr = "● ", curses.color_pair(5) | curses.A_BOLD
            elif pos in game.pellets:
                text, attr = "· ", curses.color_pair(4)
            elif GAME_MAP[r][c] == WALL:
                text, attr = "██", curses.color_pair(1) | curses.A_BOLD
            stdscr.addstr(y, c * 2, text, attr)

    x = WIDTH * 2 + 4
    stdscr.addstr(4, x, "Ghosts", curses.color_pair(3) | curses.A_BOLD)
    labels = [("Red", "Blinky", "chases you"), ("Pink", "Pinky", "ambushes ahead"), ("Cyan", "Inky", "unpredictable"), ("Orange", "Clyde", "shy up close")]
    for i, (_, name, note) in enumerate(labels):
        stdscr.addstr(6 + i, x, f"{name:<7} {note}", curses.A_DIM)

    stdscr.addstr(12, x, "Top scores", curses.color_pair(6) | curses.A_BOLD)
    for i, s in enumerate(game.scores[:5], 1):
        stdscr.addstr(13 + i, x, f"{i}. {s['score']:05d} L{s.get('level', 1)}", curses.A_DIM)

    stdscr.addstr(HEIGHT + 5, 0, "Arrows/WASD move • P pause • Q quit • tunnel wraps left/right", curses.A_DIM)
    stdscr.refresh()


def title_screen(stdscr, scores):
    stdscr.nodelay(False)
    stdscr.erase()
    art = [
        "██████╗  █████╗  ██████╗     ███╗   ███╗ █████╗ ███╗   ██╗",
        "██╔══██╗██╔══██╗██╔════╝     ████╗ ████║██╔══██╗████╗  ██║",
        "██████╔╝███████║██║          ██╔████╔██║███████║██╔██╗ ██║",
        "██╔═══╝ ██╔══██║██║          ██║╚██╔╝██║██╔══██║██║╚██╗██║",
        "██║     ██║  ██║╚██████╗     ██║ ╚═╝ ██║██║  ██║██║ ╚████║",
        "╚═╝     ╚═╝  ╚═╝ ╚═════╝     ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝",
    ]
    for i, line in enumerate(art):
        stdscr.addstr(i + 1, 0, line, curses.color_pair(2) | curses.A_BOLD)
    stdscr.addstr(9, 0, "New: ghost personalities, wrap tunnel, fruit bonuses, input buffering, top 5 scoreboard.", curses.color_pair(6))
    if scores:
        stdscr.addstr(11, 0, "Top Scores", curses.color_pair(7) | curses.A_BOLD)
        for i, s in enumerate(scores[:5], 1):
            stdscr.addstr(11 + i, 0, f"{i}. {s['score']:05d}  Level {s.get('level', 1)}  {s.get('date', '')}")
    stdscr.addstr(18, 0, "Press any key to start.", curses.color_pair(6) | curses.A_BOLD)
    stdscr.refresh()
    stdscr.getch()
    stdscr.nodelay(True)


def pause(stdscr):
    stdscr.nodelay(False)
    stdscr.addstr(23, 0, "PAUSED — press any key to resume", curses.color_pair(7) | curses.A_BOLD)
    stdscr.refresh()
    stdscr.getch()
    stdscr.nodelay(True)


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.nodelay(True)
    init_colors()
    title_screen(stdscr, Game.load_scores())

    game = Game()
    last = 0
    while True:
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            game.save_score()
            break
        if key in (ord("p"), ord("P")):
            pause(stdscr)
        if key in DIRS:
            game.buffer_direction(DIRS[key])

        now = time.time()
        if now - last >= TICK_SECONDS:
            status = game.update()
            last = now
            draw(stdscr, game)
            if status == "gameover":
                stdscr.nodelay(False)
                stdscr.addstr(HEIGHT + 6, 0, "GAME OVER — press any key", curses.color_pair(3) | curses.A_BOLD)
                stdscr.refresh()
                stdscr.getch()
                break
        time.sleep(0.01)


if __name__ == "__main__":
    curses.wrapper(main)
