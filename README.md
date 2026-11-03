# Internal Assessment 3: Jenkins CI/CD Pipeline with Terraform Infrastructure Provisioning

**Student:** Kartik Saste  
**Course assessment:** Cloud Computing, Internal Assessment 3  
**Repository:** https://github.com/kartiksaste123/jenkins-terraform-cicd  
**Stack:** Python 3.12 · Flask · pytest · flake8 · Docker · Jenkins 2.541.3 (LTS, JDK 17) · Terraform 1.9.8 · AWS EC2 (ap-south-1)

For this assessment I built a Jenkins CI/CD pipeline that pulls my code from GitHub, lints it, runs unit tests, builds a Docker image and smoke-tests it. The same pipeline then validates and plans my Terraform code, and (only when I tick a parameter) provisions a real AWS EC2 instance that runs the app. I applied it on my AWS account, opened the app on the instance's public IP, and destroyed it again with the pipeline, so everything was done for real and nothing was left running.

---

## 1. Overview

| Item | Details |
|---|---|
| Application | "Student Task Tracker", a Flask REST API with an HTML page, `/health`, `/api/info`, `/api/tasks` |
| Tests | 8 pytest tests, JUnit XML report, **98% coverage** (pytest-cov) |
| Lint | flake8 (max line length 120) |
| Container | `student-task-tracker:<BUILD_NUMBER>` (python:3.12-slim, gunicorn, non-root user, healthcheck) |
| Jenkins | Runs in Docker on `http://localhost:8081`, configured 100% as code (JCasC + Job DSL), no setup wizard |
| Jenkins job | `jenkins-terraform-cicd`, *Pipeline script from SCM* → GitHub `main` → `Jenkinsfile` |
| Trigger | Poll SCM `H/5 * * * *` (GitHub integration; see §4.3 for why polling instead of a webhook) |
| Terraform | AWS provider `~> 5.70`, default VPC, security group + `t3.micro` EC2 (Amazon Linux 2023) in **ap-south-1 (Mumbai)** |
| AWS access | Dedicated IAM user `terraform-ci` (EC2 permissions only), stored as Jenkins credential `aws-terraform-ci` |
| Results | Build #3 (SCM-triggered) all green · Build #5 `APPLY=true` created the EC2 instance and verified the app · Build #6 `DESTROY=true` removed it |

### API endpoints

| Method and path | Returns |
|---|---|
| `GET /` | HTML page with the task list, app version, build number and host |
| `GET /health` | `{"status": "ok", "time": ...}` (used by the smoke test, Docker HEALTHCHECK and the EC2 check) |
| `GET /api/info` | App name, author, version, build number and hostname |
| `GET /api/tasks` · `GET /api/tasks/<id>` | All tasks / one task (404 if missing) |
| `POST /api/tasks` | Create a task from JSON `{"title": "..."}` (400 if the title is missing) |
| `PUT /api/tasks/<id>/done` | Mark a task as done |

---

## 2. Architecture

![Architecture](docs/architecture.png)

```mermaid
flowchart TB
    subgraph SRC["1. Source"]
      direction LR
      DEV["Kartik<br/>git push"] --> GH["GitHub<br/>kartiksaste123/jenkins-terraform-cicd"] -- "SCM polling H/5 * * * *" --> JK["Jenkins in Docker :8081<br/>Pipeline script from SCM"]
    end
    subgraph CI["2. CI stages - build and test"]
      direction LR
      C1["Checkout"] --> C2["Python venv"] --> C3["flake8 lint"] --> C4["pytest<br/>JUnit + coverage"] --> C5["docker build<br/>tag BUILD_NUMBER"] --> C6["Smoke test<br/>GET /health"]
    end
    subgraph IAC["3. IaC stages - Terraform (AWS keys from Jenkins credential aws-terraform-ci)"]
      direction LR
      T1["init"] --> T2["fmt -check"] --> T3["validate"] --> T4["plan -out tfplan"] --> T5{"APPLY=true?"} -- yes --> T6["apply tfplan"] --> T7["verify app URL"]
      T5 -- "no" --> T8["stop after plan<br/>(DESTROY=true runs destroy)"]
    end
    subgraph AWS["4. AWS ap-south-1 (default VPC)"]
      direction LR
      SG["Security group<br/>22 from admin IP, 80/5000 open"] --> EC2["EC2 t3.micro<br/>Amazon Linux 2023<br/>IMDSv2, encrypted gp3"] -- "user_data: git clone + docker run -p 80:5000" --> APP["Student Task Tracker<br/>http://public-ip/"]
    end
    SRC --> CI --> IAC --> AWS
```

**Flow in words:** I push code to GitHub → Jenkins notices the new commit (SCM polling) and reads the `Jenkinsfile` from the repo → the CI stages check the code (lint, tests, Docker build, smoke test) → the IaC stages check the infrastructure code (init, fmt, validate, plan) → if `APPLY=true`, Terraform creates the EC2 instance, whose boot script clones the same GitHub repo and runs the app in Docker → Jenkins verifies the app URL. A later run with `DESTROY=true` removes everything.

---

## 3. Repository structure

```
jenkins-terraform-cicd/
├── app/
│   ├── app.py                 # Flask REST API (Student Task Tracker)
│   └── templates/index.html   # HTML page
├── tests/test_app.py          # 8 pytest unit tests
├── requirements.txt           # Flask, gunicorn (pinned)
├── requirements-dev.txt       # + pytest, pytest-cov, flake8 (pinned)
├── .flake8 · pytest.ini       # lint and test settings
├── Dockerfile                 # app image (python:3.12-slim, gunicorn, non-root)
├── Jenkinsfile                # declarative CI/CD pipeline
├── terraform/
│   ├── versions.tf            # Terraform + AWS provider versions, local backend
│   ├── provider.tf            # AWS provider, region and default tags
│   ├── variables.tf           # input variables with types, descriptions and validation
│   ├── main.tf                # AMI/VPC data sources, security group, EC2 instance, user_data
│   ├── outputs.tf             # instance id, public IP/DNS, SG id, app URL
│   ├── terraform.tfvars       # my values (region, instance type, SSH CIDR ...)
│   └── .terraform.lock.hcl    # provider lock file (exact provider version + checksums)
├── jenkins/
│   ├── Dockerfile             # Jenkins LTS + python3, Docker CLI/buildx, Terraform, plugins
│   ├── plugins.txt            # plugins installed with jenkins-plugin-cli
│   ├── casc/jenkins.yaml      # JCasC: admin user, security, credential, job (Job DSL)
│   └── start_jenkins.sh       # builds and runs the Jenkins container on port 8081
├── scripts/                   # evidence helpers (Jenkins API, screenshots, log rendering)
├── docs/architecture.png      # architecture diagram
└── evidence/
    ├── logs/                  # command outputs and Jenkins console logs (full logs in logs/jenkins_console/)
    └── screenshots/           # numbered screenshots (terminal + Jenkins UI + browser)
```

Secrets (`.secrets/`, `*.csv`), Terraform state (`*.tfstate`), `.terraform/` and plan files are excluded by `.gitignore`, so no keys or state are ever committed.

---

## 4. Jenkins setup (configuration and GitHub integration)

### 4.1 Custom Jenkins image (`jenkins/Dockerfile`)
I start `FROM jenkins/jenkins:lts-jdk17` and add the tools the pipeline needs on the built-in agent: `python3`, `python3-venv`, `pip`, `git`, the **Docker CLI + buildx** (builds use the host Docker daemon through the mounted `/var/run/docker.sock`) and **Terraform 1.9.8**. Plugins are installed at image build time with `jenkins-plugin-cli`:

`configuration-as-code`, `job-dsl`, `workflow-aggregator` (Pipeline), `git`, `github`, `junit`, `pipeline-stage-view`, `pipeline-graph-view`, `credentials-binding`, `timestamper`, `ws-cleanup`, `htmlpublisher`.

`-Djenkins.install.runSetupWizard=false` skips the setup wizard, because everything is configured as code.

### 4.2 Configuration as Code (`jenkins/casc/jenkins.yaml`)
- **Security:** local user database with one admin user `kartik`, sign-up disabled, "logged-in users can do anything", anonymous read off, CSRF protection on.
- **Credential:** `aws-terraform-ci` (Username with password = AWS access key id / secret key of the IAM user `terraform-ci`). The values are read from files mounted at `/run/secrets` (kept in the git-ignored `.secrets/` folder), so the YAML in GitHub has only `${aws_access_key_id}` style placeholders.
- **Job (Job DSL):** pipeline job `jenkins-terraform-cicd` with:
  - Definition **Pipeline script from SCM** → Git → `https://github.com/kartiksaste123/jenkins-terraform-cicd.git`, branch `*/main`, script path `Jenkinsfile` (lightweight checkout).
  - GitHub project URL property (adds the GitHub link in the job sidebar).
  - Build parameters `APPLY` and `DESTROY` (booleans, default false).
  - Trigger **Poll SCM** `H/5 * * * *`.

### 4.3 GitHub integration: why SCM polling
The normal production setup is a **GitHub webhook** (`/github-webhook/`) that calls Jenkins on every push. My Jenkins runs on a lab machine without a public URL, so GitHub cannot reach it. Instead Jenkins **polls** GitHub every 5 minutes (`H/5`, where `H` spreads the load with a hash) and starts a build only when a new commit appears. Builds **#1** and **#3** were started this way ("Started by an SCM change", screenshot 32 and 40). With a public Jenkins URL I would add the webhook in *GitHub → Settings → Webhooks* and tick "GitHub hook trigger for GITScm polling".

### 4.4 Commands to start Jenkins
```bash
# one-time: put the secrets in .secrets/jcasc/ (jenkins_admin_password, aws_access_key_id, aws_secret_access_key)
./jenkins/start_jenkins.sh          # builds kartik-jenkins:lts and runs it on http://localhost:8081
# container: -p 8081:8080, -v jenkins_home:/var/jenkins_home,
#            -v /var/run/docker.sock:/var/run/docker.sock, -v .secrets/jcasc:/run/secrets:ro
```

---

## 5. The Jenkinsfile (CI/CD pipeline)

Declarative pipeline, `agent any`, with:
- **parameters:** `APPLY` (create infrastructure) and `DESTROY` (remove it), both default `false`, so a normal push only plans.
- **options:** `timestamps()`, `buildDiscarder(logRotator(numToKeepStr: '15'))`, `timeout(45 min)`, `disableConcurrentBuilds()` (two Terraform runs must never touch the state at the same time), `skipDefaultCheckout(true)` (checkout is an explicit stage).
- **environment:** app name, image tag = `BUILD_NUMBER`, `TF_IN_AUTOMATION`, `TF_INPUT=0`, a state file path inside `JENKINS_HOME`, a provider plugin cache and `AWS_DEFAULT_REGION=ap-south-1`.

| # | Stage | What it does | Why |
|---|---|---|---|
| 1 | **Checkout** | `checkout scm` from GitHub and prints repo URL, branch, commit hash, author, message | proves the exact source revision being built |
| 2 | **Setup Python venv** | creates `.venv` and installs pinned `requirements-dev.txt` | isolated, repeatable build environment |
| 3 | **Lint (flake8)** | `flake8 --count --statistics` | fails fast on style errors (build #4 shows this working) |
| 4 | **Unit Tests (pytest)** | pytest with `--junitxml` and `--cov` (term, XML and HTML) | `junit` step publishes results/trend, `publishHTML` publishes the coverage report |
| 5 | **Build Docker Image** | `docker build -t student-task-tracker:$BUILD_NUMBER -t :latest` | every build produces a traceable image |
| 6 | **Smoke Test Container** | runs the image, curls `/health` and `/api/info`, always removes the container | proves the image actually starts and serves traffic |
| 7 | **Terraform Init** | `terraform init -backend-config=path=$JENKINS_HOME/tfstate/...` | downloads the provider; state survives workspace cleanup |
| 8 | **Terraform Fmt Check** | `terraform fmt -check -recursive -diff` | enforces canonical formatting |
| 9 | **Terraform Validate** | `terraform validate` | syntax and type checking of the configuration |
| 10 | **Terraform Plan** | binds `aws-terraform-ci` as `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, `terraform plan -out=tfplan` (or `plan -destroy` when `DESTROY=true`), archives `plan_output.txt` and `tfplan.txt` | shows exactly what will change; if the credential is missing the stage prints a clear message and skips the plan, so CI stays green |
| 11 | **Terraform Apply** | only when `APPLY=true` (and not `DESTROY`): `terraform apply tfplan`, `state list`, `terraform output` | applies exactly the reviewed plan |
| 12 | **Verify EC2 Deployment** | polls `http://<public_ip>/health` until the app is up (max 10 min) | proves the provisioned server really runs the app |
| 13 | **Terraform Destroy** | only when `DESTROY=true`: applies the destroy plan, prints resources left in state | clean teardown, no cost left behind |

**post:** `always` archives the JUnit/coverage XML and Terraform outputs (fingerprinted), `success`/`failure` print a clear result message, `cleanup` removes any smoke-test container and wipes the workspace (`cleanWs`).

Secrets never appear in the log: `withCredentials` masks them (the console shows *"Masking supported pattern matches of $AWS_SECRET_ACCESS_KEY"*), and Terraform reads them from environment variables, never from `.tf` files.

### Pipeline results

| Build | Cause | Parameters | Result | Notes |
|---|---|---|---|---|
| #1 | SCM change (first poll) + manual | APPLY=false | SUCCESS | first run, plan only |
| #2 | Manual (Kartik Saste) | APPLY=false | SUCCESS | plan only |
| **#3** | **SCM change** (new commit pushed) | APPLY=false | **SUCCESS** | all 10 CI + Terraform stages green, `Plan: 2 to add` |
| #4 | Manual | APPLY=true | FAILURE at Lint | **CI caught 6 flake8 errors** in newly added helper scripts; nothing was deployed; I fixed them in the next commit |
| **#5** | Manual | **APPLY=true** | **SUCCESS** | `Apply complete! Resources: 2 added`, app healthy on the EC2 public IP |
| **#6** | Manual | **DESTROY=true** | **SUCCESS** | `Plan: 0 to add, 0 to change, 2 to destroy` → destroyed, 0 resources left |

Stage durations of build #3: Checkout 2.8 s · Setup Python venv 4.9 s · Lint 0.3 s · Unit Tests 0.7 s · Build Docker Image 3.0 s · Smoke Test 1.9 s · Terraform Init 2.6 s · Fmt Check 0.3 s · Validate 2.2 s · Plan 8.1 s (total 32.9 s). Build #5 added Terraform Apply 25.0 s and Verify EC2 Deployment 78.4 s; build #6 Terraform Destroy 37.2 s.

---

## 6. Terraform configuration explained

| File | Contents |
|---|---|
| `versions.tf` | `required_version >= 1.5.0`, provider `hashicorp/aws ~> 5.70` (pinned; exact version in `.terraform.lock.hcl`), `backend "local" {}` |
| `provider.tf` | `provider "aws"` with `region = var.aws_region` and **default_tags** (Project, Environment, Owner, ManagedBy=Terraform, Pipeline=Jenkins) added to every resource. No keys in code. |
| `variables.tf` | `aws_region`, `project_name`, `environment`, `owner`, `instance_type`, `ssh_cidr`, `key_name` (optional, default `null`), `root_volume_size`, `app_repo_url`, `app_branch`, each with a **type, description and validation** (e.g. only `t2.micro`/`t3.micro` allowed, `ssh_cidr` must be a valid CIDR, environment one of dev/test/prod, volume 8 to 30 GiB) |
| `main.tf` | **Data sources:** latest Amazon Linux 2023 x86_64 AMI owned by Amazon, the default VPC and its default subnets. **`aws_security_group.app`:** SSH 22 only from `var.ssh_cidr` (my admin IP /32), HTTP 80 and Flask 5000 from anywhere, all egress. **`aws_instance.app`:** `t3.micro`, public IP, **IMDSv2 required** (`http_tokens = "required"`), **encrypted gp3** root volume (8 GiB, deleted on termination), Name tag, and `user_data` that installs Docker and git, clones this GitHub repo, builds the image and runs it with `-p 80:5000 -p 5000:5000 --restart unless-stopped` |
| `outputs.tf` | `instance_id`, `ami_id`, `public_ip`, `public_dns`, `security_group_id`, `app_url` |
| `terraform.tfvars` | my values: ap-south-1, t3.micro, dev, SSH CIDR = my lab public IP /32, 8 GiB |

No key pair is needed (SSH is optional via `key_name`), because the app is deployed automatically by `user_data`. This is the same idea as CI/CD: no manual steps on the server.

---

## 7. Terraform workflow: init → fmt → validate → plan → apply → destroy

```bash
cd terraform
terraform init                      # download provider, set up backend      (screenshot 10)
terraform fmt -check -recursive     # formatting check                       (screenshot 11)
terraform validate                  # configuration is valid                 (screenshot 12)
terraform plan -out=tfplan          # Plan: 2 to add, 0 to change, 0 destroy (screenshots 13, 14)
terraform apply tfplan              # run by Jenkins build #5 (APPLY=true)   (screenshot 27)
terraform output                    # app_url = "http://<public-ip>/"        (screenshot 52)
terraform destroy                   # run by Jenkins build #6 (DESTROY=true) (screenshot 29)
```

**Real provisioning on AWS (build #5):** Terraform created `sg-0fe464e81f91c0621` and instance `i-085d9d4631189d6c1` (t3.micro, ap-south-1a, AMI `ami-00531e78dd10fb3be`) with public IP **65.0.100.95**. About 80 seconds later the boot script had the app running and the pipeline's verify stage got `{"status":"ok"}` from `http://65.0.100.95/health`. I checked it with `aws ec2 describe-instances` (running, IMDSv2 required, encrypted gp3, security group rules), `curl` and a browser (screenshots 50 to 55).

**Teardown (build #6):** `Plan: 0 to add, 0 to change, 2 to destroy` → instance destroyed in 32 s and the security group in 1 s. `aws ec2 describe-instances` shows the instance `terminated`, the security group no longer exists, the IP no longer answers and the state has 0 resources (screenshot 60). The instance ran for about 4 minutes on a free-tier eligible t3.micro, so the cost is covered by the free tier credits.

---

## 8. How CI/CD and Infrastructure as Code work together

- **One source of truth:** the app code, the Dockerfile, the pipeline (`Jenkinsfile`) and the infrastructure (`terraform/`) all live in the same GitHub repo. Every change, even to a server setting, is a reviewed, versioned commit.
- **CI checks both kinds of code:** a commit runs the same quality gates for the application (lint, unit tests, Docker build, smoke test) and for the infrastructure (`fmt`, `validate`, `plan`). A broken change stops the pipeline before anything reaches AWS (build #4).
- **Plan before apply:** the plan is saved (`-out=tfplan`) and archived, and *that exact plan* is applied, so what was reviewed is what gets built.
- **Gated delivery:** creating or destroying cloud resources needs an explicit `APPLY`/`DESTROY` parameter, so a normal push can never accidentally create or delete servers.
- **Secure credentials:** AWS keys belong to a least-privilege IAM user, are stored in the Jenkins credential store and injected only into the Terraform stages as masked environment variables.
- **Repeatable environments:** because the server is code, I can create it, test it and destroy it again in minutes (builds #5 and #6), and get the identical result every time. That is Continuous Delivery of both the application and its infrastructure.

---

## 9. How to reproduce

```bash
git clone https://github.com/kartiksaste123/jenkins-terraform-cicd.git && cd jenkins-terraform-cicd
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
flake8 && pytest --cov=app                         # local checks
mkdir -p .secrets/jcasc                            # add jenkins_admin_password, aws_access_key_id, aws_secret_access_key
./jenkins/start_jenkins.sh                         # Jenkins on http://localhost:8081, job is created automatically
# Jenkins → jenkins-terraform-cicd → Build with Parameters → APPLY=false (plan), APPLY=true (deploy), DESTROY=true (teardown)
```

---

## 10. Screenshot gallery (execution evidence)

All screenshots are in `evidence/screenshots/`, and the matching text outputs are in `evidence/logs/` (full Jenkins console logs are in `evidence/logs/jenkins_console/`).

### Part A: Tools, source code and local checks

**00. Tool versions on the lab machine and inside the Jenkins container (Jenkins 2.541.3, JDK 17, Terraform 1.9.8, Docker, Python)**

![00_tool_versions](evidence/screenshots/00_tool_versions.png)

**01. Source code repository on GitHub (public) with the commit history**

![01_git_log_github](evidence/screenshots/01_git_log_github.png)

**02. Local check before pushing: flake8 clean, 8 pytest tests pass, 98% coverage**

![02_local_lint_and_tests](evidence/screenshots/02_local_lint_and_tests.png)

### Part B: Terraform validation (local)

**10. terraform init: downloads the pinned hashicorp/aws provider and sets up the local backend**

![10_terraform_init](evidence/screenshots/10_terraform_init.png)

**11. terraform fmt -check: all .tf files are formatted correctly**

![11_terraform_fmt_check](evidence/screenshots/11_terraform_fmt_check.png)

**12. terraform validate: the configuration is valid**

![12_terraform_validate](evidence/screenshots/12_terraform_validate.png)

**13. terraform plan -out=tfplan with the terraform-ci IAM user: Plan 2 to add, 0 to change, 0 to destroy**

![13_terraform_plan](evidence/screenshots/13_terraform_plan.png)

**14. Plan summary: resources to create and key settings (t3.micro, IMDSv2 required, encrypted gp3)**

![14_terraform_show_plan_summary](evidence/screenshots/14_terraform_show_plan_summary.png)

### Part C: Jenkins pipeline console evidence

**20. All Jenkins builds with every stage result and duration (from the Jenkins REST API)**

![20_jenkins_all_builds_stage_summary](evidence/screenshots/20_jenkins_all_builds_stage_summary.png)

**21. Jenkins build #3 (triggered by SCM polling): GitHub checkout with commit details, Python venv, flake8**

![21_jenkins_build3_checkout_venv_lint](evidence/screenshots/21_jenkins_build3_checkout_venv_lint.png)

**22. Jenkins build #3: pytest with JUnit XML and coverage report (8 passed, 98% coverage)**

![22_jenkins_build3_unit_tests](evidence/screenshots/22_jenkins_build3_unit_tests.png)

**23. Jenkins build #3: Docker image built and tagged with BUILD_NUMBER, container smoke-tested on /health**

![23_jenkins_build3_docker_build_smoke_test](evidence/screenshots/23_jenkins_build3_docker_build_smoke_test.png)

**24. Jenkins build #3: terraform init, fmt -check and validate inside the pipeline**

![24_jenkins_build3_terraform_init_fmt_validate](evidence/screenshots/24_jenkins_build3_terraform_init_fmt_validate.png)

**25. Jenkins build #3: terraform plan using the Jenkins credential aws-terraform-ci**

![25_jenkins_build3_terraform_plan](evidence/screenshots/25_jenkins_build3_terraform_plan.png)

**26. Jenkins build #4: the pipeline caught flake8 errors in a new commit and stopped (fixed in the next commit)**

![26_jenkins_build4_lint_failure_caught](evidence/screenshots/26_jenkins_build4_lint_failure_caught.png)

**27. Jenkins build #5 (APPLY=true): terraform apply created the security group and EC2 instance**

![27_jenkins_build5_terraform_apply](evidence/screenshots/27_jenkins_build5_terraform_apply.png)

**28. Jenkins build #5: pipeline waited for the app on the EC2 public IP and checked /health**

![28_jenkins_build5_verify_ec2_deployment](evidence/screenshots/28_jenkins_build5_verify_ec2_deployment.png)

**29. Jenkins build #6 (DESTROY=true): plan -destroy and apply removed both resources**

![29_jenkins_build6_terraform_destroy](evidence/screenshots/29_jenkins_build6_terraform_destroy.png)

### Part D: Jenkins UI

**30. Jenkins dashboard with the jenkins-terraform-cicd pipeline job**

![30_jenkins_dashboard](evidence/screenshots/30_jenkins_dashboard.png)

**31. Job page: Stage View with all stages green for builds #1 to #3**

![31_jenkins_job_page_stage_view](evidence/screenshots/31_jenkins_job_page_stage_view.png)

**32. Build #3 page: started by an SCM change, Git revision from GitHub, tests with no failures**

![32_jenkins_build3_page](evidence/screenshots/32_jenkins_build3_page.png)

**33. Build #3 pipeline graph: every stage passed; Apply/Destroy skipped because APPLY=false**

![33_jenkins_build3_pipeline_graph](evidence/screenshots/33_jenkins_build3_pipeline_graph.png)

**34. Build #3 console output (top): Pipeline from SCM checking out the GitHub repository**

![34_jenkins_build3_console_top](evidence/screenshots/34_jenkins_build3_console_top.png)

**35. Build #3 console output (bottom): post actions and Finished: SUCCESS**

![35_jenkins_build3_console_bottom_success](evidence/screenshots/35_jenkins_build3_console_bottom_success.png)

**36. Build #3 JUnit test results published by the junit step: 8 tests, 0 failures**

![36_jenkins_build3_test_results](evidence/screenshots/36_jenkins_build3_test_results.png)

**38. Coverage report (pytest-cov HTML) published with the HTML Publisher plugin**

![38_jenkins_build3_coverage_report](evidence/screenshots/38_jenkins_build3_coverage_report.png)

**39. Job configuration: Pipeline script from SCM, Git repository URL on GitHub, Poll SCM H/5 * * * ***

![39_jenkins_job_config_github_scm](evidence/screenshots/39_jenkins_job_config_github_scm.png)

**40. Git polling log: Jenkins polls GitHub and starts a build when a new commit is found**

![40_jenkins_scm_polling_log](evidence/screenshots/40_jenkins_scm_polling_log.png)

**41. Jenkins credential aws-terraform-ci (secret values hidden; the access key id is masked in this screenshot)**

![41_jenkins_credentials_masked](evidence/screenshots/41_jenkins_credentials_masked.png)

**42. Build #5 (APPLY=true) pipeline graph: Terraform Apply and Verify EC2 Deployment passed**

![42_jenkins_build5_apply_stage_graph](evidence/screenshots/42_jenkins_build5_apply_stage_graph.png)

**43. Build #5 console output: Finished: SUCCESS**

![43_jenkins_build5_apply_console_bottom](evidence/screenshots/43_jenkins_build5_apply_console_bottom.png)

**44. Build #5 parameters: APPLY=true, DESTROY=false**

![44_jenkins_build5_parameters_apply_true](evidence/screenshots/44_jenkins_build5_parameters_apply_true.png)

**45. Build #5 archived artifacts: JUnit/coverage XML, plan, apply output and terraform outputs**

![45_jenkins_build5_artifacts](evidence/screenshots/45_jenkins_build5_artifacts.png)

**46. Build #6 (DESTROY=true) pipeline graph: Terraform Destroy passed**

![46_jenkins_build6_destroy_stage_graph](evidence/screenshots/46_jenkins_build6_destroy_stage_graph.png)

**47. Build #6 console output: Finished: SUCCESS**

![47_jenkins_build6_destroy_console_bottom](evidence/screenshots/47_jenkins_build6_destroy_console_bottom.png)

**48. Final Stage View for builds #1 to #6 (plan-only, lint failure caught, apply, destroy)**

![48_jenkins_final_job_page_stage_view](evidence/screenshots/48_jenkins_final_job_page_stage_view.png)

**49. Build #6 parameters: APPLY=false, DESTROY=true**

![49_jenkins_build_parameters_page](evidence/screenshots/49_jenkins_build_parameters_page.png)

### Part E: Real provisioning on AWS EC2 and teardown

**50. aws ec2 describe-instances / volumes / security-groups: running t3.micro in ap-south-1, IMDSv2, encrypted gp3, SG rules**

![50_aws_ec2_describe_instances](evidence/screenshots/50_aws_ec2_describe_instances.png)

**51. curl against the EC2 public IP: /health 200 OK, /api/info, /api/tasks, port 5000 and the HTML page**

![51_curl_ec2_app](evidence/screenshots/51_curl_ec2_app.png)

**52. terraform state list and terraform output after apply (state kept in JENKINS_HOME)**

![52_terraform_state_list_and_output](evidence/screenshots/52_terraform_state_list_and_output.png)

**53. The Student Task Tracker app in the browser on the EC2 public IP**

![53_browser_app_on_ec2_public_ip](evidence/screenshots/53_browser_app_on_ec2_public_ip.png)

**54. GET /api/info on the EC2 instance**

![54_browser_ec2_api_info](evidence/screenshots/54_browser_ec2_api_info.png)

**55. GET /api/tasks on the EC2 instance**

![55_browser_ec2_api_tasks](evidence/screenshots/55_browser_ec2_api_tasks.png)

**60. After destroy: instance terminated, security group deleted, app unreachable, 0 resources in state**

![60_aws_after_destroy_instance_terminated](evidence/screenshots/60_aws_after_destroy_instance_terminated.png)

---

## 11. Conclusion

I configured Jenkins entirely as code, connected it to my GitHub repository and built a declarative pipeline whose stages lint, test, containerise and smoke-test the application, then initialise, format-check, validate and plan the Terraform infrastructure. With the gated `APPLY` parameter the same pipeline provisioned a real, secure t3.micro EC2 instance in Mumbai, verified the app on its public IP, and with `DESTROY` cleaned everything up again. This shows how CI/CD and Infrastructure as Code together give fast, repeatable and safe delivery of both the application and the infrastructure it runs on.
