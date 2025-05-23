// ./infrastructure-as-code/modules/function-app.bicep

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

@description('The login server URL for Azure Container Registry (e.g., https://myacr.azurecr.io).')
param acrLoginServerUrl string

@description('The username for Azure Container Registry.')
param acrUsername string

@description('The password for Azure Container Registry.')
@secure()
param acrPassword string

@description('The connection string for Azure Storage (for AzureWebJobsStorage).')
param storageConnectionString string

@description('The runtime for Azure Functions (e.g., python).')
param functionsWorkerRuntime string

@description('Flag to enable/disable App Service storage.')
param websitesEnableAppServiceStorage string = 'false' // Default to false as recommended for containers

@description('An array of additional application settings for the Function App.')
param customAppSettings array = []

// Azure Function App (Linux, Container-based)
resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux' // Specifies a Linux Function App
  identity: { // Enables System-Assigned Managed Identity
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlanId // Links to the App Service Plan
    httpsOnly: true
    clientAffinityEnabled: false

    siteConfig: {
      linuxFxVersion: fullDockerImageName // Configures the Docker container
      alwaysOn: false // For B1 plan, can be true if needed (higher cost for always running)
      ftpsState: 'FtpsOnly'
      minTlsVersion: '1.2'
      http20Enabled: true

      appSettings: union(
        [
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
          {
            name: 'PYTHON_ENABLE_WORKER_EXTENSIONS'
            value: '1' // May be needed for some Python extensions
          }
        ],
        customAppSettings // Merge custom app settings
      )
    }
  }
}

output functionAppId string = functionApp.id
output functionAppName string = functionApp.name
output functionAppHostName string = functionApp.properties.defaultHostName
