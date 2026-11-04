// ADVS27, ADVS36 — preuves à l'écran du générateur : TVA standard de la société à la composition serveur ; total de la barre
// et validation de l'échéancier sur l'option effective en C&I « Les deux ». Jouée SEULE : ADVS27 change `tva_standard`
// de la société démo le temps de l'étape et le rétablit.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage, cliquerCreerDevis, choisirMarche, declarerProfilCi, retirerLignesPrixARenseigner, KWH_COMMERCIAL } from '../helpers.js'
import { catalogueCi, retablirCatalogueApresTout, leadCi } from './_ci.js'

const etape = groupe('ADVS', ['ADVS27', 'ADVS36'])
fermerDjangoApresTout()
retablirCatalogueApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const chiffres = (t) => Number(String(t).replace(/[^\d,.]/g, '').replace(/\s/g, '').replace(',', '.'))
const produit = async (r, nom, pv) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom, prix_vente: pv, prix_achat: '111.11' } }), 'produit')

etape('PA3-01.tva_societe', ['ADVS27'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const avant = await py(`from apps.parametres.models import CompanyProfile
p = CompanyProfile.objects.get(company_id=1); v = str(p.tva_standard); p.tva_standard = 14; p.save(update_fields=['tva_standard']); sortie(v)`)
  try {
    // Marché C&I (seul parcours Auto-remplir sans carte) : le catalogue de démo, ses postes tarifés comme `amot3.spec.js`.
    await catalogueCi(r)
    const lead = await leadCi(r, `ADVS27 ${m}`)
    await page.goto(`/ventes/devis/nouveau?lead=${lead.id}`)
    await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' })).toBeVisible({ timeout: 30_000 })
    await expect(page.locator('#gen-tel')).not.toHaveValue('', { timeout: 90_000 })
    await choisirMarche(page, /Commercial/)
    await expect(page.getByTestId('ci-profil')).toBeVisible()
    for (let i = 0; i < 12; i += 1) await page.locator(`#gen-ci-kwh-${i}`).fill(String(KWH_COMMERCIAL[i]))
    await declarerProfilCi(page)
    await expect(page.getByTestId('ci-taille-retenue')).toBeVisible({ timeout: 45_000 })
    await page.getByTestId('btn-auto-remplir').click()
    await expect(page.getByTestId('btn-auto-remplir')).not.toHaveAttribute('aria-busy', 'true', { timeout: 180_000 })
    await retirerLignesPrixARenseigner(page)
    const creation = page.waitForResponse((x) => x.request().method() === 'POST' && /\/ventes\/devis\/atomic\/$/.test(new URL(x.url()).pathname))
    const rep = await cliquerCreerDevis(page, creation)
    const corps = rep.request().postDataJSON()
    expect(rep.status(), `création : ${(await rep.text()).slice(0, 300)}`).toBeLessThan(300)
    const ids = corps.lignes.map((l) => l.produit).filter(Boolean)
    const taux = await py(`from apps.stock.models import Produit
sortie({str(p.id): (str(p.tva) if p.tva is not None else None) for p in Produit.objects.filter(pk__in=${JSON.stringify(ids)})})`)
    const sansTaux = corps.lignes.filter((l) => l.produit && taux[String(l.produit)] === null)
    expect(sansTaux.length, 'au moins une ligne d\'un produit sans taux').toBeGreaterThan(0)
    for (const l of sansTaux) expect(Number(l.taux_tva), `${l.designation} : TVA standard de la société`).toBe(14)
    for (const l of corps.lignes.filter((x) => x.produit && taux[String(x.produit)] !== null)) expect(Number(l.taux_tva), `${l.designation} : son taux propre`).toBe(Number(taux[String(l.produit)]))
  } finally {
    await py(`from apps.parametres.models import CompanyProfile
p = CompanyProfile.objects.get(company_id=1); p.tva_standard = ${JSON.stringify(avant)}; p.save(update_fields=['tva_standard']); sortie(1)`)
  }
})

etape('PA3-01.les_deux_auto', ['ADVS36'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADVS36 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `a36${m}@example.invalid`, type_installation: 'commercial', categorie_commerciale: 'bureau', tension_raccordement: 'bt', raccordement: 'triphase', type_toiture: 'bac_acier', conso_mensuelle_kwh: '10000', contrat_electricite: 'bt_patente' } }), 'lead')
  const pan = await produit(r, `Panneau mono 550W ${m}`, '1000.00')
  const res = await produit(r, `Onduleur réseau 10kW ${m}`, '5000.00')
  const hyb = await produit(r, `Onduleur hybride Deye 10kW ${m}`, '8000.00')
  const bat = await produit(r, `Batterie Dyness BX51100 ${m}`, '10000.00')
  const l = (p, q, ordre, extra = {}) => ({ produit: p.id, designation: p.nom, quantite: String(q), prix_unitaire: p.prix_vente, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre, ...extra })
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'commercial', lignes: [l(pan, 12, 0), l(res, 1, 1, { variante: 'sans' }), l(hyb, 1, 2, { variante: 'avec' }), l(bat, 1, 3, { variante: 'avec', role_devis: 'batterie' })] } }), 'devis Les deux')
  const q = await py(`from apps.ventes.models import Devis
from apps.ventes.utils.options import option_totaux
d = Devis.objects.get(pk=${d.id})
ep = dict(d.etude_params or {}); ep['scenario'] = 'Les deux'; ep.pop('recommended_option', None); Devis.objects.filter(pk=d.pk).update(etude_params=ep)
d.refresh_from_db()
sortie(dict(sans=str(option_totaux(d, 'sans_batterie').get('ttc')), avec=str(option_totaux(d, 'avec_batterie').get('ttc'))))`)
  const sans = Number(q.sans)
  expect(Number(q.avec), 'les deux options diffèrent').toBeGreaterThan(sans)
  await page.goto(`/ventes/devis/nouveau?edit=${d.id}`)
  await expect(page.getByRole('heading', { name: /Générateur de Devis Solaire|Modifier/ }).first()).toBeVisible({ timeout: 60_000 })
  const barre = page.getByTestId('gen-barre-total')
  await expect(barre).toBeVisible({ timeout: 90_000 })
  await expect.poll(async () => chiffres(await barre.textContent()), { timeout: 60_000, message: 'barre = total SANS' }).toBe(sans)
  // Acompte de 30 % du SANS en MAD + solde 70 % : refusé si l'écran validait sur l'AVEC.
  const carte = page.getByTestId('carte-echeancier')
  const perso = carte.getByRole('button', { name: "Personnaliser l'échéancier" })
  if (await perso.count()) await perso.click()
  const lignes = carte.locator('[data-testid^="echeance-ligne-"]')
  await expect(lignes.first()).toBeVisible({ timeout: 30_000 })
  const n = await lignes.count()
  await carte.locator('select[aria-label^="Unité"]').first().selectOption({ label: 'MAD TTC' })
  await carte.locator('#gen-echeance-0').fill(String(Math.round(sans * 0.3 * 100) / 100))
  for (let i = 1; i < n - 1; i += 1) await carte.locator(`#gen-echeance-${i}`).fill('0')
  await carte.locator(`select[aria-label^="Unité"]`).nth(n - 1).selectOption({ label: '%' })
  await carte.locator(`#gen-echeance-${n - 1}`).fill('70')
  const sauve = page.waitForResponse((x) => x.request().method() !== 'GET' && x.url().includes(`/ventes/devis/${d.id}/`) && /replace-lines/.test(x.url()), { timeout: 120_000 })
  await page.getByRole('button', { name: /Enregistrer les modifications/ }).click()
  const rep = await sauve
  expect(rep.status(), `enregistré sans erreur d'échéancier : ${(await rep.text()).slice(0, 300)}`).toBeLessThan(300)
  await page.goto(`/ventes/devis/nouveau?edit=${d.id}`)
  await expect.poll(async () => chiffres(await page.getByTestId('gen-barre-total').textContent()), { timeout: 90_000, message: 'rouvert : même total' }).toBe(sans)
  const moteur = await py(`from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data
sortie(str(build_quote_data(Devis.objects.get(pk=${d.id}), {'pdf_mode': 'full'}).get('total_sans')))`)
  expect(Number(moteur), 'PDF = barre').toBeCloseTo(sans, 2)
})
