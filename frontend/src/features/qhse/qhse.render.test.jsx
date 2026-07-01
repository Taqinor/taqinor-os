import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// jsdom n'implémente pas ResizeObserver (mesuré par recharts ResponsiveContainer
// dans les graphiques du cockpit) — on le polyfill localement.
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

/* Tests de RENDU (smoke) des écrans QHSE. On stub `qhseApi` (aucun réseau) et
   on vérifie le comportement visible (titres, KPI, colonnes) — pas
   l'implémentation. Tout est enveloppé dans MemoryRouter + ThemeProvider. */

// Stub complet du client API : chaque ressource renvoie une liste vide, le
// cockpit reçoit des réponses de forme réaliste.
vi.mock('../../api/qhseApi', () => {
  const emptyList = () => Promise.resolve({ data: [] })
  const res = (data) => Promise.resolve({ data })
  const crud = () => ({ list: emptyList, get: emptyList, create: emptyList })
  return {
    default: {
      incidents: {
        list: emptyList,
        statistiquesTfTg: () =>
          res({ tf: '6.00', tg: '0.02', accidents_avec_arret: 3 }),
      },
      iso9001Readiness: () =>
        res({
          score_global: 72,
          niveau: 'intermediaire',
          criteres: [
            { code: 'ncr_cloturees', libelle: 'NCR clôturées', clause: '10.2', score_effectif: 90, no_data: false },
            { code: 'audits', libelle: 'Audits', clause: '9.2', score_effectif: 40, no_data: false },
          ],
        }),
      calendrier: () =>
        res({
          evenements: [
            { type: 'permis', id: 1, titre: 'Permis hauteur', date: '2026-08-01', en_retard: false, reference: 'PT-1' },
          ],
        }),
      nonConformites: { list: emptyList, historique: emptyList },
      capa: { list: emptyList, enRetard: emptyList },
      plansInspection: crud(), plansChantier: crud(), releves: crud(),
      grillesAudit: crud(), audits: crud(), notationsFinChantier: crud(),
      proceduresQualite: crud(), retoursClient: crud(),
      evaluationsRisque: crud(), permisTravail: crud(), consignationsLoto: crud(),
      inductionsSecurite: crud(), plansUrgence: crud(), secouristes: crud(),
      declarationsCnss: crud(), analysesIncident: crud(),
      dechets: crud(), bordereauxDechets: crud(), recyclageModules: crud(),
      conformitesEnvironnementales: crud(), bilansCarbone: crud(),
      indicateursEsg: crud(),
    },
  }
})

import QhseCockpit from './QhseCockpit.jsx'
import NonConformites from './NonConformites.jsx'
import Inspections from './Inspections.jsx'
import Risques from './Risques.jsx'
import Environnement from './Environnement.jsx'

function renderWith(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('QhseCockpit', () => {
  it('affiche les KPI TF/TG et la readiness ISO 9001', async () => {
    renderWith(<QhseCockpit />)
    expect(screen.getByText('Cockpit QHSE')).toBeInTheDocument()
    // Les KPI de sécurité et la préparation ISO se chargent (async).
    await waitFor(() =>
      expect(screen.getByText('Taux de fréquence (TF)')).toBeInTheDocument(),
    )
    expect(
      screen.getAllByText(/Préparation ISO 9001/).length,
    ).toBeGreaterThan(0)
  })
})

describe('NonConformites', () => {
  it('rend le registre NCR avec ses onglets', async () => {
    renderWith(<NonConformites />)
    // Les deux bascules d'onglet sont présentes.
    expect(screen.getByText('Non-conformités', { selector: 'button' }))
      .toBeInTheDocument()
    expect(screen.getByText('CAPA', { selector: 'button' })).toBeInTheDocument()
    // Le titre de la ListShell NCR apparaît après chargement.
    await waitFor(() =>
      expect(
        screen.getByText('Registre NCR — création, chatter et clôture conditionnée'),
      ).toBeInTheDocument(),
    )
  })
})

describe('Écrans à onglets (montage sans crash)', () => {
  it('monte Inspections & audits avec ses onglets', () => {
    renderWith(<Inspections />)
    expect(screen.getByText('Inspections & audits')).toBeInTheDocument()
    expect(screen.getByText('Plans d’inspection (ITP)')).toBeInTheDocument()
  })

  it('monte Risques, permis & incidents', () => {
    renderWith(<Risques />)
    expect(screen.getByText('Risques, permis & incidents')).toBeInTheDocument()
    expect(screen.getByText('Document unique')).toBeInTheDocument()
  })

  it('monte Environnement & ESG', () => {
    renderWith(<Environnement />)
    expect(screen.getByText('Environnement & ESG')).toBeInTheDocument()
    expect(screen.getByText('Bilan carbone')).toBeInTheDocument()
  })
})
