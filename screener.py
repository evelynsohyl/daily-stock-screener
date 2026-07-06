name: Daily Stock Screener

on:
  schedule:
    - cron: '0 1 * * 1-5'
  workflow_dispatch:

jobs:
  run-screener:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install yfinance

      - name: Run stock screener
        env:
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
        run: python screener.py
