import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import SanteAgenda from './SanteAgenda'

/* NTSAN4 — smoke test de l'agenda : une colonne par praticien, un rendez-vous
   affiché dans la colonne de son praticien. Appels API mockés (hors réseau). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const annuler = vi.fn(() => Promise.resolve({ data: { penalite_applicable: false } }))
const { creerRdv, apiGet } = vi.hoisted(() => ({
  creerRdv: vi.fn(() => Promise.resolve({ data: { id: 20 } })),
  apiGet: vi.fn(() => Promise.resolve({ data: { creneaux: [] } })),
}))

vi.mock('../../api/santeApi', () => ({
  default: {
    praticiens: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Dr. Alami' }] }),
    },
    rendezvous: {
      list: () => Promise.resolve({
        data: [
          {
            id: 10, praticien: 1, patient: 5, patient_nom: 'Jean Dupont',
            date_heure_debut: '2026-08-03T09:00:00Z', duree_min: 30,
            statut: 'planifie',
          },
        ],
      }),
      update: () => Promise.resolve({ data: {} }),
      annuler: (...args) => annuler(...args),
      create: (...args) => creerRdv(...args),
    },
  },
}))

// PACT115 — `disponibilites/?praticien=&date=` : mocké directement (l'agenda
// l'appelle via `../../api/axios`, pas via `santeApi`).
vi.mock('../../api/axios', () => ({
  default: { get: (...args) => apiGet(...args) },
}))

function renderAgenda() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <SanteAgenda />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('SanteAgenda', () => {
  beforeEach(() => {
    window.confirm = vi.fn(() => true)
    apiGet.mockClear()
    apiGet.mockResolvedValue({ data: { creneaux: [] } })
    creerRdv.mockClear()
    creerRdv.mockResolvedValue({ data: { id: 20 } })
  })

  it('affiche une colonne par praticien avec ses rendez-vous', async () => {
    renderAgenda()

    await waitFor(() => {
      expect(screen.getAllByText('Dr. Alami')[0]).toBeInTheDocument()
    })
    expect(screen.getByText('Jean Dupont')).toBeInTheDocument()
    expect(screen.getByTestId('agenda-colonne-1')).toBeInTheDocument()
    expect(screen.getByTestId('rdv-10')).toBeInTheDocument()
  })

  it('WIR53 — annule un rendez-vous depuis l’agenda (délai/pénalité calculés serveur)', async () => {
    renderAgenda()

    await waitFor(() => {
      expect(screen.getByText('Jean Dupont')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Annuler ce rendez-vous/i }))

    await waitFor(() => {
      expect(annuler).toHaveBeenCalledWith(10, 'clinique')
    })
  })

  it('PACT115 — choisir un praticien recharge les créneaux DEPUIS LE SERVEUR', async () => {
    apiGet.mockResolvedValue({ data: { creneaux: ['2026-08-03T09:00:00Z', '2026-08-03T09:30:00Z'] } })
    renderAgenda()
    await waitFor(() => expect(screen.getAllByText('Dr. Alami')[0]).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Praticien du nouveau rendez-vous'), { target: { value: '1' } })

    await waitFor(() => expect(apiGet).toHaveBeenCalledWith(
      '/sante/disponibilites/',
      { params: { praticien: '1', date: expect.any(String) } },
    ))
    const select = screen.getByLabelText('Créneau disponible')
    await waitFor(() => expect(select).not.toBeDisabled())
    expect(select.querySelectorAll('option').length).toBe(3) // placeholder + 2 créneaux
  })

  it('PACT115 — planifie un rendez-vous sur un créneau serveur (jamais une heure saisie à l’aveugle)', async () => {
    apiGet.mockResolvedValue({ data: { creneaux: ['2026-08-03T10:00:00Z'] } })
    renderAgenda()
    await waitFor(() => expect(screen.getAllByText('Dr. Alami')[0]).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Patient (ID)'), { target: { value: '5' } })
    fireEvent.change(screen.getByLabelText('Praticien du nouveau rendez-vous'), { target: { value: '1' } })
    const select = await screen.findByLabelText('Créneau disponible')
    await waitFor(() => expect(select).not.toBeDisabled())
    fireEvent.change(select, { target: { value: '2026-08-03T10:00:00Z' } })
    fireEvent.click(screen.getByRole('button', { name: 'Planifier' }))

    await waitFor(() => expect(creerRdv).toHaveBeenCalledWith({
      patient: 5, praticien: 1, date_heure_debut: '2026-08-03T10:00:00Z',
    }))
  })

  it('PACT115 — changer la date recharge aussi les créneaux', async () => {
    apiGet.mockResolvedValue({ data: { creneaux: [] } })
    renderAgenda()
    await waitFor(() => expect(screen.getAllByText('Dr. Alami')[0]).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Praticien du nouveau rendez-vous'), { target: { value: '1' } })
    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(1))

    fireEvent.change(screen.getByLabelText("Date de l'agenda"), { target: { value: '2026-08-04' } })
    await waitFor(() => expect(apiGet).toHaveBeenCalledWith(
      '/sante/disponibilites/', { params: { praticien: '1', date: '2026-08-04' } },
    ))
  })
})
