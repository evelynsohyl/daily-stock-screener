import yfinance as yf
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, date
import time
import warnings
warnings.filterwarnings('ignore')

# -- Market holidays (US, HK, SG) - skip on these days ----------
MARKET_HOLIDAYS = [
    date(2025, 1, 1),   date(2025, 1, 29),  date(2025, 1, 30),
    date(2025, 4, 18),  date(2025, 4, 21),  date(2025, 5, 1),
    date(2025, 5, 26),  date(2025, 6, 19),  date(2025, 7, 4),
    date(2025, 9, 1),   date(2025, 10, 1),  date(2025, 11, 27),
    date(2025, 12, 25), date(2025, 12, 26),
    date(2026, 1, 1),   date(2026, 2, 17),  date(2026, 2, 18),
    date(2026, 2, 19),  date(2026, 4, 3),   date(2026, 4, 6),
    date(2026, 5, 1),   date(2026, 5, 25),  date(2026, 6, 19),
    date(2026, 7, 3),   date(2026, 9, 7),   date(2026, 10, 1),
    date(2026, 11, 26), date(2026, 12, 25), date(2026, 12, 26),
]

def is_market_holiday():
    today = date.today()
    if today in MARKET_HOLIDAYS:
        print('Today is a market holiday (' + today.strftime('%d %b %Y') + '). Skipping.')
        return True
    return False

# -- Configuration -----------------------------------------------
SENDER_EMAIL        = 'evelynsohyl@gmail.com'
SENDER_APP_PASSWORD = 'sjef izzp kvbk htay'
RECIPIENT_EMAIL     = 'evelynsohyl@gmail.com'
MIN_SCORE           = 5

# -- Screening Criteria ------------------------------------------
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

# -- Stock Universe ----------------------------------------------
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

# -- Fetch stock data --------------------------------------------
def fetch_stock(ticker):
    try:
        t    = yf.Ticker(ticker)
        info = t.info
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
            'analyst_rating':  info.get('recommendationKey', ''),
            'target_price':    info.get('targetMeanPrice'),
            'current_price':   info.get('currentPrice') or info.get('regularMarketPrice'),
            'revenue_growth':  (info.get('revenueGrowth') or 0) * 100,
            'profit_margins':  (info.get('profitMargins') or 0) * 100,
            'insider_pct':     (info.get('heldPercentInsiders') or 0) * 100,
            'short_ratio':     info.get('shortRatio'),
            'beta':            info.get('beta'),
            'info':            info,
            'ticker_obj':      t,
        }
    except Exception as e:
        print('Error ' + ticker + ': ' + str(e))
        return None

# -- Score stock -------------------------------------------------
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

# -- Price trend check (50-day vs 200-day MA) --------------------
def get_trend(ticker_obj):
    try:
        hist = ticker_obj.history(period='1y')
        if hist is None or len(hist) < 50:
            return 'unknown', 0.0
        close = hist['Close']
        ma50  = float(close.tail(50).mean())
        ma200 = float(close.mean()) if len(close) >= 200 else float(close.mean())
        current = float(close.iloc[-1])
        pct_from_52w_low = ((current - float(close.min())) / float(close.min())) * 100
        if ma50 > ma200:
            trend = 'uptrend'
        elif ma50 < ma200 * 0.97:
            trend = 'downtrend'
        else:
            trend = 'sideways'
        return trend, round(pct_from_52w_low, 1)
    except:
        return 'unknown', 0.0

# -- Sanity checks -----------------------------------------------
def sanity_checks(stock):
    """
    Run additional checks beyond the 7 criteria.
    Returns a list of green flags, red flags, and a recommendation.
    """
    green = []
    red   = []

    # 1. Analyst consensus
    rating = (stock.get('analyst_rating') or '').lower()
    if rating in ('buy', 'strong_buy'):
        green.append('Analysts rate: ' + rating.replace('_', ' ').title())
    elif rating in ('sell', 'strong_sell', 'underperform'):
        red.append('Analysts rate: ' + rating.replace('_', ' ').title())

    # 2. Upside to analyst target price
    current = stock.get('current_price')
    target  = stock.get('target_price')
    if current and target and current > 0:
        upside = (target - current) / current * 100
        if upside >= 15:
            green.append('Analyst target upside: +' + str(round(upside, 1)) + '%')
        elif upside < 0:
            red.append('Trading above analyst target by ' + str(round(-upside, 1)) + '%')

    # 3. Price trend (50-day vs 200-day MA)
    trend, pct_52w = get_trend(stock.get('ticker_obj'))
    if trend == 'uptrend':
        green.append('Price trend: uptrend (50MA > 200MA)')
    elif trend == 'downtrend':
        red.append('Price trend: downtrend (50MA < 200MA)')
    else:
        green.append('Price trend: sideways (neutral)')

    # 4. Distance from 52-week low (buying near lows is good for value)
    if pct_52w <= 20:
        green.append('Near 52-week low (within 20%) - potential value entry')
    elif pct_52w >= 80:
        red.append('Near 52-week high (+' + str(pct_52w) + '% from low) - less margin of safety')

    # 5. Revenue growth
    rev_growth = stock.get('revenue_growth') or 0
    if rev_growth >= 5:
        green.append('Revenue growing: +' + str(round(rev_growth, 1)) + '%')
    elif rev_growth < -5:
        red.append('Revenue shrinking: ' + str(round(rev_growth, 1)) + '%')

    # 6. Profit margin
    margin = stock.get('profit_margins') or 0
    if margin >= 10:
        green.append('Healthy profit margin: ' + str(round(margin, 1)) + '%')
    elif margin < 0:
        red.append('Negative profit margin: ' + str(round(margin, 1)) + '%')

    # 7. Insider ownership (skin in the game)
    insider = stock.get('insider_pct') or 0
    if insider >= 5:
        green.append('Insider ownership: ' + str(round(insider, 1)) + '% (management invested)')

    # 8. Short interest (high short ratio = market betting against it)
    short = stock.get('short_ratio') or 0
    if short >= 10:
        red.append('High short interest ratio: ' + str(round(short, 1)) + ' days to cover')

    # 9. Beta (volatility risk)
    beta = stock.get('beta') or 1
    if beta > 2:
        red.append('High volatility: beta = ' + str(round(beta, 2)))
    elif 0.5 <= beta <= 1.5:
        green.append('Stable volatility: beta = ' + str(round(beta, 2)))

    # -- Final recommendation ------------------------------------
    green_count = len(green)
    red_count   = len(red)

    if red_count == 0 and green_count >= 4:
        recommendation = 'BUY'
        reason = 'Strong fundamentals, no red flags, multiple positive signals.'
    elif red_count >= 3:
        recommendation = 'AVOID'
        reason = 'Multiple red flags detected. Wait for conditions to improve.'
    elif red_count >= 1 and green_count >= red_count:
        recommendation = 'WAIT'
        reason = 'Some concerns present. Monitor and wait for a better entry.'
    elif red_count == 0 and green_count >= 2:
        recommendation = 'BUY'
        reason = 'Good fundamentals with positive signals.'
    else:
        recommendation = 'WAIT'
        reason = 'Insufficient positive signals to confirm entry.'

    return green, red, recommendation, reason

# -- Screen market -----------------------------------------------
def screen(tickers, market, criteria):
    print('Scanning ' + market + ' (' + str(len(tickers)) + ' stocks)...')
    results = []
    for i, ticker in enumerate(tickers):
        print('  ' + str(i + 1) + '/' + str(len(tickers)) + ' ' + ticker)
        stock = fetch_stock(ticker)
        score, passed, failed = score_stock(stock, criteria)
        if score >= MIN_SCORE:
            green, red, rec, reason = sanity_checks(stock)
            verdict = 'STRONG BUY' if score >= 6 else 'WATCH'
            results.append({
                'ticker':     ticker,
                'name':       stock['name'],
                'market':     market,
                'sector':     stock['sector'],
                'score':      score,
                'verdict':    verdict,
                'passed':     passed,
                'failed':     failed,
                'green':      green,
                'red':        red,
                'rec':        rec,
                'reason':     reason,
                'price':      stock.get('current_price'),
                'target':     stock.get('target_price'),
            })
            print('    -> ' + rec + ' | green=' + str(len(green)) + ' red=' + str(len(red)))
        time.sleep(0.4)
    print(market + ' done: ' + str(len(results)) + ' flagged')
    return results

# -- Build email HTML --------------------------------------------
def build_html(flagged, date_str):
    buy    = [s for s in flagged if s['rec'] == 'BUY']
    wait   = [s for s in flagged if s['rec'] == 'WAIT']
    avoid  = [s for s in flagged if s['rec'] == 'AVOID']

    rec_colors = {'BUY': '#1b5e20', 'WAIT': '#e65100', 'AVOID': '#b71c1c'}
    rec_bg     = {'BUY': '#e8f5e9', 'WAIT': '#fff3e0', 'AVOID': '#ffebee'}

    def price_row(s):
        if s['price'] and s['target']:
            upside = (s['target'] - s['price']) / s['price'] * 100
            return ('Current: ' + str(round(s['price'], 2)) +
                    ' | Target: ' + str(round(s['target'], 2)) +
                    ' | Upside: ' + str(round(upside, 1)) + '%')
        return ''

    def flag_list(items, color):
        if not items:
            return '<span style="color:#999">None</span>'
        return ''.join(['<span style="color:' + color + ';display:block;font-size:12px">' + x + '</span>' for x in items])

    def row(s):
        rc = rec_colors[s['rec']]
        rb = rec_bg[s['rec']]
        sc_color = '#b71c1c' if s['verdict'] == 'STRONG BUY' else '#2e7d32'
        passed_str = ''.join(['<span style="color:green;display:block;font-size:11px">+ ' + p + '</span>' for p in s['passed']])
        failed_str = ''.join(['<span style="color:#bbb;display:block;font-size:11px">- ' + f + '</span>' for f in s['failed']])
        pr = price_row(s)
        return (
            '<tr style="background:' + rb + ';border-bottom:1px solid #eee">'
            '<td style="padding:10px;font-weight:bold;font-size:14px">'
            + s['ticker'] + '<br><span style="font-size:11px;font-weight:normal;color:#555">' + s['market'] + ' | ' + s['sector'] + '</span>'
            + ('<br><span style="font-size:11px;color:#777">' + pr + '</span>' if pr else '') +
            '</td>'
            '<td style="padding:10px;font-size:12px;color:#333">' + s['name'] + '</td>'
            '<td style="padding:10px;text-align:center;font-weight:bold;color:' + sc_color + '">' + str(s['score']) + '/7</td>'
            '<td style="padding:10px">' + passed_str + failed_str + '</td>'
            '<td style="padding:10px">'
            + flag_list(s['green'], '#2e7d32') +
            flag_list(s['red'],   '#c62828') +
            '</td>'
            '<td style="padding:12px;text-align:center">'
            '<span style="background:' + rc + ';color:white;padding:6px 14px;border-radius:20px;font-weight:bold;font-size:13px">'
            + s['rec'] + '</span>'
            '<br><span style="font-size:11px;color:#555;display:block;margin-top:4px">' + s['reason'] + '</span>'
            '</td>'
            '</tr>'
        )

    def section(stocks, title, color):
        if not stocks:
            return '<p style="color:#999;margin-left:8px">None today.</p>'
        header = (
            '<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:16px">'
            '<tr style="background:' + color + ';color:white">'
            '<th style="padding:10px;text-align:left">Ticker</th>'
            '<th style="padding:10px;text-align:left">Name</th>'
            '<th style="padding:10px">Score</th>'
            '<th style="padding:10px;text-align:left">Criteria</th>'
            '<th style="padding:10px;text-align:left">Sanity Checks</th>'
            '<th style="padding:10px;text-align:center">Recommendation</th>'
            '</tr>'
        )
        return header + ''.join([row(s) for s in stocks]) + '</table>'

    summary = (
        'Screened ' + str(len(US_STOCKS)) + ' US, ' +
        str(len(HK_STOCKS)) + ' HK, ' +
        str(len(SG_STOCKS)) + ' SG stocks. ' +
        str(len(flagged)) + ' passed value criteria. | '
        'BUY: ' + str(len(buy)) + ' | WAIT: ' + str(len(wait)) + ' | AVOID: ' + str(len(avoid))
    )

    legend = (
        '<div style="background:#f9f9f9;border:1px solid #ddd;border-radius:6px;padding:12px;margin-bottom:20px;font-size:12px">'
        '<b>How to read this report:</b><br>'
        '<span style="color:#1b5e20;font-weight:bold">BUY</span> - Fundamentals strong, sanity checks pass. Consider buying a position.<br>'
        '<span style="color:#e65100;font-weight:bold">WAIT</span> - Fundamentals good but some concerns. Monitor and wait for better entry.<br>'
        '<span style="color:#b71c1c;font-weight:bold">AVOID</span> - Multiple red flags. Skip for now even though fundamentals pass.<br>'
        '<br><b>Sanity checks include:</b> analyst rating, upside to target price, price trend (50MA vs 200MA), '
        'distance from 52-week low, revenue growth, profit margin, insider ownership, short interest, and beta.'
        '</div>'
    )

    return (
        '<html><body style="font-family:Arial,sans-serif;color:#333;max-width:1000px;margin:auto;padding:20px">'
        '<h2 style="color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:8px">Daily Stock Screener - ' + date_str + '</h2>'
        '<p style="background:#e8eaf6;padding:12px;border-radius:4px">' + summary + '</p>'
        + legend +
        '<h3 style="color:#1b5e20">BUY - ' + str(len(buy)) + ' stocks</h3>' + section(buy, 'BUY', '#1b5e20') +
        '<h3 style="color:#e65100">WAIT - ' + str(len(wait)) + ' stocks</h3>' + section(wait, 'WAIT', '#e65100') +
        '<h3 style="color:#b71c1c">AVOID - ' + str(len(avoid)) + ' stocks</h3>' + section(avoid, 'AVOID', '#b71c1c') +
        '<br><p style="font-size:11px;color:#999">For informational purposes only. Not financial advice. '
        'Data from Yahoo Finance. Always do your own research before investing.</p>'
        '</body></html>'
    )

# -- Send email --------------------------------------------------
def send_email(html, date_str, buy_count, total):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Stock Screener - ' + str(buy_count) + ' BUY signals - ' + date_str
    msg['From']    = SENDER_EMAIL
    msg['To']      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, 'html'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            s.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print('Email sent!')
    except Exception as e:
        print('Email error: ' + str(e))

# -- Main --------------------------------------------------------
if __name__ == '__main__':
    if is_market_holiday():
        exit(0)
    date_str = datetime.now().strftime('%d %b %Y')
    print('Daily Stock Screener - ' + date_str)
    flagged  = screen(US_STOCKS, 'US', CRITERIA_US)
    flagged += screen(HK_STOCKS, 'HK', CRITERIA_HKSG)
    flagged += screen(SG_STOCKS, 'SG', CRITERIA_HKSG)
    buy_count = sum(1 for s in flagged if s['rec'] == 'BUY')
    print('Total flagged: ' + str(len(flagged)) + ' | BUY: ' + str(buy_count))
    html = build_html(flagged, date_str)
    send_email(html, date_str, buy_count, len(flagged))
