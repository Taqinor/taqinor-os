// WIR171 — Gating d'écran : litiges / contrats / qhse / projets / kb étaient
// INVISIBLES pour un Commercial, un Technicien ou un Viewer alors que le
// serveur leur répond 200 (garde `HasPermissionOrLegacy` sur `<app>_voir`,
// YRBAC3). La coquille applique désormais la sémantique serveur.
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

// Extrait RÉEL du preset « Commercial » (apps/roles/models.py) : palier de menu
// 'normal' (authentication/role_tiers.py — le nom n'est pas un rôle système
// responsable) et pourtant porteur des cinq permissions de lecture.
const COMMERCIAL = [
  'crm_voir', 'crm_creer', 'ventes_voir', 'stock_voir',
  'qhse_voir', 'qhse_gerer',
  'projet_voir', 'projet_gerer',
  'contrat_voir', 'contrat_gerer',
  'litige_voir', 'litige_gerer',
  'kb_voir', 'kb_gerer',
]

// Preset « Viewer » : lecture seule, aucun `_gerer`.
const VIEWER = [
  'stock_voir', 'crm_voir', 'ventes_voir',
  'qhse_voir', 'projet_voir', 'contrat_voir', 'litige_voir', 'kb_voir',
]

const CAS = [
  { cle: 'litiges', path: '/litiges', lien: '/litiges' },
  { cle: 'contrats', path: '/contrats', lien: '/contrats' },
  { cle: 'qhse', path: '/qhse', lien: '/qhse' },
  { cle: 'gestion_projet', path: '/projets', lien: '/projets' },
  { cle: 'kb', path: '/kb', lien: '/kb' },
]

describe('WIR171 — les 5 modules suivent la sémantique serveur', () => {
  CAS.forEach(({ cle, path, lien }) => {
    it(`un Commercial (palier normal + <app>_voir) voit la coquille « ${cle} »`, () => {
      const { container } = renderSidebar({ path, role: 'normal', permissions: COMMERCIAL })
      expect(navHrefs(container)).toContain(lien)
    })

    it(`un Viewer (lecture seule) voit aussi « ${cle} »`, () => {
      const { container } = renderSidebar({ path, role: 'normal', permissions: VIEWER })
      expect(navHrefs(container)).toContain(lien)
    })

    it(`un rôle FIN de palier normal SANS la permission reste dehors sur « ${cle} »`, () => {
      const { container } = renderSidebar({
        path, role: 'normal', permissions: ['crm_voir', 'ventes_voir'],
      })
      expect(navHrefs(container)).not.toContain(lien)
    })

    it(`compte LÉGACY responsable (aucune permission servie) : « ${cle} » inchangé`, () => {
      const { container } = renderSidebar({ path, role: 'responsable', permissions: [] })
      expect(navHrefs(container)).toContain(lien)
    })

    it(`compte LÉGACY de palier normal : « ${cle} » reste refusé (miroir is_responsable)`, () => {
      const { container } = renderSidebar({ path, role: 'normal', permissions: [] })
      expect(navHrefs(container)).not.toContain(lien)
    })
  })

  it('les 5 apps apparaissent au lanceur d’apps d’un Commercial', () => {
    const apps = buildInstalledApps(moduleConfigs, { role: 'normal', permissions: COMMERCIAL })
    const cles = apps.map((a) => a.key)
    CAS.forEach(({ cle }) => expect(cles).toContain(cle))
  })

  it('…et pas au lanceur d’un rôle fin dépourvu de ces permissions', () => {
    const apps = buildInstalledApps(moduleConfigs, {
      role: 'normal', permissions: ['crm_voir', 'ventes_voir'],
    })
    const cles = apps.map((a) => a.key)
    CAS.forEach(({ cle }) => expect(cles).not.toContain(cle))
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
