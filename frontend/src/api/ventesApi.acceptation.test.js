import { describe, it, expect, vi } from 'vitest'

vi.mock('./axios', () => ({ default: { post: vi.fn(() => Promise.resolve({ data: {} })) } }))

import api from './axios'
import ventesApi, { acceptationDejaFaite } from './ventesApi'

// 08/10/2026 — la réponse d'acceptation perdue (timeout) puis re-clic → 409
// « déjà accepté » : c'est un succès (le devis EST accepté), on fête.
describe('acceptationDejaFaite', () => {
  it('409 « déjà accepté » = succès', () => {
    expect(acceptationDejaFaite({ response: { status: 409, data: { detail: 'Ce devis est déjà accepté.' } } })).toBe(true)
  })
  it('autre 409 (devis remplacé) reste une erreur', () => {
    expect(acceptationDejaFaite({ response: { status: 409, data: { detail: 'Cette proposition a été remplacée par DEV-1.' } } })).toBe(false)
  })
  it('timeout / 400 restent des erreurs', () => {
    expect(acceptationDejaFaite({ code: 'ECONNABORTED' })).toBe(false)
    expect(acceptationDejaFaite({ response: { status: 400, data: { detail: 'déjà accepté' } } })).toBe(false)
  })
})

// AMSG34 (C-AMSG-015) — l'adresse saisie part sous la clé que le serveur lit
// (`to_email`, facture_documents.py::envoyer_email) ; sans adresse, corps vide.
describe('envoyerEmailFacture', () => {
  it('envoyerEmailFacture poste to_email', async () => {
    await ventesApi.envoyerEmailFacture(7, 'x@example.invalid')
    expect(api.post).toHaveBeenLastCalledWith('/ventes/factures/7/envoyer-email/', { to_email: 'x@example.invalid' })
    await ventesApi.envoyerEmailFacture(7)
    expect(api.post).toHaveBeenLastCalledWith('/ventes/factures/7/envoyer-email/', {})
  })
})
