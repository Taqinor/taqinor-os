import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

/* WIR215/XPUR21 — le lien WhatsApp/email envoyé au fournisseur pointait sur
   l'endpoint JSON : le fournisseur recevait un objet brut. Cette page est la
   destination manquante.

   Charge utile alignée sur `_public_payload` (public_views.py) : reference,
   objet, date_limite_reponse, fournisseur_nom, cloturee, offre{montant_ht,
   delai_jours, validite_jours, note} — jamais une forme inventée, et jamais
   les autres offres ni un prix interne. */

vi.mock('../../api/installationsApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    rfqPublicApi: { get: vi.fn(), repondre: vi.fn() },
  }
})

import { rfqPublicApi } from '../../api/installationsApi'
import RfqReponsePubliquePage from './RfqReponsePubliquePage'

const PAYLOAD = {
  reference: 'RFQ-2026-07-0001', objet: 'Panneaux 550W',
  date_limite_reponse: '2026-08-01', fournisseur_nom: 'SolarImport',
  cloturee: false, offre: null,
}

const renderPage = () => render(
  <MemoryRouter initialEntries={['/rfq/tok-123']}>
    <Routes>
      <Route path="/rfq/:token" element={<RfqReponsePubliquePage />} />
    </Routes>
  </MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('RfqReponsePubliquePage (WIR215)', () => {
  it('affiche la demande et soumet une offre hors session', async () => {
    rfqPublicApi.get.mockResolvedValue({ data: PAYLOAD })
    rfqPublicApi.repondre.mockResolvedValue({
      data: { ...PAYLOAD, offre: { montant_ht: '12000', delai_jours: 15, validite_jours: 30, note: '' } },
    })
    renderPage()

    expect(await screen.findByText(/RFQ-2026-07-0001/)).toBeInTheDocument()
    expect(rfqPublicApi.get).toHaveBeenCalledWith('tok-123')
    expect(screen.getByText('Panneaux 550W')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/Votre montant HT/), { target: { value: '12000' } })
    fireEvent.change(screen.getByLabelText(/Délai de livraison/), { target: { value: '15' } })
    fireEvent.click(screen.getByRole('button', { name: /Envoyer mon offre/ }))

    await waitFor(() => expect(rfqPublicApi.repondre).toHaveBeenCalledTimes(1))
    expect(rfqPublicApi.repondre.mock.calls[0][0]).toBe('tok-123')
    expect(rfqPublicApi.repondre.mock.calls[0][1])
      .toMatchObject({ montant_ht: '12000', delai_jours: '15' })
    expect(await screen.findByRole('status')).toHaveTextContent(/bien été enregistrée/)
  })

  it('offre déjà soumise : le formulaire est pré-rempli et la re-soumission met à jour', async () => {
    rfqPublicApi.get.mockResolvedValue({
      data: {
        ...PAYLOAD,
        offre: { montant_ht: '9000', delai_jours: 10, validite_jours: 20, note: 'net' },
      },
    })
    rfqPublicApi.repondre.mockResolvedValue({ data: PAYLOAD })
    renderPage()

    const montant = await screen.findByLabelText(/Votre montant HT/)
    await waitFor(() => expect(montant).toHaveValue(9000))
    // Le libellé dit que le POST est idempotent (mise à jour, pas 2e offre).
    expect(screen.getByRole('button', { name: /Mettre à jour mon offre/ })).toBeInTheDocument()
  })

  it('RFQ clôturée : lecture seule, aucun formulaire', async () => {
    rfqPublicApi.get.mockResolvedValue({
      data: {
        ...PAYLOAD, cloturee: true,
        offre: { montant_ht: '9000', delai_jours: 10, validite_jours: 20, note: '' },
      },
    })
    renderPage()

    expect(await screen.findByText(/est clôturée/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /offre/ })).toBeNull()
    expect(screen.queryByLabelText(/Votre montant HT/)).toBeNull()
  })

  it('jeton invalide : message FR, jamais du JSON brut', async () => {
    rfqPublicApi.get.mockRejectedValue({
      response: { status: 404, data: { detail: 'Lien invalide ou expiré.' } },
    })
    renderPage()

    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent(/Lien invalide ou expiré|introuvable/)
    expect(alerte.textContent).not.toMatch(/\{"detail"/)
    expect(screen.queryByLabelText(/Votre montant HT/)).toBeNull()
  })

  it('montant vide : refusé côté écran, aucun appel réseau', async () => {
    rfqPublicApi.get.mockResolvedValue({ data: PAYLOAD })
    renderPage()

    await screen.findByText(/RFQ-2026-07-0001/)
    fireEvent.click(screen.getByRole('button', { name: /Envoyer mon offre/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/montant HT/)
    expect(rfqPublicApi.repondre).not.toHaveBeenCalled()
  })
})
