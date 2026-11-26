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

const { default: useDocumentCalepinage, ecrireSection, appliquerSectionEcrite } = await import('./useDocumentCalepinage')

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
    layout.mockResolvedValue({ data: { roof_layout: null, empreinte_document: null } })
    const { result } = renderHook(() => useDocumentCalepinage(7))
    await waitFor(() => expect(result.current.etat).toBe('ok'))
    expect(result.current.document).toEqual({})
    // ACAL360 — le serveur sert null pour un document vide : jeton ''.
    expect(result.current.empreinte).toBe('')
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

  it('sans jeton (null) : aucun POST', async () => {
    const res = await ecrireSection({ calepinageId: 7, cle: 'underlay', valeur: null, empreinte: null })
    expect(res.ok).toBe(false)
    expect(enregistrerSectionLayout).not.toHaveBeenCalled()
  })

  it('document vide : poste base_empreinte \'\'', async () => {
    enregistrerSectionLayout.mockResolvedValue({ data: { empreinte_document: 'E1' } })
    const res = await ecrireSection({
      calepinageId: 7, cle: 'horizonProfile', valeur: { points: [] }, empreinte: '',
    })
    expect(res).toEqual({ ok: true, empreinte: 'E1' })
    expect(enregistrerSectionLayout).toHaveBeenCalledWith(7, {
      cle: 'horizonProfile', valeur: { points: [] }, base_empreinte: '',
    })
  })

  it('409 jeton périmé = conflit, aucune clé poussée dans l’atelier', async () => {
    // Forme RÉELLE de DocumentModifie.corps() : {detail, code, empreinte_courante}.
    enregistrerSectionLayout.mockRejectedValue({ response: { status: 409, data: {
      detail: 'périmé', code: 'document_modifie', empreinte_courante: 'E1' } } })
    const documentVivant = { empreinte: null, appliquerSection: vi.fn() }
    const res = await ecrireSection({
      calepinageId: 7, cle: 'horizonProfile', valeur: null, empreinte: 'E0', documentVivant,
    })
    expect(res).toEqual({ ok: false, conflit: true, motif: 'périmé' })
    expect(documentVivant.appliquerSection).not.toHaveBeenCalled()
  })

  it('ACAL280 — 409 verrou : PAS un conflit, le motif serveur tel quel', async () => {
    enregistrerSectionLayout.mockRejectedValue({ response: { status: 409, data: {
      roof_layout: ['Devis accepté : révisez-le (V2).'] } } })
    const res = await ecrireSection({
      calepinageId: 7, cle: 'horizonProfile', valeur: null, empreinte: 'E0',
    })
    expect(res).toEqual({ ok: false, conflit: false, motif: 'Devis accepté : révisez-le (V2).' })
  })
})

/* ACAL1816 — après « Enregistrer le profil » (Horizon), l'en-tête ne repasse plus à « Modifications non
   enregistrées » : la section ÉCRITE (empreinte servie) rebase la référence d'une scène propre. Mutant :
   pousser à la scène sans rebaser ⇒ la scène (qui porte maintenant le profil) diffère de sa référence. */
describe('ACAL1816 — appliquerSectionEcrite (document vivant de l’atelier)', () => {
  /** Une scène simulée : son empreinte change quand une section y est appliquée. */
  function atelier({ modifieeAvant = false } = {}) {
    const scene = { courant: modifieeAvant ? 'S-modifiee' : 'S0', reference: 'S0' }
    const poserEmpreinte = vi.fn()
    const vivant = {
      appliquerALaScene: vi.fn((cle) => { scene.courant = `${scene.courant}+${cle}` }),
      poserEmpreinte,
      sceneModifiee: () => scene.courant !== scene.reference,
      rebaserScene: () => { scene.reference = scene.courant },
    }
    const doc = { empreinte: 'E0', appliquerSection: (cle, valeur, apres) => appliquerSectionEcrite(vivant, cle, valeur, apres) }
    return { scene, doc, poserEmpreinte }
  }

  it('section écrite sur une scène propre : jeton servi repris, scène non modifiée', async () => {
    enregistrerSectionLayout.mockResolvedValue({ data: { empreinte_document: 'E1' } })
    const { scene, doc, poserEmpreinte } = atelier()
    const res = await ecrireSection({ calepinageId: 7, cle: 'horizonProfile', valeur: { points: [] }, empreinte: 'E0', documentVivant: doc })
    expect(res).toEqual({ ok: true, empreinte: 'E1' })
    expect(poserEmpreinte).toHaveBeenCalledWith('E1')
    expect(scene.courant).toBe('S0+horizonProfile')
    expect(scene.courant).toBe(scene.reference)
  })

  it('scène déjà modifiée ailleurs : elle le reste ; sans empreinte servie : rien n’est rebasé', () => {
    const modifiee = atelier({ modifieeAvant: true })
    modifiee.doc.appliquerSection('horizonProfile', null, 'E1')
    expect(modifiee.scene.courant).not.toBe(modifiee.scene.reference)
    const sansJeton = atelier()
    sansJeton.doc.appliquerSection('choixConception', {}, null)
    expect(sansJeton.poserEmpreinte).not.toHaveBeenCalled()
    expect(sansJeton.scene.courant).not.toBe(sansJeton.scene.reference)
  })
})
