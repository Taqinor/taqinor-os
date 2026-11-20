import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/tachesApi', async (original) => ({
  ...(await original()),
  apercuPlanification: vi.fn(),
  planifierProjet: vi.fn(),
  saisieRapide: vi.fn(),
  planifierTache: vi.fn(),
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
  // l'analyseur de la saisie (aperçu, rien écrit) : par défaut il ne lit aucune date
  api.saisieRapide.mockImplementation(lecture({}))
})

/** R4-27 — réponse de `saisie-rapide/` aperçu pour une phrase : les jours lus (`{ mot: 'AAAA-MM-JJ' }`) en jetons. */
const ligneModele = exempleContrat('taches', 'saisie_apercu').lignes[0]
function lecture(jours) {
  return ({ texte }) => {
    const jetons = Object.entries(jours).filter(([mot]) => texte.includes(mot)).map(([mot, valeur]) => ({
      type: 'jour', source: mot, debut: texte.indexOf(mot), fin: texte.indexOf(mot) + mot.length, valeur, libelle: mot,
    }))
    const titre = jetons.reduce((t, j) => t.replace(j.source, ''), texte).replace(/\s+/g, ' ').trim()
    return Promise.resolve({ data: {
      projets_communs: [], projets_nouveaux: [],
      lignes: [{ ...ligneModele, titre, jetons, champs: jetons.length ? { jour_prevu: jetons[0].valeur } : {} }],
    } })
  }
}
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

  it('R3-128 — pas 1 : le pied « Suivant » suit le contenu (jamais collé sur les priorités), il reste en bas au pas 2 ; « Plus » porte son chevron', async () => {
    const { container } = monter()
    const user = utilisateur()
    expect(container.querySelector('.ep-planifier-pied')).toHaveClass('pas-un')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    expect(container.querySelector('.ep-planifier-pied')).not.toHaveClass('pas-un')
    const resume = container.querySelector('.ep-plus > summary')
    expect(resume).toHaveTextContent('Plus')
    expect(resume.querySelector('svg')).not.toBeNull()
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

  it('Raccord F2 — une action laissée « Sans jour » part en `quand` vide (valeur du serveur ; `sans_jour` est refusé)', async () => {
    monter()
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.type(screen.getByLabelText('Nouvelle action'), 'Appeler le loueur')
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    expect(within(screen.getByRole('radiogroup', { name: 'Quand : Appeler le loueur' })).getByRole('radio', { name: 'Sans jour' }))
      .toHaveAttribute('aria-checked', 'true')
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(api.planifierProjet).toHaveBeenCalledWith(3, expect.objectContaining({
      actions: [{ titre: 'Appeler le loueur', quand: '' }],
    }))
  })

  it('R2-069 — la barre d\'étapes dit où l\'on en est ; chaque action se retire par ×', async () => {
    monter()
    const user = utilisateur()
    const barre = screen.getByRole('list', { name: 'Étapes du rituel' })
    expect(within(barre).getAllByRole('listitem')).toHaveLength(2)
    expect(within(barre).getAllByRole('listitem')[0]).toHaveAttribute('aria-current', 'step')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    expect(within(screen.getByRole('list', { name: 'Étapes du rituel' })).getAllByRole('listitem')[1]).toHaveAttribute('aria-current', 'step')
    for (const titre of ['Réserver le stand', 'Imprimer les badges']) {
      await user.type(screen.getByLabelText('Nouvelle action'), titre)
      await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    }
    await user.click(screen.getByRole('button', { name: 'Retirer « Réserver le stand »' }))
    expect(screen.queryByText('Réserver le stand')).toBeNull()
    expect(screen.getByText('Imprimer les badges')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(api.planifierProjet).toHaveBeenCalledWith(3, expect.objectContaining({ actions: [{ titre: 'Imprimer les badges', quand: '' }] }))
  })

  it('R2-069 — la date choisie se lit en français sous le champ (jamais seulement le format du navigateur)', async () => {
    monter()
    const user = utilisateur()
    await user.click(screen.getByRole('radio', { name: '2 semaines' }))
    expect(screen.getByText('mar. 1 déc.')).toBeInTheDocument() // 17/11 + 14 j = 01/12/2026
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

describe('R4-27 — « Premières actions » : les dates lues comme dans la saisie', () => {
  const ajouter = async (user, texte) => {
    await user.type(screen.getByLabelText('Nouvelle action'), texte)
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
  }

  it('« … demain » → Demain, « … samedi » → sam. 21 ; le mot lu quitte le titre ; Terminer pose le jour du samedi', async () => {
    api.saisieRapide.mockImplementation(lecture({ demain: '2026-11-18', samedi: '2026-11-21' }))
    const creees = [
      { ...reponseContrat('taches', 'planification').data.creees[0], id: 70, titre: 'Récupérer les 24 panneaux au dépôt', lock_version: 1 },
      { ...reponseContrat('taches', 'planification').data.creees[0], id: 71, titre: 'Poser les rails', lock_version: 1 },
    ]
    api.planifierProjet.mockResolvedValue({ data: { ...reponseContrat('taches', 'planification').data, creees } })
    api.planifierTache.mockResolvedValue({ data: { ...exempleContrat('taches', 'tache_ecrite'), tache: { ...creees[1], jour_prevu: '2026-11-21', lock_version: 2 } } })
    const onTermine = vi.fn()
    monter({ onTermine })
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await ajouter(user, 'Récupérer les 24 panneaux au dépôt demain')
    await ajouter(user, 'Poser les rails samedi')
    const demain = await screen.findByRole('radiogroup', { name: 'Quand : Récupérer les 24 panneaux au dépôt' })
    expect(within(demain).getByRole('radio', { name: 'Demain' })).toHaveAttribute('aria-checked', 'true')
    const samedi = await screen.findByRole('radiogroup', { name: 'Quand : Poser les rails' })
    expect(within(samedi).getByRole('radio', { name: 'sam. 21' })).toHaveAttribute('aria-checked', 'true')
    expect(within(samedi).getByRole('radio', { name: 'Sans jour' })).toHaveAttribute('aria-checked', 'false')
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(api.planifierProjet).toHaveBeenCalledWith(3, expect.objectContaining({
      actions: [{ titre: 'Récupérer les 24 panneaux au dépôt', quand: 'demain' }, { titre: 'Poser les rails', quand: '' }],
    }))
    expect(api.planifierTache).toHaveBeenCalledTimes(1)
    expect(api.planifierTache).toHaveBeenCalledWith(71, {
      jour_prevu: '2026-11-21', moment: '', heure_debut: null, quelque_jour: false, lock_version: 1,
    })
    // l'écran reçoit la tâche du samedi à son jour
    expect(onTermine.mock.calls[0][0].creees.find((c) => c.id === 71).jour_prevu).toBe('2026-11-21')
  })

  it("« Terminer » touché avant le retour de la lecture : il l'attend (jamais « … demain » dans un titre)", async () => {
    let lacher
    api.saisieRapide.mockImplementation((corps) => new Promise((r) => { lacher = () => r(lecture({ demain: '2026-11-18' })(corps)) }))
    monter()
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await ajouter(user, 'Appeler le loueur demain')
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(api.planifierProjet).not.toHaveBeenCalled()
    await act(async () => { lacher() })
    await vi.waitFor(() => expect(api.planifierProjet).toHaveBeenCalledWith(3, expect.objectContaining({
      actions: [{ titre: 'Appeler le loueur', quand: 'demain' }],
    })))
  })

  it('R4-VERIF — une action tapée SANS Entrée est prise par « Terminer » : même lecture (« lundi » devient sa date), dans le corps envoyé', async () => {
    api.saisieRapide.mockImplementation(lecture({ lundi: '2026-11-23' }))
    const creees = [
      { ...reponseContrat('taches', 'planification').data.creees[0], id: 70, titre: 'Commander les panneaux', lock_version: 1 },
      { ...reponseContrat('taches', 'planification').data.creees[0], id: 71, titre: 'Brancher le compteur', lock_version: 1 },
    ]
    api.planifierProjet.mockResolvedValue({ data: { ...reponseContrat('taches', 'planification').data, creees } })
    api.planifierTache.mockResolvedValue({ data: { ...exempleContrat('taches', 'tache_ecrite'), tache: { ...creees[1], jour_prevu: '2026-11-23', lock_version: 2 } } })
    monter()
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await ajouter(user, 'Commander les panneaux')
    await user.type(screen.getByLabelText('Nouvelle action'), 'Brancher le compteur lundi')
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    await vi.waitFor(() => expect(api.planifierProjet).toHaveBeenCalledWith(3, expect.objectContaining({
      actions: [{ titre: 'Commander les panneaux', quand: '' }, { titre: 'Brancher le compteur', quand: '' }],
    })))
    expect(api.planifierTache).toHaveBeenCalledWith(71, expect.objectContaining({ jour_prevu: '2026-11-23' }))
  })

  it('R4-VERIF — « Précédent » garde aussi le texte resté dans le champ : il devient une action, rien ne se perd', async () => {
    monter()
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.type(screen.getByLabelText('Nouvelle action'), 'Appeler le loueur')
    await user.click(screen.getByRole('button', { name: 'Précédent' }))
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    expect(screen.getByRole('radiogroup', { name: 'Quand : Appeler le loueur' })).toBeInTheDocument()
    expect(screen.getByLabelText('Nouvelle action')).toHaveValue('')
  })

  it("choisir un autre « Quand » retire le jour lu ; hors ligne, l'action garde son texte (rien n'est perdu)", async () => {
    api.saisieRapide.mockImplementationOnce(lecture({ samedi: '2026-11-21' }))
    api.saisieRapide.mockRejectedValueOnce(Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' }))
    monter()
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await ajouter(user, 'Poser les rails samedi')
    const groupe = await screen.findByRole('radiogroup', { name: 'Quand : Poser les rails' })
    await user.click(within(groupe).getByRole('radio', { name: "Aujourd'hui" }))
    expect(within(groupe).queryByRole('radio', { name: 'sam. 21' })).toBeNull()
    await ajouter(user, 'Câbler mardi')
    expect(await screen.findByText('Câbler mardi')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(api.planifierProjet).toHaveBeenCalledWith(3, expect.objectContaining({
      actions: [{ titre: 'Poser les rails', quand: 'aujourdhui' }, { titre: 'Câbler mardi', quand: '' }],
    }))
    expect(api.planifierTache).not.toHaveBeenCalled()
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
    // R2-062 — ce champ lit des ÉTAPES (une ligne non indentée = une étape), pas une liste de tâches
    expect(api.apercuPlanification).toHaveBeenCalledWith(3, { texte: 'Études :\nVisite', mode: 'etapes' })
    const lues = await screen.findByRole('list', { name: 'Étapes lues' })
    expect(within(lues).getByText('Études')).toBeInTheDocument()
    expect(within(lues).getByText('Visite')).toBeInTheDocument()
    expect(screen.getByText('Jalons').parentElement).toHaveTextContent('Mise en service')
    expect(api.planifierProjet).not.toHaveBeenCalled()
  })

  it('R2-062 — « Transport / Hébergement / Sur place » : l\'aperçu dit « 3 étapes · 0 tâche » et Terminer envoie ces 3 étapes', async () => {
    api.apercuPlanification.mockResolvedValue({ data: { projet: { id: 3, lock_version: 4 }, sections: [
      { nom: 'Transport', taches: [] }, { nom: 'Hébergement', taches: [] }, { nom: 'Sur place', taches: [] }] } })
    monter()
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.click(screen.getByText('Plus'))
    expect(screen.getByText(/Une ligne par étape/)).toBeInTheDocument()
    await user.type(screen.getByLabelText('Étapes'), 'Transport{Enter}Hébergement{Enter}Sur place')
    await user.click(screen.getByRole('button', { name: 'Lire la liste' }))
    expect(await screen.findByText('3 étapes · 0 tâche')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(api.planifierProjet).toHaveBeenCalledTimes(1)
    expect(api.planifierProjet.mock.calls[0][1].sections.map((s) => s.nom)).toEqual(['Transport', 'Hébergement', 'Sur place'])
  })

  it('« En faire une tâche » ajoute le risque aux premières actions', async () => {
    monter()
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.click(screen.getByText('Plus'))
    await user.type(screen.getByLabelText('Si ça échoue, ce sera sans doute parce que…'), 'le stand est complet')
    await user.click(screen.getByRole('button', { name: 'En faire une tâche' }))
    // R2-069 — la tâche née d'un risque est titrée « Parer : … », jamais la phrase brute du risque
    expect(screen.getByText('Parer : le stand est complet')).toBeInTheDocument()
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
