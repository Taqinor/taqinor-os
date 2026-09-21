// WIR171 — Gating d'écran : un module dont la garde serveur suit
// `HasPermissionOrLegacy` (repli légacy palier responsable/admin, YRBAC3) ne
// doit jamais rester invisible à un rôle FIN qui porte la permission fine
// mais relève d'un palier de menu plus bas. SOLMVP40 (21/09/2026) a sorti du
// produit les cinq modules qui servaient jusque-là d'exemples à ce test
// (litiges/contrats/qhse/gestion_projet/kb, cf. frontend/parked/README.md) ;
// `visites` (VT2/VTA4) est aujourd'hui le SEUL module du MVP solaire dont le
// `module.config.jsx` déclare `permRepliPalier: true`
// (`features/visites/module.config.jsx` — vérifié : aucun autre module gardé
// ne porte `perm`/`permRepliPalier` à part `reporting`/`parametres`, qui sont
// justement l'exemple ET-STRICT sans repli couvert plus bas). C'est donc le
// seul cas réel restant pour prouver la sémantique serveur de bout en bout
// via la Sidebar et le lanceur d'apps.
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import Sidebar from './Sidebar'
import { moduleConfigs } from '../../router/moduleRoutes'
import { buildInstalledApps } from '../../lib/apps/useInstalledApps'

function makeStore({ role = 'normal', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions, modulesDesactives, user: null }) => s,
      parametres: (s = { profile: { nom: 'TAQINOR' } }) => s,
    },
  })
}

function renderSidebar({ path, ...opts }) {
  return render(
    <Provider store={makeStore(opts)}>
      <MemoryRouter initialEntries={[path]}>
        <Sidebar collapsed={false} onToggle={() => {}} onNavigate={() => {}} />
      </MemoryRouter>
    </Provider>,
  )
}

const navHrefs = (container) =>
  Array.from(container.querySelectorAll('.sidebar-nav a')).map((a) => a.getAttribute('href'))

// Extrait RÉEL de `COMMERCIAL_PERMISSIONS`
// (backend/django_core/apps/roles/models.py) : palier de menu 'normal'
// (authentication/role_tiers.py — le nom n'est pas un rôle système
// responsable) et pourtant porteur de `visites_voir` (VT2 : le commercial
// terrain remplit la visite, sans jamais se donner `visites_valider`).
const COMMERCIAL = ['crm_voir', 'crm_creer', 'ventes_voir', 'stock_voir', 'visites_voir']

describe('WIR171 — le seul module MVP solaire à repli légacy suit la sémantique serveur', () => {
  it('un Commercial (palier normal + visites_voir) voit la coquille « visites »', () => {
    const { container } = renderSidebar({ path: '/visites', role: 'normal', permissions: COMMERCIAL })
    expect(navHrefs(container)).toContain('/visites')
  })

  it('un rôle fin de palier normal portant SEULEMENT visites_voir voit aussi « visites »', () => {
    const { container } = renderSidebar({ path: '/visites', role: 'normal', permissions: ['visites_voir'] })
    expect(navHrefs(container)).toContain('/visites')
  })

  it('un rôle FIN de palier normal SANS la permission reste dehors sur « visites »', () => {
    const { container } = renderSidebar({
      path: '/visites', role: 'normal', permissions: ['crm_voir', 'ventes_voir'],
    })
    expect(navHrefs(container)).not.toContain('/visites')
  })

  it('compte LÉGACY responsable (aucune permission servie) : « visites » inchangé', () => {
    const { container } = renderSidebar({ path: '/visites', role: 'responsable', permissions: [] })
    expect(navHrefs(container)).toContain('/visites')
  })

  it('compte LÉGACY de palier normal : « visites » reste refusé (miroir is_responsable)', () => {
    const { container } = renderSidebar({ path: '/visites', role: 'normal', permissions: [] })
    expect(navHrefs(container)).not.toContain('/visites')
  })

  it('l’app « visites » apparaît au lanceur d’apps d’un Commercial', () => {
    const apps = buildInstalledApps(moduleConfigs, { role: 'normal', permissions: COMMERCIAL })
    expect(apps.map((a) => a.key)).toContain('visites')
  })

  it('…et pas au lanceur d’un rôle fin dépourvu de visites_voir', () => {
    const apps = buildInstalledApps(moduleConfigs, {
      role: 'normal', permissions: ['crm_voir', 'ventes_voir'],
    })
    expect(apps.map((a) => a.key)).not.toContain('visites')
  })

  it('le Journal d’activité garde son ET STRICT (aucun repli légacy)', () => {
    // CanViewActivityLog exclut délibérément l'admin légacy sans rôle fin :
    // le relâchement WIR171 ne doit PAS déborder sur cette entrée.
    const legacyAdmin = buildInstalledApps(moduleConfigs, { role: 'admin', permissions: [] })
    const reporting = legacyAdmin.find((a) => a.key === 'reporting')
    // L'app reste visible par ses autres écrans, mais jamais via /journal.
    if (reporting) expect(reporting.to).not.toBe('/journal')
    const { container } = renderSidebar({ path: '/journal', role: 'admin', permissions: [] })
    expect(navHrefs(container)).not.toContain('/journal')
  })
})
