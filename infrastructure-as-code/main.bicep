// ./infrastructure-as-code/main.bicep

// --- Global Parameters ---
@description('The Azure region where resources will be deployed.')
param location string

// --- ACR Parameters ---
@description('The name of the Azure Container Registry.')
param acrName string

@description('The username for Azure Container Registry (usually same as acrName).')
param acrUsername string

@description('The password for Azure Container Registry (passed securely).')
@secure()
param acrPassword string

// --- Storage & App Insights Parameters ---
@description('The Instrumentation Key for Application Insights.')
param appInsightsInstrumentationKey string

@description('The connection string for the Azure Storage Account (used for AzureWebJobsStorage and function app metadata).')
param storageConnectionString string

@description('The name of the Azure Storage Account (e.g., yourstorageaccountname). Required for Consumption plan functions.')
param storageAccountName string

@description('The runtime for Azure Functions (e.g., python).')
param functionsWorkerRuntime string

@description('Flag to enable/disable App Service storage. Should be false for containers.')
param websitesEnableAppServiceStorage string = 'false'


// --- Extract Function Specific Parameters ---
@description('The name of the Extract Azure Function App.')
param extractFunctionAppName string

@description('The base name of the Docker image for the Extract function.')
param extractDockerImageBaseName string = 'extract-function'

@description('The tag for the Docker image for the Extract function.')
param extractDockerImageTag string = 'v1'

@description('The name of the datasets container in Azure Storage (for Extract function).')
param datasetsContainerName string

@description('The name of the raw data container in Azure Storage (for Extract and Transform functions).')
param rawDataContainerName string


// --- Transform Function Specific Parameters ---
@description('The name of the Transform Azure Function App.')
param transformFunctionAppName string

@description('The base name of the Docker image for the Transform function.')
param transformDockerImageBaseName string = 'transform-function'

@description('The tag for the Docker image for the Transform function.')
param transformDockerImageTag string = 'v1'

@description('The name of the transform queue in Azure Storage (for Transform function trigger).')
param transformQueueName string

@description('The name of the container for processed data (output of Databricks job).')
param processedDataContainerName string

// --- Databricks Parameters ---
@description('The Databricks workspace URL (e.g., https://adb-xxxx.azuredatabricks.net).')
param databricksHost string

@description('The Databricks Personal Access Token (PAT) for API access.')
@secure()
param databricksToken string

@description('The path to the Databricks notebook to run for transformation.')
param databricksNotebookPath string

@description('The node type ID for the Databricks job cluster (e.g., Standard_F4s_v2).')
param databricksNodeTypeId string

@description('The Spark version for the Databricks job cluster (e.g., 13.3.x-scala2.12).')
param databricksSparkVersion string

@description('Minimum number of workers for the Databricks job cluster (as string).')
param databricksMinWorkers string

@description('Maximum number of workers for the Databricks job cluster (as string).')
param databricksMaxWorkers string

@description('Timeout in seconds for the Databricks run (as string).')
param databricksRunTimeoutSeconds string

// --- Load Function Trigger Parameter ---
@description('The name of the Azure Storage Queue that triggers the Load function.')
param loadTriggerQueueName string


// ===================================================================================
// Variables
// ===================================================================================
var acrLoginServerUrl = 'https://${acrName}.azurecr.io' // ACR login server URL
var extractFullDockerImageName = 'DOCKER|${acrLoginServerUrl}/${extractDockerImageBaseName}:${extractDockerImageTag}' // Full image name for Extract function
var transformFullDockerImageName = 'DOCKER|${acrLoginServerUrl}/${transformDockerImageBaseName}:${transformDockerImageTag}' // Full image name for Transform function


// ===================================================================================
// Resources
// ===================================================================================

// Deploy Extract Function App using the module (Consumption Plan)
module extractFunctionApp 'modules/function-app.bicep' = {
  name: 'deployExtractFunctionApp' // Deployment name for this module instance
  params: {
    functionAppName: extractFunctionAppName
    location: location
    functionAppStorageAccountName: storageAccountName // Storage account name for Consumption plan
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    fullDockerImageName: extractFullDockerImageName
    acrLoginServerUrl: acrLoginServerUrl
    acrUsername: acrUsername
    acrPassword: acrPassword
    storageConnectionString: storageConnectionString // Used for AzureWebJobsStorage
    functionsWorkerRuntime: functionsWorkerRuntime
    websitesEnableAppServiceStorage: websitesEnableAppServiceStorage
    customAppSettings: [ // Custom application settings for the Extract function
      {
        name: 'DATASETS_CONTAINER_NAME'
        value: datasetsContainerName
      }
      {
        name: 'RAW_DATA_CONTAINER_NAME'
        value: rawDataContainerName
      }
      {
        name: 'TRANSFORM_TRIGGER_QUEUE_NAME' // Queue to trigger the Transform function
        value: transformQueueName
      }
      // Add any other extract-specific settings here
    ]
  }
}

// Deploy Transform Function App using the module (Consumption Plan)
module transformFunctionApp 'modules/function-app.bicep' = {
  name: 'deployTransformFunctionApp' // Deployment name for this module instance
  params: {
    functionAppName: transformFunctionAppName
    location: location
    functionAppStorageAccountName: storageAccountName // Storage account name for Consumption plan
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    fullDockerImageName: transformFullDockerImageName
    acrLoginServerUrl: acrLoginServerUrl
    acrUsername: acrUsername
    acrPassword: acrPassword
    storageConnectionString: storageConnectionString // Used for AzureWebJobsStorage
    functionsWorkerRuntime: functionsWorkerRuntime
    websitesEnableAppServiceStorage: websitesEnableAppServiceStorage
    customAppSettings: [ // Custom application settings for the Transform function
      {
        name: 'TRANSFORM_QUEUE_NAME' // Queue that triggers this Transform function
        value: transformQueueName
      }
      {
        name: 'RAW_DATA_CONTAINER_NAME' // Input container for Databricks job
        value: rawDataContainerName
      }
      {
        name: 'PROCESSED_DATA_CONTAINER_NAME' // Output container from Databricks job
        value: processedDataContainerName
      }
      {
        name: 'DATABRICKS_HOST'
        value: databricksHost
      }
      {
        name: 'DATABRICKS_TOKEN' // Passed securely
        value: databricksToken
      }
      {
        name: 'DATABRICKS_NOTEBOOK_PATH'
        value: databricksNotebookPath
      }
      {
        name: 'STORAGE_ACCOUNT_NAME' // Storage account name, might be needed by notebook
        value: storageAccountName
      }
      {
        name: 'DATABRICKS_NODE_TYPE_ID' // For defining the job cluster
        value: databricksNodeTypeId
      }
      {
        name: 'DATABRICKS_SPARK_VERSION' // Spark version for the job cluster
        value: databricksSparkVersion
      }
      {
        name: 'DATABRICKS_MIN_WORKERS' // Min workers for job cluster
        value: databricksMinWorkers
      }
      {
        name: 'DATABRICKS_MAX_WORKERS' // Max workers for job cluster
        value: databricksMaxWorkers
      }
      {
        name: 'DATABRICKS_RUN_TIMEOUT_SECONDS' // Timeout for the Databricks run
        value: databricksRunTimeoutSeconds
      }
      {
        name: 'LOAD_TRIGGER_QUEUE_NAME' // Queue to trigger the Load function
        value: loadTriggerQueueName
      }
      // Add any other transform-specific settings here
    ]
  }
}

// ===================================================================================
// Outputs (Optional, but good practice)
// ===================================================================================
output extractFunctionAppHostName string = extractFunctionApp.outputs.functionAppHostName // Hostname of the Extract function
output transformFunctionAppHostName string = transformFunctionApp.outputs.functionAppHostName // Hostname of the Transform function
