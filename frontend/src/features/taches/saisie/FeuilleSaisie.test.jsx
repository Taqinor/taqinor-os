import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { ReactReduxContext } from 'react-redux'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { memoryStore } from '../../../lib/offlineOutbox'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { creerFile, definirCompteFile, remplacerFile } from '../horsligne/captureQueue'
import { reinitialiserGestes } from '../lib/gestes'
import { aujourdhuiIso } from '../lib/textes'
import { SaisieBureau, ZoneAnnonces } from '../coquille/CoquilleTaches'
import FeuilleSaisie, { cleBrouillon, EVENEMENT_CREEES, EVENEMENT_ENVOI, lireBrouillon, messageChamps } from './FeuilleSaisie'
import ChampSaisie, { morceauxSurlignes, phraseAlerte } from '../ui/ChampSaisie'

const mocks = vi.hoisted(() => ({ saisieRapide: vi.fn(), annulerGeste: vi.fn(), listerTousLesProjets: vi.fn() }))
vi.mock('../../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  saisieRapide: mocks.saisieRapide,
  annulerGeste: mocks.annulerGeste,
  listerTousLesProjets: mocks.listerTousLesProjets,
}))

/* TCH82 — Feuille de saisie : puces lues (retirables), « Nouveau projet » et sa priorité, Entrée
   envoie, erreur SOUS le champ, brouillon rouvert identique et vidé à la déconnexion. Le client
   répond avec les échantillons du contrat (`saisie_apercu.json`, `saisie_rapide.json`,
   `erreurs.json`). */

const apercu = exempleContrat('taches', 'saisie_apercu')
const creation = exempleContrat('taches', 'saisie_rapide')
const erreurs = exempleContrat('taches', 'erreurs')
const CLE = cleBrouillon(7, 42)
const PHRASE = 'Appeler Karim demain #SiteWeb'

const store = { getState: () => ({ auth: { user: { id: 42, active_company_id: 7 } } }) }
const monter = (props = {}) => {
  const onFermer = vi.fn()
  const rendu = render(
    <ReactReduxContext.Provider value={{ store }}>
      <div className="tch"><FeuilleSaisie ouverte onFermer={onFermer} {...props} /><ZoneAnnonces /></div>
    </ReactReduxContext.Provider>,
  )
  const rouvrir = (ouverte) => rendu.rerender(
    <ReactReduxContext.Provider value={{ store }}>
      <div className="tch"><FeuilleSaisie ouverte={ouverte} onFermer={onFermer} /></div>
    </ReactReduxContext.Provider>,
  )
  return { onFermer, rouvrir, ...rendu }
}

const champ = () => screen.getByRole('textbox', { name: 'Ajouter une tâche' })
const erreurHttp = (data, status = 400) => Object.assign(new Error('http'), { response: { status, data } })

beforeEach(() => {
  window.localStorage.clear()
  mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? apercu : creation }))
  mocks.annulerGeste.mockResolvedValue({ data: {} })
  mocks.listerTousLesProjets.mockResolvedValue([])
})
afterEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
})

describe('TCH82 — feuille de saisie', () => {
  it('donne le focus au champ et lit la phrase en puces, chacune retirable (le mot reste dans le titre)', async () => {
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(champ()).toHaveFocus())
    expect(champ()).toHaveAttribute('placeholder', 'Ajouter une tâche… demain, 10 h, #projet, !!')
    await user.type(champ(), PHRASE)
    expect(champ()).toHaveValue(PHRASE)
    expect(await screen.findByText('mer. 18 nov.', {}, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.getByText('Nouveau projet : SiteWeb')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Moyenne' })).toHaveAttribute('aria-checked', 'true')

    await user.click(screen.getByRole('button', { name: 'Retirer mer. 18 nov.' }))
    await waitFor(() => {
      const dernier = mocks.saisieRapide.mock.calls.at(-1)[0]
      expect(dernier.ignorer).toEqual([{ type: 'jour', source: 'demain' }])
    })
    expect(champ()).toHaveValue(PHRASE)
  })

  it('passe visuelle n° 32 — les jetons lus sont SURLIGNÉS dans le texte (calque derrière le champ natif)', async () => {
    const user = userEvent.setup()
    const { container } = monter()
    await user.type(champ(), PHRASE)
    await screen.findByText('mer. 18 nov.', {}, { timeout: 3000 })
    const calque = container.querySelector('.saisie-miroir')
    expect(calque).toHaveAttribute('aria-hidden', 'true')
    expect([...calque.querySelectorAll('.jeton')].map((s) => [s.className, s.textContent])).toEqual([
      ['jeton', 'demain'], ['jeton nouveau', '#SiteWeb'],
    ])
    expect(calque.textContent.replace('​', '')).toBe(PHRASE) // le texte du calque = le texte tapé, à l'identique
    expect(champ()).toHaveValue(PHRASE)
  })

  it('passe visuelle n° 32 — un jeton dont la source ne tombe pas à sa place n\'est jamais surligné', () => {
    expect(morceauxSurlignes('Appeler Karim demain', [{ type: 'jour', source: 'demain', debut: 0, fin: 6 }]))
      .toEqual([{ texte: 'Appeler Karim demain' }])
    expect(morceauxSurlignes('demain !!', [
      { type: 'jour', source: 'demain', debut: 0, fin: 6 }, { type: 'priorite', source: '!!', debut: 7, fin: 9 },
    ]).map((m) => [m.texte, Boolean(m.jeton)])).toEqual([['demain', true], [' ', false], ['!!', true]])
  })

  it('« Ajouter » envoie la ligne lue (Entrée aussi, voir plus bas), avec la priorité choisie du nouveau projet, puis vide le champ et RESTE ouverte (chaîne, spec-2 §1)', async () => {
    const user = userEvent.setup()
    const { onFermer } = monter()
    await user.type(champ(), PHRASE)
    await screen.findByText('Nouveau projet : SiteWeb', {}, { timeout: 3000 })
    await user.click(screen.getByRole('radio', { name: 'Haute' }))
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    await waitFor(() => expect(champ()).toHaveValue(''))
    expect(onFermer).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog', { name: 'Ajouter une tâche' })).toBeInTheDocument()

    const envoi = mocks.saisieRapide.mock.calls.find(([corps]) => corps.apercu === false)[0]
    expect(envoi.lignes).toHaveLength(1)
    expect(envoi.lignes[0]).toMatchObject({
      index: 0, titre: 'Appeler Karim', jour_prevu: '2026-11-18', nouveau_projet: { nom: 'SiteWeb', priorite: 3 },
    })
    expect(envoi.lignes[0].client_id).toMatch(/:0$/)
    // la phrase est partie : plus de brouillon, toast « Ajoutée · Annuler »
    expect(lireBrouillon(7, 42)).toBeNull()
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    expect(toast).toHaveTextContent('Ajoutée')
    expect(screen.getByRole('button', { name: 'Annuler' })).toBeInTheDocument()
  })

  it('R3-041 — après le bouton « Ajouter », le curseur est dans le champ : la phrase suivante se tape aussitôt', async () => {
    const user = userEvent.setup()
    monter()
    await user.type(champ(), 'Appeler Karim')
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    expect(champ()).toHaveValue('')
    expect(champ()).toHaveFocus()
    await user.keyboard('Relancer Salma')
    expect(champ()).toHaveValue('Relancer Salma')
    // au clavier (Tab jusqu'au bouton, Entrée) : le focus revient aussi au champ
    await user.tab()
    await user.tab()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Ajouter' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(champ()).toHaveValue('')
    expect(champ()).toHaveFocus()
  })

  it('le brouillon est effacé AVANT l\'événement « tâches créées » : l\'écran qui le relit n\'affiche pas la carte « Brouillon »', async () => {
    const user = userEvent.setup()
    const vusALInstant = []
    const ecoute = () => vusALInstant.push(lireBrouillon(7, 42))
    window.addEventListener(EVENEMENT_CREEES, ecoute)
    try {
      const { onFermer } = monter()
      await user.type(champ(), PHRASE)
      expect(lireBrouillon(7, 42)).not.toBeNull()
      await screen.findByText('Nouveau projet : SiteWeb', {}, { timeout: 3000 })
      await user.click(screen.getByRole('button', { name: 'Ajouter' }))
      // saisie en chaîne (spec-2 §1) : la feuille reste ouverte, champ vidé ; l'événement est parti une fois
      await waitFor(() => expect(vusALInstant).toHaveLength(1))
      expect(vusALInstant).toEqual([null])
      expect(champ()).toHaveValue('')
      expect(onFermer).not.toHaveBeenCalled()
    } finally {
      window.removeEventListener(EVENEMENT_CREEES, ecoute)
    }
  })

  it('une erreur du serveur s\'affiche SOUS le champ, et ce qui est tapé reste intact', async () => {
    const user = userEvent.setup()
    mocks.saisieRapide.mockImplementation((corps) => (corps.apercu
      ? Promise.resolve({ data: apercu })
      : Promise.reject(erreurHttp(erreurs.par_ligne))))
    const { onFermer } = monter()
    await user.type(champ(), PHRASE)
    await screen.findByText('Nouveau projet : SiteWeb', {}, { timeout: 3000 })
    await user.keyboard('{Enter}')
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('Le titre est vide une fois la date et le projet retirés.')
    expect(champ()).toHaveAttribute('aria-invalid', 'true')
    expect(champ().getAttribute('aria-describedby')).toBe(alerte.id)
    expect(champ()).toHaveValue(PHRASE)
    expect(onFermer).not.toHaveBeenCalled()
    expect(lireBrouillon(7, 42).texte).toBe(PHRASE)
  })

  it('brouillon : fermée puis rouverte, la phrase est identique ; une nouvelle feuille la relit', async () => {
    const user = userEvent.setup()
    const { rouvrir, unmount } = monter()
    await user.type(champ(), 'Relancer l\'imprimeur jeudi')
    rouvrir(false)
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(window.localStorage.getItem(CLE)).toContain('Relancer l\'imprimeur jeudi')
    rouvrir(true)
    expect(champ()).toHaveValue('Relancer l\'imprimeur jeudi')
    unmount()
    monter()
    expect(champ()).toHaveValue('Relancer l\'imprimeur jeudi')
  })

  it('R3-040 — un brouillon repris : le curseur est APRÈS la phrase, la frappe s\'y ajoute (jamais « DeuxBrouillon un »)', async () => {
    const user = userEvent.setup()
    const { rouvrir, unmount } = monter()
    await user.type(champ(), 'Brouillon un')
    rouvrir(false)
    rouvrir(true)
    await waitFor(() => expect(champ()).toHaveFocus())
    expect(champ().selectionStart).toBe('Brouillon un'.length)
    expect(champ().selectionEnd).toBe('Brouillon un'.length)
    // `keyboard` (pas `type`, qui clique d'abord et poserait lui-même le curseur) : la frappe va où le champ l'a mis
    await user.keyboard(' Deux')
    expect(champ()).toHaveValue('Brouillon un Deux')
    // une nouvelle feuille qui relit le brouillon du stockage : même règle
    unmount()
    monter()
    await waitFor(() => expect(champ()).toHaveFocus())
    expect(champ().selectionStart).toBe('Brouillon un Deux'.length)
    await user.keyboard(' trois')
    expect(champ()).toHaveValue('Brouillon un Deux trois')
  })

  it('couture r2 — `n` sur un projet avant sa lecture (projet_id seul) : la puce nomme le projet, lu dans la liste', async () => {
    mocks.listerTousLesProjets.mockResolvedValue([{ id: 3, nom: 'Ventes', couleur: 'vert', priorite: 3, statut: 'actif' }])
    monter()
    act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: { projet_id: 3 } })) })
    expect(await screen.findByRole('button', { name: 'Retirer « Ventes »' })).toBeInTheDocument()
  })

  it('couture r2 — le « Quand » posé d\'office par Aujourd\'hui ne suit pas le brouillon rouvert depuis un autre écran', async () => {
    const user = userEvent.setup()
    const lieu = window.location.pathname
    try {
      window.history.pushState({}, '', '/taches/aujourdhui')
      const premiere = monter()
      act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: {} })) })
      expect(await screen.findByRole('button', { name: 'Retirer le jour choisi' })).toBeInTheDocument()
      await user.type(champ(), 'Relancer le client')
      premiere.unmount()
      window.history.pushState({}, '', '/taches/projets/3')
      monter()
      act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: { projet_id: 3, projet_nom: 'Ventes' } })) })
      expect(champ()).toHaveValue('Relancer le client') // la phrase suit
      expect(screen.queryByRole('button', { name: 'Retirer le jour choisi' })).toBeNull() // pas le jour d'Aujourd'hui
    } finally {
      window.history.pushState({}, '', lieu)
    }
  })

  it('couture r2 — une date lue dans la phrase l\'emporte : la puce « Quand » ne montre plus le jour posé d\'office', async () => {
    const user = userEvent.setup()
    const lieu = window.location.pathname
    try {
      window.history.pushState({}, '', '/taches/aujourdhui')
      monter()
      act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: {} })) })
      expect(await screen.findByRole('button', { name: 'Retirer le jour choisi' })).toBeInTheDocument()
      await user.type(champ(), PHRASE) // « demain » : l'aperçu sert jour_prevu
      expect(await screen.findByText('mer. 18 nov.', {}, { timeout: 3000 })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Retirer le jour choisi' })).toBeNull()
      expect(screen.getByRole('button', { name: 'Quand' })).toBeInTheDocument()
    } finally {
      window.history.pushState({}, '', lieu)
    }
  })

  it('la déconnexion vide le brouillon, à l\'écran et dans le stockage', async () => {
    const user = userEvent.setup()
    monter()
    await user.type(champ(), 'Appeler le fournisseur')
    expect(window.localStorage.getItem(CLE)).not.toBeNull()
    act(() => { window.dispatchEvent(new Event('taqinor:auth-logout')) })
    expect(champ()).toHaveValue('')
    expect(window.localStorage.getItem(CLE)).toBeNull()
  })

  it('« Quand » : une tuile pose le jour, la puce le dit et le jour part avec la ligne', async () => {
    const user = userEvent.setup()
    const { onFermer } = monter()
    await user.type(champ(), 'Appeler Karim')
    await user.click(screen.getByRole('button', { name: 'Quand' }))
    await user.click(screen.getByRole('radio', { name: 'Plus tard' }))
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    await waitFor(() => expect(champ()).toHaveValue(''))
    expect(onFermer).not.toHaveBeenCalled()
    const envoi = mocks.saisieRapide.mock.calls.find(([corps]) => corps.apercu === false)[0]
    expect(envoi.lignes[0]).toMatchObject({ quelque_jour: true, jour_prevu: null })
  })

  it('TCH83 — une liste collée ouvre l\'aperçu de la liste ; « Créer 2 tâches » envoie les deux lignes cochées', async () => {
    const liste = {
      projets_communs: [{ collage: 0, id: null, nom: 'Courses', nouveau: true, priorite: 2, source: 'premiere_ligne' }],
      lignes: ['lait', 'pain'].map((titre, index) => ({
        ...apercu.lignes[0], index, collage: 0, titre, jetons: [], champs: { nouveau_projet: { nom: 'Courses', priorite: 2 } },
      })),
      projets_nouveaux: [{ nom: 'Courses', priorite: 2 }],
    }
    mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? liste : creation }))
    const user = userEvent.setup()
    const { onFermer } = monter()
    fireEvent.change(champ(), { target: { value: 'Courses\nlait\npain' } })
    expect(await screen.findByText('Aperçu de ta liste', {}, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.getByText('Nouveau projet : Courses')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Créer 2 tâches' }))
    await waitFor(() => expect(onFermer).toHaveBeenCalled())
    const envoi = mocks.saisieRapide.mock.calls.find(([corps]) => corps.apercu === false)[0]
    expect(envoi.lignes.map((l) => l.titre)).toEqual(['lait', 'pain'])
    expect(envoi.lignes[0].nouveau_projet).toEqual({ nom: 'Courses', priorite: 2 })
    expect(lireBrouillon(7, 42)).toBeNull()
  })

  it('R4-25 — « Créer N tâches » : le brouillon est DÉJÀ effacé quand la feuille se ferme — l\'écran qui le relit à la fermeture ne montre pas de faux « Reprendre »', async () => {
    const liste = {
      projets_communs: [],
      lignes: ['lait', 'pain'].map((titre, index) => ({ ...apercu.lignes[0], index, collage: 0, titre, jetons: [], champs: {} })),
      projets_nouveaux: [],
    }
    mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? liste : creation }))
    const user = userEvent.setup()
    const vusALaFermeture = []
    monter({ onFermer: vi.fn(() => vusALaFermeture.push(lireBrouillon(7, 42))) })
    fireEvent.change(champ(), { target: { value: 'Divers\nlait\npain' } })
    expect(await screen.findByText('Aperçu de ta liste', {}, { timeout: 3000 })).toBeInTheDocument()
    expect(lireBrouillon(7, 42)).not.toBeNull()
    await user.click(screen.getByRole('button', { name: 'Créer 2 tâches' }))
    expect(vusALaFermeture).toEqual([null])
  })

  it('passe visuelle n° 33 — une liste COLLÉE (même ouverte par « Coller mes listes ») : l\'aperçu seul, le champ replié ; « Coller encore » le rouvre', async () => {
    const liste = {
      projets_communs: [{ collage: 0, id: null, nom: 'Courses', nouveau: true, priorite: 2, source: 'premiere_ligne' }],
      lignes: ['lait', 'pain'].map((titre, index) => ({
        ...apercu.lignes[0], index, collage: 0, titre, jetons: [], champs: { nouveau_projet: { nom: 'Courses', priorite: 2 } },
      })),
      projets_nouveaux: [{ nom: 'Courses', priorite: 2 }],
    }
    mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? liste : creation }))
    const user = userEvent.setup()
    monter()
    act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: { coller: true } })) })
    // un collage, comme le navigateur le fait : l'événement `paste` (texte collé) puis la nouvelle valeur
    fireEvent.paste(champ(), { clipboardData: { getData: () => 'Courses\nlait\npain' } })
    fireEvent.change(champ(), { target: { value: 'Courses\nlait\npain' } })
    expect(await screen.findByText('Nouveau projet : Courses', {}, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Ajouter une tâche' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Coller encore' }))
    expect(champ()).toHaveValue('')
  })

  const listeMenage = () => ({
    projets_communs: [{ collage: 0, id: null, nom: 'Ménage', nouveau: true, priorite: 2, source: 'premiere_ligne' }],
    lignes: ['Aspirer', 'Laver les vitres'].map((titre, index) => ({
      ...apercu.lignes[0], index, collage: 0, titre, jetons: [], champs: { nouveau_projet: { nom: 'Ménage', priorite: 2 } },
    })),
    projets_nouveaux: [{ nom: 'Ménage', priorite: 2 }],
  })

  it('relecture adverse F4 n° 3 — champ ouvert (« Coller mes listes ») : une suggestion du clavier ou un mot collé dans une liste ne le replie pas', async () => {
    const liste = listeMenage()
    mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? liste : creation }))
    const user = userEvent.setup()
    monter()
    act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: { coller: true } })) })
    await user.type(champ(), 'Ménage{Shift>}{Enter}{/Shift}Aspirer{Shift>}{Enter}{/Shift}')
    expect(await screen.findByText('Nouveau projet : Ménage', {}, { timeout: 3000 })).toBeInTheDocument()
    // une suggestion QuickType (ou une dictée) pose plusieurs caractères d'un coup, dans un texte qui a déjà un saut de ligne
    fireEvent.change(champ(), { target: { value: 'Ménage\nAspirer\nLaver les' } })
    // un seul mot collé (sans saut de ligne) : ce n'est pas une liste collée
    fireEvent.paste(champ(), { clipboardData: { getData: () => ' vitres' } })
    fireEvent.change(champ(), { target: { value: 'Ménage\nAspirer\nLaver les vitres' } })
    await waitFor(() => expect(mocks.saisieRapide.mock.calls.at(-1)[0].texte).toBe('Ménage\nAspirer\nLaver les vitres'))
    await screen.findByText('Nouveau projet : Ménage')
    expect(champ()).toHaveValue('Ménage\nAspirer\nLaver les vitres')
  })

  it('relecture adverse F4 n° 3 — une liste TAPÉE à la main (Maj+Entrée) garde le champ et son focus quand l\'aperçu arrive', async () => {
    const liste = listeMenage()
    mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? liste : creation }))
    const user = userEvent.setup()
    monter()
    await user.type(champ(), 'Ménage{Shift>}{Enter}{/Shift}Aspirer')
    expect(await screen.findByText('Nouveau projet : Ménage', {}, { timeout: 3000 })).toBeInTheDocument()
    expect(champ()).toHaveFocus()
    expect(champ()).toHaveValue('Ménage\nAspirer')
  })

  it('relecture adverse F4 n° 5 — Échap ferme le menu de priorité de l\'aperçu, PAS la feuille', async () => {
    const liste = {
      projets_communs: [{ collage: 0, id: null, nom: 'Courses', nouveau: true, priorite: 2, source: 'premiere_ligne' }],
      lignes: ['lait', 'pain'].map((titre, index) => ({
        ...apercu.lignes[0], index, collage: 0, titre, jetons: [], champs: { nouveau_projet: { nom: 'Courses', priorite: 2 } },
      })),
      projets_nouveaux: [{ nom: 'Courses', priorite: 2 }],
    }
    mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? liste : creation }))
    const user = userEvent.setup()
    const { onFermer } = monter()
    fireEvent.paste(champ(), { clipboardData: { getData: () => 'Courses\nlait\npain' } })
    fireEvent.change(champ(), { target: { value: 'Courses\nlait\npain' } })
    await user.click(await screen.findByRole('button', { name: 'Priorité du projet Courses : moyenne' }, { timeout: 3000 }))
    expect(await screen.findByRole('menuitemradio', { name: 'Moyenne' })).toBeInTheDocument()
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('menuitemradio', { name: 'Moyenne' })).toBeNull())
    expect(onFermer).not.toHaveBeenCalled()
    // menu fermé : Échap ferme maintenant la feuille, comme avant
    await user.keyboard('{Escape}')
    expect(onFermer).toHaveBeenCalled()
  })

  it('Raccord F2 — le contexte de l\'écran (projet courant) part avec la ligne qui n\'en nomme pas', async () => {
    const user = userEvent.setup()
    mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({
      data: corps.apercu ? { ...apercu, lignes: [{ ...apercu.lignes[0], champs: { jour_prevu: '2026-11-18' } }], projets_nouveaux: [] } : creation,
    }))
    const { onFermer } = monter()
    act(() => {
      window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: { projet_id: 3, projet_nom: 'Ventes', section_id: 8 } }))
    })
    expect(screen.getByRole('button', { name: 'Retirer « Ventes »' })).toBeInTheDocument()
    await user.type(champ(), 'Appeler Karim demain')
    await waitFor(() => expect(mocks.saisieRapide).toHaveBeenCalled())
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    await waitFor(() => expect(champ()).toHaveValue(''))
    expect(onFermer).not.toHaveBeenCalled()
    const envoi = mocks.saisieRapide.mock.calls.find(([corps]) => corps.apercu === false)[0]
    expect(envoi.lignes[0]).toMatchObject({ projet_id: 3, section_id: 8, jour_prevu: '2026-11-18' })
    // la chaîne reste sur le même projet : la phrase suivante part encore dans « Ventes »
    expect(screen.getByRole('button', { name: 'Retirer « Ventes »' })).toBeInTheDocument()
  })

  it('Raccord F2 — le jour de l\'Agenda devient le « Quand » de départ, retirable', async () => {
    monter()
    act(() => {
      window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: { jour_prevu: '2026-11-20', heure_debut: '10:00' } }))
    })
    expect(screen.getByRole('button', { name: 'Retirer le jour choisi' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /10:00/ })).toBeInTheDocument()
  })

  it('Acceptation F4 — remise par l\'hôte : la demande arrivée AVANT le montage de la feuille lui est remise entière (phrase, jour, lien)', () => {
    // la feuille est chargée à part hors de /taches : elle s'abonne à l'hôte, qui lui remet ce que l'écran a demandé entre-temps
    const desabonner = vi.fn()
    const abonner = vi.fn((lire) => { lire({ texte: 'Rappeler le fournisseur', jour_prevu: '2026-11-20' }); return desabonner })
    const { unmount } = monter({ lienParDefaut: { cible: 'crm.lead', id: 9, libelle: 'Lead' }, demandes: { abonner } })
    expect(champ()).toHaveValue('Rappeler le fournisseur')
    expect(screen.getByRole('button', { name: 'Retirer le jour choisi' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retirer le lien « Lead »' })).toBeInTheDocument()
    unmount()
    expect(desabonner).toHaveBeenCalled()
  })

  it('Acceptation F4 — remise par l\'hôte : la feuille n\'écoute plus l\'événement elle-même (un seul chemin, jamais deux lectures)', () => {
    let lire
    monter({ demandes: { abonner: (f) => { lire = f; return () => {} } } })
    act(() => {
      window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: { texte: 'Phrase que seul l\'hôte remet' } }))
    })
    expect(champ()).toHaveValue('')
    act(() => { lire({ texte: 'Remise par l\'hôte' }) })
    expect(champ()).toHaveValue('Remise par l\'hôte')
  })

  describe('Raccord F2 — hors ligne', () => {
    let file
    beforeEach(async () => {
      file = creerFile({ store: memoryStore() })
      remplacerFile(file)
      definirCompteFile(42, 7)
    })
    afterEach(() => {
      Object.defineProperty(window.navigator, 'onLine', { value: true, configurable: true })
      remplacerFile(null)
      definirCompteFile(null)
    })

    it('sans réseau, « Ajouter » met la phrase en file : « Partira dès le retour du réseau », rien n\'est perdu', async () => {
      const user = userEvent.setup()
      const { onFermer } = monter()
      await user.type(champ(), PHRASE)
      await screen.findByText('Nouveau projet : SiteWeb', {}, { timeout: 3000 })
      act(() => {
        Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true })
        window.dispatchEvent(new Event('offline'))
      })
      expect(screen.getByText('Hors ligne : elle partira dès le retour du réseau.')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Ajouter' }))
      await waitFor(async () => expect(await file.pending()).toHaveLength(1))
      // R4-22 — la feuille reste ouverte, prête pour la phrase suivante (comme en ligne)
      expect(onFermer).not.toHaveBeenCalled()
      expect(champ()).toHaveValue('')
      expect(mocks.saisieRapide.mock.calls.some(([corps]) => corps.apercu === false)).toBe(false)
      const [op] = await file.pending()
      expect(op.payload.corps.lignes[0]).toMatchObject({ titre: 'Appeler Karim', nouveau_projet: { nom: 'SiteWeb' } })
      expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Partira dès le retour du réseau')
    })

    it('R3-046 — sans réseau : l\'envoi annoncé `part` finit par `en_file` (la ligne « En attente d\'envoi » prend le relais)', async () => {
      const annonces = []
      const ecouter = (e) => annonces.push(e.detail)
      window.addEventListener(EVENEMENT_ENVOI, ecouter)
      try {
        const user = userEvent.setup()
        act(() => {
          Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true })
          window.dispatchEvent(new Event('offline'))
        })
        monter()
        await user.type(champ(), 'Rappeler Salma{Enter}')
        await waitFor(() => expect(annonces.map((a) => a.etat)).toEqual(['part', 'en_file']))
        expect(annonces[1].envoi).toBe(annonces[0].envoi)
      } finally {
        window.removeEventListener(EVENEMENT_ENVOI, ecouter)
      }
    })

    it('la mise en file efface le brouillon (et avant tout rejeu qui émet l\'événement) ; la feuille reste ouverte (R4-22)', async () => {
      const user = userEvent.setup()
      const { onFermer } = monter()
      await user.type(champ(), PHRASE)
      expect(lireBrouillon(7, 42)).not.toBeNull()
      act(() => {
        Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true })
        window.dispatchEvent(new Event('offline'))
      })
      await user.click(screen.getByRole('button', { name: 'Ajouter' }))
      expect(lireBrouillon(7, 42)).toBeNull()
      await waitFor(async () => expect(await file.pending()).toHaveLength(1))
      expect(lireBrouillon(7, 42)).toBeNull()
      expect(onFermer).not.toHaveBeenCalled()
    })

    it('une coupure pendant l\'envoi met la PHRASE en file (R2-008a : le serveur la lira au rejeu), jamais une erreur', async () => {
      const user = userEvent.setup()
      mocks.saisieRapide.mockRejectedValue(new Error('Network Error'))
      const { onFermer } = monter()
      await user.type(champ(), 'Rappeler Salma')
      await user.click(screen.getByRole('button', { name: 'Ajouter' }))
      await waitFor(async () => expect(await file.pending()).toHaveLength(1))
      expect(onFermer).not.toHaveBeenCalled()
      const [op] = await file.pending()
      expect(op.payload.corps.lignes).toBeUndefined()
      expect(op.payload.corps.phrase).toMatchObject({ textes: ['Rappeler Salma'], ignorer: [] })
      expect(screen.queryByText(/Pas de réseau/)).toBeNull()
    })

    it('R2-008a — hors ligne dès la frappe : « Test ce soir » part en file avec son contexte, « ce soir » n\'est pas mis dans un titre', async () => {
      const user = userEvent.setup()
      act(() => {
        Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true })
        window.dispatchEvent(new Event('offline'))
      })
      monter()
      act(() => {
        window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: { projet_id: 3, projet_nom: 'Ventes' } }))
      })
      await user.type(champ(), 'Test ce soir{Enter}')
      await waitFor(async () => expect(await file.pending()).toHaveLength(1))
      const [op] = await file.pending()
      expect(op.payload.corps.lignes).toBeUndefined()
      expect(op.payload.corps.phrase).toMatchObject({ textes: ['Test ce soir'], contexte: { projetId: 3 } })
      expect(op.payload.corps.phrase.cid).toEqual(expect.any(String))
      expect(mocks.saisieRapide).not.toHaveBeenCalled()
    })
  })

  describe('R4-22 — aucune lettre perdue : phrases enchaînées par Entrée, hors ligne comme en ligne', () => {
    /* La feuille est montée par un VRAI hôte (sa fermeture la démonte, comme la coquille) : une fermeture décidée au
       retour de la file emportait le champ pendant que la phrase suivante se tapait (« Bravo h » avalé). */
    let file
    let fermetures
    const PROJETS = [{ id: 11, nom: 'Salon Solaire Expo', couleur: 'terre', statut: 'actif' }]
    function Hote() {
      const [ouverte, setOuverte] = useState(true)
      return <FeuilleSaisie ouverte={ouverte} onFermer={() => { fermetures += 1; setOuverte(false) }} />
    }
    const monterHote = () => render(
      <ReactReduxContext.Provider value={{ store }}>
        <div className="tch"><Hote /><ZoneAnnonces /></div>
      </ReactReduxContext.Provider>,
    )
    const reseau = (enLigne) => act(() => {
      Object.defineProperty(window.navigator, 'onLine', { value: enLigne, configurable: true })
      window.dispatchEvent(new Event(enLigne ? 'online' : 'offline'))
    })
    /** Un temps passe (la file, le serveur reviennent) — la frappe suivante, elle, n'attend rien. */
    const unTour = () => act(() => new Promise((r) => { setTimeout(r, 0) }))
    const phrasesEnFile = async () => (await file.pending()).map((op) => op.payload.corps.phrase?.textes.join(' ')
      ?? op.payload.corps.lignes.map((l) => l.titre).join(' '))
    beforeEach(() => {
      fermetures = 0
      file = creerFile({ store: memoryStore() })
      remplacerFile(file)
      definirCompteFile(42, 7)
      mocks.listerTousLesProjets.mockResolvedValue(PROJETS)
    })
    afterEach(() => {
      Object.defineProperty(window.navigator, 'onLine', { value: true, configurable: true })
      remplacerFile(null)
      definirCompteFile(null)
    })

    for (const attente of ['sans attendre', 'un tour entre deux']) {
      it(`hors ligne, trois phrases par Entrée (${attente}) : les trois en file, entières, et la feuille reste ouverte`, async () => {
        const user = userEvent.setup({ delay: null })
        reseau(false)
        monterHote()
        await user.click(champ())
        for (const phrase of ['Alpha horsligne premier', 'Bravo horsligne second', 'Charlie horsligne tiers']) {
          await user.keyboard(`${phrase}{Enter}`)
          if (attente !== 'sans attendre') await unTour()
        }
        await waitFor(async () => expect(await file.pending()).toHaveLength(3))
        expect(await phrasesEnFile()).toEqual(['Alpha horsligne premier', 'Bravo horsligne second', 'Charlie horsligne tiers'])
        expect(fermetures).toBe(0)
        expect(champ()).toHaveValue('')
        expect(champ()).toHaveFocus()
      })
    }

    it('hors ligne, un `#projet` choisi dans la liste entre deux phrases : rien d\'avalé avant ni après', async () => {
      const user = userEvent.setup({ delay: null })
      monterHote()
      await waitFor(() => expect(mocks.listerTousLesProjets).toHaveBeenCalled())
      reseau(false)
      await user.click(champ())
      await user.keyboard('Alpha premier{Enter}')
      await unTour()
      await user.keyboard('Photos #sal')
      await waitFor(() => expect(screen.getByRole('option', { name: 'Salon Solaire Expo' })).toBeInTheDocument())
      await user.keyboard('{Enter}suite{Enter}')
      await unTour()
      await user.keyboard('Charlie tiers{Enter}')
      await waitFor(async () => expect(await file.pending()).toHaveLength(3))
      expect(await phrasesEnFile()).toEqual(['Alpha premier', 'Photos #Salon Solaire Expo suite', 'Charlie tiers'])
      expect(fermetures).toBe(0)
    })

    it('en ligne, serveur lent : trois phrases par Entrée sans attendre, les trois partent entières, dans l\'ordre', async () => {
      const attentes = []
      mocks.saisieRapide.mockImplementation((corps) => (corps.apercu
        ? Promise.resolve({ data: { ...apercu, projets_nouveaux: [], lignes: [{ ...apercu.lignes[0], titre: corps.texte, jetons: [], alertes: [], champs: {} }] } })
        : new Promise((resoudre) => attentes.push({ corps, resoudre }))))
      const user = userEvent.setup({ delay: null })
      monterHote()
      await user.click(champ())
      for (const phrase of ['Alpha enligne premier', 'Bravo enligne second', 'Charlie enligne tiers']) {
        await user.keyboard(`${phrase}{Enter}`)
        await unTour()
      }
      for (let i = 0; i < 3; i += 1) {
        await waitFor(() => expect(attentes).toHaveLength(i + 1))
        await act(async () => { attentes[i].resoudre({ data: creation }) })
      }
      expect(attentes.map((a) => a.corps.lignes[0].titre)).toEqual(['Alpha enligne premier', 'Bravo enligne second', 'Charlie enligne tiers'])
      expect(fermetures).toBe(0)
      expect(champ()).toHaveValue('')
    })

    it('un échec rendu au champ pendant qu\'une lettre vient d\'y être tapée : la lettre reste, la phrase passe par « Reprendre »', async () => {
      const attentes = []
      mocks.saisieRapide.mockImplementation((corps) => (corps.apercu
        ? Promise.resolve({ data: { ...apercu, projets_nouveaux: [], lignes: [{ ...apercu.lignes[0], titre: corps.texte, jetons: [], alertes: [], champs: {} }] } })
        : new Promise((resoudre, rejeter) => attentes.push({ corps, rejeter }))))
      const user = userEvent.setup({ delay: null })
      monterHote()
      await user.click(champ())
      await user.keyboard('Test un{Enter}')
      await waitFor(() => expect(attentes).toHaveLength(1))
      // la lettre est DANS le champ (le navigateur l'a écrite) mais React ne l'a pas encore rendue quand l'échec revient
      act(() => {
        const el = champ()
        el.value = 'B'
        attentes[0].rejeter(erreurHttp(erreurs.par_ligne))
      })
      await act(async () => {})
      expect(champ()).toHaveValue('B')
      fireEvent.change(champ(), { target: { value: 'Br' } })
      expect(champ()).toHaveValue('Br')
      expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Pas ajoutée')
    })
  })

  describe('R2-001 — taper vite après « Ajouter » ne perd jamais rien', () => {
    /** L'aperçu rend la phrase telle quelle (une ligne, aucun jeton) ; la création reste EN VOL jusqu'à `liberer`. */
    const enVol = () => {
      const attentes = []
      mocks.saisieRapide.mockImplementation((corps) => {
        if (corps.apercu) {
          return Promise.resolve({ data: {
            ...apercu, projets_nouveaux: [],
            lignes: [{ ...apercu.lignes[0], titre: corps.texte, jetons: [], alertes: [], champs: {} }],
          } })
        }
        return new Promise((resoudre, rejeter) => attentes.push({ corps, resoudre, rejeter }))
      })
      return attentes
    }
    const creations = () => mocks.saisieRapide.mock.calls.filter(([corps]) => corps.apercu === false).map(([c]) => c)

    it('Entrée vide le champ TOUT DE SUITE ; la 2e phrase tapée pendant que la 1re est en vol reste, puis part à son tour', async () => {
      const attentes = enVol()
      const user = userEvent.setup()
      const { onFermer } = monter()
      // Entrée AVANT que l'aperçu ne soit revenu : l'analyse et la création partent en arrière-plan
      await user.type(champ(), 'Test un{Enter}')
      expect(champ()).toHaveValue('')
      await user.type(champ(), 'Test deux')
      await waitFor(() => expect(attentes).toHaveLength(1))
      expect(champ()).toHaveValue('Test deux')
      // la 1re revient du serveur : la frappe de la 2e est intacte
      await act(async () => { attentes[0].resoudre({ data: creation }) })
      expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Ajoutée')
      expect(champ()).toHaveValue('Test deux')
      await user.keyboard('{Enter}')
      expect(champ()).toHaveValue('')
      await waitFor(() => expect(attentes).toHaveLength(2))
      await act(async () => { attentes[1].resoudre({ data: creation }) })
      expect(creations().map((c) => c.lignes.map((l) => l.titre))).toEqual([['Test un'], ['Test deux']])
      // deux phrases, deux clés d'idempotence différentes : jamais une tâche prise pour l'autre
      const cles = mocks.saisieRapide.mock.calls.filter(([c]) => c.apercu === false).map(([, o]) => o.cle)
      expect(new Set(cles).size).toBe(2)
      expect(onFermer).not.toHaveBeenCalled()
    })

    it('trois phrases enchaînées sans attendre : les trois partent, dans l\'ordre tapé', async () => {
      const attentes = enVol()
      const user = userEvent.setup()
      monter()
      await user.type(champ(), 'Une{Enter}Deux{Enter}Trois{Enter}')
      expect(champ()).toHaveValue('')
      for (let i = 0; i < 3; i += 1) {
        await waitFor(() => expect(attentes).toHaveLength(i + 1))
        await act(async () => { attentes[i].resoudre({ data: creation }) })
      }
      expect(creations().map((c) => c.lignes[0].titre)).toEqual(['Une', 'Deux', 'Trois'])
    })

    it('un échec pendant qu\'une autre phrase est tapée : rien n\'est effacé, toast « Pas ajoutée : … · Reprendre » qui rend la phrase', async () => {
      const attentes = enVol()
      const user = userEvent.setup()
      monter()
      await user.type(champ(), 'Test un{Enter}')
      await user.type(champ(), 'Test deux')
      await waitFor(() => expect(attentes).toHaveLength(1))
      await act(async () => { attentes[0].rejeter(erreurHttp(erreurs.par_ligne)) })
      const toast = await screen.findByRole('group', { name: 'Geste effectué' })
      expect(toast).toHaveTextContent('Pas ajoutée : Le titre est vide une fois la date et le projet retirés.')
      expect(champ()).toHaveValue('Test deux')
      await user.click(screen.getByRole('button', { name: 'Reprendre' }))
      expect(champ()).toHaveValue('Test un')
      // le focus est rendu au champ ; la phrase qu'on tapait n'est pas perdue : elle revient une fois la reprise envoyée
      await waitFor(() => expect(champ()).toHaveFocus())
      await user.keyboard('{Enter}')
      expect(champ()).toHaveValue('Test deux')
    })

    describe('R3-046 — l\'envoi est ANNONCÉ (`taqinor:taches:envoi`) ; une rafale = un seul toast', () => {
      let annonces
      let creationsAuDepart
      const ecouter = (e) => { annonces.push(e.detail); if (e.detail.etat === 'part') creationsAuDepart.push(creations().length) }
      beforeEach(() => { annonces = []; creationsAuDepart = []; window.addEventListener(EVENEMENT_ENVOI, ecouter) })
      afterEach(() => { window.removeEventListener(EVENEMENT_ENVOI, ecouter) })

      it('au toucher, AVANT tout envoi : `part` avec la ligne (client_id, titre, jour) ; au retour : `creees`', async () => {
        const attentes = enVol()
        const user = userEvent.setup()
        monter()
        await user.type(champ(), 'Test un{Enter}')
        expect(annonces[0]).toEqual({
          etat: 'part', envoi: expect.any(String), lignes: [{ client_id: expect.stringMatching(/:0$/), titre: 'Test un', jour: null }],
        })
        expect(creationsAuDepart).toEqual([0]) // annoncée avant la création
        const { envoi } = annonces[0]
        expect(annonces[0].lignes[0].client_id).toBe(`${envoi}:0`)
        await waitFor(() => expect(attentes).toHaveLength(1))
        // l'identifiant d'envoi est la clé d'idempotence de la création : la même phrase, partout
        expect(mocks.saisieRapide.mock.calls.find(([c]) => c.apercu === false)[1].cle).toBe(envoi)
        expect(attentes[0].corps.lignes[0].client_id).toBe(`${envoi}:0`)
        await act(async () => { attentes[0].resoudre({ data: creation }) })
        await waitFor(() => expect(annonces).toHaveLength(2))
        expect(annonces[1]).toEqual({ etat: 'creees', envoi, creees: creation.creees })
      })

      it('un échec : `echec` pour cet envoi (la ligne provisoire s\'efface, la phrase revient)', async () => {
        const attentes = enVol()
        const user = userEvent.setup()
        monter()
        await user.type(champ(), 'Test un{Enter}')
        await waitFor(() => expect(attentes).toHaveLength(1))
        await act(async () => { attentes[0].rejeter(erreurHttp(erreurs.par_ligne)) })
        await waitFor(() => expect(annonces.map((a) => a.etat)).toEqual(['part', 'echec']))
        expect(annonces[1]).toEqual({ etat: 'echec', envoi: annonces[0].envoi })
      })

      it('trois phrases en rafale : trois `part` tout de suite, puis UN toast « 3 tâches ajoutées » dont « Annuler » défait les trois', async () => {
        const attentes = enVol()
        const user = userEvent.setup()
        monter()
        await user.type(champ(), 'Une{Enter}Deux{Enter}Trois{Enter}')
        expect(annonces.map((a) => [a.etat, a.lignes[0].titre])).toEqual([['part', 'Une'], ['part', 'Deux'], ['part', 'Trois']])
        expect(new Set(annonces.map((a) => a.envoi)).size).toBe(3)
        for (let i = 0; i < 3; i += 1) {
          await waitFor(() => expect(attentes).toHaveLength(i + 1))
          await act(async () => { attentes[i].resoudre({ data: { ...creation, geste_id: 70 + i } }) })
          // pas de toast tant que la rafale n'est pas finie
          if (i < 2) expect(screen.queryByRole('group', { name: 'Geste effectué' })).toBeNull()
        }
        const toast = await screen.findByRole('group', { name: 'Geste effectué' })
        expect(toast).toHaveTextContent('3 tâches ajoutées')
        await user.click(within(toast).getByRole('button', { name: 'Annuler' }))
        await waitFor(() => expect(mocks.annulerGeste.mock.calls.map(([g]) => g)).toEqual([70, 71, 72]))
      })
    })

    it('un échec quand le champ est resté vide : la phrase revient dans le champ, l\'erreur dessous', async () => {
      const attentes = enVol()
      const user = userEvent.setup()
      monter()
      await user.type(champ(), 'Test un{Enter}')
      await waitFor(() => expect(attentes).toHaveLength(1))
      await act(async () => { attentes[0].rejeter(erreurHttp(erreurs.par_ligne)) })
      expect(await screen.findByRole('alert')).toHaveTextContent('Le titre est vide une fois la date et le projet retirés.')
      expect(champ()).toHaveValue('Test un')
    })
  })

  describe('R2-002 — ajoutée depuis Aujourd\'hui, elle est dans Aujourd\'hui', () => {
    const apercuDe = (champs) => (corps) => Promise.resolve({ data: corps.apercu ? {
      ...apercu, projets_nouveaux: [],
      lignes: [{ ...apercu.lignes[0], titre: 'Rappeler M. Benjelloun', jetons: [], alertes: [], champs }],
    } : creation })
    const demander = (detail = {}) => act(() => {
      window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail }))
    })
    const corpsCree = () => mocks.saisieRapide.mock.calls.find(([c]) => c.apercu === false)[0]
    afterEach(() => { window.history.pushState({}, '', '/') })

    it.each(['/taches/aujourdhui', '/taches'])('sur %s : « Quand » part sur aujourd\'hui (puce retirable), toast « Ajoutée à Aujourd\'hui »', async (chemin) => {
      window.history.pushState({}, '', chemin)
      mocks.saisieRapide.mockImplementation(apercuDe({}))
      const user = userEvent.setup()
      monter()
      demander()
      expect(screen.getByRole('button', { name: "aujourd'hui" })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Retirer le jour choisi' })).toBeInTheDocument()
      await user.type(champ(), 'Rappeler M. Benjelloun')
      await user.click(screen.getByRole('button', { name: 'Ajouter' }))
      await waitFor(() => expect(mocks.saisieRapide.mock.calls.some(([c]) => c.apercu === false)).toBe(true))
      expect(corpsCree().lignes[0]).toMatchObject({ titre: 'Rappeler M. Benjelloun', jour_prevu: aujourdhuiIso() })
      expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent("Ajoutée à Aujourd'hui")
      // la chaîne repart sur aujourd'hui pour la suivante
      expect(screen.getByRole('button', { name: "aujourd'hui" })).toBeInTheDocument()
    })

    it.each([
      ['Aujourd\'hui', '/taches/aujourdhui', {}],
      ['l\'Agenda', '/taches/agenda', { jour_prevu: '2026-11-20', heure_debut: '10:00' }],
    ])('une date lue dans la phrase (« demain ») l\'emporte sur le jour de départ (%s)', async (_ecran, chemin, detail) => {
      window.history.pushState({}, '', chemin)
      mocks.saisieRapide.mockImplementation(apercuDe({ jour_prevu: '2026-11-18' }))
      const user = userEvent.setup()
      monter()
      demander(detail)
      await user.type(champ(), 'Rappeler M. Benjelloun demain')
      await waitFor(() => expect(mocks.saisieRapide).toHaveBeenCalled())
      await user.click(screen.getByRole('button', { name: 'Ajouter' }))
      await waitFor(() => expect(mocks.saisieRapide.mock.calls.some(([c]) => c.apercu === false)).toBe(true))
      expect(corpsCree().lignes[0].jour_prevu).toBe('2026-11-18')
      // l'heure du créneau de départ ne s'accroche pas au jour lu dans la phrase
      expect(corpsCree().lignes[0].heure_debut ?? null).toBeNull()
    })

    it('le jour de départ retiré (×) : la tâche va dans À trier', async () => {
      window.history.pushState({}, '', '/taches/aujourdhui')
      mocks.saisieRapide.mockImplementation(apercuDe({}))
      const user = userEvent.setup()
      monter()
      demander()
      await user.click(screen.getByRole('button', { name: 'Retirer le jour choisi' }))
      await user.type(champ(), 'Rappeler M. Benjelloun')
      await user.click(screen.getByRole('button', { name: 'Ajouter' }))
      await waitFor(() => expect(mocks.saisieRapide.mock.calls.some(([c]) => c.apercu === false)).toBe(true))
      expect(corpsCree().lignes[0].jour_prevu).toBeUndefined()
      expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent(/^Ajoutée/)
    })

    it('ailleurs dans Tâches (un projet, À trier) : aucun jour de départ', () => {
      window.history.pushState({}, '', '/taches/a-trier')
      monter()
      demander()
      expect(screen.queryByRole('button', { name: 'Retirer le jour choisi' })).toBeNull()
      expect(screen.getByRole('button', { name: 'Quand' })).toBeInTheDocument()
    })
  })

  describe('R2-003 — « # » propose les projets ; une puce « Projet » dans le pied', () => {
    const PROJETS = [
      { id: 11, nom: 'Salon Solaire Expo', couleur: 'terre', statut: 'actif' },
      { id: 12, nom: 'Chantier Bénali 9 kWc', couleur: 'mer', statut: 'actif' },
      { id: 13, nom: 'Site web', couleur: 'ciel', statut: 'en_pause' },
      { id: 14, nom: 'Salle archivée', couleur: 'terre', statut: 'archive' },
    ]
    beforeEach(() => { mocks.listerTousLesProjets.mockResolvedValue(PROJETS) })
    const liste = () => screen.queryByRole('listbox', { name: 'Projets' })
    const options = () => screen.getAllByRole('option').map((o) => o.textContent)

    it('« Stand #Sal » : la liste filtrée (projets ouverts) ; Entrée insère #Salon Solaire Expo (R3-047 : le nom avec ses espaces) sans envoyer la phrase', async () => {
      const user = userEvent.setup()
      monter()
      await user.type(champ(), 'Stand #')
      await waitFor(() => expect(liste()).not.toBeNull())
      expect(options()).toEqual(['Salon Solaire Expo', 'Chantier Bénali 9 kWc', 'Site web'])
      expect(champ()).toHaveAttribute('aria-controls', liste().id) // jamais aria-expanded sur un champ texte (axe)
      expect(champ()).not.toHaveAttribute('aria-expanded')
      await user.type(champ(), 'Sal')
      expect(options()).toEqual(['Salon Solaire Expo'])
      await user.keyboard('{Enter}')
      expect(champ()).toHaveValue('Stand #Salon Solaire Expo ')
      expect(liste()).toBeNull()
      expect(mocks.saisieRapide.mock.calls.some(([c]) => c.apercu === false)).toBe(false)
    })

    it('sans accents ni casse, flèches puis Entrée, ou au doigt ; Échap ferme la liste, pas la feuille', async () => {
      const user = userEvent.setup()
      const { onFermer } = monter()
      await user.type(champ(), 'Visite #benal')
      await waitFor(() => expect(options()).toEqual(['Chantier Bénali 9 kWc']))
      await user.keyboard('{Escape}')
      expect(liste()).toBeNull()
      expect(onFermer).not.toHaveBeenCalled()
      await user.clear(champ())
      await user.type(champ(), 'Photos #s')
      await waitFor(() => expect(options()).toEqual(['Salon Solaire Expo', 'Site web']))
      await user.keyboard('{ArrowDown}{Enter}')
      expect(champ()).toHaveValue('Photos #Site web ')
      await user.type(champ(), 'et #cha')
      await user.click(await screen.findByRole('option', { name: 'Chantier Bénali 9 kWc' }))
      expect(champ()).toHaveValue('Photos #Site web et #Chantier Bénali 9 kWc ')
    })

    it('vague 3 — la lettre tapée juste après le choix d\'un projet n\'est jamais avalée (frappes enchaînées, une image passe entre deux)', async () => {
      // `delay: null` : aucune attente entre les touches, comme une frappe rapide sous charge
      const user = userEvent.setup({ delay: null })
      monter()
      await user.type(champ(), 'Photos #s')
      await waitFor(() => expect(options()).toEqual(['Salon Solaire Expo', 'Site web']))
      await user.keyboard('{ArrowDown}{Enter}e')
      // une image passe (rAF) entre la 1re lettre et la suite : rien de ce qui suit le choix ne doit bouger le curseur
      await act(() => new Promise((r) => { requestAnimationFrame(() => r()) }))
      await user.keyboard('t #cha')
      await waitFor(() => expect(options()).toEqual(['Chantier Bénali 9 kWc']))
      await user.keyboard('{Enter}suite')
      expect(champ()).toHaveValue('Photos #Site web et #Chantier Bénali 9 kWc suite')
      expect(champ().selectionStart).toBe(champ().value.length)
    })

    it('vague 3 — choix au MILIEU de la phrase : le curseur se pose juste après le jeton, la suite reste derrière', async () => {
      const user = userEvent.setup({ delay: null })
      monter()
      await user.type(champ(), 'Photos  demain')
      // le curseur revient entre les deux espaces, on tape « #sit »
      act(() => { champ().setSelectionRange(7, 7) })
      await user.keyboard('#sit')
      await waitFor(() => expect(options()).toEqual(['Site web']))
      await user.keyboard('{Enter}x ')
      expect(champ()).toHaveValue('Photos #Site web x demain')
    })

    it('couture r2 — « #Nom » déjà tapé EN ENTIER : Entrée envoie la phrase (la liste ne mange pas la touche)', async () => {
      const user = userEvent.setup()
      monter()
      await user.type(champ(), 'Stand #Salon_Solaire_Expo')
      await waitFor(() => expect(liste()).not.toBeNull())
      await user.keyboard('{Enter}')
      await waitFor(() => expect(mocks.saisieRapide.mock.calls.some(([c]) => c.apercu === false)).toBe(true))
      expect(champ()).toHaveValue('')
    })

    it('la puce « Projet » ouvre le sélecteur ; le projet choisi part avec la ligne et se retire', async () => {
      mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? {
        ...apercu, projets_nouveaux: [], lignes: [{ ...apercu.lignes[0], titre: 'Réserver le stand', jetons: [], alertes: [], champs: {} }],
      } : creation }))
      const user = userEvent.setup()
      monter()
      await user.type(champ(), 'Réserver le stand')
      await user.click(screen.getByRole('button', { name: 'Projet' }))
      await user.click(await screen.findByRole('option', { name: 'Salon Solaire Expo' }))
      expect(screen.getByRole('button', { name: 'Retirer « Salon Solaire Expo »' })).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Ajouter' }))
      await waitFor(() => expect(mocks.saisieRapide.mock.calls.some(([c]) => c.apercu === false)).toBe(true))
      const envoi = mocks.saisieRapide.mock.calls.find(([c]) => c.apercu === false)[0]
      expect(envoi.lignes[0]).toMatchObject({ titre: 'Réserver le stand', projet_id: 11 })
    })
  })

  it('couture r2 — la puce du projet lu porte sa teinte (data-p) ; sans couleur servie, le fond des puces lues', () => {
    const jeton = (nom, couleur) => ({ type: 'projet', source: `#${nom}`, debut: 0, fin: nom.length + 1, libelle: `● ${nom}`,
      valeur: { id: 3, nom, nouveau: false, ...(couleur ? { couleur } : {}) } })
    render(<div className="tch"><ChampSaisie valeur="" onChange={() => {}} jetons={[jeton('Salon', 'indigo'), jeton('Ventes')]} /></div>)
    const [salon, ventes] = document.querySelectorAll('[data-jeton="projet"]')
    expect(salon).toHaveClass('projet-lu')
    expect(salon).toHaveAttribute('data-p', 'indigo')
    expect(ventes).toHaveClass('lue')
    expect(ventes).not.toHaveAttribute('data-p')
  })

  describe('couture r2 — une phrase identique à une tâche ouverte : « Déjà dans ta liste » et « Ajouter quand même »', () => {
    beforeEach(() => {
      mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? {
        ...apercu, projets_nouveaux: [],
        lignes: [{ ...apercu.lignes[0], titre: corps.texte, jetons: [], alertes: [], champs: { priorite: 0 },
          cochee: false, doublon_de: 31, doublon_projet: null }],
      } : creation }))
    })

    it('Entrée ne crée rien et dit « Déjà dans ta liste » (jamais « Aucune ligne lisible. ») ; « Ajouter quand même » la crée', async () => {
      const user = userEvent.setup()
      monter()
      await user.type(champ(), 'Appeler Karim')
      await waitFor(() => expect(mocks.saisieRapide).toHaveBeenCalled(), { timeout: 3000 })
      await user.keyboard('{Enter}')
      expect(await screen.findByRole('alert')).toHaveTextContent('Déjà dans ta liste')
      expect(screen.queryByText('Aucune ligne lisible.')).toBeNull()
      expect(champ()).toHaveValue('Appeler Karim')
      expect(mocks.saisieRapide.mock.calls.some(([c]) => c.apercu === false)).toBe(false)
      await user.click(screen.getByRole('button', { name: 'Ajouter quand même' }))
      await waitFor(() => expect(mocks.saisieRapide.mock.calls.some(([c]) => c.apercu === false)).toBe(true))
      const [creee] = mocks.saisieRapide.mock.calls.find(([c]) => c.apercu === false)[0].lignes
      expect(creee.titre).toBe('Appeler Karim')
    })
  })

  describe('R2-007 — un titre de plus de 280 caractères : le vrai message, le compte, « Mettre le reste en note »', () => {
    const LONG = `${'Préparer le dossier de raccordement '.repeat(8)}et le reste`.trim()
    const MESSAGE = 'Le titre est trop long : 280 caractères au plus.'
    beforeEach(() => {
      mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? {
        ...apercu, projets_nouveaux: [],
        lignes: [{ ...apercu.lignes[0], titre: corps.texte, jetons: [], alertes: [], champs: { priorite: 0 },
          cochee: false, erreurs: { titre: [MESSAGE] } }],
      } : creation }))
    })

    it('le message du serveur sous le champ et « 300 / 280 » ; Entrée ne crée rien et ne dit pas « Aucune ligne lisible. »', async () => {
      expect(LONG.length).toBeGreaterThan(280)
      const user = userEvent.setup()
      monter()
      fireEvent.change(champ(), { target: { value: LONG } })
      expect(await screen.findByRole('alert', {}, { timeout: 3000 })).toHaveTextContent(MESSAGE)
      expect(screen.getByText(`${LONG.length} / 280`)).toBeInTheDocument()
      await user.click(champ())
      await user.keyboard('{End}{Enter}')
      await waitFor(() => expect(champ()).toHaveValue(LONG))
      expect(await screen.findByRole('alert')).toHaveTextContent(MESSAGE)
      expect(screen.queryByText('Aucune ligne lisible.')).toBeNull()
      expect(mocks.saisieRapide.mock.calls.some(([c]) => c.apercu === false)).toBe(false)
      // couture r2 — un 400 de la saisie se dit sous le champ : chaque appel fait taire le toast global
      expect(mocks.saisieRapide.mock.calls.every(([, options]) => options?.erreurSousLeChamp === true)).toBe(true)
    })

    it('« Mettre le reste en note » crée la tâche : 280 caractères au plus en titre, le reste en note', async () => {
      const user = userEvent.setup()
      monter()
      fireEvent.change(champ(), { target: { value: LONG } })
      await user.click(await screen.findByRole('button', { name: 'Mettre le reste en note' }, { timeout: 3000 }))
      await waitFor(() => expect(mocks.saisieRapide.mock.calls.some(([c]) => c.apercu === false)).toBe(true))
      const [ligneCreee] = mocks.saisieRapide.mock.calls.find(([c]) => c.apercu === false)[0].lignes
      expect(ligneCreee.titre.length).toBeLessThanOrEqual(280)
      expect(`${ligneCreee.titre} ${ligneCreee.notes}`).toBe(LONG)
      expect(champ()).toHaveValue('')
    })
  })

  describe('R2-009 (choix C-3) — au bureau, la saisie s\'ouvre EN PLACE sous « Ajouter une tâche »', () => {
    const bureau = (oui) => vi.stubGlobal('matchMedia', (q) => ({
      matches: oui && q === '(min-width: 768px)', media: q, addEventListener() {}, removeEventListener() {},
    }))
    afterEach(() => { vi.unstubAllGlobals() })
    // comme la coquille : l'écran est monté, PUIS la feuille s'ouvre
    const monterEcran = ({ ligne = true } = {}) => {
      const onFermer = vi.fn()
      const ecran = (ouverte) => (
        <ReactReduxContext.Provider value={{ store }}>
          <div className="tch" data-ecran="aujourdhui">
            {ligne ? <SaisieBureau onClick={() => {}} /> : null}
            <ul aria-label="Ma liste"><li><button type="button">Appeler le fournisseur</button></li></ul>
            <FeuilleSaisie ouverte={ouverte} onFermer={onFermer} />
            <ZoneAnnonces />
          </div>
        </ReactReduxContext.Provider>
      )
      const rendu = render(ecran(false))
      rendu.rerender(ecran(true))
      return { onFermer, ...rendu }
    }

    it('en place : posée sous la ligne, sans voile, non modale ; la liste reste à la main ; Entrée ajoute, le champ reste prêt ; Échap ferme', async () => {
      bureau(true)
      const user = userEvent.setup()
      const { onFermer, container } = monterEcran()
      const dialogue = screen.getByRole('dialog', { name: 'Ajouter une tâche' })
      expect(dialogue).toHaveClass('popover-bureau')
      expect(dialogue).toHaveAttribute('aria-modal', 'false')
      expect(container.querySelector('.saisie-bureau + .saisie-ancre')).toContainElement(dialogue)
      expect(container.querySelector('.voile')).toBeNull()
      await waitFor(() => expect(champ()).toHaveFocus())
      // la liste derrière reste vivante : on y clique, le focus y reste, la saisie aussi
      await user.click(screen.getByRole('button', { name: 'Appeler le fournisseur' }))
      expect(screen.getByRole('button', { name: 'Appeler le fournisseur' })).toHaveFocus()
      expect(screen.getByRole('dialog', { name: 'Ajouter une tâche' })).toBeInTheDocument()
      await user.click(champ())
      await user.type(champ(), PHRASE)
      await screen.findByText('Nouveau projet : SiteWeb', {}, { timeout: 3000 })
      await user.keyboard('{Enter}')
      expect(champ()).toHaveValue('') // R2-001 : vidé au toucher, l'envoi part en arrière-plan
      expect(champ()).toHaveFocus()
      await screen.findByRole('group', { name: 'Geste effectué' })
      expect(onFermer).not.toHaveBeenCalled()
      await user.keyboard('{Escape}')
      expect(onFermer).toHaveBeenCalledTimes(1)
    })

    it('R3-044 — une liste collée reste EN PLACE sous la ligne, sans voile (jamais une boîte centrée)', async () => {
      bureau(true)
      const { container } = monterEcran()
      fireEvent.change(champ(), { target: { value: 'Courses\nlait\npain' } })
      const dialogue = screen.getByRole('dialog', { name: 'Ajouter une tâche' })
      expect(dialogue).toHaveClass('popover-bureau')
      expect(dialogue).not.toHaveClass('dialogue-bureau')
      expect(dialogue).toHaveAttribute('aria-modal', 'false')
      expect(container.querySelector('.saisie-bureau + .saisie-ancre')).toContainElement(dialogue)
      expect(container.querySelector('.voile')).toBeNull()
      await waitFor(() => expect(champ()).toHaveFocus())
      expect(champ()).toHaveValue('Courses\nlait\npain')
      // l'aperçu arrive : toujours en place
      expect(await screen.findByText('Aperçu de ta liste', {}, { timeout: 3000 })).toBeInTheDocument()
      expect(screen.getByRole('dialog', { name: 'Ajouter une tâche' })).toHaveClass('popover-bureau')
      expect(container.querySelector('.voile')).toBeNull()
    })

    it('R3-044 — « Coller mes listes » s\'ouvre aussi en place quand la ligne est là', () => {
      bureau(true)
      const { container } = monterEcran()
      act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: { liste: true } })) })
      expect(screen.getByRole('dialog', { name: 'Ajouter une tâche' })).toHaveClass('popover-bureau')
      expect(container.querySelector('.voile')).toBeNull()
    })

    it('sans ligne « Ajouter une tâche » à l\'écran (Agenda, `c t` depuis une autre app) : le dialogue centré', () => {
      bureau(true)
      const { container } = monterEcran({ ligne: false })
      expect(screen.getByRole('dialog', { name: 'Ajouter une tâche' })).toHaveClass('dialogue-bureau')
      expect(container.querySelector('.voile')).not.toBeNull()
    })

    it('iPhone : la feuille du bas, inchangée (la ligne du bureau est cachée)', () => {
      bureau(false)
      const { container } = monterEcran()
      const dialogue = screen.getByRole('dialog', { name: 'Ajouter une tâche' })
      expect(dialogue).not.toHaveClass('popover-bureau')
      expect(dialogue).toHaveAttribute('aria-modal', 'true')
      expect(container.querySelector('.saisie-ancre')).not.toContainElement(dialogue)
      expect(container.querySelector('.voile')).not.toBeNull()
    })
  })

  describe('R3-045 — une puce par chose, le × DANS sa puce, le point à la couleur du projet', () => {
    const lieu = window.location.pathname
    afterEach(() => { window.history.pushState({}, '', lieu) })

    it('le × du jour est DANS la puce « aujourd\'hui » (jamais une bulle qui ne contient qu\'une croix)', async () => {
      window.history.pushState({}, '', '/taches/aujourdhui')
      const { container } = monter()
      act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: {} })) })
      const retirer = await screen.findByRole('button', { name: 'Retirer le jour choisi' })
      const puce = retirer.closest('.puce')
      expect(puce).not.toBeNull()
      expect(within(puce).getByRole('button', { name: "aujourd'hui" })).toBeInTheDocument()
      // aucune puce du pied ne se réduit à sa croix
      const pied = container.querySelector('.saisie-pied')
      ;[...pied.querySelectorAll('.puce')].forEach((p) => expect(p.textContent.trim()).not.toBe(''))
    })

    it('la puce du projet de l\'écran : un point de SA couleur (pas « ● » noir), retirable', async () => {
      mocks.listerTousLesProjets.mockResolvedValue([{ id: 3, nom: 'Ventes', couleur: 'vert', statut: 'actif' }])
      monter()
      act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: { projet_id: 3, projet_nom: 'Ventes' } })) })
      const retirer = await screen.findByRole('button', { name: 'Retirer « Ventes »' })
      const puce = retirer.closest('.puce')
      await waitFor(() => expect(puce).toHaveAttribute('data-p', 'vert'))
      expect(puce.querySelector('.point')).not.toBeNull()
      expect(puce).toHaveTextContent(/^Ventes$/)
    })

    it('un `#projet` lu dans la phrase : la puce du projet de l\'écran s\'efface (il l\'emporte), une seule puce projet', async () => {
      const lu = { type: 'projet', source: '#Ventes', debut: 8, fin: 15, libelle: '● Ventes', valeur: { id: 3, nom: 'Ventes', nouveau: false, couleur: 'vert' } }
      mocks.listerTousLesProjets.mockResolvedValue([{ id: 3, nom: 'Ventes', couleur: 'vert', statut: 'actif' }])
      mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? {
        ...apercu, projets_nouveaux: [],
        lignes: [{ ...apercu.lignes[0], titre: 'Appeler', jetons: corps.texte.includes('#') ? [lu] : [], alertes: [], champs: corps.texte.includes('#') ? { projet_id: 3 } : {} }],
      } : creation }))
      const user = userEvent.setup()
      const { container } = monter()
      act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:saisir', { detail: { projet_id: 3, projet_nom: 'Ventes' } })) })
      await user.type(champ(), 'Appeler #Ventes')
      await waitFor(() => expect(screen.queryByRole('button', { name: 'Retirer « Ventes »' })).toBeNull(), { timeout: 3000 })
      expect(container.querySelectorAll('[data-jeton="projet"]')).toHaveLength(1)
      const puce = container.querySelector('[data-jeton="projet"]')
      expect(puce.querySelector('.point')).not.toBeNull()
      expect(puce).not.toHaveTextContent('●')
    })
  })

  describe('R3-047 — la puce « Projet » du pied montre le projet lu par `#`', () => {
    const PROJETS = [
      { id: 3, nom: 'Ventes', couleur: 'vert', statut: 'actif' },
      { id: 11, nom: 'Salon Solaire Expo', couleur: 'terre', statut: 'actif' },
    ]
    const lu = (source, debut) => ({ type: 'projet', source, debut, fin: debut + source.length, libelle: '● Ventes',
      valeur: { id: 3, nom: 'Ventes', nouveau: false } })
    beforeEach(() => {
      mocks.listerTousLesProjets.mockResolvedValue(PROJETS)
      mocks.saisieRapide.mockImplementation((corps) => {
        const i = corps.texte?.indexOf('#Ventes') ?? -1
        return Promise.resolve({ data: corps.apercu ? {
          ...apercu, projets_nouveaux: [],
          lignes: [{ ...apercu.lignes[0], titre: 'Appeler', jetons: i >= 0 ? [lu('#Ventes', i)] : [], alertes: [], champs: i >= 0 ? { projet_id: 3 } : {} }],
        } : creation })
      })
    })

    it('une seule puce, DANS le pied : le nom et le point de couleur du projet ; « Projet » vide n\'y est plus ; × la retire', async () => {
      const user = userEvent.setup()
      const { container } = monter()
      await user.type(champ(), 'Appeler #Ventes')
      const pied = container.querySelector('.saisie-pied')
      await waitFor(() => expect(pied.querySelector('[data-jeton="projet"]')).not.toBeNull(), { timeout: 3000 })
      expect(container.querySelectorAll('[data-jeton="projet"]')).toHaveLength(1)
      const puce = pied.querySelector('[data-jeton="projet"]')
      expect(puce).toHaveTextContent(/^Ventes$/)
      expect(puce).toHaveAttribute('data-p', 'vert')
      expect(puce.querySelector('.point')).not.toBeNull()
      expect(within(pied).queryByRole('button', { name: 'Projet' })).toBeNull()
      await user.click(within(puce).getByRole('button', { name: 'Retirer Ventes' }))
      await waitFor(() => expect(mocks.saisieRapide.mock.calls.at(-1)[0].ignorer).toEqual([{ type: 'projet', source: '#Ventes' }]))
    })

    it('la toucher ouvre le sélecteur ; un autre projet REMPLACE `#Ventes` dans la phrase (jamais deux `#`)', async () => {
      const user = userEvent.setup()
      const { container } = monter()
      await user.type(champ(), 'Appeler #Ventes demain')
      const pied = container.querySelector('.saisie-pied')
      await waitFor(() => expect(pied.querySelector('[data-jeton="projet"]')).not.toBeNull(), { timeout: 3000 })
      await user.click(within(pied).getByRole('button', { name: 'Ventes' }))
      await user.click(await screen.findByRole('option', { name: 'Salon Solaire Expo' }))
      expect(champ()).toHaveValue('Appeler #Salon Solaire Expo demain')
    })
  })

  it('R3-042 — chaque alerte `deux_*` se lit au pluriel accordé ; « plusieurs projets » sans nom vide', () => {
    expect(Object.fromEntries([
      'jour', 'heure', 'moment', 'echeance', 'quelque_jour', 'projet', 'section', 'priorite', 'etiquette', 'duree',
      'recurrence', 'rappel',
    ].map((type) => [type, phraseAlerte(`deux_${type}`)]))).toEqual({
      jour: 'Deux jours lus : le second reste dans le titre.',
      heure: 'Deux heures lues : la seconde reste dans le titre.',
      moment: 'Deux moments lus : le second reste dans le titre.',
      echeance: 'Deux échéances lues : la seconde reste dans le titre.',
      quelque_jour: 'Deux « un jour » lus : le second reste dans le titre.',
      projet: 'Deux projets lus : le second reste dans le titre.',
      section: 'Deux étapes lues : la seconde reste dans le titre.',
      priorite: 'Deux priorités lues : la seconde reste dans le titre.',
      etiquette: 'Deux étiquettes lues : la seconde reste dans le titre.',
      duree: 'Deux durées lues : la seconde reste dans le titre.',
      recurrence: 'Deux répétitions lues : la seconde reste dans le titre.',
      rappel: 'Deux rappels lus : le second reste dans le titre.',
    })
    // le serveur n'envoie que le code (`analyseur.resoudre_projet`) : jamais « s'appellent «  » »
    expect(phraseAlerte('plusieurs_projets')).toBe('Plusieurs projets commencent ainsi : le premier est choisi.')
    expect(phraseAlerte({ code: 'plusieurs_projets' })).not.toMatch(/«\s*»/)
  })

  it('R3-042 — « plusieurs projets » se tait tant que la liste `#` est ouverte (elle montre déjà les projets)', async () => {
    mocks.listerTousLesProjets.mockResolvedValue([
      { id: 11, nom: 'Salon Solaire Expo', couleur: 'terre', statut: 'actif' },
      { id: 13, nom: 'Site web', couleur: 'ciel', statut: 'actif' },
    ])
    mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? {
      ...apercu, projets_nouveaux: [],
      lignes: [{ ...apercu.lignes[0], titre: 'Photos', jetons: [], alertes: ['plusieurs_projets'], champs: {} }],
    } : creation }))
    const user = userEvent.setup()
    monter()
    await user.type(champ(), 'Photos #s')
    await waitFor(() => expect(mocks.saisieRapide).toHaveBeenCalled(), { timeout: 3000 })
    await waitFor(() => expect(screen.getByRole('listbox', { name: 'Projets' })).toBeInTheDocument())
    expect(screen.queryByText(/Plusieurs projets/)).toBeNull()
    await user.keyboard('{Escape}') // la liste fermée : l'alerte se dit
    expect(await screen.findByText('Plusieurs projets commencent ainsi : le premier est choisi.')).toBeInTheDocument()
  })

  it('messageChamps lit le champ fautif, par ligne ou non', () => {
    expect(messageChamps(erreurs.champ)).toBe('Projet inexistant.')
    expect(messageChamps(erreurs.par_ligne)).toBe('Le titre est vide une fois la date et le projet retirés.')
    expect(messageChamps(null)).toBe('')
    // Raccord F2 — le 400 porte aussi `error` à la racine : il n'est jamais pris pour le champ fautif
    expect(messageChamps({ error: ['validation'], projet_id: ['Projet inexistant.'] })).toBe('Projet inexistant.')
    expect(messageChamps({ error: ['validation'] })).toBe('')
  })
})
