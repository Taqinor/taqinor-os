import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* CAD50 — « Annuler »/« Arrêter » n'existaient auparavant que sur la fiche
   du lead. Ce cockpit ne sert que des touches `a_faire` (jamais fait/
   sautée) : « Arrêter la cadence » se pose donc sur chaque ligne, tandis
   que « Annuler » (retour arrière 24h) ne concerne QUE la touche que
   Meryem vient de traiter dans la session en cours (`justeTraitees`).
   Charge utile = l'exemple COMMITTÉ (`relance_etape_v2.json`, PACT10). */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const ETAPES = exempleContrat('crm', 'relance_etape_v2').results
const PREMIERE = ETAPES[0]

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesDues: vi.fn(),
    getKpiAdherence: vi.fn(() => Promise.resolve({ data: { leads_sans_touche: [] } })),
    marquerRelanceEtapeFait: vi.fn(() => Promise.resolve({ data: { statut: 'fait' } })),
    marquerRelanceEtapeSautee: vi.fn(() => Promise.resolve({ data: { statut: 'sautee' } })),
    reporterRelanceEtape: vi.fn(),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
    annulerRelanceEtape: vi.fn(),
    arreterCadence: vi.fn(),
  },
}))
vi.mock('../../lib/toast', () => ({ toastError: vi.fn() }))

import crmApi from '../../api/crmApi'
import RelancesDuJourWidget from './RelancesDuJourWidget'

beforeEach(() => {
  crmApi.getRelanceEtapesDues.mockResolvedValue({ data: { count: 1, results: [PREMIERE] } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <RelancesDuJourWidget />
    </MemoryRouter>,
  )
}

describe('RelancesDuJourWidget — CAD50 (« Annuler »/« Arrêter » hors fiche)', () => {
  it('« Arrêter la cadence » ouvre la saisie du motif, exige un motif, puis appelle crmApi.arreterCadence(leadId, {motif})', async () => {
    crmApi.arreterCadence.mockResolvedValue({ data: { arretees: 1 } })
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Arrêter la cadence' }))
    const confirmer = screen.getByRole('button', { name: 'Confirmer' })
    expect(confirmer).toBeDisabled()

    fireEvent.change(screen.getByTestId('cad50-arreter-motif'), { target: { value: 'Client injoignable' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))

    await waitFor(() => expect(crmApi.arreterCadence).toHaveBeenCalledWith(
      PREMIERE.lead, { motif: 'Client injoignable' },
    ))
    // Referme sur succès.
    await waitFor(() => expect(screen.queryByTestId('cad50-arreter-motif')).not.toBeInTheDocument())
  })

  it('une touche marquée « Fait » quitte la liste et rejoint « Annuler », qui appelle crmApi.annulerRelanceEtape', async () => {
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Client joint' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(crmApi.marquerRelanceEtapeFait).toHaveBeenCalled())

    // La liste principale (RelanceEtapeRow) l'a retirée, mais elle réapparaît
    // dans le bloc « Annuler » (même lead, même touche).
    const listeAnnuler = await screen.findByTestId('cad50-annuler-liste')
    expect(listeAnnuler).toHaveTextContent(PREMIERE.lead_nom)

    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(crmApi.annulerRelanceEtape).toHaveBeenCalledWith(PREMIERE.id))
    await waitFor(() => expect(screen.queryByTestId('cad50-annuler-liste')).not.toBeInTheDocument())
  })
})
