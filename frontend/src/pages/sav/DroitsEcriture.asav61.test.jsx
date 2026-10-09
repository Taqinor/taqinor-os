import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// ASAV61 — un rôle du palier normal ne voit plus de bouton d'écriture que le
// serveur refuserait (403) sur Alarmes, Base de connaissances, Problèmes et la
// mise au rebut du parc. Rôle injecté dans le VRAI store d'auth.

vi.mock('../../api/savApi', () => ({
  default: new Proxy({
    getAlarmes: () => Promise.resolve({ data: [{
      id: 1, code: 'E07', gravite: 'warning', statut: 'active', equipement: 9,
      date_detection: '2026-10-09T10:00:00Z' }] }),
    getKbArticles: () => Promise.resolve({ data: [{
      id: 1, titre: 'Article A', corps: 'x', categorie: '', tags: [] }] }),
    getProblemes: () => Promise.resolve({ data: { results: [{
      id: 5, reference: 'PRB-1', titre: 'P', statut: 'identifie', nb_tickets: 0, impact: 0 }] } }),
    getRegroupementsSuggeres: () => Promise.resolve({ data: { results: [{
      produit_id: 1, cause_id: 1, titre_suggere: 'Groupe', nb_tickets: 3,
      tickets: [{ id: 1, reference: 'SAV-1' }] }] } }),
    getProblemeTickets: () => Promise.resolve({ data: { results: [] } }),
    getTickets: () => Promise.resolve({ data: [] }),
  }, { get: (c, n) => c[n] ?? (() => Promise.resolve({ data: [] })) }),
}))
vi.mock('../../api/axios', () => ({ default: { get: vi.fn(() => Promise.resolve({ data: [] })), post: vi.fn() } }))
vi.mock('../../api/stockApi', () => ({ default: { getProduits: () => Promise.resolve({ data: [] }) } }))
vi.mock('../../api/installationsApi', () => ({ default: { getInstallations: () => Promise.resolve({ data: [] }) } }))
vi.mock('../../api/importApi', () => ({ default: {} }))

import SavAlarmesPage from './SavAlarmesPage'
import KbArticlesPage from './KbArticlesPage'
import ProblemesPage from './ProblemesPage'
import { EquipementDetail } from './EquipementsPage'

afterEach(cleanup)

const ROLES = {
  normal: { role: 'technicien', role_nom: 'Technicien', permissions: ['sav_voir'] },
  equipement_voir: { role: 'technicien', role_nom: 'Technicien', permissions: ['sav_voir', 'equipement_voir'] },
  responsable: { role: 'responsable', role_nom: 'Responsable', permissions: ['sav_voir', 'sav_probleme_gerer'] },
}
const monter = (ui, profil) => render(
  <Provider store={configureStore({ reducer: { auth: (s = ROLES[profil]) => s } })}>
    <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>
  </Provider>)

const equipement = { id: 9, numero_serie: 'SN', statut: 'en_service', nb_tickets_ouverts: 0 }

describe('ASAV61 — gestes d\'écriture selon le rôle', () => {
  it('palier normal : listes visibles, aucun bouton Créer / Acquitter / Escalader', async () => {
    monter(<SavAlarmesPage />, 'normal')
    expect(await screen.findByText('E07')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Créer une alarme/ })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Acquitter' })).toBeNull()
    expect(screen.queryByRole('button', { name: /Escalader/ })).toBeNull()
  })

  it('responsable : tous les gestes d\'alarme', async () => {
    monter(<SavAlarmesPage />, 'responsable')
    expect(await screen.findByRole('button', { name: /Créer une alarme/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Acquitter' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Escalader/ })).toBeInTheDocument()
  })

  it('base de connaissances : lecture seule au palier normal', async () => {
    monter(<KbArticlesPage />, 'normal')
    expect(await screen.findByText('Article A')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Ajouter/ })).toBeNull()
    cleanup()
    monter(<KbArticlesPage />, 'responsable')
    expect(await screen.findByRole('button', { name: /Ajouter/ })).toBeInTheDocument()
  })

  it('problèmes : pas de création ni de gestes sans sav_probleme_gerer', async () => {
    monter(<ProblemesPage />, 'normal')
    expect(await screen.findByText('PRB-1')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Créer le problème' })).toBeNull()
    cleanup()
    monter(<ProblemesPage />, 'responsable')
    expect(await screen.findByRole('button', { name: 'Créer le problème' })).toBeInTheDocument()
  })

  it('parc : « Mettre au rebut » réservé responsable/admin', async () => {
    monter(<EquipementDetail equipement={equipement} onClose={() => {}} onSaved={() => {}} />, 'equipement_voir')
    await screen.findByRole('button', { name: /Créer un ticket SAV/ })
    expect(screen.queryByRole('button', { name: /Mettre au rebut/ })).toBeNull()
    cleanup()
    monter(<EquipementDetail equipement={equipement} onClose={() => {}} onSaved={() => {}} />, 'responsable')
    expect(await screen.findByRole('button', { name: /Mettre au rebut/ })).toBeInTheDocument()
  })
})
