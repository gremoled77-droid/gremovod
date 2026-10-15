// Development-only fixture: intentionally throw to check the fallback in a real browser.
import React from 'react';
import {createRoot} from 'react-dom/client';
import ErrorBoundary from '../src/ErrorBoundary';
import '../src/style.css';

function BrokenView():React.ReactNode { throw new Error('SMOKE_TEST_RENDER_FAILURE'); }
createRoot(document.getElementById('root')!).render(<ErrorBoundary><BrokenView/></ErrorBoundary>);
