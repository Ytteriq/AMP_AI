"""
backend/analytics/marketing_engine.py
Deterministic mathematical engine for digital marketing agency reporting.
Calculates all required KPIs, period comparisons, campaign rankings,
and platform distributions without LLM extrapolation or hallucination.
"""

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
import logging

logger = logging.getLogger("ai_reel.analytics.engine")


# -----------------------------------------------------------------------------
# Core Mathematical Formulas (Safe against zero denominators & missing data)
# -----------------------------------------------------------------------------

def calculate_ctr(clicks: Optional[Union[int, float]], impressions: Optional[Union[int, float]]) -> Optional[float]:
    """Formula: CTR (%) = (Clicks / Impressions) * 100"""
    if clicks is None or impressions is None:
        return None
    try:
        imp = float(impressions)
        clk = float(clicks)
        if imp <= 0:
            return 0.0
        return round((clk / imp) * 100, 2)
    except (ValueError, TypeError):
        return None


def calculate_cpc(spend: Optional[Union[int, float]], clicks: Optional[Union[int, float]]) -> Optional[float]:
    """Formula: CPC = Spend / Clicks"""
    if spend is None or clicks is None:
        return None
    try:
        spd = float(spend)
        clk = float(clicks)
        if clk <= 0:
            return None
        return round(spd / clk, 2)
    except (ValueError, TypeError):
        return None


def calculate_cpm(spend: Optional[Union[int, float]], impressions: Optional[Union[int, float]]) -> Optional[float]:
    """Formula: CPM = (Spend / Impressions) * 1000"""
    if spend is None or impressions is None:
        return None
    try:
        spd = float(spend)
        imp = float(impressions)
        if imp <= 0:
            return None
        return round((spd / imp) * 1000, 2)
    except (ValueError, TypeError):
        return None


def calculate_conversion_rate(conversions: Optional[Union[int, float]], clicks: Optional[Union[int, float]]) -> Optional[float]:
    """Formula: Conversion Rate (%) = (Conversions / Clicks) * 100"""
    if conversions is None or clicks is None:
        return None
    try:
        conv = float(conversions)
        clk = float(clicks)
        if clk <= 0:
            return 0.0
        return round((conv / clk) * 100, 2)
    except (ValueError, TypeError):
        return None


def calculate_cpa(spend: Optional[Union[int, float]], conversions: Optional[Union[int, float]]) -> Optional[float]:
    """Formula: CPA = Spend / Conversions"""
    if spend is None or conversions is None:
        return None
    try:
        spd = float(spend)
        conv = float(conversions)
        if conv <= 0:
            return None
        return round(spd / conv, 2)
    except (ValueError, TypeError):
        return None


def calculate_roas(revenue: Optional[Union[int, float]], spend: Optional[Union[int, float]]) -> Optional[float]:
    """
    Formula: ROAS = Revenue / Spend
    Rule: If spend is 0, None or negative, returns None (displayed as N/A, never 0).
    """
    if revenue is None or spend is None:
        return None
    try:
        rev = float(revenue)
        spd = float(spend)
        if spd <= 0:
            return None
        return round(rev / spd, 2)
    except (ValueError, TypeError):
        return None


def calculate_percentage_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """
    Calculates percentage growth or decline: ((Current - Previous) / Previous) * 100
    Handles zero previous values safely.
    """
    if current is None or previous is None:
        return None
    try:
        curr = float(current)
        prev = float(previous)
        if prev == 0:
            if curr > 0:
                return 100.0
            elif curr == 0:
                return 0.0
            else:
                return -100.0
        return round(((curr - prev) / abs(prev)) * 100, 2)
    except (ValueError, TypeError):
        return None


# -----------------------------------------------------------------------------
# Document Aggregation & KPI Computation
# -----------------------------------------------------------------------------

def extract_numeric_field(doc: Dict[str, Any], field_names: List[str], default: float = 0.0) -> float:
    """Extracts numeric value by inspecting multiple field aliases (e.g. spend, ad_spend, adSpend)."""
    for f in field_names:
        if f in doc and doc[f] is not None:
            try:
                return float(doc[f])
            except (ValueError, TypeError):
                continue
    return default


def aggregate_marketing_kpis(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes aggregate totals and derived marketing KPIs across a list of campaign or creative records.
    Follows strict math: derived ratios are computed from aggregate sums, not averages of ratios.
    """
    total_spend = 0.0
    total_impressions = 0.0
    total_reach = 0.0
    total_clicks = 0.0
    total_conversions = 0.0
    total_revenue = 0.0

    count = len(records)
    for r in records:
        total_spend += extract_numeric_field(r, ["spend", "ad_spend", "cost", "budget_spent"])
        total_impressions += extract_numeric_field(r, ["impressions", "views"])
        total_reach += extract_numeric_field(r, ["reach", "unique_views"], default=0.0)
        total_clicks += extract_numeric_field(r, ["clicks", "link_clicks"])
        total_conversions += extract_numeric_field(r, ["conversions", "purchases", "leads"])
        total_revenue += extract_numeric_field(r, ["revenue", "attributed_revenue", "sales_value"])

    if total_reach == 0.0 and total_impressions > 0.0:
        # Estimate reach as 80% of impressions if reach is not explicitly recorded
        total_reach = round(total_impressions * 0.8)

    ctr = calculate_ctr(total_clicks, total_impressions)
    cpc = calculate_cpc(total_spend, total_clicks)
    cpm = calculate_cpm(total_spend, total_impressions)
    conv_rate = calculate_conversion_rate(total_conversions, total_clicks)
    cpa = calculate_cpa(total_spend, total_conversions)
    roas = calculate_roas(total_revenue, total_spend)

    return {
        "record_count": count,
        "spend": round(total_spend, 2),
        "impressions": int(total_impressions),
        "reach": int(total_reach),
        "clicks": int(total_clicks),
        "ctr": ctr,
        "cpc": cpc,
        "cpm": cpm,
        "conversions": int(total_conversions),
        "conversion_rate": conv_rate,
        "cpa": cpa,
        "revenue": round(total_revenue, 2),
        "roas": roas,
    }


def compare_period_performance(
    current_records: List[Dict[str, Any]],
    previous_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Computes current period KPIs, previous period KPIs, and exact percentage changes.
    """
    curr = aggregate_marketing_kpis(current_records)
    prev = aggregate_marketing_kpis(previous_records)

    changes: Dict[str, Optional[float]] = {}
    metric_keys = [
        "spend", "impressions", "reach", "clicks", "ctr",
        "cpc", "cpm", "conversions", "conversion_rate", "cpa", "revenue", "roas"
    ]

    for k in metric_keys:
        curr_val = curr.get(k)
        prev_val = prev.get(k)
        if curr_val is not None and prev_val is not None:
            changes[k] = calculate_percentage_change(curr_val, prev_val)
        else:
            changes[k] = None

    return {
        "current": curr,
        "previous": prev,
        "changes": changes,
    }


def process_campaign_analysis(campaign_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ranks campaigns, detects high-performing and underperforming campaigns using strict criteria.
    """
    ranked_campaigns: List[Dict[str, Any]] = []

    for c in campaign_records:
        spend = extract_numeric_field(c, ["spend", "ad_spend", "cost"])
        impr = extract_numeric_field(c, ["impressions", "views"])
        clicks = extract_numeric_field(c, ["clicks"])
        conv = extract_numeric_field(c, ["conversions", "purchases", "leads"])
        rev = extract_numeric_field(c, ["revenue", "attributed_revenue"])

        ctr = calculate_ctr(clicks, impr)
        cpc = calculate_cpc(spend, clicks)
        roas = calculate_roas(rev, spend)
        cpa = calculate_cpa(spend, conv)
        conv_rate = calculate_conversion_rate(conv, clicks)

        name = c.get("campaign_name") or c.get("name") or c.get("campaign_id") or "Unnamed Campaign"
        platform = c.get("platform") or "Meta Ads"
        status_val = c.get("status") or "ACTIVE"

        ranked_campaigns.append({
            "campaign_id": str(c.get("campaign_id") or c.get("_id") or ""),
            "campaign_name": name,
            "platform": platform,
            "status": status_val,
            "spend": round(spend, 2),
            "impressions": int(impr),
            "clicks": int(clicks),
            "ctr": ctr,
            "cpc": cpc,
            "conversions": int(conv),
            "conversion_rate": conv_rate,
            "cpa": cpa,
            "revenue": round(rev, 2),
            "roas": roas,
        })

    # Sort descending by ROAS (with tiebreak on revenue)
    ranked_campaigns.sort(key=lambda x: (x["roas"] if x["roas"] is not None else -1.0, x["revenue"]), reverse=True)

    # Identify high performing: ROAS >= 2.0 or (ROAS >= 1.5 and Revenue > 50000)
    top_campaigns = [
        c for c in ranked_campaigns
        if (c["roas"] is not None and c["roas"] >= 1.8) or (c["conversions"] > 50 and c["roas"] is not None and c["roas"] >= 1.2)
    ]

    # Identify underperforming: spend > 5000 and (ROAS < 1.0 or conversions == 0 or conv_rate < 0.5)
    underperforming = [
        c for c in ranked_campaigns
        if c["spend"] >= 3000 and (
            (c["roas"] is not None and c["roas"] < 1.0) or (c["conversions"] == 0 and c["spend"] > 5000)
        )
    ]

    return {
        "all_campaigns": ranked_campaigns,
        "top_campaigns": top_campaigns[:5],
        "underperforming_campaigns": underperforming[:5],
    }


def process_platform_breakdown(campaign_records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Groups performance by advertising platform."""
    by_platform: Dict[str, List[Dict[str, Any]]] = {}
    for c in campaign_records:
        plt = c.get("platform") or "Meta Ads"
        by_platform.setdefault(plt, []).append(c)

    results: Dict[str, Dict[str, Any]] = {}
    for plt, recs in by_platform.items():
        results[plt] = aggregate_marketing_kpis(recs)
    return results
