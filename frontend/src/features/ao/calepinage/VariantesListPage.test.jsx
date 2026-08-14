import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* ============================================================================
   PV59 — VariantesListPage : la VRAIE liste des calepinages (`VarianteCalepinage`,
   AOF28 — la seule ressource persistée qui existe ; il n'y a pas de modèle
   « Calepinage »). Même patron de test que `AffairesList.test.jsx` : `aoApi`
   mocké au niveau module (pas `axios`), `useNavigate` mocké,
   `<ThemeProvider>` obligatoire (DataTable lit la densité via `useTheme()`).
   ========================================================================== */

const mocks = vi.hoisted(() => ({ list: vi.fn(), navigate: vi.fn() }))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../../api/aoApi', () => ({
  default: { variantes: { list: mocks.list } },
}))

import VariantesListPage from './VariantesListPage'

const renderScreen = () => render(
  <MemoryRouter><ThemeProvider><VariantesListPage /></ThemeProvider></MemoryRouter>,
)

const ROWS = [
  {
    id: 11, toiture: 7, appel_offre: 3, role: 'RETENUE', role_display: 'Variante retenue',
    nom: 'Bâtiment A — segment 2', statut: 'publiable', statut_display: 'Publiable',
    total_modules: 314, puissance_kwc: 196, est_retenue: true,
    raisons_de_non_publiabilite: [],
  },
  {
    id: 12, toiture: 8, appel_offre: 3, role: 'ALTERNATIVE', role_display: 'Alternative comparée',
    nom: 'Plan imposé du 12/08', statut: 'brouillon', statut_display: 'Brouillon',
    total_modules: 300, puissance_kwc: 187, est_retenue: false,
    raisons_de_non_publiabilite: ['Marge tronçon sous le seuil (1,2 cm < 2 cm)'],
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: ROWS })
})

// `DataTable` rend le tableau bureau ET les cartes mobiles simultanément
// (repli purement CSS, sans effet sous jsdom) : chaque libellé existe donc EN
// DOUBLE — mêmes précautions que `AffairesList.test.jsx`.
async function findRow(texte) {
  const cells = await screen.findAllByText(texte)
  const row = cells.map((c) => c.closest('tr')).find(Boolean)
  expect(row, `ligne « ${texte} » absente du tableau bureau`).toBeTruthy()
  return row
}

describe('VariantesListPage', () => {
  it('charge via aoApi.variantes.list() (useResource, jamais un axios.get direct)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(await findRow('Bâtiment A — segment 2')).toBeInTheDocument()
    expect(await findRow('Plan imposé du 12/08')).toBeInTheDocument()
  })

  it('affiche toiture/affaire, rôle, statut (statut_display), modules et kWc de chaque variante', async () => {
    renderScreen()
    const row1 = await findRow('Bâtiment A — segment 2')
    expect(within(row1).getByText('Toiture #7 · Affaire #3')).toBeInTheDocument()
    expect(within(row1).getByText('Variante retenue')).toBeInTheDocument()
    expect(within(row1).getAllByText('Publiable')).toHaveLength(1) // statut_display SEUL (colonne « Statut »)
    expect(within(row1).getByText('314')).toBeInTheDocument()
    expect(within(row1).getByText('196 kWc')).toBeInTheDocument()
  })

  it('la variante RETENUE porte l’étoile, l’autre non', async () => {
    renderScreen()
    const row1 = await findRow('Bâtiment A — segment 2')
    const row2 = await findRow('Plan imposé du 12/08')
    expect(within(row1).getByLabelText('Variante retenue')).toBeInTheDocument()
    expect(within(row2).getByLabelText('Variante non retenue')).toBeInTheDocument()
  })

  it('sans raison de non-publiabilité : badge « Aucune réserve » ; sinon, un détail dépliable NOMMÉ', async () => {
    renderScreen()
    const row1 = await findRow('Bâtiment A — segment 2')
    expect(within(row1).getByText('Aucune réserve')).toBeInTheDocument()

    const row2 = await findRow('Plan imposé du 12/08')
    expect(within(row2).queryByText('Aucune réserve')).toBeNull()
    const detail = within(row2).getByText('1 raison')
    expect(detail.closest('details')).not.toBeNull()
    fireEvent.click(detail)
    expect(within(row2).getByText('Marge tronçon sous le seuil (1,2 cm < 2 cm)')).toBeInTheDocument()
  })

  it('cliquer une ligne navigue vers l’AFFAIRE (/ao/affaires/<appel_offre>), pas la toiture', async () => {
    renderScreen()
    fireEvent.click(await findRow('Bâtiment A — segment 2'))
    expect(mocks.navigate).toHaveBeenCalledWith('/ao/affaires/3')
  })

  it('le filtre RÔLE (Segmented) relance aoApi.variantes.list() avec `role`', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({}))
    await userEvent.click(screen.getByRole('radio', { name: 'Retenue' }))
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ role: 'RETENUE' }))
  })

  it('le filtre STATUT (Segmented) relance aoApi.variantes.list() avec `statut`', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({}))
    await userEvent.click(screen.getByRole('radio', { name: 'Publiable' }))
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ statut: 'publiable' }))
  })

  it('les filtres identifiant (affaire/toiture) relancent la liste APRÈS anti-rebond', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({}))
    await userEvent.type(screen.getByLabelText('Filtrer par identifiant d’affaire'), '3')
    await waitFor(
      () => expect(mocks.list).toHaveBeenCalledWith({ appel_offre: '3' }),
      { timeout: 2000 },
    )
  })
})
