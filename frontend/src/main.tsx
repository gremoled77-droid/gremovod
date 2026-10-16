import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import ErrorBoundary from './ErrorBoundary';
import './style.css';
import './design.css';
import './mobile.css';
import './create.css';
import './home.css';
import './reels.css';
import './lightbox.css';
import './workflow.css';
import './connections.css';
import './refine.css';
import './scene.css';
import '@xyflow/react/dist/style.css';
createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
