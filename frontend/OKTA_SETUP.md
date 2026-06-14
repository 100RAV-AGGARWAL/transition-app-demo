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
 
Deployment note (Vercel):
- If deploying to Vercel, add a `vercel.json` rewrite so the SPA callback path is served by `index.html` (example `vercel.json` is present at project root). Without this you will see a 404 on `/implicit/callback` because Vercel serves static files by path.

Salesforce iframe (silent auth) integration
------------------------------------------
When embedding this app inside Salesforce as an iframe, the recommended pattern is for Salesforce (the parent) to perform authentication with Okta (using a confidential client) and then post the tokens to the iframe so the SPA can operate without prompting the user.

1) Parent requests token on demand
- The React app will post `OKTA_REQUEST_TOKEN` to the parent when the user clicks sign-in inside the iframe.

2) Parent responds with token message
- The parent should respond with a message of type `SALESFORCE_OKTA_TOKEN` and payload containing at least `accessToken` and optionally `idToken` and expiry values.

Example parent -> iframe message (postMessage):
```js
const msg = {
   type: 'SALESFORCE_OKTA_TOKEN',
   payload: {
      accessToken: 'eyJ...access...',
      idToken: 'eyJ...id...',
      expiresAtSeconds: Math.floor(Date.now()/1000) + 3600,
      scope: 'openid profile email'
   }
};
iframe.contentWindow.postMessage(msg, 'https://project-libyg.vercel.app');
```

3) Alternative: parent can push context and token proactively
- Parent may send `SALESFORCE_CONTEXT` (used for display) and `SALESFORCE_OKTA_TOKEN` at iframe load time.

Security notes
- Always set `targetOrigin` when calling `postMessage` (do not use `*` in production).
- In `EmbeddedContext` we do not enforce allowed origins by default — uncomment and set the `event.origin` check to your Salesforce domain.


