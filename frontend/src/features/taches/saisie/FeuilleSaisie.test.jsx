import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReactReduxContext } from 'react-redux'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { memoryStore } from '../../../lib/offlineOutbox'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { creerFile, definirCompteFile, remplacerFile } from '../horsligne/captureQueue'
import { reinitialiserGestes } from '../lib/gestes'
import { aujourdhuiIso } from '../lib/textes'
import { ZoneAnnonces } from '../coquille/CoquilleTaches'
import FeuilleSaisie, { cleBrouillon, EVENEMENT_CREEES, lireBrouillon, messageChamps } from './FeuilleSaisie'
import { morceauxSurlignes } from '../ui/ChampSaisie'

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
    await user.click(screen.getByRole('radio', { name: 'En réserve' }))
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
      await waitFor(() => expect(onFermer).toHaveBeenCalled())
      expect(mocks.saisieRapide.mock.calls.some(([corps]) => corps.apercu === false)).toBe(false)
      const [op] = await file.pending()
      expect(op.payload.corps.lignes[0]).toMatchObject({ titre: 'Appeler Karim', nouveau_projet: { nom: 'SiteWeb' } })
      expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Partira dès le retour du réseau')
    })

    it('la mise en file efface le brouillon avant de fermer la feuille (et avant tout rejeu qui émet l\'événement)', async () => {
      const user = userEvent.setup()
      const vusALaFermeture = []
      const fermer = vi.fn(() => vusALaFermeture.push(lireBrouillon(7, 42)))
      monter({ onFermer: fermer })
      await user.type(champ(), PHRASE)
      expect(lireBrouillon(7, 42)).not.toBeNull()
      act(() => {
        Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true })
        window.dispatchEvent(new Event('offline'))
      })
      await user.click(screen.getByRole('button', { name: 'Ajouter' }))
      await waitFor(() => expect(fermer).toHaveBeenCalled())
      expect(vusALaFermeture).toEqual([null])
    })

    it('une coupure pendant l\'envoi met la PHRASE en file (R2-008a : le serveur la lira au rejeu), jamais une erreur', async () => {
      const user = userEvent.setup()
      mocks.saisieRapide.mockRejectedValue(new Error('Network Error'))
      const { onFermer } = monter()
      await user.type(champ(), 'Rappeler Salma')
      await user.click(screen.getByRole('button', { name: 'Ajouter' }))
      await waitFor(() => expect(onFermer).toHaveBeenCalled())
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

    it('« Stand #Sal » : la liste filtrée (projets ouverts) ; Entrée insère #Salon_Solaire_Expo sans envoyer la phrase', async () => {
      const user = userEvent.setup()
      monter()
      await user.type(champ(), 'Stand #')
      await waitFor(() => expect(liste()).not.toBeNull())
      expect(options()).toEqual(['Salon Solaire Expo', 'Chantier Bénali 9 kWc', 'Site web'])
      expect(champ()).toHaveAttribute('aria-expanded', 'true')
      await user.type(champ(), 'Sal')
      expect(options()).toEqual(['Salon Solaire Expo'])
      await user.keyboard('{Enter}')
      expect(champ()).toHaveValue('Stand #Salon_Solaire_Expo ')
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
      expect(champ()).toHaveValue('Photos #Site_web ')
      await user.type(champ(), 'et #cha')
      await user.click(await screen.findByRole('option', { name: 'Chantier Bénali 9 kWc' }))
      expect(champ()).toHaveValue('Photos #Site_web et #Chantier_Bénali_9_kWc ')
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

  it('messageChamps lit le champ fautif, par ligne ou non', () => {
    expect(messageChamps(erreurs.champ)).toBe('Projet inexistant.')
    expect(messageChamps(erreurs.par_ligne)).toBe('Le titre est vide une fois la date et le projet retirés.')
    expect(messageChamps(null)).toBe('')
    // Raccord F2 — le 400 porte aussi `error` à la racine : il n'est jamais pris pour le champ fautif
    expect(messageChamps({ error: ['validation'], projet_id: ['Projet inexistant.'] })).toBe('Projet inexistant.')
    expect(messageChamps({ error: ['validation'] })).toBe('')
  })
})
