// Regista on Azure: subscription-scope entry point used by `azd up`.
targetScope = 'subscription'

@minLength(1)
@maxLength(40)
@description('azd environment name; used to name every resource.')
param environmentName string

@minLength(1)
@description('Primary region. Must offer Azure Container Apps and the chosen Foundry model.')
param location string

@description('Foundry model to deploy for the agents.')
param modelName string = 'gpt-4.1-mini'
param modelVersion string = '2025-04-14'
@description('Tokens-per-minute capacity, in thousands.')
param modelCapacity int = 50

@description('Signed-in developer (azd sets AZURE_PRINCIPAL_ID); granted model access so the agents can be tuned locally.')
param principalId string = ''

@description('Set by azd once the app has been deployed, so re-provisioning keeps the deployed image.')
param registaExists bool = false

@description('Region for the Container Apps environment and app (AZURE_APP_LOCATION); empty means the primary region.')
param appLocation string = ''

@description('Replicas kept warm (REGISTA_MIN_REPLICAS): 0 scales to zero when idle; 1 keeps the demo instant, billed at the idle rate.')
@minValue(0)
@maxValue(1)
param minReplicas int = 0

@secure()
@description('Locks the live-feed API (REGISTA_FEED_TOKEN). Generated on every provision and kept only as a Container App secret; read it with az containerapp secret show.')
param feedToken string = newGuid()

var tags = { 'azd-env-name': environmentName, app: 'regista' }

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'regista-resources'
  scope: rg
  params: {
    location: location
    tags: tags
    token: toLower(uniqueString(subscription().id, environmentName, location))
    modelName: modelName
    modelVersion: modelVersion
    modelCapacity: modelCapacity
    principalId: principalId
    appExists: registaExists
    appLocation: empty(appLocation) ? location : appLocation
    minReplicas: minReplicas
    feedToken: feedToken
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.registryEndpoint
output REGISTA_URL string = resources.outputs.appUrl
output FOUNDRY_PROJECT_ENDPOINT string = resources.outputs.foundryProjectEndpoint
output EVENTHUB_NAMESPACE string = resources.outputs.eventHubNamespace
