import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  verifier: vi.fn(),
  enregistrementsAttendus: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    domainesEnvoi: {
      list: mocks.list, create: mocks.create, verifier: mocks.verifier,
      enregistrementsAttendus: mocks.enregistrementsAttendus,
    },
  },
}))

import DomaineEnvoi from './DomaineEnvoi'

const renderScreen = () => render(<MemoryRouter><DomaineEnvoi /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({
    data: [{
      id: 1, domaine: 'taqinor.ma', spf_verifie: true, dkim_verifie: false,
      dmarc_verifie: false, authentifie: false, derniere_verification_le: '2026-07-01T00:00:00Z',
    }],
  })
})

describe('DomaineEnvoi', () => {
  it("affiche l'état SPF/DKIM/DMARC réel du domaine", async () => {
    renderScreen()
    expect(await screen.findByText('taqinor.ma')).toBeInTheDocument()
    const row = screen.getByTestId('domaine-row')
    expect(row).toHaveTextContent('✓') // SPF vérifié
    expect(row).toHaveTextContent('✗') // DKIM non vérifié
  })

  it('« Revérifier » relance la vérification puis recharge', async () => {
    mocks.verifier.mockResolvedValue({ data: {} })
    renderScreen()
    await screen.findByText('taqinor.ma')
    fireEvent.click(screen.getByTestId('domaine-reverifier'))
    await waitFor(() => expect(mocks.verifier).toHaveBeenCalledWith(1))
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
  })

  it('« Enregistrements attendus » affiche les 3 enregistrements DNS', async () => {
    mocks.enregistrementsAttendus.mockResolvedValue({
      data: {
        spf: { type: 'TXT', hote: 'taqinor.ma', valeur_attendue: 'v=spf1 include:spf.brevo.com ~all' },
        dkim: { type: 'CNAME', hote: 'mail._domainkey.taqinor.ma', valeur_attendue: 'mail._domainkey.taqinor.ma.brevo.com' },
        dmarc: { type: 'TXT', hote: '_dmarc.taqinor.ma', valeur_attendue: 'v=DMARC1; p=none;' },
      },
    })
    renderScreen()
    await screen.findByText('taqinor.ma')
    fireEvent.click(screen.getByTestId('domaine-attendus'))
    const bloc = await screen.findByTestId('domaine-attendus-1')
    expect(bloc).toHaveTextContent('SPF')
    expect(bloc).toHaveTextContent('DKIM')
    expect(bloc).toHaveTextContent('DMARC')
  })

  it('un lien mène vers les supports offline', async () => {
    renderScreen()
    await screen.findByText('taqinor.ma')
    fireEvent.click(screen.getByTestId('voir-supports-offline'))
    expect(mocks.navigate).toHaveBeenCalledWith('/marketing/supports-offline')
  })
})
