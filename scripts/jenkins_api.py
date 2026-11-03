"""Tiny Jenkins REST helper: trigger the pipeline, wait, save console + stage timings.
Usage: python scripts/jenkins_api.py build APPLY=false DESTROY=false
       python scripts/jenkins_api.py info <build>
Password is read from .secrets/jenkins_admin.txt and never printed."""
import json
import re
import sys
import time

import requests

BASE = "http://localhost:8081"
JOB = "jenkins-terraform-cicd"
PW = re.search(r"password: (\S+)", open(".secrets/jenkins_admin.txt").read()).group(1)

s = requests.Session()
s.auth = ("kartik", PW)
crumb = s.get(f"{BASE}/crumbIssuer/api/json").json()
s.headers[crumb["crumbRequestField"]] = crumb["crumb"]


def build(params):
    r = s.post(f"{BASE}/job/{JOB}/buildWithParameters", params=params, allow_redirects=False)
    r.raise_for_status()
    q = r.headers["Location"]
    while True:
        item = s.get(f"{q}api/json").json()
        if item.get("executable"):
            return item["executable"]["number"]
        time.sleep(2)


def wait(n):
    while True:
        b = s.get(f"{BASE}/job/{JOB}/{n}/api/json").json()
        if not b["building"] and b["result"]:
            return b["result"]
        time.sleep(5)


def info(n):
    wf = s.get(f"{BASE}/job/{JOB}/{n}/wfapi/describe").json()
    print(f"Build #{n}: {wf['status']}  total {wf['durationMillis'] / 1000:.1f}s")
    for st in wf["stages"]:
        print(f"  {st['name']:<26} {st['status']:<12} {st['durationMillis'] / 1000:7.1f}s")
    console = s.get(f"{BASE}/job/{JOB}/{n}/consoleText").text
    return wf, console


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        params = dict(a.split("=") for a in sys.argv[2:])
        n = build(params)
        print("started build", n, flush=True)
        print("result", wait(n))
    else:
        n = int(sys.argv[2])
    wf, console = info(n)
    open(f"/tmp/build_{n}_console.txt", "w").write(console)
    json.dump(wf, open(f"/tmp/build_{n}_wf.json", "w"), indent=2)
