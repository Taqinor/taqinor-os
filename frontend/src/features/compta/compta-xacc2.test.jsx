import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* Tests du module Comptabilité — round 2 (XACC/ZACC) :
   wiring des nouveaux écrans NotesDeFraisPage / EffetsPage / EngagementsPage
   + les nouveaux onglets ETATS/Fiscalité/Trésorerie/Rapprochements. Les appels
   API sont mockés — aucun réseau. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

vi.mock('../../api/comptaApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  const res = () => ({ list: empty, get: empty, create: empty, update: empty, remove: empty })
  return {
    default: {
      downloadBlob: vi.fn(),
      cockpit: empty,
      comptes: res(), journaux: res(), plans: res(),
      ecritures: { ...res(), valider: empty, extourner: empty },
      exercices: { ...res(), cloturer: empty, rouvrir: empty },
      tresorerie: res(),
      caisses: {
        ...res(),
        mouvementList: () => Promise.resolve({ data: [] }),
        mouvementCreer: empty,
        posterMouvement: empty,
        resume: empty,
        clotureList: empty,
        cloturer: empty,
      },
      virements: res(),
      previsionnel: res(),
      etats: {
        balance: empty, grandLivre: empty, cpc: empty, bilan: empty, esg: empty, etic: empty,
        positionTresorerie: () => Promise.resolve({ data: { comptes: [], total: 0 } }),
        previsionnelTresorerie: () => Promise.resolve({ data: { semaines: [] } }),
        balanceAgeeFournisseurs: empty,
        releveFournisseur: empty,
        tableauFlux: empty,
        tableauImmobilisations: empty,
        journalItems: empty,
        continuiteSequences: empty,
        controleIce: empty,
        dossierCloture: empty,
        exportFec: empty, liasseFiscale: empty, exportFiduciaire: empty,
        releveDeductionsTva: empty, declarationHonoraires: empty, aideIs: empty,
      },
      declarationsTva: {
        ...res(), preparer: empty, export: empty, deposer: empty,
        comparatif: empty, bordereauPdf: empty,
      },
      retenuesSource: { ...res(), verser: empty, bordereau: empty, attestation: empty, attestationAnnuelle: empty },
      timbresFiscaux: { ...res(), verser: empty },
      obligationsFiscales: { ...res(), generer: empty, rappels: () => Promise.resolve({ data: [] }) },
      effets: {
        ...res(), encaisser: empty, payer: empty, rejeter: empty,
        escompter: empty, apurerEscompte: empty, endosser: empty,
      },
      bordereaux: { ...res(), poster: empty },
      paymentRuns: { ...res(), proposer: empty, figer: empty, poster: empty, fichierVirement: empty },
      notesFrais: {
        ...res(), refacturables: empty, refacturer: empty, ocr: empty,
        soumettre: empty, valider: empty, rejeter: empty, rembourser: empty,
        recuPdf: empty, analyse: empty,
      },
      rapportsNotesFrais: { ...res(), soumettre: empty, valider: empty, rembourser: empty, recuPdf: empty },
      plafondsNotesFrais: res(),
      baremesIndemnite: res(),
      indemnitesChantier: { ...res(), soumettre: empty, valider: empty, rejeter: empty, rembourser: empty },
      retenuesGarantie: { ...res(), liberer: empty, echeances: empty },
      cautionsBancaires: { ...res(), mainlevee: empty, echeances: empty },
      contratsAvancement: { ...res(), constater: empty, avancement: empty },
      travauxEnCours: { ...res(), reprendre: empty },
      commissionPayoutRuns: { ...res(), valider: empty, poster: empty },
      compensations: { ...res(), valider: empty },
      provisionsPeriode: {
        genererFnp: empty, genererFae: empty,
        rapport: () => Promise.resolve({ data: { lignes: [] } }),
        exportCsv: empty,
      },
      pistesAudit: { list: empty, get: empty, verifier: empty, sceller: empty },
      rapprochements: {
        ...res(), lignesGl: empty, resume: empty, ajouterLigneReleve: empty,
        pointer: empty, suggestions: empty, accepterSuggestions: empty, cloturer: empty,
      },
      modelesRapprochement: { ...res(), appliquer: empty },
      rapprochements3voies: { ...res(), evaluer: empty, valider: empty },
      budgets: res(), centresCout: res(), provisionsCreances: res(),
      comptesAuxiliaires: res(), mappingsCompte: res(), piecesJustificatives: res(),
      periodes: { ...res(), cloturer: empty, rouvrir: empty },
      immobilisations: {
        ...res(), planAmortissement: empty, genererPlanAmortissement: empty,
        ceder: empty, depuisFactureFournisseur: empty,
      },
      dotations: { ...res(), poster: empty },
      cessions: { ...res(), poster: empty },
    },
  }
})

function mount(ui) {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider>{ui}</ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('NotesDeFraisPage — rendu smoke (FG135/FG136)', () => {
  it('rend le titre et les onglets', async () => {
    const { default: NotesDeFraisPage } = await import('./pages/NotesDeFraisPage.jsx')
    mount(<NotesDeFraisPage />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Notes de frais & indemnités/ })).toBeInTheDocument()
    })
    // Le libellé du 1er onglet apparaît aussi comme titre du ListShell actif — getAllByText.
    expect(screen.getAllByText('Notes de frais').length).toBeGreaterThan(0)
    expect(screen.getByText('Rapports')).toBeInTheDocument()
    expect(screen.getByText('Barèmes indemnité')).toBeInTheDocument()
  }, 30000)
})

describe('EffetsPage — rendu smoke (FG127-134)', () => {
  it('rend le titre et les onglets', async () => {
    const { default: EffetsPage } = await import('./pages/EffetsPage.jsx')
    mount(<EffetsPage />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Effets & règlements fournisseurs/ })).toBeInTheDocument()
    })
    // Le libellé du 1er onglet apparaît aussi comme titre du ListShell actif — getAllByText.
    expect(screen.getAllByText('Effets à recevoir/payer').length).toBeGreaterThan(0)
    expect(screen.getByText('Bordereaux de remise')).toBeInTheDocument()
    expect(screen.getByText('Campagnes de règlement')).toBeInTheDocument()
  }, 30000)
})

describe('EngagementsPage — rendu smoke (FG145-148/XFAC14/XACC26/COMPTA39)', () => {
  it('rend le titre et les onglets, y compris la piste d’audit pour un admin', async () => {
    const { default: EngagementsPage } = await import('./pages/EngagementsPage.jsx')
    mount(<EngagementsPage />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Engagements & clôtures avancées/ })).toBeInTheDocument()
    })
    // Le libellé du 1er onglet apparaît aussi comme titre du ListShell actif — getAllByText.
    expect(screen.getAllByText('Retenues de garantie').length).toBeGreaterThan(0)
    expect(screen.getByText('Compensations AR/AP')).toBeInTheDocument()
    expect(screen.getByText('Piste d’audit')).toBeInTheDocument()
  }, 30000)
})

describe('EtatsPage — nouveaux états ZACC round 2', () => {
  it('propose les nouveaux états dans le sélecteur', async () => {
    const { default: EtatsPage } = await import('./pages/EtatsPage.jsx')
    mount(<EtatsPage />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /États comptables/ })).toBeInTheDocument()
    })
    expect(screen.getByText('Tableau des flux')).toBeInTheDocument()
    expect(screen.getByText('Journal items')).toBeInTheDocument()
    expect(screen.getByText('Balance âgée fournisseurs')).toBeInTheDocument()
  }, 30000)
})

describe('FiscalitePage — onglet Échéances fiscales (XACC9)', () => {
  it('affiche l’onglet Échéances fiscales', async () => {
    const { default: FiscalitePage } = await import('./pages/FiscalitePage.jsx')
    mount(<FiscalitePage />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Fiscalité & déclarations/ })).toBeInTheDocument()
    })
    expect(screen.getByText('Échéances fiscales')).toBeInTheDocument()
  }, 30000)
})

describe('TresoreriePage — onglet Position & projection (FG122/FG126)', () => {
  it('affiche l’onglet position & projection', async () => {
    const { default: TresoreriePage } = await import('./pages/TresoreriePage.jsx')
    mount(<TresoreriePage />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Trésorerie & prévisionnel/ })).toBeInTheDocument()
    })
    expect(screen.getByText('Position & projection')).toBeInTheDocument()
  }, 30000)
})
