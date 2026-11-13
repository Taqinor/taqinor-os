import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import CONTRAT_AVOIR from '../../../../backend/django_core/apps/facturation/contract_samples/avoir.json'

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

// ASEC64 — gestes d'argent sur le droit `encaisser` (bascule par test).
const droits = vi.hoisted(() => ({ encaisser: true }))
vi.mock('../../hooks/useHasPermission', async (importOriginal) => ({
  ...(await importOriginal()),
  useHasPermission: (c) => c === 'encaisser' && droits.encaisser,
}))

// Les fabriques de `vi.mock` sont HISSÉES au-dessus des `const` du module :
// référencer `api` depuis la fabrique lèverait un ReferenceError et AUCUN test
// ne s'exécuterait (le fichier entier tombe). `vi.hoisted` remonte la
// déclaration avec elles — patron déjà en place dans ce dépôt
// (ExcelImport.wir48.test.jsx, BackgroundJobsBell.test.jsx).
const api = vi.hoisted(() => ({
  creerAvoir: vi.fn(() => Promise.resolve({ data: {} })),
  remettreBrouillonFacture: vi.fn(() => Promise.resolve({ data: {} })),
  abandonnerSoldeFacture: vi.fn(() => Promise.resolve({ data: {} })),
  retourClientFacture: vi.fn(() => Promise.resolve({ data: {} })),
  facturerPenalitesFacture: vi.fn(() => Promise.resolve({ data: { reference: 'FAC-PEN-1' } })),
  consoliderFactures: vi.fn(() => Promise.resolve({ data: { reference: 'FAC-CONSO-1' } })),
  encaissementGroupeFactures: vi.fn(() => Promise.resolve({ data: [{ id: 1 }, { id: 2 }] })),
  // AERR3 — tuiles d'argent relues après un geste d'argent.
  getFacturesKpis: vi.fn(() => Promise.resolve({ data: { encaisse_mois: '0' } })),
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
}))

vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, default: { ...actual.default, ...api } }
})

vi.mock('../../api/parametresApi', async (importOriginal) =>
  (await import('../../test/mocksVentesEcrans.js')).parametresApiProfil(await importOriginal(), { dgi_export_actif: false }))

// Le toast est la SEULE surface où le message d'erreur serveur apparaît ;
// on le mocke pour l'affirmer directement (le barrel `ui` réexporte Toaster).
vi.mock('../../ui/Toaster', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    toast: { success: vi.fn(), error: vi.fn(), message: vi.fn(), info: vi.fn() },
  }
})

vi.mock('../../api/uxviewsApi', async () =>
  (await import('../../test/mocksVentesEcrans.js')).uxviewsApiVide())

import FactureList from './FactureList'
import { renderFactureList } from './factureList.testHelpers.jsx'
import { toast } from '../../ui/Toaster'

const renderList = (opts) => renderFactureList(FactureList, opts)

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
      // ACNC3 — clé d'envoi créée à l'ouverture du dialogue (rejeu = un avoir).
      idempotency_key: expect.any(String),
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

  it('après l’encaissement groupé, la tuile Encaissé ce mois relit le serveur', async () => {
    // AERR3 (C-AERR-003) — mutant : retirer fetchFacturesKpis() du point de relecture ⇒ échec.
    const { configureStore } = await import('@reduxjs/toolkit')
    const { Provider } = await import('react-redux')
    const { MemoryRouter } = await import('react-router-dom')
    const { render } = await import('@testing-library/react')
    const ventes = (await import('../../features/ventes/store/ventesSlice')).default
    api.getFacturesKpis
      .mockResolvedValueOnce({ data: { encaisse_mois: '0' } })
      .mockResolvedValueOnce({ data: { encaisse_mois: '12000' } })
    const store = configureStore({
      reducer: { ventes, auth: (s = { role: 'admin' }) => s },
      preloadedState: { ventes: { ...ventes(undefined, { type: 'init' }), factures: [{ ...emise, total_ttc: 12000, montant_du: 12000 }] } },
    })
    const page = <ThemeProvider><FactureList /></ThemeProvider>
    render(<Provider store={store}><MemoryRouter initialEntries={['/ventes/factures']}>{page}</MemoryRouter></Provider>)
    const tuile = () => screen.getByText('Encaissé ce mois').parentElement.parentElement
    await waitFor(() => expect(api.getFacturesKpis).toHaveBeenCalledTimes(1))
    const user = userEvent.setup()
    await user.click(screen.getByRole('checkbox', { name: 'Tout sélectionner' }))
    const barre = await screen.findByRole('region', { name: 'Actions factures en masse' })
    await user.click(within(barre).getByRole('button', { name: 'Encaissement groupé' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Encaisser' }))
    await waitFor(() => expect(api.getFacturesKpis).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(tuile()).toHaveTextContent(/12\s?000/))
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

  it('deux envois après ECONNABORTED portent la même clé', async () => {
    // ACNC9 (C-ACNC-008) — mutant : régénérer la clé à chaque clic ⇒ échec.
    api.encaissementGroupeFactures.mockRejectedValueOnce({ code: 'ECONNABORTED', message: 'timeout' })
    const user = userEvent.setup()
    renderList({ factures: deux })
    await user.click(screen.getByRole('checkbox', { name: 'Tout sélectionner' }))
    const barre = await screen.findByRole('region', { name: 'Actions factures en masse' })
    await user.click(within(barre).getByRole('button', { name: 'Encaissement groupé' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Encaisser' }))
    await waitFor(() => expect(api.encaissementGroupeFactures).toHaveBeenCalledTimes(1))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Encaisser' }))
    await waitFor(() => expect(api.encaissementGroupeFactures).toHaveBeenCalledTimes(2))
    const [k1, k2] = api.encaissementGroupeFactures.mock.calls.map(([corps]) => corps.idempotency_key)
    expect(k1).toBeTruthy()
    expect(k2).toBe(k1)
  })

  it('400 montant : message sous Montant, boîte ouverte', async () => {
    // AERR13 (C-AERR-012) — mutant : remettre `erreurServeur(err, …)` ⇒ échec.
    api.encaissementGroupeFactures.mockRejectedValueOnce({
      response: { status: 400, data: { montant: ["Assurez-vous qu'il n'y a pas plus de 2 décimales."] } },
    })
    const user = userEvent.setup()
    renderList({ factures: deux })
    await user.click(screen.getByRole('checkbox', { name: 'Tout sélectionner' }))
    const barre = await screen.findByRole('region', { name: 'Actions factures en masse' })
    await user.click(within(barre).getByRole('button', { name: 'Encaissement groupé' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Encaisser' }))
    expect(await within(dialog).findByText("Assurez-vous qu'il n'y a pas plus de 2 décimales.")).toBeInTheDocument()
    expect(within(dialog).getByLabelText('Montant reçu (MAD)')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(toast.error).not.toHaveBeenCalledWith('Encaissement groupé impossible.')
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
  it('un utilisateur du palier « normal » sans `encaisser` ne voit aucune des six actions', async () => {
    droits.encaisser = false
    const user = userEvent.setup()
    renderList({ factures: [enRetard], role: 'normal' })
    expect(screen.queryByRole('button', { name: 'Consolider des devis' })).toBeNull()
    await ouvrirMenu(user, 'FAC-RETARD')
    expect(screen.queryByTestId('remettre-brouillon')).toBeNull()
    expect(screen.queryByTestId('facturer-penalites')).toBeNull()
    expect(screen.queryByTestId('abandonner-solde')).toBeNull()
    expect(screen.queryByTestId('retour-client')).toBeNull()
    droits.encaisser = true
  })

  it('ASEC64 — palier « normal » AVEC `encaisser` : les gestes d’argent, sans le palier', async () => {
    const user = userEvent.setup()
    renderList({ factures: [enRetard], role: 'normal' })
    await ouvrirMenu(user, 'FAC-RETARD')
    expect(screen.getByTestId('facturer-penalites')).toBeInTheDocument()
    expect(screen.getByTestId('abandonner-solde')).toBeInTheDocument()
    expect(screen.getByTestId('retour-client')).toBeInTheDocument()
    expect(screen.queryByTestId('remettre-brouillon')).toBeNull()
  })
})

/* ATOT36 (D-ATOT5, décision fondateur 10/10/2026) — la modale « Créer un
   avoir » envoie le `type` choisi : geste commercial par défaut (réduit le
   dû de la facture), correction sur choix (remise au solde de
   l'échéancier). Types et réponse simulée : contrat partagé `avoir.json`. */
describe('ATOT36 — type d’avoir à l’émission', () => {
  const ouvrirAvoir = async (user) => {
    const row = screen.getByText('FAC-2026-07-0001').closest('tr')
    await user.click(within(row).getByRole('button', { name: /^Avoir$/ }))
    return screen.findByTestId('avoir-type')
  }
  beforeEach(() => {
    api.creerAvoir.mockImplementation(() => Promise.resolve({ data: CONTRAT_AVOIR.exemple }))
  })

  it('propose les types du contrat (hors « retour », posé par retour-client)', async () => {
    const user = userEvent.setup()
    renderList({ factures: [emise] })
    const groupe = await ouvrirAvoir(user)
    const valeurs = within(groupe).getAllByRole('radio').map(r => r.value)
    expect(valeurs.sort()).toEqual(
      CONTRAT_AVOIR.types.filter(t => t !== 'retour').sort())
    expect(within(groupe).getByRole('radio', { checked: true }).value)
      .toBe(CONTRAT_AVOIR.type_par_defaut)
  })

  it('envoie geste_commercial par défaut', async () => {
    const user = userEvent.setup()
    renderList({ factures: [emise] })
    await ouvrirAvoir(user)
    await user.click(screen.getByRole('button', { name: 'Avoir total' }))
    await waitFor(() => expect(api.creerAvoir).toHaveBeenCalledWith(
      1, expect.objectContaining({ type: 'geste_commercial' })))
  })

  it('envoie correction quand elle est choisie', async () => {
    const user = userEvent.setup()
    renderList({ factures: [emise] })
    const groupe = await ouvrirAvoir(user)
    await user.click(within(groupe).getByRole('radio', { name: /Correction/ }))
    await user.click(screen.getByRole('button', { name: 'Avoir total' }))
    await waitFor(() => expect(api.creerAvoir).toHaveBeenCalledWith(
      1, expect.objectContaining({ type: 'correction' })))
  })
})
