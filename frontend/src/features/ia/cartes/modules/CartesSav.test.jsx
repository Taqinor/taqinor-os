import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'
import iaReducer from '../../store/iaSlice'
import { CONTRATS_CARTES } from '../contrats'
import CARTES_SAV from './CartesSav'

/* Nouveau fichier car : composant neuf, aucun module de test existant. */

const ex = (cle, variante) => exempleContrat(...CONTRATS_CARTES[cle], variante)
const monter = (cle, donnees) => {
  const Carte = CARTES_SAV[cle]
  const magasin = configureStore({ reducer: { ia: iaReducer } })
  return render(<Provider store={magasin}><MemoryRouter><Carte carte={{ donnees }} /></MemoryRouter></Provider>)
}

describe('carte parc_client', () => {
  it('exemple : équipements avec garantie, ticket ouvert, téléphone, liens', () => {
    monter('parc_client', ex('parc_client'))
    expect(screen.getByText('Nadia Chraibi')).toBeInTheDocument()
    expect(screen.getByText('+212661234567')).toBeInTheDocument()
    expect(screen.getByText(/Onduleur Deye 8 kW/)).toBeInTheDocument()
    expect(screen.getAllByText(/sous garantie jusqu’au/)).toHaveLength(2)
    expect(screen.getByText(/SAV-2026-11-0031 · Nouveau/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Suivre le ticket ouvert/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ouvrir SAV-2026-11-0031' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ouvrir la fiche client' })).toBeInTheDocument()
  })

  it('sans PII : aucune ligne de téléphone, contrat actif dit, aucun équipement', () => {
    const { container } = monter('parc_client', ex('parc_client', 'exemple_sans_pii'))
    expect(screen.getByText('Nadia Chraibi')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\+212|0[567]\d{8}/)
    expect(screen.getByText(/Contrat de maintenance actif jusqu’au/)).toBeInTheDocument()
    expect(screen.getByText(/Aucun équipement installé/)).toBeInTheDocument()
  })

  it('aucun client : un message, aucun bouton', () => {
    monter('parc_client', ex('parc_client', 'exemple_aucun'))
    expect(screen.getByText(/Aucun client trouvé/)).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
