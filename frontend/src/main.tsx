import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { oktaAuth } from './oktaAuth';
import { Security, LoginCallback } from '@okta/okta-react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import RequireAuth from './RequireAuth';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <Security
        oktaAuth={oktaAuth}
        restoreOriginalUri={async (_oktaAuth, originalUri) => {
          window.location.replace(originalUri || window.location.origin);
        }}
      >
        <Routes>
          <Route path="/implicit/callback" element={<LoginCallback />} />
          <Route path="/*" element={<RequireAuth><App /></RequireAuth>} />
        </Routes>
      </Security>
    </BrowserRouter>
  </React.StrictMode>
);
