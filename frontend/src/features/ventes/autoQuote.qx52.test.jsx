import { describe, it, expect } from 'vitest'
import { LEAD_TYPE_TO_MODE, libelleSuccesDevisAuto } from './autoQuote'
import { DAY_USAGE_DEFAULTS } from './solar'

// QX52 — parité mode↔type sur 4 modes (frontend). Aucun mode ne tombe dans le
// libellé/comportement d'un autre : commercial route vers SON mode (plus le
// repli historique vers industriel).

describe('QX52 — LEAD_TYPE_TO_MODE (4 modes cohérents)', () => {
  it('commercial route désormais vers commercial (plus industriel)', () => {
    expect(LEAD_TYPE_TO_MODE.commercial).toBe('commercial')
  })

  it('chaque type de lead route vers son propre mode', () => {
    expect(LEAD_TYPE_TO_MODE.residentiel).toBe('residentiel')
    expect(LEAD_TYPE_TO_MODE.industriel).toBe('industriel')
    expect(LEAD_TYPE_TO_MODE.agricole).toBe('agricole')
  })

  it('commercial et industriel restent DISTINCTS', () => {
    expect(LEAD_TYPE_TO_MODE.commercial).not.toBe(LEAD_TYPE_TO_MODE.industriel)
  })

  it('aucune valeur cible n’est hors des 4 modes canoniques', () => {
    const valid = new Set(['residentiel', 'commercial', 'industriel', 'agricole'])
    for (const v of Object.values(LEAD_TYPE_TO_MODE)) {
      expect(valid.has(v)).toBe(true)
    }
  })
})

describe('CIQ128 — plus de part diurne C&I d’écran', () => {
  it('DAY_USAGE_DEFAULTS ne porte plus d’entrée commerciale ni industrielle', () => {
    expect(DAY_USAGE_DEFAULTS).not.toHaveProperty('Commerciale')
    expect(DAY_USAGE_DEFAULTS).not.toHaveProperty('Industrielle')
    expect(typeof DAY_USAGE_DEFAULTS['Résidentielle']).toBe('number')
  })
})

// D 17/11/2026 — le bandeau de succès dit aussi l'option AVEC batterie.
describe('libelleSuccesDevisAuto — option avec batterie', () => {
  const normaliser = (t) => t.replace(/[\u202f\u00a0]/g, ' ')
  const base = { reference: 'DEV-1', kwc: 5, total_ttc: 41000, economie_an_1_ht: 12000, retour_ans: 4.2 }
  it('sans les clés « avec » : la phrase historique, inchangée', () => {
    expect(normaliser(libelleSuccesDevisAuto(base)))
      .toBe('DEV-1 · 5 kWc · 41 000 MAD TTC · économie ≈ 12 000 MAD/an · retour ≈ 4,2 ans')
    expect(libelleSuccesDevisAuto({ ...base, economie_an_1_ht_avec: null, retour_ans_avec: null }))
      .toBe(libelleSuccesDevisAuto(base))
  })
  it('avec les clés « avec » : les deux options sont libellées', () => {
    const t = normaliser(libelleSuccesDevisAuto({
      ...base, economie_an_1_ht_avec: 15000, retour_ans_avec: 6.1, kwc_avec: 6,
    }))
    expect(t).toContain('sans batterie : économie ≈ 12 000 MAD/an · retour ≈ 4,2 ans')
    expect(t).toContain('avec batterie : économie ≈ 15 000 MAD/an · retour ≈ 6,1 ans')
  })
})

// T4-V2-013 / T4-V2-015 — « Devis créé : DEV-… · 3,85 kWc · 61 800 MAD TTC » étaient
// les chiffres de l'option AVEC batterie, non dits ; l'option sans batterie
// n'apparaissait nulle part. Un lead qui souhaite une batterie n'a qu'UNE option,
// et rien ne le disait. Le bandeau lit `options` / `option_unique` servis.
describe('T4-V2-013/015 — le bandeau nomme la ou les options', () => {
  const normaliser = (t) => t.replace(/\s/g, ' ')
  const OPTIONS = [
    { variante: 'sans', libelle: 'Sans batterie', kwc: 2.2, nb_panneaux: 4, total_ttc: '37800.00' },
    { variante: 'avec', libelle: 'Avec batterie', kwc: 3.85, nb_panneaux: 7, total_ttc: '61800.00' },
  ]
  it('deux options : chacune avec SON kWc et SON total', () => {
    const t = normaliser(libelleSuccesDevisAuto({
      reference: 'DEV-202611-0118', kwc: 3.85, total_ttc: 61800, options: OPTIONS, option_unique: null,
    }))
    expect(t).toBe('DEV-202611-0118 · Sans batterie : 2,2 kWc · 37 800 MAD TTC · Avec batterie : 3,85 kWc · 61 800 MAD TTC')
  })
  it('option unique avec batterie souhaitée sur la fiche : dit', () => {
    const t = normaliser(libelleSuccesDevisAuto({
      reference: 'DEV-202611-0119', kwc: 5.5, total_ttc: 74700,
      options: [{ variante: '', libelle: 'Option unique', kwc: 5.5, nb_panneaux: 10, total_ttc: '74700.00' }],
      option_unique: { batterie: true, souhait_fiche: true },
    }))
    // Relecture m2 — et où demander les deux options (le contrôle réel de la fiche).
    expect(t).toBe('DEV-202611-0119 · 5,5 kWc · 74 700 MAD TTC · option unique : avec batterie (batterie souhaitée sur la fiche)'
      + ' · pour comparer les deux, choisissez « Les deux options » au champ « Batterie » de la fiche (Toiture & site)')
  })
  it('option unique sans batterie, sans souhait de la fiche : dit sans raison inventée', () => {
    const t = normaliser(libelleSuccesDevisAuto({
      reference: 'DEV-1', kwc: 3, total_ttc: 30000, option_unique: { batterie: false, souhait_fiche: false },
    }))
    expect(t).toBe('DEV-1 · 3 kWc · 30 000 MAD TTC · option unique : sans batterie')
  })
})

// T4-U1-026 — le bandeau dit la MÊME puissance que le devis et son PDF
// (« 5,5 kWc »), jamais un entier arrondi (« 6 kWc »).
describe('T4-U1-026 — kWc du bandeau de succès', () => {
  const normaliser = (t) => t.replace(/\s/g, ' ')
  it.each([[5.5, '5,5 kWc'], [3.85, '3,85 kWc'], [6, '6 kWc']])('%s → %s', (kwc, attendu) => {
    expect(normaliser(libelleSuccesDevisAuto({ reference: 'DEV-1', kwc })))
      .toBe(`DEV-1 · ${attendu}`)
  })
})
