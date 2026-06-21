"""
lv_levels.py -- all level definitions for NP-Hard Pac-Man.

Each entry in LEVELS is a dict that fully describes one level. The game logic
(lv_logic.py) and the visual renderer (level1.py) read from here.

Level structure
---------------
Series 1 (1A-1F)  -- index 0-5:   Base rules: walls, ghost, teleporters, power-up
Series 2 (2A-2F)  -- index 6-11:  Meta rules: teal/purple/orange walls,
                                  ambush ghost, shared teleporters,
                                  delayed power-up, meta-boxes
Series 3 (3A-3F)  -- index 12-17: Meta-meta rules: local rule zone with
                                  perimeter patrol, one-shot teal walls,
                                  delayed-PU pause, wall-breaking meta-box
Series 4 (4A)     -- index 18:    Wager mechanic, 8x8 grid, ghost A4<->G4
Series 4 (4B)     -- index 19:    Wager mechanic, 12x12 grid, ghost G6<->L6
Series 4 (4C)     -- index 20:    Estimate mechanic, 8x8 grid
Series 4 (4D)     -- index 21:    Estimate mechanic, 12x12 grid

Wall notation
-------------
Walls are stored as a frozenset of two cell coordinates:
  frozenset([(col1, row1), (col2, row2)])
The helpers _e() and _n() make these frozensets readable in the definition:
  _e(col, row)  ->  vertical wall: left edge of cell (col, row)
  _n(col, row)  ->  horizontal wall: top edge of cell (col, row)

Colour-palette mapping (Paul Tol Muted, colour-blind-safe)
----------------------------------------------------------
  walls        -> ROSE     (194,106,119)  permanent walls
  green_walls  -> TEAL     ( 93,168,153)  one-shot walls in the zone (the code name "green" is historical)
  purple_walls -> PURPLE   (159, 74,150)  permanent extra walls
  orange_gates -> SAND     (220,205,125)  one-shot gates (open); dark sand after use

Each level dict has the following keys
--------------------------------------
  title             str      display name (e.g. "LEVEL 1A")
  cols, rows        int      grid dimensions
  cell              int      cell size in pixels (visual game only)
  start             (c, r)   player start position
  goals             list     list of {"pos": (c,r), "type": "banana"}
  max_moves         int      maximum number of moves before game_over
  walls             set      rose (permanent) walls as frozensets
  green_walls       set      teal (one-shot in zone) walls -- visually light-blue/teal
  purple_walls      set      purple (permanent) walls
  orange_gates      list     one-shot gates with direction and bidirectional flag
  shared_orange_gates list   one-shot gates that also block the ghost
  gate              dict|None  optional gate {"pos":(c,r), "open": bool}
  ghost             dict|None  patrol-ghost definition
  ambush_ghost      dict|None  ambush-ghost definition
  teleporters       list|None  [portal_A, portal_B] -- player only
  shared_teleporters list|None  idem, but ghosts may use them too
  ghost_teleporters list|None  ghosts only (the player may not use them)
  powerup           dict|None  {"pos": (c,r)} -- immediate power-up
  delayed_powerup   dict|None  {"pos": (c,r)} -- delayed power-up
  require_ghost_eaten bool    True -> all ghosts must be eaten to win
  pushable_blocks   list     start positions of pushable boxes [(c,r), ...]
  meta_blocks       list     start positions of meta-boxes (sliding)
  local_rule_zone   dict|None  zone with special rules (series 3+ only)
  wager_level       bool     True -> level has a preview + wager phase (series 4)
"""

# --- Wall helpers ------------------------------------------------------------

def _e(col, row):
    """Vertical wall on the LEFT edge of cell (col, row).

    Stores the edge between (col-1, row) and (col, row) as a frozenset.
    Usage: _e(3, 2) = wall between columns B and C on row 3 (0-indexed).
    """
    return frozenset([(col - 1, row), (col, row)])

def _n(col, row):
    """Horizontal wall on the TOP edge of cell (col, row).

    Stores the edge between (col, row-1) and (col, row) as a frozenset.
    Usage: _n(2, 4) = wall between rows 4 and 5 in column C (0-indexed).
    """
    return frozenset([(col, row - 1), (col, row)])


# --- Level definitions -------------------------------------------------------
# Index -> level:
#   0=1A  1=1B  2=1C  3=1D  4=1E  5=1F
#   6=2A  7=2B  8=2C  9=2D  10=2E  11=2F
#   12=3A  13=3B  14=3C  15=3D  16=3E  17=3F
#   18=4A
LEVELS = [
# ── LEVEL 1 series (1A-1F) ───────────────────────────────────────────────────
{
    "title":               "LEVEL 1A",
    "cols":                8, "rows": 2, "cell": 90,
    "start":               (0, 0),
    "goals":               [{"pos": (7, 1), "type": "banana"}],
    "max_moves":           24,
    "walls":               set(),
    "gate":                None,
    "ghost":               None,
    "teleporters":         None,
    "powerup":             None,
    "require_ghost_eaten": False,
    "pushable_blocks":     [],
    "green_walls":         set(),
    "purple_walls":        set(),
    "orange_gates":        [],
},
{
    "title":               "LEVEL 1B",
    "cols":                7, "rows": 7, "cell": 82,
    "start":               (0, 0),
    "goals":               [{"pos": (6, 3), "type": "banana"}],
    "max_moves":           33,
    "walls": {
        _e(3,0),
        _e(1,1), _e(5,1),
        _e(1,2), _e(3,2), _e(5,2),
        _e(1,4), _e(3,4), _e(5,4),
        _e(1,5),          _e(5,5),
        _e(3,6),
    },
    "gate":                None,
    "ghost":               {"col": 0, "row": 3, "axis": "h",
                            "min_col": 0, "max_col": 5, "dir": 1},
    "teleporters":         None,
    "powerup":             None,
    "require_ghost_eaten": False,
    "pushable_blocks":     [],
    "green_walls":         set(),
    "purple_walls":        set(),
    "orange_gates":        [],
},
{
    "title":               "LEVEL 1C",
    "cols":                7, "rows": 7, "cell": 82,
    "start":               (0, 0),
    "goals":               [
        {"pos": (0, 4), "type": "banana"},
        {"pos": (5, 6), "type": "banana"},
    ],
    "max_moves":           45,
    "walls": {
        _e(2,0), _e(3,0), _e(4,0), _e(5,0),
        _e(2,1), _e(2,2), _n(2,3), _n(2,4),
        _e(5,2), _e(6,2),
        _e(2,4), _e(3,4), _e(5,4), _e(6,4),
        _e(2,5), _e(6,5),
        _e(2,6), _e(3,6), _e(6,6),
    },
    "gate":                None,
    "ghost":               {"col": 1, "row": 1, "axis": "v",
                            "min_row": 1, "max_row": 5, "dir": 1},
    "teleporters":         None,
    "powerup":             None,
    "require_ghost_eaten": False,
    "pushable_blocks":     [],
    "green_walls":         set(),
    "purple_walls":        set(),
    "orange_gates":        [
        {"edge": frozenset([(1, 3), (2, 3)]), "pass_dir": (1, 0), "bidirectional": True},  # D3↔D4
    ],
},
{
    "title":               "LEVEL 1D",
    "cols":                7, "rows": 7, "cell": 82,
    "start":               (0, 0),
    "goals":               [
        {"pos": (3, 0), "type": "banana"},
        {"pos": (5, 6), "type": "banana"},
    ],
    "max_moves":           93,
    "walls": {
        _e(2,0), _e(4,0), _e(5,0), _e(6,0),
        _e(2,1),
        _e(2,2), _e(4,2), _e(5,2), _e(6,2),
        _n(2,2), _n(3,2), _n(4,2), _n(5,3), _n(4,4), _n(4,1),
        _n(2,5), _n(5,5), _n(3,6), _n(0,2), _n(0,4),
        _e(2,4), _e(3,4), _e(5,4), _e(6,4),
        _e(2,5),          _e(6,5),
        _e(2,6), _e(3,6), _e(6,6),_e(4,3),
    },
    "gate":                None,
    "ghost":               {"col": 1, "row": 1, "axis": "v",
                            "min_row": 1, "max_row": 5, "dir": 1},
    "teleporters":         [(1, 6), (6, 1)],
    "powerup":             None,
    "require_ghost_eaten": False,
    "pushable_blocks":     [],
    "green_walls":         set(),
    "purple_walls":        set(),
    "orange_gates":        [
        {"edge": frozenset([(3, 3), (3, 4)]), "pass_dir": (0, 1), "bidirectional": True},  # D3↔D4
    ],
},
{
    "title":               "LEVEL 1E",
    "cols":                7, "rows": 7, "cell": 82,
    "start":               (0, 0),
    "goals":               [
        {"pos": (3, 0), "type": "banana"},
        {"pos": (5, 6), "type": "banana"},
    ],
    "max_moves":           81,
    "walls": {
        _e(3,0), _e(6,0),_e(4,3),
        _e(1,1), _e(3,1),
        _e(3,2), _e(5,2),
        _e(2,4), _e(3,4), _e(5,4),
        _e(2,5),          _e(6,5),
                 _e(6,6), _e(2,6),
        _n(2,1), _n(5,1), _n(0,2), _n(4,3), _n(5,3), _n(6,3),_n(3,4),
        _n(0,4), _n(5,4), _n(6,4), _n(0,5), _n(2,5), _n(6,5), _n(6,6),
    },
    "gate":                None,
    "ghost":               {"col": 1, "row": 1, "axis": "v",
                            "min_row": 1, "max_row": 5, "dir": 1},
    "teleporters":         [(0, 2), (6, 4)],
    "powerup":             {"pos": (1, 6)},
    "require_ghost_eaten": True,
    "pushable_blocks":     [],
    "green_walls":         set(),
    "purple_walls":        set(),
    "orange_gates":        [
        {"edge": frozenset([(3, 2), (3, 3)]), "pass_dir": (0, 1), "bidirectional": True},  # D3↔D4
    ],
},
{
    "title":               "LEVEL 1F",
    "cols":                7, "rows": 7, "cell": 82,
    "start":               (1, 5),
    "goals":               [
        {"pos": (1, 0), "type": "banana"},
        {"pos": (2, 0), "type": "banana"},
    ],
    "max_moves":           93,
    "walls": {
        _e(1,3), _e(2,0), _e(2,5), _e(2,6), _e(6,5),
        _e(3,1), _e(5,2), _e(5,6), _e(6,1),
        _n(2,1), _n(3,1), _n(3,2), _n(5,2), _n(6,2),
        _n(0,4), _n(2,5), _n(4,5), _n(5,5), _n(6,5), _n(3,6), _n(5,6),
    },
    "gate":  None,
    "ghost": {
        "type":      "patrol",
        "waypoints": [(3,4),(2,4),(1,4),(1,3),(1,2),(1,3),(1,4),(2,4)],
        "wp_idx":    0,
        "col":       3, "row": 4,
    },
    "teleporters":         [(2, 6), (6, 3)],
    "powerup":             {"pos": (5, 5)},
    "require_ghost_eaten": True,
    "pushable_blocks":     [(3, 5)],
    "green_walls":         set(),
    "purple_walls":        set(),
    "orange_gates":        [
        {"edge": frozenset([(4, 1), (4, 2)]), "pass_dir": (0, 1), "bidirectional": True},  # E2↔E3
    ],
},

# ── LEVEL 2 series (2A-2D, 2E): meta-rules ────────────────────────────────────
{
    # LEVEL 2A -- teal/purple/orange walls, ambush ghost, shared teleporter
    "title": "LEVEL 2A",
    "cols": 8, "rows": 8, "cell": 78,
    "start": (0, 0),
    "goals": [
        {"pos": (7, 7), "type": "banana"},   # H8
        {"pos": (5, 2), "type": "banana"},   # F3
    ],
    "max_moves": 74,
    "walls": {
        _n(2,1), _n(3,1), _n(5,1), _n(5,3), _n(6,1), _n(7,1),
        _n(7,2),_n(5,2),
        _n(4,3), _n(3,3),
        _n(0,4), _n(1,4), _n(2,4),
        _n(0,5), _n(1,5), _n(2,5), _n(6,5), _n(7,5),
        _n(3,6), _n(5,6),
        _n(0,7),
        _e(1,2),
        _e(3,0), _e(3,1), _e(3,2),
        _n(6,3), _e(4,5), _e(7,4),
        _e(5,5), _e(5,6),
        _e(6,6), _e(6,7),
        _e(7,2),
    },
    "green_walls":  set(),
    "purple_walls": set(),
    "orange_gates": [
        {"edge": frozenset([(4, 0), (4, 1)]), "pass_dir": (0, 1), "bidirectional": True},   # E1↔E2
    ],
    "gate":  None,
    "ghost": {
        "col": 3, "row": 0, "axis": "h",
        "min_col": 3, "max_col": 5, "dir": 1,   # patrolt D1-F1
    },
    "ambush_ghost": {
        "col": 0, "row": 5,
        "activated": False, "move_count": 0, "paused": False,
    },
    "teleporters":         [(7, 0), (7, 2)],   # H1 ↔ H3
    "powerups": [
        {"pos": (1, 4)},   # B5
        {"pos": (7, 4)},   # H5
    ],
    "require_ghost_eaten": True,
    "pushable_blocks":     [(5, 3), (4, 4)],
    "meta_blocks":         [],
},
{
    # LEVEL 2B -- teal walls, ambush ghost, orange gate, power-up meta
    "title": "LEVEL 2B",
    "cols": 8, "rows": 8, "cell": 78,
    "start": (0, 0),
    "goals": [
        {"pos": (7, 7), "type": "banana"},   # H8
        {"pos": (1, 6), "type": "banana"},   # B7
    ],
    "max_moves": 60,
    "walls": {
        _e(1, 0), _e(6, 0),
        _e(4, 3), _e(6, 3),
        _e(3, 6), _e(6, 6), _e(7, 6),
        _n(0, 6),
        _n(1, 1), _n(1, 6),
        _n(2, 1), _n(2, 7),
        _n(6, 7),
        _n(7, 7),
    },
    "green_walls": {
        _e(6, 1), _e(7, 1),
        _e(2, 3), _e(3, 3),
        _e(5, 4), _e(6, 4),
        _e(1, 5), _e(4, 5),
        _e(1, 6), _e(4, 6),
        _e(1, 7),
        _n(1, 2),
        _n(2, 4), _n(2, 5),
        _n(3, 1),
        _n(4, 2), _n(4, 7),
        _n(5, 5),
        _n(6, 3),
        _n(7, 1),
    },
    "purple_walls": set(),
    "orange_gates": [
        {"edge": frozenset([(6, 7), (7, 7)]), "pass_dir": (1, 0), "bidirectional": True},   # G8↔H8
    ],
    "gate":  None,
    "ghost": {
        "col": 7, "row": 2, "axis": "v",
        "min_row": 2, "max_row": 5, "dir": 1,   # patrolt H3-H6
    },
    "ambush_ghost": {
        "col": 4, "row": 6,
        "activated": False, "move_count": 0, "paused": False,
    },
    "teleporters":         [(6, 6), (0, 2)],   # G7 ↔ A3
    "powerups": [
        {"pos": (6, 3)},   # G4
        {"pos": (0, 3)},   # A4
    ],
    "require_ghost_eaten": True,
    "pushable_blocks":     [(6, 4)],           # G5
    "meta_blocks":         [],
},
{
    # LEVEL 2C -- delayed power-up, ambush ghost, normal teleporter
    "title": "LEVEL 2C",
    "cols": 8, "rows": 8, "cell": 78,
    "start": (0, 7),   # A8
    "goals": [
        {"pos": (3, 0), "type": "banana"},   # D1
        {"pos": (7, 2), "type": "banana"},   # H3
    ],
    "max_moves": 56,
    "walls": {
        _e(4, 0), _e(5, 0),
        _e(4, 1), _e(5, 1), _e(7, 1),
        _e(6, 2),
        _e(6, 5),
        _e(3, 7), _e(1, 4), _e(4, 3),
        _n(0, 5), _n(4, 5), _n(5, 5), _n(7, 5),
        _n(3, 6), _n(4, 6), _n(5, 6),
        _n(0, 7),
    },
    "green_walls": {
        _n(2, 2), _n(3, 2),
        _n(6, 2),
        _n(7, 1),
        _n(1, 3), _n(5, 3),
        _n(1, 7),
        _e(5, 4),
        _e(3, 6),
        _e(7, 6), _e(7, 7),
    },
    "purple_walls": set(),
    "orange_gates": [
        {"edge": frozenset([(3, 4), (4, 4)]), "pass_dir": (1, 0), "bidirectional": True},   # D5↔E5
    ],
    "shared_orange_gates": [],
    "gate":  None,
    "ghost": {
        "col": 6, "row": 3, "axis": "v",
        "min_row": 3, "max_row": 5, "dir": 1,   # patrolt G4-G6
    },
    "ambush_ghost": {
        "col": 4, "row": 0,   # E1
        "radius":    1,
        "activated": False, "move_count": 0, "paused": False,
    },
    "teleporters":         [(0, 2), (7, 5)],   # A3 ↔ H6
    "shared_teleporters":  None,
    "powerup":             {"pos": (7, 4)},    # H5
    "delayed_powerup":     {"pos": (3, 7)},    # D8
    "require_ghost_eaten": True,
    "pushable_blocks":     [(3, 6)],           # D7
    "meta_blocks":         [],
},
{
    # LEVEL 2D -- shared teleporter (teleporter meta), ambush ghost, delayed power-up
    "title": "LEVEL 2D",
    "cols": 8, "rows": 8, "cell": 78,
    "start": (1, 1),   # A1 (0-indexed: B2 → start=(1,1))
    "goals": [
        {"pos": (6, 0), "type": "banana"},   # G1
        {"pos": (0, 7), "type": "banana"},   # A8
    ],
    "max_moves": 56,
    "walls": {
        _e(4, 0), _e(4, 1), _e(4, 2), _e(4, 3), _e(4, 4), _e(4, 6),
        _e(7, 0),
        _e(5, 2),
        _e(6, 3),
        _e(3, 3),
        _e(1, 5), _e(5, 5),
        _n(0, 1),
        _n(2, 2), _n(5, 2),
        _n(1, 5),
        _n(2, 6), _n(5, 6),
    },
    "green_walls": {
        _e(1, 2), _e(1, 3), _e(1, 7),
        _e(4, 7),
        _e(7, 2),
        _n(6, 1), _n(6, 7),
        _n(0, 7),
    },
    "purple_walls": set(),
    "orange_gates": [
        {"edge": frozenset([(3, 5), (4, 5)]), "pass_dir": (1, 0), "bidirectional": True},   # D6↔E6
    ],
    "shared_orange_gates": [],
    "gate":  None,
    "ghost": {
        "col": 0, "row": 6, "axis": "h",
        "min_col": 0, "max_col": 3, "dir": 1,   # patrolt A7-D7
    },
    "ambush_ghost": {
        "col": 6, "row": 5,   # G6
        "radius":    1,
        "activated": False, "move_count": 0, "paused": False,
    },
    "shared_teleporters":  [(2, 3), (5, 3)],   # D4 <-> F4 (player and ghost)
    "teleporters":         [(4, 0), (7, 7)],   # E1 ↔ H8
    "powerup":             {"pos": (3, 3)},    # D4
    "delayed_powerup":     {"pos": (6, 6)},    # G8
    "require_ghost_eaten": True,
    "pushable_blocks":     [(5, 2)],           # F3
    "meta_blocks":         [],
},
{
    # LEVEL 2E -- patrol ghost (A6-E6) + ambush ghost (D2) + delayed PU (A1)
    #            shared teleporters A3<->H8, one-shot gates D6->D7 + G6->G7
    #            meta-block E2, normal block C8, bananas D8 + A8
    "title": "LEVEL 2E",
    "cols": 8, "rows": 8, "cell": 78,
    "start": (7, 0),   # H1
    "goals": [
        {"pos": (3, 7), "type": "banana"},   # D8
        {"pos": (0, 7), "type": "banana"},   # A8
    ],
    "max_moves": 58,
    "walls": {
        # -- Red horizontal walls ----------------------------------------------
        _n(6, 1),                                # G between rows 1-2
        _n(6, 2), _n(7, 2),  _n(5, 6),                      # G and H between rows 4-5
        _n(1, 6), _n(2, 6), _n(3, 6),_n(7, 6), # B,C,E,H between rows 6-7
                                                 # (D and G are one-shot gates)
        # -- Red vertical walls ------------------------------------------------
        _e(5, 1), _e(5, 2),   # E-F on rows 2 and 3
        _e(6, 4), _e(7, 5),_e(6, 2),_e(6, 3),   # F-G on row 5, G-H on row 6
        _e(2, 6),  # B-C on rows 7 and 8
        _e(1, 7),              # A-B on row 8
        _e(5, 6),_e(6, 5),    _e(1, 0),           # E-F on row 7
    },
    "green_walls": {
        _e(5, 7),   # E-F on row 8 (vertical)
        _n(0, 6),   # A between rows 6-7 (horizontal)
    },
    "purple_walls": set(),
    "orange_gates": [
        {"edge": frozenset([(4, 5), (4, 6)]), "pass_dir": (0, 1), "bidirectional": True},   # D6↔D7
    ],
    "shared_orange_gates": [],
    "gate":  None,
    "ghost": {
        "col": 2, "row": 5, "axis": "h",
        "min_col": 0, "max_col": 4, "dir": 1,   # patrolt A6-E6
    },
    "ambush_ghost": {
        "col": 1, "row": 1,   # D2
        "radius":    1,
        "activated": False, "move_count": 0, "paused": False,
    },
    "shared_teleporters":  [(0, 2), (7, 2)],   # A3 ↔ H8
    "teleporters":         None,
    "powerup":             {"pos": (3, 4)},
    "delayed_powerup":     {"pos": (0, 0)},    # A1 — vertraagde powerup
    "require_ghost_eaten": True,
    "pushable_blocks":     [(2, 7)],           # C8 -- normal box
    "meta_blocks":         [(4, 1)],           # E2 — sliding meta-block
},
{
    # LEVEL 2F
    "title": "LEVEL 2F",
    "cols": 8, "rows": 8, "cell": 78,
    "start": (0, 0),   # H1
    "goals": [
        {"pos": (7, 0), "type": "banana"},   # D8
        {"pos": (7, 7), "type": "banana"},   # A8
    ],
    "max_moves": 40,
    "walls": {
        # -- Red horizontal walls ----------------------------------------------
        _n(7, 1),_n(3, 2),_n(6, 3),_n(1, 5),_n(3, 6),_n(4, 7),
        # -- Red vertical walls ------------------------------------------------
        _e(2, 1),_e(2, 3),_e(3, 0),_e(3, 5),_e(4, 4),_e(5, 2),_e(6, 1),_e(7, 3),_e(7, 6),
    },
    "green_walls": {
        # -- Green horizontal walls --------------------------------------------
        _n(0, 1), _n(1, 4), _n(1, 7),_n(2, 7), _n(7, 2), 
        # -- Green vertical walls ----------------------------------------------
         _e(6, 5),   
    },
    "purple_walls": set(),
    "orange_gates": [
        {"edge": frozenset([(3, 6), (4, 6)]), "pass_dir": (0, 1), "bidirectional": True},   # D7↔E7
    ],
    "shared_orange_gates": [],
    "gate":  None,
    "ghost": {
        "col": 6, "row": 0, "axis": "h",
        "min_col": 3, "max_col": 6, "dir": 1,   # patrolt A6-E6
    },
    "ambush_ghost": {
        "col": 6, "row": 5,   # D2
        "radius":    1,
        "activated": False, "move_count": 0, "paused": False,
    },
    "shared_teleporters":  [(2, 5), (6, 4)],   # A3 ↔ H8
    "teleporters":         [(7, 6), (0, 2)],
    "powerup":             {"pos": (5, 6)},
    "delayed_powerup":     {"pos": (5, 1)},    # A1 — vertraagde powerup
    "require_ghost_eaten": True,
    "pushable_blocks":     [(5, 2)],           # C8 -- normal box
    "meta_blocks":         [(2, 3)],           # E2 — sliding meta-block
},

# -- LEVEL 3 series: meta-meta rules (local rule zones) -----------------------
{
    # LEVEL 3A -- 12x12 grid, local rule zone B5-E8
    # Zone effect: an ambush ghost entering the zone switches to
    #              clockwise perimeter patrol of the zone edge.
    #
    # Grid 12x12  (A-L = 0-11,  rows 1-12 = 0-11)
    # Player start:       A1  (0,0)
    # Bananas:            L1 (11,0)  K5 (10,4)  A12 (0,11)
    # Patrol ghost:       G1<->K1  (columns 6-10, row 0, horizontal)
    # Ambush ghost:       I5 (8,4), radius 2
    # Local rule zone:    B5-E8  -> rect(1,4,4,7)
    # Shared teleporters: K3 (10,2) <-> K10 (10,9)
    # Normal teleporters: A10 (0,9) <-> L12 (11,11)
    # Meta-movable block: C10 (2,9)
    # Normal box:         L8 (11,7)
    # Power-up (yellow):  H11 (7,10)
    # Delayed power-up:   C3 (2,2)
    # One-shot gate:      K<->L5 (bidirectional)
    "title": "LEVEL 3A",
    "cols": 12, "rows": 12, "cell": 68,
    "start": (0, 0),   # A1
    "goals": [
        {"pos": (11, 0),  "type": "banana"},   # L1
        {"pos": (10, 4),  "type": "banana"},   # K5
        {"pos": (0,  11), "type": "banana"},   # A12
    ],
    "max_moves": 75,
    "walls": {
        # -- Red horizontal (= vertical lines, between columns) ----------------
        _e(3,  0),   # C-D  row 1
        _e(6,  0),   # F-G  row 1
        _e(7,  2),   # G-H  row 3
        _e(8,  3),   # H-I  row 4
        _e(10, 3),   # J-K  row 4
        _e(9,  5),   # I-J  row 6
        _e(7,  6),   # G-H  row 7
        _e(8,  8),   # H-I  row 9
        _e(11, 8),   # K-L  row 9
        _e(9,  9),   # I-J  row 10
        _e(1,  10),  # A-B  row 11
        _e(6,  10),  # F-G  row 11
        _e(8,  10),  # H-I  row 11
        _e(4,  11),  # D-E  row 12
        # -- Red vertical (= horizontal lines, between rows) -------------------
        _n(8,  1),   # I   row 1-2
        _n(11, 1),   # L   row 1-2
        _n(2,  2),   # C   row 2-3
        _n(2,  3),   # C   row 3-4
        _n(7,  3),
        _n(7,  4),
        _n(8,  4),  # H   row 3-4
        _n(10, 4),   # K   row 4-5
        _n(10, 5),   # K   row 5-6
        _n(9,  7),   # J   row 7-8
        _n(6,  8),   # G   row 8-9
        _n(7,  8),   # H   row 8-9
        _n(1,  6),   # A   row 6-7
        _n(1,  7),   # A   row 7-8
        _n(3,  9),   # D   row 9-10
        _n(6,  11),  # G   row 11-12
        _n(7,  11),  # H   row 11-12
    },
    "green_walls": {
        # -- Green horizontal (= vertical lines, between columns) --------------
        _e(1,  1),   # A-B  row 2
        _e(1,  2),   # A-B  row 3
        _e(6,  5),   # F-G  row 6
        _e(6,  6),   # F-G  row 7
        _e(10, 8),   # J-K  row 9
        _e(3,  10),  # C-D  row 11
        _e(4,  10),  # D-E  row 11
        _e(11, 10),  # K-L  row 11
        # -- Green vertical (= horizontal lines, between rows) -----------------
        _n(4,  1),
        _n(4,  3),   # E   row 1-2
        _n(0,  2),   # A   row 2-3
        _n(1,  2),   # B   row 2-3
        _n(4,  3),   # E   row 3-4
        _n(5,  3),   # F   row 3-4
        _n(6,  4),
        _n(9, 4),
        _n(9, 5),   # G   row 4-5
        _n(9,  6),   # J   row 6-7
        _n(4,  9),   # E   row 9-10
        _n(5,  9),   # F   row 9-10
        _n(4,  10),  # E   row 10-11
        _n(11, 10),  # L   row 10-11
        _n(10, 11),  # K   row 11-12
        _n(11, 11),  # L   row 11-12
    },
    "purple_walls": set(),
    "orange_gates": [
        # K<->L row 5: bidirectional, single use
        {"edge": frozenset([(10, 4), (11, 4)]), "pass_dir": (1, 0), "bidirectional": True},
    ],
    "shared_orange_gates": [],
    "gate":  None,
    "ghost": {
        # Patrol ghost G1↔K1
        "col": 6, "row": 0, "axis": "h",
        "min_col": 6, "max_col": 10, "dir": 1,
    },
    "ambush_ghost": {
        "col": 8, "row": 4,   # I5 — activeert binnen radius 2
        "radius":    2,
        "activated": False, "move_count": 0, "paused": False,
    },
    "shared_teleporters":  [(10, 2), (10, 9)],   # K3 ↔ K10
    "teleporters":         [(0, 9), (11, 11)],    # A10 ↔ L12
    "powerup":             {"pos": (7, 10)},      # H11
    "delayed_powerup":     {"pos": (2, 2)},       # C3
    "require_ghost_eaten": True,
    "pushable_blocks":     [(11, 7)],             # L8
    "meta_blocks":         [(2, 9)],              # C10
    "local_rule_zone": {
        "rect":            (0, 3, 4, 8),           # B5-E8 (0-indexed)
        "ghost_effect":    "perimeter_patrol",
        "meta_meta_rules": set(),                  # 3A: only ghost zone effect
    },
},
{
    # LEVEL 3B — 12×12 grid, local rule zone B5-E8
    "title": "LEVEL 3B",
    "cols": 12, "rows": 12, "cell": 68,
    "start": (0, 0),   # A1
    "goals": [
        {"pos": (11, 4),  "type": "banana"},   # L1
        {"pos": (11, 11),  "type": "banana"},   # K5
        {"pos": (4,  9), "type": "banana"},   # A12
    ],
    "max_moves": 75,
    "walls": {
        # -- Red horizontal (= vertical lines, between columns) ----------------
        _e(6,  1),_e(1,  7),_e(1,  11),_e(2,  4),_e(3,  8),_e(3,  11),_e(4,  9),_e(6,  9),_e(7, 6),_e(7,  11),_e(8,  4),_e(8,  9),_e(11,  2),
        # -- Red vertical (= horizontal lines, between rows) -------------------
        _n(0,  4),_n(0,  7),_n(1,  2),_n(1,  3),_n(1,  9),_n(2,  5),_n(5,  3),_n(7,  3),_n(7,  11),_n(8,  10),_n(9,  11),_n(10,  1),_n(10,  9),_n(11,  1),_n(11,  4),_n(11,  3),_n(11,  5),_n(11,  10),
    },
    "green_walls": {
        # -- Green horizontal (= vertical lines, between columns) --------------
        _e(1,  2),_e(1,  4),_e(2,  10),_e(4,  11),_e(5,  4),_e(5,  5),_e(6,  3),_e(7,  3),_e(7,  4),_e(8,  6),_e(9,  5),_e(9,  0),_e(11,  1),_e(11,  11),
        # -- Green vertical (= horizontal lines, between rows) -----------------
        _n(0,  1),_n(0,  10),_n(1,  10),_n(4,  1),_n(4,  11),_n(5,  1),_n(5,  5),_n(5,  6),_n(6,  7),_n(6,  10),_n(8,  4),_n(8,  7),_n(9,  9),_n(11,  9),
    },
    "purple_walls": set(),
    "orange_gates": [
        # K<->L row 5: bidirectional, single use
        {"edge": frozenset([(10, 10), (11, 10)]), "pass_dir": (1, 0), "bidirectional": True},
    ],
    "shared_orange_gates": [],
    "gate":  None,
    "ghost": {
        # Patrol ghost D1↔D5
        "col": 3, "row": 0, "axis": "v",
        "min_row": 0, "max_row": 4, "dir": 1,
    },
    "ambush_ghost": {
        "col": 2, "row": 10,   # I5 — activeert binnen radius 2
        "radius":    2,
        "activated": False, "move_count": 0, "paused": False,
    },
    "shared_teleporters":  [(11, 7), (2, 6)],   # K3 ↔ K10
    "teleporters":         [(8, 0), (11, 10)],    # A10 ↔ L12
    "powerup":             {"pos": (0, 4)},      # H11
    "delayed_powerup":     {"pos": (10, 6)},       # C3
    "require_ghost_eaten": True,
    "pushable_blocks":     [(2, 0)],             # L8
    "meta_blocks":         [(10, 4)],              # C10
    "local_rule_zone": {
        "rect":            (4, 2, 9, 7),           # B5-E8 (0-indexed)
        "ghost_effect":    "perimeter_patrol",
        "meta_meta_rules": {"green_wall_oneshot"},  # 3B: ghost + one-shot green walls
    },
},
{
    # LEVEL 3C — 12×12 grid, local rule zone B5-E8
    "title": "LEVEL 3C",
    "cols": 12, "rows": 12, "cell": 68,
    "start": (0, 0),   # A1
    "goals": [
        {"pos": (11, 0),  "type": "banana"},   # L1
        {"pos": (0, 10),  "type": "banana"},   # K5
        {"pos": (11, 4), "type": "banana"},   # A12
    ],
    "max_moves": 75,
    "walls": {
        # -- Red horizontal (= vertical lines, between columns) ----------------
        _e(2,  0),_e(2,  1),_e(4,  0),_e(4,  1),_e(6,  0),_e(6,  1),_e(8,  0),_e(8,  1),
        _e(3,  10),_e(3,  11),_e(5,  10),_e(5,  11),_e(7,  10),_e(7,  11),_e(9,  11),  # C-D  row 1

        # -- Red vertical (= horizontal lines, between rows) -------------------
        _n(1,  3),_n(1,  5), _n(1,  7),_n(1,  9),_n(10,  3),_n(10,  5), _n(10,  7),_n(10,  9),
    },
    "green_walls": {
        # -- Green horizontal (= vertical lines, between columns) --------------
        _e(3,  0),_e(3,  1),_e(5,  0),_e(5,  1),_e(7,  0),_e(7,  1),_e(9,  0),_e(9,  1),
        _e(2,  10),_e(2,  11),_e(4,  10),_e(4,  11),_e(6,  10),_e(6,  11),_e(8,  10),_e(8,  11),_e(10,  10),_e(10,  11),
        # -- Green vertical (= horizontal lines, between rows) -----------------
        _n(1,  4),_n(1,  6), _n(1,  8),_n(1, 10),_n(10,  4),_n(10,  6), _n(10,  8),_n(10, 10),
    },
    "purple_walls": set(),
    "orange_gates": [
        # K<->L row 5: bidirectional, single use
        {"edge": frozenset([(10, 4), (11, 4)]), "pass_dir": (1, 0), "bidirectional": True},
    ],
    "shared_orange_gates": [],
    "gate":  None,
    "ghost": {
        # Patrol ghost G1↔K1
        "col": 6, "row": 2, "axis": "h",
        "min_col": 6, "max_col": 11, "dir": 1,
    },
    "ambush_ghost": {
        "col": 9, "row": 6,   # I5 — activeert binnen radius 2
        "radius":    2,
        "activated": False, "move_count": 0, "paused": False,
    },
    "shared_teleporters":  [(6, 11), (9, 4)],   # K3 ↔ K10
    "teleporters":         [(0, 11), (11, 11)],    # A10 ↔ L12
    "powerup":             {"pos": (9, 10)},      # H11
    "delayed_powerup":     {"pos": (4, 7)},       # C3
    "require_ghost_eaten": True,
    "pushable_blocks":     [(6, 6)],             # L8
    "meta_blocks":         [(9, 9)],              # C10
    "local_rule_zone": {
        "rect":            (0, 4, 5, 9),           # B5-E8 (0-indexed)
        "ghost_effect":    "perimeter_patrol",
        "meta_meta_rules": {"green_wall_oneshot", "delayed_pu_pause"},  # 3C: +delayed PU
    },
},
{
    # LEVEL 3D — 12×12, local rule zone A1→F6
    # Meta-meta: meta-block breaks walls inside zone while sliding
    # Meta-meta: shared TPs one-way for player (enter from zone side C3 only)
    # Meta-meta: green walls inside zone are one-shot for player
    "title": "LEVEL 3D",
    "cols": 12, "rows": 12, "cell": 68,
    "start": (2, 6),   # C7
    "goals": [
        {"pos": (5, 2),  "type": "banana"},   # F3
        {"pos": (0, 11), "type": "banana"},   # A12
        {"pos": (10, 7), "type": "banana"},   # K8
    ],
    "max_moves": 80,
    "walls": {
        # ── Inside zone red walls ─────────────────────────────────────────────
        _n(1, 3),   # B3↔4
        _n(4, 3),   # E3↔4
        # ── Outside zone red horizontal (between rows) ────────────────────────
        _n(10, 1),  # K1↔2
        _n(11, 1),  # L1↔2
        _n(2, 3),   # C3↔4
        _n(11, 4),  # L4↔5
        _n(11, 5),  # L5↔6
        _n(5, 7),   # F7↔8
        _n(1, 8),   # B8↔9
        _n(7, 8),   # H8↔9
        _n(4, 9),   # E9↔10
        _n(0, 10),  # A10↔11
        _n(2, 11),  # C11↔12
        _n(3, 11),  # D11↔12
        _n(6, 11),  # G11↔12
        # ── Outside zone red vertical (between columns) ───────────────────────
        _e(7, 0),   # G↔H row 1
        _e(9, 0),   # I↔J row 1
        _e(10, 1),  # J↔K row 2
        _e(11, 1),  # K↔L row 2
        _e(10, 5),  # J↔K row 6
        _e(2, 6),   # B↔C row 7
        _e(2, 7),   # B↔C row 8
        _e(4, 7),   # D↔E row 8
        _e(11, 8),  # K↔L row 9
        _e(4, 10),  # D↔E row 11
        _e(9, 11),  # I↔J row 12
    },
    "green_walls": {
        # ── Inside zone green (one-shot for player, meta-meta 2B rule) ────────
        _n(2, 2),   # C2↔3
        _n(3, 2),   # D2↔3
        _n(2, 4),   # C4↔5
        _n(3, 4),   # D4↔5
        _e(2, 2),   # B↔C row 3
        _e(2, 3),   # B↔C row 4
        _e(4, 2),   # D↔E row 3
        _e(4, 3),   # D↔E row 4
        _e(3, 1),   # C↔D row 2
        _e(3, 4),   # C↔D row 5
        # ── Outside zone green horizontal (between rows) ──────────────────────
        _n(9, 3),   # J3↔4
        _n(10, 3),  # K3↔4
        _n(11, 3),  # L3↔4
        _n(8, 4),   # I4↔5
        _n(5, 8),   # F8↔9
        _n(6, 9),   # G9↔10
        _n(7, 9),   # H9↔10
        _n(11, 10), # L10↔11
        _n(10, 11), # K11↔12
        # ── Outside zone green vertical (between columns) ─────────────────────
        _e(7, 2),   # G↔H row 3
        _e(9, 2),   # I↔J row 3
        _e(8, 4),   # H↔I row 5
        _e(9, 4),   # I↔J row 5
        _e(8, 5),   # H↔I row 6
        _e(8, 9),   # H↔I row 10
        _e(8, 11),  # H↔I row 12
        _e(3, 11),  # C↔D row 12
        _e(11, 11), # K↔L row 12
    },
    "purple_walls": set(),
    "orange_gates": [],
    "shared_orange_gates": [],
    "gate": None,
    "ghost": {
        # Patrol ghost H1↔H7
        "col": 7, "row": 0, "axis": "v",
        "min_row": 0, "max_row": 6, "dir": 1,
    },
    "ambush_ghost": {
        "col": 9, "row": 9,   # J10, radius 2
        "radius": 2,
        "activated": False, "move_count": 0, "paused": False,
    },
    "teleporters":        [(6, 11), (11, 6)],   # G12 ↔ L7
    "shared_teleporters": [(2, 2),  (11, 7)],   # C3 (zone, exit) ↔ L8 (entry)
    "shared_tp_zone_entry": True,               # player may only enter from index 1 (outside zone)
    "powerup":        {"pos": (5, 9)},          # F10
    "delayed_powerup": {"pos": (3, 3)},         # D4
    "require_ghost_eaten": True,
    "pushable_blocks": [(2, 9)],                # C10
    "meta_blocks":     [(6, 1)],                # G2
    "local_rule_zone": {
        "rect":            (0, 0, 5, 5),         # A1→F6
        "ghost_effect":    "perimeter_patrol",
        "meta_meta_rules": {"green_wall_oneshot", "delayed_pu_pause"},  # 3D: +TP (via shared_tp_zone_entry)
    },
},
{
    # LEVEL 3E — 12×12, local rule zone G1→L6
    # Meta-meta: meta-block breaks walls inside zone while sliding (3D rule)
    # Meta-meta: shared TPs one-way (enter from outside zone B11 only, exit at H4)
    # Meta-meta: green walls inside zone are one-shot for player (2B rule)
    "title": "LEVEL 3E",
    "cols": 12, "rows": 12, "cell": 68,
    "start": (0, 0),   # A1
    "goals": [
        {"pos": (7, 1),  "type": "banana"},   # H2
        {"pos": (0, 7),  "type": "banana"},   # A8
        {"pos": (7, 11), "type": "banana"},   # H12
    ],
    "max_moves": 80,
    "walls": {
        # ── Inside zone red horizontal (between rows at a column) ─────────────
        _n(9, 1),   # J1↔2
        _n(9, 2),   # J2↔3
        _n(7, 1),   # H1↔2
        _n(7, 2),   # H2↔3
        # ── Inside zone red vertical (between columns at a row) ───────────────
        _e(7, 1),   # G↔H row 2
        _e(8, 1),   # H↔I row 2
        _e(11, 2),  # K↔L row 3
        _e(11, 4),  # K↔L row 5
        _e(7, 3),   # G↔H row 4
        # ── Outside zone red horizontal ───────────────────────────────────────
        _n(3, 1),   # D1↔2
        _n(4, 1),   # E1↔2
        _n(1, 3),   # B3↔4
        _n(4, 3),   # E3↔4
        _n(5, 3),   # F3↔4
        _n(4, 4),   # E4↔5
        _n(3, 5),   # D5↔6
        _n(2, 6),   # C6↔7
        _n(1, 8),   # B8↔9
        _n(11, 8),  # L8↔9
        _n(1, 9),   # B9↔10
        _n(6, 9),   # G9↔10
        _n(10, 9),  # K9↔10
        _n(8, 10),  # I10↔11
        _n(9, 10),  # J10↔11
        _n(2, 11),  # C11↔12
        _n(4, 11),  # E11↔12
        _n(8, 11),  # I11↔12
        # ── Outside zone red vertical ─────────────────────────────────────────
        _e(6, 6),   # F↔G row 7
        _e(11, 6),  # K↔L row 7
        _e(4, 8),   # D↔E row 9
        _e(4, 9),   # D↔E row 10
        _e(1, 10),  # A↔B row 11
        _e(5, 10),  # E↔F row 11
        _e(11, 11), # K↔L row 12
    },
    "green_walls": {
        # ── Inside zone green horizontal (one-shot for player, meta-meta) ─────
        _n(7, 3),   # H3↔4
        _n(7, 5),   # H5↔6
        _n(8, 4),   # I4↔5
        _n(9, 3),   # J3↔4
        _n(9, 5),   # J5↔6
        _n(10, 4),  # K4↔5
        # ── Inside zone green vertical ────────────────────────────────────────
        _e(11, 1),  # K↔L row 2
        # ── Outside zone green horizontal ─────────────────────────────────────
        _n(0, 5),   # A5↔6
        _n(3, 9),   # D9↔10
        _n(0, 10),  # A10↔11
        _n(7, 11),  # H11↔12
        # ── Outside zone green vertical ───────────────────────────────────────
        _e(1, 0),   # A↔B row 1
        _e(3, 0),   # C↔D row 1
        _e(2, 1),   # B↔C row 2
        _e(4, 1),   # D↔E row 2
        _e(3, 3),   # C↔D row 4
        _e(2, 4),   # B↔C row 5
        _e(4, 5),   # D↔E row 6
        _e(2, 6),   # B↔C row 7
        _e(1, 8),   # A↔B row 9
        _e(8, 8),   # H↔I row 9
        _e(10, 8),  # J↔K row 9
        _e(1, 9),   # A↔B row 10
        _e(6, 9),   # F↔G row 10
        _e(11, 9),  # K↔L row 10
        _e(9, 10),  # I↔J row 11
        _e(3, 11),  # C↔D row 12
        _e(6, 11),  # F↔G row 12
    },
    "purple_walls": set(),
    "orange_gates": [
        {"edge": frozenset([(5, 6), (5, 7)]), "pass_dir": (0, 1), "bidirectional": True},
    ],
    "shared_orange_gates": [],
    "gate": None,
    "ghost": {
        # Patrol ghost A4↔F4 (horizontal, row index 3)
        "col": 0, "row": 3, "axis": "h",
        "min_col": 0, "max_col": 5, "dir": 1,
    },
    "ambush_ghost": {
        "col": 2, "row": 9,   # C10, radius 2
        "radius": 2,
        "activated": False, "move_count": 0, "paused": False,
    },
    "teleporters":        [(10, 10), (2, 2)],   # K11 ↔ C3
    "shared_teleporters": [(7, 3),   (1, 10)],  # H4 (zone exit) ↔ B11 (entry)
    "shared_tp_zone_entry": True,               # player enters from index 1 (B11, outside zone)
    "powerup":        {"pos": (0, 5)},          # A6
    "delayed_powerup": {"pos": (9, 5)},         # J6
    "require_ghost_eaten": True,
    "pushable_blocks": [(8, 7)],                # I8
    "meta_blocks":     [(9, 1)],                # J2
    "local_rule_zone": {
        "rect":            (6, 0, 11, 5),        # G1→L6
        "ghost_effect":    "perimeter_patrol",
        "meta_meta_rules": {"green_wall_oneshot", "delayed_pu_pause", "meta_block_breaks"},  # 3E: all
    },
},
{
    # LEVEL 3F — 12×12, local rule zone G7→L12
    # Meta-meta: meta-block breaks walls inside zone while sliding (3D/3E rule)
    # Ghost-only teleporter: L1 ↔ H10 (chasing ghost pathfinds through it; player cannot use)
    "title": "LEVEL 3F",
    "cols": 12, "rows": 12, "cell": 68,
    "start": (0, 0),   # A1
    "goals": [
        {"pos": (11, 3), "type": "banana"},   # L4
        {"pos": (9, 8),  "type": "banana"},   # J9
        {"pos": (2, 8),  "type": "banana"},   # C9
    ],
    "max_moves": 80,
    "walls": {
        # ── Outside zone red horizontal (between rows) ────────────────────────
        _n(3, 1),   # D1↔2
        _n(4, 1),   # E1↔2
        _n(6, 1),   # G1↔2
        _n(2, 2),   # C2↔3
        _n(9, 2),   # J2↔3
        _n(11, 2),  # L2↔3
        _n(6, 3),   # G3↔4
        _n(6, 4),   # G4↔5
        _n(7, 4),   # H4↔5
        _n(5, 5),   # F5↔6
        _n(11, 5),  # L5↔6
        _n(3, 6),   # D6↔7
        _n(6, 6),   # G6↔7 (zone top border)
        _n(10, 6),  # K6↔7 (zone top border)
        _n(4, 7),   # E7↔8
        _n(5, 7),   # F7↔8
        _n(0, 8),   # A8↔9
        _n(4, 8),   # E8↔9
        _n(1, 9),   # B9↔10
        _n(4, 10),  # E10↔11
        _n(1, 11),  # B11↔12
        _n(4, 11),  # E11↔12
        # ── Inside zone red horizontal ────────────────────────────────────────
        _n(8, 8),   # I8↔9
        _n(10, 8),  # K8↔9
        _n(7, 10),  # H10↔11
        # ── Outside zone red vertical (between cols) ──────────────────────────
        _e(1, 0),   # A↔B  row 1
        _e(8, 0),   # H↔I  row 1
        _e(10, 0),  # J↔K  row 1
        _e(2, 1),   # B↔C  row 2
        _e(9, 1),   # I↔J  row 2
        _e(3, 2),   # C↔D  row 3
        _e(5, 2),   # E↔F  row 3
        _e(1, 3),   # A↔B  row 4
        _e(2, 3),   # B↔C  row 4
        _e(3, 3),   # C↔D  row 4
        _e(6, 3),   # F↔G  row 4
        _e(9, 3),   # I↔J  row 4
        _e(10, 3),  # J↔K  row 4
        _e(2, 4),   # B↔C  row 5
        _e(4, 4),   # D↔E  row 5
        _e(5, 4),   # E↔F  row 5
        _e(8, 4),   # H↔I  row 5
        _e(11, 4),  # K↔L  row 5
        _e(1, 5),   # A↔B  row 6
        _e(2, 5),   # B↔C  row 6
        _e(7, 5),   # G↔H  row 6
        _e(10, 5),  # J↔K  row 6
        _e(4, 6),   # D↔E  row 7
        _e(3, 7),   # C↔D  row 8
        _e(4, 8),   # D↔E  row 9
        _e(3, 9),   # C↔D  row 10
        _e(3, 11),  # C↔D  row 12
        # ── Inside zone red vertical ──────────────────────────────────────────
        _e(6, 6),   # F↔G  row 7 (zone left border)
        _e(6, 8),   # F↔G  row 9
        _e(6, 11),  # F↔G  row 12
        _e(9, 9),   # I↔J  row 10
        _e(9, 10),  # I↔J  row 11
        _e(11, 9),  # K↔L  row 10
        _e(11, 10), # K↔L  row 11
    },
    "green_walls": {
        # ── Outside zone green horizontal ─────────────────────────────────────
        _n(10, 1),  # K1↔2
        _n(5, 2),   # F2↔3
        _n(10, 2),  # K2↔3
        _n(9, 4),   # J4↔5
        _n(2, 5),   # C5↔6
        _n(0, 6),   # A6↔7
        _n(5, 8),   # F8↔9
        _n(2, 9),   # C9↔10
        # ── Inside zone green horizontal ──────────────────────────────────────
        _n(7, 7),   # H7↔8
        _n(7, 8),   # H8↔9
        _n(7, 11),  # H11↔12
        _n(9, 10),  # J10↔11
        _n(10, 10), # K10↔11
        # ── Outside zone green vertical ────────────────────────────────────────
        _e(3, 0),   # C↔D  row 1
        _e(6, 0),   # F↔G  row 1
        _e(8, 1),   # H↔I  row 2
        _e(7, 2),   # G↔H  row 3
        _e(9, 2),   # I↔J  row 3
        _e(5, 3),   # E↔F  row 4
        _e(11, 3),  # K↔L  row 4
        _e(1, 4),   # A↔B  row 5
        _e(6, 4),   # F↔G  row 5
        _e(10, 4),  # J↔K  row 5
        _e(5, 5),   # E↔F  row 6
        _e(2, 6),   # B↔C  row 7
        _e(2, 7),   # B↔C  row 8
        _e(4, 7),   # D↔E  row 8
        _e(3, 8),   # C↔D  row 9
        _e(5, 9),   # E↔F  row 10
        _e(2, 10),  # B↔C  row 11
        _e(4, 10),  # D↔E  row 11
        # ── Inside zone green vertical ─────────────────────────────────────────
        _e(9, 8),   # I↔J  row 9
        _e(10, 8),  # J↔K  row 9
        _e(7, 9),   # G↔H  row 10
    },
    "purple_walls": set(),
    "orange_gates": [
        # One-shot gate D6↔E6 (bidirectional)
        {"edge": frozenset([(3, 5), (4, 5)]), "pass_dir": (1, 0), "bidirectional": True},
    ],
    "shared_orange_gates": [],
    "gate": None,
    "ghost": {
        # Patrol ghost I1↔I6
        "col": 8, "row": 0, "axis": "v",
        "min_row": 0, "max_row": 5, "dir": 1,
    },
    "ambush_ghost": {
        "col": 2, "row": 9,   # C10, radius 2
        "radius": 2,
        "activated": False, "move_count": 0, "paused": False,
    },
    "teleporters":       [(1, 0), (2, 0)],   # B1 ↔ C1
    "shared_teleporters": None,
    "ghost_teleporters":  [(11, 0), (7, 9)], # L1 ↔ H10 (ghost only, not player)
    "powerup":           {"pos": (5, 2)},    # F3
    "delayed_powerup":   {"pos": (11, 11)},  # L12
    "require_ghost_eaten": True,
    "pushable_blocks":   [(0, 4)],           # A5
    "meta_blocks":       [(8, 4)],           # I5
    "local_rule_zone": {
        "rect":            (6, 6, 11, 11),    # G7→L12
        "ghost_effect":    "perimeter_patrol",
        "meta_meta_rules": {"green_wall_oneshot", "delayed_pu_pause", "meta_block_breaks"},  # 3F: all
    },
},
# ── LEVEL 4 series: wagering mechanic ────────────────────────────────────────
# 4A: Wagering types A & B
# 8×8 grid. Start A1. Bananas D4+B8. Ghost patrol A4↔G4.
# Teleporters A2↔D3. Powerup G5. Pushable box D6.
{
    "title":               "LEVEL 4A",
    "cols":                8, "rows": 8, "cell": 70,
    "start":               (0, 0),
    "goals":               [
        {"pos": (3, 3), "type": "banana"},
        {"pos": (1, 7), "type": "banana"},
    ],
    "max_moves":           25,
    "optimal_moves":       18,
    "walls":               {
        # -- Horizontal walls (between row r and r+1) --------------------------
        frozenset([(2, 0), (2, 1)]),   # C1↔2
        frozenset([(3, 0), (3, 1)]),   # D1↔2
        frozenset([(3, 1), (3, 2)]),   # D2↔3
        frozenset([(2, 2), (2, 3)]),   # C3↔4
        frozenset([(4, 2), (4, 3)]),   # E3↔4
        frozenset([(7, 2), (7, 3)]),   # H3↔4
        frozenset([(2, 3), (2, 4)]),   # C4↔5
        frozenset([(4, 3), (4, 4)]),   # E4↔5
        frozenset([(1, 4), (1, 5)]),   # B5↔6
        frozenset([(3, 4), (3, 5)]),   # D5↔6
        frozenset([(1, 5), (1, 6)]),   # B6↔7
        frozenset([(5, 5), (5, 6)]),   # F6↔7
        frozenset([(1, 6), (1, 7)]),   # B7↔8
        frozenset([(5, 6), (5, 7)]),   # F7↔8
        frozenset([(7, 6), (7, 7)]),   # H7↔8
        # -- Vertical walls (between col c and c+1) ----------------------------
        frozenset([(5, 0), (6, 0)]),   # FG1
        frozenset([(6, 0), (7, 0)]),   # GH1
        frozenset([(0, 1), (1, 1)]),   # AB2
        frozenset([(4, 1), (5, 1)]),   # EF2
        frozenset([(5, 1), (6, 1)]),   # FG2
        frozenset([(6, 1), (7, 1)]),   # GH2
        frozenset([(2, 2), (3, 2)]),   # CD3
        frozenset([(3, 2), (4, 2)]),   # DE3
        frozenset([(0, 4), (1, 4)]),   # AB5
        frozenset([(2, 4), (3, 4)]),   # CD5
        frozenset([(3, 4), (4, 4)]),   # DE5
        frozenset([(5, 4), (6, 4)]),   # FG5
        frozenset([(6, 4), (7, 4)]),   # GH5
        frozenset([(4, 5), (5, 5)]),   # EF6
        frozenset([(1, 6), (2, 6)]),   # BC7
        frozenset([(2, 6), (3, 6)]),   # CD7
        frozenset([(6, 6), (7, 6)]),   # GH7
        frozenset([(1, 7), (2, 7)]),   # BC8
        frozenset([(2, 7), (3, 7)]),   # CD8
    },
    "gate":                None,
    "ghost":               {
        "col": 0, "row": 3,
        "axis": "h", "dir": 1,
        "min_col": 0, "max_col": 6,
        "min_row": 3, "max_row": 3,
    },
    "teleporters":         [(0, 1), (3, 2)],
    "powerup":             {"pos": (6, 4)},
    "powerups":            [{"pos": (6, 4)}],
    "require_ghost_eaten": True,
    "pushable_blocks":     [(3, 5)],
    "green_walls":         set(),
    "purple_walls":        set(),
    "orange_gates":        [],
    "wager_level":         True,
    "wager_coins":         50,
    "wager_move_price":    5,
    "preview_seconds":     30,
},
# ── LEVEL 4B ─────────────────────────────────────────────────────────────────
# 12×12 grid. Start A1. Bananas I11+E3. Ghost patrol G6↔L6 (horizontal).
# Teleporters L11↔F4. Powerup L9. Pushable box K11.
{
    "title":               "LEVEL 4B",
    "cols":                12, "rows": 12, "cell": 55,
    "start":               (0, 0),
    "goals":               [
        {"pos": (8, 10), "type": "banana"},   # I11
        {"pos": (4,  2), "type": "banana"},   # E3
    ],
    "max_moves":           45,
    "optimal_moves":       43,
    "walls":               {
        # -- Horizontal walls (between row r and r+1) --------------------------
        frozenset([(2,  0), (2,  1)]),    # C1↔2
        frozenset([(3,  0), (3,  1)]),    # D1↔2
        frozenset([(4,  0), (4,  1)]),    # E1↔2
        frozenset([(5,  0), (5,  1)]),    # F1↔2
        frozenset([(6,  0), (6,  1)]),    # G1↔2
        frozenset([(7,  0), (7,  1)]),    # H1↔2
        frozenset([(8,  0), (8,  1)]),    # I1↔2
        frozenset([(9,  0), (9,  1)]),    # J1↔2
        frozenset([(10, 0), (10, 1)]),    # K1↔2

        frozenset([(1,  1), (1,  2)]),    # B2↔3
        frozenset([(2,  1), (2,  2)]),    # C2↔3
        frozenset([(6,  1), (6,  2)]),    # G2↔3
        frozenset([(7,  1), (7,  2)]),    # H2↔3
        frozenset([(8,  1), (8,  2)]),    # I2↔3
        frozenset([(9,  1), (9,  2)]),    # J2↔3
        frozenset([(10, 1), (10, 2)]),    # K2↔3
        frozenset([(11, 1), (11, 2)]),    # L2↔3

        frozenset([(1,  2), (1,  3)]),    # B3↔4
        frozenset([(4,  2), (4,  3)]),    # E3↔4
        frozenset([(5,  2), (5,  3)]),    # F3↔4
        frozenset([(9,  2), (9,  3)]),    # J3↔4

        frozenset([(3,  3), (3,  4)]),    # D4↔5
        frozenset([(5,  3), (5,  4)]),    # F4↔5
        frozenset([(7,  3), (7,  4)]),    # H4↔5
        frozenset([(10, 3), (10, 4)]),    # K4↔5

        frozenset([(5,  4), (5,  5)]),    # F5↔6

        frozenset([(1,  5), (1,  6)]),    # B6↔7
        frozenset([(4,  5), (4,  6)]),    # E6↔7
        frozenset([(5,  5), (5,  6)]),    # F6↔7

        frozenset([(2,  6), (2,  7)]),    # C7↔8
        frozenset([(6,  6), (6,  7)]),    # G7↔8
        frozenset([(10, 6), (10, 7)]),    # K7↔8

        frozenset([(1,  8), (1,  9)]),    # B9↔10
        frozenset([(6,  8), (6,  9)]),    # G9↔10

        frozenset([(3,  9), (3,  10)]),   # D10↔11
        frozenset([(4,  9), (4,  10)]),   # E10↔11
        frozenset([(8,  9), (8,  10)]),   # I10↔11
        frozenset([(9,  9), (9,  10)]),   # J10↔11
        frozenset([(10, 9), (10, 10)]),   # K10↔11
        frozenset([(11, 9), (11, 10)]),   # L10↔11

        frozenset([(2,  10), (2,  11)]),  # C11↔12
        frozenset([(7,  10), (7,  11)]),  # H11↔12
        frozenset([(8,  10), (8,  11)]),  # I11↔12
        frozenset([(9,  10), (9,  11)]),  # J11↔12
        frozenset([(10, 10), (10, 11)]),  # K11↔12
        frozenset([(11, 10), (11, 11)]),  # L11↔12

        # -- Vertical walls (between col c and c+1) ----------------------------
        frozenset([(1,  0), (2,  0)]),    # BC row1
        frozenset([(0,  1), (1,  1)]),    # AB row2
        frozenset([(3,  1), (4,  1)]),    # DE row2
        frozenset([(2,  2), (3,  2)]),    # CD row3
        frozenset([(3,  2), (4,  2)]),    # DE row3
        frozenset([(10, 2), (11, 2)]),    # KL row3
        frozenset([(0,  3), (1,  3)]),    # AB row4
        frozenset([(2,  3), (3,  3)]),    # CD row4
        frozenset([(5,  3), (6,  3)]),    # FG row4
        frozenset([(8,  3), (9,  3)]),    # IJ row4
        frozenset([(3,  4), (4,  4)]),    # DE row5
        frozenset([(4,  4), (5,  4)]),    # EF row5
        frozenset([(9,  4), (10, 4)]),    # JK row5
        frozenset([(0,  5), (1,  5)]),    # AB row6
        frozenset([(3,  5), (4,  5)]),    # DE row6
        frozenset([(0,  6), (1,  6)]),    # AB row7
        frozenset([(9,  6), (10, 6)]),    # JK row7
        frozenset([(8,  7), (9,  7)]),    # IJ row8
        frozenset([(2,  8), (3,  8)]),    # CD row9
        frozenset([(7,  8), (8,  8)]),    # HI row9
        frozenset([(0,  9), (1,  9)]),    # AB row10
        frozenset([(6,  9), (7,  9)]),    # GH row10
        frozenset([(7,  9), (8,  9)]),    # HI row10
        frozenset([(0,  10), (1,  10)]),  # AB row11
        frozenset([(6,  10), (7,  10)]),  # GH row11
        frozenset([(3,  11), (4,  11)]),  # DE row12
        frozenset([(4,  11), (5,  11)]),  # EF row12
    },
    "gate":                None,
    "ghost":               {
        "col": 6, "row": 5,
        "axis": "h", "dir": 1,
        "min_col": 6, "max_col": 11,
        "min_row": 5, "max_row": 5,
    },
    "teleporters":         [(11, 10), (5, 3)],   # L11 ↔ F4
    "powerup":             {"pos": (11, 8)},      # L9
    "powerups":            [{"pos": (11, 8)}],
    "require_ghost_eaten": True,
    "pushable_blocks":     [(10, 10)],            # K11
    "green_walls":         set(),
    "purple_walls":        set(),
    "orange_gates":        [],
    "wager_level":         True,
    "wager_coins":         50,
    "wager_move_price":    5,
    "preview_seconds":     30,
},
# ── LEVEL 4C ─────────────────────────────────────────────────────────────────
# Estimate type: no move limit, player guesses how close to optimal.
# 8×8 grid. Start A1. Bananas H4+H5. Ghost L-patrol G3→E3→E6→G6 (waypoints).
# Teleporters A2↔A8. Powerup G5. Movable block B1.
{
    "title":               "LEVEL 4C",
    "cols":                8, "rows": 8, "cell": 70,
    "start":               (0, 0),
    "goals":               [
        {"pos": (7, 3), "type": "banana"},   # H4
        {"pos": (7, 4), "type": "banana"},   # H5
    ],
    "max_moves":           9999,
    "optimal_moves":       25,
    "walls":               {
        # Horizontal walls
        frozenset([(3, 0), (3, 1)]),   # D1,2
        frozenset([(6, 0), (6, 1)]),   # G1,2
        frozenset([(0, 0), (0, 1)]),   # A1,2
        frozenset([(2, 2), (2, 3)]),   # C3,4
        frozenset([(0, 3), (0, 4)]),   # A4,5
        frozenset([(3, 3), (3, 4)]),   # D4,5
        frozenset([(5, 3), (5, 4)]),   # F4,5
        frozenset([(6, 3), (6, 4)]),   # G4,5
        frozenset([(7, 3), (7, 4)]),   # H4,5
        frozenset([(1, 4), (1, 5)]),   # B5,6
        frozenset([(1, 5), (1, 6)]),   # B6,7
        frozenset([(4, 5), (4, 6)]),   # E6,7
        frozenset([(6, 5), (6, 6)]),   # G6,7
        # Vertical walls
        frozenset([(0, 1), (1, 1)]),   # AB2
        frozenset([(3, 1), (4, 1)]),   # DE2
        frozenset([(4, 1), (5, 1)]),   # EF2
        frozenset([(1, 2), (2, 2)]),   # BC3
        frozenset([(3, 2), (4, 2)]),   # DE3
        frozenset([(5, 3), (6, 3)]),   # FG4
        frozenset([(6, 3), (7, 3)]),   # GH4
        frozenset([(0, 4), (1, 4)]),   # AB5
        frozenset([(5, 4), (6, 4)]),   # FG5
        frozenset([(6, 4), (7, 4)]),   # GH5
        frozenset([(2, 5), (3, 5)]),   # CD6
        frozenset([(0, 6), (1, 6)]),   # AB7
        frozenset([(2, 6), (3, 6)]),   # CD7
        frozenset([(5, 6), (6, 6)]),   # FG7
        frozenset([(6, 6), (7, 6)]),   # GH7
        frozenset([(4, 7), (5, 7)]),   # EF8
    },
    "gate":                None,
    "ghost":               {
        "type":      "patrol",
        "col":       6, "row": 2,      # startpositie G3
        "wp_idx":    0,
        "waypoints": [
            (6, 2),   # G3  ← startpunt
            (5, 2),   # F3
            (4, 2),   # E3
            (4, 3),   # E4
            (4, 4),   # E5
            (4, 5),   # E6
            (5, 5),   # F6
            (6, 5),   # G6
            (6, 4),   # G5  <- turning point (wall G4,5 blocks G4->G3)
            (6, 5),   # G6
            (5, 5),   # F6
            (4, 5),   # E6
            (4, 4),   # E5
            (4, 3),   # E4
            (4, 2),   # E3
            (5, 2),   # F3
        ],
    },
    "teleporters":         [(0, 1), (0, 7)],   # A2 ↔ A8
    "powerup":             {"pos": (6, 4)},     # G5
    "powerups":            [{"pos": (6, 4)}],
    "require_ghost_eaten": True,
    "pushable_blocks":     [(1, 0)],            # B1
    "green_walls":         set(),
    "purple_walls":        set(),
    "orange_gates":        [],
    "estimate_level":      True,
    "wager_level":         True,
},
# ── LEVEL 4D ─────────────────────────────────────────────────────────────────
# Estimate type: no move limit, player guesses how close to optimal.
# 12×12 grid. Start A1. Bananas L1+A12. Ghost patrol J5↔L5 (horizontal).
# Teleporters A7↔L6. Powerup I3. Movable block A11.
{
    "title":               "LEVEL 4D",
    "cols":                12, "rows": 12, "cell": 55,
    "start":               (0, 0),
    "goals":               [
        {"pos": (11, 0),  "type": "banana"},   # L1
        {"pos": (0,  11), "type": "banana"},   # A12
    ],
    "max_moves":           9999,
    "optimal_moves":       37,
    "walls":               {
        # Horizontal walls
        frozenset([(1,  0), (1,  1)]),    # B1,2
        frozenset([(3,  0), (3,  1)]),    # D1,2
        frozenset([(8,  0), (8,  1)]),    # I1,2
        frozenset([(5,  1), (5,  2)]),    # F2,3
        frozenset([(11, 1), (11, 2)]),    # L2,3
        frozenset([(1,  2), (1,  3)]),    # B3,4
        frozenset([(2,  2), (2,  3)]),    # C3,4
        frozenset([(6,  2), (6,  3)]),    # G3,4
        frozenset([(8,  2), (8,  3)]),    # I3,4
        frozenset([(2,  3), (2,  4)]),    # C4,5
        frozenset([(5,  3), (5,  4)]),    # F4,5
        frozenset([(8,  3), (8,  4)]),    # I4,5
        frozenset([(1,  4), (1,  5)]),    # B5,6
        frozenset([(2,  4), (2,  5)]),    # C5,6
        frozenset([(7,  5), (7,  6)]),    # H6,7
        frozenset([(1,  6), (1,  7)]),    # B7,8
        frozenset([(5,  6), (5,  7)]),    # F7,8
        frozenset([(0,  7), (0,  8)]),    # A8,9
        frozenset([(2,  7), (2,  8)]),    # C8,9
        frozenset([(10, 7), (10, 8)]),    # K8,9
        frozenset([(2,  8), (2,  9)]),    # C9,10
        frozenset([(9,  8), (9,  9)]),    # J9,10
        frozenset([(5,  9), (5,  10)]),   # F10,11
        frozenset([(6,  9), (6,  10)]),   # G10,11
        frozenset([(1,  10), (1,  11)]),  # B11,12
        frozenset([(2,  10), (2,  11)]),  # C11,12
        frozenset([(8,  10), (8,  11)]),  # I11,12
        frozenset([(10, 10), (10, 11)]),  # K11,12
        # Vertical walls
        frozenset([(6,  0), (7,  0)]),    # GH1
        frozenset([(1,  1), (2,  1)]),    # BC2
        frozenset([(5,  1), (6,  1)]),    # FG2
        frozenset([(9,  1), (10, 1)]),    # JK2
        frozenset([(3,  2), (4,  2)]),    # DE3
        frozenset([(5,  2), (6,  2)]),    # FG3
        frozenset([(8,  2), (9,  2)]),    # IJ3
        frozenset([(0,  3), (1,  3)]),    # AB4
        frozenset([(9,  3), (10, 3)]),    # JK4
        frozenset([(0,  4), (1,  4)]),    # AB5
        frozenset([(5,  4), (6,  4)]),    # FG5
        frozenset([(8,  4), (9,  4)]),    # IJ5
        frozenset([(4,  5), (5,  5)]),    # EF6
        frozenset([(9,  5), (10, 5)]),    # JK6
        frozenset([(6,  5), (7,  5)]),    # GH6
        frozenset([(0,  6), (1,  6)]),    # AB7
        frozenset([(7,  6), (8,  6)]),    # HI7
        frozenset([(9,  6), (10, 6)]),    # JK7
        frozenset([(2,  7), (3,  7)]),    # CD8
        frozenset([(3,  7), (4,  7)]),    # DE8
        frozenset([(4,  7), (5,  7)]),    # EF8
        frozenset([(1,  8), (2,  8)]),    # BC9
        frozenset([(6,  8), (7,  8)]),    # GH9
        frozenset([(3,  9), (4,  9)]),    # DE10
        frozenset([(7,  9), (8,  9)]),    # HI10
        frozenset([(0,  10), (1,  10)]),  # AB11
        frozenset([(5,  10), (6,  10)]),  # FG11
        frozenset([(7,  10), (8,  10)]),  # HI11
        frozenset([(4,  11), (5,  11)]),  # EF12
        frozenset([(9,  11), (10, 11)]),  # JK12
    },
    "gate":                None,
    "ghost":               {
        "col": 9, "row": 4,
        "axis": "h", "dir": 1,
        "min_col": 9, "max_col": 11,
        "min_row": 4, "max_row": 4,
    },
    "teleporters":         [(0, 6), (11, 5)],   # A7 ↔ L6
    "powerup":             {"pos": (8, 2)},      # I3
    "powerups":            [{"pos": (8, 2)}],
    "require_ghost_eaten": True,
    "pushable_blocks":     [(0, 10)],            # A11
    "green_walls":         set(),
    "purple_walls":        set(),
    "orange_gates":        [],
    "estimate_level":      True,
    "wager_level":         True,
},
]
#python level1.py