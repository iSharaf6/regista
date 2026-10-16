// Reads the containers of an existing Container App so `azd provision` keeps the image that
// `azd deploy` pushed instead of resetting it to the placeholder. A module (separate deployment)
// avoids a circular reference to the app being deployed.

param exists bool
param name string

resource existingApp 'Microsoft.App/containerApps@2026-07-01' existing = if (exists) {
  name: name
}

output containers array = exists ? existingApp!.properties.template.containers : []
