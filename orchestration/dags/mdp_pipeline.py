import os

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

REPO = os.path.expanduser("~/market-data-platform")
PY = os.environ.get("MDP_PY", "/opt/anaconda3/bin/python")
DBT = os.environ.get("MDP_DBT", "/opt/anaconda3/bin/dbt")

with DAG(
    dag_id="mdp_pipeline",
    start_date=pendulum.datetime(2026, 11, 1, tz="UTC"),
    schedule="*/15 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": pendulum.duration(minutes=1)},
    tags=["mdp"],
) as dag:
    produce = BashOperator(
        task_id="produce_finnhub",
        bash_command=f"cd {REPO} && {PY} producer/finnhub_producer.py --seconds 120",
    )
    land_bronze = BashOperator(
        task_id="land_bronze",
        bash_command=f"cd {REPO} && {PY} consumer/bronze_writer.py --idle-exit 15",
    )
    copy_raw = BashOperator(
        task_id="copy_into_raw",
        bash_command=f"cd {REPO} && {PY} sql/run_copy.py",
    )
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {REPO}/transform && {DBT} build",
    )

    produce >> land_bronze >> copy_raw >> dbt_build
