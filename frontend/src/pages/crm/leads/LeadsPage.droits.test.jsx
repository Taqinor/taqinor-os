import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { render, cleanup, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../../../features/crm/store/crmSlice'
import { PIPELINE_STAGES } from '../../../features/crm/stages'

// ADRG152 — `/crm/leads` ne laisse aux vues que les gestes que la route accepte :
// « Responsable » = `crm_reassign` ; champs, étape, « Perdu », glisser = `crm_modifier`.
const dnd = vi.hoisted(() => ({ onDragEnd: null }))
// Le vrai DndContext, dont on garde le gestionnaire de dépôt pour le rejouer à la main.
vi.mock('@dnd-kit/core', async (original) => {
  const reel = await original()
  const DndContext = (props) => { dnd.onDragEnd = props.onDragEnd; return <reel.DndContext {...props} /> }
  return { ...reel, DndContext }
})
vi.mock('../../../api/crmApi', () => {
  const vide = () => Promise.resolve({ data: [] })
  const defaut = {
    getLeads: vi.fn(() => Promise.resolve({ data: { results: [], next: null } })),
    updateLead: vi.fn(() => Promise.resolve({ data: {} })),
  }
  return { default: new Proxy(defaut, { get: (t, k) => (k in t ? t[k] : (t[k] = vi.fn(vide))) }) }
})

import crmApi from '../../../api/crmApi'
import LeadsPage from './LeadsPage'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

const [PREMIERE, DEUXIEME] = PIPELINE_STAGES
// Lignes tirées de l'exemple de contrat committé (crm/lead_list), champs utiles au test surchargés.
const LISTE = exempleContrat('crm', 'lead_list')
const LEADS = [
  { ...LISTE.results[0], id: 1, nom: 'Alpha', stage: PREMIERE, owner: null, devis: [], stage_since_days: 1 },
  { ...LISTE.results[0], id: 2, nom: 'Bravo', stage: PREMIERE, owner: null, devis: [], stage_since_days: 1 },
]
// Codes des stores `init_roles` (permissions_registre.py) — seuls les codes CRM comptent ici.
const COMMERCIAL = ['crm_voir', 'crm_creer', 'crm_modifier', 'crm_export']
const VIEWER = ['crm_voir']
const DIRECTEUR = [...COMMERCIAL, 'crm_reassign']

function monter(permissions, vue) {
  sessionStorage.setItem('taqinor.leads.view', vue)
  const auth = { role: 'responsable', permissions, user: { id: 5, username: 'moi', is_staff: false } }
  const store = configureStore({
    reducer: { crm: crmReducer, auth: (s = auth) => s },
    middleware: (gdm) => gdm({ serializableCheck: false, immutableCheck: false }),
  })
  return render(
    <Provider store={store}>
      <MemoryRouter><LeadsPage /></MemoryRouter>
    </Provider>,
  )
}

// Le geste « Marquer perdu » d'une carte kanban vit dans son menu « Actions du lead … ».
async function menuPerdu() {
  await userEvent.click((await screen.findAllByRole('button', { name: /^Actions du lead / }))[0])
  return screen.queryByRole('menuitem', { name: /Marquer perdu/ })
}

const pickers = () => screen.findAllByTitle('Assigner un responsable')

beforeEach(() => {
  crmApi.getLeads.mockResolvedValue({ data: { ...LISTE, results: LEADS, next: null } })
})
afterEach(() => { cleanup(); vi.clearAllMocks(); sessionStorage.clear() })

describe('LeadsPage — droits métier (ADRG152)', () => {
  it("Commercial : Responsable inerte ; Viewer : aucun geste d'écriture", async () => {
    for (const vue of ['liste', 'kanban']) {
      monter(COMMERCIAL, vue)
      const lignes = await pickers()
      expect(lignes).toHaveLength(2)
      for (const b of lignes) expect(b).toBeDisabled()
      cleanup()
    }
    // Commercial (`crm_modifier`) : « Marquer perdu » reste offert sur la carte.
    monter(COMMERCIAL, 'kanban')
    expect(await menuPerdu()).not.toBeNull()
    cleanup()
    // Viewer en kanban : « Responsable » inerte, aucun « Perdu », un glisser n'envoie aucun PATCH.
    monter(VIEWER, 'kanban')
    for (const b of await pickers()) expect(b).toBeDisabled()
    expect(await menuPerdu()).toBeNull()
    await waitFor(() => expect(dnd.onDragEnd).toBeTypeOf('function'))
    await act(async () => {
      await dnd.onDragEnd({
        active: { data: { current: { lead: LEADS[0] } } },
        over: { id: DEUXIEME },
      })
    })
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })

  it('Directeur : Responsable actif', async () => {
    for (const vue of ['liste', 'kanban']) {
      monter(DIRECTEUR, vue)
      for (const b of await pickers()) expect(b).not.toBeDisabled()
      cleanup()
    }
  })
})

// Vue liste — champs et étape = cellules `InlineEdit` (bouton « Cliquer pour modifier » quand actives,
// simple texte quand inertes) ; « Marquer perdu » = bouton de chaque ligne non perdue.
describe('LeadsPage — vue liste, droits métier (ADRG152)', () => {
  const editables = () => screen.queryAllByTitle('Cliquer pour modifier')
  const perdus = () => screen.queryAllByRole('button', { name: 'Marquer perdu' })

  it('Viewer : champs et étape inertes, aucun « Marquer perdu » sur les lignes', async () => {
    monter(VIEWER, 'liste')
    for (const b of await pickers()) expect(b).toBeDisabled()
    expect(editables()).toHaveLength(0)
    expect(perdus()).toHaveLength(0)
  })

  it('Commercial et Directeur : champs actifs et « Marquer perdu » sur chaque ligne', async () => {
    for (const permissions of [COMMERCIAL, DIRECTEUR]) {
      monter(permissions, 'liste')
      await pickers()
      expect(editables().length).toBeGreaterThanOrEqual(2)
      expect(perdus()).toHaveLength(2)
      cleanup()
    }
  })
})
