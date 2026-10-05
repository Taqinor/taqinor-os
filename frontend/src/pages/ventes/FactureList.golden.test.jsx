/* SPL193 — GOLDEN de FactureList (aucun déplacement) : DOM de `document.body`
   (liste, kanban, états de ligne, dialogues) + journal ORDONNÉ des appels du
   flux d'export comptable (handleExportComptable, handleJournalComptable,
   handleAuditNumerotation, sondage pollExportJobAndDownload).

   Les golden vivent dans `factureList/__golden__/` ; ils ne sont JAMAIS
   régénérés après capture (`CI=true vitest run` : toMatchFileSnapshot n'écrit
   alors rien et échoue au moindre écart). SPL211/SPL212 doivent passer sans
   aucune mise à jour.

   `today` est calculé au CHARGEMENT du module (FactureList.jsx) : la date est
   figée par `vi.hoisted` AVANT le premier import. Les mocks sont ceux de
   FactureList.test.jsx (ventesSlice, ventesApi, parametresApi, uxviewsApi) +
   l'axios partagé et les sorties navigateur (jamais la source testée). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, within, fireEvent, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

const T0 = '2026-07-15T10:00:00.000Z'

// Doit s'exécuter AVANT l'import de FactureList (`today` au niveau module).
vi.hoisted(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-07-15T10:00:00.000Z'))
})

const journal = vi.hoisted(() => ({ lignes: [] }))
const noter = (...a) => journal.lignes.push(a)

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  exportStatus: vi.fn(),
  journalVentes: vi.fn(),
  auditNumerotation: vi.fn(),
  openPdfBlob: vi.fn(),
  downloadXlsx: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn(), message: vi.fn(), info: vi.fn() },
}))

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, fetchFactures: () => ({ type: 'ventes/fetchFactures/noop' }) }
})

vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      lienPaiementFacture: vi.fn(() => Promise.resolve({ data: {} })),
      dgiExportFacture: vi.fn(() => Promise.resolve({ data: new Blob(['<xml/>']) })),
      dgiConformiteFacture: vi.fn(() => Promise.resolve({ data: { conforme: true, problemes: [] } })),
      bulkFactures: vi.fn(() => Promise.resolve({ data: {} })),
      getFacture: vi.fn(() => Promise.resolve({
        data: {
          id: 1, reference: 'FAC-2026-07-0001', montant_du: 5000,
          lignes: [{ id: 11, designation: 'Panneau 550 W', quantite: 4, produit: 77 }],
        },
      })),
      getDevis: vi.fn(() => Promise.resolve({
        data: [{ id: 31, reference: 'DEV-1', client_nom: 'ACME', total_ttc: 3000 }],
      })),
      whatsappFacture: vi.fn(() => Promise.resolve({
        data: { message: 'Bonjour ACME', url: 'https://x.example/f/1', wa_url: 'https://wa.me/1' },
      })),
      getNotesDebit: vi.fn(() => Promise.resolve({ data: [] })),
      journalVentes: mocks.journalVentes,
      auditNumerotation: mocks.auditNumerotation,
      exportStatus: mocks.exportStatus,
    },
  }
})

vi.mock('../../api/parametresApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getProfile: vi.fn(() => Promise.resolve({ data: { dgi_export_actif: false } })),
    },
  }
})

vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listSavedViews: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    createSavedView: vi.fn(() => Promise.resolve({ data: {} })),
    updateSavedView: vi.fn(() => Promise.resolve({ data: {} })),
    deleteSavedView: vi.fn(() => Promise.resolve({})),
  },
}))

// Réseau axios partagé (export comptable + historique du dialogue de paiement).
vi.mock('../../api/axios', () => ({
  default: { get: mocks.apiGet, post: vi.fn(() => Promise.resolve({ data: {} })) },
}))

// Sorties navigateur : on les JOURNALISE (jamais la source testée).
vi.mock('../../utils/pdfBlob', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, openPdfBlob: mocks.openPdfBlob }
})
vi.mock('../../api/importApi', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, downloadXlsx: mocks.downloadXlsx }
})
vi.mock('../../ui/Toaster', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: mocks.toast }
})

import FactureList from './FactureList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const GOLDEN = './factureList/__golden__/'

// ── Normalisation du DOM ────────────────────────────────────────────────────
// ids `useId` (`:r1:`, `«r1»`, `radix-…`) : numérotation dépendante de l'ordre
// de rendu -> remplacés par un jeton stable.
const normaliser = (html) => html
  .replace(/(?:«|:)r[0-9a-z]+(?:»|:)/g, 'ID')
  .replace(/></g, '>\n<')
  .concat('\n')

const snap = () => normaliser(document.body.innerHTML)

function renderList({ factures = [], role = 'admin' } = {}) {
  const store = configureStore({
    reducer: {
      ventes: (s = { factures, loading: false, error: null }) => s,
      auth: (s = { role }) => s,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/factures']}>
        <ThemeProvider><FactureList /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

const base = {
  client: 9, client_nom: 'ACME', client_telephone: '+212600000000', date_emission: '2026-07-01',
  total_ttc: 5000, montant_paye: 0, montant_du: 5000,
}
const FACTURES = [
  { ...base, id: 1, reference: 'FAC-2026-07-0001', statut: 'emise', date_echeance: '2026-08-01' },
  { ...base, id: 2, reference: 'FAC-BROUILLON', statut: 'brouillon', date_echeance: '2026-08-01' },
  { ...base, id: 3, reference: 'FAC-PARTIELLE', statut: 'emise', date_echeance: '2026-08-01',
    montant_paye: 2000, montant_du: 3000 },
  { ...base, id: 4, reference: 'FAC-PAYEE', statut: 'payee', date_echeance: '2026-08-01',
    montant_paye: 5000, montant_du: 0 },
  { ...base, id: 5, reference: 'FAC-RETARD', statut: 'en_retard', date_echeance: '2026-06-01' },
]

const menuLigne = async (user, reference) => {
  const row = screen.getByText(reference).closest('tr')
  await user.click(within(row).getByRole('button', { name: /Actions/ }))
}
const menuExporter = async (user) => {
  await user.click(screen.getByRole('button', { name: /Exporter/ }))
}

const figerDate = () => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(T0))
}

let confirmSpy
beforeEach(() => {
  vi.clearAllMocks()
  journal.lignes.length = 0
  confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
  mocks.apiGet.mockImplementation((url) => Promise.resolve(
    String(url).includes('/historique/')
      ? { status: 200, data: [] }
      : { status: 200, data: new Blob(['x']) }))
  mocks.journalVentes.mockImplementation(() => Promise.resolve({ status: 200, data: new Blob(['x']) }))
  mocks.auditNumerotation.mockImplementation(() => Promise.resolve({ data: { conforme: true } }))
  mocks.openPdfBlob.mockImplementation((_b, nom) => noter('openPdfBlob', nom))
  mocks.downloadXlsx.mockImplementation((_b, nom) => noter('downloadXlsx', nom))
})
afterEach(() => {
  confirmSpy.mockRestore()
  cleanup()
  vi.useRealTimers()
  figerDate()
})

describe('FactureList — golden DOM', () => {
  it('liste : états de ligne (brouillon, émise, partielle, payée, en retard)', async () => {
    renderList({ factures: FACTURES })
    await screen.findByText('FAC-RETARD')
    await expect(snap()).toMatchFileSnapshot(`${GOLDEN}factureList.liste.html`)
  })

  it('kanban', async () => {
    const user = userEvent.setup()
    renderList({ factures: FACTURES })
    await user.click(screen.getByRole('button', { name: /Kanban/ }))
    await expect(snap()).toMatchFileSnapshot(`${GOLDEN}factureList.kanban.html`)
  })

  it('dialogues : paiement, avoir, abandon, retour, consolider, encaissement groupé, export comptable, journal, WhatsApp, note de débit', async () => {
    const sections = []
    const capter = async (nom, ouvrir, attendre) => {
      const user = userEvent.setup()
      renderList({ factures: FACTURES })
      await screen.findByText('FAC-RETARD')
      await ouvrir(user)
      await attendre()
      sections.push(`<!-- ===== ${nom} ===== -->\n${snap()}`)
      cleanup()
    }
    const dialogue = () => screen.findByRole('dialog')

    await capter('paiement', async (user) => {
      const row = screen.getByText('FAC-2026-07-0001').closest('tr')
      await user.click(within(row).getByRole('button', { name: /Encaisser/ }))
    }, dialogue)

    await capter('avoir', async (user) => {
      const row = screen.getByText('FAC-2026-07-0001').closest('tr')
      await user.click(within(row).getByRole('button', { name: /^Avoir$/ }))
    }, dialogue)

    await capter('abandon', async (user) => {
      await menuLigne(user, 'FAC-2026-07-0001')
      await user.click(await screen.findByTestId('abandonner-solde'))
    }, dialogue)

    await capter('retour', async (user) => {
      await menuLigne(user, 'FAC-2026-07-0001')
      await user.click(await screen.findByTestId('retour-client'))
    }, async () => { await dialogue(); await screen.findByText('Panneau 550 W') })

    await capter('consolider', async (user) => {
      await user.click(screen.getByRole('button', { name: 'Consolider des devis' }))
    }, async () => { await dialogue(); await screen.findByText('DEV-1') })

    await capter('encaissement-groupe', async (user) => {
      const row = screen.getByText('FAC-2026-07-0001').closest('tr')
      await user.click(within(row).getByRole('checkbox'))
      await user.click(await screen.findByRole('button', { name: 'Encaissement groupé' }))
    }, dialogue)

    await capter('export-comptable', async (user) => {
      await menuExporter(user)
      await user.click(await screen.findByRole('menuitem', { name: /Export comptable/ }))
    }, dialogue)

    await capter('journal', async (user) => {
      await menuExporter(user)
      await user.click(await screen.findByRole('menuitem', { name: /Journal comptable/ }))
    }, dialogue)

    await capter('whatsapp', async (user) => {
      await menuLigne(user, 'FAC-2026-07-0001')
      await user.click(await screen.findByRole('menuitem', { name: /WhatsApp/ }))
    }, async () => { await dialogue(); await screen.findByText(/Bonjour ACME/) })

    await capter('note-debit', async (user) => {
      await menuLigne(user, 'FAC-2026-07-0001')
      await user.click(await screen.findByRole('menuitem', { name: /Note de débit/ }))
    }, dialogue)

    expect(sections).toHaveLength(10)
    await expect(sections.join('\n')).toMatchFileSnapshot(`${GOLDEN}factureList.dialogues.html`)
  })
})

// ── Flux d'export comptable : journal ordonné des appels ───────────────────
const flux = {}

const lireAppels = () => ({
  apiGet: mocks.apiGet.mock.calls
    .filter(([url]) => String(url).includes('/export-comptable/'))
    .map(([url, opts]) => [url, opts]),
  journalVentes: mocks.journalVentes.mock.calls,
  exportStatus: mocks.exportStatus.mock.calls,
  auditNumerotation: mocks.auditNumerotation.mock.calls.length,
  toast: Object.fromEntries(
    Object.entries(mocks.toast).map(([k, f]) => [k, f.mock.calls]).filter(([, c]) => c.length)),
  sorties: [...journal.lignes],
})

const reponse202 = (jobId) => ({
  status: 202,
  data: { text: () => Promise.resolve(JSON.stringify({ job_id: jobId })) },
})

async function soumettreDialogue(user, ouvrirMenu, libelle, bouton) {
  await menuExporter(user)
  await user.click(await screen.findByRole('menuitem', { name: ouvrirMenu }))
  const dlg = await screen.findByRole('dialog')
  return { dlg, bouton: within(dlg).getByRole('button', { name: bouton }), libelle }
}

describe('FactureList — golden flux export comptable', () => {
  it('export comptable : xlsx synchrone puis csv', async () => {
    const user = userEvent.setup()
    renderList({ factures: FACTURES })
    await screen.findByText('FAC-RETARD')
    const { dlg, bouton } = await soumettreDialogue(user, /Export comptable/, 'export', /^Télécharger$/)
    expect(within(dlg).getByLabelText('Date de début')).toBeInTheDocument()
    await user.click(bouton)
    await waitFor(() => expect(lireAppels().apiGet.length).toBe(2))
    await waitFor(() => expect(journal.lignes.length).toBe(2))
    flux.exportComptableSync = lireAppels()
    expect(flux.exportComptableSync.apiGet.length).toBe(2)
  })

  it('journal des ventes : mois, synchrone', async () => {
    const user = userEvent.setup()
    renderList({ factures: FACTURES })
    await screen.findByText('FAC-RETARD')
    const { bouton } = await soumettreDialogue(user, /Journal comptable/, 'journal', /^Télécharger$/)
    await user.click(bouton)
    await waitFor(() => expect(mocks.journalVentes).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(journal.lignes.length).toBe(1))
    flux.journalSync = lireAppels()
  })

  it('audit de numérotation : conforme, puis anomalies', async () => {
    const user = userEvent.setup()
    renderList({ factures: FACTURES })
    await screen.findByText('FAC-RETARD')
    await menuExporter(user)
    await user.click(await screen.findByRole('menuitem', { name: /Audit numérotation/ }))
    await waitFor(() => expect(mocks.toast.success).toHaveBeenCalledTimes(1))
    mocks.auditNumerotation.mockImplementationOnce(() => Promise.resolve({
      data: {
        conforme: false, total_manquants: 1, total_doublons: 1,
        facture: [{ radical: 'FAC-2026-07', manquants: ['0002'], doublons: ['0003'] }],
      },
    }))
    await menuExporter(user)
    await user.click(await screen.findByRole('menuitem', { name: /Audit numérotation/ }))
    await waitFor(() => expect(mocks.toast.error).toHaveBeenCalledTimes(1))
    flux.auditNumerotation = lireAppels()
  })

  it('sondage de job : pending, pending, ready -> téléchargement', async () => {
    const clics = []
    const clic = vi.spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function () { clics.push([this.href, this.download]) })

    const user = userEvent.setup()
    renderList({ factures: FACTURES })
    await screen.findByText('FAC-RETARD')
    mocks.journalVentes.mockImplementation(() => Promise.resolve(reponse202('JOB-1')))
    const { bouton } = await soumettreDialogue(user, /Journal comptable/, 'journal', /^Télécharger$/)
    const statuts = [{ status: 'pending' }, { status: 'pending' },
      { status: 'ready', download_url: 'https://dl.example/j.xlsx', filename: 'journal.xlsx' }]
    mocks.exportStatus.mockImplementation(() => Promise.resolve({ data: statuts.shift() }))

    // Minuteurs factices UNIQUEMENT pour le sondage (Date reste figée).
    vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'] })
    vi.setSystemTime(new Date(T0))
    fireEvent.click(bouton)
    for (let i = 0; i < 3; i += 1) await vi.advanceTimersByTimeAsync(2000)
    await vi.advanceTimersByTimeAsync(0)
    flux.sondagePret = { ...lireAppels(), clics: [...clics], minuteursRestants: vi.getTimerCount() }
    expect(clics.length).toBe(1)
    clic.mockRestore()
  })

  it('sondage de job : job « pending » au-delà de 5 min -> échec signalé', async () => {
    const user = userEvent.setup()
    renderList({ factures: FACTURES })
    await screen.findByText('FAC-RETARD')
    mocks.journalVentes.mockImplementation(() => Promise.resolve(reponse202('JOB-2')))
    mocks.exportStatus.mockImplementation(() => Promise.resolve({ data: { status: 'pending' } }))
    const { bouton } = await soumettreDialogue(user, /Journal comptable/, 'journal', /^Télécharger$/)

    vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'] })
    vi.setSystemTime(new Date(T0))
    fireEvent.click(bouton)
    await vi.advanceTimersByTimeAsync(5 * 60 * 1000 + 4000)
    await vi.advanceTimersByTimeAsync(0)
    flux.sondageTimeout = {
      ...lireAppels(),
      // 150 sondages identiques : on fige leurs arguments distincts + le compte.
      exportStatus: [...new Set(mocks.exportStatus.mock.calls.map(c => JSON.stringify(c)))],
      nbSondages: mocks.exportStatus.mock.calls.length,
      minuteursRestants: vi.getTimerCount(),
    }
    expect(mocks.toast.error).toHaveBeenCalledTimes(1)
  })

  it('journal ordonné des appels (golden)', async () => {
    const contenu = JSON.stringify(flux, null, 1) + '\n'
    await expect(contenu).toMatchFileSnapshot(`${GOLDEN}factureList.flux.json`)
  })
})
