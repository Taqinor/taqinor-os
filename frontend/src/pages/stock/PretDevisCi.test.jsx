import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { documentContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import { produitStockBase, propsCatalogueBase } from './catalogue.testHelpers.js'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { CatalogueTable } from './CatalogueTable.jsx'

/* ============================================================================
   CCAT9 / CCAT14 — encadré « Prêt pour les devis » (onglets C&I + agricole) et
   `/stock?ci=a_completer`. Contrats partagés : pret_devis_ci.json et
   pret_devis_agricole.json — LUS dans les fichiers (PACT10), jamais recopiés.
   L'encadré est monté par StockList (dont le module de test mocke tout le
   store) et non par CatalogueTable ; le test du paramètre `?ci=` s'appuie, lui,
   sur le vrai CatalogueTable ci-dessous.
   ========================================================================== */

const { getPretDevisCi, getPretDevisAgricole } = vi.hoisted(() => ({
  getPretDevisCi: vi.fn(), getPretDevisAgricole: vi.fn(),
}))
vi.mock('../../api/stockApi', () => ({ default: { getPretDevisCi, getPretDevisAgricole } }))

import PretDevisCi from './PretDevisCi.jsx'

const contrat = documentContrat('stock', 'pret_devis_ci').exemple
const contratAgri = documentContrat('stock', 'pret_devis_agricole').exemple

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
const nbManquantsAgri = contratAgri.nb_obligatoires_manquants

function reponsesContrat() {
  getPretDevisCi.mockResolvedValue(reponseContrat('stock', 'pret_devis_ci'))
  getPretDevisAgricole.mockResolvedValue(reponseContrat('stock', 'pret_devis_agricole'))
}

const toutOk = (c) => ({
  data: {
    ...c, pret: true, nb_obligatoires_manquants: 0,
    postes: c.postes.map((p) => ({ ...p, statut: 'ok', articles: [] })),
  },
})

describe('PretDevisCi (CCAT9, CCAT14)', () => {
  beforeEach(() => {
    getPretDevisCi.mockReset()
    getPretDevisAgricole.mockReset()
    if (!window.matchMedia) {
      window.matchMedia = vi.fn().mockImplementation((q) => ({
        matches: false, media: q, onchange: null,
        addListener: vi.fn(), removeListener: vi.fn(),
        addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
      }))
    }
  })

  it('manque : titre = somme des deux segments, ouvert, article + motif, bouton vers son lien', async () => {
    reponsesContrat()
    monter(<PretDevisCi />)
    const total = nbManquants + nbManquantsAgri
    expect(await screen.findByText(
      `Prêt pour les devis : ${total} éléments obligatoires à compléter`)).toBeTruthy()
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

  it('deux onglets avec leur compte ; le premier non prêt est ouvert ; changer d’onglet montre l’agricole', async () => {
    reponsesContrat()
    monter(<PretDevisCi />)
    const ongletCi = await screen.findByRole('tab', {
      name: `Commercial & industriel (${nbManquants})` })
    const ongletAgri = screen.getByRole('tab', { name: `Agricole (${nbManquantsAgri})` })
    expect(ongletCi.getAttribute('aria-selected')).toBe('true')
    expect(ongletAgri.getAttribute('aria-selected')).toBe('false')
    expect(screen.queryByTestId('poste-ci-pompe:mono')).toBeNull()
    fireEvent.click(ongletAgri)
    expect(ongletAgri.getAttribute('aria-selected')).toBe('true')
    const ligne = screen.getByTestId('poste-ci-pompe:mono')
    expect(within(ligne).getByText('Pompe à courbe constructeur, monophasée')).toBeTruthy()
    expect(within(ligne).getByText('Absent du catalogue')).toBeTruthy()
    // les postes C&I ne sont plus affichés
    const posteCi = contrat.postes.find((p) => p.statut === 'a_completer' && p.obligatoire)
    expect(screen.queryByTestId(`poste-ci-${posteCi.cle}`)).toBeNull()
  })

  it('C&I prêt, agricole non : l’onglet agricole est ouvert d’office ; compte « prêt » sans chiffre', async () => {
    getPretDevisCi.mockResolvedValue(toutOk(contrat))
    getPretDevisAgricole.mockResolvedValue(reponseContrat('stock', 'pret_devis_agricole'))
    monter(<PretDevisCi />)
    expect(await screen.findByRole('tab', { name: 'Commercial & industriel (prêt)' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: `Agricole (${nbManquantsAgri})` })
      .getAttribute('aria-selected')).toBe('true')
    expect(screen.getByTestId('poste-ci-pompe:mono')).toBeTruthy()
    expect(screen.getByText(
      `Prêt pour les devis : ${nbManquantsAgri} éléments obligatoires à compléter`)).toBeTruthy()
  })

  it('tout est ok : « Prêt pour les devis », replié ; clic ouvre ; OK facultatif derrière « Voir tout »', async () => {
    getPretDevisCi.mockResolvedValue(toutOk(contrat))
    getPretDevisAgricole.mockResolvedValue(toutOk(contratAgri))
    monter(<PretDevisCi />)
    const bouton = await screen.findByRole('button', { name: /^Prêt pour les devis$/ })
    expect(bouton.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByTestId(`poste-ci-${contrat.postes[0].cle}`)).toBeNull()
    fireEvent.click(bouton)
    expect(bouton.getAttribute('aria-expanded')).toBe('true')
    const facultatif = contrat.postes.find((p) => !p.obligatoire)
    expect(screen.queryByTestId(`poste-ci-${facultatif.cle}`)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Voir tout' }))
    expect(screen.getByTestId(`poste-ci-${facultatif.cle}`)).toBeTruthy()
  })

  it('un segment en erreur est masqué, l’autre reste affiché', async () => {
    getPretDevisCi.mockResolvedValue(reponseContrat('stock', 'pret_devis_ci'))
    getPretDevisAgricole.mockRejectedValue(new Error('500'))
    const { unmount } = monter(<PretDevisCi />)
    expect(await screen.findByText(
      `Prêt pour les devis : ${nbManquants} éléments obligatoires à compléter`)).toBeTruthy()
    expect(screen.getByRole('tab', { name: `Commercial & industriel (${nbManquants})` })).toBeTruthy()
    expect(screen.queryByRole('tab', { name: /Agricole/ })).toBeNull()
    unmount()

    getPretDevisCi.mockRejectedValue(new Error('500'))
    getPretDevisAgricole.mockResolvedValue(reponseContrat('stock', 'pret_devis_agricole'))
    monter(<PretDevisCi />)
    expect(await screen.findByRole('tab', { name: `Agricole (${nbManquantsAgri})` })).toBeTruthy()
    expect(screen.queryByRole('tab', { name: /Commercial/ })).toBeNull()
    expect(screen.getByTestId('poste-ci-pompe:mono')).toBeTruthy()
  })

  it('les deux en erreur : rien à l’écran (aide, pas un verrou)', async () => {
    getPretDevisCi.mockRejectedValue(new Error('500'))
    getPretDevisAgricole.mockRejectedValue(new Error('500'))
    monter(<PretDevisCi />)
    await waitFor(() => expect(getPretDevisCi).toHaveBeenCalled())
    await waitFor(() => expect(getPretDevisAgricole).toHaveBeenCalled())
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
