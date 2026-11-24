"""Analytics package initialization."""
from backend.analytics.metrics import (
    calculate_profit,
    calculate_roi,
    calculate_engagement_rate,
    aggregate_agency_metrics,
    rank_reels_by_profit,
    rank_reels_by_roi,
    find_high_views_low_profit,
    compare_agencies,
    compare_campaigns,
    summarize_performance,
)

__all__ = [
    "calculate_profit",
    "calculate_roi",
    "calculate_engagement_rate",
    "aggregate_agency_metrics",
    "rank_reels_by_profit",
    "rank_reels_by_roi",
    "find_high_views_low_profit",
    "compare_agencies",
    "compare_campaigns",
    "summarize_performance",
]
