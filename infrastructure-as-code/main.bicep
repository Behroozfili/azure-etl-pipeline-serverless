@description('The Azure region where resources will be deployed.')
param location string

@description('The name of the App Service Plan.')
param appServicePlanName string

@description('The name of the Azure Container Registry.')
param acrName string

@description('The username for Azure Container Registry (usually same as acrName).')
param acrUsername string

@secure()
@description('The password for Azure Container Registry. Best practice: source from Key Vault.')
param acrPassword string

// پارامتر appInsightsInstrumentationKey حذف شد زیرا استفاده نمی‌شد و App Insights جدید ایجاد می‌شود.
// اگر نیاز به اتصال به App Insights موجود دارید، می‌توانید این پارامتر را برگردانید و منطق appInsights را تغییر دهید.

@secure()
@description('The connection string for the Azure Storage Account primarily used by Functions runtime (AzureWebJobsStorage). Best practice: source from Key Vault.')
param storageConnectionString string

@description('The name of the Azure Storage Account where AzureWebJobsStorage queues and metadata reside. Required for queue creation.')
param webJobsStorageAccountName string

// --- Data Storage & Spark Access Parameters ---
@description('The name of the Azure Storage Account where raw, datasets, and models are stored (used by Spark/Databricks).')
param dataStorageAccountName string

@secure()
@description('The account key for the dataStorageAccountName (used by Spark/Databricks if not using MI/SP). Best practice: source from Key Vault.')
param dataStorageAccountKey string

// --- Databricks Integration Parameters ---
@description('The Databricks workspace URL (e.g., https://adb-xxxxxxxxxxxxxxx.x.azuredatabricks.net).')
param databricksHost string

@secure()
@description('The Databricks Personal Access Token (PAT) for API calls. Best practice: source from Key Vault.')
param databricksToken string

@description('The Job ID in Databricks for the Data Transformation notebook.')
param databricksJobIdDataTransformation string

@description('The Job ID in Databricks for the Model Training notebook.')
param databricksJobIdModelTraining string
// --- End of Databricks Parameters ---

@description('The runtime for Azure Functions (e.g., python).')
param functionsWorkerRuntime string = 'python'

@description('Flag to enable/disable App Service storage. Usually "false" for Docker-based functions.')
param websitesEnableAppServiceStorage string = 'false'

// --- Storage Container and Queue Names ---
@description('The name of the raw data container in Azure Storage (input for Extract/Transform).')
param rawDataContainerName string = 'rawdata'
@description('The name of the datasets container in Azure Storage (output of Transform, input for Load/Train).')
param datasetsContainerName string = 'datasets'
@description('The name of the models container in Azure Storage (output of Train).')
param modelContainerName string = 'models'
@description('The name of the final output container in Azure Storage (output of Load, if applicable).')
param finalOutputContainerName string = 'finaloutput'

@description('The name of the transform queue in Azure Storage (triggers Transform function).')
param transformQueueName string = 'transform-queue'
@description('The name of the load queue in Azure Storage (triggers Load function).')
param loadQueueName string = 'load-queue'
@description('The name of the train model queue in Azure Storage (triggers Train Model function).')
param trainModelQueueName string = 'train-model-queue' // مقدار پیش‌فرض را با خط تیره تنظیم می‌کنیم تا با parameters.json شما سازگارتر باشد

// --- Function App Specific Parameters ---
@description('The name of the Extract Azure Function App.')
param extractFunctionAppName string
@description('The base name of the Docker image for the Extract function.')
param extractDockerImageBaseName string = 'extract-function'
@description('The tag for the Docker image for the Extract function.')
param extractDockerImageTag string = 'latest'

@description('The name of the Transform Azure Function App.')
param transformFunctionAppName string
@description('The base name of the Docker image for the Transform function.')
param transformDockerImageBaseName string = 'transform-function'
@description('The tag for the Docker image for the Transform function.')
param transformDockerImageTag string = 'latest'

@description('The name of the Load Azure Function App.')
param loadFunctionAppName string
@description('The base name of the Docker image for the Load function.')
param loadDockerImageBaseName string = 'load-function'
@description('The tag for the Docker image for the Load function.')
param loadDockerImageTag string = 'latest'

@description('The name of the Train Model Azure Function App.')
param trainModelFunctionAppName string
@description('The base name of the Docker image for the Train Model function.')
param trainModelDockerImageBaseName string = 'train-model-function'
@description('The tag for the Docker image for the Train Model function.')
param trainModelDockerImageTag string = 'latest'


// Variables
var acrLoginServerUrl = 'https://${acrName}.azurecr.io'
var extractFullDockerImageName = 'DOCKER|${acrLoginServerUrl}/${extractDockerImageBaseName}:${extractDockerImageTag}'
var transformFullDockerImageName = 'DOCKER|${acrLoginServerUrl}/${transformDockerImageBaseName}:${transformDockerImageTag}'
var loadFullDockerImageName = 'DOCKER|${acrLoginServerUrl}/${loadDockerImageBaseName}:${loadDockerImageTag}'
var trainModelFullDockerImageName = 'DOCKER|${acrLoginServerUrl}/${trainModelDockerImageBaseName}:${trainModelDockerImageTag}'
var appInsightsResourceName = 'appi-${appServicePlanName}'

// --- Resources ---

// App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'B1'
    tier:'Basic'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsResourceName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
  }
}

// Storage Account for AzureWebJobsStorage (where queues will be created)
resource webJobsStorage 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: webJobsStorageAccountName
}

// --- Storage Queues ---
// First, get a reference to the queue service of the existing storage account
resource storageAccountQueueService 'Microsoft.Storage/storageAccounts/queueServices@2023-01-01' existing = {
  name: 'default' // The default queue service is always named 'default'
  parent: webJobsStorage // The existing storage account resource
}

// Now, define the queues as children of this queue service
resource transformQueueResource 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-01-01' = {
  name: transformQueueName
  parent: storageAccountQueueService
}

resource loadQueueResource 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-01-01' = {
  name: loadQueueName
  parent: storageAccountQueueService
}

resource trainModelQueueResource 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-01-01' = {
  name: trainModelQueueName
  parent: storageAccountQueueService
}

// --- Function App Deployments ---

// Deploy Extract Function
module extractFunctionApp 'modules/function-app.bicep' = {
  name: 'deploy-${extractFunctionAppName}'
  params: {
    functionAppName: extractFunctionAppName
    location: location
    appServicePlanId: appServicePlan.id
    appInsightsInstrumentationKey: appInsights.properties.InstrumentationKey // استفاده از کلید App Insights جدید
    fullDockerImageName: extractFullDockerImageName
    acrLoginServerUrl: acrLoginServerUrl
    acrUsername: acrUsername
    acrPassword: acrPassword
    storageConnectionString: storageConnectionString
    functionsWorkerRuntime: functionsWorkerRuntime
    websitesEnableAppServiceStorage: websitesEnableAppServiceStorage
    customAppSettings: [
      { name: 'RAW_DATA_CONTAINER_NAME', value: rawDataContainerName }
      { name: 'TransformQueueName', value: transformQueueName }
      { name: 'STORAGE_ACCOUNT_NAME', value: dataStorageAccountName }
    ]
  }
}

// Deploy Transform Function
module transformFunctionApp 'modules/function-app.bicep' = {
  name: 'deploy-${transformFunctionAppName}'
  params: {
    functionAppName: transformFunctionAppName
    location: location
    appServicePlanId: appServicePlan.id
    appInsightsInstrumentationKey: appInsights.properties.InstrumentationKey // استفاده از کلید App Insights جدید
    fullDockerImageName: transformFullDockerImageName
    acrLoginServerUrl: acrLoginServerUrl
    acrUsername: acrUsername
    acrPassword: acrPassword
    storageConnectionString: storageConnectionString
    functionsWorkerRuntime: functionsWorkerRuntime
    websitesEnableAppServiceStorage: websitesEnableAppServiceStorage
    customAppSettings: [
      { name: 'DATABRICKS_HOST', value: databricksHost }
      { name: 'DATABRICKS_TOKEN', value: databricksToken }
      { name: 'DATABRICKS_JOB_ID_TRANSFORMATION', value: databricksJobIdDataTransformation }
      { name: 'STORAGE_ACCOUNT_NAME_PARAM', value: dataStorageAccountName }
      { name: 'RAW_DATA_CONTAINER_NAME_PARAM', value: rawDataContainerName }
      { name: 'DATASETS_CONTAINER_NAME_PARAM', value: datasetsContainerName }
      { name: 'AZURE_STORAGE_ACCOUNT_KEY_PARAM', value: dataStorageAccountKey }
      { name: 'TransformQueueName', value: transformQueueName }
      { name: 'LoadQueueName', value: loadQueueName }
    ]
  }
}

// Deploy Load Function
module loadFunctionApp 'modules/function-app.bicep' = {
  name: 'deploy-${loadFunctionAppName}'
  params: {
    functionAppName: loadFunctionAppName
    location: location
    appServicePlanId: appServicePlan.id
    appInsightsInstrumentationKey: appInsights.properties.InstrumentationKey // استفاده از کلید App Insights جدید
    fullDockerImageName: loadFullDockerImageName
    acrLoginServerUrl: acrLoginServerUrl
    acrUsername: acrUsername
    acrPassword: acrPassword
    storageConnectionString: storageConnectionString
    functionsWorkerRuntime: functionsWorkerRuntime
    websitesEnableAppServiceStorage: websitesEnableAppServiceStorage
    customAppSettings: [
      { name: 'DATASETS_CONTAINER_NAME', value: datasetsContainerName }
      { name: 'FINAL_OUTPUT_CONTAINER_NAME', value: finalOutputContainerName }
      { name: 'STORAGE_ACCOUNT_NAME', value: dataStorageAccountName }
      { name: 'LoadQueueName', value: loadQueueName }
      { name: 'TrainModelQueueName', value: trainModelQueueName }
    ]
  }
}

// Deploy Train Model Function
module trainModelFunctionApp 'modules/function-app.bicep' = {
  name: 'deploy-${trainModelFunctionAppName}'
  params: {
    functionAppName: trainModelFunctionAppName
    location: location
    appServicePlanId: appServicePlan.id
    appInsightsInstrumentationKey: appInsights.properties.InstrumentationKey // استفاده از کلید App Insights جدید
    fullDockerImageName: trainModelFullDockerImageName
    acrLoginServerUrl: acrLoginServerUrl
    acrUsername: acrUsername
    acrPassword: acrPassword
    storageConnectionString: storageConnectionString
    functionsWorkerRuntime: functionsWorkerRuntime
    websitesEnableAppServiceStorage: websitesEnableAppServiceStorage
    customAppSettings: [
      { name: 'DATABRICKS_HOST', value: databricksHost }
      { name: 'DATABRICKS_TOKEN', value: databricksToken }
      { name: 'DATABRICKS_JOB_ID_MODEL_TRAINING', value: databricksJobIdModelTraining }
      { name: 'STORAGE_ACCOUNT_NAME_PARAM', value: dataStorageAccountName }
      { name: 'DATASETS_CONTAINER_NAME_PARAM', value: datasetsContainerName }
      { name: 'MODELS_CONTAINER_NAME_PARAM', value: modelContainerName }
      { name: 'AZURE_STORAGE_ACCOUNT_KEY_PARAM', value: dataStorageAccountKey }
      { name: 'TrainModelQueueName', value: trainModelQueueName }
    ]
  }
}

// Outputs
output extractFunctionAppHostName string = extractFunctionApp.outputs.functionAppHostName
output transformFunctionAppHostName string = transformFunctionApp.outputs.functionAppHostName
output loadFunctionAppHostName string = loadFunctionApp.outputs.functionAppHostName
output trainModelFunctionAppHostName string = trainModelFunctionApp.outputs.functionAppHostName
output deployedAppInsightsName string = appInsights.name
output deployedAppInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
