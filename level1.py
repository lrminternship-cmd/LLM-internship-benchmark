"""
level1.py -- visual pygame game for NP-Hard Pac-Man.

Responsible for everything the player sees and for handling input. The game
logic (what actually happens) lives in lv_logic.py; this file calls those
functions and draws the result.

Screen modes
------------
  "intro"             ->  opening screen (press any key to start)
  "preview"           ->  wager levels: show the level for N seconds before bidding
  "wager"             ->  slider to buy/sell extra moves for coins
  "playing"           ->  game screen with grid, HUD and input
  "series_transition" ->  interstitial after finishing a series (1->2, 2->3, 3->4)
  "end_screen"        ->  end screen after finishing all levels

Draw order per frame (game screen)
----------------------------------
  1. Background + grid cells + walls/labels       (draw_grid)
  2. Level title                                  (draw_level_title)
  3. Local rule zone overlay                      (draw_local_rule_zone)
  4. Shared teleporters                           (draw_shared_teleporter)
  5. Orange gates                                 (draw_orange_gate_wall)
  6. Gate                                         (draw_gate)
  7. Power-ups                                    (draw_lightning / draw_delayed_powerup)
  8. Goals / bananas                              (draw_banana / draw_food)
  9. Boxes                                        (draw_box / draw_meta_box)
  10. Ghosts + patrol trail                       (draw_ghost / draw_ambush_ghost)
  11. Pac-Man                                     (draw_pacman)
  12. HUD (moves bar, scores)                     (draw_hud)
  13. Game-over / level-complete overlay

Animations
----------
  The variable `t` increases in seconds (60 fps). All animations are sinusoids
  over t: bobbing, mouth animation, colour pulsing, etc. This gives smooth
  animations without state machines.

Input
-----
  Arrow keys or WASD -> move
  R                  -> restart the current level
  SPACE              -> confirm (wager / next level)
  ESC                -> quit
"""

import pygame
from pygame.locals import *
import sys
import math
import json
import os
import datetime
import time

from lv_constants import *
from lv_levels    import LEVELS
from lv_logic     import (make_state, player_blocked_edge,
                          move_ghost, move_ambush_ghost,
                          apply_ghost_shared_teleport,
                          slide_meta_box,
                          _edge_in_local_rule_zone)

# ─── Opslag-helpers ───────────────────────────────────────────────────────────

_BASE_DIR        = os.path.join(os.path.dirname(__file__), "human_runs")
RUNS_DIR_EXPLICIT = os.path.join(_BASE_DIR, "pacman_explicit")
RUNS_DIR_IMPLICIT = os.path.join(_BASE_DIR, "pacman_implicit")
WAGER_DIR_AFTER_EXPLICIT = os.path.join(_BASE_DIR, "pacman_wager", "after_explicit")
WAGER_DIR_AFTER_IMPLICIT = os.path.join(_BASE_DIR, "pacman_wager", "after_implicit")
LEADERBOARD_FILE_EXPLICIT       = os.path.join(os.path.dirname(__file__), "leaderboard_explicit.json")
LEADERBOARD_FILE_IMPLICIT       = os.path.join(os.path.dirname(__file__), "leaderboard_implicit.json")
WAGER_LEADERBOARD_FILE_EXPLICIT = os.path.join(os.path.dirname(__file__), "leaderboard_wager_explicit.json")
WAGER_LEADERBOARD_FILE_IMPLICIT = os.path.join(os.path.dirname(__file__), "leaderboard_wager_implicit.json")


def _save_run_log(lvl, attempt_num, moves_log, result, moves_used, implicit=False,
                  fail_reason=None, start_time=None, session_dir=None, wager_data=None):
    """Save one attempt as JSON in the session directory, with a summary and metrics."""
    target_dir = session_dir or RUNS_DIR
    os.makedirs(target_dir, exist_ok=True)
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = lvl["title"].replace(" ", "_").replace("/", "-")
    fname = f"{ts}_{slug}_attempt{attempt_num}{'_implicit' if implicit else ''}.json"

    # ── Metrics berekenen ─────────────────────────────────────────────────────
    think_times = [e["think_time_s"] for e in moves_log if e.get("think_time_s") is not None]
    total_time  = round(sum(think_times), 3) if think_times else None
    avg_time    = round(total_time / len(think_times), 3) if think_times else None
    max_time    = round(max(think_times), 3) if think_times else None
    min_time    = round(min(think_times), 3) if think_times else None

    # Time from level start to the last move (including the first move with no predecessor)
    wall_time = None
    if start_time is not None:
        wall_time = round(time.monotonic() - start_time, 3)

    metrics = {
        "total_moves":         moves_used,
        "max_moves":           lvl["max_moves"],
        "moves_efficiency":    f"{moves_used}/{lvl['max_moves']}",
        "total_time_s":        wall_time,
        "avg_think_time_s":    avg_time,
        "max_think_time_s":    max_time,
        "min_think_time_s":    min_time,
    }

    data = {
        "timestamp":    datetime.datetime.now().isoformat(),
        "level":        lvl["title"],
        "attempt":      attempt_num,
        "implicit":     implicit,
        "final_status": result,           # "win" | "game_over" | "skipped"
        "final_reason": fail_reason or ("Level completed!" if result == "win" else ""),
        "moves_used":   moves_used,
        "max_moves":    lvl["max_moves"],
        "metrics":      metrics,
        "moves_log":    moves_log,
    }
    if wager_data is not None:
        data["wager"] = wager_data
    out_path = os.path.join(target_dir, fname)
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    return out_path


def _save_session_summary(session_files, player_name="", implicit=False, session_dir=None):
    """Generate a single summary document of all levels played in this session."""
    target_dir = session_dir or RUNS_DIR
    os.makedirs(target_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{ts}_SESSION_SUMMARY{'_implicit' if implicit else ''}.json"

    levels = []
    total_moves_all   = 0
    total_time_all    = 0.0
    total_think_all   = 0.0
    think_count       = 0
    levels_won        = 0
    levels_failed     = 0
    levels_skipped    = 0

    for fpath in sorted(session_files):
        try:
            with open(fpath) as f:
                d = json.load(f)
        except Exception:
            continue

        think_times = [e["think_time_s"] for e in d.get("moves_log", [])
                       if e.get("think_time_s") is not None]
        level_total_think = sum(think_times)
        total_think_all  += level_total_think
        think_count      += len(think_times)

        m = d.get("metrics", {})
        wall = m.get("total_time_s") or 0
        total_time_all  += wall
        total_moves_all += d.get("moves_used", 0)

        status = d.get("final_status", "")
        if status == "win":
            levels_won     += 1
        elif status == "skipped":
            levels_skipped += 1
        else:
            levels_failed  += 1

        levels.append({
            "level":            d.get("level"),
            "attempt":          d.get("attempt"),
            "final_status":     status,
            "final_reason":     d.get("final_reason", ""),
            "moves_used":       d.get("moves_used"),
            "max_moves":        d.get("max_moves"),
            "moves_efficiency": m.get("moves_efficiency", ""),
            "total_time_s":     wall,
            "avg_think_time_s": m.get("avg_think_time_s"),
            "max_think_time_s": m.get("max_think_time_s"),
            "min_think_time_s": m.get("min_think_time_s"),
        })

    summary = {
        "timestamp":          datetime.datetime.now().isoformat(),
        "player":             player_name,
        "implicit":           implicit,
        "levels_played":      len(levels),
        "levels_won":         levels_won,
        "levels_failed":      levels_failed,
        "levels_skipped":     levels_skipped,
        "total_moves":        total_moves_all,
        "total_time_s":       round(total_time_all, 3),
        "avg_think_time_s":   round(total_think_all / think_count, 3) if think_count else None,
        "per_level":          levels,
    }

    out_path = os.path.join(target_dir, fname)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    return out_path


def _lb_file(implicit):
    return LEADERBOARD_FILE_IMPLICIT if implicit else LEADERBOARD_FILE_EXPLICIT

def _wager_lb_file(implicit):
    return WAGER_LEADERBOARD_FILE_IMPLICIT if implicit else WAGER_LEADERBOARD_FILE_EXPLICIT

def _load_leaderboard(implicit=False):
    """Load the leaderboard list from JSON; returns [] if the file does not exist."""
    path = _lb_file(implicit)
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


def _save_leaderboard(entries, implicit=False):
    """Schrijf leaderboard-lijst gesorteerd op: 1) first_try desc, 2) total_moves asc, 3) total_time_s asc."""
    entries_sorted = sorted(
        entries,
        key=lambda e: (
            -e.get("first_try", 0),
             e.get("total_moves", 999999),
             e.get("total_time_s", 999999),
        )
    )
    with open(_lb_file(implicit), "w") as f:
        json.dump(entries_sorted, f, indent=2)


def _load_wager_leaderboard(implicit=False):
    path = _wager_lb_file(implicit)
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


def _save_wager_leaderboard(entries, implicit=False):
    """Schrijf wager leaderboard gesorteerd op total_wager_coins desc."""
    entries_sorted = sorted(entries, key=lambda e: -e.get("total_wager_coins", 0))
    with open(_wager_lb_file(implicit), "w") as f:
        json.dump(entries_sorted, f, indent=2)


# --- Drawing helpers ---------------------------------------------------------
def cell_rect(col, row, lvl):
    """Return the pygame.Rect of cell (col, row) in screen coordinates.
    PADDING shifts the grid so there is room for the column/row labels.
    """
    return pygame.Rect(PADDING + col * lvl["cell"],
                       PADDING + row * lvl["cell"],
                       lvl["cell"], lvl["cell"])


def draw_wall_edge(surf, edge, lvl):
    """Draw a red permanent wall between two cells.
    Automatically decides whether it is a vertical or horizontal wall based
    on the row coordinates of the two cells in the frozenset.
    The small rectangles at the ends are decorative end caps.
    """
    (c1, r1), (c2, r2) = tuple(edge)
    cell = lvl["cell"]
    if r1 == r2:
        col_right = max(c1, c2)
        x  = PADDING + col_right * cell
        y1 = PADDING + min(r1, r2) * cell + 3
        y2 = PADDING + (min(r1, r2) + 1) * cell - 3
        pygame.draw.line(surf, C_WALL_LINE, (x, y1), (x, y2), 5)
        pygame.draw.rect(surf, C_WALL_LINE, pygame.Rect(x-4, y1-2, 8, 4))
        pygame.draw.rect(surf, C_WALL_LINE, pygame.Rect(x-4, y2-2, 8, 4))
    else:
        row_bot = max(r1, r2)
        col_l   = min(c1, c2)
        y  = PADDING + row_bot * cell
        x1 = PADDING + col_l * cell + 3
        x2 = PADDING + (col_l + 1) * cell - 3
        pygame.draw.line(surf, C_WALL_LINE, (x1, y), (x2, y), 5)
        pygame.draw.rect(surf, C_WALL_LINE, pygame.Rect(x1-2, y-4, 4, 8))
        pygame.draw.rect(surf, C_WALL_LINE, pygame.Rect(x2-2, y-4, 4, 8))


def draw_colored_wall(surf, edge, color, lvl, width=4):
    """Draw a coloured wall (blue/green or purple) with the same geometry
    as draw_wall_edge but with adjustable colour and line width.
    Used for green (one-shot) and purple (permanent) walls.
    """
    (c1, r1), (c2, r2) = tuple(edge)
    cell = lvl["cell"]
    if r1 == r2:
        col_right = max(c1, c2)
        x  = PADDING + col_right * cell
        y1 = PADDING + min(r1, r2) * cell + 4
        y2 = PADDING + (min(r1, r2) + 1) * cell - 4
        pygame.draw.line(surf, color, (x, y1), (x, y2), width)
        pygame.draw.rect(surf, color, pygame.Rect(x - 3, y1 - 2, 6, 4))
        pygame.draw.rect(surf, color, pygame.Rect(x - 3, y2 - 2, 6, 4))
    else:
        row_bot = max(r1, r2)
        y  = PADDING + row_bot * cell
        x1 = PADDING + min(c1, c2) * cell + 4
        x2 = PADDING + (min(c1, c2) + 1) * cell - 4
        pygame.draw.line(surf, color, (x1, y), (x2, y), width)
        pygame.draw.rect(surf, color, pygame.Rect(x1 - 2, y - 3, 4, 6))
        pygame.draw.rect(surf, color, pygame.Rect(x2 - 2, y - 3, 4, 6))


def draw_orange_gate_wall(surf, og, used, lvl):
    """Draw an orange one-shot gate.
    Open gates (not yet used) get an arrow indicating the pass-through direction;
    bidirectional gates get arrows on both sides.
    Used/closed gates are drawn in dark teal without an arrow.
    """
    edge     = og["edge"]
    pass_dir = og["pass_dir"]
    (c1, r1), (c2, r2) = tuple(edge)
    cell  = lvl["cell"]
    color = C_ORANGE_USED if used else C_ORANGE_WALL

    bidir = og.get("bidirectional", False)
    if r1 == r2:
        col_right = max(c1, c2)
        x  = PADDING + col_right * cell
        y1 = PADDING + min(r1, r2) * cell + 4
        y2 = PADDING + (min(r1, r2) + 1) * cell - 4
        pygame.draw.line(surf, color, (x, y1), (x, y2), 5)
        if not used:
            mid_y = (y1 + y2) // 2
            a = 9
            if bidir:
                pts_l = [(x - a, mid_y), (x - 2, mid_y - a//2), (x - 2, mid_y + a//2)]
                pts_r = [(x + a, mid_y), (x + 2, mid_y - a//2), (x + 2, mid_y + a//2)]
                pygame.draw.polygon(surf, color, pts_l)
                pygame.draw.polygon(surf, color, pts_r)
            elif pass_dir[0] < 0:
                pts = [(x - a, mid_y), (x + 4, mid_y - a//2), (x + 4, mid_y + a//2)]
                pygame.draw.polygon(surf, color, pts)
            else:
                pts = [(x + a, mid_y), (x - 4, mid_y - a//2), (x - 4, mid_y + a//2)]
                pygame.draw.polygon(surf, color, pts)
        pygame.draw.rect(surf, color, pygame.Rect(x - 3, y1 - 2, 6, 4))
        pygame.draw.rect(surf, color, pygame.Rect(x - 3, y2 - 2, 6, 4))
    else:
        row_bot = max(r1, r2)
        y  = PADDING + row_bot * cell
        x1 = PADDING + min(c1, c2) * cell + 4
        x2 = PADDING + (min(c1, c2) + 1) * cell - 4
        pygame.draw.line(surf, color, (x1, y), (x2, y), 5)
        if not used:
            mid_x = (x1 + x2) // 2
            a = 9
            if bidir:
                pts_u = [(mid_x, y - a), (mid_x - a//2, y - 2), (mid_x + a//2, y - 2)]
                pts_d = [(mid_x, y + a), (mid_x - a//2, y + 2), (mid_x + a//2, y + 2)]
                pygame.draw.polygon(surf, color, pts_u)
                pygame.draw.polygon(surf, color, pts_d)
            elif pass_dir[1] < 0:
                pts = [(mid_x, y - a), (mid_x - a//2, y + 4), (mid_x + a//2, y + 4)]
                pygame.draw.polygon(surf, color, pts)
            else:
                pts = [(mid_x, y + a), (mid_x - a//2, y - 4), (mid_x + a//2, y - 4)]
                pygame.draw.polygon(surf, color, pts)
        pygame.draw.rect(surf, color, pygame.Rect(x1 - 2, y - 3, 4, 6))
        pygame.draw.rect(surf, color, pygame.Rect(x2 - 2, y - 3, 4, 6))


def draw_gate(surf, col, row, lvl, open_, t):
    """Draw the regular gate (door) in a cell.
    Open gate: two gateposts + arch + green glowing passage.
    Closed gate: red filled cell with bars and a centre line.
    The parameter t is the animation time so the glow can pulse.
    """
    rect = cell_rect(col, row, lvl)
    cx   = rect.centerx
    c    = lvl["cell"]
    m, pw = 8, 10
    if open_:
        pygame.draw.rect(surf, C_GATE_FRAME,
                         pygame.Rect(rect.x+m, rect.y+m, pw, c-2*m), border_radius=3)
        pygame.draw.rect(surf, C_GATE_FRAME,
                         pygame.Rect(rect.right-m-pw, rect.y+m, pw, c-2*m), border_radius=3)
        arc_rect = pygame.Rect(rect.x+m, rect.y+m, c-2*m, (c-2*m)//2)
        pygame.draw.arc(surf, C_GATE_OPEN, arc_rect, 0, math.pi, 4)
        glow_w = max(1, c-2*m-pw*2-4)
        glow   = pygame.Surface((glow_w, c-2*m), pygame.SRCALPHA)
        glow.fill((*C_GATE_OPEN, int(60 + 40 * math.sin(t * 3))))
        surf.blit(glow, (rect.x+m+pw+2, rect.y+m))
    else:
        pygame.draw.rect(surf, C_GATE_SHUT,
                         pygame.Rect(rect.x+m, rect.y+m, c-2*m, c-2*m), border_radius=4)
        for i in range(4):
            by = rect.y + m + (c-2*m)*i//4
            pygame.draw.line(surf, C_GATE_FRAME, (rect.x+m, by), (rect.right-m, by), 3)
        pygame.draw.line(surf, C_GATE_FRAME, (cx, rect.y+m), (cx, rect.bottom-m), 3)


def draw_teleporter(surf, col, row, lvl, t, color_inner, color_outer):
    """Draw a rotating teleporter with concentric rings.
    Each ring is a semi-transparent circle at a rotating position.
    color_inner and color_outer set the colour gradient from inside to outside.
    The two endpoints of a teleporter pair each get a different phase (t vs t+pi)
    so they rotate as mirror images of each other.
    """
    rect  = cell_rect(col, row, lvl)
    cx, cy = rect.centerx, rect.centery
    rings = 5
    for i in range(rings, 0, -1):
        r     = int((lvl["cell"] * 0.38) * i / rings)
        angle = t * 2.5 + i * (math.pi * 2 / rings)
        ax    = int(cx + r * 0.7 * math.cos(angle))
        ay    = int(cy + r * 0.7 * math.sin(angle))
        frac  = i / rings
        rc    = int(color_outer[0]*frac + color_inner[0]*(1-frac))
        gc2   = int(color_outer[1]*frac + color_inner[1]*(1-frac))
        bc    = int(color_outer[2]*frac + color_inner[2]*(1-frac))
        alpha = int(80 + 120 * (1 - frac))
        cs    = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
        pygame.draw.circle(cs, (rc, gc2, bc, alpha), (r+1, r+1), r, max(1, r//3))
        surf.blit(cs, (cx-r-1, cy-r-1))
        pygame.draw.line(surf, (rc, gc2, bc), (cx, cy), (ax, ay), 2)
    pygame.draw.circle(surf, (0, 0, 0), (cx, cy), int(lvl["cell"] * 0.10))
    pygame.draw.circle(surf, C_WHITE,   (cx, cy), int(4 + 3*math.sin(t*6)))


def draw_shared_teleporter(surf, col, row, lvl, t, is_first=True):
    """Shared teleporter (player and ghost) -- inverted colours."""
    if is_first:
        draw_teleporter(surf, col, row, lvl, t,
                        color_inner=C_TP_SHARED_A, color_outer=(100, 120, 10))
    else:
        draw_teleporter(surf, col, row, lvl, t + math.pi,
                        color_inner=C_TP_SHARED_B, color_outer=(150, 40, 10))

    rect   = cell_rect(col, row, lvl)
    cx, cy = rect.centerx, rect.centery
    gr     = int(lvl["cell"] * 0.13)
    color  = C_TP_SHARED_A if is_first else C_TP_SHARED_B

    pygame.draw.ellipse(surf, color, pygame.Rect(cx - gr, cy - gr, gr * 2, gr * 2))
    pygame.draw.rect(surf,   color, pygame.Rect(cx - gr, cy,       gr * 2, gr // 2 + 2))
    segs = 3
    wave = [(cx - gr + 2 * gr * i / segs,
             cy + gr + 1 - int(3 * math.sin(math.pi * i)))
            for i in range(segs + 1)]
    pygame.draw.polygon(surf, C_BG,
                        [(cx - gr, cy + gr + 3)] + wave + [(cx + gr, cy + gr + 3)])


def draw_ghost_teleporter(surf, col, row, lvl, t, is_first=True):
    """Ghost-only teleporter -- ghost colour (the player cannot use this portal)."""
    # Greyish-blue tint to distinguish it from shared TPs
    inner = C_GHOST if is_first else C_GHOST_SCARED
    outer = (60, 60, 100) if is_first else (20, 40, 80)
    draw_teleporter(surf, col, row, lvl, t + (math.pi if not is_first else 0),
                    color_inner=inner, color_outer=outer)
    # Small ghost icon in the middle to indicate the type
    rect = cell_rect(col, row, lvl)
    cx, cy = rect.centerx, rect.centery
    gs = int(lvl["cell"] * 0.12)
    pygame.draw.circle(surf, inner, (cx, cy - gs // 4), gs)
    pts = [(cx - gs, cy - gs // 4 + gs // 2),
           (cx - gs, cy + gs),
           (cx - gs // 2, cy + gs - gs // 3),
           (cx, cy + gs),
           (cx + gs // 2, cy + gs - gs // 3),
           (cx + gs, cy + gs),
           (cx + gs, cy - gs // 4 + gs // 2)]
    pygame.draw.polygon(surf, inner, pts)


def draw_lightning(surf, col, row, lvl, t):
    rect = cell_rect(col, row, lvl)
    cx, cy = rect.centerx, rect.centery + int(3 * math.sin(t * 4))
    s = int(lvl["cell"] * 0.28)
    pts = [(cx + s*0.1,  cy - s),
           (cx - s*0.1,  cy - s*0.05),
           (cx + s*0.3,  cy - s*0.05),
           (cx - s*0.4,  cy + s),
           (cx + s*0.05, cy + s*0.1),
           (cx - s*0.2,  cy + s*0.1)]
    pts = [(int(x), int(y)) for x, y in pts]
    pulse = int(20 + 8 * math.sin(t * 5))
    glow_surf = pygame.Surface((pulse*2, pulse*2), pygame.SRCALPHA)
    pygame.draw.circle(glow_surf, (*C_LIGHTNING, 60), (pulse, pulse), pulse)
    surf.blit(glow_surf, (cx - pulse, cy - pulse))
    pygame.draw.polygon(surf, C_LIGHTNING_D, pts)
    pygame.draw.polygon(surf, C_LIGHTNING,   pts, 2)


def draw_delayed_powerup(surf, col, row, lvl, t, countdown=0):
    """Delayed power-up -- inverted colour of the normal lightning."""
    rect = cell_rect(col, row, lvl)
    cx, cy = rect.centerx, rect.centery + int(3 * math.sin(t * 4))
    s = int(lvl["cell"] * 0.28)
    pts = [(cx + s*0.1,  cy - s),
           (cx - s*0.1,  cy - s*0.05),
           (cx + s*0.3,  cy - s*0.05),
           (cx - s*0.4,  cy + s),
           (cx + s*0.05, cy + s*0.1),
           (cx - s*0.2,  cy + s*0.1)]
    pts = [(int(x), int(y)) for x, y in pts]
    pulse = int(20 + 8 * math.sin(t * 5))
    glow_surf = pygame.Surface((pulse * 2, pulse * 2), pygame.SRCALPHA)
    pygame.draw.circle(glow_surf, (*C_DELAY_PU, 60), (pulse, pulse), pulse)
    surf.blit(glow_surf, (cx - pulse, cy - pulse))
    pygame.draw.polygon(surf, C_DELAY_PU,   pts)
    pygame.draw.polygon(surf, C_DELAY_PU_D, pts, 2)

    dot_r   = 4
    dot_gap = dot_r * 2 + 3
    total_w = DELAY_PU_MOVES * dot_gap - 3
    dot_y   = rect.bottom - dot_r - 5
    dot_x0  = cx - total_w // 2 + dot_r
    for i in range(DELAY_PU_MOVES):
        dx     = dot_x0 + i * dot_gap
        filled = (countdown == 0) or (i < countdown)
        if filled:
            pygame.draw.circle(surf, C_DELAY_PU_D, (dx, dot_y), dot_r)
        pygame.draw.circle(surf, C_DELAY_PU, (dx, dot_y), dot_r, 2)


def draw_box(surf, col, row, lvl):
    rect  = cell_rect(col, row, lvl)
    m     = 8
    inner = pygame.Rect(rect.x+m, rect.y+m, rect.w-2*m, rect.h-2*m)
    pygame.draw.rect(surf, (10, 10, 20),
                     pygame.Rect(inner.x+4, inner.y+4, inner.w, inner.h), border_radius=4)
    pygame.draw.rect(surf, C_BOX,      inner, border_radius=4)
    pygame.draw.rect(surf, C_BOX_EDGE, inner, 3, border_radius=4)
    cx, cy = inner.centerx, inner.centery
    pygame.draw.line(surf, C_BOX_CROSS, (inner.x, cy),    (inner.right, cy),    2)
    pygame.draw.line(surf, C_BOX_CROSS, (cx, inner.y),    (cx, inner.bottom),   2)
    for bx, by in [(inner.x+5, inner.y+5), (inner.right-5, inner.y+5),
                   (inner.x+5, inner.bottom-5), (inner.right-5, inner.bottom-5)]:
        pygame.draw.circle(surf, C_BOX_EDGE, (bx, by), 3)


def draw_meta_box(surf, col, row, lvl):
    """Meta-box (blue) -- slides until it hits an obstacle."""
    rect  = cell_rect(col, row, lvl)
    m     = 8
    inner = pygame.Rect(rect.x + m, rect.y + m, rect.w - 2*m, rect.h - 2*m)
    pygame.draw.rect(surf, (10, 10, 20),
                     pygame.Rect(inner.x + 4, inner.y + 4, inner.w, inner.h), border_radius=4)
    pygame.draw.rect(surf, C_META_BOX,     inner, border_radius=4)
    pygame.draw.rect(surf, C_META_BOX_EDG, inner, 3, border_radius=4)
    cx, cy = inner.centerx, inner.centery
    pygame.draw.line(surf, C_META_BOX_CRS, (inner.x, cy),  (inner.right, cy),  2)
    pygame.draw.line(surf, C_META_BOX_CRS, (cx, inner.y),  (cx, inner.bottom), 2)
    for bx, by in [(inner.x+5, inner.y+5), (inner.right-5, inner.y+5),
                   (inner.x+5, inner.bottom-5), (inner.right-5, inner.bottom-5)]:
        pygame.draw.circle(surf, C_META_BOX_EDG, (bx, by), 3)
    a = 6
    arrows = [
        [(cx, inner.y - 2),      (cx - a, inner.y + a),      (cx + a, inner.y + a)],
        [(cx, inner.bottom + 2), (cx - a, inner.bottom - a),  (cx + a, inner.bottom - a)],
        [(inner.x - 2, cy),      (inner.x + a, cy - a),       (inner.x + a, cy + a)],
        [(inner.right + 2, cy),  (inner.right - a, cy - a),   (inner.right - a, cy + a)],
    ]
    for pts in arrows:
        pygame.draw.polygon(surf, C_META_BOX_EDG, pts)


def draw_grid(surf, lvl, font_small, t, used_green_walls=None, broken_walls=None):
    """Draw the base layer of the playfield: cells, walls and coordinate labels.

    Draw order within draw_grid:
      1. Cell backgrounds (dark blue) + cell border (C_GRID)
      2. Normal teleporters (before the walls, so walls sit on top)
      3. Ghost-only teleporters
      4. Red walls (lvl["walls"]) -- broken ones skipped
      5. Green (one-shot) walls -- used ones are darker
      6. Purple walls
      7. Column labels (A, B, C...) above the grid
      8. Rij-labels (1, 2, 3…) links van het grid

    used_green_walls: set van frozensets — blauwe muren al eenmaal gebruikt
    broken_walls:     set van frozensets — muren verbroken door meta-doos
    """
    cols, rows, cell = lvl["cols"], lvl["rows"], lvl["cell"]
    for r in range(rows):
        for c in range(cols):
            rect = cell_rect(c, r, lvl)
            pygame.draw.rect(surf, C_CELL, rect)
            pygame.draw.rect(surf, C_GRID, rect, 2)
    if lvl["teleporters"]:
        tp = lvl["teleporters"]
        draw_teleporter(surf, tp[0][0], tp[0][1], lvl, t, C_TP_A, (150, 80, 255))
        draw_teleporter(surf, tp[1][0], tp[1][1], lvl, t + math.pi, C_TP_B, (30, 220, 255))
    gtps = lvl.get("ghost_teleporters")
    if gtps:
        if lvl.get("title") == "LEVEL 3F":
            draw_shared_teleporter(surf, gtps[0][0], gtps[0][1], lvl, t, is_first=True)
            draw_shared_teleporter(surf, gtps[1][0], gtps[1][1], lvl, t, is_first=False)
        else:
            draw_ghost_teleporter(surf, gtps[0][0], gtps[0][1], lvl, t, is_first=True)
            draw_ghost_teleporter(surf, gtps[1][0], gtps[1][1], lvl, t, is_first=False)
    broken = broken_walls or set()
    for edge in lvl["walls"]:
        if edge not in broken:
            draw_wall_edge(surf, edge, lvl)
    used_gw = used_green_walls or set()
    for edge in lvl.get("green_walls", set()):
        if edge in broken:
            continue
        color = C_GREEN_WALL_USED if edge in used_gw else C_GREEN_WALL
        draw_colored_wall(surf, edge, color, lvl)
    for edge in lvl.get("purple_walls", set()):
        if edge not in broken:
            draw_colored_wall(surf, edge, C_PURPLE_WALL, lvl)
    for c in range(cols):
        img = font_small.render(chr(ord('A') + c), True, C_LABEL)
        surf.blit(img, (PADDING + c*cell + cell//2 - img.get_width()//2,
                        PADDING - img.get_height() - 10))
    for r in range(rows):
        img = font_small.render(str(r+1), True, C_LABEL)
        surf.blit(img, (PADDING - img.get_width() - 12,
                        PADDING + r*cell + cell//2 - img.get_height()//2))


def draw_food(surf, col, row, lvl, t):
    rect = cell_rect(col, row, lvl)
    cx, cy = rect.centerx, rect.centery
    p = int(4 * math.sin(t * 3))
    pygame.draw.circle(surf, C_FOOD,    (cx, cy), 18+p)
    pygame.draw.circle(surf, C_FOOD_IN, (cx, cy), 10+p)


def draw_banana(surf, col, row, lvl, t):
    rect = cell_rect(col, row, lvl)
    cx, cy = rect.centerx, rect.centery + int(3 * math.sin(t * 2.5))
    pts = [(cx + 22*math.cos(math.pi*0.15 + math.pi*0.7*i/19),
            cy + 14*math.sin(math.pi*0.15 + math.pi*0.7*i/19) - 6)
           for i in range(20)]
    pygame.draw.lines(surf, C_BANANA,   False, pts, 8)
    pygame.draw.lines(surf, C_BANANA_D, False, pts, 3)
    pygame.draw.circle(surf, C_BANANA_D, (int(pts[0][0]),  int(pts[0][1])),  4)
    pygame.draw.circle(surf, C_BANANA_D, (int(pts[-1][0]), int(pts[-1][1])), 4)


def draw_pacman(surf, col, row, lvl, t, direction, powered):
    """Draw Pac-Man as an animated pizza wedge.
    The mouth angle oscillates via sin(t*5) between nearly-closed and 35 degrees.
    `direction` sets the base rotation of the wedge (0 deg = right).
    `powered` = True -> orange colour + glow effect around Pac-Man.
    """
    rect  = cell_rect(col, row, lvl)
    cx, cy = rect.centerx, rect.centery
    r      = int(lvl["cell"] * 0.28)
    mouth  = abs(math.sin(t * 5)) * 35 + 5
    base   = {"RIGHT": 0, "LEFT": 180, "DOWN": 90, "UP": 270}.get(direction, 0)
    span   = 360 - 2*mouth
    color  = C_PAC_POWERED if powered else C_PAC
    if powered:
        glow = pygame.Surface((r*4, r*4), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*C_LIGHTNING, int(60 + 40*math.sin(t*8))), (r*2, r*2), r*2)
        surf.blit(glow, (cx - r*2, cy - r*2))
    pts = [(cx, cy)]
    for i in range(41):
        a = math.radians(base + mouth + span*i/40)
        pts.append((cx + r*math.cos(a), cy - r*math.sin(a)))
    pygame.draw.polygon(surf, color, pts)
    ex, ey = {"RIGHT": (-4,-10), "LEFT": (4,-10),
              "DOWN": (-8,-4),   "UP": (-8,-4)}.get(direction, (-4,-10))
    pygame.draw.circle(surf, C_EYE,     (cx+ex,   cy+ey),   4)
    pygame.draw.circle(surf, C_EYE_PUP, (cx+ex+1, cy+ey+1), 2)


def draw_ghost_patrol_trail(surf, ghost, lvl):
    """Draws a faint line through the cells the patrol ghost traverses."""
    if not ghost:
        return
    cell   = lvl["cell"]
    color  = (200, 200, 255, 35)
    dot_c  = (200, 200, 255, 40)
    axis   = ghost.get("axis")

    if ghost.get("type") == "patrol":
        # Waypoint-based patrol: draw lines between consecutive unique waypoints
        wps = ghost.get("waypoints", [])
        seen = []
        for wp in wps:
            if wp not in seen:
                seen.append(wp)
        if len(seen) < 2:
            return
        for i in range(len(seen) - 1):
            c1, r1 = seen[i]
            c2, r2 = seen[i + 1]
            x1 = PADDING + c1 * cell + cell // 2
            y1 = PADDING + r1 * cell + cell // 2
            x2 = PADDING + c2 * cell + cell // 2
            y2 = PADDING + r2 * cell + cell // 2
            line_surf = pygame.Surface((abs(x2-x1) or 2, abs(y2-y1) or 2), pygame.SRCALPHA)
            line_surf.fill(color)
            surf.blit(line_surf, (min(x1,x2), min(y1,y2)))
        for c, r in seen:
            cx = PADDING + c * cell + cell // 2
            cy = PADDING + r * cell + cell // 2
            dot = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(dot, dot_c, (3, 3), 3)
            surf.blit(dot, (cx - 3, cy - 3))
    elif axis == "h":
        r = ghost["row"]
        x1 = PADDING + ghost["min_col"] * cell + cell // 2
        x2 = PADDING + ghost["max_col"] * cell + cell // 2
        y  = PADDING + r * cell + cell // 2
        trail = pygame.Surface((x2 - x1, 2), pygame.SRCALPHA)
        trail.fill(color)
        surf.blit(trail, (x1, y - 1))
        for c in range(ghost["min_col"], ghost["max_col"] + 1):
            cx = PADDING + c * cell + cell // 2
            dot = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(dot, dot_c, (3, 3), 3)
            surf.blit(dot, (cx - 3, y - 3))
    elif axis == "v":
        c = ghost["col"]
        y1 = PADDING + ghost["min_row"] * cell + cell // 2
        y2 = PADDING + ghost["max_row"] * cell + cell // 2
        x  = PADDING + c * cell + cell // 2
        trail = pygame.Surface((2, y2 - y1), pygame.SRCALPHA)
        trail.fill(color)
        surf.blit(trail, (x - 1, y1))
        for r in range(ghost["min_row"], ghost["max_row"] + 1):
            cy = PADDING + r * cell + cell // 2
            dot = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(dot, dot_c, (3, 3), 3)
            surf.blit(dot, (x - 3, cy - 3))


def draw_ghost(surf, col, row, lvl, t, scared):
    rect  = cell_rect(col, row, lvl)
    cx, cy = rect.centerx, rect.centery + int(3 * math.sin(t * 2))
    r     = int(lvl["cell"] * 0.28)
    if scared:
        color = C_WHITE if int(t * 6) % 2 == 0 else C_GHOST_SCARED
    else:
        color = C_GHOST
    pygame.draw.ellipse(surf, color, pygame.Rect(cx-r, cy-r, r*2, r*2))
    pygame.draw.rect(surf, color, pygame.Rect(cx-r, cy, r*2, r))
    segs = 4
    wave = [(cx - r + 2*r*i/segs, cy + r - int(6*math.sin(math.pi*i)))
            for i in range(segs+1)]
    pygame.draw.polygon(surf, C_BG, [(cx-r, cy+r+2)] + wave + [(cx+r, cy+r+2)])
    eye_col = C_GHOST_EYE_SC if scared else C_EYE
    for ex in (-r//3, r//3):
        pygame.draw.circle(surf, eye_col, (cx+ex, cy - r//4), 5)
        if not scared:
            pygame.draw.circle(surf, C_GHOST_EYE, (cx+ex+1, cy - r//4 + 1), 3)


def draw_ambush_ghost(surf, col, row, lvl, t, activated, paused=False, scared=False):
    rect        = cell_rect(col, row, lvl)
    cx, cy_base = rect.centerx, rect.centery

    if scared:
        cy = cy_base + int(3 * math.sin(t * 3.5))
        r  = int(lvl["cell"] * 0.28)
        color = C_WHITE if int(t * 6) % 2 == 0 else C_GHOST_SCARED
        pygame.draw.ellipse(surf, color, pygame.Rect(cx - r, cy - r, r * 2, r * 2))
        pygame.draw.rect(surf,   color, pygame.Rect(cx - r, cy, r * 2, r))
        segs = 4
        wave = [(cx - r + 2 * r * i / segs, cy + r - int(6 * math.sin(math.pi * i)))
                for i in range(segs + 1)]
        pygame.draw.polygon(surf, C_BG, [(cx - r, cy + r + 2)] + wave + [(cx + r, cy + r + 2)])
        for ex in (-r // 3, r // 3):
            pygame.draw.circle(surf, C_GHOST_EYE_SC, (cx + ex, cy - r // 4), 5)
        return

    if not activated:
        cy = cy_base + int(4 * math.sin(t * 0.8))
        r  = int(lvl["cell"] * 0.26)
        glow = pygame.Surface((r * 5, r * 5), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*C_AMBUSH_GHOST, int(25 + 15 * math.sin(t * 0.8))),
                           (r * 2 + 2, r * 2 + 2), r * 2)
        surf.blit(glow, (cx - r * 2, cy - r * 2))
        body = pygame.Surface((r * 2 + 2, r * 2 + r // 2 + 4), pygame.SRCALPHA)
        pygame.draw.ellipse(body, (*C_AMBUSH_GHOST, 120), pygame.Rect(0, 0, r * 2, r * 2))
        pygame.draw.rect(body,   (*C_AMBUSH_GHOST, 120), pygame.Rect(0, r, r * 2, r // 2 + 2))
        surf.blit(body, (cx - r, cy - r))
        for ex in (-r // 3, r // 3):
            pygame.draw.line(surf, C_AMBUSH_GHOST_EYE,
                             (cx + ex - 4, cy - r // 4),
                             (cx + ex + 4, cy - r // 4), 2)

    elif paused:
        cy = cy_base
        r  = int(lvl["cell"] * 0.28)
        pygame.draw.ellipse(surf, C_AMBUSH_GHOST, pygame.Rect(cx - r, cy - r, r * 2, r * 2))
        pygame.draw.rect(surf,   C_AMBUSH_GHOST, pygame.Rect(cx - r, cy, r * 2, r))
        segs = 4
        wave = [(cx - r + 2 * r * i / segs, cy + r - int(6 * math.sin(math.pi * i)))
                for i in range(segs + 1)]
        pygame.draw.polygon(surf, C_BG, [(cx - r, cy + r + 2)] + wave + [(cx + r, cy + r + 2)])
        for ex in (-r // 3, r // 3):
            pygame.draw.circle(surf, C_EYE,              (cx + ex, cy - r // 4), 5)
            pygame.draw.circle(surf, C_AMBUSH_GHOST_EYE, (cx + ex, cy - r // 4), 3)
        px, py = cx + r - 2, cy - r - 13
        for i in range(2):
            pygame.draw.rect(surf, C_AMBUSH_GHOST_EYE,
                             pygame.Rect(px + i * 7, py, 5, 10), border_radius=1)

    else:
        cy = cy_base + int(3 * math.sin(t * 3.5))
        r  = int(lvl["cell"] * 0.28)
        glow = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*C_AMBUSH_GHOST, int(70 + 40 * math.sin(t * 4))),
                           (r * 2, r * 2), r * 2)
        surf.blit(glow, (cx - r * 2, cy - r * 2))
        pygame.draw.ellipse(surf, C_AMBUSH_GHOST, pygame.Rect(cx - r, cy - r, r * 2, r * 2))
        pygame.draw.rect(surf,   C_AMBUSH_GHOST, pygame.Rect(cx - r, cy, r * 2, r))
        segs = 4
        wave = [(cx - r + 2 * r * i / segs, cy + r - int(6 * math.sin(math.pi * i)))
                for i in range(segs + 1)]
        pygame.draw.polygon(surf, C_BG, [(cx - r, cy + r + 2)] + wave + [(cx + r, cy + r + 2)])
        for ex in (-r // 3, r // 3):
            pygame.draw.circle(surf, C_EYE,              (cx + ex,     cy - r // 4),     5)
            pygame.draw.circle(surf, C_AMBUSH_GHOST_EYE, (cx + ex + 1, cy - r // 4 + 1), 3)


def draw_local_rule_zone(surf, lrz, lvl, t):
    """Draw the local rule zone as a coloured semi-transparent overlay.

    The zone is drawn before the ghosts and player so that all elements
    appear on top of it. The border pulses slightly to accentuate the zone.
    """
    c_min, r_min, c_max, r_max = lrz["rect"]
    cell = lvl["cell"]
    w = (c_max - c_min + 1) * cell
    h = (r_max - r_min + 1) * cell
    x = PADDING + c_min * cell
    y = PADDING + r_min * cell

    # Background tint (Tol purple -- distinct from the teal meta-walls)
    zone_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    zone_surf.fill((159, 74, 150, 45))
    surf.blit(zone_surf, (x, y))

    # Pulserende rand
    pulse = int(140 + 40 * math.sin(t * 2.5))
    border_color = (159, 74, 150, pulse)
    border_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(border_surf, border_color,
                     pygame.Rect(0, 0, w, h), 3, border_radius=4)
    surf.blit(border_surf, (x, y))


def draw_level_title(surf, lvl, font_big, font_small, gw):
    """Level title centered at the top of the grid surface."""
    title_font = font_big if font_big.size(lvl["title"])[0] < gw - 20 else font_small
    title = title_font.render(lvl["title"], True, C_PAC)
    surf.blit(title, (max(4, gw // 2 - title.get_width() // 2), 10))


def _draw_controls_panel(surf, font_big, font_small, x, y, w, h):
    """Controls legend for the implicit mode (left of the grid)."""
    controls = [
        ("Arrow keys / WASD", "Move Pac-Man"),
        ("R",                 "Restart (+1 attempts)"),
        ("SPACE",             "Confirm / next level"),
        ("ESC",               "Quit game"),
    ]
    PAD = 10
    row_h = font_small.get_height() * 2 + 6
    panel_h = PAD * 2 + font_small.get_height() + 10 + len(controls) * row_h
    panel_y = y + (h - panel_h) // 2

    pygame.draw.rect(surf, (30, 30, 50), pygame.Rect(x, panel_y, w, panel_h), border_radius=8)
    pygame.draw.rect(surf, (80, 80, 120), pygame.Rect(x, panel_y, w, panel_h), 1, border_radius=8)

    cy = panel_y + PAD
    header = font_small.render("CONTROLS", True, (180, 180, 220))
    surf.blit(header, (x + w // 2 - header.get_width() // 2, cy))
    cy += header.get_height() + 6
    pygame.draw.line(surf, (80, 80, 120), (x + PAD, cy), (x + w - PAD, cy), 1)
    cy += 8

    for key, desc in controls:
        # scale the text so the key label always fits within the width
        key_s = font_small.render(key, True, (255, 220, 80))
        if key_s.get_width() > w - PAD * 2:
            scale_f = (w - PAD * 2) / key_s.get_width()
            key_s = pygame.transform.smoothscale(
                key_s, (int(key_s.get_width() * scale_f), int(key_s.get_height() * scale_f)))
        desc_s = font_small.render(desc, True, (180, 180, 180))
        if desc_s.get_width() > w - PAD * 2:
            scale_f = (w - PAD * 2) / desc_s.get_width()
            desc_s = pygame.transform.smoothscale(
                desc_s, (int(desc_s.get_width() * scale_f), int(desc_s.get_height() * scale_f)))
        surf.blit(key_s,  (x + PAD, cy))
        surf.blit(desc_s, (x + PAD, cy + key_s.get_height() + 1))
        cy += row_h


def draw_implicit_legend_panel(surf, font_big, font_small, lvl_title, x, y, w, fs_h,
                               scroll_offset=0, max_panel_h=None):
    """In implicit mode, show the known elements (with explanation) + controls in one panel."""
    entries  = IMPLICIT_LEGEND.get(lvl_title, [])
    controls = [
        ("Arrow keys / WASD", "Move Pac-Man"),
        ("R",                 "Restart (+1 attempts)"),
        ("SPACE",             "Confirm / next level"),
        ("ESC",               "Quit game"),
    ]

    PAD    = 12
    bh     = font_big.get_height()
    sh     = font_small.get_height()
    dot_r  = 6
    SB_W   = 6   # scrollbar breedte
    text_x = x + PAD + dot_r * 2 + 8
    text_w = w - PAD * 2 - dot_r * 2 - 8 - SB_W

    def _wrap_lines(text):
        words = text.split()
        lines, line = [], []
        for word in words:
            test = " ".join(line + [word])
            if font_small.size(test)[0] > text_w and line:
                lines.append(" ".join(line))
                line = [word]
            else:
                line.append(word)
        if line:
            lines.append(" ".join(line))
        return lines

    def _entry_h(desc):
        h = bh + 4
        if desc:
            h += len(_wrap_lines(desc)) * (sh + 2) + 6
        return h

    # Bereken totale inhoudshoogte
    content_h = PAD
    if entries:
        content_h += bh + 8           # KNOWN ELEMENTS header + lijn
        for _, _, desc in entries:
            content_h += _entry_h(desc)
        content_h += 14               # separator
    content_h += bh + 8              # CONTROLS header + lijn
    for _ in controls:
        content_h += sh * 2 + 6
    content_h += PAD

    cap = max_panel_h if max_panel_h is not None else fs_h - 20
    panel_h = min(cap, content_h)
    panel_y = max(10, (fs_h - panel_h) // 2)

    # Clamp the scroll so you cannot scroll past the end
    max_scroll = max(0, content_h - panel_h)
    scroll_offset = min(scroll_offset, max_scroll)

    pygame.draw.rect(surf, (30, 30, 50),  pygame.Rect(x, panel_y, w, panel_h), border_radius=8)
    pygame.draw.rect(surf, (80, 80, 120), pygame.Rect(x, panel_y, w, panel_h), 1, border_radius=8)

    # Clip rect so content does not draw outside the panel
    clip_rect = pygame.Rect(x, panel_y, w - SB_W - 2, panel_h)
    old_clip  = surf.get_clip()
    surf.set_clip(clip_rect)

    cy = panel_y + PAD - scroll_offset

    # ── Known elements ────────────────────────────────────────────────────────
    if entries:
        hdr = font_big.render("KNOWN ELEMENTS", True, (180, 180, 220))
        surf.blit(hdr, (x + PAD, cy))
        cy += bh + 6
        pygame.draw.line(surf, (80, 80, 120), (x + PAD, cy), (x + w - PAD - SB_W, cy), 1)
        cy += 8

        for color, name, desc in entries:
            pygame.draw.circle(surf, color, (x + PAD + dot_r, cy + bh // 2), dot_r)
            name_font = font_small if font_big.size(name)[0] > text_w else font_big
            surf.blit(name_font.render(name, True, C_WHITE), (text_x, cy))
            cy += name_font.get_height() + 4
            if desc:
                for ls in _wrap_lines(desc):
                    surf.blit(font_small.render(ls, True, (180, 180, 180)), (text_x, cy))
                    cy += sh + 2
                cy += 6

        cy += 6
        pygame.draw.line(surf, (80, 80, 120), (x + PAD, cy), (x + w - PAD - SB_W, cy), 1)
        cy += 8

    # ── Controls ──────────────────────────────────────────────────────────────
    hdr2 = font_big.render("CONTROLS", True, (180, 180, 220))
    surf.blit(hdr2, (x + PAD, cy))
    cy += bh + 6
    pygame.draw.line(surf, (80, 80, 120), (x + PAD, cy), (x + w - PAD - SB_W, cy), 1)
    cy += 8

    for key, desc in controls:
        key_s  = font_small.render(key,  True, (255, 220, 80))
        desc_s = font_small.render(desc, True, (180, 180, 180))
        surf.blit(key_s,  (x + PAD, cy))
        surf.blit(desc_s, (x + PAD, cy + sh + 1))
        cy += sh * 2 + 6

    surf.set_clip(old_clip)

    # -- Scrollbar (only if there is more content than is visible) ------------
    if max_scroll > 0:
        sb_x      = x + w - SB_W - 2
        sb_track_h = panel_h - 8
        sb_thumb_h = max(20, int(sb_track_h * panel_h / content_h))
        sb_thumb_y = panel_y + 4 + int((sb_track_h - sb_thumb_h) * scroll_offset / max_scroll)
        pygame.draw.rect(surf, (50, 50, 80),  pygame.Rect(sb_x, panel_y + 4, SB_W, sb_track_h), border_radius=3)
        pygame.draw.rect(surf, (120, 120, 180), pygame.Rect(sb_x, sb_thumb_y, SB_W, sb_thumb_h), border_radius=3)


def _implicit_legend_content_h(font_big, font_small, lvl_title, panel_w):
    """Compute the total content height of the implicit legend panel for lvl_title."""
    entries  = IMPLICIT_LEGEND.get(lvl_title, [])
    controls = [None] * 4   # 4 control-rijen
    PAD   = 12
    bh    = font_big.get_height()
    sh    = font_small.get_height()
    SB_W  = 6
    text_w = panel_w - PAD * 2 - 6 * 2 - 8 - SB_W

    def _wrap_n(text):
        words = text.split()
        lines, line = [], []
        for word in words:
            test = " ".join(line + [word])
            if font_small.size(test)[0] > text_w and line:
                lines.append(" ".join(line))
                line = [word]
            else:
                line.append(word)
        if line:
            lines.append(" ".join(line))
        return len(lines)

    h = PAD
    if entries:
        h += bh + 8
        for _, name, desc in entries:
            name_h = sh if font_big.size(name)[0] > text_w else bh
            h += name_h + 4
            if desc:
                h += _wrap_n(desc) * (sh + 2) + 6
        h += 14
    h += bh + 8
    h += len(controls) * (sh * 2 + 6)
    h += PAD
    return h


def draw_hud(surf, lvl, state, font_med, font_small, implicit=False, trial=1, max_trials=3, time_left=None):
    """Draw the HUD (heads-up display) below the playfield.

    Contains:
    - Moves bar: each cell = one move; green -> plenty, orange -> nearly out
    - Banana counter (only with multiple goals)
    - Ghost counter (eaten / total) if require_ghost_eaten is active
    - Power-up indicator: cells for the remaining powered_turns
    - Textual ghost status: "Eat him now!" / "Gets you!" / "Eaten!"
    """
    hud_y     = PADDING + lvl["rows"] * lvl["cell"] + 18
    max_moves = state.get("wager_max_moves", lvl["max_moves"])
    grid_w    = lvl["cols"] * lvl["cell"]
    moves     = state["moves_left"]
    powered   = state["powered_turns"]

    if not lvl.get("wager_level"):
        trial_txt = font_small.render(f"ATTEMPT {trial}/{max_trials}", True, C_LABEL)
        surf.blit(trial_txt, (PADDING + grid_w - trial_txt.get_width(), hud_y))
    if lvl.get("estimate_level"):
        moves_used_n = lvl["max_moves"] - state["moves_left"]
        surf.blit(font_small.render(f"MOVES USED:  {moves_used_n}", True, C_LABEL), (PADDING, hud_y))
    else:
        surf.blit(font_small.render("MOVES LEFT", True, C_LABEL), (PADDING, hud_y))
        pygame.draw.rect(surf, C_MOVE_BAR,
                         pygame.Rect(PADDING, hud_y+26, grid_w, 30), border_radius=6)
        bar_inner = grid_w - 4
        bw = max(1, bar_inner // max_moves)
        for i in range(max_moves):
            x = PADDING + 2 + i * bw
            if x + bw - 2 > PADDING + grid_w - 2:
                break
            color = (C_MOVE_NO if i >= moves else
                     C_MOVE_WARN if moves <= max_moves * 0.25 else C_MOVE_OK)
            pygame.draw.rect(surf, color,
                             pygame.Rect(x, hud_y+28, bw-2, 26), border_radius=3)
        num = font_med.render(str(moves), True, C_WHITE)
        surf.blit(num, (PADDING + grid_w + 14, hud_y + 26 + 15 - num.get_height()//2))

    total = len(state["goals"])
    ban_x = PADDING
    done = sum(1 for g in state["goals"] if g.get("collected"))
    ban_label = font_small.render(f"BANANAS: {done}/{total}", True, C_BANANA)
    surf.blit(ban_label, (ban_x, hud_y + 65))
    ban_x += ban_label.get_width() + 20

    if lvl["require_ghost_eaten"]:
        total_g = (1 if lvl["ghost"] else 0) + (1 if lvl.get("ambush_ghost") else 0)
        eaten_g = (1 if state["ghost_eaten"] else 0) + (
            1 if lvl.get("ambush_ghost") and state.get("ambush_ghost") is None else 0)
        ghost_counter = font_small.render(f"GHOSTS: {eaten_g}/{total_g}", True, C_GHOST)
        surf.blit(ghost_counter, (ban_x, hud_y + 65))
        ban_x += ghost_counter.get_width() + 20

    _pus = lvl.get("powerups") or ([lvl["powerup"]] if lvl.get("powerup") else [])
    if _pus:
        pw_label = font_small.render("POWER:", True, C_LIGHTNING)
        surf.blit(pw_label, (PADDING + grid_w//2, hud_y + 65))
        bar_x = PADDING + grid_w//2 + pw_label.get_width() + 8
        for i in range(POWER_TURNS):
            bc = C_POWER_BAR if i < powered else C_MOVE_NO
            pygame.draw.rect(surf, bc,
                                 pygame.Rect(bar_x + i*18, hud_y + 65, 14, 14), border_radius=3)

        if lvl["require_ghost_eaten"] and not implicit:
            gtxt = None
            if state["ghost_eaten"] and not lvl.get("ambush_ghost"):
                gtxt = font_small.render("Ghost: Eaten!", True, C_WIN)
            elif eaten_g == total_g:
                gtxt = font_small.render("All ghosts eaten!", True, C_WIN)
            elif powered:
                gtxt = font_small.render("Ghost: Eat him now!", True, C_LIGHTNING)
            if gtxt:
                surf.blit(gtxt, (PADDING, hud_y + 85))



def draw_level_complete(surf, font_large, font_big, win_w, win_h, next_num):
    overlay = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 185))
    surf.blit(overlay, (0, 0))
    cx = win_w // 2
    msg = font_large.render("LEVEL COMPLETE!", True, C_WIN)
    surf.blit(msg, (cx - msg.get_width()//2, win_h//2 - 60))
    if next_num:
        sub = font_big.render(f"Press SPACE for Level {next_num}", True, C_NEXT)
    else:
        sub = font_big.render("Congratulations — all done!", True, C_WHITE)
    surf.blit(sub, (cx - sub.get_width()//2, win_h//2 + 20))


def draw_instructions(surf, font_big, font_small, w, h, t):
    """Brief instructions screen shown once after name entry, before level 1A."""
    surf.fill(C_BG)
    cx = w // 2

    for i in range(20):
        sx = int((w * ((i * 173) % 100)) // 100)
        sy = int((h * ((i * 113) % 100)) // 100)
        sr = int(1 + 2 * math.sin(t * 1.2 + i))
        pygame.draw.circle(surf, C_GRID, (sx, sy), sr)

    y = int(h * 0.08)
    title = font_big.render("BEFORE YOU BEGIN", True, C_PAC)
    surf.blit(title, (cx - title.get_width() // 2, y))
    y += title.get_height() + 14
    pygame.draw.line(surf, C_GRID, (cx - 360, y), (cx + 360, y), 2)
    y += 24

    lines = [
        ("ABOUT THE GAME", True),
        ("", False),
        ("You are about to play a turn-based, grid-based puzzle game inspired by Pac-Man.", False),
        ("Each level has a goal — study the information panel carefully.", False),
        ("", False),
        ("MOVES & ATTEMPTS", True),
        ("", False),
        ("Every level gives you a limited number of moves to reach the goal.", False),
        ("Be deliberate — every step counts.", False),
        ("", False),
        ("If you run out of moves the level resets. You have a limited number of attempts", False),
        ("per level before the game automatically moves you to the next one.", False),
        ("", False),
        ("TIME LIMIT", True),
        ("", False),
        ("There is a total time limit of 30 minutes across all levels.", False),
        ("Any time you have left on a level carries over to the next one.", False),
        ("", False),
        ("Take your time to think, but keep an eye on the clock.", False),
    ]

    bh = font_big.get_height()
    sh = font_small.get_height()
    for text, is_header in lines:
        if not text:
            y += sh // 2
            continue
        if is_header:
            s = font_big.render(text, True, C_WIN)
            surf.blit(s, (cx - s.get_width() // 2, y))
            y += bh + 6
        else:
            s = font_small.render(text, True, C_WHITE)
            surf.blit(s, (cx - s.get_width() // 2, y))
            y += sh + 6

    y += 20
    pygame.draw.line(surf, C_GRID, (cx - 360, y), (cx + 360, y), 1)
    y += 20
    blink = int(200 + 55 * math.sin(t * 3))
    hint = font_small.render("PRESS ANY KEY TO START LEVEL 1A", True, (blink, blink, blink))
    surf.blit(hint, (cx - hint.get_width() // 2, y))


def draw_intro(surf, font_big, font_med, font_small, w, h, t, participant_id="", input_active=True):
    """Intro screen with Pac-Man preview and title."""
    surf.fill(C_BG)
    cx = w // 2

    # ── Decorative pellet row at the bottom ───────────────────────────────────
    for i in range(22):
        px = 60 + i * ((w - 120) // 21)
        pulse = int(6 + 3 * math.sin(t * 3 + i * 0.4))
        alpha = int(120 + 80 * math.sin(t * 2 + i * 0.3))
        ps = pygame.Surface((pulse * 2, pulse * 2), pygame.SRCALPHA)
        pygame.draw.circle(ps, (*C_PAC, alpha), (pulse, pulse), pulse)
        surf.blit(ps, (px - pulse, int(h * 0.88) - pulse))

    # ── Title block (top third of screen) ────────────────────────────────────
    y_top = int(h * 0.12)

    title1 = font_big.render("THE NEWEST VERSION OF", True, C_WHITE)
    title2 = font_big.render("PAC-MAN", True, C_PAC)
    title3 = font_big.render("NOW AVAILABLE", True, C_WHITE)
    sub    = font_small.render("— NP-HARD EDITION —", True, C_LIGHTNING)

    surf.blit(title1, (cx - title1.get_width() // 2, y_top))
    surf.blit(title2, (cx - title2.get_width() // 2, y_top + 48))
    surf.blit(title3, (cx - title3.get_width() // 2, y_top + 96))
    surf.blit(sub,    (cx - sub.get_width() // 2,    y_top + 148))

    # ── Separator ─────────────────────────────────────────────────────────────
    sep_y = y_top + 182
    pygame.draw.line(surf, C_GRID, (cx - 320, sep_y), (cx + 320, sep_y), 2)

    # ── Pac-Man + ghosts preview (middle of screen) ───────────────────────────
    preview_y = int(h * 0.47)

    pr = 58
    mouth = abs(math.sin(t * 4)) * 38 + 4
    pts   = [(cx - 150, preview_y)]
    for i in range(41):
        a = math.radians(mouth + (360 - 2 * mouth) * i / 40)
        pts.append((cx - 150 + pr * math.cos(a), preview_y - pr * math.sin(a)))
    pygame.draw.polygon(surf, C_PAC, pts)
    pygame.draw.circle(surf, C_EYE,     (cx - 136, preview_y - 26), 7)
    pygame.draw.circle(surf, C_EYE_PUP, (cx - 134, preview_y - 24), 3)

    ghost_colors = [C_GHOST, (255, 130, 130), (130, 255, 255)]
    for gi, gc in enumerate(ghost_colors):
        gx = cx + 50 + gi * 90
        gy = preview_y + int(6 * math.sin(t * 2 + gi * 1.1))
        gr = 36
        pygame.draw.ellipse(surf, gc, pygame.Rect(gx - gr, gy - gr, gr * 2, gr * 2))
        pygame.draw.rect(surf, gc, pygame.Rect(gx - gr, gy, gr * 2, gr))
        segs = 4
        wave = [(gx - gr + 2 * gr * i / segs, gy + gr - int(9 * math.sin(math.pi * i)))
                for i in range(segs + 1)]
        pygame.draw.polygon(surf, C_BG, [(gx - gr, gy + gr + 2)] + wave + [(gx + gr, gy + gr + 2)])
        for ex in (-gr // 3, gr // 3):
            pygame.draw.circle(surf, C_EYE, (gx + ex, gy - gr // 4), 8)
            pygame.draw.circle(surf, C_GHOST_EYE, (gx + ex + 1, gy - gr // 4 + 1), 4)

    # ── Participant ID invoerveld ──────────────────────────────────────────────
    field_y = int(h * 0.65)
    label = font_small.render("PARTICIPANT NUMBER:", True, C_LABEL)
    surf.blit(label, (cx - label.get_width() // 2, field_y))

    box_w, box_h = 260, 36
    box_x = cx - box_w // 2
    box_y = field_y + label.get_height() + 8
    box_col = C_PAC if input_active else (80, 80, 80)
    pygame.draw.rect(surf, (20, 20, 40), pygame.Rect(box_x, box_y, box_w, box_h), border_radius=6)
    pygame.draw.rect(surf, box_col, pygame.Rect(box_x, box_y, box_w, box_h), 2, border_radius=6)

    display_text = participant_id + ("|" if input_active and int(t * 2) % 2 == 0 else "")
    id_surf = font_big.render(display_text, True, C_WHITE)
    surf.blit(id_surf, (cx - id_surf.get_width() // 2, box_y + box_h // 2 - id_surf.get_height() // 2))

    # ── Instructie onderaan ────────────────────────────────────────────────────
    if participant_id:
        blink = int(200 + 55 * math.sin(t * 3))
        hint = font_small.render("PRESS ENTER TO START", True, (blink, blink, blink))
    else:
        hint = font_small.render("ENTER YOUR PARTICIPANT NUMBER TO START", True, (160, 160, 160))
    surf.blit(hint, (cx - hint.get_width() // 2, box_y + box_h + 20))


def draw_series_transition(surf, font_big, font_med, font_small, w, h, t,
                           series_done, series_next, stats=None):
    """Interstitial screen after finishing a level series."""
    surf.fill(C_BG)
    cx = w // 2
    cy = int(h * 0.30)

    # Background stars
    for i in range(24):
        sx = int((w * ((i * 137) % 100)) // 100)
        sy = int((h * ((i *  97) % 100)) // 100)
        sr = int(2 + 2 * math.sin(t * 1.5 + i))
        pygame.draw.circle(surf, C_GRID, (sx, sy), sr)

    # Title
    done_txt = font_big.render(f"LEVEL {series_done} COMPLETED!", True, C_WIN)
    surf.blit(done_txt, (cx - done_txt.get_width() // 2, cy - 40))

    pygame.draw.line(surf, C_GRID, (cx - 320, cy + 4), (cx + 320, cy + 4), 2)

    # Series stats
    if stats:
        hdr = font_big.render(f"YOUR LEVEL {series_done} STATS", True, C_LABEL)
        surf.blit(hdr, (cx - hdr.get_width() // 2, cy + 22))
        stat_lines = [
            (f"Total moves used:             {stats['moves']}", C_WHITE),
            (f"Levels completed first try:   {stats['first_try']} / {stats['total']}", C_WIN),
            (f"Levels that needed retries:   {stats['retried']} / {stats['total']}", C_LOSE),
        ]
        for i, (text, color) in enumerate(stat_lines):
            rendered = font_small.render(text, True, color)
            surf.blit(rendered, (cx - rendered.get_width() // 2, cy + 64 + i * 26))

    pygame.draw.line(surf, C_GRID, (cx - 320, cy + 150), (cx + 320, cy + 150), 2)

    # Next series announcement
    blink = int(200 + 55 * math.sin(t * 3))
    if series_next is not None:
        next_txt  = font_big.render(f"UP NEXT: LEVEL {series_next}", True, C_NEXT)
        press_txt = font_small.render(f"PRESS SPACEBAR TO CONTINUE TO LEVEL {series_next}",
                                      True, (blink, blink, blink))
        surf.blit(next_txt,  (cx - next_txt.get_width() // 2,  cy + 166))
        surf.blit(press_txt, (cx - press_txt.get_width() // 2, cy + 206))
    else:
        press_txt = font_small.render("PRESS SPACEBAR TO CONTINUE",
                                      True, (blink, blink, blink))
        surf.blit(press_txt, (cx - press_txt.get_width() // 2, cy + 166))

    # Decorative Pac-Man
    pr = 32
    mouth = abs(math.sin(t * 4)) * 35 + 5
    pts = [(cx, cy + 280)]
    for i in range(41):
        a = math.radians(mouth + (360 - 2 * mouth) * i / 40)
        pts.append((cx + pr * math.cos(a), cy + 280 - pr * math.sin(a)))
    pygame.draw.polygon(surf, C_PAC, pts)


def draw_preview_overlay(surf, font_big, font_small, gw, gh, seconds_left):
    """Semi-transparent overlay on top of the level during the preview phase."""
    overlay = pygame.Surface((gw, gh), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 90))
    surf.blit(overlay, (0, 0))


    secs = math.ceil(seconds_left)
    # Countdown ring
    cx, cy = gw // 2, gh - 38
    r = 20
    frac = max(0.0, seconds_left / 20.0)
    pygame.draw.circle(surf, C_LABEL, (cx, cy), r, 3)
    if frac > 0:
        arc_rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
        pygame.draw.arc(surf, C_PAC, arc_rect,
                        math.pi / 2, math.pi / 2 + frac * 2 * math.pi, 3)
    num = font_small.render(str(secs), True, C_WHITE)
    surf.blit(num, (cx - num.get_width() // 2, cy - num.get_height() // 2))


def _measure_wager_preview_legend(font_big, font_small, lvl):
    """Compute the required content height of the wager preview legend."""
    PAD = 14
    bh  = font_big.get_height()
    sh  = font_small.get_height()

    h = PAD
    # ELEMENTS header
    h += bh + 8
    entries = [
        ("Pac-Man",      "You — arrow keys"),
        ("Ghost",        "Lethal"),
        ("Teleporter",   "Step on → teleport"),
        ("Power-up",     "Ghost turns scared"),
        ("Pushable box", "Push by walking into it"),
        ("Red wall",     "Blocks movement"),
    ]
    for _, desc in entries:
        h += sh + 2
        h += (sh + 6) if desc else 4
    h += 6
    # GHOST PATH header
    h += bh + 8
    ghost = lvl.get("ghost")
    if ghost:
        h += bh + 4
        if ghost.get("type") == "patrol":
            h += sh + 4
        h += sh + 10
    # GOALS header
    h += bh + 8
    goal_lines = []
    if any(g["type"] == "banana" for g in lvl.get("goals", [])):
        goal_lines.append(True)
    if lvl.get("require_ghost_eaten"):
        goal_lines.append(True)
    h += len(goal_lines) * (sh + 6)
    h += PAD
    return h


def draw_wager_preview_legend(surf, font_big, font_small, lvl, x, available_y, w, available_h):
    """Legend + ghost path for the wager preview phase, left of the grid.
    Height is determined by the content; the box is centred vertically."""
    PAD = 14
    bh  = font_big.get_height()
    sh  = font_small.get_height()

    content_h = _measure_wager_preview_legend(font_big, font_small, lvl)
    h = min(content_h, available_h)
    # Centre vertically in the available space
    y = available_y + max(0, (available_h - h) // 2)

    # Background with an outline
    pygame.draw.rect(surf, (20, 20, 45), pygame.Rect(x, y, w, h), border_radius=8)
    pygame.draw.rect(surf, C_BORDER,     pygame.Rect(x, y, w, h), 2, border_radius=8)

    # Clip so text never runs outside the box
    old_clip = surf.get_clip()
    surf.set_clip(pygame.Rect(x, y, w, h))

    def _section(label, cy):
        s = font_big.render(label, True, (200, 200, 255))
        surf.blit(s, (x + PAD, cy))
        return cy + bh + 8

    def _entry(dot_col, label, desc, cy):
        pygame.draw.circle(surf, dot_col, (x + PAD + 5, cy + sh // 2), 5)
        name_s = font_small.render(label, True, (220, 220, 220))
        surf.blit(name_s, (x + PAD + 14, cy))
        cy += sh + 2
        if desc:
            desc_s = font_small.render(desc, True, (150, 160, 170))
            surf.blit(desc_s, (x + PAD + 14, cy))
            cy += sh + 6
        else:
            cy += 4
        return cy

    cy = y + PAD
    cy = _section("ELEMENTS", cy)

    entries = [
        (C_PAC,        "Pac-Man",      "You — arrow keys"),
        (C_GHOST,      "Ghost",        "Lethal"),
        ((46,37,133),  "Teleporter",   "Step on → teleport"),
        (C_LIGHTNING,  "Power-up",     "Ghost turns scared"),
        ((160,100,60), "Pushable box", "Push by walking into it"),
        ((194,106,119),"Red wall",     "Blocks movement"),
    ]
    for dot_col, label, desc in entries:
        cy = _entry(dot_col, label, desc, cy)

    cy += 6
    cy = _section("GHOST PATH", cy)

    ghost = lvl.get("ghost")
    if ghost:
        col_names = "ABCDEFGHIJKL"
        if ghost.get("type") == "patrol":
            wps = ghost["waypoints"]
            start = wps[0]
            end_idx = len(wps) // 2
            end = wps[end_idx]
            path_str  = f"{col_names[start[0]]}{start[1]+1}  <-->  {col_names[end[0]]}{end[1]+1}"
            path_str2 = "(L-shaped route)"
        else:
            path_str2 = None
            axis = ghost.get("axis", "h")
            if axis == "h":
                c1 = ghost.get("min_col", ghost["col"])
                c2 = ghost.get("max_col", ghost["col"])
                row = ghost["row"] + 1
                path_str = f"{col_names[c1]}{row}  <->  {col_names[c2]}{row}"
            else:
                r1 = ghost.get("min_row", ghost["row"])
                r2 = ghost.get("max_row", ghost["row"])
                col = ghost["col"]
                path_str = f"{col_names[col]}{r1+1}  <->  {col_names[col]}{r2+1}"
        ps = font_big.render(path_str, True, C_GHOST)
        surf.blit(ps, (x + PAD, cy))
        cy += bh + 4
        if path_str2:
            ps2 = font_small.render(path_str2, True, (150, 160, 170))
            surf.blit(ps2, (x + PAD, cy))
            cy += sh + 4
        note = font_small.render("Moves after you each turn", True, (150, 160, 170))
        surf.blit(note, (x + PAD, cy))
        cy += sh + 10

    cy = _section("GOALS", cy)
    goal_lines = []
    if any(g["type"] == "banana" for g in lvl.get("goals", [])):
        goal_lines.append("Collect all bananas")
    if lvl.get("require_ghost_eaten"):
        goal_lines.append("Eat all ghosts")
    for goal_line in goal_lines:
        gs = font_small.render(f"• {goal_line}", True, (220, 220, 100))
        surf.blit(gs, (x + PAD, cy))
        cy += sh + 6

    surf.set_clip(old_clip)


def draw_wager_screen(surf, font_big, font_small, w, h, t,
                      base_moves, slider_pos, max_buy, max_sell, move_price, coins):
    """Wagering screen: sliding bar to buy/sell moves for coins."""
    surf.fill(C_BG)
    cx = w // 2

    # ── Background stars ──────────────────────────────────────────────────────
    for i in range(20):
        sx = int((w * ((i * 173) % 100)) // 100)
        sy = int((h * ((i * 113) % 100)) // 100)
        sr = int(1 + 2 * math.sin(t * 1.2 + i))
        pygame.draw.circle(surf, C_GRID, (sx, sy), sr)

    # ── Title ─────────────────────────────────────────────────────────────────
    title = font_big.render("PLACE YOUR BET", True, C_PAC)
    surf.blit(title, (cx - title.get_width() // 2, int(h * 0.07)))
    sub = font_small.render("Adjust your moves before playing — no second chances!", True, C_LABEL)
    surf.blit(sub, (cx - sub.get_width() // 2, int(h * 0.07) + 34))

    # ── Coin balance ──────────────────────────────────────────────────────────
    current_moves = base_moves + slider_pos
    coins_after   = coins - slider_pos * move_price

    bal_y = int(h * 0.22)
    coin_color = C_WIN if coins_after >= 0 else C_LOSE
    bal_box = pygame.Rect(cx - 180, bal_y, 360, 64)
    pygame.draw.rect(surf, (20, 30, 60), bal_box, border_radius=10)
    pygame.draw.rect(surf, C_BORDER, bal_box, 2, border_radius=10)

    bal_lbl = font_small.render("COIN BALANCE", True, C_LABEL)
    surf.blit(bal_lbl, (cx - bal_lbl.get_width() // 2, bal_y + 8))

    coin_pulse = int(200 + 55 * math.sin(t * 4))
    coin_txt = font_big.render(f"{coins_after}", True, (coin_pulse, coin_pulse, 0))
    surf.blit(coin_txt, (cx - coin_txt.get_width() // 2, bal_y + 28))

    # ── Move count display ────────────────────────────────────────────────────
    mv_y = int(h * 0.42)
    mv_box = pygame.Rect(cx - 120, mv_y, 240, 56)
    pygame.draw.rect(surf, (20, 30, 60), mv_box, border_radius=10)
    pygame.draw.rect(surf, C_BORDER, mv_box, 2, border_radius=10)
    mv_lbl = font_small.render("MOVES", True, C_LABEL)
    surf.blit(mv_lbl, (cx - mv_lbl.get_width() // 2, mv_y + 6))
    mv_clr = C_MOVE_OK if slider_pos >= 0 else C_MOVE_WARN
    mv_txt = font_big.render(str(current_moves), True, mv_clr)
    surf.blit(mv_txt, (cx - mv_txt.get_width() // 2, mv_y + 24))

    # ── Slider ────────────────────────────────────────────────────────────────
    sl_y     = int(h * 0.62)
    sl_w     = min(600, int(w * 0.75))
    sl_x0    = cx - sl_w // 2
    sl_x1    = cx + sl_w // 2
    total_positions = max_buy + max_sell   # total notches each side
    notch_count = max_buy + max_sell       # number of non-center notches on each side

    # Track bar
    pygame.draw.rect(surf, (30, 40, 70),
                     pygame.Rect(sl_x0, sl_y - 6, sl_w, 12), border_radius=6)

    # Colored fill: left = sell (warn), right = buy (ok)
    if slider_pos < 0:
        fill_x = cx + slider_pos * (sl_w // 2) // max(max_sell, 1)
        fill_w = cx - fill_x
        pygame.draw.rect(surf, C_MOVE_WARN,
                         pygame.Rect(fill_x, sl_y - 4, fill_w, 8), border_radius=4)
    elif slider_pos > 0:
        fill_x = cx
        fill_w = slider_pos * (sl_w // 2) // max(max_buy, 1)
        pygame.draw.rect(surf, C_MOVE_OK,
                         pygame.Rect(fill_x, sl_y - 4, fill_w, 8), border_radius=4)

    # Notch marks
    for n in range(-max_sell, max_buy + 1):
        nx = cx + n * (sl_w // 2) // max(max(max_sell, max_buy), 1)
        nh = 14 if n == 0 else 8
        nc = C_WHITE if n == 0 else C_LABEL
        pygame.draw.line(surf, nc, (nx, sl_y - nh), (nx, sl_y + nh), 2 if n == 0 else 1)
        # Label at extremes and center
        if n in (-max_sell, 0, max_buy):
            lbl = font_small.render(str(n), True, nc)
            surf.blit(lbl, (nx - lbl.get_width() // 2, sl_y + 20))

    # Slider thumb (diamond)
    thumb_x = cx + slider_pos * (sl_w // 2) // max(max(max_sell, max_buy), 1)
    diamond_size = 14
    ds = diamond_size
    diamond_pts = [
        (thumb_x,      sl_y - ds),
        (thumb_x + ds, sl_y),
        (thumb_x,      sl_y + ds),
        (thumb_x - ds, sl_y),
    ]
    thumb_col = C_MOVE_WARN if slider_pos < 0 else (C_MOVE_OK if slider_pos > 0 else C_PAC)
    pulse_surf = pygame.Surface((ds*4, ds*4), pygame.SRCALPHA)
    pygame.draw.circle(pulse_surf, (*thumb_col, int(60 + 40 * math.sin(t * 5))),
                       (ds*2, ds*2), ds*2)
    surf.blit(pulse_surf, (thumb_x - ds*2, sl_y - ds*2))
    pygame.draw.polygon(surf, thumb_col, diamond_pts)
    pygame.draw.polygon(surf, C_WHITE, diamond_pts, 2)

    # Sell / Buy labels at ends — sell gives coins, buy costs coins
    sell_lbl = font_small.render(f"SELL  (+{move_price} coins/move)", True, C_MOVE_WARN)
    buy_lbl  = font_small.render(f"BUY  (-{move_price} coins/move)", True, C_MOVE_OK)
    surf.blit(sell_lbl, (sl_x0, sl_y - 44))
    surf.blit(buy_lbl,  (sl_x1 - buy_lbl.get_width(), sl_y - 44))

    # Delta annotation near thumb
    if slider_pos != 0:
        sign = "+" if slider_pos > 0 else ""
        delta_move = font_small.render(f"{sign}{slider_pos} moves", True, thumb_col)
        # Buying costs coins (orange), selling earns coins (green)
        coin_delta = -slider_pos * move_price
        coin_sign  = "+" if coin_delta >= 0 else ""
        delta_coin_col = C_MOVE_WARN if slider_pos > 0 else C_WIN
        delta_coin = font_small.render(f"{coin_sign}{coin_delta} coins", True, delta_coin_col)
        surf.blit(delta_move, (thumb_x - delta_move.get_width() // 2, sl_y - 72))
        surf.blit(delta_coin, (thumb_x - delta_coin.get_width() // 2, sl_y - 52))

    # ── Controls hint ─────────────────────────────────────────────────────────
    hint_y = int(h * 0.86)
    pygame.draw.line(surf, C_GRID, (cx - 300, hint_y - 14), (cx + 300, hint_y - 14), 1)
    hint1 = font_small.render("← →  adjust moves", True, C_LABEL)
    surf.blit(hint1, (cx - hint1.get_width() // 2, hint_y))
    blink = int(200 + 55 * math.sin(t * 3))
    hint2 = font_small.render("PRESS SPACE TO START PLAYING", True, (blink, blink, blink))
    surf.blit(hint2, (cx - hint2.get_width() // 2, hint_y + 22))


def draw_game_over(surf, font_large, font_big, font_small, reason, win_w, win_h, fails=0, max_fails=3, wager=False):
    overlay = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 185))
    surf.blit(overlay, (0, 0))
    cx = win_w // 2
    msg = font_large.render("GAME OVER", True, C_LOSE)
    surf.blit(msg, (cx - msg.get_width()//2, win_h//2 - 80))
    sub = font_big.render(reason, True, C_WHITE)
    surf.blit(sub, (cx - sub.get_width()//2, win_h//2 - 10))
    if wager:
        hint = font_big.render("Press R to continue to the next level", True, (255, 140, 60))
    else:
        attempt_txt = font_big.render(f"Attempt {fails} of {max_fails}", True, C_LABEL)
        surf.blit(attempt_txt, (cx - attempt_txt.get_width()//2, win_h//2 + 30))
        if fails >= max_fails:
            hint = font_big.render("No attempts left — Press R to continue", True, (255, 140, 60))
        else:
            hint = font_big.render("Press R to try again", True, C_LABEL)
    surf.blit(hint, (cx - hint.get_width()//2, win_h//2 + 70))


def draw_leaderboard(surf, font_big, font_small, w, h, t, stats, name, name_confirmed,
                     lb_entries=None):
    """Leaderboard screen shown after all levels are done."""
    surf.fill(C_BG)
    cx = w // 2

    # Background stars
    for i in range(30):
        sx = int((w * ((i * 137) % 100)) // 100)
        sy = int((h * ((i *  97) % 100)) // 100)
        sr = int(2 + 2 * math.sin(t * 1.5 + i))
        pygame.draw.circle(surf, C_GRID, (sx, sy), sr)

    y = int(h * 0.08)
    title = font_big.render("LEADERBOARD", True, C_WIN)
    surf.blit(title, (cx - title.get_width() // 2, y))
    y += title.get_height() + 20

    pygame.draw.line(surf, C_GRID, (cx - 320, y), (cx + 320, y), 2)
    y += 20

    # Player name
    name_label = font_small.render("PLAYER:", True, C_LABEL)
    surf.blit(name_label, (cx - 280, y))
    display_name = name if name_confirmed else (name + ("_" if int(t * 2) % 2 == 0 else ""))
    name_val = font_big.render(display_name or "___", True, C_PAC)
    surf.blit(name_val, (cx - 280 + name_label.get_width() + 14, y - 2))
    y += max(name_label.get_height(), name_val.get_height()) + 30

    pygame.draw.line(surf, C_GRID, (cx - 320, y), (cx + 320, y), 1)
    y += 20

    # Stats
    first_try    = stats.get("first_try", 0)
    total_levels = stats.get("total_levels", 0)
    total_moves  = stats.get("total_moves", 0)
    total_time_s = stats.get("total_time_s", 0)
    _tm = int(total_time_s)
    time_str = f"{_tm // 60}m {_tm % 60}s"

    rows = [
        ("Levels first try:",  f"{first_try} / {total_levels}"),
        ("Total moves used:",  f"{total_moves}"),
        ("Total time:",        time_str),
    ]
    for label, value in rows:
        lbl_s = font_small.render(label, True, C_LABEL)
        val_s = font_big.render(value, True, C_WHITE)
        surf.blit(lbl_s, (cx - 280, y))
        surf.blit(val_s, (cx - 280 + lbl_s.get_width() + 16, y - 2))
        y += max(lbl_s.get_height(), val_s.get_height()) + 16

    y += 20
    pygame.draw.line(surf, C_GRID, (cx - 320, y), (cx + 320, y), 1)
    y += 24

    if not name_confirmed:
        hint = font_small.render("Type your name and press ENTER to confirm", True, (180, 180, 220))
        surf.blit(hint, (cx - hint.get_width() // 2, y))
    else:
        blink = int(200 + 55 * math.sin(t * 3))
        hint = font_small.render("PRESS ANY KEY TO CONTINUE TO LEVEL 4", True, (blink, blink, blink))
        surf.blit(hint, (cx - hint.get_width() // 2, y))
        sub2 = font_small.render("(or ESC to quit)", True, (120, 120, 140))
        surf.blit(sub2, (cx - sub2.get_width() // 2, y + font_small.get_height() + 6))

    # ── Historische top-5 ──────────────────────────────────────────────────────
    if lb_entries:
        y += 44
        pygame.draw.line(surf, C_GRID, (cx - 320, y), (cx + 320, y), 1)
        y += 16
        top_lbl = font_small.render("ALL TIME TOP SCORES", True, C_LABEL)
        surf.blit(top_lbl, (cx - top_lbl.get_width() // 2, y))
        y += top_lbl.get_height() + 12

        # Table columns: x position of each column
        col_rank  = cx - 300
        col_name  = cx - 260
        col_ft    = cx +  30
        col_moves = cx + 130
        col_time  = cx + 220

        # Kopteksten
        C_HDR = C_LABEL
        surf.blit(font_small.render("#",          True, C_HDR), (col_rank,  y))
        surf.blit(font_small.render("Name",       True, C_HDR), (col_name,  y))
        surf.blit(font_small.render("First try",  True, C_HDR), (col_ft,    y))
        surf.blit(font_small.render("Moves",      True, C_HDR), (col_moves, y))
        surf.blit(font_small.render("Time",       True, C_HDR), (col_time,  y))
        y += font_small.get_height() + 4
        pygame.draw.line(surf, C_GRID, (cx - 300, y), (cx + 300, y), 1)
        y += 8

        medal_colors = [(255, 215, 0), (192, 192, 192), (205, 127, 50)]
        row_h = font_big.get_height() + 6
        for rank, entry in enumerate(lb_entries[:5]):
            col_r  = medal_colors[rank] if rank < 3 else C_WHITE
            tl     = entry.get("total_levels", 0)
            ft     = entry.get("first_try", 0)
            ts     = int(entry.get("total_time_s", 0))
            surf.blit(font_small.render(f"#{rank + 1}",                        True, col_r),           (col_rank,  y + 2))
            surf.blit(font_big.render(entry.get("name", "?"),                  True, col_r),           (col_name,  y - 1))
            surf.blit(font_small.render(f"{ft} / {tl}",                        True, (160, 220, 160)), (col_ft,    y + 2))
            surf.blit(font_small.render(f"{entry.get('total_moves', '?')}",    True, C_WHITE),         (col_moves, y + 2))
            surf.blit(font_small.render(f"{ts // 60}m {ts % 60:02d}s",         True, (180, 180, 255)), (col_time,  y + 2))
            y += row_h


def draw_wager_leaderboard(surf, font_big, font_small, w, h, t, total_coins, lb_entries):
    """Leaderboard after the wager game: sorted by total coins."""
    surf.fill(C_BG)
    cx = w // 2

    for i in range(30):
        sx = int((w * ((i * 137) % 100)) // 100)
        sy = int((h * ((i *  97) % 100)) // 100)
        sr = int(2 + 2 * math.sin(t * 1.5 + i))
        pygame.draw.circle(surf, C_GRID, (sx, sy), sr)

    y = int(h * 0.08)
    title = font_big.render("BONUS ROUND LEADERBOARD", True, C_WIN)
    surf.blit(title, (cx - title.get_width() // 2, y))
    y += title.get_height() + 8
    sub = font_small.render("Total coins across levels 4A, 4B, 4C and 4D", True, C_LABEL)
    surf.blit(sub, (cx - sub.get_width() // 2, y))
    y += sub.get_height() + 20

    pygame.draw.line(surf, C_GRID, (cx - 340, y), (cx + 340, y), 2)
    y += 18

    # Jouw score
    pulse = int(180 + 75 * abs(math.sin(t * 3)))
    your_lbl = font_small.render("YOUR SCORE:", True, C_LABEL)
    surf.blit(your_lbl, (cx - 200, y))
    your_val = font_big.render(f"{total_coins} coins", True, (pulse, pulse, 0))
    surf.blit(your_val, (cx - 200 + your_lbl.get_width() + 12, y - 4))
    y += your_val.get_height() + 18

    pygame.draw.line(surf, C_GRID, (cx - 340, y), (cx + 340, y), 1)
    y += 16

    # Top scores
    hdr = font_small.render("ALL TIME TOP SCORES", True, C_LABEL)
    surf.blit(hdr, (cx - hdr.get_width() // 2, y))
    y += hdr.get_height() + 10

    col_rank  = cx - 300
    col_name  = cx - 250
    col_coins = cx + 80
    row_h     = font_small.get_height() + 8

    for rank, entry in enumerate(lb_entries[:8]):
        clr = C_WIN if rank == 0 else (C_PAC if rank == 1 else C_WHITE)
        rank_s  = font_small.render(f"{rank+1}.", True, clr)
        name_s  = font_small.render(entry.get("name", "?"), True, clr)
        coins_s = font_small.render(f"{entry.get('total_wager_coins', 0)} coins", True, clr)
        surf.blit(rank_s,  (col_rank,  y))
        surf.blit(name_s,  (col_name,  y))
        surf.blit(coins_s, (col_coins, y))
        y += row_h

    pygame.draw.line(surf, C_GRID, (cx - 340, y + 4), (cx + 340, y + 4), 1)

    blink = int(200 + 55 * math.sin(t * 3))
    hint = font_small.render("PRESS ANY KEY TO CONTINUE", True, (blink, blink, blink))
    surf.blit(hint, (cx - hint.get_width() // 2, int(h * 0.90)))


def draw_wager_intro(surf, font_big, font_small, w, h, t):
    """Explanation screen for the wager game (Level 4)."""
    surf.fill(C_BG)
    cx = w // 2

    for i in range(20):
        sx = int((w * ((i * 173) % 100)) // 100)
        sy = int((h * ((i * 113) % 100)) // 100)
        sr = int(1 + 2 * math.sin(t * 1.2 + i))
        pygame.draw.circle(surf, C_GRID, (sx, sy), sr)

    y = int(h * 0.07)
    title = font_big.render("LEVEL 4  —  WAGERING GAME", True, C_PAC)
    surf.blit(title, (cx - title.get_width() // 2, y))
    y += title.get_height() + 10
    sub = font_small.render("A new kind of challenge", True, C_LABEL)
    surf.blit(sub, (cx - sub.get_width() // 2, y))
    y += sub.get_height() + 20
    pygame.draw.line(surf, C_GRID, (cx - 360, y), (cx + 360, y), 2)
    y += 24

    lines = [
        ("HOW IT WORKS", True),
        ("", False),
        ("You will now play TWO wager levels: 4A and 4B.", False),
        ("", False),
        ("Before each level you get a short preview of the grid.", False),
        ("Study the layout carefully — use this time to plan your route.", False),
        ("", False),
        ("COINS", True),
        ("", False),
        ("Each wager level starts with 100 coins.", False),
        ("Before playing you can BUY extra moves or SELL moves for coins.", False),
        ("Each move costs or earns you 5 coins.", False),
        ("", False),
        ("BUYING moves  →  more room to solve the puzzle, but costs coins.", False),
        ("SELLING moves →  earn coins, but you'll have fewer moves to solve it.", False),
        ("", False),
        ("Complete the level  →  keep all your remaining coins.", False),
        ("Fail the level      →  lose all coins from that level (previous levels kept).", False),
        ("", False),
        ("Use LEFT / RIGHT arrow keys to adjust your wager.", False),
        ("Press SPACE to confirm and start playing.", False),
    ]

    bh = font_big.get_height()
    sh = font_small.get_height()
    for text, is_header in lines:
        if not text:
            y += sh // 2
            continue
        if is_header:
            s = font_big.render(text, True, C_WIN)
            surf.blit(s, (cx - s.get_width() // 2, y))
            y += bh + 6
        else:
            s = font_small.render(text, True, C_WHITE)
            surf.blit(s, (cx - s.get_width() // 2, y))
            y += sh + 6

    y += 20
    pygame.draw.line(surf, C_GRID, (cx - 360, y), (cx + 360, y), 1)
    y += 20
    blink = int(200 + 55 * math.sin(t * 3))
    hint = font_small.render("PRESS ANY KEY TO START LEVEL 4A", True, (blink, blink, blink))
    surf.blit(hint, (cx - hint.get_width() // 2, y))


def draw_estimate_screen(surf, font_big, font_small, w, h, t,
                         moves_used, optimal_moves, selected, coins):
    """Screen shown after completing an estimate level."""
    surf.fill(C_BG)
    cx = w // 2

    for i in range(20):
        sx = int((w * ((i * 173) % 100)) // 100)
        sy = int((h * ((i * 113) % 100)) // 100)
        sr = int(1 + 2 * math.sin(t * 1.2 + i))
        pygame.draw.circle(surf, C_GRID, (sx, sy), sr)

    y = int(h * 0.07)
    title = font_big.render("HOW CLOSE WERE YOU?", True, C_PAC)
    surf.blit(title, (cx - title.get_width() // 2, y))
    y += title.get_height() + 14

    sub = font_small.render(f"You used  {moves_used}  moves", True, C_WHITE)
    surf.blit(sub, (cx - sub.get_width() // 2, y))
    y += sub.get_height() + 6
    hint = font_small.render("How many moves off from optimal were you?", True, C_LABEL)
    surf.blit(hint, (cx - hint.get_width() // 2, y))
    y += hint.get_height() + 30

    pygame.draw.line(surf, C_GRID, (cx - 360, y), (cx + 360, y), 1)
    y += 20

    btn_w, btn_h, gap = 160, 64, 20
    total_w = 6 * btn_w + 5 * gap
    bx = cx - total_w // 2

    for i, (lo, hi, label, reward) in enumerate(ESTIMATE_RANGES):
        rect = pygame.Rect(bx + i * (btn_w + gap), y, btn_w, btn_h)
        is_sel = (selected == i)
        bg_col = (50, 90, 140) if is_sel else (20, 30, 60)
        border_col = C_PAC if is_sel else C_BORDER
        pygame.draw.rect(surf, bg_col, rect, border_radius=10)
        pygame.draw.rect(surf, border_col, rect, 2, border_radius=10)
        lbl = font_big.render(label, True, C_WHITE if is_sel else C_LABEL)
        surf.blit(lbl, (rect.centerx - lbl.get_width() // 2, rect.y + 10))
        rew = font_small.render(reward, True,
              (100, 220, 100) if "+" in reward else
              (220, 100, 100) if "-" in reward else C_LABEL)
        surf.blit(rew, (rect.centerx - rew.get_width() // 2, rect.y + 40))

    y += btn_h + 40
    coin_s = font_small.render(f"Coins: {coins}", True, (220, 200, 50))
    surf.blit(coin_s, (cx - coin_s.get_width() // 2, y))
    y += coin_s.get_height() + 16

    if selected is not None:
        blink = int(200 + 55 * math.sin(t * 3))
        confirm = font_small.render("PRESS SPACE TO CONFIRM", True, (blink, blink, blink))
        surf.blit(confirm, (cx - confirm.get_width() // 2, y))
    else:
        nav = font_small.render("Use LEFT / RIGHT to choose your estimate", True, C_LABEL)
        surf.blit(nav, (cx - nav.get_width() // 2, y))


def draw_estimate_result(surf, font_big, font_small, w, h, t, info):
    """Screen shown right after confirming the estimate guess, before coin_result."""
    surf.fill(C_BG)
    cx = w // 2

    for i in range(20):
        sx = int((w * ((i * 173) % 100)) // 100)
        sy = int((h * ((i * 113) % 100)) // 100)
        sr = int(1 + 2 * math.sin(t * 1.2 + i))
        pygame.draw.circle(surf, C_GRID, (sx, sy), sr)

    correct       = info.get("guess_correct", False)
    gap_actual    = info.get("gap_actual", 0)
    moves_used    = info.get("moves_used", 0)
    optimal       = info.get("optimal_moves", 0)
    guess_label   = info.get("guess_label", "")
    gap_reward    = info.get("gap_reward", 0)
    bonus         = info.get("guess_bonus", 0)
    total_reward  = info.get("total_coin_reward", 0)

    y = int(h * 0.08)

    # Header
    header_txt = "CORRECT!" if correct else "NOT QUITE!"
    header_col = C_WIN if correct else C_LOSE
    header = font_big.render(header_txt, True, header_col)
    surf.blit(header, (cx - header.get_width() // 2, y))
    y += header.get_height() + 24

    pygame.draw.line(surf, C_GRID, (cx - 320, y), (cx + 320, y), 1)
    y += 18

    # Moves breakdown
    row_y = y
    used_lbl = font_small.render(f"Your moves:     {moves_used}", True, C_WHITE)
    surf.blit(used_lbl, (cx - used_lbl.get_width() // 2, row_y))
    row_y += used_lbl.get_height() + 8
    opt_lbl  = font_small.render(f"Optimal moves:  {optimal}", True, C_WHITE)
    surf.blit(opt_lbl, (cx - opt_lbl.get_width() // 2, row_y))
    row_y += opt_lbl.get_height() + 8
    gap_col  = C_WIN if gap_actual == 0 else C_LABEL
    gap_lbl  = font_small.render(f"Actual gap:     {gap_actual}", True, gap_col)
    surf.blit(gap_lbl, (cx - gap_lbl.get_width() // 2, row_y))
    row_y += gap_lbl.get_height() + 8
    guess_lbl = font_small.render(f"Your guess:     {guess_label}", True,
                                  C_WIN if correct else C_LOSE)
    surf.blit(guess_lbl, (cx - guess_lbl.get_width() // 2, row_y))
    row_y += guess_lbl.get_height() + 22

    pygame.draw.line(surf, C_GRID, (cx - 320, row_y), (cx + 320, row_y), 1)
    row_y += 18

    # Coins breakdown
    pulse = int(180 + 75 * abs(math.sin(t * 3)))
    gap_r_lbl = font_small.render(f"Gap reward:   +{gap_reward} coins", True,
                                  (pulse, pulse, 0) if gap_reward > 0 else C_LABEL)
    surf.blit(gap_r_lbl, (cx - gap_r_lbl.get_width() // 2, row_y))
    row_y += gap_r_lbl.get_height() + 8
    if correct:
        bon_lbl = font_small.render(f"Guess bonus:  +{bonus} coins", True, C_WIN)
        surf.blit(bon_lbl, (cx - bon_lbl.get_width() // 2, row_y))
        row_y += bon_lbl.get_height() + 8
    else:
        no_bon = font_small.render("Guess bonus:  +0 coins  (wrong range)", True, C_LABEL)
        surf.blit(no_bon, (cx - no_bon.get_width() // 2, row_y))
        row_y += no_bon.get_height() + 8
    total_s = font_big.render(f"Total: +{total_reward} coins", True,
                              (pulse, pulse, 0) if total_reward > 0 else C_LABEL)
    surf.blit(total_s, (cx - total_s.get_width() // 2, row_y))
    row_y += total_s.get_height() + 18

    # Hint
    blink = int(200 + 55 * math.sin(t * 3))
    hint = font_small.render("PRESS ANY KEY TO CONTINUE", True, (blink, blink, blink))
    surf.blit(hint, (cx - hint.get_width() // 2, int(h * 0.88)))


def draw_estimate_intro(surf, font_big, font_small, w, h, t):
    """Explanation screen for the estimate-type wager level (Level 4C)."""
    surf.fill(C_BG)
    cx = w // 2

    for i in range(20):
        sx = int((w * ((i * 173) % 100)) // 100)
        sy = int((h * ((i * 113) % 100)) // 100)
        sr = int(1 + 2 * math.sin(t * 1.2 + i))
        pygame.draw.circle(surf, C_GRID, (sx, sy), sr)

    y = int(h * 0.07)
    title = font_big.render("LEVEL 4C  —  ESTIMATE GAME", True, C_PAC)
    surf.blit(title, (cx - title.get_width() // 2, y))
    y += title.get_height() + 10
    sub = font_small.render("A new kind of challenge", True, C_LABEL)
    surf.blit(sub, (cx - sub.get_width() // 2, y))
    y += sub.get_height() + 20
    pygame.draw.line(surf, C_GRID, (cx - 360, y), (cx + 360, y), 2)
    y += 24

    lines = [
        ("HOW IT WORKS", True),
        ("", False),
        ("You will now play TWO estimate levels: 4C and 4D.", False),
        ("", False),
        ("There is no move limit — take as many moves as you need.", False),
        ("The counter at the bottom shows how many moves you have used so far.", False),
        ("", False),
        ("AFTER COMPLETING THE LEVEL", True),
        ("", False),
        ("You will see how many moves you used.", False),
        ("You then estimate how far off you were from the optimal (fewest possible) moves.", False),
        ("", False),
        ("Choose one of six ranges:", False),
        ("Exact  /  ±1  /  ±2  /  ±3  /  ±4  /  ±5 or more", False),
        ("", False),
        ("COINS", True),
        ("", False),
        ("Gap reward  (always earned, based on actual gap from optimal):", False),
        ("Exact=50   ±1=40   ±2=30   ±3=20   ±4=10   ±5+=0 coins", False),
        ("", False),
        ("Guess bonus  (only if your chosen range matches the actual gap):", False),
        ("+50 coins extra if your estimate was correct.", False),
        ("", False),
        ("Use LEFT / RIGHT arrow keys to choose your range.", False),
        ("Press SPACE to confirm.", False),
    ]

    bh = font_big.get_height()
    sh = font_small.get_height()
    for text, is_header in lines:
        if not text:
            y += sh // 2
            continue
        if is_header:
            s = font_big.render(text, True, C_WIN)
            surf.blit(s, (cx - s.get_width() // 2, y))
            y += bh + 6
        else:
            s = font_small.render(text, True, C_WHITE)
            surf.blit(s, (cx - s.get_width() // 2, y))
            y += sh + 6

    y += 20
    pygame.draw.line(surf, C_GRID, (cx - 360, y), (cx + 360, y), 1)
    y += 20
    blink = int(200 + 55 * math.sin(t * 3))
    hint = font_small.render("PRESS ANY KEY TO START LEVEL 4C", True, (blink, blink, blink))
    surf.blit(hint, (cx - hint.get_width() // 2, y))


def draw_coin_result(surf, font_big, font_small, w, h, t, info):
    """Interstitial after each wager level: coins earned + current balance."""
    surf.fill(C_BG)
    cx = w // 2

    for i in range(25):
        sx = int((w * ((i * 137) % 100)) // 100)
        sy = int((h * ((i *  97) % 100)) // 100)
        sr = int(1 + 2 * math.sin(t * 1.5 + i))
        pygame.draw.circle(surf, C_GRID, (sx, sy), sr)

    level_name  = info.get("level_name", "")
    coins_earned = info.get("coins_earned", 0)
    balance      = info.get("balance", 0)
    won          = info.get("won", True)

    # Title
    status_txt = "LEVEL COMPLETE" if won else "LEVEL FAILED"
    status_col = C_WIN if won else C_LOSE
    title = font_big.render(status_txt, True, status_col)
    surf.blit(title, (cx - title.get_width() // 2, int(h * 0.12)))
    lvl_s = font_small.render(level_name, True, C_LABEL)
    surf.blit(lvl_s, (cx - lvl_s.get_width() // 2, int(h * 0.12) + title.get_height() + 6))

    pygame.draw.line(surf, C_GRID, (cx - 260, int(h * 0.28)), (cx + 260, int(h * 0.28)), 2)

    # Coins earned this level
    cy = int(h * 0.33)
    lbl1 = font_small.render("COINS THIS LEVEL", True, C_LABEL)
    surf.blit(lbl1, (cx - lbl1.get_width() // 2, cy))
    cy += lbl1.get_height() + 6
    coin_col = C_WIN if coins_earned >= 0 else C_LOSE
    pulse = int(180 + 75 * abs(math.sin(t * 3)))
    earned_s = font_big.render(f"{'+' if coins_earned >= 0 else ''}{coins_earned}", True,
                               (pulse, pulse, 0) if coins_earned > 0 else coin_col)
    surf.blit(earned_s, (cx - earned_s.get_width() // 2, cy))

    pygame.draw.line(surf, C_GRID, (cx - 260, int(h * 0.56)), (cx + 260, int(h * 0.56)), 1)

    # Total balance
    cy = int(h * 0.60)
    lbl2 = font_small.render("TOTAL BALANCE", True, C_LABEL)
    surf.blit(lbl2, (cx - lbl2.get_width() // 2, cy))
    cy += lbl2.get_height() + 6
    bal_pulse = int(180 + 75 * abs(math.sin(t * 2.5 + 1)))
    bal_s = font_big.render(str(balance), True, (bal_pulse, bal_pulse, 0))
    surf.blit(bal_s, (cx - bal_s.get_width() // 2, cy))

    # Hint
    blink = int(200 + 55 * math.sin(t * 3))
    hint = font_small.render("PRESS ANY KEY TO CONTINUE", True, (blink, blink, blink))
    surf.blit(hint, (cx - hint.get_width() // 2, int(h * 0.84)))


def draw_end_screen(surf, font_big, font_small, w, h, t, stats, wager_lb_entries=None):
    """Credits / end screen shown after completing all levels."""
    surf.fill(C_BG)
    cx = w // 2

    for i in range(30):
        sx = int((w * ((i * 137) % 100)) // 100)
        sy = int((h * ((i *  97) % 100)) // 100)
        sr = int(2 + 2 * math.sin(t * 1.5 + i))
        pygame.draw.circle(surf, C_GRID, (sx, sy), sr)

    title = font_big.render("THANK YOU FOR PLAYING!", True, C_WIN)
    surf.blit(title, (cx - title.get_width() // 2, int(h * 0.38)))

    pr = 32
    pac_y = int(h * 0.55)
    mouth = abs(math.sin(t * 4)) * 38 + 4
    pts = [(cx, pac_y)]
    for i in range(41):
        a = math.radians(mouth + (360 - 2 * mouth) * i / 40)
        pts.append((cx + pr * math.cos(a), pac_y - pr * math.sin(a)))
    pygame.draw.polygon(surf, C_PAC, pts)
    pygame.draw.circle(surf, C_EYE,     (cx + 14, pac_y - 20), 6)
    pygame.draw.circle(surf, C_EYE_PUP, (cx + 16, pac_y - 18), 3)

    blink = int(200 + 55 * math.sin(t * 3))
    hint = font_small.render("PRESS ESCAPE TO QUIT", True, (blink, blink, blink))
    surf.blit(hint, (cx - hint.get_width() // 2, int(h * 0.72)))


# ─── Level legends for the play screen ───────────────────────────────────────
# Each entry: (color_RGB, label, description)
# Shown to the right of the grid when enough screen space is available.
LEVEL_LEGENDS = {
    "LEVEL 1A": {
        "entries": [
            ((220, 190,  50), "Banana",        "Collect ALL bananas to complete the level"),
        ],
        "goals": ["Eat all bananas"],
    },
    "LEVEL 1B": {
        "entries": [
            ((194, 106, 119), "Pink wall",     "Permanently blocks your movement"),
            ((148, 203, 236), "Patrol ghost",  "Moves back and forward across the indicated line — Lethal. Player moves first, ghost after."),
        ],
        "goals": ["Eat all bananas"],
    },
    "LEVEL 1C": {
        "entries": [
            ((194, 106, 119), "Pink wall",     "Permanently blocks your movement"),
            ((148, 203, 236), "Patrol ghost",  "Moves back and forward across the indicated line — Lethal. Player moves first, ghost after."),
            ((220, 205, 125), "Yellow gate",   "Pass through once in either direction — closes permanently after"),
        ],
        "goals": ["Eat all bananas"],
    },
    "LEVEL 1D": {
        "entries": [
            ((194, 106, 119), "Pink wall",     "Permanently blocks your movement"),
            ((148, 203, 236), "Patrol ghost",  "Moves back and forward across the indicated line — Lethal. Player moves first, ghost after."),
            ((220, 205, 125), "Yellow gate",   "Pass through once in either direction — closes permanently after"),
            (( 46,  37, 133), "Teleporter",    "Step on it → instantly jump to the other teleporter"),
        ],
        "goals": ["Eat all bananas"],
    },
    "LEVEL 1E": {
        "entries": [
            ((194, 106, 119), "Pink wall",     "Permanently blocks your movement"),
            ((148, 203, 236), "Patrol ghost",  "Moves back and forward across the indicated line — Lethal. Player moves first, ghost after."),
            ((220, 205, 125), "Yellow gate",   "Pass through once in either direction — closes permanently after"),
            (( 46,  37, 133), "Teleporter",    "Step on it → instantly jump to the other teleporter"),
            ((255, 230,  80), "Power-up", "Pick up → ghost turns scared for 6 moves"),
            ((148, 203, 236), "Scared ghost",  "Walk into it to eat it while it's scared"),
        ],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
    "LEVEL 1F": {
        "entries": [
            ((194, 106, 119), "Pink wall",     "Permanently blocks your movement"),
            ((148, 203, 236), "Patrol ghost",  "Moves back and forward across the indicated line — Lethal. Player moves first, ghost after."),
            ((220, 205, 125), "Yellow gate",   "Pass through once in either direction — closes permanently after"),
            (( 46,  37, 133), "Teleporter",    "Step on it → instantly jump to the other teleporter"),
            ((255, 230,  80), "Power-up", "Pick up → ghost turns scared for 6 moves"),
            ((160, 100,  60), "Pushable box",  "Walk into it to push it one step forward"),
        ],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
    # ── Serie 2 ───────────────────────────────────────────────────────────────
    # "known"      → serie-1 elementen, klein lettertype
    # "new_entries" → nieuw in dit level, normaal lettertype + beschrijving
    "LEVEL 2A": {
        "known": [
            ((220, 190,  50), "Banana"),
            ((194, 106, 119), "Pink wall"),
            ((220, 205, 125), "Yellow gate"),
            ((148, 203, 236), "Patrol ghost"),
            (( 46,  37, 133), "Teleporter"),
            ((255, 230,  80), "Power-up"),
            ((160, 100,  40), "Pushable box"),
        ],
        "new_entries": [],
        "entries": [],
        "meta_rule": ("Chasing ghost", (126, 41, 84),
            "Chases you directly — activates when you get in the pink area around it. "
            "Pauses every 5th move. You must eat it."),
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
    "LEVEL 2B": {
        "known": [
            ((220, 190,  50), "Banana"),
            ((194, 106, 119), "Pink wall"),
            ((220, 205, 125), "Yellow gate"),
            ((148, 203, 236), "Patrol ghost"),
            (( 46,  37, 133), "Teleporter"),
            ((255, 230,  80), "Power-up"),
            ((160, 100,  40), "Pushable box"),
        ],
        "new_entries": [],
        "entries": [],
        "meta_rules": [
            ("Chasing ghost", (126, 41, 84),
             "Chases you directly — activates when you get in the pink area around it. "
             "Pauses every 5th move. You must eat it."),
            ("Teal wall", (93, 168, 153),
             "You are able to walk through these walls."
             "The ghost can't walk through."),
        ],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
    "LEVEL 2C": {
        "known": [
            ((220, 190,  50), "Banana"),
            ((194, 106, 119), "Pink wall"),
            ((220, 205, 125), "Yellow gate"),
            ((148, 203, 236), "Patrol ghost"),
            (( 46,  37, 133), "Teleporter"),
            ((255, 230,  80), "Power-up"),
            ((160, 100,  40), "Pushable box"),
        ],
        "new_entries": [],
        "entries": [],
        "meta_rules": [
            ("Chasing ghost", (126, 41, 84),
             "Chases you directly — activates when you get in the pink area around it. "
             "Pauses every 5th move. You must eat it."),
            ("Teal wall", (93, 168, 153),
             "You are able to walk through these walls. "
             "The ghost can't walk through."),
            ("Delayed power-up", (255, 230, 80),
             "Power up activates 3 moves after you pick it up"),
        ],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
    "LEVEL 2D": {
        "known": [
            ((220, 190,  50), "Banana"),
            ((194, 106, 119), "Pink wall"),
            ((220, 205, 125), "Yellow gate"),
            ((148, 203, 236), "Patrol ghost"),
            (( 46,  37, 133), "Teleporter"),
            ((255, 230,  80), "Power-up"),
            ((160, 100,  40), "Pushable box"),
        ],
        "new_entries": [],
        "entries": [],
        "meta_rules": [
            ("Chasing ghost", (126, 41, 84),
             "Chases you directly — activates when you get in the pink area around it. "
             "Pauses every 5th move. You must eat it."),
            ("Teal wall", (93, 168, 153),
             "You are able to walk through these walls. "
             "The ghost can't walk through."),
            ("Delayed power-up", (255, 230, 80),
             "Power up activates 3 moves after you pick it up."),
            ("Shared teleporter", (51, 117, 56),
             "Both you AND the ghost use this teleporter. "),
        ],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
    "LEVEL 2E": {
        "known": [
            ((220, 190,  50), "Banana"),
            ((194, 106, 119), "Pink wall"),
            ((220, 205, 125), "Yellow gate"),
            ((148, 203, 236), "Patrol ghost"),
            (( 46,  37, 133), "Teleporter"),
            ((255, 230,  80), "Power-up"),
            ((160, 100,  40), "Pushable box"),
        ],
        "new_entries": [],
        "entries": [],
        "meta_rules": [
            ("Chasing ghost", (126, 41, 84),
             "Chases you directly — activates when you get in the pink area around it. "
             "Pauses every 5th move. You must eat it."),
            ("Teal wall", (93, 168, 153),
             "You are able to walk through these walls. "
             "The ghost can't walk through."),
            ("Delayed power-up", (255, 230, 80),
             "Power up activates 3 moves after you pick it up."),
            ("Shared teleporter", (51, 117, 56),
             "Both you AND the ghost use this teleporter."),
            ("Sliding meta-block", (93, 168, 153),
             "A teal block that slides when pushed — travels multiple cells "
             "until it hits a wall."),
        ],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
    "LEVEL 2F": {
        "known": [
            ((220, 190,  50), "Banana"),
            ((194, 106, 119), "Pink wall"),
            ((220, 205, 125), "Yellow gate"),
            ((148, 203, 236), "Patrol ghost"),
            (( 46,  37, 133), "Teleporter"),
            ((255, 230,  80), "Power-up"),
            ((160, 100,  40), "Pushable box"),
        ],
        "new_entries": [],
        "entries": [],
        "meta_rules": [
            ("Chasing ghost", (126, 41, 84),
             "Chases you directly — activates when you get in the pink area around it. "
             "Pauses every 5th move. You must eat it."),
            ("Teal wall", (93, 168, 153),
             "You are able to walk through these walls. "
             "The ghost can't walk through."),
            ("Delayed power-up", (255, 230, 80),
             "Power up activates 3 moves after you pick it up."),
            ("Shared teleporter", (51, 117, 56),
             "Both you AND the ghost use this teleporter."),
            ("Sliding meta-block", (93, 168, 153),
             "A teal block that slides when pushed — travels multiple cells "
             "until it hits a wall."),
        ],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },

    # ── Serie 3 ───────────────────────────────────────────────────────────────
    # No base components shown ("serie3": True skips that section).
    # "meta_rules" shown small/compact (name + color dot, no description).
    # "zone_rules" shown large with full description (cumulative per level).
    "LEVEL 3A": {
        "serie3": True,
        "meta_rules": [
            ("Chasing ghost",     (126,  41,  84), ""),
            ("Teal wall",         ( 93, 168, 153), ""),
            ("Delayed power-up",  (255, 230,  80), ""),
            ("Shared teleporter", ( 51, 117,  56), ""),
            ("Sliding meta-block",( 93, 168, 153), ""),
        ],
        "zone_rules": [
            ("Chasing ghost (zone)", (159, 74, 150),
             "Inside the purple zone: the chasing ghost switches to patrolling "
             "the zone border instead of chasing you."),
        ],
        "entries": [],
        "new_entries": [],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
    "LEVEL 3B": {
        "serie3": True,
        "meta_rules": [
            ("Chasing ghost",     (126,  41,  84), ""),
            ("Teal wall",         ( 93, 168, 153), ""),
            ("Delayed power-up",  (255, 230,  80), ""),
            ("Shared teleporter", ( 51, 117,  56), ""),
            ("Sliding meta-block",( 93, 168, 153), ""),
        ],
        "zone_rules": [
            ("Chasing ghost (zone)", (159, 74, 150),
             "Inside the purple zone: the chasing ghost switches to patrolling "
             "the zone border instead of chasing you."),
            ("Teal wall (zone)", (93, 168, 153),
             "Inside the zone: teal walls become one-shot "
             "after the player passes through once they shut."),
        ],
        "entries": [],
        "new_entries": [],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
    "LEVEL 3C": {
        "serie3": True,
        "meta_rules": [
            ("Chasing ghost",     (126,  41,  84), ""),
            ("Teal wall",         ( 93, 168, 153), ""),
            ("Delayed power-up",  (255, 230,  80), ""),
            ("Shared teleporter", ( 51, 117,  56), ""),
            ("Sliding meta-block",( 93, 168, 153), ""),
        ],
        "zone_rules": [
            ("Chasing ghost (zone)", (159, 74, 150),
             "Inside the purple zone: the chasing ghost switches to patrolling "
             "the zone border instead of chasing you."),
            ("Teal wall (zone)", (93, 168, 153),
             "Inside the zone: teal walls become one-shot "
             "after the player passes through once they shut."),
            ("Delayed PU (zone)", (255, 230, 80),
             "Inside the zone: the delayed power-up timer pauses — it resumes "
             "when you leave the zone."),
        ],
        "entries": [],
        "new_entries": [],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
    "LEVEL 3D": {
        "serie3": True,
        "meta_rules": [
            ("Chasing ghost",     (126,  41,  84), ""),
            ("Teal wall",         ( 93, 168, 153), ""),
            ("Delayed power-up",  (255, 230,  80), ""),
            ("Shared teleporter", ( 51, 117,  56), ""),
            ("Sliding meta-block",( 93, 168, 153), ""),
        ],
        "zone_rules": [
            ("Chasing ghost (zone)", (159, 74, 150),
             "Inside the purple zone: the chasing ghost switches to patrolling "
             "the zone border instead of chasing you."),
            ("Teal wall (zone)", (93, 168, 153),
             "Inside the zone: teal walls become one-shot "
             "after the player passes through once they shut."),
            ("Delayed PU (zone)", (255, 230, 80),
             "Inside the zone: the delayed power-up timer pauses — it resumes "
             "when you leave the zone."),
            ("Shared TP (zone)", (51, 117, 56),
             "You can enter the zone via the outside shared TP "
             "You can't leave the zone via the shared TP."),
        ],
        "entries": [],
        "new_entries": [],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
    "LEVEL 3E": {
        "serie3": True,
        "meta_rules": [
            ("Chasing ghost",     (126,  41,  84), ""),
            ("Teal wall",         ( 93, 168, 153), ""),
            ("Delayed power-up",  (255, 230,  80), ""),
            ("Shared teleporter", ( 51, 117,  56), ""),
            ("Sliding meta-block",( 93, 168, 153), ""),
        ],
        "zone_rules": [
            ("Chasing ghost (zone)", (159, 74, 150),
             "Inside the purple zone: the chasing ghost switches to patrolling "
             "the zone border instead of chasing you."),
            ("Teal wall (zone)", (93, 168, 153),
             "Inside the zone: teal walls become one-shot "
             "after the player passes through once they shut."),
            ("Delayed PU (zone)", (255, 230, 80),
             "Inside the zone: the delayed power-up timer pauses — it resumes "
             "when you leave the zone."),
            ("Shared TP (zone)", (51, 117, 56),
             "You can only enter the zone through the shared TP. You can't use it to exit"),
            ("Meta-block (zone)", (93, 168, 153),
             "The sliding meta-block breaks all walls it encounters in the zone"),
        ],
        "entries": [],
        "new_entries": [],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
    "LEVEL 3F": {
        "serie3": True,
        "meta_rules": [
            ("Chasing ghost",     (126,  41,  84), ""),
            ("Teal wall",         ( 93, 168, 153), ""),
            ("Delayed power-up",  (255, 230,  80), ""),
            ("Shared teleporter", ( 51, 117,  56), ""),
            ("Sliding meta-block",( 93, 168, 153), ""),
        ],
        "zone_rules": [
            ("Chasing ghost (zone)", (159, 74, 150),
             "Inside the purple zone: the chasing ghost switches to patrolling "
             "the zone border instead of chasing you."),
            ("Teal wall (zone)", (93, 168, 153),
             "Inside the zone: teal walls become one-shot "
             "after the player passes through once they shut."),
            ("Delayed PU (zone)", (255, 230, 80),
             "Inside the zone: the delayed power-up timer pauses — it resumes "
             "when you leave the zone."),
            ("Shared TP (zone)", (51, 117, 56),
             "Entering the zone via a shared teleporter immediately triggers "
             "the zone effect on the ghost."),
            ("Meta-block (zone)", (93, 168, 153),
             "If the sliding meta-block exits the zone, it breaks and disappears."),
        ],
        "entries": [],
        "new_entries": [],
        "goals": ["Eat all bananas", "Eat all ghosts"],
    },
}

# -- Implicit legend: per level, the elements introduced in PREVIOUS levels --
# Built from LEVEL_LEGENDS: colour + name only, no description.
def _build_implicit_legends():
    """Return dict title → list of (color, name, desc) tuples seen in all prior levels."""
    order = list(LEVEL_LEGENDS.keys())
    seen  = []   # cumulatief (color, name, desc) — geen dubbelen op naam
    result = {}
    for title in order:
        result[title] = list(seen)
        leg = LEVEL_LEGENDS[title]
        new = []
        for color, name, *rest in leg.get("entries", []):
            new.append((color, name, rest[0] if rest else ""))
        for color, name, *rest in leg.get("new_entries", []):
            new.append((color, name, rest[0] if rest else ""))
        for color, name in leg.get("known", []):
            new.append((color, name, ""))
        raw_meta = leg.get("meta_rules") or ([leg["meta_rule"]] if leg.get("meta_rule") else [])
        for name, color, *rest in raw_meta:
            new.append((color, name, rest[0] if rest else ""))
        for name, color, *rest in leg.get("zone_rules", []):
            new.append((color, name, rest[0] if rest else ""))
        seen_names = {n for _, n, _ in seen}
        for item in new:
            if item[1] not in seen_names:
                seen.append(item)
                seen_names.add(item[1])
    return result

IMPLICIT_LEGEND = _build_implicit_legends()

# Accent color per level — shown in the panel header bar
_LEGEND_ACCENT = {
    "LEVEL 1A": (220, 190,  50),
    "LEVEL 1B": (148, 203, 236),
    "LEVEL 1C": (220, 205, 125),
    "LEVEL 1D": ( 46,  37, 133),
    "LEVEL 1E": (255, 230,  80),
    "LEVEL 1F": (148, 203, 236),
    "LEVEL 2A": ( 93, 168, 153),
    "LEVEL 2B": ( 93, 168, 153),
    "LEVEL 2C": (255, 230,  80),
    "LEVEL 2D": ( 51, 117,  56),
    "LEVEL 2E": ( 93, 168, 153),
    "LEVEL 2F": ( 93, 168, 153),
    "LEVEL 3A": (159,  74, 150),
    "LEVEL 3B": (159,  74, 150),
    "LEVEL 3C": (159,  74, 150),
    "LEVEL 3D": (159,  74, 150),
    "LEVEL 3E": (159,  74, 150),
    "LEVEL 3F": (159,  74, 150),
}


def _render_wrapped(surf, font, text, color, x, y, max_w):
    """Render text, wrapping to a second line if it exceeds max_w. Returns new y."""
    r = font.render(text, True, color)
    if r.get_width() <= max_w:
        surf.blit(r, (x, y))
        return y + r.get_height()
    # Split at midpoint of words
    words = text.split()
    mid   = max(1, len(words) // 2)
    for part in (" ".join(words[:mid]), " ".join(words[mid:])):
        r2 = font.render(part, True, color)
        surf.blit(r2, (x, y))
        y += r2.get_height()
    return y


def _word_wrap_lines(font, text, max_w):
    """Return number of lines needed to wrap text at max_w pixels."""
    if not text:
        return 0
    words = text.split()
    line  = ""
    lines = 0
    for word in words:
        test = (line + " " + word).strip()
        if font.size(test)[0] <= max_w:
            line = test
        else:
            if line:
                lines += 1
            line = word
    if line:
        lines += 1
    return lines


# Master lookup: element name → (color, description) — built from serie-1 entries
_ELEMENT_DESC: dict = {}
def _build_element_desc():
    for leg in LEVEL_LEGENDS.values():
        for color, name, *rest in leg.get("entries", []):
            if name not in _ELEMENT_DESC and rest:
                _ELEMENT_DESC[name] = (color, rest[0])
        for color, name, *rest in leg.get("new_entries", []):
            if name not in _ELEMENT_DESC and rest:
                _ELEMENT_DESC[name] = (color, rest[0])
        raw_meta = leg.get("meta_rules") or ([leg["meta_rule"]] if leg.get("meta_rule") else [])
        for name, color, *rest in raw_meta:
            if name not in _ELEMENT_DESC and rest and rest[0]:
                _ELEMENT_DESC[name] = (color, rest[0])
        for name, color, *rest in leg.get("zone_rules", []):
            if name not in _ELEMENT_DESC and rest and rest[0]:
                _ELEMENT_DESC[name] = (color, rest[0])
_build_element_desc()


def _legend_all_entries(lvl_title):
    """Return ordered list of (color, name, desc) for all elements in a level's legend,
    with descriptions filled in from _ELEMENT_DESC where missing.
    For serie-3 levels the base rules come from IMPLICIT_LEGEND (cumulative prior levels)."""
    leg = LEVEL_LEGENDS.get(lvl_title)
    if not leg:
        return []
    seen  = set()
    result = []

    def _add(color, name, desc):
        if name in seen:
            return
        seen.add(name)
        if not desc:
            _, d = _ELEMENT_DESC.get(name, (color, ""))
            desc = d
        result.append((color, name, desc))

    if leg.get("serie3"):
        # Base rules: all elements seen up to and including the previous serie-2 level
        for color, name, desc in IMPLICIT_LEGEND.get(lvl_title, []):
            _add(color, name, desc)
    else:
        for color, name in leg.get("known", []):
            _add(color, name, "")
        for color, name, *rest in leg.get("entries", []):
            _add(color, name, rest[0] if rest else "")
        for color, name, *rest in leg.get("new_entries", []):
            _add(color, name, rest[0] if rest else "")

    raw_meta = leg.get("meta_rules") or ([leg["meta_rule"]] if leg.get("meta_rule") else [])
    for name, color, *rest in raw_meta:
        _add(color, name, rest[0] if rest else "")
    for name, color, *rest in leg.get("zone_rules", []):
        _add(color, name, rest[0] if rest else "")
    return result


def _legend_content_h(font_big, font_small, lvl_title, panel_w):
    """Calculate total scrollable content height for the legend panel."""
    legend = LEVEL_LEGENDS.get(lvl_title)
    if not legend:
        return 0
    PAD    = 14
    SB_W   = 6
    sh     = font_small.get_height()
    bh     = font_big.get_height()
    text_w = panel_w - PAD * 2 - 8 - SB_W
    section_h = 1 + 10 + bh + 6  # separator line + padding + header + gap

    entries = _legend_all_entries(lvl_title)
    h = 10  # top padding after panel header

    leg = legend
    has_base  = bool(leg.get("known") or leg.get("entries") or leg.get("new_entries")
                     or (leg.get("serie3") and IMPLICIT_LEGEND.get(lvl_title)))
    has_meta  = bool(leg.get("meta_rules") or leg.get("meta_rule"))
    has_zone  = bool(leg.get("zone_rules"))

    n_sections = sum([has_base, has_meta, has_zone])
    h += n_sections * section_h

    for _, _, desc in entries:
        h += bh + 4
        if desc:
            h += _word_wrap_lines(font_small, desc, text_w) * (sh + 2) + 4
        h += 10

    goals = legend.get("goals", [])
    h += 14 + 1 + 14 + bh + 8 + len(goals) * (sh + 6)
    h += 14 + 1 + 14 + bh + 8 + 4 * (sh + 8)
    return h


def _legend_panel_height(font_big, font_small, lvl_title, panel_w):
    """Height of the panel for level 1A–1F (cap used for scrolling in later levels)."""
    hdr_h = 36
    return hdr_h + _legend_content_h(font_big, font_small, lvl_title, panel_w)


def draw_legend_panel(surf, font_big, font_small, lvl_title, panel_x, panel_y, panel_w, panel_h,
                      scroll_offset=0):
    """Draws the legend panel with all elements (incl. descriptions) and scrollbar."""
    legend = LEVEL_LEGENDS.get(lvl_title)
    if not legend:
        return

    PAD    = 14
    SB_W   = 6
    hdr_h  = 36
    accent = _LEGEND_ACCENT.get(lvl_title, (160, 160, 220))
    text_x = panel_x + PAD + 8
    max_tw = panel_w - PAD * 2 - 8 - SB_W

    # ── Panel background ─────────────────────────────────────────────────────
    bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    bg.fill((10, 10, 32, 225))
    surf.blit(bg, (panel_x, panel_y))
    pygame.draw.rect(surf, (50, 50, 90),
                     pygame.Rect(panel_x, panel_y, panel_w, panel_h), 2, border_radius=10)

    # ── Header bar (always visible, not scrolled) ─────────────────────────────
    hdr_bg2 = pygame.Surface((panel_w, hdr_h), pygame.SRCALPHA)
    hdr_bg2.fill((*accent, 55))
    surf.blit(hdr_bg2, (panel_x, panel_y))
    pygame.draw.rect(surf, accent, pygame.Rect(panel_x, panel_y, 4, hdr_h),
                     border_top_left_radius=10)
    title_surf = font_big.render("Legend", True, (255, 255, 255))
    surf.blit(title_surf, (panel_x + PAD + 4, panel_y + (hdr_h - title_surf.get_height()) // 2))

    # ── Scrollable content area ───────────────────────────────────────────────
    content_h  = _legend_content_h(font_big, font_small, lvl_title, panel_w)
    scroll_area_h = panel_h - hdr_h
    max_scroll = max(0, content_h - scroll_area_h)
    scroll_offset = min(max(0, scroll_offset), max_scroll)

    clip_rect = pygame.Rect(panel_x, panel_y + hdr_h, panel_w - SB_W - 2, scroll_area_h)
    old_clip  = surf.get_clip()
    surf.set_clip(clip_rect)

    y = panel_y + hdr_h + 10 - scroll_offset
    sh = font_small.get_height()
    bh = font_big.get_height()

    def _draw_wrapped_desc(text, cy):
        words = text.split()
        line  = ""
        for word in words:
            test = (line + " " + word).strip()
            if font_small.size(test)[0] <= max_tw:
                line = test
            else:
                if line:
                    surf.blit(font_small.render(line, True, (175, 185, 210)), (text_x, cy))
                    cy += sh + 2
                line = word
        if line:
            surf.blit(font_small.render(line, True, (175, 185, 210)), (text_x, cy))
            cy += sh + 2
        return cy

    # ── Entries grouped by section ────────────────────────────────────────────
    def _draw_section_header(label, cy):
        pygame.draw.line(surf, (50, 50, 90),
                         (panel_x + PAD, cy), (panel_x + panel_w - PAD - SB_W, cy), 1)
        cy += 10
        surf.blit(font_big.render(label, True, (200, 200, 255)), (panel_x + PAD, cy))
        cy += bh + 6
        return cy

    def _draw_entry(color, label, desc, cy):
        pygame.draw.rect(surf, (*color, 200),
                         pygame.Rect(panel_x + 4, cy, 3, bh + 4), border_radius=2)
        lbl_surf = font_big.render(label, True, color)
        if lbl_surf.get_width() > max_tw:
            scale_f = max_tw / lbl_surf.get_width()
            lbl_surf = pygame.transform.smoothscale(
                lbl_surf, (max_tw, int(lbl_surf.get_height() * scale_f)))
        surf.blit(lbl_surf, (text_x, cy))
        cy += bh + 4
        if desc:
            cy = _draw_wrapped_desc(desc, cy)
            cy += 4
        cy += 10
        return cy

    leg = LEVEL_LEGENDS.get(lvl_title, {})

    # Fixed classification: which names belong to which section
    _BASE_NAMES = {
        "Patrol ghost", "Teleporter", "Power-up", "Pushable box", "Yellow gate", "Pink wall",
        "Scared ghost", "Banana",
    }
    _HIDE_FROM_LEGEND = {"Banana"} if lvl_title != "LEVEL 1A" else set()
    _META_NAMES = {
        "Chasing ghost", "Shared teleporter", "Delayed power-up",
        "Sliding meta-block", "Teal wall",
    }
    # Everything else (zone_rules) → ZONE RULES

    # Collect all entries for this level from LEVEL_LEGENDS + IMPLICIT_LEGEND
    all_entries = _legend_all_entries(lvl_title)
    seen = set()
    base_final  = []
    meta_entries = []
    zone_entries = []
    for color, name, desc in all_entries:
        if name in seen or name in _HIDE_FROM_LEGEND:
            continue
        seen.add(name)
        if name in _BASE_NAMES:
            base_final.append((color, name, desc))
        elif name in _META_NAMES:
            meta_entries.append((color, name, desc))
        else:
            zone_entries.append((color, name, desc))

    if base_final:
        y = _draw_section_header("BASE COMPONENTS", y)
        for color, label, desc in base_final:
            y = _draw_entry(color, label, desc, y)

    if meta_entries:
        y = _draw_section_header("META-RULES", y)
        for color, label, desc in meta_entries:
            y = _draw_entry(color, label, desc, y)

    if zone_entries:
        y = _draw_section_header("ZONE RULES", y)
        for color, label, desc in zone_entries:
            y = _draw_entry(color, label, desc, y)

    # ── Goals ─────────────────────────────────────────────────────────────────
    goals = legend.get("goals", [])
    y += 14
    pygame.draw.line(surf, (50, 50, 90), (panel_x + PAD, y), (panel_x + panel_w - PAD - SB_W, y), 1)
    y += 14
    surf.blit(font_big.render("GOALS", True, (200, 200, 255)), (panel_x + PAD, y))
    y += bh + 8
    for goal in goals:
        surf.blit(font_small.render(f"• {goal}", True, (175, 185, 210)), (panel_x + PAD, y))
        y += sh + 6

    # ── Controls ──────────────────────────────────────────────────────────────
    y += 14
    pygame.draw.line(surf, (50, 50, 90), (panel_x + PAD, y), (panel_x + panel_w - PAD - SB_W, y), 1)
    y += 14
    surf.blit(font_big.render("CONTROLS", True, (200, 200, 255)), (panel_x + PAD, y))
    y += bh + 8
    for key, desc in [("Arrow keys / WASD", "Move"), ("R", "Restart (+1 attempt)"),
                      ("SPACE", "Next level"), ("ESC", "Quit")]:
        key_surf  = font_small.render(key,        True, (255, 220, 80))
        desc_surf = font_small.render(f"— {desc}", True, (175, 185, 210))
        surf.blit(key_surf,  (panel_x + PAD, y))
        surf.blit(desc_surf, (panel_x + PAD + key_surf.get_width() + 6, y))
        y += sh + 8

    surf.set_clip(old_clip)

    # ── Scrollbar ────────────────────────────────────────────────────────────
    if max_scroll > 0:
        sb_x       = panel_x + panel_w - SB_W - 2
        track_h    = scroll_area_h - 8
        thumb_h    = max(20, int(track_h * scroll_area_h / content_h))
        thumb_y    = panel_y + hdr_h + 4 + int((track_h - thumb_h) * scroll_offset / max_scroll)
        pygame.draw.rect(surf, (50, 50, 80),   pygame.Rect(sb_x, panel_y + hdr_h + 4, SB_W, track_h), border_radius=3)
        pygame.draw.rect(surf, (120, 120, 180), pygame.Rect(sb_x, thumb_y, SB_W, thumb_h), border_radius=3)


# ─── Serie-navigatie constanten ───────────────────────────────────────────────

# Which level index is the last of each series, and which series it leads to
# next. After level 5 (1F) -> interstitial "1->2", after level 11 (2F) -> "2->3", etc.
ESTIMATE_RANGES = [
    (0,   0,  "Exact!",  "Bonus +50"),
    (1,   1,  "± 1",     "Bonus +50"),
    (2,   2,  "± 2",     "Bonus +50"),
    (3,   3,  "± 3",     "Bonus +50"),
    (4,   4,  "± 4",     "Bonus +50"),
    (5, 999,  "± 5+",    "Bonus +50"),
]
# Reward based on the actual gap (regardless of the bet): 50/40/30/20/10/0
ESTIMATE_GAP_REWARDS  = [50, 40, 30, 20, 10, 0]   # index = gap (5+ → 0)
ESTIMATE_BONUS        = 50                          # bonus als gok correct is
ESTIMATE_COIN_REWARDS = ESTIMATE_GAP_REWARDS        # backwards compat alias

SERIES_LAST = {
    5:  ("1", "2"),
    11: ("2", "3"),
    17: ("3", None),   # Serie 3 eindigt het hoofdspel; serie 4 is optionele wager-game
}

# First level index of each series -- used to navigate after the interstitial
SERIES_FIRST = {1: 0, 2: 6, 3: 12, 4: 18}

# Wager dirs are chosen based on the implicit flag when wager_session_dir is created


# ─── Hoofd game-loop ──────────────────────────────────────────────────────────

def main(implicit=False):
    """Start the full pygame game and run the event/render loop.

    The loop runs at 60 fps. Per frame:
      1. Process pygame events (key presses, quit)
      2. Process game logic if the player made a valid move
      3. Draw the current screen based on screen_mode
      4. pygame.display.flip() -- push the frame to the screen
    """
    pygame.init()

    # Load the pixel font if the file exists; otherwise fall back to a system font
    if __import__("os").path.exists(FONT_PATH):
        font_large = pygame.font.Font(FONT_PATH, 28)
        font_big   = pygame.font.Font(FONT_PATH, 18)
        font_small = pygame.font.Font(FONT_PATH, 10)
    else:
        font_large = pygame.font.SysFont("monospace", 40, bold=True)
        font_big   = pygame.font.SysFont("monospace", 26, bold=True)
        font_small = pygame.font.SysFont("monospace", 15)
    font_med = font_big

    _info = pygame.display.Info()
    screen = pygame.display.set_mode((_info.current_w, _info.current_h), pygame.FULLSCREEN)
    fs_w, fs_h = screen.get_size()
    pygame.display.set_caption("NP-Hard Pac-Man")

    # The active screen mode determines what is drawn and which input is processed
    # Mogelijke waarden: "intro" | "preview" | "wager" | "playing"
    #                    | "series_transition" | "leaderboard" | "wager_intro" | "end_screen"
    screen_mode     = "intro"
    transition_info = None   # (series_done, series_next, stats) voor tussenscherm
    current_level_idx = 0

    lvl   = LEVELS[0]
    state = make_state(lvl)
    clock = pygame.time.Clock()
    t     = 0.0

    # ── Participant ID ────────────────────────────────────────────────────────
    participant_id = ""             # ingevuld op het intro-scherm

    # -- Session directory (created once the player starts, incl. participant ID) --
    _session_ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    _session_tag  = f"{'implicit' if implicit else 'explicit'}"
    _runs_dir     = RUNS_DIR_IMPLICIT if implicit else RUNS_DIR_EXPLICIT
    session_dir   = os.path.join(_runs_dir, f"{_session_ts}_{_session_tag}")  # voorlopig; wordt hergemaakt bij start
    session_start_wall = time.monotonic()

    # ── Statistics ────────────────────────────────────────────────────────────
    total_moves_used = 0          # sum of moves used across all completed levels
    level_attempts   = {}         # idx → number of play attempts
    level_fails      = {}         # idx → number of failed attempts
    series_moves     = {}         # series_num → moves used in that series
    end_stats        = {}         # filled when last level completes
    player_name      = ""         # entered on leaderboard screen
    name_confirmed   = False      # True after ENTER pressed on leaderboard
    lb_saved         = False      # True after leaderboard entry is saved once
    MAX_FAILS        = 3          # max failures serie 1; 5 vanaf serie 2

    # -- Series timer (30 min per series, surplus carries over) ----------------
    SERIES_TIME_LIMIT = 30 * 60   # 1800 seconden per serie
    series_time_end   = None      # time.monotonic() deadline voor huidige serie

    def _start_series_timer(carry_over=0.0):
        nonlocal series_time_end
        series_time_end = time.monotonic() + SERIES_TIME_LIMIT + carry_over

    def _series_time_left():
        if series_time_end is None:
            return SERIES_TIME_LIMIT
        return max(0.0, series_time_end - time.monotonic())

    def _max_fails_for(idx):
        if idx < 6:   return 3   # serie 1
        if idx < 18:  return 2   # serie 2 en 3
        return 1                  # serie 4 (wager: geen retry)

    # -- Run log (per attempt) -------------------------------------------------
    current_run_log  = []         # list of dicts: {move, col, row, moves_left, status, think_time_s}
    last_move_time   = None       # time.monotonic() timestamp of last accepted move
    level_start_time = None       # time.monotonic() when current level/attempt started
    session_files       = []      # paths of run-log files for serie 1-3
    wager_session_files = []      # paths of run-log files for serie 4
    legend_scroll    = 0          # pixel scroll offset for implicit legend panel
    expl_scroll      = 0          # pixel scroll offset for explicit legend panel

    # ── Wagering state ────────────────────────────────────────────────────────
    preview_timer    = 0.0        # counts down from preview_seconds
    wager_coins      = 0          # coin balance — reset per wager level, accumulates across estimate levels
    wager_slider     = 0          # current slider offset (moves bought/sold)
    total_wager_coins = 0         # eindtotaal coins over alle 4 levels
    estimate_choice  = None       # player's button choice on estimate screen (0-5)
    estimate_moves   = 0          # moves used in the completed estimate level
    wager_lvl_idx    = None       # index of the level being wagered on
    wager_session_dir = None      # aparte map voor serie 4 logs
    wager_done        = False     # True nadat alle wager levels gespeeld zijn
    _wager_decision  = None       # dict met wager-beslissing, wordt meegegeven aan save
    coin_result_info = {}         # info voor het coin_result tussenscherm
    _coin_result_next = None      # callable: wat er na coin_result gebeurt
    estimate_result_info = {}     # info voor het estimate_result tussenscherm
    _estimate_result_next = None  # callable: wat er na estimate_result gebeurt

    def _show_coin_result(coins_earned, balance, won, next_fn):
        nonlocal screen_mode, t, coin_result_info, _coin_result_next
        coin_result_info = {
            "level_name":   lvl["title"],
            "coins_earned": coins_earned,
            "balance":      balance,
            "won":          won,
        }
        _coin_result_next = next_fn
        screen_mode = "coin_result"
        t = 0.0

    def _series_of(idx):
        """Return which series (1/2/3) a level index belongs to."""
        for i, last in enumerate(sorted(SERIES_LAST.keys())):
            if idx <= last:
                return i + 1
        return len(SERIES_LAST) + 1

    def _series_stats(series_num):
        """Compute first_try / retried counts for a given series."""
        idxs = [i for i in level_attempts if _series_of(i) == series_num]
        first_try = sum(1 for i in idxs if level_attempts[i] == 1)
        retried   = sum(1 for i in idxs if level_attempts[i] > 1)
        moves     = series_moves.get(series_num, 0)
        return {"moves": moves, "first_try": first_try, "retried": retried,
                "total": len([i for i in range(len(LEVELS)) if _series_of(i) == series_num])}

    def _finish_game():
        nonlocal screen_mode, t, wager_done, wager_session_dir
        is_wager_finish = current_level_idx >= SERIES_FIRST[4]
        if is_wager_finish:
            wager_done = True
        s3  = _series_stats(3)
        all_attempts = list(level_attempts.values())
        completed = sum(1 for idx, a in level_attempts.items()
                        if LEVELS[idx] and a >= 1 and level_fails.get(idx, 0) < _max_fails_for(idx))
        end_stats.update({
            "total_moves":    total_moves_used,
            "first_try":      sum(1 for i, a in level_attempts.items()
                                  if a == 1 and level_fails.get(i, 0) == 0),
            "retried":        sum(1 for a in all_attempts if a > 1),
            "total_levels":   SERIES_FIRST[4],   # 18: serie 1-3 only, wager levels niet meegeteld
            "total_time_s":   round(time.monotonic() - session_start_wall, 1),
            "s3_moves":       s3["moves"],
            "s3_first_try":   s3["first_try"],
            "s3_retried":     s3["retried"],
            "s3_total":       s3["total"],
        })
        if session_files:
            _save_session_summary(session_files, player_name=player_name, implicit=implicit,
                                  session_dir=session_dir)
        if wager_session_files:
            _save_session_summary(wager_session_files, player_name=player_name, implicit=implicit,
                                  session_dir=wager_session_dir)
        if is_wager_finish:
            # After series 4: save wager leaderboard -> wager_leaderboard screen -> end_screen
            end_stats["total_wager_coins"] = total_wager_coins
            _wentries = _load_wager_leaderboard(implicit)
            _wentries.append({
                "name":               player_name.strip() or participant_id.strip(),
                "timestamp":          datetime.datetime.now().isoformat(),
                "total_wager_coins":  total_wager_coins,
                "implicit":           implicit,
            })
            _save_wager_leaderboard(_wentries, implicit)
            screen_mode = "wager_leaderboard"
        else:
            # Na serie 3: leaderboard (serie 1-3) → na doorklikken wager_intro
            screen_mode = "leaderboard"
        t = 0.0

    def _active_session_dir():
        """Return the correct session_dir: wager dir for series 4, otherwise the normal dir."""
        if current_level_idx >= SERIES_FIRST[4] and wager_session_dir:
            return wager_session_dir
        return session_dir

    def switch_to(idx):
        nonlocal current_level_idx, lvl, state, t, screen_mode
        nonlocal current_run_log, last_move_time, level_start_time
        nonlocal preview_timer, wager_slider, wager_lvl_idx, legend_scroll, expl_scroll
        nonlocal estimate_choice, estimate_moves, _wager_decision, wager_coins
        nonlocal wager_session_dir
        _wager_decision = None
        legend_scroll = 0
        expl_scroll   = 0
        level_attempts[idx] = level_attempts.get(idx, 0) + 1
        current_level_idx = idx
        lvl   = LEVELS[idx]
        state = make_state(lvl)
        current_run_log  = []
        last_move_time   = None
        level_start_time = time.monotonic()
        pygame.display.set_caption(f"NP-Hard Pac-Man  -  {lvl['title']}")
        t = 0.0
        if lvl.get("estimate_level") or lvl.get("wager_level"):
            # Make sure wager_session_dir exists even if the leaderboard was skipped
            if wager_session_dir is None:
                import datetime as _dt
                _wts  = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                _wtag = "wager"
                _pid  = (participant_id.strip().replace(" ", "_") or "unknown")
                _wager_base = WAGER_DIR_AFTER_IMPLICIT if implicit else WAGER_DIR_AFTER_EXPLICIT
                wager_session_dir = os.path.join(_wager_base, f"P{_pid}_{_wts}_{_wtag}")
                os.makedirs(wager_session_dir, exist_ok=True)
        if lvl.get("estimate_level"):
            wager_lvl_idx = idx
            screen_mode   = "playing"
        elif lvl.get("wager_level"):
            preview_timer = float(lvl.get("preview_seconds", 20))
            wager_slider  = 0
            wager_lvl_idx = idx
            wager_coins   = 100   # elke wager level (4A, 4B) begint met 100 coins
            screen_mode   = "preview"
        else:
            screen_mode = "playing"

    while True:
        dt = clock.tick(60) / 1000.0
        t += dt

        # ── Serietimer: time's up → game_over ────────────────────────────────
        if screen_mode == "playing" and not lvl.get("wager_level") and series_time_end is not None and _series_time_left() <= 0:
            state["status"] = "game_over"
            state["reason"] = "Time's up! Serie time limit reached."

        # ── Preview countdown ─────────────────────────────────────────────────
        if screen_mode == "preview":
            preview_timer -= dt
            if preview_timer <= 0:
                screen_mode = "wager"

        for event in pygame.event.get():
            if event.type == QUIT:
                if session_files:
                    _save_session_summary(session_files, player_name=player_name,
                                          implicit=implicit, session_dir=session_dir)
                if wager_session_files:
                    _save_session_summary(wager_session_files, player_name=player_name,
                                          implicit=implicit, session_dir=wager_session_dir)
                pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEWHEEL and screen_mode == "playing":
                if implicit:
                    legend_scroll -= event.y * 20
                    legend_scroll = max(0, legend_scroll)
                else:
                    expl_scroll -= event.y * 20
                    expl_scroll = max(0, expl_scroll)
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    if session_files:
                        _save_session_summary(session_files, player_name=player_name,
                                              implicit=implicit, session_dir=session_dir)
                    if wager_session_files:
                        _save_session_summary(wager_session_files, player_name=player_name,
                                              implicit=implicit, session_dir=wager_session_dir)
                    pygame.quit(); sys.exit()

                # -- Estimate result: any key advances to coin_result ---------
                if screen_mode == "estimate_result":
                    if _estimate_result_next is not None:
                        _estimate_result_next()
                    continue

                # -- Coin result: any key advances ----------------------------
                if screen_mode == "coin_result":
                    if _coin_result_next is not None:
                        _coin_result_next()
                    continue

                # ── Leaderboard: naam invoeren ────────────────────────────────
                if screen_mode == "leaderboard":
                    if not name_confirmed:
                        if event.key == K_RETURN and player_name.strip():
                            name_confirmed = True
                            if not lb_saved:
                                lb_saved = True
                                entries = _load_leaderboard(implicit)
                                entries.append({
                                    "name":         player_name.strip(),
                                    "timestamp":    datetime.datetime.now().isoformat(),
                                    "total_moves":  end_stats.get("total_moves", 0),
                                    "first_try":    end_stats.get("first_try", 0),
                                    "total_levels": end_stats.get("total_levels", 0),
                                    "total_time_s": end_stats.get("total_time_s", 0),
                                    "implicit":     implicit,
                                })
                                _save_leaderboard(entries, implicit)
                        elif event.key == K_BACKSPACE:
                            player_name = player_name[:-1]
                        elif event.unicode and event.unicode.isprintable() and len(player_name) < 20:
                            player_name += event.unicode
                    else:
                        # Name confirmed -> wager intro (leaderboard is always after series 3)
                        if wager_session_dir is None:
                            _pid = participant_id.strip().replace(" ", "_") or "unknown"
                            _wts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            _wtag = f"{'implicit' if implicit else 'explicit'}"
                            _wager_base = WAGER_DIR_AFTER_IMPLICIT if implicit else WAGER_DIR_AFTER_EXPLICIT
                            wager_session_dir = os.path.join(_wager_base, f"P{_pid}_{_wts}_{_wtag}")
                            os.makedirs(wager_session_dir, exist_ok=True)
                        screen_mode = "wager_intro"
                        t = 0.0
                    continue

                # -- Wager leaderboard: any key -> end_screen -----------------
                if screen_mode == "wager_leaderboard":
                    screen_mode = "end_screen"
                    t = 0.0
                    continue

                # -- End screen: only ESC quits -------------------------------
                if screen_mode == "end_screen":
                    continue

                # -- Wager intro: any key starts level 4 ----------------------
                if screen_mode == "wager_intro":
                    switch_to(SERIES_FIRST[4])
                    continue

                # -- Intro: text input for participant ID, ENTER to start -----
                if screen_mode == "intro":
                    if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                        if participant_id.strip():
                            _session_ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            _session_tag = f"{'implicit' if implicit else 'explicit'}"
                            _pid         = participant_id.strip().replace(" ", "_")
                            _runs_dir    = RUNS_DIR_IMPLICIT if implicit else RUNS_DIR_EXPLICIT
                            session_dir  = os.path.join(_runs_dir, f"P{_pid}_{_session_ts}_{_session_tag}")
                            os.makedirs(session_dir, exist_ok=True)
                            screen_mode = "instructions"
                            t = 0.0
                    elif event.key == pygame.K_BACKSPACE:
                        participant_id = participant_id[:-1]
                    elif event.unicode and event.unicode.isprintable() and len(participant_id) < 12:
                        participant_id += event.unicode
                    continue

                # ── Instructions: any key → level 1A ────────────────────────
                if screen_mode == "instructions":
                    _start_series_timer()
                    switch_to(0)
                    continue

                # ── Preview: any key skips remaining preview time ─────────────
                if screen_mode == "preview":
                    preview_timer = 0.0
                    continue

                # ── Estimate intro: any key starts level 4C ──────────────────
                if screen_mode == "estimate_intro":
                    switch_to(20)
                    continue

                # ── Estimate: navigate buttons or confirm ─────────────────────
                if screen_mode == "estimate":
                    if event.key in (K_RIGHT, K_d):
                        estimate_choice = min(5, (0 if estimate_choice is None else estimate_choice) + 1)
                    elif event.key in (K_LEFT, K_a):
                        estimate_choice = max(0, (0 if estimate_choice is None else estimate_choice) - 1)
                    elif event.key == K_SPACE and estimate_choice is not None:
                        gap = abs(estimate_moves - lvl["optimal_moves"])
                        lo, hi, label, _ = ESTIMATE_RANGES[estimate_choice]
                        correct         = lo <= gap <= hi
                        gap_reward      = ESTIMATE_GAP_REWARDS[min(gap, 5)]
                        bonus           = ESTIMATE_BONUS if correct else 0
                        total_reward    = gap_reward + bonus
                        coins_before    = wager_coins
                        wager_coins    += total_reward
                        total_wager_coins += total_reward
                        _estimate_data = {
                            "optimal_moves":        lvl["optimal_moves"],
                            "moves_used":           estimate_moves,
                            "gap_actual":           gap,
                            "gap_reward":           gap_reward,
                            "guess_label":          label,
                            "guess_range":          [lo, hi],
                            "guess_correct":        correct,
                            "guess_bonus":          bonus,
                            "total_coin_reward":    total_reward,
                            "coins_before":         coins_before,
                            "coins_after":          wager_coins,
                        }
                        p = _save_run_log(lvl, level_attempts.get(current_level_idx, 1),
                                          list(current_run_log), "win", estimate_moves, implicit,
                                          start_time=level_start_time,
                                          session_dir=_active_session_dir(),
                                          wager_data=_estimate_data)
                        if p: wager_session_files.append(p)
                        total_moves_used += estimate_moves
                        s = _series_of(current_level_idx)
                        series_moves[s] = series_moves.get(s, 0) + estimate_moves
                        nxt = current_level_idx + 1
                        _next = (lambda: switch_to(nxt)) if nxt < len(LEVELS) else _finish_game
                        estimate_result_info  = dict(_estimate_data)
                        _estimate_result_next = lambda: _show_coin_result(
                            total_reward, total_wager_coins, True, _next)
                        screen_mode = "estimate_result"
                        t = 0.0
                    continue

                # ── Wager: adjust slider or confirm ──────────────────────────
                if screen_mode == "wager":
                    move_price = lvl.get("wager_move_price", 5)
                    max_buy    = min(15, wager_coins // move_price)
                    max_sell   = min(15, lvl["max_moves"] - 1)
                    if event.key in (K_RIGHT, K_d):
                        if wager_slider < max_buy:
                            wager_slider += 1
                    elif event.key in (K_LEFT, K_a):
                        if wager_slider > -max_sell:
                            wager_slider -= 1
                    elif event.key == K_SPACE:
                        # Confirm wager: apply coins & moves then start playing
                        coins_before = wager_coins
                        wager_coins -= wager_slider * move_price
                        wagered_total = lvl["max_moves"] + wager_slider
                        state["moves_left"]    = wagered_total
                        state["wager_max_moves"] = wagered_total
                        _wager_decision = {
                            "moves_bought":   max(0, wager_slider),
                            "moves_sold":     max(0, -wager_slider),
                            "net_change":     wager_slider,
                            "coins_spent":    wager_slider * move_price,
                            "coins_before":   coins_before,
                            "coins_after":    wager_coins,
                            "base_moves":     lvl["max_moves"],
                            "final_moves":    wagered_total,
                        }
                        screen_mode = "playing"
                    continue

                # -- Interstitial: space -> first level of the next series ----
                if screen_mode == "series_transition":
                    if event.key == K_SPACE and transition_info:
                        next_series = transition_info[1]
                        if next_series is None:
                            _finish_game()
                        else:
                            _start_series_timer(carry_over=_series_time_left())
                            switch_to(SERIES_FIRST[int(next_series)])
                    continue

                # ── Spelscherm ────────────────────────────────────────────────
                if event.key == K_r:
                    if lvl.get("wager_level") and state["status"] == "game_over":
                        # Wager level: failing = losing coins, move on to the next level
                        moves_used = lvl["max_moves"] - state["moves_left"]
                        coins_lost = wager_coins
                        wager_coins = 0   # verlies alles
                        _wd = _wager_decision.copy() if _wager_decision else {}
                        _wd["coins_lost_on_fail"] = coins_lost
                        _wd["coins_after_fail"]   = 0
                        p = _save_run_log(lvl, level_attempts.get(current_level_idx, 1),
                                          list(current_run_log), "game_over", moves_used, implicit,
                                          fail_reason=state.get("reason", ""),
                                          start_time=level_start_time,
                                          session_dir=_active_session_dir(),
                                          wager_data=_wd)
                        if p: wager_session_files.append(p)
                        nxt = current_level_idx + 1
                        _next = (lambda: switch_to(nxt)) if nxt < len(LEVELS) else _finish_game
                        _show_coin_result(-coins_lost, total_wager_coins, False, _next)
                        continue
                    if not lvl.get("wager_level"):
                        if state["status"] == "game_over":
                            attempt_num = level_attempts.get(current_level_idx, 1)
                            moves_used  = lvl["max_moves"] - state["moves_left"]
                            fail_reason = state.get("reason", "")
                            fails = level_fails.get(current_level_idx, 0) + 1
                            level_fails[current_level_idx] = fails
                            if fails >= _max_fails_for(current_level_idx):
                                # Auto-skip to next level after 3 fails
                                p = _save_run_log(lvl, attempt_num, list(current_run_log),
                                                  "skipped", moves_used, implicit,
                                                  fail_reason=fail_reason,
                                                  start_time=level_start_time,
                                                  session_dir=_active_session_dir())
                                if p: session_files.append(p)
                                nxt = current_level_idx + 1
                                if current_level_idx in SERIES_LAST:
                                    series_done, series_next = SERIES_LAST[current_level_idx]
                                    series_num = int(series_done)
                                    transition_info = (series_done, series_next, _series_stats(series_num))
                                    screen_mode = "series_transition"
                                    t = 0.0
                                elif nxt < len(LEVELS):
                                    switch_to(nxt)
                                else:
                                    _finish_game()
                            else:
                                p = _save_run_log(lvl, attempt_num, list(current_run_log),
                                                  "game_over", moves_used, implicit,
                                                  fail_reason=fail_reason,
                                                  start_time=level_start_time,
                                                  session_dir=_active_session_dir())
                                if p: session_files.append(p)
                                switch_to(current_level_idx)
                        else:
                            # Voluntary reset while playing -- also counts as an attempt
                            fails = level_fails.get(current_level_idx, 0) + 1
                            level_fails[current_level_idx] = fails
                            moves_used = lvl["max_moves"] - state["moves_left"]
                            p = _save_run_log(lvl, level_attempts.get(current_level_idx, 1),
                                              list(current_run_log),
                                              "reset", moves_used, implicit,
                                              fail_reason="Player reset",
                                              start_time=level_start_time,
                                              session_dir=_active_session_dir())
                            if p: session_files.append(p)
                            if fails >= _max_fails_for(current_level_idx):
                                nxt = current_level_idx + 1
                                if nxt < len(LEVELS):
                                    switch_to(nxt)
                                else:
                                    _finish_game()
                            else:
                                switch_to(current_level_idx)
                    continue

                if event.key == K_SPACE and state["status"] == "level_complete":
                    # Record stats for the completed level
                    moves_this_level = lvl["max_moves"] - state["moves_left"]
                    attempt_num = level_attempts.get(current_level_idx, 1)
                    # Estimate levels: skip save here — the estimate handler saves after the guess
                    if not lvl.get("estimate_level"):
                        _wd = _wager_decision if lvl.get("wager_level") else None
                        p = _save_run_log(lvl, attempt_num, list(current_run_log),
                                          "win", moves_this_level, implicit,
                                          start_time=level_start_time,
                                          session_dir=_active_session_dir(),
                                          wager_data=_wd)
                        if p:
                            if lvl.get("wager_level"):
                                wager_session_files.append(p)
                            else:
                                session_files.append(p)
                        total_moves_used += moves_this_level
                        s = _series_of(current_level_idx)
                        series_moves[s] = series_moves.get(s, 0) + moves_this_level
                        # 4A/4B won: add coins to the total
                        if lvl.get("wager_level") and not lvl.get("estimate_level"):
                            total_wager_coins += wager_coins

                    if current_level_idx in SERIES_LAST:
                        series_done, series_next = SERIES_LAST[current_level_idx]
                        series_num = int(series_done)
                        transition_info = (series_done, series_next, _series_stats(series_num))
                        screen_mode     = "series_transition"
                        t = 0.0
                    elif lvl.get("wager_level") and not lvl.get("estimate_level"):
                        # 4A/4B gewonnen: coin_result tonen, daarna estimate_intro of volgende level
                        nxt = current_level_idx + 1
                        def _after_4ab():
                            nonlocal estimate_moves, estimate_choice, screen_mode, t
                            if nxt < len(LEVELS) and LEVELS[nxt].get("estimate_level"):
                                estimate_moves  = moves_this_level
                                estimate_choice = None
                                screen_mode     = "estimate_intro"
                                t = 0.0
                            elif nxt < len(LEVELS):
                                switch_to(nxt)
                            else:
                                _finish_game()
                        _show_coin_result(wager_coins, total_wager_coins, True, _after_4ab)
                    else:
                        nxt = current_level_idx + 1
                        if nxt < len(LEVELS) and LEVELS[nxt].get("estimate_level") and not lvl.get("estimate_level"):
                            estimate_moves  = moves_this_level
                            estimate_choice = None
                            screen_mode     = "estimate_intro"
                            t = 0.0
                        elif lvl.get("estimate_level"):
                            estimate_moves  = moves_this_level
                            estimate_choice = None
                            screen_mode     = "estimate"
                            t = 0.0
                        elif nxt < len(LEVELS):
                            switch_to(nxt)
                        else:
                            _finish_game()
                    continue

                if state["status"] != "playing":
                    continue

                dc, dr, direction = 0, 0, state["direction"]
                if   event.key in (K_RIGHT, K_d): dc, direction =  1, "RIGHT"
                elif event.key in (K_LEFT,  K_a): dc, direction = -1, "LEFT"
                elif event.key in (K_DOWN,  K_s): dr, direction =  1, "DOWN"
                elif event.key in (K_UP,    K_w): dr, direction = -1, "UP"
                if dc == 0 and dr == 0:
                    continue

                cur_col, cur_row   = state["col"], state["row"]
                new_col = cur_col + dc
                new_row = cur_row + dr
                gate               = state["gate"]
                box_positions      = {(b[0], b[1]) for b in state["boxes"]}
                meta_box_positions = {(b[0], b[1]) for b in state["meta_boxes"]}
                all_box_positions  = box_positions | meta_box_positions

                out_of_bounds = not (0 <= new_col < lvl["cols"]
                                     and 0 <= new_row < lvl["rows"])
                hits_wall = (not out_of_bounds
                             and player_blocked_edge(lvl, state,
                                                     cur_col, cur_row, new_col, new_row))
                hits_gate = (not out_of_bounds and not hits_wall
                             and gate and not gate["open"]
                             and (new_col, new_row) == tuple(gate["pos"]))

                # ── Normale doos ──────────────────────────────────────────────
                hits_box   = (not out_of_bounds and not hits_wall and not hits_gate
                              and (new_col, new_row) in box_positions)
                box_push_ok = False
                pushed_idx  = -1
                if hits_box:
                    bdest_col = new_col + dc
                    bdest_row = new_row + dr
                    box_edge  = frozenset([(new_col, new_row), (bdest_col, bdest_row)])
                    box_wall_blocked = (
                        box_edge in lvl["walls"]
                        or box_edge in lvl.get("green_walls",  set())
                        or box_edge in lvl.get("purple_walls", set())
                        or any(og["edge"] == box_edge for og in state.get("orange_gates", []))
                        or any(sg["edge"] == box_edge for sg in state.get("shared_orange_gates", []))
                    )
                    can_push = (0 <= bdest_col < lvl["cols"]
                                and 0 <= bdest_row < lvl["rows"]
                                and not box_wall_blocked
                                and not (gate and not gate["open"]
                                         and (bdest_col, bdest_row) == tuple(gate["pos"]))
                                and (bdest_col, bdest_row) not in all_box_positions)
                    if can_push:
                        box_push_ok = True
                        for idx, b in enumerate(state["boxes"]):
                            if b[0] == new_col and b[1] == new_row:
                                pushed_idx = idx
                                break

                # -- Meta-box (slides until an obstacle) ----------------------
                hits_meta_box   = (not out_of_bounds and not hits_wall and not hits_gate
                                   and not hits_box
                                   and (new_col, new_row) in meta_box_positions)
                meta_slide_dest = None
                pushed_meta_idx = -1
                if hits_meta_box:
                    other_boxes     = all_box_positions - {(new_col, new_row)}
                    meta_slide_dest = slide_meta_box(new_col, new_row, dc, dr,
                                                     lvl, state, other_boxes)
                    if meta_slide_dest != (new_col, new_row):
                        for idx, b in enumerate(state["meta_boxes"]):
                            if b[0] == new_col and b[1] == new_row:
                                pushed_meta_idx = idx
                                break

                blocked = (out_of_bounds or hits_wall or hits_gate
                           or (hits_box and not box_push_ok)
                           or (hits_meta_box and meta_slide_dest == (new_col, new_row)))
                if blocked:
                    state["direction"]   = direction
                    state["moves_left"] -= 1
                    if state["moves_left"] == 0:
                        state["status"] = "game_over"
                        state["reason"] = "No moves left!"
                    continue

                if box_push_ok and pushed_idx >= 0:
                    state["boxes"][pushed_idx][0] += dc
                    state["boxes"][pushed_idx][1] += dr

                if pushed_meta_idx >= 0 and meta_slide_dest:
                    state["meta_boxes"][pushed_meta_idx][0] = meta_slide_dest[0]
                    state["meta_boxes"][pushed_meta_idx][1] = meta_slide_dest[1]

                state["col"]        = new_col
                state["row"]        = new_row
                state["direction"]  = direction
                state["moves_left"] -= 1

                edge_moved = frozenset([(cur_col, cur_row), (new_col, new_row)])

                # -- Mark a one-shot green wall (meta-meta green_wall_oneshot) -
                lrz_gw = lvl.get("local_rule_zone")
                if lrz_gw and "green_wall_oneshot" in lrz_gw.get("meta_meta_rules", set()):
                    if edge_moved in lvl.get("green_walls", set()):
                        if _edge_in_local_rule_zone(lvl, cur_col, cur_row, new_col, new_row):
                            state["used_green_walls"].add(edge_moved)

                # ── Oranje poort activeren ─────────────────────────────────────
                for og in state["orange_gates"]:
                    if og["edge"] == edge_moved and not og["used"]:
                        if og.get("bidirectional") or (dc, dr) == tuple(og["pass_dir"]):
                            og["used"] = True

                # -- Shared one-shot gate (player) ----------------------------
                for sg in state.get("shared_orange_gates", []):
                    if sg["edge"] == edge_moved and not sg["used"]:
                        if sg.get("bidirectional") or (dc, dr) == tuple(sg["pass_dir"]):
                            sg["used"] = True

                # ── Reguliere gate ────────────────────────────────────────────
                if gate and gate["open"] and (new_col, new_row) == tuple(gate["pos"]):
                    gate["open"] = False

                # ── Teleporters ───────────────────────────────────────────────
                pre_tp_col, pre_tp_row = state["col"], state["row"]   # save for ghost activation
                tps = lvl["teleporters"]
                if tps:
                    pos = (state["col"], state["row"])
                    for i, tp in enumerate(tps):
                        if pos == tuple(tp):
                            dest = tps[1 - i]
                            state["col"] = dest[0]
                            state["row"] = dest[1]
                            break

                # ── Gedeelde teleporters ──────────────────────────────────────
                stps = lvl.get("shared_teleporters")
                if stps:
                    pos = (state["col"], state["row"])
                    for i, stp in enumerate(stps):
                        if pos == tuple(stp):
                            # Meta-meta rule (3D): if zone_entry flag set,
                            # player may only enter from index 0 (zone side)
                            if lvl.get("shared_tp_zone_entry") and i != 1:
                                break   # zone TP is exit-only: player can only enter from outside
                            dest = stps[1 - i]
                            state["col"] = dest[0]
                            state["row"] = dest[1]
                            break

                # -- Ghost teleporters (player only outside the zone) ---------
                gtps = lvl.get("ghost_teleporters")
                if gtps:
                    pos = (state["col"], state["row"])
                    lrz = lvl.get("local_rule_zone")
                    for i, gtp in enumerate(gtps):
                        if pos == tuple(gtp):
                            # Player may only use the endpoint that lies outside the zone
                            in_zone = False
                            if lrz:
                                c_min, r_min, c_max, r_max = lrz["rect"]
                                in_zone = (c_min <= gtp[0] <= c_max and
                                           r_min <= gtp[1] <= r_max)
                            if not in_zone:
                                dest = gtps[1 - i]
                                state["col"] = dest[0]
                                state["row"] = dest[1]
                            break

                # -- Ambush ghost: also check activation against the pre-teleport cell -
                ag_pre = state.get("ambush_ghost")
                if ag_pre and not ag_pre["activated"]:
                    cheby_pre = max(abs(ag_pre["col"] - pre_tp_col),
                                    abs(ag_pre["row"] - pre_tp_row))
                    if cheby_pre <= ag_pre.get("radius", 2):
                        ag_pre["activated"] = True

                # ── Power-up ──────────────────────────────────────────────────
                _pus = lvl.get("powerups") or ([lvl["powerup"]] if lvl.get("powerup") else [])
                for _pi, _pu in enumerate(_pus):
                    if (_pi not in state["powerups_taken"]
                            and (state["col"], state["row"]) == tuple(_pu["pos"])):
                        state["powerups_taken"].add(_pi)
                        state["powered_turns"] = POWER_TURNS + 1  # +1 because power-down runs this same move

                # ── Vertraagde power-up ───────────────────────────────────────
                dpu = lvl.get("delayed_powerup")
                if (dpu and not state["delayed_pu_taken"]
                        and (state["col"], state["row"]) == tuple(dpu["pos"])):
                    state["delayed_pu_taken"] = True
                    lrz = lvl.get("local_rule_zone")
                    if lrz:
                        c_min, r_min, c_max, r_max = lrz["rect"]
                        in_zone = (c_min <= state["col"] <= c_max
                                   and r_min <= state["row"] <= r_max)
                    else:
                        in_zone = False
                    if in_zone:
                        state["delayed_pu_in_zone"]   = True
                        state["delayed_pu_countdown"] = 0
                    else:
                        state["delayed_pu_in_zone"]   = False
                        state["delayed_pu_countdown"] = DELAY_PU_MOVES + 1  # +1 because pickup move itself decrements

                # -- Ghost collision before movement --------------------------
                if state["ghost"] and not state["ghost_eaten"]:
                    g = state["ghost"]
                    if g["col"] == state["col"] and g["row"] == state["row"]:
                        if state["powered_turns"] > 0:
                            state["ghost_eaten"]   = True
                            state["powered_turns"] = 0
                        else:
                            state["status"] = "game_over"
                            state["reason"] = "Caught by the ghost!"
                            continue

                # -- Ambush ghost collision before movement -------------------
                if state.get("ambush_ghost"):
                    ag = state["ambush_ghost"]
                    if ag["col"] == state["col"] and ag["row"] == state["row"]:
                        if state["powered_turns"] > 0:
                            state["ambush_ghost"]  = None
                            state["powered_turns"] = 0
                        else:
                            state["status"] = "game_over"
                            state["reason"] = "Ambushed!"
                            continue

                # ── Doelen verzamelen ─────────────────────────────────────────
                for goal in state["goals"]:
                    if (not goal.get("collected")
                            and (state["col"], state["row"]) == tuple(goal["pos"])):
                        goal["collected"] = True

                goals_done = all(g.get("collected") for g in state["goals"])
                patrol_done = not lvl["ghost"] or state["ghost_eaten"]
                ambush_done = not lvl.get("ambush_ghost") or state.get("ambush_ghost") is None
                ghost_done  = not lvl["require_ghost_eaten"] or (patrol_done and ambush_done)
                if goals_done and ghost_done:
                    state["status"] = "level_complete"
                    continue

                # ── Power-down ────────────────────────────────────────────────
                if state["powered_turns"] > 0:
                    state["powered_turns"] -= 1

                # ── Vertraagde power-up aftellen ──────────────────────────────
                if state["delayed_pu_taken"] and not state["powered_turns"]:
                    lrz_dp = lvl.get("local_rule_zone")
                    zone_pause_active = (lrz_dp and
                                        "delayed_pu_pause" in lrz_dp.get("meta_meta_rules", set()))
                    in_zone_now = False
                    if zone_pause_active:
                        c_min, r_min, c_max, r_max = lrz_dp["rect"]
                        in_zone_now = (c_min <= state["col"] <= c_max
                                       and r_min <= state["row"] <= r_max)

                    if state["delayed_pu_in_zone"]:
                        # Paused in zone — resume countdown when player leaves
                        if not in_zone_now:
                            state["delayed_pu_in_zone"] = False
                            if state["delayed_pu_countdown"] == 0:
                                # First departure: start the countdown (exit move itself not counted)
                                state["delayed_pu_countdown"] = DELAY_PU_MOVES
                            # If countdown > 0: was re-paused mid-countdown; resume from current value
                    elif state["delayed_pu_countdown"] > 0:
                        # Countdown active — pause if player re-entered zone
                        if in_zone_now:
                            state["delayed_pu_in_zone"] = True
                        else:
                            state["delayed_pu_countdown"] -= 1
                            if state["delayed_pu_countdown"] == 0:
                                state["powered_turns"] = POWER_TURNS

                # -- Ghost moves ----------------------------------------------
                gate_cells = set()
                if gate and not gate["open"]:
                    gate_cells.add(tuple(gate["pos"]))
                if state["ghost"] and not state["ghost_eaten"]:
                    move_ghost(state["ghost"], lvl, gate_cells, state.get("broken_walls"))
                    apply_ghost_shared_teleport(state["ghost"], lvl)
                    g = state["ghost"]
                    if g["col"] == state["col"] and g["row"] == state["row"]:
                        if state["powered_turns"] > 0:
                            state["ghost_eaten"]   = True
                            state["powered_turns"] = 0
                            _g_done  = all(gl.get("collected") for gl in state["goals"])
                            _p_done  = not lvl["ghost"] or state["ghost_eaten"]
                            _a_done  = not lvl.get("ambush_ghost") or state.get("ambush_ghost") is None
                            _gh_done = not lvl["require_ghost_eaten"] or (_p_done and _a_done)
                            if _g_done and _gh_done:
                                state["status"] = "level_complete"
                                continue
                        else:
                            state["status"] = "game_over"
                            state["reason"] = "Caught by the ghost!"
                            continue

                # -- Ambush ghost moves ---------------------------------------
                if state.get("ambush_ghost"):
                    ag = state["ambush_ghost"]
                    move_ambush_ghost(ag, lvl, state["col"], state["row"],
                                      gate_cells,
                                      state.get("shared_orange_gates"),
                                      state.get("broken_walls"))
                    apply_ghost_shared_teleport(ag, lvl)
                    if ag["col"] == state["col"] and ag["row"] == state["row"]:
                        if state["powered_turns"] > 0:
                            state["ambush_ghost"]  = None
                            state["powered_turns"] = 0
                            _g_done  = all(gl.get("collected") for gl in state["goals"])
                            _p_done  = not lvl["ghost"] or state["ghost_eaten"]
                            _a_done  = not lvl.get("ambush_ghost") or state.get("ambush_ghost") is None
                            _gh_done = not lvl["require_ghost_eaten"] or (_p_done and _a_done)
                            if _g_done and _gh_done:
                                state["status"] = "level_complete"
                                continue
                        else:
                            state["status"] = "game_over"
                            state["reason"] = "Ambushed!"
                            continue

                if state["moves_left"] == 0:
                    state["status"] = "game_over"
                    state["reason"] = "No moves left!"

                # -- Log the move ---------------------------------------------
                now = time.monotonic()
                think_time = round(now - last_move_time, 3) if last_move_time is not None else None
                last_move_time = now
                current_run_log.append({
                    "move":         direction,
                    "col":          state["col"],
                    "row":          state["row"],
                    "moves_left":   state["moves_left"],
                    "status":       state["status"],
                    "think_time_s": think_time,
                })

        # ── Draw: wager screen ───────────────────────────────────────────────
        if screen_mode == "wager":
            move_price = lvl.get("wager_move_price", 5)
            max_buy    = min(15, wager_coins // move_price)
            max_sell   = min(15, lvl["max_moves"] - 1)
            draw_wager_screen(screen, font_big, font_small, fs_w, fs_h, t,
                              lvl["max_moves"], wager_slider,
                              max_buy, max_sell, move_price, wager_coins)
            pygame.display.flip()
            continue

        # -- Draw: intro screen ---------------------------------------------------
        if screen_mode == "intro":
            draw_intro(screen, font_big, font_big, font_small, fs_w, fs_h, t,
                       participant_id=participant_id)
            pygame.display.flip()
            continue

        # ── Draw: instructions screen ────────────────────────────────────────
        if screen_mode == "instructions":
            draw_instructions(screen, font_big, font_small, fs_w, fs_h, t)
            pygame.display.flip()
            continue

        # -- Draw: coin result interstitial -----------------------------------
        if screen_mode == "coin_result":
            draw_coin_result(screen, font_big, font_small, fs_w, fs_h, t, coin_result_info)
            pygame.display.flip()
            continue

        # ── Draw: wager leaderboard ──────────────────────────────────────────
        if screen_mode == "wager_leaderboard":
            draw_wager_leaderboard(screen, font_big, font_small, fs_w, fs_h, t,
                                   end_stats.get("total_wager_coins", total_wager_coins),
                                   _load_wager_leaderboard(implicit))
            pygame.display.flip()
            continue

        # ── Draw: wager intro ────────────────────────────────────────────────
        if screen_mode == "wager_intro":
            draw_wager_intro(screen, font_big, font_small, fs_w, fs_h, t)
            pygame.display.flip()
            continue

        # ── Draw: estimate intro ─────────────────────────────────────────────
        if screen_mode == "estimate_intro":
            draw_estimate_intro(screen, font_big, font_small, fs_w, fs_h, t)
            pygame.display.flip()
            continue

        # ── Draw: estimate screen ────────────────────────────────────────────
        if screen_mode == "estimate":
            draw_estimate_screen(screen, font_big, font_small, fs_w, fs_h, t,
                                 estimate_moves, lvl.get("optimal_moves", 0),
                                 estimate_choice, wager_coins)
            pygame.display.flip()
            continue

        # ── Draw: estimate result (goed/fout + coins breakdown) ──────────────
        if screen_mode == "estimate_result":
            draw_estimate_result(screen, font_big, font_small, fs_w, fs_h, t,
                                 estimate_result_info)
            pygame.display.flip()
            continue

        # ── Draw: end screen ─────────────────────────────────────────────────
        if screen_mode == "end_screen":
            draw_end_screen(screen, font_big, font_small, fs_w, fs_h, t, end_stats,
                            wager_lb_entries=_load_wager_leaderboard(implicit))
            pygame.display.flip()
            continue

        # ── Draw: leaderboard ────────────────────────────────────────────────
        if screen_mode == "leaderboard":
            draw_leaderboard(screen, font_big, font_small, fs_w, fs_h, t,
                             end_stats, player_name, name_confirmed,
                             lb_entries=_load_leaderboard(implicit))
            pygame.display.flip()
            continue

        # -- Draw: interstitial between series ------------------------------------
        if screen_mode == "series_transition":
            draw_series_transition(screen, font_big, font_big, font_small,
                                   fs_w, fs_h, t, *transition_info)
            pygame.display.flip()
            continue

        # -- Draw: game screen ----------------------------------------------------
        screen.fill(C_BG)
        gw = lvl["cols"] * lvl["cell"] + PADDING * 2 + 50
        gh = lvl["rows"] * lvl["cell"] + PADDING * 2 + 115
        grid_surf = pygame.Surface((gw, gh))
        grid_surf.fill(C_BG)

        border = pygame.Rect(PADDING-5, PADDING-5,
                             lvl["cols"]*lvl["cell"]+10,
                             lvl["rows"]*lvl["cell"]+10)
        pygame.draw.rect(grid_surf, C_BORDER, border, 3, border_radius=6)

        draw_grid(grid_surf, lvl, font_small, t, state.get("used_green_walls"), state.get("broken_walls"))

        # -- Activation zone of the ambush ghost ----------------------------------
        _ag = state.get("ambush_ghost")
        if _ag and not _ag["activated"]:
            _r = _ag.get("radius", AMBUSH_RADIUS)
            _zone_cell = pygame.Surface((lvl["cell"], lvl["cell"]), pygame.SRCALPHA)
            _zone_cell.fill((194, 106, 119, 55))   # Tol rose
            for _zc in range(lvl["cols"]):
                for _zr in range(lvl["rows"]):
                    if max(abs(_zc - _ag["col"]), abs(_zr - _ag["row"])) <= _r:
                        _zrect = cell_rect(_zc, _zr, lvl)
                        grid_surf.blit(_zone_cell, (_zrect.x, _zrect.y))

        lrz = lvl.get("local_rule_zone")
        if lrz:
            draw_local_rule_zone(grid_surf, lrz, lvl, t)

        stps = lvl.get("shared_teleporters")
        if stps:
            draw_shared_teleporter(grid_surf, stps[0][0], stps[0][1], lvl, t, is_first=True)
            draw_shared_teleporter(grid_surf, stps[1][0], stps[1][1], lvl, t, is_first=False)

        for sg in state.get("shared_orange_gates", []):
            draw_orange_gate_wall(grid_surf, sg, sg["used"], lvl)

        for og in state.get("orange_gates", []):
            draw_orange_gate_wall(grid_surf, og, og["used"], lvl)

        gate = state["gate"]
        if gate:
            draw_gate(grid_surf, gate["pos"][0], gate["pos"][1], lvl, gate["open"], t)

        _pus = lvl.get("powerups") or ([lvl["powerup"]] if lvl.get("powerup") else [])
        for _pi, _pu in enumerate(_pus):
            if _pi not in state["powerups_taken"]:
                draw_lightning(grid_surf, _pu["pos"][0], _pu["pos"][1], lvl, t)

        dpu = lvl.get("delayed_powerup")
        if dpu and not state["delayed_pu_taken"]:
            draw_delayed_powerup(grid_surf, dpu["pos"][0], dpu["pos"][1], lvl, t, countdown=0)
        elif state["delayed_pu_in_zone"]:
            # Picked up but still in zone — show all dots filled, waiting to start
            draw_delayed_powerup(grid_surf, state["col"], state["row"], lvl, t,
                                 countdown=DELAY_PU_MOVES)
        elif state["delayed_pu_countdown"] > 0:
            draw_delayed_powerup(grid_surf, state["col"], state["row"], lvl, t,
                                 countdown=state["delayed_pu_countdown"])

        for goal in state["goals"]:
            if not goal.get("collected"):
                gc, gr = goal["pos"]
                if goal["type"] == "food":
                    draw_food(grid_surf, gc, gr, lvl, t)
                else:
                    draw_banana(grid_surf, gc, gr, lvl, t)

        for box in state["boxes"]:
            draw_box(grid_surf, box[0], box[1], lvl)

        for box in state["meta_boxes"]:
            draw_meta_box(grid_surf, box[0], box[1], lvl)

        if state["ghost"] and not state["ghost_eaten"]:
            g      = state["ghost"]
            draw_ghost_patrol_trail(grid_surf, g, lvl)
            scared = state["powered_turns"] > 0
            draw_ghost(grid_surf, g["col"], g["row"], lvl, t, scared)

        if state.get("ambush_ghost"):
            ag = state["ambush_ghost"]
            draw_ambush_ghost(grid_surf, ag["col"], ag["row"], lvl, t,
                              ag["activated"], ag["paused"],
                              scared=state["powered_turns"] > 0)

        powered = state["powered_turns"] > 0
        draw_pacman(grid_surf, state["col"], state["row"], lvl, t,
                    state["direction"], powered)

        if screen_mode != "preview":
            draw_hud(grid_surf, lvl, state, font_med, font_small, implicit=implicit,
                     trial=level_fails.get(current_level_idx, 0) + 1, max_trials=_max_fails_for(current_level_idx),
                     time_left=_series_time_left())

        if state["status"] == "level_complete":
            nxt = current_level_idx + 1
            has_next = nxt < len(LEVELS) and current_level_idx not in SERIES_LAST
            draw_level_complete(grid_surf, font_large, font_big, gw, gh,
                                LEVELS[nxt]["title"] if has_next else None)
        elif state["status"] == "game_over":
            draw_game_over(grid_surf, font_large, font_big, font_small, state["reason"], gw, gh,
                           fails=level_fails.get(current_level_idx, 0) + 1, max_fails=_max_fails_for(current_level_idx),
                           wager=bool(lvl.get("wager_level")))

        # ── Preview overlay (drawn last, on top of everything) ────────────────
        if screen_mode == "preview":
            draw_preview_overlay(grid_surf, font_big, font_small, gw, gh, preview_timer)

        # ── Legenda-panelen ───────────────────────────────────────────────────
        leg_margin = 20
        _serie2_titles = {"LEVEL 2A","LEVEL 2B","LEVEL 2C","LEVEL 2D","LEVEL 2E","LEVEL 2F"}
        _serie3_titles = {"LEVEL 3A","LEVEL 3B","LEVEL 3C","LEVEL 3D","LEVEL 3E","LEVEL 3F"}

        # Left: explicit legend (explicit mode only)
        is_wager_preview = screen_mode == "preview" and lvl.get("wager_level")
        is_estimate      = screen_mode == "playing" and lvl.get("estimate_level")
        show_legend = (screen_mode == "playing" and not implicit and lvl["title"] in LEVEL_LEGENDS)
        if is_wager_preview or is_estimate:
            leg_w = 300  # links van het grid, grid verschuift naar rechts
        elif not show_legend:
            leg_w = 0
        elif lvl["title"] in _serie3_titles:
            leg_w = 345
        elif lvl["title"] in _serie2_titles:
            leg_w = 360
        else:
            leg_w = 300

        # Left: implicit legend (known elements + controls) in implicit mode
        impl_panel_w = 280 if implicit else 0

        left_w = leg_w if leg_w > 0 else impl_panel_w

        n_margins = (2 if left_w > 0 else 1)
        available_w = fs_w - left_w - leg_margin * n_margins
        scale = min(available_w / gw, fs_h / gh, 1.0)
        if scale < 1.0:
            sw = max(1, int(gw * scale))
            sh = max(1, int(gh * scale))
            grid_surf = pygame.transform.smoothscale(grid_surf, (sw, sh))
            gw, gh = sw, sh

        if left_w > 0:
            grid_x = leg_margin + left_w + leg_margin
        else:
            grid_x = (fs_w - gw) // 2
        grid_y = (fs_h - gh) // 2

        # Level title above the grid on the main screen (after scaling, always visible)
        title_surf_r = font_large.render(lvl["title"], True, C_PAC)
        screen.blit(title_surf_r, (8, 8))

        # Series timer below the level title, top left (not on wager levels)
        if screen_mode == "playing" and not lvl.get("wager_level"):
            _tl = _series_time_left()
            _tm, _ts = int(_tl) // 60, int(_tl) % 60
            _tc = (220, 60, 60) if _tl < 120 else (255, 200, 50) if _tl < 300 else C_LABEL
            _tt = font_small.render(f"TIME  {_tm:02d}:{_ts:02d}", True, _tc)
            screen.blit(_tt, (8, 8 + title_surf_r.get_height() + 4))

        screen.blit(grid_surf, (grid_x, grid_y))

        _timer_bottom = 8 + title_surf_r.get_height() + font_small.get_height() + 16
        if (is_wager_preview or is_estimate) and leg_w > 0:
            leg_x = leg_margin
            leg_y = _timer_bottom
            leg_h = fs_h - leg_y - 10
            draw_wager_preview_legend(screen, font_big, font_small, lvl,
                                      leg_x, leg_y, leg_w, leg_h)
        elif leg_w > 0:
            leg_x   = leg_margin
            _1f_h   = 36 + _legend_content_h(font_big, font_small, "LEVEL 1F", leg_w)
            leg_h   = min(_1f_h, fs_h - _timer_bottom - 10)
            leg_y   = max(_timer_bottom, (fs_h - leg_h) // 2)
            draw_legend_panel(screen, font_big, font_small,
                              lvl["title"], leg_x, leg_y, leg_w, leg_h,
                              scroll_offset=expl_scroll)
        elif implicit and screen_mode == "playing":
            _1f_h = _implicit_legend_content_h(font_big, font_small, "LEVEL 1F", impl_panel_w)
            _max_h = min(_1f_h, fs_h - 20)
            draw_implicit_legend_panel(screen, font_big, font_small,
                                       lvl["title"], leg_margin, 0, impl_panel_w, fs_h,
                                       scroll_offset=legend_scroll, max_panel_h=_max_h)

        if screen_mode == "preview":
            msg = font_big.render("MEMORIZE THIS LEVEL!", True, C_PAC)
            screen.blit(msg, (fs_w - msg.get_width() - 16, 8))

        pygame.display.flip()


if __name__ == "__main__":
    import sys
    implicit = "--implicit" in sys.argv
    main(implicit=implicit)
