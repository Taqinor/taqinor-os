import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, render, screen, within, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// AFAC26 — les réponses simulées du lien de paiement sont LUES dans le contrat
// partagé `lien_paiement.json` (AFAC20), plus un payload inventé.
const CONTRAT_LIEN = JSON.parse(readFileSync(join(
  dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..', 'backend',
  'django_core', 'apps', 'facturation', 'contract_samples', 'lien_paiement.json'), 'utf8')).exemple
const toastMock = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), message: vi.fn(), info: vi.fn() }))
vi.mock('../../ui/Toaster', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: toastMock }
})

// WR2b — la liste des factures ne doit toucher aucun réseau pendant le test :
// on neutralise le thunk de chargement (le composant le dispatche au montage).
vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchFactures: () => ({ type: 'ventes/fetchFactures/noop' }),
    // AERR3 — la relecture après un geste relit aussi les tuiles : même neutralisation.
    fetchFacturesKpis: () => ({ type: 'ventes/fetchFacturesKpis/noop' }),
  }
})

// WR2b — espionne lienPaiementFacture / dgiExportFacture / dgiConformiteFacture
// / bulkFactures (le pouvoir de la liste factures complétant WR2).
vi.mock('../../api/ventesApi', async (importOriginal) =>
  (await import('../../test/etendreApi')).etendreApi(importOriginal, {
    lienPaiementFacture: vi.fn(() => Promise.resolve({
      // montant figé à la création ≠ montant_a_payer : l'écran annonce le second.
      data: { ...CONTRAT_LIEN, montant: '5000.00', montant_a_payer: '900.00' },
    })),
    dgiExportFacture: vi.fn(() => Promise.resolve({
      data: new Blob(['<xml/>'], { type: 'application/xml' }),
    })),
    dgiConformiteFacture: vi.fn(() => Promise.resolve({ data: { conforme: true, problemes: [] } })),
    // VNT46 — quittance d'UN paiement (GET paiements/<id>/recu-pdf/).
    recuPdfPaiement: vi.fn(() => Promise.resolve({
      data: new Blob(['%PDF'], { type: 'application/pdf' }),
      headers: { 'content-disposition': 'inline; filename="Quittance_REC-1.pdf"' },
    })),
    bulkFactures: vi.fn(() => Promise.resolve({
      data: { 1: { ok: true, detail: 'Émise.' } },
    })),
  }))

vi.mock('../../api/parametresApi', async (importOriginal) =>
  (await import('../../test/mocksVentesEcrans.js')).parametresApiProfil(await importOriginal(), { dgi_export_actif: false }))

// WIR21 — vues sauvegardées côté serveur (remplace le localStorage FG11).
vi.mock('../../api/uxviewsApi', async () =>
  (await import('../../test/mocksVentesEcrans.js')).uxviewsApiVide({ id: 1, ecran: 'ventes.factures' }))

import FactureList from './FactureList'
import ventesApi from '../../api/ventesApi'
import parametresApi from '../../api/parametresApi'
import uxviewsApi from '../../api/uxviewsApi'
// ARC53 — FactureList rend son tableau via le moteur `ui/datatable` (useDensity),
// qui EXIGE un <ThemeProvider> dans l'arbre (présent en prod via <Layout>). Ajout
// de wrapper de HARNAIS uniquement — aucune assertion n'est modifiée.
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// ASEC64 — les gestes d'argent lisent le droit `encaisser` (porté par défaut ici).
function makeStore({ factures = [], loading = false, error = null, role = 'admin', permissions = ['encaisser'] } = {}) {
  return configureStore({
    reducer: {
      ventes: (state = { factures, loading, error }) => state,
      auth: (state = { role, permissions }) => state,
    },
  })
}

function renderList(opts) {
  const store = makeStore(opts)
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/factures']}>
        <ThemeProvider>
          <FactureList />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('FactureList — lien profond ?id= ouvert directement', () => {
  it('attend la liste avant de chercher la facture, puis ouvre sa fiche', async () => {
    const f = { id: 77, reference: 'FAC-2026-07-0077', client_nom: 'ACME', statut: 'emise',
      date_emission: '2026-07-01', date_echeance: '2026-08-01', total_ttc: 5000, montant_paye: 0, montant_du: 5000 }
    const base = makeStore({ factures: [] }).getState()
    const store = configureStore({
      reducer: (etat = base, action) => (action.type === 'essai/charge'
        ? { ...etat, ventes: { ...etat.ventes, factures: [f] } } : etat),
      middleware: (d) => d({ serializableCheck: false, immutableCheck: false }),
    })
    render(
      <Provider store={store}>
        <MemoryRouter initialEntries={['/ventes/factures?id=77']}>
          <ThemeProvider>
            <FactureList />
          </ThemeProvider>
        </MemoryRouter>
      </Provider>,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    act(() => { store.dispatch({ type: 'essai/charge' }) })
    expect(await screen.findByRole('dialog')).toHaveTextContent('Éditer — FAC-2026-07-0077')
  })
})

const baseFacture = {
  id: 1, reference: 'FAC-2026-07-0001', client_nom: 'ACME', statut: 'emise',
  date_emission: '2026-07-01', date_echeance: '2026-08-01',
  total_ttc: 5000, montant_paye: 0, montant_du: 5000,
}

describe('FactureList — AERR15 : raccourci « a » de la fiche facture', () => {
  it('boîte par-dessus le formulaire : « a » ne génère pas', async () => {
    // AERR15 (C-AERR-013) — mutant : retirer `{ scopeRef }` ⇒ échec.
    const pdf = vi.spyOn(ventesApi, 'genererPdfFacture').mockResolvedValue({ data: {} })
    // Brouillon : « Nouveau client » (la boîte posée par-dessus) n'est actif
    // qu'en brouillon (horsBrouillon ⇒ bouton désactivé).
    const f = { id: 5, reference: 'FAC-AERR15', client_nom: 'ACME', statut: 'brouillon',
      date_emission: '2026-07-01', date_echeance: '2026-08-01', total_ttc: 5000, montant_paye: 0, montant_du: 5000 }
    render(
      <Provider store={makeStore({ factures: [f] })}>
        <MemoryRouter initialEntries={['/ventes/factures?id=5']}>
          <ThemeProvider><FactureList /></ThemeProvider>
        </MemoryRouter>
      </Provider>,
    )
    await screen.findByRole('dialog')
    fireEvent.click(screen.getByRole('button', { name: /Nouveau client/ }))
    // La boîte du dessus rend celle du formulaire aria-hidden : on compte les deux.
    await waitFor(() => expect(screen.getAllByRole('dialog', { hidden: true }).length).toBeGreaterThan(1))
    fireEvent.keyDown(document.body, { key: 'a' })
    await new Promise((r) => setTimeout(r, 0))
    expect(pdf).not.toHaveBeenCalled()
    pdf.mockRestore()
  })
})

describe('FactureList — AERR17 : émettre une ligne demande confirmation', () => {
  it('Émettre d\'une ligne brouillon : confirmation nommée, Annuler ⇒ aucune émission', async () => {
    // AERR17 (C-AERR-015) — mutant : retirer le `confirmMsg` ⇒ échec.
    const emettre = vi.spyOn(ventesApi, 'emettreFacture').mockResolvedValue({ data: {} })
    const { ConfirmProvider } = await import('../../providers/ConfirmProvider.jsx')
    const f = { ...baseFacture, id: 12, reference: 'BROUILLON-12', statut: 'brouillon', total_ttc: 5000 }
    render(
      <Provider store={makeStore({ factures: [f] })}>
        <MemoryRouter initialEntries={['/ventes/factures']}>
          <ThemeProvider><ConfirmProvider><FactureList /></ConfirmProvider></ThemeProvider>
        </MemoryRouter>
      </Provider>,
    )
    const row = screen.getByText('BROUILLON-12').closest('tr')
    fireEvent.click(within(row).getByRole('button', { name: /Émettre/ }))
    const boite = await screen.findByRole('alertdialog')
    expect(boite).toHaveTextContent('Émettre la facture BROUILLON-12')
    expect(boite).toHaveTextContent('Un numéro légal lui sera attribué.')
    fireEvent.click(within(boite).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(emettre).not.toHaveBeenCalled()
    emettre.mockRestore()
  })
})

describe('FactureList — AERR20 : « Marquer payée sans détail »', () => {
  it('motif vide : boîte ouverte + erreur sous Motif ; refus serveur : motif gardé', async () => {
    // AERR20 (C-AERR-018) — mutant : remettre `setPayeeSecheMotif('')` avant le test ⇒ échec.
    const marquer = vi.spyOn(ventesApi, 'marquerPayeeFacture')
      .mockRejectedValue({ response: { status: 400, data: { detail: 'Refusé.' } } })
    const user = userEvent.setup()
    renderList({ factures: [{ ...baseFacture, id: 42, reference: 'FAC-2026-11-0042' }] })
    const row = screen.getByText('FAC-2026-11-0042').closest('tr')
    await user.click(within(row).getByRole('button', { name: /Actions/ }))
    await user.click(await screen.findByTestId('marquer-payee'))
    const boite = await screen.findByRole('alertdialog')
    await user.click(within(boite).getByRole('button', { name: 'Marquer payée quand même' }))
    expect(within(boite).getByText(/Motif obligatoire/)).toBeInTheDocument()
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(marquer).not.toHaveBeenCalled()

    await user.type(within(boite).getByLabelText(/Motif/), 'virement hors ERP')
    await user.click(within(boite).getByRole('button', { name: 'Marquer payée quand même' }))
    await waitFor(() => expect(marquer).toHaveBeenCalledWith(42, 'virement hors ERP'))
    await waitFor(() => expect(toastMock.error).toHaveBeenCalled())
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(within(screen.getByRole('alertdialog')).getByLabelText(/Motif/)).toHaveValue('virement hors ERP')
    marquer.mockRestore()
  })
})

describe('FactureList — WIR21 : vues sauvegardées côté serveur', () => {
  it('affiche le bouton « Vues » (ViewsManagerPopover) et charge les vues serveur', async () => {
    renderList({ factures: [baseFacture] })
    expect(await screen.findByTestId('uxviews-open-btn')).toBeInTheDocument()
    await waitFor(() => expect(uxviewsApi.listSavedViews).toHaveBeenCalledWith('ventes.factures', expect.objectContaining({ page: 1 })))
  })

  it('« Enregistrer cette vue » crée une SavedView serveur (ecran ventes.factures)', async () => {
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('Factures en retard')
    renderList({ factures: [baseFacture] })
    fireEvent.click(await screen.findByRole('button', { name: /Enregistrer cette vue/ }))
    await waitFor(() => expect(uxviewsApi.createSavedView).toHaveBeenCalledWith(expect.objectContaining({
      ecran: 'ventes.factures', nom: 'Factures en retard', visibilite: 'PERSONNELLE',
    })))
    promptSpy.mockRestore()
  })
})

describe('FactureList — AERR1 : relecture en cours ou ratée après un geste', () => {
  it('relecture rejetée : les lignes restent, avis + Réessayer, boîte Paiement montée', async () => {
    const trois = [1, 2, 3].map((i) => ({ ...baseFacture, id: i, reference: `FAC-AERR1-000${i}` }))
    const base = makeStore({ factures: trois }).getState()
    const store = configureStore({
      reducer: (etat = base, action) => {
        if (action.type === 'essai/relecture') return { ...etat, ventes: { ...etat.ventes, loading: true, error: null } }
        if (action.type === 'essai/rejet') return { ...etat, ventes: { ...etat.ventes, loading: false, error: 'Réseau' } }
        return etat
      },
      middleware: (d) => d({ serializableCheck: false, immutableCheck: false }),
    })
    render(
      <Provider store={store}>
        <MemoryRouter initialEntries={['/ventes/factures']}>
          <ThemeProvider><FactureList /></ThemeProvider>
        </MemoryRouter>
      </Provider>,
    )
    const row = screen.getByText('FAC-AERR1-0001').closest('tr')
    fireEvent.click(within(row).getByRole('button', { name: /Encaisser/ }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    act(() => { store.dispatch({ type: 'essai/relecture' }) })
    expect(screen.getByText('FAC-AERR1-0003')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    act(() => { store.dispatch({ type: 'essai/rejet' }) })
    for (const i of [1, 2, 3]) expect(screen.getByText(`FAC-AERR1-000${i}`)).toBeInTheDocument()
    const avis = screen.getByTestId('factures-pas-a-jour')
    expect(avis).toHaveTextContent('Liste pas à jour')
    // La boîte Paiement est modale : le reste de la page est aria-hidden.
    expect(within(avis).getByRole('button', { name: 'Réessayer', hidden: true })).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.queryByText('Erreur de chargement')).toBeNull()
  })
})

describe('FactureList — WR2b : « Payer en ligne »', () => {
  it('crée le lien de paiement et le copie au presse-papier', async () => {
    const writeText = vi.fn(() => Promise.resolve())
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    renderList({ factures: [{ ...baseFacture }] })
    const row = screen.getByText('FAC-2026-07-0001').closest('tr')
    fireEvent.click(within(row).getByRole('button', { name: /Payer en ligne/ }))
    await waitFor(() => {
      expect(ventesApi.lienPaiementFacture).toHaveBeenCalledWith(1)
    })
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(CONTRAT_LIEN.pay_url)
    })
  })

  it('Payer en ligne, writeText rejeté : pas de « Création … impossible », action Ouvrir', async () => {
    // AERR10 (C-AERR-010) — mutant : remettre la copie dans le `try` commun ⇒ échec.
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: vi.fn(() => Promise.reject(new Error('refus'))) }, configurable: true })
    toastMock.error.mockClear()
    renderList({ factures: [{ ...baseFacture }] })
    const row = screen.getByText('FAC-2026-07-0001').closest('tr')
    fireEvent.click(within(row).getByRole('button', { name: /Payer en ligne/ }))
    // Le toast du lien est cherché parmi tous les appels : un toast réseau parasite
    // (« Connexion perdue ») peut arriver après lui sous charge (file de merge #1389).
    const appels = toastMock.error.mock.calls
    await waitFor(() => expect(appels.some(([m]) => String(m).includes(CONTRAT_LIEN.pay_url))).toBe(true))
    expect(appels.some(([m]) => /Création du lien de paiement impossible/.test(String(m)))).toBe(false)
    const [, opts] = appels.find(([m]) => String(m).includes(CONTRAT_LIEN.pay_url))
    expect(opts?.action?.label).toBe('Ouvrir')
  })

  it('le toast annonce montant_a_payer', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: vi.fn(() => Promise.resolve()) }, configurable: true })
    renderList({ factures: [{ ...baseFacture }] })
    const row = screen.getByText('FAC-2026-07-0001').closest('tr')
    fireEvent.click(within(row).getByRole('button', { name: /Payer en ligne/ }))
    await waitFor(() => expect(toastMock.success).toHaveBeenCalled())
    const msg = toastMock.success.mock.calls.at(-1)[0]
    expect(msg).toMatch(/900,00/)
    expect(msg).not.toMatch(/5\s?000/)
  })

  it('pas de bouton Payer en ligne si exigible nul', () => {
    renderList({
      factures: [{ ...baseFacture, id: 3, reference: 'FAC-RETENUE', montant_du: 10000, montant_exigible: '0.00' }],
    })
    const row = screen.getByText('FAC-RETENUE').closest('tr')
    expect(within(row).queryByRole('button', { name: /Payer en ligne/ })).toBeNull()
    expect(within(row).getByRole('button', { name: /Encaisser/ })).toBeInTheDocument()
  })

  it('n\'affiche pas le bouton quand la facture est déjà soldée', () => {
    renderList({
      factures: [{ ...baseFacture, id: 2, reference: 'FAC-SOLDEE', montant_du: 0, encaissable: false }],
    })
    const row = screen.getByText('FAC-SOLDEE').closest('tr')
    expect(within(row).queryByRole('button', { name: /Payer en ligne/ })).toBeNull()
  })
})

describe('FactureList — WR2b : Export DGI + badge conformité (gated par dgi_export_actif)', () => {
  it('masque le bouton Export DGI et le badge conformité quand le flag société est OFF', async () => {
    const user = userEvent.setup()
    renderList({ factures: [{ ...baseFacture }] })
    await waitFor(() => expect(parametresApi.getProfile).toHaveBeenCalled())
    const row = screen.getByText('FAC-2026-07-0001').closest('tr')
    expect(within(row).queryByText(/Conformité DGI/)).toBeNull()
    await user.click(within(row).getByRole('button', { name: 'Actions' }))
    expect(screen.queryByText(/Export DGI/)).toBeNull()
  })

  it('affiche le badge conformité et l\'action Export DGI quand le flag société est ON', async () => {
    const user = userEvent.setup()
    parametresApi.getProfile.mockResolvedValueOnce({ data: { dgi_export_actif: true } })
    // ADRG18 — l'Export DGI exige `ventes_export` (code de sa route).
    renderList({ factures: [{ ...baseFacture }], permissions: ['encaisser', 'ventes_export'] })
    const row = await screen.findByText('FAC-2026-07-0001').then(el => el.closest('tr'))
    await waitFor(() => {
      expect(within(row).getByText(/Conformité DGI/)).toBeVisible()
    })
    await user.click(within(row).getByRole('button', { name: 'Actions' }))
    const exportItem = await screen.findByRole('menuitem', { name: /Export DGI/ })
    await user.click(exportItem)
    await waitFor(() => {
      expect(ventesApi.dgiExportFacture).toHaveBeenCalledWith(1)
    })
  })

  it('le clic sur le badge conformité appelle le contrôle DGI (aucun statut modifié)', async () => {
    parametresApi.getProfile.mockResolvedValueOnce({ data: { dgi_export_actif: true } })
    renderList({ factures: [{ ...baseFacture }] })
    const row = await screen.findByText('FAC-2026-07-0001').then(el => el.closest('tr'))
    const badge = await waitFor(() => within(row).getByText(/Conformité DGI/))
    fireEvent.click(badge)
    await waitFor(() => {
      expect(ventesApi.dgiConformiteFacture).toHaveBeenCalledWith(1)
    })
  })
})

describe('FactureList — WR2b : barre d\'actions en masse (bulkFactures)', () => {
  beforeEach(() => { ventesApi.bulkFactures.mockClear() })

  it('sélectionne une facture puis lance « Émettre » en masse via bulkFactures', async () => {
    renderList({
      factures: [
        { ...baseFacture, id: 1, reference: 'FAC-BULK-1', statut: 'brouillon' },
        { ...baseFacture, id: 2, reference: 'FAC-BULK-2', statut: 'brouillon' },
      ],
    })
    const row1 = screen.getByText('FAC-BULK-1').closest('tr')
    fireEvent.click(within(row1).getByRole('checkbox', { name: /Sélectionner la facture FAC-BULK-1/ }))

    const bulkBar = screen.getByRole('region', { name: 'Actions factures en masse' })
    expect(within(bulkBar).getByText('1')).toBeVisible()
    // AERR7 — l'émission en masse est confirmée (repli hors provider : window.confirm).
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    fireEvent.click(within(bulkBar).getByRole('button', { name: 'Émettre' }))

    await waitFor(() => {
      expect(ventesApi.bulkFactures).toHaveBeenCalledWith('emettre', [1])
    })
    confirmSpy.mockRestore()
  })

  it('Émettre en masse : confirmation nommée, Annuler ⇒ aucun bulkFactures', async () => {
    // AERR7 (C-AERR-007) — mutant : retirer l'`await confirm(` ⇒ échec.
    const { ConfirmProvider } = await import('../../providers/ConfirmProvider.jsx')
    const store = makeStore({
      factures: [
        { ...baseFacture, id: 1, reference: 'FAC-BULK-1', statut: 'brouillon' },
        { ...baseFacture, id: 2, reference: 'FAC-BULK-2', statut: 'brouillon' },
      ],
    })
    render(
      <Provider store={store}>
        <MemoryRouter initialEntries={['/ventes/factures']}>
          <ThemeProvider><ConfirmProvider><FactureList /></ConfirmProvider></ThemeProvider>
        </MemoryRouter>
      </Provider>,
    )
    fireEvent.click(screen.getByRole('checkbox', { name: 'Tout sélectionner' }))
    const bulkBar = screen.getByRole('region', { name: 'Actions factures en masse' })
    fireEvent.click(within(bulkBar).getByRole('button', { name: 'Émettre' }))
    const boite = await screen.findByRole('alertdialog')
    expect(boite).toHaveTextContent('Émettre 2 factures ?')
    expect(boite).toHaveTextContent('FAC-BULK-1, FAC-BULK-2')
    fireEvent.click(within(boite).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(ventesApi.bulkFactures).not.toHaveBeenCalled()
    expect(within(bulkBar).getByText('2')).toBeVisible()

    fireEvent.click(within(bulkBar).getByRole('button', { name: 'Émettre' }))
    fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(ventesApi.bulkFactures).toHaveBeenCalledWith('emettre', [1, 2]))
  })

  it('bulk partiel : raison de la refusée affichée, sélection = la refusée', async () => {
    // AERR8 (C-AERR-008) — mutant : remettre `clearSelection()` en échec partiel ⇒ échec.
    ventesApi.bulkFactures.mockResolvedValueOnce({
      data: { 1: { ok: true }, 2: { ok: true }, 3: { ok: false, detail: 'ICE du client manquant.' } },
    })
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderList({
      factures: [1, 2, 3].map(i => ({ ...baseFacture, id: i, reference: `FAC-LOT-${i}`, statut: 'brouillon' })),
    })
    fireEvent.click(screen.getByRole('checkbox', { name: 'Tout sélectionner' }))
    const bulkBar = screen.getByRole('region', { name: 'Actions factures en masse' })
    fireEvent.click(within(bulkBar).getByRole('button', { name: 'Émettre' }))
    await waitFor(() => expect(toastMock.error).toHaveBeenCalled())
    const msg = toastMock.error.mock.calls.at(-1)[0]
    expect(msg).toMatch(/FAC-LOT-3 : ICE du client manquant\./)
    expect(msg).not.toMatch(/FAC-LOT-1/)
    await waitFor(() => expect(within(bulkBar).getByText('1')).toBeVisible())
    expect(screen.getByRole('checkbox', { name: /Sélectionner la facture FAC-LOT-3/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /Sélectionner la facture FAC-LOT-1/ })).not.toBeChecked()
    confirmSpy.mockRestore()
  })

  it('tout sélectionner coche toutes les lignes filtrées', () => {
    renderList({
      factures: [
        { ...baseFacture, id: 1, reference: 'FAC-ALL-1' },
        { ...baseFacture, id: 2, reference: 'FAC-ALL-2' },
      ],
    })
    fireEvent.click(screen.getByRole('checkbox', { name: 'Tout sélectionner' }))
    const bulkBar = screen.getByRole('region', { name: 'Actions factures en masse' })
    expect(within(bulkBar).getByText('2')).toBeVisible()
  })
})

describe('FactureList — ZFAC9 : bascule Liste/Kanban', () => {
  it('la vue Liste (tableau) est affichée par défaut', () => {
    renderList({ factures: [{ ...baseFacture }] })
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.queryByTestId('facture-kanban-board')).not.toBeInTheDocument()
  })

  it('basculer sur Kanban masque le tableau et regroupe par colonne (même onglet/dérivation)', async () => {
    const user = userEvent.setup()
    renderList({
      factures: [
        { ...baseFacture, id: 1, reference: 'FAC-K-1', statut: 'brouillon' },
        { ...baseFacture, id: 2, reference: 'FAC-K-2', statut: 'payee', montant_du: 0 },
      ],
    })
    await user.click(screen.getByRole('button', { name: /Kanban/ }))
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByTestId('facture-kanban-board')).toBeInTheDocument()
    expect(screen.getByTestId('fkb-count-brouillon')).toHaveTextContent('1')
    expect(screen.getByTestId('fkb-count-payee')).toHaveTextContent('1')
    expect(screen.getByText('FAC-K-1')).toBeInTheDocument()
    expect(screen.getByText('FAC-K-2')).toBeInTheDocument()
  })

  it('revenir sur Liste réaffiche le tableau', async () => {
    const user = userEvent.setup()
    renderList({ factures: [{ ...baseFacture }] })
    await user.click(screen.getByRole('button', { name: /Kanban/ }))
    await user.click(screen.getByRole('button', { name: /^Liste/ }))
    expect(screen.getByRole('table')).toBeInTheDocument()
  })
})

describe('FactureList — VX142(a) : toolbar « Exporter » unique, plus de window.prompt', () => {
  it('le menu « Exporter » regroupe Exporter Excel / Journal comptable / Export comptable / Audit numérotation', async () => {
    const user = userEvent.setup()
    const promptSpy = vi.spyOn(window, 'prompt')
    // ADRG18 — « Exporter Excel » exige `ventes_export` (code de sa route).
    renderList({ factures: [{ ...baseFacture }], permissions: ['encaisser', 'ventes_export'] })
    await user.click(screen.getByRole('button', { name: /^Exporter$/ }))
    expect(screen.getByRole('menuitem', { name: /Exporter Excel/ })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: /Journal comptable/ })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: /Export comptable/ })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: /Audit numérotation/ })).toBeVisible()
    expect(promptSpy).not.toHaveBeenCalled()
  })

  it('« Journal comptable… » ouvre un Dialog mois/trimestre, jamais window.prompt', async () => {
    const user = userEvent.setup()
    const promptSpy = vi.spyOn(window, 'prompt')
    renderList({ factures: [{ ...baseFacture }] })
    await user.click(screen.getByRole('button', { name: /^Exporter$/ }))
    await user.click(screen.getByRole('menuitem', { name: /Journal comptable/ }))
    expect(screen.getByRole('heading', { name: 'Journal comptable' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Mois' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Trimestre' })).toBeVisible()
    expect(promptSpy).not.toHaveBeenCalled()
  })

  it('à 00:30 le 1er décembre (heure du Maroc), le journal propose 2025-12', async () => {
    // AERR18 (C-AERR-016) — mutant : remettre `toISOString().slice(0, 7)` ⇒ échec (UTC = la veille).
    vi.useFakeTimers({ toFake: ['Date'] })
    // 2025 et non 2026 : UTC+1 dans TOUTES les bases tz (avant le décret 2.26.530
    // du 20/09/2026 — la base tz du runner CI place fin 2026 à UTC+0 ; cf. dateLocale.test.mjs).
    vi.setSystemTime(new Date('2025-11-30T23:30:00Z')) // 00:30 à Casablanca (UTC+1)
    try {
      const user = userEvent.setup()
      renderList({ factures: [{ ...baseFacture }] })
      await user.click(screen.getByRole('button', { name: /^Exporter$/ }))
      await user.click(screen.getByRole('menuitem', { name: /Journal comptable/ }))
      expect(await screen.findByLabelText('Mois du journal')).toHaveValue('2025-12')
    } finally {
      vi.useRealTimers()
    }
  })

  it('« Export comptable… » ouvre un Dialog à deux champs date, jamais window.prompt', async () => {
    const user = userEvent.setup()
    const promptSpy = vi.spyOn(window, 'prompt')
    renderList({ factures: [{ ...baseFacture }] })
    await user.click(screen.getByRole('button', { name: /^Exporter$/ }))
    await user.click(screen.getByRole('menuitem', { name: /Export comptable/ }))
    expect(screen.getByRole('heading', { name: 'Export comptable' })).toBeVisible()
    expect(screen.getByLabelText('Date de début')).toBeVisible()
    expect(screen.getByLabelText('Date de fin')).toBeVisible()
    expect(promptSpy).not.toHaveBeenCalled()
  })
})

describe('FactureList — VX142(b) : nextBestAction en position 1, style distinct', () => {
  it('une facture brouillon montre « Émettre » recommandé en PREMIER bouton de la rangée', () => {
    renderList({
      factures: [{ ...baseFacture, id: 2, reference: 'FAC-NBA-1', statut: 'brouillon', montant_du: 0 }],
    })
    const row = screen.getByText('FAC-NBA-1').closest('tr')
    const actionsCell = row.cells[row.cells.length - 1]
    const buttons = within(actionsCell).getAllByRole('button')
    expect(buttons[0]).toHaveAccessibleName(/Émettre/)
    expect(buttons[0]).toHaveAttribute('title', 'Action recommandée')
    // Une seule occurrence du bouton Émettre (pas de doublon plus loin dans la rangée).
    expect(within(actionsCell).getAllByRole('button', { name: /Émettre/ })).toHaveLength(1)
  })

  it('une facture émise partiellement payée montre « Encaisser » recommandé en PREMIER, sans doublon', () => {
    renderList({
      factures: [{
        ...baseFacture, id: 3, reference: 'FAC-NBA-2', statut: 'emise',
        date_echeance: '2099-01-01', montant_paye: 1000, montant_du: 4000,
      }],
    })
    const row = screen.getByText('FAC-NBA-2').closest('tr')
    const actionsCell = row.cells[row.cells.length - 1]
    const buttons = within(actionsCell).getAllByRole('button')
    expect(buttons[0]).toHaveAccessibleName(/Encaisser/)
    // « Enregistrer paiement » (position historique) ne réapparaît pas à côté.
    expect(within(actionsCell).queryByRole('button', { name: /Enregistrer paiement/ })).toBeNull()
  })
})

/* ============================================================================
   ARC49-FIX — LA LISTE DES FACTURES SUR TÉLÉPHONE
   Bug de production : sous 768 px, /ventes/factures n'affichait RIEN. Le moteur
   `ui/datatable` masque son conteneur `data-dt-table` (`hidden dt-desktop:block`)
   et ne compensait par le repli en cartes `data-dt-cards` que si l'écran ne
   passe ni `renderRow`, ni `hideMobileCards`, ni `groupBy` — or FactureList
   passe `renderRow`. Ni table, ni carte : écran blanc. L'invariant GÉNÉRIQUE est
   gardé dans src/ui/datatable/DataTable.test.jsx (§ ARC49-FIX) ; ce test-ci le
   verrouille sur l'ÉCRAN réellement signalé.
   ========================================================================== */
describe('FactureList — ARC49-FIX : la liste reste visible sur téléphone (< 768 px)', () => {
  it('les lignes de factures restent peintes sous 768 px', () => {
    const { container } = renderList({ factures: [baseFacture] })
    const conteneurTable = container.querySelector('[data-dt-table]')
    expect(conteneurTable).toBeTruthy()
    // FactureList passe `renderRow` : le moteur n'émet AUCUNE carte mobile.
    expect(container.querySelector('[data-dt-cards]')).toBeNull()
    // La table est donc le SEUL rendu possible des lignes : son conteneur ne
    // doit pas porter `hidden` (display:none à TOUTE largeur), sinon l'écran est
    // littéralement vide sur téléphone.
    expect(conteneurTable.className.split(/\s+/)).not.toContain('hidden')
    // …et c'est bien lui qui porte la facture.
    expect(within(conteneurTable).getByText('FAC-2026-07-0001')).toBeInTheDocument()
    // Le rendu « cartes » sur téléphone vient de la CSS `.data-table`
    // (@media max-width:768px, index.css : thead masqué + td::before =
    // attr(data-label)) — règles inopérantes tant qu'un ANCÊTRE est masqué.
    expect(conteneurTable.querySelector('table').className).toContain('data-table')
  })
})


/* ============================================================================
   VNT46 (D-VNT-1) — gestes de la facture dans la LISTE : Annuler / Supprimer
   réservés au palier responsable/admin (PEUT_ANNULER côté serveur), Supprimer
   seulement sur un BROUILLON-<id>, un Reçu PAR paiement encaissé.
   ========================================================================== */
describe('FactureList — VNT46 : annuler / supprimer / reçu par paiement', () => {
  const brouillonProvisoire = {
    ...baseFacture, id: 5, reference: 'BROUILLON-5', statut: 'brouillon', total_ttc: 14700, montant_du: 14700,
  }
  const brouillonLegal = { ...brouillonProvisoire, id: 6, reference: 'FAC-2026-10-0006' }

  it('Commercial : ni Annuler ni Supprimer dans le menu', async () => {
    const user = userEvent.setup()
    renderList({ factures: [brouillonProvisoire, baseFacture], role: 'normal' })
    for (const ref of ['BROUILLON-5', 'FAC-2026-07-0001']) {
      const row = screen.getByText(ref).closest('tr')
      await user.click(within(row).getByTitle("Plus d'actions"))
      await screen.findByRole('menu')
      expect(screen.queryByTestId('annuler-facture')).toBeNull()
      expect(screen.queryByTestId('supprimer-brouillon')).toBeNull()
      await user.keyboard('{Escape}')
    }
  })

  it('responsable : Supprimer sur BROUILLON-<id>, pas sur un brouillon à numéro légal', async () => {
    const user = userEvent.setup()
    renderList({ factures: [brouillonProvisoire, brouillonLegal], role: 'responsable' })
    let row = screen.getByText('BROUILLON-5').closest('tr')
    await user.click(within(row).getByTitle("Plus d'actions"))
    expect(await screen.findByTestId('supprimer-brouillon')).toBeInTheDocument()
    expect(screen.getByTestId('annuler-facture')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    row = screen.getByText('FAC-2026-10-0006').closest('tr')
    await user.click(within(row).getByTitle("Plus d'actions"))
    await screen.findByTestId('annuler-facture')
    expect(screen.queryByTestId('supprimer-brouillon')).toBeNull()
  })

  it('Reçu : un bouton par paiement encaissé, appelle GET paiements/<id>/recu-pdf/', async () => {
    const user = userEvent.setup()
    const payee = { ...baseFacture, id: 7, reference: 'FAC-2026-07-0007', montant_paye: 5000, montant_du: 0,
      paiements: [
        { id: 31, statut: 'encaisse', montant: '5000.00', date_paiement: '2026-07-10', numero_recu: 'REC-1' },
        { id: 32, statut: 'rejete', montant: '900.00', date_paiement: '2026-07-11' },
      ] }
    renderList({ factures: [payee] })
    const row = screen.getByText('FAC-2026-07-0007').closest('tr')
    const boutons = within(row).getAllByTestId('recu-paiement')
    expect(boutons).toHaveLength(1)
    await user.click(boutons[0])
    await waitFor(() => expect(ventesApi.recuPdfPaiement).toHaveBeenCalledWith(31))
  })
})
