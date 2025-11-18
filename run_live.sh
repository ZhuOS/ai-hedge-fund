#!/bin/bash
# AI Hedge Fund Live Trading Runner
# Usage: ./run_live.sh --tickers AAPL MSFT

cd "$(dirname "$0")"
PYTHONPATH=. poetry run python src/live_main.py --tickers AAPL
# PYTHONPATH=. poetry run python src/live_main.py --tickers "$@"