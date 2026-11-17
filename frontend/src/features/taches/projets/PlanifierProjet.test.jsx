import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/tachesApi', async (original) => ({
  ...(await original()),
  apercuPlanification: vi.fn(),
  planifierProjet: vi.fn(),
}))

const api = await import('../../../api/tachesApi')
const { default: PlanifierProjet, QUESTION_COPILOTE } = await import('./PlanifierProjet')

/* TCH91 — le rituel en deux pas : rien n'est écrit avant « Terminer » ; la liste collée est lue sans rien écrire
   (planification_apercu.json) ; « Terminer » envoie tout d'un coup (planification.json) ; le brouillon rouvert
   est identique ; une erreur du serveur s'affiche sous le champ nommé. */

const AUJOURDHUI = '2026-11-17'
const projet = (suite = {}) => ({ ...exempleContrat('taches', 'projet'), ...suite })
const CLE = 'taqinor:draft:taches:plan-projet:3'

const monter = (props = {}) => render(
  <PlanifierProjet projet={projet()} aujourdhui={AUJOURDHUI} onTermine={() => {}} onPasser={() => {}} {...props} />,
)
const utilisateur = () => userEvent.setup()

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-11-17T09:00:00'))
  window.localStorage.clear()
  api.apercuPlanification.mockResolvedValue(reponseContrat('taches', 'planification_apercu'))
  api.planifierProjet.mockResolvedValue(reponseContrat('taches', 'planification'))
})
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks(); window.localStorage.clear() })

describe('TCH91 — Planifier le projet : pas 1 et pas 2', () => {
  it('pas 1 : « Ce sera fini quand… », échéance, priorité ; Suivant mène au pas 2', async () => {
    monter()
    const user = utilisateur()
    expect(screen.getByText('Ventes · pas 1 sur 2')).toBeInTheDocument()
    expect(screen.getByLabelText('Ce sera fini quand…')).toBeInTheDocument()
    const echeances = within(screen.getByRole('radiogroup', { name: 'Échéance' })).getAllByRole('radio').map((r) => r.textContent)
    expect(echeances).toEqual(['1 semaine', '2 semaines', '1 mois', '6 semaines', '3 mois'])
    const priorites = within(screen.getByRole('radiogroup', { name: 'Priorité' })).getAllByRole('radio').map((r) => r.querySelector('b').textContent)
    expect(priorites).toEqual(['Haute', 'Moyenne', 'Basse'])
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    expect(screen.getByText('Ventes · pas 2 sur 2')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Premières actions' })).toBeInTheDocument()
    expect(api.planifierProjet).not.toHaveBeenCalled()
  })

  it('Terminer envoie priorité, objectif, échéance, actions et lock_version d\'un coup, puis rend la main', async () => {
    const onTermine = vi.fn()
    monter({ onTermine })
    const user = utilisateur()
    await user.type(screen.getByLabelText('Ce sera fini quand…'), 'Stand monté')
    await user.click(screen.getByRole('radio', { name: '2 semaines' }))
    await user.click(screen.getByRole('radio', { name: /Haute/ }))
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.type(screen.getByLabelText('Nouvelle action'), 'Réserver le stand')
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    await user.click(within(screen.getByRole('radiogroup', { name: 'Quand : Réserver le stand' })).getByRole('radio', { name: "Aujourd'hui" }))
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(api.planifierProjet).toHaveBeenCalledWith(3, {
      priorite: 3,
      objectif: 'Stand monté',
      echeance: '2026-12-01',
      risque: '',
      sections: [],
      actions: [{ titre: 'Réserver le stand', quand: 'aujourdhui' }],
      lock_version: 4,
    })
    expect(onTermine).toHaveBeenCalledWith(expect.objectContaining({ geste_id: 85 }))
    expect(window.localStorage.getItem(CLE)).toBeNull()
  })

  it('Raccord F2 — une action laissée « Sans jour » part en `quand: plus_tard` (valeur du serveur)', async () => {
    monter()
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.type(screen.getByLabelText('Nouvelle action'), 'Appeler le loueur')
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    expect(within(screen.getByRole('radiogroup', { name: 'Quand : Appeler le loueur' })).getByRole('radio', { name: 'Sans jour' }))
      .toHaveAttribute('aria-checked', 'true')
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(api.planifierProjet).toHaveBeenCalledWith(3, expect.objectContaining({
      actions: [{ titre: 'Appeler le loueur', quand: 'plus_tard' }],
    }))
  })

  it('Passer rend la main sans rien écrire', async () => {
    const onPasser = vi.fn()
    monter({ onPasser })
    await utilisateur().click(screen.getByRole('button', { name: 'Passer' }))
    expect(onPasser).toHaveBeenCalledTimes(1)
    expect(api.planifierProjet).not.toHaveBeenCalled()
    expect(api.apercuPlanification).not.toHaveBeenCalled()
  })
})

describe('TCH91 — Planifier le projet : liste collée, risque, Copilote', () => {
  it('« Lire la liste » appelle l\'aperçu (rien écrit) et montre étapes et jalons', async () => {
    monter()
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.click(screen.getByText('Plus'))
    await user.type(screen.getByLabelText('Étapes'), 'Études :{Enter}Visite')
    await user.click(screen.getByRole('button', { name: 'Lire la liste' }))
    expect(api.apercuPlanification).toHaveBeenCalledWith(3, { texte: 'Études :\nVisite' })
    const lues = await screen.findByRole('list', { name: 'Étapes lues' })
    expect(within(lues).getByText('Études')).toBeInTheDocument()
    expect(within(lues).getByText('Visite')).toBeInTheDocument()
    expect(screen.getByText('Jalons').parentElement).toHaveTextContent('Mise en service')
    expect(api.planifierProjet).not.toHaveBeenCalled()
  })

  it('« En faire une tâche » ajoute le risque aux premières actions', async () => {
    monter()
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.click(screen.getByText('Plus'))
    await user.type(screen.getByLabelText('Si ça échoue, ce sera sans doute parce que…'), 'le stand est complet')
    await user.click(screen.getByRole('button', { name: 'En faire une tâche' }))
    expect(screen.getByText('le stand est complet')).toBeInTheDocument()
  })

  it('« Planifier avec le Copilote » ouvre le Copilote avec la question et le projet ; absent si confidentiel', async () => {
    const recu = vi.fn()
    window.addEventListener('taqinor:assistant:ouvrir', recu)
    const { unmount } = monter()
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.click(screen.getByRole('button', { name: 'Planifier avec le Copilote' }))
    expect(recu.mock.calls[0][0].detail).toMatchObject({ question: QUESTION_COPILOTE, envoyer: true, projet_id: 3 })
    window.removeEventListener('taqinor:assistant:ouvrir', recu)
    unmount()

    window.localStorage.clear()
    monter({ projet: projet({ confidentiel: true }) })
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    expect(screen.queryByRole('button', { name: 'Planifier avec le Copilote' })).toBeNull()
  })
})

describe('TCH91 — Planifier le projet : brouillon et erreurs', () => {
  it('le brouillon est gardé et rouvert à l\'identique (pas, priorité, objectif, échéance, actions)', async () => {
    const premier = monter()
    const user = utilisateur()
    await user.type(screen.getByLabelText('Ce sera fini quand…'), 'Stand monté')
    await user.click(screen.getByRole('radio', { name: '1 mois' }))
    await user.click(screen.getByRole('radio', { name: /Basse/ }))
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.type(screen.getByLabelText('Nouvelle action'), 'Réserver le stand')
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    await act(async () => { await new Promise((fin) => { setTimeout(fin, 600) }) })
    premier.unmount()

    monter()
    expect(screen.getByText('Ventes · pas 2 sur 2')).toBeInTheDocument()
    expect(screen.getByText('Réserver le stand')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Précédent' }))
    expect(screen.getByLabelText('Ce sera fini quand…')).toHaveValue('Stand monté')
    expect(screen.getByLabelText('Choisir')).toHaveValue('2026-12-17')
    expect(screen.getByRole('radio', { name: /Basse/ })).toHaveAttribute('aria-checked', 'true')
  })

  it('un refus du serveur s\'affiche sous le champ nommé et ramène au pas 1', async () => {
    api.planifierProjet.mockRejectedValue({ response: { status: 400, data: { echeance: ['Cette date est passée.'] } } })
    monter()
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('Cette date est passée.')
    expect(screen.getByLabelText('Choisir')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('Ventes · pas 1 sur 2')).toBeInTheDocument()
  })

  it('une coupure réseau se dit en haut du rituel, la saisie reste', async () => {
    api.planifierProjet.mockRejectedValue(new Error('Network Error'))
    monter()
    const user = utilisateur()
    await user.type(screen.getByLabelText('Ce sera fini quand…'), 'Stand monté')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Connexion perdue')
    await user.click(screen.getByRole('button', { name: 'Précédent' }))
    expect(screen.getByLabelText('Ce sera fini quand…')).toHaveValue('Stand monté')
  })
})
