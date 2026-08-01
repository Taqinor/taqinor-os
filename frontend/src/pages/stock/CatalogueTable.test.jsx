import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { CatalogueTable, severiteStock, jaugeStock } from './CatalogueTable.jsx'

/* ============================================================================
   J142 - Stock refonte : le catalogue passe au moteur DataTable unifie.
   Le moteur a besoin d'un <Router> (useSearchParams) et d'un <ThemeProvider>
   (useDensity). On les fournit via `wrapper`.
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
  nom: 'Panneau 550 Wc',
  sku: 'PAN-550',
  marque: 'JA Solar',
  prix_vente: '1000',
  prix_achat: '700',
  tva: 20,
  quantite_stock: 12,
  quantite_reservee: 0,
  quantite_disponible: 12,
  seuil_alerte: 5,
  is_low_stock: false,
  is_archived: false,
  categorie: { id: 3, nom: 'Panneaux', ordre: 1 },
  ...over,
})

function renderTable(props = {}) {
  return render(
    <CatalogueTable
      produits={[baseProduit()]}
      categories={[{ id: 3, nom: 'Panneaux' }]}
      loading={false}
      canWrite
      canDelete
      onEdit={() => {}}
      onDelete={() => {}}
      onHistorique={() => {}}
      onReapprovisionner={() => {}}
      onInlineSave={vi.fn().mockResolvedValue({})}
      selected={new Set()}
      onToggleSelect={() => {}}
      {...props}
    />,
    { wrapper },
  )
}

describe('CatalogueTable (J142)', () => {
  beforeEach(() => {
    // matchMedia est requis par la densite ; jsdom ne l'a pas toujours.
    if (!window.matchMedia) {
      window.matchMedia = vi.fn().mockImplementation((q) => ({
        matches: false, media: q, onchange: null,
        addListener: vi.fn(), removeListener: vi.fn(),
        addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
      }))
    }
  })

  it('rend les produits dans le moteur DataTable (grille accessible)', () => {
    renderTable()
    expect(screen.getAllByRole('grid').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Panneau 550 Wc/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/PAN-550/).length).toBeGreaterThan(0)
  })

  it('virtualise les grandes listes (ne materialise pas les ~500 lignes)', () => {
    const many = Array.from({ length: 500 }, (u, i) =>
      baseProduit({ id: i + 1, nom: `Produit ${i + 1}`, sku: `SKU-${i + 1}` }))
    renderTable({ produits: many })
    // Le moteur ne met jamais les 500 lignes dans le DOM en meme temps
    // (pagination + virtualisation). On compte les lignes-donnees de la grille.
    const grid = screen.getByRole('grid')
    const dataRows = within(grid).getAllByRole('row').filter(
      (r) => r.querySelector('[role="gridcell"]'))
    expect(dataRows.length).toBeGreaterThan(0)
    expect(dataRows.length).toBeLessThan(120)
    expect(within(grid).getByText('Produit 1', { exact: true })).toBeTruthy()
    expect(within(grid).queryByText('Produit 480', { exact: true })).toBeNull()
  })

  it('edite une cellule (stock) sur le contrat clavier EditableCell -> onInlineSave', () => {
    const onInlineSave = vi.fn().mockResolvedValue({})
    renderTable({ onInlineSave })
    const editButtons = screen.getAllByTitle('Double-cliquez pour modifier')
    expect(editButtons.length).toBeGreaterThan(0)
    const stockCell = editButtons.find((b) => b.textContent.includes('12'))
    expect(stockCell).toBeTruthy()
    fireEvent.doubleClick(stockCell)
    const input = document.querySelector('input')
    fireEvent.change(input, { target: { value: '20' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(onInlineSave).toHaveBeenCalledTimes(1)
    const [prod, field, value] = onInlineSave.mock.calls[0]
    expect(prod.id).toBe(1)
    expect(field).toBe('quantite_stock')
    expect(String(value)).toBe('20')
  })

  it('affiche un etat vide quand le catalogue filtre est vide', () => {
    renderTable({ produits: [] })
    expect(screen.getAllByText(/Aucun produit|Aucun resultat/i).length).toBeGreaterThan(0)
  })

  it('affiche des squelettes apres le delai anti-clignotement (chargement prolonge)', () => {
    vi.useFakeTimers()
    try {
      renderTable({ produits: [], loading: true })
      act(() => { vi.advanceTimersByTime(600) })
      expect(document.querySelector('[data-skeleton-row]')).toBeTruthy()
    } finally {
      vi.useRealTimers()
    }
  })

  it('rend la metrique TTC et le prix HT par ligne', () => {
    renderTable()
    // 1000 HT + TVA 20% = 1200 TTC ; le separateur de milliers depend de la
    // locale (1 200 / 1.200 / 1,200 / 1200) : on reste tolerant.
    expect(screen.getAllByText(/1\D?200/).length).toBeGreaterThan(0)
    // VX75 — formatMAD ajoute un séparateur de milliers (« 1 000,00 HT ») ;
    // on reste tolérant sur ce séparateur (espace/nbsp/narrow-nbsp ou aucun).
    expect(screen.getAllByText(/1\s?000[.,]00 HT/).length)
      .toBeGreaterThan(0)
  })

  it('en lecture seule (canWrite=false) les cellules ne sont pas editables', () => {
    renderTable({ canWrite: false, onInlineSave: null, onToggleSelect: null })
    expect(screen.queryByTitle('Double-cliquez pour modifier')).toBeNull()
  })

  it('expose une case de selection multiple (pilotee par StockList) qui appelle onToggleSelect', () => {
    const onToggleSelect = vi.fn()
    renderTable({ onToggleSelect, selected: new Set() })
    const box = screen.getAllByLabelText(/Selectionner Panneau 550 Wc|Sélectionner Panneau 550 Wc/)[0]
    expect(box).toBeTruthy()
    fireEvent.click(box)
    expect(onToggleSelect).toHaveBeenCalledWith(1)
  })

  it('ne rend aucune case de selection en lecture seule', () => {
    renderTable({ canWrite: false, onInlineSave: null, onToggleSelect: null })
    expect(screen.queryByLabelText(/lectionner Panneau 550 Wc/)).toBeNull()
  })
})

/* ============================================================================
   APX19 — Le niveau de stock devient LISIBLE : jauge colorée, sévérité
   distincte (rupture ≠ sous seuil, deux urgences différentes qui partageaient
   un seul badge), et UNE SEULE hauteur de ligne.
   ========================================================================== */

const rupture = (over = {}) => baseProduit({
  id: 10, nom: 'Batterie Deyness 5 kWh', sku: 'BAT-DEY-5',
  quantite_stock: 0, quantite_disponible: 0, seuil_alerte: 5,
  is_low_stock: true, ...over,
})
const sousSeuil = (over = {}) => baseProduit({
  id: 11, nom: 'Onduleur Deye 5 kW', sku: 'OND-DEY-5',
  quantite_stock: 3, quantite_reservee: 2, quantite_disponible: 1,
  seuil_alerte: 5, is_low_stock: true, ...over,
})
const sain = (over = {}) => baseProduit({
  id: 12, nom: 'Cable solaire 6 mm', sku: 'CAB-6',
  quantite_stock: 40, quantite_disponible: 40, seuil_alerte: 5,
  is_low_stock: false, ...over,
})

describe('APX19 — severite du stock (logique pure)', () => {
  it('distingue rupture, sous seuil et sain', () => {
    expect(severiteStock(rupture())).toBe('rupture')
    expect(severiteStock(sousSeuil())).toBe('bas')
    expect(severiteStock(sain())).toBe('ok')
  })

  it('la rupture prime sur is_low_stock (0 en stock = on ne peut plus vendre)', () => {
    expect(severiteStock({ quantite_stock: 0, seuil_alerte: 0, is_low_stock: false }))
      .toBe('rupture')
  })

  it('deduit le sous-seuil meme si le serveur n\'a pas pose is_low_stock', () => {
    expect(severiteStock({ quantite_stock: 2, seuil_alerte: 5 })).toBe('bas')
  })

  it('la jauge vise 2x le seuil — la MEME cible que la suggestion de reassort', () => {
    expect(jaugeStock({ quantite_stock: 0, seuil_alerte: 5 })).toBe(0)
    expect(jaugeStock({ quantite_stock: 5, seuil_alerte: 5 })).toBe(50)
    expect(jaugeStock({ quantite_stock: 10, seuil_alerte: 5 })).toBe(100)
    // Jamais au-dessus de 100 (un surstock ne deborde pas la piste).
    expect(jaugeStock({ quantite_stock: 999, seuil_alerte: 5 })).toBe(100)
    // Sans seuil renseigne, on ne promet rien : plein si non nul, vide sinon.
    expect(jaugeStock({ quantite_stock: 7, seuil_alerte: 0 })).toBe(100)
    expect(jaugeStock({ quantite_stock: 0, seuil_alerte: 0 })).toBe(0)
  })
})

describe('APX19 — severite lisible sans lire', () => {
  it('rupture et sous seuil ne portent plus LE MEME badge', () => {
    renderTable({ produits: [rupture(), sousSeuil()], canWrite: false, onInlineSave: null })
    expect(screen.getAllByText('Rupture').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Sous seuil').length).toBeGreaterThan(0)
  })

  it('un produit sain ne porte aucun badge d\'alerte', () => {
    renderTable({ produits: [sain()], canWrite: false, onInlineSave: null })
    expect(screen.queryByText('Rupture')).toBeNull()
    expect(screen.queryByText('Sous seuil')).toBeNull()
  })

  it('rend une jauge de niveau par produit', () => {
    const { container } = renderTable({
      produits: [sousSeuil()], canWrite: false, onInlineSave: null,
    })
    expect(container.querySelector('.pcat-jauge')).toBeTruthy()
  })
})

describe('APX19 — une seule hauteur de ligne', () => {
  it('les zones de hauteur fixe existent sur CHAQUE ligne, remplies ou vides', () => {
    renderTable({
      produits: [rupture(), sousSeuil(), sain()],
      canWrite: false, onInlineSave: null, onToggleSelect: null,
    })
    // Le moteur peut rendre chaque ligne deux fois (table + carte mobile) :
    // ce qui compte est qu'AUCUNE ligne ne perde sa reserve de hauteur.
    const details = screen.getAllByTestId('pcat-stock-detail')
    const severites = screen.getAllByTestId('pcat-sev')
    expect(details.length).toBeGreaterThanOrEqual(3)
    expect(severites.length).toBeGreaterThanOrEqual(3)
    // Le produit sain a une ligne de detail VIDE — presente quand meme : c'est
    // elle qui empeche la hauteur de dependre des donnees. Celui qui a du
    // stock reserve la remplit : les deux cas coexistent a hauteur egale.
    expect(details.some((d) => d.textContent === '')).toBe(true)
    expect(details.some((d) => /2 rés\. · 1 dispo/.test(d.textContent))).toBe(true)
    // Meme chose cote severite : occupee pour rupture/sous-seuil, vide pour sain.
    expect(severites.some((s) => s.textContent === '')).toBe(true)
    expect(severites.some((s) => s.textContent !== '')).toBe(true)
  })

  it('la cellule Seuil n\'empile plus bouton ni « commander ~N »', () => {
    renderTable({
      produits: [sousSeuil()], canWrite: false, onInlineSave: null,
      onReapprovisionner: () => {},
    })
    // « commander ~7 » vivait en 3e ligne de la cellule : il est passe dans le
    // libelle de l'action de ligne, plus dans la grille.
    const cellules = screen.getAllByTestId('pcat-sev')
    for (const c of cellules) expect(c.textContent).not.toMatch(/commander/i)
  })
})

describe('APX19 — reassort en <= 2 clics', () => {
  it('expose « Reapprovisionner » avec la quantite suggeree, et l\'appelle', () => {
    const onReapprovisionner = vi.fn()
    renderTable({
      produits: [sousSeuil()], canWrite: false, onInlineSave: null,
      onToggleSelect: null, onReapprovisionner,
    })
    // Suggestion = 2x seuil - stock = 10 - 3 = 7.
    const boutons = screen.getAllByLabelText(/Réapprovisionner \(commander ~7\)/)
    expect(boutons.length).toBeGreaterThan(0)
    fireEvent.click(boutons[0])
    expect(onReapprovisionner).toHaveBeenCalledTimes(1)
    expect(onReapprovisionner.mock.calls[0][0].id).toBe(11)
  })

  it('aucun reassort propose sur un produit sain', () => {
    renderTable({
      produits: [sain()], canWrite: false, onInlineSave: null,
      onToggleSelect: null, onReapprovisionner: () => {},
    })
    expect(screen.queryByLabelText(/Réapprovisionner/)).toBeNull()
  })
})
