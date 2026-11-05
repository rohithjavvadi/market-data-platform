import os
import snowflake.connector

conn = snowflake.connector.connect(
    account="VZKISNL-UC48480",
    user="LOADER_SVC",
    authenticator="SNOWFLAKE_JWT",
    private_key_file=os.path.expanduser("~/.snowflake/loader_svc_key.p8"),
    role="LOADER",
    warehouse="MDP_WH",
)
sql = """
COPY INTO RAW.MARKET.TRADES (RECORD, FILE_NAME, FILE_ROW_NUMBER)
FROM (SELECT $1, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER FROM @RAW.MARKET.BRONZE_TRADES)
PATTERN = '.*[.]json[.]gz'
"""
try:
    rows = conn.cursor().execute(sql).fetchall()
    loaded = sum(1 for r in rows if len(r) > 1 and r[1] == "LOADED")
    print(f"copy: files_loaded={loaded} results={len(rows)}")
    for r in rows:
        print(r)
finally:
    conn.close()
