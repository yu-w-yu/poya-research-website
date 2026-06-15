from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

try:
    import requests
except ModuleNotFoundError:
    requests = None


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
CACHE_DIR = ROOT / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

APP_USER_AGENT = os.getenv(
    "INVEST_APP_USER_AGENT",
    "InvestmentResearchLab/0.1 research prototype contact=local@example.com",
)
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "").strip()


def _cache_key(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def get_json(url: str, ttl_seconds: int = 900) -> dict | list:
    if requests is None:
        raise RuntimeError("requests package is not installed; network analysis API is unavailable.")

    path = _cache_key(url)
    if path.exists() and time.time() - path.stat().st_mtime < ttl_seconds:
        return json.loads(path.read_text(encoding="utf-8"))

    response = requests.get(url, headers={"User-Agent": APP_USER_AGENT}, timeout=20)
    response.raise_for_status()
    data = response.json()
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text in {"", "--", "X", "除權息"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def roc_to_iso(text: str) -> str:
    y, m, d = [int(part) for part in text.split("/")]
    return f"{y + 1911:04d}-{m:02d}-{d:02d}"


def month_starts(months: int = 18) -> list[str]:
    today = dt.date.today()
    cursor = dt.date(today.year, today.month, 1)
    out = []
    for _ in range(months):
        out.append(cursor.strftime("%Y%m01"))
        cursor = dt.date(cursor.year - 1, 12, 1) if cursor.month == 1 else dt.date(cursor.year, cursor.month - 1, 1)
    return out


def fetch_twse(symbol: str) -> dict:
    rows = {}
    warnings = []
    display_name = f"{symbol}.TW"
    for month in month_starts(18):
        params = urlencode({"date": month, "stockNo": symbol, "response": "json"})
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?{params}"
        try:
            payload = get_json(url, ttl_seconds=1800)
        except Exception as exc:
            warnings.append(f"TWSE {month} failed: {exc}")
            continue
        if payload.get("stat") != "OK":
            continue
        if payload.get("title") and display_name == f"{symbol}.TW":
            display_name = payload["title"].split("各日成交資訊")[0].strip()
        for item in payload.get("data", []):
            date = roc_to_iso(item[0])
            rows[date] = {
                "date": date,
                "open": to_float(item[3]),
                "high": to_float(item[4]),
                "low": to_float(item[5]),
                "close": to_float(item[6]),
                "volume": to_float(item[1]),
            }
    if len(rows) < 60:
        try:
            for item in fetch_finmind_tw_stock_price(symbol):
                rows[item["date"]] = item
        except Exception as exc:
            warnings.append(f"FinMind fallback failed: {exc}")
    prices = [v for _, v in sorted(rows.items()) if v["close"] is not None]
    if not prices:
        raise ValueError("沒有回傳可分析的台股價格資料。請確認股票代碼，例如 2330、2308。")
    return {
        "market": "TWSE",
        "symbol": symbol,
        "name": display_name,
        "currency": "TWD",
        "prices": prices,
        "fundamentals": {},
        "filings": [],
        "sources": [
            {
                "name": "TWSE 個股日成交資訊",
                "url": "https://www.twse.com.tw/zh/trading/historical/stock-day.html",
                "note": "官方上市股票日成交資料，後端按月查詢並快取。",
            },
            {
                "name": "FinMind TaiwanStockPrice",
                "url": "https://api.finmindtrade.com/docs",
                "note": "當 TWSE 歷史月份因連續查詢限制或資料不足時，用公開 REST API 補足日線資料。",
            }
        ],
        "warnings": warnings[:6],
    }


def fetch_finmind_tw_stock_price(symbol: str) -> list[dict]:
    end = dt.date.today()
    start = end - dt.timedelta(days=430)
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": symbol,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    if FINMIND_TOKEN:
        params["token"] = FINMIND_TOKEN
    url = f"https://api.finmindtrade.com/api/v4/data?{urlencode(params)}"
    payload = get_json(url, ttl_seconds=1800)
    if payload.get("status") != 200:
        raise ValueError(payload.get("msg") or "FinMind API did not return success")
    rows = []
    for item in payload.get("data", []):
        rows.append(
            {
                "date": item.get("date"),
                "open": to_float(item.get("open")),
                "high": to_float(item.get("max")),
                "low": to_float(item.get("min")),
                "close": to_float(item.get("close")),
                "volume": to_float(item.get("Trading_Volume")),
            }
        )
    return rows


def fetch_alpha_vantage(symbol: str) -> dict:
    if not ALPHA_VANTAGE_API_KEY:
        raise ValueError("美股價格資料需要設定 ALPHA_VANTAGE_API_KEY。台股可直接輸入上市股票代碼，例如 2330。")
    params = urlencode(
        {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol.upper(),
            "outputsize": "compact",
            "apikey": ALPHA_VANTAGE_API_KEY,
        }
    )
    url = f"https://www.alphavantage.co/query?{params}"
    payload = get_json(url, ttl_seconds=900)
    series = payload.get("Time Series (Daily)")
    if not series:
        msg = payload.get("Note") or payload.get("Error Message") or "Alpha Vantage 沒有回傳日線資料。"
        raise ValueError(str(msg))
    prices = []
    for date, row in sorted(series.items()):
        prices.append(
            {
                "date": date,
                "open": to_float(row.get("1. open")),
                "high": to_float(row.get("2. high")),
                "low": to_float(row.get("3. low")),
                "close": to_float(row.get("4. close")),
                "adjustedClose": to_float(row.get("5. adjusted close")),
                "volume": to_float(row.get("6. volume")),
            }
        )
    return {
        "market": "US",
        "symbol": symbol.upper(),
        "name": symbol.upper(),
        "currency": "USD",
        "prices": prices[-260:],
        "fundamentals": fetch_sec_fundamentals(symbol.upper()),
        "filings": fetch_sec_filings(symbol.upper()),
        "sources": [
            {
                "name": "Alpha Vantage TIME_SERIES_DAILY_ADJUSTED",
                "url": "https://www.alphavantage.co/documentation/",
                "note": "官方 API，需使用者自己的 API key；依方案限制請求頻率。",
            },
            {
                "name": "SEC EDGAR data.sec.gov",
                "url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
                "note": "官方公開申報與 XBRL 財務資料。",
            },
        ],
        "warnings": [],
    }


def sec_ticker_map() -> dict:
    data = get_json("https://www.sec.gov/files/company_tickers.json", ttl_seconds=86400)
    return {item["ticker"].upper(): item for item in data.values()}


def latest_fact(company_facts: dict, names: list[str], unit: str = "USD") -> float | None:
    facts = company_facts.get("facts", {}).get("us-gaap", {})
    candidates = []
    for name in names:
        units = facts.get(name, {}).get("units", {})
        for item in units.get(unit, []):
            if "fy" in item and "val" in item and item.get("form") in {"10-K", "10-Q", "20-F", "40-F"}:
                candidates.append(item)
    if not candidates:
        return None
    candidates.sort(key=lambda x: (str(x.get("end", "")), str(x.get("filed", ""))))
    return float(candidates[-1]["val"])


def annual_series(company_facts: dict, names: list[str], unit: str = "USD") -> list[dict]:
    facts = company_facts.get("facts", {}).get("us-gaap", {})
    rows = []
    for name in names:
        for item in facts.get(name, {}).get("units", {}).get(unit, []):
            if item.get("form") in {"10-K", "20-F", "40-F"} and "fy" in item and "val" in item:
                rows.append({"fy": item["fy"], "val": float(item["val"]), "filed": item.get("filed", "")})
    latest_by_year = {}
    for row in rows:
        if row["fy"] not in latest_by_year or row["filed"] > latest_by_year[row["fy"]]["filed"]:
            latest_by_year[row["fy"]] = row
    return [latest_by_year[k] for k in sorted(latest_by_year)[-5:]]


def yoy(series: list[dict]) -> float | None:
    if len(series) < 2 or not series[-2]["val"]:
        return None
    return (series[-1]["val"] / series[-2]["val"] - 1) * 100


def fetch_sec_fundamentals(symbol: str) -> dict:
    try:
        item = sec_ticker_map().get(symbol.upper())
        if not item:
            return {}
        cik = f"{int(item['cik_str']):010d}"
        facts = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", ttl_seconds=86400)
        revenue = annual_series(facts, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"])
        income = annual_series(facts, ["NetIncomeLoss"])
        assets = latest_fact(facts, ["Assets"])
        liabilities = latest_fact(facts, ["Liabilities"])
        return {
            "companyName": item.get("title"),
            "cik": cik,
            "revenueYoY": yoy(revenue),
            "netIncomeYoY": yoy(income),
            "latestRevenue": revenue[-1]["val"] if revenue else None,
            "latestNetIncome": income[-1]["val"] if income else None,
            "debtToAssets": (liabilities / assets * 100) if liabilities and assets else None,
        }
    except Exception as exc:
        return {"warning": f"SEC fundamentals failed: {exc}"}


def fetch_sec_filings(symbol: str) -> list[dict]:
    try:
        item = sec_ticker_map().get(symbol.upper())
        if not item:
            return []
        cik = f"{int(item['cik_str']):010d}"
        data = get_json(f"https://data.sec.gov/submissions/CIK{cik}.json", ttl_seconds=3600)
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        desc = recent.get("primaryDocDescription", [])
        filings = []
        for i, form in enumerate(forms[:30]):
            if form in {"10-K", "10-Q", "8-K", "20-F", "6-K"}:
                filings.append(
                    {
                        "form": form,
                        "date": dates[i] if i < len(dates) else "",
                        "description": desc[i] if i < len(desc) else "",
                        "accession": accessions[i] if i < len(accessions) else "",
                    }
                )
            if len(filings) >= 6:
                break
        return filings
    except Exception:
        return []


def sma(values: list[float], n: int) -> float | None:
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def pct(a, b):
    if a is None or b in (None, 0):
        return None
    return (a / b - 1) * 100


def rsi(values: list[float], n: int = 14) -> float | None:
    if len(values) <= n:
        return None
    gains = []
    losses = []
    for i in range(-n, 0):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))
    avg_gain = sum(gains) / n
    avg_loss = sum(losses) / n
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def atr(prices: list[dict], n: int = 14) -> float | None:
    if len(prices) <= n:
        return None
    trs = []
    for i in range(1, len(prices)):
        high = prices[i]["high"]
        low = prices[i]["low"]
        prev = prices[i - 1]["close"]
        if None not in (high, low, prev):
            trs.append(max(high - low, abs(high - prev), abs(low - prev)))
    if len(trs) < n:
        return None
    return sum(trs[-n:]) / n


def local_levels(prices: list[dict], current: float) -> dict:
    window = prices[-90:]
    lows = [p["low"] for p in window if p.get("low")]
    highs = [p["high"] for p in window if p.get("high")]
    if not lows or not highs:
        return {"support": None, "resistance": None}
    supports = sorted([x for x in lows if x <= current * 0.995], reverse=True)
    resistances = sorted([x for x in highs if x >= current * 1.005])
    return {
        "support": supports[0] if supports else min(lows),
        "resistance": resistances[0] if resistances else max(highs),
    }


def format_money(value):
    if value is None:
        return None
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    return f"{value:.2f}"


def score_to_label(score: int) -> str:
    if score >= 3:
        return "偏多"
    if score <= -3:
        return "偏空"
    return "中性"


def build_agents(context: dict) -> dict:
    ind = context["indicators"]
    current = context["quote"]["close"]
    support = context["levels"]["support"]
    resistance = context["levels"]["resistance"]
    atr_value = ind.get("atr14") or (current * 0.03)
    fundamentals = context.get("fundamentals") or {}

    agents = []

    technical_score = 0
    tech_points = []
    if ind.get("sma20") and current > ind["sma20"]:
        technical_score += 1
        tech_points.append("收盤價站上 20 日均線")
    if ind.get("sma60") and current > ind["sma60"]:
        technical_score += 1
        tech_points.append("中期均線結構偏強")
    if ind.get("rsi14") and ind["rsi14"] > 70:
        technical_score -= 1
        tech_points.append("RSI 進入偏熱區")
    elif ind.get("rsi14") and ind["rsi14"] < 35:
        technical_score += 1
        tech_points.append("RSI 接近低檔反彈區")
    agents.append(
        {
            "name": "技術交易員",
            "stance": score_to_label(technical_score),
            "score": technical_score,
            "notes": tech_points or ["價格與均線訊號未形成明確方向"],
        }
    )

    risk_score = 0
    risk_points = []
    if ind.get("volatility20") and ind["volatility20"] > 35:
        risk_score -= 1
        risk_points.append("近 20 日年化波動偏高，部位需縮小")
    if support and current and (current - support) / current < 0.03:
        risk_score += 1
        risk_points.append("價格接近支撐區，停損距離可控")
    if resistance and current and (resistance - current) / current < 0.03:
        risk_score -= 1
        risk_points.append("上方壓力距離過近，追價風險提高")
    agents.append(
        {
            "name": "風控經理",
            "stance": score_to_label(risk_score),
            "score": risk_score,
            "notes": risk_points or ["目前風險沒有極端訊號，仍需設定停損與部位上限"],
        }
    )

    fundamental_score = 0
    fundamental_points = []
    if fundamentals.get("revenueYoY") is not None:
        if fundamentals["revenueYoY"] > 5:
            fundamental_score += 1
            fundamental_points.append(f"最近年度營收年增 {fundamentals['revenueYoY']:.1f}%")
        elif fundamentals["revenueYoY"] < -5:
            fundamental_score -= 1
            fundamental_points.append(f"最近年度營收年減 {abs(fundamentals['revenueYoY']):.1f}%")
    if fundamentals.get("netIncomeYoY") is not None:
        if fundamentals["netIncomeYoY"] > 5:
            fundamental_score += 1
            fundamental_points.append(f"淨利年增 {fundamentals['netIncomeYoY']:.1f}%")
        elif fundamentals["netIncomeYoY"] < -5:
            fundamental_score -= 1
            fundamental_points.append(f"淨利年減 {abs(fundamentals['netIncomeYoY']):.1f}%")
    if fundamentals.get("debtToAssets") is not None and fundamentals["debtToAssets"] > 75:
        fundamental_score -= 1
        fundamental_points.append(f"負債佔資產 {fundamentals['debtToAssets']:.1f}%，槓桿偏高")
    agents.append(
        {
            "name": "基本面分析師",
            "stance": score_to_label(fundamental_score),
            "score": fundamental_score,
            "notes": fundamental_points or ["目前資料源未提供足夠基本面資料；以價格與量能訊號為主"],
        }
    )

    catalyst_score = 0
    catalyst_points = []
    for filing in context.get("filings", [])[:3]:
        catalyst_points.append(f"{filing.get('date')} {filing.get('form')} {filing.get('description')}".strip())
    if catalyst_points:
        catalyst_points.insert(0, "近期 SEC 申報需納入事件風險檢查")
    agents.append(
        {
            "name": "事件研究員",
            "stance": score_to_label(catalyst_score),
            "score": catalyst_score,
            "notes": catalyst_points or ["未取得即時新聞授權來源；本版不抓取新聞網站，只列官方資料與價格事件"],
        }
    )

    total = sum(agent["score"] for agent in agents)
    consensus = score_to_label(total)
    entry_pullback = support + 0.35 * atr_value if support else current - atr_value
    entry_pullback = min(entry_pullback, current * 0.995)
    entry_breakout = resistance + 0.1 * atr_value if resistance else current + atr_value
    stop = (support - 0.8 * atr_value) if support else current - 1.5 * atr_value
    target = resistance if resistance and resistance > current else current + 2 * atr_value

    horizons = {
        "short": {
            "label": "短線 1-10 日",
            "view": score_to_label(technical_score + risk_score),
            "plan": "回測支撐不破可低接；若放量突破壓力，採突破追蹤。跌破停損區則撤退。",
        },
        "medium": {
            "label": "中線 2-12 週",
            "view": score_to_label(technical_score + fundamental_score),
            "plan": "觀察 20/60 日均線是否維持多頭排列，量縮回檔優於急漲追價。",
        },
        "long": {
            "label": "長線 6-24 月",
            "view": score_to_label(fundamental_score),
            "plan": "長線以基本面成長、資本結構與財報更新驗證；資料不足時不應只憑技術面持有。",
        },
    }

    return {
        "agents": agents,
        "consensus": {
            "stance": consensus,
            "score": total,
            "summary": "團隊共識由技術、風控、基本面與事件資料加權形成；它是研究輔助，不是保證獲利的交易訊號。",
            "buyZone": round(entry_pullback, 2),
            "breakoutBuy": round(entry_breakout, 2),
            "stopLoss": round(max(stop, 0), 2),
            "takeProfit": round(target, 2),
        },
        "horizons": horizons,
    }


def analyze_dataset(dataset: dict) -> dict:
    prices = dataset["prices"]
    closes = [p["close"] for p in prices if p.get("close") is not None]
    if len(closes) < 20:
        raise ValueError("有效價格資料少於 20 筆，無法產生可靠技術分析。")

    current = prices[-1]
    previous = prices[-2] if len(prices) > 1 else current
    returns = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes)) if closes[i - 1]]
    recent_returns = returns[-20:] if len(returns) >= 20 else returns
    volatility20 = (math.sqrt(252) * (sum((x - sum(recent_returns) / len(recent_returns)) ** 2 for x in recent_returns) / max(len(recent_returns) - 1, 1)) ** 0.5 * 100) if recent_returns else None
    levels = local_levels(prices, current["close"])
    indicators = {
        "sma20": sma(closes, 20),
        "sma60": sma(closes, 60),
        "sma120": sma(closes, 120),
        "rsi14": rsi(closes, 14),
        "atr14": atr(prices, 14),
        "volatility20": volatility20,
        "change1d": pct(current["close"], previous["close"]),
        "change20d": pct(current["close"], closes[-21] if len(closes) > 20 else None),
        "change60d": pct(current["close"], closes[-61] if len(closes) > 60 else None),
    }
    context = {
        "quote": {
            "date": current["date"],
            "open": current["open"],
            "high": current["high"],
            "low": current["low"],
            "close": current["close"],
            "volume": current.get("volume"),
            "previousClose": previous["close"],
        },
        "levels": levels,
        "indicators": indicators,
        "fundamentals": dataset.get("fundamentals", {}),
        "filings": dataset.get("filings", []),
    }
    agent_result = build_agents(context)
    return {
        **dataset,
        "prices": prices[-180:],
        "quote": context["quote"],
        "levels": levels,
        "indicators": indicators,
        "fundamentalsFormatted": {
            k: (round(v, 2) if isinstance(v, float) else v) for k, v in dataset.get("fundamentals", {}).items()
        },
        "agents": agent_result["agents"],
        "consensus": agent_result["consensus"],
        "horizons": agent_result["horizons"],
        "disclaimer": "本工具僅供研究與教育用途，不構成投資建議、招攬或保證收益。交易前請自行查證資料並評估風險。",
    }


def fetch_dataset(symbol: str, market: str) -> dict:
    clean = re.sub(r"[^0-9A-Za-z.]", "", symbol).upper()
    if not clean:
        raise ValueError("請輸入股票代碼。")
    if market == "auto":
        market = "twse" if clean.isdigit() else "us"
    if market == "twse":
        return fetch_twse(clean)
    if market == "us":
        return fetch_alpha_vantage(clean.replace(".US", ""))
    raise ValueError("market 只支援 auto、twse、us。")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def write_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/analyze":
            try:
                qs = parse_qs(parsed.query)
                symbol = qs.get("symbol", ["2330"])[0]
                market = qs.get("market", ["auto"])[0].lower()
                dataset = fetch_dataset(symbol, market)
                self.write_json(analyze_dataset(dataset))
            except Exception as exc:
                self.write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/health":
            self.write_json({"ok": True})
            return
        super().do_GET()


def main():
    port = int(os.getenv("PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Investment research app running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
