import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   WIR192 — rapprochement 3 voies (XPUR10) : une facture en exception était
   invisible et inrésolvable depuis l'écran. Badge `statut_controle` + file
   « En exception », action « Résoudre l'exception » (Responsable/Admin).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getFacturesFournisseur: vi.fn(() => Promise.resolve({
      data: [
        { id: 1, reference: 'FF-1', fournisseur_nom: 'JA Solar', statut: 'a_payer', statut_controle: 'normale', montant_ttc: '1000', solde_du: '1000' },
        {
          id: 2, reference: 'FF-2', fournisseur_nom: 'Sunrak', statut: 'a_payer',
          statut_controle: 'exception', motif_ecart: 'Écart de 500 MAD vs BCF-2',
          montant_ttc: '2000', solde_du: '2000',
        },
      ],
    })),
    getFacturesEnException: vi.fn(() => Promise.resolve({
      data: [{
        id: 2, reference: 'FF-2', fournisseur_nom: 'Sunrak', statut: 'a_payer',
        statut_controle: 'exception', motif_ecart: 'Écart de 500 MAD vs BCF-2',
        montant_ttc: '2000', solde_du: '2000',
      }],
    })),
    resoudreExceptionFacture: vi.fn(() => Promise.resolve({
      data: {
        id: 2, reference: 'FF-2', statut: 'a_payer', statut_controle: 'resolue',
        montant_ttc: '2000', total_paye: '0', solde_du: '2000', paiements: [],
      },
    })),
    getFactureFournisseur: vi.fn((id) => Promise.resolve({
      data: {
        id, reference: `FF-${id}`, statut: 'a_payer', statut_controle: 'exception',
        motif_ecart: 'Écart de 500 MAD vs BCF-2',
        montant_ttc: '2000', total_paye: '0', solde_du: '2000', paiements: [],
      },
    })),
    getAllFournisseurs: vi.fn(() => Promise.resolve({ data: [] })),
    getBonsCommandeFournisseur: vi.fn(() => Promise.resolve({ data: [] })),
    // AUDV04 — acomptes fournisseur ouverts (chargés au montage, panneau
    // optionnel affiché uniquement si des lignes existent).
    acomptesFournisseurOuverts: vi.fn(() => Promise.resolve({ data: [] })),
    createFactureFournisseur: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
    ajouterPaiementFournisseur: vi.fn(() => Promise.reject(new Error('Network Error'))),
  },
}))

import stockApi from '../../api/stockApi'
import FacturesFournisseur, { FactureDetail, NouvelleFacture } from './FacturesFournisseur.jsx'

function makeStore({ role = 'admin' } = {}) {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: { user: { id: 1 }, role, role_nom: role, permissions: [], isAuthenticated: true, loading: false },
    },
  })
}

function renderPage(store = makeStore()) {
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><FacturesFournisseur /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('FacturesFournisseur — badge et file « En exception » (WIR192)', () => {
  it('affiche le badge « En exception » sur la ligne concernée, infobulle = motif_ecart', async () => {
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Factures fournisseur' })
    const badge = within(grid).getByText('En exception')
    expect(badge.closest('[title]')).toHaveAttribute('title', 'Écart de 500 MAD vs BCF-2')
  })

  it('le bouton « En exception » charge la file dédiée', async () => {
    renderPage()
    await screen.findByRole('grid', { name: 'Factures fournisseur' })

    // Le repli « cartes mobiles » du DataTable rend chaque ligne cliquable en
    // `role="button"` : la carte FF-2 porte le badge « En exception » dans son
    // nom accessible. On vise donc le bouton de filtre par son nom EXACT.
    await userEvent.click(screen.getByRole('button', { name: 'En exception' }))
    await waitFor(() => expect(stockApi.getFacturesEnException).toHaveBeenCalled())
    const grid = await screen.findByRole('grid', { name: 'Factures fournisseur' })
    expect(within(grid).getByText('FF-2')).toBeInTheDocument()
    expect(within(grid).queryByText('FF-1')).toBeNull()
  })
})

describe('FactureDetail — résoudre une exception (WIR192)', () => {
  const factureException = {
    id: 2, reference: 'FF-2', statut: 'a_payer', statut_controle: 'exception',
    motif_ecart: 'Écart de 500 MAD vs BCF-2',
    fournisseur_nom: 'Sunrak', montant_ttc: '2000', total_paye: '0', solde_du: '2000',
    paiements: [],
  }

  it('affiche le motif de l\'écart et le bouton « Résoudre l\'exception » (Responsable/Admin)', () => {
    // `canResoudre` est un PROP simple (jamais un hook Redux) : ce composant
    // se monte sans Provider, comme dans wr4ReceptionFacture.test.jsx.
    render(<ThemeProvider>
      <FactureDetail facture={factureException} canResoudre onClose={() => {}} onSaved={() => {}} />
    </ThemeProvider>)
    expect(screen.getByText('Écart de 500 MAD vs BCF-2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Résoudre l'exception/ })).toBeInTheDocument()
  })

  it('sans le droit (canResoudre=false), aucun bouton de résolution n\'apparaît', () => {
    render(<ThemeProvider>
      <FactureDetail facture={factureException} canResoudre={false} onClose={() => {}} onSaved={() => {}} />
    </ThemeProvider>)
    expect(screen.queryByRole('button', { name: /Résoudre l'exception/ })).toBeNull()
  })

  it('confirmer la résolution appelle resoudreExceptionFacture et sort la facture de la file', async () => {
    const onSaved = vi.fn()
    render(<ThemeProvider>
      <FactureDetail facture={factureException} canResoudre onClose={() => {}} onSaved={onSaved} />
    </ThemeProvider>)

    await userEvent.click(screen.getByRole('button', { name: /Résoudre l'exception/ }))
    await userEvent.type(screen.getByPlaceholderText('Commentaire de résolution (optionnel)'), 'Vérifié avec le fournisseur')
    await userEvent.click(screen.getByRole('button', { name: 'Confirmer la résolution' }))

    await waitFor(() => expect(stockApi.resoudreExceptionFacture).toHaveBeenCalledWith(
      2, { commentaire: 'Vérifié avec le fournisseur' },
    ))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    // La facture résolue ne montre plus le bandeau/bouton d'exception.
    expect(screen.queryByRole('button', { name: /Résoudre l'exception/ })).toBeNull()
  })
})

/* ASTK105 (C-ASTK-035) — la grille du détail boucle : TTC − payé − acomptes
   imputés − avoirs imputés = solde dû (clés déjà servies par le serializer). */
describe('FactureDetail — chaîne du solde (ASTK105)', () => {
  it('la chaîne du solde boucle', () => {
    const facture = {
      id: 5, reference: 'FF-5', statut: 'partiellement_payee', statut_controle: 'normale',
      fournisseur_nom: 'JA Solar', montant_ttc: '12000.00', total_paye: '1000.00',
      total_acomptes_imputes: '3600.00', total_avoirs_imputes: '0.00', solde_du: '7400.00',
      paiements: [],
    }
    render(<ThemeProvider>
      <FactureDetail facture={facture} onClose={() => {}} onSaved={() => {}} />
    </ThemeProvider>)
    const valeur = (libelle) => screen.getByText(libelle).parentElement.textContent
    expect(valeur('Total TTC')).toMatch(/12\s?000,00/)
    expect(valeur('Déjà payé')).toMatch(/1\s?000,00/)
    expect(valeur('Acomptes imputés')).toMatch(/3\s?600,00/)
    expect(valeur('Avoirs imputés')).toMatch(/0,00/)
    expect(valeur('Solde dû')).toMatch(/7\s?400,00/)
  })
})

/* ACNC73 (C-ACNC-VER3-300) — réponse perdue sur « Ajouter le paiement » : la
   fiche relit la facture (règlement passé + solde relu) avant tout second clic. */
describe('FactureDetail — réponse perdue sur un règlement (ACNC73)', () => {
  it('réponse perdue : la fiche relit la facture et montre le règlement', async () => {
    const user = userEvent.setup()
    const base = { id: 7, reference: 'FF-7', statut: 'a_payer', statut_controle: 'normale',
      fournisseur_nom: 'JA Solar', montant_ttc: '10000.00', total_paye: '0.00', solde_du: '10000.00' }
    stockApi.getFactureFournisseur.mockResolvedValueOnce({ data: { ...base, statut: 'partiellement_payee',
      total_paye: '3000.00', solde_du: '7000.00',
      paiements: [{ id: 1, montant: '3000.00', date_paiement: '2026-11-15', mode: 'virement' }] } })
    render(<ThemeProvider>
      <FactureDetail facture={{ ...base, paiements: [] }} onClose={() => {}} onSaved={() => {}} />
    </ThemeProvider>)
    await user.type(screen.getByLabelText('Montant'), '3000')
    await user.click(screen.getByRole('button', { name: 'Ajouter le paiement' }))
    await waitFor(() => expect(stockApi.getFactureFournisseur).toHaveBeenCalledWith(7))
    await waitFor(() => expect(screen.queryByText('Aucun paiement.')).toBeNull())
    expect(screen.getByText('Déjà payé').parentElement.textContent).toMatch(/3\s?000,00/)
    expect(screen.getByText('Solde dû').parentElement.textContent).toMatch(/7\s?000,00/)
  })
})

/* ACNC74 (C-ACNC-VER4-400, D-ACNC-1) — règlement identique du jour : la phrase serveur
   s'affiche et « Confirmer » renvoie avec `confirmer_doublon` (mutant : l'ignorer ⇒ échec). */
describe('FactureDetail — règlement identique (ACNC74)', () => {
  it('409 paiement_similaire : phrase serveur puis « Confirmer » renvoie avec confirmer_doublon', async () => {
    const user = userEvent.setup()
    const PHRASE = "Un règlement de 3 000 MAD a déjà été enregistré aujourd'hui sur cette facture : confirmer ?"
    const base = { id: 8, reference: 'FF-8', statut: 'partiellement_payee', statut_controle: 'normale',
      fournisseur_nom: 'JA Solar', montant_ttc: '10000.00', total_paye: '3000.00', solde_du: '7000.00', paiements: [] }
    stockApi.ajouterPaiementFournisseur
      .mockRejectedValueOnce({ response: { status: 409, data: { code: 'paiement_similaire', detail: PHRASE } } })
      .mockResolvedValueOnce({ data: { ...base, total_paye: '6000.00', solde_du: '4000.00' } })
    render(<ThemeProvider>
      <FactureDetail facture={base} onClose={() => {}} onSaved={() => {}} />
    </ThemeProvider>)
    await user.type(screen.getByLabelText('Montant'), '3000')
    await user.click(screen.getByRole('button', { name: 'Ajouter le paiement' }))
    expect(await screen.findByText(PHRASE)).toBeInTheDocument()
    expect(screen.queryByText("L'enregistrement du paiement a échoué.")).toBeNull()
    const [, c1, o1] = stockApi.ajouterPaiementFournisseur.mock.calls.at(-1)
    expect(c1.confirmer_doublon).toBeUndefined()
    await user.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(screen.queryByText(PHRASE)).toBeNull())
    const [, c2, o2] = stockApi.ajouterPaiementFournisseur.mock.calls.at(-1)
    expect(c2).toMatchObject({ montant: 3000, confirmer_doublon: true })
    expect(o2.idempotencyKey).toBe(o1.idempotencyKey)
    expect(screen.getByText('Solde dû').parentElement.textContent).toMatch(/4\s?000,00/)
  })
})

describe('FacturesFournisseur — acomptes ouverts réservés à prix_achat_voir (ASTK255, rejeu)', () => {
  it('un compte à rôle fin SANS prix_achat_voir ne demande pas les acomptes ouverts (403 évité)', async () => {
    stockApi.acomptesFournisseurOuverts.mockClear()
    const store = configureStore({
      reducer: { auth: authReducer },
      preloadedState: {
        auth: { user: { id: 2 }, role: 'normal', role_nom: 'Commercial', permissions: ['achats_payer'], isAuthenticated: true, loading: false },
      },
    })
    renderPage(store)
    await screen.findByRole('grid', { name: 'Factures fournisseur' })
    expect(stockApi.acomptesFournisseurOuverts).not.toHaveBeenCalled()
  })

  it('un compte avec prix_achat_voir (ou légacy sans codes) les demande toujours', async () => {
    stockApi.acomptesFournisseurOuverts.mockClear()
    renderPage()
    await screen.findByRole('grid', { name: 'Factures fournisseur' })
    await waitFor(() => expect(stockApi.acomptesFournisseurOuverts).toHaveBeenCalled())
  })
})

describe("Nouvelle facture — nature d'achat (AAPV6)", () => {
  it('pré-choisit « Prestations de services » pour un sous-traitant et poste type_achat', async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <NouvelleFacture
          fournisseurs={[{ id: 5, nom: 'Sous-traitant SA', type: 'service' },
            { id: 6, nom: 'Grossiste', type: 'materiel' }]}
          bons={[]} onClose={() => {}} onSaved={() => {}} />
      </ThemeProvider>,
    )
    await user.click(screen.getByLabelText('Fournisseur'))
    await user.click(await screen.findByRole('option', { name: 'Sous-traitant SA' }))
    expect(screen.getByLabelText('Nature')).toHaveTextContent('Prestations de services')
    await user.type(screen.getByLabelText('Montant TTC'), '12000')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(stockApi.createFactureFournisseur).toHaveBeenCalledWith(
      expect.objectContaining({ fournisseur: 5, type_achat: 'services' }),
      expect.objectContaining({ idempotencyKey: expect.any(String) })))  // ACNC23
  })

  it('ACNC23 — une facture au même ref_fournisseur dit « Facture déjà saisie : <référence> »', async () => {
    const user = userEvent.setup()
    const onSaved = vi.fn()
    stockApi.createFactureFournisseur.mockResolvedValueOnce({
      data: { id: 10, doublon_warning: [{ id: 9, reference: 'FAF-2026-11-0009' }] } })
    render(
      <ThemeProvider>
        <NouvelleFacture fournisseurs={[{ id: 6, nom: 'Grossiste', type: 'materiel' }]}
          bons={[]} onClose={() => {}} onSaved={onSaved} />
      </ThemeProvider>,
    )
    await user.click(screen.getByLabelText('Fournisseur'))
    await user.click(await screen.findByRole('option', { name: 'Grossiste' }))
    await user.type(screen.getByLabelText('Montant TTC'), '10000')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(
      expect.stringContaining('Facture déjà saisie : FAF-2026-11-0009')))
  })
})
