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

/** R2-015 — l'appareil simulé : `doigt` = `(pointer: coarse)` vrai (iPhone), sinon un bureau. */
const appareil = (doigt) => {
  window.matchMedia = (q) => ({ matches: Boolean(doigt) && q.includes('coarse'), media: q, addEventListener() {}, removeEventListener() {} })
}

beforeEach(() => {
  vi.clearAllMocks()
  window.localStorage.clear()
  reinitialiserGestes()
  appareil(false)
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

  it('aucune carte du serveur : une astuce par jour, chacune une seule fois, « OK » la retient (au doigt)', async () => {
    appareil(true)
    const { unmount } = monter({ carte: null, avecAstuce: true, jour: '2030-02-01' })
    expect(screen.getByText('Balaie une ligne vers la gauche pour la reporter, vers la droite pour la cocher.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'OK' }))
    expect(screen.queryByText(/Balaie une ligne/)).toBeNull()
    unmount()
    monter({ carte: null, avecAstuce: true, jour: '2030-02-01' })
    expect(screen.queryByRole('region', { name: 'Astuce' })).toBeNull() // déjà une aujourd'hui
    document.body.innerHTML = ''
    monter({ carte: null, avecAstuce: true, jour: '2030-02-02' })
    expect(screen.getByText('Garde le doigt sur une ligne pour voir toutes ses actions.')).toBeInTheDocument()
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

describe('R2-015 — une astuce par appareil : le balayage n\'est jamais appris à la souris', () => {
  const lesAstuces = async (jours, doigt) => {
    appareil(doigt)
    const vues = []
    for (const jour of jours) {
      const { unmount } = monter({ carte: null, avecAstuce: true, jour })
      const region = screen.queryByRole('region', { name: 'Astuce' })
      vues.push(region ? region.querySelector('b').textContent : null)
      if (region) await userEvent.click(screen.getByRole('button', { name: 'OK' }))
      unmount()
    }
    return vues
  }

  it('au bureau : jamais « Balaie » ni l\'appui long ; touches, glisser vers l\'agenda, puis #nom', async () => {
    const vues = await lesAstuces(['2031-01-01', '2031-01-02', '2031-01-03', '2031-01-04'], false)
    expect(vues).toEqual([
      'Touche n pour ajouter, ? pour voir les touches.',
      "Glisse une tâche sur l'agenda pour lui donner une heure.",
      'Tape #nom pour ranger dans un projet.',
      null,
    ])
  })

  it('au doigt : le balayage, puis l\'appui long, puis #nom ; jamais les touches du clavier', async () => {
    const vues = await lesAstuces(['2031-02-01', '2031-02-02', '2031-02-03', '2031-02-04'], true)
    expect(vues).toEqual([
      'Balaie une ligne vers la gauche pour la reporter, vers la droite pour la cocher.',
      'Garde le doigt sur une ligne pour voir toutes ses actions.',
      'Tape #nom pour ranger dans un projet.',
      null,
    ])
  })
})

describe('R2-014 — une carte au plus par matin, et aucun constat qui remonte après le bilan', () => {
  it('répondre à une carte du serveur ne fait pas venir une astuce à sa place, ni maintenant ni après rechargement', async () => {
    appareil(true)
    const jour = '2031-03-01'
    const onRepondre = vi.fn()
    const props = { jour, maintenant: '2026-11-17T09:10:00+01:00', objectif: 5, avecAstuce: true, onRepondre }
    const { rerender } = render(<CarteDuMoment carte={carteRythme()} {...props} />)
    await userEvent.click(screen.getByRole('button', { name: 'Monter à 6' }))
    expect(onRepondre).toHaveBeenCalledWith(expect.objectContaining({ id: 41 }), 'oui')
    rerender(<CarteDuMoment carte={null} {...props} />) // le parent retire la carte répondue
    expect(screen.queryByRole('region', { name: 'Astuce' })).toBeNull()
    expect(screen.queryByText(/Balaie une ligne/)).toBeNull()
    document.body.innerHTML = ''
    render(<CarteDuMoment carte={null} {...props} />) // rechargement : la journée reste prise
    expect(screen.queryByRole('region', { name: 'Astuce' })).toBeNull()
  })

  it('« Pas maintenant » écarte la carte sans faire venir une astuce ; le lendemain une astuce revient', async () => {
    appareil(true)
    monter({ carte: { type: 'alleger', proposition: null, donnees: { faites: 1, prevues: 4 } }, avecAstuce: true, jour: '2031-03-02' })
    await userEvent.click(screen.getByRole('button', { name: 'Pas maintenant' }))
    expect(screen.queryByRole('region')).toBeNull()
    document.body.innerHTML = ''
    monter({ carte: null, avecAstuce: true, jour: '2031-03-03' })
    expect(screen.getByRole('region', { name: 'Astuce' })).toBeInTheDocument()
  })

  it('Garder compte aussi comme une carte répondue', async () => {
    const { onGarder } = monter({ carte: { type: 'garder', proposition: null, donnees: { n: 2, objectif: 5 } }, avecAstuce: true, jour: '2031-03-04' })
    await userEvent.click(screen.getByRole('button', { name: 'Garder ces 2' }))
    expect(onGarder).toHaveBeenCalledTimes(1)
    document.body.innerHTML = ''
    monter({ carte: null, avecAstuce: true, jour: '2031-03-04' })
    expect(screen.queryByRole('region', { name: 'Astuce' })).toBeNull()
  })

  it('un constat n\'est plus montré une fois le bilan fait ; avant le bilan il l\'est', () => {
    const constat = () => {
      const c = carteRythme()
      c.proposition = Object.assign(proposition(), {
        type: 'constat', cle: 'C5', texte: '57 % de tes 51 tâches finies entre 10 h et 12 h.', boutons: [{ reponse: 'ok', libelle: 'OK' }],
      })
      return c
    }
    const { unmount } = monter({ carte: constat(), jour: '2031-03-05' })
    expect(screen.getByText('57 % de tes 51 tâches finies entre 10 h et 12 h.')).toBeInTheDocument()
    unmount()
    const { container } = monter({ carte: constat(), jour: '2031-03-06', bilanFait: true, avecAstuce: true })
    expect(container).toBeEmptyDOMElement()
  })

  it('un constat à question se lit « phrase + question » et « Oui » y répond', async () => {
    const c = carteRythme()
    c.proposition = Object.assign(proposition(), {
      type: 'constat', cle: 'C7', texte: '2 tâches reportées 3 fois ou plus. Les revoir maintenant ?',
      boutons: [{ reponse: 'oui', libelle: 'Oui' }, { reponse: 'pas_maintenant', libelle: 'Pas maintenant' }],
    })
    const { onRepondre } = monter({ carte: c, jour: '2031-03-07' })
    expect(screen.getByText('2 tâches reportées 3 fois ou plus. Les revoir maintenant ?')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Oui' }))
    expect(onRepondre).toHaveBeenCalledWith(expect.objectContaining({ cle: 'C7' }), 'oui')
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
    d.essentiel = []
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

  it('au toucher (R3-020) : « 1 faite sur 5 », le temps contre le disponible, puis Mon rythme', async () => {
    const onRythme = vi.fn()
    render(<MemoryRouter><Progression donnees={aujourdhui()} onRythme={onRythme} /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: /Détail de la journée/ }))
    const detail = screen.getByRole('group', { name: 'Détail de la journée' })
    expect(detail).toHaveTextContent('1 faite sur 5')
    expect(detail).not.toHaveTextContent('accepté')
    expect(detail).not.toHaveTextContent('gardée')
    expect(detail).toHaveTextContent('Reste : 1 h 15 pour 3 h disponibles · 1 sans durée') // R4-01 : LA charge servie
    expect(detail).not.toHaveTextContent('Temps libre')
    await userEvent.click(screen.getByRole('button', { name: /Mon rythme/ }))
    expect(onRythme).toHaveBeenCalledTimes(1)
  })
})

describe('R3-022 — au plus UNE carte de conseil par jour (astuce ou révélation), ni maintenant ni au rechargement', () => {
  const revelation = () => ({ type: 'revelation', proposition: { ...proposition(), type: 'revelation', cle: 'mon_iphone', texte: 'Mets tes tâches sur ton iPhone.', boutons: [] } })

  it('OK sur l\'astuce du balayage : la révélation servie ne prend PAS sa place, même rechargée', async () => {
    appareil(true)
    const jour = '2032-05-04'
    const poignees = { onRepondre: vi.fn(), onNaviguer: vi.fn(), onCopilote: vi.fn() }
    const { rerender, unmount } = render(<CarteDuMoment jour={jour} carte={revelation()} {...poignees} />)
    expect(screen.getByText(/Balaie une ligne/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'OK' }))
    rerender(<CarteDuMoment jour={jour} carte={revelation()} {...poignees} />)
    expect(screen.queryByRole('region', { name: 'Astuce' })).toBeNull()
    unmount()
    render(<CarteDuMoment jour={jour} carte={revelation()} {...poignees} />) // « rechargement »
    expect(screen.queryByRole('region', { name: 'Astuce' })).toBeNull()
    // le lendemain, la carte de conseil revient (une par jour)
    render(<CarteDuMoment jour="2032-05-05" carte={revelation()} {...poignees} />)
    expect(screen.getAllByRole('region', { name: 'Astuce' })).toHaveLength(1)
  })

  it('OK sur une révélation : aucune astuce ni autre révélation ce jour-là', async () => {
    appareil(true)
    const jour = '2032-06-01'
    const poignees = { onRepondre: vi.fn(), onNaviguer: vi.fn(), onCopilote: vi.fn() }
    // toutes les astuces du doigt déjà vues : la révélation est la carte de conseil du jour
    window.localStorage.setItem('taches:astuces', JSON.stringify({ vues: ['balayage', 'appui_long', 'diese'], jour: '2032-05-31' }))
    const { rerender } = render(<CarteDuMoment jour={jour} carte={revelation()} {...poignees} />)
    await userEvent.click(screen.getByRole('button', { name: 'OK' }))
    expect(poignees.onRepondre).toHaveBeenCalledWith(expect.objectContaining({ cle: 'mon_iphone' }), 'ok')
    rerender(<CarteDuMoment jour={jour} carte={{ ...revelation(), proposition: { ...revelation().proposition, cle: 'revue', id: 99 } }} {...poignees} />)
    expect(screen.queryByRole('region', { name: 'Astuce' })).toBeNull()
  })
})
