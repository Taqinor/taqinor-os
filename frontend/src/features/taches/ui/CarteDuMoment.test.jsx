import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../lib/gestes'
import Progression from '../aujourdhui/Progression'
import CarteDuMoment from './CarteDuMoment'

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const api = (await import('../../../api/axios')).default
const { default: Aujourdhui } = await import('../../../pages/taches/Aujourdhui')

/* TCH77 — chaque type de carte du moment est rendu (échantillons carte_du_moment.json,
   proposition.json, vu.json) et la réponse part à `rythme/propositions/{id}/repondre/` ;
   la progression lit `aujourdhui.json` : « 1 sur 5 · essentiel 0/1 », « Reprise », détail au toucher. */

const contrat = (nom) => structuredClone(exempleContrat('taches', nom))
const carteRythme = () => contrat('carte_du_moment')
const proposition = () => contrat('proposition')

let numero = 0
function monter(props) {
  numero += 1
  const poignees = { onRepondre: vi.fn(), onGarder: vi.fn(), onAlleger: vi.fn(), onBilan: vi.fn(), onNaviguer: vi.fn(), onCopilote: vi.fn() }
  const rendu = render(
    <CarteDuMoment jour={`2030-01-${String(numero).padStart(2, '0')}`} maintenant="2026-11-17T15:00:00+01:00" objectif={5}
      avecAstuce={false} {...poignees} {...props} />,
  )
  return { ...rendu, ...poignees }
}

beforeEach(() => {
  vi.clearAllMocks()
  window.localStorage.clear()
  reinitialiserGestes()
})

describe('TCH77 — chaque type de carte du moment', () => {
  it('`rythme` : le texte de la proposition et ses boutons ; la réponse remonte avec la proposition', async () => {
    const { onRepondre } = monter({ carte: carteRythme() })
    expect(screen.getByText('Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Monter à 6' }))
    expect(onRepondre).toHaveBeenCalledWith(expect.objectContaining({ id: 41 }), 'oui')
    await userEvent.click(screen.getByRole('button', { name: 'Pas maintenant' }))
    expect(onRepondre).toHaveBeenLastCalledWith(expect.objectContaining({ id: 41 }), 'pas_maintenant')
  })

  it('`pause` rend la même carte à réponse', () => {
    const carte = carteRythme()
    carte.type = 'pause'
    carte.proposition.boutons = [{ reponse: 'reactiver', libelle: 'Le réactiver' }, { reponse: 'ok', libelle: 'OK' }]
    monter({ carte })
    expect(screen.getByRole('button', { name: 'Le réactiver' })).toBeInTheDocument()
  })

  it('`retour` : « Tu reviens après 10 jours » avec ses deux boutons', async () => {
    const carte = contrat('vu').carte_du_moment
    const { onRepondre } = monter({ carte })
    expect(screen.getByText('Tu reviens après 10 jours : 18 tâches attendaient.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Les remettre dans Proposé' }))
    expect(onRepondre).toHaveBeenCalledWith(expect.objectContaining({ type: 'retour' }), 'remettre_dans_propose')
    expect(screen.getByRole('button', { name: 'Les voir une par une' })).toBeInTheDocument()
  })

  it('`garder` : « 3 tâches proposées pour atteindre 5 » et Garder ces 3 ; une seule : Garder celle-ci', async () => {
    const { onGarder, unmount } = monter({ carte: { type: 'garder', proposition: null, donnees: { n: 3, objectif: 5 } } })
    expect(screen.getByText('3 tâches proposées')).toBeInTheDocument()
    expect(screen.getByText('pour atteindre 5')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Garder ces 3' }))
    expect(onGarder).toHaveBeenCalledTimes(1)
    unmount()
    monter({ carte: { type: 'garder', proposition: null, donnees: { n: 1, objectif: 5 } } })
    expect(screen.getByText('1 tâche proposée')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Garder celle-ci' })).toBeInTheDocument()
  })

  it('`alleger` : « 1 sur 5 à 15 h », Alléger ma journée, et « Pas maintenant » écarte la carte sans rien écrire', async () => {
    const { onAlleger, onRepondre } = monter({ carte: { type: 'alleger', proposition: null, donnees: { faites: 1, prevues: 4 } } })
    expect(screen.getByText('1 sur 5 à 15 h')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Alléger ma journée' }))
    expect(onAlleger).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Pas maintenant' }))
    expect(screen.queryByText('1 sur 5 à 15 h')).toBeNull()
    expect(onRepondre).not.toHaveBeenCalled()
  })

  it('`faire_bilan` : « Ta journée se termine. » et Faire le bilan', async () => {
    const { onBilan } = monter({ carte: { type: 'faire_bilan', proposition: null, donnees: {} } })
    expect(screen.getByText('Ta journée se termine.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Faire le bilan' }))
    expect(onBilan).toHaveBeenCalledWith(null)
  })

  it('`bilan_hier` : Faire le bilan d\'hier ouvre le bilan d\'hier ; Passer l\'écarte', async () => {
    const { onBilan } = monter({ carte: { type: 'bilan_hier', proposition: null, donnees: { jour: '2026-11-16' } } })
    expect(screen.getByText("Le bilan d'hier n'est pas fait : il reste possible jusqu'à midi.")).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: "Faire le bilan d'hier" }))
    expect(onBilan).toHaveBeenCalledWith('2026-11-16')
    await userEvent.click(screen.getByRole('button', { name: 'Passer' }))
    expect(screen.queryByText(/Le bilan d'hier/)).toBeNull()
  })

  it('`revelation` mon_iphone : le bouton mène à Mon iPhone et répond OK ; OK seul répond OK', async () => {
    const carte = carteRythme()
    carte.type = 'revelation'
    carte.proposition = Object.assign(proposition(), {
      type: 'revelation', cle: 'mon_iphone', texte: 'Mets tes tâches sur ton iPhone : notifications, calendrier, Siri et tuile.',
      boutons: [{ reponse: 'ok', libelle: 'OK' }],
    })
    const { onRepondre, onNaviguer } = monter({ carte })
    await userEvent.click(screen.getByRole('button', { name: 'Mon iPhone' }))
    expect(onRepondre).toHaveBeenCalledWith(expect.objectContaining({ cle: 'mon_iphone' }), 'ok')
    expect(onNaviguer).toHaveBeenCalledWith('/taches/reglages/iphone')
  })

  it('aucune carte du serveur : une astuce par jour, chacune une seule fois, « OK » la retient', async () => {
    const { unmount } = monter({ carte: null, avecAstuce: true, jour: '2030-02-01' })
    expect(screen.getByText('Balaie une ligne vers la gauche pour la reporter, vers la droite pour la cocher.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'OK' }))
    expect(screen.queryByText(/Balaie une ligne/)).toBeNull()
    unmount()
    monter({ carte: null, avecAstuce: true, jour: '2030-02-01' })
    expect(screen.queryByRole('region', { name: 'Astuce' })).toBeNull() // déjà une aujourd'hui
    document.body.innerHTML = ''
    monter({ carte: null, avecAstuce: true, jour: '2030-02-02' })
    expect(screen.getByText('Touche n pour ajouter, ? pour voir les touches.')).toBeInTheDocument()
  })

  it('une carte du serveur passe avant l\'astuce', () => {
    monter({ carte: carteRythme(), avecAstuce: true, jour: '2030-03-01' })
    expect(screen.getByText(/On passe à 6/)).toBeInTheDocument()
    expect(screen.queryByText(/Balaie une ligne/)).toBeNull()
  })

  it('hors ligne : les boutons à réponse sont grisés', () => {
    monter({ carte: carteRythme(), enLigne: false })
    expect(screen.getByRole('button', { name: 'Monter à 6' })).toHaveAttribute('aria-disabled', 'true')
  })
})

describe('TCH77 — la réponse part à repondre/ depuis l\'écran', () => {
  it('Monter à 6 poste {reponse: "oui"} sur rythme/propositions/41/repondre/ et la carte disparaît', async () => {
    api.get.mockResolvedValue({ data: contrat('aujourdhui') })
    api.post.mockImplementation((url) => Promise.resolve({ data: url.includes('repondre') ? contrat('proposition_repondue') : {} }))
    render(<MemoryRouter><Aujourdhui /></MemoryRouter>)
    await userEvent.click(await screen.findByRole('button', { name: 'Monter à 6' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/rythme/propositions/41/repondre/', { reponse: 'oui' }))
    await waitFor(() => expect(screen.queryByText(/On passe à 6/)).toBeNull())
    expect(screen.getByText('1 sur 5')).toBeInTheDocument()
  })

  it('l\'écran dit « vu » à l\'ouverture, avant de lire la journée', async () => {
    api.get.mockResolvedValue({ data: contrat('aujourdhui') })
    api.post.mockResolvedValue({ data: contrat('vu') })
    render(<MemoryRouter><Aujourdhui /></MemoryRouter>)
    await screen.findByText('Devis Settat')
    expect(api.post).toHaveBeenCalledWith('/taches/vu/', { ecran: 'aujourdhui' })
  })
})

describe('TCH77 — la ligne de progression', () => {
  const aujourdhui = () => contrat('aujourdhui')
  const monterProgression = (donnees) => render(<MemoryRouter><Progression donnees={donnees} onRythme={vi.fn()} /></MemoryRouter>)

  it('pousser : « 1 sur 5 · essentiel 0/1 » et 1 segment fait sur 5', () => {
    const { container } = monterProgression(aujourdhui())
    expect(screen.getByRole('button')).toHaveTextContent('1 sur 5 · essentiel 0/1')
    expect(container.querySelectorAll('.segments i')).toHaveLength(5)
    expect(container.querySelectorAll('.segments i.fait')).toHaveLength(1)
  })

  it('sans essentiel : « 1 sur 5 » seul', () => {
    const d = aujourdhui()
    d.progression.essentiel_prevues = 0
    monterProgression(d)
    expect(screen.getByRole('button')).toHaveTextContent(/^1 sur 5$/)
  })

  it('tenir : « ton rythme : 3 à 5 » ; libre : « 1 faite » ; retour : « Reprise · objectif 5 »', () => {
    const tenir = aujourdhui()
    Object.assign(tenir.objectif, { mode: 'tenir', zone: [3, 5] })
    const { unmount } = monterProgression(tenir)
    expect(screen.getByRole('button')).toHaveTextContent('1 sur 5 · ton rythme : 3 à 5')
    unmount()
    const libre = aujourdhui()
    Object.assign(libre.objectif, { mode: 'libre', nb: null })
    const rendu = monterProgression(libre)
    expect(screen.getByRole('button')).toHaveTextContent(/^1 faite$/)
    rendu.unmount()
    const reprise = aujourdhui()
    reprise.progression.reprise = true
    monterProgression(reprise)
    expect(screen.getByRole('button')).toHaveTextContent('Reprise · objectif 5')
  })

  it('au toucher : objectif et source, gardées faites, temps, temps libre, puis Mon rythme', async () => {
    const onRythme = vi.fn()
    render(<MemoryRouter><Progression donnees={aujourdhui()} onRythme={onRythme} /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: /Détail de la journée/ }))
    const detail = screen.getByRole('group', { name: 'Détail de la journée' })
    expect(detail).toHaveTextContent('Objectif du jour : 5 (accepté)')
    expect(detail).toHaveTextContent('1 des 4 gardées')
    expect(detail).toHaveTextContent('Temps : 1 h 15 prévues + 1 sans durée')
    expect(detail).toHaveTextContent('Temps libre : 3 h (4 h moins 1 h de rendez-vous)')
    await userEvent.click(screen.getByRole('button', { name: /Mon rythme/ }))
    expect(onRythme).toHaveBeenCalledTimes(1)
  })
})
