import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, renderHook, waitFor } from '@testing-library/react'
import { EMPTY_FILTERS } from '../../../features/crm/stages'

/* Incident 02/10/2026 — le lead « ouissam merbahi » archivé « avait disparu » :
   l'accès aux archivés était la dernière rangée du panneau « Filtres », la
   recherche ne regardait que les actifs, et un lien ?lead=<id> vers un lead
   archivé n'ouvrait rien. Trois accès, trois gardes. */
vi.mock('../../../features/crm/useCanaux', () => ({
  default: () => ({ options: [], labels: {} }),
}))
vi.mock('../../../api/crmApi', () => ({
  default: { getLead: vi.fn(() => Promise.resolve({ data: { id: 1569, nom: 'ouissam merbahi', is_archived: true } })) },
}))

import crmApi from '../../../api/crmApi'
import FilterBar from './FilterBar'
import ArchivedSearchHint from './ArchivedSearchHint'
import useDeepLinkedLead from './useDeepLinkedLead'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('FilterBar — accès VISIBLE aux leads archivés', () => {
  it('le bouton « Archivés » (hors panneau Filtres) bascule sur les archivés', () => {
    const setFilters = vi.fn()
    render(<FilterBar filters={{ ...EMPTY_FILTERS }} setFilters={setFilters} leads={[]} />)
    const btn = screen.getByRole('button', { name: 'Voir les leads archivés' })
    expect(btn).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(btn)
    expect(setFilters).toHaveBeenCalledWith(expect.objectContaining({ archived: 'seuls' }))
  })

  it('actif, il se dit enfoncé et ramène aux leads actifs', () => {
    const setFilters = vi.fn()
    render(<FilterBar filters={{ ...EMPTY_FILTERS, archived: 'seuls' }} setFilters={setFilters} leads={[]} />)
    const btn = screen.getByRole('button', { name: 'Revenir aux leads actifs' })
    expect(btn).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(btn)
    expect(setFilters).toHaveBeenCalledWith(expect.objectContaining({ archived: 'actifs' }))
  })
})

describe('ArchivedSearchHint — une recherche sans résultat propose les archivés', () => {
  it('aucun lead actif trouvé → proposition, et le clic élargit', () => {
    const onWiden = vi.fn()
    render(<ArchivedSearchHint q="merbahi" archived="actifs" count={0} loading={false} onWiden={onWiden} />)
    expect(screen.getByRole('status')).toHaveTextContent('Aucun lead actif ne correspond à « merbahi »')
    fireEvent.click(screen.getByRole('button', { name: 'Chercher aussi dans les leads archivés' }))
    expect(onWiden).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['des résultats existent', { q: 'merbahi', archived: 'actifs', count: 2, loading: false }],
    ['pas de recherche', { q: '  ', archived: 'actifs', count: 0, loading: false }],
    ['déjà élargi à Tous', { q: 'merbahi', archived: 'tous', count: 0, loading: false }],
    ['déjà sur les archivés', { q: 'merbahi', archived: 'seuls', count: 0, loading: false }],
    ['chargement en cours', { q: 'merbahi', archived: 'actifs', count: 0, loading: true }],
  ])('muet quand %s', (_cas, props) => {
    const { container } = render(<ArchivedSearchHint {...props} onWiden={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('useDeepLinkedLead — un lien vers un lead archivé ouvre sa fiche', () => {
  it('lead dans la liste chargée → aucune requête', () => {
    const leads = [{ id: 7, nom: 'actif' }]
    const { result } = renderHook(() => useDeepLinkedLead('7', leads, false))
    expect(result.current).toEqual({ id: 7, nom: 'actif' })
    expect(crmApi.getLead).not.toHaveBeenCalled()
  })

  it('lead absent de la liste (archivé) → la fiche est chargée et ouverte', async () => {
    const { result } = renderHook(() => useDeepLinkedLead('1569', [{ id: 7 }], false))
    await waitFor(() => expect(result.current?.id).toBe(1569))
    expect(crmApi.getLead).toHaveBeenCalledWith('1569')
    expect(result.current.is_archived).toBe(true)
  })

  it('pendant le chargement de la liste → on attend (aucune requête prématurée)', () => {
    renderHook(() => useDeepLinkedLead('1569', [], true))
    expect(crmApi.getLead).not.toHaveBeenCalled()
  })

  it('aucun lien → null', () => {
    const { result } = renderHook(() => useDeepLinkedLead(null, [{ id: 7 }], false))
    expect(result.current).toBeNull()
  })
})
