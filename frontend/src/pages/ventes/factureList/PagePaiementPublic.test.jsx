import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* AFAC26 — page publique /payer/:token. Réponses simulées LUES dans le contrat
   `paiement_public.json` (AFAC20) : aucun payload inventé. */

const http = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('../../../api/axios', () => ({ default: http }))

import PagePaiementPublic from './PagePaiementPublic'

const ICI = dirname(fileURLToPath(import.meta.url))
const CONTRAT = JSON.parse(readFileSync(join(
  ICI, '..', '..', '..', '..', '..', 'backend', 'django_core', 'apps', 'facturation',
  'contract_samples', 'paiement_public.json'), 'utf8'))

function rendre() {
  return render(
    <MemoryRouter initialEntries={['/payer/tok123']}>
      <Routes><Route path="/payer/:token" element={<PagePaiementPublic />} /></Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => http.get.mockReset())

describe('PagePaiementPublic — AFAC26', () => {
  it('affiche le montant à payer du contrat, la référence et le RIB', async () => {
    http.get.mockResolvedValue({ data: CONTRAT.exemple })
    rendre()
    expect(await screen.findByTestId('montant-a-regler')).toHaveTextContent(/15\s?000,00 MAD à régler/)
    expect(http.get).toHaveBeenCalledWith('/public/pay/tok123/')
    expect(screen.getByText(/FAC-2026-10-0007 — Atlas Agro SARL/)).toBeInTheDocument()
    expect(screen.getByTestId('rib')).toHaveTextContent(CONTRAT.exemple.rib)
    // le montant figé (trace) n'est jamais celui affiché
    expect(screen.queryByText(/20\s?000,00/)).toBeNull()
  })

  it('affiche Facture réglée quand le lien est payé', async () => {
    http.get.mockResolvedValue({ data: CONTRAT.exemple_paye })
    rendre()
    expect(await screen.findByText('Facture réglée')).toBeInTheDocument()
    expect(screen.queryByTestId('montant-a-regler')).toBeNull()
  })

  it('affiche Facture annulée sans montant', async () => {
    http.get.mockResolvedValue({ data: { ...CONTRAT.exemple, statut: 'annule', montant: '0.00' } })
    rendre()
    expect(await screen.findByText('Facture annulée')).toBeInTheDocument()
    expect(screen.queryByTestId('montant-a-regler')).toBeNull()
    expect(screen.queryByText(/MAD/)).toBeNull()
  })

  it('affiche Lien expiré', async () => {
    http.get.mockResolvedValue({ data: { ...CONTRAT.exemple, statut: 'expire', expire: true } })
    rendre()
    expect(await screen.findByText('Lien expiré')).toBeInTheDocument()
  })

  it('jeton inconnu : message honnête, jamais un faux montant', async () => {
    // réponse vide (le serveur ne rend rien pour un jeton inconnu) : jamais de faux montant
    http.get.mockResolvedValue({ data: null })
    rendre()
    expect(await screen.findByRole('alert')).toHaveTextContent(/introuvable|expiré/)
  })

  it('le contrat ne porte aucune donnée interne', () => {
    expect(JSON.stringify(CONTRAT.exemple)).not.toMatch(/prix_achat|marge/)
  })
})
