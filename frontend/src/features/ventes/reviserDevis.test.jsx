// QJR533 — « Réviser » dit ce qui se passe et ouvre la V2 en Édition complète.
// Run : npx vitest run src/features/ventes/reviserDevis.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../../api/ventesApi', () => ({
  default: { reviserDevis: vi.fn() },
}))

import ventesApi from '../../api/ventesApi'
import { toast } from '../../ui'
import { reviserEtOuvrir, conflitDevis } from './reviserDevis'
import { documentContrat } from '../../test/fixtures/contractSamples'

const DEVIS = { id: 12, reference: 'DEV-202609-0012', chantier: null }

beforeEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('QJR533 — reviserEtOuvrir', () => {
  it('409 {detail} → toast.error du message serveur, pas de navigation', async () => {
    const erreur = vi.spyOn(toast, 'error').mockImplementation(() => {})
    const navigate = vi.fn()
    ventesApi.reviserDevis.mockRejectedValue({
      response: { status: 409, data: { detail: 'Déjà remplacé par DEV-202609-0013.' } },
    })
    const r = await reviserEtOuvrir({ devis: DEVIS, navigate })
    expect(r).toBeNull()
    expect(erreur).toHaveBeenCalledWith('Déjà remplacé par DEV-202609-0013.')
    expect(navigate).not.toHaveBeenCalled()
  })

  it('échec sans message → texte de repli, pas de navigation', async () => {
    const erreur = vi.spyOn(toast, 'error').mockImplementation(() => {})
    const navigate = vi.fn()
    ventesApi.reviserDevis.mockRejectedValue(new Error('réseau'))
    await reviserEtOuvrir({ devis: DEVIS, navigate })
    expect(erreur).toHaveBeenCalledWith(expect.stringContaining('révision'))
    expect(navigate).not.toHaveBeenCalled()
  })

  it("succès {id: 99} → toast.success puis navigate('/ventes/devis/nouveau?edit=99')", async () => {
    const ok = vi.spyOn(toast, 'success').mockImplementation(() => {})
    const navigate = vi.fn()
    const onApres = vi.fn()
    ventesApi.reviserDevis.mockResolvedValue({ data: { id: 99, reference: 'DEV-202609-0099' } })
    await reviserEtOuvrir({ devis: DEVIS, navigate, onApres })
    expect(ok).toHaveBeenCalledWith('Version créée : DEV-202609-0099')
    expect(navigate).toHaveBeenCalledWith('/ventes/devis/nouveau?edit=99')
    expect(onApres).toHaveBeenCalledTimes(1)
  })

  it("chantier 'en_cours' → toast.warning AVANT l'appel serveur", async () => {
    const ordre = []
    vi.spyOn(toast, 'warning').mockImplementation(() => { ordre.push('warning') })
    vi.spyOn(toast, 'success').mockImplementation(() => {})
    ventesApi.reviserDevis.mockImplementation(() => {
      ordre.push('appel')
      return Promise.resolve({ data: { id: 99, reference: 'X' } })
    })
    await reviserEtOuvrir({
      devis: { ...DEVIS, chantier: { id: 7, reference: 'CH-7', statut: 'en_cours' } },
      navigate: vi.fn(),
    })
    expect(ordre).toEqual(['warning', 'appel'])
  })
})

// VNT80 — un 409 qui NOMME un autre devis (forme unique `successeur` VNT24, ou
// `vente_active` VNT54 ; exemples committés de devis_prix_negocie.json) rend
// `{conflit, successeur}` à l'appelant, qui l'affiche sous la carte.
describe('VNT80 — conflit nommant un autre devis', () => {
  const ERREURS = documentContrat('ventes', 'devis_prix_negocie').erreurs_409
  const refus = (data) => ({ response: { status: 409, data } })

  it('conflitDevis lit le CODE du corps : successeur ou vente_active, sinon null', () => {
    expect(conflitDevis(ERREURS.version_remplacee)).toEqual({
      code: 'version_remplacee', conflit: ERREURS.version_remplacee.detail,
      successeur: ERREURS.version_remplacee.successeur,
    })
    expect(conflitDevis(ERREURS.vente_active_existante).successeur).toEqual(ERREURS.vente_active_existante.vente_active)
    expect(conflitDevis(ERREURS.pas_une_vente_active)).toBeNull()
    expect(conflitDevis(null)).toBeNull()
  })

  it('version remplacée + onConflit : {conflit, successeur} rendu, aucun toast, aucune navigation', async () => {
    const erreur = vi.spyOn(toast, 'error').mockImplementation(() => {})
    const navigate = vi.fn()
    const onConflit = vi.fn()
    ventesApi.reviserDevis.mockRejectedValue(refus(ERREURS.version_remplacee))
    const r = await reviserEtOuvrir({ devis: DEVIS, navigate, onConflit })
    const attendu = { conflit: ERREURS.version_remplacee.detail, successeur: ERREURS.version_remplacee.successeur }
    expect(r).toEqual(attendu)
    expect(onConflit).toHaveBeenCalledWith(attendu)
    expect(erreur).not.toHaveBeenCalled()
    expect(navigate).not.toHaveBeenCalled()
  })

  it('vente active existante sans onConflit : toast du message serveur, conflit rendu', async () => {
    const erreur = vi.spyOn(toast, 'error').mockImplementation(() => {})
    ventesApi.reviserDevis.mockRejectedValue(refus(ERREURS.vente_active_existante))
    const r = await reviserEtOuvrir({ devis: DEVIS, navigate: vi.fn() })
    expect(r.successeur).toEqual(ERREURS.vente_active_existante.vente_active)
    expect(erreur).toHaveBeenCalledWith(ERREURS.vente_active_existante.detail)
  })
})
