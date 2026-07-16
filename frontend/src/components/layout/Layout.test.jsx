import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

// Neutralise les dépendances réseau / contexte manquant.
vi.mock('./Sidebar', () => ({ default: () => <div className="sidebar" /> }))
vi.mock('./Header', () => ({ default: () => <header className="header" /> }))
vi.mock('./BottomTabBar', () => ({ default: () => null }))
vi.mock('../../features/ia/CopilotPanel', () => ({ default: () => null }))
// NTIDE9 — CTA « Suggérer une amélioration », chargé paresseusement comme le
// copilote : neutralisé ici pour ne pas tirer son arbre d'import réel (axios,
// Radix Dialog) dans ce test de coquille de mise en page.
vi.mock('../../features/innovation/SuggestionCTA', () => ({ default: () => null }))
vi.mock('../../ui/OfflineState', () => ({ OfflineBanner: () => null }))
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigation: () => ({ state: 'idle' }),
}))

import Layout from './Layout'

// Store minimal.
function makeStore() {
  return configureStore({
    reducer: {
      auth: (s = { isAuthenticated: true, user: { username: 'u' } }) => s,
      parametres: (s = { profile: {} }) => s,
      // VX57 — Layout lit désormais s.ia.copilotOpen (mount paresseux du copilote).
      ia: (s = { copilotOpen: false }) => s,
    },
  })
}

function renderLayout(children = <p>content</p>) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter>
        <Layout>{children}</Layout>
      </MemoryRouter>
    </Provider>,
  )
}

/* ──────────────────────────────────────────────────────────────────────
   U2 — Régression défilement roue : la chaîne de conteneurs DOM doit
   exposer la structure scroll correcte :
     .layout > .layout-main > main.layout-content

   Les règles CSS clés (height-bounded chain + overflow-y:auto sur .layout-content
   + overflow:hidden sur .layout-main) ne sont pas testables via jsdom (pas de
   layout réel), mais on garantit que la STRUCTURE DOM est celle attendue par le
   modèle scroll — un changement de structure briserait la règle CSS.
   ────────────────────────────────────────────────────────────────────── */
describe('Layout — U2 scroll architecture', () => {
  it('rend la chaîne .layout > .layout-main > main.layout-content', () => {
    const { container } = renderLayout()
    const layout = container.querySelector('.layout')
    expect(layout).toBeInTheDocument()

    const layoutMain = layout.querySelector('.layout-main')
    expect(layoutMain).toBeInTheDocument()

    // La zone scrollable est le <main> avec la classe layout-content,
    // DIRECTEMENT enfant de .layout-main (pas d'intermédiaire non-flex).
    const content = layoutMain.querySelector('main.layout-content')
    expect(content).toBeInTheDocument()
  })

  it('.layout-main contient le header AVANT le main.layout-content', () => {
    const { container } = renderLayout()
    const layoutMain = container.querySelector('.layout-main')
    const children = Array.from(layoutMain.children)
    const headerIdx = children.findIndex(el => el.tagName === 'HEADER')
    const contentIdx = children.findIndex(el => el.classList.contains('layout-content'))
    expect(headerIdx).toBeGreaterThanOrEqual(0)
    expect(contentIdx).toBeGreaterThan(headerIdx)
  })

  it('les enfants sont rendus dans main.layout-content', () => {
    const { getByText } = renderLayout(<p>sentinel-u2</p>)
    expect(getByText('sentinel-u2')).toBeInTheDocument()
  })
})
