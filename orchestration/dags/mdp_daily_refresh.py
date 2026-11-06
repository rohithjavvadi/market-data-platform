import os

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

REPO = os.path.expanduser("~/market-data-platform")
PY = os.environ.get("MDP_PY", "/opt/anaconda3/bin/python")

with DAG(
    dag_id="mdp_daily_refresh",
    description="After US close: latest Tiingo daily bars + SEC EDGAR to bronze. mdp_pipeline loads and transforms.",
    start_date=pendulum.datetime(2026, 11, 1, tz="UTC"),
    schedule="15 1 * * 2-6",
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": pendulum.duration(minutes=10),
        "execution_timeout": pendulum.duration(minutes=20),
    },
    tags=["mdp"],
) as dag:
    tiingo = BashOperator(
        task_id="tiingo_daily_bars",
        bash_command=f"cd {REPO} && {PY} backfill/tiingo_daily.py --days 7",
    )
    edgar = BashOperator(
        task_id="edgar_extract",
        bash_command=f"cd {REPO} && {PY} edgar/edgar_extract.py",
    )
