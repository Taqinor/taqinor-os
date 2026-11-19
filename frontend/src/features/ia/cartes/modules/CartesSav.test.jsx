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

describe('carte liste_tickets', () => {
  it('exemple : retard de service dit, garantie, geste, liens', () => {
    monter('liste_tickets', ex('liste_tickets'))
    expect(screen.getByText('Tickets (2)')).toBeInTheDocument()
    expect(screen.getByText(/SAV-2026-11-0031 — Nadia Chraibi/)).toBeInTheDocument()
    expect(screen.getAllByText(/En retard sur l’échéance de service/)).toHaveLength(1)
    expect(screen.getByText(/À faire : Planifier l’intervention/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Ouvrir le ticket' })).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Tickets à traiter' })).toBeInTheDocument()
  })

  it('liste vide : un message', () => {
    monter('liste_tickets', ex('liste_tickets', 'exemple_vide'))
    expect(screen.getByText(/Aucun ticket ne correspond/)).toBeInTheDocument()
  })
})

describe('carte fiche_ticket', () => {
  it('exemple : la description du client et les activités sont CITÉES en texte brut', () => {
    monter('fiche_ticket', ex('fiche_ticket'))
    expect(screen.getByText(/SAV-2026-11-0031 — Nouveau/)).toBeInTheDocument()
    const citations = document.querySelectorAll('blockquote')
    expect(citations).toHaveLength(2)
    expect(citations[0]).toHaveTextContent(/erreur F13/)
    expect(screen.getByText(/Échéance .* — en retard/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ouvrir le ticket' })).toBeInTheDocument()
  })

  it('un texte tiers n’est jamais du HTML et il est coupé poliment', () => {
    const donnees = { ...ex('fiche_ticket'), description: `<img src=x onerror=alert(1)> ${'a'.repeat(900)}` }
    const { container } = monter('fiche_ticket', donnees)
    expect(container.querySelector('img')).toBeNull()
    const citation = container.querySelector('blockquote')
    expect(citation.textContent).toContain('<img src=x')
    expect(citation.textContent.endsWith('… »')).toBe(true)
    expect(citation.textContent.length).toBeLessThan(400)
  })
})

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
