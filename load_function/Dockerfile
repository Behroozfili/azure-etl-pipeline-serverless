FROM mcr.microsoft.com/azure-functions/python:4-python3.9-slim

ENV AzureWebJobsScriptRoot=/home/site/wwwroot/load_function \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    FUNCTIONS_WORKER_RUNTIME=python \
    PYTHON_ENABLE_WORKER_EXTENSIONS=1 \
    PYTHONPATH=/home/site/wwwroot

COPY load_function/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /home/site/wwwroot

