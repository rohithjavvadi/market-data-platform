import os

import snowflake.connector

LOADS = [
    ("RAW.MARKET.TRADES", "@RAW.MARKET.BRONZE_TRADES", ".*[.]parquet"),
    ("RAW.MARKET.DAILY_BARS", "@RAW.MARKET.BRONZE_DAILY_BARS", ".*[.]parquet"),
    ("RAW.MARKET.EDGAR_FILINGS", "@RAW.MARKET.BRONZE_EDGAR", ".*[.]json[.]gz"),
]

SQL = """
COPY INTO {table} (RECORD, FILE_NAME, FILE_ROW_NUMBER)
FROM (SELECT $1, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER FROM {stage})
PATTERN = '{pattern}'
"""

conn = snowflake.connector.connect(
    account="VZKISNL-UC48480",
    user="LOADER_SVC",
    authenticator="SNOWFLAKE_JWT",
    private_key_file=os.path.expanduser("~/.snowflake/loader_svc_key.p8"),
    role="LOADER",
    warehouse="MDP_WH",
)
try:
    cur = conn.cursor()
    for table, stage, pattern in LOADS:
        rows = cur.execute(SQL.format(table=table, stage=stage, pattern=pattern)).fetchall()
        files = sum(1 for r in rows if len(r) > 1 and r[1] == "LOADED")
        loaded_rows = sum(r[3] for r in rows if len(r) > 3 and r[1] == "LOADED")
        print(f"{table}: files_loaded={files} rows_loaded={loaded_rows}")
finally:
    conn.close()
