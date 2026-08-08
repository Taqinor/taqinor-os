import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   VAO36 — Acheteurs cibles + relances : le carnet de démarchage (VAO29).
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
}))

vi.mock('../../api/veilleAoApi', () => ({
  default: { acheteursCibles: { list: mocks.list, create: mocks.create } },
}))

import AcheteursCibles from './AcheteursCibles'
import { TYPES_ACHETEUR } from './veilleAoShared'

const renderScreen = () => render(
  <MemoryRouter><ThemeProvider><AcheteursCibles /></ThemeProvider></MemoryRouter>,
)

const ROWS = [
  {
    id: 1, nom: 'Fondation Alpha', type: 'fondation', dernier_contact: '2026-07-01',
    prochaine_relance: '2026-08-01', statut_relation: 'en_discussion', lead_id: 42,
  },
  {
    id: 2, nom: 'Clinique Beta', type: 'clinique', dernier_contact: null,
    prochaine_relance: null, statut_relation: 'nouveau', lead_id: null,
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: ROWS })
})

async function findRow(nom) {
  const cells = await screen.findAllByText(nom)
  const row = cells.map((c) => c.closest('tr')).find(Boolean)
  expect(row, `ligne « ${nom} » absente du tableau bureau`).toBeTruthy()
  return row
}

describe('AcheteursCibles', () => {
  it('charge le carnet via veilleAoApi.acheteursCibles.list()', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(await findRow('Fondation Alpha')).toBeInTheDocument()
    expect(await findRow('Clinique Beta')).toBeInTheDocument()
  })

  it('VAO36 (Done=) — une relance due est visible SANS la chercher (centre d’échéances)', async () => {
    renderScreen()
    const titre = await screen.findByText('Relances dues')
    // Card racine du centre d'échéances : parent du bandeau de titre, qui
    // contient aussi la liste des relances (structure `EcheanceCenter`).
    const centre = titre.closest('div').parentElement
    expect(within(centre).getByText('Fondation Alpha')).toBeInTheDocument()
  })

  it('VAO36 (Done=) — le lien CRM ouvre le lead EXISTANT, jamais une création', async () => {
    renderScreen()
    const row1 = await findRow('Fondation Alpha')
    const lien = within(row1).getByRole('link', { name: 'Voir le lead' })
    expect(lien).toHaveAttribute('href', '/crm/leads/42')
  })

  it('affiche « Aucun lead lié » quand lead_id est absent (aucune création implicite)', async () => {
    renderScreen()
    const row2 = await findRow('Clinique Beta')
    expect(within(row2).getByText('Aucun lead lié')).toBeInTheDocument()
    expect(within(row2).queryByRole('link')).not.toBeInTheDocument()
  })

  it('VAO36 (Done=) — la création rapide part d’un formulaire VIDE, aucune donnée d’organisme inventée', async () => {
    renderScreen()
    await findRow('Fondation Alpha')
    fireEvent.click(screen.getByRole('button', { name: /Nouvel acheteur cible/ }))
    const champNom = await screen.findByLabelText('Nom de l’organisme')
    expect(champNom).toHaveValue('')
  })

  it('la création rapide appelle acheteursCibles.create() et rafraîchit la liste', async () => {
    mocks.create.mockResolvedValue({ data: { id: 3 } })
    renderScreen()
    await findRow('Fondation Alpha')
    fireEvent.click(screen.getByRole('button', { name: /Nouvel acheteur cible/ }))
    fireEvent.change(await screen.findByLabelText('Nom de l’organisme'), { target: { value: 'Groupe Gamma' } })
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Groupe Gamma', type: 'fondation' }),
    ))
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
  })

  it('couvre les 8 catégories d’amorçage de VAO29, jamais un nom d’organisme inventé', () => {
    expect(TYPES_ACHETEUR).toHaveLength(8)
    for (const t of TYPES_ACHETEUR) {
      expect(t.value).not.toMatch(/[A-Z ]/) // slug, jamais un libellé pré-rempli
    }
  })
})
