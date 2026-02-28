---
name: analyze_data
description: Parse, analyze, and extract insights from structured and semi-structured data (CSV, JSON, SQLite, logs)
---

# Analyze Data

Perform data analysis on files within the project — statistical summaries, anomaly detection, trend identification, and data transformation.

## When to Use

- User asks to **analyze**, **summarize**, or **extract insights** from data files
- Working with CSV, JSON, JSONL, SQLite databases, or structured logs
- Need to compute statistics, find outliers, compare datasets, or validate data quality

## Workflow

### 1. Identify the Data Source

- Use `find_by_name` to locate data files (`.csv`, `.json`, `.sqlite`, `.db`, `.log`, `.parquet`)
- Use `view_file` to inspect file structure and first few rows
- For databases, use `run_command` with `sqlite3` to inspect schema

### 2. Choose Analysis Approach

| Task                | Method                                 |
| ------------------- | -------------------------------------- |
| Quick preview       | `view_file` (first 50 lines)           |
| Row/column counts   | Python one-liner via `run_command`     |
| Statistical summary | Python script with `pandas` or stdlib  |
| SQL queries         | `sqlite3` CLI via `run_command`        |
| Pattern detection   | Python script or `grep_search` on logs |

### 3. Execute Analysis

#### CSV / JSON Analysis (Python inline)
```bash
python3 -c "
import pandas as pd
df = pd.read_csv('data.csv')
print('Shape:', df.shape)
print('\nColumn Types:')
print(df.dtypes)
print('\nSummary Statistics:')
print(df.describe())
print('\nNull Counts:')
print(df.isnull().sum())
print('\nSample Rows:')
print(df.head(10))
"
```

#### SQLite Analysis
```bash
sqlite3 database.db <<'EOF'
.tables
.schema table_name
SELECT COUNT(*) FROM table_name;
SELECT * FROM table_name LIMIT 10;
EOF
```

#### JSON Structure Inspection
```bash
python3 -c "
import json
with open('data.json') as f:
    data = json.load(f)
if isinstance(data, list):
    print(f'Array of {len(data)} items')
    print('Keys:', list(data[0].keys()) if data else 'empty')
elif isinstance(data, dict):
    print('Top-level keys:', list(data.keys()))
"
```

#### Log Analysis
```bash
# Count error frequency
grep -c 'ERROR' app.log

# Extract timestamps of errors
grep 'ERROR' app.log | head -20

# Count by error type
grep 'ERROR' app.log | awk '{print $NF}' | sort | uniq -c | sort -rn
```

### 4. Report Results

Present findings in a clear, structured format:
- **Data shape** — rows, columns, size
- **Key statistics** — mean, median, min, max, std for numeric columns
- **Data quality** — null counts, duplicate rows, type mismatches
- **Notable patterns** — trends, outliers, correlations
- **Recommendations** — data cleaning steps, further analysis suggestions

## Advanced Techniques

### Anomaly Detection
```python
# Z-score based outlier detection
from scipy import stats
z_scores = stats.zscore(df['column'])
outliers = df[abs(z_scores) > 3]
```

### Time Series Trends
```python
df['date'] = pd.to_datetime(df['date'])
df.set_index('date', inplace=True)
print(df.resample('D').mean())  # Daily averages
```

### Data Comparison
```python
df1 = pd.read_csv('before.csv')
df2 = pd.read_csv('after.csv')
diff = df1.compare(df2)
print(f"Changed rows: {len(diff)}")
```

## Error Handling

- **Missing pandas**: Fall back to `csv` stdlib module or install via `pip install pandas`
- **Large files**: Use `head`/`tail` commands first, then sample with `df.sample(1000)`
- **Encoding issues**: Try `encoding='utf-8-sig'` or `encoding='latin1'`
- **Malformed data**: Use `error_bad_lines=False` (pandas) or preprocess with `sed`/`awk`
