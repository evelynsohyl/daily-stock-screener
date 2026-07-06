"""
Daily Stock Screener Agent
A Simple Reflex Agent that screens US, HK and SG stocks for value investing opportunities.
Sends an email report with flagged stocks to evelynsohyl@gmail.com
"""

import yfinance as yf
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import time

# -- Configuration -------------------------------------
SENDER_EMAIL        = 'evelynsohyl@gmail.com'
SENDER_APP_PASSWORD = 'sjef izzp kvbk htay'
RECIPIENT_EMAIL     = 'evelynsohyl@gmail.com'
MIN_SCORE_TO_FLAG   = 5

# -- Screening Criteria --------------------------------
# US stocks trade at higher valuations, so we use relaxed P/E and P/B thresholds.
# HK and SG stocks use the original stricter thresholds.

CRITERIA_US = {
    'pe_ratio'        : {'threshold': 25,   'direction': 'below', 'label': 'P/E < 25'},
    'pb_ratio'        : {'threshold': 3.0,  'direction': 'below', 'label': 'P/B < 3.0'},
    'dividend_yield'  : {'threshold': 2.0,  'direction': 'above', 'label': 'Div Yield > 2%'},
    'debt_to_equity'  : {'threshold': 100,  'direction': 'below', 'label': 'D/E < 100'},
    'earnings_growth' : {'threshold': 5.0,  'direction': 'above', 'label': 'EPS Growth > 5%'},
    'current_ratio'   : {'threshold': 1.5,  'direction': 'above', 'label': 'Current Ratio > 1.5'},
    'roe'             : {'threshold': 15.0, 'direction': 'above', 'label': 'ROE > 15%'},
}

CRITERIA_HK_SG = {
    'pe_ratio'        : {'threshold': 15,   'direction': 'below', 'label': 'P/E < 15'},
    'pb_ratio'        : {'threshold': 1.5,  'direction': 'below', 'label': 'P/B < 1.5'},
    'dividend_yield'  : {'threshold': 3.0,  'direction': 'above', 'label': 'Div Yield > 3%'},
    'debt_to_equity'  : {'threshold': 50,   'direction': 'below', 'label': 'D/E < 50'},
    'earnings_growth' : {'threshold': 5.0,  'direction': 'above', 'label': 'EPS Growth > 5%'},
    'current_ratio'   : {'threshold': 1.5,  'direction': 'above', 'label': 'Current Ratio > 1.5'},
    'roe'             : {'threshold': 12.0, 'direction': 'above', 'label': 'ROE > 12%'},
}

# -- Stock Universe ------------------------------------
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
    'MU','LRCX','KLAC','AMAT','ADI','MCHP','ON','STX','WDC','HPQ'
]

HK_STOCKS = [
    '0700.HK','0941.HK','9988.HK','1299.HK','0005.HK','0939.HK','1398.HK','3988.HK',
    '2318.HK','0388.HK','0002.HK','0003.HK','0006.HK','0016.HK','0017.HK','0019.HK',
    '0027.HK','0066.HK','0083.HK','0101.HK','0175.HK','0267.HK','0288.HK','0291.HK',
    '0316.HK','0322.HK','0386.HK','0669.HK','0688.HK','0762.HK','0823.HK','0857.HK',
    '0868.HK','0883.HK','0960.HK','0992.HK','1038.HK','1044.HK','1093.HK','1109.HK',
    '1113.HK','1177.HK','1211.HK','1378.HK','1810.HK','1876.HK','2020.HK','2269.HK','2382.HK'
]

SG_STOCKS = [
    'D05.SI','O39.SI','U11.SI','Z74.SI','C6L.SI','S68.SI','F34.SI','BN4.SI','G13.SI',
    'C38U.SI','A17U.SI','ME8U.SI','N2IU.SI','J36.SI','S63.SI','V03.SI','BS6.SI','H78.SI',
    'U96.SI','C09.SI','S58.SI','T39.SI','Y92.SI','9CI.SI','U14.SI','AWX.SI','5E2.SI',
    'BVA.SI','P40U.SI','AJBU.SI'
]

# -- Fetch Stock Data ----------------------------------
def fetch_stock(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        if not info or info.get('quoteType') is None:
            print('  ' + ticker + ': No summary info found, symbol may be delisted')
            return None
        dye = info.get('dividendYield')
        div = (dye * 100) if dye else 0.0
        dte = info.get('debtToEquity')
        eg  = info.get('earningsGrowth')
        return {
            'ticker'          : ticker,
            'name'            : info.get('longName', ticker),
            'sector'          : info.get('sector', 'N/A'),
            'pe_ratio'        : info.get('trailingPE'),
            'pb_ratio'        : info.get('priceToBook'),
            'dividend_yield'  : div,
            'debt_to_equity'  : dte,
            'earnings_growth' : (eg * 100) if eg else None,
            'current_ratio'   : info.get('currentRatio'),
            'roe'             : (info.get('returnOnEquity', 0) or 0) * 100,
        }
    except Exception as e:
        print('  ERROR fetching ' + ticker + ': ' + str(e))
        return None

# -- Score Stock ---------------------------------------
def score_stock(stock, criteria):
    if not stock:
        return 0, [], []
    score, passed, failed = 0, [], []
    for metric, config in criteria.items():
        value = stock.get(metric)
        if value is None:
            failed.append(config['label'] + ' (no data)')
            continue
        t = config['threshold']
        if (config['direction'] == 'below' and value < t) or \
           (config['direction'] == 'above' and value > t):
            score += 1
            passed.append(config['label'] + ' (' + str(round(value, 1)) + ')')
        else:
            failed.append(config['label'] + ' (' + str(round(value, 1)) + ')')
    return score, passed, failed

# -- Screen Market -------------------------------------
def screen_market(tickers, label, criteria):
    print('\n[' + label + '] Scanning ' + str(len(tickers)) + ' stocks...')
    flagged = []
    for i, ticker in enumerate(tickers):
        print('  ' + str(i + 1) + '/' + str(len(tickers)) + ' ' + ticker)
        stock = fetch_stock(ticker)
        score, passed, failed = score_stock(stock, criteria)
        if score >= MIN_SCORE_TO_FLAG:
            verdict = 'STRONG BUY' if score >= 6 else 'WATCH LIST'
            flagged.append({
                'ticker'  : ticker,
                'name'    : stock['name'],
                'sector'  : stock['sector'],
                'score'   : score,
                'verdict' : verdict,
                'passed'  : passed,
                'failed'  : failed,
                'market'  : label,
            })
        time.sleep(0.3)
    print('  [' + label + '] Done - ' + str(len(flagged)) + ' flagged out of ' + str(len(tickers)))
    return flagged

# -- Build Email HTML ----------------------------------
def build_email_html(flagged, run_date):
    strong = [s for s in flagged if 'STRONG' in s['verdict']]
    watch  = [s for s in flagged if 'WATCH'  in s['verdict']]

    def rows(stocks):
        html = ''
        for s in stocks:
            color = '#b71c1c' if 'STRONG' in s['verdict'] else '#2e7d32'
            passed_str = '<br>'.join(["<span style='color:green'>&#10003; " + p + "</span>" for p in s['passed']])
            failed_str = '<br>'.join(["<span style='color:#999'>&#10007; " + f + "</span>" for f in s['failed']])
            html += (
                "<tr>"
                "<td style='padding:8px;font-weight:bold;color:" + color + "'>" + s['ticker'] + "</td>"
                "<td style='padding:8px'>" + s['name'] + "</td>"
                "<td style='padding:8px'>" + s['market'] + "</td>"
                "<td style='padding:8px'>" + s['sector'] + "</td>"
                "<td style='padding:8px;text-align:center;font-weight:bold;color:" + color + "'>" + str(s['score']) + "/7</td>"
                "<td style='padding:8px;font-size:12px'>" + passed_str + "</td>"
                "<td style='padding:8px;font-size:12px'>" + failed_str + "</td>"
                "</tr>"
            )
        return html

    def table(stocks, color):
        if not stocks:
            return "<p style='color:#999'>No stocks in this category today.</p>"
        return (
            "<table style='width:100%;border-collapse:collapse;font-size:13px'>"
            "<tr style='background:" + color + ";color:white'>"
            "<th style='padding:8px'>Ticker</th>"
            "<th style='padding:8px'>Name</th>"
            "<th style='padding:8px'>Market</th>"
            "<th style='padding:8px'>Sector</th>"
            "<th style='padding:8px'>Score</th>"
            "<th style='padding:8px'>Passed</th>"
            "<th style='padding:8px'>Failed</th>"
            "</tr>"
            + rows(stocks) +
            "</table>"
        )

    return (
        "<html><body style='font-family:Arial,sans-serif;color:#333;max-width:900px;margin:auto;padding:20px'>"
        "<h2 style='color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:8px'>Daily Stock Screener - " + run_date + "</h2>"
        "<p style='background:#e8eaf6;padding:12px;border-radius:4px'>"
        "Screened <b>" + str(len(US_STOCKS)) + " US</b>, <b>" + str(len(HK_STOCKS)) + " HK</b>, <b>" + str(len(SG_STOCKS)) + " SG</b> stocks today.<br>"
        "US criteria: P/E &lt; 25, P/B &lt; 3.0, Div &gt; 2%, D/E &lt; 100, EPS Growth &gt; 5%, Current Ratio &gt; 1.5, ROE &gt; 15%<br>"
        "HK/SG criteria: P/E &lt; 15, P/B &lt; 1.5, Div &gt; 3%, D/E &lt; 50, EPS Growth &gt; 5%, Current Ratio &gt; 1.5, ROE &gt; 12%<br>"
        "<b>" + str(len(flagged)) + "</b> stocks flagged. | Strong Buys: <b>" + str(len(strong)) + "</b> | Watch: <b>" + str(len(watch)) + "</b></p>"
        "<h3 style='color:#b71c1c'>Strong Buys - Score 6 or 7 out of 7 (" + str(len(strong)) + " stocks)</h3>" + table(strong, '#b71c1c') +
        "<br><h3 style='color:#2e7d32'>Watch List - Score 5 out of 7 (" + str(len(watch)) + " stocks)</h3>" + table(watch, '#2e7d32') +
        "<br><p style='font-size:11px;color:#999'>For informational purposes only. Not financial advice. Data from Yahoo Finance.</p>"
        "</body></html>"
    )

# -- Send Email ----------------------------------------
def send_email(html, run_date, total):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Daily Stock Screener - ' + str(total) + ' stocks flagged - ' + run_date
    msg['From']    = SENDER_EMAIL
    msg['To']      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, 'html'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print('Email sent to ' + RECIPIENT_EMAIL + '!')
    except Exception as e:
        print('Email failed: ' + str(e))

# -- Main ----------------------------------------------
if __name__ == '__main__':
    run_date = datetime.now().strftime('%d %b %Y')
    print('=' * 56)
    print('  DAILY STOCK SCREENER AGENT')
    print('  Date    : ' + run_date)
    print('  Markets : US (' + str(len(US_STOCKS)) + ') | HK (' + str(len(HK_STOCKS)) + ') | SG (' + str(len(SG_STOCKS)) + ')')
    print('=' * 56)

    all_flagged  = screen_market(US_STOCKS, 'US', CRITERIA_US)
    all_flagged += screen_market(HK_STOCKS, 'HK', CRITERIA_HK_SG)
    all_flagged += screen_market(SG_STOCKS, 'SG', CRITERIA_HK_SG)

    print('\n' + '=' * 56)
    print('  DONE - ' + str(len(all_flagged)) + ' stocks flagged')
    print('  Strong Buys : ' + str(sum(1 for s in all_flagged if 'STRONG' in s['verdict'])))
    print('  Watch List  : ' + str(sum(1 for s in all_flagged if 'WATCH'  in s['verdict'])))
    print('=' * 56)

    html = build_email_html(all_flagged, run_date)
    send_email(html, run_date, len(all_flagged))
