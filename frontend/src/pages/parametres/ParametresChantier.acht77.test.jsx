import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor, fireEvent, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* ACHT77 — les sections de paramètres chantier affichent le message serveur
   d'un refus (400 sous le champ, 409 `detail`) au lieu d'un message générique
   ou d'un `catch` muet, et la corbeille d'un champ de fiche demande confirmation.
   Faux serveur en mémoire qui renvoie les corps réels : 400 DRF par champ
   (ACHT76, sonde COUT-7) et 409 du `UsageGuardedDestroyMixin` (ACHT73). */

const apiMock = vi.hoisted(() => ({
  getStagesChantier: vi.fn(),
  saveStageChantier: vi.fn(),
  deleteStageChantier: vi.fn(),
  getEquipesTerrain: vi.fn(),
  saveEquipeTerrain: vi.fn(),
  deleteEquipeTerrain: vi.fn(),
  getFicheTemplates: vi.fn(),
  saveFicheTemplate: vi.fn(),
  deleteFicheTemplate: vi.fn(),
  saveFicheChamp: vi.fn(),
  deleteFicheChamp: vi.fn(),
}))
vi.mock('../../api/installationsApi', () => ({ default: apiMock }))

import { toast } from '../../ui/confirm'
import { ThemeProvider } from '../../design/ThemeProvider'
import { ConfirmProvider } from '../../providers/ConfirmProvider'
import EtapesChantierSection from './EtapesChantierSection'
import EquipeTerrainSection from './EquipeTerrainSection'
import FicheInterventionModelesSection from './FicheInterventionModelesSection'

const store = configureStore({
  reducer: {
    auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [], user: null }) => s,
  },
})

const reponseErreur = (status, data) => Object.assign(new Error('refus'), {
  response: { status, data, headers: { 'content-type': 'application/json' } },
})

const renderWith = async (ui) => {
  await act(async () => {
    render(
      <Provider store={store}>
        <ThemeProvider>
          <ConfirmProvider>{ui}</ConfirmProvider>
        </ThemeProvider>
      </Provider>,
    )
  })
}

beforeEach(() => {
  Object.values(apiMock).forEach((f) => f.mockReset())
  vi.spyOn(toast, 'error').mockImplementation(() => {})
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('ACHT77 EtapesChantierSection — doublon de clé', () => {
  it("affiche le 400 par champ du serveur, pas « Ajout impossible. »", async () => {
    apiMock.getStagesChantier.mockResolvedValue({
      data: { results: [{ id: 1, cle: 'etude_site', libelle: 'Étude site', ordre: 0, actif: true, bloquant: false, protege: false }] },
    })
    apiMock.saveStageChantier.mockRejectedValue(
      reponseErreur(400, { cle: ['Cette clé existe déjà.'] }))
    await renderWith(<EtapesChantierSection />)
    await screen.findByDisplayValue('Étude site')
    fireEvent.change(screen.getByPlaceholderText('Nouvelle étape…'), { target: { value: 'Etude site' } })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Cette clé existe déjà.'))
    expect(apiMock.saveStageChantier.mock.calls[0][1].cle).toBe('etude_site')
  })

  it('une modification refusée n\'est plus avalée en silence', async () => {
    apiMock.getStagesChantier.mockResolvedValue({
      data: { results: [{ id: 1, cle: 'a', libelle: 'A', ordre: 0, actif: true, bloquant: false, protege: false }] },
    })
    apiMock.saveStageChantier.mockRejectedValue(reponseErreur(409, { detail: 'Étape utilisée par 2 chantiers.' }))
    await renderWith(<EtapesChantierSection />)
    await screen.findByDisplayValue('A')
    fireEvent.click(screen.getByRole('button', { name: 'Rendre bloquant' }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Étape utilisée par 2 chantiers.'))
  })
})

describe('ACHT77 EquipeTerrainSection — suppression refusée', () => {
  it('affiche le message du 409 et ne masque plus l\'erreur', async () => {
    apiMock.getEquipesTerrain.mockResolvedValue({
      data: { results: [{ id: 7, nom: 'E1', actif: true, chef: null, membres: [], nb_membres: 0 }] },
    })
    apiMock.deleteEquipeTerrain.mockRejectedValue(
      reponseErreur(409, { detail: 'Utilisée par 1 intervention.' }))
    await renderWith(<EquipeTerrainSection assignables={[]} />)
    await screen.findByDisplayValue('E1')
    fireEvent.click(screen.getByLabelText("Supprimer l'équipe"))
    const dialog = await screen.findByRole('alertdialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Supprimer' }))
    expect(await screen.findByText('Utilisée par 1 intervention.')).toBeInTheDocument()
    // CLAUSE PERSISTANCE : la section recharge la liste, l'équipe est toujours là.
    expect(screen.getByDisplayValue('E1')).toBeInTheDocument()
  })

  it('un doublon de nom à la création affiche le message sous forme lisible', async () => {
    apiMock.getEquipesTerrain.mockResolvedValue({ data: { results: [] } })
    apiMock.saveEquipeTerrain.mockRejectedValue(reponseErreur(400, { nom: ['Cette équipe existe déjà.'] }))
    await renderWith(<EquipeTerrainSection assignables={[]} />)
    fireEvent.change(await screen.findByPlaceholderText('Nouvelle équipe terrain'), { target: { value: 'E1' } })
    fireEvent.keyDown(screen.getByPlaceholderText('Nouvelle équipe terrain'), { key: 'Enter' })
    expect(await screen.findByText('Cette équipe existe déjà.')).toBeInTheDocument()
  })
})

describe('ACHT77 FicheInterventionModelesSection — corbeille d\'un champ', () => {
  const tpl = {
    id: 3, nom: 'Pose', type_intervention: 'pose', actif: true, protege: false,
    champs: [{ id: 11, libelle: 'Isolement', cle: 'iso', type_champ: 'mesure', unite: 'MΩ', obligatoire: false }],
  }

  it('Annuler ne supprime rien', async () => {
    apiMock.getFicheTemplates.mockResolvedValue({ data: { results: [tpl] } })
    await renderWith(<FicheInterventionModelesSection />)
    await screen.findByText('Isolement')
    fireEvent.click(screen.getByLabelText('Retirer le champ'))
    const dialog = await screen.findByRole('alertdialog')
    fireEvent.click(within(dialog).getByText('Annuler'))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(apiMock.deleteFicheChamp).not.toHaveBeenCalled()
  })

  it('Confirmer affiche le 409 et le champ reste', async () => {
    apiMock.getFicheTemplates.mockResolvedValue({ data: { results: [tpl] } })
    apiMock.deleteFicheChamp.mockRejectedValue(
      reponseErreur(409, { detail: 'Utilisé par 1 valeur de fiche.' }))
    await renderWith(<FicheInterventionModelesSection />)
    await screen.findByText('Isolement')
    fireEvent.click(screen.getByLabelText('Retirer le champ'))
    const dialog = await screen.findByRole('alertdialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Supprimer' }))
    expect(await screen.findByText('Utilisé par 1 valeur de fiche.')).toBeInTheDocument()
    expect(apiMock.deleteFicheChamp).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Isolement')).toBeInTheDocument()
  })
})
