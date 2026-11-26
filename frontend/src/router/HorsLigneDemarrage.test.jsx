// J3 — l'écran de démarrage a deux textes : « Hors ligne » et « serveur lent » (nouvel essai seul).
// Rendu réel du composant sous un routeur de données (jamais de lecture du source).
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import HorsLigneDemarrage from './HorsLigneDemarrage.jsx'

function monter(donnee, url = '/') {
  const routeur = createMemoryRouter(
    [{ path: '*', element: <HorsLigneDemarrage />, loader: () => donnee }],
    { initialEntries: [url] },
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

  it('T4-X8-002 : rechargé hors ligne sur le relevé de visite, la phrase dit ce que deviennent mesures et photos', async () => {
    monter({ horsLigne: true }, '/calepinage/1978/releve')
    expect(await screen.findByText('Hors ligne')).toBeTruthy()
    expect(screen.getByText('Vos mesures et vos photos sont gardées sur ce téléphone. '
      + 'Elles s’afficheront et partiront au retour du réseau.')).toBeTruthy()
    expect(screen.queryByText(/Vos données restent sur cet appareil/)).toBeNull()
  })
})
