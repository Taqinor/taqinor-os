import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../lib/gestes'
import VueChronologie, { Burnup } from './VueChronologie'
import Tableau from '../ui/Tableau'

vi.mock('../../../api/tachesApi', async (original) => ({
  ...(await original()),
  lireVueProjet: vi.fn(),
  modifierProjet: vi.fn(),
  modifierTache: vi.fn(),
  annulerGeste: vi.fn(),
  listerToutesLesTaches: vi.fn(),
  listerTousLesProjets: vi.fn(),
}))

const api = await import('../../../api/tachesApi')
const { default: Projet } = await import('../../../pages/taches/Projet')

/* TCH90 — vues Tableau et Chronologie d'un projet (mémorisées dans `affichage.vue`), burn-up. Tout est lu de
   `projet_vue.json` (`exempleContrat`) : une étape, un jalon, l'échéance du projet, `burnup`. La vue mémorisée se
   prouve par « enregistrer → rouvrir → enregistrer sans toucher » : l'objet du SERVEUR (un faux serveur en mémoire
   qui applique le PATCH comme le vrai) ne bouge plus au second passage. */

const AUJOURDHUI = '2026-11-17'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(`${AUJOURDHUI}T09:00:00`))
  reinitialiserGestes()
})
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks(); reinitialiserGestes() })

/** La vue servie, avec une étape datée, un jalon, une tâche sans date et l'échéance du projet. */
function vueDatee() {
  const vue = structuredClone(exempleContrat('taches', 'projet_vue'))
  vue.sections[0].date_debut = '2026-11-09'
  vue.sections[0].taches[0].jalon = true
  vue.sections[0].taches[0].echeance = '2026-11-19'
  vue.projet.echeance = '2026-12-15'
  vue.sans_section[0].jour_prevu = null
  vue.sans_section[0].echeance = null
  return vue
}

describe('TCH90 — Chronologie', () => {
  it('range étapes, jalon, aujourd\'hui et échéance par date, avec « Sans date » et les comptes SERVIS', () => {
    render(<VueChronologie vue={vueDatee()} aujourdhui={AUJOURDHUI} />)
    const frise = screen.getByRole('list', { name: 'Chronologie du projet jusqu\'à l\'échéance' })
    const lignes = within(frise).getAllByRole('listitem').map((l) => l.textContent)
    expect(lignes).toEqual([
      expect.stringContaining('Études'),
      expect.stringContaining("Aujourd'hui"),
      expect.stringContaining('Devis Settat'),
      expect.stringContaining('Échéance du projet'),
    ])
    expect(lignes[0]).toContain('lun. 09/11 → lun. 30')
    expect(lignes[0]).toContain('4 sur 5') // 4 faites, 1 ouverte : `compteurs` du serveur, jamais recompté
    expect(lignes[2]).toContain('Jalon')
    expect(lignes[3]).toContain('mar. 15 déc.')
    expect(screen.getByText('Sans date :').parentElement).toHaveTextContent('Sans date : Timbres')
  })

  it('une étape sans date se range au jour même, « Sans date »', () => {
    const vue = vueDatee()
    vue.sections[0].date_debut = null
    vue.sections[0].date_fin = null
    render(<VueChronologie vue={vue} aujourdhui={AUJOURDHUI} />)
    const frise = screen.getByRole('list', { name: 'Chronologie du projet jusqu\'à l\'échéance' })
    expect(within(frise).getAllByRole('listitem')[0]).toHaveTextContent('Sans date')
  })

  it('dessine la piste du bureau : barre de l\'étape, jalon, traits « aujourd\'hui » et « échéance »', () => {
    render(<VueChronologie vue={vueDatee()} aujourdhui={AUJOURDHUI} />)
    const piste = screen.getByRole('group', { name: /Chronologie : étapes et jalons/ })
    expect(within(piste).getByText('Études')).toBeInTheDocument()
    expect(within(piste).getByText(/Devis Settat · jeu\. 19/)).toBeInTheDocument()
    expect(within(piste).getByText(/Échéance · mar\. 15 déc\./)).toBeInTheDocument()
    expect(within(piste).getByText(/Aujourd'hui · mar\. 17/)).toBeInTheDocument()
  })
})

describe('TCH90 — Burn-up « Avancement par semaine »', () => {
  it('rend les points SERVIS et la légende du serveur', () => {
    render(<Burnup vue={exempleContrat('taches', 'projet_vue')} aujourdhui={AUJOURDHUI} />)
    const liste = screen.getByRole('list', { name: 'Avancement par semaine' })
    expect(within(liste).getAllByRole('listitem')).toHaveLength(1)
    expect(liste).toHaveTextContent('10 sur 18')
    expect(screen.getByText('reconstruit depuis les dates actuelles')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Avancement par semaine/ })).toBeInTheDocument()
  })

  it('autant de points que de semaines servies, sans légende si le serveur n\'en sert pas', () => {
    const vue = exempleContrat('taches', 'projet_vue')
    vue.burnup = [{ semaine: '2026-11-02', total: 10, faites: 4 }, { semaine: '2026-11-09', total: 18, faites: 10 }]
    vue.burnup_legende = null
    render(<Burnup vue={vue} aujourdhui={AUJOURDHUI} />)
    expect(within(screen.getByRole('list', { name: 'Avancement par semaine' })).getAllByRole('listitem')).toHaveLength(2)
    expect(screen.queryByText(/reconstruit/)).toBeNull()
  })
})

/** Un faux serveur : `lireVueProjet` rend l'objet mémorisé, `modifierProjet` l'écrit (verrou compris) comme le vrai. */
function fauxServeur() {
  const serveur = { vue: structuredClone(exempleContrat('taches', 'projet_vue')) }
  api.lireVueProjet.mockImplementation(async () => ({ data: structuredClone(serveur.vue) }))
  api.modifierProjet.mockImplementation(async (id, corps) => {
    const projet = serveur.vue.projet
    if (corps.lock_version !== projet.lock_version) throw Object.assign(new Error('conflit'), { response: { status: 409, data: { code: 'conflit_version' } } })
    serveur.vue.projet = { ...projet, affichage: { ...projet.affichage, ...corps.affichage }, lock_version: projet.lock_version + 1 }
    return { data: structuredClone(serveur.vue.projet) }
  })
  return serveur
}

const monter = (chemin = '/taches/projets/3') => render(
  <MemoryRouter initialEntries={[chemin]}>
    <Routes><Route path="/taches/projets/:id" element={<Projet />} /></Routes>
  </MemoryRouter>,
)

describe('TCH90 — la vue choisie est mémorisée côté serveur (affichage.vue)', () => {
  it('enregistrer → rouvrir → enregistrer sans toucher : l\'objet du serveur ne bouge plus', async () => {
    const serveur = fauxServeur()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const premier = monter()
    const choix = await screen.findByRole('radiogroup', { name: 'Vue' })
    expect(within(choix).getByRole('radio', { name: 'Liste' })).toBeChecked()

    await user.click(within(choix).getByRole('radio', { name: 'Chronologie' })) // 1. enregistrer
    await waitFor(() => expect(serveur.vue.projet.affichage.vue).toBe('chronologie'))
    expect(api.modifierProjet).toHaveBeenCalledWith(3, expect.objectContaining({
      affichage: expect.objectContaining({ vue: 'chronologie', tri: 'manuel', groupe: 'section' }), lock_version: 4,
    }))
    expect(serveur.vue.projet.lock_version).toBe(5)
    expect(screen.getByRole('list', { name: 'Chronologie du projet jusqu\'à l\'échéance' })).toBeInTheDocument()
    premier.unmount()

    monter() // 2. rouvrir : sans `?vue=`, la vue mémorisée revient d'elle-même
    expect(await screen.findByRole('list', { name: 'Chronologie du projet jusqu\'à l\'échéance' })).toBeInTheDocument()
    expect(within(screen.getByRole('radiogroup', { name: 'Vue' })).getByRole('radio', { name: 'Chronologie' })).toBeChecked()

    const apres = structuredClone(serveur.vue.projet)
    api.modifierProjet.mockClear()
    await user.click(within(screen.getByRole('radiogroup', { name: 'Vue' })).getByRole('radio', { name: 'Chronologie' })) // 3. sans toucher
    expect(api.modifierProjet).not.toHaveBeenCalled()
    expect(serveur.vue.projet).toEqual(apres)
  })

  it('une vue de l\'adresse (?vue=tableau) s\'affiche sans rien écrire ; la choisir la mémorise', async () => {
    const serveur = fauxServeur()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    monter('/taches/projets/3?vue=tableau')
    expect(await screen.findByRole('region', { name: 'Études' })).toBeInTheDocument()
    expect(screen.getByRole('tablist', { name: 'Étapes' })).toBeInTheDocument()
    expect(api.modifierProjet).not.toHaveBeenCalled()
    await user.click(within(screen.getByRole('radiogroup', { name: 'Vue' })).getByRole('radio', { name: 'Tableau' }))
    await waitFor(() => expect(serveur.vue.projet.affichage.vue).toBe('tableau'))
    expect(api.modifierProjet).toHaveBeenCalledTimes(1)
  })

  it('un refus du serveur remet la vue d\'avant et le dit', async () => {
    const serveur = fauxServeur()
    api.modifierProjet.mockRejectedValue({ response: { status: 400, data: { detail: 'Valeur inconnue.' } } })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    monter()
    await user.click(within(await screen.findByRole('radiogroup', { name: 'Vue' })).getByRole('radio', { name: 'Tableau' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(serveur.vue.projet.affichage.vue).toBe('liste')
  })

  it('« Avancement par semaine » s\'ouvre depuis le ⋯ du projet avec le burn-up servi', async () => {
    fauxServeur()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    monter()
    await screen.findByRole('radiogroup', { name: 'Vue' })
    await user.click(screen.getByRole('button', { name: /Plus d'actions|Plus/ }))
    await user.click(await screen.findByRole('menuitem', { name: 'Avancement par semaine' }))
    expect(await screen.findByText('10 sur 18')).toBeInTheDocument()
  })
})

/** dnd-kit mesure les rectangles : jsdom n'en a pas, on pose des colonnes côte à côte (une carte par colonne). */
function poserRectangles() {
  const original = Element.prototype.getBoundingClientRect
  Element.prototype.getBoundingClientRect = function rect() {
    const colonne = this.matches?.('section.ep-col') ? this : this.closest?.('section.ep-col')
    if (!colonne) return original.call(this)
    const rang = Array.from(colonne.parentElement.children).indexOf(colonne)
    const carte = this.classList?.contains('ep-carte')
    const gauche = rang * 300 + (carte ? 8 : 0)
    const largeur = carte ? 264 : 280
    const haut = carte ? 40 : 0
    const hauteur = carte ? 60 : 400
    return { x: gauche, y: haut, left: gauche, top: haut, right: gauche + largeur, bottom: haut + hauteur, width: largeur, height: hauteur, toJSON() { return this } }
  }
  return () => { Element.prototype.getBoundingClientRect = original }
}

describe('TCH90 — Tableau : déplacer une carte au clavier (kanbanA11y.js)', () => {
  let rendre
  beforeEach(() => { rendre = poserRectangles() })
  afterEach(() => rendre())

  // dnd-kit n'écoute le clavier qu'un tour d'horloge APRÈS la saisie : chaque touche attend ce tour.
  const touche = async (cible, code) => {
    await act(async () => {
      fireEvent.keyDown(cible, { code, key: code === 'Space' ? ' ' : code })
      await new Promise((fin) => { setTimeout(fin, 15) })
    })
  }
  const deplacerAuClavier = async (poignee) => {
    poignee.focus()
    await touche(poignee, 'Space')
    await touche(document, 'ArrowRight')
    await touche(document, 'Space')
  }

  it('une colonne par étape puis « Sans étape » ; la poignée porte les instructions et les annonces en français', () => {
    render(<Tableau vue={exempleContrat('taches', 'projet_vue')} aujourdhui={AUJOURDHUI} onDeplacer={vi.fn()} onTerminer={vi.fn()}
      onOuvrir={vi.fn()} onAction={vi.fn()} onAjouter={vi.fn()} onAnnonce={vi.fn()} />)
    expect(within(screen.getByRole('region', { name: 'Études' })).getByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Sans étape' })).getByRole('button', { name: 'Timbres' })).toBeInTheDocument()
    expect(screen.getAllByText('4 sur 5').length).toBeGreaterThan(0) // l'onglet et l'en-tête de colonne : le compte SERVI
    const poignee = screen.getByRole('button', { name: 'Déplacer « Devis Settat »' })
    const aide = document.getElementById(poignee.getAttribute('aria-describedby'))
    expect(aide).toHaveTextContent('Pour déplacer une carte au clavier')
  })

  it('Espace, → puis Espace : la carte change de colonne (onDeplacer reçoit la tâche et l\'étape cible)', async () => {
    const onDeplacer = vi.fn()
    render(<Tableau vue={exempleContrat('taches', 'projet_vue')} aujourdhui={AUJOURDHUI} onDeplacer={onDeplacer} onTerminer={vi.fn()}
      onOuvrir={vi.fn()} onAction={vi.fn()} onAjouter={vi.fn()} onAnnonce={vi.fn()} />)
    await deplacerAuClavier(screen.getByRole('button', { name: 'Déplacer « Devis Settat »' }))
    await waitFor(() => expect(onDeplacer).toHaveBeenCalledTimes(1))
    expect(onDeplacer.mock.calls[0][0].id).toBe(20)
    expect(onDeplacer.mock.calls[0][1]).toBeNull() // « Sans étape »
  })

  it('déposer dans la même colonne n\'écrit rien', async () => {
    const onDeplacer = vi.fn()
    render(<Tableau vue={exempleContrat('taches', 'projet_vue')} aujourdhui={AUJOURDHUI} onDeplacer={onDeplacer} onTerminer={vi.fn()}
      onOuvrir={vi.fn()} onAction={vi.fn()} onAjouter={vi.fn()} onAnnonce={vi.fn()} />)
    const poignee = screen.getByRole('button', { name: 'Déplacer « Devis Settat »' })
    poignee.focus()
    await touche(poignee, 'Space')
    await touche(document, 'Space')
    expect(onDeplacer).not.toHaveBeenCalled()
  })

  it('dans l\'écran : la carte part dans « Sans étape » à l\'instant, le serveur confirme, Annuler la remet', async () => {
    fauxServeur()
    api.modifierTache.mockResolvedValue({ data: exempleContrat('taches', 'tache_ecrite') })
    api.annulerGeste.mockResolvedValue({ data: {} })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    monter('/taches/projets/3?vue=tableau')
    await screen.findByRole('region', { name: 'Études' })
    await deplacerAuClavier(screen.getByRole('button', { name: 'Déplacer « Devis Settat »' }))
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledWith(20, { section_id: null, lock_version: 4 }))
    expect(within(screen.getByRole('region', { name: 'Sans étape' })).getByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Études' })).queryByRole('button', { name: 'Devis Settat' })).toBeNull()
    expect(api.lireVueProjet).toHaveBeenCalledTimes(1) // la vue n'est pas relue

    await user.click(await screen.findByRole('button', { name: 'Annuler' }))
    expect(api.annulerGeste).toHaveBeenCalledWith(77)
    await waitFor(() => expect(within(screen.getByRole('region', { name: 'Études' })).getByRole('button', { name: 'Devis Settat' })).toBeInTheDocument())
  })

  it('un refus du serveur ramène la carte dans sa colonne et le dit', async () => {
    fauxServeur()
    api.modifierTache.mockRejectedValue(new Error('Network Error'))
    monter('/taches/projets/3?vue=tableau')
    await screen.findByRole('region', { name: 'Études' })
    await deplacerAuClavier(screen.getByRole('button', { name: 'Déplacer « Devis Settat »' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Études' })).getByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
  })
})
