# ChessBot

Small Python chess engine using python-chess with an alpha-beta search, MVV-LVA move ordering, quiescence search and a transposition table.

This repository contains a single script `chess_bot.py` that runs a command-line interactive bot (bot vs bot) and contains the core search/evaluation logic.

## Quick start

1. Create and activate a virtual environment (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

2. Run the bot:

```powershell
python .\chess_bot.py
```

The program prints the board to the console and the bot will play itself (the script is set up so both sides are played by the engine by default).

## Files

- `chess_bot.py` - main engine logic and CLI entrypoint.
- `requirements.txt` - Python dependencies.
- `README.md` - this file.

## Design notes

- Evaluation and MVV-LVA move-ordering use centipawn scales so search heuristics and static evaluation are numerically consistent.
- Transposition table stores (depth, eval, flag, best_move) to speed up repeated position lookups.
- Search uses iterative deepening with time-limited searches and quiescence at leaf nodes.

## TODO:

- GUI Frontend instead of console (build a web/desktop UI)
- UCI Protocol Support (let it be used by standard chess GUIs like Arena or Scid)
- ELO Calibration and Testing Suite (run automated matches vs stockfish + visualise performance)
- Self-Play Training Data Collection (log positions and train eval model)
- Time Control Engine (blitz, rapid, classical modes)
- Benchmarking and Profiling Dashboard (search depth, nodes/second, pruning stats)
