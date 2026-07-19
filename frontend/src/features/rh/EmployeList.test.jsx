import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import EmployeList from './EmployeList.jsx'

/* WIR33 — Liste des employés : le bouton « Nouvel employé » ouvre le dialogue
   de création câblé sur `rhApi.createEmploye` (jusqu'ici défini sans
   appelant). Smoke : le module ne plante jamais au montage. */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getEmployes: vi.fn(empty),
      getComptesActifsSortis: vi.fn(empty),
      getDepartements: vi.fn(empty),
      createEmploye: vi.fn(),
      deleteEmploye: vi.fn(),
    },
  }
})

function renderListe() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <EmployeList />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('EmployeList — création manuelle (WIR33)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('affiche le bouton « Nouvel employé »', async () => {
    renderListe()
    expect(await screen.findByRole('button', { name: /Nouvel employé/ })).toBeInTheDocument()
  })

  it('ouvre le dialogue et crée le dossier via rhApi.createEmploye', async () => {
    rhApi.createEmploye.mockResolvedValueOnce({ data: { id: 42 } })
    renderListe()

    fireEvent.click(await screen.findByRole('button', { name: /Nouvel employé/ }))
    expect(screen.getByText('Nouveau dossier employé')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Matricule'), { target: { value: 'M100' } })
    fireEvent.change(screen.getByLabelText('Nom'), { target: { value: 'Idrissi' } })
    fireEvent.change(screen.getByLabelText('Prénom'), { target: { value: 'Karim' } })

    fireEvent.click(screen.getByRole('button', { name: 'Créer le dossier' }))

    await waitFor(() => expect(rhApi.createEmploye).toHaveBeenCalledWith(
      expect.objectContaining({ matricule: 'M100', nom: 'Idrissi', prenom: 'Karim' }),
    ))
  })
})
