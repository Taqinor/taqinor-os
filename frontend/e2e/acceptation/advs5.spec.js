// ADVS27 — TVA standard de la société à la composition serveur de l'écran générateur (résidentiel, Auto-remplir). Jouée SEULE :
// change `tva_standard` et le taux de 234 articles de la démo le temps de l'étape, tout est rétabli à la fin.
// ROUGE au 04/11 : les lignes posées par `ligneProduitCatalogue` (accessoires) gardent 20 % (rapport de lane).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage, cliquerCreerDevis } from '../helpers.js'

const etape = groupe('ADVS', ['ADVS27'])
fermerDjangoApresTout()
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

etape('PA3-01.tva_societe', ['ADVS27'], async ({ page }) => {
  const r = page.request
  const m = marque()
  let taux = {}
  const avant = await py(`from apps.parametres.models import CompanyProfile
p = CompanyProfile.objects.get(company_id=1); v = str(p.tva_standard); p.tva_standard = 14; p.save(update_fields=['tva_standard']); sortie(v)`)
  try {
    // Le catalogue démo porte un taux sur ses articles composés : le temps de l'étape, seuls les panneaux gardent le leur (témoin « son
    // taux propre ») ; les autres passent à NULL (le Given) et tout est rétabli à la fin.
    taux = await py(`from apps.stock.models import Produit
q = Produit.objects.filter(company_id=1, tva__isnull=False).exclude(nom__icontains='panneau')
garde = {str(i): str(t) for i, t in q.values_list('id', 'tva')}
q.update(tva=None); sortie(garde)`)
    // Parcours résidentiel (composition serveur, `useCompositionEcran.js`, la porte que la tâche corrige) : taille saisie puis Auto-remplir.
    // Le jumeau C&I (`lignesDepuisCompositionCi` → `ligneProduitCatalogue` sans taux société) garde 20 : signalé au fondateur, non corrigé ici.
    const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADVS27 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `a27${m}@example.invalid`, type_installation: 'residentiel', facture_hiver: '1500', facture_ete: '1500' } }), 'lead')
    await page.goto(`/ventes/devis/nouveau?lead=${lead.id}`)
    await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' })).toBeVisible({ timeout: 30_000 })
    await expect(page.locator('#gen-tel')).not.toHaveValue('', { timeout: 90_000 })
    await page.getByTestId('gen-kwc-cible').fill('5')
    await page.getByTestId('btn-auto-remplir').click()
    await expect(page.getByTestId('btn-auto-remplir')).not.toHaveAttribute('aria-busy', 'true', { timeout: 180_000 })
    await expect(page.locator('table.lines-table tbody tr[data-line-key]').first()).toBeVisible({ timeout: 60_000 })
    const creation = page.waitForResponse((x) => x.request().method() === 'POST' && /\/ventes\/devis\/atomic\/$/.test(new URL(x.url()).pathname), { timeout: 150_000 })
    const rep = await cliquerCreerDevis(page, creation)
    const corps = rep.request().postDataJSON()
    expect(rep.status(), `création : ${(await rep.text()).slice(0, 300)}`).toBeLessThan(300)
    const ids = corps.lignes.map((l) => l.produit).filter(Boolean)
    const lus = await py(`from apps.stock.models import Produit
sortie({str(p.id): (str(p.tva) if p.tva is not None else None) for p in Produit.objects.filter(pk__in=${JSON.stringify(ids)})})`)
    const sansTaux = corps.lignes.filter((l) => l.produit && lus[String(l.produit)] === null)
    expect(sansTaux.length, 'au moins une ligne d\'un produit sans taux').toBeGreaterThan(0)
    expect(sansTaux.map((l) => [l.designation, Number(l.taux_tva)]).filter((x) => x[1] !== 14), 'toutes les lignes sans taux : TVA standard de la société').toEqual([])
    for (const l of corps.lignes.filter((x) => x.produit && lus[String(x.produit)] !== null)) expect(Number(l.taux_tva), `${l.designation} : son taux propre`).toBe(Number(lus[String(l.produit)]))
  } finally {
    await py(`from apps.stock.models import Produit
for i, t in ${JSON.stringify(taux)}.items(): Produit.objects.filter(pk=int(i)).update(tva=t)
sortie(1)`)
    await py(`from apps.parametres.models import CompanyProfile
p = CompanyProfile.objects.get(company_id=1); p.tva_standard = ${JSON.stringify(avant)}; p.save(update_fields=['tva_standard']); sortie(1)`)
  }
})
