import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR271 — aucun appel n'était jamais clôturable depuis l'écran : la durée
   et l'issue restaient à jamais vides, et l'entrée chatter que
   `services.terminer_appel` pose sur la fiche résolue ne partait donc
   jamais. Ces tests épinglent : (1) le bouton « Terminer » n'existe QUE sur
   un appel EN_COURS, (2) il envoie `duree_secondes`/`issue` au serveur,
   (3) un 400 serveur (« Entier requis. ») s'affiche TEL QUEL. */

const mocks = vi.hoisted(() => ({
  getAppels: vi.fn(),
  appelSortant: vi.fn(),
  terminerAppel: vi.fn(),
}))

vi.mock('../../api/voipApi', () => ({
  default: {
    getAppels: mocks.getAppels,
    appelSortant: mocks.appelSortant,
    terminerAppel: mocks.terminerAppel,
  },
}))

import VoipJournalPage from './VoipJournalPage'

const APPEL_EN_COURS = {
  id: 1, direction: 'sortant', numero: '+212600000000', statut: 'en_cours',
  started_at: '2026-08-15T10:00:00Z', duree_secondes: null, issue: '',
}
const APPEL_TERMINE = {
  id: 2, direction: 'entrant', numero: '+212611111111', statut: 'termine',
  started_at: '2026-08-15T09:00:00Z', duree_secondes: 42, issue: 'repondu',
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getAppels.mockResolvedValue({ data: [APPEL_EN_COURS, APPEL_TERMINE] })
})

describe('VoipJournalPage — clôture d’appel (WIR271)', () => {
  it('affiche « Terminer » uniquement sur l’appel EN_COURS, jamais sur le terminé', async () => {
    render(<VoipJournalPage />)
    await screen.findByText('+212600000000')
    const boutons = screen.getAllByRole('button', { name: 'Terminer' })
    expect(boutons).toHaveLength(1)
  })

  it('« Terminer » envoie la durée pré-remplie et l’issue saisie', async () => {
    mocks.terminerAppel.mockResolvedValueOnce({
      data: { ...APPEL_EN_COURS, statut: 'termine', duree_secondes: 120, issue: 'repondu' },
    })
    render(<VoipJournalPage />)
    await screen.findByText('+212600000000')

    await userEvent.click(screen.getByRole('button', { name: 'Terminer' }))
    const dureeInput = screen.getByLabelText("Durée de l'appel +212600000000")
    // Pré-remplie (dérivée de started_at), non vide.
    expect(dureeInput.value).not.toBe('')

    await userEvent.clear(dureeInput)
    await userEvent.type(dureeInput, '120')
    await userEvent.type(screen.getByLabelText("Issue de l'appel +212600000000"), 'repondu')
    await userEvent.click(screen.getByRole('button', { name: 'Valider' }))

    await waitFor(() => expect(mocks.terminerAppel).toHaveBeenCalledWith(
      1, { duree_secondes: '120', issue: 'repondu' },
    ))
  })

  it('un 400 serveur (« Entier requis. ») s’affiche tel quel', async () => {
    mocks.terminerAppel.mockRejectedValueOnce({
      response: { status: 400, data: { duree_secondes: 'Entier requis.' } },
    })
    render(<VoipJournalPage />)
    await screen.findByText('+212600000000')

    await userEvent.click(screen.getByRole('button', { name: 'Terminer' }))
    await userEvent.click(screen.getByRole('button', { name: 'Valider' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Entier requis.')
  })
})
