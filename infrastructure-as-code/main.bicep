@description('The Azure region where resources will be deployed.')
param location string

@description('The name of the App Service Plan.')
param appServicePlanName string

@description('The name of the Azure Container Registry.')
param acrName string

@description('The username for Azure Container Registry (usually same as acrName).')
param acrUsername string

@description('The password for Azure Container Registry.')
@secure()
param acrPassword string

@description('The Instrumentation Key for Application Insights.')
param appInsightsInstrumentationKey string

@description('The connection string for the Azure Storage Account.')
param storageConnectionString string

@description('The runtime for Azure Functions (e.g., python).')
param functionsWorkerRuntime string

@description('Flag to enable/disable App Service storage.')
param websitesEnableAppServiceStorage string = 'false'

@description('The name of the Extract Azure Function App.')
param extractFunctionAppName string

@description('The base name of the Docker image for the Extract function.')
param extractDockerImageBaseName string = 'extract-function'

@description('The tag for the Docker image for the Extract function.')
param extractDockerImageTag string = 'v1'

@description('The name of the Transform Azure Function App.')   // جدید
param transformFunctionAppName string

@description('The base name of the Docker image for the Transform function.')  // جدید
param transformDockerImageBaseName string = 'transform-function'

@description('The tag for the Docker image for the Transform function.')   // جدید
param transformDockerImageTag string = 'v1'

@description('The name of the datasets container in Azure Storage.')
param datasetsContainerName string

@description('The name of the raw data container in Azure Storage.')
param rawDataContainerName string

@description('The name of the transform queue in Azure Storage.')
param transformQueueName string

// Variables
var acrLoginServerUrl = 'https://${acrName}.azurecr.io'
var extractFullDockerImageName = 'DOCKER|${acrName}.azurecr.io/${extractDockerImageBaseName}:${extractDockerImageTag}'
var transformFullDockerImageName = 'DOCKER|${acrName}.azurecr.io/${transformDockerImageBaseName}:${transformDockerImageTag}'

// App Service Plan
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

// Deploy Extract Function
module extractFunctionApp 'modules/function-app.bicep' = {
  name: 'deployExtractFunctionApp'
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
      {
        name: 'TRANSFORM_QUEUE_NAME'
        value: transformQueueName
      }
    ]
  }
}

// Deploy Transform Function - 
module transformFunctionApp 'modules/function-app.bicep' = {
  name: 'deployTransformFunctionApp'
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
    ]
  }
}

output extractFunctionAppHostName string = extractFunctionApp.outputs.functionAppHostName
output transformFunctionAppHostName string = transformFunctionApp.outputs.functionAppHostName  // خروجی جدید
