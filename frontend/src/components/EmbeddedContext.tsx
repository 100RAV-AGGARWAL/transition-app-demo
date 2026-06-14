import React, { useEffect, useState } from 'react';

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

            // Expect a simple envelope: { type: 'SALESFORCE_CONTEXT', payload: { ... } }
            if (typeof data === 'object' && data.type === 'SALESFORCE_CONTEXT') {
                setContext(data.payload ?? null);
                setOrigin(event.origin);
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
