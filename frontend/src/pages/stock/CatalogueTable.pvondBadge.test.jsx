import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { CatalogueTable } from './CatalogueTable.jsx'

/* ============================================================================
   PVOND (fondateur 18/08) — badge « Non chiffrable » sur la liste Stock.
   ----------------------------------------------------------------------------
   Même patron que « prix à renseigner »/« SKU manquant » (badge inline sous
   le nom du produit) et même DONNÉE que la bannière « Onduleur(s) non
   chiffrable(s) » du générateur de devis : `produit.specs_solaire.manquantes`
   (calculée serveur, déjà servie par la liste des produits — zéro appel
   réseau supplémentaire). Vérifie que le badge apparaît/disparaît avec cette
   liste et ne s'affiche jamais pour un produit qui n'est pas un onduleur.

   NOTE — vitest ne peut pas s'exécuter dans ce worktree (pas de
   node_modules) : ces tests sont écrits selon les conventions de
   CatalogueTable.test.jsx et vérifiés à la seule syntaxe (esbuild). Le CI
   normal les exécutera réellement.
   ========================================================================== */

function wrapper({ children }) {
  return (
    <MemoryRouter>
      <ThemeProvider>{children}</ThemeProvider>
    </MemoryRouter>
  )
}

const baseProduit = (over = {}) => ({
  id: 1,
  nom: 'Onduleur hybride Deye 8kW',
  sku: 'OND-DEYE-8K',
  marque: 'Deye',
  prix_vente: '14000',
  prix_achat: '9000',
  tva: 20,
  quantite_stock: 3,
  quantite_reservee: 0,
  quantite_disponible: 3,
  seuil_alerte: 1,
  is_low_stock: false,
  is_archived: false,
  categorie: { id: 5, nom: 'Onduleurs hybrides', ordre: 2 },
  specs_solaire: { famille: 'onduleur', plage_batterie_v: null, v_nominal: null, manquantes: [] },
  ...over,
})

function renderTable(props = {}) {
  return render(
    <CatalogueTable
      produits={[baseProduit()]}
      loading={false}
      canWrite
      canDelete
      onEdit={() => {}}
      onDelete={() => {}}
      onHistorique={() => {}}
      onReapprovisionner={() => {}}
      selected={new Set()}
      onToggleSelect={() => {}}
      {...props}
    />,
    { wrapper },
  )
}

describe('CatalogueTable — badge « Non chiffrable » (PVOND)', () => {
  it('affiche le badge quand l\'onduleur a des variables du contrat manquantes', () => {
    renderTable({
      produits: [baseProduit({
        specs_solaire: {
          famille: 'onduleur', plage_batterie_v: null, v_nominal: null,
          manquantes: ['courant maxi par MPPT (A)', 'garantie constructeur'],
        },
      })],
    })
    const grid = screen.getByRole('grid')
    const badge = within(grid).getByText('Non chiffrable')
    expect(badge).toBeTruthy()
    expect(badge.title).toBe(
      'Non chiffrable — il manque : courant maxi par MPPT (A), garantie constructeur')
  })

  it('n\'affiche PAS le badge pour un onduleur complet (manquantes vide)', () => {
    renderTable({ produits: [baseProduit({
      specs_solaire: { famille: 'onduleur', plage_batterie_v: [40, 60], v_nominal: null, manquantes: [] },
    })] })
    expect(screen.queryByText('Non chiffrable')).toBeNull()
  })

  it('n\'affiche jamais le badge pour un produit qui n\'est pas un onduleur', () => {
    renderTable({ produits: [baseProduit({
      nom: 'Panneau JA Solar 550W', categorie: { id: 3, nom: 'Panneaux', ordre: 1 },
      // Un produit non-onduleur n'a jamais de `manquantes` (le backend
      // renvoie toujours [] pour lui) — même sans specs_solaire du tout.
      specs_solaire: undefined,
    })] })
    expect(screen.queryByText('Non chiffrable')).toBeNull()
  })

  it('le badge coexiste avec « SKU manquant » sans se remplacer', () => {
    renderTable({ produits: [baseProduit({
      sku: '',
      specs_solaire: { famille: 'onduleur', plage_batterie_v: null, v_nominal: null, manquantes: ['puissance AC (kW)'] },
    })] })
    const grid = screen.getByRole('grid')
    expect(within(grid).getByText('SKU manquant')).toBeTruthy()
    expect(within(grid).getByText('Non chiffrable')).toBeTruthy()
  })
})
