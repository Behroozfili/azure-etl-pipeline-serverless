// ./infrastructure-as-code/modules/function-app.bicep

@description('The name of the Azure Function App.')
param functionAppName string

@description('The Azure region where the Function App will be deployed.')
param location string

// param appServicePlanId string // Not needed for Consumption plan

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

@description('The connection string for Azure Storage (used for AzureWebJobsStorage and function app metadata in Consumption plan).')
param storageConnectionString string

@description('The name of the Azure Storage Account used by the Function App in Consumption plan.')
param functionAppStorageAccountName string // e.g., 'yourstorageaccountname'

@description('The runtime for Azure Functions (e.g., python).')
param functionsWorkerRuntime string

@description('Flag to enable/disable App Service storage. Should be false for containers.')
param websitesEnableAppServiceStorage string = 'false' // Default to false as recommended for containers

@description('An array of additional application settings for the Function App.')
param customAppSettings array = []

// Azure Function App (Linux, Container-based, Consumption Plan)
resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux,container' // Specifies a Linux Function App, container based for Consumption
  identity: { // Enables System-Assigned Managed Identity
    type: 'SystemAssigned'
  }
  properties: {
    // serverFarmId is NOT used for Consumption plan
    httpsOnly: true
    clientAffinityEnabled: false // Not relevant for Consumption, but good to set false

    siteConfig: {
      linuxFxVersion: fullDockerImageName // Configures the Docker container
      // alwaysOn is NOT applicable for Consumption plan
      ftpsState: 'FtpsOnly'
      minTlsVersion: '1.2'
      http20Enabled: true
      appSettings: union( // Merge default and custom app settings
        [
          {
            name: 'AzureWebJobsStorage' // Crucial for function app operation (triggers, state)
            value: storageConnectionString
          }
          {
            name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING' // Used by Consumption plan for function content
            value: storageConnectionString
          }
          {
            name: 'WEBSITE_CONTENTSHARE' // Unique share name per function app for its content
            value: toLower('${functionAppName}contentshare') // Auto-generates a unique share name
          }
          {
            name: 'APPINSIGHTS_INSTRUMENTATIONKEY' // For Application Insights integration
            value: appInsightsInstrumentationKey
          }
          {
            name: 'FUNCTIONS_EXTENSION_VERSION' // Specifies the Functions runtime version
            value: '~4' // Recommended for latest features
          }
          {
            name: 'FUNCTIONS_WORKER_RUNTIME' // Specifies the language worker
            value: functionsWorkerRuntime
          }
          {
            name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE' // Should be false for containers
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
            name: 'PYTHON_ENABLE_WORKER_EXTENSIONS' // May be needed for some Python extensions
            value: '1'
          }
          {
            name: 'FUNCTIONS_V2_COMPATIBILITY_MODE' // Ensure it's not accidentally enabled if using ~4
            value: 'false'
          }
        ],
        customAppSettings // Merge custom app settings provided by the main Bicep file
      )
    }
  }
}

// Outputs for the module
output functionAppId string = functionApp.id // Resource ID of the Function App
output functionAppName string = functionApp.name // Name of the Function App
output functionAppHostName string = functionApp.properties.defaultHostName // Default hostname of the Function App
