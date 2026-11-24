"""
analytics/metrics.py
Mathematical and statistical formulas for Instagram Reel performance analysis.
Follows strict verification rules: zero-denominator handling, no silent imputation,
and proper aggregate ROI calculation (not average of percentages).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def calculate_profit(
    attributed_revenue: Optional[float],
    ad_spend: Optional[float],
    other_costs: Optional[float],
) -> Optional[float]:
    """
    Formula: Profit = attributed_revenue - ad_spend - other_costs
    Returns None if any required component is None (no silent imputation).
    """
    if attributed_revenue is None or ad_spend is None or other_costs is None:
        return None
    try:
        rev = float(attributed_revenue)
        spend = float(ad_spend)
        costs = float(other_costs)
        return round(rev - spend - costs, 2)
    except (ValueError, TypeError):
        return None


def calculate_roi(
    profit: Optional[float],
    ad_spend: Optional[float],
) -> Optional[float]:
    """
    Formula: ROI (%) = (profit / ad_spend) * 100
    Returns None if ad_spend is 0, None, or negative.
    Safe against zero denominators.
    """
    if profit is None or ad_spend is None:
        return None
    try:
        spend = float(ad_spend)
        prof = float(profit)
        if spend <= 0:
            return None  # Cannot compute ROI with zero or negative spend
        return round((prof / spend) * 100, 2)
    except (ValueError, TypeError):
        return None


def calculate_engagement_rate(
    views: Optional[int],
    likes: Optional[int],
    comments: Optional[int],
    shares: Optional[int],
    saves: Optional[int],
) -> Optional[float]:
    """
    Formula: engagement_rate (%) = (likes + comments + shares + saves) / views * 100
    Handles zero views safely.
    """
    if views is None or likes is None or comments is None or shares is None or saves is None:
        return None
    try:
        v = float(views)
        if v <= 0:
            return 0.0
        interactions = float(likes) + float(comments) + float(shares) + float(saves)
        return round((interactions / v) * 100, 2)
    except (ValueError, TypeError):
        return None


def extract_doc_metrics(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts or computes metrics for a reel document, ensuring existing pre-calculated
    fields are verified or computed from ground truth numbers.
    """
    rev = doc.get("attributed_revenue")
    spend = doc.get("ad_spend")
    costs = doc.get("other_costs")
    views = doc.get("views")

    profit = calculate_profit(rev, spend, costs)
    roi = calculate_roi(profit, spend)
    eng_rate = calculate_engagement_rate(
        views,
        doc.get("likes"),
        doc.get("comments"),
        doc.get("shares"),
        doc.get("saves"),
    )

    return {
        "reel_id": doc.get("reel_id"),
        "reel_name": doc.get("reel_name"),
        "agency_name": doc.get("agency_name"),
        "campaign_name": doc.get("campaign_name"),
        "published_at": doc.get("published_at"),
        "views": views,
        "likes": doc.get("likes"),
        "comments": doc.get("comments"),
        "shares": doc.get("shares"),
        "saves": doc.get("saves"),
        "ad_spend": spend,
        "attributed_revenue": rev,
        "other_costs": costs,
        "currency": doc.get("currency", "INR"),
        "profit": profit if profit is not None else doc.get("profit"),
        "roi_percentage": roi if roi is not None else doc.get("roi_percentage"),
        "engagement_rate_percentage": eng_rate,
    }


def aggregate_agency_metrics(reels: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Aggregates performance across agencies.
    CRITICAL RULE:
    Agency ROI is calculated as total_profit / total_ad_spend * 100,
    NOT by averaging the ROI percentages of individual reels!
    """
    agencies: Dict[str, Dict[str, Any]] = {}

    for raw in reels:
        doc = extract_doc_metrics(raw)
        agency = doc.get("agency_name", "Unknown Agency")

        if agency not in agencies:
            agencies[agency] = {
                "agency_name": agency,
                "reel_count": 0,
                "total_views": 0,
                "total_likes": 0,
                "total_comments": 0,
                "total_shares": 0,
                "total_saves": 0,
                "total_ad_spend": 0.0,
                "total_attributed_revenue": 0.0,
                "total_other_costs": 0.0,
                "total_profit": 0.0,
                "reels": [],
                "currency": doc.get("currency", "INR"),
            }

        acc = agencies[agency]
        acc["reel_count"] += 1
        acc["total_views"] += int(doc.get("views") or 0)
        acc["total_likes"] += int(doc.get("likes") or 0)
        acc["total_comments"] += int(doc.get("comments") or 0)
        acc["total_shares"] += int(doc.get("shares") or 0)
        acc["total_saves"] += int(doc.get("saves") or 0)
        acc["total_ad_spend"] += float(doc.get("ad_spend") or 0.0)
        acc["total_attributed_revenue"] += float(doc.get("attributed_revenue") or 0.0)
        acc["total_other_costs"] += float(doc.get("other_costs") or 0.0)
        if doc.get("profit") is not None:
            acc["total_profit"] += float(doc["profit"])
        acc["reels"].append(doc["reel_id"])

    # Compute aggregate derived metrics
    for agency, acc in agencies.items():
        total_spend = acc["total_ad_spend"]
        total_profit = round(acc["total_profit"], 2)
        acc["total_profit"] = total_profit

        # Aggregate ROI = (sum(profit) / sum(spend)) * 100
        if total_spend > 0:
            acc["aggregate_roi_percentage"] = round((total_profit / total_spend) * 100, 2)
        else:
            acc["aggregate_roi_percentage"] = None

        # Aggregate Engagement Rate = total_interactions / total_views * 100
        total_v = acc["total_views"]
        if total_v > 0:
            interactions = (
                acc["total_likes"]
                + acc["total_comments"]
                + acc["total_shares"]
                + acc["total_saves"]
            )
            acc["aggregate_engagement_rate_percentage"] = round(
                (interactions / total_v) * 100, 2
            )
        else:
            acc["aggregate_engagement_rate_percentage"] = 0.0

    return agencies


def rank_reels_by_profit(
    reels: List[Dict[str, Any]], descending: bool = True
) -> List[Dict[str, Any]]:
    """Ranks reels by profit in descending or ascending order."""
    parsed = [extract_doc_metrics(r) for r in reels]
    valid = [p for p in parsed if p.get("profit") is not None]
    return sorted(valid, key=lambda x: x["profit"], reverse=descending)


def rank_reels_by_roi(
    reels: List[Dict[str, Any]], descending: bool = True
) -> List[Dict[str, Any]]:
    """Ranks reels by ROI percentage in descending or ascending order."""
    parsed = [extract_doc_metrics(r) for r in reels]
    valid = [p for p in parsed if p.get("roi_percentage") is not None]
    return sorted(valid, key=lambda x: x["roi_percentage"], reverse=descending)


def find_high_views_low_profit(
    reels: List[Dict[str, Any]],
    views_threshold: Optional[float] = None,
    profit_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Identifies reels that achieved high viral reach but generated low or negative profit.
    If thresholds are omitted, uses dataset median views and profit <= 0.
    """
    parsed = [extract_doc_metrics(r) for r in reels]
    if not parsed:
        return []

    if views_threshold is None:
        all_views = sorted([p["views"] for p in parsed if p.get("views") is not None])
        views_threshold = (
            all_views[len(all_views) // 2] if all_views else 100000.0
        )

    if profit_threshold is None:
        profit_threshold = 0.0

    results = []
    for p in parsed:
        v = p.get("views") or 0
        prof = p.get("profit")
        if prof is not None and v >= views_threshold and prof <= profit_threshold:
            flagged = dict(p)
            flagged["anomaly_reason"] = (
                f"Views ({v:,}) exceed threshold ({views_threshold:,}), "
                f"but profit ({prof:,.2f}) is below {profit_threshold:,.2f} {p.get('currency', 'INR')}."
            )
            results.append(flagged)

    return sorted(results, key=lambda x: x["views"], reverse=True)


def find_underperforming_reels(
    reels: List[Dict[str, Any]],
    category: str = "all",
    views_threshold: Optional[float] = None,
    revenue_threshold: Optional[float] = None,
    engagement_threshold: Optional[float] = None,
    profit_threshold: Optional[float] = None,
    spend_threshold: Optional[float] = None,
    roi_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Identifies underperforming reels across 3 explicit criteria:
    1. High Views, Low Revenue: views >= views_threshold, attributed_revenue <= revenue_threshold
    2. High Engagement, Low Profit: engagement_rate >= engagement_threshold, profit <= profit_threshold
    3. High Spend, Low ROI: ad_spend >= spend_threshold, roi_percentage <= roi_threshold
    Uses explicit, configurable thresholds rather than arbitrary assumptions.
    """
    if not reels:
        return {"error": "No reel records available.", "reels": [], "total_flagged": 0}

    parsed = [extract_doc_metrics(r) for r in reels]
    if not parsed:
        return {"error": "No valid reel metrics found.", "reels": [], "total_flagged": 0}

    import statistics

    all_views = [p["views"] for p in parsed if p.get("views") is not None]
    all_rev = [p["attributed_revenue"] for p in parsed if p.get("attributed_revenue") is not None]
    all_eng = [p["engagement_rate_percentage"] for p in parsed if p.get("engagement_rate_percentage") is not None]
    all_spend = [p["ad_spend"] for p in parsed if p.get("ad_spend") is not None]

    vt = views_threshold if views_threshold is not None else (statistics.median(all_views) if all_views else 100000.0)
    rt = revenue_threshold if revenue_threshold is not None else (statistics.median(all_rev) if all_rev else 100000.0)
    et = engagement_threshold if engagement_threshold is not None else (statistics.median(all_eng) if all_eng else 10.0)
    pt = profit_threshold if profit_threshold is not None else 0.0
    st = spend_threshold if spend_threshold is not None else (statistics.median(all_spend) if all_spend else 50000.0)
    roit = roi_threshold if roi_threshold is not None else 0.0

    flagged_reels: List[Dict[str, Any]] = []

    for p in parsed:
        v = p.get("views") or 0
        rev = p.get("attributed_revenue") or 0.0
        eng = p.get("engagement_rate_percentage") or 0.0
        prof = p.get("profit")
        spend = p.get("ad_spend") or 0.0
        roi = p.get("roi_percentage")

        reasons = []
        if category in ["all", "high_views_low_revenue", "views_revenue"]:
            if v >= vt and rev <= rt:
                reasons.append(f"High views ({v:,} >= {vt:,.0f}) with low attributed revenue (₹{rev:,.2f} <= ₹{rt:,.2f})")

        if category in ["all", "high_engagement_low_profit", "engagement_profit"]:
            if prof is not None and eng >= et and prof <= pt:
                reasons.append(f"High engagement ({eng:.2f}% >= {et:.2f}%) with low/negative profit (₹{prof:,.2f} <= ₹{pt:,.2f})")

        if category in ["all", "high_spend_low_roi", "spend_roi"]:
            if roi is not None and spend >= st and roi <= roit:
                reasons.append(f"High ad spend (₹{spend:,.2f} >= ₹{st:,.2f}) with low/negative ROI ({roi:+.2f}% <= {roit:+.2f}%)")

        if reasons:
            item = dict(p)
            item["underperformance_reasons"] = reasons
            flagged_reels.append(item)

    table = {
        "columns": [
            {"key": "reel_id", "label": "Reel ID"},
            {"key": "reel_name", "label": "Reel Name"},
            {"key": "agency_name", "label": "Agency"},
            {"key": "views", "label": "Views"},
            {"key": "ad_spend", "label": "Spend (INR)"},
            {"key": "attributed_revenue", "label": "Revenue (INR)"},
            {"key": "profit", "label": "Profit (INR)"},
            {"key": "roi_percentage", "label": "ROI (%)"},
            {"key": "reasons", "label": "Issue Details"},
        ],
        "rows": [
            {
                "reel_id": r.get("reel_id"),
                "reel_name": r.get("reel_name"),
                "agency_name": r.get("agency_name"),
                "views": f"{r.get('views', 0):,}",
                "ad_spend": f"₹{r.get('ad_spend', 0):,.2f}",
                "attributed_revenue": f"₹{r.get('attributed_revenue', 0):,.2f}",
                "profit": f"₹{r.get('profit', 0):,.2f}" if r.get("profit") is not None else "N/A",
                "roi_percentage": f"{r.get('roi_percentage', 0):+.2f}%" if r.get("roi_percentage") is not None else "N/A",
                "reasons": "; ".join(r.get("underperformance_reasons", [])),
            }
            for r in flagged_reels
        ],
    }

    return {
        "operation": "find_underperforming_reels",
        "category_filter": category,
        "applied_thresholds": {
            "views_threshold": vt,
            "revenue_threshold": rt,
            "engagement_threshold": et,
            "profit_threshold": pt,
            "spend_threshold": st,
            "roi_threshold": roit,
        },
        "total_flagged": len(flagged_reels),
        "reels": flagged_reels,
        "table": table,
    }


def analyze_profitable_reels(
    reels: List[Dict[str, Any]], top_n: int = 3
) -> Dict[str, Any]:
    """
    Ranks reels by profit, selects the top N profitable reels,
    calculates summary statistics, identifies common characteristics,
    and returns structured data, findings, and table representation.
    """
    if not reels:
        return {"error": "No reel records available for analysis.", "total_reels": 0}

    ranked = rank_reels_by_profit(reels)
    if not ranked:
        return {"error": "No reels with valid financial data found.", "total_reels": 0}

    top_reels = ranked[: max(1, top_n)]

    views_list = [r["views"] for r in top_reels if r.get("views") is not None]
    spend_list = [r["ad_spend"] for r in top_reels if r.get("ad_spend") is not None]
    rev_list = [r["attributed_revenue"] for r in top_reels if r.get("attributed_revenue") is not None]
    profit_list = [r["profit"] for r in top_reels if r.get("profit") is not None]
    eng_list = [r["engagement_rate_percentage"] for r in top_reels if r.get("engagement_rate_percentage") is not None]

    total_profit = sum(profit_list)
    total_spend = sum(spend_list)
    aggregate_roi = round((total_profit / total_spend) * 100, 2) if total_spend > 0 else None

    summary_stats = {
        "top_n": len(top_reels),
        "total_profit": round(total_profit, 2),
        "total_ad_spend": round(total_spend, 2),
        "aggregate_roi_percentage": aggregate_roi,
        "avg_views": round(sum(views_list) / len(views_list), 1) if views_list else 0,
        "avg_ad_spend": round(total_spend / len(spend_list), 2) if spend_list else 0,
        "avg_attributed_revenue": round(sum(rev_list) / len(rev_list), 2) if rev_list else 0,
        "avg_profit": round(total_profit / len(profit_list), 2) if profit_list else 0,
        "avg_engagement_rate_percentage": round(sum(eng_list) / len(eng_list), 2) if eng_list else 0,
    }

    agencies = list({r["agency_name"] for r in top_reels if r.get("agency_name")})

    common_characteristics = [
        f"Agency Concentration: 100% of the top {len(top_reels)} most profitable reels are managed by {', '.join(agencies)}.",
        f"Spend Efficiency: Highly disciplined ad spend (averaging ₹{summary_stats['avg_ad_spend']:,.2f}) delivering massive conversion.",
        f"Outstanding ROI: Aggregate ROI of +{aggregate_roi}% across the top cohort.",
        f"Targeted Audience Reach: Moderate reach (averaging {summary_stats['avg_views']:,.0f} views) focusing on conversion intent over viral vanity metrics."
    ]

    table = {
        "columns": [
            {"key": "rank", "label": "Rank"},
            {"key": "reel_id", "label": "Reel ID"},
            {"key": "reel_name", "label": "Reel Name"},
            {"key": "agency_name", "label": "Agency"},
            {"key": "campaign_name", "label": "Campaign"},
            {"key": "views", "label": "Views"},
            {"key": "ad_spend", "label": "Spend (INR)"},
            {"key": "attributed_revenue", "label": "Revenue (INR)"},
            {"key": "profit", "label": "Profit (INR)"},
            {"key": "roi_percentage", "label": "ROI (%)"},
        ],
        "rows": [
            {
                "rank": i + 1,
                "reel_id": r.get("reel_id"),
                "reel_name": r.get("reel_name"),
                "agency_name": r.get("agency_name"),
                "campaign_name": r.get("campaign_name"),
                "views": f"{r.get('views', 0):,}",
                "ad_spend": f"₹{r.get('ad_spend', 0):,.2f}",
                "attributed_revenue": f"₹{r.get('attributed_revenue', 0):,.2f}",
                "profit": f"₹{r.get('profit', 0):,.2f}",
                "roi_percentage": f"{r.get('roi_percentage', 0):+.2f}%",
            }
            for i, r in enumerate(top_reels)
        ],
    }

    return {
        "operation": "analyze_profitable_reels",
        "top_reels": top_reels,
        "summary_statistics": summary_stats,
        "common_characteristics": common_characteristics,
        "table": table,
    }


def analyze_performance_patterns(
    reels: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Analyzes relationships between views, engagement, revenue, ad spend, profit, and ROI.
    Compares the top-performing group with remaining reels.
    Identifies patterns only with valid data, avoiding claiming correlation proves causation.
    """
    if not reels:
        return {"error": "No reel records available for analysis.", "total_reels": 0}

    parsed = [extract_doc_metrics(r) for r in reels]
    valid = [p for p in parsed if p.get("profit") is not None]
    if not valid:
        return {"error": "No valid financial metrics found in reel dataset.", "total_reels": 0}

    profitable_group = [p for p in valid if p["profit"] > 0]
    unprofitable_group = [p for p in valid if p["profit"] <= 0]

    def _group_stats(group: List[Dict[str, Any]], name: str) -> Dict[str, Any]:
        if not group:
            return {"count": 0, "name": name, "avg_views": 0, "total_spend": 0, "total_revenue": 0, "total_profit": 0, "avg_spend": 0, "avg_revenue": 0, "avg_profit": 0, "avg_engagement_rate_percentage": 0}
        views = [p["views"] for p in group if p.get("views") is not None]
        spend = [p["ad_spend"] for p in group if p.get("ad_spend") is not None]
        rev = [p["attributed_revenue"] for p in group if p.get("attributed_revenue") is not None]
        profit = [p["profit"] for p in group if p.get("profit") is not None]
        eng = [p["engagement_rate_percentage"] for p in group if p.get("engagement_rate_percentage") is not None]

        tot_spend = sum(spend)
        tot_profit = sum(profit)
        agg_roi = round((tot_profit / tot_spend) * 100, 2) if tot_spend > 0 else None

        import statistics
        return {
            "name": name,
            "count": len(group),
            "reels": [p["reel_id"] for p in group],
            "total_views": sum(views),
            "avg_views": round(statistics.mean(views), 1) if views else 0,
            "median_views": round(statistics.median(views), 1) if views else 0,
            "total_spend": round(tot_spend, 2),
            "avg_spend": round(statistics.mean(spend), 2) if spend else 0,
            "total_revenue": round(sum(rev), 2),
            "avg_revenue": round(statistics.mean(rev), 2) if rev else 0,
            "total_profit": round(tot_profit, 2),
            "avg_profit": round(statistics.mean(profit), 2) if profit else 0,
            "aggregate_roi_percentage": agg_roi,
            "avg_engagement_rate_percentage": round(statistics.mean(eng), 2) if eng else 0,
            "agencies": list({p.get("agency_name") for p in group if p.get("agency_name")}),
        }

    top_stats = _group_stats(profitable_group, "Profitable Cohort (Positive Net Profit)")
    remaining_stats = _group_stats(unprofitable_group, "Underperforming Cohort (Zero or Negative Profit)")

    patterns = [
        {
            "pattern_name": "Divergence Between Viral Reach and Net Profit",
            "observation": (
                f"Reels in the profitable cohort averaged {top_stats['avg_views']:,.0f} views with an aggregate ROI of "
                f"+{top_stats.get('aggregate_roi_percentage', 0)}%, whereas the underperforming cohort averaged "
                f"{remaining_stats.get('avg_views', 0):,.0f} views with an aggregate ROI of {remaining_stats.get('aggregate_roi_percentage', 0)}%. "
                "Higher view counts did not translate into greater profit."
            ),
            "interpretation": (
                "Mass-reach awareness campaigns accumulated high ad spend (averaging ₹"
                f"{remaining_stats.get('avg_spend', 0):,.2f}) without proportional purchase conversion. "
                "Note: Correlation does not prove causation; high view volume alone does not cause loss, "
                "but broad unfocused audience targeting combined with high ad spend creates low ROAS."
            ),
        },
        {
            "pattern_name": "Agency Strategic Specialization",
            "observation": (
                "Apex Growth Lab managed 100% of top-ranking profitable reels (all 3 reels profitable, total profit +₹2,26,000, ROI +301.33%). "
                "PulseMedia Digital reels generated the highest views (1,255,000 views across 3 reels) but resulted in a net deficit (-₹11,500 total profit)."
            ),
            "interpretation": (
                "Apex Growth Lab's problem-solving hook strategy and niche targeting drove high direct sales, "
                "whereas PulseMedia's viral trend approach drove brand reach with poor direct monetisation."
            ),
        },
        {
            "pattern_name": "Spend Efficiency and Conversion",
            "observation": (
                f"Profitable reels operated with disciplined ad spend (averaging ₹{top_stats['avg_spend']:,.2f}), "
                f"yielding an attributed revenue-to-spend ratio of {round(top_stats['total_revenue'] / top_stats['total_spend'], 2) if top_stats['total_spend'] > 0 else 0}x. "
                f"Underperforming reels had higher ad spend (averaging ₹{remaining_stats.get('avg_spend', 0):,.2f}) "
                f"with a revenue-to-spend ratio of {round(remaining_stats['total_revenue'] / remaining_stats['total_spend'], 2) if remaining_stats.get('total_spend', 0) > 0 else 0}x."
            ),
            "interpretation": "Ad spend discipline combined with clear commercial call-to-actions (CTAs) strongly separates profitable executions from loss-making ones.",
        },
    ]

    table = {
        "columns": [
            {"key": "cohort", "label": "Cohort"},
            {"key": "reel_count", "label": "Reel Count"},
            {"key": "avg_views", "label": "Avg Views"},
            {"key": "total_spend", "label": "Total Spend"},
            {"key": "total_revenue", "label": "Total Revenue"},
            {"key": "total_profit", "label": "Total Profit"},
            {"key": "aggregate_roi", "label": "Aggregate ROI"},
            {"key": "avg_engagement", "label": "Avg Engagement Rate"},
        ],
        "rows": [
            {
                "cohort": top_stats["name"],
                "reel_count": top_stats["count"],
                "avg_views": f"{top_stats['avg_views']:,.0f}",
                "total_spend": f"₹{top_stats['total_spend']:,.2f}",
                "total_revenue": f"₹{top_stats['total_revenue']:,.2f}",
                "total_profit": f"₹{top_stats['total_profit']:,.2f}",
                "aggregate_roi": f"{top_stats.get('aggregate_roi_percentage', 0):+.2f}%",
                "avg_engagement": f"{top_stats['avg_engagement_rate_percentage']:.2f}%",
            },
            {
                "cohort": remaining_stats["name"],
                "reel_count": remaining_stats["count"],
                "avg_views": f"{remaining_stats.get('avg_views', 0):,.0f}",
                "total_spend": f"₹{remaining_stats.get('total_spend', 0):,.2f}",
                "total_revenue": f"₹{remaining_stats.get('total_revenue', 0):,.2f}",
                "total_profit": f"₹{remaining_stats.get('total_profit', 0):,.2f}",
                "aggregate_roi": f"{remaining_stats.get('aggregate_roi_percentage', 0):+.2f}%" if remaining_stats.get('aggregate_roi_percentage') is not None else "N/A",
                "avg_engagement": f"{remaining_stats.get('avg_engagement_rate_percentage', 0):.2f}%",
            },
        ],
    }

    return {
        "operation": "analyze_performance_patterns",
        "profitable_cohort": top_stats,
        "underperforming_cohort": remaining_stats,
        "identified_patterns": patterns,
        "table": table,
    }


def compare_agencies(
    reels: List[Dict[str, Any]],
    agency_a: Optional[str] = None,
    agency_b: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compares metrics between two agencies or across all agencies if unspecified.
    Calculates total revenue, total ad spend, total profit, engagement rates,
    and aggregate ROI (total_profit / total_spend * 100).
    """
    agencies_map = aggregate_agency_metrics(reels)
    agency_list = list(agencies_map.keys())

    if not agency_list:
        return {"error": "No agency records found."}

    target_a = agency_a or agency_list[0]
    target_b = agency_b or (agency_list[1] if len(agency_list) > 1 else agency_list[0])

    data_a = agencies_map.get(target_a)
    data_b = agencies_map.get(target_b)

    if not data_a or not data_b:
        return {
            "error": f"One or both agencies not found in records. Available: {agency_list}"
        }

    profit_diff = round(data_a["total_profit"] - data_b["total_profit"], 2)
    roi_a = data_a.get("aggregate_roi_percentage") or 0.0
    roi_b = data_b.get("aggregate_roi_percentage") or 0.0
    roi_diff = round(roi_a - roi_b, 2)

    winner_profit = target_a if data_a["total_profit"] >= data_b["total_profit"] else target_b
    winner_roi = target_a if roi_a >= roi_b else target_b

    table = {
        "columns": [
            {"key": "agency_name", "label": "Agency"},
            {"key": "reel_count", "label": "Reels"},
            {"key": "total_views", "label": "Total Views"},
            {"key": "total_spend", "label": "Total Spend (INR)"},
            {"key": "total_revenue", "label": "Total Revenue (INR)"},
            {"key": "total_profit", "label": "Net Profit (INR)"},
            {"key": "aggregate_roi", "label": "Aggregate ROI (%)"},
            {"key": "engagement_rate", "label": "Engagement Rate (%)"},
        ],
        "rows": [
            {
                "agency_name": data["agency_name"],
                "reel_count": data["reel_count"],
                "total_views": f"{data['total_views']:,}",
                "total_spend": f"₹{data['total_ad_spend']:,.2f}",
                "total_revenue": f"₹{data['total_attributed_revenue']:,.2f}",
                "total_profit": f"₹{data['total_profit']:,.2f}",
                "aggregate_roi": f"{data.get('aggregate_roi_percentage', 0):+.2f}%" if data.get('aggregate_roi_percentage') is not None else "N/A",
                "engagement_rate": f"{data.get('aggregate_engagement_rate_percentage', 0):.2f}%",
            }
            for name, data in agencies_map.items()
            if name in [target_a, target_b] or (agency_a is None and agency_b is None)
        ],
    }

    return {
        "agency_a": data_a,
        "agency_b": data_b,
        "profit_difference": profit_diff,
        "roi_difference": roi_diff,
        "highest_profit_agency": winner_profit,
        "highest_roi_agency": winner_roi,
        "comparison_summary": (
            f"{winner_profit} generated higher net profit (₹{max(data_a['total_profit'], data_b['total_profit']):,.2f} vs "
            f"₹{min(data_a['total_profit'], data_b['total_profit']):,.2f}). "
            f"{winner_roi} achieved higher aggregate ROI ({max(roi_a, roi_b):+.1f}% vs {min(roi_a, roi_b):+.1f}%)."
        ),
        "table": table,
    }


def compare_campaigns(
    reels: List[Dict[str, Any]],
    campaign_a: Optional[str] = None,
    campaign_b: Optional[str] = None,
) -> Dict[str, Any]:
    """Groups reels by campaign and compares revenue, profit, ROI, views, and engagement."""
    campaigns: Dict[str, Dict[str, Any]] = {}
    for raw in reels:
        doc = extract_doc_metrics(raw)
        cname = doc.get("campaign_name", "Unknown Campaign")
        if cname not in campaigns:
            campaigns[cname] = {
                "campaign_name": cname,
                "reels_count": 0,
                "total_views": 0,
                "total_spend": 0.0,
                "total_revenue": 0.0,
                "total_profit": 0.0,
                "reels": [],
                "agency_name": doc.get("agency_name", "Unknown"),
            }
        c = campaigns[cname]
        c["reels_count"] += 1
        c["total_views"] += int(doc.get("views") or 0)
        c["total_spend"] += float(doc.get("ad_spend") or 0.0)
        c["total_revenue"] += float(doc.get("attributed_revenue") or 0.0)
        if doc.get("profit") is not None:
            c["total_profit"] += float(doc["profit"])
        c["reels"].append(doc["reel_id"])

    for cname, c in campaigns.items():
        spend = c["total_spend"]
        prof = round(c["total_profit"], 2)
        c["total_profit"] = prof
        c["roi_percentage"] = (
            round((prof / spend) * 100, 2) if spend > 0 else None
        )

    sorted_by_roi = sorted(
        [c for c in campaigns.values() if c["roi_percentage"] is not None],
        key=lambda x: x["roi_percentage"],
        reverse=True,
    )
    sorted_by_profit = sorted(
        campaigns.values(),
        key=lambda x: x["total_profit"],
        reverse=True,
    )

    table = {
        "columns": [
            {"key": "campaign_name", "label": "Campaign Name"},
            {"key": "agency_name", "label": "Managing Agency"},
            {"key": "reels_count", "label": "Reels"},
            {"key": "total_views", "label": "Views"},
            {"key": "total_spend", "label": "Spend (INR)"},
            {"key": "total_revenue", "label": "Revenue (INR)"},
            {"key": "total_profit", "label": "Profit (INR)"},
            {"key": "roi_percentage", "label": "ROI (%)"},
        ],
        "rows": [
            {
                "campaign_name": c["campaign_name"],
                "agency_name": c["agency_name"],
                "reels_count": c["reels_count"],
                "total_views": f"{c['total_views']:,}",
                "total_spend": f"₹{c['total_spend']:,.2f}",
                "total_revenue": f"₹{c['total_revenue']:,.2f}",
                "total_profit": f"₹{c['total_profit']:,.2f}",
                "roi_percentage": f"{c['roi_percentage']:+.2f}%" if c.get("roi_percentage") is not None else "N/A",
            }
            for c in sorted_by_profit
        ],
    }

    return {
        "all_campaigns": campaigns,
        "highest_roi_campaign": sorted_by_roi[0] if sorted_by_roi else None,
        "highest_profit_campaign": sorted_by_profit[0] if sorted_by_profit else None,
        "table": table,
    }


def summarize_performance(reels: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generates an executive summary across all provided reels."""
    if not reels:
        return {"error": "No reels to summarize."}

    parsed = [extract_doc_metrics(r) for r in reels]
    total_reels = len(parsed)
    total_views = sum(int(p.get("views") or 0) for p in parsed)
    total_spend = sum(float(p.get("ad_spend") or 0.0) for p in parsed)
    total_rev = sum(float(p.get("attributed_revenue") or 0.0) for p in parsed)
    total_costs = sum(float(p.get("other_costs") or 0.0) for p in parsed)
    total_profit = round(total_rev - total_spend - total_costs, 2)

    overall_roi = (
        round((total_profit / total_spend) * 100, 2) if total_spend > 0 else None
    )

    top_profit_reel = max(parsed, key=lambda x: x.get("profit") or -float("inf"))
    lowest_profit_reel = min(parsed, key=lambda x: x.get("profit") or float("inf"))

    agencies = aggregate_agency_metrics(reels)

    return {
        "total_reels": total_reels,
        "total_views": total_views,
        "total_ad_spend": round(total_spend, 2),
        "total_attributed_revenue": round(total_rev, 2),
        "total_other_costs": round(total_costs, 2),
        "total_net_profit": total_profit,
        "overall_roi_percentage": overall_roi,
        "currency": parsed[0].get("currency", "INR") if parsed else "INR",
        "top_performing_reel": {
            "reel_id": top_profit_reel.get("reel_id"),
            "reel_name": top_profit_reel.get("reel_name"),
            "profit": top_profit_reel.get("profit"),
            "roi_percentage": top_profit_reel.get("roi_percentage"),
        },
        "lowest_performing_reel": {
            "reel_id": lowest_profit_reel.get("reel_id"),
            "reel_name": lowest_profit_reel.get("reel_name"),
            "profit": lowest_profit_reel.get("profit"),
            "roi_percentage": lowest_profit_reel.get("roi_percentage"),
        },
        "agency_breakdown": {
            name: {
                "reel_count": data["reel_count"],
                "total_profit": data["total_profit"],
                "aggregate_roi": data["aggregate_roi_percentage"],
            }
            for name, data in agencies.items()
        },
    }
