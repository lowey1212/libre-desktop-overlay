# Security and safety

- Do not commit Gluroo URLs, tokens, API headers, passwords, or personal glucose exports.
- Do not commit Juggluco phone addresses, API secrets, or personal glucose exports.
- User-specific Gluroo connection values are entered at runtime and are not embedded in source, executables, or GitHub releases.
- Remembered Gluroo connection details are stored through Windows Credential Manager when available.
- Remembered Juggluco API secrets are stored separately through Windows Credential Manager (`juggluco-api-secret`) and are sent in the `api_secret` request header, never in the visible URL.
- Optional FoodData Central API keys are also stored through Windows Credential Manager and are never embedded in the executable or repository.
- Food, insulin, and custom food-list data are stored locally in the current Windows user profile and are included only when the user explicitly exports them.
- The project does not send glucose data to an additional server of its own.
- If a Gluroo access URL, token, or header is exposed, revoke or regenerate it in Gluroo.
- Keep Juggluco's web server on the trusted home network and never expose or port-forward port 17580 to the public internet.
- This is a convenience display, not a medical device. Confirm readings in the official Libre/Gluroo application before treatment decisions, especially when data is delayed or does not match symptoms.
- Timeline events and food estimates are for record-keeping and discussion only. The application never calculates or recommends insulin doses.
