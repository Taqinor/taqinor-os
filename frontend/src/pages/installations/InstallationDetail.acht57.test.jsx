import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ACHT57 — « Mettre à jour » n'envoie que le DIFF des champs modifiés, le
   formulaire se resynchronise après chaque rafraîchissement, et les champs
   gelés sont grisés quand cloture_verrouillee. Test COMPORTEMENTAL : un faux
   serveur en mémoire applique le corps reçu au chantier (il pose les dates à
   l'avancée et refuse le champ gelé d'un chantier clôturé), puis relecture. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const db = {}
const fakeServer = vi.hoisted(() => ({ advance: null }))

vi.mock('./ChantierGateTimeline', () => ({
  default: ({ installationId, onAdvanced }) => (
    <button type="button" onClick={async () => {
      fakeServer.advance(installationId)
      await onAdvanced()
    }}>Avancer (stepper)</button>
  ),
}))

vi.mock('./ChantierChecklist', () => ({ default: () => null }))
vi.mock('../../features/installations/offline/OfflineSyncIndicator', () => ({
  default: () => null,
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getHistorique: () => Promise.resolve({ data: [] }),
    getTypesIntervention: () => Promise.resolve({ data: [] }),
    getInstallation: (id) => Promise.resolve({ data: { ...db[id] } }),
    updateInstallation: (id, body) => {
      const row = db[id]
      if (row.cloture_verrouillee && 'puissance_installee_kwc' in body) {
        return Promise.reject({ response: { data: { puissance_installee_kwc: ['Champ gelé.'] } } })
      }
      Object.assign(row, body)
      return Promise.resolve({ data: { ...row } })
    },
  },
}))
vi.mock('../../api/savApi', () => ({
  default: {
    getEquipements: () => Promise.resolve({ data: [] }),
    getTickets: () => Promise.resolve({ data: [] }),
    getContrats: () => Promise.resolve({ data: [] }),
  },
}))
vi.mock('../../api/crmApi', () => ({
  default: { getAssignableUsers: () => Promise.resolve({ data: [] }) },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: () => Promise.resolve({ data: { lignes: [] } }),
    getReglementaire: () => Promise.resolve({ data: { results: [] } }),
  },
}))

import InstallationDetail from './InstallationDetail'

const store = () => configureStore({
  reducer: { stock: (s = { produits: [] }) => s },
})

function renderDetail(row) {
  return render(
    <Provider store={store()}>
      <MemoryRouter initialEntries={['/chantiers']}>
        <ThemeProvider>
          <InstallationDetail installation={{ ...row }} onClose={() => {}} onSaved={() => {}} />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  db[1] = { id: 1, reference: 'CH-1', statut: 'materiel_commande', annule: false, notes: '' }
  db[2] = { id: 2, reference: 'CH-2', statut: 'en_cours', annule: false, notes: '' }
  db[3] = {
    id: 3, reference: 'CH-3', statut: 'installe', annule: false, notes: '',
    puissance_installee_kwc: 6.5, cloture_verrouillee: true,
  }
  fakeServer.advance = (id) => {
    if (id === 1) Object.assign(db[1], { statut: 'planifie', date_pose_prevue: '2026-10-20' })
    if (id === 2) Object.assign(db[2], { statut: 'installe', date_pose_reelle: '2026-10-09' })
  }
})
afterEach(() => { cleanup() })

describe('InstallationDetail — ACHT57 diff + resynchronisation', () => {
  it.each([
    [1, 'planifie', 'date_pose_prevue', '2026-10-20'],
    [2, 'installe', 'date_pose_reelle', '2026-10-09'],
  ])('chantier %i : avancer au stepper puis modifier Notes ne recule pas le statut', async (id, statut, dateKey, dateVal) => {
    const user = userEvent.setup()
    renderDetail(db[id])
    await user.click(await screen.findByRole('tab', { name: /Jalons/ }))
    await user.click(await screen.findByRole('button', { name: 'Avancer (stepper)' }))
    await user.click(screen.getByRole('tab', { name: /Aperçu/ }))
    await user.type(await screen.findByLabelText('Notes'), 'RAS')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(db[id].notes).toBe('RAS'))
    expect(db[id].statut).toBe(statut)
    expect(db[id][dateKey]).toBe(dateVal)
  })

  it('chantier clôturé : champ gelé grisé et enregistrement réussi', async () => {
    const user = userEvent.setup()
    renderDetail(db[3])
    expect(await screen.findByLabelText('Puissance installée (kWc)')).toBeDisabled()
    await user.type(screen.getByLabelText('Notes'), 'Clos')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(db[3].notes).toBe('Clos'))
    expect(db[3].puissance_installee_kwc).toBe(6.5)
    expect(screen.queryByText(/Champ gelé/)).toBeNull()
  })
})
