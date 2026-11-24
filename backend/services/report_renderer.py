"""
backend/services/report_renderer.py
Renders structured report JSON into client-ready, styled HTML documents.
Supports direct presentation, HTML download, and browser Print-to-PDF formatting.
"""

from typing import Any, Dict, List


def render_report_to_html(report_data: Dict[str, Any]) -> str:
    """Generates an executive, client-ready HTML document from structured report JSON."""
    client_info = report_data.get("client_info", {})
    report_title = report_data.get("report_title", "Marketing Performance Report")
    report_type = report_data.get("report_type", "performance_analysis")

    is_content_strategy = report_type in ["content_strategy", "content_calendar", "advertising_strategy"]

    if is_content_strategy:
        return _render_content_strategy_html(report_data, client_info, report_title)
    return _render_performance_report_html(report_data, client_info, report_title)


def _render_performance_report_html(data: Dict[str, Any], client: Dict[str, Any], title: str) -> str:
    overview = data.get("performance_overview", {})
    curr = overview.get("current", {})
    prev = overview.get("previous", {})
    changes = overview.get("changes", {})
    exec_summary = data.get("executive_summary", {})
    campaigns = data.get("campaign_performance", [])
    recommendations = data.get("recommended_actions", [])
    creatives = data.get("creative_observations", [])
    next_strategy = data.get("next_period_strategy", [])

    def fmt_curr(val):
        return f"₹{val:,.2f}" if isinstance(val, (int, float)) else "N/A"

    def fmt_num(val):
        return f"{val:,}" if isinstance(val, (int, float)) else "0"

    def fmt_pct(val):
        if val is None:
            return ""
        sign = "+" if val > 0 else ""
        color = "#10b981" if val > 0 else "#ef4444" if val < 0 else "#94a3b8"
        return f'<span style="color: {color}; font-size: 0.85rem; font-weight: 600;">{sign}{val:.1f}%</span>'

    # Build campaign rows
    campaign_rows = ""
    for c in campaigns:
        roas_str = f"{c.get('roas'):.2f}x" if c.get('roas') is not None else "N/A"
        campaign_rows += f"""
        <tr>
            <td style="font-weight: 600; color: #0f172a;">{c.get('campaign_name')}</td>
            <td><span class="badge badge-platform">{c.get('platform', 'Meta')}</span></td>
            <td>{fmt_curr(c.get('spend'))}</td>
            <td>{fmt_num(c.get('clicks'))}</td>
            <td>{fmt_num(c.get('conversions'))}</td>
            <td style="font-weight: 600;">{fmt_curr(c.get('revenue'))}</td>
            <td style="font-weight: 700; color: #4f46e5;">{roas_str}</td>
            <td><span class="badge badge-active">{c.get('status', 'ACTIVE')}</span></td>
        </tr>
        """

    # Build recommendations
    rec_cards = ""
    for r in recommendations:
        priority = r.get("priority", "Medium")
        p_color = "#ef4444" if priority == "High" else "#f59e0b" if priority == "Medium" else "#10b981"
        rec_cards += f"""
        <div class="rec-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <h4 style="margin: 0; font-size: 1rem; color: #0f172a;">{r.get('action')}</h4>
                <span style="background: {p_color}20; color: {p_color}; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 700;">{priority} Priority</span>
            </div>
            <p style="margin: 0 0 0.5rem 0; color: #475569; font-size: 0.9rem;"><strong>Rationale:</strong> {r.get('reason')}</p>
            <p style="margin: 0; color: #64748b; font-size: 0.85rem;"><strong>Evidence:</strong> {r.get('supporting_evidence')}</p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title} - {client.get('client_name')}</title>
    <style>
        body {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; line-height: 1.6; color: #1e293b; background: #f8fafc; margin: 0; padding: 2rem; }}
        .report-container {{ max-width: 1000px; margin: 0 auto; background: #ffffff; padding: 2.5rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); }}
        .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #e2e8f0; padding-bottom: 1.5rem; margin-bottom: 2rem; }}
        .header h1 {{ margin: 0 0 0.5rem 0; font-size: 1.85rem; color: #0f172a; }}
        .client-meta {{ font-size: 0.9rem; color: #64748b; line-height: 1.5; }}
        .section-title {{ font-size: 1.25rem; font-weight: 700; color: #0f172a; margin: 2rem 0 1rem 0; padding-bottom: 0.4rem; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; gap: 0.5rem; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .kpi-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1.25rem; }}
        .kpi-title {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 0.4rem; }}
        .kpi-value {{ font-size: 1.65rem; font-weight: 800; color: #0f172a; line-height: 1.2; }}
        .exec-box {{ background: linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 100%); border-left: 4px solid #0284c7; padding: 1.25rem 1.5rem; border-radius: 0 8px 8px 0; margin-bottom: 2rem; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.9rem; }}
        th {{ background: #f1f5f9; color: #475569; text-align: left; padding: 0.75rem 1rem; font-weight: 600; border-bottom: 2px solid #cbd5e1; }}
        td {{ padding: 0.75rem 1rem; border-bottom: 1px solid #e2e8f0; }}
        .badge {{ display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }}
        .badge-platform {{ background: #e0e7ff; color: #4338ca; }}
        .badge-active {{ background: #dcfce7; color: #15803d; }}
        .rec-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 0.75rem; }}
        @media print {{
            body {{ background: #ffffff; padding: 0; }}
            .report-container {{ box-shadow: none; padding: 0; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="header">
            <div>
                <h1>{title}</h1>
                <div class="client-meta">
                    <strong>Client:</strong> {client.get('client_name')} &bull; 
                    <strong>Industry:</strong> {client.get('industry')} &bull; 
                    <strong>Platform:</strong> {client.get('platform', 'All Platforms')}<br>
                    <strong>Period:</strong> {client.get('reporting_period', {}).get('label', 'Recent Period')} &bull;
                    <strong>Generated:</strong> {client.get('report_date')}
                </div>
            </div>
            <div style="text-align: right;">
                <span style="background: #4f46e5; color: white; padding: 0.4rem 0.8rem; border-radius: 6px; font-weight: 700; font-size: 0.85rem;">AI_REEL Agency Platform</span>
            </div>
        </div>

        <div class="exec-box">
            <h3 style="margin: 0 0 0.5rem 0; color: #0369a1; font-size: 1.1rem;">Executive Performance Overview</h3>
            <p style="margin: 0 0 0.75rem 0; color: #334155;">{exec_summary.get('overall_performance', '')}</p>
            <div style="font-size: 0.9rem; color: #0f172a;">
                <strong>Core Takeaway:</strong> {exec_summary.get('core_observation', '')}
            </div>
        </div>

        <div class="section-title">📊 Key Performance Overview</div>
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">Total Ad Spend</div>
                <div class="kpi-value">{fmt_curr(curr.get('spend'))}</div>
                <div>{fmt_pct(changes.get('spend'))} vs prior period</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Attributed Revenue</div>
                <div class="kpi-value">{fmt_curr(curr.get('revenue'))}</div>
                <div>{fmt_pct(changes.get('revenue'))} vs prior period</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Blended ROAS</div>
                <div class="kpi-value" style="color: #4f46e5;">{curr.get('roas') or 'N/A'}{'x' if curr.get('roas') is not None else ''}</div>
                <div>{fmt_pct(changes.get('roas'))} vs prior period</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Conversions</div>
                <div class="kpi-value">{fmt_num(curr.get('conversions'))}</div>
                <div>{fmt_pct(changes.get('conversions'))} vs prior period</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Click-Through Rate (CTR)</div>
                <div class="kpi-value">{curr.get('ctr') or 0.0}%</div>
                <div>{fmt_pct(changes.get('ctr'))} vs prior period</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Cost Per Click (CPC)</div>
                <div class="kpi-value">{fmt_curr(curr.get('cpc'))}</div>
                <div>{fmt_pct(changes.get('cpc'))} vs prior period</div>
            </div>
        </div>

        <div class="section-title">🚀 Campaign Performance Breakdown</div>
        <table>
            <thead>
                <tr>
                    <th>Campaign</th>
                    <th>Platform</th>
                    <th>Spend</th>
                    <th>Clicks</th>
                    <th>Conversions</th>
                    <th>Revenue</th>
                    <th>ROAS</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {campaign_rows}
            </tbody>
        </table>

        <div class="section-title">🎯 Prioritized Strategic Recommendations</div>
        {rec_cards}

        <div class="section-title">📅 Next Period Strategy Initiatives</div>
        <ul style="padding-left: 1.25rem; color: #334155;">
            {''.join(f'<li style="margin-bottom: 0.4rem;">{s}</li>' for s in next_strategy)}
        </ul>

        <div style="margin-top: 3rem; text-align: center; color: #94a3b8; font-size: 0.8rem; border-top: 1px solid #e2e8f0; padding-top: 1rem;">
            Generated by AI_REEL Enterprise Marketing Reporting System &bull; Confidential Agency Client Report
        </div>
    </div>
</body>
</html>"""


def _render_content_strategy_html(data: Dict[str, Any], client: Dict[str, Any], title: str) -> str:
    ideas = data.get("content_ideas", [])
    pillars = data.get("content_pillars", [])
    calendar = data.get("content_calendar", [])
    recs = data.get("strategic_recommendations", {})
    kpis = data.get("performance_measurement", [])

    # Build ideas rows
    idea_rows = ""
    for item in ideas:
        idea_rows += f"""
        <tr>
            <td style="font-weight: 700; color: #4f46e5;">#{item.get('item_no')}</td>
            <td><span class="badge" style="background: #fdf2f8; color: #be185d;">{item.get('format')}</span></td>
            <td style="font-weight: 600;">{item.get('content_idea')}</td>
            <td style="color: #0369a1; font-style: italic;">"{item.get('hook')}"</td>
            <td>{item.get('description')}</td>
            <td style="font-weight: 600; color: #15803d;">{item.get('cta')}</td>
        </tr>
        """

    # Build calendar rows
    cal_rows = ""
    for c in calendar:
        cal_rows += f"""
        <tr>
            <td style="font-weight: 700;">{c.get('date')}</td>
            <td>{c.get('platform')}</td>
            <td>{c.get('format')}</td>
            <td style="font-weight: 600;">{c.get('topic')}</td>
            <td>{c.get('content_objective')}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title} - {client.get('client_name')}</title>
    <style>
        body {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; line-height: 1.6; color: #1e293b; background: #f8fafc; margin: 0; padding: 2rem; }}
        .report-container {{ max-width: 1000px; margin: 0 auto; background: #ffffff; padding: 2.5rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); }}
        .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #e2e8f0; padding-bottom: 1.5rem; margin-bottom: 2rem; }}
        .header h1 {{ margin: 0 0 0.5rem 0; font-size: 1.85rem; color: #0f172a; }}
        .theme-banner {{ background: linear-gradient(135deg, #ede9fe 0%, #fce7f3 100%); border-left: 4px solid #8b5cf6; padding: 1.25rem 1.5rem; border-radius: 0 8px 8px 0; margin-bottom: 2rem; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.9rem; }}
        th {{ background: #f1f5f9; color: #475569; text-align: left; padding: 0.75rem 1rem; font-weight: 600; border-bottom: 2px solid #cbd5e1; }}
        td {{ padding: 0.75rem 1rem; border-bottom: 1px solid #e2e8f0; }}
        .badge {{ display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }}
        .section-title {{ font-size: 1.25rem; font-weight: 700; color: #0f172a; margin: 2rem 0 1rem 0; padding-bottom: 0.4rem; border-bottom: 1px solid #e2e8f0; }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="header">
            <div>
                <h1>{title}</h1>
                <div style="font-size: 0.9rem; color: #64748b;">
                    <strong>Brand:</strong> {client.get('client_name')} &bull; 
                    <strong>Industry:</strong> {client.get('industry')} &bull;
                    <strong>Generated:</strong> {client.get('report_date')}
                </div>
            </div>
            <div style="text-align: right;">
                <span style="background: #8b5cf6; color: white; padding: 0.4rem 0.8rem; border-radius: 6px; font-weight: 700; font-size: 0.85rem;">Content Architecture</span>
            </div>
        </div>

        <div class="theme-banner">
            <h3 style="margin: 0 0 0.3rem 0; color: #6d28d9; font-size: 1.15rem;">Campaign Theme: {data.get('campaign_theme')}</h3>
            <p style="margin: 0; color: #475569; font-size: 0.95rem;">{data.get('theme_relevance')}</p>
        </div>

        <div class="section-title">💡 High-Converting Content Concepts</div>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Format</th>
                    <th>Content Idea</th>
                    <th>Opening Hook</th>
                    <th>Creative Visual Cue</th>
                    <th>Call to Action</th>
                </tr>
            </thead>
            <tbody>
                {idea_rows}
            </tbody>
        </table>

        <div class="section-title">📅 Publishing Schedule Calendar</div>
        <table>
            <thead>
                <tr>
                    <th>Schedule</th>
                    <th>Platform</th>
                    <th>Format</th>
                    <th>Topic</th>
                    <th>Objective</th>
                </tr>
            </thead>
            <tbody>
                {cal_rows}
            </tbody>
        </table>

        <div class="section-title">📈 Success Measurement KPIs</div>
        <ul style="padding-left: 1.25rem; color: #334155;">
            {''.join(f'<li style="margin-bottom: 0.4rem;">{k}</li>' for k in kpis)}
        </ul>

        <div style="margin-top: 3rem; text-align: center; color: #94a3b8; font-size: 0.8rem; border-top: 1px solid #e2e8f0; padding-top: 1rem;">
            Generated by AI_REEL Enterprise Marketing Reporting System &bull; Confidential Agency Client Report
        </div>
    </div>
</body>
</html>"""
