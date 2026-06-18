import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Provider } from 'react-redux'
import { RouterProvider } from 'react-router-dom'
import { store } from './store'
import router from './router'
import PwaPrompts from './features/pwa/PwaPrompts'
import { ThemeProvider } from './design/ThemeProvider'
import { initTheme } from './design/theme'
import './index.css'

// Applique la préférence de thème/densité avant le rendu (aucun flash). Inerte
// pour les écrans existants (couleurs en dur, aucun `dark:` utilisé).
initTheme()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Provider store={store}>
      <ThemeProvider>
        <RouterProvider router={router} />
        <PwaPrompts />
      </ThemeProvider>
    </Provider>
  </StrictMode>,
)
