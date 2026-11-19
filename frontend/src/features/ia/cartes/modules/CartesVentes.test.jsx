import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'
import iaReducer from '../../store/iaSlice'
import { CONTRATS_CARTES } from '../contrats'
import { COMPOSANTS } from '../registre'

/* Nouveau fichier car : composant neuf, aucun module de test existant. Chaque carte
   est rendue avec l'ÉCHANTILLON committé de son contrat, jamais une charge à la main. */

const ex = (cle, variante) => exempleContrat(...CONTRATS_CARTES[cle], variante)
const monter = (cle, donnees) => {
  const Carte = COMPOSANTS[cle]
  const store = configureStore({ reducer: { ia: iaReducer } })
  return render(<Provider store={store}><MemoryRouter><Carte carte={{ donnees }} /></MemoryRouter></Provider>)
}

describe('carte liste_impayes', () => {
  it('exemple : total, tranches, une rangée par facture avec retard et promesse', () => {
    monter('liste_impayes', ex('liste_impayes'))
    expect(screen.getByText(/Impayés : .*40\s?600,00.*2 factures/)).toBeInTheDocument()
    expect(screen.getByText(/Ferme Ait Lahcen SARL — /)).toBeInTheDocument()
    expect(screen.getByText(/FAC-202610-0015 · Relance 2 · 34 j de retard/)).toBeInTheDocument()
    expect(screen.getByText(/promesse pour le /)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Relancer le client/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Ouvrir la facture' })).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Ouvrir les relances' })).toBeInTheDocument()
  })

  it('liste vide : un message, aucun bouton', () => {
    monter('liste_impayes', ex('liste_impayes', 'exemple_vide'))
    expect(screen.getByText(/Aucun impayé/)).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})

describe('carte vente_etat', () => {
  it('exemple : référence, client, montants du serveur, tranches, facture, lien', () => {
    monter('vente_etat', ex('vente_etat'))
    expect(screen.getByText(/Vente DEV-202610-0021 — Driss Lahlou/)).toBeInTheDocument()
    expect(screen.getAllByText(/49\s?000,00/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Livraison du matériel — /)).toBeInTheDocument()
    expect(screen.getByText(/FAC-202610-0007/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Facturer la prochaine tranche/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Ouvrir le devis/ })).toBeInTheDocument()
  })

  it('brouillon à émettre : la raison du serveur et le brouillon sont dits', () => {
    monter('vente_etat', ex('vente_etat', 'exemple_brouillon_a_emettre'))
    expect(screen.getByText(/est en brouillon : émettez-la/)).toBeInTheDocument()
    expect(screen.getByText(/BROUILLON-126/)).toBeInTheDocument()
    expect(screen.getByText(/Émettre le brouillon/)).toBeInTheDocument()
  })
})
