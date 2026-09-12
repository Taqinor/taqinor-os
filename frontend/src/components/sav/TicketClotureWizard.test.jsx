import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* NTSRV30 — Assistant de clôture (3 étapes).

   Critère d'acceptation : un agent novice ne peut pas refermer un ticket en
   oubliant cause/remède, et un agent expert garde l'ancien raccourci
   « Clôture rapide » en un clic. */

const CAUSES = [
  { id: 1, nom: 'Défaut composant' },
  { id: 2, nom: 'Usure normale' },
]
const REMEDES = [
  { id: 7, nom: 'Remplacement pièce' },
  { id: 8, nom: 'Reparamétrage' },
]

vi.mock('../../api/savApi', () => ({
  default: {
    getCausesDefaillance: vi.fn(() => Promise.resolve({ data: CAUSES })),
    getRemedesDefaillance: vi.fn(() => Promise.resolve({ data: REMEDES })),
    updateTicket: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
    cloturerTicket: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
    lienClientTicket: vi.fn(() => Promise.resolve({
      data: { token: 'jeton-9', url: 'https://exemple.test/suivi/jeton-9' },
    })),
  },
}))

vi.mock('../../api/kbApi', () => ({
  default: {
    creerArticleDepuisTicket: vi.fn(() => Promise.resolve({
      data: { id: 44, titre: 'Défaut composant', statut: 'brouillon' },
    })),
  },
}))

import kbApi from '../../api/kbApi'
import savApi from '../../api/savApi'
import TicketClotureWizard from './TicketClotureWizard'

const TICKET = {
  id: 9,
  reference: 'SAV-2026-0009',
  description: 'Onduleur en défaut.',
  equipement_nom: 'Onduleur X',
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

async function rendreEtChargerReferentiels(props = {}) {
  render(<TicketClotureWizard ticket={TICKET} {...props} />)
  await waitFor(() =>
    expect(screen.getByRole('option', { name: 'Défaut composant' }))
      .toBeInTheDocument())
}

async function allerEtape3() {
  await rendreEtChargerReferentiels()
  fireEvent.change(screen.getByLabelText(/Cause de la panne/),
    { target: { value: '1' } })
  fireEvent.change(screen.getByLabelText(/Remède appliqué/),
    { target: { value: '7' } })
  fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
  fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
}

describe('TicketClotureWizard (NTSRV30)', () => {
  it('charge les référentiels cause/remède à l\'ouverture', async () => {
    await rendreEtChargerReferentiels()
    expect(savApi.getCausesDefaillance).toHaveBeenCalled()
    expect(savApi.getRemedesDefaillance).toHaveBeenCalled()
    expect(screen.getByRole('option', { name: 'Remplacement pièce' }))
      .toBeInTheDocument()
  })

  it('refuse l\'étape 1 sans cause ni remède, en nommant chaque champ',
    async () => {
      await rendreEtChargerReferentiels()
      fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
      expect(screen.getByText('Choisissez la cause de la panne.'))
        .toBeInTheDocument()
      expect(screen.getByText('Choisissez le remède appliqué.'))
        .toBeInTheDocument()
      // Toujours à l'étape 1 : rien n'a été clôturé.
      expect(screen.getByText(/étape 1 sur 3/)).toBeInTheDocument()
      expect(savApi.cloturerTicket).not.toHaveBeenCalled()
    })

  it('avance à l\'étape 2 une fois cause et remède choisis', async () => {
    await rendreEtChargerReferentiels()
    fireEvent.change(screen.getByLabelText(/Cause de la panne/),
      { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText(/Remède appliqué/),
      { target: { value: '7' } })
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
    expect(screen.getByText(/étape 2 sur 3/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Créer un article KB/)).not.toBeChecked()
  })

  it('clôture en posant cause, remède et canal de résolution', async () => {
    await allerEtape3()
    fireEvent.change(screen.getByLabelText(/Canal de résolution/),
      { target: { value: 'a_distance' } })
    fireEvent.click(screen.getByRole('button', { name: 'Clôturer le ticket' }))
    await waitFor(() => expect(savApi.cloturerTicket).toHaveBeenCalledWith(9))
    expect(savApi.updateTicket).toHaveBeenCalledWith(9, {
      cause: 1, remede: 7, canal_resolution: 'a_distance',
    })
  })

  it('ne crée un article KB que si la case est cochée', async () => {
    await allerEtape3()
    fireEvent.click(screen.getByRole('button', { name: 'Clôturer le ticket' }))
    await waitFor(() => expect(savApi.cloturerTicket).toHaveBeenCalled())
    expect(kbApi.creerArticleDepuisTicket).not.toHaveBeenCalled()
  })

  it('pré-remplit l\'article KB avec la cause et le remède saisis',
    async () => {
      await rendreEtChargerReferentiels()
      fireEvent.change(screen.getByLabelText(/Cause de la panne/),
        { target: { value: '1' } })
      fireEvent.change(screen.getByLabelText(/Remède appliqué/),
        { target: { value: '7' } })
      fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
      fireEvent.click(screen.getByLabelText(/Créer un article KB/))
      fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
      fireEvent.click(
        screen.getByRole('button', { name: 'Clôturer le ticket' }))
      await waitFor(() =>
        expect(kbApi.creerArticleDepuisTicket).toHaveBeenCalledWith(
          expect.objectContaining({
            ticket_id: 9,
            cause: 'Défaut composant',
            remede: 'Remplacement pièce',
          })))
    })

  it('déclenche l\'enquête et affiche le lien client', async () => {
    await allerEtape3()
    fireEvent.click(screen.getByRole('button', { name: 'Clôturer le ticket' }))
    await waitFor(() =>
      expect(savApi.lienClientTicket).toHaveBeenCalledWith(9))
    expect(await screen.findByText('https://exemple.test/suivi/jeton-9'))
      .toBeInTheDocument()
  })

  it('n\'appelle pas l\'enquête quand la case est décochée', async () => {
    await allerEtape3()
    fireEvent.click(screen.getByLabelText(/Envoyer l'enquête de satisfaction/))
    fireEvent.click(screen.getByRole('button', { name: 'Clôturer le ticket' }))
    await waitFor(() => expect(savApi.cloturerTicket).toHaveBeenCalled())
    expect(savApi.lienClientTicket).not.toHaveBeenCalled()
  })

  it('garde le raccourci « Clôture rapide » en un clic', async () => {
    const onTermine = vi.fn()
    await rendreEtChargerReferentiels({ onTermine })
    fireEvent.click(screen.getByRole('button', { name: 'Clôture rapide' }))
    await waitFor(() => expect(savApi.cloturerTicket).toHaveBeenCalledWith(9))
    // Le raccourci ne pose NI cause NI remède : comportement d'avant, intact.
    expect(savApi.updateTicket).not.toHaveBeenCalled()
    await waitFor(() =>
      expect(onTermine).toHaveBeenCalledWith({ rapide: true }))
  })

  it('affiche l\'erreur serveur au lieu d\'un message générique', async () => {
    savApi.cloturerTicket.mockRejectedValueOnce({
      response: { data: { detail: 'Transition interdite depuis Nouveau.' } },
    })
    await rendreEtChargerReferentiels()
    fireEvent.click(screen.getByRole('button', { name: 'Clôture rapide' }))
    expect(await screen.findByText('Transition interdite depuis Nouveau.'))
      .toBeInTheDocument()
  })
})
