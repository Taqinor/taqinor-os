import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'
import iaReducer from '../../store/iaSlice'
import { CONTRATS_CARTES } from '../contrats'
import CARTES_REPORTING from './CartesReporting'

/* Nouveau fichier car : composant neuf, aucun module de test existant. */

const ex = (variante) => exempleContrat(...CONTRATS_CARTES.chiffres_ca, variante)
const monter = (donnees) => {
  const Carte = CARTES_REPORTING.chiffres_ca
  const magasin = configureStore({ reducer: { ia: iaReducer } })
  return render(<Provider store={magasin}><MemoryRouter><Carte carte={{ donnees }} /></MemoryRouter></Provider>)
}

describe('carte chiffres_ca', () => {
  it('trois chiffres distincts, chacun avec son libellé ET sa définition, jamais additionnés', () => {
    const { container } = monter(ex())
    const sample = ex()
    for (const c of sample.chiffres) {
      expect(screen.getByText(c.libelle)).toBeInTheDocument()
      expect(screen.getByText(c.definition)).toBeInTheDocument()
    }
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
    expect(screen.getByText(/412\s?500,00/)).toBeInTheDocument()
    expect(screen.getByText(/268\s?300,00/)).toBeInTheDocument()
    expect(screen.getByText(/231\s?700,00/)).toBeInTheDocument()
    // Aucune somme (912 500,00) ni rapport (%) entre les trois chiffres.
    expect(container.textContent).not.toMatch(/912\s?500|%/)
  })

  it('la note du serveur et le geste « voir les impayés » sont affichés, avec le lien du rapport', () => {
    monter(ex())
    expect(screen.getByText(/ne jamais dire « le CA » sans dire lequel/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Voir les impayés/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ouvrir le rapport commercial' })).toBeInTheDocument()
  })

  it('sans note ni geste : rien d’autre que les trois chiffres', () => {
    monter({ ...ex(), note: '', a_faire: 'rien' })
    expect(screen.queryByText(/À faire/)).not.toBeInTheDocument()
    expect(screen.queryByText(/sans dire lequel/)).not.toBeInTheDocument()
  })
})
