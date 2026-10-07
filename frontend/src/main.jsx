import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Provider } from 'react-redux'
import { RouterProvider } from 'react-router-dom'
import { store } from './store'
import router from './router'
// ADOC146 — composants globaux montés HORS du RouterProvider (Toaster, PWA,
// message d'accueil, moment d'accueil, langue serveur) : UNE liste, dans
// components/ShellGlobal.jsx, balayée par un test pour chaque portée portail.
import ShellGlobal from './components/ShellGlobal'
import { ThemeProvider } from './design/ThemeProvider'
import { initTheme } from './design/theme'
// Providers UX globaux (lane BEHAVIORS). ConfirmProvider + SessionProvider sont
// indépendants du routeur → montés ici, autour du RouterProvider. (La palette ⌘K
// et les raccourcis, qui ont besoin du contexte routeur, sont montés DANS le
// router, cf. router/index.jsx → WithLayout ; le Toaster vit dans ShellGlobal.)
import { ConfirmProvider } from './providers/ConfirmProvider'
import { SessionProvider } from './providers/SessionProvider'
// N93 — cadre i18n (langue d'interface + RTL). Monté HAUT dans l'arbre pour
// que toutes les routes disposent de `t()` / de la locale. FR par défaut.
import { I18nProvider } from './i18n'
// NTI18N2 — propage `dir` aux primitives Radix (Tabs/DropdownMenu/…), voir
// le commentaire du fichier. Fichier PARTAGÉ (main.jsx) : ajout additif
// minimal (un import + un wrap), signalé au fold.
import RtlDirectionProvider from './i18n/RtlDirectionProvider'
import './index.css'
// VX61 — capture Web Vitals RÉELS terrain (INP/LCP/CLS/TTFB), hand-roll
// PerformanceObserver, no-op total si l'API est absente.
import { initVitals } from './lib/vitals'
// VX206 — socle local d'observabilité : promesses rejetées / erreurs non
// gérées hors du rendu React (event handlers, `.then()`, outbox…).
import { installGlobalErrors } from './lib/globalErrors'
// QAH8 — Sentry armé AU DÉMARRAGE (no-op total sans VITE_SENTRY_DSN) + tag
// `company` qui suit l'utilisateur connecté, comme core.monitoring côté Django.
import { initMonitoring, suivreSocieteDuStore } from './lib/monitoring'

// Applique la préférence de thème/densité avant le rendu (aucun flash). Inerte
// pour les écrans existants (couleurs en dur, aucun `dark:` utilisé).
initTheme()
initVitals({ isAuthenticated: () => Boolean(store.getState().auth?.isAuthenticated) })
installGlobalErrors()
initMonitoring().catch(() => {})
suivreSocieteDuStore(store)

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
      <I18nProvider chargerSurcharges={false}>
        <RtlDirectionProvider>
          <ThemeProvider>
            <ConfirmProvider>
              <SessionProvider>
                <RouterProvider router={router} />
              </SessionProvider>
            </ConfirmProvider>
            <ShellGlobal />
          </ThemeProvider>
        </RtlDirectionProvider>
      </I18nProvider>
    </Provider>
  </StrictMode>,
)
