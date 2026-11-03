"""Cut readable per-stage excerpts out of the saved Jenkins console logs
(evidence/logs/jenkins_console/build_N_console.txt) for terminal-style PNGs.
UTC timestamps are converted to IST; Jenkins '[Pipeline]' bookkeeping lines are dropped."""
import re
from datetime import datetime, timedelta

TS = re.compile(r"^\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\.\d+Z\] ")
IST = timedelta(hours=5, minutes=30)


def stages(n):
    out, cur = {}, None
    for line in open(f"evidence/logs/jenkins_console/build_{n}_console.txt", encoding="utf-8"):
        m = re.match(r"^\[Pipeline\] \{ \((.+)\)$", line.rstrip())
        if m:
            cur = m.group(1)
            out.setdefault(cur, [])
            continue
        if cur is None or line.startswith("[Pipeline]"):
            continue
        t = TS.match(line)
        if t:
            ist = (datetime.fromisoformat(t.group(1)) + IST).strftime("%H:%M:%S")
            line = f"[{ist} IST] " + line[t.end():]
        out[cur].append(line.rstrip("\n"))
    return out


def excerpt(name, n, wanted, title, max_per_stage=None, grep=None):
    st = stages(n)
    lines = [f"# {title}", f"# Source: http://localhost:8081/job/jenkins-terraform-cicd/{n}/console", ""]
    for s in wanted:
        body = st.get(s, [])
        if grep and s in grep:
            body = [b for b in body if re.search(grep[s], b)]
        if max_per_stage and len(body) > max_per_stage:
            body = body[:max_per_stage] + [f"   ... ({len(body) - max_per_stage} more lines in the full console log)"]
        lines += [f"===== Stage: {s} =====", *body, ""]
    open(f"evidence/logs/{name}.txt", "w").write("\n".join(lines) + "\n")
    print(name, len(lines))


excerpt("21_jenkins_build3_checkout_venv_lint", 3, ["Checkout", "Setup Python venv", "Lint (flake8)"],
        "Jenkins build #3 (started by an SCM change) - GitHub checkout, Python venv, flake8")
excerpt("22_jenkins_build3_unit_tests", 3, ["Unit Tests (pytest)"],
        "Jenkins build #3 - pytest with JUnit XML + coverage")
excerpt("23_jenkins_build3_docker_build_smoke_test", 3, ["Build Docker Image", "Smoke Test Container"],
        "Jenkins build #3 - Docker image build (tagged with BUILD_NUMBER) and container smoke test", max_per_stage=40)
excerpt("24_jenkins_build3_terraform_init_fmt_validate", 3,
        ["Terraform Init", "Terraform Fmt Check", "Terraform Validate"],
        "Jenkins build #3 - terraform init / fmt -check / validate")
excerpt("25_jenkins_build3_terraform_plan", 3, ["Terraform Plan"],
        "Jenkins build #3 - terraform plan -out=tfplan (credentials from Jenkins credential 'aws-terraform-ci')")
excerpt("26_jenkins_build4_lint_failure_caught", 4, ["Lint (flake8)"],
        "Jenkins build #4 - CI caught flake8 errors in a new commit, pipeline stopped (fixed in the next commit)")
excerpt("27_jenkins_build5_terraform_apply", 5, ["Terraform Plan", "Terraform Apply"],
        "Jenkins build #5 (APPLY=true) - terraform plan + apply creates the EC2 instance",
        grep={"Terraform Plan": r"Plan:|will be created|Reading|Read complete|instance_type|tfplan"})
excerpt("28_jenkins_build5_verify_ec2_deployment", 5, ["Verify EC2 Deployment"],
        "Jenkins build #5 - pipeline waits for the app on the EC2 public IP and checks /health")
excerpt("29_jenkins_build6_terraform_destroy", 6, ["Terraform Plan", "Terraform Destroy"],
        "Jenkins build #6 (DESTROY=true) - terraform plan -destroy + apply removes everything",
        grep={"Terraform Plan": r"Plan:|will be destroyed|Refreshing|tfplan"})
