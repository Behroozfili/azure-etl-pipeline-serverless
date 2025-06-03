# ./transform_function/Dockerfile

# Use the official Python base image for Azure Functions.
# Make sure the Python version (e.g., python3.9) matches your development and Databricks environment if applicable.
FROM mcr.microsoft.com/azure-functions/python:4-python3.9

# Set the working directory in the container for the function app.
WORKDIR /home/site/wwwroot

# Copy the requirements.txt file first to leverage Docker layer caching.
# If requirements.txt doesn't change, this layer won't be rebuilt.
COPY transform_function/requirements.txt .

# Create a virtual environment and install dependencies.
# This isolates dependencies and is a good practice.
RUN python -m venv .venv
# Activate the virtual environment and install packages.
# Using --no-cache-dir can reduce image size.
RUN . .venv/bin/activate && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the function app code into the working directory.
COPY transform_function/__init__.py .
COPY transform_function/function.json .
# If you have other local Python modules or files used by __init__.py, copy them here.
# Example: COPY transform_function/my_helper_module.py .

# Azure Functions runtimeStamp settings.
ENV AzureWebJobsScriptRoot=/home/site/wwwroot
ENV AzureFunctionsJobHost__Logging__LogLevel__Default=Information
# Optional: Set the Python path to include the site-packages of the virtual environment.
# This might be handled by the base image, but can be explicit.
# ENV PYTHONPATH="/home/site/wwwroot/.venv/lib/python3.9/site-packages:${PYTHONPATH}"


# The base image (mcr.microsoft.com/azure-functions/python) handles the CMD instruction
# to start the Azure Functions host. No need to specify CMD here.
# EXPOSE 80 (is also handled by the base image if needed)