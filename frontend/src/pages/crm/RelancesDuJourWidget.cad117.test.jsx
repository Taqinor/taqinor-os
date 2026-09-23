import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* CAD117 — « X leads sans cadence » : compteur cliquable à côté des
   relances du jour, qui ouvre la liste servie par `kpi_adherence.
   leads_sans_touche` (même sélecteur que `AdherenceRelancesPanel.jsx`,
   jamais recompté ici). Lecture seule : aucun démarrage de cadence en masse
   depuis ce compteur. Charge utile = l'exemple COMMITTÉ
   (`apps/crm/contract_samples/kpi_adherence.json`, PACT10). */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const KPI = exempleContrat('crm', 'kpi_adherence')
const LEAD_SANS_CADENCE = KPI.leads_sans_touche[0]

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesDues: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
    getKpiAdherence: vi.fn(),
    marquerRelanceEtapeFait: vi.fn(),
    marquerRelanceEtapeSautee: vi.fn(),
    reporterRelanceEtape: vi.fn(),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import RelancesDuJourWidget from './RelancesDuJourWidget'

beforeEach(() => {
  crmApi.getKpiAdherence.mockResolvedValue(reponseContrat('crm', 'kpi_adherence'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <RelancesDuJourWidget />
    </MemoryRouter>,
  )
}

describe('RelancesDuJourWidget — CAD117 « X leads sans cadence »', () => {
  it('le compteur apparaît dès qu\'un lead est sans touche, et lit kpi-adherence (jours=30)', async () => {
    mount()
    await waitFor(() => expect(crmApi.getKpiAdherence).toHaveBeenCalledWith({ jours: 30 }))
    expect(await screen.findByTestId('cad117-sans-cadence')).toBeInTheDocument()
    expect(screen.getByText('1 lead sans cadence')).toBeInTheDocument()
  })

  it('cliquer le compteur ouvre la liste correspondante, en lecture seule', async () => {
    mount()
    await screen.findByTestId('cad117-sans-cadence')
    // Repliée par défaut : le nom du lead sans cadence n'apparaît pas encore.
    expect(screen.queryByText(LEAD_SANS_CADENCE.nom)).not.toBeInTheDocument()

    fireEvent.click(screen.getByText('1 lead sans cadence'))
    expect(await screen.findByText(LEAD_SANS_CADENCE.nom)).toBeInTheDocument()
    expect(screen.getByText(new RegExp(LEAD_SANS_CADENCE.ville))).toBeInTheDocument()
    // Garde-fou : aucun bouton de démarrage de cadence en masse sur cette liste.
    expect(screen.queryByRole('button', { name: /relancer|initialiser/i })).not.toBeInTheDocument()
  })

  it('aucun compteur quand tous les leads ont une touche (leads_sans_touche vide)', async () => {
    // Même exemple COMMITTÉ, `leads_sans_touche` vidé — aucune variante
    // « exemple_vide » n'existe pour ce contrat (contrairement à
    // `relance_etape_v2`) : on ne change que ce SEUL champ, jamais la forme.
    crmApi.getKpiAdherence.mockResolvedValue({ data: { ...KPI, leads_sans_touche: [] } })
    mount()
    await waitFor(() => expect(crmApi.getKpiAdherence).toHaveBeenCalled())
    expect(screen.queryByTestId('cad117-sans-cadence')).not.toBeInTheDocument()
  })

  it('crmApi.getKpiAdherence absente du mock (suites existantes) : repli silencieux, jamais un plantage', async () => {
    const original = crmApi.getKpiAdherence
    delete crmApi.getKpiAdherence
    expect(() => mount()).not.toThrow()
    await waitFor(() => expect(screen.getByTestId('relances-du-jour-widget')).toBeInTheDocument())
    expect(screen.queryByTestId('cad117-sans-cadence')).not.toBeInTheDocument()
    crmApi.getKpiAdherence = original
  })
})
