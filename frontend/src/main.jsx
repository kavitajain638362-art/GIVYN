import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import '@fontsource/instrument-serif/latin-400.css'
import '@fontsource/dm-sans/latin-400.css'
import '@fontsource/dm-sans/latin-600.css'
import '@fontsource/libre-baskerville/latin-400.css'
import '@fontsource/cormorant-garamond/latin-400.css'
import '@fontsource/cormorant-garamond/latin-600.css'
import App from './App.jsx'
import './styles.css'

createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>,
)
