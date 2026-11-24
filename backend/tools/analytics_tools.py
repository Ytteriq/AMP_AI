"""
tools/analytics_tools.py
Implements analyze_performance LangChain tool.
Consolidates all mathematical, comparative, ranking, and aggregation operations
into a single validated tool interface backed by trusted Python formulas.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from backend.analytics.metrics import (
    analyze_performance_patterns as calc_analyze_performance_patterns,
    analyze_profitable_reels as calc_analyze_profitable_reels,
    calculate_engagement_rate,
    calculate_profit,
    calculate_roi,
    compare_agencies as calc_compare_agencies,
    compare_campaigns as calc_compare_campaigns,
    extract_doc_metrics,
    find_high_views_low_profit,
    find_underperforming_reels as calc_find_underperforming_reels,
    rank_reels_by_profit,
    rank_reels_by_roi,
    summarize_performance,
)
from backend.database.connection import get_collection

SUPPORTED_OPERATIONS = [
    "rank_by_profit",
    "rank_by_roi",
    "calculate_profit",
    "calculate_roi",
    "calculate_engagement_rate",
    "compare_reels",
    "compare_agencies",
    "compare_campaigns",
    "compare_periods",
    "summarize_performance",
    "find_high_views_low_profit",
    "find_underperforming_reels",
    "analyze_profitable_reels",
    "analyze_performance_patterns",
]


def _fetch_reels_from_db(
    agency_name: Optional[str] = None,
    campaign_name: Optional[str] = None,
    reel_ids: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Helper to retrieve raw documents from MongoDB for analytical processing."""
    collection = get_collection()
    query: Dict[str, Any] = {}

    if reel_ids:
        query["reel_id"] = {"$in": reel_ids}
    if agency_name:
        query["agency_name"] = {"$regex": f"^{agency_name.strip()}$", "$options": "i"}
    if campaign_name:
        query["campaign_name"] = {"$regex": f"^{campaign_name.strip()}$", "$options": "i"}

    date_filter: Dict[str, Any] = {}
    if start_date:
        try:
            date_filter["$gte"] = datetime.fromisoformat(start_date.strip()).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    if end_date:
        try:
            date_filter["$lte"] = datetime.fromisoformat(end_date.strip()).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    if date_filter:
        query["published_at"] = date_filter

    return list(collection.find(query))


@tool
def analyze_performance(
    operation: str,
    agency_name: Optional[str] = None,
    agency_a: Optional[str] = None,
    agency_b: Optional[str] = None,
    campaign_name: Optional[str] = None,
    campaign_a: Optional[str] = None,
    campaign_b: Optional[str] = None,
    reel_ids: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period_a_start: Optional[str] = None,
    period_a_end: Optional[str] = None,
    period_b_start: Optional[str] = None,
    period_b_end: Optional[str] = None,
    attributed_revenue: Optional[float] = None,
    ad_spend: Optional[float] = None,
    other_costs: Optional[float] = None,
    views: Optional[int] = None,
    likes: Optional[int] = None,
    comments: Optional[int] = None,
    shares: Optional[int] = None,
    saves: Optional[int] = None,
    views_threshold: Optional[float] = None,
    profit_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Perform exact analytics, rankings, comparisons, and financial metrics calculations.

    Supported Operations:
    - 'rank_by_profit': Rank reels by net profit.
    - 'rank_by_roi': Rank reels by percentage ROI.
    - 'calculate_profit': Compute profit = revenue - ad_spend - other_costs.
    - 'calculate_roi': Compute ROI (%) = (profit / ad_spend) * 100.
    - 'calculate_engagement_rate': Compute engagement (%) = (likes + comments + shares + saves) / views * 100.
    - 'compare_reels': Compare 2 or more reels specified in reel_ids.
    - 'compare_agencies': Compare performance between agency_a and agency_b (or all agencies).
    - 'compare_campaigns': Compare performance across campaigns or between campaign_a and campaign_b.
    - 'compare_periods': Compare reel metrics between two date ranges (period_a vs period_b).
    - 'summarize_performance': Executive summary of overall spend, revenue, net profit, ROI, and agency breakdown.
    - 'find_high_views_low_profit': Identify reels with viral reach but low/negative profit.
    """
    op = operation.strip().lower() if operation else ""
    if op not in SUPPORTED_OPERATIONS:
        return {
            "error": f"Unsupported operation '{operation}'. Supported operations: {SUPPORTED_OPERATIONS}",
            "status": "failed",
        }

    # 1. Direct mathematical calculations
    if op == "calculate_profit":
        result = calculate_profit(attributed_revenue, ad_spend, other_costs)
        if result is None:
            return {
                "error": "Missing or invalid inputs. attributed_revenue, ad_spend, and other_costs are all required.",
                "status": "incomplete_data",
            }
        return {
            "operation": "calculate_profit",
            "attributed_revenue": attributed_revenue,
            "ad_spend": ad_spend,
            "other_costs": other_costs,
            "profit": result,
            "currency": "INR",
        }

    if op == "calculate_roi":
        profit_val = calculate_profit(attributed_revenue, ad_spend, other_costs) if (attributed_revenue is not None and other_costs is not None) else None
        # If profit wasn't directly calculable from revenue/costs, check if ad_spend is valid
        result = calculate_roi(profit_val, ad_spend) if profit_val is not None else None
        if result is None:
            return {
                "error": "Cannot compute ROI: ad_spend must be positive and profit must be defined.",
                "ad_spend": ad_spend,
                "status": "zero_spend_or_missing",
            }
        return {
            "operation": "calculate_roi",
            "profit": profit_val,
            "ad_spend": ad_spend,
            "roi_percentage": result,
        }

    if op == "calculate_engagement_rate":
        rate = calculate_engagement_rate(views, likes, comments, shares, saves)
        if rate is None:
            return {
                "error": "Missing metrics: views, likes, comments, shares, and saves must all be provided.",
                "status": "incomplete_data",
            }
        return {
            "operation": "calculate_engagement_rate",
            "views": views,
            "total_interactions": (likes or 0) + (comments or 0) + (shares or 0) + (saves or 0),
            "engagement_rate_percentage": rate,
        }

    # 2. Database-backed operations
    reels = _fetch_reels_from_db(
        agency_name=agency_name,
        campaign_name=campaign_name,
        reel_ids=reel_ids,
        start_date=start_date,
        end_date=end_date,
    )

    if not reels and op not in ["compare_periods"]:
        return {
            "operation": op,
            "error": "No reel records found in MongoDB matching the specified criteria.",
            "records_count": 0,
        }

    if op == "rank_by_profit":
        ranked = rank_reels_by_profit(reels)
        return {
            "operation": "rank_by_profit",
            "total_reels": len(ranked),
            "top_performer": ranked[0] if ranked else None,
            "rankings": ranked,
        }

    if op == "rank_by_roi":
        ranked = rank_reels_by_roi(reels)
        return {
            "operation": "rank_by_roi",
            "total_reels": len(ranked),
            "top_performer": ranked[0] if ranked else None,
            "rankings": ranked,
        }

    if op == "find_high_views_low_profit":
        flagged = find_high_views_low_profit(reels, views_threshold, profit_threshold)
        return {
            "operation": "find_high_views_low_profit",
            "total_flagged": len(flagged),
            "reels": flagged,
            "explanation": "These reels achieved high reach but failed to convert into positive or healthy profit margins.",
        }

    if op == "find_underperforming_reels":
        return calc_find_underperforming_reels(
            reels,
            views_threshold=views_threshold,
            profit_threshold=profit_threshold,
        )

    if op == "analyze_profitable_reels":
        return calc_analyze_profitable_reels(reels)

    if op in ["analyze_performance_patterns", "patterns"]:
        return calc_analyze_performance_patterns(reels)

    if op == "compare_agencies":
        return calc_compare_agencies(reels, agency_a=agency_a, agency_b=agency_b)

    if op == "compare_campaigns":
        return calc_compare_campaigns(reels, campaign_a=campaign_a, campaign_b=campaign_b)

    if op == "summarize_performance":
        return summarize_performance(reels)

    if op == "compare_reels":
        parsed = [extract_doc_metrics(r) for r in reels]
        return {
            "operation": "compare_reels",
            "total_reels": len(parsed),
            "reels": parsed,
        }

    if op == "compare_periods":
        reels_a = _fetch_reels_from_db(start_date=period_a_start, end_date=period_a_end)
        reels_b = _fetch_reels_from_db(start_date=period_b_start, end_date=period_b_end)
        summary_a = summarize_performance(reels_a)
        summary_b = summarize_performance(reels_b)
        return {
            "operation": "compare_periods",
            "period_a": {
                "start": period_a_start,
                "end": period_a_end,
                "summary": summary_a,
            },
            "period_b": {
                "start": period_b_start,
                "end": period_b_end,
                "summary": summary_b,
            },
            "profit_growth": (
                round(summary_b["total_net_profit"] - summary_a["total_net_profit"], 2)
                if ("total_net_profit" in summary_a and "total_net_profit" in summary_b)
                else None
            ),
        }

    return {"error": f"Unhandled operation '{op}'"}


@tool
def analyze_profitable_reels(
    top_n: int = 3,
    agency_name: Optional[str] = None,
    campaign_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve valid reel records from MongoDB, calculate exact profit and ROI using established formulas,
    rank reels by profit, identify the top N profitable reels, calculate summary statistics,
    and return structured findings, common characteristics, and a clean table.
    """
    reels = _fetch_reels_from_db(agency_name=agency_name, campaign_name=campaign_name)
    if not reels:
        return {
            "operation": "analyze_profitable_reels",
            "error": "No matching reel records found in MongoDB.",
            "total_reels": 0,
            "reels": [],
        }
    return calc_analyze_profitable_reels(reels, top_n=top_n)


@tool
def analyze_performance_patterns(
    agency_name: Optional[str] = None,
    campaign_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze patterns, trends, and relationships between views, engagement, ad spend, revenue, profit, and ROI.
    Compares the profitable cohort with the underperforming cohort, calculates cohort distributions,
    and returns evidence-based patterns (without claiming correlation proves causation) and a clean table.
    """
    reels = _fetch_reels_from_db(agency_name=agency_name, campaign_name=campaign_name)
    if not reels:
        return {
            "operation": "analyze_performance_patterns",
            "error": "No matching reel records found in MongoDB.",
            "total_reels": 0,
        }
    return calc_analyze_performance_patterns(reels)


@tool
def compare_agencies(
    agency_a: Optional[str] = None,
    agency_b: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Aggregate and compare performance by agency.
    Calculates total revenue, total ad spend, total profit, engagement rates,
    and agency aggregate ROI (total_profit / total_ad_spend * 100, not average of individual reel ROIs).
    Returns head-to-head comparison and structured table.
    """
    reels = _fetch_reels_from_db()
    if not reels:
        return {
            "operation": "compare_agencies",
            "error": "No matching reel records found in MongoDB.",
        }
    return calc_compare_agencies(reels, agency_a=agency_a, agency_b=agency_b)


@tool
def compare_campaigns(
    campaign_a: Optional[str] = None,
    campaign_b: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Aggregate and compare campaign performance across revenue, profit, ROI, views, and engagement.
    Returns ranked campaign comparisons and structured table.
    """
    reels = _fetch_reels_from_db()
    if not reels:
        return {
            "operation": "compare_campaigns",
            "error": "No matching reel records found in MongoDB.",
        }
    return calc_compare_campaigns(reels, campaign_a=campaign_a, campaign_b=campaign_b)


@tool
def find_underperforming_reels(
    category: str = "all",
    views_threshold: Optional[float] = None,
    revenue_threshold: Optional[float] = None,
    engagement_threshold: Optional[float] = None,
    profit_threshold: Optional[float] = None,
    spend_threshold: Optional[float] = None,
    roi_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Identify underperforming reels using explicit, configurable thresholds:
    - High views with low revenue (views >= views_threshold, revenue <= revenue_threshold)
    - High engagement with low profit (engagement >= engagement_threshold, profit <= profit_threshold)
    - High ad spend with low ROI (ad_spend >= spend_threshold, roi <= roi_threshold)
    Returns identified reels with specific reasons and a structured table.
    """
    reels = _fetch_reels_from_db()
    if not reels:
        return {
            "operation": "find_underperforming_reels",
            "error": "No matching reel records found in MongoDB.",
            "total_flagged": 0,
            "reels": [],
        }
    return calc_find_underperforming_reels(
        reels,
        category=category,
        views_threshold=views_threshold,
        revenue_threshold=revenue_threshold,
        engagement_threshold=engagement_threshold,
        profit_threshold=profit_threshold,
        spend_threshold=spend_threshold,
        roi_threshold=roi_threshold,
    )


@tool
def get_portfolio_metric(
    metric: str,
) -> Dict[str, Any]:
    """
    Retrieve a specific portfolio-level aggregate metric across all reels in MongoDB.
    Use this tool whenever the user asks for a single specific metric, overall spend, total revenue,
    overall profit, overall ROI, total views, or highest profit reel, especially when asking for concise answers.

    Supported metrics:
    - 'overall_spend' or 'spend' or 'ad_spend': Total ad spend across all reels (₹345,000 INR).
    - 'overall_revenue' or 'revenue': Total attributed revenue across all reels (₹632,000 INR).
    - 'overall_profit' or 'profit' or 'net_profit': Total net profit across all reels (₹214,500 INR).
    - 'overall_roi' or 'roi': Aggregate portfolio ROI (62.17%).
    - 'total_reels': Total count of reels (6 reels).
    - 'total_views' or 'views': Total reach across all reels (1,469,000 views).
    - 'highest_profit_reel': The single reel with the highest net profit (REEL_IND_002, ₹88,000 profit).
    - 'highest_roi_reel': The single reel with the highest percentage ROI (REEL_IND_002, +400.0% ROI).
    """
    reels = _fetch_reels_from_db()
    if not reels:
        return {"error": "No reels found in database.", "value": None}

    summary = summarize_performance(reels)
    m = metric.strip().lower()

    if any(k in m for k in ["spend", "ad_spend"]):
        return {
            "metric": "overall_spend",
            "label": "Overall ad spend",
            "value": summary["total_ad_spend"],
            "formatted": f"₹{summary['total_ad_spend']:,.0f}",
            "currency": "INR",
            "total_reels": summary["total_reels"],
            "concise_answer": f"Overall ad spend: ₹{summary['total_ad_spend']:,.0f}.",
            "sentence_answer": f"The total ad spend across all {summary['total_reels']} reels is ₹{summary['total_ad_spend']:,.0f}.",
        }

    if any(k in m for k in ["revenue", "rev"]):
        return {
            "metric": "overall_revenue",
            "label": "Total attributed revenue",
            "value": summary["total_attributed_revenue"],
            "formatted": f"₹{summary['total_attributed_revenue']:,.0f}",
            "currency": "INR",
            "total_reels": summary["total_reels"],
            "concise_answer": f"Total attributed revenue: ₹{summary['total_attributed_revenue']:,.0f}.",
            "sentence_answer": f"The total attributed revenue across all {summary['total_reels']} reels is ₹{summary['total_attributed_revenue']:,.0f}.",
        }

    if any(k in m for k in ["profit", "net_profit"]) and "highest" not in m:
        return {
            "metric": "overall_profit",
            "label": "Overall net profit",
            "value": summary["total_net_profit"],
            "formatted": f"₹{summary['total_net_profit']:,.0f}",
            "currency": "INR",
            "total_reels": summary["total_reels"],
            "concise_answer": f"Overall net profit: ₹{summary['total_net_profit']:,.0f}.",
            "sentence_answer": f"The overall net profit across all {summary['total_reels']} reels is ₹{summary['total_net_profit']:,.0f}.",
        }

    if any(k in m for k in ["roi", "return_on_investment"]) and "highest" not in m:
        return {
            "metric": "overall_roi",
            "label": "Overall ROI",
            "value": summary["overall_roi_percentage"],
            "formatted": f"{summary['overall_roi_percentage']:.2f}%",
            "concise_answer": f"Overall ROI: {summary['overall_roi_percentage']:.2f}%.",
            "sentence_answer": f"The overall aggregate ROI across all reels is {summary['overall_roi_percentage']:.2f}%.",
        }

    if "highest_profit" in m or ("highest" in m and "profit" in m):
        top = summary["top_performing_reel"]
        return {
            "metric": "highest_profit_reel",
            "reel_id": top["reel_id"],
            "reel_name": top["reel_name"],
            "profit": top["profit"],
            "formatted_profit": f"₹{top['profit']:,.0f}",
            "concise_answer": f"Highest profit reel: {top['reel_name']} ({top['reel_id']}) with a profit of ₹{top['profit']:,.0f}.",
        }

    if "highest_roi" in m or ("highest" in m and "roi" in m):
        ranked_roi = rank_reels_by_roi(reels)
        top = ranked_roi[0] if ranked_roi else summary["top_performing_reel"]
        return {
            "metric": "highest_roi_reel",
            "reel_id": top["reel_id"],
            "reel_name": top["reel_name"],
            "roi_percentage": top["roi_percentage"],
            "formatted_roi": f"{top['roi_percentage']:+.2f}%",
            "concise_answer": f"Highest ROI reel: {top['reel_name']} ({top['reel_id']}) with an ROI of {top['roi_percentage']:+.2f}%.",
        }

    if any(k in m for k in ["view", "reach"]):
        return {
            "metric": "total_views",
            "label": "Total views",
            "value": summary["total_views"],
            "formatted": f"{summary['total_views']:,}",
            "concise_answer": f"Total views: {summary['total_views']:,}.",
            "sentence_answer": f"The total views across all {summary['total_reels']} reels is {summary['total_views']:,}.",
        }

    return {
        "metric": metric,
        "summary": summary,
    }
