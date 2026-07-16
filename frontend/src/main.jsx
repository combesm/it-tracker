import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Intercepteur fetch global pour injecter le jeton de sécurité
const originalFetch = window.fetch;
window.fetch = async (url, options = {}) => {
  if (url.toString().includes('/api/') && !url.toString().includes('/api/login')) {
    const token = localStorage.getItem('tracker_token');
    if (token) {
      options.headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
      };
    }
  }
  const response = await originalFetch(url, options);
  
  if (response.status === 401 && url.toString().includes('/api/') && !url.toString().includes('/api/login')) {
    localStorage.removeItem('tracker_token');
    localStorage.removeItem('tracker_username');
    window.dispatchEvent(new Event('auth-failed'));
  }
  return response;
};

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
