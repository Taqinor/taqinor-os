import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

// Neutralise les dépendances réseau / contexte manquant (même liste que
// Layout.test.jsx) pour isoler le comportement SCA24 (fetch + application du
// TenantTheme) sans dépendre du reste du shell.
vi.mock('./Sidebar', () => ({ default: () => <div className="sidebar" /> }))
vi.mock('./Header', () => ({ default: () => <header className="header" /> }))
vi.mock('./BottomTabBar', () => ({ default: () => null }))
vi.mock('../../features/ia/CopilotPanel', () => ({ default: () => null }))
// NTIDE9/NTIDE37 — même neutralisation que Layout.test.jsx (voir ce fichier).
vi.mock('../../features/innovation/SuggestionCTA', () => ({ default: () => null }))
vi.mock('../../features/innovation/FeedbackButton', () => ({ default: () => null }))
vi.mock('../../ui/OfflineState', () => ({ OfflineBanner: () => null }))
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigation: () => ({ state: 'idle' }),
}))

const getCourant = vi.fn()
vi.mock('../../api/coreApi', () => ({
  default: { theme: { getCourant: (...args) => getCourant(...args) } },
}))

import Layout from './Layout'
import { getCurrentTenantTheme, resetTenantTheme, TENANT_THEME_VARS } from '../../design/tenantTheme'

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

function renderLayout() {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter>
        <Layout><p>content</p></Layout>
      </MemoryRouter>
    </Provider>,
  )
}

/* SCA24 — Layout est l'UNIQUE lecteur réseau du TenantTheme (core/theme/courant/,
   endpoint EXISTANT, zéro backend touché) ; il republie via le pub/sub de
   design/tenantTheme.js, consommé par Header sans refetch. */
describe('Layout — SCA24 application du TenantTheme', () => {
  afterEach(() => {
    getCourant.mockReset()
    resetTenantTheme()
    document.documentElement.style.removeProperty(TENANT_THEME_VARS.primary)
    document.documentElement.style.removeProperty(TENANT_THEME_VARS.logo)
  })

  it('cas appliqué : un thème renseigné pose les variables CSS + le pub/sub', async () => {
    getCourant.mockResolvedValue({
      data: { couleur_primaire: '#1a3b8c', logo_url: '/media/logo.png', nom_affichage: 'ACME' },
    })
    renderLayout()
    await waitFor(() => {
      expect(document.documentElement.style.getPropertyValue(TENANT_THEME_VARS.primary)).toBe('#1a3b8c')
    })
    expect(getCurrentTenantTheme().nomAffichage).toBe('ACME')
  })

  it('cas repli neutre : réponse vide (aucun thème configuré) → aucune variable posée', async () => {
    getCourant.mockResolvedValue({
      data: { logo_url: '', couleur_primaire: '', couleur_secondaire: '', nom_affichage: '' },
    })
    renderLayout()
    await waitFor(() => expect(getCourant).toHaveBeenCalled())
    expect(document.documentElement.style.getPropertyValue(TENANT_THEME_VARS.primary)).toBe('')
    expect(getCurrentTenantTheme().nomAffichage).toBe('')
  })

  it('cas résilient : l’échec réseau/permission ne casse jamais le rendu, repli neutre appliqué', async () => {
    getCourant.mockRejectedValue(new Error('403 Forbidden'))
    const { container } = renderLayout()
    await waitFor(() => expect(getCourant).toHaveBeenCalled())
    // Le shell reste rendu normalement malgré l'échec.
    expect(container.querySelector('.layout')).toBeInTheDocument()
    expect(document.documentElement.style.getPropertyValue(TENANT_THEME_VARS.primary)).toBe('')
  })
})
