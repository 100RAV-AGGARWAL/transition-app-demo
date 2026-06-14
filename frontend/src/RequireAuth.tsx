import React, { useEffect } from 'react';
import { useOktaAuth } from '@okta/okta-react';

export default function RequireAuth({ children }: { children: React.ReactNode }) {
    const { oktaAuth, authState } = useOktaAuth();

    useEffect(() => {
        if (authState && !authState.isAuthenticated) {
            oktaAuth.signInWithRedirect();
        }
    }, [authState, oktaAuth]);

    if (!authState || authState.isPending) return <p>Loading authentication…</p>;

    if (!authState.isAuthenticated) return <p>Redirecting to sign-in…</p>;

    return children;
}
