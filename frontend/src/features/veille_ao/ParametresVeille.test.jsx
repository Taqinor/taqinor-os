import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   VAO35 — Paramètres de veille : mots-clés, sources, exclusions, cadence, et
   le bouton « Rafraîchir maintenant » (VAO23, MÊME job que le beat).
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  sourcesList: vi.fn(),
  sourcesUpdate: vi.fn(),
  motsList: vi.fn(),
  motsCreate: vi.fn(),
  motsUpdate: vi.fn(),
  reglesList: vi.fn(),
  reglesUpdate: vi.fn(),
  sante: vi.fn(),
  declencher: vi.fn(),
  jobsStatusList: vi.fn(),
}))

vi.mock('../../api/veilleAoApi', () => ({
  default: {
    sources: { list: mocks.sourcesList, update: mocks.sourcesUpdate },
    motsCles: { list: mocks.motsList, create: mocks.motsCreate, update: mocks.motsUpdate },
    reglesExclusion: { list: mocks.reglesList, update: mocks.reglesUpdate },
    sante: mocks.sante,
    collecte: { declencher: mocks.declencher },
  },
}))

vi.mock('../../api/coreApi', () => ({
  default: { jobsStatus: { list: mocks.jobsStatusList } },
}))

import ParametresVeille from './ParametresVeille'

const renderScreen = () => render(
  <MemoryRouter><ThemeProvider><ParametresVeille /></ThemeProvider></MemoryRouter>,
)

// `type_source` est le nom RÉELLEMENT servi par `apps/veille_ao` (le libellé
// lisible arrive en `type_source_libelle`) — la fixture suit le serveur.
// Volontairement SANS `type_source_libelle` : le rendre égal à `libelle`
// ferait matcher « Portail officiel » deux fois et casserait la recherche.
const SOURCES = [{ id: 1, code: 'pmmp', libelle: 'Portail officiel', type_source: 'portail_officiel', actif: true }]
const MOTS = [{ id: 1, libelle: 'solaire', niveau: 'noyau', poids: 3, actif: true }]
const REGLES = [{ id: 1, portee: 'acheteur', valeur: 'ONEE-Eau', motif: 'hors zone', actif: true, compteur_application: 4 }]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.sourcesList.mockResolvedValue({ data: SOURCES })
  mocks.motsList.mockResolvedValue({ data: MOTS })
  mocks.reglesList.mockResolvedValue({ data: REGLES })
  mocks.sante.mockResolvedValue({
    data: { collecte_active: false, derniere_collecte_reussie: '2026-08-06T06:00:00Z', alarme_active: false, avis_examines_hier: 3 },
  })
  mocks.jobsStatusList.mockResolvedValue({ data: [] })
})

describe('ParametresVeille', () => {
  it('charge sources, mots-clés et règles d’exclusion', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.sourcesList).toHaveBeenCalled())
    await waitFor(() => expect(mocks.motsList).toHaveBeenCalled())
    await waitFor(() => expect(mocks.reglesList).toHaveBeenCalled())
    expect(await screen.findByText('Portail officiel')).toBeInTheDocument()
    expect(await screen.findByText('solaire')).toBeInTheDocument()
  })

  it('VAO35 (Done=) — l’état DÉSARMÉ est impossible à confondre avec ARMÉ', async () => {
    renderScreen()
    expect(await screen.findByText(/DÉSARMÉE — accord fondateur requis/)).toBeInTheDocument()
    expect(screen.queryByText(/: ARMÉE/)).not.toBeInTheDocument()
  })

  it('affiche « ARMÉE » quand la collecte est active côté serveur', async () => {
    mocks.sante.mockResolvedValue({ data: { collecte_active: true, derniere_collecte_reussie: '2026-08-07T06:00:00Z' } })
    renderScreen()
    expect(await screen.findByText(/: ARMÉE/)).toBeInTheDocument()
    expect(screen.queryByText(/DÉSARMÉE/)).not.toBeInTheDocument()
  })

  it('ajouter un mot-clé appelle motsCles.create et rafraîchit la liste (VAO9/VAO35)', async () => {
    mocks.motsCreate.mockResolvedValue({ data: { id: 2 } })
    renderScreen()
    await screen.findByText('solaire')
    fireEvent.change(screen.getByLabelText('Libellé'), { target: { value: 'pompage solaire' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }))
    await waitFor(() => expect(mocks.motsCreate).toHaveBeenCalledWith(
      expect.objectContaining({ libelle: 'pompage solaire', niveau: 'noyau', actif: true }),
    ))
    await waitFor(() => expect(mocks.motsList).toHaveBeenCalledTimes(2))
  })

  it('désactiver une source appelle sources.update(id, { actif: false })', async () => {
    mocks.sourcesUpdate.mockResolvedValue({ data: {} })
    renderScreen()
    await screen.findByText('Portail officiel')
    fireEvent.click(screen.getByRole('switch', { name: /Source active/ }))
    await waitFor(() => expect(mocks.sourcesUpdate).toHaveBeenCalledWith(1, { actif: false }))
  })

  it('affiche le compteur d’application d’une règle d’exclusion', async () => {
    renderScreen()
    expect(await screen.findByText(/appliquée 4 fois/)).toBeInTheDocument()
  })

  it('« Rafraîchir maintenant » appelle EXACTEMENT collecte.declencher() (VAO23, même job que le beat)', async () => {
    mocks.declencher.mockResolvedValue({ data: { id: 77, statut: 'en_cours' } })
    renderScreen()
    fireEvent.click(screen.getByRole('button', { name: /Rafraîchir maintenant/ }))
    await waitFor(() => expect(mocks.declencher).toHaveBeenCalledTimes(1))
  })

  it('VAO35 (Done=) — double clic ne lance pas deux collectes : le bouton se désactive immédiatement', async () => {
    mocks.declencher.mockImplementation(() => new Promise((resolve) => setTimeout(() => resolve({ data: { id: 1, statut: 'termine' } }), 20)))
    renderScreen()
    const bouton = screen.getByRole('button', { name: /Rafraîchir maintenant/ })
    fireEvent.click(bouton)
    fireEvent.click(bouton) // le bouton est déjà `disabled` après le 1er clic
    await waitFor(() => expect(mocks.declencher).toHaveBeenCalledTimes(1))
  })
})
