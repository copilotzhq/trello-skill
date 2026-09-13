# Authentication

1. Open https://trello.com/apps/admin and register an app. For an API-only app, Atlassian's managing-apps documentation says an iframe connector URL is not needed.
2. Open its API Key tab and generate a key.
3. Authorize a user token using the key. Start with read scope; request read,write for mutations. Account scope is not needed. Prefer expiring tokens.
4. Supply TRELLO_API_KEY and TRELLO_TOKEN to each CLI process using the host's secret store/environment. Do not put literal tokens in chat, scripts, command history or repository files. Shell exports may not survive isolated agent executions.

The CLI sends an OAuth Authorization header to api.trello.com over HTTPS, not credentials in query strings. It refuses redirects and does not save credentials. Tokens follow the authorizing user's access, not a board-specific grant. Use a dedicated account with limited board access when stronger isolation is needed. Revoke exposed tokens in account settings under Applications.

Official documentation:
- https://developer.atlassian.com/cloud/trello/guides/rest-api/authorization/
- https://developer.atlassian.com/cloud/trello/guides/power-ups/managing-apps/
