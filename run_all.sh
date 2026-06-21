#!/bin/bash
# run_all.sh -- full test suite for NP-Hard Pac-Man benchmarking.
#
# Runs each model on all levels of Series 1, 2 and 3 (levels 0-17).
# Series 4 (wager level, index 18) is skipped.
#
# Usage:
#   chmod +x run_all.sh
#   ./run_all.sh                        # all models, all levels
#   ./run_all.sh deepseek-chat          # DeepSeek only
#   ./run_all.sh deepseek-chat claude   # DeepSeek + Claude
#
# Output:
#   - JSON logs per run in logs/
#   - Terminal output per model in logs/terminal/<model>.txt
#
# Run in the background (you can safely close the terminal):
#   nohup ./run_all.sh > logs/terminal/run_all.txt 2>&1 &

set -euo pipefail

# -- Configuration ------------------------------------------------------------
RUNS=5           # number of runs per level per model
LEVELS=(0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17)  # Series 1-3, no wager
LOG_DIR="logs"
TERMINAL_DIR="logs/terminal"

ALL_MODELS=(
    "claude-opus-4-7"
    "gpt-5.4"
    "deepseek-chat"
    "gemini-2.5-pro"
    "kimi-k2.6"
)

# If arguments are given, use them as the model list
if [ $# -gt 0 ]; then
    ALL_MODELS=("$@")
fi

# -- Setup --------------------------------------------------------------------
mkdir -p "$LOG_DIR" "$TERMINAL_DIR"

echo "========================================================"
echo "  NP-Hard Pac-Man -- full test suite"
echo "  Models   : ${ALL_MODELS[*]}"
echo "  Levels   : ${#LEVELS[@]} (Series 1-3)"
echo "  Runs/lvl : $RUNS"
echo "  Started  : $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================================"

TOTAL_RUNS=$(( ${#ALL_MODELS[@]} * ${#LEVELS[@]} * RUNS ))
echo "  Total runs to execute: $TOTAL_RUNS"
echo ""

COMPLETED=0
FAILED=0

# -- Main loop ----------------------------------------------------------------
for MODEL in "${ALL_MODELS[@]}"; do
    MODEL_LOG="$TERMINAL_DIR/${MODEL}.txt"
    echo "--------------------------------------------------------"
    echo "  Model: $MODEL"
    echo "  Log  : $MODEL_LOG"
    echo "--------------------------------------------------------"

    # Reset this model's log file at the start of the model
    echo "Model: $MODEL  |  Started: $(date '+%Y-%m-%d %H:%M:%S')" > "$MODEL_LOG"

    for LEVEL_IDX in "${LEVELS[@]}"; do
        echo "  [$(date '+%H:%M:%S')] Level index $LEVEL_IDX -- $RUNS runs..."

        # Runs 1 through RUNS for this level
        for RUN in $(seq 1 $RUNS); do
            echo -n "    Run $RUN/$RUNS... "

            # Execute the run; catch errors without stopping the script
            if python api_runner.py \
                --model "$MODEL" \
                --level "$LEVEL_IDX" \
                --runs 1 \
                >> "$MODEL_LOG" 2>&1; then
                echo "done"
                COMPLETED=$(( COMPLETED + 1 ))
            else
                echo "ERROR (see $MODEL_LOG)"
                FAILED=$(( FAILED + 1 ))
            fi

            # Short pause between runs to avoid rate limits
            sleep 1
        done
    done

    echo "  Model $MODEL done: $(date '+%H:%M:%S')"
    echo ""
done

# -- Final stats --------------------------------------------------------------
echo "========================================================"
echo "  DONE -- $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Succeeded : $COMPLETED / $TOTAL_RUNS"
echo "  Failed    : $FAILED"
echo "========================================================"

# Run analyze_logs.py once everything is finished
if [ -f "analyze_logs.py" ]; then
    echo ""
    echo "  Cognitive flexibility analysis:"
    python analyze_logs.py
fi
