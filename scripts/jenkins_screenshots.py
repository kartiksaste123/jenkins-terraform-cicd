"""Headless-Chrome screenshots of the Jenkins UI (logged in as kartik).
Usage: python scripts/jenkins_screenshots.py <build_number> NN_file:shot [NN_file:shot ...]
Any AWS access key id pattern on a page is masked before the screenshot."""
import os
import re
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(__file__))
from render_terminal_png import add_url_bar  # noqa: E402

BASE = "http://localhost:8081"
JOB = f"{BASE}/job/jenkins-terraform-cicd"
OUT = "evidence/screenshots"
PW = re.search(r"password: (\S+)", open(".secrets/jenkins_admin.txt").read()).group(1)
AK = open(".secrets/jcasc/aws_access_key_id").read().strip()
MASK_JS = """(ak) => { const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n; while ((n = w.nextNode())) { if (n.nodeValue.includes(ak) || /AKIA[A-Z0-9]{16}/.test(n.nodeValue))
  n.nodeValue = n.nodeValue.split(ak).join('AKIA****************').replace(/AKIA[A-Z0-9]{16}/g, 'AKIA****************'); } }"""

build = sys.argv[1]
wanted = [a.split(":") for a in sys.argv[2:]]

SHOTS = {
    "dashboard": (f"{BASE}/", None, False),
    "job_page_stage_view": (f"{JOB}/", "stage", True),
    "build_page": (f"{JOB}/{build}/", None, True),
    "pipeline_graph": (f"{JOB}/{build}/stages", "graph", False),
    "console_top": (f"{JOB}/{build}/console", "top", False),
    "console_bottom": (f"{JOB}/{build}/console", "bottom", False),
    "test_results": (f"{JOB}/{build}/testReport/", None, True),
    "artifacts": (f"{JOB}/{build}/artifact/", None, True),
    "coverage_report": (f"{JOB}/{build}/Coverage_20Report/", None, True),
    "build_parameters": (f"{JOB}/{build}/parameters/", None, False),
    "job_config_scm": (f"{JOB}/configure", "scm", False),
    "scm_polling_log": (f"{JOB}/scmPollLog/", None, False),
    "credentials": (f"{BASE}/manage/credentials/", None, False),
}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(f"{BASE}/login")
    page.fill("input[name=j_username]", "kartik")
    page.fill("input[name=j_password]", PW)
    page.press("input[name=j_password]", "Enter")
    page.wait_for_load_state("networkidle")
    for fname, name in wanted:
        url, mode, full = SHOTS[name]
        page.set_viewport_size({"width": 1920 if mode in ("stage", "graph") else 1440, "height": 900})
        page.goto(url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2500)
        if mode == "bottom":
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(800)
        elif mode == "stage":
            try:
                page.wait_for_selector(".cbwf-stage-view, #pipeline-box, table.jobsTable", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
        elif mode == "scm":
            loc = page.locator("text=Repository URL").first
            try:
                loc.scroll_into_view_if_needed(timeout=5000)
                page.evaluate("window.scrollBy(0, -250)")
            except Exception:
                pass
            page.wait_for_timeout(800)
        page.evaluate(MASK_JS, AK)
        assert AK not in page.inner_text("body")
        path = f"{OUT}/{fname}.png"
        page.screenshot(path=path, full_page=full)
        add_url_bar(path, url)
        print(path)
    b.close()
