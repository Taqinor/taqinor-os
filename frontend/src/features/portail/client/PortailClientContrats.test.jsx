import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import {
  documentContrat, exempleContrat, reponseContrat,
} from '../../../test/fixtures/contractSamples'

/* ADOC139 — « Mes contrats » : clés du contrat mes_contrats_maintenance.json
   affichées telles quelles, demande de renouvellement/résiliation. Le « serveur
   de test » refuse (400) une demande sans type, comme le vrai. */

vi.mock('../../../api/portailApi', () => ({
  default: { contrats: { liste: vi.fn(), demander: vi.fn() } },
}))

import portailApi from '../../../api/portailApi'
import PortailClientContrats from './PortailClientContrats.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const contrat = documentContrat('portail', 'mes_contrats_maintenance')
const [c] = exempleContrat('portail', 'mes_contrats_maintenance').results

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><PortailClientContrats /></ThemeProvider></MemoryRouter>,
  )
}

describe('PortailClientContrats — ADOC139', () => {
  it('affiche le contrat avec les valeurs servies', async () => {
    portailApi.contrats.liste.mockResolvedValue(reponseContrat('portail', 'mes_contrats_maintenance'))
    renderPage()
    await screen.findByText(c.chantier)
    expect(screen.getByText(new RegExp(c.periodicite_display))).toBeTruthy()
    expect(screen.getByText(/50 %/)).toBeTruthy()
  })

  it('envoie type_demande + message et affiche le message du serveur', async () => {
    portailApi.contrats.liste.mockResolvedValue(reponseContrat('portail', 'mes_contrats_maintenance'))
    portailApi.contrats.demander.mockImplementation((id, corps) => (
      corps.type_demande
        ? Promise.resolve({ data: contrat.exemple_demande.reponse })
        : Promise.reject({ response: { status: 400, data: { type_demande: ['requis'] } } })
    ))
    renderPage()
    await screen.findByText(c.chantier)
    fireEvent.change(screen.getByLabelText('Message (facultatif)'),
      { target: { value: contrat.exemple_demande.corps.message } })
    fireEvent.click(screen.getByRole('button', { name: 'Demander le renouvellement' }))
    await waitFor(() => expect(portailApi.contrats.demander)
      .toHaveBeenCalledWith(c.id, contrat.exemple_demande.corps))
    expect(await screen.findByText(contrat.exemple_demande.reponse.detail)).toBeTruthy()
  })

  it('la résiliation envoie son propre type', async () => {
    portailApi.contrats.liste.mockResolvedValue(reponseContrat('portail', 'mes_contrats_maintenance'))
    portailApi.contrats.demander.mockResolvedValue({ data: contrat.exemple_demande.reponse })
    renderPage()
    await screen.findByText(c.chantier)
    fireEvent.click(screen.getByRole('button', { name: 'Demander la résiliation' }))
    await waitFor(() => expect(portailApi.contrats.demander)
      .toHaveBeenCalledWith(c.id, { type_demande: 'resiliation', message: '' }))
  })

  it('un compte lecture seule voit le refus du serveur', async () => {
    portailApi.contrats.liste.mockResolvedValue(reponseContrat('portail', 'mes_contrats_maintenance'))
    portailApi.contrats.demander.mockRejectedValue({
      response: { status: 403, data: { detail: 'Votre accès est en lecture seule.' } },
    })
    renderPage()
    await screen.findByText(c.chantier)
    fireEvent.click(screen.getByRole('button', { name: 'Demander le renouvellement' }))
    expect(await screen.findByText('Votre accès est en lecture seule.')).toBeTruthy()
  })
})
