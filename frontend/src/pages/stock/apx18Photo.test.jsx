import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   APX18 — Photo produit (dégatée par mot fondateur du 2026-08-01).

   Ce que ces tests verrouillent :
   - le catalogue montre la PHOTO quand il y en a une, l'ICÔNE DE CATÉGORIE
     sinon — dans la MÊME boîte : la hauteur de ligne ne dépend jamais de la
     présence d'une photo (le repli est construit d'office, il fonctionne que
     le produit ait été photographié ou pas) ;
   - la fiche produit affiche la photo en tête et NE rend AUCUN cadre vide
     quand il n'y en a pas ;
   - `prix_achat` reste absent de toutes ces surfaces (loi fondateur).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: { produitPrevisionnel: vi.fn().mockResolvedValue({ data: null }) },
}))

import { CatalogueTable } from './CatalogueTable.jsx'
import { ProduitDetail } from './ProduitDetail.jsx'

const store = configureStore({
  reducer: { auth: (s = { role: 'Directeur', role_nom: 'Directeur', permissions: [] }) => s },
})

function wrapper({ children }) {
  return (
    <Provider store={store}>
      <MemoryRouter><ThemeProvider>{children}</ThemeProvider></MemoryRouter>
    </Provider>
  )
}

const produit = (over = {}) => ({
  id: 1,
  nom: 'Panneau 550 Wc',
  sku: 'PAN-550',
  marque: 'JA Solar',
  prix_vente: '1000',
  prix_achat: '742.5',
  tva: 20,
  quantite_stock: 12,
  quantite_reservee: 0,
  quantite_disponible: 12,
  seuil_alerte: 5,
  is_low_stock: false,
  is_archived: false,
  categorie: { id: 3, nom: 'Panneaux photovoltaïques', ordre: 1 },
  image_url: null,
  ...over,
})

function renderCatalogue(produits) {
  return render(
    <CatalogueTable produits={produits} loading={false} canWrite={false} />,
    { wrapper },
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
})

describe('APX18 — vignette du catalogue', () => {
  it('affiche la photo du produit quand il en a une', () => {
    renderCatalogue([produit({ image_url: '/api/django/stock/produits/1/image/' })])
    const vignettes = screen.getAllByTestId('pcat-vignette')
    expect(vignettes.length).toBeGreaterThan(0)
    const img = vignettes[0].querySelector('img')
    expect(img).toBeTruthy()
    expect(img.getAttribute('src')).toBe('/api/django/stock/produits/1/image/')
    // Vignette décorative : le nom du produit est déjà dans la cellule, un
    // alt bavard ne ferait que doubler la lecture d'écran.
    expect(img.getAttribute('alt')).toBe('')
  })

  it('sans photo : repli sur l\'icône de catégorie, JAMAIS de trou', () => {
    renderCatalogue([produit({ image_url: null })])
    const vignettes = screen.getAllByTestId('pcat-vignette')
    expect(vignettes.length).toBeGreaterThan(0)
    // Aucune image, mais un visuel bien présent (icône lucide = <svg>).
    expect(vignettes[0].querySelector('img')).toBeNull()
    expect(vignettes[0].querySelector('svg')).toBeTruthy()
  })

  it('la vignette existe pour CHAQUE ligne, photographiée ou non — la boîte '
     + 'est la même, donc la hauteur de ligne ne bouge pas', () => {
    renderCatalogue([
      produit({ id: 1, nom: 'Avec photo', image_url: '/api/django/stock/produits/1/image/' }),
      produit({ id: 2, nom: 'Sans photo', image_url: null }),
    ])
    const vignettes = screen.getAllByTestId('pcat-vignette')
    // Le moteur peut rendre la ligne deux fois (table + carte mobile) : on
    // vérifie que chaque vignette porte exactement une classe de boîte fixe.
    expect(vignettes.length).toBeGreaterThanOrEqual(2)
    for (const v of vignettes) expect(v.className).toContain('pcat-vignette')
  })

  it('n\'expose JAMAIS le prix d\'achat (loi fondateur)', () => {
    const { container } = renderCatalogue([
      produit({ image_url: '/api/django/stock/produits/1/image/' }),
    ])
    expect(container.textContent).not.toMatch(/742[.,]5/)
    expect(container.textContent).not.toMatch(/prix d'achat/i)
  })
})

describe('APX18 — photo en tête de la fiche produit', () => {
  const fiche = (over = {}) => ({
    id: 7,
    nom: 'Pompe OSP 30-15',
    sku: 'OSP-30-15',
    categorie: { id: 9, nom: 'Pompes' },
    quantite_en_commande: 0,
    bcf_sources_en_commande: [],
    ...over,
  })

  it('rend la photo quand le produit en a une', () => {
    render(
      <ProduitDetail
        produit={fiche({ image_url: '/api/django/stock/produits/7/image/' })}
        onClose={() => {}}
      />, { wrapper },
    )
    const img = screen.getByTestId('pdet-photo')
    expect(img.getAttribute('src')).toBe('/api/django/stock/produits/7/image/')
    // Texte alternatif utile (jamais un alt vide sur une image porteuse).
    expect(img.getAttribute('alt')).toMatch(/Pompe OSP 30-15/)
  })

  it('sans photo : AUCUN cadre vide n\'est rendu', () => {
    render(<ProduitDetail produit={fiche()} onClose={() => {}} />, { wrapper })
    expect(screen.queryByTestId('pdet-photo')).toBeNull()
  })
})
