# API & Interface Documentation

This project does not expose a public REST API over HTTP. Instead, it exposes internal module APIs for programmatic invocation of the pipeline components.

## `etl.pipeline`

```python
from etl.pipeline import ETLPipeline

pipeline = ETLPipeline()
pipeline.run_pipeline()
```
- **Description**: Triggers the end-to-end Extract, Transform, and Load process.
- **Side-effects**: Truncates and populates the `olist_analytics` MySQL database.

## `analysis.analytics_report`

```python
from analysis.analytics_report import generate_report

generate_report()
```
- **Description**: Triggers Pandas to query MySQL, compute statistical aggregates, generate matplotlib/seaborn charts to `reports/charts/`, and compile `business_analysis_report.md`.

## `spark.spark_report`

```python
from spark.spark_report import generate_report

generate_report()
```
- **Description**: Spawns a localized Apache Spark session, processes raw CSVs utilizing distributed algorithms (Broadcast Joins, Repartitioning), and outputs performance metrics.

## `ai.report_generator`

```python
from ai.report_generator import AIReportGenerator

generator = AIReportGenerator()
generator.generate_full_report(kpis, sales_data, customer_data)
```
- **Description**: Makes external HTTP calls to `generativeai.googleapis.com`. Returns generated insights and saves them to `ai_business_report.md`.
