import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
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
  const crud = () => ({
    list: emptyList, get: emptyList, create: emptyList, update: emptyList,
    remove: emptyList,
  })
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
      paretoDefauts: () => res({ pareto: [], premier_passage: {} }),
      nonConformites: {
        list: emptyList, historique: emptyList,
        poserDisposition: emptyList, depuisTicketSav: emptyList,
        creerIntervention: emptyList, tauxDefaillanceProduit: emptyList,
      },
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
      derogations: crud(),
      plansControleReception: crud(), pointsControleReception: crud(),
      controlesReception: { ...crud(), statuer: emptyList },
      codesDefaut: crud(),
      etapesDeclarationAt: { ...crud(), marquerFait: emptyList },
      liensSignalement: { ...crud(), qr: emptyList },
      signalementsPublics: crud(),
      observationsSecurite: {
        ...crud(), convertirCapa: emptyList, convertirNcr: emptyList,
        compteurs: emptyList,
      },
      exercicesUrgence: crud(),
      aspectsEnvironnementaux: { ...crud(), aRevoir: emptyList },
      relevesConsommation: crud(),
      coutNonQualite: () => res({ interne: null, externe: null, total: null }),
      demandesChangement: {
        ...crud(), transitionner: emptyList, creerCapa: emptyList,
        aReverser: emptyList, relancer: emptyList,
      },
      veillesReglementaires: { ...crud(), genererRevuesDues: emptyList },
      revuesVeille: { ...crud(), conclure: emptyList },
      ia: { suggestionClassification: emptyList, suggestionAnalyse: emptyList },
      causerieSecuritePdf: emptyList,
    },
  }
})

import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import authReducer from '../auth/store/authSlice'
import QhseCockpit from './QhseCockpit.jsx'
import NonConformites from './NonConformites.jsx'
import Inspections from './Inspections.jsx'
import Risques from './Risques.jsx'
import Environnement from './Environnement.jsx'

// Environnement (coût de non-qualité, XQHS22) consulte `useHasPermission`
// (react-redux) — un Provider minimal évite le crash « no store found ».
function makeStore() {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Responsable',
        permissions: [], isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderWith(ui) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter>
        <ThemeProvider>{ui}</ThemeProvider>
      </MemoryRouter>
    </Provider>,
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
  it('rend le registre NCR avec ses onglets (dont XQHS2 Dérogations)', async () => {
    renderWith(<NonConformites />)
    // Les trois bascules d'onglet sont présentes (NCR / CAPA / Dérogations).
    expect(screen.getByText('Non-conformités', { selector: 'button' }))
      .toBeInTheDocument()
    expect(screen.getByText('CAPA', { selector: 'button' })).toBeInTheDocument()
    expect(screen.getByText('Dérogations', { selector: 'button' }))
      .toBeInTheDocument()
    // Le titre de la ListShell NCR apparaît après chargement.
    await waitFor(() =>
      expect(
        screen.getByText('Registre NCR — création, chatter et clôture conditionnée'),
      ).toBeInTheDocument(),
    )
  })

  it('propose l’assistance IA (XQHS25) dans le dialogue de création NCR', async () => {
    renderWith(<NonConformites />)
    fireEvent.click(screen.getByText('Nouvelle NCR'))
    expect(
      await screen.findByText('Suggérer la gravité (IA)'),
    ).toBeInTheDocument()
  })
})

describe('Écrans à onglets (montage sans crash)', () => {
  it('monte Inspections & audits avec l’onglet Contrôle réception (XQHS3)', () => {
    renderWith(<Inspections />)
    expect(screen.getByText('Inspections & audits')).toBeInTheDocument()
    expect(screen.getByText('Plans d’inspection (ITP)')).toBeInTheDocument()
    expect(screen.getByText('Contrôle réception')).toBeInTheDocument()
  })

  it('monte Risques, permis & incidents avec Signalement QR (XQHS16) et BBS (XQHS17)', () => {
    renderWith(<Risques />)
    expect(screen.getByText('Risques, permis & incidents')).toBeInTheDocument()
    expect(screen.getByText('Document unique')).toBeInTheDocument()
    expect(screen.getByText('Signalement QR')).toBeInTheDocument()
    expect(screen.getByText('Observations BBS')).toBeInTheDocument()
  })

  it('monte Environnement & ESG avec Aspects environnementaux (XQHS20) et Changement & veille (XQHS24/26)', () => {
    renderWith(<Environnement />)
    expect(screen.getByText('Environnement & ESG')).toBeInTheDocument()
    expect(screen.getByText('Bilan carbone')).toBeInTheDocument()
    expect(screen.getByText('Aspects environnementaux')).toBeInTheDocument()
    expect(screen.getByText('Changement & veille')).toBeInTheDocument()
  })
})
