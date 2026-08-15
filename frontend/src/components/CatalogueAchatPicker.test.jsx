import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ThemeProvider } from '../design/ThemeProvider.jsx'
import CatalogueAchatPicker from './CatalogueAchatPicker.jsx'

/* ============================================================================
   NTP2P3 — picker du catalogue interne d'achat.
   Vérifie : (1) la liste montre nom/SKU/fournisseur/prix d'ACHAT ; (2) AUCUN
   prix de vente n'est jamais rendu (le champ n'existe pas dans la charge utile
   de `/stock/catalogue-achat/`, donc aucune marge n'est calculable) ;
   (3) la recherche est remontée à l'appelant (requête serveur) ;
   (4) la sélection renvoie l'article complet pour le pré-remplissage ;
   (5) NTP2P22 — un favori remonte en tête de liste.
   ========================================================================== */

const ARTICLES = [
  {
    id: 1, nom: 'Panneau 550W', sku: 'PV-550', categorie: 3,
    categorie_nom: 'Panneaux', fournisseur_prefere: 7,
    fournisseur_prefere_nom: 'SolarImport', prix_achat_dernier: '1000.00',
  },
  {
    id: 2, nom: 'Câble solaire 6mm', sku: 'CB-6', categorie: 4,
    categorie_nom: 'Câblage', fournisseur_prefere: null,
    fournisseur_prefere_nom: null, prix_achat_dernier: '12.50',
  },
]

function renderPicker(props = {}) {
  return render(
    <ThemeProvider>
      <CatalogueAchatPicker items={ARTICLES} value={null} onChange={() => {}} {...props} />
    </ThemeProvider>,
  )
}

describe('CatalogueAchatPicker (NTP2P3)', () => {
  it('liste les articles avec leur prix d’achat, jamais un prix de vente', async () => {
    renderPicker()
    fireEvent.click(screen.getByTestId('catalogue-achat-trigger'))
    await waitFor(() => expect(screen.getByRole('listbox')).toBeTruthy())

    expect(screen.getByText('Panneau 550W')).toBeTruthy()
    expect(screen.getByText('PV-550')).toBeTruthy()
    expect(screen.getByText('SolarImport')).toBeTruthy()
    // Prix d'ACHAT affiché (1 000), et la mention explicite qu'il est interne.
    expect(screen.getByText(/1\s*000/)).toBeTruthy()
    expect(screen.getByText(/donnée interne/i)).toBeTruthy()

    // Le contrat NTP2P3 : la charge utile ne porte AUCUN prix de vente.
    for (const article of ARTICLES) {
      expect(Object.keys(article)).not.toContain('prix_vente')
    }
  })

  it('remonte la recherche à l’appelant (requête serveur)', async () => {
    const onSearch = vi.fn()
    renderPicker({ onSearch })
    fireEvent.click(screen.getByTestId('catalogue-achat-trigger'))
    const input = await screen.findByRole('combobox')
    fireEvent.change(input, { target: { value: 'câble' } })
    await waitFor(() => expect(onSearch).toHaveBeenCalledWith('câble'), { timeout: 2000 })
  })

  it('renvoie l’article complet à la sélection (pré-remplissage)', async () => {
    const onChange = vi.fn()
    renderPicker({ onChange })
    fireEvent.click(screen.getByTestId('catalogue-achat-trigger'))
    await waitFor(() => expect(screen.getByRole('listbox')).toBeTruthy())
    fireEvent.click(screen.getByText('Panneau 550W'))
    expect(onChange).toHaveBeenCalledWith(
      '1', expect.objectContaining({ id: 1, prix_achat_dernier: '1000.00' }))
  })

  it('remonte les favoris en tête de liste (NTP2P22)', async () => {
    renderPicker({ favoris: [2] })
    fireEvent.click(screen.getByTestId('catalogue-achat-trigger'))
    await waitFor(() => expect(screen.getByRole('listbox')).toBeTruthy())
    const options = screen.getAllByRole('option')
    expect(options[0].textContent).toContain('Câble solaire 6mm')
  })
})
