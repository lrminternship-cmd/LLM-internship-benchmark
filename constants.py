"""
constants.py -- shared constants for the Pac-Man engine.

ORIGIN: part of the Pac-Man game engine adapted from https://pacmancode.com
(author: Jonathan Richards). Comments added for this thesis.

Grid and screen geometry, the colour palette, and the integer enums used as
keys throughout the engine (directions, entity names, ghost modes, text ids).
Directions are chosen so that an opposite direction is just the negation:
UP/DOWN = 1/-1 and LEFT/RIGHT = 2/-2, which lets code flip a heading with `* -1`.
"""

# --- Grid and screen geometry (a tile is 16x16 px; the maze is 28x36 tiles) ---
TILEWIDTH = 16
TILEHEIGHT = 16
NROWS = 36
NCOLS = 28
SCREENWIDTH = NCOLS*TILEWIDTH
SCREENHEIGHT = NROWS*TILEHEIGHT
SCREENSIZE = (SCREENWIDTH, SCREENHEIGHT)

# --- RGB colour palette ---
BLACK = (0, 0, 0)
YELLOW = (255, 255, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
PINK = (255,100,150)
TEAL = (100,255,255)
ORANGE = (230,190,40)
GREEN = (0, 255, 0)

# --- Direction keys. Opposite = negation (handy for reversing a heading). ---
STOP = 0
UP = 1
DOWN = -1
LEFT = 2
RIGHT = -2
PORTAL = 3   # not a movement; marks a wrap-around tunnel link between nodes

# --- Entity-name keys (used for sprites and per-node access permissions) ---
PACMAN = 0
PELLET = 1
POWERPELLET = 2
GHOST = 3
BLINKY = 4
PINKY = 5
INKY = 6
CLYDE = 7
FRUIT = 8

# --- Ghost mode keys ---
SCATTER = 0   # flee to a fixed home corner
CHASE = 1     # pursue Pac-Man (per-ghost targeting logic)
FREIGHT = 2   # "frightened": edible, after a power pellet
SPAWN = 3     # returning to the ghost house after being eaten

# --- Text element ids (see text.py / TextGroup) ---
SCORETXT = 0
LEVELTXT = 1
READYTXT = 2
PAUSETXT = 3
GAMEOVERTXT = 4
