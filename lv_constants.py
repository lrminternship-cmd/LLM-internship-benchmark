"""
lv_constants.py -- shared constants for the NP-Hard Pac-Man project.

Imported by the visual game (level1.py), the headless API runner (api_runner.py)
and the game logic (lv_logic.py). Centralising every magic number here means a
value only has to be changed in one place.
"""

import os

# Path to the pixel font used by the visual game.
# If the file is missing, level1.py falls back to a system font.
FONT_PATH = os.path.join(os.path.dirname(__file__), "PressStart2P-Regular.ttf")

# Pixels between the window edge and the first cell of the grid.
# Larger = more room for the column/row labels and the border.
PADDING   = 65


# --- Colour palette (RGB tuples) ---------------------------------------------
# Based on Paul Tol's Muted colour-blind-safe palette:
#   navy(46,37,133)  green(51,117,56)  teal(93,168,153)  light-blue(148,203,236)
#   sand(220,205,125)  rose(194,106,119)  purple(159,74,150)  dark-purple(126,41,84)

C_BG           = ( 10,   8,  25)  # window background (deep navy)
C_GRID         = ( 38,  32,  90)  # cell-border colour in the grid
C_CELL         = ( 18,  16,  45)  # cell fill
C_LABEL        = (148, 203, 236)  # column/row labels -- Tol light-blue
C_PAC          = (255, 220,   0)  # Pac-Man (yellow, iconic)
C_PAC_POWERED  = (255, 140,   0)  # Pac-Man while powered up (orange)
C_EYE          = (255, 255, 255)  # eye white
C_EYE_PUP     = (  0,   0,   0)  # pupil
C_FOOD         = (220, 205, 125)  # food pellet -- Tol sand
C_FOOD_IN      = (240, 230, 170)  # food pellet inner ring
C_BANANA       = (220, 205, 125)  # banana (goal) -- Tol sand
C_BANANA_D     = (130, 115,  45)  # banana dark outline
C_WALL_LINE    = (194, 106, 119)  # permanent wall -- Tol rose
C_GHOST        = (148, 203, 236)  # patrol ghost -- Tol light-blue
C_GHOST_SCARED = ( 46,  37, 133)  # scared ghost -- Tol navy
C_GHOST_EYE    = (  0,  50, 160)  # pupil of a normal ghost
C_GHOST_EYE_SC = (220, 205, 125)  # pupil of a scared ghost -- Tol sand
C_AMBUSH_GHOST     = (126,  41,  84)  # ambush ghost -- Tol dark-purple (clearly visible)
C_AMBUSH_GHOST_EYE = (220, 205, 125)  # eye of the ambush ghost -- Tol sand
C_GATE_OPEN    = ( 51, 117,  56)  # open gate -- Tol green
C_GATE_SHUT    = (126,  41,  84)  # closed gate -- Tol dark-purple
C_GATE_FRAME   = (220, 205, 125)  # gate frame -- Tol sand
C_TP_A         = ( 46,  37, 133)  # teleporter endpoint A -- Tol navy
C_TP_B         = (148, 203, 236)  # teleporter endpoint B -- Tol light-blue
C_TP_SHARED_A  = ( 51, 117,  56)  # shared teleporter A -- Tol green (visually distinct from TP_A/B)
C_TP_SHARED_B  = (220, 205, 125)  # shared teleporter B -- Tol sand (warm, distinct from TP_SHARED_A)
C_LIGHTNING    = (220, 205, 125)  # power-up lightning -- Tol sand
C_LIGHTNING_D  = (130, 115,  45)  # power-up lightning outline
C_DELAY_PU     = ( 46,  37, 133)  # delayed power-up -- Tol navy
C_DELAY_PU_D   = ( 93, 168, 153)  # delayed power-up outline -- Tol teal
C_BOX          = (160, 100,  40)  # pushable box (brown)
C_BOX_EDGE     = (100,  60,  20)  # box edge
C_BOX_CROSS    = (120,  75,  30)  # cross on the box
C_META_BOX     = ( 93, 168, 153)  # meta-box -- Tol teal
C_META_BOX_EDG = (148, 203, 236)  # meta-box edge -- Tol light-blue
C_META_BOX_CRS = (120, 185, 170)  # meta-box cross
C_MOVE_OK      = ( 51, 117,  56)  # remaining moves -- plenty -- Tol green
C_MOVE_WARN    = (220, 205, 125)  # remaining moves -- nearly out -- Tol sand
C_MOVE_NO      = ( 38,  32,  80)  # spent moves in the bar
C_MOVE_BAR     = ( 18,  16,  45)  # background of the moves bar
C_POWER_BAR    = (220, 205, 125)  # power-up duration indicator -- Tol sand
C_WIN          = ( 51, 117,  56)  # green text on a win -- Tol green
C_LOSE         = (194, 106, 119)  # red text on a loss -- Tol rose
C_WHITE        = (255, 255, 255)
C_BORDER       = ( 46,  37, 133)  # grid border -- Tol navy
C_NEXT         = (148, 203, 236)  # "next level" colour -- Tol light-blue
C_GREEN_WALL      = ( 93, 168, 153)  # one-shot wall -- visually TEAL (Tol teal); the name "GREEN" is historical
C_GREEN_WALL_USED = ( 28,  60,  55)  # one-shot wall after use -- dark teal, blocked
C_PURPLE_WALL  = (159,  74, 150)  # permanent wall (visually: PURPLE) -- Tol purple
C_ORANGE_WALL  = (220, 205, 125)  # one-shot gate open (visually: SAND) -- Tol sand
C_ORANGE_USED  = ( 75,  65,  30)  # one-shot gate after use (dark sand, closed)
C_FRIEND_GHOST     = ( 51, 117,  56)  # friendly ghost -- Tol green
C_FRIEND_GHOST_EYE = ( 15,  55,  20)  # friendly ghost eye


# --- Game constants ----------------------------------------------------------

# Number of moves the player can eat ghosts after picking up a power-up.
# After POWER_TURNS moves the ghosts become dangerous again.
POWER_TURNS       = 6

# Number of moves the delayed power-up waits AFTER the player leaves the zone
# before it activates. Lower = less challenging.
DELAY_PU_MOVES    = 3

# Chebyshev distance at which a sleeping ambush ghost wakes up.
# Chebyshev = max(|d_col|, |d_row|) -- makes a diagonal approach equally dangerous.
AMBUSH_RADIUS     = 2

# The ambush ghost pauses every AMBUSH_PAUSE_FREQ moves during the chase.
# This gives the player a brief breather and makes the timing predictable.
AMBUSH_PAUSE_FREQ = 5
