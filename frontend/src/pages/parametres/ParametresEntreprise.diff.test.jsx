import {
  definirProfil, rendreParametresEntreprise, updateProfile,
} from '../../test/parametresEntrepriseHarness'
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { diffProfilePayload } from './peConstants'

/* APAR16 — l'écran Paramètres (profil société) n'envoie que le SEUL diff des
   champs modifiés + l'`updated_at` lu au chargement (verrou optimiste). Avant :
   `{...form}` complet → l'enregistrement de A réécrivait le RIB que B venait
   de changer. */

const PROFIL = {
  id: 1, nom: 'Démo', rib: 'RIB-B', tva_standard: 20, tva_panneaux: 10,
  ice: '', email: '', telephone: '', updated_at: '2026-10-08T10:00:00.123456Z',
}

describe('APAR16 — diffProfilePayload', () => {
  it('ne garde que les clés modifiées + updated_at', () => {
    const base = { rib: 'B', tva_standard: 20, payment_terms: { r: [1, 2] } }
    const next = { rib: 'B', tva_standard: 14, payment_terms: { r: [1, 2] } }
    expect(diffProfilePayload(base, next, 'T0')).toEqual({ tva_standard: 14, updated_at: 'T0' })
  })
  it('objets imbriqués comparés par valeur', () => {
    const base = { payment_terms: { r: [1, 2] } }
    const next = { payment_terms: { r: [1, 3] } }
    expect(diffProfilePayload(base, next, 'T')).toEqual({ payment_terms: { r: [1, 3] }, updated_at: 'T' })
  })
})

describe('APAR16 — Enregistrer envoie le seul champ modifié', () => {
  beforeEach(() => {
    definirProfil(PROFIL)
    updateProfile.mockImplementation((data) => Promise.resolve({ data: { ...PROFIL, ...data } }))
  })
  afterEach(() => { cleanup(); updateProfile.mockReset() })

  it('seul le champ modifié part (avec updated_at), jamais le RIB', async () => {
    const { container } = rendreParametresEntreprise()
    await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
    const nom = container.querySelector('input[name="nom"]')
    fireEvent.change(nom, { target: { name: 'nom', value: 'Démo SARL' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    const envoye = updateProfile.mock.calls[0][0]
    expect(envoye).toEqual({ nom: 'Démo SARL', updated_at: PROFIL.updated_at })
    expect(envoye).not.toHaveProperty('rib')
  })
})
