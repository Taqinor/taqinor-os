import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import ListeEtat from './ListeEtat'

/* AERR93 — Nouveau fichier car : aucun module de test pour ListeEtat. Une
   relecture ratée ne remplace plus la liste déjà affichée : contenu gardé +
   avis « pas à jour » ; l'erreur plein cadre reste réservée à une liste jamais
   chargée. */

afterEach(() => { cleanup(); vi.clearAllMocks() })

const lignes = [1, 2, 3].map((n) => <div key={n}>Ligne {n}</div>)

describe('ListeEtat — AERR93', () => {
  it('erreur avec contenu : contenu gardé + avis', () => {
    const onRetry = vi.fn()
    render(<ListeEtat error="Délai dépassé" empty="Vide" onRetry={onRetry}>{lignes}</ListeEtat>)
    expect(screen.getByText('Ligne 1')).toBeInTheDocument()
    expect(screen.getByText('Ligne 3')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Délai dépassé')
    expect(screen.queryByText('Impossible de charger')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('erreur sans contenu : « Impossible de charger » comme avant', () => {
    render(<ListeEtat error="Délai dépassé" empty="Vide">{false}</ListeEtat>)
    expect(screen.getByText('Impossible de charger')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Réessayer' })).toBeNull()
  })

  it('rechargement avec contenu : la liste reste (pas de spinner plein cadre)', () => {
    render(<ListeEtat loading empty="Vide">{lignes}</ListeEtat>)
    expect(screen.getByText('Ligne 2')).toBeInTheDocument()
    expect(screen.queryByText('Chargement…')).toBeNull()
  })

  it('sans contenu ni erreur : état vide', () => {
    render(<ListeEtat empty="Nomenclature vide">{false}</ListeEtat>)
    expect(screen.getByText('Nomenclature vide')).toBeInTheDocument()
  })
})
