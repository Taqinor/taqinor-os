import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'
import iaReducer from '../../store/iaSlice'
import { CONTRATS_CARTES } from '../contrats'
import CARTES_STOCK from './CartesStock'

/* Nouveau fichier car : composant neuf, aucun module de test existant. */

const ex = (variante) => exempleContrat(...CONTRATS_CARTES.niveau_stock, variante)
const monter = (donnees) => {
  const Carte = CARTES_STOCK.niveau_stock
  const magasin = configureStore({ reducer: { ia: iaReducer } })
  return render(<Provider store={magasin}><MemoryRouter><Carte carte={{ donnees }} /></MemoryRouter></Provider>)
}

describe('carte niveau_stock', () => {
  it('exemple : le disponible d’abord, l’alerte sous seuil, la suggestion, aucun prix', () => {
    const { container } = monter(ex())
    expect(screen.getByText('Niveaux de stock (2)')).toBeInTheDocument()
    expect(screen.getByText('Panneau Canadian Solar 710W')).toBeInTheDocument()
    expect(screen.getByText(/Disponible : 880 u/)).toBeInTheDocument()
    expect(screen.getByText(/Sous le seuil d’alerte \(4 u\)/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Réapprovisionner/)).toBeInTheDocument()
    expect(screen.getByText('Quantité suggérée')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Voir les mouvements' })).toHaveLength(2)
    // Aucun prix : ni « MAD », ni tiret, ni ligne de valeur de stock.
    expect(container.textContent).not.toMatch(/MAD|prix|valeur/i)
  })

  it('un produit à zéro réserve reste lisible : pas de ligne « Réservé » vide', () => {
    monter(ex())
    expect(screen.getAllByText('Réservé aux chantiers')).toHaveLength(1)
  })

  it('aucun produit : un message', () => {
    monter(ex('exemple_vide'))
    expect(screen.getByText(/Aucun produit ne correspond/)).toBeInTheDocument()
  })
})
