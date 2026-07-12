import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Provider } from 'react-redux'
import { RouterProvider } from 'react-router-dom'
import { store } from './store'
import router from './router'
import PwaPrompts from './features/pwa/PwaPrompts'
// VX156 — moment d'accueil de marque, one-shot à la première connexion.
import WelcomeMoment from './components/WelcomeMoment'
import { ThemeProvider } from './design/ThemeProvider'
import { initTheme } from './design/theme'
// Providers UX globaux (lane BEHAVIORS). Toaster + ConfirmProvider +
// SessionProvider sont indépendants du routeur → montés ici, autour du
// RouterProvider. (La palette ⌘K et les raccourcis, qui ont besoin du contexte
// routeur, sont montés DANS le router, cf. router/index.jsx → WithLayout.)
import { Toaster } from './ui/Toaster'
import { ConfirmProvider } from './providers/ConfirmProvider'
import { SessionProvider } from './providers/SessionProvider'
// N93 — cadre i18n (langue d'interface + RTL). Monté HAUT dans l'arbre pour
// que toutes les routes disposent de `t()` / de la locale. FR par défaut.
import { I18nProvider } from './i18n'
import './index.css'
// VX61 — capture Web Vitals RÉELS terrain (INP/LCP/CLS/TTFB), hand-roll
// PerformanceObserver, no-op total si l'API est absente.
import { initVitals } from './lib/vitals'

// Applique la préférence de thème/densité avant le rendu (aucun flash). Inerte
// pour les écrans existants (couleurs en dur, aucun `dark:` utilisé).
initTheme()
initVitals()

// VX189(d) — avertisseur DEV-ONLY des Long Animation Frames (jank thread
// principal). `import()` DYNAMIQUE derrière `import.meta.env.DEV` (jamais un
// import statique) : Vite inline la constante à `false` en build prod, ce qui
// rend la branche entière (et l'import qu'elle contient) morte — Rollup
// l'élimine, aucun chunk devPerfWarn.js n'existe dans le build prod.
if (import.meta.env.DEV) {
  import('./lib/devPerfWarn').then((m) => m.installDevPerfWarn())
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Provider store={store}>
      <I18nProvider>
        <ThemeProvider>
          <ConfirmProvider>
            <SessionProvider>
              <RouterProvider router={router} />
            </SessionProvider>
          </ConfirmProvider>
          <Toaster />
          <PwaPrompts />
          <WelcomeMoment />
        </ThemeProvider>
      </I18nProvider>
    </Provider>
  </StrictMode>,
)
