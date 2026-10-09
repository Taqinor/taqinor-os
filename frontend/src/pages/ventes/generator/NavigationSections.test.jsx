// EDC9 — navigation de sections collante + cartes d'étude repliables.
// Les puces sont les cartes RÉELLEMENT rendues (une carte absente ⇒ pas de
// puce) ; « Aperçu de la Simulation » est repliée par défaut en Édition
// complète et dépliée en création ; l'état est relu depuis localStorage
// (`devis:edition:cartes-repliees`, par utilisateur) ; un clic défile jusqu'à
// la carte (doux, sauf mouvement réduit) et marque la puce `aria-current`.
//
// Écran RÉEL rendu, API mockées.
// Run : npx vitest run src/pages/ventes/generator/NavigationSections.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor, within, fireEvent, act } from '@testing-library/react'

import {
  DEVIS_INSTALLATION, makeStoreGenerateur, renderGenerateurEdition,
  preparerApisGenerateur, matchMediaDe,
} from '../../../test/generateurEmbarque'

// EDC (gardes CI) : fabriques partagées — src/test/mocksApiDevis.js.
vi.mock('../../../api/crmApi', async () => (await import('../../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../../api/stockApi', async () => (await import('../../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../../api/parametresApi', async () => (await import('../../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../../api/ventesApi', async () => (await import('../../../test/mocksApiDevis.js')).ventesApiMock())

import stockApi from '../../../api/stockApi'
import ventesApi from '../../../api/ventesApi'
import { CLE_CARTES_REPLIEES } from './cartesRepliees'

const rendre = ({ editId = null, role } = {}) => renderGenerateurEdition(
  { editId }, { store: makeStoreGenerateur({ role }) })

const nav = () => screen.getByRole('navigation', { name: 'Sections du devis' })
const puces = () => within(nav()).queryAllByRole('button').map((b) => b.textContent)

const MATCH_MEDIA_ORIGINAL = window.matchMedia
beforeEach(() => {
  preparerApisGenerateur({ stockApi, ventesApi, produits: [], devis: DEVIS_INSTALLATION })
  window.matchMedia = matchMediaDe(false)
})
afterEach(() => {
  window.matchMedia = MATCH_MEDIA_ORIGINAL
  delete globalThis.IntersectionObserver
})

describe('EDC9 — puces = cartes rendues', () => {
  it('création : Document → Enregistrer, sans Échéancier (carte absente en création)', async () => {
    rendre()
    await waitFor(() => expect(puces()).toEqual([
      'Document', 'Lead & Client', 'Technique', 'Simulation', 'Lignes', 'Texte client', 'Enregistrement',
    ]))
    // Chaque puce mène à une carte qui existe.
    for (const id of ['gen-sec-document', 'gen-sec-lignes', 'gen-sec-enregistrer']) {
      expect(document.getElementById(id)).not.toBeNull()
    }
  })

  it('une carte qui disparaît (Simulation en agricole) perd sa puce', async () => {
    rendre()
    await waitFor(() => expect(puces()).toContain('Simulation'))
    fireEvent.click(screen.getByRole('radio', { name: /Agricole/ }))
    await waitFor(() => expect(puces()).not.toContain('Simulation'))
    expect(document.getElementById('gen-sec-simulation')).toBeNull()
    expect(puces()).toContain('Lignes')
  })

  it('Édition complète : la puce Échéancier apparaît avec sa carte', async () => {
    rendre({ editId: 42 })
    await waitFor(() => expect(puces()).toContain('Échéancier'))
    expect(puces()).toEqual([
      'Document', 'Lead & Client', 'Technique', 'Simulation', 'Lignes', 'Échéancier',
      'Texte client', 'Enregistrement',
    ])
  })
})

describe('EDC9 — cartes d\'étude repliables', () => {
  it('création : Simulation dépliée, aucun bouton de repli', async () => {
    rendre()
    await waitFor(() => expect(puces()).toContain('Simulation'))
    expect(document.getElementById('gen-sec-simulation-contenu')).not.toHaveAttribute('hidden')
    expect(screen.queryByRole('button', { name: /« Aperçu de la Simulation »/ })).toBeNull()
  })

  it('Édition complète : Simulation repliée PAR DÉFAUT (en-tête visible), dépliable, choix mémorisé', async () => {
    rendre({ editId: 42 })
    const bouton = await screen.findByRole('button', { name: 'Déplier « Aperçu de la Simulation »' })
    expect(bouton).toHaveAttribute('aria-expanded', 'false')
    expect(bouton).toHaveAttribute('aria-controls', 'gen-sec-simulation-contenu')
    const contenu = document.getElementById('gen-sec-simulation-contenu')
    expect(contenu).toHaveAttribute('hidden')
    // Jamais masquée : la carte et son titre restent là.
    expect(screen.getByText('Aperçu de la Simulation')).toBeInTheDocument()
    fireEvent.click(bouton)
    expect(screen.getByRole('button', { name: 'Replier « Aperçu de la Simulation »' }))
      .toHaveAttribute('aria-expanded', 'true')
    expect(contenu).not.toHaveAttribute('hidden')
    expect(JSON.parse(window.localStorage.getItem(CLE_CARTES_REPLIEES)))
      .toEqual({ 1: { simulation: false, surcharges: true } })
  })

  it('état relu depuis localStorage (par utilisateur) : Simulation dépliée à l\'ouverture', async () => {
    window.localStorage.setItem(CLE_CARTES_REPLIEES, JSON.stringify({
      1: { simulation: false }, 2: { simulation: true },
    }))
    rendre({ editId: 42 })
    const bouton = await screen.findByRole('button', { name: 'Replier « Aperçu de la Simulation »' })
    expect(bouton).toHaveAttribute('aria-expanded', 'true')
    expect(document.getElementById('gen-sec-simulation-contenu')).not.toHaveAttribute('hidden')
  })

  it('stockage illisible : retour au défaut, sans erreur', async () => {
    window.localStorage.setItem(CLE_CARTES_REPLIEES, '{pas du json')
    rendre({ editId: 42 })
    expect(await screen.findByRole('button', { name: 'Déplier « Aperçu de la Simulation »' }))
      .toHaveAttribute('aria-expanded', 'false')
  })

  it('administrateur : « Surcharges (registre) » repliée par défaut, contenu toujours monté', async () => {
    rendre({ editId: 42, role: 'admin' })
    const panneau = await screen.findByTestId('overrides-panel')
    const bouton = within(panneau).getByRole('button', { name: 'Déplier « Surcharges (registre) »' })
    expect(bouton).toHaveAttribute('aria-expanded', 'false')
    expect(document.getElementById('gen-surcharges-contenu')).toHaveAttribute('hidden')
    expect(within(panneau).getByTestId('overrides-valeur')).toBeInTheDocument()
  })
})

describe('EDC9 — défilement et section courante', () => {
  it('un clic défile jusqu\'à la carte (doux) et marque la puce aria-current', async () => {
    const spy = vi.spyOn(Element.prototype, 'scrollIntoView')
    rendre()
    await waitFor(() => expect(puces()).toContain('Lignes'))
    spy.mockClear()
    const lignesPuce = within(nav()).getByRole('button', { name: 'Lignes' })
    fireEvent.click(lignesPuce)
    const carte = document.getElementById('gen-sec-lignes')
    const appel = spy.mock.contexts.findIndex((ctx) => ctx === carte)
    expect(appel).toBeGreaterThanOrEqual(0)
    expect(spy.mock.calls[appel][0]).toEqual({ block: 'start', behavior: 'smooth' })
    expect(lignesPuce).toHaveAttribute('aria-current', 'true')
    expect(within(nav()).getByRole('button', { name: 'Document' })).not.toHaveAttribute('aria-current')
    spy.mockRestore()
  })

  it('mouvement réduit : défilement instantané', async () => {
    window.matchMedia = matchMediaDe(true)
    const spy = vi.spyOn(Element.prototype, 'scrollIntoView')
    rendre()
    await waitFor(() => expect(puces()).toContain('Texte client'))
    spy.mockClear()
    fireEvent.click(within(nav()).getByRole('button', { name: 'Texte client' }))
    const carte = document.getElementById('gen-sec-texte')
    const appel = spy.mock.contexts.findIndex((ctx) => ctx === carte)
    expect(spy.mock.calls[appel][0]).toEqual({ block: 'start', behavior: 'auto' })
    spy.mockRestore()
  })

  it('la section qui croise la bande sous la barre devient la puce courante (IntersectionObserver)', async () => {
    const instances = []
    globalThis.IntersectionObserver = class {
      constructor(cb, options) { this.cb = cb; this.options = options; this.cibles = []; instances.push(this) }
      observe(el) { this.cibles.push(el) }
      unobserve() {}
      disconnect() {}
    }
    rendre()
    await waitFor(() => expect(puces()).toContain('Technique'))
    await waitFor(() => expect(instances.at(-1)?.cibles.length).toBe(7))
    const io = instances.at(-1)
    expect(io.options.rootMargin).toMatch(/^-\d+px 0px -55% 0px$/)
    const technique = document.getElementById('gen-sec-technique')
    act(() => io.cb([{ target: technique, isIntersecting: true }]))
    expect(within(nav()).getByRole('button', { name: 'Technique' })).toHaveAttribute('aria-current', 'true')
  })
})
