// ./infrastructure-as-code/main.bicep

// ===================================================================================
// Parameters - مقادیری که از خارج (مثلاً از .env از طریق دستور CLI) پاس داده می‌شوند
// ===================================================================================
@description('The Azure region where resources will be deployed.')
param location string

@description('The name of the Azure Function App.')
param functionAppName string

@description('The name of the App Service Plan.')
param appServicePlanName string

@description('The Instrumentation Key for Application Insights (from .env).')
param appInsightsInstrumentationKey string

@description('The name of the Azure Container Registry (from .env).')
param acrName string

@description('The username for Azure Container Registry (from .env, usually same as acrName).')
param acrUsername string

@description('The password for Azure Container Registry (from .env, passed securely).')
@secure()
param acrPassword string

@description('The base name of the Docker image (without tag).')
param dockerImageBaseName string = 'extract-function'

@description('The tag for the Docker image.')
param dockerImageTag string = 'v1'

@description('The connection string for the Azure Storage Account (from .env).')
param storageConnectionString string

@description('The name of the datasets container in Azure Storage (from .env).')
param datasetsContainerName string

@description('The name of the raw data container in Azure Storage (from .env).')
param rawDataContainerName string

@description('The name of the transform queue in Azure Storage (from .env).')
param transformQueueName string

@description('The runtime for Azure Functions (e.g., python, from .env).')
param functionsWorkerRuntime string

@description('Flag to enable/disable App Service storage (from .env).')
param websitesEnableAppServiceStorage string


// ===================================================================================
// Variables - مقادیر کمکی که در داخل Bicep ساخته می‌شوند
// ===================================================================================
var fullDockerImageName = 'DOCKER|${acrName}.azurecr.io/${dockerImageBaseName}:${dockerImageTag}'
var acrLoginServerUrl = 'https://${acrName}.azurecr.io'


// ===================================================================================
// Resources - تعریف منابع Azure
// ===================================================================================

// App Service Plan (Linux, Basic B1 tier)
resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
    size: 'B1'
  }
  kind: 'linux' // Specifies that the plan is for Linux
  properties: {
    reserved: true // Required for non-Consumption Linux plans
  }
}

// Azure Function App (Linux, Container-based)
resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux' // Specifies a Linux Function App
  identity: { // Enables System-Assigned Managed Identity
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id // Links to the App Service Plan
    httpsOnly: true
    clientAffinityEnabled: false // Typically false for Function Apps

    siteConfig: {
      linuxFxVersion: fullDockerImageName // Configures the Docker container
      alwaysOn: false // For B1 plan, can be true if needed (higher cost for always running)
      ftpsState: 'FtpsOnly'
      minTlsVersion: '1.2'
      http20Enabled: true

      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: storageConnectionString
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsightsInstrumentationKey
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: functionsWorkerRuntime
        }
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: websitesEnableAppServiceStorage
        }
        // --- ACR Credentials for pulling the image ---
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: acrLoginServerUrl
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_USERNAME'
          value: acrUsername
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_PASSWORD'
          value: acrPassword
        }
        // --- Your Application Specific Settings ---
        {
          name: 'DATASETS_CONTAINER_NAME'
          value: datasetsContainerName
        }
        {
          name: 'RAW_DATA_CONTAINER_NAME'
          value: rawDataContainerName
        }
        {
          name: 'TRANSFORM_QUEUE_NAME'
          value: transformQueueName
        }
        {
          name: 'PYTHON_ENABLE_WORKER_EXTENSIONS'
          value: '1' // May be needed for some Python extensions
        }
      ]
    }
  }
}
