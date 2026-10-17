// Regista resources: Microsoft Foundry (project + model), Azure Container Apps, Event Hubs,
// Log Analytics + Application Insights, Container Registry. Keyless: one user-assigned
// managed identity with least-privilege role assignments.

param location string
param tags object
param token string
param modelName string
param modelVersion string
param modelCapacity int
param principalId string
param appExists bool
@description('Region for the Container Apps environment and app; the subscription may allow only one environment per region.')
param appLocation string
@description('0 scales to zero when idle; 1 keeps one replica warm (billed at the idle rate while nobody watches).')
param minReplicas int

var abbr = take('regista${token}', 20)
var appName = 'ca-${abbr}'

// ------------------------------------------------------------------ identity
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${abbr}'
  location: location
  tags: tags
}

// ------------------------------------------------------------------ observability
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${abbr}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${abbr}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

// ------------------------------------------------------------------ Microsoft Foundry
resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: 'aif-${abbr}'
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: 'aif-${abbr}'
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: 'regista'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'Regista match director'
    description: 'Agents that turn synthetic football events into explainable, personalised match intelligence.'
  }
}

resource model 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: modelName
  sku: { name: 'GlobalStandard', capacity: modelCapacity }
  properties: {
    model: { format: 'OpenAI', name: modelName, version: modelVersion }
  }
  // child operations on one account must not run concurrently (409 Conflict otherwise)
  dependsOn: [foundryProject]
}

// ------------------------------------------------------------------ Event Hubs (the ingest stage)
resource ehNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: 'evhns-${abbr}'
  location: location
  tags: tags
  sku: { name: 'Standard', tier: 'Standard', capacity: 1 }
  properties: { disableLocalAuth: true }
}

resource matchEvents 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: ehNamespace
  name: 'match-events'
  properties: { partitionCount: 4, messageRetentionInDays: 1 }
}

resource fabricGroup 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = {
  parent: matchEvents
  name: 'fabric-rti'
}

// ------------------------------------------------------------------ container platform
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: replace('cr${abbr}', '-', '')
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource env 'Microsoft.App/managedEnvironments@2026-07-01' = {
  name: 'caewp-${abbr}' // workload-profiles environment (an earlier Express one was named cae-)
  location: appLocation
  tags: tags
  properties: {
    // Pin the standard mode: left unset, new environments default to Express, which cannot pull from ACR
    // with a managed identity or set revision suffixes. Same consumption billing either way.
    environmentMode: 'WorkloadProfiles'
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

module fetchImage 'fetch-image.bicep' = {
  name: 'regista-fetch-image'
  params: { exists: appExists, name: appName }
}

resource app 'Microsoft.App/containerApps@2026-07-01' = {
  name: appName
  location: appLocation
  tags: union(tags, { 'azd-service-name': 'regista' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [{ server: registry.properties.loginServer, identity: identity.id }]
    }
    template: {
      containers: [
        {
          name: 'regista'
          // placeholder until the first `azd deploy` pushes the Regista image
          image: appExists ? fetchImage.outputs.containers[0].image : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: [
            { name: 'REGISTA_LLM', value: 'foundry' }
            { name: 'FOUNDRY_PROJECT_ENDPOINT', value: 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com/api/projects/${foundryProject.name}' }
            { name: 'FOUNDRY_MODEL', value: model.name }
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'REGISTA_BUS', value: 'eventhubs' }
            { name: 'EVENTHUB_NAMESPACE', value: '${ehNamespace.name}.servicebus.windows.net' }
            { name: 'EVENTHUB_NAME', value: matchEvents.name }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
            { name: 'OTEL_SERVICE_NAME', value: 'regista' }
            { name: 'REGISTA_AUTOPLAY', value: '1' }
          ]
          probes: [
            { type: 'Liveness', httpGet: { path: '/api/health', port: 8000 }, periodSeconds: 30 }
          ]
        }
      ]
      // The live match session is held in memory: one replica keeps every viewer on the same broadcast.
      // Scale-out path: move session fan-out to Event Hubs consumer groups / Web PubSub.
      // minReplicas 0 scales to zero when nobody is watching (each cold start autoplays from kickoff);
      // 1 keeps the demo instant during judging. With no viewers the app pauses itself, so a warm replica
      // stays at the idle rate and makes no model calls. Use minReplicas, not a scale rule: a replica held
      // above the minimum by a rule is billed at the active rate.
      scale: { minReplicas: minReplicas, maxReplicas: 1 }
    }
  }
  dependsOn: [acrPull]
}

// ------------------------------------------------------------------ least-privilege roles
var roles = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  eventHubsDataSender: '2b629674-e913-4c01-ae53-ef4638d8f975'
  cognitiveServicesOpenAIUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  azureAIUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, roles.acrPull)
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
  }
}

resource ehSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(ehNamespace.id, identity.id, roles.eventHubsDataSender)
  scope: ehNamespace
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.eventHubsDataSender)
  }
}

resource openAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, identity.id, roles.cognitiveServicesOpenAIUser)
  scope: foundry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveServicesOpenAIUser)
  }
}

resource aiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, identity.id, roles.azureAIUser)
  scope: foundry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.azureAIUser)
  }
}

// the developer running `azd up` can call the same model locally (`REGISTA_LLM=foundry regista llm-eval`)
resource devAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(foundry.id, principalId, roles.azureAIUser)
  scope: foundry
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.azureAIUser)
  }
}

resource devOpenAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(foundry.id, principalId, roles.cognitiveServicesOpenAIUser)
  scope: foundry
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveServicesOpenAIUser)
  }
}

output registryEndpoint string = registry.properties.loginServer
output appUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output foundryProjectEndpoint string = 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com/api/projects/${foundryProject.name}'
output eventHubNamespace string = '${ehNamespace.name}.servicebus.windows.net'
