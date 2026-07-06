import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { controlePermis, alertesToEcheanceItems, optionsFrom, VEHICULE_STATUTS } from './flotte'

// jsdom n'implémente pas ResizeObserver (mesuré par certains primitifs UI) —
// on le polyfill localement pour que les écrans se montent proprement.
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

/* Tests du module Flotte (UX15–UX20). Deux volets : (1) la logique PURE de
   contrôle de permis à l'affectation (FLOTTE9, miroir backend) — le garde-fou
   qui bloque une affectation quand le permis est invalide ; (2) un rendu smoke
   d'un écran, enveloppé dans <MemoryRouter> + <ThemeProvider>. Les appels API
   sont mockés pour rester hors réseau. */

// Mock du client API : chaque endpoint renvoie une liste vide (rendu smoke).
vi.mock('../../api/flotteApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  const crud = { list: empty, get: empty, create: empty, update: empty, remove: empty }
  return {
    default: {
      vehicules: crud, modelesVehicule: crud, engins: crud, referentiels: crud,
      actifs: { ...crud, detenteursCourants: empty, documents: empty },
      conducteurs: crud,
      affectations: { ...crud, masse: empty },
      reservations: crud,
      demandesVehicule: crud,
      etatsDesLieux: { ...crud, signer: empty },
      chartesVehicule: crud, accusesCharte: crud,
      plansEntretien: { ...crud, echeances: empty, rollout: empty },
      echeancesEntretien: crud, garages: crud, garanties: crud,
      ordresReparation: { ...crud, couts: empty, cloturer: empty, approuver: empty },
      pneumatiques: crud, pieces: crud,
      contratsVehicule: { ...crud, expirants: empty },
      couts: crud,
      echeancesReglementaires: crud, assurances: crud, visitesTechniques: crud,
      cartesGrises: crud, baremesVignette: crud,
      pleins: { ...crud, ocr: empty },
      cartes: crud, sinistres: crud, infractions: crud,
      relevesTelematiques: crud, trajetsTelematiques: crud, trajetsChantier: crud,
      zonesGeographiques: { ...crud, evaluer: empty },
      rappelsConstructeur: { ...crud, rapprocher: empty },
      signalements: { ...crud, convertirEnOr: empty },
      modelesInspection: crud,
      inspections: { ...crud, tauxCompletion: empty },
      budgets: crud,
      remisesAccessoire: crud,
      tableauBord: () => Promise.resolve({ data: {} }),
      alertesEcheances: () => Promise.resolve({ data: { alertes: [] } }),
      vehiculeTco: empty, vehiculeTsav: empty, vehiculeEcoConduite: empty,
      vehiculeAmortissement: empty, vehiculeLedger: empty,
      vehiculeHistorique: empty, vehiculeActivites: empty,
      changerStatut: empty, ceder: empty,
      rapportCouts: empty, rapportRemplacement: empty, rapportBudget: empty,
    },
  }
})

import VehiculesList from './VehiculesList'
import ConformiteScreen from './ConformiteScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('controlePermis (FLOTTE9 — garde-fou d’affectation)', () => {
  const today = new Date('2026-07-01')

  it('autorise quand le véhicule n’exige aucune catégorie', () => {
    const r = controlePermis(
      { numero_permis: '', categorie_permis: '' },
      { categorie_permis_requise: '' },
      today,
    )
    expect(r.ok).toBe(true)
    expect(r.code).toBe('')
  })

  it('bloque (permis_manquant) quand le véhicule exige une catégorie et le conducteur n’a pas de permis', () => {
    const r = controlePermis(
      { numero_permis: '', categorie_permis: '' },
      { categorie_permis_requise: 'C' },
      today,
    )
    expect(r.ok).toBe(false)
    expect(r.code).toBe('permis_manquant')
    expect(r.message).toMatch(/permis valide/i)
  })

  it('bloque (permis_expire) quand le permis est expiré', () => {
    const r = controlePermis(
      { numero_permis: 'AB123', categorie_permis: 'C', date_expiration: '2026-06-01' },
      { categorie_permis_requise: 'C' },
      today,
    )
    expect(r.ok).toBe(false)
    expect(r.code).toBe('permis_expire')
  })

  it('bloque (categorie_inadaptee) quand la catégorie requise n’est pas portée', () => {
    const r = controlePermis(
      { numero_permis: 'AB123', categorie_permis: 'B', date_expiration: '2030-01-01' },
      { categorie_permis_requise: 'CE' },
      today,
    )
    expect(r.ok).toBe(false)
    expect(r.code).toBe('categorie_inadaptee')
  })

  it('autorise quand le conducteur porte la catégorie requise (multi-catégories) et permis valide', () => {
    const r = controlePermis(
      { numero_permis: 'AB123', categorie_permis: 'B, CE', date_expiration: '2030-01-01' },
      { categorie_permis_requise: 'ce' }, // insensible à la casse / aux espaces
      today,
    )
    expect(r.ok).toBe(true)
    expect(r.code).toBe('')
  })
})

describe('helpers purs Flotte', () => {
  it('alertesToEcheanceItems mappe libelle/date/jours vers des items EcheanceCenter', () => {
    const items = alertesToEcheanceItems([
      { source: 'assurance', objet_id: 5, libelle: 'Assurance X', date_echeance: '2026-07-10', jours_restants: 9, actif_label: 'AB-123' },
    ])
    expect(items).toHaveLength(1)
    expect(items[0]).toMatchObject({ label: 'Assurance X', date: '2026-07-10', daysLeft: 9, meta: 'AB-123' })
  })

  it('optionsFrom transforme un map de choix en options {value,label}', () => {
    expect(optionsFrom(VEHICULE_STATUTS)).toContainEqual({ value: 'actif', label: 'Actif' })
  })
})

describe('rendu smoke des écrans', () => {
  it('VehiculesList affiche le titre et le basculeur de parc', async () => {
    withProviders(<VehiculesList />)
    expect(
      screen.getByRole('heading', { name: /Véhicules & engins/ }),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByRole('radiogroup', { name: /Type de parc/ })).toBeInTheDocument(),
    )
  })

  it('ConformiteScreen affiche le centre d’échéances réglementaires', async () => {
    withProviders(<ConformiteScreen />)
    expect(
      screen.getByRole('heading', { name: 'Conformité réglementaire' }),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(
        screen.getByText(/Échéances réglementaires à surveiller/),
      ).toBeInTheDocument(),
    )
  })
})
