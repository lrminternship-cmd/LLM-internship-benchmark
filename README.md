# NP-Hard Pac-Man -- LLM Benchmark

Code accompanying a thesis (Psychobiology, year 3). The project uses a modified,
NP-Hard variant of Pac-Man as a benchmark to compare the reasoning and planning
ability of large language models (LLMs) with that of humans.

It consists of several game variants plus matching API runners that let LLMs
play the games headless (without a graphical interface).

## Components

| Variant            | Playable (human)        | LLM runner                     |
|--------------------|-------------------------|--------------------------------|
| Pac-Man (NP-Hard)  | `level1.py`             | `api_runner.py`                |
| Language game      | `language_game.py`      | `language_api_runner.py`       |
| Language control   | --                      | `language_control_runner.py`   |
| Wager / estimate   | (in `level1.py`)        | `api_runner.py`                |

NP-Hard game modules (own work): `level1.py` (visual game), `lv_logic.py`
(headless game logic), `lv_levels.py` (level definitions), `lv_constants.py`.
Analysis: `analyze_logs.py`.

## Attribution -- Pac-Man engine

The base Pac-Man engine is adapted from the tutorial at
[pacmancode.com](https://pacmancode.com) by Jonathan Richards. These files are
the original or lightly modified engine and are clearly marked as such in their
module docstrings:

> `run.py` (reference playable demo), `entity.py`, `ghosts.py`, `pacman.py`,
> `nodes.py`, `pellets.py`, `sprites.py`, `modes.py`, `mazedata.py`, `fruit.py`,
> `animation.py`, `pauser.py`, `text.py`, `vector.py`, `constants.py`.

All the NP-Hard rules, levels, scoring/wager mechanics, the headless simulation
and the LLM benchmark code (`level1.py`, `lv_*.py`, `language_game.py`, the
`*_runner.py` scripts and `analyze_logs.py`) are this project's own work.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Requires Python 3.12.

## API keys

The LLM runners read keys from environment variables -- **no** keys are stored in
the code. Set whichever you need:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."     # Claude
export OPENAI_API_KEY="sk-proj-..."       # GPT
export DEEPSEEK_API_KEY="sk-..."          # DeepSeek
export GOOGLE_API_KEY="AIzaSy..."         # Gemini
export MOONSHOT_API_KEY="sk-..."          # Kimi (optional)
```

## Usage

Play the game by hand:

```bash
python level1.py        # NP-Hard Pac-Man (the experiment build)
python run.py           # original reference Pac-Man demo (pacmancode.com)
```

Let an LLM play a level:

```bash
# Pac-Man benchmark
python api_runner.py --model claude-opus-4-7 --level 0
python api_runner.py --all-models --level 0 --runs 3

# Language game
python language_api_runner.py --model gpt-5.5 --level 1
python language_api_runner.py --model claude-opus-4-7 --level 2 --single-shot

# Control condition
python language_control_runner.py --model gemini-3.1-pro-preview --runs 3
```

Run logs are written locally to `logs*/` (not included in this repository).
Analyse them with:

```bash
python analyze_logs.py
```

## Data

The research data (run logs, human participants, datasets) is **not** included in
this repository -- see `.gitignore`. The human data is kept out of the repo for
privacy reasons.

> Note: the runner examples use placeholder model IDs (e.g. `claude-opus-4-7`,
> `gpt-5.5`). Adjust these to the model names available on your API account.
