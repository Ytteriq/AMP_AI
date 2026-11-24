"""
backend/schemas/report_schemas.py
Pydantic schemas for the Professional AI Marketing Report Generation Platform.
Validates report payloads, KPI structures, client contexts, and structured outputs.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Common Client & Context Schemas
# -----------------------------------------------------------------------------

class ClientInfo(BaseModel):
    """Client identity and reporting parameters."""
    client_id: str = Field(..., description="Unique client identifier")
    client_name: str = Field(..., description="Brand or business name")
    industry: str = Field(default="Digital Commerce", description="Client industry or vertical")
    platform: str = Field(default="All Platforms", description="Marketing platform(s) analyzed")
    reporting_period: Dict[str, Any] = Field(
        default_factory=lambda: {"label": "Last 30 Days", "start": "", "end": ""},
        description="Date range of analyzed marketing data",
    )
    report_date: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%B %d, %Y"),
        description="Formatted date the report was generated",
    )


class ClientRecord(BaseModel):
    """Client entity stored in MongoDB 'clients' collection."""
    agency_id: str = Field(default="agency_default", description="Managing agency identifier")
    client_id: str = Field(..., description="Unique client identifier")
    client_name: str = Field(..., description="Brand or client name")
    industry: str = Field(default="E-Commerce", description="Client industry")
    website: Optional[str] = None
    brand_guidelines: Optional[str] = None
    target_audience: Optional[str] = None
    marketing_goals: Optional[List[str]] = Field(default_factory=list)
    products: Optional[List[str]] = Field(default_factory=list)
    connected_platforms: Optional[List[str]] = Field(default_factory=lambda: ["Meta Ads", "Instagram", "Google Ads"])


class AgencyRecord(BaseModel):
    """Agency profile stored in MongoDB 'agencies' collection."""
    agency_id: str = Field(default="agency_default")
    agency_name: str = Field(default="PulseMedia Digital Agency")
    contact_email: Optional[str] = None
    created_at: Optional[str] = None


# -----------------------------------------------------------------------------
# KPI Overview & Comparison Schemas
# -----------------------------------------------------------------------------

class KPIOverviewItem(BaseModel):
    """Calculated financial and marketing KPIs for a specific period."""
    spend: float = Field(0.0, description="Total advertising expenditure")
    impressions: int = Field(0, description="Total ad impressions")
    reach: int = Field(0, description="Unique audience reached")
    clicks: int = Field(0, description="Total link clicks")
    ctr: Optional[float] = Field(None, description="Click-through rate percentage")
    cpc: Optional[float] = Field(None, description="Cost per click")
    cpm: Optional[float] = Field(None, description="Cost per thousand impressions")
    conversions: int = Field(0, description="Total direct conversions")
    conversion_rate: Optional[float] = Field(None, description="Conversion rate percentage")
    cpa: Optional[float] = Field(None, description="Cost per acquisition")
    revenue: float = Field(0.0, description="Attributed sales revenue")
    roas: Optional[float] = Field(None, description="Return on ad spend (Revenue / Spend)")


class PeriodComparison(BaseModel):
    """Side-by-side KPI comparison between current and previous reporting periods."""
    current: KPIOverviewItem
    previous: KPIOverviewItem
    changes: Dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="Percentage changes for each KPI: ((Current - Previous) / Previous) * 100",
    )


# -----------------------------------------------------------------------------
# Performance Report Sub-sections
# -----------------------------------------------------------------------------

class ExecutiveSummary(BaseModel):
    """High-level executive overview for C-level and agency stakeholders."""
    overall_performance: str = Field(..., description="Summary of overall account health and trajectory")
    key_improvements: List[str] = Field(default_factory=list, description="Top positive metrics and milestones")
    key_declines: List[str] = Field(default_factory=list, description="Metrics or campaigns experiencing dips")
    main_opportunities: List[str] = Field(default_factory=list, description="Immediate growth opportunities")
    core_observation: str = Field(..., description="Most crucial single observation of this period")


class ImportantChange(BaseModel):
    """Significant performance shift or anomaly identified in the period."""
    metric: str = Field(..., description="Metric or area, e.g. 'ROAS Efficiency' or 'Meta Traffic'")
    description: str = Field(..., description="Clear explanation of the change")
    impact: Literal["positive", "negative", "neutral"] = Field("neutral")


class CampaignPerformanceItem(BaseModel):
    """Individual campaign row in the performance table."""
    campaign_name: str
    platform: str = "Meta Ads"
    spend: float
    clicks: int
    conversions: int
    revenue: float
    roas: Optional[float] = None
    status: str = "ACTIVE"
    highlight: Optional[str] = None


class CreativeObservation(BaseModel):
    """Analysis of creative assets and ad fatigue."""
    creative_name: str
    format: str = "Video / Reel"
    observation: str
    ctr_or_conv_comparison: Optional[str] = None
    action_item: str


class PrioritizedRecommendation(BaseModel):
    """Actionable recommendation with strict evidentiary backing."""
    action: str = Field(..., description="Exact action to take")
    reason: str = Field(..., description="Business rationale")
    supporting_evidence: str = Field(..., description="Data metrics justifying this step")
    priority: Literal["High", "Medium", "Low"] = "Medium"
    expected_outcome: Optional[str] = Field(None, description="Expected operational outcome (no false guarantees)")


# -----------------------------------------------------------------------------
# Complete Marketing Performance Report Schema
# -----------------------------------------------------------------------------

class PerformanceReport(BaseModel):
    """Client-ready Marketing Performance Report."""
    report_id: str
    report_title: str = "Marketing Performance Report"
    report_type: str = "performance_analysis"
    client_info: ClientInfo
    executive_summary: ExecutiveSummary
    performance_overview: PeriodComparison
    important_changes: List[ImportantChange] = Field(default_factory=list)
    campaign_performance: List[CampaignPerformanceItem] = Field(default_factory=list)
    high_performing_campaigns: List[Dict[str, Any]] = Field(default_factory=list)
    underperforming_campaigns: List[Dict[str, Any]] = Field(default_factory=list)
    creative_observations: List[CreativeObservation] = Field(default_factory=list)
    revenue_analysis: Dict[str, Any] = Field(default_factory=dict)
    roas_analysis: Dict[str, Any] = Field(default_factory=dict)
    recommended_actions: List[PrioritizedRecommendation] = Field(default_factory=list)
    next_period_strategy: List[str] = Field(default_factory=list)
    platform_breakdown: Optional[Dict[str, Any]] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# Content Strategy Report Schemas
# -----------------------------------------------------------------------------

class ContentIdeaItem(BaseModel):
    """Detailed content post concept."""
    item_no: int
    format: Literal["Reels", "Carousels", "Static Posts", "Stories"]
    content_idea: str
    hook: str
    description: str
    cta: str


class ContentPillarItem(BaseModel):
    """Thematic content pillar."""
    pillar_name: str
    percentage_share: int = 25
    description: str
    topics: List[str] = Field(default_factory=list)


class CalendarScheduleItem(BaseModel):
    """Date-wise publishing schedule item."""
    date: str
    platform: str
    format: str
    topic: str
    content_objective: str


class ContentStrategyReport(BaseModel):
    """Client-ready Monthly Content Strategy Report."""
    report_id: str
    report_title: str = "Monthly Content Strategy"
    report_type: str = "content_strategy"
    client_info: ClientInfo
    strategic_overview: str
    campaign_theme: str
    theme_relevance: str
    content_ideas: List[ContentIdeaItem] = Field(default_factory=list)
    content_pillars: List[ContentPillarItem] = Field(default_factory=list)
    strategic_recommendations: Dict[str, List[str]] = Field(default_factory=dict)
    content_calendar: List[CalendarScheduleItem] = Field(default_factory=list)
    performance_measurement: List[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Request & Response Wrappers
# -----------------------------------------------------------------------------

class ReportGenerationRequest(BaseModel):
    """Form submission payload to generate a report."""
    agency_id: str = Field(default="agency_default")
    client_id: str = Field(..., min_length=1)
    report_type: Literal[
        "performance_analysis",
        "campaign_performance",
        "creative_performance",
        "monthly_marketing",
        "content_strategy",
        "content_calendar",
        "advertising_strategy",
    ] = "performance_analysis"
    platform: str = Field(default="All Platforms")
    date_range: str = Field(default="Last 30 Days")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    campaign_filter: Optional[str] = None
    product_filter: Optional[str] = None


class SaveReportRequest(BaseModel):
    """Payload to persist a report in MongoDB 'reports' collection."""
    agency_id: str = Field(default="agency_default")
    client_id: str
    report_type: str
    report_title: str
    platform: str
    reporting_period: Dict[str, Any]
    report_data: Dict[str, Any]
    summary: Optional[str] = None
    pdf_url: Optional[str] = None
