// NTI18N2 — Layout miroir RTL : /ui (galerie de composants, sans auth) + les
// 5 écrans clés cités par la tâche (Dashboard, CRM Leads kanban, Devis,
// Stock, Paramètres — projet `chromium`, déjà pré-authentifié via
// `storageState`, voir playwright.config.js). Bascule l'interface en arabe
// AVANT le premier paint (comme le thème sombre d'apps-a11y.spec.js) via le
// même mécanisme que le sélecteur de langue réel (`taqinor.locale` en
// localStorage, lu par `readInitialLocale()`/`I18nProvider`) — jamais un flag
// dédié au test.
//
// Vérifie deux choses objectives, mesurables sans jugement visuel :
//   1. `dir="rtl"` est bien posé sur `<html>` (le cadre i18n bascule) ;
//   2. AUCUN débordement horizontal du viewport — même technique que
//      `zoom.spec.js` (VX69) : `scrollWidth - innerWidth` doit rester ≤ 1px,
//      seuil qui absorbe l'arrondi sous-pixel sans laisser passer un vrai
//      chevauchement/texte tronqué qui pousse la largeur du document.
import { test, expect } from '@playwright/test'

const SCREENS = [
  { path: '/ui', label: '/ui (galerie de composants)' },
  { path: '/dashboard', label: 'Dashboard' },
  { path: '/crm/leads', label: 'CRM Leads (kanban)' },
  { path: '/ventes/devis', label: 'Devis' },
  { path: '/stock', label: 'Stock' },
  { path: '/parametres', label: 'Paramètres' },
]

async function forcerArabeRtl(page) {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor.locale', 'ar') } catch { /* mode privé */ }
  })
}

async function assertNoHOverflow(page, label) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow, `débordement horizontal RTL — ${label}`).toBeLessThanOrEqual(1)
}

test.describe('NTI18N2: layout miroir RTL — /ui + 5 écrans clés', () => {
  for (const { path, label } of SCREENS) {
    test(`${label} : dir=rtl posé, aucun débordement horizontal`, async ({ page }) => {
      await forcerArabeRtl(page)
      await page.goto(path)
      // Laisse le shell (sidebar/header) et le contenu de la page se peindre
      // avant de mesurer — un flash pré-hydratation fausserait la mesure.
      await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
      await page.waitForLoadState('networkidle')
      await assertNoHOverflow(page, label)
    })
  }
})
