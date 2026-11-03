"""ETL pipeline orchestration.

``run_pipeline`` returns a structured result so the same call can drive the
Streamlit Data Studio, automated checks, and the CLI. Data stages always run;
the load stage targets MySQL when it is reachable and transparently falls back
to the embedded SQLite analytics store otherwise. After a successful load the
dashboard cache is invalidated, so the top KPIs and all seven tabs reflect the
new data on the next rerun.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .config import REPORTS_DIR, logger
from .extract import extract_data
from .load import load_data
from .transform import transform_data
from .validator import validate_data

STATUS_SUCCESS = "success"
STATUS_PARTIAL = "partial"
STATUS_ERROR = "error"

ProgressCallback = Callable[[Dict[str, Any]], None]


def _invalidate_dashboard_cache() -> None:
    """Clear Streamlit's cached views after an ETL write when a runtime exists."""

    if not any(
        name == "streamlit" or name.startswith("streamlit.")
        for name in sys.modules
    ):
        return

    try:
        from dashboard.database import reset_data_source

        reset_data_source()
        logger.info("Dashboard data-source cache invalidated after ETL load.")
    except Exception as exc:  # pragma: no cover - UI guard
        logger.warning("Could not invalidate dashboard cache: %s", exc)


def generate_report(stats: Dict[str, Any], output_path: str) -> str:
    """Generate an ETL summary report and save it as UTF-8."""

    validation_stats = stats.get("validation_stats") or {}
    load_stats = stats.get("load_stats") or {}

    report_lines = [
        "========================================",
        "          ETL SUMMARY REPORT            ",
        "========================================",
        f"Status: {stats.get('status', 'unknown')}",
        f"Execution Time: {float(stats.get('execution_time', 0.0)):.2f} seconds",
        f"Rows Extracted: {int(stats.get('rows_extracted', 0)):,}",
        f"Rows Cleaned: {int(stats.get('rows_transformed', 0)):,}",
        "",
        "--- Pipeline Stages ---",
    ]

    for stage in stats.get("stages", []):
        report_lines.append(
            f"  [{str(stage.get('status', '')).upper():<8}] "
            f"{stage.get('name', 'stage')}: {stage.get('detail', '')}"
        )

    report_lines.append("\n--- Validation Results ---")
    for table, v_stats in validation_stats.items():
        report_lines.append(f"\nTable: {table}")
        report_lines.append(f"  Rows Read: {v_stats.get('total_rows', 0)}")
        missing = v_stats.get("missing_values") or {}
        if missing:
            report_lines.append(f"  Missing Values: {missing}")
        report_lines.append(
            f"  Duplicate Rows: {v_stats.get('duplicate_rows', 0)}"
        )

    if load_stats:
        target = stats.get("load_target") or "database"
        report_lines.append(f"\n--- Transformation & Loading ({target}) ---")
        if stats.get("sqlite_path"):
            report_lines.append(f"SQLite file: {stats['sqlite_path']}")
        for table, rows_loaded in load_stats.items():
            original = validation_stats.get(table, {}).get("total_rows", 0)
            report_lines.append(f"\nTable: {table}")
            report_lines.append(f"  Rows Cleaned/Loaded: {rows_loaded}")
            report_lines.append(f"  Rows Removed: {max(0, original - rows_loaded)}")

        views_written = stats.get("views_written") or {}
        if views_written:
            report_lines.append("\n--- Analytical Views ---")
            for view, rows in views_written.items():
                report_lines.append(f"  {view}: {rows} rows")
    else:
        report_lines.append(
            "\n--- Transformation & Loading ---\n"
            "Load stage skipped: this in-memory run did not request a write."
        )

    if stats.get("error"):
        report_lines.append(f"\n--- Error ---\n{stats['error']}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(report_lines))

    logger.info("Report generated successfully at %s", output_path)
    return output_path


def run_pipeline(
    raise_on_error: bool = False,
    load: bool = True,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """Run Extract -> Validate -> Transform -> Load and return structured stats.

    ``load=False`` keeps the cleaned frames in memory only, which is what the
    demo/dashboard path uses when MySQL is unavailable.
    """

    logger.info("Starting ETL Pipeline (load=%s)", load)
    started = time.time()
    stages: list[Dict[str, Any]] = []

    result: Dict[str, Any] = {
        "status": STATUS_ERROR,
        "stages": stages,
        "rows_processed": 0,
        "rows_extracted": 0,
        "rows_transformed": 0,
        "rows_loaded": 0,
        "rows_removed": 0,
        "validation_stats": {},
        "load_stats": {},
        "load_target": None,
        "views_written": {},
        "sqlite_path": None,
        "execution_time": 0.0,
        "report_path": None,
        "error": None,
    }

    def stage(
        name: str, status: str, detail: str = "", **extra: Any
    ) -> Dict[str, Any]:
        entry = {"name": name, "status": status, "detail": detail, **extra}
        stages.append(entry)
        if progress_callback is not None:
            try:
                progress_callback(entry)
            except Exception as callback_error:  # pragma: no cover - UI guard
                logger.warning("Progress callback failed: %s", callback_error)
        return entry

    def finish(status: str, error: Optional[str] = None) -> Dict[str, Any]:
        result["status"] = status
        result["error"] = error
        result["execution_time"] = round(time.time() - started, 3)
        result["rows_removed"] = max(
            0, result["rows_extracted"] - result["rows_transformed"]
        )

        report_entry = stage("Report", STATUS_SUCCESS, "Writing ETL summary report...")
        try:
            report_path = Path(REPORTS_DIR) / "etl_summary_report.txt"
            result["report_path"] = generate_report(result, str(report_path))
            report_entry["detail"] = f"Saved to {result['report_path']}"
        except OSError as report_error:  # pragma: no cover - filesystem failures
            report_entry["status"] = STATUS_ERROR
            report_entry["detail"] = f"Report could not be written: {report_error}"
            logger.error("Could not write ETL report: %s", report_error)

        if status == STATUS_ERROR:
            logger.error("ETL Pipeline failed: %s", error)
            if raise_on_error:
                raise RuntimeError(error or "ETL pipeline failed")
        else:
            logger.info(
                "ETL Pipeline completed with status %s in %.2fs.",
                status,
                result["execution_time"],
            )
        return result

    # 1. Extract -----------------------------------------------------------
    try:
        dfs = extract_data()
        if not dfs:
            raise RuntimeError(
                "No dataset CSV files could be extracted. Seed sample data or "
                "place the Olist CSVs in data/raw/."
            )
        result["rows_extracted"] = int(sum(len(frame) for frame in dfs.values()))
        result["rows_processed"] = result["rows_extracted"]
        stage(
            "Extract",
            STATUS_SUCCESS,
            f"{len(dfs)} datasets · {result['rows_extracted']:,} rows",
            rows=result["rows_extracted"],
        )
    except Exception as extract_error:
        stage("Extract", STATUS_ERROR, str(extract_error))
        return finish(STATUS_ERROR, f"Extract stage failed: {extract_error}")

    # 2. Validate ----------------------------------------------------------
    try:
        validation_stats = validate_data(dfs)
        result["validation_stats"] = validation_stats
        duplicate_rows = int(
            sum(
                int(stats.get("duplicate_rows") or 0)
                for stats in validation_stats.values()
            )
        )
        missing_cells = int(
            sum(
                sum((stats.get("missing_values") or {}).values())
                for stats in validation_stats.values()
            )
        )
        stage(
            "Validate",
            STATUS_SUCCESS,
            (
                f"{len(validation_stats)} tables · {duplicate_rows:,} duplicates · "
                f"{missing_cells:,} missing cells"
            ),
            duplicates=duplicate_rows,
            missing_cells=missing_cells,
        )
    except Exception as validate_error:
        stage("Validate", STATUS_ERROR, str(validate_error))
        return finish(STATUS_ERROR, f"Validate stage failed: {validate_error}")

    # 3. Transform ---------------------------------------------------------
    try:
        dfs_cleaned = transform_data(dfs)
        result["rows_transformed"] = int(
            sum(len(frame) for frame in dfs_cleaned.values())
        )
        result["rows_processed"] = result["rows_transformed"]
        stage(
            "Transform",
            STATUS_SUCCESS,
            (
                f"{result['rows_transformed']:,} rows kept · "
                f"{max(0, result['rows_extracted'] - result['rows_transformed']):,} removed"
            ),
            rows=result["rows_transformed"],
        )
    except Exception as transform_error:
        stage("Transform", STATUS_ERROR, str(transform_error))
        return finish(STATUS_ERROR, f"Transform stage failed: {transform_error}")

    # 4. Load --------------------------------------------------------------
    load_error: Optional[str] = None
    if load:
        try:
            load_result = load_data(dfs_cleaned)
            load_stats = load_result.get("tables") or {}
            views_written = load_result.get("views") or {}

            result["load_stats"] = load_stats
            result["load_target"] = load_result.get("target")
            result["views_written"] = views_written
            result["sqlite_path"] = load_result.get("path")
            result["rows_loaded"] = int(
                sum(int(rows) for rows in load_stats.values())
            )

            target = result["load_target"] or "database"
            target_label = (
                "MySQL"
                if target == "mysql"
                else f"embedded SQLite ({result['sqlite_path']})"
            )
            detail = f"{result['rows_loaded']:,} rows written to {target_label}"
            if views_written:
                detail += f" · {len(views_written)} analytical views"

            stage(
                "Load",
                STATUS_SUCCESS,
                detail,
                rows=result["rows_loaded"],
                target=target,
                views=len(views_written),
            )
            _invalidate_dashboard_cache()
        except Exception as load_exc:
            load_error = f"Load stage failed: {type(load_exc).__name__}: {load_exc}"
            stage("Load", STATUS_ERROR, load_error)
    else:
        stage(
            "Load",
            "skipped",
            "Load disabled — cleaned frames kept in memory for this run",
        )

    # 5. Report ------------------------------------------------------------
    status = STATUS_PARTIAL if load_error else STATUS_SUCCESS
    return finish(status, load_error)


def main() -> int:
    """CLI entry point: print a JSON summary and exit non-zero on failure."""

    result = run_pipeline(raise_on_error=False)
    summary = {key: value for key, value in result.items() if key != "stages"}
    print(json.dumps(summary, indent=2, default=str))
    print("\nStages:")
    for entry in result["stages"]:
        print(f"  [{entry['status']}] {entry['name']}: {entry['detail']}")

    return 0 if result["status"] != STATUS_ERROR else 1


if __name__ == "__main__":
    sys.exit(main())
