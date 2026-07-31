import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   WIR107 — les deux écrans qui rendent enfin pilotables les sous-ensembles
   comptables avancés : le cockpit de clôture (NTFIN26-34) et les écritures
   récurrentes (XACC8). Avant, les endpoints existaient (ou manquaient) sans
   aucun client ni page — donc INATTEIGNABLES depuis l'ERP.
   Tests : (1) le module déclare bien les deux routes/entrées de nav ;
   (2) rendu smoke de chaque page, API mockée (aucun réseau).
   ========================================================================== */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const vide = () => Promise.resolve({ data: { results: [] } })
const res = () => ({
  list: vide, get: vide, create: vide, update: vide, remove: vide,
})

vi.mock('../../api/comptaApi', () => ({
  default: {
    downloadBlob: vi.fn(),
    comptes: res(),
    journaux: res(),
    periodes: { ...res(), cloturer: vide, rouvrir: vide },
    modelesCloture: { ...res(), seed: vide },
    instancesCloture: { ...res(), instancier: vide },
    tachesCloture: { ...res(), cocher: vide, genererOd: vide },
    accrualsCloture: { ...res(), poster: vide },
    justificationsVariation: res(),
    modelesEcriture: { ...res(), generer: vide },
    lignesModeleEcriture: res(),
    abonnementsEcriture: { ...res(), genererDues: vide },
  },
}))

function mount(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('WIR107 — enregistrement des deux écrans dans le module compta', () => {
  it('déclare les routes /comptabilite/cloture et /comptabilite/ecritures-recurrentes', async () => {
    const { default: config } = await import('./module.config.jsx')
    const chemins = config.routes.map((r) => r.path)
    expect(chemins).toContain('/comptabilite/cloture')
    expect(chemins).toContain('/comptabilite/ecritures-recurrentes')
  })

  it('expose les deux entrées de navigation, gatées responsable/admin', async () => {
    const { default: config } = await import('./module.config.jsx')
    const cloture = config.nav.items.find((i) => i.to === '/comptabilite/cloture')
    const recurrentes = config.nav.items.find(
      (i) => i.to === '/comptabilite/ecritures-recurrentes')
    expect(cloture).toBeTruthy()
    expect(recurrentes).toBeTruthy()
    expect(cloture.roles).toEqual(['responsable', 'admin'])
    expect(recurrentes.roles).toEqual(['responsable', 'admin'])
  })

  it('résout le titre « écritures récurrentes » AVANT celui des écritures', async () => {
    const { default: config } = await import('./module.config.jsx')
    const idxRec = config.titles.findIndex(
      ([p]) => p === '/comptabilite/ecritures-recurrentes')
    const idxEcr = config.titles.findIndex(([p]) => p === '/comptabilite/ecritures')
    expect(idxRec).toBeGreaterThanOrEqual(0)
    expect(idxRec).toBeLessThan(idxEcr)
  })
})

describe('CloturePage — rendu smoke (NTFIN26-34)', () => {
  it('affiche le cockpit de clôture et son onglet checklist', async () => {
    const { default: CloturePage } = await import('./pages/CloturePage.jsx')
    mount(<CloturePage />)
    expect(await screen.findByRole('heading', { name: /Cockpit de clôture/ }))
      .toBeInTheDocument()
    expect(screen.getByLabelText('Période comptable')).toBeInTheDocument()
  }, 30000)
})

describe('EcrituresRecurrentesPage — rendu smoke (XACC8)', () => {
  it('affiche l’écran des écritures récurrentes', async () => {
    const { default: Page } = await import('./pages/EcrituresRecurrentesPage.jsx')
    mount(<Page />)
    expect(await screen.findByRole('heading', { name: /Écritures récurrentes/ }))
      .toBeInTheDocument()
  }, 30000)
})
