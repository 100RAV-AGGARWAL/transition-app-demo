import { OktaAuth } from '@okta/okta-auth-js';

const issuer = import.meta.env.VITE_OKTA_ISSUER ?? 'https://integrator-6419223.okta.com/oauth2/default';
const clientId = import.meta.env.VITE_OKTA_CLIENT_ID ?? '0oa142vxg88RcD1SZ698';
const redirectUri = window.location.origin + '/implicit/callback';

export const oktaAuth = new OktaAuth({
    issuer,
    clientId,
    redirectUri,
    scopes: ['openid', 'profile', 'email'],
    pkce: true,
});

export default oktaAuth;
