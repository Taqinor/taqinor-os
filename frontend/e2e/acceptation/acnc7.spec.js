// Preuve en direct ACNC, lot 7 (contre-visite du 15/11, C-ACNC-VER3-300) : ACNC73 (PLAN_AUDIT_STOCK.md) — la fiche
// facture fournisseur relit la facture après une réponse perdue sur « Ajouter le paiement ».
//
// Règle de preuve (METHODE §C.4 point 7) : le geste est joué À L'ÉCRAN sous le rôle LIVRÉ « Directeur » du registre
// (compte d'essai connecté PAR L'ÉCRAN DE CONNEXION) ; la réponse du POST est coupée APRÈS passage au serveur
// (`route.fetch()` puis `route.abort()`, patron d'acnc6.spec.js PF9.4-ACNC72) ; la base est relue par le shell Django.
// Facture fournisseur de 10 000 TTC créée par le shell, retirée à la fin.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI } from './_django.js'
import { uiLoginJusquAuxApps } from '../helpers.js'
import { monter, T, marque, SOC, note, ouverts } from './_acnc.js'

const etape = groupe('ACNC', ['ACNC73'])
monter()
const J = JSON.stringify
const INIT = () => {
  try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
}
const apres = []
test.afterEach(async () => {
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})

/** Compte d'essai du rôle LIVRÉ `nomRole` (rôle système de la société démo, palier dérivé du rôle). */
async function compte(prefixe, nomRole) {
  const nom = `${prefixe}_${marque()}`
  await py(`from apps.roles.models import Role
from authentication.role_tiers import tier_for_role_fields
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True)
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
u.role_legacy = tier_for_role_fields(r.nom, r.est_systeme, r.permissions); u.save(update_fields=['role_legacy'])
sortie(u.id)`)
  return nom
}
/** Navigateur À FROID du compte `nom` (connexion par l'écran), surveillé par les oracles. */
async function ecran(page, suivi, testInfo, nom) {
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block', viewport: { width: 1600, height: 1000 },
  })
  ouverts.push(ctx)
  if (!page.isClosed()) await page.close()
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  return p
}

const factureFournisseur = (m) => py(`import datetime
from decimal import Decimal
from apps.stock.models import Fournisseur
from apps.achats.models import FactureFournisseur
f = Fournisseur.objects.create(company_id=${SOC}, nom='Fournisseur ACNC73 ${m}', type='service')
ttc = Decimal('10000'); ht = (ttc / Decimal('1.2')).quantize(Decimal('0.01'))
ff = FactureFournisseur.objects.create(company_id=${SOC}, reference='FF-ACNC73-${m}', fournisseur=f,
    date_facture=datetime.date.today(), montant_ht=ht, montant_tva=ttc - ht, montant_ttc=ttc)
sortie(dict(f=f.pk, ff=ff.pk, ref=ff.reference, solde=str(ff.solde_du)))`)
const retirer = (x) => py(`from apps.stock.models import Fournisseur
from apps.achats.models import FactureFournisseur, PaiementFournisseur
PaiementFournisseur.objects.filter(facture_id=${x.ff}).delete(); FactureFournisseur.objects.filter(pk=${x.ff}).delete(); Fournisseur.objects.filter(pk=${x.f}).delete()
sortie(True)`)
const base = (x) => py(`from apps.achats.models import FactureFournisseur, PaiementFournisseur
ff = FactureFournisseur.objects.get(pk=${x.ff})
sortie({'reglements': [str(p.montant) for p in PaiementFournisseur.objects.filter(facture=ff).order_by('pk')], 'solde': str(ff.solde_du)})`)

etape('PF9.4-ACNC73-fiche-facture', ['ACNC73'], async ({ page, suivi, testInfo }) => {
  const nom = await compte('acnc73', 'Directeur')
  const m = marque()
  const x = await factureFournisseur(m)
  apres.push(() => retirer(x))
  expect(Number(x.solde), 'Given : facture fournisseur de 10 000 TTC à payer').toBe(10000)
  const rx = new RegExp(`/api/django/stock/factures-fournisseur/${x.ff}/paiements/$`)
  const relecture = new RegExp(`/api/django/stock/factures-fournisseur/${x.ff}/$`)
  const envois = []
  const p = await ecran(page, suivi, testInfo, nom)
  p.on('request', (q) => { if (q.method() === 'POST' && rx.test(q.url().split('?')[0])) envois.push(q.headers()['idempotency-key'] ?? null) })
  suivi.attendre(rx, 'reseau')
  let coupe = true
  await p.route(rx, async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    if (coupe) { coupe = false; await route.fetch(); return route.abort('failed') }
    return route.continue()
  })
  const ouvrir = async () => {
    await p.goto('/stock/factures-fournisseur')
    await p.getByPlaceholder('Rechercher (référence, fournisseur)…').fill(x.ref, { timeout: 60_000 })
    await p.getByRole('row').filter({ hasText: x.ref }).getByText(x.ref).first().click({ timeout: 60_000 })
    const dlg = p.getByRole('dialog').filter({ hasText: `Facture — ${x.ref}` })
    await expect(dlg, 'fiche de la facture ouverte').toBeVisible({ timeout: 30_000 })
    return dlg
  }
  const soldeDu = (dlg) => dlg.getByText('Solde dû', { exact: true }).locator('..')
  const lignesPaiement = (dlg) => dlg.getByRole('row').filter({ hasText: /3\s?000/ })
  let dlg = await ouvrir()
  await expect(dlg.getByText('Aucun paiement.'), 'Given : aucun paiement').toBeVisible()
  await expect(soldeDu(dlg), 'Given : solde dû 10 000').toContainText(/10\s?000/)

  // 3 000 : la réponse du POST est coupée APRÈS passage au serveur ; la fiche relit la facture (GET) sans rechargement.
  await dlg.locator('#pay-montant').fill('3000')
  const relue = p.waitForResponse((q) => q.request().method() === 'GET' && relecture.test(q.url().split('?')[0]), T)
  await dlg.getByRole('button', { name: 'Ajouter le paiement' }).click()
  await expect.poll(() => envois.length, { timeout: 30_000 }).toBe(1)
  expect((await relue).status(), 'la fiche relit sa facture après la réponse perdue').toBe(200)
  expect(await base(x), 'shell : le POST coupé est passé au serveur (un règlement de 3 000, solde 7 000)')
    .toEqual({ reglements: ['3000.00'], solde: '7000.00' })
  // AVANT tout second clic : la fiche montre le règlement de 3 000 et le solde relu de 7 000.
  await expect(lignesPaiement(dlg), 'avant le second clic : règlement de 3 000 affiché').toHaveCount(1, { timeout: 30_000 })
  await expect(dlg.getByText('Aucun paiement.'), 'avant le second clic : plus « Aucun paiement »').toHaveCount(0)
  await expect(soldeDu(dlg), 'avant le second clic : solde dû relu 7 000').toContainText(/7\s?000/)
  const bandeau = await dlg.getByRole('alert').allInnerTexts().catch(() => [])
  note(testInfo, 'bandeau après la réponse perdue', J(bandeau))

  // Un simple réessai (même saisie, même clé) ne crée AUCUN second règlement.
  const [rep] = await Promise.all([
    p.waitForResponse((q) => q.request().method() === 'POST' && rx.test(q.url().split('?')[0]), T),
    dlg.getByRole('button', { name: 'Ajouter le paiement' }).click(),
  ])
  note(testInfo, 'réessai', `HTTP ${rep.status()} rejoué=${rep.headers()['idempotent-replayed'] ?? rep.headers()['idempotency-replayed'] ?? '?'}`)
  expect(rep.status(), `réessai : ${(await rep.text()).slice(0, 200)}`).toBeLessThan(300)
  expect(envois.length, 'deux envois').toBe(2)
  expect(envois[0], 'une clé envoyée').toBeTruthy()
  expect(envois[1], 'simple réessai : MÊME clé').toBe(envois[0])
  expect(await base(x), 'shell : toujours UN règlement de 3 000, solde 7 000').toEqual({ reglements: ['3000.00'], solde: '7000.00' })
  await expect(lignesPaiement(dlg), 'après le réessai : un seul règlement affiché').toHaveCount(1, { timeout: 30_000 })
  await expect(soldeDu(dlg), 'après le réessai : solde 7 000').toContainText(/7\s?000/)

  // Persistance : refermer puis rouvrir la fiche ⇒ mêmes règlements et même solde ; puis après rechargement.
  await p.unrouteAll({ behavior: 'ignoreErrors' })
  await dlg.getByRole('button', { name: 'Fermer' }).first().click()
  await expect(dlg, 'fiche refermée').toBeHidden({ timeout: 30_000 })
  await p.getByRole('row').filter({ hasText: x.ref }).getByText(x.ref).first().click({ timeout: 60_000 })
  dlg = p.getByRole('dialog').filter({ hasText: `Facture — ${x.ref}` })
  await expect(dlg, 'fiche rouverte').toBeVisible({ timeout: 30_000 })
  await expect(lignesPaiement(dlg), 'rouverte : un règlement de 3 000').toHaveCount(1, { timeout: 30_000 })
  await expect(soldeDu(dlg), 'rouverte : solde 7 000').toContainText(/7\s?000/)
  await p.reload()
  dlg = await ouvrir()
  await expect(lignesPaiement(dlg), 'rechargée : un règlement de 3 000').toHaveCount(1, { timeout: 30_000 })
  await expect(soldeDu(dlg), 'rechargée : solde 7 000').toContainText(/7\s?000/)
})
