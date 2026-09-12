import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import gestionProjetApi from '../../../api/gestionProjetApi'
import PortefeuillePage from './PortefeuillePage'

/* AUDV16 (PROJ36/PROJ26) — écran Portefeuille : `tableau_portefeuille` était
   déjà câblé backend + client API mais aucun écran ne l'appelait.

   CHT13 — le revenu n'est plus câblé à 0 : la marge réelle affichée ici
   reflète désormais le CA FACTURÉ réel. Contrat partagé (PACT10) : la charge
   utile vient du MÊME fichier que le backend affirme (`apps/gestion_projet/
   contract_samples/tableau_portefeuille.json`) — jamais un objet inventé à
   la main (l'ancien mock local divergeait déjà du fil réseau réel : il
   portait `note_satisfaction`/`politique_facturation` par ligne, des clés
   que l'action `portefeuille` n'a jamais sérialisées). */

// PACT10 — l'exemple committé, lu depuis le fichier réel (jamais recopié).
const PORTEFEUILLE = exempleContrat('gestion_projet', 'tableau_portefeuille')

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getPortefeuille: vi.fn(),
  },
}))

beforeEach(() => {
  gestionProjetApi.getPortefeuille.mockResolvedValue({ data: PORTEFEUILLE })
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('PortefeuillePage', () => {
  it('charge et affiche le tableau de bord portefeuille (lignes + totaux)', async () => {
    withProviders(<PortefeuillePage />)

    await waitFor(() => expect(gestionProjetApi.getPortefeuille).toHaveBeenCalled())
    // DataTable rend un double affichage (table desktop + cartes mobile) :
    // au moins une occurrence de chaque ligne, jamais une occurrence unique.
    await waitFor(() => expect(screen.getAllByText('Villa Fès').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Riad Marrakech').length).toBeGreaterThan(0)

    // Totaux portefeuille (bandeau KPI).
    const totalRetards = screen.getByText('Retards cumulés').closest('div')
    expect(within(totalRetards).getByText('2')).toBeInTheDocument()
  })

  it('affiche la marge réelle avec les nouveaux chiffres (revenu réel CHT13)', async () => {
    withProviders(<PortefeuillePage />)
    await waitFor(() => expect(gestionProjetApi.getPortefeuille).toHaveBeenCalled())
    await waitFor(() => expect(screen.getAllByText('Villa Fès').length).toBeGreaterThan(0))

    // Villa Fès (P-1) a désormais une marge réelle POSITIVE (2500.00, exemple
    // du contrat CHT13) — avant CHT13 le revenu était TOUJOURS 0 donc la
    // marge réelle ne pouvait jamais être positive. `\s` tolère l'espace fine
    // insécable d'Intl.NumberFormat('fr-FR').
    const margePositive = screen.getAllByText((_content, node) => (
      node.tagName === 'SPAN' && /^2\s*500,00\s*MAD$/.test(node.textContent)))
    expect(margePositive.length).toBeGreaterThan(0)
    expect(margePositive[0]).not.toHaveClass('text-destructive')

    // Riad Marrakech (P-2) reste négative (-1500.00) : les deux cas cohabitent.
    const margeNegative = screen.getAllByText((_content, node) => (
      node.tagName === 'SPAN' && /^-1\s*500,00\s*MAD$/.test(node.textContent)))
    expect(margeNegative.length).toBeGreaterThan(0)
    expect(margeNegative[0]).toHaveClass('text-destructive')

    // Bandeau « Marge réelle cumulée » : 1000.00 (somme 2500 − 1500), donc
    // non-négatif — avant CHT13 le total ne pouvait jamais être positif.
    const bandeau = screen.getByText('Marge réelle cumulée').closest('div')
    expect(within(bandeau).getByText((_content, node) => (
      /^1\s*000,00\s*MAD$/.test(node.textContent)))).toBeInTheDocument()
  })

  it('re-filtre par statut', async () => {
    const user = userEvent.setup()
    withProviders(<PortefeuillePage />)
    await waitFor(() => expect(gestionProjetApi.getPortefeuille).toHaveBeenCalledTimes(1))

    const planifie = screen.getByRole('radio', { name: /Planifié/i })
    await user.click(planifie)

    await waitFor(() => expect(gestionProjetApi.getPortefeuille).toHaveBeenCalledTimes(2))
    expect(gestionProjetApi.getPortefeuille).toHaveBeenLastCalledWith({ statut: 'planifie' })
  })
})
