// ./infrastructure-as-code/main.bicep
@description('The Azure region where resources will be deployed.')
param location string

@description('The name of the App Service Plan.')
param appServicePlanName string

// --- ACR Parameters ---
@description('The name of the Azure Container Registry.')
param acrName string

@description('The username for Azure Container Registry (usually same as acrName).')
param acrUsername string

@description('The password for Azure Container Registry (passed securely).')
@secure()
param acrPassword string

// --- Storage & App Insights Parameters (assuming these are shared or passed from .env) ---
@description('The Instrumentation Key for Application Insights.')
param appInsightsInstrumentationKey string

@description('The connection string for the Azure Storage Account.')
param storageConnectionString string

@description('The runtime for Azure Functions (e.g., python).')
param functionsWorkerRuntime string

@description('Flag to enable/disable App Service storage.')
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

@description('The name of the raw data container in Azure Storage (for Extract function).')
param rawDataContainerName string


// --- Transform Function Specific Parameters (add these when you are ready for transform) ---
@description('The name of the Transform Azure Function App.')
param transformFunctionAppName string

@description('The base name of the Docker image for the Transform function.')
param transformDockerImageBaseName string = 'transform-function'

@description('The tag for the Docker image for the Transform function.')
param transformDockerImageTag string = 'v1'

@description('The name of the transform queue in Azure Storage (for Transform function).')
param transformQueueName string


// ===================================================================================
// Variables
// ===================================================================================
var acrLoginServerUrl = 'https://${acrName}.azurecr.io'

var extractFullDockerImageName = 'DOCKER|${acrName}.azurecr.io/${extractDockerImageBaseName}:${extractDockerImageTag}'
var transformFullDockerImageName = 'DOCKER|${acrName}.azurecr.io/${transformDockerImageBaseName}:${transformDockerImageTag}' // For when transform is ready


// ===================================================================================
// Resources
// ===================================================================================

// App Service Plan (Linux, Basic B1 tier) - Shared by all function apps
resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
    size: 'B1'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// Deploy Extract Function App using the module
module extractFunctionApp 'modules/function-app.bicep' = {
  name: 'deployExtractFunctionApp' // Deployment name for this module instance
  params: {
    functionAppName: extractFunctionAppName
    location: location
    appServicePlanId: appServicePlan.id
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    fullDockerImageName: extractFullDockerImageName
    acrLoginServerUrl: acrLoginServerUrl
    acrUsername: acrUsername
    acrPassword: acrPassword
    storageConnectionString: storageConnectionString
    functionsWorkerRuntime: functionsWorkerRuntime
    websitesEnableAppServiceStorage: websitesEnableAppServiceStorage
    customAppSettings: [
      {
        name: 'DATASETS_CONTAINER_NAME'
        value: datasetsContainerName
      }
      {
        name: 'RAW_DATA_CONTAINER_NAME'
        value: rawDataContainerName
      }
      // Add any other extract-specific settings here
    ]
  }
}

// Deploy Transform Function App using the module (Uncomment and configure when ready)
/*
module transformFunctionApp 'modules/function-app.bicep' = {
  name: 'deployTransformFunctionApp' // Deployment name for this module instance
  params: {
    functionAppName: transformFunctionAppName
    location: location
    appServicePlanId: appServicePlan.id
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    fullDockerImageName: transformFullDockerImageName
    acrLoginServerUrl: acrLoginServerUrl
    acrUsername: acrUsername
    acrPassword: acrPassword
    storageConnectionString: storageConnectionString
    functionsWorkerRuntime: functionsWorkerRuntime
    websitesEnableAppServiceStorage: websitesEnableAppServiceStorage
    customAppSettings: [
      {
        name: 'TRANSFORM_QUEUE_NAME'
        value: transformQueueName
      }
      {
        name: 'RAW_DATA_CONTAINER_NAME' // Transform might also need this
        value: rawDataContainerName
      }
      // Add any other transform-specific settings here
    ]
  }
}
*/

// ===================================================================================
// Outputs (Optional, but good practice)
// ===================================================================================
output extractFunctionAppHostName string = extractFunctionApp.outputs.functionAppHostName
// output transformFunctionAppHostName string = transformFunctionApp.outputs.functionAppHostName // When ready
