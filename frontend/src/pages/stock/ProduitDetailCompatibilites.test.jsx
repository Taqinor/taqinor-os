import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   PVCOMPAT (fondateur 20/08/2026) — onglet « Compatibilités » de la fiche
   produit du stock : au-delà de la complétude de la fiche, l'onglet montre
   les produits compatibles des autres familles (avec la raison quand ils ne
   le sont pas) et, pour un onduleur, un verdict d'installabilité avec le
   stock actuel (composition qu'il rejoindrait ou problème nommé).

   Fixtures reprises TEXTUELLEMENT du contrat gelé
   backend/django_core/apps/stock/contract_samples/produit_compatibilites.json
   (`exemple`, `exemple_non_installable`, `exemple_panneau`) — l'écran ne doit
   jamais réécrire ni tronquer les phrases envoyées par le serveur.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    produitPrevisionnel: vi.fn(),
    getFichesTechniques: vi.fn(),
    getCompatibilites: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import { ProduitDetail } from './ProduitDetail.jsx'

const store = configureStore({
  reducer: { auth: (s = { role: 'Directeur', role_nom: 'Directeur', permissions: [] }) => s },
})
function wrapper({ children }) {
  return <Provider store={store}><MemoryRouter><ThemeProvider>{children}</ThemeProvider></MemoryRouter></Provider>
}

const onduleur = {
  id: 12,
  nom: 'Onduleur hybride Deye 10kW Triphasé',
  sku: 'OND-H-10',
  quantite_en_commande: 0,
  bcf_sources_en_commande: [],
}

const panneau = {
  id: 3,
  nom: 'Panneau Canadien Solar 710W',
  sku: 'PAN-710',
  quantite_en_commande: 0,
  bcf_sources_en_commande: [],
}

// Fixtures reprises du contrat gelé (exemple / exemple_non_installable / exemple_panneau).
const FIXTURE_INSTALLABLE = {
  produit: { id: 12, nom: 'Onduleur hybride Deye 10kW Triphasé', famille: 'onduleur_hybride' },
  fiche_incomplete: [],
  installable: true,
  bilan: {
    verdict: 'installable',
    composition: [
      {
        role: 'panneau', produit_id: 3, nom: 'Panneau Canadien Solar 710W', quantite: 14,
        detail: '2 chaînes de 7 — Voc à froid 386 V sous la limite 500 V, fenêtre MPPT 150-425 V respectée, 17,6 A sous les 26 A par MPPT',
      },
      {
        role: 'batterie', produit_id: 7, nom: 'Batterie Dyness 10 kWh', quantite: 1,
        detail: "51,2 V nominale dans la plage batterie 40-60 V de l'onduleur",
      },
    ],
    problemes: [],
  },
  familles: [
    {
      famille: 'panneau',
      produits: [
        { id: 3, nom: 'Panneau Canadien Solar 710W', ok: true, raison: '' },
        { id: 4, nom: 'Panneau Jinko 710W', ok: true, raison: '' },
      ],
    },
    {
      famille: 'batterie',
      produits: [
        { id: 7, nom: 'Batterie Dyness 10 kWh', ok: true, raison: '' },
        {
          id: 9, nom: 'Batterie Dyness HV 16 kWh', ok: false,
          raison: "tension nominale inconnue (fiche technique sans « tension nominale (V) ») — complétez la fiche pour trancher",
        },
      ],
    },
  ],
}

const FIXTURE_NON_INSTALLABLE = {
  produit: { id: 31, nom: 'Onduleur réseau compact 3kW', famille: 'onduleur_reseau' },
  fiche_incomplete: [],
  installable: false,
  bilan: {
    verdict: 'non installable',
    composition: [],
    problemes: [
      'aucun panneau du stock ne convient : courant maxi par MPPT (13 A) inférieur au courant de court-circuit de chaque panneau (≥ 18,5 A)',
    ],
  },
  familles: [
    {
      famille: 'panneau',
      produits: [
        {
          id: 3, nom: 'Panneau Canadien Solar 710W', ok: false,
          raison: 'courant de court-circuit 18,6 A au-dessus du courant maxi par MPPT (13 A)',
        },
      ],
    },
    { famille: 'batterie', produits: [] },
  ],
}

const FIXTURE_PANNEAU = {
  produit: { id: 3, nom: 'Panneau Canadien Solar 710W', famille: 'panneau' },
  fiche_incomplete: [],
  installable: true,
  bilan: null,
  familles: [
    {
      famille: 'onduleur',
      produits: [
        { id: 12, nom: 'Onduleur hybride Deye 10kW Triphasé', ok: true, raison: '' },
        {
          id: 31, nom: 'Onduleur réseau compact 3kW', ok: false,
          raison: 'courant de court-circuit 18,6 A au-dessus du courant maxi par MPPT (13 A)',
        },
      ],
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  stockApi.getFichesTechniques.mockResolvedValue({ data: [] })
  stockApi.produitPrevisionnel.mockResolvedValue({ data: null })
})

const ouvrirOnglet = async (produit) => {
  render(<ProduitDetail produit={produit} onClose={() => {}} />, { wrapper })
  await userEvent.click(screen.getByRole('tab', { name: 'Compatibilités' }))
  return screen.findByTestId('pdet-compatibilites')
}

describe('PVCOMPAT — onduleur installable', () => {
  it('affiche la composition (produit × quantité + détail) et les familles ✓', async () => {
    stockApi.getCompatibilites.mockResolvedValue({ data: FIXTURE_INSTALLABLE })
    await ouvrirOnglet(onduleur)

    expect(stockApi.getCompatibilites).toHaveBeenCalledWith(12)
    expect(await screen.findByText('installable')).toBeInTheDocument()
    expect(screen.getByText('Panneau Canadien Solar 710W × 14')).toBeInTheDocument()
    expect(screen.getByText(/2 chaînes de 7 — Voc à froid 386 V/)).toBeInTheDocument()
    expect(screen.getByText('Batterie Dyness 10 kWh × 1')).toBeInTheDocument()
    expect(screen.getByText(/51,2 V nominale dans la plage batterie/)).toBeInTheDocument()

    // Familles listées avec leur état : deux panneaux ✓, une batterie ✗ motivée.
    expect(screen.getByText('Panneau Jinko 710W')).toBeInTheDocument()
    expect(screen.getByText('Batterie Dyness HV 16 kWh')).toBeInTheDocument()
    expect(screen.getByText(/tension nominale inconnue/)).toBeInTheDocument()
  })

  it('pointe vers Paramètres → Gammes & marques', async () => {
    stockApi.getCompatibilites.mockResolvedValue({ data: FIXTURE_INSTALLABLE })
    await ouvrirOnglet(onduleur)
    const lien = screen.getByRole('link', { name: /Gammes & marques/ })
    expect(lien).toHaveAttribute('href', '/parametres/gammes')
  })
})

describe('PVCOMPAT — onduleur non installable', () => {
  it("affiche verbatim la phrase du problème (courant maxi MPPT vs courant de court-circuit)", async () => {
    stockApi.getCompatibilites.mockResolvedValue({ data: FIXTURE_NON_INSTALLABLE })
    await ouvrirOnglet({ ...onduleur, id: 31, nom: 'Onduleur réseau compact 3kW' })

    expect(await screen.findByText('non installable')).toBeInTheDocument()
    expect(screen.getByText(
      'aucun panneau du stock ne convient : courant maxi par MPPT (13 A) inférieur au courant de court-circuit de chaque panneau (≥ 18,5 A)',
    )).toBeInTheDocument()
    // Aucune composition à montrer : le verdict négatif ne mime pas un succès.
    expect(screen.queryByTestId('pdet-compat-composition')).not.toBeInTheDocument()
    // Batterie : famille vide → message honnête, pas un tableau vide silencieux.
    expect(screen.getByText('Aucun produit de cette famille dans le stock.')).toBeInTheDocument()
  })
})

describe('PVCOMPAT — fiche technique incomplète', () => {
  it('affiche les libellés français des champs manquants', async () => {
    stockApi.getCompatibilites.mockResolvedValue({
      data: { ...FIXTURE_INSTALLABLE, fiche_incomplete: ['Courant maxi par MPPT (A)', 'Tension max absolue (V)'] },
    })
    await ouvrirOnglet(onduleur)

    expect(screen.getByText('Courant maxi par MPPT (A)')).toBeInTheDocument()
    expect(screen.getByText('Tension max absolue (V)')).toBeInTheDocument()
    // Le bilan continue d'être rendu malgré la fiche incomplète — on ne s'arrête pas là.
    expect(screen.getByText('installable')).toBeInTheDocument()
  })
})

describe('PVCOMPAT — panneau (pas de bilan d\'installabilité)', () => {
  it('liste les onduleurs compatibles/incompatibles, sans bloc « installable »', async () => {
    stockApi.getCompatibilites.mockResolvedValue({ data: FIXTURE_PANNEAU })
    await ouvrirOnglet(panneau)

    expect(screen.getByText('Onduleur hybride Deye 10kW Triphasé')).toBeInTheDocument()
    expect(screen.getByText('Onduleur réseau compact 3kW')).toBeInTheDocument()
    expect(screen.getByText(/courant de court-circuit 18,6 A au-dessus/)).toBeInTheDocument()
    expect(screen.queryByTestId('pdet-compat-bilan')).not.toBeInTheDocument()
  })
})

describe('PVCOMPAT — erreur serveur', () => {
  it('affiche un message calme et laisse l\'onglet monté', async () => {
    stockApi.getCompatibilites.mockRejectedValue(new Error('boom'))
    render(<ProduitDetail produit={onduleur} onClose={() => {}} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Compatibilités' }))
    expect(await screen.findByText('Compatibilités indisponibles.')).toBeInTheDocument()
    // L'onduleur reste consultable : les autres onglets ne sont pas cassés.
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    expect(await screen.findByTestId('pdet-fiche-technique')).toBeInTheDocument()
  })
})
