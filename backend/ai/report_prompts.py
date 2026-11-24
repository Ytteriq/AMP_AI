"""
backend/ai/report_prompts.py
System prompts and user prompt builders for the AI Marketing Report Generation Platform.
Enforces strict anti-hallucination data accuracy, client context conditioning,
and structured JSON outputs for professional agency reporting.
"""

import json
from typing import Any, Dict, List, Optional

# -----------------------------------------------------------------------------
# Base System Prompt: Marketing Analytics & Performance Report Agent
# -----------------------------------------------------------------------------

MARKETING_REPORT_SYSTEM_PROMPT = """You are AI_REEL, an expert Digital Marketing Analytics and Strategy Agent working for professional digital marketing agencies.

Your responsibility is to analyze marketing performance data and generate comprehensive, accurate, professional marketing reports.

You are NOT a conversational chatbot.
You are a professional marketing report generation system.

YOUR RESPONSIBILITIES:
1. Understand the client's business and industry.
2. Analyze the supplied marketing performance data.
3. Identify important changes in campaign performance.
4. Identify high-performing and underperforming campaigns.
5. Analyze advertising efficiency.
6. Identify opportunities and potential problems.
7. Generate actionable marketing recommendations.
8. Develop future marketing strategies when requested.
9. Generate structured, client-ready reports.

DATA ACCURACY RULES (CRITICAL):
- Only use the information supplied in the provided context.
- Never invent impressions, clicks, spend, revenue, conversions or ROAS.
- Never assume that missing data means zero.
- Clearly distinguish between zero values and unavailable values.
- Never invent campaign names or product names.
- Never claim a campaign is successful without supporting metrics.
- Never invent audience demographics.
- Never invent creative performance observations.
- If information is unavailable, explicitly state that it is unavailable.
- Do not present assumptions as facts.
- Do not change calculated KPI values supplied by the analytics engine.
- Recommendations must be supported by available evidence.
- Clearly distinguish historical performance from future recommendations.

RECOMMENDATION REQUIREMENTS:
Every recommendation must explain:
1. What action should be taken?
2. Why should it be taken?
3. Which data supports this recommendation?
4. What outcome is expected? (Do not guarantee future results).

REPORT WRITING STYLE:
- Professional, analytical, clear, business-oriented.
- Concise but informative, suitable for direct presentation to C-level agency clients.
- Avoid generic marketing platitudes, repetitive explanations, conversational chit-chat, and unsupported claims.

OUTPUT FORMAT:
You MUST respond with a single valid JSON object adhering strictly to the requested report schema. Do not wrap in conversational dialogue.
"""

# -----------------------------------------------------------------------------
# Content Strategy Agent System Prompt
# -----------------------------------------------------------------------------

CONTENT_STRATEGY_SYSTEM_PROMPT = """You are AI_REEL, a Lead Content Strategist working for top-tier digital marketing agencies.

Your responsibility is to generate structured, client-ready Monthly Content Strategy and Content Calendar reports.

You are NOT a conversational chatbot.
You are a professional marketing report generation system.

YOUR RESPONSIBILITIES:
1. Understand the client's business, industry, target audience persona, and brand voice.
2. Formulate a compelling, cohesive campaign theme aligned with the client's marketing objectives.
3. Design high-converting content ideas spanning diverse formats: Reels, Carousels, Static Posts, and Stories.
4. Provide structured hooks, visual concepts, descriptions, and conversion-oriented Calls to Action (CTAs).
5. Establish balanced content pillars and distribution tactics.
6. Build a date-wise publishing calendar.
7. Define clear performance evaluation KPIs.

DATA & ETHICS RULES:
- Content strategy includes creative concepts, but must NEVER fabricate historical analytics or sales numbers.
- If product prices, discounts, or offers are not specified in the client brief, do NOT invent them.
- Tailor tone, language (e.g. English, Hinglish, regional nuances where requested), and hooks specifically to the target market.

OUTPUT FORMAT:
You MUST respond with a single valid JSON object adhering strictly to the requested ContentStrategyReport schema. Do not include conversational preambles.
"""


# -----------------------------------------------------------------------------
# Prompt Builders
# -----------------------------------------------------------------------------

def build_performance_report_user_prompt(
    client_info: Dict[str, Any],
    calculated_analytics: Dict[str, Any],
    campaign_analysis: Dict[str, Any],
    creatives_data: Optional[List[Dict[str, Any]]] = None,
    platform_breakdown: Optional[Dict[str, Any]] = None,
) -> str:
    """Builds a contextual prompt containing pre-calculated metrics for the Performance Report Agent."""
    return f"""Generate a comprehensive, client-ready Marketing Performance Report for the following client based ONLY on the verified analytics data below:

CLIENT PROFILE:
{json.dumps(client_info, indent=2)}

VERIFIED CALCULATED MARKETING KPIS (Calculated by Analytics Engine - DO NOT ALTER):
{json.dumps(calculated_analytics, indent=2)}

CAMPAIGN PERFORMANCE DATA:
{json.dumps(campaign_analysis, indent=2)}

CREATIVE ASSET DATA (If empty, explicitly report creative data as unavailable):
{json.dumps(creatives_data or [], indent=2)}

PLATFORM BREAKDOWN:
{json.dumps(platform_breakdown or {}, indent=2)}

REQUIRED REPORT JSON STRUCTURE:
{{
  "report_title": "Marketing Performance Report",
  "report_type": "performance_analysis",
  "executive_summary": {{
    "overall_performance": "Analytical summary of account health, total spend, revenue, and ROAS trajectory.",
    "key_improvements": ["Specific improvement with numbers", "..."],
    "key_declines": ["Specific decline or efficiency loss with numbers", "..."],
    "main_opportunities": ["Actionable opportunity identified from data", "..."],
    "core_observation": "The single most critical takeaway for the agency client."
  }},
  "important_changes": [
    {{
      "metric": "e.g. ROAS Efficiency",
      "description": "Specific change comparison between current and previous periods",
      "impact": "positive | negative | neutral"
    }}
  ],
  "campaign_performance": [
    {{
      "campaign_name": "...",
      "platform": "...",
      "spend": 0.0,
      "clicks": 0,
      "conversions": 0,
      "revenue": 0.0,
      "roas": 0.0,
      "status": "ACTIVE",
      "highlight": "..."
    }}
  ],
  "high_performing_campaigns": [
    {{
      "campaign_name": "...",
      "metrics_summary": "...",
      "success_factor": "Evidence-backed rationale"
    }}
  ],
  "underperforming_campaigns": [
    {{
      "campaign_name": "...",
      "metrics_summary": "...",
      "issue_identified": "Evidence-backed diagnosis"
    }}
  ],
  "creative_observations": [
    {{
      "creative_name": "...",
      "format": "Video / Reel | Static | Carousel",
      "observation": "...",
      "ctr_or_conv_comparison": "...",
      "action_item": "..."
    }}
  ],
  "revenue_analysis": {{
    "current_revenue": 0.0,
    "previous_revenue": 0.0,
    "growth_rate_pct": 0.0,
    "top_contributor": "...",
    "observations": "..."
  }},
  "roas_analysis": {{
    "current_roas": 0.0,
    "previous_roas": 0.0,
    "efficiency_trend": "...",
    "observations": "..."
  }},
  "recommended_actions": [
    {{
      "action": "...",
      "reason": "...",
      "supporting_evidence": "...",
      "priority": "High | Medium | Low",
      "expected_outcome": "..."
    }}
  ],
  "next_period_strategy": [
    "Concrete strategic initiative 1",
    "Concrete strategic initiative 2",
    "Concrete strategic initiative 3"
  ]
}}
"""


def build_content_strategy_user_prompt(
    client_info: Dict[str, Any],
    reporting_period: Dict[str, Any],
    platform: str,
    historical_highlights: Optional[Dict[str, Any]] = None,
) -> str:
    """Builds a contextual prompt for the Content Strategy Agent."""
    return f"""Formulate a comprehensive Monthly Content Strategy and Content Calendar report for this client:

CLIENT IDENTITY & BRIEF:
{json.dumps(client_info, indent=2)}

TARGET PLATFORMS: {platform}
REPORTING PERIOD: {json.dumps(reporting_period)}

HISTORICAL TOP THEMES (For context):
{json.dumps(historical_highlights or {}, indent=2)}

REQUIRED CONTENT STRATEGY JSON STRUCTURE:
{{
  "report_title": "Monthly Content Strategy",
  "report_type": "content_strategy",
  "strategic_overview": "Comprehensive direction detailing brand positioning, audience capture strategy, and growth targets.",
  "campaign_theme": "Catchy, thematic umbrella title for the month",
  "theme_relevance": "Why this theme resonates with the target audience at this time",
  "content_ideas": [
    {{
      "item_no": 1,
      "format": "Reels",
      "content_idea": "...",
      "hook": "Attention-grabbing first 3 seconds",
      "description": "Visual direction and narrative structure",
      "cta": "Direct call to action"
    }},
    {{
      "item_no": 2,
      "format": "Carousels",
      "content_idea": "...",
      "hook": "Slide 1 title",
      "description": "Slide-by-slide value breakdown",
      "cta": "Save and share CTA"
    }},
    {{
      "item_no": 3,
      "format": "Static Posts",
      "content_idea": "...",
      "hook": "Striking graphic headline",
      "description": "Core message and visual layout",
      "cta": "Comment CTA"
    }},
    {{
      "item_no": 4,
      "format": "Stories",
      "content_idea": "...",
      "hook": "Interactive poll/sticker hook",
      "description": "Sequence of 3-4 story frames",
      "cta": "Link sticker CTA"
    }}
  ],
  "content_pillars": [
    {{
      "pillar_name": "Educational & Value",
      "percentage_share": 35,
      "description": "...",
      "topics": ["Topic A", "Topic B"]
    }},
    {{
      "pillar_name": "Product In-Action / Social Proof",
      "percentage_share": 30,
      "description": "...",
      "topics": ["Demo", "Customer Stories"]
    }},
    {{
      "pillar_name": "Relatable & Community",
      "percentage_share": 20,
      "description": "...",
      "topics": ["Memes", "Trends"]
    }},
    {{
      "pillar_name": "Conversion & Direct Offer",
      "percentage_share": 15,
      "description": "...",
      "topics": ["Limited bundles", "Exclusive perks"]
    }}
  ],
  "strategic_recommendations": {{
    "targeting": ["Recommendation on audience segments"],
    "distribution": ["Recommendation on posting cadence, optimal times"],
    "creative_direction": ["Visual style, color grading, font cues"],
    "engagement": ["Comment retention, DM automation tips"],
    "campaigns": ["Paid amplification recommendations"]
  }},
  "content_calendar": [
    {{
      "date": "Day 1",
      "platform": "Instagram",
      "format": "Reels",
      "topic": "...",
      "content_objective": "Top of funnel reach"
    }},
    {{
      "date": "Day 4",
      "platform": "Instagram",
      "format": "Carousels",
      "topic": "...",
      "content_objective": "Educational retention & saves"
    }},
    {{
      "date": "Day 8",
      "platform": "Meta Ads",
      "format": "Reels",
      "topic": "...",
      "content_objective": "Direct conversion"
    }},
    {{
      "date": "Day 12",
      "platform": "Instagram",
      "format": "Static Posts",
      "topic": "...",
      "content_objective": "Social proof & review"
    }}
  ],
  "performance_measurement": [
    "Reel 3-Second Retention Rate (Benchmark: >30%)",
    "Average Save-to-Reach Ratio (Benchmark: >3%)",
    "Click-Through Rate on Bio Link (Benchmark: >1.8%)",
    "Direct Attributed Return on Content Spend"
  ]
}}
"""
