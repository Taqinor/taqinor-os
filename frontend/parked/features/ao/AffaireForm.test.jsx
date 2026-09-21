import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* AOF — écran de création d'affaire AO (`/ao/affaires/nouveau`).
   Radix Select ne s'ouvre pas de façon fiable sous jsdom (portail + pointer
   events) — pattern établi (paie/BulletinDetail.test.jsx,
   pages/ventes/ListesPrixPage.test.jsx) : <select> natif à la place, le reste
   de `../../ui` reste réel. */
vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children }) => (
      <select role="combobox" value={value} onChange={(e) => onValueChange(e.target.value)}>
        {children}
      </select>
    ),
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})

const mocks = vi.hoisted(() => ({ create: vi.fn(), navigate: vi.fn() }))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/aoApi', () => ({
  default: { affaires: { create: mocks.create } },
}))

import AffaireForm from './AffaireForm'

const renderScreen = () => render(<MemoryRouter><AffaireForm /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AffaireForm — création (POST /ao/appels-offres/)', () => {
  it('poste vers aoApi.affaires.create() avec le seul `objet` rempli, et JAMAIS `company`', async () => {
    mocks.create.mockResolvedValue({ data: { id: 42 } })
    renderScreen()

    fireEvent.change(screen.getByLabelText(/^Objet/), { target: { value: 'Centrale PV — usine textile' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer l'affaire/ }))

    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1))
    const payload = mocks.create.mock.calls[0][0]
    expect(payload.objet).toBe('Centrale PV — usine textile')
    expect(payload).not.toHaveProperty('company')
    // la référence n'est PAS exigée : soumission possible avec le seul objet.
    expect(payload).not.toHaveProperty('reference')
  })

  it("n'exige jamais la référence — le champ n'est ni requis ni bloquant", async () => {
    mocks.create.mockResolvedValue({ data: { id: 7 } })
    renderScreen()

    const refInput = screen.getByLabelText('Référence interne (facultative)')
    expect(refInput).not.toBeRequired()

    fireEvent.change(screen.getByLabelText(/^Objet/), { target: { value: 'Pompage agricole' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer l'affaire/ }))

    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
  })

  it('succès → navigue vers la fiche de l’affaire créée (id lu dans .data) avec un toast', async () => {
    mocks.create.mockResolvedValue({ data: { id: 99, objet: 'Ombrières parking' } })
    renderScreen()

    fireEvent.change(screen.getByLabelText(/^Objet/), { target: { value: 'Ombrières parking' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer l'affaire/ }))

    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledWith('/ao/affaires/99'))
  })

  it('erreur 400 par champ renvoyée par le serveur : affichée VERBATIM sous le bon champ', async () => {
    mocks.create.mockRejectedValue({
      response: {
        status: 400,
        data: { objet: ['Ce champ ne peut être vide.'], acheteur: ['Trop long (255 caractères maximum).'] },
      },
    })
    renderScreen()

    fireEvent.change(screen.getByLabelText(/^Objet/), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer l'affaire/ }))

    expect(await screen.findByText('Ce champ ne peut être vide.')).toBeInTheDocument()
    expect(await screen.findByText('Trop long (255 caractères maximum).')).toBeInTheDocument()
    expect(mocks.navigate).not.toHaveBeenCalled()
  })

  it('noValidate sur le formulaire + champs numériques en step="any" (jamais un rejet/arrondi client)', () => {
    const { container } = renderScreen()
    const form = container.querySelector('form')
    expect(form.noValidate).toBe(true)

    const numericLabels = [
      "Validité de l'offre (jours)", "Délai d'exécution (jours)",
      'Montant estimé (MAD)', 'Caution provisoire (MAD)',
    ]
    numericLabels.forEach((label) => {
      const input = screen.getByLabelText(label)
      expect(input).toHaveAttribute('type', 'number')
      expect(input).toHaveAttribute('step', 'any')
    })
  })

  it('« Annuler » revient à /ao/affaires', () => {
    renderScreen()
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(mocks.navigate).toHaveBeenCalledWith('/ao/affaires')
  })

  it('le bouton est désactivé pendant l’envoi (pas de double-soumission)', async () => {
    let resolveCreate
    mocks.create.mockReturnValue(new Promise((resolve) => { resolveCreate = resolve }))
    renderScreen()

    fireEvent.change(screen.getByLabelText(/^Objet/), { target: { value: 'Centrale PV' } })
    const btn = screen.getByRole('button', { name: /Créer l'affaire/ })
    fireEvent.click(btn)

    await waitFor(() => expect(screen.getByRole('button', { name: 'Création…' })).toBeDisabled())
    fireEvent.click(screen.getByRole('button', { name: 'Création…' }))
    expect(mocks.create).toHaveBeenCalledTimes(1)

    resolveCreate({ data: { id: 1 } })
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalled())
  })

  it('le bouton de création est désactivé tant que `objet` est vide', () => {
    renderScreen()
    expect(screen.getByRole('button', { name: /Créer l'affaire/ })).toBeDisabled()
  })
})
