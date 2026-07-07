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
# SCREENING CRITERIA - MULTI-BUCKET
# ================================================================

# --- Growth bucket (US / HK / SG) ---
# For companies with EPS growth > 20% or revenue growth > 20%
# Uses PEG, Rule of 40, gross margin, FCF proxy
CRITERIA_GROWTH = {
    'peg_ratio':       {'threshold': 1.5,  'direction': 'below', 'label': 'PEG < 1.5'},
    'revenue_growth':  {'threshold': 15.0, 'direction': 'above', 'label': 'Revenue Growth > 15%'},
    'gross_margins':   {'threshold': 40.0, 'direction': 'above', 'label': 'Gross Margin > 40%'},
    'profit_margins':  {'threshold': 10.0, 'direction': 'above', 'label': 'Profit Margin > 10%'},
    'earnings_growth': {'threshold': 20.0, 'direction': 'above', 'label': 'EPS Growth > 20%'},
    'roe':             {'threshold': 15.0, 'direction': 'above', 'label': 'ROE > 15%'},
    'debt_to_equity':  {'threshold': 150,  'direction': 'below', 'label': 'D/E < 150'},
}

# --- Value bucket US ---
# For mature/stable US companies with moderate growth
CRITERIA_VALUE_US = {
    'pe_ratio':        {'threshold': 25,   'direction': 'below', 'label': 'P/E < 25'},
    'pb_ratio':        {'threshold': 3.0,  'direction': 'below', 'label': 'P/B < 3.0'},
    'debt_to_equity':  {'threshold': 100,  'direction': 'below', 'label': 'D/E < 100'},
    'earnings_growth': {'threshold': 5.0,  'direction': 'above', 'label': 'EPS Growth > 5%'},
    'current_ratio':   {'threshold': 1.5,  'direction': 'above', 'label': 'Current Ratio > 1.5'},
    'roe':             {'threshold': 15.0, 'direction': 'above', 'label': 'ROE > 15%'},
    'profit_margins':  {'threshold': 8.0,  'direction': 'above', 'label': 'Profit Margin > 8%'},
}

# --- Value bucket HK/SG ---
# Stricter thresholds for HK/SG mature companies
CRITERIA_VALUE_HKSG = {
    'pe_ratio':        {'threshold': 15,   'direction': 'below', 'label': 'P/E < 15'},
    'pb_ratio':        {'threshold': 1.5,  'direction': 'below', 'label': 'P/B < 1.5'},
    'debt_to_equity':  {'threshold': 50,   'direction': 'below', 'label': 'D/E < 50'},
    'earnings_growth': {'threshold': 5.0,  'direction': 'above', 'label': 'EPS Growth > 5%'},
    'current_ratio':   {'threshold': 1.5,  'direction': 'above', 'label': 'Current Ratio > 1.5'},
    'roe':             {'threshold': 12.0, 'direction': 'above', 'label': 'ROE > 12%'},
    'profit_margins':  {'threshold': 8.0,  'direction': 'above', 'label': 'Profit Margin > 8%'},
}

# --- Dividend / Income bucket (HK & SG only - US excluded due to 30% withholding tax) ---
CRITERIA_DIVIDEND = {
    'dividend_yield':  {'threshold': 3.5,  'direction': 'above', 'label': 'Div Yield > 3.5%'},
    'payout_ratio':    {'threshold': 75.0, 'direction': 'below', 'label': 'Payout Ratio < 75%'},
    'debt_to_equity':  {'threshold': 80,   'direction': 'below', 'label': 'D/E < 80'},
    'roe':             {'threshold': 8.0,  'direction': 'above', 'label': 'ROE > 8%'},
    'pe_ratio':        {'threshold': 20,   'direction': 'below', 'label': 'P/E < 20'},
    'revenue_growth':  {'threshold': -5.0, 'direction': 'above', 'label': 'Revenue not declining'},
    'profit_margins':  {'threshold': 5.0,  'direction': 'above', 'label': 'Profit Margin > 5%'},
}

# --- REIT bucket (HK & SG only) ---
# REITs use different metrics - EPS distorted by depreciation
CRITERIA_REIT = {
    'dividend_yield':  {'threshold': 4.0,  'direction': 'above', 'label': 'Dist Yield > 4%'},
    'pb_ratio':        {'threshold': 1.2,  'direction': 'below', 'label': 'P/B < 1.2 (NAV discount)'},
    'debt_to_equity':  {'threshold': 100,  'direction': 'below', 'label': 'D/E < 100'},
    'roe':             {'threshold': 5.0,  'direction': 'above', 'label': 'ROE > 5%'},
    'revenue_growth':  {'threshold': -5.0, 'direction': 'above', 'label': 'Revenue not declining'},
    'profit_margins':  {'threshold': 10.0, 'direction': 'above', 'label': 'Profit Margin > 10%'},
    'current_ratio':   {'threshold': 0.8,  'direction': 'above', 'label': 'Current Ratio > 0.8'},
}

MIN_SCORE_GROWTH   = 5  # out of 7
MIN_SCORE_VALUE    = 5  # out of 7
MIN_SCORE_DIVIDEND = 5  # out of 7
MIN_SCORE_REIT     = 4  # out of 7

def classify_bucket(stock, market):
    """Classify a stock into Growth / Value / Dividend / REIT bucket."""
    sector       = (stock.get('sector') or '').lower()
    # Use None-safe values: only treat as growth if data actually exists
    eps_growth   = stock.get('earnings_growth')  # may be None
    rev_growth   = stock.get('revenue_growth') or 0
    div_yield    = stock.get('dividend_yield') or 0
    is_reit      = 'real estate' in sector
    is_hksg      = market in ('HK', 'SG')
    # Only flag as growth if we have real EPS growth data confirming it
    is_growth    = ((eps_growth is not None and eps_growth >= 20) or rev_growth >= 20)

    if is_reit and is_hksg:
        return 'REIT', CRITERIA_REIT, MIN_SCORE_REIT
    if is_growth:
        return 'Growth', CRITERIA_GROWTH, MIN_SCORE_GROWTH
    if is_hksg and div_yield >= 3.5:
        return 'Dividend', CRITERIA_DIVIDEND, MIN_SCORE_DIVIDEND
    if market == 'US':
        return 'Value', CRITERIA_VALUE_US, MIN_SCORE_VALUE
    return 'Value', CRITERIA_VALUE_HKSG, MIN_SCORE_VALUE

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
        t_obj = yf.Ticker(ticker)
        # Fetch 3 timeframes
        hist_5y  = t_obj.history(period='5y',  interval='1mo')
        hist_1y  = t_obj.history(period='1y',  interval='1wk')
        hist_3mo = t_obj.history(period='3mo', interval='1d')
        if hist_5y is None or len(hist_5y) < 6:
            return None

        panels = [
            (hist_5y,  '5Y (Monthly)'),
            (hist_1y,  '1Y (Weekly)'),
            (hist_3mo, '3M (Daily)'),
        ]

        fig, axes = plt.subplots(1, 3, figsize=(10, 2.2))
        fig.patch.set_facecolor('#f9f9f9')

        for ax, (hist, label) in zip(axes, panels):
            ax.set_facecolor('#f9f9f9')
            if hist is None or len(hist) < 3:
                ax.text(0.5, 0.5, 'N/A', ha='center', va='center',
                        transform=ax.transAxes, fontsize=9, color='#aaa')
                ax.set_title(label, fontsize=8, color='#555', pad=3)
                ax.set_xticks([])
                ax.set_yticks([])
                for spine in ax.spines.values():
                    spine.set_visible(False)
                continue
            close = hist['Close']
            color = '#2e7d32' if float(close.iloc[-1]) >= float(close.iloc[0]) else '#c62828'
            ax.plot(hist.index, close, color=color, linewidth=1.5)
            ax.fill_between(hist.index, close, float(close.min()), alpha=0.08, color=color)
            # Add 50-period MA on 5Y and 1Y panels
            if len(close) >= 10:
                ma = close.rolling(min(50, len(close)//2)).mean()
                ax.plot(hist.index, ma, color='#1565c0', linewidth=0.8, linestyle='--', alpha=0.7)
            # Label current price on right
            ax.annotate(str(round(float(close.iloc[-1]), 1)),
                        xy=(hist.index[-1], float(close.iloc[-1])),
                        fontsize=7, color=color, ha='right')
            ax.set_title(label, fontsize=8, color='#555', pad=3)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)

        plt.tight_layout(pad=0.3)
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=90, bbox_inches='tight', pad_inches=0.05)
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')
    except Exception as e:
        print('Chart error ' + ticker + ': ' + str(e))
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
        # Get ticker symbol and company name for relevance filtering
        ticker_sym = (ticker_obj.ticker or '').upper().replace('.HK','').replace('.SI','')
        try:
            company_name = (ticker_obj.info.get('shortName') or ticker_obj.info.get('longName') or '').lower()
            # Extract first meaningful word from company name (e.g. 'visa' from 'Visa Inc.')
            company_keywords = [w for w in company_name.replace(',','').replace('.','').split() if len(w) > 3 and w not in ('inc','corp','ltd','group','holdings','limited','company')]
        except:
            company_keywords = []
        neg_words = ['downgrade','cut','miss','loss','decline','fall','drop','warn','risk',
                     'lawsuit','fraud','recall','investigation','layoff','bankruptcy','default']
        pos_words = ['upgrade','beat','record','growth','profit','raise','expand','strong',
                     'buy','outperform','dividend','acquisition','partnership']
        headlines = []
        neg_count = 0
        pos_count = 0
        for item in news[:10]:  # Check more items to find relevant ones
            content = item.get('content', {})
            title = (content.get('title', '') if isinstance(content, dict) else '') or item.get('title', '')
            if not title:
                continue
            title_lower = title.lower()
            # Check if headline is relevant to this company
            related_tickers = content.get('relatedTickers', []) if isinstance(content, dict) else []
            is_relevant = (
                ticker_sym.lower() in title_lower or
                any(kw in title_lower for kw in company_keywords) or
                ticker_sym in [str(t).upper() for t in related_tickers]
            )
            if not is_relevant:
                continue
            headlines.append(title)
            if any(w in title_lower for w in neg_words):
                neg_count += 1
            if any(w in title_lower for w in pos_words):
                pos_count += 1
            if len(headlines) >= 3:
                break
        if not headlines:
            return ['No company-specific news found today.'], 'neutral'
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
        dy  = info.get('dividendYield')
        eg  = info.get('earningsGrowth')
        pr  = info.get('payoutRatio')
        gm  = info.get('grossMargins')
        peg = info.get('pegRatio')
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
            'gross_margins':   (gm * 100) if gm else None,
            'payout_ratio':    (pr * 100) if pr else None,
            'peg_ratio':       peg,
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
        # Fetch 1 year of daily data for proper MA calculation
        hist = ticker_obj.history(period='1y')
        if hist is None or len(hist) < 50:
            return 'unknown', 0.0
        close = hist['Close']
        # True rolling MAs - last value of the rolling window
        ma50  = float(close.rolling(50).mean().iloc[-1])
        ma200 = float(close.rolling(min(200, len(close))).mean().iloc[-1])
        current = float(close.iloc[-1])
        # 52-week high/low from full year
        week52_low  = float(close.min())
        week52_high = float(close.max())
        pct_from_52w_low = ((current - week52_low) / week52_low) * 100
        if ma50 > ma200 * 1.01:
            trend = 'uptrend'
        elif ma50 < ma200 * 0.99:
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

    # Graham value only meaningful for Value/Dividend/REIT buckets, not Growth
    # (Growth stocks are intentionally priced above Graham value due to future earnings)
    bucket = stock.get('_bucket', 'Value')
    graham = stock.get('graham_value')
    if graham and current and current > 0 and bucket not in ('Growth',):
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

    market = stock.get('_market', '')
    events = get_upcoming_events(stock.get('ticker_obj'))
    for ev in events:
        if 'Earnings' in ev:
            red.append(ev)
        elif 'dividend' in ev.lower() and market == 'US':
            pass  # Skip ex-dividend alerts for US stocks (30% withholding tax makes this irrelevant)
        else:
            green.append(ev)

    green_count = len(green)
    red_count   = len(red)

    # Entry quality check: reject stocks that are overextended regardless of fundamentals
    # A stock near its 52-week high with analyst target below current price is a poor entry
    entry_ok = True
    entry_reason = ''
    if pct_52w >= 85:
        entry_ok = False
        entry_reason = 'Price near 52-week high (' + str(pct_52w) + '% above low) - wait for pullback'
    current2 = stock.get('current_price')
    target2  = stock.get('target_price')
    if entry_ok and current2 and target2 and current2 > 0:
        upside2 = (target2 - current2) / current2 * 100
        if upside2 < 5:
            entry_ok = False
            entry_reason = 'Analyst target offers <5% upside (' + str(round(upside2,1)) + '%) - limited reward'

    if red_count >= 3:
        rec = 'AVOID'
        reason = str(red_count) + ' red flags: ' + '; '.join(red) + '.'
    elif not entry_ok:
        rec = 'AVOID'
        reason = 'Entry not ideal: ' + entry_reason + '.'
    elif red_count == 0 and green_count >= 4:
        rec = 'BUY'
        reason = 'Strong fundamentals, no red flags, ' + str(green_count) + ' positive signals.'
    elif red_count == 0 and green_count >= 2:
        rec = 'BUY'
        reason = 'Good fundamentals, ' + str(green_count) + ' positive signals, no red flags.'
    elif red_count >= 1 and green_count > red_count:
        rec = 'BUY'
        reason = 'Mostly positive: ' + str(green_count) + ' green, ' + str(red_count) + ' concern(s): ' + '; '.join(red) + '.'
    else:
        rec = 'AVOID'
        reason = 'Insufficient positive signals (' + str(green_count) + ' green, ' + str(red_count) + ' red).'

    return green, red, rec, reason, headlines

# ================================================================
# SCREEN MARKET
# ================================================================
def screen(tickers, market, wl_history):
    print('Scanning ' + market + ' (' + str(len(tickers)) + ' stocks)...')
    results = []
    for i, ticker in enumerate(tickers):
        print('  ' + str(i + 1) + '/' + str(len(tickers)) + ' ' + ticker)
        stock = fetch_stock(ticker)
        if not stock:
            time.sleep(0.5)
            continue
        bucket, criteria, min_sc = classify_bucket(stock, market)
        # Inject bucket and market into stock dict for use in sanity_checks
        stock['_bucket'] = bucket
        stock['_market'] = market
        sc, passed, failed = score_stock(stock, criteria)
        if sc >= min_sc:
            green, red, rec, reason, headlines = sanity_checks(stock)
            verdict = 'STRONG BUY' if sc >= len(criteria) - 1 else 'WATCH'
            wl_status = get_watchlist_status(ticker, wl_history)
            chart_b64 = get_mini_chart(ticker)
            results.append({
                'ticker':     ticker,
                'name':       stock['name'],
                'market':     market,
                'sector':     stock['sector'],
                'bucket':     bucket,
                'score':      sc,
                'max_score':  len(criteria),
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
            print('    -> ' + bucket + ' | ' + rec + ' (' + wl_status + ')')
        time.sleep(0.5)
    return results

# ================================================================
# BUILD EMAIL HTML
# ================================================================
def build_html(flagged, date_str, market_colour, portfolio_pnl, wl_history):
    buy   = [s for s in flagged if s['rec'] == 'BUY']
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
        bucket_colors = {'Growth': '#1565c0', 'Value': '#4a148c', 'Dividend': '#1b5e20', 'REIT': '#e65100'}
        bucket_color = bucket_colors.get(s.get('bucket', 'Value'), '#555')
        bucket_badge = '<span style="background:' + bucket_color + ';color:white;font-size:10px;padding:2px 6px;border-radius:10px;margin-left:4px">' + s.get('bucket', 'Value') + '</span>'
        new_badge = ('<span style="background:#1a237e;color:white;font-size:10px;padding:2px 6px;border-radius:10px;margin-left:4px">NEW</span>'
                     if s['wl_status'] == 'new' else
                     '<span style="background:#777;color:white;font-size:10px;padding:2px 6px;border-radius:10px;margin-left:4px">RETURNING</span>')
        price_line = ''
        if s['price'] and s['target']:
            upside = (s['target'] - s['price']) / s['price'] * 100
            price_line = ('<div style="font-size:12px;color:#555;margin-top:2px">Price: ' +
                          str(round(s['price'], 2)) + ' | Analyst target: ' + str(round(s['target'], 2)) +
                          ' | Upside: ' + str(round(upside, 1)) + '%</div>')
        graham_line = ''
        # Graham value is only meaningful for Value/Dividend/REIT - hide for Growth stocks
        if s['graham'] and s['price'] and s['price'] > 0 and s.get('bucket') != 'Growth':
            mos = (s['graham'] - s['price']) / s['price'] * 100
            mos_color = '#2e7d32' if mos >= 0 else '#c62828'
            graham_line = ('<div style="font-size:12px;color:' + mos_color + ';margin-top:2px">Graham value: ' +
                           str(s['graham']) + ' | Margin of safety: ' + str(round(mos, 1)) + '%</div>')
        chart_img = ''
        if s['chart']:
            cid = 'chart_' + s['ticker'].replace('.', '_').replace('-', '_')
            chart_img = '<img src="cid:' + cid + '" style="width:480px;height:100px;margin-top:6px;border-radius:4px">'
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
            '<div style="font-size:16px;font-weight:bold">' + s['ticker'] + bucket_badge + new_badge + '</div>'
            '<div style="font-size:12px;color:#555">' + s['name'] + '</div>'
            '<div style="font-size:11px;color:#888">' + s['market'] + ' | ' + s['sector'] + '</div>'
            + price_line + graham_line + chart_img +
            '</td>'
            '<td style="padding:12px;min-width:120px">'
            '<div style="font-size:13px;font-weight:bold;color:#2e7d32">' + str(s['score']) + '/' + str(s.get('max_score', 7)) + '</div>'
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
        '<span style="color:#1b5e20;font-weight:bold">BUY</span> = strong fundamentals + good entry point (not extended, analyst upside exists). '
        'Stocks that pass fundamentals but are overextended or have red flags are excluded. '
        '<b>NEW</b> badge = first time appearing. '
        'Graham value = estimated intrinsic value (Graham Number formula). '
        '<b>Buckets:</b> '
        '<span style="background:#1565c0;color:white;padding:1px 5px;border-radius:8px;font-size:11px">Growth</span> = EPS/Rev growth >20%, scored on PEG &amp; Rule of 40. '
        '<span style="background:#4a148c;color:white;padding:1px 5px;border-radius:8px;font-size:11px">Value</span> = mature companies, scored on P/E, P/B, ROE. '
        '<span style="background:#1b5e20;color:white;padding:1px 5px;border-radius:8px;font-size:11px">Dividend</span> = HK/SG income stocks (US excluded - 30% withholding tax). '
        '<span style="background:#e65100;color:white;padding:1px 5px;border-radius:8px;font-size:11px">REIT</span> = HK/SG real estate trusts, scored on yield &amp; NAV. '
        'Not financial advice.</div>'
    )

    summary = ('Screened ' + str(len(US_STOCKS)) + ' US + ' + str(len(HK_STOCKS)) + ' HK + ' +
               str(len(SG_STOCKS)) + ' SG = ' + str(len(US_STOCKS)+len(HK_STOCKS)+len(SG_STOCKS)) +
               ' stocks. ' + str(len(flagged)) + ' passed value criteria. | '
               'BUY: <b>' + str(len(buy)) + '</b> | AVOID (not shown): <b>' + str(len(avoid)) + '</b>')

    return (
        '<html><body style="font-family:Arial,sans-serif;color:#333;max-width:1100px;margin:auto;padding:20px">'
        '<h2 style="color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:8px">Daily Stock Screener - ' + date_str + '</h2>'
        '<p style="background:#e8eaf6;padding:12px;border-radius:4px">' + summary + '</p>'
        + dip_banner + mc_html + legend + pnl_html + sector_warning +
        '<h3 style="color:#1b5e20">BUY - ' + str(len(buy)) + ' stocks</h3>' + section(buy, 'BUY', '#1b5e20') +
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

    flagged  = screen(US_STOCKS, 'US', wl_history)
    flagged += screen(HK_STOCKS, 'HK', wl_history)
    flagged += screen(SG_STOCKS, 'SG', wl_history)

    save_watchlist([s['ticker'] for s in flagged])

    buy_count = sum(1 for s in flagged if s['rec'] == 'BUY')
    print('Total flagged: ' + str(len(flagged)) + ' | BUY: ' + str(buy_count))

    html = build_html(flagged, date_str, market_colour, portfolio_pnl, wl_history)
    send_email(html, date_str, buy_count, flagged)
