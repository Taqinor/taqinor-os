import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import {
  nouvelleEtape,
  renumeroterEtapes,
  deplacerEtape,
  ajouterEtape,
  retirerEtape,
  validerDefinition,
  normaliserJobs,
  normaliserModeles,
  estEnRetardSla,
  heuresDeRetard,
  normaliserInstances,
} from './workflow'

/* Tests du module Workflow (XPLT8). Deux volets, dans le MEME fichier
   `.test.jsx` (vitest.config.js ne collecte que `*.test.jsx` -- les fichiers
   `*.test.mjs` sont reserves aux contrats source exécutés par `node --test`,
   cf. `src/api/monitoringApi.test.mjs` ; meme convention que
   `features/flotte/flotte.test.jsx` qui mele logique pure et rendu) :
   (1) la logique PURE de `workflow.js` (etapes ordonnees, validation,
   normalisation, SLA) -- aucun DOM requis ; (2) un rendu smoke des deux
   ecrans, enveloppes dans <MemoryRouter> + <ThemeProvider>, cablage API
   mocke pour rester hors reseau. */

describe('workflow.js -- logique pure', () => {
  describe('etapes ordonnees (editeur fonctionnel, pas de canvas)', () => {
    it('nouvelleEtape() renvoie une etape vide avec le bon ordre', () => {
      const s = nouvelleEtape(3)
      expect(s.ordre).toBe(3)
      expect(s.nom).toBe('')
      expect(s.type_approbation).toBe('manuelle')
    })

    it('ajouterEtape() ajoute a la fin et renumerote 1..n', () => {
      let steps = ajouterEtape([])
      expect(steps).toHaveLength(1)
      expect(steps[0].ordre).toBe(1)
      steps = ajouterEtape(steps)
      steps = ajouterEtape(steps)
      expect(steps.map((s) => s.ordre)).toEqual([1, 2, 3])
    })

    it('deplacerEtape() monte une etape et renumerote', () => {
      const steps = [
        { ordre: 1, nom: 'A' },
        { ordre: 2, nom: 'B' },
        { ordre: 3, nom: 'C' },
      ]
      const moved = deplacerEtape(steps, 2, -1) // C monte au-dessus de B
      expect(moved.map((s) => s.nom)).toEqual(['A', 'C', 'B'])
      expect(moved.map((s) => s.ordre)).toEqual([1, 2, 3])
    })

    it('deplacerEtape() descend une etape et renumerote', () => {
      const steps = [
        { ordre: 1, nom: 'A' },
        { ordre: 2, nom: 'B' },
      ]
      const moved = deplacerEtape(steps, 0, 1)
      expect(moved.map((s) => s.nom)).toEqual(['B', 'A'])
    })

    it('deplacerEtape() ignore un deplacement hors bornes (ne jette pas)', () => {
      const steps = [{ ordre: 1, nom: 'A' }]
      expect(deplacerEtape(steps, 0, -1).map((s) => s.nom)).toEqual(['A'])
      expect(deplacerEtape(steps, 0, 1).map((s) => s.nom)).toEqual(['A'])
      expect(deplacerEtape(undefined, 0, 1)).toEqual([])
    })

    it('retirerEtape() retire et renumerote', () => {
      const steps = [
        { ordre: 1, nom: 'A' },
        { ordre: 2, nom: 'B' },
        { ordre: 3, nom: 'C' },
      ]
      const next = retirerEtape(steps, 1) // retire B
      expect(next.map((s) => s.nom)).toEqual(['A', 'C'])
      expect(next.map((s) => s.ordre)).toEqual([1, 2])
    })

    it('renumeroterEtapes() est defensif sur une entree non-tableau', () => {
      expect(renumeroterEtapes(null)).toEqual([])
      expect(renumeroterEtapes(undefined)).toEqual([])
    })
  })

  describe('validation de definition (creation locale)', () => {
    it('rejette une definition sans nom', () => {
      const erreurs = validerDefinition({ nom: '', steps: [{ nom: 'Etape 1' }] })
      expect(erreurs.length).toBeGreaterThan(0)
    })

    it('rejette une definition sans etape', () => {
      const erreurs = validerDefinition({ nom: 'Validation devis', steps: [] })
      expect(erreurs.some((e) => e.includes('étape'))).toBe(true)
    })

    it('rejette une etape sans nom', () => {
      const erreurs = validerDefinition({
        nom: 'X', steps: [{ nom: '' }, { nom: 'B' }],
      })
      expect(erreurs.some((e) => e.includes('1'))).toBe(true)
    })

    it('accepte une definition 3 etapes valides (Done du XPLT8)', () => {
      const erreurs = validerDefinition({
        nom: 'Validation devis',
        steps: [{ nom: 'Etape 1' }, { nom: 'Etape 2' }, { nom: 'Etape 3' }],
      })
      expect(erreurs).toEqual([])
    })

    it('ne jette jamais sur une definition manquante/malformee', () => {
      expect(validerDefinition(undefined).length).toBeGreaterThan(0)
      expect(validerDefinition(null).length).toBeGreaterThan(0)
      expect(() => validerDefinition({})).not.toThrow()
    })
  })

  describe('normalisation des jobs planifies (FG368)', () => {
    it('trie par nom et filtre les entrees non-objet', () => {
      const jobs = normaliserJobs([
        { name: 'Zeta', task: 't1' },
        { name: 'Alpha', task: 't2' },
        null,
        'garbage',
      ])
      expect(jobs.map((j) => j.name)).toEqual(['Alpha', 'Zeta'])
    })

    it('renvoie [] sur une entree non-tableau (jamais de throw)', () => {
      expect(normaliserJobs(undefined)).toEqual([])
      expect(normaliserJobs(null)).toEqual([])
      expect(normaliserJobs({ not: 'an array' })).toEqual([])
    })
  })

  describe('normalisation des modeles de workflow (FG369)', () => {
    it('filtre les entrees non-objet', () => {
      const modeles = normaliserModeles([{ code: 'a' }, null, undefined, 3])
      expect(modeles).toEqual([{ code: 'a' }])
    })

    it('renvoie [] sur une entree non-tableau', () => {
      expect(normaliserModeles(undefined)).toEqual([])
    })
  })

  describe('SLA (echeance / retard)', () => {
    const maintenant = new Date('2026-07-05T12:00:00Z')

    it("detecte un retard SLA quand l'echeance est passee et le statut en attente", () => {
      const item = { statut: 'en_attente', sla_echeance: '2026-07-01T00:00:00Z' }
      expect(estEnRetardSla(item, maintenant)).toBe(true)
    })

    it("ne signale aucun retard si le statut n'est plus en attente", () => {
      const item = { statut: 'approuve', sla_echeance: '2026-07-01T00:00:00Z' }
      expect(estEnRetardSla(item, maintenant)).toBe(false)
    })

    it('ne signale aucun retard sans echeance', () => {
      expect(estEnRetardSla({ statut: 'en_attente' }, maintenant)).toBe(false)
    })

    it('ne jette jamais sur une date invalide ou un item manquant', () => {
      expect(estEnRetardSla({ statut: 'en_attente', sla_echeance: 'pas-une-date' }, maintenant)).toBe(false)
      expect(estEnRetardSla(null, maintenant)).toBe(false)
      expect(estEnRetardSla(undefined, maintenant)).toBe(false)
    })

    it('heuresDeRetard() calcule un delta positif en heures', () => {
      const item = { statut: 'en_attente', sla_echeance: '2026-07-05T06:00:00Z' }
      expect(heuresDeRetard(item, maintenant)).toBe(6)
    })

    it('heuresDeRetard() renvoie 0 si non en retard', () => {
      const item = { statut: 'approuve', sla_echeance: '2026-07-01T00:00:00Z' }
      expect(heuresDeRetard(item, maintenant)).toBe(0)
    })
  })

  describe('normalisation des instances en cours (XKB1, source=workflow)', () => {
    it('ne garde que les items de source "workflow"', () => {
      const out = normaliserInstances({
        items: [
          { id: 1, source: 'workflow', libelle: 'Etape A' },
          { id: 2, source: 'automation', libelle: 'Autre' },
        ],
      })
      expect(out).toHaveLength(1)
      expect(out[0].id).toBe(1)
    })

    it('calcule en_retard localement si absent du payload', () => {
      const out = normaliserInstances({
        items: [
          {
            id: 1, source: 'workflow', statut: 'en_attente',
            sla_echeance: '2000-01-01T00:00:00Z',
          },
        ],
      })
      expect(out[0].en_retard).toBe(true)
    })

    it('respecte en_retard deja fourni par le backend sans le recalculer', () => {
      const out = normaliserInstances({
        items: [{ id: 1, source: 'workflow', en_retard: false }],
      })
      expect(out[0].en_retard).toBe(false)
    })

    it('ne jette jamais sur un payload absent/malforme', () => {
      expect(normaliserInstances(undefined)).toEqual([])
      expect(normaliserInstances({})).toEqual([])
      expect(normaliserInstances({ items: null })).toEqual([])
    })
  })
})

// jsdom n'implemente pas ResizeObserver (mesure par certains primitifs UI).
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (typeof window.matchMedia === 'undefined') {
    window.matchMedia = () => ({
      matches: false,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
    })
  }
})

const jobsList = vi.fn()
const jobsRun = vi.fn()
const templatesList = vi.fn()
const templatesInstaller = vi.fn()
const instancesListPending = vi.fn()
const instancesDecider = vi.fn()
const definitionsList = vi.fn()
const definitionsCreate = vi.fn()
const definitionsUpdate = vi.fn()
const definitionsRemove = vi.fn()

vi.mock('../../api/coreApi', () => ({
  default: {
    jobs: { list: (...a) => jobsList(...a), run: (...a) => jobsRun(...a) },
    workflowTemplates: {
      list: (...a) => templatesList(...a),
      installer: (...a) => templatesInstaller(...a),
    },
    workflowDefinitions: {
      list: (...a) => definitionsList(...a),
      create: (...a) => definitionsCreate(...a),
      update: (...a) => definitionsUpdate(...a),
      remove: (...a) => definitionsRemove(...a),
    },
    workflowInstances: {
      listPending: (...a) => instancesListPending(...a),
      decider: (...a) => instancesDecider(...a),
    },
  },
}))

import TachesPlanifieesScreen from './TachesPlanifieesScreen'
import WorkflowsScreen from './WorkflowsScreen'

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  jobsList.mockResolvedValue({ data: [] })
  jobsRun.mockResolvedValue({ data: { task_id: 'abc123', status: 'envoye' } })
  templatesList.mockResolvedValue({ data: [] })
  templatesInstaller.mockResolvedValue({ data: { code: 'x', nom: 'X', nb_etapes: 3 } })
  instancesListPending.mockResolvedValue({ data: { items: [], total: 0 } })
  instancesDecider.mockResolvedValue({ data: { detail: 'ok' } })
  definitionsList.mockResolvedValue({ data: [] })
  definitionsCreate.mockResolvedValue({
    data: {
      id: 1, nom: 'Validation devis', description: '',
      steps: [{ id: 1 }, { id: 2 }, { id: 3 }],
    },
  })
  definitionsUpdate.mockResolvedValue({ data: { id: 1, steps: [] } })
  definitionsRemove.mockResolvedValue({ data: {} })
})

describe('TachesPlanifieesScreen (FG368)', () => {
  it('se monte sans jeter sur une liste vide', async () => {
    withProviders(<TachesPlanifieesScreen />)
    await waitFor(() => expect(jobsList).toHaveBeenCalled())
    expect(screen.getByText('Tâches planifiées')).toBeTruthy()
  })

  it('se monte sans jeter quand le backend renvoie une forme inattendue', async () => {
    jobsList.mockResolvedValue({ data: null })
    withProviders(<TachesPlanifieesScreen />)
    await waitFor(() => expect(jobsList).toHaveBeenCalled())
  })

  it('affiche la liste des jobs planifies (nom, tache, dernier run)', async () => {
    jobsList.mockResolvedValue({
      data: [
        {
          name: 'Relance devis', task: 'automation.tasks.relance_devis',
          schedule: 'daily', enabled: true, source: 'beat', last_run: null,
        },
      ],
    })
    withProviders(<TachesPlanifieesScreen />)
    // DataTable rend a la fois la table desktop ET les cartes mobiles (masquees
    // par CSS, pas retirees du DOM) : on attend >=1 occurrence.
    await waitFor(() => expect(screen.getAllByText('Relance devis').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Jamais exécuté').length).toBeGreaterThan(0)
  })

  it('declenche l\'execution manuelle d\'un job (bouton Executer)', async () => {
    jobsList.mockResolvedValue({
      data: [{
        name: 'Relance devis', task: 'automation.tasks.relance_devis',
        schedule: 'daily', enabled: true, source: 'beat', last_run: null,
      }],
    })
    const user = userEvent.setup()
    withProviders(<TachesPlanifieesScreen />)
    await waitFor(() => expect(screen.getAllByText('Relance devis').length).toBeGreaterThan(0))

    // Cible la ligne de la table DESKTOP (<tr>) — la carte mobile n'a pas de kebab.
    const row = screen.getAllByText('Relance devis')
      .map((el) => el.closest('tr')).find(Boolean)
    expect(row).toBeTruthy()
    const kebab = within(row).getByLabelText("Plus d'actions sur la ligne")
    await user.click(kebab)
    const executerItem = await screen.findByText('Exécuter')
    await user.click(executerItem)

    await waitFor(() => expect(jobsRun).toHaveBeenCalledWith('automation.tasks.relance_devis'))
  })

  it('degrade proprement (toast) sur un 503 broker indisponible', async () => {
    jobsList.mockResolvedValue({
      data: [{
        name: 'Relance devis', task: 'automation.tasks.relance_devis',
        schedule: 'daily', enabled: true, source: 'beat', last_run: null,
      }],
    })
    jobsRun.mockRejectedValue({ response: { status: 503, data: { detail: 'Broker indisponible.' } } })
    const user = userEvent.setup()
    withProviders(<TachesPlanifieesScreen />)
    await waitFor(() => expect(screen.getAllByText('Relance devis').length).toBeGreaterThan(0))

    const row = screen.getAllByText('Relance devis')
      .map((el) => el.closest('tr')).find(Boolean)
    const kebab = within(row).getByLabelText("Plus d'actions sur la ligne")
    await user.click(kebab)
    const executerItem = await screen.findByText('Exécuter')
    await user.click(executerItem)

    await waitFor(() => expect(jobsRun).toHaveBeenCalled())
    // Ne jette pas : l'ecran reste monte apres l'echec.
    expect(screen.getByText('Tâches planifiées')).toBeTruthy()
  })
})

describe('WorkflowsScreen (FG366/368/369)', () => {
  it('se monte sans jeter et affiche les 3 onglets', async () => {
    withProviders(<WorkflowsScreen />)
    expect(screen.getByRole('tab', { name: 'Definitions' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Modeles' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Instances en cours' })).toBeTruthy()
  })

  it('cree une definition 3 etapes (Done XPLT8) via l\'editeur ordonne', async () => {
    const user = userEvent.setup()
    withProviders(<WorkflowsScreen />)

    await user.type(screen.getByTestId('wf-def-nom'), 'Validation devis')
    await user.click(screen.getByTestId('wf-def-add-step'))
    await user.click(screen.getByTestId('wf-def-add-step'))
    await user.click(screen.getByTestId('wf-def-add-step'))

    const stepInputs = screen.getAllByPlaceholderText("Nom de l'etape")
    expect(stepInputs).toHaveLength(3)
    await user.type(stepInputs[0], 'Etape 1')
    await user.type(stepInputs[1], 'Etape 2')
    await user.type(stepInputs[2], 'Etape 3')

    await user.click(screen.getByTestId('wf-def-create'))

    await waitFor(() => {
      expect(screen.getByTestId('wf-def-created-list')).toBeTruthy()
    })
    expect(screen.getByText('3 etapes')).toBeTruthy()
  })

  it('reordonne les etapes avec les boutons monter/descendre (pas de canvas)', async () => {
    const user = userEvent.setup()
    withProviders(<WorkflowsScreen />)

    await user.click(screen.getByTestId('wf-def-add-step'))
    await user.click(screen.getByTestId('wf-def-add-step'))
    let stepInputs = screen.getAllByPlaceholderText("Nom de l'etape")
    await user.type(stepInputs[0], 'A')
    await user.type(stepInputs[1], 'B')

    const step1 = screen.getByTestId('wf-def-step-1')
    await user.click(within(step1).getByLabelText('Monter'))

    stepInputs = screen.getAllByPlaceholderText("Nom de l'etape")
    expect(stepInputs[0].value).toBe('B')
    expect(stepInputs[1].value).toBe('A')
  })

  it('installe un modele depuis le catalogue (bouton Installer)', async () => {
    templatesList.mockResolvedValue({
      data: [{ code: 'relance_devis', nom: 'Relance devis', description: 'x', nb_etapes: 3, steps: [] }],
    })
    const user = userEvent.setup()
    withProviders(<WorkflowsScreen />)
    await user.click(screen.getByRole('tab', { name: 'Modeles' }))

    await waitFor(() => expect(templatesList).toHaveBeenCalled())
    const installBtn = await screen.findByTestId('wf-template-install-relance_devis')
    await user.click(installBtn)

    await waitFor(() => expect(templatesInstaller).toHaveBeenCalledWith('relance_devis'))
  })

  it('liste les instances en cours et approuve une etape depuis l\'UI', async () => {
    instancesListPending.mockResolvedValue({
      data: {
        items: [
          {
            id: 42, source: 'workflow', libelle: 'Etape workflow',
            statut: 'en_attente', demandeur: 'jdupont',
          },
        ],
        total: 1,
      },
    })
    const user = userEvent.setup()
    withProviders(<WorkflowsScreen />)
    await user.click(screen.getByRole('tab', { name: 'Instances en cours' }))

    await waitFor(() => expect(instancesListPending).toHaveBeenCalled())
    const approveBtn = await screen.findByTestId('wf-instance-approve-42')
    await user.click(approveBtn)

    await waitFor(() =>
      expect(instancesDecider).toHaveBeenCalledWith(42, 'approuver', undefined))
  })

  it('rejette une etape avec motif obligatoire', async () => {
    instancesListPending.mockResolvedValue({
      data: { items: [{ id: 7, source: 'workflow', libelle: 'Etape X', statut: 'en_attente' }], total: 1 },
    })
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('Incomplet')
    const user = userEvent.setup()
    withProviders(<WorkflowsScreen />)
    await user.click(screen.getByRole('tab', { name: 'Instances en cours' }))

    const rejectBtn = await screen.findByTestId('wf-instance-reject-7')
    await user.click(rejectBtn)

    await waitFor(() =>
      expect(instancesDecider).toHaveBeenCalledWith(7, 'refuser', 'Incomplet'))
    promptSpy.mockRestore()
  })

  it('n\'appelle pas decider si le motif de rejet est vide', async () => {
    instancesListPending.mockResolvedValue({
      data: { items: [{ id: 9, source: 'workflow', libelle: 'Etape Y', statut: 'en_attente' }], total: 1 },
    })
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('')
    const user = userEvent.setup()
    withProviders(<WorkflowsScreen />)
    await user.click(screen.getByRole('tab', { name: 'Instances en cours' }))

    const rejectBtn = await screen.findByTestId('wf-instance-reject-9')
    await user.click(rejectBtn)

    expect(instancesDecider).not.toHaveBeenCalled()
    promptSpy.mockRestore()
  })

  it('se monte sans jeter quand les instances renvoient une forme inattendue', async () => {
    instancesListPending.mockResolvedValue({ data: null })
    withProviders(<WorkflowsScreen />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('tab', { name: 'Instances en cours' }))
    await waitFor(() => expect(instancesListPending).toHaveBeenCalled())
  })
})
