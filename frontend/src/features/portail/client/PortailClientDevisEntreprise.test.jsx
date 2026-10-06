import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

/* CIQ322 (D-CIQ-11) — la signature d'un devis C&I sur le portail demande la
   raison sociale, la qualité du signataire et l'ICE. La liste vient du contrat
   COMMITTÉ `apps/portail/contract_samples/mes_devis_liste.json` (un devis
   envoyé `exige_identite_entreprise: true`) ; le corps attendu et la réponse
   400 viennent de `apps/ventes/contract_samples/acceptation_entreprise.json`
   — jamais un mock écrit à la main. */

vi.mock('../../../api/portailApi', () => ({
  default: { devis: { liste: vi.fn(), accepter: vi.fn(), pdfUrl: (id) => `/pdf/${id}` } },
}))

import portailApi from '../../../api/portailApi'
import PortailClientDevis from './PortailClientDevis.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const CORPS_PORTAIL = exempleContrat('ventes', 'acceptation_entreprise', 'exemple_portail').corps
const REPONSE = exempleContrat('ventes', 'acceptation_entreprise', 'reponse')

function renderPage() {
  return render(
    <MemoryRouter>
      <ThemeProvider><PortailClientDevis /></ThemeProvider>
    </MemoryRouter>,
  )
}

function listeAvec(exige) {
  const liste = exempleContrat('portail', 'mes_devis_liste')
  const [envoye] = liste.results
  return { data: { results: [{ ...envoye, exige_identite_entreprise: exige }] } }
}

async function ouvrirDialogue(reference) {
  await screen.findByText(reference)
  fireEvent.click(screen.getByRole('button', { name: 'Accepter' }))
  await screen.findByLabelText('Votre nom')
}

function signer() {
  fireEvent.change(screen.getByLabelText('Votre nom'), { target: { value: CORPS_PORTAIL.nom } })
  fireEvent.click(screen.getByRole('checkbox'))
}

describe('PortailClientDevis — CIQ322 identité d’entreprise', () => {
  it('devis industriel : trois champs requis, corps `entreprise` envoyé', async () => {
    const contrat = reponseContrat('portail', 'mes_devis_liste')
    const [envoye] = contrat.data.results
    expect(envoye.exige_identite_entreprise).toBe(true)
    portailApi.devis.liste.mockResolvedValue(contrat)
    portailApi.devis.accepter.mockResolvedValue({ data: REPONSE.exemple })
    renderPage()
    await ouvrirDialogue(envoye.reference)
    signer()

    const confirmer = screen.getByRole('button', { name: 'Confirmer l’acceptation' })
    // Nom + consentement ne suffisent pas : l'identité d'entreprise manque.
    expect(confirmer).toBeDisabled()

    const { entreprise } = CORPS_PORTAIL
    fireEvent.change(screen.getByLabelText('Raison sociale'), { target: { value: entreprise.raison_sociale } })
    fireEvent.change(screen.getByLabelText('Qualité du signataire'), { target: { value: entreprise.signataire_qualite } })
    expect(confirmer).toBeDisabled()
    fireEvent.change(screen.getByLabelText('ICE'), { target: { value: entreprise.ice } })
    expect(confirmer).not.toBeDisabled()

    fireEvent.click(confirmer)
    await waitFor(() => expect(portailApi.devis.accepter).toHaveBeenCalledTimes(1))
    const [id, corps] = portailApi.devis.accepter.mock.calls[0]
    expect(id).toBe(envoye.id)
    expect(corps).toEqual({
      nom: CORPS_PORTAIL.nom,
      consent_esign: CORPS_PORTAIL.consent_esign,
      entreprise,
    })
  })

  it('l’erreur 400 du serveur s’affiche sous le champ fautif', async () => {
    const liste = listeAvec(true)
    portailApi.devis.liste.mockResolvedValue(liste)
    portailApi.devis.accepter.mockRejectedValue({ response: { status: 400, data: REPONSE.exemple_400 } })
    renderPage()
    await ouvrirDialogue(liste.data.results[0].reference)
    signer()
    const { entreprise } = CORPS_PORTAIL
    fireEvent.change(screen.getByLabelText('Raison sociale'), { target: { value: entreprise.raison_sociale } })
    fireEvent.change(screen.getByLabelText('Qualité du signataire'), { target: { value: entreprise.signataire_qualite } })
    fireEvent.change(screen.getByLabelText('ICE'), { target: { value: '12AB' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer l’acceptation' }))

    const alerte = await screen.findByRole('alert')
    expect(alerte.textContent).toBe(REPONSE.exemple_400.detail)
    expect(alerte.id).toBe(`portail-entreprise-${REPONSE.exemple_400.champ.split('.')[1]}-erreur`)
    expect(screen.getByLabelText('ICE')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Raison sociale')).not.toHaveAttribute('aria-invalid')
  })

  it('devis résidentiel : aucun de ces champs, corps inchangé', async () => {
    const liste = listeAvec(false)
    portailApi.devis.liste.mockResolvedValue(liste)
    portailApi.devis.accepter.mockResolvedValue({ data: REPONSE.exemple })
    renderPage()
    await ouvrirDialogue(liste.data.results[0].reference)
    expect(screen.queryByLabelText('Raison sociale')).toBeNull()
    expect(screen.queryByLabelText('Qualité du signataire')).toBeNull()
    expect(screen.queryByLabelText('ICE')).toBeNull()
    signer()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer l’acceptation' }))
    await waitFor(() => expect(portailApi.devis.accepter).toHaveBeenCalledTimes(1))
    expect(portailApi.devis.accepter.mock.calls[0][1]).toEqual({
      nom: CORPS_PORTAIL.nom,
      consent_esign: true,
    })
  })
})
