"""
Daily Stock Screener Agent
Runs via GitHub Actions every weekday at 9 AM Singapore time.
App Password is stored securely as a GitHub Secret (never in the code).
"""

import yfinance as yf
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import time

# ── Configuration ─────────────────────────────────────────────
SENDER_EMAIL        = 'evelynsohyl@gmail.com'
SENDER_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')  # Loaded from GitHub Secret
RECIPIENT_EMAIL     = 'evelynsohyl@gmail.com'
MIN_SCORE_TO_FLAG   = 5

# ── Screening Criteria ────────────────────────────────────────
CRITERIA = {
    'pe_ratio'        : {'threshold': 15,   'direction': 'below', 'label': 'P/E < 15'},
    'pb_ratio'        : {'threshold': 1.5,  'direction': 'below', 'label': 'P/B < 1.5'},
    'dividend_yield'  : {'threshold': 3.0,  'direction': 'above', 'label': 'Div Yield > 3%'},
    'debt_to_equity'  : {'threshold': 50,   'direction': 'below', 'label': 'D/E < 50'},
    'earnings_growth' : {'threshold': 5.0,  'direction': 'above', 'label': 'EPS Growth > 5%'},
    'current_ratio'   : {'threshold': 1.5,  'direction': 'above', 'label': 'Current Ratio > 1.5'},
    'roe'             : {'threshold': 12.0, 'direction': 'above', 'label': 'ROE > 12%'},
}

# ── Stock Universe ────────────────────────────────────────────
US_STOCKS = [
    'AAPL','MSFT','GOOGL','AMZN','NVDA','META','TSLA','BRK-B','JPM','V',
    'UNH','XOM','JNJ','WMT','MA','PG','HD','CVX','MRK','ABBV',
    'PEP','KO','AVGO','COST','MCD','BAC','CSCO','CRM','ACN','LIN',
    'TMO','ABT','ORCL','NFLX','AMD','ADBE','DHR','TXN','NEE','PM',
    'UPS','MS','RTX','INTC','QCOM','HON','IBM','GS','CAT','AMGN',
    'INTU','SPGI','BLK','AXP','DE','ELV','GILD','MDT','VRTX','ISRG',
    'MO','SYK','ZTS','REGN','CI','CB','PLD','SO','DUK','MMC',
    'AON','ICE','CME','WM','CL','ITW','EMR','ETN','PH','GD',
    'LMT','NOC','F','GM','TGT','LOW','NKE','SBUX','GE','MMM',
    'MU','LRCX','KLAC','AMAT','ADI','MCHP','ON','STX','WDC','HPQ',
]

HK_STOCKS = [
    '0700.HK','0941.HK','9988.HK','1299.HK','0005.HK','0939.HK','1398.HK',
    '3988.HK','2318.HK','0388.HK','0002.HK','0003.HK','0006.HK',
    '0016.HK','0017.HK','0019.HK','0027.HK','0066.HK','0083.HK','0101.HK',
    '0175.HK','0267.HK','0288.HK','0291.HK','0316.HK','0322.HK','0386.HK',
    '0669.HK','0688.HK','0762.HK','0823.HK','0857.HK','0868.HK','0883.HK',
    '0960.HK','0992.HK','1038.HK','1044.HK','1093.HK','1109.HK','1113.HK',
    '1177.HK','1211.HK','1378.HK','1810.HK','1876.HK','2020.HK','2269.HK',
    '2382.HK',
]

SG_STOCKS = [
    'D05.SI','O39.SI','U11.SI','Z74.SI','C6L.SI','S68.SI','F34.SI',
    'BN4.SI','G13.SI','C38U.SI','A17U.SI','ME8U.SI','N2IU.SI','J36.SI',
    'S63.SI','V03.SI','BS6.SI','H78.SI','U96.SI','C09.SI','S58.SI',
    'T39.SI','Y92.SI','9CI.SI','U14.SI','AWX.SI','5E2.SI','BVA.SI',
    'P40U.SI','AJBU.SI',
]

# ── Agent Functions ───────────────────────────────────────────
def fetch_stock(ticker):
    try:
        info = yf.Ticker(ticker).info
        if not info or info.get('regularMarketPrice') is None and info.get('currentPrice') is None:
            print(f'  SKIP {ticker}: no price data')
            return None
        return {
            'ticker'         : ticker,
            'name'           : info.get('longName') or info.get('shortName', ticker),
            'sector'         : info.get('sector', 'N/A'),
            'pe_ratio'       : info.get('trailingPE'),
            'pb_ratio'       : info.get('priceToBook'),
            'dividend_yield' : (info.get('dividendYield') or 0) * 100,
            'debt_to_equity' : info.get('debtToEquity'),
            'earnings_growth': (info.get('earningsGrowth') or 0) * 100,
            'current_ratio'  : info.get('currentRatio'),
            'roe'            : (info.get('returnOnEquity') or 0) * 100,
        }
    except Exception as e:
        print(f'  ERROR {ticker}: {e}')
        return None

def score_stock(stock):
    if not stock:
        return 0, [], []
    score, passed, failed = 0, [], []
    for metric, config in CRITERIA.items():
        value = stock.get(metric)
        if value is None:
            failed.append(f"{config['label']} (no data)")
            continue
        ok = value < config['threshold'] if config['direction'] == 'below' else value > config['threshold']
        if ok:
            score += 1
            passed.append(f"{config['label']} ({value:.1f})")
        else:
            failed.append(f"{config['label']} ({value:.1f})")
    return score, passed, failed

def screen_market(tickers, label):
    print(f'\n[{label}] Scanning {len(tickers)} stocks...')
    flagged = []
    for i, ticker in enumerate(tickers):
        print(f'  {i+1}/{len(tickers)} {ticker}')
        stock = fetch_stock(ticker)
        score, passed, failed = score_stock(stock)
        if score >= MIN_SCORE_TO_FLAG:
            flagged.append({
                'ticker' : ticker,
                'name'   : stock['name'],
                'sector' : stock['sector'],
                'score'  : score,
                'verdict': '🌟 STRONG BUY' if score >= 6 else '✅ WATCH',
                'passed' : passed,
                'market' : label,
            })
        time.sleep(0.5)
    print(f'[{label}] Done — {len(flagged)} flagged')
    return flagged

def build_email_html(flagged, run_date):
    strong = [s for s in flagged if 'STRONG' in s['verdict']]
    watch  = [s for s in flagged if 'WATCH'  in s['verdict']]

    def rows(stocks):
        r = ''
        for s in sorted(stocks, key=lambda x: -x['score']):
            r += (f"<tr>"
                  f"<td style='padding:8px;font-weight:bold;color:#1a237e'>{s['ticker']}</td>"
                  f"<td style='padding:8px'>{s['name']}</td>"
                  f"<td style='padding:8px;text-align:center'><b>{s['market']}</b></td>"
                  f"<td style='padding:8px'>{s['sector']}</td>"
                  f"<td style='padding:8px;text-align:center;font-weight:bold;font-size:16px'>{s['score']}/7</td>"
                  f"<td style='padding:8px;font-size:12px;color:#2e7d32'>{'<br>'.join(s['passed'])}</td>"
                  f"</tr>")
        return r

    def table(stocks, color):
        if not stocks:
            return '<p style="color:#999"><i>No stocks met this threshold today.</i></p>'
        return (f"<table border='1' cellspacing='0' style='border-collapse:collapse;width:100%;font-size:13px'>"
                f"<tr style='background:{color};color:white'>"
                f"<th style='padding:8px'>Ticker</th><th style='padding:8px'>Name</th>"
                f"<th style='padding:8px'>Market</th><th style='padding:8px'>Sector</th>"
                f"<th style='padding:8px'>Score</th><th style='padding:8px'>Criteria Passed</th></tr>"
                f"{rows(stocks)}</table>")

    return (f"<html><body style='font-family:Arial,sans-serif;color:#333;max-width:900px;margin:auto;padding:20px'>"
            f"<h2 style='color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:8px'>📈 Daily Stock Screener — {run_date}</h2>"
            f"<p style='background:#e8eaf6;padding:12px;border-radius:4px'>"
            f"Screened <b>{len(US_STOCKS)} US</b>, <b>{len(HK_STOCKS)} HK</b>, <b>{len(SG_STOCKS)} SG</b> stocks today.<br>"
            f"<b>{len(flagged)}</b> stocks flagged. &nbsp;|&nbsp; 🌟 Strong Buys: <b>{len(strong)}</b> &nbsp;|&nbsp; ✅ Watch: <b>{len(watch)}</b></p>"
            f"<h3 style='color:#b71c1c'>🌟 Strong Buys — Score 6 or 7 out of 7 ({len(strong)} stocks)</h3>{table(strong,'#b71c1c')}"
            f"<br><h3 style='color:#2e7d32'>✅ Watch List — Score 5 out of 7 ({len(watch)} stocks)</h3>{table(watch,'#2e7d32')}"
            f"<br><p style='font-size:11px;color:#999'>⚠️ For informational purposes only. Not financial advice. Data from Yahoo Finance.</p>"
            f"</body></html>")

def send_email(html, run_date, total):
    if not SENDER_APP_PASSWORD:
        print('❌ GMAIL_APP_PASSWORD secret not set in GitHub!')
        return
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'📈 Daily Stock Screener — {total} stocks flagged | {run_date}'
    msg['From']    = SENDER_EMAIL
    msg['To']      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, 'html'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print(f'✅ Email sent to {RECIPIENT_EMAIL}!')
    except Exception as e:
        print(f'❌ Email failed: {e}')

# ── Main ──────────────────────────────────────────────────────
if __name__ == '__main__':
    run_date = datetime.now().strftime('%d %b %Y')
    print('=' * 56)
    print('  🤖  DAILY STOCK SCREENER AGENT')
    print(f'  Date    : {run_date}')
    print(f'  Markets : US ({len(US_STOCKS)}) | HK ({len(HK_STOCKS)}) | SG ({len(SG_STOCKS)})')
    print('=' * 56)

    all_flagged  = screen_market(US_STOCKS, 'US')
    all_flagged += screen_market(HK_STOCKS, 'HK')
    all_flagged += screen_market(SG_STOCKS, 'SG')

    print(f'\n{"="*56}')
    print(f'  DONE — {len(all_flagged)} stocks flagged')
    print(f'  Strong Buys : {sum(1 for s in all_flagged if "STRONG" in s["verdict"])}')
    print(f'  Watch List  : {sum(1 for s in all_flagged if "WATCH"  in s["verdict"])}')
    print(f'{"="*56}')

    html = build_email_html(all_flagged, run_date)
    send_email(html, run_date, len(all_flagged))
