import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'

vi.mock('../../api/tachesApi', async (original) => ({
  ...(await original()),
  lireRevue: vi.fn(),
  deciderRevue: vi.fn(),
  lireVueProjet: vi.fn(),
}))

const api = await import('../../api/tachesApi')
const { default: Revue } = await import('./Revue')

/* TCH93 — la Revue rend `revue_projets.json` : bilan (ou « Semaine courte »), une carte par projet, les quatre
   décisions écrivent `revue_decision.json`, la fin mène à « Planifier ma semaine ». */

function Lieu() {
  const l = useLocation()
  return <div data-testid="lieu">{`${l.pathname}${l.search}`}</div>
}
const monter = () => render(
  <MemoryRouter initialEntries={['/taches/revue']}>
    <Routes>
      <Route path="/taches/revue" element={<Revue />} />
      <Route path="*" element={<Lieu />} />
    </Routes>
  </MemoryRouter>,
)
const revue = () => structuredClone(exempleContrat('taches', 'revue_projets'))
const seconde = () => {
  const r = revue()
  const deux = structuredClone(r.cartes[0])
  deux.projet = { ...deux.projet, id: 5, nom: 'Site web', couleur: 'ciel', priorite: 2, sante: [], a_planifier: true }
  deux.faites_semaine = []
  deux.faites_nb = 0
  deux.bloquees = []
  deux.prochaine_action = null
  deux.revue = { intention: '', decision: '', focus: false }
  r.cartes.push(deux)
  return r
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-11-17T09:00:00'))
  reinitialiserGestes()
  api.lireRevue.mockResolvedValue(reponseContrat('taches', 'revue_projets'))
  api.deciderRevue.mockResolvedValue(reponseContrat('taches', 'revue_decision'))
  api.lireVueProjet.mockResolvedValue(reponseContrat('taches', 'projet_vue'))
})
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks(); reinitialiserGestes() })

describe('TCH93 — Revue : en tête et carte', () => {
  it('le bilan du serveur, puis la carte du projet avec faites, attente, prochaine action et santé', async () => {
    monter()
    expect(await screen.findByText('Du lun. 16 au ven. 20 : 26 tâches en 5 jours (précédente : 23). Objectif atteint 4 jours sur 5 · essentiel 4 sur 5 · 20 des 24 gardées.')).toBeInTheDocument()
    const carte = screen.getByRole('region', { name: 'Ventes' })
    expect(within(carte).getByText('Faites cette semaine : Dossier subvention')).toBeInTheDocument()
    expect(within(carte).getByText('« Pose » attend « Livraison »')).toBeInTheDocument()
    expect(within(carte).getByText('Prochaine action : Devis Settat')).toBeInTheDocument()
    expect(within(carte).getByText('Rien de fait depuis 10 jours travaillés.')).toBeInTheDocument()
    expect(within(carte).getByText('à surveiller')).toBeInTheDocument()
    expect(within(carte).getByText('1/1')).toBeInTheDocument()
    expect(within(carte).getByLabelText('Intention de la semaine (facultatif)')).toHaveValue('')
    expect(within(carte).getByRole('checkbox', { name: 'Projet de la semaine' })).toBeChecked() // focus_projet_id = 3
    const boutons = within(carte).getAllByRole('button').map((b) => b.textContent)
    expect(boutons).toEqual(expect.arrayContaining(['Garder', 'Pause', 'Terminer', 'Suivant', 'Changer']))
  })

  it('passe visuelle n° 45 — « Projet de la semaine » est l\'étoile de la maquette (la case native reste lisible) ; échéance avec son mois', async () => {
    monter()
    const carte = await screen.findByRole('region', { name: 'Ventes' })
    const caseFocus = within(carte).getByRole('checkbox', { name: 'Projet de la semaine' })
    const etiquette = caseFocus.closest('label')
    expect(etiquette).toHaveClass('ep-focus')
    expect(etiquette.querySelector('svg')).not.toBeNull()
    expect(within(carte).getByText('échéance mar. 15 déc.')).toBeInTheDocument()
  })

  it('Semaine courte : « Semaine courte, on reprend lundi. » à la place du bilan', async () => {
    const r = revue()
    r.semaine_courte = true
    api.lireRevue.mockResolvedValue({ data: r })
    monter()
    expect(await screen.findByText('Semaine courte, on reprend lundi.')).toBeInTheDocument()
    expect(screen.queryByText(/26 tâches/)).toBeNull()
  })

  it('aucun projet actif : « Aucun projet actif »', async () => {
    const r = revue()
    r.cartes = []
    api.lireRevue.mockResolvedValue({ data: r })
    monter()
    expect(await screen.findByText('Aucun projet actif')).toBeInTheDocument()
  })

  it('une revue illisible est dite, sans carte inventée', async () => {
    api.lireRevue.mockRejectedValue(new Error('Network Error'))
    monter()
    expect(await screen.findByRole('alert')).toHaveTextContent('Connexion perdue')
    expect(screen.queryByRole('region')).toBeNull()
  })
})

describe('TCH93 — Revue : décisions', () => {
  it('Garder écrit la décision avec intention, prochaine action et focus, puis passe à la carte suivante', async () => {
    api.lireRevue.mockResolvedValue({ data: seconde() })
    monter()
    const user = userEvent.setup()
    const carte = await screen.findByRole('region', { name: 'Ventes' })
    await user.type(within(carte).getByLabelText('Intention de la semaine (facultatif)'), 'Signer Settat')
    await user.click(within(carte).getByRole('button', { name: 'Garder' }))
    expect(api.deciderRevue).toHaveBeenCalledWith(3, {
      semaine: '2026-11-16', intention: 'Signer Settat', prochaine_action_id: 20, decision: 'garder', focus: true, issue: null,
    })
    expect(await screen.findByRole('region', { name: 'Site web' })).toBeInTheDocument()
    expect(screen.getByText('2/2')).toBeInTheDocument()
  })

  it('Pause et Suivant écrivent leur décision', async () => {
    api.lireRevue.mockResolvedValue({ data: seconde() })
    monter()
    const user = userEvent.setup()
    await user.click(within(await screen.findByRole('region', { name: 'Ventes' })).getByRole('button', { name: 'Pause' }))
    expect(api.deciderRevue).toHaveBeenLastCalledWith(3, expect.objectContaining({ decision: 'pause' }))
    await user.click(within(await screen.findByRole('region', { name: 'Site web' })).getByRole('button', { name: 'Suivant' }))
    expect(api.deciderRevue).toHaveBeenLastCalledWith(5, expect.objectContaining({ decision: 'passe', prochaine_action_id: null, focus: false }))
  })

  it('Terminer demande « Atteint ou abandonné ? » et envoie l\'issue choisie', async () => {
    monter()
    const user = userEvent.setup()
    const carte = await screen.findByRole('region', { name: 'Ventes' })
    await user.click(within(carte).getByRole('button', { name: 'Terminer' }))
    expect(api.deciderRevue).not.toHaveBeenCalled()
    await user.click(within(carte).getByRole('radio', { name: 'Atteint' }))
    expect(api.deciderRevue).toHaveBeenCalledWith(3, expect.objectContaining({ decision: 'terminer', issue: 'atteint' }))
  })

  it('« Déjà « A » cette semaine. » reste sur la carte, sous la case, et la carte ne bouge pas', async () => {
    api.deciderRevue.mockRejectedValue({ response: { status: 400, data: { focus: ['Déjà « A » cette semaine.'] } } })
    monter()
    const user = userEvent.setup()
    const carte = await screen.findByRole('region', { name: 'Ventes' })
    await user.click(within(carte).getByRole('button', { name: 'Garder' }))
    expect(await within(carte).findByRole('alert')).toHaveTextContent('Déjà « A » cette semaine.')
    expect(within(carte).getByRole('checkbox', { name: 'Projet de la semaine' })).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('region', { name: 'Ventes' })).toBeInTheDocument()
  })

  it('Changer propose les tâches ouvertes du projet et retient le choix pour la décision', async () => {
    monter()
    const user = userEvent.setup()
    const carte = await screen.findByRole('region', { name: 'Ventes' })
    await user.click(within(carte).getByRole('button', { name: 'Changer' }))
    await user.selectOptions(await within(carte).findByLabelText('Prochaine action'), 'Timbres')
    expect(within(carte).getByText('Prochaine action : Timbres')).toBeInTheDocument()
    await user.click(within(carte).getByRole('button', { name: 'Garder' }))
    expect(api.deciderRevue).toHaveBeenCalledWith(3, expect.objectContaining({ prochaine_action_id: 42 }))
  })
})

describe('TCH93 — Revue : la fin', () => {
  it('après la dernière carte, « Planifier ma semaine » ouvre l\'agenda de la semaine en mode placer', async () => {
    monter()
    const user = userEvent.setup()
    await user.click(within(await screen.findByRole('region', { name: 'Ventes' })).getByRole('button', { name: 'Suivant' }))
    await user.click(await screen.findByRole('button', { name: 'Planifier ma semaine' }))
    await waitFor(() => expect(screen.getByTestId('lieu')).toHaveTextContent('/taches/agenda?vue=semaine&placer=1'))
  })
})
