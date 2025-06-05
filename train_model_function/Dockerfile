FROM mcr.microsoft.com/azure-functions/python:4-python3.9

ENV AzureWebJobsScriptRoot=/home/site/wwwroot
ENV AzureFunctionsJobHost__Logging__Console__IsEnabled=true

WORKDIR /home/site/wwwroot

# Assuming the Docker build context is the root of the project (serverless-etl-pipeline-azure/)
COPY ./11.train_model_function/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./11.train_model_function/__init__.py .
COPY ./11.train_model_function/function.json .

# Copy other necessary files from 11.train_model_function directory if any
# COPY ./11.train_model_function/other_file.py .
