import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* WIR215/XPUR21 — page PUBLIQUE /rfq/:token (aucun login) : le lien envoyé au
   fournisseur menait à l'ENDPOINT JSON. Couvre :
   (1) le GET remplit la page et pré-remplit l'offre déjà soumise ;
   (2) la soumission POSTe l'offre sur le même jeton (re-soumission = mise à
       jour de LA MÊME offre, jamais une seconde) ;
   (3) un jeton invalide donne un message FRANÇAIS, jamais du JSON ;
   (4) une RFQ clôturée est en LECTURE SEULE. */

const axiosMock = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: axiosMock }))

import RfqReponsePubliquePage from './RfqReponsePubliquePage'

const PAYLOAD = {
  reference: 'RFQ-2607-0003',
  objet: 'Panneaux 450W',
  date_limite_reponse: '2026-08-30',
  fournisseur_nom: 'SolarImport',
  cloturee: false,
  offre: null,
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/rfq/JETON123']}>
      <Routes>
        <Route path="/rfq/:token" element={<RfqReponsePubliquePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  axiosMock.get.mockResolvedValue({ data: PAYLOAD })
  axiosMock.post.mockResolvedValue({ data: { ...PAYLOAD, offre: { montant_ht: '125000' } } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RfqReponsePubliquePage — WIR215', () => {
  it('charge la demande de prix depuis le jeton et affiche le formulaire', async () => {
    renderPage()
    await waitFor(() => expect(axiosMock.get).toHaveBeenCalledWith(
      '/public/installations/rfq/JETON123/'))
    expect(await screen.findByText(/RFQ-2607-0003/)).toBeInTheDocument()
    expect(screen.getByText('Panneaux 450W')).toBeInTheDocument()
    expect(screen.getByLabelText('Montant HT proposé')).toBeInTheDocument()
  })

  it('soumet l’offre sur le MÊME jeton et confirme en français', async () => {
    const user = userEvent.setup()
    renderPage()
    const montant = await screen.findByLabelText('Montant HT proposé')
    await user.type(montant, '125000')
    await user.type(screen.getByLabelText('Délai de livraison (jours)'), '21')
    await user.type(screen.getByLabelText('Validité de l’offre (jours)'), '30')
    await user.click(screen.getByRole('button', { name: 'Envoyer mon offre' }))

    await waitFor(() => expect(axiosMock.post).toHaveBeenCalledWith(
      '/public/installations/rfq/JETON123/',
      { montant_ht: '125000', delai_jours: '21', validite_jours: '30', note: '' },
    ))
    expect(await screen.findByRole('status')).toHaveTextContent(/offre a bien été enregistrée/)
  })

  it('pré-remplit une offre déjà soumise (re-soumission = correction)', async () => {
    axiosMock.get.mockResolvedValue({
      data: {
        ...PAYLOAD,
        offre: { montant_ht: '99000', delai_jours: 14, validite_jours: 45, note: 'Stock dispo' },
      },
    })
    renderPage()
    expect(await screen.findByLabelText('Montant HT proposé')).toHaveValue(99000)
    expect(screen.getByLabelText('Commentaire (optionnel)')).toHaveValue('Stock dispo')
  })

  it('jeton invalide → message FRANÇAIS, jamais du JSON', async () => {
    axiosMock.get.mockRejectedValue({ response: { status: 404, data: { detail: 'Lien invalide ou expiré.' } } })
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /introuvable, expiré ou révoqué/)
    expect(screen.queryByRole('button', { name: 'Envoyer mon offre' })).toBeNull()
  })

  it('RFQ clôturée → lecture seule, aucun formulaire', async () => {
    axiosMock.get.mockResolvedValue({
      data: { ...PAYLOAD, cloturee: true, offre: { montant_ht: '99000', delai_jours: 14, validite_jours: 45, note: '' } },
    })
    renderPage()
    expect(await screen.findByRole('status')).toHaveTextContent(/clôturée/)
    expect(screen.queryByRole('button', { name: 'Envoyer mon offre' })).toBeNull()
    expect(screen.getByTestId('rfq-offre-lecture')).toHaveTextContent('99000')
  })
})
