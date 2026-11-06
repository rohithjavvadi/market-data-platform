import os

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

REPO = os.path.expanduser("~/market-data-platform")
PY = os.environ.get("MDP_PY", "/opt/anaconda3/bin/python")
DBT = os.environ.get("MDP_DBT", "/opt/anaconda3/bin/dbt")
JAVA_HOME = os.environ.get(
    "JAVA_HOME", "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
)
SPARK_ENV = f"export JAVA_HOME={JAVA_HOME} && cd {REPO}"
UTC_END = "$(date -u +%F)"

with DAG(
    dag_id="mdp_pipeline",
    start_date=pendulum.datetime(2026, 11, 1, tz="UTC"),
    schedule="*/15 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 1,
        "retry_delay": pendulum.duration(minutes=1),
        "execution_timeout": pendulum.duration(minutes=12),
    },
    tags=["mdp"],
) as dag:
    copy_raw = BashOperator(
        task_id="copy_into_raw",
        bash_command=f"cd {REPO} && {PY} sql/run_copy.py",
    )
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {REPO}/transform && {DBT} build",
    )
    spark_silver = BashOperator(
        task_id="spark_bronze_to_silver",
        bash_command=f"{SPARK_ENV} && {PY} spark/bronze_to_silver_trades.py --end {UTC_END} --days 2",
    )
    spark_bars = BashOperator(
        task_id="spark_silver_to_bars_1m",
        bash_command=f"{SPARK_ENV} && {PY} spark/silver_to_bars_1m.py --end {UTC_END} --days 2",
    )

    parity = BashOperator(
        task_id="bars_parity_check",
        bash_command=f"{SPARK_ENV} && {PY} spark/check_bars_parity.py --date {UTC_END}",
    )

    copy_raw >> dbt_build
    spark_silver >> spark_bars
    [dbt_build, spark_bars] >> parity
