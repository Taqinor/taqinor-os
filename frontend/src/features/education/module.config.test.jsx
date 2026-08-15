import { describe, it, expect, beforeAll, vi } from 'vitest'
import { Suspense } from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
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
      // WIR212/NTEDU38 — galerie photo : un élève SANS photo renvoie
      // `photo_url: null` (avatar générique attendu côté écran).
      trombinoscope: () => Promise.resolve({
        data: {
          count: 2,
          results: [
            { id: 1, nom: 'Alami', prenom: 'Sara', photo_url: '/api/django/records/attachments/7/download/' },
            { id: 2, nom: 'Bennani', prenom: 'Omar', photo_url: null },
          ],
        },
      }),
    },
    // WIR212/NTEDU17 — périodes de notation + bulletins (publication NTEDU33).
    periodes: {
      list: () => Promise.resolve({
        data: [{ id: 3, annee_scolaire: 1, libelle: 'Trimestre 1', ordre: 1,
          date_debut: '2026-09-01', date_fin: '2026-12-15' }],
      }),
      create: () => Promise.resolve({ data: { id: 4 } }),
    },
    bulletins: {
      list: () => Promise.resolve({
        data: [{ id: 20, eleve: 1, periode: 3, appreciation_generale: 'Bon trimestre.',
          publie: false, date_publication: null }],
      }),
      create: () => Promise.resolve({ data: { id: 21 } }),
      update: () => Promise.resolve({ data: { id: 20 } }),
      publier: () => Promise.resolve({ data: { id: 20, publie: true } }),
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
      // WIR212/NTEDU17 — bulletin PDF (blob).
      bulletinPdf: () => Promise.resolve({ data: new Blob(['%PDF']), headers: {} }),
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
  '/education/import',
  // WIR212 — l'écran « Périodes & bulletins » : sans lui, la publication d'un
  // bulletin (seul chemin d'écriture de `publie`) n'existait que dans l'admin.
  '/education/bulletins',
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
  // NTEDU36 — 10e route/entrée de nav ajoutée (Import CSV élèves).
  it('déclare les 10 routes ET les 10 entrées de nav ÉDUCATION, gatées', () => {
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

  it('monte Import via /education/import (NTEDU36)', async () => {
    renderRoute('/education/import')
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Import CSV élèves' })).toBeTruthy(), { timeout: 25000 })
    expect(screen.getByRole('button', { name: 'Importer un fichier' })).toBeTruthy()
  }, 30000)

  // ── WIR212 — bulletins publiables + trombinoscope atteignable ───────────
  it('monte Périodes & bulletins via /education/bulletins', async () => {
    renderRoute('/education/bulletins')
    await waitFor(
      () => expect(screen.getByRole('heading', { name: 'Périodes & bulletins' })).toBeTruthy(),
      { timeout: 25000 })
  }, 30000)

  it('WIR212 — publier un bulletin passe par l’action serveur dédiée', async () => {
    const { default: educationApi } = await import('../../api/educationApi')
    const spyPublier = vi.spyOn(educationApi.bulletins, 'publier')
    renderRoute('/education/bulletins')
    const select = await screen.findByTestId('edu-periode-select', {}, { timeout: 25000 })
    fireEvent.change(select, { target: { value: '3' } })
    // Le bulletin 20 existe déjà pour l'élève 1 sur la période 3 → publiable.
    const btn = await screen.findByTestId('edu-bulletin-publier-1')
    expect(btn).not.toBeDisabled()
    fireEvent.click(btn)
    await waitFor(() => expect(spyPublier).toHaveBeenCalledWith(20))
  }, 30000)

  it('WIR212 — le PDF de bulletin part avec la période choisie', async () => {
    const { default: educationApi } = await import('../../api/educationApi')
    const spyPdf = vi.spyOn(educationApi.eleves, 'bulletinPdf')
    renderRoute('/education/bulletins')
    const select = await screen.findByTestId('edu-periode-select', {}, { timeout: 25000 })
    fireEvent.change(select, { target: { value: '3' } })
    fireEvent.click(await screen.findByTestId('edu-bulletin-pdf-1'))
    await waitFor(() => expect(spyPdf).toHaveBeenCalledWith(1, '3'))
  }, 30000)

  it('WIR212/NTEDU38 — le trombinoscope est ATTEIGNABLE depuis Structure', async () => {
    renderRoute('/education/structure')
    await waitFor(() => expect(screen.getByText('CE1-A')).toBeTruthy(), { timeout: 25000 })
    fireEvent.click(screen.getByTestId('edu-trombinoscope-1'))
    await waitFor(() => expect(screen.getByTestId('edu-trombinoscope')).toBeTruthy())
    expect(screen.getAllByTestId('edu-trombinoscope-eleve')).toHaveLength(2)
    // Élève sans photo → avatar générique (initiales), jamais une image cassée.
    expect(screen.getByTestId('edu-trombinoscope-avatar-2')).toBeTruthy()
    expect(screen.getByAltText('Sara Alami')).toBeTruthy()
  }, 30000)
})
