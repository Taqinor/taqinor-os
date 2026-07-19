import { describe, it, expect } from 'vitest'
import { formatNumber, formatMAD, formatMoney, formatRatio } from './adsengine'

/* ENG21 — le module « Publicité » s'auto-enregistre via son module.config.jsx
   (pattern UX1, collecté par le glob de router/moduleRoutes.jsx) et est gaté
   responsable/admin. On vérifie ici la FORME de la config (nav ↔ routes ↔
   titres, rôles) comme le fait compta.test.jsx pour son propre module, plus les
   helpers de présentation purs partagés par les écrans ENG22–ENG28. */

describe('adsengine — helpers de formatage (montants MAD, jamais de valeur inventée)', () => {
  it('formatNumber groupe les milliers et rend « — » si la donnée manque', () => {
    expect(formatNumber(1234)).toBe('1 234')
    expect(formatNumber(1234567)).toBe('1 234 567')
    expect(formatNumber(0)).toBe('0')
    expect(formatNumber(null)).toBe('—')
    expect(formatNumber(undefined)).toBe('—')
    expect(formatNumber(NaN)).toBe('—')
  })

  it('formatNumber gère les décimales et les nombres négatifs', () => {
    expect(formatNumber(1234.5, 2)).toBe('1 234,50')
    expect(formatNumber(-4200)).toBe('-4 200')
    expect(formatNumber('850')).toBe('850')
  })

  it('formatMAD suffixe « MAD » (et propage le repli « — »)', () => {
    expect(formatMAD(1250)).toBe('1 250 MAD')
    expect(formatMAD(42.5, 2)).toBe('42,50 MAD')
    expect(formatMAD(null)).toBe('—')
  })

  it('formatMoney étiquette la devise du COMPTE (jamais MAD en dur)', () => {
    // Meta rapporte dans la devise du compte publicitaire (souvent USD).
    expect(formatMoney(1250, 'USD')).toBe('1 250 USD')
    expect(formatMoney(42.5, 'EUR', 2)).toBe('42,50 EUR')
    expect(formatMoney(1250)).toBe('1 250 MAD') // repli devise inconnue
    expect(formatMoney(null, 'USD')).toBe('—')
  })

  it('formatRatio rend une décimale par défaut', () => {
    expect(formatRatio(1.83)).toBe('1,8')
    expect(formatRatio(null)).toBe('—')
  })
})

describe('adsengine — module.config (auto-enregistrement ENG21)', () => {
  it('nav et routes sont cohérents, gatés responsable/admin', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('adsengine')
    // Écrans : dashboard, cockpit, approbations, campagnes, créatifs,
    // commentaires, instagram, expérimentations, plan de vol, backlog, règles,
    // simulation, reporting, brief, journal, connexion (écrans ADSDEEP ajoutés
    // au fil des tâches — cockpit ADSDEEP22, commentaires ADSDEEP54, IG ADSDEEP56).
    // +1 : « L'Arbre » (ASG6 — la vue plan-vivant de l'Assumption Engine).
    // +1 : « Table des faits » (PUB6/AGEN1 — versions + entrées + publication).
    expect(config.routes).toHaveLength(18)
    expect(config.nav.items).toHaveLength(18)
    expect(config.titles).toHaveLength(18)

    const routePaths = config.routes.map(r => r.path).sort()
    const navTargets = config.nav.items.map(i => i.to).sort()
    expect(navTargets).toEqual(routePaths)

    // Chaque route ET chaque item de nav est gaté responsable/admin.
    config.routes.forEach(r => expect(r.roles).toEqual(['responsable', 'admin']))
    config.nav.items.forEach(i => expect(i.roles).toEqual(['responsable', 'admin']))

    // La boîte d'approbation (écran-vaisseau-amiral) est présente.
    expect(routePaths).toContain('/publicite/approbations')
    expect(config.sectionLabels).toEqual({ publicite: 'Publicité' })
  })

  it('chaque item de nav porte un libellé et une icône', async () => {
    const { default: config } = await import('./module.config.jsx')
    config.nav.items.forEach(i => {
      expect(typeof i.label).toBe('string')
      expect(i.label.length).toBeGreaterThan(0)
      expect(i.icon).toBeTruthy()
    })
  })
})
