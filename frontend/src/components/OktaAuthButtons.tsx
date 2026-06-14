import React from 'react';
import { useOktaAuth } from '@okta/okta-react';

export default function OktaAuthButtons() {
    const { oktaAuth, authState } = useOktaAuth();

    async function login() {
        // If embedded inside an iframe, request the parent (Salesforce) to provide a token
        try {
            if (window.self !== window.top) {
                window.parent.postMessage({ type: 'OKTA_REQUEST_TOKEN' }, '*');
                return;
            }
        } catch (e) {
            // ignore cross-origin read errors
        }
        await oktaAuth.signInWithRedirect();
    }

    async function logout() {
        await oktaAuth.signOut();
    }

    if (!authState) return null;

    if (!authState.isAuthenticated) {
        return <button onClick={login}>Sign in</button>;
    }

    const name = authState?.idToken?.claims?.name ?? authState?.accessToken?.claims?.name ?? 'User';

    return (
        <div className="okta-auth">
            <span className="profile-name">{name}</span>
            <button onClick={logout}>Sign out</button>
        </div>
    );
}
