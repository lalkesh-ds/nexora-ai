import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#111113',
            border: '1px solid rgba(255,255,255,0.08)',
            color: '#f4f4f5',
          },
        }}
      />
    </BrowserRouter>
  </StrictMode>,
)
