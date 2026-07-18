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
        // WIR32 — `list`/`creerIntervention`/`tauxDefaillanceProduit` sont des
        // vi.fn() (au lieu de la simple fonction `emptyList` partagée) pour
        // que les tests NcrDetail (pont NCR↔SAV) puissent surcharger la
        // réponse et vérifier les appels.
        list: vi.fn(emptyList), historique: emptyList,
        poserDisposition: emptyList, depuisTicketSav: emptyList,
        creerIntervention: vi.fn(() => Promise.resolve({ data: {} })),
        tauxDefaillanceProduit: vi.fn(emptyList),
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
      // WIR32 — `create` en vi.fn() : dialogue de création de dérogation.
      derogations: { ...crud(), create: vi.fn(() => Promise.resolve({ data: {} })) },
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
import qhseApi from '../../api/qhseApi'
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

describe('NonConformites — NcrDetail (WIR32 — pont NCR↔SAV + dérogation)', () => {
  const ncrRow = {
    id: 7, reference: 'NCR-0007', titre: 'Casse verre', statut: 'ouverte',
    gravite: 'majeure', chantier_id: 42, date_detection: '2026-07-01',
    date_creation: '2026-07-01', disposition: null,
  }

  // DataTable rend à la fois la table desktop et le repli carte mobile (CSS
  // seul, `dt-desktop:hidden` — les deux existent dans le DOM en jsdom) :
  // on cible toujours le PREMIER match (`getAllByText(...)[0]`), même patron
  // que KbParcoursPage.test.jsx.
  async function ouvrirNcr() {
    const matches = await screen.findAllByText('Casse verre')
    fireEvent.click(matches[0])
  }

  it('ouvre une intervention SAV depuis la NCR (creerIntervention, jusqu’ici sans appelant)', async () => {
    qhseApi.nonConformites.list.mockResolvedValueOnce({ data: [ncrRow] })
    qhseApi.nonConformites.creerIntervention.mockResolvedValueOnce({
      data: { ticket_id: 9, ticket_reference: 'SAV-0009', created: true },
    })
    renderWith(<NonConformites />)
    await ouvrirNcr()
    const btn = await screen.findByRole(
      'button', { name: /Créer une intervention SAV/ })
    fireEvent.click(btn)
    await waitFor(() => expect(qhseApi.nonConformites.creerIntervention)
      .toHaveBeenCalledWith(7, {}))
  })

  it('affiche le taux de défaillance produit dans son onglet (tauxDefaillanceProduit)', async () => {
    qhseApi.nonConformites.list.mockResolvedValueOnce({ data: [ncrRow] })
    qhseApi.nonConformites.tauxDefaillanceProduit.mockResolvedValueOnce({
      data: [{ produit_id: 3, produit_nom: 'Onduleur Huawei', nb_ncr: 4 }],
    })
    renderWith(<NonConformites />)
    await ouvrirNcr()
    fireEvent.click(await screen.findByText('Taux de défaillance produit'))
    expect(await screen.findByText('Onduleur Huawei')).toBeInTheDocument()
    expect(screen.getByText('4 NCR')).toBeInTheDocument()
  })

  it('crée une dérogation depuis la NCR (DerogationsRegister n’était que lecture seule)', async () => {
    qhseApi.nonConformites.list.mockResolvedValueOnce({ data: [ncrRow] })
    renderWith(<NonConformites />)
    await ouvrirNcr()
    fireEvent.click(await screen.findByRole(
      'button', { name: /Créer une dérogation/ }))
    fireEvent.change(
      await screen.findByPlaceholderText("Justification de l'acceptation en l'état"),
      { target: { value: 'Tolérance client validée' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer la dérogation' }))
    await waitFor(() => expect(qhseApi.derogations.create).toHaveBeenCalledWith(
      expect.objectContaining({
        non_conformite: 7, justification: 'Tolérance client validée',
      })))
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
