import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider'
import { ConfirmProvider } from '../../providers/ConfirmProvider'
import { confirmerSuppression } from './confirmation.testHelpers.js'

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
  <ThemeProvider><ConfirmProvider><SecuriteIdentitePage /></ConfirmProvider></ThemeProvider>,
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

  it('lit TOUTES les pages des règles IP (51 objets ⇒ 51 lignes)', async () => {
    const tout = Array.from({ length: 51 }, (_, i) => ({ id: i + 1, cidr: `10.0.${i}.0/24`, label: '' }))
    H.ipList.mockImplementation(({ page = 1 } = {}) => Promise.resolve({ data: {
      count: 51,
      next: page === 1 ? 'http://x/?page=2' : null,
      results: page === 1 ? tout.slice(0, 50) : tout.slice(50),
    } }))
    renderPage()
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Supprimer la règle' })).toHaveLength(51))
    H.ipList.mockImplementation(() => Promise.resolve({ data: [] }))
  })

  it('lit la posture de sécurité', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('tab', { name: /Posture/ }))
    await waitFor(() => expect(H.posture).toHaveBeenCalled())
    expect(await screen.findByText('72')).toBeInTheDocument()
    expect(screen.getByText('1 compte dormant')).toBeInTheDocument()
  })

  it('AERR57 — lecture du profil rejetée : aucun enregistrement possible', async () => {
    const user = userEvent.setup()
    H.getProfile.mockImplementationOnce(() => Promise.reject(new Error('panne')))
    renderPage()
    await user.click(screen.getByRole('tab', { name: /Bannière/ }))
    expect(await screen.findByText(/n.ont pas pu être lus/)).toBeInTheDocument()
    const enregistrer = screen.getByRole('button', { name: 'Enregistrer' })
    expect(enregistrer).toBeDisabled()
    fireEvent.click(enregistrer)
    expect(H.updateProfile).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Réessayer' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeEnabled())
    expect(screen.getByLabelText(/Seuil de verrouillage/)).toHaveValue(5)
  })

  it('AERR64 — Supprimer puis Annuler : aucune suppression ; confirmation nommée', async () => {
    H.ipList.mockImplementation(() => Promise.resolve({ data: [{ id: 4, cidr: '10.0.0.0/24', label: 'Bureau' }] }))
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Supprimer la règle' }))
    expect(await screen.findByText(/Supprimer la plage « 10\.0\.0\.0\/24 »/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByText(/Supprimer la plage/)).toBeNull())
    expect(H.ipRemove).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Supprimer la règle' }))
    await confirmerSuppression(user)
    await waitFor(() => expect(H.ipRemove).toHaveBeenCalledWith(4))
    H.ipList.mockImplementation(() => Promise.resolve({ data: [] }))
  })
})
