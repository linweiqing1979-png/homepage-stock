#!/usr/bin/env python3
"""财经主页 - 股票速览后端服务"""
import json, sys, os, re, subprocess
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')

SKILL_ROOT = Path('/opt/homebrew/lib/node_modules/stock-analyzer-skill/scripts')

# Load stock database
def load_stocks():
    with open(SKILL_ROOT / 'data' / 'all_stocks.json') as f:
        data = json.load(f)
    stocks = set()
    for board_name, board_list in data.items():
        if isinstance(board_list, list):
            for s in board_list:
                if isinstance(s, str) and s:
                    stocks.add(s)
    return sorted(stocks)

STOCKS = load_stocks()
print(f'已加载 {len(STOCKS)} 只股票')

# Popular stocks with names (for search display)
POPULAR = {
    'sh600519': '贵州茅台', 'sz000858': '五粮液', 'sz300750': '宁德时代',
    'sz002415': '海康威视', 'sz002475': '立讯精密', 'sz002049': '紫光国微',
    'sh600276': '恒瑞医药', 'sh603259': '药明康德', 'sz300274': '阳光电源',
    'sh601138': '工业富联', 'sh688981': '中芯国际', 'sz002371': '北方华创',
    'sh688012': '中微公司', 'sh688008': '澜起科技', 'sh600584': '长电科技',
    'sh688256': '寒武纪', 'sh603501': '豪威集团', 'sh688041': '海光信息',
    'sh688235': '百济神州', 'sh688331': '荣昌生物', 'sz300124': '汇川技术',
    'sh601689': '拓普集团', 'sh605117': '德业股份', 'sz300308': '中际旭创',
    'sz300502': '新易盛', 'sz300394': '天孚通信', 'sz002463': '沪电股份',
    'sh600346': '恒力石化', 'sh600096': '云天化', 'sh600887': '伊利股份',
    'sh600900': '长江电力', 'sh601899': '紫金矿业', 'sh600809': '山西汾酒',
    'sz002594': '比亚迪', 'sh601328': '交通银行', 'sh600036': '招商银行',
    'sh601288': '农业银行', 'sh601398': '工商银行', 'sh601939': '建设银行',
    'sh688266': '泽璟制药', 'sh600196': '复星医药', 'sh600570': '恒生电子',
    'sz300782': '卓胜微', 'sh688525': '佰维存储', 'sh601601': '中国太保',
    'sh600188': '兖矿能源', 'sh601088': '中国神华', 'sz002185': '华天科技',
    'sz002156': '通富微电', 'sh600460': '士兰微', 'sz300024': '机器人',
    'sh603160': '汇顶科技', 'sz300014': '亿纬锂能', 'sz002074': '国轩高科',
    'sz300759': '康龙化成', 'sz300347': '泰格医药', 'sz002821': '凯莱英',
    'sh688180': '君实生物', 'sz300558': '贝达药业', 'sz300474': '景嘉微',
    'sh688036': '传音控股', 'sh603288': '海天味业', 'sh600598': '北大荒',
    'sh601225': '陕西煤业', 'sh600988': '赤峰黄金', 'sh600025': '华能水电',
    'sh600886': '国投电力', 'sh600566': '济川药业', 'sh600362': '江西铜业',
    'sh601857': '中国石油', 'sh600028': '中国石化', 'sz000969': '安泰科技',
    'sh600893': '航发动力', 'sh600745': '闻泰科技', 'sh600879': '航天电子',
    'sh600592': '龙溪股份', 'sh688120': '华海清科', 'sh600551': '时代出版',
    'sh600688': '上海石化', 'sh600579': '中化装备', 'sz300131': '英唐智控',
}

def get_stock_name(code):
    """Get stock name, fetching from quote if not in popular list"""
    if code in POPULAR:
        return POPULAR[code]
    # Try to fetch from quote
    try:
        import sys, os
        sys.path.insert(0, str(SKILL_ROOT))
        os.chdir(str(SKILL_ROOT))
        from data import get_quote
        q = get_quote(code)
        name = q.name if hasattr(q, 'name') and q.name else ''
        if name:
            POPULAR[code] = name
            return name
    except:
        pass
    return ''

def get_pinyin_initials(name):
    """拼音首字母映射 - 完整覆盖A股常见字"""
    pmap = {
        '安':'A','百':'B','宝':'B','北':'B','贝':'B','比':'B','博':'B','邦':'B','保':'B','白':'B','波':'B','包':'B','本':'B',
        '长':'C','传':'C','创':'C','春':'C','赤':'C','川':'C','晨':'C','成':'C','城':'C','程':'C','车':'C','材':'C','纯':'C','楚':'C','超':'C','慈':'C','磁':'C','崇':'C',
        '大':'D','德':'D','电':'D','东':'D','动':'D','达':'D','迪':'D','地':'D','道':'D','鼎':'D','多':'D','岛':'D','第':'D','当':'D',
        '恩':'E','二':'E','尔':'E','鹅':'E',
        '方':'F','飞':'F','福':'F','复':'F','风':'F','富':'F','汾':'F','发':'F','丰':'F','房':'F','纺':'F','钒':'F','奉':'F',
        '国':'G','高':'G','光':'G','广':'G','工':'G','歌':'G','港':'G','桂':'G','格':'G','冠':'G','钢':'G','谷':'G',
        '华':'H','海':'H','恒':'H','航':'H','豪':'H','合':'H','寒':'H','宏':'H','汇':'H','湖':'H','化':'H','杭':'H','汉':'H','惠':'H','和':'H','瀚':'H','好':'H',
        '金':'J','九':'J','景':'J','君':'J','江':'J','机':'J','京':'J','嘉':'J','均':'J','健':'J','洁':'J','巨':'J','建':'J','集':'J','吉':'J','加':'J','锦':'J','晶':'J','精':'J',
        '凯':'K','科':'K','康':'K','口':'K','矿':'K','开':'K','客':'K','可':'K','坤':'K','克':'K',
        '立':'L','联':'L','龙':'L','澜':'L','蓝':'L','绿':'L','力':'L','利':'L','路':'L','理':'L','良':'L','领':'L','旅':'L','凌':'L','鲁':'L','隆':'L','浪':'L','罗':'L','洛':'L',
        '明':'M','民':'M','牧':'M','美':'M','茅':'M','迈':'M','名':'M','煤':'M','墨':'M','密':'M',
        '能':'N','南':'N','宁':'N','农':'N','牛':'N','纳':'N','诺':'N',
        '片':'P','平':'P','派':'P','浦':'P','鹏':'P','普':'P','品':'P',
        '齐':'Q','青':'Q','千':'Q','旗':'Q','泉':'Q','启':'Q','奇':'Q','前':'Q','秦':'Q','强':'Q','全':'Q','潜':'Q',
        '人':'R','日':'R','荣':'R','瑞':'R','润':'R','软':'R','燃':'R','融':'R','若':'R','锐':'R',
        '三':'S','上':'S','生':'S','神':'S','水':'S','深':'S','赛':'S','时':'S','士':'S','数':'S','山':'S','盛':'S','石':'S','世':'S','首':'S','顺':'S','双':'S','苏':'S','四':'S','思':'S',
        '天':'T','太':'T','通':'T','拓':'T','泰':'T','同':'T','特':'T','唐':'T','铁':'T','图':'T','钛':'T','腾':'T','桐':'T',
        '万':'W','闻':'W','微':'W','文':'W','韦':'W','五':'W','维':'W','网':'W','物':'W','伟':'W','王':'W','卫':'W','旺':'W','威':'W',
        '新':'X','信':'X','星':'X','先':'X','兴':'X','西':'X','小':'X','雄':'X','芯':'X','学':'X','现':'X','湘':'X','协':'X','雪':'X',
        '阳':'Y','药':'Y','亿':'Y','用':'Y','云':'Y','医':'Y','永':'Y','一':'Y','有':'Y','银':'Y','兖':'Y','伊':'Y','洋':'Y','远':'Y','亚':'Y','烟':'Y','谊':'Y','源':'Y','鱼':'Y','盈':'Y','扬':'Y','友':'Y','易':'Y','悦':'Y','英':'Y','元':'Y','韵':'Y','应':'Y',
        '中':'Z','紫':'Z','兆':'Z','卓':'Z','智':'Z','招':'Z','泽':'Z','证':'Z','重':'Z','张':'Z','浙':'Z','正':'Z','之':'Z','洲':'Z','志':'Z','展':'Z','珠':'Z','振':'Z','章':'Z','轴':'Z','臻':'Z',
    }
    return ''.join(pmap.get(c, c[0].upper()) for c in name)


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
        for code in STOCKS:
            code_short = code.replace('sh', '').replace('sz', '').replace('bj', '')
            name = POPULAR.get(code, '')
            score = 0
            if q == code: score = 100
            elif q == code_short: score = 95
            elif code_short.startswith(q): score = 80
            elif q in code_short: score = 70
            if score > 0:
                results.append({'code': code, 'code_short': code_short,
                    'name': name or code_short, 'pinyin': get_pinyin_initials(name) if name else '', 'score': score})
    else:
        # Search popular stocks by name / pinyin
        for code, name in POPULAR.items():
            code_short = code.replace('sh', '').replace('sz', '').replace('bj', '')
            pinyin = get_pinyin_initials(name)
            score = 0
            if q == name: score = 90
            elif q in name: score = 60
            elif q == pinyin: score = 85
            elif q in pinyin: score = 50
            if score > 0:
                results.append({'code': code, 'code_short': code_short,
                    'name': name, 'pinyin': pinyin, 'score': score})

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


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8820, debug=False)
