# earnings_calendar_tool.py — 近期财报日历工具
#
# 数据来源：Nasdaq 财报日历 API（api.nasdaq.com），无需 API key。
# 覆盖范围：美股、加拿大股市等在 Nasdaq 收录的上市公司。
# 过滤规则：只保留市值 >= 10 亿美元的公司，并标注最值得关注的头部公司。

import re
import requests
from datetime import date, timedelta
from smolagents import tool

_NASDAQ_EARNINGS_URL = "https://api.nasdaq.com/api/calendar/earnings"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    # Nasdaq API 会校验 Referer，缺少时返回 403
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}

# 发布时间映射为可读中文
_TIME_MAP = {
    "time-pre-market":   "盘前",
    "time-after-hours":  "盘后",
    "time-not-supplied": "待定",
}

# 市值门槛（单位：美元）
_MIN_MARKET_CAP = 1_000_000_000       # 10 亿，基础过滤线
_HIGHLIGHT_CAP  = 10_000_000_000      # 100 亿，标注为重点关注


def _parse_market_cap(raw: str) -> int:
    """将 '$444,952,441,942' 格式的市值字符串解析为整数，解析失败返回 0。"""
    digits = re.sub(r"[^\d]", "", raw)  # 去掉 $、逗号等非数字字符
    return int(digits) if digits else 0


def _format_cap(value: int) -> str:
    """将市值整数格式化为易读的缩写，如 $444.9B、$5.2B、$980M。"""
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    return f"${value / 1_000_000:.0f}M"


def _fetch_one_day(target_date: str) -> list[dict]:
    """拉取单日财报列表，返回 row 列表，失败返回空列表。"""
    try:
        resp = requests.get(
            _NASDAQ_EARNINGS_URL,
            params={"date": target_date},
            headers=_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json().get("data", {}).get("rows") or []
        for row in rows:
            row["_date"] = target_date
            row["_cap_int"] = _parse_market_cap(row.get("marketCap", ""))
        return rows
    except Exception:
        return []


@tool
def get_earnings_calendar(days: int = 7) -> str:
    """Get upcoming earnings reports for the next N days, filtered to companies
    with market cap >= $1B. Highlights top companies (market cap >= $10B).

    Data source: Nasdaq earnings calendar API. Covers US-listed companies.

    Args:
        days: Number of days to look ahead from today (1-14). Defaults to 7.
    """
    days = max(1, min(days, 14))

    today = date.today()
    all_rows: list[dict] = []
    for offset in range(days):
        target = (today + timedelta(days=offset)).isoformat()
        all_rows.extend(_fetch_one_day(target))

    if not all_rows:
        return "No earnings data found for the requested period."

    # 过滤：只保留市值 >= 10 亿美元的公司
    filtered = [r for r in all_rows if r["_cap_int"] >= _MIN_MARKET_CAP]
    if not filtered:
        return "No companies with market cap >= $1B found in the requested period."

    # 按日期分组，组内按市值降序排列
    seen_dates: list[str] = []
    by_date: dict[str, list[dict]] = {}
    for row in filtered:
        d = row["_date"]
        if d not in by_date:
            seen_dates.append(d)
            by_date[d] = []
        by_date[d].append(row)
    for d in seen_dates:
        by_date[d].sort(key=lambda r: r["_cap_int"], reverse=True)

    # ── 头部：最值得关注的公司（市值 >= 100 亿，跨所有日期，取前 10）──
    highlights = sorted(
        [r for r in filtered if r["_cap_int"] >= _HIGHLIGHT_CAP],
        key=lambda r: r["_cap_int"],
        reverse=True,
    )[:10]

    lines = [f"未来 {days} 天财报日历（市值 ≥ $1B，数据来源：Nasdaq）\n"]

    if highlights:
        lines.append("★ 最值得关注（市值 ≥ $10B，按市值排序）")
        for row in highlights:
            symbol  = row.get("symbol", "")
            name    = row.get("name", "")
            timing  = _TIME_MAP.get(row.get("time", ""), "待定")
            eps_est = row.get("epsForecast", "")
            cap_str = _format_cap(row["_cap_int"])
            d       = row["_date"]
            line = f"  {symbol:<6} {name[:32]:<32}  {d}  {timing:<4}  市值:{cap_str}"
            if eps_est:
                line += f"  EPS预期:{eps_est}"
            lines.append(line)
        lines.append("")

    # ── 按日期列出所有 $1B+ 公司 ──
    lines.append("── 按日期明细 ──")
    for d in seen_dates:
        rows = by_date[d]
        lines.append(f"\n{d}（{len(rows)} 家，市值 ≥ $1B）")
        for row in rows:
            symbol  = row.get("symbol", "")
            name    = row.get("name", "")
            timing  = _TIME_MAP.get(row.get("time", ""), "待定")
            eps_est = row.get("epsForecast", "")
            qtr     = row.get("fiscalQuarterEnding", "")
            cap_str = _format_cap(row["_cap_int"])
            # 市值 >= 100 亿加星号标注
            star = "★" if row["_cap_int"] >= _HIGHLIGHT_CAP else " "
            line = f" {star} {symbol:<6} {name[:30]:<30}  {timing:<4}  市值:{cap_str}"
            if eps_est:
                line += f"  EPS:{eps_est}"
            if qtr:
                line += f"  财季:{qtr}"
            lines.append(line)

    return "\n".join(lines).strip()
