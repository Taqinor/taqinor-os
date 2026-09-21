import { describe, it, expect, beforeAll, vi } from 'vitest'
import { Suspense } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR57 — le module Hôtellerie (5 écrans construits) n'avait AUCUN registre :
   ni route ni entrée de nav ne l'atteignait. On vérifie ici (1) que la config
   déclare bien les routes + les entrées de nav, et (2) que chaque écran se
   monte réellement via sa route (rendu via `config.routes`, réseau mocké).
   WIR146 — étend la couverture aux 3 écrans opérationnels ajoutés
   (check-in/out, recettes, salles & banquets) : le backend
   (ReservationViewSet.check_in/check_out/fiche_police_pdf, RecetteViewSet,
   SalleEvenementViewSet, EvenementBanquetViewSet.generer_devis/beo_pdf)
   était complet et testé mais aucun écran ne le consommait. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

vi.mock('../../api/hospitalityApi', () => ({
  default: {
    tableauBord: () => Promise.resolve({
      data: { adr: 0, revpar: 0, taux_occupation: 0, no_show_rate: 0 },
    }),
    listChambres: () => Promise.resolve({ data: [{ id: 1, numero: '101', nom: '' }] }),
    listReservations: () => Promise.resolve({
      data: [{
        id: 1, statut: 'confirmee', statut_display: 'Confirmée',
        date_arrivee: '2026-09-01', date_depart: '2026-09-05', client_nom: 'Alami',
      }],
    }),
    listMainCourante: () => Promise.resolve({ data: [] }),
    listTachesMenage: () => Promise.resolve({ data: [] }),
    // WIR146 — check-in/out, recettes, banquets.
    checkIn: () => Promise.resolve({ data: {} }),
    checkOut: () => Promise.resolve({ data: {} }),
    fichesPolice: () => Promise.resolve({ data: [] }),
    fichePolicePdf: () => Promise.resolve({ data: new Blob() }),
    listRecettes: () => Promise.resolve({
      data: [{ id: 1, nom_plat: 'Tajine poulet', categorie_menu: 'plat', categorie_menu_display: 'Plat', prix_vente_ht: '80.00' }],
    }),
    createRecette: () => Promise.resolve({ data: {} }),
    listIngredientsRecette: () => Promise.resolve({ data: [] }),
    ajouterIngredientRecette: () => Promise.resolve({ data: {} }),
    retirerIngredientRecette: () => Promise.resolve({ data: {} }),
    listSallesEvenement: () => Promise.resolve({
      data: [{ id: 1, nom: 'Salle Atlas', capacite_max: 120 }],
    }),
    createSalleEvenement: () => Promise.resolve({ data: {} }),
    listEvenementsBanquet: () => Promise.resolve({
      data: [{
        id: 1, nom_evenement: 'Mariage Bennani', salle: 1, salle_nom: 'Salle Atlas',
        date_debut: '2026-10-01T18:00:00Z', date_fin: '2026-10-02T02:00:00Z',
        nb_convives: 150, statut: 'brouillon', statut_display: 'Brouillon',
        devis_ventes_id: null,
      }],
    }),
    createEvenementBanquet: () => Promise.resolve({ data: {} }),
    genererDevisEvenement: () => Promise.resolve({ data: { devis_id: 1, devis_reference: 'DV-0001' } }),
    beoPdf: () => Promise.resolve({ data: new Blob() }),
  },
}))

import config from './module.config.jsx'

const PATHS = [
  '/hospitality',
  '/hospitality/chambres',
  '/hospitality/reservations',
  '/hospitality/main-courante',
  '/hospitality/menage',
  '/hospitality/check-in-out',
  '/hospitality/recettes',
  '/hospitality/banquets',
]

function renderRoute(path) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Suspense fallback={<div>chargement…</div>}>
          <Routes>
            {config.routes.map((r) => {
              const C = r.component
              return <Route key={r.path} path={r.path} element={<C />} />
            })}
          </Routes>
        </Suspense>
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('hospitality — module.config (WIR57/WIR146)', () => {
  it('déclare les 8 routes ET les 8 entrées de nav HÔTELLERIE, gatées', () => {
    expect(config.key).toBe('hospitality')
    expect(config.nav.label).toBe('HÔTELLERIE')
    for (const p of PATHS) {
      const route = config.routes.find((r) => r.path === p)
      expect(route, `route ${p}`).toBeTruthy()
      expect(route.roles).toEqual(['normal', 'responsable', 'admin'])
      const nav = config.nav.items.find((i) => i.to === p)
      expect(nav, `nav ${p}`).toBeTruthy()
      expect(nav.icon).toBeTruthy()
    }
    expect(config.sectionLabels.hospitality).toBe('Hôtellerie')
  })

  it('monte le Tableau de bord via /hospitality', async () => {
    renderRoute('/hospitality')
    // Premier montage lazy du module : le chunk (+ Card/Stat) peut mettre plus
    // d'1s à se transformer en environnement de test, d'où un délai généreux.
    await waitFor(() => expect(screen.getByText('ADR (prix moyen/nuit)')).toBeTruthy(), { timeout: 5000 })
  })

  it('monte le Plan des chambres via /hospitality/chambres', async () => {
    renderRoute('/hospitality/chambres')
    await waitFor(() => expect(screen.getByText(/101/)).toBeTruthy(), { timeout: 5000 })
  })

  it('monte les Réservations via /hospitality/reservations', async () => {
    renderRoute('/hospitality/reservations')
    await waitFor(() => expect(screen.getByTestId('cell-1-0')).toBeTruthy(), { timeout: 5000 })
  })

  it('monte la Main courante via /hospitality/main-courante', async () => {
    renderRoute('/hospitality/main-courante')
    await waitFor(() => expect(screen.getByText('Aucune note')).toBeTruthy())
  })

  it('monte le Ménage via /hospitality/menage', async () => {
    renderRoute('/hospitality/menage')
    await waitFor(() => expect(screen.getByText('Aucune tâche à faire')).toBeTruthy())
  })

  it('monte Check-in / check-out via /hospitality/check-in-out avec la réservation à checker-in', async () => {
    renderRoute('/hospitality/check-in-out')
    await waitFor(() => expect(screen.getByText(/Alami/)).toBeTruthy(), { timeout: 5000 })
    expect(screen.getByRole('button', { name: 'Check-in' })).toBeTruthy()
  })

  it('monte Recettes via /hospitality/recettes avec la fiche technique chargée', async () => {
    renderRoute('/hospitality/recettes')
    await waitFor(() => expect(screen.getByText('Tajine poulet')).toBeTruthy(), { timeout: 5000 })
  })

  it('monte Salles & banquets via /hospitality/banquets avec la salle et l’événement chargés', async () => {
    renderRoute('/hospitality/banquets')
    await waitFor(() => expect(screen.getByText(/Mariage Bennani/)).toBeTruthy(), { timeout: 5000 })
    expect(screen.getByText(/Salle Atlas \(120 pers\.\)/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Générer le devis' })).toBeTruthy()
  })
})
