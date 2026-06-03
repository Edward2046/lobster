# reports/__init__.py

from service.reports.finance import build_report as build_finance_report
from service.reports.earnings import build_report as build_earnings_report
from service.reports.food_trends import build_report as build_food_trends_report
from service.reports.tech_news import build_report as build_tech_news_report

__all__ = [
    "build_finance_report",
    "build_earnings_report",
    "build_food_trends_report",
    "build_tech_news_report",
]
