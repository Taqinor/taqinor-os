import { describe, it, expect, beforeAll, vi } from 'vitest'
import { Suspense } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR143 — le module Éducation (backend NTEDU complet) n'avait AUCUN frontend :
   ni route, ni entrée de nav, ni écran ne l'atteignait. On vérifie ici (1) que
   la config déclare bien les 9 routes P1 + les 9 entrées de nav, et (2) que
   chaque écran se monte réellement via sa route (rendu via `config.routes`,
   réseau mocké) — même patron que `features/hospitality/module.config.test.jsx`
   (WIR57). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

vi.mock('../../api/educationApi', () => ({
  default: {
    anneesScolaires: {
      list: () => Promise.resolve({ data: [{ id: 1, libelle: '2026-2027', statut: 'active' }] }),
    },
    niveaux: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'CE1', cycle: 'primaire' }] }),
    },
    classes: {
      list: () => Promise.resolve({
        data: [{ id: 1, nom: 'CE1-A', niveau: 1, niveau_nom: 'CE1', effectif: 2, capacite_max: 30 }],
      }),
    },
    familles: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Alami', parent1_nom: 'M. Alami', parent1_telephone: '0600000000' }] }),
    },
    eleves: {
      list: () => Promise.resolve({
        data: [{
          id: 1, nom: 'Alami', prenom: 'Sara', famille: 1, classe: 1,
          numero_dossier: 'EL-0001', statut: 'inscrit',
        }],
      }),
    },
    inscriptions: {
      list: () => Promise.resolve({
        data: [{
          id: 1, eleve: 1, annee_scolaire: 1, classe_demandee: 1,
          classe_affectee: null, statut: 'en_attente',
        }],
      }),
    },
    echeanciers: {
      list: () => Promise.resolve({
        data: [{
          id: 1, eleve: 1, montant_total: '12000.00', nombre_echeances: 3,
          lignes: [{ id: 1, libelle: 'Échéance 1', montant: '4000.00', date_echeance: '2026-09-01', statut: 'a_venir' }],
        }],
      }),
    },
    seances: {
      list: () => Promise.resolve({ data: [] }),
      create: () => Promise.resolve({ data: { id: 1 } }),
    },
    presences: {
      bulkSaisie: () => Promise.resolve({ data: [] }),
    },
    evaluations: {
      list: () => Promise.resolve({ data: [] }),
      create: () => Promise.resolve({ data: { id: 1 } }),
    },
    matieresClasse: {
      list: () => Promise.resolve({ data: [{ id: 1, classe: 1, matiere: 1, matiere_nom: 'Français' }] }),
    },
    notes: {
      bulkSaisie: () => Promise.resolve({ data: [] }),
    },
    emploiDuTemps: {
      list: () => Promise.resolve({ data: [] }),
    },
    menusCantine: {
      list: () => Promise.resolve({ data: [{ id: 1, date: '2026-09-01', description: 'Poulet riz', allergenes: [] }] }),
    },
    inscriptionsCantine: {
      list: () => Promise.resolve({ data: [] }),
    },
    incidents: {
      list: () => Promise.resolve({ data: [] }),
    },
  },
}))

import config from './module.config.jsx'

const PATHS = [
  '/education/structure',
  '/education/familles-eleves',
  '/education/inscriptions',
  '/education/echeancier',
  '/education/presences',
  '/education/notes',
  '/education/emploi-du-temps',
  '/education/cantine',
  '/education/discipline',
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

describe('education — module.config (WIR143)', () => {
  it('déclare les 9 routes ET les 9 entrées de nav ÉDUCATION, gatées', () => {
    expect(config.key).toBe('education')
    expect(config.nav.label).toBe('ÉDUCATION')
    for (const p of PATHS) {
      const route = config.routes.find((r) => r.path === p)
      expect(route, `route ${p}`).toBeTruthy()
      expect(route.roles.length).toBeGreaterThan(0)
      const nav = config.nav.items.find((i) => i.to === p)
      expect(nav, `nav ${p}`).toBeTruthy()
      expect(nav.icon).toBeTruthy()
    }
    expect(config.sectionLabels.education).toBe('Éducation')
  })

  // NB (même patron que compta.test.jsx) : sous charge parallèle (cold
  // transform de plusieurs fichiers lourds à la fois), le rendu peut dépasser
  // largement 5 s — délai interne relevé ET délai de test explicite (30 s,
  // au-delà du défaut vitest.config.js) pour ne pas le plafonner en sous-main.
  it('monte Structure via /education/structure avec la classe chargée', async () => {
    renderRoute('/education/structure')
    await waitFor(() => expect(screen.getByText('CE1-A')).toBeTruthy(), { timeout: 25000 })
    expect(screen.getByText('2 / 30')).toBeTruthy()
  }, 30000)

  it('monte Familles & élèves via /education/familles-eleves avec l’élève chargé', async () => {
    renderRoute('/education/familles-eleves')
    await waitFor(() => expect(screen.getByText('EL-0001')).toBeTruthy(), { timeout: 25000 })
  }, 30000)

  it('monte Inscriptions via /education/inscriptions', async () => {
    renderRoute('/education/inscriptions')
    // Le <h1> est un rendu statique (présent dès le premier commit du
    // composant, avant la résolution de `useEducationResource`) : attendre
    // dessus ne garantit PAS que la liste d'inscriptions (fetch async séparé)
    // est arrivée. « en_attente » vient de cette liste : il lui faut son
    // propre waitFor, sinon la ligne suivante course contre le chargement.
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Inscriptions' })).toBeTruthy(), { timeout: 25000 })
    await waitFor(() => expect(screen.getByText('en_attente')).toBeTruthy(), { timeout: 25000 })
  }, 30000)

  it('monte Échéancier via /education/echeancier (lecture seule)', async () => {
    renderRoute('/education/echeancier')
    await waitFor(() => expect(screen.getByText(/Total 12000.00/)).toBeTruthy(), { timeout: 25000 })
  }, 30000)

  it('monte Présences via /education/presences', async () => {
    renderRoute('/education/presences')
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Présences' })).toBeTruthy(), { timeout: 25000 })
  }, 30000)

  it('monte Notes via /education/notes', async () => {
    renderRoute('/education/notes')
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Notes' })).toBeTruthy(), { timeout: 25000 })
  }, 30000)

  it('monte Emploi du temps via /education/emploi-du-temps', async () => {
    renderRoute('/education/emploi-du-temps')
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Emploi du temps' })).toBeTruthy(), { timeout: 25000 })
  }, 30000)

  it('monte Cantine via /education/cantine avec le menu chargé', async () => {
    renderRoute('/education/cantine')
    await waitFor(() => expect(screen.getByText(/Poulet riz/)).toBeTruthy(), { timeout: 25000 })
  }, 30000)

  it('monte Discipline via /education/discipline', async () => {
    renderRoute('/education/discipline')
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Discipline' })).toBeTruthy(), { timeout: 25000 })
  }, 30000)
})
