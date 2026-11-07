import json
import os
import subprocess
import urllib.request

import pendulum

RUN_DATE = "{{ (dag_run.logical_date or dag_run.run_after).strftime('%Y-%m-%d') }}"


def notify_failure(context):
    ti = context["ti"]
    exc = str(context.get("exception"))[:300]
    msg = f"MDP FAILED {ti.dag_id}.{ti.task_id} run={context.get('run_id')} try={ti.try_number}: {exc}"
    print(msg)
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
            subprocess.run(
                ["osascript", "-e", f'display notification {json.dumps(msg[:200])} with title "Airflow MDP"'],
                timeout=10,
                check=False,
            )
    except Exception as e:
        print(f"alert delivery failed: {e}")


def default_args(retries, delay_min, max_delay_min, timeout_min):
    return {
        "retries": retries,
        "retry_delay": pendulum.duration(minutes=delay_min),
        "retry_exponential_backoff": True,
        "max_retry_delay": pendulum.duration(minutes=max_delay_min),
        "execution_timeout": pendulum.duration(minutes=timeout_min),
        "on_failure_callback": notify_failure,
    }
