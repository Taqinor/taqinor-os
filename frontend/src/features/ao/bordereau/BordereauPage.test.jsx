import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { formatDate, formatMAD } from '../../../lib/format'
import BordereauPage from './BordereauPage'
import { quantiteVerrouillee, cadreAcheteur } from './LigneRow.utils'

/* AOF179 — l'écran Bordereau.
   Cas réel de la session AO FRDISI : sur remarque du client, la ligne
   « Câbles DC Bâtiment B » a été déplacée des PRESTATIONS COMMUNES vers la
   section BÂTIMENT B (devenue l'item 16), avec renumérotation complète et
   TOTAUX INCHANGÉS. */

const SECTIONS = [
  { id: 1, numero: 'A', libelle: 'Bâtiment A' },
  { id: 2, numero: 'B', libelle: 'Bâtiment B' },
  { id: 4, numero: 'D', libelle: 'Prestations communes' },
]

const L_CALEPINAGE = {
  id: 101, numero: 1, section: 1, designation: 'Modules photovoltaïques 625 Wc',
  unite: 'U', quantite: 152, quantite_source: 'calepinage',
  prix_unitaire: 1200, prix_unitaire_lettres: 'mille deux cents dirhams',
  tva: 20,
  // VOLONTAIREMENT différent de 152 × 1 200 = 182 400 : le serveur fait foi.
  total_ht: 182000,
}
const L_ACHETEUR = {
  id: 102, numero: 2, section: 2, designation: 'Onduleur 60 kWc (cadre acheteur)',
  unite: 'U', quantite: 2, quantite_source: 'acheteur',
  prix_unitaire: 41000, prix_unitaire_lettres: 'quarante et un mille dirhams',
  tva: 20, total_ht: 82000,
}
const L_MANUELLE = {
  id: 103, numero: 3, section: 4, designation: 'Câbles DC Bâtiment B',
  unite: 'ml', quantite: 300, quantite_source: 'manuelle',
  prix_unitaire: 45, prix_unitaire_lettres: 'quarante-cinq dirhams',
  tva: 20, total_ht: 13500,
}

const TOTAUX = {
  sous_total_ht: 5219280, remise_globale: 12000, total_ht: 5207280,
  tva_montant: 1041456, total_ttc: 6248736,
  total_ttc_lettres: 'six millions deux cent quarante-huit mille sept cent trente-six dirhams',
  clause_reserve: 'Les prix sont fermes et non révisables pendant toute la durée du marché.',
}

const AVANT = {
  id: 9, indice_revision: 'B', sections: SECTIONS,
  lignes: [L_CALEPINAGE, L_ACHETEUR, L_MANUELLE], ...TOTAUX,
}

// Le serveur renumérote 1..N et PROUVE le total inchangé (AOF123).
const APRES = {
  ...AVANT,
  lignes: [
    { ...L_CALEPINAGE, numero: 1 },
    { ...L_ACHETEUR, numero: 15 },
    { ...L_MANUELLE, section: 2, numero: 16 },
  ],
}

const services = {
  onDeplacerLigne: vi.fn(),
  onModifierLigne: vi.fn(),
  onDeverrouiller: vi.fn(),
  onAppliquerPrix: vi.fn(),
}

const renderPage = (props) => render(
  <BordereauPage bordereau={AVANT} {...services} {...props} />,
)

/* `formatMAD` s'appuie sur `Intl` fr-FR, qui sépare les milliers par une ESPACE
   FINE INSÉCABLE (U+202F). Testing Library normalise les espaces du texte du
   DOM mais PAS la chaîne attendue : `getByText(formatMAD(182000))` échouait donc
   alors que l'écran affichait bien « 182 000,00 MAD ». On compare la chaîne
   attendue normalisée de la même façon — le montant reste vérifié au caractère
   près, seule la classe d'espace est neutralisée. */
const mad = (valeur) => formatMAD(valeur).replace(/\s+/g, ' ')

beforeEach(() => {
  vi.clearAllMocks()
  services.onDeplacerLigne.mockResolvedValue({ data: APRES })
  services.onModifierLigne.mockResolvedValue({ data: AVANT })
  services.onDeverrouiller.mockResolvedValue({ data: AVANT })
  services.onAppliquerPrix.mockResolvedValue({ data: AVANT })
})

describe('BordereauPage (AOF179)', () => {
  it('déplacer une ligne appelle le service de renumérotation et affiche le total INCHANGÉ du serveur', async () => {
    renderPage()
    expect(screen.getByText(mad(TOTAUX.total_ttc))).toBeInTheDocument()

    await userEvent.click(
      screen.getByRole('combobox', { name: /Déplacer « Câbles DC Bâtiment B »/ }),
    )
    await userEvent.click(await screen.findByRole('option', { name: 'B — Bâtiment B' }))

    await waitFor(() => expect(services.onDeplacerLigne).toHaveBeenCalledWith(L_MANUELLE, 2))
    // Renumérotation visible ET total STRICTEMENT identique (preuve serveur).
    await waitFor(() => expect(screen.getByText('16')).toBeInTheDocument())
    expect(screen.getByText(mad(TOTAUX.total_ttc))).toBeInTheDocument()
    expect(screen.getByText(mad(TOTAUX.total_ht))).toBeInTheDocument()
  })

  it('AUCUN total n’est dérivé côté front : le total de ligne du serveur l’emporte sur quantité × PU', () => {
    renderPage()
    expect(screen.getByText(mad(182000))).toBeInTheDocument()
    expect(screen.queryByText(mad(182400))).not.toBeInTheDocument()
  })

  it('affiche les trois régimes de quantité avec leur badge', () => {
    renderPage()
    expect(screen.getByText('quantité issue du calepinage — verrouillée')).toBeInTheDocument()
    expect(screen.getByText('cadre acheteur — non modifiable')).toBeInTheDocument()
    expect(screen.getByText('manuelle')).toBeInTheDocument()
  })

  it('une quantité de calepinage et une ligne acheteur ne s’éditent PAS sans déverrouillage', () => {
    renderPage()
    expect(screen.getByLabelText('Quantité — Modules photovoltaïques 625 Wc')).toBeDisabled()
    expect(screen.getByLabelText('Quantité — Onduleur 60 kWc (cadre acheteur)')).toBeDisabled()
    expect(screen.getByLabelText('Quantité — Câbles DC Bâtiment B')).toBeEnabled()
    // La ligne du cadre acheteur ne se déplace pas non plus.
    expect(screen.getByRole('combobox', { name: /Déplacer « Onduleur 60 kWc/ })).toBeDisabled()
  })

  it('le déverrouillage exige un MOTIF et le transmet au service tracé', async () => {
    renderPage()
    fireEvent.click(
      screen.getByRole('button', { name: 'Déverrouiller la quantité — Modules photovoltaïques 625 Wc' }),
    )
    const valider = await screen.findByRole('button', { name: 'Déverrouiller' })
    expect(valider).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Motif du déverrouillage'), {
      target: { value: 'quantité corrigée après relevé contradictoire du 27/07' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Déverrouiller' }))
    await waitFor(() => expect(services.onDeverrouiller).toHaveBeenCalledWith(
      L_CALEPINAGE, 'quantité corrigée après relevé contradictoire du 27/07',
    ))
  })

  it('le P.U. et le P.U. en lettres sont en LECTURE SEULE (aucun champ de saisie)', () => {
    renderPage()
    expect(screen.getByText('mille deux cents dirhams')).toBeInTheDocument()
    expect(screen.queryByLabelText(/P\.U\./)).not.toBeInTheDocument()
  })

  it('la clause de réserve est affichée en pied et n’est PAS éditable', () => {
    renderPage()
    expect(screen.getByText('Clause de réserve (non éditable)')).toBeInTheDocument()
    expect(screen.getByText(TOTAUX.clause_reserve)).toBeInTheDocument()
    expect(screen.queryByDisplayValue(TOTAUX.clause_reserve)).not.toBeInTheDocument()
  })

  it('une proposition de PU de la bibliothèque cite sa DATE et son DOSSIER d’origine', async () => {
    renderPage({
      propositionsPrix: {
        103: { prix_unitaire: 42, date: '2026-05-14', dossier_origine: 'AO-2026-004' },
      },
    })
    expect(screen.getByText(/PU proposé \(bibliothèque de prix\)/)).toBeInTheDocument()
    expect(screen.getByText(new RegExp(`relevé le ${formatDate('2026-05-14')}`))).toBeInTheDocument()
    expect(screen.getByText(/dossier AO-2026-004/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Appliquer ce PU' }))
    await waitFor(() => expect(services.onAppliquerPrix).toHaveBeenCalledWith(
      L_MANUELLE, { prix_unitaire: 42, date: '2026-05-14', dossier_origine: 'AO-2026-004' },
    ))
  })

  it('quantiteVerrouillee / cadreAcheteur : les régimes sont des règles, pas du style', () => {
    expect(quantiteVerrouillee(L_CALEPINAGE)).toBe(true)
    expect(quantiteVerrouillee(L_ACHETEUR)).toBe(true)
    expect(quantiteVerrouillee(L_MANUELLE)).toBe(false)
    expect(quantiteVerrouillee({ ...L_CALEPINAGE, deverrouillee: true })).toBe(false)
    expect(cadreAcheteur(L_ACHETEUR)).toBe(true)
    expect(cadreAcheteur({ ...L_ACHETEUR, deverrouillee: true })).toBe(false)
  })
})
