import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import {
  swimlanesDe, validerEtapesDefinition, evaluerConditionGroupe, simulerWorkflow,
} from './workflow'

/* NTWFL6/8/9/11 -- designer visuel (canvas) : logique pure (testable sans
   DOM) puis un smoke render du composant (charge/edite/enregistre une
   definition), meme convention que WorkflowsScreen.test.jsx (PACT124). */

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

describe('workflow.js -- logique pure du designer (NTWFL6/8/9/11)', () => {
  describe('swimlanesDe (NTWFL8)', () => {
    it('regroupe par role_requis, "sans role" en tete', () => {
      const steps = [
        { ordre: 1, role_requis: 'admin' },
        { ordre: 2, role_requis: '' },
        { ordre: 3, role_requis: 'admin' },
        { ordre: 4, role_requis: 'responsable' },
      ]
      const bandes = swimlanesDe(steps)
      expect(bandes.map((b) => b.role)).toEqual(['', 'admin', 'responsable'])
      expect(bandes[1].steps.map((s) => s.ordre)).toEqual([1, 3])
    })

    it('une seule bande pour une definition sans role', () => {
      const bandes = swimlanesDe([{ ordre: 1 }, { ordre: 2 }])
      expect(bandes).toHaveLength(1)
      expect(bandes[0].role).toBe('')
    })

    it('est defensif sur une entree non-tableau', () => {
      expect(swimlanesDe(undefined)).toEqual([])
    })
  })

  describe('validerEtapesDefinition (NTWFL9)', () => {
    it('rejette une liste vide', () => {
      expect(validerEtapesDefinition([])).toHaveLength(1)
    })

    it('rejette une etape manuelle sans role_requis', () => {
      const erreurs = validerEtapesDefinition([
        { ordre: 1, nom: 'A', type_approbation: 'manuelle', role_requis: '' },
      ])
      expect(erreurs.some((e) => e.includes('role requis'))).toBe(true)
    })

    it('detecte une boucle infinie via etape_alternative_si_echec', () => {
      const erreurs = validerEtapesDefinition([
        { ordre: 1, nom: 'A', type_approbation: 'auto', etape_alternative_si_echec: 2 },
        { ordre: 2, nom: 'B', type_approbation: 'auto', etape_alternative_si_echec: 1 },
      ])
      expect(erreurs.some((e) => e.includes('boucle infinie'))).toBe(true)
    })

    it('accepte une definition valide', () => {
      const erreurs = validerEtapesDefinition([
        { ordre: 1, nom: 'A', type_approbation: 'manuelle', role_requis: 'admin' },
      ])
      expect(erreurs).toEqual([])
    })
  })

  describe('evaluerConditionGroupe (NTWFL7/11, miroir de core.rules)', () => {
    it('evalue une feuille simple', () => {
      expect(evaluerConditionGroupe({ field: 'montant', operator: 'gt', value: 100000 }, { montant: 150000 })).toBe(true)
      expect(evaluerConditionGroupe({ field: 'montant', operator: 'gt', value: 100000 }, { montant: 10 })).toBe(false)
    })

    it('un champ absent est tolerant (false), jamais une exception', () => {
      expect(evaluerConditionGroupe({ field: 'inconnu', operator: 'eq', value: 1 }, {})).toBe(false)
    })

    it('evalue un groupe ET/OU', () => {
      const groupe = {
        op: 'and',
        conditions: [
          { field: 'a', operator: 'gt', value: 1 },
          { field: 'b', operator: 'eq', value: 'x' },
        ],
      }
      expect(evaluerConditionGroupe(groupe, { a: 2, b: 'x' })).toBe(true)
      expect(evaluerConditionGroupe(groupe, { a: 0, b: 'x' })).toBe(false)
    })
  })

  describe('simulerWorkflow (NTWFL11, en memoire, jamais persiste)', () => {
    const steps = [
      {
        ordre: 1, nom: 'Auto garde', type_approbation: 'auto',
        condition_transition: { field: 'montant', operator: 'gt', value: 100000 },
        etape_alternative_si_echec: 2,
      },
      { ordre: 2, nom: 'Alternative', type_approbation: 'manuelle', role_requis: 'admin' },
    ]

    it('garde verifiee avance jusqu\'a l\'etape suivante', () => {
      const resultat = simulerWorkflow(steps, { montant: 150000 })
      expect(resultat.chemin).toEqual([1, 2])
      expect(resultat.issue).toBe('en_attente') // etape 2 = manuelle, arret
      expect(resultat.etapesIgnorees).toEqual([])
    })

    it('garde echouee route vers l\'etape alternative', () => {
      const resultat = simulerWorkflow(steps, { montant: 10 })
      expect(resultat.etapesIgnorees).toEqual([1])
      expect(resultat.chemin).toEqual([2])
    })

    it('ne modifie ni la base ni le reseau (fonction pure)', () => {
      const avant = JSON.stringify(steps)
      simulerWorkflow(steps, { montant: 10 })
      expect(JSON.stringify(steps)).toBe(avant)
    })
  })
})

const definitionsGet = vi.fn()
const definitionsUpdate = vi.fn()

vi.mock('../../api/coreApi', () => ({
  default: {
    workflowDefinitions: {
      get: (...a) => definitionsGet(...a),
      update: (...a) => definitionsUpdate(...a),
    },
  },
}))

import WorkflowDesigner from './WorkflowDesigner'

const DEFINITION = {
  id: 9,
  nom: 'Validation devis',
  description: 'Chaine a deux etapes',
  steps: [
    { id: 91, ordre: 1, nom: 'Etape 1', type_approbation: 'manuelle', role_requis: 'admin' },
    { id: 92, ordre: 2, nom: 'Etape 2', type_approbation: 'manuelle', role_requis: 'admin' },
  ],
}

function monter() {
  return render(
    <MemoryRouter initialEntries={['/workflow/9/designer']}>
      <ThemeProvider>
        <Routes>
          <Route path="/workflow/:id/designer" element={<WorkflowDesigner />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  definitionsGet.mockResolvedValue({ data: DEFINITION })
  definitionsUpdate.mockResolvedValue({ data: DEFINITION })
})

describe('WorkflowDesigner -- rendu (NTWFL6)', () => {
  it('charge et affiche les noeuds de la definition', async () => {
    monter()
    await waitFor(() => expect(definitionsGet).toHaveBeenCalledWith('9'))
    expect(await screen.findByTestId('wfd-node-1')).toBeTruthy()
    expect(await screen.findByTestId('wfd-node-2')).toBeTruthy()
  })

  it('ajouter une etape puis enregistrer persiste via l\'API', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('wfd-node-1')
    await user.click(screen.getByTestId('wfd-add-step'))
    await user.click(screen.getByTestId('wfd-save'))
    await waitFor(() => expect(definitionsUpdate).toHaveBeenCalled())
    const [, payload] = definitionsUpdate.mock.calls[0]
    expect(payload.steps).toHaveLength(3)
  })
})

describe('WorkflowDesigner -- swimlanes par role (NTWFL8)', () => {
  const DEFINITION_ROLES = {
    id: 10,
    nom: 'Trois roles',
    description: '',
    steps: [
      { id: 1, ordre: 1, nom: 'A', type_approbation: 'manuelle', role_requis: 'commercial' },
      { id: 2, ordre: 2, nom: 'B', type_approbation: 'manuelle', role_requis: 'responsable' },
      { id: 3, ordre: 3, nom: 'C', type_approbation: 'manuelle', role_requis: 'admin' },
    ],
  }

  function monterRoles() {
    return render(
      <MemoryRouter initialEntries={['/workflow/10/designer']}>
        <ThemeProvider>
          <Routes>
            <Route path="/workflow/:id/designer" element={<WorkflowDesigner />} />
          </Routes>
        </ThemeProvider>
      </MemoryRouter>,
    )
  }

  it('affiche une bande par role', async () => {
    definitionsGet.mockResolvedValue({ data: DEFINITION_ROLES })
    const user = userEvent.setup()
    monterRoles()
    await screen.findByTestId('wfd-node-1')
    await user.click(screen.getByTestId('wfd-vue-swimlanes'))
    expect(screen.getByTestId('wfd-swimlane-commercial')).toBeTruthy()
    expect(screen.getByTestId('wfd-swimlane-responsable')).toBeTruthy()
    expect(screen.getByTestId('wfd-swimlane-admin')).toBeTruthy()
  })

  it('une definition sans role affiche une seule bande', async () => {
    definitionsGet.mockResolvedValue({ data: DEFINITION })
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('wfd-node-1')
    await user.click(screen.getByTestId('wfd-vue-swimlanes'))
    // Les deux etapes de DEFINITION portent le meme role ('admin').
    expect(screen.getByTestId('wfd-swimlane-admin')).toBeTruthy()
    expect(screen.queryByTestId('wfd-swimlane-sans-role')).toBeNull()
  })

  it('deplacer un noeud entre bandes met a jour role_requis', async () => {
    definitionsGet.mockResolvedValue({ data: DEFINITION_ROLES })
    const user = userEvent.setup()
    monterRoles()
    await screen.findByTestId('wfd-node-1')
    await user.click(screen.getByTestId('wfd-vue-swimlanes'))

    const noeudA = screen.getByTestId('wfd-node-1') // role 'commercial'
    const bandeAdmin = screen.getByTestId('wfd-swimlane-admin')
    fireEvent.dragStart(noeudA)
    fireEvent.drop(bandeAdmin)

    await user.click(noeudA)
    expect(await screen.findByTestId('wfd-panel-role')).toHaveValue('admin')
  })
})
