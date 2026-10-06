import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import {
  documentContrat, exempleContrat, reponseContrat,
} from '../../../test/fixtures/contractSamples'

/* ADOC136 — « Mes demandes SAV » : liste, création, fil client du ticket lié
   (contrats mes_demandes_sav_liste.json, mes_tickets_fil.json,
   mes_chantiers_liste.json). */

vi.mock('../../../api/portailApi', () => ({
  default: {
    demandesSav: { liste: vi.fn(), creer: vi.fn(), fil: vi.fn() },
    chantiers: { liste: vi.fn() },
  },
}))

import portailApi from '../../../api/portailApi'
import PortailClientSav from './PortailClientSav.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const contrat = documentContrat('portail', 'mes_demandes_sav_liste')
const [soumise, priseEnCharge] = exempleContrat('portail', 'mes_demandes_sav_liste').results

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><PortailClientSav /></ThemeProvider></MemoryRouter>,
  )
}

function remplir() {
  fireEvent.change(screen.getByLabelText('Sujet'), { target: { value: soumise.sujet } })
  fireEvent.change(screen.getByLabelText('Description'), { target: { value: soumise.description } })
  fireEvent.change(screen.getByLabelText('Chantier concerné'),
    { target: { value: String(soumise.chantier_id) } })
}

describe('PortailClientSav — ADOC136', () => {
  it('crée une demande sur son chantier : la liste rechargée la montre « Soumise »', async () => {
    let creee = false
    portailApi.demandesSav.liste.mockImplementation(() => Promise.resolve({
      data: { results: creee ? [soumise, priseEnCharge] : [priseEnCharge] },
    }))
    portailApi.demandesSav.creer.mockImplementation((corps) => {
      creee = true
      return Promise.resolve({ data: { ...contrat.creation.reponses['201'], sujet: corps.sujet } })
    })
    portailApi.chantiers.liste.mockResolvedValue(reponseContrat('portail', 'mes_chantiers_liste'))
    renderPage()
    await screen.findByText(priseEnCharge.sujet)
    expect(screen.queryByText(soumise.sujet, { selector: 'p' })).toBeNull()
    await screen.findByRole('option', { name: 'CH-2026-0012' })
    remplir()
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer la demande' }))
    await waitFor(() => expect(portailApi.demandesSav.creer).toHaveBeenCalledWith(
      contrat.creation.exemple_corps,
    ))
    expect(await screen.findByText(soumise.sujet, { selector: 'p' })).toBeTruthy()
    expect(screen.getByText('Soumise')).toBeTruthy()
  })

  it('un compte lecture seule voit le refus du serveur', async () => {
    portailApi.demandesSav.liste.mockResolvedValue(reponseContrat('portail', 'mes_demandes_sav_liste'))
    portailApi.chantiers.liste.mockResolvedValue(reponseContrat('portail', 'mes_chantiers_liste'))
    portailApi.demandesSav.creer.mockRejectedValue({
      response: { status: 403, data: contrat.creation.reponses['403'] },
    })
    renderPage()
    await screen.findByText(priseEnCharge.sujet)
    fireEvent.change(screen.getByLabelText('Sujet'), { target: { value: 'X' } })
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer la demande' }))
    expect(await screen.findByText(contrat.creation.reponses['403'].detail)).toBeTruthy()
  })

  it('le fil de la demande liée à un ticket affiche les entrées client-visibles', async () => {
    portailApi.demandesSav.liste.mockResolvedValue(reponseContrat('portail', 'mes_demandes_sav_liste'))
    portailApi.chantiers.liste.mockResolvedValue(reponseContrat('portail', 'mes_chantiers_liste'))
    portailApi.demandesSav.fil.mockResolvedValue(reponseContrat('portail', 'mes_tickets_fil'))
    renderPage()
    await screen.findByText(priseEnCharge.sujet)
    // seule la demande prise en charge (ticket_id) offre le suivi
    expect(screen.getAllByRole('button', { name: 'Voir le suivi' })).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Voir le suivi' }))
    expect(portailApi.demandesSav.fil).toHaveBeenCalledWith(priseEnCharge.id)
    for (const m of exempleContrat('portail', 'mes_tickets_fil').results) {
      expect(await screen.findByText(m.body)).toBeTruthy()
    }
  })
})
