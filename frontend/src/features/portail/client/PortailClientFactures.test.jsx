import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

/* AUD137 — une facture ANNULÉE (ou déjà PAYÉE) n'affiche plus « reste dû » ni
   le bouton « Payer » : l'écran lit désormais `payable` (jamais `!payee`
   seul), champ posé par `apps.ventes.selectors.factures_du_client_portail`
   côté serveur. La charge de la liste vient du contrat COMMITTÉ
   (`apps/portail/contract_samples/mes_factures_liste.json`, PACT10) — jamais
   un `PAYLOAD` réécrit à la main ici : si le serveur change de forme, ce test
   casse tout seul.

   Le contrat porte exactement TROIS factures : FAC-2026-0101 (émise,
   payable), FAC-2026-0102 (annulée, non payable) et FAC-2026-0100 (payée,
   non payable) — d'où les décomptes globaux « exactement UN bouton Payer »
   plutôt qu'un scoping DOM par carte. */

vi.mock('../../../api/portailApi', () => ({
  default: { factures: { liste: vi.fn(), payer: vi.fn() } },
}))

import portailApi from '../../../api/portailApi'
import PortailClientFactures from './PortailClientFactures.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPage() {
  return render(
    <MemoryRouter>
      <ThemeProvider><PortailClientFactures /></ThemeProvider>
    </MemoryRouter>,
  )
}

describe('PortailClientFactures — AUD137', () => {
  it('les trois factures du contrat committé sont toutes affichées', async () => {
    portailApi.factures.liste.mockResolvedValue(
      reponseContrat('portail', 'mes_factures_liste'))
    renderPage()

    await screen.findByText('FAC-2026-0101')
    expect(screen.getByText('FAC-2026-0102')).toBeInTheDocument()
    expect(screen.getByText('FAC-2026-0100')).toBeInTheDocument()
  })

  it('seule la facture payable (émise) montre « reste dû » et « Payer » — '
     + "l'annulée et la payée n'affichent ni l'un ni l'autre", async () => {
    portailApi.factures.liste.mockResolvedValue(
      reponseContrat('portail', 'mes_factures_liste'))
    renderPage()

    await screen.findByText('FAC-2026-0101')
    // Une seule facture `payable: true` dans le contrat -> exactement un
    // bouton et une mention « reste dû », jamais trois.
    expect(screen.getAllByRole('button', { name: /payer/i })).toHaveLength(1)
    expect(screen.getAllByText(/reste dû/i)).toHaveLength(1)
  })

  it('cliquer Payer appelle l’API avec l’id de la facture payable', async () => {
    portailApi.factures.liste.mockResolvedValue(
      reponseContrat('portail', 'mes_factures_liste'))
    portailApi.factures.payer.mockResolvedValue({
      data: {
        paiement_id: 1, reference: 'PF-AAAA', statut: 'initie',
        montant: '12000.00', paiement_en_ligne_actif: false,
        virement: { beneficiaire: '', banque: '', rib: '' },
      },
    })
    renderPage()

    await screen.findByText('FAC-2026-0101')
    screen.getByRole('button', { name: /payer/i }).click()
    await waitFor(() =>
      expect(portailApi.factures.payer).toHaveBeenCalledWith(101))
  })
})
