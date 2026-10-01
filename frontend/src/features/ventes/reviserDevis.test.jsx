// QJR533 — « Réviser » dit ce qui se passe et ouvre la V2 en Édition complète.
// Run : npx vitest run src/features/ventes/reviserDevis.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../../api/ventesApi', () => ({
  default: { reviserDevis: vi.fn() },
}))

import ventesApi from '../../api/ventesApi'
import { toast } from '../../ui'
import { reviserEtOuvrir } from './reviserDevis'

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
