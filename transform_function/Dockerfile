FROM mcr.microsoft.com/azure-functions/python:4-python3.9-slim

# Install OpenJDK 11 required by Spark
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-11-jdk-headless && \
    rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Install Python dependencies
COPY transform_function/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

ENV AzureWebJobsScriptRoot=/home/site/wwwroot
ENV AzureFunctionsJobHost__Logging__Console__IsEnabled=true

# Copy project files
COPY . /home/site/wwwroot/

WORKDIR /home/site/wwwroot
