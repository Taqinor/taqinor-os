import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { raisonRefusStatut } from '../../features/installations/statuses'

/* ACHT61 — la raison EXACTE d'un refus de statut d'intervention (forme réelle
   DRF `{statut: [raisons], error: {…}}`) s'affiche sous le Select de « Ma
   journée », avec UN seul toast. Le pont axios (toast automatique de tout
   appel échoué qui n'a pas posé `suppressErrorToast`) est émulé par le faux
   `updateIntervention` : il toaste lui-même si l'appelant n'a pas coupé le
   pont — donc retirer `suppressErrorToast` fait apparaître un toast de plus. */

const RAISON = 'Confirmez « Tout est chargé » dans la liste de préparation avant de quitter « À préparer ».'
const CORPS_REEL = { statut: [RAISON], error: { code: 'invalid', message: 'Validation' } }

const { rejected } = vi.hoisted(() => ({
  rejected: () => Promise.reject(new Error('non mocké')),
}))
const toastMock = vi.hoisted(() => ({
  success: vi.fn(), error: vi.fn(), info: vi.fn(), message: vi.fn(),
}))
vi.mock('../../ui/Toaster', () => ({
  toast: toastMock,
  Toaster: () => null,
  default: () => null,
}))
vi.mock('../../api/installationsApi', () => ({
  default: {
    getMaTournee: vi.fn(),
    updateIntervention: vi.fn((id, data, config) => {
      const err = { response: { status: 400, data: CORPS_REEL } }
      if (!config?.suppressErrorToast) toastMock.error('Requête invalide.') // pont axios
      return Promise.reject(err)
    }),
    getInterventions: vi.fn(rejected),
    getPreparation: vi.fn(rejected),
    getPhotos: vi.fn(rejected),
    getSerials: vi.fn(rejected),
    getConsommation: vi.fn(rejected),
    getMemos: vi.fn(rejected),
    getReserves: vi.fn(rejected),
    getSafety: vi.fn(rejected),
    getToolReturn: vi.fn(rejected),
    getCode: vi.fn(rejected),
    compteRenduUrl: vi.fn(() => ''),
  },
}))
vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children, disabled }) => {
      const kids = Array.isArray(children) ? children : [children]
      const label = kids.find((c) => c && c.props && c.props['aria-label'])?.props?.['aria-label']
      return (
        <select role="combobox" aria-label={label} value={value ?? ''} disabled={disabled}
                onChange={(e) => onValueChange(e.target.value)}>
          {children}
        </select>
      )
    },
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})

import installationsApi from '../../api/installationsApi'
import MaJourneePage from './MaJourneePage'

const todayISO = () => {
  const d = new Date()
  return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

beforeEach(() => {
  installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [{
    id: 7, statut: 'a_preparer', client_nom: 'Client Sept',
    type_intervention: 'pose', date_prevue: todayISO(),
  }] } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('raisonRefusStatut — ACHT61', () => {
  it('lit la forme réelle {statut: [raisons]}', () => {
    expect(raisonRefusStatut({ response: { data: CORPS_REEL } })).toBe(RAISON)
  })
  it('repli sur transition_block_reason puis detail, sinon null', () => {
    expect(raisonRefusStatut({ response: { data: { transition_block_reason: 'X' } } })).toBe('X')
    expect(raisonRefusStatut({ response: { data: { detail: 'Y' } } })).toBe('Y')
    expect(raisonRefusStatut({ response: { data: {} } })).toBeNull()
    expect(raisonRefusStatut(new Error('réseau'))).toBeNull()
  })
})

describe('MaJourneePage — ACHT61 raison exacte, un seul toast', () => {
  it('le changement manuel affiche la raison sous le Select sans toast doublé', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)
    await user.click(await screen.findByText('Client Sept'))
    await user.selectOptions(await screen.findByLabelText("Statut de l'intervention"), 'prete')

    const indice = await screen.findByTestId('mj-indice-statut')
    expect(indice).toHaveTextContent(RAISON)
    await waitFor(() => expect(toastMock.error).toHaveBeenCalledTimes(1))
    expect(toastMock.error).toHaveBeenCalledWith(RAISON)
    expect(installationsApi.updateIntervention).toHaveBeenCalledWith(
      7, { statut: 'prete' }, { suppressErrorToast: true })
  })
})
