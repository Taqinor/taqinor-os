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

/* TCH93 — la Revue rend `revue_projets.json` : bilan (ou « Semaine courte »), une carte par projet, les décisions
   écrivent `revue_decision.json`, la fin mène à « Planifier ma semaine ».
   R2-068 — UNE intention en tête ; Garder · Pause · Terminer en segmenté puis « Suivant → » ; reprise à la première
   carte non décidée ; revue déjà décidée = résumé. */

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
const suivant = (carte) => within(carte).getByRole('button', { name: 'Suivant →' })

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
    // R3-090 / L1 — la tête est le texte servi (« Cette semaine : 26 faites (23 la précédente). Essentiel 4 sur 5. »)
    expect(await screen.findByText(revue().bilan_semaine.texte)).toBeInTheDocument()
    expect(screen.queryByText(/Objectif atteint|gardées/)).toBeNull()
    const carte = screen.getByRole('region', { name: 'Ventes' })
    expect(within(carte).getByText('Faites cette semaine : Dossier subvention')).toBeInTheDocument()
    expect(within(carte).getByText('« Pose » attend « Livraison »')).toBeInTheDocument()
    expect(within(carte).getByText('Prochaine action : Devis Settat')).toBeInTheDocument()
    expect(within(carte).getByText('Rien de fait depuis 10 jours travaillés.')).toBeInTheDocument()
    expect(within(carte).getByText('à surveiller')).toBeInTheDocument()
    expect(within(carte).getByText('1/2')).toBeInTheDocument()
    // R2-068 — UNE seule intention, en tête (plus un champ par carte)
    expect(screen.getAllByLabelText('Intention de la semaine (facultatif)')).toHaveLength(1)
    expect(screen.getByLabelText('Intention de la semaine (facultatif)')).toHaveValue('')
    expect(within(carte).getByRole('checkbox', { name: 'Projet de la semaine' })).toBeChecked() // focus_projet_id = 3
    // R2-068 — Garder · Pause · Terminer en segmenté (Garder d'office), puis « Suivant → »
    const choix = within(carte).getByRole('radiogroup', { name: 'Décision' })
    expect(within(choix).getAllByRole('radio').map((r) => r.textContent)).toEqual(['Continuer', 'Pause', 'Terminer'])
    expect(within(choix).getByRole('radio', { name: 'Continuer' })).toBeChecked()
    expect(suivant(carte)).toBeInTheDocument()
    expect(within(carte).getByRole('button', { name: 'Changer' })).toBeInTheDocument()
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
  it('Suivant → écrit la décision (Garder d\'office) avec l\'intention d\'en tête, la prochaine action et le focus, puis passe à la carte suivante', async () => {
    api.lireRevue.mockResolvedValue({ data: seconde() })
    monter()
    const user = userEvent.setup()
    const carte = await screen.findByRole('region', { name: 'Ventes' })
    await user.type(screen.getByLabelText('Intention de la semaine (facultatif)'), 'Signer Settat')
    await user.click(suivant(carte))
    expect(api.deciderRevue).toHaveBeenCalledWith(3, {
      semaine: '2026-11-16', intention: 'Signer Settat', prochaine_action_id: 20, decision: 'garder', focus: true, issue: null,
    })
    expect(await screen.findByRole('region', { name: 'Site web' })).toBeInTheDocument()
    expect(screen.getByText('3/3')).toBeInTheDocument()
    // l'intention n'est PAS redemandée : le même champ, déjà rempli
    expect(screen.getAllByLabelText('Intention de la semaine (facultatif)')).toHaveLength(1)
    expect(screen.getByLabelText('Intention de la semaine (facultatif)')).toHaveValue('Signer Settat')
  })

  it('Pause (segmenté) et Passer écrivent leur décision', async () => {
    api.lireRevue.mockResolvedValue({ data: seconde() })
    monter()
    const user = userEvent.setup()
    const premiere = await screen.findByRole('region', { name: 'Ventes' })
    await user.click(within(premiere).getByRole('radio', { name: 'Pause' }))
    await user.click(suivant(premiere))
    expect(api.deciderRevue).toHaveBeenLastCalledWith(3, expect.objectContaining({ decision: 'pause' }))
    await user.click(within(await screen.findByRole('region', { name: 'Site web' })).getByRole('button', { name: 'Passer' }))
    expect(api.deciderRevue).toHaveBeenLastCalledWith(5, expect.objectContaining({ decision: 'passe', prochaine_action_id: null, focus: false }))
  })

  it("C-5 — « Pause » dit, en une phrase, ce qui reste prévu aujourd'hui (nombre SERVI) ; sans nombre servi, rien", async () => {
    const un = revue()
    un.cartes[0].prevues_aujourdhui_nb = 1
    api.lireRevue.mockResolvedValue({ data: un })
    const { unmount } = monter()
    const user = userEvent.setup()
    let carte = await screen.findByRole('region', { name: 'Ventes' })
    expect(within(carte).queryByText(/dans ta journée/)).toBeNull() // Garder : rien
    await user.click(within(carte).getByRole('radio', { name: 'Pause' }))
    expect(within(carte).getByText("1 tâche prévue aujourd'hui reste dans ta journée.")).toBeInTheDocument()
    await user.click(within(carte).getByRole('radio', { name: 'Continuer' }))
    expect(within(carte).queryByText(/dans ta journée/)).toBeNull()
    unmount()

    const deux = revue()
    deux.cartes[0].prevues_aujourdhui_nb = 2
    api.lireRevue.mockResolvedValue({ data: deux })
    const second = monter()
    carte = await screen.findByRole('region', { name: 'Ventes' })
    await user.click(within(carte).getByRole('radio', { name: 'Pause' }))
    expect(within(carte).getByText("2 tâches prévues aujourd'hui restent dans ta journée.")).toBeInTheDocument()
    second.unmount()

    // le serveur sert 0, ou ne sert pas le nombre : aucune phrase, aucun chiffre inventé
    for (const valeur of [0, undefined]) {
      const sans = revue()
      if (valeur === undefined) delete sans.cartes[0].prevues_aujourdhui_nb
      else sans.cartes[0].prevues_aujourdhui_nb = valeur
      api.lireRevue.mockResolvedValue({ data: sans })
      const rendu = monter()
      carte = await screen.findByRole('region', { name: 'Ventes' })
      await user.click(within(carte).getByRole('radio', { name: 'Pause' }))
      expect(within(carte).queryByText(/dans ta journée/)).toBeNull()
      rendu.unmount()
    }
  })

  it('Terminer demande « Atteint ou abandonné ? » : Suivant → reste éteint jusqu\'au choix, puis envoie l\'issue', async () => {
    monter()
    const user = userEvent.setup()
    const carte = await screen.findByRole('region', { name: 'Ventes' })
    await user.click(within(carte).getByRole('radio', { name: 'Terminer' }))
    expect(suivant(carte)).toBeDisabled()
    expect(api.deciderRevue).not.toHaveBeenCalled()
    await user.click(within(carte).getByRole('radio', { name: 'Atteint' }))
    await user.click(suivant(carte))
    expect(api.deciderRevue).toHaveBeenCalledWith(3, expect.objectContaining({ decision: 'terminer', issue: 'atteint' }))
  })

  it('« Déjà « A » cette semaine. » reste sur la carte, sous la case, et la carte ne bouge pas', async () => {
    api.deciderRevue.mockRejectedValue({ response: { status: 400, data: { focus: ['Déjà « A » cette semaine.'] } } })
    monter()
    const user = userEvent.setup()
    const carte = await screen.findByRole('region', { name: 'Ventes' })
    await user.click(suivant(carte))
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
    await user.click(suivant(carte))
    expect(api.deciderRevue).toHaveBeenCalledWith(3, expect.objectContaining({ prochaine_action_id: 42 }))
  })
})

describe('R2-068 — Revue : reprise et résumé', () => {
  const decide = (carte, decision, intention = '') => { carte.revue = { intention, decision, focus: false } }

  it('une revue interrompue reprend à la PREMIÈRE carte non décidée (plus de retour à 1/N)', async () => {
    const r = seconde()
    decide(r.cartes[0], 'garder', 'Signer Settat')
    api.lireRevue.mockResolvedValue({ data: r })
    monter()
    expect(await screen.findByRole('region', { name: 'Site web' })).toBeInTheDocument()
    expect(screen.getByText('3/3')).toBeInTheDocument()
    expect(screen.getByLabelText('Intention de la semaine (facultatif)')).toHaveValue('Signer Settat') // l'intention déjà posée revient
  })

  it('revue déjà décidée cette semaine : le RÉSUMÉ et « Planifier ma semaine », aucune carte', async () => {
    const r = seconde()
    decide(r.cartes[0], 'garder')
    decide(r.cartes[2], 'pause')
    api.lireRevue.mockResolvedValue({ data: r })
    monter()
    const user = userEvent.setup()
    const resume = await screen.findByRole('list', { name: 'Résumé de la revue' })
    expect(within(resume).getByText('Ventes').closest('li')).toHaveTextContent('Continue')
    expect(within(resume).getByText('Site web').closest('li')).toHaveTextContent('En pause')
    expect(screen.queryByRole('region', { name: 'Ventes' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Planifier ma semaine' }))
    await waitFor(() => expect(screen.getByTestId('lieu')).toHaveTextContent('/taches/agenda?vue=semaine&placer=1'))
  })

  it('R3-090 — un projet déjà mis en pause cette semaine (servi avec sa décision) n\'est pas redemandé, il est dans le résumé', async () => {
    monter()
    const user = userEvent.setup()
    await user.type(await screen.findByPlaceholderText('Ce que tu veux finir cette semaine…'), 'Signer Settat')
    await user.click(suivant(screen.getByRole('region', { name: 'Ventes' })))
    expect(api.deciderRevue).toHaveBeenCalledTimes(1)
    const resume = await screen.findByRole('list', { name: 'Résumé de la revue' })
    expect(within(resume).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['VentesContinue', 'ÉquipeEn pause'])
    expect(screen.getByText(/Intention de la semaine/).closest('p')).toHaveTextContent('Intention de la semaine · Signer Settat')
  })

  it('R3-090 — toucher une ligne du résumé rouvre sa carte ; la décision écrite ramène au résumé', async () => {
    const r = revue()
    decide(r.cartes[0], 'garder', 'Signer Settat')
    api.lireRevue.mockResolvedValue({ data: r })
    monter()
    const user = userEvent.setup()
    const resume = await screen.findByRole('list', { name: 'Résumé de la revue' })
    await user.click(within(resume).getByRole('button', { name: /Équipe/ }))
    const carte = await screen.findByRole('region', { name: 'Équipe' })
    expect(within(carte).getByRole('radio', { name: 'Pause' })).toBeChecked()
    await user.click(within(carte).getByRole('radio', { name: 'Continuer' }))
    await user.click(suivant(carte))
    expect(api.deciderRevue).toHaveBeenLastCalledWith(r.cartes[1].projet.id, expect.objectContaining({ decision: 'garder', intention: 'Signer Settat' }))
    const apres = await screen.findByRole('list', { name: 'Résumé de la revue' })
    expect(within(apres).getByText('Équipe').closest('li')).toHaveTextContent('Continue')
  })

  it('la dernière décision du parcours mène au même résumé', async () => {
    monter()
    const user = userEvent.setup()
    await user.click(suivant(await screen.findByRole('region', { name: 'Ventes' })))
    const resume = await screen.findByRole('list', { name: 'Résumé de la revue' })
    expect(within(resume).getByText('Ventes').closest('li')).toHaveTextContent('Continue')
    expect(screen.getByRole('button', { name: 'Planifier ma semaine' })).toBeInTheDocument()
  })
})

describe('TCH93 — Revue : la fin', () => {
  it('après la dernière carte, « Planifier ma semaine » ouvre l\'agenda de la semaine en mode placer', async () => {
    monter()
    const user = userEvent.setup()
    await user.click(within(await screen.findByRole('region', { name: 'Ventes' })).getByRole('button', { name: 'Passer' }))
    await user.click(await screen.findByRole('button', { name: 'Planifier ma semaine' }))
    await waitFor(() => expect(screen.getByTestId('lieu')).toHaveTextContent('/taches/agenda?vue=semaine&placer=1'))
  })

  it.each([
    ['mardi', '2026-11-17T09:00:00', '/taches/agenda?vue=semaine&placer=1'],
    ['jeudi', '2026-11-19T09:00:00', '/taches/agenda?vue=semaine&placer=1&jour=2026-11-23'],
    ['dimanche', '2026-11-22T18:00:00', '/taches/agenda?vue=semaine&placer=1&jour=2026-11-23'],
    ['jeudi de fin de mois', '2026-12-31T09:00:00', '/taches/agenda?vue=semaine&placer=1&jour=2027-01-04'],
  ])('R3-099 — un %s (%s), « Planifier ma semaine » ouvre %s', async (_jour, maintenant, attendu) => {
    vi.setSystemTime(new Date(maintenant))
    monter()
    const user = userEvent.setup()
    await user.click(within(await screen.findByRole('region', { name: 'Ventes' })).getByRole('button', { name: 'Passer' }))
    await user.click(await screen.findByRole('button', { name: 'Planifier ma semaine' }))
    await waitFor(() => expect(screen.getByTestId('lieu').textContent).toBe(attendu))
  })
})
