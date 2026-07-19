import { describe, it, expect } from 'vitest'
import { WIZARD_STEPS, HEALTH_REMEDIATIONS, stepStatus } from './connectionWizard'

/* PUB46 — Assistant de connexion guidé : contenu pur. */

describe('WIZARD_STEPS', () => {
  it('4 étapes obligatoires + 1 optionnelle, numérotées dans l’ordre', () => {
    expect(WIZARD_STEPS).toHaveLength(5)
    WIZARD_STEPS.forEach((s, i) => expect(s.numero).toBe(i + 1))
  })

  it('chaque étape porte un titre, une description et un lien externe', () => {
    WIZARD_STEPS.forEach(s => {
      expect(s.titre.length).toBeGreaterThan(0)
      expect(s.description.length).toBeGreaterThan(0)
      expect(s.lien).toMatch(/^https:\/\//)
      expect(s.lienLabel.length).toBeGreaterThan(0)
    })
  })

  it("aucun contenu ne mentionne « activer » (contrat : pas de toggle d'activation)", () => {
    WIZARD_STEPS.forEach(s => {
      expect(s.titre.toLowerCase()).not.toMatch(/activer/)
      expect(s.description.toLowerCase()).not.toMatch(/activer/)
    })
  })

  it("l'étape jeton pointe vers la clé de statut 'token'", () => {
    const tokenStep = WIZARD_STEPS.find(s => s.key === 'token')
    expect(tokenStep.statutCles).toEqual(['token'])
  })
})

describe('HEALTH_REMEDIATIONS', () => {
  it('couvre les clés de statut non triviales (token/ad_account/page/pixel/capi)', () => {
    for (const key of ['token', 'ad_account', 'page', 'pixel', 'capi']) {
      expect(HEALTH_REMEDIATIONS[key].message.length).toBeGreaterThan(0)
    }
  })

  it("aucune remédiation ne mentionne « activer »", () => {
    Object.values(HEALTH_REMEDIATIONS).forEach(r => {
      expect(r.message.toLowerCase()).not.toMatch(/activer/)
    })
  })
})

describe('stepStatus', () => {
  const step = (statutCles) => ({ statutCles })

  it('étape sans statut backend dédié -> "manuel"', () => {
    expect(stepStatus(step([]), {})).toBe('manuel')
  })

  it('toutes les clés vertes -> "ok"', () => {
    expect(stepStatus(step(['token']), { token: true })).toBe('ok')
    expect(stepStatus(step(['page', 'pixel']), { page: true, pixel: true })).toBe('ok')
  })

  it('une clé rouge -> "a_faire"', () => {
    expect(stepStatus(step(['page', 'pixel']), { page: true, pixel: false })).toBe('a_faire')
  })

  it('statut pas encore chargé -> "inconnu" (jamais fabriqué vert)', () => {
    expect(stepStatus(step(['token']), {})).toBe('inconnu')
    expect(stepStatus(step(['token']), null)).toBe('inconnu')
  })
})
