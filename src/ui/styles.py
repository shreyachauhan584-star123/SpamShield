
"""Simple and consistent styling for GramSuraksha AI."""

from __future__ import annotations

import html

NAVY = "#12284c"
TEAL = "#0f766e"
AMBER = "#92400e"
RED = "#991b1b"

RISK_STYLE = {
    "LOW": (TEAL, "#e3f4f1", "✅"),
    "MEDIUM": (AMBER, "#fdf1cf", "⚠️"),
    "HIGH": (RED, "#fde8e8", "🚨"),
    "UNKNOWN": ("#1e3a5f", "#e6edf6", "❓"),
}

TEXT_SCALE = {0: 1.0, 1: 1.15, 2: 1.3}


def build_css(scale_idx=0):
    px = 16 * TEXT_SCALE.get(scale_idx, 1.0)

    return f"""
    <style>

    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans:wght@400;600;700&family=Noto+Sans+Devanagari:wght@400;600;700&display=swap');

    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,0,0');

    /* Global styling */
    html {{
        font-size: {px}px;
    }}

    html, body, .stMarkdown, textarea, button, input {{
        font-family: 'Inter', 'Noto Sans',
        'Noto Sans Devanagari', sans-serif !important;
    }}

    /* Material Symbols */
    .material-symbols-rounded,
    [data-testid="stIconMaterial"] {{
        font-family: "Material Symbols Rounded" !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-size: 24px !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        white-space: nowrap !important;
        word-wrap: normal !important;
        direction: ltr !important;
        font-feature-settings: "liga";
        -webkit-font-feature-settings: "liga";
        -webkit-font-smoothing: antialiased;
    }}

    /* Main container */
    .block-container {{
        max-width: 850px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }}

    /* Headings */
    h1, h2, h3 {{
        color: {NAVY};
        letter-spacing: -0.02em;
    }}

    h1 {{
        font-size: 1.9rem !important;
        font-weight: 700 !important;
    }}

    h2 {{
        font-size: 1.45rem !important;
    }}

    h3 {{
        font-size: 1.15rem !important;
    }}

    p, li {{
        line-height: 1.65;
    }}

    /* Home page heading */
    .gs-hero {{
        background: {NAVY};
        color: white;
        border-radius: 14px;
        padding: 1.5rem;
        margin-bottom: 1.3rem;
    }}

    .gs-hero h1 {{
        color: white;
        margin: 0;
        font-size: 1.8rem !important;
    }}

    .gs-hero .sub {{
        font-size: 1.1rem;
        font-weight: 600;
        margin-top: 0.4rem;
        color: #bfe9e3;
    }}

    .gs-hero .tag {{
        margin-top: 0.5rem;
        color: #e6edf6;
        line-height: 1.5;
    }}

    /* Buttons */
    .stButton > button {{
        width: 100%;
        min-height: 45px;
        height: auto !important;
        padding: 0.7rem 1rem !important;
        border-radius: 9px;
        font-size: 0.95rem;
        font-weight: 600;
        white-space: normal !important;
        line-height: 1.5 !important;
        text-align: left !important;
        overflow: visible !important;
        word-break: normal !important;
        overflow-wrap: break-word !important;
    }}

    .stButton > button p {{
        margin: 0 !important;
        line-height: 1.5 !important;
    }}

    .stButton > button:focus-visible,
    textarea:focus-visible {{
        outline: 3px solid #f59e0b !important;
        outline-offset: 2px;
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0.5rem;
        border-bottom: 1px solid #e2e8f0;
    }}

    .stTabs [data-baseweb="tab"] {{
        padding: 0.65rem 1rem;
        border-radius: 8px 8px 0 0;
        font-weight: 600;
    }}

    .stTabs [data-baseweb="tab-highlight"] {{
        background-color: {TEAL};
    }}

    .stTabs [data-baseweb="tab-panel"] {{
        padding-top: 1.2rem;
    }}

    /* Input fields */
    textarea {{
        font-size: 1rem !important;
        line-height: 1.6 !important;
    }}

    [data-baseweb="input"],
    [data-baseweb="select"] {{
        border-radius: 8px;
    }}

    /* Expanders */
    [data-testid="stExpander"] {{
        border: 1px solid #dce3ec;
        border-radius: 10px;
        margin-bottom: 0.65rem;
        background: white;
    }}

    [data-testid="stExpander"] summary {{
        font-weight: 600;
        padding: 0.7rem;
        white-space: normal !important;
        line-height: 1.5 !important;
        align-items: center;
    }}

    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
        padding: 0.8rem 1rem 1rem;
    }}

    /* Result cards */
    .gs-risk {{
        border-radius: 12px;
        border-left: 7px solid var(--c);
        background: var(--bg);
        padding: 1rem 1.2rem;
        margin: 1rem 0;
        color: #111827;
    }}

    .gs-risk .level {{
        font-weight: 700;
        font-size: 1rem;
        color: var(--c);
    }}

    .gs-risk .head {{
        font-weight: 700;
        font-size: 1.3rem;
        margin: 0.3rem 0;
        color: #111827;
    }}

    .gs-risk .sum {{
        font-size: 1rem;
        line-height: 1.6;
    }}

    /* Message card */
    .gs-msg {{
        background: white;
        border: 1px solid #cbd5e1;
        border-radius: 9px;
        padding: 0.8rem 1rem;
        line-height: 1.6;
        word-break: break-word;
        color: #111827;
    }}

    mark.gs-mark {{
        background: #fcd34d;
        color: #111827;
        padding: 0 0.15em;
        border-radius: 3px;
    }}

    /* Indicator cards */
    .gs-ind {{
        border: 1px solid #cbd5e1;
        border-radius: 9px;
        background: white;
        padding: 0.7rem 0.9rem;
        margin-bottom: 0.5rem;
        color: #111827;
    }}

    .gs-ind .sev {{
        font-weight: 700;
        font-size: 0.85rem;
        color: {NAVY};
    }}

    .gs-ind code {{
        background: #eef2f7;
        color: #111827;
        padding: 0.1rem 0.3rem;
        border-radius: 4px;
    }}

    /* Quote card */
    .gs-quote {{
        border-left: 4px solid {TEAL};
        background: #f1f7f6;
        padding: 0.9rem 1rem;
        border-radius: 8px;
        color: #111827;
        line-height: 1.6;
        margin: 0.5rem 0;
    }}

    /* Columns */
    [data-testid="column"] {{
        min-width: 0 !important;
    }}

    /* Markdown text */
    .stMarkdown p {{
        line-height: 1.6 !important;
        overflow-wrap: anywhere;
    }}

    /* Responsive layout */
    @media (max-width: 640px) {{

        .block-container {{
            padding: 1rem 1rem 2rem;
        }}

        .gs-hero {{
            padding: 1.1rem;
        }}

        .gs-hero h1 {{
            font-size: 1.5rem !important;
        }}

        .gs-risk .head {{
            font-size: 1.15rem;
        }}

    }}

    </style>
    """


def hero_html(title, subtitle, tagline):
    e = html.escape

    return (
        f'<div class="gs-hero">'
        f'<h1>🛡️ {e(title)}</h1>'
        f'<div class="sub">{e(subtitle)}</div>'
        f'<div class="tag">{e(tagline)}</div>'
        f'</div>'
    )


def risk_card_html(level, level_label, headline, summary):
    c, bg, icon = RISK_STYLE[level]
    e = html.escape

    return (
        f'<div class="gs-risk" role="status" aria-live="polite" '
        f'style="--c:{c};--bg:{bg}">'
        f'<div class="level">{icon} {e(level_label)}</div>'
        f'<div class="head">{e(headline)}</div>'
        f'<div class="sum">{e(summary)}</div></div>'
    )


def quote_html(text):
    return (
        f'<div class="gs-quote">'
        f'{html.escape(text)}'
        f'</div>'
    )
