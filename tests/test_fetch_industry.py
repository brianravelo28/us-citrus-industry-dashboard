"""The NASS fetch against mocked QuickStats responses: the filters, the row-count funnel and the failure modes."""

import itertools
import json

import pandas as pd
import pytest

import fetch_industry_data as fid

CLASSES = ("ALL CLASSES", "VALENCIA")
UTILS = ("ALL UTILIZATION PRACTICES", "UTILIZED", "FRESH MARKET")
DOMAINS = ("TOTAL", "AREA GROWN")
PERIODS = ("YEAR", "MARKETING YEAR")
YEARS = (2025, 2026, 2027)            # 2027 is NASS's forecast for the coming season


def row(cls="ALL CLASSES", util="ALL UTILIZATION PRACTICES", domain="TOTAL", period="YEAR", year=2026, value="100", state="FL"):
    return {"class_desc": cls, "util_practice_desc": util, "domain_desc": domain, "reference_period_desc": period,
            "state_alpha": state, "year": str(year), "Value": value}


def full_grid():
    """72 rows per query: every combination of class, utilization, domain, reference period and year (2025 withheld)."""
    return [row(c, u, d, p, y, "(D)" if y == 2025 else "1,000")
            for c, u, d, p, y in itertools.product(CLASSES, UTILS, DOMAINS, PERIODS, YEARS)]


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setenv("NASS_KEY", "test-key")
    monkeypatch.setattr(fid.time, "sleep", lambda s: None)


def serve(monkeypatch, rows_for=lambda params: full_grid()):
    monkeypatch.setattr(fid, "get_json", lambda url, params, headers=None, attempts=3: {"data": rows_for(params)})


def test_the_funnel_adds_up_from_the_query_to_the_final_table(monkeypatch):
    serve(monkeypatch)
    report = {}
    df = fid.build_table(report)
    calls = len(fid.FRUITS) * len(fid.MEASURES)                       # 30 queries of 72 rows
    assert report["query_rows"] == 72 * calls
    assert report["dropped_not_all_classes"] == 36 * calls            # the VALENCIA class
    assert report["dropped_other_utilization"] == 24 * calls          # two of the three utilization practices
    assert report["dropped_domain_split"] == 6 * calls                # the domain that is not TOTAL
    assert report["dropped_other_reference_period"] == 3 * calls      # the other of YEAR / MARKETING YEAR
    assert report["dropped_after_last_season"] == 1 * calls           # the 2027 forecast
    assert report["final_rows"] == len(df) == 2 * calls               # 2025 and 2026
    assert (report["query_rows"] - report["dropped_not_all_classes"] - report["dropped_other_utilization"]
            - report["dropped_domain_split"] - report["dropped_other_reference_period"]
            - report["dropped_after_last_season"]) == report["final_rows"]
    assert len(report["series"]) == calls and {"commodity", "measure", *fid.STAGES} <= set(report["series"][0])


def test_only_the_all_classes_total_is_kept_withheld_values_stay_blank_and_forecasts_are_dropped(monkeypatch):
    serve(monkeypatch)
    df = fid.build_table()
    assert df["year"].max() == fid.END_YEAR and set(df["year"]) == {2025, 2026}
    blanks = df[df["value"].isna()]
    assert set(blanks["year"]) == {2025} and (blanks["note"] == "withheld (D)").all()          # withheld: kept, with its reason
    assert (df.loc[df["year"] == 2026, "value"] == 1000).all()                                 # "1,000" parsed
    assert (df.loc[df["year"] == 2026, "status"] == "preliminary").all() and (df.loc[df["year"] == 2025, "status"] == "reported").all()
    assert not df.duplicated(["fruit", "state", "measure", "year"]).any()


def test_the_same_responses_give_the_same_files_and_a_changed_response_gives_a_different_one(monkeypatch):
    """Backs the Methodology's determinism claim."""
    serve(monkeypatch)
    first, second = fid.build_table(), fid.build_table()
    pd.testing.assert_frame_equal(first, second)                                  # nothing random in the fetch
    def changed(params):                       # the same response with one value revised
        return [{**r, "Value": "1,001" if r["Value"] == "1,000" else r["Value"]} for r in full_grid()]
    serve(monkeypatch, changed)
    third = fid.build_table()
    assert not first.equals(third) and (third.loc[third["year"] == 2026, "value"] == 1001).all()   # a different input, a different output


def test_the_totals_fetch_reports_its_own_funnel(monkeypatch):
    serve(monkeypatch)
    report = {}
    totals = fid.build_totals(report)
    calls = len(fid.TOTALS_MEASURES)
    assert report["query_rows"] == 72 * calls and report["final_rows"] == len(totals) == 2 * calls
    assert report["dropped_after_last_season"] == calls and set(totals["measure"]) == set(fid.TOTALS_MEASURES)


def test_a_state_year_with_two_total_rows_stops_the_run(monkeypatch):
    serve(monkeypatch, lambda params: [row(), row()])
    with pytest.raises(fid.FetchError, match="more than one total row"):
        fid.build_table()
    with pytest.raises(fid.FetchError, match="more than one total row"):
        fid.build_totals()


def test_a_response_that_reports_success_and_returns_nothing_stops_the_run(monkeypatch):
    serve(monkeypatch, lambda params: [])
    with pytest.raises(fid.FetchError, match="no citrus rows"):
        fid.build_table()
    with pytest.raises(fid.FetchError, match="no rows"):
        fid.build_totals()
    serve(monkeypatch, lambda params: [row(cls="VALENCIA")])           # rows, but none is an all-classes total
    with pytest.raises(fid.FetchError, match="no citrus rows"):
        fid.build_table()


def test_an_unexpected_value_stops_the_run(monkeypatch):
    serve(monkeypatch, lambda params: [row(value="about 100")])
    with pytest.raises(fid.FetchError, match="unexpected value"):
        fid.build_table()


def test_missing_key_is_reported_without_echoing_anything(monkeypatch):
    monkeypatch.delenv("NASS_KEY")
    with pytest.raises(fid.FetchError, match="NASS_KEY is not set"):
        fid.fetch_series("ORANGES", "AREA BEARING", "ACRES", "YEAR", "ALL UTILIZATION PRACTICES")


def test_write_report_writes_both_funnels_and_the_pull_date(monkeypatch, tmp_path):
    serve(monkeypatch)
    fruit, totals = {}, {}
    fid.build_table(fruit)
    fid.build_totals(totals)
    path = tmp_path / "report.json"
    fid.write_report(fruit, totals, str(path))
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["last_season"] == fid.END_YEAR and len(doc["pulled"]) == 10
    assert doc["citrus_by_state"]["final_rows"] == fruit["final_rows"] and doc["citrus_totals"]["final_rows"] == totals["final_rows"]


# --- the committed report ------------------------------------------------------------------------------

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def test_the_committed_report_matches_the_committed_data():
    """The funnel in docs/METHODOLOGY.md comes from this file; it must describe the files in data/."""
    doc = json.loads((ROOT / "data/fetch_report.json").read_text(encoding="utf-8"))
    for key, csv in (("citrus_by_state", "citrus_by_state.csv"), ("citrus_totals", "citrus_totals_by_state.csv")):
        r = doc[key]
        assert r["final_rows"] == len(pd.read_csv(ROOT / "data" / csv))
        assert (r["query_rows"] - r["dropped_not_all_classes"] - r["dropped_other_utilization"] - r["dropped_domain_split"]
                - r["dropped_other_reference_period"] - r["dropped_after_last_season"]) == r["final_rows"]
        assert sum(s["query_rows"] for s in r["series"]) == r["query_rows"]
    from src import manifest
    assert doc["pulled"] == manifest.load(ROOT / "data/manifest.json")["data/citrus_by_state.csv"]["pulled"]
