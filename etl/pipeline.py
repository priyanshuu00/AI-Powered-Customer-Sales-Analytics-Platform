import time
import os
import json
from .config import logger, REPORTS_DIR
from .extract import extract_data
from .validator import validate_data
from .transform import transform_data
from .load import load_data

def generate_report(stats: dict, output_path: str):
    """Generates an ETL Summary Report and saves it to a file."""
    report_lines = [
        "========================================",
        "          ETL SUMMARY REPORT            ",
        "========================================",
        f"Execution Time: {stats['execution_time']:.2f} seconds",
        "\n--- Validation Results ---"
    ]
    
    for table, v_stats in stats['validation_stats'].items():
        report_lines.append(f"\nTable: {table}")
        report_lines.append(f"  Rows Read: {v_stats['total_rows']}")
        if v_stats['missing_values']:
            report_lines.append(f"  Missing Values: {v_stats['missing_values']}")
        report_lines.append(f"  Duplicate Rows: {v_stats['duplicate_rows']}")
        
    report_lines.append("\n--- Transformation & Loading ---")
    for table, rows_loaded in stats['load_stats'].items():
        # Get original row count
        original_rows = stats['validation_stats'].get(table, {}).get('total_rows', 0)
        rows_removed = original_rows - rows_loaded
        
        report_lines.append(f"\nTable: {table}")
        report_lines.append(f"  Rows Cleaned/Loaded: {rows_loaded}")
        report_lines.append(f"  Rows Removed: {rows_removed}")
        
    report_content = "\n".join(report_lines)
    
    with open(output_path, "w") as f:
        f.write(report_content)
        
    logger.info(f"Report generated successfully at {output_path}")


def run_pipeline():
    logger.info("Starting ETL Pipeline")
    start_time = time.time()
    
    try:
        # 1. Extract
        dfs = extract_data()
        
        # 2. Validate
        validation_stats = validate_data(dfs)
        
        # 3. Transform
        dfs_cleaned = transform_data(dfs)
        
        # 4. Load
        load_stats = load_data(dfs_cleaned)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 5. Reporting
        pipeline_stats = {
            "execution_time": execution_time,
            "validation_stats": validation_stats,
            "load_stats": load_stats
        }
        
        report_path = os.path.join(REPORTS_DIR, "etl_summary_report.txt")
        generate_report(pipeline_stats, report_path)
        
        logger.info(f"ETL Pipeline completed in {execution_time:.2f} seconds.")
        
    except Exception as e:
        logger.error(f"ETL Pipeline Failed: {str(e)}", exc_info=True)


if __name__ == "__main__":
    run_pipeline()
