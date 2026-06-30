#!/usr/bin/env python3
"""财经主页 - 股票速览后端服务"""
import json, sys, os, re, subprocess
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')

SKILL_ROOT = Path('/opt/homebrew/lib/node_modules/stock-analyzer-skill/scripts')

# Load complete stock database (5300+ names)
_stock_names_file = Path(__file__).parent / 'stock_names.json'
if _stock_names_file.exists():
    with open(_stock_names_file) as f:
        STOCK_NAMES = json.load(f)
    print(f'已加载 {len(STOCK_NAMES)} 只股票名称（完整版）')
else:
    STOCK_NAMES = {}
    print('⚠️ stock_names.json 未找到，搜索将受限')

# Full code list for code searches
def load_all_codes():
    with open(SKILL_ROOT / 'data' / 'all_stocks.json') as f:
        data = json.load(f)
    codes = []
    for board, lst in data.items():
        if isinstance(lst, list):
            codes.extend(lst)
    return sorted(codes)

ALL_CODES = load_all_codes()
print(f'已加载 {len(ALL_CODES)} 只股票代码')

def get_pinyin(name):
    """拼音首字母 + 全拼 - 使用 pypinyin 库"""
    try:
        from pypinyin import pinyin, Style
        initials = ''.join(p[0][0].upper() for p in pinyin(name, style=Style.FIRST_LETTER))
        full = ''.join(p[0] for p in pinyin(name, style=Style.NORMAL))
        return initials, full
    except ImportError:
        initials = ''.join(c[0].upper() if '一' <= c <= '鿿' else c.upper() for c in name)
        return initials, initials.lower()


@app.route('/api/indices')
def indices():
    """Get major index quotes"""
    try:
        import sys, os
        sys.path.insert(0, str(SKILL_ROOT))
        os.chdir(str(SKILL_ROOT))
        from data import get_quote
        codes = ['sh000001','sz399001','sz399006','sh000300','sh000016','sh000688']
        result = {}
        for c in codes:
            try:
                q = get_quote(c)
                result[c] = {
                    'name': q.name if hasattr(q,'name') else '',
                    'price': q.price if hasattr(q,'price') else 0,
                    'change_pct': q.change_pct if hasattr(q,'change_pct') else 0,
                }
            except: pass
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/indices/trend')
def indices_trend():
    """Get recent K-line data for indices to draw mini trend charts"""
    try:
        import sys, os
        sys.path.insert(0, str(SKILL_ROOT))
        os.chdir(str(SKILL_ROOT))
        from data import get_kline
        codes = ['sh000001','sz399001','sz399006','sh000688','sh000300','sh000016']
        result = {}
        for c in codes:
            try:
                kline = get_kline(c, scale=240, datalen=20)
                closes = [k.close for k in kline if hasattr(k, 'close')]
                if closes:
                    result[c] = closes
            except: pass
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/api/search')
def search():
    q = request.args.get('q', '').strip().upper()
    if not q or len(q) < 1:
        return jsonify([])

    # Check if query looks like a code (digits) or name/pinyin
    is_code_query = q.isdigit() or q.startswith(('SH', 'SZ', 'BJ'))

    results = []
    if is_code_query:
        # Search full stock list by code
        for code in ALL_CODES:
            code_short = code.replace('sh', '').replace('sz', '').replace('bj', '')
            name = STOCK_NAMES.get(code, '')
            score = 0
            if q == code: score = 100
            elif q == code_short: score = 95
            elif code_short.startswith(q): score = 80
            elif q in code_short: score = 70
            if score > 0:
                results.append({'code': code, 'code_short': code_short,
                    'name': name or code_short, 'pinyin': get_pinyin(name)[0] if name else '', 'score': score})
    else:
        # Search ALL 5300+ stocks by name / pinyin
        q_lower = q.lower()
        for code, name in STOCK_NAMES.items():
            code_short = code.replace('sh', '').replace('sz', '').replace('bj', '')
            initials, full_py = get_pinyin(name)
            score = 0
            if q == name: score = 90
            elif q in name: score = 60
            elif q_lower == initials.lower(): score = 88
            elif q_lower == full_py: score = 86
            elif full_py.startswith(q_lower): score = 75
            elif initials.lower().startswith(q_lower): score = 72
            elif q_lower in full_py: score = 55
            elif q_lower in initials.lower(): score = 50
            if score > 0:
                results.append({'code': code, 'code_short': code_short,
                    'name': name, 'pinyin': initials, 'score': score})

    results.sort(key=lambda x: x['score'], reverse=True)
    return jsonify(results[:8])


@app.route('/api/analyze')
def analyze():
    code = request.args.get('code', '')
    if not code:
        return jsonify({'error': '请输入股票代码'}), 400

    result = {'code': code}

    # 1. Quote
    try:
        import sys
        sys.path.insert(0, str(SKILL_ROOT))
        os.chdir(str(SKILL_ROOT))
        from data import get_quote
        q = get_quote(code)
        result['name'] = q.name if hasattr(q, 'name') else ''
        result['price'] = q.price if hasattr(q, 'price') else 0
        result['change_pct'] = q.change_pct if hasattr(q, 'change_pct') else 0
        result['pe'] = q.pe if hasattr(q, 'pe') else 0
        result['pb'] = q.pb if hasattr(q, 'pb') else 0
        result['total_cap'] = q.total_cap if hasattr(q, 'total_cap') else 0
    except Exception as e:
        result['quote_error'] = str(e)

    # 2. Finance
    try:
        sys.path.insert(0, str(SKILL_ROOT))
        os.chdir(str(SKILL_ROOT))
        from data import get_finance
        fin = get_finance(code)
        if fin and len(fin) >= 2:
            # Sort: find full-year report first, then Q1
            fy = None
            q1 = None
            for f in fin:
                rd = str(f.report_date) if hasattr(f, 'report_date') else ''
                if '-12-31' in rd:
                    fy = f
                elif '-03-31' in rd:
                    q1 = f
            if fy:
                result['roe'] = fy.roe if hasattr(fy, 'roe') else 0
                result['eps'] = fy.eps if hasattr(fy, 'eps') else 0
                result['revenue_yoy'] = fy.revenue_yoy if hasattr(fy, 'revenue_yoy') else 0
                result['profit_yoy'] = fy.net_profit_yoy if hasattr(fy, 'net_profit_yoy') else 0
                result['gross_margin'] = fy.gross_margin if hasattr(fy, 'gross_margin') else 0
                result['net_margin'] = fy.net_margin if hasattr(fy, 'net_margin') else 0
                result['debt_ratio'] = fy.debt_ratio if hasattr(fy, 'debt_ratio') else 0
                result['ocf_per_share'] = fy.ocf_per_share if hasattr(fy, 'ocf_per_share') else 0
                result['bps'] = fy.bps if hasattr(fy, 'bps') else 0
            if q1:
                result['q1_revenue'] = q1.revenue_yoy if hasattr(q1, 'revenue_yoy') else 0
                result['q1_profit'] = q1.net_profit_yoy if hasattr(q1, 'net_profit_yoy') else 0
                result['q1_roe'] = q1.roe if hasattr(q1, 'roe') else 0
    except Exception as e:
        result['finance_error'] = str(e)

    # 3. Shareholder data
    try:
        sys.path.insert(0, str(SKILL_ROOT))
        os.chdir(str(SKILL_ROOT))
        from data.chip import get_holders
        holders = get_holders(code, periods=4)
        if holders:
            hdata = []
            for h in holders[:6]:
                hdata.append({
                    'date': str(h.end_date) if hasattr(h, 'end_date') else '',
                    'num': h.holder_num if hasattr(h, 'holder_num') else 0,
                    'change': h.holder_num_change if hasattr(h, 'holder_num_change') else 0,
                })
            result['holders'] = hdata
    except Exception as e:
        result['holders_error'] = str(e)

    # 4. Technical
    try:
        os.chdir(str(SKILL_ROOT))
        tech_output = subprocess.check_output(
            ['python3', 'scripts/technical.py', code, '--quick'],
            timeout=30, cwd=str(SKILL_ROOT.parent)
        ).decode()
        result['technical'] = tech_output
    except Exception as e:
        result['technical_error'] = str(e)

    return jsonify(result)


import time as _time_mod

# ── 理杏仁 PE/PB 分位点 ──────────────────────────────
LIXINGER_TOKEN = os.environ.get("LIXINGER_TOKEN", "")
LIXINGER_URL = "https://open.lixinger.com/api/cn/company/fundamental/non_financial"

LIXINGER_METRICS = [
    "pe_ttm", "pe_ttm.y5.cvpos", "pe_ttm.y10.cvpos",
    "pb", "pb.y5.cvpos", "pb.y10.cvpos",
    "dyr", "mc", "ey", "sp", "spc",
]


@app.route('/api/lixinger')
def lixinger():
    """Get PE/PB percentile data from 理杏仁 for a single stock"""
    code = request.args.get('code', '')
    if not code:
        return jsonify({'error': '缺少股票代码'}), 400
    if not LIXINGER_TOKEN:
        return jsonify({'error': 'LIXINGER_TOKEN 未配置'}), 503

    # Strip sh/sz prefix for 理杏仁
    lx_code = code.replace('sh', '').replace('sz', '').replace('bj', '')

    import requests as req_lx
    from datetime import datetime as dt_lx, timedelta

    data = None
    for offset in [0, 1, 2]:
        try_date = (dt_lx.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
        try:
            resp = req_lx.post(
                LIXINGER_URL,
                json={
                    "token": LIXINGER_TOKEN,
                    "date": try_date,
                    "stockCodes": [lx_code],
                    "metricsList": LIXINGER_METRICS,
                },
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            result = resp.json()
            if result.get("code") == 1 and result.get("data"):
                data = result["data"][0]
                break
        except Exception:
            continue

    if not data:
        return jsonify({'error': '理杏仁无可用数据'}), 404

    def pct_label(v):
        """Convert 0-1 percentile to human label"""
        if v is None: return '--'
        pct = v * 100
        if pct < 5: return f'{pct:.1f}% 极低'
        if pct < 20: return f'{pct:.1f}% 偏低'
        if pct < 50: return f'{pct:.1f}% 适中'
        if pct < 80: return f'{pct:.1f}% 偏高'
        return f'{pct:.1f}% 极高'

    return jsonify({
        'code': code,
        'date': data.get('date', ''),
        'pe_ttm': data.get('pe_ttm'),
        'pe_pct5': data.get('pe_ttm.y5.cvpos'),
        'pe_pct10': data.get('pe_ttm.y10.cvpos'),
        'pe_pct5_label': pct_label(data.get('pe_ttm.y5.cvpos')),
        'pe_pct10_label': pct_label(data.get('pe_ttm.y10.cvpos')),
        'pb': data.get('pb'),
        'pb_pct5': data.get('pb.y5.cvpos'),
        'pb_pct10': data.get('pb.y10.cvpos'),
        'pb_pct5_label': pct_label(data.get('pb.y5.cvpos')),
        'pb_pct10_label': pct_label(data.get('pb.y10.cvpos')),
        'dyr': data.get('dyr'),
        'ey': data.get('ey'),
        'mc': data.get('mc'),
    })


# ETF-based sector proxies (using real ETF data via skill — always works)
SECTOR_ETFS = {
    '半导体': 'sh512480', '新能源车': 'sh515030', '银行': 'sh512800',
    '白酒': 'sh512690', '光伏': 'sh515790', '军工': 'sh512660',
    '医药': 'sh512010', '证券': 'sh512880', '科创50': 'sh588000',
    '人工智能': 'sh515070', '芯片': 'sh512760', '消费电子': 'sh159732',
    '电力': 'sh159611', '煤炭': 'sh515220', '稀土': 'sh516780',
    '通信': 'sh515880', '计算机': 'sh512720', '传媒': 'sh512980',
    '汽车': 'sh516110', '房地产': 'sh512200', '钢铁': 'sh515210',
    '有色': 'sh512400', '化工': 'sh516020', '农业': 'sh159865',
    '家电': 'sh159996', '建材': 'sh516750', '旅游': 'sh159766',
    '中药': 'sh159647', '中证500': 'sh510500', '创业板': 'sh159915',
    '红利': 'sh510880', '纳指': 'sh513100', '黄金': 'sh518880',
    '港股通': 'sh513090', '沪深300': 'sh510300',
}

_sector_cache = {'data': None, 'time': 0}

@app.route('/api/sectors')
def sectors():
    """Get sector/ETF performance ranking using skill's data fetchers"""
    if _sector_cache['data'] is not None and _time_mod.time() - _sector_cache['time'] < 180:
        return jsonify(_sector_cache['data'])

    try:
        sys.path.insert(0, str(SKILL_ROOT))
        os.chdir(str(SKILL_ROOT))
        from data import get_quotes, get_kline

        # Fetch all quotes in parallel (skill supports batch fetching)
        codes = list(SECTOR_ETFS.values())
        names = list(SECTOR_ETFS.keys())
        quotes = get_quotes(codes, use_cache=False)

        result = []
        for i, (name, code) in enumerate(zip(names, codes)):
            sector = {'code': code, 'name': name, 'price': 0, 'change_pct': 0, 'trend': []}
            q = quotes[i] if i < len(quotes) else None
            if q and q.price > 0:
                sector['price'] = q.price
                if hasattr(q, 'change_pct') and q.change_pct:
                    sector['change_pct'] = q.change_pct
                elif hasattr(q, 'prev_close') and q.prev_close and q.prev_close > 0:
                    sector['change_pct'] = round((q.price - q.prev_close) / q.prev_close * 100, 2)
            result.append(sector)

        result.sort(key=lambda x: x['change_pct'], reverse=True)
        result = [s for s in result if s['price'] > 0]
        _sector_cache['data'] = result
        _sector_cache['time'] = _time_mod.time()

        # Fetch K-lines in background (won't block response)
        def _fetch_trends():
            for i, (name, code) in enumerate(zip(names, codes)):
                if i < len(result) and result[i]['price'] > 0:
                    try:
                        kline = get_kline(code, scale=101, datalen=12)
                        if kline:
                            closes = [k.close for k in kline if hasattr(k, 'close') and k.close > 0]
                            if closes:
                                result[i]['trend'] = closes
                    except:
                        pass
            _sector_cache['data'] = result  # update cache with trends
            _sector_cache['time'] = _time_mod.time()

        import threading
        threading.Thread(target=_fetch_trends, daemon=True).start()

        return jsonify(result)
    except Exception as e:
        if _sector_cache['data'] is not None:
            return jsonify(_sector_cache['data'])
        return jsonify({'error': str(e)}), 500


@app.route('/api/watchlist')
def watchlist():
    """Get quote + mini trend for a list of stock codes"""
    codes = request.args.get('codes', '')
    if not codes:
        return jsonify({})
    code_list = [c.strip() for c in codes.split(',') if c.strip()]
    if not code_list:
        return jsonify({})

    result = {}
    try:
        import sys, os
        sys.path.insert(0, str(SKILL_ROOT))
        os.chdir(str(SKILL_ROOT))
        from data import get_quote, get_kline

        for code in code_list:
            item = {'code': code}
            try:
                q = get_quote(code)
                item['name'] = q.name if hasattr(q, 'name') else ''
                item['price'] = q.price if hasattr(q, 'price') else 0
                item['change_pct'] = q.change_pct if hasattr(q, 'change_pct') else 0
            except:
                item['price'] = 0
                item['change_pct'] = 0

            try:
                kline = get_kline(code, scale=240, datalen=20)
                closes = [k.close for k in kline if hasattr(k, 'close')]
                if closes:
                    item['trend'] = closes
            except:
                item['trend'] = []

            result[code] = item
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8820))
    host = os.environ.get('HOST', '127.0.0.1')
    app.run(host=host, port=port, debug=False)
