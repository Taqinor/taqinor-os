import { describe, it, expect } from 'vitest'
import { fallbackPerKwc } from '@rooflib/productionEngine'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { productionAtelierDepuisChiffrage } from './useAtelierBoot'

/* ACAL994 — la production de l'atelier ERP vient du bloc `chiffrage` servi par design-context
   (ACAL993) quand il est servi ; sinon le repli de table, étiqueté « estimation ». Les valeurs
   viennent de l'exemple COMMITTÉ du contrat, jamais d'une charge utile écrite à la main. */
const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const CHIFFRAGE = CTX.chiffrage
const CFG = { panels: 100 }

describe('productionAtelierDepuisChiffrage (ACAL994)', () => {
  it('chiffrage servi ⇒ kWc × production par kWc = la production servie par le serveur', () => {
    const parKwc = productionAtelierDepuisChiffrage(CHIFFRAGE)(CFG)
    expect(CHIFFRAGE.production_annuelle_kwh.etat).toBe('servi')
    expect(parKwc.annualKwh * CHIFFRAGE.kwc.valeur)
      .toBeCloseTo(CHIFFRAGE.production_annuelle_kwh.valeur, 6)
    expect(parKwc.monthlyKwh).toHaveLength(12)
    expect(parKwc.monthlyKwh.reduce((a, b) => a + b, 0)).toBeCloseTo(parKwc.annualKwh, 6)
    // Valeur NAVIGATEUR tant que rien n'est enregistré : la source reste « estimation ».
    expect(parKwc.source).toBe('estimate')
  })

  it('non servi ⇒ le repli de table, jamais le chiffre du serveur', () => {
    const repli = fallbackPerKwc().annualKwh
    for (const etat of ['non_servi', 'indisponible']) {
      const bloc = { ...CHIFFRAGE, production_annuelle_kwh: { ...CHIFFRAGE.production_annuelle_kwh, etat } }
      expect(productionAtelierDepuisChiffrage(bloc)(CFG).annualKwh).toBe(repli)
    }
  })

  it('aucun chiffrage ou kWc non servi ⇒ le repli de table', () => {
    const repli = fallbackPerKwc().annualKwh
    expect(productionAtelierDepuisChiffrage(undefined)(CFG).annualKwh).toBe(repli)
    expect(productionAtelierDepuisChiffrage(null)(CFG).annualKwh).toBe(repli)
    const sansKwc = { ...CHIFFRAGE, kwc: { ...CHIFFRAGE.kwc, etat: 'non_servi' } }
    expect(productionAtelierDepuisChiffrage(sansKwc)(CFG).annualKwh).toBe(repli)
  })
})
