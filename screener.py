import yfinance as yf
import smtplib
import json
import os
import base64
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime, date, timedelta
from collections import Counter
import time
import warnings
warnings.filterwarnings('ignore')

# ================================================================
# CONFIGURATION
# ================================================================
SENDER_EMAIL        = 'evelynsohyl@gmail.com'
SENDER_APP_PASSWORD = 'sjef izzp kvbk htay'
RECIPIENT_EMAIL     = 'evelynsohyl@gmail.com'
MIN_SCORE           = 5
WATCHLIST_FILE      = 'watchlist_history.json'
PORTFOLIO_FILE      = 'portfolio.json'

# ================================================================
# MARKET HOLIDAYS
# ================================================================
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
        print('Today is a market holiday. Skipping.')
        return True
    return False

# ================================================================
# SCREENING CRITERIA
# ================================================================
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

# ================================================================
# STOCK UNIVERSE
# ================================================================
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

# ================================================================
# MARKET COLOUR: Fear & Greed + VIX
# ================================================================
def get_fear_greed():
    try:
        r = requests.get('https://production.dataviz.cnn.io/index/fearandgreed/graphdata', timeout=8)
        data = r.json()
        score = float(data['fear_and_greed']['score'])
        rating = data['fear_and_greed']['rating']
        prev_close = float(data['fear_and_greed']['previous_close'])
        return {'score': round(score, 1), 'rating': rating, 'prev': round(prev_close, 1)}
    except Exception as e:
        print('Fear & Greed error: ' + str(e))
        return None

def get_vix():
    try:
        vix = yf.Ticker('^VIX')
        info = vix.info
        current = info.get('regularMarketPrice') or info.get('previousClose')
        hist = vix.history(period='1mo')
        avg30 = float(hist['Close'].mean()) if len(hist) > 0 else None
        return {'current': round(current, 2), 'avg30': round(avg30, 2) if avg30 else None}
    except Exception as e:
        print('VIX error: ' + str(e))
        return None

def get_market_colour():
    fg  = get_fear_greed()
    vix = get_vix()
    signals = []
    dip_opportunity = False
    color = '#1a237e'

    if fg:
        score = fg['score']
        if score <= 25:
            signals.append('Fear & Greed: ' + str(score) + ' - EXTREME FEAR - classic buy-the-dip zone')
            dip_opportunity = True
            color = '#b71c1c'
        elif score <= 45:
            signals.append('Fear & Greed: ' + str(score) + ' - FEAR - market oversold, watch for entries')
            dip_opportunity = True
            color = '#e65100'
        elif score >= 75:
            signals.append('Fear & Greed: ' + str(score) + ' - EXTREME GREED - market overbought, be cautious')
            color = '#6a1b9a'
        elif score >= 55:
            signals.append('Fear & Greed: ' + str(score) + ' - GREED - elevated, reduce new positions')
        else:
            signals.append('Fear & Greed: ' + str(score) + ' - NEUTRAL - normal market conditions')

    if vix:
        v = vix['current']
        avg = vix['avg30']
        if v >= 30:
            signals.append('VIX: ' + str(v) + ' - HIGH FEAR / market stress - strong buy-the-dip signal')
            dip_opportunity = True
        elif v >= 20:
            signals.append('VIX: ' + str(v) + ' - ELEVATED volatility - proceed with caution')
        else:
            signals.append('VIX: ' + str(v) + ' - LOW volatility - calm market')
        if avg:
            signals.append('VIX 30-day avg: ' + str(avg))

    return {'signals': signals, 'dip': dip_opportunity, 'color': color, 'fg': fg, 'vix': vix}

# ================================================================
# MINI PRICE CHART
# ================================================================
def get_mini_chart(ticker):
    try:
        hist = yf.Ticker(ticker).history(period='6mo')
        if hist is None or len(hist) < 20:
            return None
        fig, ax = plt.subplots(figsize=(4, 1.5))
        fig.patch.set_facecolor('#f9f9f9')
        ax.set_facecolor('#f9f9f9')
        close = hist['Close']
        color = '#2e7d32' if float(close.iloc[-1]) >= float(close.iloc[0]) else '#c62828'
        ax.plot(hist.index, close, color=color, linewidth=1.5)
        ax.fill_between(hist.index, close, float(close.min()), alpha=0.1, color=color)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=80, bbox_inches='tight', pad_inches=0.05)
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')
    except:
        return None

# ================================================================
# WATCHLIST MEMORY
# ================================================================
def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}

def save_watchlist(current_tickers):
    today = date.today().isoformat()
    history = load_watchlist()
    history[today] = current_tickers
    # Keep only last 30 days
    keys = sorted(history.keys())[-30:]
    history = {k: history[k] for k in keys}
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump(history, f)

def get_watchlist_status(ticker, history):
    dates = sorted(history.keys())
    if len(dates) < 2:
        return 'new'
    yesterday = dates[-1] if dates else None
    if yesterday and ticker in history.get(yesterday, []):
        return 'returning'
    for d in dates[:-1]:
        if ticker in history.get(d, []):
            return 'returning'
    return 'new'

# ================================================================
# PORTFOLIO TRACKER
# ================================================================
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE) as f:
                return json.load(f)
        except:
            pass
    return []

def get_portfolio_pnl():
    portfolio = load_portfolio()
    if not portfolio:
        return []
    results = []
    for pos in portfolio:
        try:
            ticker = pos['ticker']
            buy_price = pos['buy_price']
            buy_date  = pos['buy_date']
            shares    = pos.get('shares', 1)
            info = yf.Ticker(ticker).info
            current = info.get('regularMarketPrice') or info.get('currentPrice')
            if current:
                pnl_pct = (current - buy_price) / buy_price * 100
                pnl_val = (current - buy_price) * shares
                results.append({
                    'ticker':    ticker,
                    'buy_price': buy_price,
                    'buy_date':  buy_date,
                    'current':   round(current, 2),
                    'pnl_pct':   round(pnl_pct, 2),
                    'pnl_val':   round(pnl_val, 2),
                    'shares':    shares,
                })
        except Exception as e:
            print('Portfolio error ' + pos.get('ticker','?') + ': ' + str(e))
    return results

# ================================================================
# DCF FAIR VALUE (simplified)
# ================================================================
def dcf_fair_value(info):
    try:
        eps = info.get('trailingEps')
        growth = (info.get('earningsGrowth') or 0)
        pe = info.get('trailingPE')
        if not eps or eps <= 0:
            return None
        # Simple Graham Number: sqrt(22.5 * EPS * BV)
        bv = info.get('bookValue')
        if bv and bv > 0 and eps > 0:
            graham = (22.5 * eps * bv) ** 0.5
            return round(graham, 2)
        return None
    except:
        return None

# ================================================================
# NEWS SENTIMENT (recent headlines via yfinance)
# ================================================================
def get_news_sentiment(ticker_obj):
    try:
        news = ticker_obj.news
        if not news:
            return [], 'neutral'
        headlines = []
        neg_words = ['downgrade','cut','miss','loss','decline','fall','drop','warn','risk',
                     'lawsuit','fraud','recall','investigation','layoff','bankruptcy','default']
        pos_words = ['upgrade','beat','record','growth','profit','raise','expand','strong',
                     'buy','outperform','dividend','acquisition','partnership']
        neg_count = 0
        pos_count = 0
        for item in news[:5]:
            # yfinance new structure: title nested under item['content']['title']
            content = item.get('content', {})
            title = (content.get('title', '') if isinstance(content, dict) else '') or item.get('title', '')
            if not title:
                continue
            headlines.append(title)
            title_lower = title.lower()
            if any(w in title_lower for w in neg_words):
                neg_count += 1
            if any(w in title_lower for w in pos_words):
                pos_count += 1
        if neg_count >= 2:
            sentiment = 'negative'
        elif pos_count >= 2:
            sentiment = 'positive'
        else:
            sentiment = 'neutral'
        return headlines, sentiment
    except:
        return [], 'neutral'

# ================================================================
# EARNINGS & DIVIDEND CALENDAR
# ================================================================
def get_upcoming_events(ticker_obj):
    events = []
    try:
        cal = ticker_obj.calendar
        if cal is not None and not cal.empty:
            if 'Earnings Date' in cal.index:
                ed = cal.loc['Earnings Date']
                if hasattr(ed, '__iter__'):
                    for d in ed:
                        try:
                            days = (d.date() - date.today()).days
                            if 0 <= days <= 21:
                                events.append('Earnings in ' + str(days) + ' days (' + d.strftime('%d %b') + ') - higher risk')
                        except:
                            pass
    except:
        pass
    try:
        info = ticker_obj.info
        ex_div = info.get('exDividendDate')
        if ex_div:
            ex_date = date.fromtimestamp(ex_div)
            days = (ex_date - date.today()).days
            if 0 <= days <= 30:
                events.append('Ex-dividend in ' + str(days) + ' days (' + ex_date.strftime('%d %b') + ') - buy before to capture dividend')
    except:
        pass
    return events

# ================================================================
# FETCH STOCK DATA
# ================================================================
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
            'graham_value':    dcf_fair_value(info),
            'info':            info,
            'ticker_obj':      t,
        }
    except Exception as e:
        print('Error ' + ticker + ': ' + str(e))
        return None

# ================================================================
# SCORE STOCK
# ================================================================
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

# ================================================================
# PRICE TREND
# ================================================================
def get_trend(ticker_obj):
    try:
        hist = ticker_obj.history(period='1y')
        if hist is None or len(hist) < 50:
            return 'unknown', 0.0
        close = hist['Close']
        ma50  = float(close.tail(50).mean())
        ma200 = float(close.mean())
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

# ================================================================
# SANITY CHECKS
# ================================================================
def sanity_checks(stock):
    green = []
    red   = []

    rating = (stock.get('analyst_rating') or '').lower()
    if rating in ('buy', 'strong_buy'):
        green.append('Analysts: ' + rating.replace('_', ' ').title())
    elif rating in ('sell', 'strong_sell', 'underperform'):
        red.append('Analysts: ' + rating.replace('_', ' ').title())

    current = stock.get('current_price')
    target  = stock.get('target_price')
    if current and target and current > 0:
        upside = (target - current) / current * 100
        if upside >= 15:
            green.append('Target upside: +' + str(round(upside, 1)) + '%')
        elif upside < 0:
            red.append('Above analyst target by ' + str(round(-upside, 1)) + '%')

    trend, pct_52w = get_trend(stock.get('ticker_obj'))
    if trend == 'uptrend':
        green.append('Trend: uptrend (50MA > 200MA)')
    elif trend == 'downtrend':
        red.append('Trend: downtrend (50MA < 200MA)')
    else:
        green.append('Trend: sideways (neutral)')

    if pct_52w <= 20:
        green.append('Near 52-week low (' + str(pct_52w) + '% above) - value entry')
    elif pct_52w >= 80:
        red.append('Near 52-week high (+' + str(pct_52w) + '% from low)')

    rev_growth = stock.get('revenue_growth') or 0
    if rev_growth >= 5:
        green.append('Revenue growing: +' + str(round(rev_growth, 1)) + '%')
    elif rev_growth < -5:
        red.append('Revenue shrinking: ' + str(round(rev_growth, 1)) + '%')

    margin = stock.get('profit_margins') or 0
    if margin >= 10:
        green.append('Profit margin: ' + str(round(margin, 1)) + '%')
    elif margin < 0:
        red.append('Negative margin: ' + str(round(margin, 1)) + '%')

    insider = stock.get('insider_pct') or 0
    if insider >= 5:
        green.append('Insider ownership: ' + str(round(insider, 1)) + '%')

    short = stock.get('short_ratio') or 0
    if short >= 10:
        red.append('High short interest: ' + str(round(short, 1)) + ' days')

    beta = stock.get('beta') or 1
    if beta > 2:
        red.append('High beta: ' + str(round(beta, 2)))
    elif 0.5 <= beta <= 1.5:
        green.append('Stable beta: ' + str(round(beta, 2)))

    graham = stock.get('graham_value')
    if graham and current and current > 0:
        margin_of_safety = (graham - current) / current * 100
        if margin_of_safety >= 20:
            green.append('Graham value: ' + str(graham) + ' (+' + str(round(margin_of_safety, 1)) + '% margin of safety)')
        elif margin_of_safety < -20:
            red.append('Trading above Graham value by ' + str(round(-margin_of_safety, 1)) + '%')

    headlines, sentiment = get_news_sentiment(stock.get('ticker_obj'))
    if sentiment == 'negative':
        red.append('Recent news: negative sentiment detected')
    elif sentiment == 'positive':
        green.append('Recent news: positive sentiment')

    events = get_upcoming_events(stock.get('ticker_obj'))
    for ev in events:
        if 'Earnings' in ev:
            red.append(ev)
        else:
            green.append(ev)

    green_count = len(green)
    red_count   = len(red)

    if red_count == 0 and green_count >= 4:
        rec = 'BUY'
        reason = 'Strong fundamentals, no red flags, multiple positive signals.'
    elif red_count >= 3:
        rec = 'AVOID'
        reason = 'Multiple red flags. Wait for conditions to improve.'
    elif red_count >= 1 and green_count >= red_count:
        rec = 'WAIT'
        reason = 'Some concerns. Monitor and wait for better entry.'
    elif red_count == 0 and green_count >= 2:
        rec = 'BUY'
        reason = 'Good fundamentals with positive signals.'
    else:
        rec = 'WAIT'
        reason = 'Insufficient positive signals to confirm entry.'

    return green, red, rec, reason, headlines

# ================================================================
# SCREEN MARKET
# ================================================================
def screen(tickers, market, criteria, wl_history):
    print('Scanning ' + market + ' (' + str(len(tickers)) + ' stocks)...')
    results = []
    for i, ticker in enumerate(tickers):
        print('  ' + str(i + 1) + '/' + str(len(tickers)) + ' ' + ticker)
        stock = fetch_stock(ticker)
        sc, passed, failed = score_stock(stock, criteria)
        if sc >= MIN_SCORE:
            green, red, rec, reason, headlines = sanity_checks(stock)
            verdict = 'STRONG BUY' if sc >= 6 else 'WATCH'
            wl_status = get_watchlist_status(ticker, wl_history)
            chart_b64 = get_mini_chart(ticker)
            results.append({
                'ticker':     ticker,
                'name':       stock['name'],
                'market':     market,
                'sector':     stock['sector'],
                'score':      sc,
                'verdict':    verdict,
                'passed':     passed,
                'failed':     failed,
                'green':      green,
                'red':        red,
                'rec':        rec,
                'reason':     reason,
                'headlines':  headlines,
                'wl_status':  wl_status,
                'chart':      chart_b64,
                'price':      stock.get('current_price'),
                'target':     stock.get('target_price'),
                'graham':     stock.get('graham_value'),
            })
            print('    -> ' + rec + ' (' + wl_status + ')')
        time.sleep(0.5)
    return results

# ================================================================
# BUILD EMAIL HTML
# ================================================================
def build_html(flagged, date_str, market_colour, portfolio_pnl, wl_history):
    buy   = [s for s in flagged if s['rec'] == 'BUY']
    wait  = [s for s in flagged if s['rec'] == 'WAIT']
    avoid = [s for s in flagged if s['rec'] == 'AVOID']

    # Sector concentration
    sector_counts = Counter(s['sector'] for s in buy)
    sector_warning = ''
    for sector, cnt in sector_counts.items():
        if cnt >= 3:
            sector_warning += ('<div style="background:#fff3e0;border-left:4px solid #e65100;padding:8px;margin:4px 0;font-size:12px">'
                               'Sector concentration: ' + str(cnt) + ' BUY signals in <b>' + sector + '</b> - consider diversifying</div>')

    rec_colors = {'BUY': '#1b5e20', 'WAIT': '#e65100', 'AVOID': '#b71c1c'}
    rec_bg     = {'BUY': '#f1f8e9', 'WAIT': '#fff8f0', 'AVOID': '#fff0f0'}

    def stock_card(s):
        rc = rec_colors[s['rec']]
        rb = rec_bg[s['rec']]
        new_badge = ('<span style="background:#1a237e;color:white;font-size:10px;padding:2px 6px;border-radius:10px;margin-left:6px">NEW</span>'
                     if s['wl_status'] == 'new' else
                     '<span style="background:#555;color:white;font-size:10px;padding:2px 6px;border-radius:10px;margin-left:6px">RETURNING</span>')
        price_line = ''
        if s['price'] and s['target']:
            upside = (s['target'] - s['price']) / s['price'] * 100
            price_line = ('<div style="font-size:12px;color:#555;margin-top:2px">Price: ' +
                          str(round(s['price'], 2)) + ' | Analyst target: ' + str(round(s['target'], 2)) +
                          ' | Upside: ' + str(round(upside, 1)) + '%</div>')
        graham_line = ''
        if s['graham'] and s['price'] and s['price'] > 0:
            mos = (s['graham'] - s['price']) / s['price'] * 100
            mos_color = '#2e7d32' if mos >= 0 else '#c62828'
            graham_line = ('<div style="font-size:12px;color:' + mos_color + ';margin-top:2px">Graham value: ' +
                           str(s['graham']) + ' | Margin of safety: ' + str(round(mos, 1)) + '%</div>')
        chart_img = ''
        if s['chart']:
            cid = 'chart_' + s['ticker'].replace('.', '_').replace('-', '_')
            chart_img = '<img src="cid:' + cid + '" style="width:200px;height:75px;margin-top:6px;border-radius:4px">'
        passed_html = ''.join(['<span style="color:#2e7d32;font-size:11px;display:block">+ ' + p + '</span>' for p in s['passed']])
        failed_html = ''.join(['<span style="color:#bbb;font-size:11px;display:block">- ' + f + '</span>' for f in s['failed']])
        green_html  = ''.join(['<span style="color:#2e7d32;font-size:11px;display:block">&#10003; ' + g + '</span>' for g in s['green']])
        red_html    = ''.join(['<span style="color:#c62828;font-size:11px;display:block">&#10007; ' + r + '</span>' for r in s['red']])
        news_html = ''
        if s['headlines']:
            news_html = ('<div style="margin-top:6px;font-size:11px;color:#666"><b>Recent news:</b><br>' +
                         '<br>'.join(['&bull; ' + h for h in s['headlines'][:3]]) + '</div>')
        return (
            '<tr style="background:' + rb + ';border-bottom:2px solid #eee;vertical-align:top">'
            '<td style="padding:12px;min-width:160px">'
            '<div style="font-size:16px;font-weight:bold">' + s['ticker'] + new_badge + '</div>'
            '<div style="font-size:12px;color:#555">' + s['name'] + '</div>'
            '<div style="font-size:11px;color:#888">' + s['market'] + ' | ' + s['sector'] + '</div>'
            + price_line + graham_line + chart_img +
            '</td>'
            '<td style="padding:12px;min-width:120px">'
            '<div style="font-size:13px;font-weight:bold;color:' + ('#b71c1c' if s['verdict']=='STRONG BUY' else '#2e7d32') + '">' + str(s['score']) + '/7</div>'
            + passed_html + failed_html +
            '</td>'
            '<td style="padding:12px;min-width:180px">' + green_html + red_html + '</td>'
            '<td style="padding:12px;min-width:120px">' + news_html + '</td>'
            '<td style="padding:12px;text-align:center;min-width:100px">'
            '<div style="background:' + rc + ';color:white;padding:8px 16px;border-radius:20px;font-weight:bold;font-size:14px;display:inline-block">' + s['rec'] + '</div>'
            '<div style="font-size:11px;color:#555;margin-top:4px">' + s['reason'] + '</div>'
            '</td>'
            '</tr>'
        )

    def section(stocks, title, color):
        if not stocks:
            return '<p style="color:#999;margin-left:8px;font-size:13px">None today.</p>'
        tbl = (
            '<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px">'
            '<tr style="background:' + color + ';color:white">'
            '<th style="padding:10px;text-align:left">Stock</th>'
            '<th style="padding:10px;text-align:left">Score & Criteria</th>'
            '<th style="padding:10px;text-align:left">Sanity Checks</th>'
            '<th style="padding:10px;text-align:left">News</th>'
            '<th style="padding:10px;text-align:center">Action</th>'
            '</tr>'
        )
        return tbl + ''.join([stock_card(s) for s in stocks]) + '</table>'

    # Market colour section
    mc = market_colour
    mc_color = mc.get('color', '#1a237e')
    dip_banner = ''
    if mc.get('dip'):
        dip_banner = ('<div style="background:#b71c1c;color:white;padding:12px;border-radius:6px;margin-bottom:12px;font-size:14px;font-weight:bold">'
                      'BUY THE DIP OPPORTUNITY DETECTED - Fear/VIX signals suggest market oversold. '
                      'Value stocks flagged today may offer exceptional entry points.</div>')
    mc_html = ('<div style="background:#f5f5f5;border-left:4px solid ' + mc_color + ';padding:12px;border-radius:4px;margin-bottom:16px">'
               '<b style="color:' + mc_color + '">Market Colour</b><br>'
               + ''.join(['<div style="font-size:13px;margin-top:4px">' + sig + '</div>' for sig in mc.get('signals', [])]) +
               '</div>')

    # Portfolio P&L section
    pnl_html = ''
    if portfolio_pnl:
        rows = ''
        for p in portfolio_pnl:
            color = '#2e7d32' if p['pnl_pct'] >= 0 else '#c62828'
            rows += ('<tr>'
                     '<td style="padding:8px">' + p['ticker'] + '</td>'
                     '<td style="padding:8px">' + str(p['buy_price']) + '</td>'
                     '<td style="padding:8px">' + str(p['current']) + '</td>'
                     '<td style="padding:8px;color:' + color + ';font-weight:bold">' + ('+' if p['pnl_pct'] >= 0 else '') + str(p['pnl_pct']) + '%</td>'
                     '<td style="padding:8px;color:' + color + '">' + ('+' if p['pnl_val'] >= 0 else '') + str(p['pnl_val']) + '</td>'
                     '<td style="padding:8px;color:#888">' + p['buy_date'] + '</td>'
                     '</tr>')
        pnl_html = (
            '<h3 style="color:#1a237e">Your Portfolio</h3>'
            '<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px">'
            '<tr style="background:#1a237e;color:white">'
            '<th style="padding:8px">Ticker</th><th style="padding:8px">Buy Price</th>'
            '<th style="padding:8px">Current</th><th style="padding:8px">P&L %</th>'
            '<th style="padding:8px">P&L Value</th><th style="padding:8px">Buy Date</th>'
            '</tr>' + rows + '</table>'
        )

    legend = (
        '<div style="background:#f9f9f9;border:1px solid #ddd;border-radius:6px;padding:12px;margin-bottom:20px;font-size:12px">'
        '<b>How to read:</b> '
        '<span style="color:#1b5e20;font-weight:bold">BUY</span> = strong fundamentals + sanity checks pass. '
        '<span style="color:#e65100;font-weight:bold">WAIT</span> = good fundamentals but some concerns. '
        '<span style="color:#b71c1c;font-weight:bold">AVOID</span> = multiple red flags. '
        '<b>NEW</b> badge = first time appearing. '
        'Graham value = estimated intrinsic value using Graham Number formula. '
        'Not financial advice.</div>'
    )

    summary = ('Screened ' + str(len(US_STOCKS)) + ' US + ' + str(len(HK_STOCKS)) + ' HK + ' +
               str(len(SG_STOCKS)) + ' SG = ' + str(len(US_STOCKS)+len(HK_STOCKS)+len(SG_STOCKS)) +
               ' stocks. ' + str(len(flagged)) + ' passed value criteria. | '
               'BUY: <b>' + str(len(buy)) + '</b> | WAIT: <b>' + str(len(wait)) + '</b> | AVOID: <b>' + str(len(avoid)) + '</b>')

    return (
        '<html><body style="font-family:Arial,sans-serif;color:#333;max-width:1100px;margin:auto;padding:20px">'
        '<h2 style="color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:8px">Daily Stock Screener - ' + date_str + '</h2>'
        '<p style="background:#e8eaf6;padding:12px;border-radius:4px">' + summary + '</p>'
        + dip_banner + mc_html + legend + pnl_html + sector_warning +
        '<h3 style="color:#1b5e20">BUY - ' + str(len(buy)) + ' stocks</h3>' + section(buy, 'BUY', '#1b5e20') +
        '<h3 style="color:#e65100">WAIT - ' + str(len(wait)) + ' stocks</h3>' + section(wait, 'WAIT', '#e65100') +
        '<h3 style="color:#b71c1c">AVOID - ' + str(len(avoid)) + ' stocks</h3>' + section(avoid, 'AVOID', '#b71c1c') +
        '<br><p style="font-size:11px;color:#999">For informational purposes only. Not financial advice. Data from Yahoo Finance.</p>'
        '</body></html>'
    )

# ================================================================
# SEND EMAIL
# ================================================================
def send_email(html, date_str, buy_count, flagged):
    # Use multipart/related so inline images (cid:) are supported by Gmail
    msg_outer = MIMEMultipart('mixed')
    msg_outer['Subject'] = 'Stock Screener - ' + str(buy_count) + ' BUY signals - ' + date_str
    msg_outer['From']    = SENDER_EMAIL
    msg_outer['To']      = RECIPIENT_EMAIL

    msg_related = MIMEMultipart('related')
    msg_related.attach(MIMEText(html, 'html'))

    # Attach each chart as an inline image with Content-ID
    for s in flagged:
        if s.get('chart'):
            img_data = base64.b64decode(s['chart'])
            img = MIMEImage(img_data, 'png')
            cid = 'chart_' + s['ticker'].replace('.', '_').replace('-', '_')
            img.add_header('Content-ID', '<' + cid + '>')
            img.add_header('Content-Disposition', 'inline', filename=cid + '.png')
            msg_related.attach(img)

    msg_outer.attach(msg_related)
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            s.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg_outer.as_string())
        print('Email sent!')
    except Exception as e:
        print('Email error: ' + str(e))

# ================================================================
# MAIN
# ================================================================
if __name__ == '__main__':
    if is_market_holiday():
        exit(0)

    date_str = datetime.now().strftime('%d %b %Y')
    print('Daily Stock Screener - ' + date_str)

    print('Fetching market colour...')
    market_colour = get_market_colour()
    for sig in market_colour['signals']:
        print('  ' + sig)

    print('Loading watchlist history...')
    wl_history = load_watchlist()

    print('Loading portfolio...')
    portfolio_pnl = get_portfolio_pnl()

    flagged  = screen(US_STOCKS, 'US', CRITERIA_US,   wl_history)
    flagged += screen(HK_STOCKS, 'HK', CRITERIA_HKSG, wl_history)
    flagged += screen(SG_STOCKS, 'SG', CRITERIA_HKSG, wl_history)

    save_watchlist([s['ticker'] for s in flagged])

    buy_count = sum(1 for s in flagged if s['rec'] == 'BUY')
    print('Total flagged: ' + str(len(flagged)) + ' | BUY: ' + str(buy_count))

    html = build_html(flagged, date_str, market_colour, portfolio_pnl, wl_history)
    send_email(html, date_str, buy_count, flagged)
