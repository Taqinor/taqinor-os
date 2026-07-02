// QP1 — Filtre du picker produit par type de slot (via classifyProduct). On
// vérifie que `typeFilter` restreint bien la liste affichée au type attendu
// (ex. seuls les onduleurs hybrides pour une ligne « Onduleur hybride ») et
// que sans typeFilter (ligne non typée) la liste reste complète.

import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ProduitPicker from './ProduitPicker'

const PRODUITS = [
  { id: 1, nom: 'Onduleur Hybride Deye 6kW', prix_vente: 8000, tva: 20, is_archived: false },
  { id: 2, nom: 'Onduleur Réseau Huawei 5kW', prix_vente: 6000, tva: 20, is_archived: false },
  { id: 3, nom: 'Panneau Solaire 550W', prix_vente: 900, tva: 10, is_archived: false },
  { id: 4, nom: 'Batterie Lithium 5kWh', prix_vente: 15000, tva: 20, is_archived: false },
]

function openPicker() {
  fireEvent.click(screen.getByRole('button'))
}

describe('ProduitPicker typeFilter (QP1)', () => {
  it('sans typeFilter, affiche tous les produits', () => {
    render(<ProduitPicker produits={PRODUITS} value="" onChange={() => {}} />)
    openPicker()
    expect(screen.getByText('Onduleur Hybride Deye 6kW')).toBeInTheDocument()
    expect(screen.getByText('Onduleur Réseau Huawei 5kW')).toBeInTheDocument()
    expect(screen.getByText('Panneau Solaire 550W')).toBeInTheDocument()
    expect(screen.getByText('Batterie Lithium 5kWh')).toBeInTheDocument()
  })

  it('avec typeFilter="onduleur_hybride", ne montre que les onduleurs hybrides', () => {
    render(<ProduitPicker produits={PRODUITS} value="" onChange={() => {}} typeFilter="onduleur_hybride" />)
    openPicker()
    expect(screen.getByText('Onduleur Hybride Deye 6kW')).toBeInTheDocument()
    expect(screen.queryByText('Onduleur Réseau Huawei 5kW')).not.toBeInTheDocument()
    expect(screen.queryByText('Panneau Solaire 550W')).not.toBeInTheDocument()
    expect(screen.queryByText('Batterie Lithium 5kWh')).not.toBeInTheDocument()
  })

  it('avec typeFilter="panneau", ne montre que les panneaux', () => {
    render(<ProduitPicker produits={PRODUITS} value="" onChange={() => {}} typeFilter="panneau" />)
    openPicker()
    expect(screen.getByText('Panneau Solaire 550W')).toBeInTheDocument()
    expect(screen.queryByText('Onduleur Hybride Deye 6kW')).not.toBeInTheDocument()
  })

  it('avec typeFilter="batterie", ne montre que les batteries', () => {
    render(<ProduitPicker produits={PRODUITS} value="" onChange={() => {}} typeFilter="batterie" />)
    openPicker()
    expect(screen.getByText('Batterie Lithium 5kWh')).toBeInTheDocument()
    expect(screen.queryByText('Onduleur Réseau Huawei 5kW')).not.toBeInTheDocument()
  })
})
