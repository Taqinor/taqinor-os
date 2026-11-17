// Preuves en direct ASUP, vague d'acceptation 8 (runner GitHub, 17/11/2026) — audit PF10 « suppression, archivage,
// restauration », dossier docs/audits/2026-11-11-parcours-PF10.md. ASUP67 : un lead en corbeille anonymisé par
// « Anonymiser (RGPD) » ne montre plus son nom ni son téléphone dans la corbeille commune (`/parametres/corbeille` et
// `GET trash/corbeille/`), l'entrée restant restaurable. Rejeu SANS écart d'ASUP62 (le libellé de la corbeille était
// l'écart déclaré de la vague 6). Même patron que `asup7.spec.js` : gestes par la VRAIE route / le vrai écran / le
// vrai shell Django, données propres retirées en fin d'étape, persistance = relecture en base ou rechargement.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, telephoneMobileUnique, uiLoginJusquAuxApps, connexionApi, lireJson } from '../helpers.js'

const etape = groupe('ASUP', ['ASUP67', 'ASUP62'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 420_000 })
const INIT = () => {
  try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
}
test.beforeEach(async ({ page }) => { await page.addInitScript(INIT); await assurerSessionPage(page) })
const contextesUi = []
const apres = []
test.afterEach(async () => {
  for (const c of contextesUi.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`

async function auRepos(suivi) {
  for (const p of suivi.pages.filter((x) => !x.isClosed())) await p.waitForLoadState('networkidle').catch(() => undefined)
}
const compteDirecteur = (nom, prenom) => py(`from apps.roles.models import Role
u = compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom='Directeur').pk, societe=${SOC})
u.first_name = ${J(prenom)}; u.save(update_fields=['first_name'])
sortie(u.id)`)
async function apiSous(testInfo, nom) {
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return ctx
}
async function ecran(page, suivi, testInfo, nom) {
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(u.locale ? { locale: u.locale } : {}), ...(u.timezoneId ? { timezoneId: u.timezoneId } : {}), viewport: { width: 1600, height: 1000 },
  })
  contextesUi.push(ctx)
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  return p
}
const supprimerLeads = (pks) => py(`from apps.crm.models import Lead
for pk in ${J(pks)}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`)
const supprimerClient = (pk) => py(`from apps.crm.models import Client
try: Client.objects.filter(pk=${pk}).delete()
except Exception as exc: print('nettoyage', exc)`)
/** Entrée ACTIVE de la corbeille commune d'un lead, relue en base. */
const entreeDe = (pk) => py(`from django.contrib.contenttypes.models import ContentType
from apps.crm.models import Lead
from apps.trash.models import ElementSupprime
e = ElementSupprime.objects.filter(content_type=ContentType.objects.get_for_model(Lead), object_id=${pk}).order_by('-pk').first()
sortie(None if e is None else dict(id=e.pk, libelle=e.libelle_snapshot, donnees=e.donnees_snapshot, restaure=e.restaure_le is not None))`)

// ═══ PF10.4 — ASUP67 : le nom d'un lead anonymisé disparaît de la corbeille commune, l'entrée reste restaurable ═══
etape('PF10.4-ASUP67', ['ASUP67'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `asup8di_${m}`
  const prenomDi = `Sup${m}`
  const nomLead = `Karim ${m}`
  const tel = telephoneMobileUnique()
  await compteDirecteur(nom, prenomDi)
  const x = await py(`from apps.crm.models import Client, Lead
CO = ${SOC}
c = Client.objects.create(company_id=CO, nom='ASUP67 ${m}', prenom='Client', email='asup67-a-${m}@example.invalid', telephone=${J(telephoneMobileUnique())})
l = Lead.objects.create(company_id=CO, nom=${J(nomLead)}, email='asup67-b-${m}@example.invalid', telephone=${J(tel)}, client=c, stage='NEW')
l.soft_delete(user=U.objects.get(username=${J(nom)}))
sortie(dict(client=c.pk, lead=l.pk))`)
  apres.push(async () => { await supprimerLeads([x.lead]); await supprimerClient(x.client) })
  const avant = await entreeDe(x.lead)
  expect(avant, 'Given : le lead est en corbeille, son nom lisible dans l’entrée').toBeTruthy()
  expect(avant.libelle, 'Given : libellé = nom d’origine').toContain(nomLead)
  const ctx = await apiSous(testInfo, nom)
  try {
    // When : le Directeur lance « Anonymiser (RGPD) » (vraie route de la fiche client).
    const a = await ctx.post(`${API}/crm/clients/${x.client}/anonymize/`, T)
    expect(a.status(), `anonymize : ${(await a.text()).slice(0, 300)}`).toBe(200)
    // Then (base) : libellé neutre, données sans nom ni téléphone.
    const e = await entreeDe(x.lead)
    expect(e.libelle, 'entrée de corbeille : libellé neutre « Lead anonymisé »').toBe('Lead anonymisé')
    expect(J(e.donnees), 'donnees_snapshot : ni nom ni téléphone').not.toMatch(new RegExp(`Karim|${m}|${tel.replace(/^\+/, '').slice(-8)}`))
    expect(e.restaure, 'entrée toujours ouverte (non restaurée)').toBe(false)
    // Then (API) : GET trash/corbeille/ ne contient plus « Karim » ; l'entrée porte le libellé neutre.
    const liste = await lireJson(await ctx.get(`${API}/trash/corbeille/?page_size=500`, T), 'corbeille')
    const entrees = Array.isArray(liste) ? liste : (liste.results || [])
    const brut = J(liste)
    expect(brut, 'GET trash/corbeille/ : pas de nom « Karim » du lead').not.toContain(nomLead)
    expect(brut, 'GET trash/corbeille/ : pas de téléphone du lead').not.toContain(tel.replace(/^\+/, '').slice(-8))
    const dansListe = entrees.find((el) => el.id === e.id)
    expect(dansListe, 'l’entrée du lead est dans la liste de la corbeille').toBeTruthy()
    expect(dansListe.libelle_snapshot, 'liste : libellé neutre').toBe('Lead anonymisé')
    const detail = await lireJson(await ctx.get(`${API}/trash/corbeille/${e.id}/`, T), 'détail corbeille')
    expect(J(detail), 'détail : ni nom ni téléphone').not.toMatch(new RegExp(`Karim|${tel.replace(/^\+/, '').slice(-8)}`))
    // Then (écran) : /parametres/corbeille montre « Lead anonymisé », jamais le nom.
    const p = await ecran(page, suivi, testInfo, nom)
    await p.goto('/parametres/corbeille')
    const rangee = p.getByTestId('corbeille-row').filter({ hasText: prenomDi }).filter({ hasText: 'Lead anonymisé' })
    await expect(rangee.first(), 'écran : l’entrée du lead porte le libellé « Lead anonymisé »').toBeVisible({ timeout: 60_000 })
    await expect(rangee.first().getByRole('button', { name: 'Restaurer' }), 'écran : l’entrée reste restaurable (bouton Restaurer)').toBeVisible()
    await expect(p.getByTestId('corbeille-row').filter({ hasText: nomLead }), 'écran : aucune ligne ne montre « Karim »').toHaveCount(0)
    expect(await p.locator('body').innerText(), 'écran : nom absent de la page').not.toContain(nomLead)
    await p.reload()
    await expect(p.getByTestId('corbeille-row').filter({ hasText: prenomDi }).filter({ hasText: 'Lead anonymisé' }).first(), 'persistance : rechargement').toBeVisible({ timeout: 60_000 })
    expect(await p.locator('body').innerText(), 'persistance : nom toujours absent').not.toContain(nomLead)
    // Then (restauration) : l'entrée est restaurable — la fiche anonymisée revient.
    const r = await ctx.post(`${API}/trash/corbeille/${e.id}/restaurer/`, T)
    expect(r.status(), `restaurer : ${(await r.text()).slice(0, 300)}`).toBe(200)
    const lu = await py(`from apps.crm.models import Lead
l = Lead.all_objects.get(pk=${x.lead}); sortie([l.nom, l.is_deleted])`)
    expect(lu, 'lead restauré : fiche anonymisée, plus supprimée').toEqual(['Anonymisé', false])
    expect((await entreeDe(x.lead)).restaure, 'entrée marquée restaurée').toBe(true)
    await auRepos(suivi)
  } finally { await ctx.dispose() }
})

// ═══ PF10.4 — ASUP62 SANS écart : « Anonymiser (RGPD) » efface aussi les leads du client déjà en corbeille ═══
etape('PF10.4-ASUP62', ['ASUP62'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `asup8d62_${m}`
  await compteDirecteur(nom, `Sup62${m}`)
  const x = await py(`from apps.crm.models import Client, Lead
CO = ${SOC}
c = Client.objects.create(company_id=CO, nom='ASUP62 ${m}', prenom='Client', email='asup62-a-${m}@example.invalid', telephone=${J(telephoneMobileUnique())})
l = Lead.objects.create(company_id=CO, nom='ASUP62 lead corbeille ${m}', email='asup62-b-${m}@example.invalid', telephone=${J(telephoneMobileUnique())}, client=c, stage='NEW')
v = Lead.objects.create(company_id=CO, nom='ASUP62 lead vivant ${m}', email='asup62-c-${m}@example.invalid', telephone=${J(telephoneMobileUnique())}, client=c, stage='NEW')
l.soft_delete(user=U.objects.get(username='demo_admin'))
sortie(dict(client=c.pk, corbeille=l.pk, vivant=v.pk))`)
  apres.push(async () => { await supprimerLeads([x.corbeille, x.vivant]); await supprimerClient(x.client) })
  const lu = (pk) => py(`from apps.crm.models import Lead
l = Lead.all_objects.get(pk=${pk})
sortie(dict(nom=l.nom, email=l.email or '', telephone=l.telephone or '', supprime=l.is_deleted))`)
  expect((await lu(x.corbeille)).supprime, 'Given : le lead du client est en corbeille, aux e-mail et téléphone différents').toBe(true)
  const ctx = await apiSous(testInfo, nom)
  try {
    const a = await ctx.post(`${API}/crm/clients/${x.client}/anonymize/`, T)
    expect(a.status(), `anonymize : ${(await a.text()).slice(0, 300)}`).toBe(200)
    const c = await lu(x.corbeille)
    expect(c, 'lead en corbeille : nom anonymisé, e-mail et téléphone vides, toujours supprimé').toEqual({ nom: 'Anonymisé', email: '', telephone: '', supprime: true })
    expect((await lu(x.vivant)).nom, 'lead vivant : anonymisé aussi').toBe('Anonymisé')
    expect(await lu(x.corbeille), 'persistance : identique').toEqual(c)
    // Clause « libellé anonymisé dans la corbeille commune » : le nom d'origine ne figure plus dans l'entrée.
    const corb = await entreeDe(x.corbeille)
    expect(corb, 'entrée de la corbeille commune du lead').toBeTruthy()
    expect(J(corb), 'le nom d’origine du lead ne figure plus dans la corbeille commune').not.toContain(`ASUP62 lead corbeille ${m}`)
    expect(corb.libelle, 'libellé neutre').toBe('Lead anonymisé')
    const p = await ecran(page, suivi, testInfo, nom)
    await p.goto('/parametres/corbeille')
    await expect(p.getByTestId('corbeille-row').first(), 'écran : la corbeille est affichée').toBeVisible({ timeout: 60_000 })
    expect(await p.locator('body').innerText(), 'écran : le nom d’origine du lead est absent').not.toContain(`ASUP62 lead corbeille ${m}`)
    await auRepos(suivi)
  } finally { await ctx.dispose() }
})
