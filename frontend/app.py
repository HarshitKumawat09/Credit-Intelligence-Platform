import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

# -------------------------
# Page Config
# -------------------------
st.set_page_config(page_title="CredLens", page_icon="🤖", layout="wide")

# -------------------------
# Hide Streamlit default UI elements (menu and footer)
# -------------------------
# We REMOVED "header {visibility: hidden;}" to make the mobile button work.
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# -------------------------
# Load Font Awesome
# -------------------------
st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
""", unsafe_allow_html=True)

# -------------------------
# Custom CSS for App Styling
# -------------------------
st.markdown("""
    <style>
    .stButton button:hover {
        background-color: #ff3333 !important;
        transform: scale(1.05);
        box-shadow: 0px 4px 12px rgba(255, 0, 0, 0.4);
        transition: all 0.2s ease-in-out;
    }
    .stTextInput input:hover {
        border: 2px solid #00c4cc !important;
        box-shadow: 0px 0px 8px rgba(0, 196, 204, 0.6);
        transition: all 0.2s ease-in-out;
    }
    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.1);
        border-radius: 12px;
        padding: 12px;
        transition: all 0.2s ease-in-out;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-4px);
        box-shadow: 0px 6px 14px rgba(0, 0, 0, 0.1);
    }
    div[data-testid="stMetric"] > div:first-child {
        font-size: 0.8em;
        font-weight: 600;
    }
    div[data-testid="stMetric"] > div:nth-child(2) {
        font-size: 1.8em;
        font-weight: 700;
    }
    .js-plotly-plot:hover {
        transform: scale(1.01);
        transition: all 0.2s ease-in-out;
        box-shadow: 0px 6px 14px rgba(0, 0, 0, 0.1);
        border-radius: 10px;
    }
    a:hover {
        color: #00c4cc !important;
        text-decoration: underline;
    }
    </style>
""", unsafe_allow_html=True)

# -------------------------
# Configurations & Helper
# -------------------------
AGENCY_RATINGS = {"AAPL": "AA+", "MSFT": "AAA", "GOOGL": "AA+", "NVDA": "A-", "JPM": "A-", "TSLA": "BB+"}
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1/score")
API_BASE_URL = BACKEND_URL.split("/score")[0] if "/score" in BACKEND_URL else "http://localhost:8000/api/v1"

def get_api_data(ticker: str):
    """Fetches analysis data from the backend API."""
    try:
        response = requests.get(f"{BACKEND_URL}/{ticker}")
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as err:
        error_data = err.response.json()
        error_type = error_data.get("type")

        if error_type == 'INVALID_TICKER':
            st.error(f"Ticker '{ticker}' not found. Please ensure it's a valid US-listed stock and check for spelling errors.")
        else:
            st.error("An unexpected error occurred in the backend.")
        return None

    except requests.exceptions.RequestException:
        st.error("Error connecting to the backend API. Please ensure the server is running.")
        return None

def get_score_history(ticker: str, limit: int = 100):
    """Fetches saved score history for a ticker from the backend API."""
    try:
        response = requests.get(f"{API_BASE_URL}/risk-scores/ticker/{ticker}?limit={limit}")
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return []

def get_alerts(ticker: str, limit: int = 50, active_only: bool = True):
    """Fetches alerts for a ticker from the backend API."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/alerts/ticker/{ticker}?limit={limit}&active_only={'true' if active_only else 'false'}"
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return []

def get_watchlist():
    try:
        response = requests.get(f"{API_BASE_URL}/watchlist/")
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return []

def add_to_watchlist(ticker: str):
    try:
        response = requests.post(f"{API_BASE_URL}/watchlist/", json={"ticker": ticker})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None

def remove_from_watchlist(ticker: str):
    try:
        response = requests.delete(f"{API_BASE_URL}/watchlist/{ticker}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None

def _risk_level_from_score(score):
    try:
        s = float(score)
    except Exception:
        return "N/A"
    return "LOW" if s >= 75 else "MEDIUM" if s >= 50 else "HIGH"

def _pdf_escape(text: str) -> str:
    return (
        str(text)
        .replace('\\', '\\\\')
        .replace('(', '\\(')
        .replace(')', '\\)')
        .replace('\n', ' ')
    )

def _make_simple_pdf(lines):
    lines = ["" if l is None else str(l) for l in lines]

    y = 760
    line_height = 14
    left_margin = 50

    def set_font(font_key: str, size: int):
        return [f"/{font_key} {size} Tf"]

    # Build one content stream with both text and vector drawing
    content_lines = []
    content_lines.append("0 0 0 rg")
    content_lines.append("BT")
    content_lines.extend(set_font("F1", 12))
    content_lines.append(f"{left_margin} {y} Td")

    def newline():
        return f"0 -{line_height} Td"

    def draw_separator(current_y: int):
        sep_y = max(60, current_y - 6)
        return [
            "q",
            "0.7 0.7 0.7 RG",
            "1 w",
            f"{left_margin} {sep_y} m",
            f"560 {sep_y} l",
            "S",
            "Q",
        ]

    first_line = True
    for raw in lines[:80]:
        line = raw.strip("\r")

        if line == "__SEPARATOR__":
            content_lines.append("ET")
            content_lines.extend(draw_separator(y))
            y -= line_height
            content_lines.append("BT")
            content_lines.extend(set_font("F1", 12))
            content_lines.append(f"{left_margin} {y} Td")
            first_line = True
            continue

        # Basic styling tokens
        if line.startswith("# "):
            text = line[2:].strip()
            content_lines.append("ET")
            y -= 6
            content_lines.append("BT")
            content_lines.extend(set_font("F2", 20))
            content_lines.append(f"{left_margin} {y} Td")
            content_lines.append(f"({_pdf_escape(text)}) Tj")
            content_lines.append("ET")
            y -= 24
            content_lines.append("BT")
            content_lines.extend(set_font("F1", 12))
            content_lines.append(f"{left_margin} {y} Td")
            first_line = True
            continue

        if line.startswith("## "):
            text = line[3:].strip()
            if not first_line:
                content_lines.append(newline())
                y -= line_height
            content_lines.extend(set_font("F2", 13))
            content_lines.append(f"({_pdf_escape(text)}) Tj")
            content_lines.extend(set_font("F1", 12))
            first_line = False
            continue

        # Normal body line
        if not first_line:
            content_lines.append(newline())
            y -= line_height
        content_lines.append(f"({_pdf_escape(line)}) Tj")
        first_line = False

    content_lines.append("ET")

    # Top-right badge: boxed green check + CredLens Certified
    content_lines.extend([
        "q",
        "0 0.55 0 RG",
        "1.5 w",
        "390 735 170 32 re",
        "S",
        "0 0.55 0 RG",
        "2 w",
        "402 749 m",
        "408 743 l",
        "418 755 l",
        "S",
        "0 0.55 0 rg",
        "BT",
        "/F2 11 Tf",
        "430 744 Td",
        "(CredLens Certified) Tj",
        "ET",
        "Q",
    ])

    # Footer stamp: green check + CredLens Certified
    content_lines.extend([
        "q",
        "0 0.55 0 RG",
        "2 w",
        "50 45 m",
        "58 37 l",
        "72 55 l",
        "S",
        "0 0.55 0 rg",
        "BT",
        "/F2 12 Tf",
        "85 40 Td",
        "(CredLens Certified) Tj",
        "ET",
        "Q",
    ])

    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>\nendobj\n"
    )
    objects.append(
        b"4 0 obj\n<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    objects.append(b"6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n")

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)

def _make_styled_report_pdf(
    *,
    ticker: str,
    company_name: str,
    generated_at: str,
    assessment_type: str,
    score: str,
    risk_level: str,
    active_alerts: int,
    impact_rows: list,
    history_rows: list,
):
    def f_rgb(rgb):
        r, g, b = rgb
        return f"{r:.3f} {g:.3f} {b:.3f}"

    GREEN = (0.063, 0.725, 0.506)
    GREEN_DARK = (0.016, 0.471, 0.341)
    GREEN_BG = (0.925, 0.992, 0.961)
    RED = (0.937, 0.267, 0.267)
    GRAY_TEXT = (0.400, 0.400, 0.400)
    BORDER = (0.878, 0.878, 0.878)
    HEADER_BG = (0.965, 0.965, 0.965)

    content = []

    def draw_rect(x, y, w, h, *, stroke_rgb=None, fill_rgb=None, line_width=1):
        ops = ["q"]
        if fill_rgb is not None:
            ops.append(f"{f_rgb(fill_rgb)} rg")
        if stroke_rgb is not None:
            ops.append(f"{f_rgb(stroke_rgb)} RG")
        ops.append(f"{line_width} w")
        ops.append(f"{x} {y} {w} {h} re")
        if fill_rgb is not None and stroke_rgb is not None:
            ops.append("B")
        elif fill_rgb is not None:
            ops.append("f")
        else:
            ops.append("S")
        ops.append("Q")
        content.extend(ops)

    def draw_line(x1, y1, x2, y2, *, stroke_rgb=BORDER, line_width=1):
        content.extend(
            [
                "q",
                f"{f_rgb(stroke_rgb)} RG",
                f"{line_width} w",
                f"{x1} {y1} m",
                f"{x2} {y2} l",
                "S",
                "Q",
            ]
        )

    def draw_text(x, y, text, *, font="F1", size=12, rgb=(0, 0, 0)):
        content.extend(
            [
                "q",
                f"{f_rgb(rgb)} rg",
                "BT",
                f"/{font} {int(size)} Tf",
                f"{int(x)} {int(y)} Td",
                f"({_pdf_escape(text)}) Tj",
                "ET",
                "Q",
            ]
        )

    page_w = 612
    page_h = 792

    margin_x = 40
    y_top = page_h - 50

    draw_text(margin_x, y_top, "CredLens Report", font="F2", size=22)
    draw_text(
        margin_x,
        y_top - 26,
        f"Target: {company_name} ({ticker})",
        font="F2",
        size=13,
    )
    draw_text(
        margin_x,
        y_top - 44,
        f"Generated: {generated_at} | Assessment Type: {assessment_type}",
        font="F1",
        size=10,
        rgb=GRAY_TEXT,
    )

    badge_w = 165
    badge_h = 26
    badge_x = page_w - margin_x - badge_w
    badge_y = y_top - 6
    draw_rect(badge_x, badge_y, badge_w, badge_h, stroke_rgb=GREEN, fill_rgb=GREEN_BG, line_width=1)
    content.extend(
        [
            "q",
            f"{f_rgb(GREEN)} RG",
            "2 w",
            f"{badge_x + 10} {badge_y + 13} m",
            f"{badge_x + 15} {badge_y + 8} l",
            f"{badge_x + 25} {badge_y + 18} l",
            "S",
            "Q",
        ]
    )
    draw_text(badge_x + 34, badge_y + 8, "CredLens Certified", font="F2", size=11, rgb=GREEN_DARK)

    divider_y = y_top - 58
    draw_line(margin_x, divider_y, page_w - margin_x, divider_y, stroke_rgb=BORDER, line_width=1)

    card_y = divider_y - 85
    card_h = 70
    gap = 12
    card_w = int((page_w - 2 * margin_x - 2 * gap) / 3)
    card1_x = margin_x
    card2_x = card1_x + card_w + gap
    card3_x = card2_x + card_w + gap

    draw_rect(card1_x, card_y, card_w, card_h, stroke_rgb=BORDER, fill_rgb=(1, 1, 1), line_width=1)
    draw_rect(card2_x, card_y, card_w, card_h, stroke_rgb=BORDER, fill_rgb=(1, 1, 1), line_width=1)
    draw_rect(card3_x, card_y, card_w, card_h, stroke_rgb=BORDER, fill_rgb=(1, 1, 1), line_width=1)

    score_color = GREEN if str(risk_level).upper() == "LOW" else RED if str(risk_level).upper() == "HIGH" else (0.961, 0.620, 0.043)

    draw_text(card1_x + 16, card_y + 40, str(score), font="F2", size=28, rgb=score_color)
    draw_text(card1_x + 16, card_y + 16, "Overall Score", font="F1", size=10, rgb=GRAY_TEXT)

    draw_text(card2_x + 16, card_y + 40, str(risk_level).upper(), font="F2", size=22)
    draw_text(card2_x + 16, card_y + 16, "Risk Level", font="F1", size=10, rgb=GRAY_TEXT)

    draw_text(card3_x + 16, card_y + 40, str(active_alerts), font="F2", size=28)
    draw_text(card3_x + 16, card_y + 16, "Active Alerts", font="F1", size=10, rgb=GRAY_TEXT)

    section1_y = card_y - 36
    draw_text(margin_x, section1_y, "Impact Analysis", font="F2", size=14)
    draw_text(margin_x, section1_y - 16, "Analysis of metric shifts since the last model run.", font="F1", size=10, rgb=GRAY_TEXT)

    table_x = margin_x
    table_y_top = section1_y - 34
    row_h = 18
    cols = [260, 90, 90, 90]
    table_w = sum(cols)

    draw_rect(table_x, table_y_top - row_h, table_w, row_h, stroke_rgb=BORDER, fill_rgb=HEADER_BG, line_width=1)
    headers = ["Metric Name", "Impact (Δ)", "Previous", "Latest"]
    cx = table_x
    for i, h in enumerate(headers):
        draw_text(cx + 6, table_y_top - 13, h, font="F2", size=10)
        cx += cols[i]

    max_rows = 6
    rows = impact_rows[:max_rows] if isinstance(impact_rows, list) else []
    for r_i, r in enumerate(rows):
        y_row_top = table_y_top - (r_i + 1) * row_h
        draw_rect(table_x, y_row_top - row_h, table_w, row_h, stroke_rgb=BORDER, fill_rgb=(1, 1, 1), line_width=1)
        metric = str(r.get("metric") or r.get("feature") or "")
        delta = r.get("delta")
        prev = r.get("prev")
        latest = r.get("latest")
        try:
            delta_f = float(delta)
        except Exception:
            delta_f = None
        d_color = GREEN if (delta_f is not None and delta_f >= 0) else RED

        draw_text(table_x + 6, y_row_top - 13, metric[:42], font="F1", size=10)
        draw_text(table_x + cols[0] + 6, y_row_top - 13, f"{float(delta):+.2f}" if delta_f is not None else "N/A", font="F2", size=10, rgb=d_color)
        draw_text(table_x + cols[0] + cols[1] + 6, y_row_top - 13, f"{float(prev):+.2f}" if prev is not None else "N/A", font="F1", size=10)
        draw_text(table_x + cols[0] + cols[1] + cols[2] + 6, y_row_top - 13, f"{float(latest):+.2f}" if latest is not None else "N/A", font="F1", size=10)

    section2_y = table_y_top - (len(rows) + 2) * row_h - 30
    draw_line(margin_x, section2_y + 18, page_w - margin_x, section2_y + 18, stroke_rgb=BORDER, line_width=1)
    draw_text(margin_x, section2_y, "Recent Audit Log", font="F2", size=14)

    audit_y_top = section2_y - 18
    audit_cols = [220, 80, 100]
    audit_w = sum(audit_cols)
    draw_rect(table_x, audit_y_top - row_h, audit_w, row_h, stroke_rgb=BORDER, fill_rgb=HEADER_BG, line_width=1)
    audit_headers = ["Timestamp", "Score", "Risk"]
    ax = table_x
    for i, h in enumerate(audit_headers):
        draw_text(ax + 6, audit_y_top - 13, h, font="F2", size=10)
        ax += audit_cols[i]

    h_rows = history_rows[:3] if isinstance(history_rows, list) else []
    for r_i, r in enumerate(h_rows):
        y_row_top = audit_y_top - (r_i + 1) * row_h
        draw_rect(table_x, y_row_top - row_h, audit_w, row_h, stroke_rgb=BORDER, fill_rgb=(1, 1, 1), line_width=1)
        ts = str(r.get("timestamp") or r.get("created_at") or "")
        sc = r.get("score")
        rk = str(r.get("risk") or r.get("risk_level") or "")
        draw_text(table_x + 6, y_row_top - 13, ts[:22], font="F1", size=10)
        draw_text(table_x + audit_cols[0] + 6, y_row_top - 13, f"{float(sc):.1f}" if sc is not None else "N/A", font="F1", size=10)
        draw_text(table_x + audit_cols[0] + audit_cols[1] + 6, y_row_top - 13, rk[:12], font="F1", size=10)

    content.extend(
        [
            "q",
            f"{f_rgb(GREEN)} RG",
            "2 w",
            "50 45 m",
            "58 37 l",
            "72 55 l",
            "S",
            "Q",
        ]
    )
    draw_text(85, 40, "CredLens Certified", font="F2", size=12, rgb=GREEN_DARK)

    stream = "\n".join(content).encode("latin-1", errors="replace")

    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>\nendobj\n"
    )
    objects.append(
        b"4 0 obj\n<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    objects.append(b"6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n")

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)

def _extract_explanation(score_item: dict):
    fi = score_item.get('feature_importance') or {}
    exp = fi.get('explanation')
    return exp if isinstance(exp, list) else []

def _drivers_delta(latest_item: dict, prev_item: dict, top_n: int = 5):
    latest = _extract_explanation(latest_item)
    prev = _extract_explanation(prev_item)
    latest_map = {d.get('feature'): d for d in latest if d.get('feature')}
    prev_map = {d.get('feature'): d for d in prev if d.get('feature')}
    keys = set(latest_map.keys()) | set(prev_map.keys())
    changes = []
    for k in keys:
        l_imp = float(latest_map.get(k, {}).get('impact', 0) or 0)
        p_imp = float(prev_map.get(k, {}).get('impact', 0) or 0)
        delta = l_imp - p_imp
        changes.append({"feature": k, "delta_impact": delta, "latest_impact": l_imp, "prev_impact": p_imp})
    changes.sort(key=lambda x: abs(x['delta_impact']), reverse=True)
    return changes[:top_n]

def _compute_risk_outlook(history: list, window: int = 6):
    if not history or not isinstance(history, list):
        return None
    scores = []
    for item in history:
        try:
            scores.append(float(item.get('score')))
        except Exception:
            continue
    if len(scores) < 3:
        return None
    scores = scores[-window:]
    n = len(scores)
    slope = (scores[-1] - scores[0]) / max(1, (n - 1))
    diffs = [scores[i] - scores[i - 1] for i in range(1, n)]
    if diffs:
        mean_diff = sum(diffs) / len(diffs)
        var = sum((d - mean_diff) ** 2 for d in diffs) / len(diffs)
        vol = var ** 0.5
    else:
        mean_diff = 0.0
        vol = 0.0

    if slope > 0.6:
        label = "Improving"
    elif slope < -0.6:
        label = "Worsening"
    else:
        label = "Stable"

    strength = abs(slope)
    if strength >= 2.0 and vol <= max(0.6, strength * 0.8):
        confidence = "High"
    elif strength >= 1.0:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "label": label,
        "confidence": confidence,
        "window": n,
        "slope": slope,
        "total_change": scores[-1] - scores[0],
        "volatility": vol,
    }

def _estimate_scenario_score_change(score_result: dict, price_shock_pct: float, vol_multiplier: float, rate_shock: float):
    explanation = score_result.get('explanation')
    if not explanation or not isinstance(explanation, list):
        return None

    feature_map = {d.get('feature'): d for d in explanation if d.get('feature')}

    def get_val(name: str):
        try:
            return float(feature_map.get(name, {}).get('value'))
        except Exception:
            return None

    def get_imp(name: str):
        try:
            return float(feature_map.get(name, {}).get('impact', 0) or 0)
        except Exception:
            return 0.0

    adjustments = []

    def add_adjustment(feature: str, new_value):
        base = get_val(feature)
        imp = get_imp(feature)
        if base is None:
            return
        try:
            dv = float(new_value) - float(base)
        except Exception:
            return
        if abs(dv) < 1e-9:
            return
        if abs(base) > 1e-6:
            sensitivity = imp / base
        else:
            sensitivity = imp
        delta_impact = sensitivity * dv
        adjustments.append(
            {
                "feature": feature,
                "base": base,
                "new": float(new_value),
                "delta_value": dv,
                "impact": imp,
                "est_delta_impact": delta_impact,
            }
        )

    pc30 = get_val('price_change_pct_30d')
    pc90 = get_val('price_change_pct_90d')
    if pc30 is not None:
        add_adjustment('price_change_pct_30d', pc30 + price_shock_pct)
    if pc90 is not None:
        add_adjustment('price_change_pct_90d', pc90 + price_shock_pct)

    v30 = get_val('volatility_30d')
    v90 = get_val('volatility_90d')
    if v30 is not None:
        add_adjustment('volatility_30d', v30 * vol_multiplier)
    if v90 is not None:
        add_adjustment('volatility_90d', v90 * vol_multiplier)

    tr = get_val('treasury_rate_change_30d')
    if tr is not None:
        add_adjustment('treasury_rate_change_30d', tr + rate_shock)

    if not adjustments:
        return None

    delta_impact_sum = sum(a['est_delta_impact'] for a in adjustments)

    try:
        base_score = float(score_result.get('stability_score'))
    except Exception:
        base_score = None

    score_delta_est = -10.0 * float(delta_impact_sum)
    if base_score is None:
        new_score = None
    else:
        new_score = max(0.0, min(100.0, base_score + score_delta_est))

    return {
        "base_score": base_score,
        "score_delta_est": score_delta_est,
        "new_score": new_score,
        "delta_impact_sum": delta_impact_sum,
        "adjustments": adjustments,
    }

def format_market_cap(mc):
    """Formats a large number into a human-readable market cap string."""
    if mc is None:
        return "N/A"
    if mc >= 1e12:
        return f"${mc/1e12:.2f} T"
    if mc >= 1e9:
        return f"${mc/1e9:.2f} B"
    if mc >= 1e6:
        return f"${mc/1e6:.2f} M"
    return str(mc)

# -------------------------
# Main UI Layout
# -------------------------
st.markdown("""
    <div style="display: flex; align-items: center; margin-bottom: 1em;">
        <div style="font-size: 2.5em; margin-right: 10px; font-weight: bold;
                    background: linear-gradient(45deg, #00897B, #01579B);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                    color: transparent;">
            <i class="fa-solid fa-arrow-trend-up"></i> CredLens
        </div>
        <div style="font-size: 1.8em; color: #666;">
            Credit Scorecard
        </div>
    </div>
""", unsafe_allow_html=True)

# --- This is the Python code that creates the sidebar ---
st.sidebar.header("Analysis Options")
watchlist_items = get_watchlist()
watchlist_tickers = [item.get("ticker") for item in watchlist_items if item.get("ticker")]

selected_watchlist_ticker = st.sidebar.selectbox(
    "Watchlist",
    options=[""] + watchlist_tickers,
    index=0,
)

if "ticker_input" not in st.session_state:
    st.session_state["ticker_input"] = "SMCI"
if selected_watchlist_ticker:
    st.session_state["ticker_input"] = selected_watchlist_ticker

ticker_input = st.sidebar.text_input("Enter Company Ticker", key="ticker_input").upper()

col_w1, col_w2 = st.sidebar.columns(2)
with col_w1:
    if st.button("Add to Watchlist"):
        if ticker_input:
            add_to_watchlist(ticker_input)
            st.rerun()
with col_w2:
    if st.button("Remove"):
        if ticker_input:
            remove_from_watchlist(ticker_input)
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Compare")
compare_selected = st.sidebar.multiselect(
    "Select up to 5 tickers",
    options=watchlist_tickers,
    default=watchlist_tickers[:2] if len(watchlist_tickers) >= 2 else watchlist_tickers,
    max_selections=5,
)
compare_manual = st.sidebar.text_input("Add tickers (comma-separated)", value="")
compare_button = st.sidebar.button("Compare Selected")

analyze_button = st.sidebar.button("Analyze Creditworthiness", type="primary")
st.sidebar.info("Enter a stock ticker (e.g., AAPL, SMCI, BA) to get its real-time, explainable stability score.")

if compare_button:
    manual = [t.strip().upper() for t in compare_manual.split(",") if t.strip()]
    tickers_to_compare = []
    for t in (compare_selected + manual):
        if t and t not in tickers_to_compare:
            tickers_to_compare.append(t)
        if len(tickers_to_compare) >= 5:
            break

    if not tickers_to_compare:
        st.warning("Select or enter at least one ticker to compare.")
    else:
        st.header("Comparison")
        rows = []
        for t in tickers_to_compare:
            with st.spinner(f"Fetching {t}..."):
                data = get_api_data(t)
            if not data:
                continue
            score_result = data.get('score_result', {})
            info = data.get('company_info', {})
            score = score_result.get('stability_score')
            rows.append({
                "Ticker": t,
                "Company": data.get('company_name', t),
                "Score": score,
                "Risk Level": _risk_level_from_score(score),
                "Assessment": score_result.get('assessment_type', 'N/A'),
                "News Sentiment": score_result.get('latest_sentiment', None),
                "Market Cap": info.get('marketCap'),
                "P/E": info.get('trailingPE'),
                "S&P Rating": AGENCY_RATINGS.get(t, "N/A"),
            })

        if not rows:
            st.error("Could not fetch data for the selected tickers.")
        else:
            compare_df = pd.DataFrame(rows)
            st.dataframe(compare_df, use_container_width=True)
            try:
                plot_df = compare_df.copy()
                plot_df['Score'] = pd.to_numeric(plot_df['Score'], errors='coerce')
                plot_df = plot_df.dropna(subset=['Score'])
                if not plot_df.empty:
                    fig_compare = px.bar(
                        plot_df,
                        x='Ticker',
                        y='Score',
                        color='Risk Level',
                        title='Stability Score Comparison',
                        template='plotly_white'
                    )
                    st.plotly_chart(fig_compare, use_container_width=True)
            except Exception:
                pass

if analyze_button:
    if not ticker_input:
        st.warning("Please enter a company ticker.")
    else:
        with st.spinner(f"Analyzing {ticker_input}..."):
            api_data = get_api_data(ticker_input)

        if api_data:
            score_result = api_data['score_result']
            info = api_data.get('company_info', {})
            company_name = api_data.get('company_name', ticker_input)

            plotly_template = 'plotly_white'

            st.header(f"Analysis for {company_name}")

            score = score_result.get('stability_score', 0)
            if score_result.get('assessment_type') != 'Heuristic':
                if score > 75:
                    st.success("✅ Stable: Credit-risk under control.")
                elif score > 50:
                    st.warning("⚠ Neutral: Some factors indicate potential risk.")
                else:
                    st.error("🚨 Volatile: Significant downside risk detected.")

            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                if score_result.get('assessment_type') == 'Heuristic':
                    st.metric("Stability Score", score_result['stability_score'], "Heuristic")
                else:
                    outlook = 'Stable' if score > 75 else 'Neutral' if score > 50 else 'Volatile'
                    st.metric("Stability Score", score, f"{outlook} Outlook")

            with col2:
                sentiment = score_result.get('latest_sentiment', 0.0)
                sentiment_text = "Positive" if sentiment > 0.05 else "Negative" if sentiment < -0.05 else "Neutral"
                st.metric("News Sentiment", f"{sentiment:.2f}", sentiment_text)

            with col3:
                st.metric("Market Cap", format_market_cap(info.get('marketCap')))

            with col4:
                st.metric("P/E Ratio", f"{info.get('trailingPE'):.2f}" if info.get('trailingPE') else "N/A")

            with col5:
                st.metric("S&P Rating", AGENCY_RATINGS.get(ticker_input, "N/A"))

            st.markdown("---")

            col1, col2 = st.columns((1, 1))
            with col1:
                st.subheader("Why this score? (Key Drivers)")
                if score_result.get('assessment_type') == 'Heuristic':
                    st.warning("The ML model could not be trained. A qualitative assessment is provided instead.")
                    st.subheader("Qualitative Observations")
                    for obs in score_result['explanation']:
                        st.markdown(f"- {obs['feature']}: {obs['value']}")
                else:
                    explanation_df = pd.DataFrame(score_result['explanation'])
                    explanation_df = explanation_df[explanation_df['impact'].abs() > 0.001]
                    explanation_df['impact_description'] = explanation_df['impact'].apply(lambda x: "Increases Risk" if x > 0 else "Decreases Risk")
                    explanation_df['impact_abs'] = explanation_df['impact'].abs()
                    fig_drivers_chart = px.bar(
                        explanation_df,
                        x='impact_abs',
                        y='feature',
                        color='impact_description',
                        color_discrete_map={'Increases Risk': '#FF4B4B', 'Decreases Risk': '#2ECC71'},
                        orientation='h',
                        labels={'impact_abs': 'Magnitude of Impact', 'feature': 'Feature'},
                        template=plotly_template
                    )
                    fig_drivers_chart.update_layout(
                        yaxis={'categoryorder': 'total ascending'},
                        title="Feature Impact on Downside Risk",
                        height=400,
                        margin=dict(l=170)
                    )
                    st.plotly_chart(fig_drivers_chart, use_container_width=True)

            with col2:
                st.subheader("Historical Stock Performance (1 Year)")
                stock_df = pd.DataFrame.from_dict(api_data['stock_history'], orient='index')
                stock_df.index = pd.to_datetime(stock_df.index)
                fig_stock_chart = px.line(
                    stock_df,
                    y='Close',
                    title=f"{ticker_input} Closing Price",
                    template=plotly_template
                )
                fig_stock_chart.update_layout(height=400)
                st.plotly_chart(fig_stock_chart, use_container_width=True)

            st.markdown("---")

            history = get_score_history(ticker_input, limit=100)
            if history:
                history_df = pd.DataFrame(history)
                if 'created_at' in history_df.columns:
                    history_df['created_at'] = pd.to_datetime(history_df['created_at'])
                    history_df.sort_values('created_at', inplace=True)

                st.subheader("Stability Score History")
                fig_history = px.line(
                    history_df,
                    x='created_at',
                    y='score',
                    markers=True,
                    title=f"{ticker_input} Stability Score Over Time",
                    template=plotly_template
                )
                fig_history.update_layout(height=350)
                st.plotly_chart(fig_history, use_container_width=True)

                cols_to_show = [c for c in ['created_at', 'score', 'risk_level', 'model_version'] if c in history_df.columns]
                if cols_to_show:
                    st.dataframe(history_df[cols_to_show].tail(10), use_container_width=True)

                st.markdown("---")

                st.subheader("Risk Outlook")
                outlook_data = _compute_risk_outlook(history_df.to_dict(orient='records'), window=6)
                if outlook_data:
                    label = outlook_data['label']
                    conf = outlook_data['confidence']
                    total = outlook_data['total_change']
                    slope = outlook_data['slope']
                    if label == "Improving":
                        st.success(f"Outlook: {label} ({conf} confidence)")
                    elif label == "Worsening":
                        st.warning(f"Outlook: {label} ({conf} confidence)")
                    else:
                        st.info(f"Outlook: {label} ({conf} confidence)")
                    st.caption(
                        f"Based on last {outlook_data['window']} saved runs: total change {total:+.1f} points, avg {slope:+.2f} points/run."
                    )
                else:
                    st.info("Run this ticker a few more times to generate a trend-based outlook.")
            else:
                st.info("No saved score history yet. Run analysis a few times to build a history chart.")

            alerts_data = get_alerts(ticker_input, limit=20, active_only=True)
            if alerts_data:
                st.subheader("Active Alerts")
                alerts_df = pd.DataFrame(alerts_data)
                if 'created_at' in alerts_df.columns:
                    alerts_df['created_at'] = pd.to_datetime(alerts_df['created_at'])
                cols_to_show = [c for c in ['created_at', 'alert_type', 'message'] if c in alerts_df.columns]
                if cols_to_show:
                    st.dataframe(alerts_df[cols_to_show], use_container_width=True)
            else:
                st.subheader("Active Alerts")
                st.info("No active alerts for this ticker.")

            st.markdown("---")

            st.subheader("What changed since last run")
            if history and isinstance(history, list) and len(history) >= 2:
                latest_item = history[0]
                prev_item = history[1]

                latest_score = latest_item.get('score')
                prev_score = prev_item.get('score')
                try:
                    score_delta = float(latest_score) - float(prev_score)
                except Exception:
                    score_delta = None

                if score_delta is not None:
                    if score_delta >= 0:
                        st.success(f"Score change: +{score_delta:.1f} points")
                    else:
                        st.warning(f"Score change: {score_delta:.1f} points")

                driver_changes = _drivers_delta(latest_item, prev_item, top_n=8)
                if driver_changes:
                    dc_df = pd.DataFrame(driver_changes)
                    st.dataframe(dc_df, use_container_width=True)
                else:
                    st.info("Not enough driver data to compute changes.")
            else:
                st.info("Run this ticker at least twice to see changes over time.")

            st.markdown("---")

            st.subheader("Scenario Simulator (What-if)")
            if score_result.get('assessment_type') == 'Heuristic':
                st.info("Scenario simulation is available only for ML-based assessments.")
            else:
                sc1, sc2, sc3 = st.columns(3)
                with sc1:
                    price_shock_pct = st.slider("Price shock (add to 30d/90d % change)", -30.0, 30.0, -10.0, 1.0)
                with sc2:
                    vol_multiplier = st.slider("Volatility multiplier (30d/90d)", 0.5, 2.5, 1.25, 0.05)
                with sc3:
                    rate_shock = st.slider("10Y rate change shock (30d)", -2.0, 2.0, 0.25, 0.05)

                sim = _estimate_scenario_score_change(score_result, price_shock_pct, vol_multiplier, rate_shock)
                if sim and sim.get('new_score') is not None:
                    new_score = sim['new_score']
                    base_score = sim['base_score']
                    delta = sim['score_delta_est']
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Baseline Score", f"{base_score:.1f}")
                    with col_b:
                        st.metric("Estimated Score Change", f"{delta:+.1f}")
                    with col_c:
                        st.metric("Estimated New Score", f"{new_score:.1f}", _risk_level_from_score(new_score))
                    adj_df = pd.DataFrame(sim.get('adjustments') or [])
                    if not adj_df.empty:
                        show_cols = [c for c in ['feature', 'base', 'new', 'delta_value', 'impact', 'est_delta_impact'] if c in adj_df.columns]
                        st.dataframe(adj_df[show_cols], use_container_width=True)
                    st.caption("This is a directional estimate based on latest driver impacts; not a regulated credit rating.")
                else:
                    st.info("Not enough driver data to simulate. Try running the ticker again to store feature impacts.")

            st.subheader("Download Report")
            generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')
            report_lines = [
                f"# CredLens Report - {ticker_input}",
                "__SEPARATOR__",
                "## Company",
                f"Name: {company_name}",
                f"Generated: {generated_at}",
                "",
                "## Score Summary",
                f"Latest score: {score_result.get('stability_score', 'N/A')}",
                f"Assessment: {score_result.get('assessment_type', 'N/A')}",
                f"Risk level: {_risk_level_from_score(score_result.get('stability_score'))}",
                "",
                "## Alerts",
                f"Active alerts: {len(alerts_data) if isinstance(alerts_data, list) else 0}",
                "",
                "## What changed since last run",
            ]

            if history and isinstance(history, list) and len(history) >= 2:
                latest_item = history[0]
                prev_item = history[1]
                try:
                    report_lines.append(
                        f"Score delta: {float(latest_item.get('score')) - float(prev_item.get('score')):+.1f}"
                    )
                except Exception:
                    report_lines.append("Score delta: N/A")

                for ch in _drivers_delta(latest_item, prev_item, top_n=5):
                    report_lines.append(
                        f"- {ch['feature']}: delta_impact={ch['delta_impact']:+.2f} (prev={ch['prev_impact']:+.2f}, latest={ch['latest_impact']:+.2f})"
                    )
            else:
                report_lines.append("(Run at least twice to compute changes)")

            report_lines.append("")
            report_lines.append("__SEPARATOR__")
            report_lines.append("## Recent score history")
            if history and isinstance(history, list):
                for item in list(history)[:5]:
                    report_lines.append(
                        f"- {item.get('created_at', '')}: score={item.get('score', '')}, risk={item.get('risk_level', '')}"
                    )
            else:
                report_lines.append("(No saved history)")

            score_for_pdf = score_result.get('stability_score', 'N/A')
            risk_for_pdf = _risk_level_from_score(score_result.get('stability_score'))

            impact_rows = []
            if history and isinstance(history, list) and len(history) >= 2:
                latest_item = history[0]
                prev_item = history[1]
                for ch in _drivers_delta(latest_item, prev_item, top_n=5):
                    impact_rows.append(
                        {
                            "metric": ch.get("feature"),
                            "delta": ch.get("delta_impact"),
                            "prev": ch.get("prev_impact"),
                            "latest": ch.get("latest_impact"),
                        }
                    )

            history_rows = []
            if history and isinstance(history, list):
                for item in list(history)[:3]:
                    history_rows.append(
                        {
                            "timestamp": item.get("created_at", ""),
                            "score": item.get("score"),
                            "risk": item.get("risk_level"),
                        }
                    )

            pdf_bytes = _make_styled_report_pdf(
                ticker=ticker_input,
                company_name=company_name,
                generated_at=generated_at,
                assessment_type=str(score_result.get('assessment_type', 'N/A')),
                score=str(score_for_pdf),
                risk_level=str(risk_for_pdf),
                active_alerts=int(len(alerts_data) if isinstance(alerts_data, list) else 0),
                impact_rows=impact_rows,
                history_rows=history_rows,
            )
            st.download_button(
                label="Download PDF",
                data=pdf_bytes,
                file_name=f"{ticker_input}_report.pdf",
                mime="application/pdf",
            )

            news = api_data.get('recent_news_for_context')
            if news:
                st.subheader("Recent News Headlines")
                for article in news:
                    st.markdown(f"[{article['title']}]({article['url']})** \n*Source: {article['source']} | Published: {pd.to_datetime(article['publishedAt']).strftime('%Y-%m-%d')}*")

else:
    st.info("Enter a ticker in the sidebar and click 'Analyze' to begin.")

# ------------------------
# Custom Footer
# ------------------------
st.markdown("""
    <div style='text-align: center; color: gray; font-size: 14px; margin-top: 30px;'>
        © 2025 CredLens | Hackathon Prototype
    </div>
""", unsafe_allow_html=True)
