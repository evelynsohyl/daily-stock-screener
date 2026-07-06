import yfinance as yf
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, date
import time

# Market holidays (US, HK, SG combined) - dates when all markets are closed
# Update this list each year
MARKET_HOLIDAYS = [
    # 2025
    date(2025, 1, 1),   # New Year's Day
    date(2025, 1, 29),  # Lunar New Year (HK/SG)
    date(2025, 1, 30),  # Lunar New Year (HK/SG)
    date(2025, 4, 18),  # Good Friday
    date(2025, 4, 21),  # Easter Monday
    date(2025, 5, 1),   # Labour Day (HK/SG)
    date(2025, 5, 26),  # Memorial Day (US)
    date(2025, 6, 19),  # Juneteenth (US)
    date(2025, 7, 4),   # Independence Day (US)
    date(2025, 9, 1),   # Labor Day (US)
    date(2025, 10, 1),  # National Day (HK)
    date(2025, 11, 27), # Thanksgiving (US)
    date(2025, 12, 25), # Christmas
    date(2025, 12, 26), # Boxing Day (HK/SG)
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 2, 17),  # Lunar New Year (HK/SG)
    date(2026, 2, 18),  # Lunar New Year (HK/SG)
    date(2026, 2, 19),  # Lunar New Year (HK/SG)
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 6),   # Easter Monday
    date(2026, 5, 1),   # Labour Day (HK/SG)
    date(2026, 5, 25),  # Memorial Day (US)
    date(2026, 6, 19),  # Juneteenth (US)
    date(2026, 7, 3),   # Independence Day observed (US)
    date(2026, 9, 7),   # Labor Day (US)
    date(2026, 10, 1),  # National Day (HK)
    date(2026, 11, 26), # Thanksgiving (US)
    date(2026, 12, 25), # Christmas
    date(2026, 12, 26), # Boxing Day (HK/SG)
]

def is_market_holiday():
    today = date.today()
    if today in MARKET_HOLIDAYS:
        print('Today is a market holiday (' + today.strftime('%d %b %Y') + '). Skipping.')
        return True
    return False

SENDER_EMAIL = 'evelynsohyl@gmail.com'
SENDER_APP_PASSWORD = 'sjef izzp kvbk htay'
RECIPIENT_EMAIL = 'evelynsohyl@gmail.com'
MIN_SCORE = 5

CRITERIA_US = {
    'pe_ratio':        {'threshold': 25,   'direction': 'below', 'label': 'P/E < 25'},
    'pb_ratio':        {'threshold': 3.0,  'direction': 'below', 'label': 'P/B < 3.0'},
    'dividend_yield':  {'threshold': 2.0,  'direction': 'above', 'label': 'Div Yield > 2%'},
    'debt_to_equity':  {'threshold': 100,  'direction': 'below', 'label': 'D/E < 100'},
    'earnings_growth': {'threshold': 5.0,  'direction': 'above', 'label': 'EPS Growth > 5%'},
    'current_ratio':   {'threshold': 1.5,  'direction': 'above', 'label': 'Current Ratio > 1.5'},
    'roe':             {'threshold': 15.0, 'direction': 'above', 'label': 'ROE > 15%'},
}

CRITERIA_HKSG = {
    'pe_ratio':        {'threshold': 15,   'direction': 'below', 'label': 'P/E < 15'},
    'pb_ratio':        {'threshold': 1.5,  'direction': 'below', 'label': 'P/B < 1.5'},
    'dividend_yield':  {'threshold': 3.0,  'direction': 'above', 'label': 'Div Yield > 3%'},
    'debt_to_equity':  {'threshold': 50,   'direction': 'below', 'label': 'D/E < 50'},
    'earnings_growth': {'threshold': 5.0,  'direction': 'above', 'label': 'EPS Growth > 5%'},
    'current_ratio':   {'threshold': 1.5,  'direction': 'above', 'label': 'Current Ratio > 1.5'},
    'roe':             {'threshold': 12.0, 'direction': 'above', 'label': 'ROE > 12%'},
}

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
    '0700.HK','0941.HK','9988.HK','1299.HK','0005.HK','0939.HK','1398.HK','3988.HK',
    '2318.HK','0388.HK','0002.HK','0003.HK','0006.HK','0016.HK','0017.HK','0019.HK',
    '0027.HK','0066.HK','0083.HK','0101.HK','0175.HK','0267.HK','0288.HK','0291.HK',
    '0316.HK','0322.HK','0386.HK','0669.HK','0688.HK','0762.HK','0823.HK','0857.HK',
    '0868.HK','0883.HK','0960.HK','0992.HK','1038.HK','1044.HK','1093.HK','1109.HK',
    '1113.HK','1177.HK','1211.HK','1378.HK','1810.HK','1876.HK','2020.HK','2269.HK','2382.HK',
]

SG_STOCKS = [
    'D05.SI','O39.SI','U11.SI','Z74.SI','C6L.SI','S68.SI','F34.SI','BN4.SI','G13.SI',
    'C38U.SI','A17U.SI','ME8U.SI','N2IU.SI','J36.SI','S63.SI','V03.SI','BS6.SI','H78.SI',
    'U96.SI','C09.SI','S58.SI','T39.SI','Y92.SI','9CI.SI','U14.SI','AWX.SI','5E2.SI',
    'BVA.SI','P40U.SI','AJBU.SI',
]


def fetch_stock(ticker):
    try:
        info = yf.Ticker(ticker).info
        if not info or info.get('quoteType') is None:
            return None
        dy = info.get('dividendYield')
        eg = info.get('earningsGrowth')
        return {
            'ticker':          ticker,
            'name':            info.get('longName', ticker),
            'sector':          info.get('sector', 'N/A'),
            'pe_ratio':        info.get('trailingPE'),
            'pb_ratio':        info.get('priceToBook'),
            'dividend_yield':  (dy * 100) if dy else 0.0,
            'debt_to_equity':  info.get('debtToEquity'),
            'earnings_growth': (eg * 100) if eg else None,
            'current_ratio':   info.get('currentRatio'),
            'roe':             (info.get('returnOnEquity') or 0) * 100,
        }
    except Exception as e:
        print('Error ' + ticker + ': ' + str(e))
        return None


def score_stock(stock, criteria):
    if not stock:
        return 0, [], []
    score, passed, failed = 0, [], []
    for key, cfg in criteria.items():
        val = stock.get(key)
        if val is None:
            failed.append(cfg['label'] + ' (no data)')
            continue
        ok = (cfg['direction'] == 'below' and val < cfg['threshold']) or \
             (cfg['direction'] == 'above' and val > cfg['threshold'])
        if ok:
            score += 1
            passed.append(cfg['label'] + ' (' + str(round(val, 1)) + ')')
        else:
            failed.append(cfg['label'] + ' (' + str(round(val, 1)) + ')')
    return score, passed, failed


def screen(tickers, market, criteria):
    print('Scanning ' + market + ' (' + str(len(tickers)) + ' stocks)...')
    results = []
    for i, ticker in enumerate(tickers):
        print('  ' + str(i + 1) + '/' + str(len(tickers)) + ' ' + ticker)
        stock = fetch_stock(ticker)
        score, passed, failed = score_stock(stock, criteria)
        if score >= MIN_SCORE:
            verdict = 'STRONG BUY' if score >= 6 else 'WATCH'
            results.append({
                'ticker':  ticker,
                'name':    stock['name'],
                'market':  market,
                'sector':  stock['sector'],
                'score':   score,
                'verdict': verdict,
                'passed':  passed,
                'failed':  failed,
            })
        time.sleep(0.3)
    print(market + ' done: ' + str(len(results)) + ' flagged')
    return results


def build_html(flagged, date):
    strong = [s for s in flagged if s['verdict'] == 'STRONG BUY']
    watch  = [s for s in flagged if s['verdict'] == 'WATCH']

    def row(s):
        color = '#b71c1c' if s['verdict'] == 'STRONG BUY' else '#2e7d32'
        p = '<br>'.join(['+ ' + x for x in s['passed']])
        f = '<br>'.join(['- ' + x for x in s['failed']])
        return (
            '<tr>'
            '<td style="padding:8px;font-weight:bold;color:' + color + '">' + s['ticker'] + '</td>'
            '<td style="padding:8px">' + s['name'] + '</td>'
            '<td style="padding:8px">' + s['market'] + '</td>'
            '<td style="padding:8px">' + s['sector'] + '</td>'
            '<td style="padding:8px;text-align:center;font-weight:bold;color:' + color + '">' + str(s['score']) + '/7</td>'
            '<td style="padding:8px;font-size:12px;color:green">' + p + '</td>'
            '<td style="padding:8px;font-size:12px;color:#999">' + f + '</td>'
            '</tr>'
        )

    def table(stocks, color):
        if not stocks:
            return '<p style="color:#999">None today.</p>'
        header = (
            '<table style="width:100%;border-collapse:collapse;font-size:13px">'
            '<tr style="background:' + color + ';color:white">'
            '<th style="padding:8px">Ticker</th>'
            '<th style="padding:8px">Name</th>'
            '<th style="padding:8px">Market</th>'
            '<th style="padding:8px">Sector</th>'
            '<th style="padding:8px">Score</th>'
            '<th style="padding:8px">Passed</th>'
            '<th style="padding:8px">Failed</th>'
            '</tr>'
        )
        return header + ''.join([row(s) for s in stocks]) + '</table>'

    summary = (
        'Screened ' + str(len(US_STOCKS)) + ' US, ' +
        str(len(HK_STOCKS)) + ' HK, ' +
        str(len(SG_STOCKS)) + ' SG stocks. ' +
        str(len(flagged)) + ' flagged | Strong Buys: ' + str(len(strong)) +
        ' | Watch: ' + str(len(watch))
    )

    criteria_note = (
        'US criteria: P/E&lt;25, P/B&lt;3.0, Div&gt;2%, D/E&lt;100, EPS&gt;5%, CR&gt;1.5, ROE&gt;15% | '
        'HK/SG criteria: P/E&lt;15, P/B&lt;1.5, Div&gt;3%, D/E&lt;50, EPS&gt;5%, CR&gt;1.5, ROE&gt;12%'
    )

    return (
        '<html><body style="font-family:Arial,sans-serif;color:#333;max-width:960px;margin:auto;padding:20px">'
        '<h2 style="color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:8px">Daily Stock Screener - ' + date + '</h2>'
        '<p style="background:#e8eaf6;padding:12px;border-radius:4px">' + summary + '<br><small>' + criteria_note + '</small></p>'
        '<h3 style="color:#b71c1c">Strong Buys (score 6-7) - ' + str(len(strong)) + ' stocks</h3>' + table(strong, '#b71c1c') +
        '<br><h3 style="color:#2e7d32">Watch List (score 5) - ' + str(len(watch)) + ' stocks</h3>' + table(watch, '#2e7d32') +
        '<br><p style="font-size:11px;color:#999">For informational purposes only. Not financial advice. Data from Yahoo Finance.</p>'
        '</body></html>'
    )


def send_email(html, date, total):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Daily Stock Screener - ' + str(total) + ' flagged - ' + date
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, 'html'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            s.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print('Email sent!')
    except Exception as e:
        print('Email error: ' + str(e))


if __name__ == '__main__':
    if is_market_holiday():
        exit(0)
    date = datetime.now().strftime('%d %b %Y')
    print('Daily Stock Screener - ' + date)
    flagged  = screen(US_STOCKS, 'US', CRITERIA_US)
    flagged += screen(HK_STOCKS, 'HK', CRITERIA_HKSG)
    flagged += screen(SG_STOCKS, 'SG', CRITERIA_HKSG)
    print('Total flagged: ' + str(len(flagged)))
    html = build_html(flagged, date)
    send_email(html, date, len(flagged))
