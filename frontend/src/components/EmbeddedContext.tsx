import React, { useEffect, useState } from 'react';
import oktaAuth from '../oktaAuth';

type SfContext = {
    [key: string]: any;
};

export default function EmbeddedContext() {
    const [context, setContext] = useState<SfContext | null>(null);
    const [origin, setOrigin] = useState<string | null>(null);

    useEffect(() => {
        function handleMessage(event: MessageEvent) {
            // OPTIONAL: restrict allowed origins for security
            // if (event.origin !== 'https://your-salesforce-domain') return;

            const data = event.data;
            if (!data) return;
            // Expect envelopes:
            // { type: 'SALESFORCE_CONTEXT', payload: { ... } }
            // { type: 'SALESFORCE_OKTA_TOKEN', payload: { accessToken, idToken?, expiresAtSeconds?, scope? } }
            if (typeof data === 'object' && data.type === 'SALESFORCE_CONTEXT') {
                setContext(data.payload ?? null);
                setOrigin(event.origin);
            }

            if (typeof data === 'object' && data.type === 'SALESFORCE_OKTA_TOKEN') {
                const payload = data.payload ?? {};
                const at = payload.accessToken;
                if (at) {
                    const expiresAt = payload.expiresAtSeconds ?? Math.floor(Date.now() / 1000) + (payload.expiresInSeconds ?? 3600);
                    const tokenObj: any = {
                        accessToken: at,
                        expiresAt,
                        scope: payload.scope ?? 'openid profile email',
                        tokenType: payload.tokenType ?? 'Bearer',
                    };
                    // store token in okta auth tokenManager for API usage
                    try {
                        // tokenManager.add may require any-typed input depending on library version
                        // @ts-ignore
                        oktaAuth.tokenManager.add('accessToken', tokenObj);
                    } catch (e) {
                        try {
                            // fallback: set directly
                            // @ts-ignore
                            oktaAuth.tokenManager.set('accessToken', tokenObj);
                        } catch (e2) {
                            // ignore
                        }
                    }
                }

                // optionally register id token
                if (payload.idToken) {
                    const idt: any = { idToken: payload.idToken, expiresAt: payload.idTokenExpiresAtSeconds ?? Math.floor(Date.now() / 1000) + 3600 };
                    try {
                        // @ts-ignore
                        oktaAuth.tokenManager.add('idToken', idt);
                    } catch (e) {
                        try {
                            // @ts-ignore
                            oktaAuth.tokenManager.set('idToken', idt);
                        } catch (e2) {
                            // ignore
                        }
                    }
                }
                // reflect token presence in UI by storing a minimal context entry
                setContext((prev) => ({ ...(prev ?? {}), __okta_token_loaded: true, __okta_expires_at: payload.expiresAtSeconds }));
            }
        }

        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, []);

    if (!context) return null;

    function renderValue(value: any) {
        if (value === null || value === undefined) return <span style={{ color: '#666' }}>—</span>;
        if (typeof value === 'object') {
            return (
                <details>
                    <summary style={{ cursor: 'pointer' }}>View</summary>
                    <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap', marginTop: 6 }}>{JSON.stringify(value, null, 2)}</pre>
                </details>
            );
        }
        return <span>{String(value)}</span>;
    }

    const rows = Object.entries(context);

    return (
        <div className="embedded-context" style={{ marginLeft: '1rem', maxWidth: 420 }}>
            <details open>
                <summary style={{ cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>Salesforce Context</summary>
                <div style={{ fontSize: 13, marginTop: 8, color: '#444' }}>
                    <div style={{ marginBottom: 8, color: '#666' }}>origin: {origin}</div>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <tbody>
                            {rows.map(([key, val]) => (
                                <tr key={key} style={{ borderBottom: '1px solid #eee' }}>
                                    <td style={{ padding: '6px 8px', verticalAlign: 'top', width: 140, color: '#222', fontWeight: 600 }}>{key}</td>
                                    <td style={{ padding: '6px 8px' }}>{renderValue(val)}</td>
                                </tr>
                            ))}
                            {rows.length === 0 && (
                                <tr>
                                    <td colSpan={2} style={{ padding: '6px 8px', color: '#666' }}>No context provided</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </details>
        </div>
    );
}
