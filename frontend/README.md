# AgentShield dashboard

Next.js UI for the API in the repo root. See the root `README.md` for setup, threat model, and deployment.

```bash
export API_UPSTREAM_URL=http://127.0.0.1:8741
export API_KEY=dev-only-change-me
npm run dev -- --hostname 0.0.0.0 --port 8742
```

The browser calls `/backend-api`, and this server attaches `X-API-Key`.
