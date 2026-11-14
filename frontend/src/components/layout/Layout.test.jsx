import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

// Neutralise les dépendances réseau / contexte manquant.
vi.mock('./Sidebar', () => ({ default: () => <div className="sidebar" /> }))
vi.mock('./Header', () => ({ default: () => <header className="header" /> }))
vi.mock('./BottomTabBar', () => ({ default: () => null }))
vi.mock('../../features/ia/CopilotPanel', () => ({ default: () => null }))
// NTIDE9/NTIDE37 — les deux CTA innovation ont quitté la coquille Layout le
// 2026-08-04 (ordre fondateur) : leur porte est le menu profil du Header, plus
// aucun mock à neutraliser ici.
vi.mock('../../ui/OfflineState', () => ({ OfflineBanner: () => null }))
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigation: () => ({ state: 'idle' }),
}))
// ADRG122 — seule la lecture de la tournée est observée ; le reste du client
// d'API reste le vrai.
vi.mock('../../api/installationsApi', async (orig) => {
  const reel = (await orig()).default
  return { default: { ...reel, getMaTournee: vi.fn() } }
})

import Layout from './Layout'
import * as LayoutModule from './Layout'
import installationsApi from '../../api/installationsApi'
import { todayLocalIso } from '../../lib/dateLocale'

// Store minimal (`auth` : droits du compte connecté, compte hérité par défaut).
function makeStore(auth = {}) {
  const session = { isAuthenticated: true, user: { username: 'u' }, ...auth }
  return configureStore({
    reducer: {
      auth: (s = session) => s,
      parametres: (s = { profile: {} }) => s,
      // VX57 — Layout lit désormais s.ia.copilotOpen (mount paresseux du copilote).
      ia: (s = { copilotOpen: false }) => s,
    },
  })
}

function renderLayout(children = <p>content</p>, auth) {
  return render(
    <Provider store={makeStore(auth)}>
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

/* ODY33 — UNE seule coquille : plus de kill-switch VITE_APPS_SHELL ni de
   chemin legacy ; Layout monte toujours Sidebar + Header (mode Apps). */
describe('Layout — coquille unique (ODY33)', () => {
  it("n'exporte plus le flag APPS_SHELL_ENABLED", () => {
    expect('APPS_SHELL_ENABLED' in LayoutModule).toBe(false)
  })

  it('monte toujours la Sidebar et le Header de la coquille', () => {
    const { container } = renderLayout(<p>sentinel-ody33</p>)
    expect(container.querySelector('.sidebar')).not.toBeNull()
    expect(container.querySelector('header.header')).not.toBeNull()
  })
})

/* ADRG122 — la coquille de tout écran connecté (dont l'accueil `/apps`) monte
   le pré-chargement matinal de la tournée : il ne part que pour un compte
   auquel le serveur sert `ma-tournee` (lecture du module chantiers). */
describe('Layout — pré-chargement de la tournée selon le droit (ADRG122)', () => {
  const MATIN = new Date(2026, 10, 14, 8, 30)
  // Profils tels que `/auth/me/` les sert (`portee` comprise).
  const COMMERCIAL = {
    user: { username: 'co', portee: 'interne' }, role: 'normal', role_nom: 'Commercial',
    permissions: ['crm_voir', 'crm_creer', 'ventes_voir', 'ventes_creer', 'sav_voir'],
  }
  const TECHNICIEN = {
    user: { username: 'te', portee: 'interne' }, role: 'normal', role_nom: 'Technicien',
    permissions: ['installation_voir', 'installation_gerer', 'intervention_gerer', 'sav_voir'],
  }

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(MATIN)
    window.localStorage.clear()
    installationsApi.getMaTournee.mockReset()
    installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [] } })
  })
  afterEach(() => { vi.useRealTimers() })

  it('Technicien, le matin : la tournée du jour est toujours pré-chargée', async () => {
    renderLayout(<p>accueil</p>, TECHNICIEN)
    await waitFor(() => expect(installationsApi.getMaTournee).toHaveBeenCalledTimes(1))
    expect(installationsApi.getMaTournee)
      .toHaveBeenCalledWith(todayLocalIso(MATIN), { suppressErrorToast: true })
  })

  it('Commercial, le matin : `ma-tournee` n’est jamais demandé', async () => {
    const { findByText } = renderLayout(<p>accueil</p>, COMMERCIAL)
    expect(await findByText('accueil')).toBeInTheDocument()
    expect(installationsApi.getMaTournee).not.toHaveBeenCalled()
  })

  it('état posé par la connexion, profil pas encore servi par `/auth/me/` : rien ne part', async () => {
    // `setCredentials` après `/token/` (Login, fenêtre de session expirée) : même pour un Technicien.
    const { findByText } = renderLayout(<p>accueil</p>,
      { user: { username: 'te' }, role: 'normal', role_nom: null, permissions: [] })
    expect(await findByText('accueil')).toBeInTheDocument()
    expect(installationsApi.getMaTournee).not.toHaveBeenCalled()
  })

  it('session fermée : rien ne part, même avec un profil resté en mémoire', async () => {
    const { findByText } = renderLayout(<p>accueil</p>, { ...TECHNICIEN, isAuthenticated: false })
    expect(await findByText('accueil')).toBeInTheDocument()
    expect(installationsApi.getMaTournee).not.toHaveBeenCalled()
  })
})
