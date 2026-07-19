import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider'

/* WIR134 — l'écran Sécurité & Identité monte ses onglets, liste/crée une règle
   IP, révoque un appareil, lit la posture. */

const H = vi.hoisted(() => ({
  npList: vi.fn(() => Promise.resolve({ data: [] })),
  npCreate: vi.fn(() => Promise.resolve({ data: { id: 7 } })),
  ipList: vi.fn(() => Promise.resolve({ data: [] })),
  ipCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  ipRemove: vi.fn(() => Promise.resolve({ data: {} })),
  devList: vi.fn(() => Promise.resolve({ data: [{ id: 3, label: 'iPhone', is_active: true }] })),
  devForget: vi.fn(() => Promise.resolve({ data: {} })),
  posture: vi.fn(() => Promise.resolve({ data: { score: 72, mfa_pct: 90, sso: true, dormant: 1, sod_open: 0, items_faibles: ['1 compte dormant'] } })),
  bgList: vi.fn(() => Promise.resolve({ data: [] })),
  bgGrant: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  saList: vi.fn(() => Promise.resolve({ data: [] })),
  saCreate: vi.fn(() => Promise.resolve({ data: {} })),
  saRemove: vi.fn(() => Promise.resolve({ data: {} })),
  getProfile: vi.fn(() => Promise.resolve({ data: { login_banner_text: '', lockout_max_attempts: 5 } })),
  updateProfile: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/identityApi', () => ({
  default: {
    networkPolicies: { list: H.npList, create: H.npCreate },
    ipRules: { list: H.ipList, create: H.ipCreate, remove: H.ipRemove },
    trustedDevices: { list: H.devList, forget: H.devForget },
    posture: H.posture,
    breakGlass: { list: H.bgList, grant: H.bgGrant },
    serviceAccounts: { list: H.saList, create: H.saCreate, remove: H.saRemove },
  },
}))
vi.mock('../../api/parametresApi', () => ({
  default: { getProfile: H.getProfile, updateProfile: H.updateProfile },
}))

import SecuriteIdentitePage from './SecuriteIdentitePage'

const renderPage = () => render(
  <ThemeProvider><SecuriteIdentitePage /></ThemeProvider>,
)

beforeEach(() => { Object.values(H).forEach((f) => f.mockClear && f.mockClear()) })
afterEach(() => cleanup())

describe('WIR134 SecuriteIdentitePage', () => {
  it('monte l’écran et l’onglet Réseau', async () => {
    renderPage()
    expect(screen.getByText('Sécurité & Identité')).toBeInTheDocument()
    await waitFor(() => expect(H.ipList).toHaveBeenCalled())
    expect(screen.getByText(/Politique réseau/)).toBeInTheDocument()
  })

  it('crée une règle IP (crée la politique au besoin)', async () => {
    renderPage()
    await waitFor(() => expect(H.ipList).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('Plage CIDR'), { target: { value: '10.0.0.0/8' } })
    fireEvent.click(screen.getByText('Ajouter une règle IP'))
    await waitFor(() => expect(H.npCreate).toHaveBeenCalled())
    await waitFor(() => expect(H.ipCreate).toHaveBeenCalledWith(
      expect.objectContaining({ cidr: '10.0.0.0/8', policy: 7 })))
  })

  it('lit la posture de sécurité', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: /Posture/ }))
    await waitFor(() => expect(H.posture).toHaveBeenCalled())
    expect(await screen.findByText('72')).toBeInTheDocument()
    expect(screen.getByText('1 compte dormant')).toBeInTheDocument()
  })
})
