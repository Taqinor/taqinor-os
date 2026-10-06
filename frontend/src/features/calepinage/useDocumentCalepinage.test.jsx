import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act, cleanup } from '@testing-library/react'

/* ============================================================================
   ACAL24 (C-ACAL-044) — la lecture UNIQUE du document : un échec de lecture ne
   devient jamais un document vide (qu'un « Enregistrer » écraserait ensuite).
   Test-du-test : remettre `.catch(() => setLayout(null))` sans état d'erreur
   fait repasser « un échec de lecture donne etat 'erreur' » au rouge.
   ========================================================================== */

const layout = vi.fn()
const enregistrerSectionLayout = vi.fn()
vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      layout: (...a) => layout(...a),
      enregistrerSectionLayout: (...a) => enregistrerSectionLayout(...a),
    },
  },
}))

const { default: useDocumentCalepinage, ecrireSection } = await import('./useDocumentCalepinage')

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('useDocumentCalepinage', () => {
  it('lit le document et son jeton : etat ok', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { zones: [{ id: 'z1' }] }, empreinte_document: 'E0' } })
    const { result } = renderHook(() => useDocumentCalepinage(7))
    expect(result.current.etat).toBe('chargement')
    await waitFor(() => expect(result.current.etat).toBe('ok'))
    expect(result.current.document).toEqual({ zones: [{ id: 'z1' }] })
    expect(result.current.empreinte).toBe('E0')
    expect(layout).toHaveBeenCalledWith(7)
  })

  it('un échec de lecture donne etat « erreur », jamais un document vide', async () => {
    layout.mockRejectedValue(new Error('500'))
    const { result } = renderHook(() => useDocumentCalepinage(7))
    await waitFor(() => expect(result.current.etat).toBe('erreur'))
    expect(result.current.document).toBeNull()
    expect(result.current.empreinte).toBeNull()
  })

  it('une réponse qui n’est pas un document est une erreur', async () => {
    layout.mockResolvedValue({ data: '<html>' })
    const { result } = renderHook(() => useDocumentCalepinage(7))
    await waitFor(() => expect(result.current.etat).toBe('erreur'))
    expect(result.current.document).toBeNull()
  })

  it('un calepinage sans conception lue avec succès rend un objet vide (ok), pas null', async () => {
    layout.mockResolvedValue({ data: { roof_layout: null, empreinte_document: 'E0' } })
    const { result } = renderHook(() => useDocumentCalepinage(7))
    await waitFor(() => expect(result.current.etat).toBe('ok'))
    expect(result.current.document).toEqual({})
  })

  it('sans identifiant : erreur, aucune requête', () => {
    const { result } = renderHook(() => useDocumentCalepinage(null))
    expect(result.current.etat).toBe('erreur')
    expect(layout).not.toHaveBeenCalled()
  })

  it('inactif : aucune lecture', () => {
    const { result } = renderHook(() => useDocumentCalepinage(7, { actif: false }))
    expect(layout).not.toHaveBeenCalled()
    expect(result.current.etat).toBe('chargement')
  })

  it('recharger relit ; appliquerSection garde document et jeton alignés', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { a: 1 }, empreinte_document: 'E0' } })
    const { result } = renderHook(() => useDocumentCalepinage(7))
    await waitFor(() => expect(result.current.etat).toBe('ok'))
    const generation = result.current.generation

    act(() => result.current.appliquerSection('b', 2, 'E1'))
    expect(result.current.document).toEqual({ a: 1, b: 2 })
    expect(result.current.empreinte).toBe('E1')
    expect(result.current.generation).toBe(generation) // pas une relecture

    layout.mockResolvedValue({ data: { roof_layout: { a: 9 }, empreinte_document: 'E2' } })
    act(() => result.current.recharger())
    await waitFor(() => expect(result.current.empreinte).toBe('E2'))
    expect(layout).toHaveBeenCalledTimes(2)
    expect(result.current.generation).not.toBe(generation)
    expect(result.current.document).toEqual({ a: 9 })
  })
})

describe('ecrireSection', () => {
  it('poste {cle, valeur, base_empreinte} et pousse la clé dans l’atelier vivant', async () => {
    enregistrerSectionLayout.mockResolvedValue({ data: { empreinte_document: 'E1' } })
    const documentVivant = { empreinte: 'EV', appliquerSection: vi.fn() }
    const res = await ecrireSection({
      calepinageId: 7, cle: 'poseSurfaces', valeur: [{ id: 's' }], empreinte: 'E0', documentVivant,
    })
    expect(res).toEqual({ ok: true, empreinte: 'E1' })
    expect(enregistrerSectionLayout).toHaveBeenCalledWith(7, {
      cle: 'poseSurfaces', valeur: [{ id: 's' }], base_empreinte: 'EV',
    })
    expect(documentVivant.appliquerSection).toHaveBeenCalledWith('poseSurfaces', [{ id: 's' }], 'E1')
  })

  it('sans jeton : aucun POST', async () => {
    const res = await ecrireSection({ calepinageId: 7, cle: 'underlay', valeur: null, empreinte: null })
    expect(res.ok).toBe(false)
    expect(enregistrerSectionLayout).not.toHaveBeenCalled()
  })

  it('409 = conflit, aucune clé poussée dans l’atelier', async () => {
    enregistrerSectionLayout.mockRejectedValue({ response: { status: 409, data: { detail: 'périmé' } } })
    const documentVivant = { empreinte: null, appliquerSection: vi.fn() }
    const res = await ecrireSection({
      calepinageId: 7, cle: 'horizonProfile', valeur: null, empreinte: 'E0', documentVivant,
    })
    expect(res).toEqual({ ok: false, conflit: true, motif: 'périmé' })
    expect(documentVivant.appliquerSection).not.toHaveBeenCalled()
  })
})
