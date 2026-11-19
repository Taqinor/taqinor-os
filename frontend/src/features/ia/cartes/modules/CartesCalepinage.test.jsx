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

/* Nouveau fichier car : composant neuf, aucun module de test existant. Chaque carte est
   rendue avec l'échantillon COMMITTÉ de son contrat (jamais une charge utile tapée). */

const exemple = (paire, variante = 'exemple') => exempleContrat(paire[0], paire[1], variante)

function Route() {
  return <span data-testid="route">{`${useLocation().pathname}${useLocation().search}`}</span>
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

describe('fiche_calepinage', () => {
  it('résumé : conception, production, devis, geste suivant et lien', async () => {
    monter('fiche_calepinage', exemple(CONTRATS_CARTES.fiche_calepinage))
    expect(screen.getByText(/CAL-2611-0012/)).toBeInTheDocument()
    expect(screen.getByText(/12 panneaux/)).toBeInTheDocument()
    expect(screen.getByText(/PAN-A/)).toBeInTheDocument()
    expect(screen.getByText(/DEV-202611-0045/)).toHaveTextContent(/pas à jour/)
    expect(screen.getByText(/À faire : Publier au devis/)).toBeInTheDocument()
    expect(screen.getByText(/ce n’est pas le chiffre montré au client/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Ouvrir le calepinage/ }))
    expect(screen.getByTestId('route')).toHaveTextContent('/calepinage/12')
  })

  it('borne haute : la mention est dite, aucun P90, le blocage électrique est listé', () => {
    monter('fiche_calepinage', exemple(CONTRATS_CARTES.fiche_calepinage, 'exemple_borne_haute'))
    expect(screen.getAllByText(/borne haute/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/P90/)).not.toBeInTheDocument()
    expect(screen.getByText(/Tension de chaîne/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Corriger le verdict électrique/)).toBeInTheDocument()
  })

  it('jumeau « du lead » : même rendu, et variante sans calepinage', () => {
    const { unmount } = monter('fiche_calepinage', exemple(CONTRATS_JUMEAUX.fiche_calepinage))
    expect(screen.getByText(/CAL-2611-0012/)).toBeInTheDocument()
    unmount()
    monter('fiche_calepinage', exemple(CONTRATS_JUMEAUX.fiche_calepinage, 'exemple_sans_calepinage'))
    expect(screen.getByText(/Aucun calepinage ouvert/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Créer le calepinage/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Ouvrir la fiche du lead/ })).toBeInTheDocument()
  })
})

describe('liste_calepinages', () => {
  it('une rangée par calepinage, signaux et lien', async () => {
    monter('liste_calepinages', exemple(CONTRATS_CARTES.liste_calepinages))
    expect(screen.getByText(/Calepinages à traiter \(3\)/)).toBeInTheDocument()
    expect(screen.getByText(/Blocage électrique · Aucun devis lié · Approbation attendue/)).toBeInTheDocument()
    const boutons = screen.getAllByRole('button', { name: 'Ouvrir' })
    expect(boutons).toHaveLength(3)
    await userEvent.click(boutons[1])
    expect(screen.getByTestId('route')).toHaveTextContent('/calepinage/14?onglet=verdict-electrique')
  })

  it('liste vide', () => {
    monter('liste_calepinages', exemple(CONTRATS_CARTES.liste_calepinages, 'exemple_vide'))
    expect(screen.getByText(/Aucun calepinage à traiter/)).toBeInTheDocument()
  })
})

describe('contenance', () => {
  it('visite : estimation étiquetée, fourchette, suppositions, jamais un chiffre de devis', () => {
    monter('contenance', exemple(CONTRATS_CARTES.contenance))
    expect(screen.getByText(/Estimation — Mesuré à la visite/)).toBeInTheDocument()
    expect(screen.getAllByText(/16 à 18 panneaux/).length).toBeGreaterThan(0)
    expect(screen.getByText(/ni un chiffre de devis/)).toBeInTheDocument()
    expect(screen.getByText(/Sens de pose inconnu/)).toBeInTheDocument()
  })

  it('dicté : la mention « dictées » est visible', () => {
    monter('contenance', exemple(CONTRATS_CARTES.contenance, 'exemple_dicte'))
    expect(screen.getByText(/Estimation — Dimensions dictées/)).toBeInTheDocument()
    expect(screen.getByText(/Dimensions dictées, non mesurées/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Dessiner le calepinage/)).toBeInTheDocument()
  })
})
