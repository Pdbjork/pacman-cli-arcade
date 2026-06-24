# Steak-Man: Wolf Run

A colorful arcade-style Pac-Man variant for the terminal, written in pure Python using the standard-library `curses` module.

You are a **T-bone steak** 🥩 trying to survive a maze full of hungry **wolves** 🐺.

## Features

- Real-time keyboard movement with arrow keys or WASD
- T-bone steak player sprite 🥩
- Wolves instead of ghosts 🐺
- Butcher-power pellets that scare wolves 🐶
- Cherry-glaze bonus fruit 🍒
- Improved chunky maze graphics
- Wolf personalities: Alpha, Stalker, Trickster, and Shy Wolf
- Wraparound tunnel
- Input buffering for smoother turns
- Level progression
- Persistent top-5 scoreboard in `.pacman_scores.json`

## Run Steak-Man

```bash
python3 pacman_game.py
```

## Run Steak Doom

A first-person DOOM/Wolfenstein-style terminal maze shooter is included too, with raycast corridors, wolf health bars, visible pickups, an exit beacon, fog-of-war minimap, hot sauce rage mode, and wolf proximity warnings:

```bash
python3 doom_steak.py
```

Steak Doom controls:

- `↑/↓` or `W/S` move forward/back
- `←/→` or `Q/E` turn left/right
- `A/D` strafe left/right
- `Space` throw steak sauce
- `M` toggle full/fog minimap
- `P` pause
- `X` quit

> Works best in a real terminal window with emoji support and enough space for the game board.
