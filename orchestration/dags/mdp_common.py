import json
import os
import subprocess
import urllib.request
from datetime import timedelta

import pendulum
from airflow.sdk.definitions.deadline import DeadlineAlert, DeadlineReference, SyncCallback

RUN_DATE = "{{ (dag_run.logical_date or dag_run.run_after).strftime('%Y-%m-%d') }}"


ALERT_LOG = os.path.expanduser("~/market-data-platform/logs/alerts.log")


def _send(msg):
    print(msg)
    try:
        os.makedirs(os.path.dirname(ALERT_LOG), exist_ok=True)
        with open(ALERT_LOG, "a") as f:
            f.write(f"{pendulum.now('UTC').to_iso8601_string()} {msg}\n")
    except Exception as e:
        print(f"alert log write failed: {e}")
    url = os.environ.get("MDP_ALERT_WEBHOOK")
    try:
        if url:
            req = urllib.request.Request(
                url,
                data=json.dumps({"text": msg}).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
        else:
            r = subprocess.run(
                ["osascript", "-e", f'display notification {json.dumps(msg[:200])} with title "Airflow MDP"'],
                timeout=10,
                check=False,
                capture_output=True,
                text=True,
            )
            if r.returncode:
                print(f"osascript rc={r.returncode} err={r.stderr.strip()}")
    except Exception as e:
        print(f"alert delivery failed: {e}")


def notify_failure(context):
    ti = context["ti"]
    exc = str(context.get("exception"))[:300]
    _send(f"MDP FAILED {ti.dag_id}.{ti.task_id} run={context.get('run_id')} try={ti.try_number}: {exc}")


def deadline_missed(**kwargs):
    ctx = kwargs.get("context") or {}
    dr = ctx.get("dag_run") if isinstance(ctx, dict) else None
    dr = dr if isinstance(dr, dict) else {}
    _send(
        f"MDP DEADLINE MISSED {dr.get('dag_id', kwargs.get('label'))} ({kwargs.get('minutes')} min) "
        f"run={dr.get('dag_run_id')} queued_at={dr.get('queued_at')} state={dr.get('state')}"
    )


def deadline(minutes, label):
    return DeadlineAlert(
        reference=DeadlineReference.DAGRUN_QUEUED_AT,
        interval=timedelta(minutes=minutes),
        callback=SyncCallback(deadline_missed, kwargs={"label": label, "minutes": minutes}),
    )


def default_args(retries, delay_min, max_delay_min, timeout_min):
    return {
        "retries": retries,
        "retry_delay": pendulum.duration(minutes=delay_min),
        "retry_exponential_backoff": True,
        "max_retry_delay": pendulum.duration(minutes=max_delay_min),
        "execution_timeout": pendulum.duration(minutes=timeout_min),
        "on_failure_callback": notify_failure,
    }
