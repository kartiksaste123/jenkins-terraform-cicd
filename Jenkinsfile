// =====================================================================
// Jenkins CI/CD pipeline - Student Task Tracker (Kartik Saste)
// GitHub -> Lint -> Unit tests -> Docker build -> Smoke test
//        -> Terraform init/fmt/validate/plan -> (gated) apply / destroy on AWS EC2
// =====================================================================
pipeline {
    agent any

    parameters {
        booleanParam(name: 'APPLY', defaultValue: false,
            description: 'Run terraform apply to create the EC2 instance on AWS (ap-south-1).')
        booleanParam(name: 'DESTROY', defaultValue: false,
            description: 'Run terraform destroy to remove all infrastructure created by this pipeline.')
    }

    options {
        timestamps()
        skipDefaultCheckout(true)
        buildDiscarder(logRotator(numToKeepStr: '15', artifactNumToKeepStr: '10'))
        timeout(time: 45, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    environment {
        APP_NAME           = 'student-task-tracker'
        IMAGE_TAG          = "${env.BUILD_NUMBER}"
        TF_DIR             = 'terraform'
        TF_IN_AUTOMATION   = 'true'
        TF_INPUT           = '0'
        TF_STATE_FILE      = "${env.JENKINS_HOME}/tfstate/jenkins-terraform-cicd/terraform.tfstate"
        TF_PLUGIN_CACHE_DIR = "${env.JENKINS_HOME}/.terraform.d/plugin-cache"
        AWS_DEFAULT_REGION = 'ap-south-1'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh '''
                    echo "Repository : $(git config --get remote.origin.url)"
                    echo "Branch     : ${GIT_BRANCH:-main}"
                    git log -1 --pretty=format:'Commit     : %H%nAuthor     : %an <%ae>%nDate       : %ad%nMessage    : %s%n'
                '''
            }
        }

        stage('Setup Python venv') {
            steps {
                sh '''
                    python3 --version
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --quiet --upgrade pip
                    pip install --quiet -r requirements-dev.txt
                    pip freeze | grep -iE "flask|pytest|flake8|gunicorn"
                '''
            }
        }

        stage('Lint (flake8)') {
            steps {
                sh '. .venv/bin/activate && flake8 --count --statistics && echo "flake8: no issues found"'
            }
        }

        stage('Unit Tests (pytest)') {
            steps {
                sh '''
                    . .venv/bin/activate
                    mkdir -p reports
                    pytest --junitxml=reports/junit.xml \
                           --cov=app --cov-report=term-missing \
                           --cov-report=xml:reports/coverage.xml \
                           --cov-report=html:reports/coverage-html
                '''
            }
            post {
                always {
                    junit testResults: 'reports/junit.xml', allowEmptyResults: false
                    publishHTML(target: [reportName: 'Coverage Report', reportDir: 'reports/coverage-html',
                                         reportFiles: 'index.html', keepAll: true, alwaysLinkToLastBuild: true,
                                         allowMissing: false])
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                    docker build --build-arg BUILD_NUMBER=${BUILD_NUMBER} \
                        -t ${APP_NAME}:${IMAGE_TAG} -t ${APP_NAME}:latest .
                    docker images ${APP_NAME}
                '''
            }
        }

        stage('Smoke Test Container') {
            steps {
                sh '''
                    docker rm -f smoke-${BUILD_NUMBER} 2>/dev/null || true
                    docker run -d --name smoke-${BUILD_NUMBER} ${APP_NAME}:${IMAGE_TAG}
                    # Jenkins and the app container share the default Docker bridge, so curl the container IP
                    SMOKE_IP=$(docker inspect -f '{{.NetworkSettings.IPAddress}}' smoke-${BUILD_NUMBER})
                    echo "Smoke-test container IP: ${SMOKE_IP}"
                    for i in $(seq 1 20); do
                        if curl -fsS http://${SMOKE_IP}:5000/health; then
                            echo; echo "Smoke test passed on attempt $i"; break
                        fi
                        [ "$i" -eq 20 ] && { docker logs smoke-${BUILD_NUMBER}; exit 1; }
                        sleep 1
                    done
                    curl -fsS http://${SMOKE_IP}:5000/api/info; echo
                '''
            }
            post {
                always {
                    sh 'docker rm -f smoke-${BUILD_NUMBER} || true'
                }
            }
        }

        stage('Terraform Init') {
            steps {
                dir(env.TF_DIR) {
                    sh '''
                        terraform version
                        mkdir -p "$(dirname "$TF_STATE_FILE")" "$TF_PLUGIN_CACHE_DIR"
                        terraform init -input=false -no-color -backend-config="path=${TF_STATE_FILE}"
                    '''
                }
            }
        }

        stage('Terraform Fmt Check') {
            steps {
                dir(env.TF_DIR) {
                    sh 'terraform fmt -check -recursive -diff -no-color && echo "terraform fmt: all files correctly formatted"'
                }
            }
        }

        stage('Terraform Validate') {
            steps {
                dir(env.TF_DIR) {
                    sh 'terraform validate -no-color'
                }
            }
        }

        stage('Terraform Plan') {
            steps {
                script {
                    // AWS keys come from the Jenkins credential 'aws-terraform-ci' (never hard-coded).
                    // If it is missing, the plan is skipped with a clear message so CI stays green.
                    env.HAS_AWS = 'false'
                    try {
                        withCredentials([usernamePassword(credentialsId: 'aws-terraform-ci',
                                usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                            env.HAS_AWS = 'true'
                        }
                    } catch (err) {
                        echo "AWS credential 'aws-terraform-ci' not available (${err.class.simpleName}) - skipping terraform plan."
                    }
                    if (env.HAS_AWS == 'true') {
                        withCredentials([usernamePassword(credentialsId: 'aws-terraform-ci',
                                usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                            dir(env.TF_DIR) {
                                String mode = params.DESTROY ? '-destroy ' : ''
                                sh """#!/bin/bash
                                    set -eo pipefail
                                    terraform plan ${mode}-input=false -no-color -out=tfplan | tee plan_output.txt
                                    terraform show -no-color tfplan > tfplan.txt
                                """
                            }
                        }
                    } else {
                        writeFile file: "${env.TF_DIR}/plan_output.txt",
                                  text: 'terraform plan skipped: no AWS credentials configured (validate passed)\n'
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'terraform/plan_output.txt, terraform/tfplan.txt', allowEmptyArchive: true
                }
            }
        }

        stage('Terraform Apply') {
            when {
                beforeAgent true
                allOf {
                    expression { params.APPLY }
                    expression { !params.DESTROY }
                    expression { env.HAS_AWS == 'true' }
                }
            }
            steps {
                withCredentials([usernamePassword(credentialsId: 'aws-terraform-ci',
                        usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                    dir(env.TF_DIR) {
                        sh '''#!/bin/bash
                            set -eo pipefail
                            terraform apply -input=false -no-color -auto-approve tfplan | tee apply_output.txt
                            terraform state list
                            terraform output -no-color | tee outputs.txt
                            terraform output -json > outputs.json
                        '''
                    }
                }
            }
        }

        stage('Verify EC2 Deployment') {
            when {
                allOf {
                    expression { params.APPLY }
                    expression { !params.DESTROY }
                    expression { env.HAS_AWS == 'true' }
                }
            }
            steps {
                dir(env.TF_DIR) {
                    sh '''
                        APP_URL=$(python3 -c "import json;print(json.load(open('outputs.json'))['app_url']['value'])")
                        echo "Waiting for the app at ${APP_URL} (EC2 user_data installs Docker and builds the image)..."
                        for i in $(seq 1 40); do
                            if curl -fsS -m 5 "${APP_URL}health"; then
                                echo; echo "EC2 app is healthy after attempt $i"
                                curl -fsS -m 5 "${APP_URL}api/info"; echo
                                exit 0
                            fi
                            sleep 15
                        done
                        echo "App did not become healthy in time"; exit 1
                    '''
                }
            }
        }

        stage('Terraform Destroy') {
            when {
                allOf {
                    expression { params.DESTROY }
                    expression { env.HAS_AWS == 'true' }
                }
            }
            steps {
                withCredentials([usernamePassword(credentialsId: 'aws-terraform-ci',
                        usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                    dir(env.TF_DIR) {
                        sh '''#!/bin/bash
                            set -eo pipefail
                            terraform apply -input=false -no-color -auto-approve tfplan | tee destroy_output.txt
                        '''
                        sh 'terraform state list | wc -l | xargs -I{} echo "Resources left in state: {}"'
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/**, terraform/*_output.txt, terraform/outputs.*, terraform/tfplan.txt',
                             allowEmptyArchive: true, fingerprint: true
        }
        success {
            echo "SUCCESS: ${env.JOB_NAME} #${env.BUILD_NUMBER} - lint, tests, Docker build and Terraform checks all passed."
        }
        failure {
            echo "FAILURE: ${env.JOB_NAME} #${env.BUILD_NUMBER} - check the stage logs above."
        }
        cleanup {
            sh 'docker rm -f smoke-${BUILD_NUMBER} >/dev/null 2>&1 || true'
            cleanWs(deleteDirs: true, notFailBuild: true)
        }
    }
}
