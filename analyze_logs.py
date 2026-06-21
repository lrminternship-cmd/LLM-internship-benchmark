"""
analyze_logs.py -- cognitive flexibility analysis for NP-Hard Pac-Man runs.

Reads all JSON log files from logs/ and computes a cognitive flexibility profile
per model based on three core measures:

  blocked_rate       -- fraction of moves that were blocked (lower = more efficient)
  perseveration_rate -- fraction of blocked moves that had already been blocked
                        before at the same position/direction (lower = less perseveration)
  switch_cost        -- difference in blocked_rate before vs after the first zone entry
                        (negative = better after the rule change; positive = worse)

Usage
-----
  python analyze_logs.py                      # all logs in logs/
  python analyze_logs.py --dir my_logs/       # custom directory
  python analyze_logs.py --level "Level 1A"   # filter by level name
  python analyze_logs.py --model claude        # filter by model prefix
  python analyze_logs.py --csv output.csv     # export to CSV
"""

import argparse
import json
import os
import sys
from collections import defaultdict


# ─── Load helpers ─────────────────────────────────────────────────────────────
def load_runs(log_dir, level_filter=None, model_filter=None):
    runs = []
    for fname in sorted(os.listdir(log_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(log_dir, fname)
        with open(path, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"  [SKIP] {fname}: {e}", file=sys.stderr)
                continue
        if level_filter and level_filter.lower() not in data.get("level", "").lower():
            continue
        if model_filter and model_filter.lower() not in data.get("model", "").lower():
            continue
        runs.append(data)
    return runs


def _safe(val, fmt=".3f"):
    return f"{val:{fmt}}" if val is not None else "  N/A "


# ─── Per-run summary row ──────────────────────────────────────────────────────
def run_summary(run):
    m = run.get("metrics", {})
    return {
        "model":               run["model"],
        "level":               run["level"],
        "run":                 run["run"],
        "status":              run["final_status"],
        "moves_used":          run["moves_used"],
        "blocked_rate":        m.get("blocked_rate"),
        "perseveration_count": m.get("perseveration_count"),
        "perseveration_rate":  m.get("perseveration_rate"),
        "switch_cost":         m.get("switch_cost"),
        "zone_transitions":    len(m.get("zone_transition_moves", [])),
    }


# ─── Aggregate across runs for one (model, level) pair ───────────────────────
def aggregate(rows):
    def avg(key):
        vals = [r[key] for r in rows if r[key] is not None]
        return sum(vals) / len(vals) if vals else None

    wins     = [r for r in rows if r["status"] == "level_complete"]
    win_rate = len(wins) / len(rows) if rows else 0.0

    return {
        "n_runs":              len(rows),
        "win_rate":            win_rate,
        "avg_moves":           avg("moves_used"),
        "avg_blocked_rate":    avg("blocked_rate"),
        "avg_persev_count":    avg("perseveration_count"),
        "avg_persev_rate":     avg("perseveration_rate"),
        "avg_switch_cost":     avg("switch_cost"),
        "n_with_zone":         sum(1 for r in rows if r["zone_transitions"] > 0),
    }


# ─── Print tables ─────────────────────────────────────────────────────────────
def print_per_run_table(summaries):
    print(f"\n{'='*100}")
    print("  PER-RUN DETAIL")
    print(f"{'='*100}")
    hdr = (f"  {'MODEL':<22} {'LEVEL':<14} {'RUN':>3}  {'STATUS':<14} "
           f"{'MOVES':>6}  {'BLK%':>5}  {'PERSEV':>6}  {'PERSEV%':>7}  {'SW_COST':>8}")
    print(hdr)
    print(f"  {'-'*95}")
    for r in summaries:
        win_str  = "WIN" if r["status"] == "level_complete" else "loss"
        blk_pct  = f"{r['blocked_rate']*100:.1f}%" if r["blocked_rate"] is not None else "  N/A"
        p_cnt    = str(r["perseveration_count"]) if r["perseveration_count"] is not None else "N/A"
        p_rate   = f"{r['perseveration_rate']*100:.1f}%" if r["perseveration_rate"] is not None else "  N/A"
        sw_cost  = _safe(r["switch_cost"])
        print(f"  {r['model']:<22} {r['level']:<14} {r['run']:>3}  {win_str:<14} "
              f"{r['moves_used']:>6}  {blk_pct:>5}  {p_cnt:>6}  {p_rate:>7}  {sw_cost:>8}")


def print_aggregate_table(by_model_level):
    print(f"\n{'='*100}")
    print("  AGGREGATE — COGNITIVE FLEXIBILITY PROFILE  (avg across runs)")
    print(f"{'='*100}")
    hdr = (f"  {'MODEL':<22} {'LEVEL':<14} {'N':>3}  {'WIN%':>5}  "
           f"{'BLK%':>5}  {'PERSEV':>6}  {'PERSEV%':>7}  {'SW_COST':>8}  NOTE")
    print(hdr)
    print(f"  {'-'*95}")

    for (model, level), agg in sorted(by_model_level.items()):
        win_pct   = f"{agg['win_rate']*100:.0f}%"
        blk_pct   = f"{agg['avg_blocked_rate']*100:.1f}%" if agg["avg_blocked_rate"] is not None else "  N/A"
        p_cnt     = f"{agg['avg_persev_count']:.1f}" if agg["avg_persev_count"] is not None else "  N/A"
        p_rate    = f"{agg['avg_persev_rate']*100:.1f}%" if agg["avg_persev_rate"] is not None else "  N/A"
        sw_cost   = _safe(agg["avg_switch_cost"])
        note      = f"zone in {agg['n_with_zone']}/{agg['n_runs']} runs" if agg["n_with_zone"] else ""
        print(f"  {model:<22} {level:<14} {agg['n_runs']:>3}  {win_pct:>5}  "
              f"{blk_pct:>5}  {p_cnt:>6}  {p_rate:>7}  {sw_cost:>8}  {note}")


def print_model_ranking(by_model_level):
    """Rank models by composite cognitive flexibility score across all levels."""
    model_scores = defaultdict(list)
    for (model, _level), agg in by_model_level.items():
        # Lower is better for all three metrics
        blk   = agg["avg_blocked_rate"]    or 0.0
        persv = agg["avg_persev_rate"]     or 0.0
        sw    = agg["avg_switch_cost"]     or 0.0
        # Simple unweighted sum — lower = more flexible
        model_scores[model].append((blk, persv, sw))

    ranked = []
    for model, scores in model_scores.items():
        avg_blk   = sum(s[0] for s in scores) / len(scores)
        avg_persv = sum(s[1] for s in scores) / len(scores)
        avg_sw    = sum(s[2] for s in scores) / len(scores)
        composite = avg_blk + avg_persv + max(avg_sw, 0)  # penalise positive switch cost only
        ranked.append((composite, model, avg_blk, avg_persv, avg_sw))

    ranked.sort()

    print(f"\n{'='*80}")
    print("  MODEL RANKING  (composite score = blocked_rate + persev_rate + max(switch_cost,0))")
    print(f"  Lower = more cognitively flexible")
    print(f"{'='*80}")
    print(f"  {'RANK':>4}  {'MODEL':<22}  {'COMPOSITE':>9}  {'BLK%':>6}  {'PERSEV%':>7}  {'SW_COST':>8}")
    print(f"  {'-'*72}")
    for rank, (comp, model, blk, persv, sw) in enumerate(ranked, start=1):
        print(f"  {rank:>4}  {model:<22}  {comp:>9.4f}  {blk*100:>5.1f}%  {persv*100:>6.1f}%  {sw:>+8.3f}")


# ─── CSV export ───────────────────────────────────────────────────────────────
def export_csv(summaries, path):
    import csv
    fields = ["model", "level", "run", "status", "moves_used",
              "blocked_rate", "perseveration_count", "perseveration_rate",
              "switch_cost", "zone_transitions"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(summaries)
    print(f"\n  CSV saved to: {path}")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Cognitive flexibility analysis for Pac-Man runs")
    parser.add_argument("--dir",   default="logs", help="Log directory (default: logs/)")
    parser.add_argument("--level", default=None,   help="Filter by level name substring")
    parser.add_argument("--model", default=None,   help="Filter by model name prefix")
    parser.add_argument("--csv",   default=None,   help="Export per-run table to CSV file")
    parser.add_argument("--no-detail", action="store_true", help="Skip per-run detail table")
    args = parser.parse_args()

    if not os.path.isdir(args.dir):
        print(f"Log directory not found: {args.dir!r}")
        sys.exit(1)

    runs = load_runs(args.dir, level_filter=args.level, model_filter=args.model)
    if not runs:
        print(f"No matching log files found in {args.dir!r}")
        sys.exit(0)

    summaries = [run_summary(r) for r in runs]

    # Group by (model, level)
    by_model_level = defaultdict(list)
    for s in summaries:
        by_model_level[(s["model"], s["level"])].append(s)

    aggregated = {key: aggregate(rows) for key, rows in by_model_level.items()}

    if not args.no_detail:
        print_per_run_table(summaries)

    print_aggregate_table(aggregated)
    print_model_ranking(aggregated)

    if args.csv:
        export_csv(summaries, args.csv)


if __name__ == "__main__":
    main()
