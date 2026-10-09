import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, cleanup } from '@testing-library/react'
import { reponseContrat } from '../../test/fixtures/contractSamples'

/* ASAV31 — la page publique de suivi dit l'état réel : « Annulé » /
   « Fusionné dans <réf> », sans formulaire de satisfaction. Les réponses
   viennent de l'exemple committé ticket_suivi_public.json (ASAV1). */

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import api from '../../api/axios'
import { renderSuiviPage as renderPage } from './__testutils__/renderSuiviPage.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('TicketSuiviPage ASAV31', () => {
  it('ticket annulé : bandeau « Annulé », pas de « Nouveau », pas de formulaire', async () => {
    api.get.mockResolvedValueOnce(reponseContrat('sav', 'ticket_suivi_public', 'exemple_annule'))
    renderPage()
    expect(await screen.findByText('Annulé')).toBeInTheDocument()
    expect(screen.queryByText(/Nouveau/)).toBeNull()
    expect(screen.queryByText(/Envoyer ma réponse/)).toBeNull()
  })

  it('doublon fusionné : « Fusionné dans <référence> »', async () => {
    api.get.mockResolvedValueOnce(reponseContrat('sav', 'ticket_suivi_public', 'exemple_fusionne'))
    renderPage()
    expect(await screen.findByText('Fusionné dans SAV-2026-10-0042')).toBeInTheDocument()
    expect(screen.queryByText(/Envoyer ma réponse/)).toBeNull()
  })

  it('ticket vivant : statut affiché comme avant', async () => {
    api.get.mockResolvedValueOnce(reponseContrat('sav', 'ticket_suivi_public'))
    renderPage()
    expect(await screen.findByText('En cours')).toBeInTheDocument()
    expect(screen.queryByText('Annulé')).toBeNull()
  })

  it('ticket annulé alors que statut résolu : jamais de formulaire', async () => {
    const r = reponseContrat('sav', 'ticket_suivi_public', 'exemple_annule')
    api.get.mockResolvedValueOnce({ data: { ...r.data, statut: 'resolu' } })
    renderPage()
    await screen.findByText('Annulé')
    expect(screen.queryByText(/Envoyer ma réponse/)).toBeNull()
  })
})
