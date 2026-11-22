import { describe, it, expect, vi } from 'vitest'
import { fallbackPerKwc } from '@rooflib/productionEngine'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import {
  productionAtelierDepuisChiffrage, adresseSansDoublon, MESSAGE_ACCES_REFUSE,
  cadrerToitAtelier, ZOOM_MAX_CADRAGE_ATELIER, hauteurCouverteParTiroir,
} from './useAtelierBoot'

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

describe('R2-03 / R2-20', () => {
  it('la ville déjà portée par l’adresse n’est pas répétée', () => {
    expect(adresseSansDoublon('Quartier Founty, Agadir', 'Agadir')).toBe('Quartier Founty, Agadir')
    expect(adresseSansDoublon('Quartier Founty, agadir', 'Agadir ')).toBe('Quartier Founty, agadir')
    expect(adresseSansDoublon('12 rue des Oliviers', 'Casablanca')).toBe('12 rue des Oliviers, Casablanca')
    expect(adresseSansDoublon('', 'Casablanca')).toBe('Casablanca')
    expect(adresseSansDoublon(null, null)).toBe('')
  })

  it('un 403 dit le refus de droit, jamais « introuvable — réessayez »', () => {
    expect(MESSAGE_ACCES_REFUSE).toBe('Vous n’avez pas accès à ce calepinage.')
  })
})

describe('F6 — cadrage du toit par l’atelier ERP', () => {
  it('demande le cadrage avec le plafond relevé de l’atelier (22, le site public garde 19)', () => {
    const cadrerToit = vi.fn(() => true)
    expect(cadrerToitAtelier({ cadrerToit })).toBe(true)
    expect(cadrerToit).toHaveBeenCalledWith({ zoomMax: ZOOM_MAX_CADRAGE_ATELIER, basPx: 0 })
    expect(ZOOM_MAX_CADRAGE_ATELIER).toBe(22)
  })
  it('H1 — tablette : le cadrage vise la partie de la carte AU-DESSUS du tiroir (pixels couverts mesurés)', () => {
    const boite = (top, bottom) => ({ getBoundingClientRect: () => ({ top, bottom }) })
    const racine = (tiroir) => ({
      getElementById: (id) => (id === 'rp9-map' ? boite(64, 820) : null),
      querySelector: () => tiroir,
    })
    expect(hauteurCouverteParTiroir(racine(boite(540, 820)))).toBe(280)
    expect(hauteurCouverteParTiroir(racine(null)), 'bureau : aucun tiroir').toBe(0)
    expect(hauteurCouverteParTiroir(null)).toBe(0)
    const cadrerToit = vi.fn(() => true)
    cadrerToitAtelier({ cadrerToit }, racine(boite(540, 820)))
    expect(cadrerToit).toHaveBeenCalledWith({ zoomMax: ZOOM_MAX_CADRAGE_ATELIER, basPx: 280 })
  })
  it('sans constructeur ou sans `cadrerToit` : rien, jamais une erreur', () => {
    expect(cadrerToitAtelier(null)).toBe(false)
    expect(cadrerToitAtelier({})).toBe(false)
  })
})
