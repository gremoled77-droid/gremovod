import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import ErrorBoundary from './ErrorBoundary';
import './style.css';
import './design.css';
import './mobile.css';
import './create.css';
import './video.css';
import './home.css';
import './lightbox.css';
import './workflow.css';
import './connections.css';
import './refine.css';
import './scene.css';
import './idea.css';
import './world.css';
import './settings.css';
import '@xyflow/react/dist/style.css';
createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
