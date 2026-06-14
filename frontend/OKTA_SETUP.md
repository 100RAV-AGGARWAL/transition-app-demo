Okta integration setup

1. Ensure you have an Okta SPA application with PKCE enabled.
2. Configure the app's Redirect URI to: `http://localhost:5173/implicit/callback`
3. Set these environment variables (see `.env`):
   - `VITE_OKTA_ISSUER` — your Okta issuer (e.g. https://dev-xxxx.okta.com/oauth2/default)
   - `VITE_OKTA_CLIENT_ID` — your SPA client id
4. Install frontend deps and run:

```bash
cd frontend
npm install
npm run dev
```

Notes:
- The app uses `@okta/okta-react` and `@okta/okta-auth-js` and mounts a `/implicit/callback` route to handle the OAuth redirect.
- API requests include the Okta access token in the `Authorization` header when available.
