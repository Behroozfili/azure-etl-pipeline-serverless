@description('The name of the Azure Function App.')
param functionAppName string

@description('The Azure region where the Function App will be deployed.')
param location string

@description('The Resource ID of the App Service Plan to use.')
param appServicePlanId string

@description('The Instrumentation Key for Application Insights.')
param appInsightsInstrumentationKey string

@description('The full Docker image name (e.g., DOCKER|myacr.azurecr.io/myimage:tag).')
param fullDockerImageName string

@description('The login server URL for Azure Container Registry.')
param acrLoginServerUrl string

@description('The username for Azure Container Registry.')
param acrUsername string

@description('The password for Azure Container Registry.')
@secure()
param acrPassword string

@description('The connection string for Azure Storage.')
param storageConnectionString string

@description('The runtime for Azure Functions.')
param functionsWorkerRuntime string

@description('Flag to enable/disable App Service storage.')
param websitesEnableAppServiceStorage string = 'false'

@description('Additional application settings.')
param customAppSettings array = []

resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlanId
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: fullDockerImageName
      appSettings: union([
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
        {
          name: 'PYTHON_ENABLE_WORKER_EXTENSIONS'
          value: '1'
        }
      ], customAppSettings)
    }
  }
}

output functionAppId string = functionApp.id
output functionAppName string = functionApp.name
output functionAppHostName string = functionApp.properties.defaultHostName
