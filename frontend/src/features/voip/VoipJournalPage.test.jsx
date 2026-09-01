import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR271 — un appel jamais clôturable : ni durée ni issue ni chatter n'étaient
   jamais écrits (le wrapper `voipApi.terminerAppel` existait déjà côté client,
   mais aucun bouton ne l'appelait). Couvre le bouton « Terminer » exposé
   uniquement sur les appels OUVERTS (initié/sonnant/en cours — jamais sur un
   appel déjà terminé/manqué), la durée PRÉ-REMPLIE (écoulée depuis
   `started_at`), et le 400 serveur (« Entier requis. ») affiché tel quel. */
vi.mock('../../api/voipApi', () => ({
  default: {
    getAppels: vi.fn(),
    appelSortant: vi.fn(),
    terminerAppel: vi.fn(),
  },
}))

import voipApi from '../../api/voipApi'
import VoipJournalPage from './VoipJournalPage.jsx'

const APPEL_OUVERT = {
  id: 12,
  direction: 'entrant',
  numero: '0600000000',
  cible: { libelle: 'Client Test' },
  statut: 'en_cours',
  issue: '',
  started_at: new Date(Date.now() - 90 * 1000).toISOString(),
  duree_secondes: null,
}

const APPEL_TERMINE = {
  id: 13,
  direction: 'sortant',
  numero: '0611111111',
  cible: null,
  statut: 'termine',
  issue: 'répondu',
  started_at: new Date(Date.now() - 600 * 1000).toISOString(),
  duree_secondes: 45,
}

function setAppels(list) {
  voipApi.getAppels.mockResolvedValue({ data: list })
}

describe('VoipJournalPage — clôture d’un appel ouvert (WIR271)', () => {
  beforeEach(() => {
    voipApi.getAppels.mockReset()
    voipApi.appelSortant.mockReset()
    voipApi.terminerAppel.mockReset()
  })

  it('affiche « Terminer » seulement sur les appels encore ouverts', async () => {
    setAppels([APPEL_OUVERT, APPEL_TERMINE])
    render(<VoipJournalPage />)

    const rowOuvert = (await screen.findByText('0600000000')).closest('tr')
    const rowTermine = screen.getByText('0611111111').closest('tr')
    expect(
      within(rowOuvert).getByRole('button', { name: 'Terminer' }),
    ).toBeInTheDocument()
    expect(
      within(rowTermine).queryByRole('button', { name: 'Terminer' }),
    ).not.toBeInTheDocument()
  })

  it('pré-remplit la durée écoulée et clôture avec l’issue saisie', async () => {
    setAppels([APPEL_OUVERT])
    voipApi.terminerAppel.mockResolvedValueOnce({
      data: { ...APPEL_OUVERT, statut: 'termine', duree_secondes: 90, issue: 'répondu' },
    })
    render(<VoipJournalPage />)

    const row = (await screen.findByText('0600000000')).closest('tr')
    await userEvent.click(within(row).getByRole('button', { name: 'Terminer' }))

    // Pré-remplie : un entier positif (l'appel a démarré il y a 90 s), jamais vide.
    const dureeInput = within(row).getByLabelText('Durée (secondes)')
    expect(dureeInput.value).not.toBe('')
    expect(Number(dureeInput.value)).toBeGreaterThanOrEqual(0)

    const issueInput = within(row).getByLabelText('Issue')
    await userEvent.type(issueInput, 'répondu')
    await userEvent.click(within(row).getByRole('button', { name: 'Confirmer' }))

    await waitFor(() => expect(voipApi.terminerAppel).toHaveBeenCalledTimes(1))
    const [id, body] = voipApi.terminerAppel.mock.calls[0]
    expect(id).toBe(12)
    expect(Number(body.duree_secondes)).toBeGreaterThanOrEqual(0)
    expect(body.issue).toBe('répondu')

    // Le journal est rechargé après clôture (formulaire refermé).
    await waitFor(() => expect(voipApi.getAppels).toHaveBeenCalledTimes(2))
  })

  it('affiche le 400 "Entier requis." du serveur tel quel, en français', async () => {
    setAppels([APPEL_OUVERT])
    voipApi.terminerAppel.mockRejectedValueOnce({
      response: { status: 400, data: { duree_secondes: 'Entier requis.' } },
    })
    render(<VoipJournalPage />)

    const row = (await screen.findByText('0600000000')).closest('tr')
    await userEvent.click(within(row).getByRole('button', { name: 'Terminer' }))
    await userEvent.click(within(row).getByRole('button', { name: 'Confirmer' }))

    expect(await within(row).findByRole('alert')).toHaveTextContent('Entier requis.')
  })

  it('« Annuler » referme le formulaire sans appeler terminerAppel', async () => {
    setAppels([APPEL_OUVERT])
    render(<VoipJournalPage />)

    const row = (await screen.findByText('0600000000')).closest('tr')
    await userEvent.click(within(row).getByRole('button', { name: 'Terminer' }))
    await userEvent.click(within(row).getByRole('button', { name: 'Annuler' }))

    expect(
      within(row).queryByLabelText('Durée (secondes)'),
    ).not.toBeInTheDocument()
    expect(within(row).getByRole('button', { name: 'Terminer' })).toBeInTheDocument()
    expect(voipApi.terminerAppel).not.toHaveBeenCalled()
  })
})
