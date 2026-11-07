# Project Screenshots Checklist

The repository ships four 1920x1080 dark-mode screenshots of the 2026 glassmorphic Bento UI in `docs/images/`. They are captured headlessly from the live Streamlit app with Playwright (viewport `1920x1080`, `device_scale_factor=1`) and embedded in the main `README.md`.

## 1. Dashboard Overview — `docs/images/overview.png`
- **Capture:** The top of the live dashboard with the expanded sidebar (`LIVE - CLOUD SQL ENGINE`), the 2026 hero banner, the four Bento KPI cards (Total Revenue, Total Orders, Unique Customers, Customer Satisfaction), and the top of the Sales tab.
- **Purpose:** Hooks the viewer immediately with the polished 2026 UI and the active storage tier.

## 2. Sales Analytics — `docs/images/sales.png`
- **Capture:** The `📈 Sales` tab scrolled to **Revenue Performance**, showing the `Revenue Trend (Monthly)` spline chart and the `Top 10 States by Revenue` bar chart.
- **Purpose:** Demonstrates Plotly interactivity, temporal revenue tracking, and geographic contribution.

## 3. Customer Intelligence — `docs/images/customer.png`
- **Capture:** The `👥 Customers` tab after clicking it and waiting for both Plotly charts to render: `Top 10 Cities by Customer Count` and `Top 10 Customers by Lifetime Value`.
- **Purpose:** Demonstrates customer analytics and lifetime-value concentration.

## 4. AI Copilot Executive Summary — `docs/images/ai_insights.png`
- **Capture:** The `✨ AI Copilot` tab after clicking **Generate Executive Summary**, with the generated intelligence card visible above the `Ask Data Copilot` chat section.
- **Purpose:** Highlights the Gemini 3-layer REST integration and the polished, exportable executive narrative.

## Additional Assets
- **`docs/images/erd_placeholder.png`** — Database ERD placeholder for the 3NF schema section.
- **`docs/images/spark_placeholder.png`** — Spark execution placeholder for the distributed processing section.

## Capture Notes
- Wait for `[data-testid="stAppViewContainer"]`, the four `.bento-kpi-card` elements, and the active tab's `.js-plotly-plot` charts before taking a shot.
- Allow a two-second settle delay for fonts and chart animations.
- For a fresh capture, start the app with `python -m streamlit run app.py`, then run a Playwright script against `http://localhost:8501`.
- Playwright is a development-only tool and is intentionally **not** listed in `requirements.txt`, keeping the Streamlit Cloud dependency set lightweight.
