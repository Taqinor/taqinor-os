import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// jsdom n'implémente pas ResizeObserver (mesuré par recharts ResponsiveContainer
// dans le graphique du cockpit) — on le polyfill localement.
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})
import {
  totalDebit, totalCredit, ecart, estEquilibree,
} from './ecritureBalance.js'

/* Tests du module Comptabilité (UX2–UX9) :
   1) garde d'équilibre d'écriture (aide pure) ;
   2) rendu smoke du cockpit et d'un écran de liste (config du module).
   Les appels API sont mockés — aucun réseau. Tout écran utilisant <Link> /
   DataTable est enveloppé dans <MemoryRouter> + <ThemeProvider>. */

// ── Mock du client API compta (aucun appel réseau réel) ──
vi.mock('../../api/comptaApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  const res = () => ({ list: empty, get: empty, create: empty, update: empty, remove: empty })
  return {
    default: {
      downloadBlob: vi.fn(),
      cockpit: () => Promise.resolve({
        data: {
          resultat_periode: 12000, chiffre_affaires: 80000, tresorerie: 45000,
          marge_brute: 30000, marge_brute_pct: 37.5,
          encours_clients: 15000, encours_fournisseurs: 8000,
          dso: 21, dpo: 14, top_encours_clients: [{ tiers_id: 3, encours: 9000 }],
        },
      }),
      comptes: res(), journaux: res(), plans: res(),
      ecritures: { ...res(), valider: empty, extourner: empty },
      exercices: { ...res(), cloturer: empty, rouvrir: empty },
    },
  }
})

function mount(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ecritureBalance — garde d’équilibre (UX4)', () => {
  const l = (debit, credit, compte = 1) => ({ compte, debit, credit })

  it('somme débits et crédits (chaînes fr acceptées)', () => {
    const lignes = [l('1 000', ''), l('', '1 000')]
    expect(totalDebit(lignes)).toBe(1000)
    expect(totalCredit(lignes)).toBe(1000)
    expect(ecart(lignes)).toBe(0)
  })

  it('équilibrée quand débit == crédit sur ≥2 comptes', () => {
    expect(estEquilibree([l(500, 0), l(0, 500)])).toBe(true)
  })

  it('déséquilibrée quand les totaux diffèrent', () => {
    expect(estEquilibree([l(500, 0), l(0, 400)])).toBe(false)
    expect(ecart([l(500, 0), l(0, 400)])).toBe(100)
  })

  it('refuse une écriture toute à zéro ou à une seule ligne', () => {
    expect(estEquilibree([l(0, 0), l(0, 0)])).toBe(false)
    expect(estEquilibree([l(500, 0)])).toBe(false)
    // Une ligne sans compte ne compte pas comme ligne portée.
    expect(estEquilibree([{ compte: '', debit: 500, credit: 0 }, l(0, 500)])).toBe(false)
  })
})

// NB : le premier import d'un écran tire les barils `ui` + `charts` (recharts),
// dont la transformation sous jsdom peut dépasser 25 s à froid — d'où un timeout
// large (30 s) sur les tests de rendu (cf. tests estimateur, même environnement).
describe('CockpitPage — rendu smoke (UX2)', () => {
  it('affiche les KPI financiers du cockpit', async () => {
    const { default: CockpitPage } = await import('./pages/CockpitPage.jsx')
    mount(<CockpitPage />)
    expect(await screen.findByText('Résultat de la période')).toBeInTheDocument()
    expect(screen.getByText('Trésorerie nette')).toBeInTheDocument()
    // Le titre de la page est présent.
    expect(screen.getByRole('heading', { name: /Cockpit financier/ })).toBeInTheDocument()
  }, 30000)
})

describe('CockpitPage — VX115 : KPI vers l’écran d’action + index des exports', () => {
  it('« Créances clients » pointe vers la balance âgée et « DSO » vers les relances', async () => {
    const { default: CockpitPage } = await import('./pages/CockpitPage.jsx')
    mount(<CockpitPage />)
    const creances = await screen.findByText('Créances clients')
    expect(creances.closest('a')).toHaveAttribute('href', '/reporting/balance-agee')
    const dso = screen.getByText('DSO (encaissement client)')
    expect(dso.closest('a')).toHaveAttribute('href', '/ventes/relances')
    // Résultat/Trésorerie restent sur les états — c'est juste là.
    const resultat = screen.getByText('Résultat de la période')
    expect(resultat.closest('a')).toHaveAttribute('href', '/comptabilite/etats')
    const tresorerie = screen.getByText('Trésorerie nette')
    expect(tresorerie.closest('a')).toHaveAttribute('href', '/comptabilite/tresorerie')
  }, 30000)

  it('affiche la carte « Où trouver mes exports » avec les 4 destinations', async () => {
    const { default: CockpitPage } = await import('./pages/CockpitPage.jsx')
    mount(<CockpitPage />)
    expect(await screen.findByText('Où trouver mes exports')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Factures — Export comptable/ }))
      .toHaveAttribute('href', '/ventes/factures')
    expect(screen.getByRole('link', { name: /Fiscalité/ })).toHaveAttribute('href', '/comptabilite/fiscalite')
    expect(screen.getByRole('link', { name: /États CGNC/ })).toHaveAttribute('href', '/comptabilite/etats')
    expect(screen.getByRole('link', { name: /Balance âgée/ })).toHaveAttribute('href', '/reporting/balance-agee')
  }, 30000)
})

describe('resolveTiersLabel — VX232(a) : le KPI n°1 ne montre plus « Tiers #42 » brut', () => {
  it('résout un tiers connu vers son nom réel', async () => {
    const { resolveTiersLabel } = await import('./pages/CockpitPage.jsx')
    expect(resolveTiersLabel(3, { 3: 'SOMACHOR SA' })).toBe('SOMACHOR SA')
  })

  it('replie sur « Tiers #N » quand le répertoire ne contient pas ce tiers, et « Non affecté » sans tiers_id', async () => {
    const { resolveTiersLabel } = await import('./pages/CockpitPage.jsx')
    expect(resolveTiersLabel(42, {})).toBe('Tiers #42')
    expect(resolveTiersLabel(null, {})).toBe('Non affecté')
  })
})

describe('PlanComptablePage — rendu smoke (UX3)', () => {
  it('rend le titre et le sélecteur de vue', async () => {
    const { default: PlanComptablePage } = await import('./pages/PlanComptablePage.jsx')
    mount(<PlanComptablePage />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Plan comptable & journaux/ })).toBeInTheDocument()
    })
    expect(screen.getByText('Comptes CGNC')).toBeInTheDocument()
    expect(screen.getByText('Journaux')).toBeInTheDocument()
  }, 30000)
})

describe('module.config — enregistrement (UX2–UX9 + XACC/ZACC round 2)', () => {
  it('déclare 11 routes/nav gatées responsable+admin sous /comptabilite', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('compta')
    expect(config.routes).toHaveLength(11)
    expect(config.nav.items).toHaveLength(11)
    // Chaque item de nav correspond à une route.
    const navTargets = config.nav.items.map((i) => i.to).sort()
    const routePaths = config.routes.map((r) => r.path).sort()
    expect(navTargets).toEqual(routePaths)
    // Toutes gatées responsable/admin.
    for (const r of config.routes) {
      expect(r.roles).toEqual(['responsable', 'admin'])
    }
    // La base /comptabilite est présente.
    expect(routePaths).toContain('/comptabilite')
  })
})
