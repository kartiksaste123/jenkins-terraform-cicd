# Custom Jenkins controller image with the build tools the pipeline needs
FROM jenkins/jenkins:lts-jdk17

USER root
ARG TERRAFORM_VERSION=1.9.8
ARG DOCKER_CLI_VERSION=26.1.4
ARG BUILDX_VERSION=0.17.1

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv python3-pip git curl unzip ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 # Docker CLI only (builds talk to the host Docker daemon through the mounted socket)
 && curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz \
    | tar -xz --strip-components=1 -C /usr/local/bin docker/docker \
 && mkdir -p /usr/local/lib/docker/cli-plugins \
 && curl -fsSLo /usr/local/lib/docker/cli-plugins/docker-buildx \
    https://github.com/docker/buildx/releases/download/v${BUILDX_VERSION}/buildx-v${BUILDX_VERSION}.linux-amd64 \
 && chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx \
 # Terraform
 && curl -fsSLo /tmp/tf.zip https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip \
 && unzip -q /tmp/tf.zip -d /usr/local/bin && rm /tmp/tf.zip

USER jenkins

# Skip the setup wizard; configure everything with Configuration-as-Code (JCasC)
ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
    CASC_JENKINS_CONFIG=/usr/share/jenkins/casc/jenkins.yaml

COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

COPY casc/jenkins.yaml /usr/share/jenkins/casc/jenkins.yaml
