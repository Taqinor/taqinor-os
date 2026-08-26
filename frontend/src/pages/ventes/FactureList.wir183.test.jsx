import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR183 — Six actions Facture COMPLÈTES côté serveur, sans aucune UI :
   remettre-brouillon (ZFAC1), abandonner-solde (XFAC13), retour-client
   (XPOS7), facturer-pénalités (XFAC6), consolider (XFAC11) et
   encaissement-groupe (ZFAC6). Ce fichier vérifie, POUR CHACUNE, que le
   point d'entrée existe, qu'il envoie le VRAI corps attendu par le serveur,
   et qu'un refus serveur est affiché tel quel. */

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, fetchFactures: () => ({ type: 'ventes/fetchFactures/noop' }) }
})

const api = {
  remettreBrouillonFacture: vi.fn(() => Promise.resolve({ data: {} })),
  abandonnerSoldeFacture: vi.fn(() => Promise.resolve({ data: {} })),
  retourClientFacture: vi.fn(() => Promise.resolve({ data: {} })),
  facturerPenalitesFacture: vi.fn(() => Promise.resolve({ data: { reference: 'FAC-PEN-1' } })),
  consoliderFactures: vi.fn(() => Promise.resolve({ data: { reference: 'FAC-CONSO-1' } })),
  encaissementGroupeFactures: vi.fn(() => Promise.resolve({ data: [{ id: 1 }, { id: 2 }] })),
  getFacture: vi.fn(() => Promise.resolve({
    data: {
      id: 1, reference: 'FAC-2026-07-0001', montant_du: 5000,
      lignes: [
        { id: 11, designation: 'Panneau 550 W', quantite: 4, produit: 77 },
        // Ligne LIBRE (sans produit) : non retournable, jamais envoyée.
        { id: 12, designation: 'Forfait pose', quantite: 1, produit: null },
      ],
    },
  })),
  getDevis: vi.fn(() => Promise.resolve({
    data: [
      { id: 31, reference: 'DEV-1', client_nom: 'ACME', total_ttc: 3000 },
      { id: 32, reference: 'DEV-2', client_nom: 'ACME', total_ttc: 2000 },
    ],
  })),
}

vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, default: { ...actual.default, ...api } }
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

// Le toast est la SEULE surface où le message d'erreur serveur apparaît ;
// on le mocke pour l'affirmer directement (le barrel `ui` réexporte Toaster).
vi.mock('../../ui/Toaster', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    toast: { success: vi.fn(), error: vi.fn(), message: vi.fn(), info: vi.fn() },
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

import FactureList from './FactureList'
import { toast } from '../../ui/Toaster'

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

const emise = {
  id: 1, reference: 'FAC-2026-07-0001', client: 9, client_nom: 'ACME',
  statut: 'emise', date_emission: '2026-07-01', date_echeance: '2099-08-01',
  total_ttc: 5000, montant_paye: 0, montant_du: 5000,
}
const enRetard = {
  ...emise, id: 2, reference: 'FAC-RETARD', statut: 'en_retard',
  date_echeance: '2020-01-01',
}

const ouvrirMenu = async (user, reference) => {
  const row = screen.getByText(reference).closest('tr')
  await user.click(within(row).getByRole('button', { name: /Actions/ }))
}

let confirmSpy
beforeEach(() => {
  // `clearAllMocks` efface les APPELS sans toucher aux implémentations des
  // `vi.fn(() => Promise.resolve(...))` ci-dessus (`restoreAllMocks` les
  // casserait pour les tests suivants — on restaure donc le seul espion).
  vi.clearAllMocks()
  // `useConfirm()` hors provider retombe sur `window.confirm`, non implémenté
  // par jsdom : on le neutralise en « oui ».
  confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
})
afterEach(() => { confirmSpy.mockRestore() })

describe('WIR183 — ZFAC1 : remettre en brouillon', () => {
  it('appelle remettre-brouillon depuis le menu d’une facture émise', async () => {
    const user = userEvent.setup()
    renderList({ factures: [emise] })
    await ouvrirMenu(user, 'FAC-2026-07-0001')
    await user.click(await screen.findByTestId('remettre-brouillon'))
    await waitFor(() => expect(api.remettreBrouillonFacture).toHaveBeenCalledWith(1))
  })

  it('affiche TEL QUEL le refus du serveur', async () => {
    api.remettreBrouillonFacture.mockRejectedValueOnce({
      response: { data: { detail: 'Période comptable verrouillée.' } },
    })
    const user = userEvent.setup()
    renderList({ factures: [emise] })
    await ouvrirMenu(user, 'FAC-2026-07-0001')
    await user.click(await screen.findByTestId('remettre-brouillon'))
    await waitFor(() => expect(toast.error)
      .toHaveBeenCalledWith('Période comptable verrouillée.'))
  })

  it('n’est pas proposé sur une facture qui n’est pas émise', async () => {
    const user = userEvent.setup()
    renderList({ factures: [{ ...emise, statut: 'payee', montant_du: 0 }] })
    await ouvrirMenu(user, 'FAC-2026-07-0001')
    expect(screen.queryByTestId('remettre-brouillon')).toBeNull()
  })
})

describe('WIR183 — XFAC6 : facturer les pénalités de retard', () => {
  it('appelle facturer-penalites depuis une facture en retard', async () => {
    const user = userEvent.setup()
    renderList({ factures: [enRetard] })
    await ouvrirMenu(user, 'FAC-RETARD')
    await user.click(await screen.findByTestId('facturer-penalites'))
    await waitFor(() => expect(api.facturerPenalitesFacture).toHaveBeenCalledWith(2))
  })

  it('affiche TEL QUEL le refus du serveur', async () => {
    api.facturerPenalitesFacture.mockRejectedValueOnce({
      response: { data: { detail: 'Aucun niveau de relance atteint pour cette facture.' } },
    })
    const user = userEvent.setup()
    renderList({ factures: [enRetard] })
    await ouvrirMenu(user, 'FAC-RETARD')
    await user.click(await screen.findByTestId('facturer-penalites'))
    await waitFor(() => expect(toast.error)
      .toHaveBeenCalledWith('Aucun niveau de relance atteint pour cette facture.'))
  })
})

describe('WIR183 — XFAC13 : abandonner le solde', () => {
  it('envoie le motif choisi (obligatoire côté serveur)', async () => {
    const user = userEvent.setup()
    renderList({ factures: [emise] })
    await ouvrirMenu(user, 'FAC-2026-07-0001')
    await user.click(await screen.findByTestId('abandonner-solde'))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Abandonner le solde' }))
    await waitFor(() => expect(api.abandonnerSoldeFacture)
      .toHaveBeenCalledWith(1, 'irrecouvrable'))
  })

  it('affiche TEL QUEL le refus du serveur', async () => {
    api.abandonnerSoldeFacture.mockRejectedValueOnce({
      response: { data: { detail: 'Facture annulée : abandon impossible.' } },
    })
    const user = userEvent.setup()
    renderList({ factures: [emise] })
    await ouvrirMenu(user, 'FAC-2026-07-0001')
    await user.click(await screen.findByTestId('abandonner-solde'))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Abandonner le solde' }))
    await waitFor(() => expect(toast.error)
      .toHaveBeenCalledWith('Facture annulée : abandon impossible.'))
  })
})

describe('WIR183 — XPOS7 : retour client', () => {
  it('n’envoie QUE les lignes à produit, avec motif et re-stockage', async () => {
    const user = userEvent.setup()
    renderList({ factures: [emise] })
    await ouvrirMenu(user, 'FAC-2026-07-0001')
    await user.click(await screen.findByTestId('retour-client'))
    const dialog = await screen.findByRole('dialog')
    // La ligne LIBRE (sans produit) n'est pas proposée au retour.
    expect(within(dialog).queryByText('Forfait pose')).toBeNull()
    expect(within(dialog).getByText('Panneau 550 W')).toBeInTheDocument()

    await user.type(within(dialog).getByLabelText(/Motif du retour/), 'Panneau cassé')
    await user.click(within(dialog).getByRole('checkbox', { name: 'Remettre en stock' }))
    const qte = within(dialog).getAllByRole('spinbutton')[0]
    await user.clear(qte)
    await user.type(qte, '2')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer le retour' }))

    await waitFor(() => expect(api.retourClientFacture).toHaveBeenCalledWith(1, {
      motif: 'Panneau cassé',
      restocker: true,
      lignes: [{ produit: 77, quantite: '2' }],
    }))
  })

  it('affiche TEL QUEL le refus du serveur', async () => {
    api.retourClientFacture.mockRejectedValueOnce({
      response: { data: { detail: 'Ligne 1 : quantité retournée (9) supérieure à la quantité vendue.' } },
    })
    const user = userEvent.setup()
    renderList({ factures: [emise] })
    await ouvrirMenu(user, 'FAC-2026-07-0001')
    await user.click(await screen.findByTestId('retour-client'))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText(/Motif du retour/), 'Erreur')
    const qte = within(dialog).getAllByRole('spinbutton')[0]
    await user.clear(qte)
    await user.type(qte, '9')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer le retour' }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(
      'Ligne 1 : quantité retournée (9) supérieure à la quantité vendue.'))
  })
})

describe('WIR183 — XFAC11 : consolider des devis', () => {
  it('envoie les ids de DEVIS sélectionnés (jamais des ids de facture)', async () => {
    const user = userEvent.setup()
    renderList({ factures: [emise] })
    await user.click(await screen.findByRole('button', { name: 'Consolider des devis' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('checkbox', { name: 'Sélectionner le devis DEV-1' }))
    await user.click(within(dialog).getByRole('checkbox', { name: 'Sélectionner le devis DEV-2' }))
    await user.click(within(dialog).getByRole('button', { name: /Consolider \(2\)/ }))
    await waitFor(() => expect(api.consoliderFactures).toHaveBeenCalledWith([31, 32]))
  })

  it('affiche TEL QUEL le refus du serveur', async () => {
    api.consoliderFactures.mockRejectedValueOnce({
      response: { data: { detail: 'Tous les devis doivent appartenir au même client.' } },
    })
    const user = userEvent.setup()
    renderList({ factures: [emise] })
    await user.click(await screen.findByRole('button', { name: 'Consolider des devis' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('checkbox', { name: 'Sélectionner le devis DEV-1' }))
    await user.click(within(dialog).getByRole('checkbox', { name: 'Sélectionner le devis DEV-2' }))
    await user.click(within(dialog).getByRole('button', { name: /Consolider \(2\)/ }))
    await waitFor(() => expect(toast.error)
      .toHaveBeenCalledWith('Tous les devis doivent appartenir au même client.'))
  })
})

describe('WIR183 — ZFAC6 : encaissement groupé', () => {
  const deux = [emise, { ...emise, id: 3, reference: 'FAC-B', montant_du: 2000 }]

  it('envoie client, montant et la liste des factures sélectionnées', async () => {
    const user = userEvent.setup()
    renderList({ factures: deux })
    await user.click(screen.getByRole('checkbox', { name: 'Tout sélectionner' }))
    const barre = await screen.findByRole('region', { name: 'Actions factures en masse' })
    await user.click(within(barre).getByRole('button', { name: 'Encaissement groupé' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Encaisser' }))
    await waitFor(() => expect(api.encaissementGroupeFactures)
      .toHaveBeenCalledWith(expect.objectContaining({
        client: 9, factures: [1, 3], mode: 'virement',
      })))
    // Sans répartition saisie, le serveur répartit en FIFO : la clé n'est
    // même pas envoyée.
    expect(api.encaissementGroupeFactures.mock.calls[0][0])
      .not.toHaveProperty('repartition')
  })

  it('transmet la répartition forcée quand elle est saisie', async () => {
    const user = userEvent.setup()
    renderList({ factures: deux })
    await user.click(screen.getByRole('checkbox', { name: 'Tout sélectionner' }))
    const barre = await screen.findByRole('region', { name: 'Actions factures en masse' })
    await user.click(within(barre).getByRole('button', { name: 'Encaissement groupé' }))
    const dialog = await screen.findByRole('dialog')
    const champ = within(dialog).getByLabelText('Montant affecté à FAC-B')
    await user.clear(champ)
    await user.type(champ, '2000')
    await user.click(within(dialog).getByRole('button', { name: 'Encaisser' }))
    await waitFor(() => expect(api.encaissementGroupeFactures)
      .toHaveBeenCalledWith(expect.objectContaining({
        repartition: { 3: '2000' },
      })))
  })

  it('est désactivé si la sélection mélange plusieurs clients', async () => {
    const user = userEvent.setup()
    renderList({
      factures: [emise, { ...emise, id: 4, reference: 'FAC-C', client: 42 }],
    })
    await user.click(screen.getByRole('checkbox', { name: 'Tout sélectionner' }))
    const barre = await screen.findByRole('region', { name: 'Actions factures en masse' })
    expect(within(barre).getByRole('button', { name: 'Encaissement groupé' }))
      .toBeDisabled()
  })

  it('affiche TEL QUEL le refus du serveur', async () => {
    api.encaissementGroupeFactures.mockRejectedValueOnce({
      response: { data: { detail: 'Le montant dépasse le total dû des factures.' } },
    })
    const user = userEvent.setup()
    renderList({ factures: deux })
    await user.click(screen.getByRole('checkbox', { name: 'Tout sélectionner' }))
    const barre = await screen.findByRole('region', { name: 'Actions factures en masse' })
    await user.click(within(barre).getByRole('button', { name: 'Encaissement groupé' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Encaisser' }))
    await waitFor(() => expect(toast.error)
      .toHaveBeenCalledWith('Le montant dépasse le total dû des factures.'))
  })
})

describe('WIR183 — gating de palier', () => {
  it('un utilisateur du palier « normal » ne voit aucune des six actions', async () => {
    const user = userEvent.setup()
    renderList({ factures: [enRetard], role: 'normal' })
    expect(screen.queryByRole('button', { name: 'Consolider des devis' })).toBeNull()
    await ouvrirMenu(user, 'FAC-RETARD')
    expect(screen.queryByTestId('remettre-brouillon')).toBeNull()
    expect(screen.queryByTestId('facturer-penalites')).toBeNull()
    expect(screen.queryByTestId('abandonner-solde')).toBeNull()
    expect(screen.queryByTestId('retour-client')).toBeNull()
  })
})
