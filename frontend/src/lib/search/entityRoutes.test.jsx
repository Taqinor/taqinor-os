import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { ROUTE, LIST_ROUTE, TYPE_LABEL, TYPE_ACCENT, useEntitySearch } from './entityRoutes'
import reportingApi from '../../api/reportingApi'

vi.mock('../../api/reportingApi', () => ({
  default: { search: vi.fn() },
}))

function Harness({ term, enabled }) {
  const { groups, loading, failed } = useEntitySearch(term, { enabled })
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="failed">{String(failed)}</span>
      <span data-testid="groups">{JSON.stringify(groups)}</span>
    </div>
  )
}

describe('VX13 — entityRoutes (source unique GlobalSearch + CommandPalette)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    reportingApi.search.mockReset()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('ROUTE/LIST_ROUTE/TYPE_LABEL sont l’UNION des deux tables d’origine (aucun type perdu)', () => {
    // Types connus historiquement d'un seul côté (GlobalSearch OU CommandPalette).
    expect(ROUTE.bon_commande).toBeTypeOf('function')
    expect(ROUTE.contrat).toBeTypeOf('function')
    expect(ROUTE.dossier).toBeTypeOf('function')
    expect(ROUTE.produit).toBeTypeOf('function')
    expect(LIST_ROUTE.contrat).toBeTypeOf('function')
    expect(TYPE_LABEL.devis).toBe('Devis')
  })

  it('VX220 — ROUTE atterrit sur le RECORD (pas la liste) pour lead/client/devis/facture/chantier/ticket', () => {
    // Défaut prouvé (avant VX220) : seul `lead` ouvrait la fiche, les autres
    // types retombaient sur leur liste nue (`ROUTE.client() === '/crm'` etc.).
    // Chaque type réutilise désormais la convention DÉJÀ établie par sa propre
    // page — jamais une deuxième convention pour le même type.
    expect(ROUTE.lead(42)).toBe('/crm/leads?lead=42')
    expect(ROUTE.client(42)).toBe('/crm?id=42')
    expect(ROUTE.devis(42)).toBe('/ventes/devis?devis=42')
    expect(ROUTE.facture(42)).toBe('/ventes/factures?id=42')
    expect(ROUTE.chantier(42)).toBe('/chantiers?id=42')
    expect(ROUTE.ticket(42)).toBe('/sav?id=42')
  })

  it('TYPE_ACCENT — chaque clé pointe vers une des 7 clés --module-accent-* de VX8', () => {
    const VALID = ['brass', 'azur', 'nuit', 'success', 'destructive', 'warning', 'lune']
    Object.values(TYPE_ACCENT).forEach((accent) => {
      expect(VALID).toContain(accent)
    })
    expect(TYPE_ACCENT.devis).toBe('brass')
  })

  it('ne cherche rien tant que le terme fait moins de 2 caractères', async () => {
    render(<Harness term="a" enabled />)
    await vi.advanceTimersByTimeAsync(300)
    expect(reportingApi.search).not.toHaveBeenCalled()
    expect(screen.getByTestId('groups').textContent).toBe('[]')
  })

  it('débounce ~250 ms avant d’appeler /reporting/search', async () => {
    reportingApi.search.mockResolvedValue({ data: { groups: [{ type: 'lead', label: 'Leads', results: [] }] } })
    render(<Harness term="solaire" enabled />)
    await vi.advanceTimersByTimeAsync(100)
    expect(reportingApi.search).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(200)
    expect(reportingApi.search).toHaveBeenCalledWith('solaire')
  })

  it('n’appelle PAS le serveur quand enabled=false (CommandPalette fermée)', async () => {
    render(<Harness term="solaire" enabled={false} />)
    await vi.advanceTimersByTimeAsync(500)
    expect(reportingApi.search).not.toHaveBeenCalled()
  })

  it('failed=true sur échec réseau, groups vidés', async () => {
    // Vrais timers ici : le rejet asynchrone + ses microtâches ne se vident pas
    // proprement sous fake timers (et `waitFor` boucle sous fake timers). Le
    // debounce 250 ms tourne pour de vrai, `waitFor` sonde normalement.
    vi.useRealTimers()
    reportingApi.search.mockRejectedValue(new Error('network'))
    render(<Harness term="solaire" enabled />)
    await waitFor(
      () => expect(screen.getByTestId('failed').textContent).toBe('true'),
      { timeout: 2000 },
    )
    expect(screen.getByTestId('groups').textContent).toBe('[]')
  })
})
