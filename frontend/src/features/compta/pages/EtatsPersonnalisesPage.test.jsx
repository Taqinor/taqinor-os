import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* WIR280/WIR279 (XACC19) — États financiers PARAMÉTRABLES : le modèle, la
   validation de formule et l'évaluation existaient côté services sans AUCUN
   écran. La charge utile de `evaluer/` reprend EXACTEMENT le contrat committé
   (`apps/compta/contract_samples/etat_personnalise_evaluer.json`, WIR279) —
   jamais inventée : une ligne « titre » porte un `valeurs` VIDE (jamais des
   zéros).

   `ListShell`/`DataTable` rend deux fois la même ligne (repli desktop +
   cartes mobile) : les requêtes sur la liste sont scopées à
   `[data-dt-table]` (même patron que `EmpruntsPage.test.jsx`). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  remove: vi.fn(),
  evaluer: vi.fn(),
  budgets: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    etatsPersonnalises: { list: mocks.list, create: mocks.create, remove: mocks.remove, evaluer: mocks.evaluer },
    budgets: { list: mocks.budgets },
  },
}))

import EtatsPersonnalisesPage from './EtatsPersonnalisesPage.jsx'

// Contrat committé WIR279 (apps/compta/contract_samples/etat_personnalise_evaluer.json).
const EVALUATION = {
  etat: 5,
  libelle: 'Compte de résultat simplifié',
  colonnes: [
    { id: 21, libelle: '2026', type_colonne: 'periode' },
    { id: 22, libelle: '2025', type_colonne: 'comparatif_n1' },
  ],
  lignes: [
    { id: 41, libelle: 'PRODUITS', type_ligne: 'titre', valeurs: {} },
    { id: 42, libelle: "Chiffre d'affaires", type_ligne: 'total', valeurs: { 21: '1250000.00', 22: '980000.00' } },
    { id: 43, libelle: "Résultat d'exploitation", type_ligne: 'total', valeurs: { 21: '312500.00', 22: '-44000.00' } },
  ],
}

const ETAT = {
  id: 5, libelle: 'Compte de résultat simplifié', description: 'CPC simplifié',
  lignes: [
    { id: 41, ordre: 0, libelle: 'PRODUITS', type_ligne: 'titre', formule: '' },
    { id: 42, ordre: 1, libelle: "Chiffre d'affaires", type_ligne: 'total', formule: '+70' },
  ],
  colonnes: [
    { id: 21, ordre: 0, libelle: '2026', type_colonne: 'periode', date_debut: '2026-01-01', date_fin: '2026-12-31', budget: null },
  ],
  created_by: 1, date_creation: '2026-01-01T09:00:00Z',
}

function mount() {
  return render(
    <MemoryRouter>
      <ThemeProvider><EtatsPersonnalisesPage /></ThemeProvider>
    </MemoryRouter>,
  )
}

async function tableDesktop(container) {
  await waitFor(() => expect(container.querySelector('[data-dt-table]')).toBeTruthy())
  return within(container.querySelector('[data-dt-table]'))
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [ETAT] })
  mocks.budgets.mockResolvedValue({ data: [] })
  mocks.create.mockResolvedValue({ data: { id: 6 } })
  mocks.remove.mockResolvedValue({ data: {} })
  mocks.evaluer.mockResolvedValue({ data: EVALUATION })
})

describe('EtatsPersonnalisesPage — liste (WIR280)', () => {
  it('affiche la liste des états personnalisés', async () => {
    const { container } = mount()
    const table = await tableDesktop(container)
    expect(await table.findByText('Compte de résultat simplifié')).toBeInTheDocument()
  })
})

describe('EtatsPersonnalisesPage — constructeur lignes/formules (WIR280/WIR279)', () => {
  it('crée un état avec une ligne à formule et une colonne période', async () => {
    const user = userEvent.setup()
    const { container } = mount()
    await tableDesktop(container)

    await user.click(screen.getByRole('button', { name: 'Nouvel état' }))
    // Le libellé de l'état est `required` (astérisque aria-hidden posé par
    // `Label` — inclus dans le textContent brut, pas dans le nom accessible) :
    // requête en préfixe plutôt qu'une égalité exacte.
    await user.type(screen.getByLabelText(/^Libellé/, { selector: '#etat-libelle' }), 'Bilan simplifié')
    await user.type(screen.getByLabelText('Libellé', { selector: '#ligne-libelle-0' }), 'ACTIF')
    await user.selectOptions(screen.getByLabelText('Type', { selector: '#ligne-type-0' }), 'total')
    await user.type(screen.getByLabelText(/Formule/), '+21,+22')
    await user.type(screen.getByLabelText('Libellé', { selector: '#colonne-libelle-0' }), '2027')

    await user.click(screen.getByRole('button', { name: "Enregistrer l'état" }))

    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({
      libelle: 'Bilan simplifié',
      description: '',
      lignes: [{ ordre: 0, libelle: 'ACTIF', type_ligne: 'total', formule: '+21,+22' }],
      colonnes: [{ ordre: 0, libelle: '2027', type_colonne: 'periode', date_debut: null, date_fin: null, budget: null }],
    }))
  })
})

describe('EtatsPersonnalisesPage — rendu évalué + export (WIR280/WIR279)', () => {
  it('évalue un état et rend EXACTEMENT le contrat committé (titre sans valeur)', async () => {
    const user = userEvent.setup()
    const { container } = mount()
    const table = await tableDesktop(container)
    await table.findByText('Compte de résultat simplifié')

    await user.click(table.getByRole('button', { name: 'Évaluer' }))

    await waitFor(() => expect(mocks.evaluer).toHaveBeenCalledWith(5))
    expect(await screen.findByText("Chiffre d'affaires")).toBeInTheDocument()
    // Colonnes dynamiques = celles renvoyées par le serveur.
    expect(screen.getByRole('columnheader', { name: '2026' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '2025' })).toBeInTheDocument()
    // Montants EXACTS du contrat (1 250 000,00 / -44 000,00).
    expect(screen.getByText(/250\s?000,00/)).toBeInTheDocument()
    expect(screen.getByText(/-44\s?000,00/)).toBeInTheDocument()
    // La ligne « titre » (PRODUITS) n'affiche AUCUNE valeur — jamais un 0 inventé.
    const ligneTitre = screen.getByText('PRODUITS').closest('tr')
    within(ligneTitre).getAllByRole('cell').slice(1).forEach((cell) => {
      expect(cell).toHaveTextContent('')
    })
  })

  it('exporte le rendu évalué en CSV (ComptaTable)', async () => {
    const user = userEvent.setup()
    const { container } = mount()
    const table = await tableDesktop(container)
    await table.findByText('Compte de résultat simplifié')

    await user.click(table.getByRole('button', { name: 'Évaluer' }))
    await screen.findByText("Chiffre d'affaires")

    expect(screen.getByRole('button', { name: 'Exporter CSV' })).toBeInTheDocument()
  })
})

describe('EtatsPersonnalisesPage — suppression (WIR280)', () => {
  it('supprime un état', async () => {
    const user = userEvent.setup()
    const { container } = mount()
    const table = await tableDesktop(container)
    await table.findByText('Compte de résultat simplifié')

    await user.click(table.getByRole('button', { name: 'Supprimer' }))

    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith(5))
  })
})
