# Azure Serverless ETL Pipeline

A comprehensive serverless ETL (Extract, Transform, Load) pipeline built on Azure Functions with automated CI/CD deployment using GitHub Actions.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Usage](#usage)
- [Monitoring](#monitoring)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)

## 🚀 Overview

This project implements a scalable, serverless ETL pipeline using Azure Functions that processes data through multiple stages:

- **Extract Function**: Retrieves data from various sources
- **Transform Function**: Processes and transforms data using custom logic
- **Load Function**: Stores processed data in target destinations
- **Train Model Function**: Triggers machine learning model training processes

The pipeline leverages Azure Storage Queues for orchestration and includes integration with Azure Databricks for advanced analytics.

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  Extract        │───▶│  Transform       │───▶│  Load           │───▶│  Train Model     │
│  Function       │    │  Function        │    │  Function       │    │  Function        │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └──────────────────┘
         │                        │                        │                        │
         ▼                        ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  Azure Storage  │    │  Azure Storage   │    │  Azure Storage  │    │  Azure Databricks│
│  Queue          │    │  Queue           │    │  Queue          │    │  Workspace       │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └──────────────────┘
```

### Key Components

- **Azure Functions**: Serverless compute for ETL operations
- **Azure Container Registry (ACR)**: Docker image storage
- **Azure Storage**: Queue management and data storage
- **Azure Databricks**: Advanced analytics and ML model training
- **GitHub Actions**: CI/CD pipeline automation
- **Bicep**: Infrastructure as Code (IaC)

## 📋 Prerequisites

### Required Tools

- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) (latest version)
- [Docker](https://docs.docker.com/get-docker/) (for containerized functions)
- [Python 3.9+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)

### Azure Resources

- Azure Subscription with appropriate permissions
- Resource Group creation rights
- Azure Container Registry access
- Azure Functions deployment permissions
- Azure Databricks workspace (optional)

### Environment Setup

1. **Azure CLI Login**
   ```bash
   az login
   az account set --subscription "<your-subscription-id>"
   ```

2. **Docker Setup**
   ```bash
   docker --version
   # Ensure Docker daemon is running
   ```

## 📁 Project Structure

```
azure-serverless-etl/
├── .github/
│   └── workflows/
│       └── ci-cd.yml                 # GitHub Actions CI/CD pipeline
├── infrastructure-as-code/
│   ├── main.bicep                    # Main Bicep template
│   └── parameters.json               # Deployment parameters
├── extract_function/
│   ├── Dockerfile                    # Extract function container
│   ├── requirements.txt              # Python dependencies
│   └── function_app.py               # Extract function code
├── transform_function/
│   ├── Dockerfile                    # Transform function container
│   ├── requirements.txt              # Python dependencies
│   └── function_app.py               # Transform function code
├── load_function/
│   ├── Dockerfile                    # Load function container
│   ├── requirements.txt              # Python dependencies
│   └── function_app.py               # Load function code
├── train_model_function/
│   ├── requirements.txt              # Python dependencies
│   └── function_app.py               # Model training function code
├── databricks/
│   └── notebooks/                    # Databricks notebooks for analytics
├── scripts/
│   ├── deploy-extract.sh             # Extract function deployment
│   ├── build-transform.sh            # Transform function build & push
│   ├── run-load-local.sh             # Local load function testing
│   └── trigger-training.sh           # Model training trigger
├── .env.example                      # Environment variables template
├── requirements.txt                  # Root project dependencies
└── README.md                         # This file
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the root directory based on `.env.example`:

```bash
# Azure Configuration
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_RESOURCE_GROUP=etlResourceGroup
AZURE_LOCATION=eastus

# Azure Container Registry
ACR_NAME=your-acr-name
ACR_LOGIN_SERVER=your-acr-name.azurecr.io

# Function Apps
EXTRACT_FUNCTION_APP_NAME=your-extract-function-name
TRANSFORM_FUNCTION_APP_NAME=your-transform-function-name
LOAD_FUNCTION_APP_NAME=your-load-function-name
TRAIN_MODEL_FUNCTION_APP_NAME=your-train-model-function-name

# Storage Configuration
AZURE_STORAGE_CONNECTION_STRING=your-storage-connection-string
AZURE_STORAGE_ACCOUNT_NAME=your-storage-account-name

# Queue Names
EXTRACT_QUEUE_NAME=extract-input-queue
TRANSFORM_QUEUE_NAME=transform-input-queue
LOAD_QUEUE_NAME=load-input-queue
TRAIN_MODEL_QUEUE_NAME=train-model-queue

# Container Names
DATASETS_CONTAINER_NAME=datasets
FINAL_OUTPUT_CONTAINER_NAME=finaloutput

# Databricks Configuration (Optional)
DATABRICKS_WORKSPACE_URL=https://your-databricks-instance.azuredatabricks.net
DATABRICKS_TOKEN=your-databricks-token
DATABRICKS_NOTEBOOKS_PATH=/Shared/ETL_Pipeline_Notebooks
```

### Bicep Parameters

Update `infrastructure-as-code/parameters.json` with your specific values:

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "location": {
      "value": "eastus"
    },
    "resourcePrefix": {
      "value": "your-prefix"
    },
    "acrName": {
      "value": "your-acr-name"
    }
  }
}
```

## 🚀 Deployment

### Method 1: Automated CI/CD (Recommended)

1. **Fork this repository** to your GitHub account

2. **Configure GitHub Secrets** in your repository settings:
   ```
   AZURE_CREDENTIALS
   AZURE_SUBSCRIPTION_ID
   EXTRACT_FUNCTION_APP_NAME
   LOAD_FUNCTION_APP_NAME
   TRAIN_MODEL_FUNCTION_APP_NAME
   TRANSFORM_FUNCTION_APP_NAME
   DATABRICKS_TOKEN
   ```

3. **Push to main branch** to trigger automatic deployment:
   ```bash
   git add .
   git commit -m "Initial deployment"
   git push origin main
   ```

### Method 2: Manual Deployment

#### Step 1: Deploy Infrastructure

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Deploy Extract Function
./scripts/deploy-extract.sh
```

#### Step 2: Build and Deploy Transform Function

```bash
# Build and push Transform function
./scripts/build-transform.sh
```

#### Step 3: Deploy Load Function

```bash
# Build and run Load function locally for testing
./scripts/run-load-local.sh build
./scripts/run-load-local.sh run

# Test with sample message
./scripts/run-load-local.sh send_message sample-test-blob.txt
```

#### Step 4: Deploy Train Model Function

```bash
# Trigger model training
./scripts/trigger-training.sh
```

## 📖 Usage

### Starting the ETL Pipeline

1. **Trigger Extract Function**
   ```bash
   # Send message to extract queue
   az storage message put \
     --queue-name extract-input-queue \
     --content "source-data-reference" \
     --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
   ```

2. **Monitor Pipeline Progress**
   ```bash
   # Check function logs
   az functionapp logs tail --name behExtractFunc20240521 --resource-group etlResourceGroup
   ```

### Local Development & Testing

#### Running Load Function Locally

```bash
# Build and run locally
./scripts/run-load-local.sh full_test

# Send custom test message
./scripts/run-load-local.sh send_message your-blob-name.txt
```

#### Testing Transform Function

```bash
# Build transform function
./scripts/build-transform.sh

# Check container logs
docker logs transform-function-container -f
```

### Pipeline Orchestration

The ETL pipeline follows this sequence:

1. **Extract** → Processes source data and sends message to transform queue
2. **Transform** → Applies business logic and sends message to load queue  
3. **Load** → Stores processed data and triggers model training
4. **Train Model** → Initiates ML model training in Databricks

## 📊 Monitoring

### Azure Function Monitoring

- **Application Insights**: Integrated logging and monitoring
- **Function App Logs**: Real-time log streaming
- **Queue Monitoring**: Message processing metrics

### Health Checks

```bash
# Check function status
az functionapp show --name your-extract-function-name --resource-group your-resource-group --query "state"

# Monitor queue depth
az storage queue metadata show --name extract-input-queue --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
```

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
4. **Add tests** for new functionality
5. **Run linting and tests**
   ```bash
   flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
   pytest
   ```
6. **Submit a pull request**

### Code Standards

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings for all functions
- Include unit tests for new features

## 🔧 Troubleshooting

### Common Issues

#### 1. Docker Build Failures

**Problem**: Docker build fails with permission errors
```bash
# Solution: Check Docker daemon and permissions
sudo systemctl start docker
sudo usermod -aG docker $USER
```

#### 2. Azure CLI Authentication

**Problem**: `az login` fails or expires
```bash
# Solution: Re-authenticate and set subscription
az login --use-device-code
az account set --subscription "your-subscription-id"
```

#### 3. Function Deployment Errors

**Problem**: Function deployment fails
```bash
# Solution: Check function app exists and permissions
az functionapp list --resource-group your-resource-group
az role assignment list --assignee your-user-id
```

#### 4. Queue Message Processing Issues

**Problem**: Messages not being processed
```bash
# Solution: Check connection string and queue existence
az storage queue list --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
az storage message peek --queue-name your-queue-name --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
```

### Debugging Tips

1. **Enable detailed logging** in function apps
2. **Use Application Insights** for distributed tracing
3. **Check queue message visibility timeout** settings
4. **Verify environment variables** in function app configuration
5. **Monitor resource quotas** and limits

### Getting Help

- **Azure Documentation**: [Azure Functions Documentation](https://docs.microsoft.com/en-us/azure/azure-functions/)
- **GitHub Issues**: Report bugs and feature requests
- **Azure Support**: For infrastructure-related issues

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Contact

For questions and support, please create an issue in the GitHub repository.

## 👨‍💻 Author

**Behrooz Filzadeh**

---

**Happy ETL Processing! 🚀**
