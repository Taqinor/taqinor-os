import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReactReduxContext } from 'react-redux'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { memoryStore } from '../../../lib/offlineOutbox'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { creerFile, definirCompteFile, remplacerFile } from '../horsligne/captureQueue'
import { reinitialiserGestes } from '../lib/gestes'
import { ZoneAnnonces } from '../coquille/CoquilleTaches'
import FeuilleSaisie, { cleBrouillon, EVENEMENT_CREEES, lireBrouillon, messageChamps } from './FeuilleSaisie'

const mocks = vi.hoisted(() => ({ saisieRapide: vi.fn(), annulerGeste: vi.fn() }))
vi.mock('../../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  saisieRapide: mocks.saisieRapide,
  annulerGeste: mocks.annulerGeste,
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
      await waitFor(() => expect(onFermer).toHaveBeenCalled())
      expect(vusALInstant).toEqual([null])
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

    it('une coupure pendant l\'envoi met la ligne en file au lieu d\'une erreur ; sans analyse, le texte entier sert de titre', async () => {
      const user = userEvent.setup()
      mocks.saisieRapide.mockRejectedValue(new Error('Network Error'))
      const { onFermer } = monter()
      await user.type(champ(), 'Rappeler Salma')
      await user.click(screen.getByRole('button', { name: 'Ajouter' }))
      await waitFor(() => expect(onFermer).toHaveBeenCalled())
      const [op] = await file.pending()
      expect(op.payload.corps.lignes).toEqual([expect.objectContaining({ index: 0, titre: 'Rappeler Salma' })])
      expect(screen.queryByText(/Pas de réseau/)).toBeNull()
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
