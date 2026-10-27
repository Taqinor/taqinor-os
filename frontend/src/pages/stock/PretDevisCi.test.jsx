import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { documentContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import { produitStockBase, propsCatalogueBase } from './catalogue.testHelpers.js'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { CatalogueTable } from './CatalogueTable.jsx'

/* ============================================================================
   CCAT9 — encadré « Prêt pour le devis C&I » + `/stock?ci=a_completer`.
   Contrat partagé : pret_devis_ci.json — LU dans le fichier (PACT10), jamais
   recopié. Fichier neuf : l'encadré est monté par StockList (dont le module de
   test mocke tout le store) et non par CatalogueTable ; le test du paramètre
   `?ci=` s'appuie, lui, sur le vrai CatalogueTable ci-dessous.
   ========================================================================== */

const { getPretDevisCi } = vi.hoisted(() => ({ getPretDevisCi: vi.fn() }))
vi.mock('../../api/stockApi', () => ({ default: { getPretDevisCi } }))

import PretDevisCi from './PretDevisCi.jsx'

const contrat = documentContrat('stock', 'pret_devis_ci').exemple

function Lieu() {
  const l = useLocation()
  return <div data-testid="lieu">{l.pathname + l.search}</div>
}

function monter(ui, entree = '/stock') {
  return render(
    <MemoryRouter initialEntries={[entree]}>
      <ThemeProvider>
        <Routes>
          <Route path="*" element={<>{ui}<Lieu /></>} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

const nbManquants = contrat.nb_obligatoires_manquants

describe('PretDevisCi (CCAT9)', () => {
  beforeEach(() => {
    getPretDevisCi.mockReset()
    if (!window.matchMedia) {
      window.matchMedia = vi.fn().mockImplementation((q) => ({
        matches: false, media: q, onchange: null,
        addListener: vi.fn(), removeListener: vi.fn(),
        addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
      }))
    }
  })

  it("manque : titre avec N, ouvert, article + motif, bouton vers son lien", async () => {
    getPretDevisCi.mockResolvedValue(reponseContrat('stock', 'pret_devis_ci'))
    monter(<PretDevisCi />)
    expect(await screen.findByText(
      new RegExp(`${nbManquants} éléments obligatoires à compléter`))).toBeTruthy()
    expect(screen.getByRole('button', { expanded: true })).toBeTruthy()
    const poste = contrat.postes.find((p) => p.statut === 'a_completer' && p.obligatoire)
    const ligne = screen.getByTestId(`poste-ci-${poste.cle}`)
    expect(within(ligne).getByText('À compléter')).toBeTruthy()
    const art = poste.articles[0]
    expect(within(ligne).getByText(`${art.nom} — ${art.motif}`)).toBeTruthy()
    const lien = within(ligne).getByRole('link', { name: poste.action.texte })
    fireEvent.click(lien)
    expect(screen.getByTestId('lieu').textContent).toBe(poste.action.lien)
    // statut absent -> « Absent du catalogue » ; facultatif -> « recommandé »
    expect(screen.getByText('Absent du catalogue')).toBeTruthy()
    const opt = contrat.postes.find((p) => !p.obligatoire)
    expect(within(screen.getByTestId(`poste-ci-${opt.cle}`)).getByText('recommandé')).toBeTruthy()
    // jamais de prix
    expect(document.body.textContent).not.toMatch(/prix_achat|MAD|DH/)
  })

  it('tout est ok : « Prêt pour le devis C&I », replié ; clic ouvre ; OK facultatif derrière « Voir tout »', async () => {
    const pret = {
      ...contrat, pret: true, nb_obligatoires_manquants: 0,
      postes: contrat.postes.map((p) => ({ ...p, statut: 'ok', articles: [] })),
    }
    getPretDevisCi.mockResolvedValue({ data: pret })
    monter(<PretDevisCi />)
    const bouton = await screen.findByRole('button', { name: /Prêt pour le devis C&I/ })
    expect(bouton.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByTestId(`poste-ci-${contrat.postes[0].cle}`)).toBeNull()
    fireEvent.click(bouton)
    expect(bouton.getAttribute('aria-expanded')).toBe('true')
    const facultatif = contrat.postes.find((p) => !p.obligatoire)
    expect(screen.queryByTestId(`poste-ci-${facultatif.cle}`)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Voir tout' }))
    expect(screen.getByTestId(`poste-ci-${facultatif.cle}`)).toBeTruthy()
  })

  it('erreur serveur : rien à l’écran (aide, pas un verrou)', async () => {
    getPretDevisCi.mockRejectedValue(new Error('500'))
    monter(<PretDevisCi />)
    await waitFor(() => expect(getPretDevisCi).toHaveBeenCalled())
    expect(screen.queryByTestId('pret-devis-ci')).toBeNull()
  })
})

describe('CatalogueTable — ?ci=a_completer (CCAT9)', () => {
  const produit = {
    ...produitStockBase,
    categorie: { id: 3, nom: 'Panneaux', ordre: 1 },
    etat_ci: { eligible_ci: true, prix_connu: true },
  }
  const aCompleter = {
    ...produitStockBase, id: 2, nom: 'Coffret AC C&I', sku: 'CI-COF',
    categorie: { id: 3, nom: 'Panneaux', ordre: 1 },
    etat_ci: { eligible_ci: true, prix_connu: false },
  }
  const rendre = (entree) => render(
    <MemoryRouter initialEntries={[entree]}>
      <ThemeProvider>
        <CatalogueTable
          produits={[produit, aCompleter]}
          categories={[{ id: 3, nom: 'Panneaux' }]}
          {...propsCatalogueBase}
          onInlineSave={vi.fn().mockResolvedValue({})}
          selected={new Set()}
          onToggleSelect={() => {}}
        />
      </ThemeProvider>
    </MemoryRouter>,
  )

  it('?ci=a_completer ouvre le filtre', () => {
    rendre('/stock?ci=a_completer')
    expect(screen.getByTestId('filtre-ci-a-completer').getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByTestId('ci-raisons').textContent).toMatch(/Coffret AC C&I/)
  })

  it('sans paramètre le filtre est éteint', () => {
    rendre('/stock')
    expect(screen.getByTestId('filtre-ci-a-completer').getAttribute('aria-pressed')).toBe('false')
  })
})
