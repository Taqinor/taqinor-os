// MRY15 — frise de cadence de la fiche lead : TOUTES les étapes du lead
// (tous statuts, toutes cadences), depuis le contrat committé
// `apps/crm/contract_samples/relance_etape_v2.json` (PACT10) filtré côté
// `crmApi.getRelanceEtapesLead` (jamais un objet retapé à la main).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'

const ETAPES = exempleContrat('crm', 'relance_etape_v2').results

vi.mock('../../../../api/crmApi', () => ({
  default: {
    getRelanceEtapesLead: vi.fn(),
  },
}))

import crmApi from '../../../../api/crmApi'
import CadenceFrise from './CadenceFrise'

beforeEach(() => {
  crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { count: ETAPES.length, results: ETAPES } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('MRY15 CadenceFrise', () => {
  it('charge la frise du lead avec ?lead=<id>&scope=lead', async () => {
    render(<CadenceFrise leadId={1489} />)
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledWith(1489))
    expect(await screen.findByText(ETAPES[0].libelle)).toBeInTheDocument()
    expect(screen.getByText(ETAPES[1].libelle)).toBeInTheDocument()
    expect(screen.getAllByTestId('cadence-frise-etape')).toHaveLength(2)
  })

  it('rien à afficher quand le lead n\'a pas de cadence', async () => {
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { count: 0, results: [] } })
    render(<CadenceFrise leadId={1} />)
    expect(await screen.findByText(/Aucune cadence sur ce lead/)).toBeInTheDocument()
  })

  it('ne charge rien sans leadId (mode création)', () => {
    render(<CadenceFrise leadId={null} />)
    expect(crmApi.getRelanceEtapesLead).not.toHaveBeenCalled()
  })

  it('recharge quand reloadToken change (après Relancer/Arrêter la cadence)', async () => {
    const { rerender } = render(<CadenceFrise leadId={1489} reloadToken={0} />)
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledTimes(1))
    rerender(<CadenceFrise leadId={1489} reloadToken={1} />)
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledTimes(2))
  })

  it('affiche un état d\'erreur si le serveur échoue', async () => {
    crmApi.getRelanceEtapesLead.mockRejectedValue(new Error('boom'))
    render(<CadenceFrise leadId={1489} />)
    expect(await screen.findByText(/Frise de cadence indisponible/)).toBeInTheDocument()
  })
})
