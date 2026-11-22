// J3 — l'écran de démarrage a deux textes : « Hors ligne » et « serveur lent » (nouvel essai seul).
// Rendu réel du composant sous un routeur de données (jamais de lecture du source).
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import HorsLigneDemarrage from './HorsLigneDemarrage.jsx'

function monter(donnee) {
  const routeur = createMemoryRouter(
    [{ path: '/', element: <HorsLigneDemarrage />, loader: () => donnee }],
    { initialEntries: ['/'] },
  )
  return render(<RouterProvider router={routeur} />)
}

describe('HorsLigneDemarrage', () => {
  it('serveur lent : titre dédié et bouton « Réessayer »', async () => {
    monter({ horsLigne: true, lent: true })
    expect(await screen.findByText('Le serveur met du temps à répondre')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Réessayer' })).toBeTruthy()
    expect(screen.getByRole('alert').getAttribute('data-etat-demarrage')).toBe('lent')
  })

  it('hors ligne : titre « Hors ligne » et phrase de connexion', async () => {
    monter({ horsLigne: true })
    expect(await screen.findByText('Hors ligne')).toBeTruthy()
    expect(screen.getByText(/Impossible de joindre le serveur\./)).toBeTruthy()
    expect(screen.getByRole('alert').getAttribute('data-etat-demarrage')).toBe('hors-ligne')
  })
})
