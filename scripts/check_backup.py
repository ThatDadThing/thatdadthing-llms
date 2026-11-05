"""Decide whether today's scheduled backup should build a discovery feed."""
import datetime as dt
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
OVERNIGHT_TITLE = "Discovery refresh (3 a.m. Eastern)"


def overnight_succeeded(runs, day, verified):
    return any(
        run["event"] == "schedule"
        and run["head_branch"] == "main"
        and run["display_title"] == OVERNIGHT_TITLE
        and run["status"] == "completed"
        and run["conclusion"] == "success"
        and dt.datetime.fromisoformat(run["created_at"]).astimezone(EASTERN).date() == day
        and verified(run["id"])
        for run in runs
    )


def main():
    # Anchor the decision to the backup run's creation day, not runner queue time.
    base = f'{os.environ["GITHUB_API_URL"]}/repos/{os.environ["GITHUB_REPOSITORY"]}/actions'
    headers = {"Authorization": f'Bearer {os.environ["GH_TOKEN"]}',
               "Accept": "application/vnd.github+json"}

    def get(path):
        with urlopen(Request(base + path, headers=headers), timeout=30) as response:
            return json.load(response)

    current = get(f'/runs/{os.environ["GITHUB_RUN_ID"]}')
    day = dt.datetime.fromisoformat(current["created_at"]).astimezone(EASTERN).date()
    start = dt.datetime.combine(day, dt.time(), EASTERN).astimezone(dt.timezone.utc)
    query = urlencode({"branch": "main", "event": "schedule", "status": "success",
                       "created": ">=" + start.isoformat(), "per_page": 100})
    history = get("/workflows/publish.yml/runs?" + query)
    if history["total_count"] > len(history["workflow_runs"]):
        raise RuntimeError("Incomplete refresh history")
    def verified(run_id):
        jobs = get(f"/runs/{run_id}/jobs?per_page=100")
        return any(job["name"] == "verify" and job["conclusion"] == "success"
                   for job in jobs["jobs"])

    succeeded = overnight_succeeded(history["workflow_runs"], day, verified)
    backup = not succeeded and current["run_attempt"] == 1
    print(f"Overnight success for {day}: {succeeded}. Run backup: {backup}.")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        print(f"proceed={str(backup).lower()}", file=output)


if __name__ == "__main__":
    main()

