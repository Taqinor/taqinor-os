import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'
import iaReducer from '../../store/iaSlice'
import { CONTRATS_CARTES, CONTRATS_JUMEAUX } from '../contrats'
import { COMPOSANTS } from '../registre'

/* Nouveau fichier car : composant neuf, aucun module de test existant. Payloads = échantillons
   committés des contrats, jamais écrits à la main. */

const exemple = (paire, variante = 'exemple') => exempleContrat(paire[0], paire[1], variante)

function Route() {
  return <span data-testid="route">{useLocation().pathname}</span>
}

function monter(cle, donnees) {
  const Carte = COMPOSANTS[cle]
  const store = configureStore({ reducer: { ia: iaReducer } })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <Carte carte={{ type: 'resultat', carte: cle, donnees }} />
        <Route />
      </MemoryRouter>
    </Provider>,
  )
}

describe('liste_visites', () => {
  it('totaux, une rangée par visite, sans technicien dit, liens vers chaque visite', async () => {
    monter('liste_visites', exemple(CONTRATS_CARTES.liste_visites))
    expect(screen.getByText(/7 planifiée\(s\) · 2 sans technicien · 1 à valider/)).toBeInTheDocument()
    expect(screen.getByText(/Salma Berrada/)).toBeInTheDocument()
    expect(screen.getByText(/sans technicien$/)).toBeInTheDocument()
    expect(screen.getByText(/avec Youssef Alami/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Assigner un technicien/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Valider la visite/)).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('button', { name: 'Ouvrir la visite' })[1])
    expect(screen.getByTestId('route')).toHaveTextContent('/visites/90')
  })

  it('liste vide : message, lien vers toutes les visites', async () => {
    monter('liste_visites', exemple(CONTRATS_CARTES.liste_visites, 'exemple_vide'))
    expect(screen.getByText(/Aucune visite pour cette recherche/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Toutes les visites' }))
    expect(screen.getByTestId('route')).toHaveTextContent('/visites/toutes')
  })
})

describe('fiche_visite', () => {
  it('visite validée : déroulé, texte du terrain cité, trois liens', async () => {
    monter('fiche_visite', exemple(CONTRATS_CARTES.fiche_visite))
    expect(screen.getByText(/Aziz Benali — Casablanca/)).toBeInTheDocument()
    expect(screen.getByText('Validée (feu vert)')).toBeInTheDocument()
    expect(screen.getByText(/Terrasse dégagée côté sud/).closest('blockquote')).toBeInTheDocument()
    expect(screen.getAllByText(/cité tel quel/)).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Calage' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Revue des visites' }))
    expect(screen.getByTestId('route')).toHaveTextContent('/visites/revue')
  })

  it('à compléter : manquants, photo à refaire, geste suivant', () => {
    monter('fiche_visite', exemple(CONTRATS_CARTES.fiche_visite, 'exemple_a_completer'))
    expect(screen.getByText('Photo : tableau électrique')).toBeInTheDocument()
    expect(screen.getByText(/Tableau électrique \(floue\)/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Compléter la visite/)).toBeInTheDocument()
  })

  it('jumeau (après annulation) : annulée, plus de date, rien à faire', () => {
    monter('fiche_visite', exemple(CONTRATS_JUMEAUX.fiche_visite))
    expect(screen.getByText('Annulée')).toBeInTheDocument()
    expect(screen.getByText(/pas de date/)).toBeInTheDocument()
    expect(screen.queryByText(/À faire/)).not.toBeInTheDocument()
  })
})

describe('charge_equipe', () => {
  it('une rangée par personne, jour par jour, la note « aucune heure » est dite', () => {
    monter('charge_equipe', exemple(CONTRATS_CARTES.charge_equipe))
    expect(screen.getByText(/aucune heure ni trajet calculés/)).toBeInTheDocument()
    expect(screen.getByText('Omar Fassi (vous)')).toBeInTheDocument()
    expect(screen.getByText(/2 visite\(s\) · 0 intervention\(s\)/)).toBeInTheDocument()
    expect(screen.getByText(/indisponible/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Assigner les visites sans technicien/)).toBeInTheDocument()
  })

  it('soi seul', () => {
    monter('charge_equipe', exemple(CONTRATS_CARTES.charge_equipe, 'exemple_soi_seul'))
    expect(screen.getByText('Omar Fassi (vous)')).toBeInTheDocument()
    expect(screen.queryByText(/À faire/)).not.toBeInTheDocument()
  })
})
