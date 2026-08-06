"""
Agent 14 — SECFilingsAgent
Extracts key financial metrics from income statement, cash flow statement,
and balance sheet.

Data source notes:
- Live path: yfinance `financials`, `cashflow`, and `balance_sheet` DataFrames.
  yfinance aggregates data from Yahoo Finance / Macrotrends, which in turn
  sources from SEC EDGAR filings — this is NOT a direct EDGAR XBRL parser.
  Latency and coverage differ from the EDGAR full-text API. If asked about
  EDGAR XBRL parsing or EDGAR rate limits, this agent does not demonstrate that.
- Demo path: hardcoded FY2020-FY2023 actuals for the 8 demo tickers
  (XOM, CVX, FCX, JPM, ABBV, MPC, MSFT, KO). These are approximate figures
  sourced from public filings at development time, not retrieved at runtime.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from apm.core.agent import Agent, AgentOutput, AnnualFinancials, Context, SECFilingsData

log = logging.getLogger(__name__)

# Amounts in USD millions — approximate FY2023/FY2024 actuals
_DEMO: dict[str, dict[str, Any]] = {
    "XOM": {
        "annual": [
            {"year": 2023, "revenue": 398_675, "gross_profit": 88_050, "operating_income": 51_810,
             "net_income": 36_010, "operating_cf": 55_370, "capex": 26_310, "fcf": 29_060,
             "eps_basic": 8.89, "gross_margin": 0.221, "operating_margin": 0.130, "net_margin": 0.090},
            {"year": 2022, "revenue": 398_675, "gross_profit": 97_800, "operating_income": 73_600,
             "net_income": 55_740, "operating_cf": 76_800, "capex": 21_300, "fcf": 55_500,
             "eps_basic": 14.11, "gross_margin": 0.245, "operating_margin": 0.185, "net_margin": 0.140},
            {"year": 2021, "revenue": 276_692, "gross_profit": 54_200, "operating_income": 33_100,
             "net_income": 23_040, "operating_cf": 48_100, "capex": 15_700, "fcf": 32_400,
             "eps_basic": 5.39, "gross_margin": 0.196, "operating_margin": 0.120, "net_margin": 0.083},
            {"year": 2020, "revenue": 177_290, "gross_profit": 16_100, "operating_income": -5_700,
             "net_income": -22_440, "operating_cf": 14_600, "capex": 21_400, "fcf": -6_800,
             "eps_basic": -5.23, "gross_margin": 0.091, "operating_margin": -0.032, "net_margin": -0.127},
        ],
        "revenue_cagr_3yr_pct": 12.1, "fcf_yield_pct": 5.8, "debt_to_equity": 0.15,
        "current_ratio": 1.38, "roe_pct": 18.2,
        "latest_10k_period": "FY2023", "latest_10q_period": "Q3 2024",
    },
    "CVX": {
        "annual": [
            {"year": 2023, "revenue": 196_913, "gross_profit": 37_210, "operating_income": 30_110,
             "net_income": 21_369, "operating_cf": 33_830, "capex": 16_460, "fcf": 17_370,
             "eps_basic": 11.24, "gross_margin": 0.189, "operating_margin": 0.153, "net_margin": 0.109},
            {"year": 2022, "revenue": 235_717, "gross_profit": 50_100, "operating_income": 44_600,
             "net_income": 35_465, "operating_cf": 49_600, "capex": 14_800, "fcf": 34_800,
             "eps_basic": 18.28, "gross_margin": 0.213, "operating_margin": 0.189, "net_margin": 0.150},
            {"year": 2021, "revenue": 155_607, "gross_profit": 27_100, "operating_income": 20_700,
             "net_income": 15_625, "operating_cf": 29_200, "capex": 11_700, "fcf": 17_500,
             "eps_basic": 8.14, "gross_margin": 0.174, "operating_margin": 0.133, "net_margin": 0.100},
            {"year": 2020, "revenue": 94_471,  "gross_profit": 6_800,  "operating_income": -4_900,
             "net_income": -5_543, "operating_cf": 10_600, "capex": 13_500, "fcf": -2_900,
             "eps_basic": -2.96, "gross_margin": 0.072, "operating_margin": -0.052, "net_margin": -0.059},
        ],
        "revenue_cagr_3yr_pct": 9.7, "fcf_yield_pct": 6.2, "debt_to_equity": 0.13,
        "current_ratio": 1.31, "roe_pct": 15.8,
        "latest_10k_period": "FY2023", "latest_10q_period": "Q3 2024",
    },
    "FCX": {
        "annual": [
            {"year": 2023, "revenue": 22_855, "gross_profit": 7_310, "operating_income": 4_180,
             "net_income": 1_854, "operating_cf": 5_200, "capex": 3_110, "fcf": 2_090,
             "eps_basic": 1.26, "gross_margin": 0.320, "operating_margin": 0.183, "net_margin": 0.081},
            {"year": 2022, "revenue": 22_789, "gross_profit": 8_240, "operating_income": 5_630,
             "net_income": 3_017, "operating_cf": 6_700, "capex": 3_900, "fcf": 2_800,
             "eps_basic": 2.07, "gross_margin": 0.362, "operating_margin": 0.247, "net_margin": 0.132},
            {"year": 2021, "revenue": 22_945, "gross_profit": 9_410, "operating_income": 6_690,
             "net_income": 4_282, "operating_cf": 6_600, "capex": 2_700, "fcf": 3_900,
             "eps_basic": 2.86, "gross_margin": 0.410, "operating_margin": 0.292, "net_margin": 0.187},
            {"year": 2020, "revenue": 14_196, "gross_profit": 4_200, "operating_income": 2_100,
             "net_income": 583,  "operating_cf": 3_200, "capex": 1_700, "fcf": 1_500,
             "eps_basic": 0.39, "gross_margin": 0.296, "operating_margin": 0.148, "net_margin": 0.041},
        ],
        "revenue_cagr_3yr_pct": 17.2, "fcf_yield_pct": 2.9, "debt_to_equity": 0.55,
        "current_ratio": 2.14, "roe_pct": 22.5,
        "latest_10k_period": "FY2023", "latest_10q_period": "Q3 2024",
    },
    "JPM": {
        "annual": [
            {"year": 2023, "revenue": 158_102, "gross_profit": None, "operating_income": 49_600,
             "net_income": 49_552, "operating_cf": 62_100, "capex": 3_800, "fcf": 58_300,
             "eps_basic": 16.23, "gross_margin": None, "operating_margin": 0.314, "net_margin": 0.314},
            {"year": 2022, "revenue": 128_695, "gross_profit": None, "operating_income": 37_500,
             "net_income": 37_676, "operating_cf": 45_200, "capex": 3_300, "fcf": 41_900,
             "eps_basic": 12.09, "gross_margin": None, "operating_margin": 0.293, "net_margin": 0.293},
            {"year": 2021, "revenue": 121_649, "gross_profit": None, "operating_income": 48_300,
             "net_income": 48_334, "operating_cf": 55_600, "capex": 2_800, "fcf": 52_800,
             "eps_basic": 15.36, "gross_margin": None, "operating_margin": 0.397, "net_margin": 0.397},
            {"year": 2020, "revenue": 119_543, "gross_profit": None, "operating_income": 25_800,
             "net_income": 29_131, "operating_cf": 34_500, "capex": 2_700, "fcf": 31_800,
             "eps_basic": 8.88, "gross_margin": None, "operating_margin": 0.216, "net_margin": 0.244},
        ],
        "revenue_cagr_3yr_pct": 9.8, "fcf_yield_pct": 12.4, "debt_to_equity": 1.41,
        "current_ratio": None, "roe_pct": 17.3,
        "latest_10k_period": "FY2023", "latest_10q_period": "Q3 2024",
    },
    "ABBV": {
        "annual": [
            {"year": 2023, "revenue": 54_318, "gross_profit": 38_520, "operating_income": 14_800,
             "net_income": 4_863, "operating_cf": 16_840, "capex": 848, "fcf": 15_992,
             "eps_basic": 2.79, "gross_margin": 0.709, "operating_margin": 0.272, "net_margin": 0.090},
            {"year": 2022, "revenue": 58_054, "gross_profit": 42_100, "operating_income": 20_400,
             "net_income": 11_836, "operating_cf": 22_300, "capex": 990, "fcf": 21_310,
             "eps_basic": 6.69, "gross_margin": 0.725, "operating_margin": 0.351, "net_margin": 0.204},
            {"year": 2021, "revenue": 56_197, "gross_profit": 39_800, "operating_income": 18_700,
             "net_income": 11_542, "operating_cf": 20_200, "capex": 791, "fcf": 19_409,
             "eps_basic": 6.45, "gross_margin": 0.708, "operating_margin": 0.333, "net_margin": 0.205},
            {"year": 2020, "revenue": 45_804, "gross_profit": 32_100, "operating_income": 14_900,
             "net_income": 4_616, "operating_cf": 18_700, "capex": 669, "fcf": 18_031,
             "eps_basic": 2.72, "gross_margin": 0.701, "operating_margin": 0.325, "net_margin": 0.101},
        ],
        "revenue_cagr_3yr_pct": 5.8, "fcf_yield_pct": 10.2, "debt_to_equity": 2.52,
        "current_ratio": 1.11, "roe_pct": 51.6,
        "latest_10k_period": "FY2023", "latest_10q_period": "Q3 2024",
    },
    "MPC": {
        "annual": [
            {"year": 2023, "revenue": 149_062, "gross_profit": 12_410, "operating_income": 12_100,
             "net_income": 10_224, "operating_cf": 13_530, "capex": 1_920, "fcf": 11_610,
             "eps_basic": 27.00, "gross_margin": 0.083, "operating_margin": 0.081, "net_margin": 0.069},
            {"year": 2022, "revenue": 179_581, "gross_profit": 19_300, "operating_income": 18_900,
             "net_income": 14_516, "operating_cf": 17_200, "capex": 2_100, "fcf": 15_100,
             "eps_basic": 33.92, "gross_margin": 0.107, "operating_margin": 0.105, "net_margin": 0.081},
            {"year": 2021, "revenue": 119_982, "gross_profit": 8_700, "operating_income": 7_300,
             "net_income": 9_738, "operating_cf": 10_100, "capex": 1_700, "fcf": 8_400,
             "eps_basic": 16.86, "gross_margin": 0.073, "operating_margin": 0.061, "net_margin": 0.081},
            {"year": 2020, "revenue": 68_867,  "gross_profit": 1_200, "operating_income": -1_800,
             "net_income": -9_826, "operating_cf": 1_500, "capex": 2_500, "fcf": -1_000,
             "eps_basic": -15.54, "gross_margin": 0.017, "operating_margin": -0.026, "net_margin": -0.143},
        ],
        "revenue_cagr_3yr_pct": 18.8, "fcf_yield_pct": 9.4, "debt_to_equity": 0.52,
        "current_ratio": 1.52, "roe_pct": 42.8,
        "latest_10k_period": "FY2023", "latest_10q_period": "Q3 2024",
    },
    "MSFT": {
        "annual": [
            {"year": 2024, "revenue": 245_122, "gross_profit": 171_008, "operating_income": 109_433,
             "net_income": 88_136, "operating_cf": 118_548, "capex": 55_719, "fcf": 74_071,
             "eps_basic": 11.80, "gross_margin": 0.698, "operating_margin": 0.447, "net_margin": 0.360},
            {"year": 2023, "revenue": 211_915, "gross_profit": 146_052, "operating_income": 88_523,
             "net_income": 72_361, "operating_cf": 87_582, "capex": 28_107, "fcf": 59_475,
             "eps_basic": 9.65, "gross_margin": 0.689, "operating_margin": 0.418, "net_margin": 0.341},
            {"year": 2022, "revenue": 198_270, "gross_profit": 135_620, "operating_income": 83_383,
             "net_income": 72_738, "operating_cf": 89_035, "capex": 23_886, "fcf": 65_149,
             "eps_basic": 9.65, "gross_margin": 0.684, "operating_margin": 0.421, "net_margin": 0.367},
            {"year": 2021, "revenue": 168_088, "gross_profit": 115_856, "operating_income": 69_916,
             "net_income": 61_271, "operating_cf": 76_740, "capex": 20_622, "fcf": 56_118,
             "eps_basic": 8.05, "gross_margin": 0.689, "operating_margin": 0.416, "net_margin": 0.365},
        ],
        "revenue_cagr_3yr_pct": 13.4, "fcf_yield_pct": 1.9, "debt_to_equity": 0.35,
        "current_ratio": 1.78, "roe_pct": 37.2,
        "latest_10k_period": "FY2024", "latest_10q_period": "Q1 FY2025",
    },
    "KO": {
        "annual": [
            {"year": 2023, "revenue": 45_754, "gross_profit": 26_904, "operating_income": 11_311,
             "net_income": 10_714, "operating_cf": 11_599, "capex": 2_054, "fcf": 9_545,
             "eps_basic": 2.47, "gross_margin": 0.588, "operating_margin": 0.247, "net_margin": 0.234},
            {"year": 2022, "revenue": 43_004, "gross_profit": 25_004, "operating_income": 10_909,
             "net_income": 9_542, "operating_cf": 10_908, "capex": 1_484, "fcf": 9_424,
             "eps_basic": 2.19, "gross_margin": 0.581, "operating_margin": 0.254, "net_margin": 0.222},
            {"year": 2021, "revenue": 38_655, "gross_profit": 22_622, "operating_income": 10_308,
             "net_income": 9_771, "operating_cf": 10_209, "capex": 1_367, "fcf": 8_842,
             "eps_basic": 2.25, "gross_margin": 0.585, "operating_margin": 0.267, "net_margin": 0.253},
            {"year": 2020, "revenue": 33_014, "gross_profit": 19_252, "operating_income": 8_997,
             "net_income": 8_985, "operating_cf": 9_844, "capex": 1_177, "fcf": 8_667,
             "eps_basic": 2.07, "gross_margin": 0.583, "operating_margin": 0.273, "net_margin": 0.272},
        ],
        "revenue_cagr_3yr_pct": 11.5, "fcf_yield_pct": 3.5, "debt_to_equity": 1.78,
        "current_ratio": 1.02, "roe_pct": 40.8,
        "latest_10k_period": "FY2023", "latest_10q_period": "Q3 2024",
    },
}


class SECFilingsAgent(Agent):
    name = "sec_filings"

    def run(self, context: Context) -> AgentOutput:
        tickers = self._tickers(context)
        results: dict[str, SECFilingsData] = {}

        if context.demo_mode:
            for t in tickers:
                raw = _DEMO.get(t)
                if raw:
                    results[t] = self._from_raw(t, raw)
        else:
            for t in tickers:
                try:
                    results[t] = self._fetch_live(t)
                except Exception as exc:
                    log.warning("SEC filing fetch failed for %s: %s — using demo", t, exc)
                    raw = _DEMO.get(t)
                    if raw:
                        results[t] = self._from_raw(t, raw)

        context.sec_filings = results

        avg_fcf_yield = (
            sum(d.fcf_yield_pct for d in results.values() if d.fcf_yield_pct is not None) /
            max(1, sum(1 for d in results.values() if d.fcf_yield_pct is not None))
        )
        rationale = (
            f"Analysed {len(results)} tickers | "
            f"Avg FCF yield: {avg_fcf_yield:.1f}% | "
            + " | ".join(
                f"{t}: rev ${d.annual[0].revenue/1000:.0f}B, op_margin {d.annual[0].operating_margin*100:.0f}%"
                for t, d in list(results.items())[:3]
                if d.annual and d.annual[0].operating_margin is not None
            )
        )

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=78.0,
            confidence_label=self._confidence_label(78.0),
            rationale=rationale,
            data={k: v.model_dump() for k, v in results.items()},
            warnings=[],
            provenance={"source": "yfinance income_stmt / cashflow / balance_sheet" if not context.demo_mode else "demo pre-seeded FY2023/2024 actuals"},
        )

    def _tickers(self, context: Context) -> list[str]:
        if context.recommendations:
            return [r.ticker for r in context.recommendations.ranked]
        if context.fundamentals:
            return list(context.fundamentals.keys())
        return list(_DEMO.keys())

    def _fetch_live(self, ticker: str) -> SECFilingsData:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info or {}

        income = t.financials          # columns = dates, rows = items
        cf = t.cashflow
        bs = t.balance_sheet

        def _get(df, key, col_idx=0):
            if df is None or df.empty:
                return None
            for row_key in df.index:
                if key.lower() in row_key.lower():
                    try:
                        val = df.iloc[df.index.tolist().index(row_key), col_idx]
                        return float(val) / 1e6 if val and val == val else None  # convert to millions
                    except Exception:
                        return None
            return None

        annual: list[AnnualFinancials] = []
        if income is not None and not income.empty:
            for i, col in enumerate(income.columns[:4]):
                yr = col.year if hasattr(col, "year") else int(str(col)[:4])
                rev    = _get(income, "Total Revenue", i)
                gp     = _get(income, "Gross Profit", i)
                oi     = _get(income, "Operating Income", i)
                ni     = _get(income, "Net Income", i)
                ocf    = _get(cf, "Operating Cash Flow", i) or _get(cf, "Total Cash From Operating", i)
                capex_ = _get(cf, "Capital Expenditure", i) or _get(cf, "Purchases Of", i)
                if capex_ and capex_ > 0:
                    capex_ = -capex_  # yfinance sometimes returns positive
                fcf_   = (ocf + capex_) if ocf and capex_ else None
                eps    = _get(income, "Basic EPS", i)
                gm = gp / rev if gp and rev and rev > 0 else None
                om = oi / rev if oi and rev and rev > 0 else None
                nm = ni / rev if ni and rev and rev > 0 else None
                annual.append(AnnualFinancials(
                    year=yr, revenue=rev, gross_profit=gp, operating_income=oi,
                    net_income=ni, operating_cf=ocf, capex=capex_, free_cash_flow=fcf_,
                    eps_basic=eps, gross_margin=gm, operating_margin=om, net_margin=nm,
                ))

        # 3-yr revenue CAGR
        cagr = None
        if len(annual) >= 4 and annual[0].revenue and annual[3].revenue and annual[3].revenue > 0:
            cagr = round(((annual[0].revenue / annual[3].revenue) ** (1 / 3) - 1) * 100, 1)

        return SECFilingsData(
            ticker=ticker,
            annual=annual,
            revenue_cagr_3yr_pct=cagr,
            fcf_yield_pct=round(info.get("freeCashflow", 0) / info.get("marketCap", 1) * 100, 1) if info.get("marketCap") else None,
            debt_to_equity=round(info.get("debtToEquity", 0) / 100, 2) if info.get("debtToEquity") else None,
            current_ratio=info.get("currentRatio"),
            return_on_equity_pct=round(info.get("returnOnEquity", 0) * 100, 1) if info.get("returnOnEquity") else None,
            latest_10k_period=f"FY{annual[0].year}" if annual else None,
            latest_10q_period=None,
        )

    def _from_raw(self, ticker: str, raw: dict) -> SECFilingsData:
        annual = [
            AnnualFinancials(
                year=a["year"],
                revenue=a.get("revenue"),
                gross_profit=a.get("gross_profit"),
                operating_income=a.get("operating_income"),
                net_income=a.get("net_income"),
                operating_cf=a.get("operating_cf"),
                capex=a.get("capex"),
                free_cash_flow=a.get("fcf"),
                eps_basic=a.get("eps_basic"),
                gross_margin=a.get("gross_margin"),
                operating_margin=a.get("operating_margin"),
                net_margin=a.get("net_margin"),
            )
            for a in raw.get("annual", [])
        ]
        return SECFilingsData(
            ticker=ticker,
            annual=annual,
            revenue_cagr_3yr_pct=raw.get("revenue_cagr_3yr_pct"),
            fcf_yield_pct=raw.get("fcf_yield_pct"),
            debt_to_equity=raw.get("debt_to_equity"),
            current_ratio=raw.get("current_ratio"),
            return_on_equity_pct=raw.get("roe_pct"),
            latest_10k_period=raw.get("latest_10k_period"),
            latest_10q_period=raw.get("latest_10q_period"),
        )
