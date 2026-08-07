# User Guide

## 1. Prerequisites
Ensure you have the following installed:
- Python 3.9+
- MySQL Server 8.0+
- Java (Required for Apache Spark)

## 2. Configuration
Create a `.env` file in the root of the project:
```env
DB_USER=root
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=3306
DB_NAME=olist_analytics
GEMINI_API_KEY=your_google_gemini_key
```

## 3. Database Initialization
Before running the ETL, you must create the database schema:
1. Open MySQL Workbench.
2. Run the scripts found in `database/schema.sql` and `database/indexes.sql`.
3. Finally, run `database/views.sql` to establish the dashboard reporting views.

## 4. Pipeline Execution
To ingest the raw data into MySQL:
```bash
python -m etl.pipeline
```
*Note: This may take a few minutes depending on hardware, as millions of rows are validated and inserted.*

## 5. Launching the BI Dashboard
Once data is loaded, you can launch the interactive Streamlit application:
```bash
streamlit run dashboard/app.py
```
This will open a local web server (typically `http://localhost:8501`) where you can interactively filter and drill down into the business metrics.

## 6. Requesting AI Insights
To generate an automated text report using the Gemini LLM:
```bash
python -m ai.report_generator
```
Check the `reports/` folder for the newly generated `.md` files.
