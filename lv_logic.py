"""
lv_logic.py -- complete game logic for NP-Hard Pac-Man (headless, no pygame).

This file contains everything needed to simulate a level without graphical
output. Both the visual game (level1.py) and the API benchmark runner
(api_runner.py) import from here.

Architecture
------------
  make_state(lvl)               ->  build a fresh game state for a level
  player_blocked_edge(...)      ->  check whether the PLAYER may take a cell edge
  ghost_blocked_edge(...)       ->  check whether a GHOST may take a cell edge
  move_ghost(...)               ->  move the patrol ghost one step
  move_ambush_ghost(...)        ->  move the ambush ghost (BFS + zone mode)
  apply_ghost_shared_teleport(...) -> teleport a ghost through a shared/ghost portal
  slide_meta_box(...)           ->  compute the end position of a sliding meta-box
  bfs_next_step(...)            ->  BFS shortest path for the ambush ghost

Wall storage
------------
Walls are stored as a frozenset of two cell coordinates:
  frozenset([(col1, row1), (col2, row2)])
This makes direction irrelevant -- a wall between A and B is the same frozenset
as a wall between B and A.
"""

import copy
from collections import deque
from lv_constants import AMBUSH_RADIUS, AMBUSH_PAUSE_FREQ, POWER_TURNS, DELAY_PU_MOVES


# --- Wall checks -------------------------------------------------------------

def wall_between(walls, c1, r1, c2, r2):
    """Check whether there is a wall between cell (c1,r1) and (c2,r2)."""
    return frozenset([(c1, r1), (c2, r2)]) in walls


def player_blocked_edge(lvl, state, c1, r1, c2, r2):
    """Return True if the PLAYER may NOT take the edge (c1,r1)->(c2,r2).

    Order of checks (earlier = higher priority):
    1. Red wall (lvl["walls"]) -- permanent, unless broken by a meta-box
    2. Purple wall -- permanent, never breakable
    3. Blue wall (green_walls) inside the zone + meta-meta rule "green_wall_oneshot"
       -> may be passed once; blocked afterwards
    4. Orange one-shot gate (orange_gates) -- direction-dependent, single use
    5. Shared one-shot gate (shared_orange_gates) -- idem, also for the ghost
    """
    edge   = frozenset([(c1, r1), (c2, r2)])
    broken = state.get("broken_walls", set())

    # Red permanent walls (broken ones excluded -- a meta-box can break them)
    if edge in lvl["walls"] and edge not in broken:
        return True

    # Purple walls are always permanent for the player
    if edge in lvl.get("purple_walls", set()) and edge not in broken:
        return True

    # Blue walls: normally passable, but inside the local rule zone with the
    # "green_wall_oneshot" meta-meta rule you may pass through only once.
    if edge in lvl.get("green_walls", set()):
        lrz = lvl.get("local_rule_zone")
        if (lrz and "green_wall_oneshot" in lrz.get("meta_meta_rules", set())
                and _edge_in_local_rule_zone(lvl, c1, r1, c2, r2)):
            if edge in state.get("used_green_walls", set()):
                return True  # already used once -> now blocked

    # Orange one-shot gates: check whether already used and whether direction matches
    for og in state.get("orange_gates", []):
        if og["edge"] == edge:
            if og["used"]:
                return True  # gate is closed after use
            if not og.get("bidirectional"):
                dc, dr = c2 - c1, r2 - r1
                if (dc, dr) != tuple(og["pass_dir"]):
                    return True  # wrong direction -- one-way gate

    # Shared one-shot gates (also visible to the ghost)
    for sg in state.get("shared_orange_gates", []):
        if sg["edge"] == edge:
            if sg["used"]:
                return True
            dc, dr = c2 - c1, r2 - r1
            if (dc, dr) != tuple(sg["pass_dir"]):
                return True

    return False


def _edge_in_local_rule_zone(lvl, c1, r1, c2, r2):
    """Return True if BOTH cells of the edge lie inside the local rule zone.

    Used to decide whether a wall interaction falls under the zone rules.
    A wall on the boundary (one cell inside, one outside) does NOT count as a
    zone wall.
    """
    lrz = lvl.get("local_rule_zone")
    if not lrz:
        return False
    c_min, r_min, c_max, r_max = lrz["rect"]
    return (c_min <= c1 <= c_max and r_min <= r1 <= r_max
            and c_min <= c2 <= c_max and r_min <= r2 <= r_max)


def ghost_blocked_edge(lvl, c1, r1, c2, r2, shared_gates=None, broken_walls=None):
    """Return True if a GHOST may NOT take the edge (c1,r1)->(c2,r2).

    Ghosts follow different wall rules than the player:
    - Red walls: blocked (unless broken)
    - Blue walls OUTSIDE the zone: blocked (ghosts cannot pass them)
    - Blue walls INSIDE the zone: passable (the zone effect does not stop them)
    - Purple walls: deliberately NOT checked -- ghosts ignore purple walls
    - Orange gates: always blocked for ordinary patrol ghosts
    - Shared gates: blocked if already used or wrong direction
    """
    edge   = frozenset([(c1, r1), (c2, r2)])
    broken = broken_walls or set()

    if edge in lvl["walls"] and edge not in broken:
        return True

    # Blue walls are passable for ghosts ONLY inside the local rule zone.
    # Outside the zone they are an obstacle for ghosts (but not for players).
    in_zone = _edge_in_local_rule_zone(lvl, c1, r1, c2, r2)
    if edge in lvl.get("green_walls", set()) and not in_zone and edge not in broken:
        return True

    # Ordinary orange gates always block ghosts (player-only mechanic)
    for og in lvl.get("orange_gates", []):
        if og["edge"] == edge:
            return True

    # Shared gates: a ghost may pass in the correct direction until they are used
    if shared_gates:
        for sg in shared_gates:
            if sg["edge"] == edge:
                if sg["used"]:
                    return True
                dc, dr = c2 - c1, r2 - r1
                if (dc, dr) != tuple(sg["pass_dir"]):
                    return True

    return False


# --- Creating the state ------------------------------------------------------

def make_state(lvl):
    """Build a fresh, independent game state from a level definition.

    The state is a dict holding all mutable game data. The level definition
    (lvl) holds the fixed setup (walls, goals, start position); the state holds
    what changes while playing (position, moves used, etc.).

    Returns a deep-copied state so that multiple simulations can run independently
    of one another (relevant for the multi-run API benchmark).
    """
    return {
        # Current player position (col = x-axis, row = y-axis, 0-indexed)
        "col":                  lvl["start"][0],
        "row":                  lvl["start"][1],

        # Remaining moves; if this reaches 0 -> game_over
        "moves_left":           lvl["max_moves"],

        # Direction for Pac-Man's animation (not for game logic)
        "direction":            "RIGHT",

        # "playing" | "level_complete" | "game_over"
        "status":               "playing",
        "reason":               "",  # game_over reason, for display

        # List of goal dicts; each goal gets "collected": True once reached
        "goals":                [dict(g) for g in lvl["goals"]],

        # Gate state (None if the level has no gate)
        "gate":                 dict(lvl["gate"]) if lvl["gate"] else None,

        # Deep-copied ghost dicts so the state is fully independent
        "ghost":                copy.deepcopy(lvl["ghost"])        if lvl["ghost"]               else None,
        "ambush_ghost":         copy.deepcopy(lvl["ambush_ghost"]) if lvl.get("ambush_ghost")    else None,

        # Power-up tracking (supports multiple power-ups via a list)
        "powerups_taken":       set(),   # set of indices of power-ups already picked up
        "powered_turns":        0,       # countdown; > 0 -> player can eat ghosts
        "ghost_eaten":          False,   # True once the patrol ghost has been eaten

        # Delayed power-up -- only activates DELAY_PU_MOVES moves AFTER pickup
        "delayed_pu_taken":     False,
        "delayed_pu_countdown": 0,       # remaining moves until activation
        "delayed_pu_in_zone":   False,   # True -> countdown is paused (meta-meta rule)

        # Blue walls the player has already passed once (one-shot in the zone)
        "used_green_walls":     set(),

        # Walls broken by a sliding meta-box (meta-meta "meta_block_breaks")
        "broken_walls":         set(),

        # Pushable boxes -- list of [col, row] (mutable, so list, not tuple)
        "boxes":                [list(b) for b in lvl["pushable_blocks"]],

        # Meta-boxes -- slide until an obstacle instead of one step
        "meta_boxes":           [list(b) for b in lvl.get("meta_blocks", [])],

        # One-shot gates: passable once, in one direction
        "orange_gates": [
            {"edge": og["edge"], "pass_dir": og["pass_dir"], "used": False,
             "bidirectional": og.get("bidirectional", False)}
            for og in lvl.get("orange_gates", [])
        ],

        # Shared one-shot gates: work for both the player and the ghost
        "shared_orange_gates": [
            {"edge": sg["edge"], "pass_dir": sg["pass_dir"], "used": False}
            for sg in lvl.get("shared_orange_gates", [])
        ],
    }


# --- Ghost movement ----------------------------------------------------------

def move_ghost(ghost, lvl, blocked_cells, broken_walls=None):
    """Move the patrol ghost one step.

    Two behaviour types:
    1. "patrol" (waypoint-based): follows a fixed list of coordinates in a
       cyclic loop. Used for complex routes (e.g. level 1F).
    2. Bouncing patrol (default): moves along one axis (h or v) until it hits a
       boundary or wall, then reverses. Easier to predict.

    blocked_cells: set of cells the ghost may not enter (e.g. a closed gate).
    broken_walls:  walls broken by a meta-box (the ghost can pass through them).
    """
    if ghost.get("type") == "patrol":
        # Waypoint patrol: simply take the next waypoint in the list
        ghost["wp_idx"] = (ghost["wp_idx"] + 1) % len(ghost["waypoints"])
        wp = ghost["waypoints"][ghost["wp_idx"]]
        ghost["col"] = wp[0]
        ghost["row"] = wp[1]
        return

    bw = broken_walls or set()

    if ghost["axis"] == "h":
        # Horizontal bounce
        nxt = ghost["col"] + ghost["dir"]
        if (nxt < ghost["min_col"] or nxt > ghost["max_col"]
                or ghost_blocked_edge(lvl, ghost["col"], ghost["row"], nxt, ghost["row"], broken_walls=bw)
                or (nxt, ghost["row"]) in blocked_cells):
            ghost["dir"] *= -1  # reverse
            nxt = ghost["col"] + ghost["dir"]
        if (ghost["min_col"] <= nxt <= ghost["max_col"]
                and not ghost_blocked_edge(lvl, ghost["col"], ghost["row"], nxt, ghost["row"], broken_walls=bw)
                and (nxt, ghost["row"]) not in blocked_cells):
            ghost["col"] = nxt
    else:
        # Vertical bounce
        nxt = ghost["row"] + ghost["dir"]
        if (nxt < ghost["min_row"] or nxt > ghost["max_row"]
                or ghost_blocked_edge(lvl, ghost["col"], ghost["row"], ghost["col"], nxt, broken_walls=bw)
                or (ghost["col"], nxt) in blocked_cells):
            ghost["dir"] *= -1
            nxt = ghost["row"] + ghost["dir"]
        if (ghost["min_row"] <= nxt <= ghost["max_row"]
                and not ghost_blocked_edge(lvl, ghost["col"], ghost["row"], ghost["col"], nxt, broken_walls=bw)
                and (ghost["col"], nxt) not in blocked_cells):
            ghost["row"] = nxt


def move_friendly_ghost(ghost, lvl, blocked_cells):
    """Friendly ghost -- same movement logic as the ordinary ghost.
    Reserved for future level types; currently unused.
    """
    move_ghost(ghost, lvl, blocked_cells)


# --- BFS: shortest path for the ambush ghost ---------------------------------

def bfs_next_step(ghost_col, ghost_row, target_col, target_row, lvl,
                  blocked_cells, shared_gates=None, skip_tp_at_start=False,
                  broken_walls=None):
    """Return (dc, dr) for the first step on the shortest path via BFS.

    The ambush ghost uses this to chase the player.
    BFS guarantees the shortest path; it accounts for:
    - ghost_blocked_edge: all wall types relevant to ghosts
    - shared_teleporters and ghost_teleporters: ghosts may use these
    - skip_tp_at_start=True: prevents ping-pong right after a teleporter jump
      (the ghost would otherwise immediately jump back through the portal)

    Returns (0, 0) if no path exists (a boxed-in ghost).
    """
    start  = (ghost_col, ghost_row)
    target = (target_col, target_row)
    if start == target:
        return (0, 0)

    # Build a map of teleporter links (shared + ghost-only)
    tp_map = {}
    stps = lvl.get("shared_teleporters")
    if stps:
        tp_map[tuple(stps[0])] = tuple(stps[1])
        tp_map[tuple(stps[1])] = tuple(stps[0])
    gtps = lvl.get("ghost_teleporters")
    if gtps:
        tp_map[tuple(gtps[0])] = tuple(gtps[1])
        tp_map[tuple(gtps[1])] = tuple(gtps[0])

    queue   = deque([(start, None)])  # (position, first_step)
    visited = {start}

    while queue:
        (c, r), first = queue.popleft()

        # Try all four directions
        for dc, dr in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nc, nr = c + dc, r + dr
            if (nc, nr) in visited:
                continue
            if not (0 <= nc < lvl["cols"] and 0 <= nr < lvl["rows"]):
                continue
            if ghost_blocked_edge(lvl, c, r, nc, nr, shared_gates, broken_walls=broken_walls or set()):
                continue
            if (nc, nr) in blocked_cells:
                continue

            # Remember the very first step -- that is what we return
            step = first if first is not None else (dc, dr)
            if (nc, nr) == target:
                return step
            visited.add((nc, nr))
            queue.append(((nc, nr), step))

        # Teleporter jump from the current position
        if (c, r) in tp_map:
            if (c, r) == start and skip_tp_at_start:
                continue  # skip the teleporter at the start position (anti ping-pong)
            nc, nr = tp_map[(c, r)]
            if (nc, nr) not in visited:
                step = first if first is not None else (nc - c, nr - r)
                if (nc, nr) == target:
                    return step
                visited.add((nc, nr))
                queue.append(((nc, nr), step))

    return (0, 0)  # no path found


# --- Local rule zone: perimeter computation ----------------------------------

def compute_zone_perimeter(rect):
    """Return the edge cells of a rectangular zone in CLOCKWISE order.

    rect = (col_min, row_min, col_max, row_max)
    Order: top ->  right (down)  bottom (left)  left (up)

    Used by the ambush ghost when it enters the zone and switches to perimeter
    patrol (meta-meta rule "perimeter_patrol").
    Corners are included only once (no duplicates).
    """
    c_min, r_min, c_max, r_max = rect
    p = []
    for c in range(c_min, c_max + 1):          # top ->
        p.append((c, r_min))
    for r in range(r_min + 1, r_max + 1):       # right (down)
        p.append((c_max, r))
    for c in range(c_max - 1, c_min - 1, -1):  # bottom (left)
        p.append((c, r_max))
    for r in range(r_max - 1, r_min, -1):       # left (up)
        p.append((c_min, r))
    return p


# --- Ambush ghost movement ---------------------------------------------------

def move_ambush_ghost(ghost, lvl, player_col, player_row, blocked_cells,
                      shared_gates=None, broken_walls=None):
    """Move the ambush ghost one step.

    Behaviour state machine with three modes:

    1. DORMANT -- the ghost stays still until the player comes within Chebyshev
       distance ghost["radius"]. Chebyshev = max(|d_col|, |d_row|).

    2. ACTIVE (chasing) -- follows the player via BFS. Pauses every
       AMBUSH_PAUSE_FREQ moves (gives the player a breather).

    3. ZONE MODE -- once the ghost steps into a local_rule_zone with effect
       "perimeter_patrol", it switches to clockwise edge patrol. It walks the
       perimeter of the zone until it leaves. This mode takes priority over
       chasing.
    """
    lrz = lvl.get("local_rule_zone")

    # -- Mode 3: zone patrol (highest priority) --------------------------------
    if lrz and lrz.get("ghost_effect") == "perimeter_patrol":
        c_min, r_min, c_max, r_max = lrz["rect"]
        in_zone = (c_min <= ghost["col"] <= c_max
                   and r_min <= ghost["row"] <= r_max)

        if in_zone:
            if not ghost.get("zone_mode", False):
                # First time in the zone: build the perimeter list and find the
                # start index (the closest edge point to the current position)
                ghost["activated"] = True
                perimeter = compute_zone_perimeter(lrz["rect"])
                entry = (ghost["col"], ghost["row"])
                if entry in perimeter:
                    start_idx = perimeter.index(entry)
                else:
                    # Interior cell (unexpected): pick the nearest edge cell
                    start_idx = min(range(len(perimeter)),
                                    key=lambda i: (abs(perimeter[i][0] - entry[0])
                                                   + abs(perimeter[i][1] - entry[1])))
                ghost["zone_mode"]      = True
                ghost["zone_perimeter"] = perimeter
                ghost["zone_wp_idx"]    = start_idx

            # One step clockwise along the edge
            perimeter = ghost["zone_perimeter"]
            next_idx  = (ghost["zone_wp_idx"] + 1) % len(perimeter)
            ghost["zone_wp_idx"]        = next_idx
            ghost["col"], ghost["row"] = perimeter[next_idx]
            ghost["paused"]            = False
            return

        elif ghost.get("zone_mode"):
            # Ghost has left the zone -> reset to normal chase mode
            ghost["zone_mode"]      = False
            ghost["zone_perimeter"] = None
            ghost["zone_wp_idx"]    = 0

    # -- Mode 1: check whether the ghost wakes up ------------------------------
    if not ghost["activated"]:
        chebyshev = max(abs(ghost["col"] - player_col),
                        abs(ghost["row"] - player_row))
        if chebyshev <= ghost.get("radius", AMBUSH_RADIUS):
            ghost["activated"] = True

    if not ghost["activated"]:
        ghost["paused"] = False
        return

    # -- Mode 2: chase with periodic pause -------------------------------------
    ghost["move_count"] += 1
    if ghost["move_count"] % AMBUSH_PAUSE_FREQ == 0:
        # Every AMBUSH_PAUSE_FREQ moves the ghost stays still for one turn
        ghost["paused"] = True
        return

    ghost["paused"] = False
    prev_col, prev_row = ghost["col"], ghost["row"]

    # Teleporter cooldown: prevents the ghost from immediately jumping back
    # through the same portal right after it went through
    tp_cd = ghost.get("tp_cooldown", 0)
    if tp_cd > 0:
        ghost["tp_cooldown"] = tp_cd - 1
        skip_tp = True
    else:
        skip_tp = False

    dc, dr = bfs_next_step(ghost["col"], ghost["row"],
                           player_col, player_row,
                           lvl, blocked_cells, shared_gates,
                           skip_tp_at_start=skip_tp,
                           broken_walls=broken_walls)

    # Only move one step (teleporter jumps are handled by
    # apply_ghost_shared_teleport AFTER this function)
    if abs(dc) <= 1 and abs(dr) <= 1:
        ghost["col"] += dc
        ghost["row"] += dr

    # If the ghost passed through a shared one-shot gate: mark it as used
    if shared_gates and (dc != 0 or dr != 0):
        edge_moved = frozenset([(prev_col, prev_row), (ghost["col"], ghost["row"])])
        for sg in shared_gates:
            if sg["edge"] == edge_moved and not sg["used"]:
                if (dc, dr) == tuple(sg["pass_dir"]):
                    sg["used"] = True


def apply_ghost_shared_teleport(ghost, lvl):
    """Teleport a ghost if it is standing on a shared or ghost-only portal.

    Must ALWAYS be called AFTER move_ghost() or move_ambush_ghost().
    The 1-turn cooldown prevents ping-pong: without it the ghost would jump
    straight back through the portal right after arriving.

    Returns True if the ghost was teleported, otherwise False.
    """
    if ghost.get("tp_cooldown", 0) > 0:
        return False

    pos = (ghost["col"], ghost["row"])
    for tp_key in ("shared_teleporters", "ghost_teleporters"):
        stp = lvl.get(tp_key)
        if not stp:
            continue
        for i, tp in enumerate(stp):
            if pos == tuple(tp):
                dest = stp[1 - i]
                ghost["col"]        = dest[0]
                ghost["row"]        = dest[1]
                ghost["tp_cooldown"] = 1  # block the return jump for 1 turn
                return True

    return False


# --- Meta-box slide ----------------------------------------------------------

def slide_meta_box(col, row, dc, dr, lvl, state, all_box_pos):
    """Compute the end position of a sliding meta-box.

    A meta-box (M) slides in the given direction until it stops because of:
    - A red, blue or purple wall
    - An orange gate
    - Another box or meta-box
    - The closed gate cell
    - The edge of the grid

    Meta-meta rule "meta_block_breaks" (only active inside the local rule zone):
    If the block hits a wall INSIDE the zone, that wall is broken and the block
    keeps sliding. Red, green and purple walls can be broken this way. Orange
    gates and other boxes never break.

    Returns the end position (col, row).
    """
    gate      = state["gate"]
    gate_cell = tuple(gate["pos"]) if gate and not gate["open"] else None
    broken    = state.get("broken_walls", set())
    lrz       = lvl.get("local_rule_zone")

    def in_zone(c, r):
        """True if cell (c, r) is in the zone AND the meta_block_breaks rule is active."""
        if not lrz:
            return False
        if "meta_block_breaks" not in lrz.get("meta_meta_rules", set()):
            return False
        c_min, r_min, c_max, r_max = lrz["rect"]
        return c_min <= c <= c_max and r_min <= r <= r_max

    def is_breakable_wall(edge):
        """True if the wall CAN be broken (red, green or purple -- not orange)."""
        return (edge in lvl["walls"]
                or edge in lvl.get("green_walls",  set())
                or edge in lvl.get("purple_walls", set()))

    while True:
        nc, nr = col + dc, row + dr

        # Stop at the edge of the grid
        if not (0 <= nc < lvl["cols"] and 0 <= nr < lvl["rows"]):
            break

        edge = frozenset([(col, row), (nc, nr)])

        # Orange gates and other boxes always stop the block
        if any(og["edge"] == edge for og in state.get("orange_gates", [])):
            break
        if (nc, nr) in all_box_pos:
            break
        if gate_cell and (nc, nr) == gate_cell:
            break

        # Wall check with optional wall-breaking (meta-meta rule)
        if is_breakable_wall(edge) and edge not in broken:
            if in_zone(col, row) and in_zone(nc, nr):
                # BOTH cells in the zone -> wall breaks, block keeps sliding
                broken.add(edge)
                state["broken_walls"] = broken
            else:
                # Outside the zone (or only one cell in the zone) -> stop normally
                break

        col, row = nc, nr

    return col, row
