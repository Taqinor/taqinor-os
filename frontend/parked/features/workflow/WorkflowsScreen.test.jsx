import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT124 — l'ecran des workflows ne savait QUE creer une definition puis
   reinitialiser son formulaire : aucun chemin ne permettait de rouvrir une
   definition deja creee. Ces tests couvrent le chemin qui manquait —
   « cliquer une definition existante ouvre ses etapes en edition (ajout,
   retrait, reordonnancement) et enregistre ».

   Ils vivent dans un fichier dedie pour ne pas alourdir `workflow.test.jsx`
   (logique pure + smoke des deux ecrans), dont les cas restent valides. */

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

const definitionsList = vi.fn()
const definitionsCreate = vi.fn()
const definitionsUpdate = vi.fn()
const definitionsRemove = vi.fn()
const templatesList = vi.fn()
const templatesInstaller = vi.fn()
const instancesListPending = vi.fn()
const instancesDecider = vi.fn()

vi.mock('../../api/coreApi', () => ({
  default: {
    workflowDefinitions: {
      list: (...a) => definitionsList(...a),
      create: (...a) => definitionsCreate(...a),
      update: (...a) => definitionsUpdate(...a),
      remove: (...a) => definitionsRemove(...a),
    },
    workflowTemplates: {
      list: (...a) => templatesList(...a),
      installer: (...a) => templatesInstaller(...a),
    },
    workflowInstances: {
      listPending: (...a) => instancesListPending(...a),
      decider: (...a) => instancesDecider(...a),
    },
  },
}))

import WorkflowsScreen from './WorkflowsScreen'

const DEFINITION = {
  id: 7,
  nom: 'Validation devis',
  description: 'Chaine a deux etapes',
  steps: [
    {
      id: 71, ordre: 1, nom: 'Controle commercial',
      type_approbation: 'manuelle', sla_heures: 4,
      role_requis: 'responsable', escalade_vers: '',
    },
    {
      id: 72, ordre: 2, nom: 'Visa direction',
      type_approbation: 'role', sla_heures: null,
      role_requis: 'admin', escalade_vers: '',
    },
  ],
}

function monter() {
  return render(
    <MemoryRouter>
      <ThemeProvider><WorkflowsScreen /></ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  definitionsList.mockResolvedValue({ data: [DEFINITION] })
  definitionsCreate.mockResolvedValue({ data: { id: 8, nom: 'X', steps: [] } })
  definitionsUpdate.mockResolvedValue({ data: { ...DEFINITION } })
  definitionsRemove.mockResolvedValue({ data: {} })
  templatesList.mockResolvedValue({ data: [] })
  templatesInstaller.mockResolvedValue({ data: {} })
  instancesListPending.mockResolvedValue({ data: { items: [], total: 0 } })
  instancesDecider.mockResolvedValue({ data: {} })
})

describe('WorkflowsScreen — edition d’une definition existante (PACT124)', () => {
  it('ouvre les etapes d’une definition existante dans l’editeur', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('wf-def-created-list')

    await user.click(screen.getByTestId('wf-def-edit-7'))

    // Le formulaire est pre-rempli avec la definition ET ses etapes.
    expect(screen.getByTestId('wf-def-nom').value).toBe('Validation devis')
    const etapes = screen.getAllByPlaceholderText("Nom de l'etape")
    expect(etapes).toHaveLength(2)
    expect(etapes[0].value).toBe('Controle commercial')
    expect(etapes[1].value).toBe('Visa direction')
    // Le bouton d’action change de sens : on modifie, on ne cree plus.
    expect(screen.getByTestId('wf-def-create')).toHaveTextContent(
      'Enregistrer les modifications',
    )
  })

  it('ajoute, retire et reordonne les etapes puis enregistre (Done PACT124)', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('wf-def-created-list')
    await user.click(screen.getByTestId('wf-def-edit-7'))

    // Retire la 2e etape, en ajoute une nouvelle, puis la fait remonter.
    const step1 = screen.getByTestId('wf-def-step-1')
    await user.click(within(step1).getByLabelText('Retirer'))
    await user.click(screen.getByTestId('wf-def-add-step'))
    const etapes = screen.getAllByPlaceholderText("Nom de l'etape")
    await user.type(etapes[1], 'Visa DAF')
    await user.click(
      within(screen.getByTestId('wf-def-step-1')).getByLabelText('Monter'),
    )

    await user.click(screen.getByTestId('wf-def-create'))

    await waitFor(() => expect(definitionsUpdate).toHaveBeenCalledWith(7, {
      nom: 'Validation devis',
      description: 'Chaine a deux etapes',
      steps: [
        {
          ordre: 1, nom: 'Visa DAF', type_approbation: 'manuelle',
          sla_heures: null, role_requis: '', escalade_vers: '',
        },
        {
          ordre: 2, nom: 'Controle commercial', type_approbation: 'manuelle',
          sla_heures: 4, role_requis: 'responsable', escalade_vers: '',
        },
      ],
    }))
  })

  it('un simple renommage n’envoie PAS les etapes (aucune suppression inutile)', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('wf-def-created-list')
    await user.click(screen.getByTestId('wf-def-edit-7'))

    const nom = screen.getByTestId('wf-def-nom')
    await user.clear(nom)
    await user.type(nom, 'Validation devis v2')
    await user.click(screen.getByTestId('wf-def-create'))

    await waitFor(() => expect(definitionsUpdate).toHaveBeenCalledWith(7, {
      nom: 'Validation devis v2',
      description: 'Chaine a deux etapes',
    }))
  })

  it('annuler l’edition rend le formulaire a la creation', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('wf-def-created-list')
    await user.click(screen.getByTestId('wf-def-edit-7'))
    await user.click(screen.getByTestId('wf-def-cancel-edit'))

    expect(screen.getByTestId('wf-def-nom').value).toBe('')
    expect(screen.queryAllByPlaceholderText("Nom de l'etape")).toHaveLength(0)
    expect(screen.getByTestId('wf-def-create')).toHaveTextContent('Creer la definition')
    expect(screen.queryByTestId('wf-def-cancel-edit')).toBeNull()
  })

  it('remonte proprement un refus serveur sans quitter le mode edition', async () => {
    definitionsUpdate.mockRejectedValue({
      response: { data: { detail: 'Modification impossible.' } },
    })
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('wf-def-created-list')
    await user.click(screen.getByTestId('wf-def-edit-7'))
    await user.click(screen.getByTestId('wf-def-create'))

    await waitFor(() => expect(definitionsUpdate).toHaveBeenCalled())
    expect(screen.getByTestId('wf-def-cancel-edit')).toBeTruthy()
  })
})
