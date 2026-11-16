// Preuves en direct ASUP, vague 6 (runner GitHub) — audit PF10 « suppression, archivage, restauration »,
// dossier docs/audits/2026-11-11-parcours-PF10.md. ASUP4 (produit archivé à mouvements), ASUP5 + ASUP6
// (compte à traces : refus serveur puis écran « Désactiver le compte »), ASUP48 (archivage d'un lead signé à suite
// réelle), ASUP56 (« Annuler » de la corbeille `core`). Chaque étape joue le geste À L'ÉCRAN ou par la VRAIE route sous
// le rôle LIVRÉ du registre (compte d'essai de la société démo), AFFIRME ce que la clause nomme (statut, message,
// ligne gardée), recharge puis relit la base. Données propres créées par le shell Django et retirées en fin d'étape.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, telephoneMobileUnique, uiLoginJusquAuxApps, connexionApi, lireJson } from '../helpers.js'

const etape = groupe('ASUP', ['ASUP4', 'ASUP5', 'ASUP6', 'ASUP48', 'ASUP56'])
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
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte }).first()

async function auRepos(suivi) {
  for (const p of suivi.pages.filter((x) => !x.isClosed())) await p.waitForLoadState('networkidle').catch(() => undefined)
}
/** Compte d'essai du rôle LIVRÉ `nomRole` (société démo) ; renvoie son id. */
const compteRole = (nom, nomRole, prenom = 'Essai') => py(`from apps.roles.models import Role
u = compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}).pk, societe=${SOC})
u.first_name = ${J(prenom)}; u.save(update_fields=['first_name'])
sortie(u.id)`)
/** Contexte API connecté (par /token/) sous le compte `nom`. */
async function apiSous(testInfo, nom) {
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return ctx
}
/** Navigateur À FROID du compte `nom` (connexion par l'écran de login), surveillé par les oracles. */
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
/** La capture de l'étape est prise sur la première page ouverte : on ferme la page démo pour capturer l'écran affirmé. */
const montrer = async (page) => { await page.close().catch(() => undefined) }
const supprimerLeads = (pks) => py(`from apps.crm.models import Lead
for pk in ${J(pks)}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`)
const fermerVisite = async (p) => {
  const b = p.getByRole('button', { name: 'Fermer la visite guidée' })
  await b.waitFor({ state: 'visible', timeout: 10_000 }).then(() => b.click()).catch(() => undefined)
}
/** Presse un bouton de ligne hors de la fenêtre visible (cellule d'actions défilante) : focus + Entrée. */
const presser = async (p, bouton) => { await bouton.focus(); await p.keyboard.press('Enter') }

// ═══ PF10.3 — ASUP4 : /stock › Archivés › Supprimer sur un produit à mouvements ⇒ 409 nommé, produit et mouvements gardés ═══
etape('PF10.3-ASUP4', ['ASUP4'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `asup4di_${m}`
  await compteRole(nom, 'Directeur')
  const nomA = `ASUP4 Variateur ${m} A`
  const nomB = `ASUP4 Variateur ${m} B`
  const skuA = `ASUP4-${m}-A`
  const ids = await py(`from decimal import Decimal
from apps.stock.models import Produit, MouvementStock
CO = ${SOC}
a = Produit.objects.create(company_id=CO, nom=${J(nomA)}, sku=${J(skuA)}, prix_achat=Decimal('4200.00'), prix_vente=Decimal('5900.00'), is_archived=True)
b = Produit.objects.create(company_id=CO, nom=${J(nomB)}, sku='ASUP4-${m}-B', prix_achat=Decimal('4200.00'), prix_vente=Decimal('5900.00'), is_archived=True)
for t, av, ap in (('entree', 0, 10), ('sortie', 10, 0)):
    MouvementStock.objects.create(company_id=CO, produit=a, type_mouvement=t, quantite=10, quantite_avant=av, quantite_apres=ap)
sortie(dict(a=a.pk, b=b.pk))`)
  apres.push(() => py(`from apps.stock.models import Produit, MouvementStock
MouvementStock.objects.filter(produit_id__in=${J([ids.a, ids.b])}).delete()
Produit.objects.filter(pk__in=${J([ids.a, ids.b])}).delete()`))
  const etat = () => py(`from apps.stock.models import Produit, MouvementStock
sortie(dict(a=Produit.objects.filter(pk=${ids.a}).exists(), mvts=MouvementStock.objects.filter(produit_id=${ids.a}).count(),
  b=Produit.objects.filter(pk=${ids.b}).exists()))`)
  const di = await apiSous(testInfo, nom)
  const jour = new Date().toISOString().slice(0, 10)
  const valo = async () => lireJson(await di.get(`${API}/stock/produits/valorisation-a-date/?date=${jour}`, T), 'valorisation')
  try {
    const avant = await valo()
    expect(await etat(), 'Given : produit A + 2 mouvements, produit B sans mouvement').toEqual({ a: true, mvts: 2, b: true })
    // When (écran) : /stock › Archivés › Supprimer sur le produit A, saisie du SKU, « Supprimer définitivement ».
    const p = await ecran(page, suivi, testInfo, nom)
    suivi.attendre(/\/stock\/produits\/\d+\/force-delete\/$/, 409)
    await p.goto('/stock')
    await p.getByRole('button', { name: /^Archivés/ }).first().click({ timeout: 60_000 })
    const ligne = (n) => p.getByRole('row').filter({ hasText: n })
    await expect(ligne(nomA), 'produit A listé dans « Produits archivés »').toBeVisible({ timeout: 60_000 })
    await ligne(nomA).getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
    await p.getByRole('menuitem', { name: 'Supprimer' }).click()
    const dlg = p.getByRole('alertdialog')
    await expect(dlg).toContainText('Suppression définitive')
    await dlg.locator('#fd-confirm').fill(skuA)
    await dlg.getByRole('button', { name: 'Supprimer définitivement' }).click()
    // Then : message 409 affiché (nombre de mouvements nommé, « l'archive suffit »), produit toujours listé.
    const t = toast(p, 'Suppression définitive refusée')
    await expect(t, 'message 409 affiché').toBeVisible({ timeout: 30_000 })
    await expect(t, 'le message nomme « 2 mouvements de stock »').toContainText('2 mouvements de stock')
    await expect(t, 'le message dit que l\'archive suffit').toContainText('archive suffit')
    await dlg.getByRole('button', { name: 'Annuler' }).click()
    await expect(ligne(nomA), 'produit A toujours listé').toBeVisible()
    // Persistance : relire produit et mouvements (base) ; valorisation à date inchangée ; recharger l'écran.
    expect(await etat(), 'produit A et ses 2 mouvements toujours en base').toEqual({ a: true, mvts: 2, b: true })
    expect(await valo(), 'valorisation à date inchangée').toEqual(avant)
    await p.reload()
    await p.getByRole('button', { name: /^Archivés/ }).first().click({ timeout: 60_000 })
    await expect(ligne(nomA), 'après rechargement : produit A toujours listé').toBeVisible({ timeout: 60_000 })
    // Second produit archivé (sans mouvement ni référence) : 200, supprimé comme avant (vraie route du bouton).
    const r2 = await di.delete(`${API}/stock/produits/${ids.b}/force-delete/`, T)
    expect(r2.status(), `produit B : ${(await r2.text()).slice(0, 200)}`).toBe(200)
    expect(await etat(), 'produit B supprimé, A intact').toEqual({ a: true, mvts: 2, b: false })
    await auRepos(suivi)
    await montrer(page)
  } finally { await di.dispose() }
})

// ═══ PF10.1 — ASUP5 : DELETE users/<id>/ sur un compte à traces ⇒ 409 nommé sans rien effacer ; compte vierge ⇒ 204 ═══
const TRACES = (m, tech) => `from decimal import Decimal
from apps.crm.models import Client, Lead
from apps.ventes.models import Facture, Paiement
CO = ${SOC}
tech = U.objects.get(pk=${tech})
c = Client.objects.create(company_id=CO, nom='ASUP traces ${m}', prenom='')
f = Facture.objects.create(company_id=CO, reference='FAC-ASUP5-${m}', client=c, statut='emise', taux_tva=Decimal('20'))
p = Paiement.objects.create(company_id=CO, facture=f, montant=Decimal('100'), date_paiement=timezone.localdate(), mode='virement', created_by=tech)
l = Lead.objects.create(company_id=CO, nom='ASUP traces lead ${m}', owner=tech, stage='NEW')
sortie(dict(client=c.pk, facture=f.pk, paiement=p.pk, lead=l.pk))`
const NETTOYER_TRACES = (x) => py(`from apps.crm.models import Client, Lead
from apps.ventes.models import Facture, Paiement
for qs in (Paiement.objects.filter(pk=${x.paiement}), Lead.all_objects.filter(pk=${x.lead}), Facture.objects.filter(pk=${x.facture}), Client.objects.filter(pk=${x.client})):
    try: qs.delete()
    except Exception as exc: print('nettoyage', exc)`)

etape('PF10.1-ASUP5', ['ASUP5'], async ({ page, testInfo }) => {
  const m = marque()
  const di = `asup5di_${m}`
  const tech = `asup5te_${m}`
  const vierge = `asup5vi_${m}`
  await compteRole(di, 'Directeur')
  const idTech = await compteRole(tech, 'Technicien')
  const idVierge = await compteRole(vierge, 'Commercial')
  const x = await py(TRACES(m, idTech))
  apres.push(() => NETTOYER_TRACES(x))
  const ctx = await apiSous(testInfo, di)
  try {
    // When : le Directeur DELETE users/<id>/ sur le Technicien (auteur d'un paiement, propriétaire d'un lead).
    const r1 = await ctx.delete(`${API}/users/${idTech}/`, T)
    const corps1 = await r1.text()
    expect(r1.status(), `compte à traces : ${corps1.slice(0, 300)}`).toBe(409)
    expect(corps1, 'le message nomme les traces : auteur du paiement').toMatch(/auteur de 1 paiement/)
    expect(corps1, 'le message nomme les traces : propriétaire du lead').toMatch(/propriétaire de 1 lead/)
    expect(corps1, 'le message invite à désactiver').toMatch(/désactivez-le/)
    expect(JSON.parse(corps1).code, 'code machine').toBe('compte_avec_traces')
    // Persistance : compte et liens intacts.
    const lu = await py(`from apps.ventes.models import Paiement
from apps.crm.models import Lead
sortie(dict(existe=U.objects.filter(pk=${idTech}).exists(), actif=U.objects.get(pk=${idTech}).is_active,
  paiement=Paiement.objects.get(pk=${x.paiement}).created_by_id, lead=Lead.objects.get(pk=${x.lead}).owner_id))`)
    expect(lu, 'compte actif, Paiement.created_by et Lead.owner inchangés').toEqual({ existe: true, actif: true, paiement: idTech, lead: idTech })
    // Compte vierge : 204 comme avant, compte retiré.
    const r2 = await ctx.delete(`${API}/users/${idVierge}/`, T)
    expect(r2.status(), `compte vierge : ${(await r2.text()).slice(0, 200)}`).toBe(204)
    expect(await py(`sortie(U.objects.filter(pk=${idVierge}).exists())`), 'compte vierge supprimé').toBe(false)
    await page.goto('/admin/users')
    await expect(page.locator('body')).toBeVisible()
  } finally { await ctx.dispose() }
})

// ═══ PF10.1 — ASUP6 : /admin/users, suppression refusée pour traces ⇒ motif + « Désactiver le compte » ═══
etape('PF10.1-ASUP6', ['ASUP6'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const di = `asup6di_${m}`
  const tech = `asup6te_${m}`
  const vierge = `asup6vi_${m}`
  await compteRole(di, 'Directeur')
  const idTech = await compteRole(tech, 'Technicien')
  const idVierge = await compteRole(vierge, 'Commercial')
  const x = await py(TRACES(m, idTech))
  apres.push(() => NETTOYER_TRACES(x))
  const p = await ecran(page, suivi, testInfo, di)
  suivi.attendre(/\/users\/\d+\/$/, 409)
  await p.goto('/admin/users')
  const ligne = (n) => p.getByRole('row').filter({ hasText: n })
  await expect(ligne(tech), 'compte à traces listé').toBeVisible({ timeout: 60_000 })
  // Supprimer le compte à traces : la confirmation ne promet pas un effacement définitif.
  await ligne(tech).getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
  await p.getByRole('menuitem', { name: 'Supprimer' }).click()
  const dlg = p.getByRole('alertdialog')
  await expect(dlg).toContainText('Supprimer cet utilisateur ?')
  await expect(dlg, 'jamais « sera définitivement supprimé » pour un compte à traces').not.toContainText('sera définitivement supprimé')
  await dlg.getByRole('button', { name: 'Supprimer', exact: true }).click()
  // Refus 409 : le motif serveur s'affiche avec le bouton « Désactiver le compte ».
  const alerte = p.getByRole('alert').filter({ hasText: 'Désactiver le compte' })
  await expect(alerte, 'motif du refus affiché').toBeVisible({ timeout: 30_000 })
  await expect(alerte).toContainText(tech)
  await expect(alerte).toContainText('désactivez-le')
  await expect(alerte).toContainText('auteur de 1 paiement')
  const patch = p.waitForRequest((r) => r.method() === 'PATCH' && new RegExp(`/users/${idTech}/$`).test(r.url()), T)
  await alerte.getByRole('button', { name: 'Désactiver le compte' }).click()
  expect((await patch).postDataJSON(), 'PATCH users/<id>/ {is_active: false}').toEqual({ is_active: false })
  await expect(ligne(tech), 'la ligne passe « Inactif »').toContainText('Inactif', { timeout: 30_000 })
  await expect(p.getByRole('alert').filter({ hasText: 'Désactiver le compte' }), 'bandeau refermé').toHaveCount(0)
  // Persistance : recharger — le compte est listé inactif, en base inactif, traces intactes.
  await p.reload()
  await expect(ligne(tech), 'après rechargement : compte inactif').toContainText('Inactif', { timeout: 60_000 })
  expect(await py(`from apps.ventes.models import Paiement
sortie(dict(actif=U.objects.get(pk=${idTech}).is_active, paiement=Paiement.objects.get(pk=${x.paiement}).created_by_id))`),
  'en base : inactif, paiement toujours attribué').toEqual({ actif: false, paiement: idTech })
  // Compte vierge : suppression comme avant, ligne retirée.
  await ligne(vierge).getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
  await p.getByRole('menuitem', { name: 'Supprimer' }).click()
  await p.getByRole('alertdialog').getByRole('button', { name: 'Supprimer', exact: true }).click()
  await expect(toast(p, 'Utilisateur supprimé.')).toBeVisible({ timeout: 30_000 })
  await expect(ligne(vierge), 'ligne du compte vierge retirée').toHaveCount(0)
  expect(await py(`sortie(U.objects.filter(pk=${idVierge}).exists())`), 'compte vierge supprimé en base').toBe(false)
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF10.3 — ASUP48 : « Archiver » sur un lead signé à facture ⇒ 409 nommé sans rien écrire ; en masse : sauté avec la raison ═══
etape('PF10.3-ASUP48', ['ASUP48'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `asup48cr_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const ids = await py(`from decimal import Decimal
from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, Facture
CO = ${SOC}
own = U.objects.get(pk=${cr})
tels = ${J([telephoneMobileUnique(), telephoneMobileUnique(), telephoneMobileUnique()])}
mk = lambda n, t: Lead.objects.create(company_id=CO, nom='ASUP48 ' + n + ' ${m}', prenom='Essai', stage=stages.SIGNED, owner=own, telephone=t)
a, b, c = mk('suite', tels[0]), mk('seul', tels[1]), mk('masse', tels[2])
cl = Client.objects.create(company_id=CO, nom='ASUP48 client ${m}', prenom='')
d = Devis.objects.create(company_id=CO, reference='DEV-ASUP48-${m}', client=cl, lead=a, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), date_acceptation=timezone.localdate(), created_by=own)
f = Facture.objects.create(company_id=CO, reference='FAC-ASUP48-${m}', client=cl, devis=d, statut='emise', taux_tva=Decimal('20'))
sortie(dict(a=a.pk, b=b.pk, c=c.pk, client=cl.pk, devis=d.pk, facture=f.pk, ref=f.reference))`)
  apres.push(async () => {
    await py(`from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, Facture
for qs in (Facture.objects.filter(pk=${ids.facture}), Devis.objects.filter(pk=${ids.devis})):
    try: qs.delete()
    except Exception as exc: print('nettoyage', exc)`)
    await supprimerLeads([ids.a, ids.b, ids.c])
    await py(`from apps.crm.models import Client
try: Client.objects.filter(pk=${ids.client}).delete()
except Exception as exc: print('nettoyage client', exc)`)
  })
  const etat = (pk) => py(`from apps.crm import stages
from apps.crm.models import Lead, LeadActivity
l = Lead.all_objects.get(pk=${pk})
sortie(dict(archive=l.is_archived, signe=l.stage == stages.SIGNED, notes=LeadActivity.objects.filter(lead_id=${pk}).count()))`)
  const avantA = await etat(ids.a)
  expect([avantA.archive, avantA.signe], 'Given : lead A signé, non archivé, devis accepté + facture émise').toEqual([false, true])
  const p = await ecran(page, suivi, testInfo, nom)
  suivi.attendre(new RegExp(`/crm/leads/${ids.a}/archiver/$`), 409)
  await p.goto(`/crm/leads?view=liste&q=${m}`)
  const ligne = (n) => p.locator('tr.lv-row').filter({ hasText: `ASUP48 ${n} ${m}` })
  await expect(ligne('suite'), 'lead signé à suite listé').toBeVisible({ timeout: 60_000 })
  await fermerVisite(p)
  // « Archiver » sur le lead signé à facture émise : message nommé affiché, rien d'écrit.
  const boite = p.getByRole('alertdialog')
  await presser(p, ligne('suite').getByRole('button', { name: 'Archiver', exact: true }))
  await boite.getByRole('button', { name: 'Archiver', exact: true }).click()
  const refus = toast(p, 'Impossible d\'archiver ce lead signé')
  await expect(refus, 'message 409 nommé affiché').toBeVisible({ timeout: 30_000 })
  await expect(refus, 'le message nomme la facture').toContainText(ids.ref)
  expect(await etat(ids.a), 'lead inchangé : non archivé, toujours signé, aucune note ajoutée').toEqual({ archive: false, signe: true, notes: avantA.notes })
  // Lead signé sans aucune suite : archivé comme aujourd'hui (toast « Lead archivé. »).
  await presser(p, ligne('seul').getByRole('button', { name: 'Archiver', exact: true }))
  await boite.getByRole('button', { name: 'Archiver', exact: true }).click()
  await expect(toast(p, 'Lead archivé.'), 'signé sans suite : archivé').toBeVisible({ timeout: 30_000 })
  expect((await etat(ids.b)).archive, 'en base : lead sans suite archivé').toBe(true)
  // Action en masse « archive » (vraie route) : le lead à suite est sauté AVEC la raison, l'autre est archivé.
  const ctx = await apiSous(testInfo, nom)
  try {
    const r = await ctx.post(`${API}/crm/leads/bulk/`, { ...T, data: { action: 'archive', ids: [ids.a, ids.c] } })
    expect(r.status(), `masse : ${(await r.text()).slice(0, 300)}`).toBe(200)
    const corps = await r.json()
    expect(corps.updated, 'en masse : un seul lead archivé').toBe(1)
    expect(corps.skipped.map((s) => s.id), 'en masse : le lead à suite est sauté').toEqual([ids.a])
    expect(corps.skipped[0].reason, 'en masse : la raison nomme la facture').toContain(ids.ref)
    expect(corps.skipped[0].reason).toContain('Impossible d\'archiver ce lead signé')
  } finally { await ctx.dispose() }
  // Persistance : relire en base puis recharger l'écran.
  expect(await etat(ids.a), 'persistance : A toujours non archivé et signé').toEqual({ archive: false, signe: true, notes: avantA.notes })
  expect((await etat(ids.c)).archive, 'persistance : C (sans suite) archivé en masse').toBe(true)
  await p.reload()
  await expect(ligne('suite'), 'après rechargement : le lead signé à suite reste dans la liste').toBeVisible({ timeout: 60_000 })
  await expect(ligne('seul'), 'après rechargement : le lead archivé a quitté la liste').toHaveCount(0)
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF10.3 — ASUP56 : « Annuler » (corbeille `core`) d'un lead absorbé / à doublon vivant ⇒ 409 nommé, lead toujours supprimé ═══
etape('PF10.3-ASUP56', ['ASUP56'], async ({ page, suivi }) => {
  const m = marque()
  const tel = telephoneMobileUnique()
  const tel2 = telephoneMobileUnique()
  const ids = await py(`from apps.crm.leads_fusion import merge_leads
from apps.crm.models import Lead
CO = ${SOC}
adm = U.objects.get(username='demo_admin')
mk = lambda n, **k: Lead.objects.create(company_id=CO, nom='ASUP56 ' + n + ' ${m}', stage='NEW', **k)
b, a = mk('B'), mk('A')
merge_leads(b, [a], adm)
c, d = mk('C', telephone=${J(tel)}), mk('D', telephone=${J(tel)})
e = mk('E')
c2, d2 = mk('C2', telephone=${J(tel2)}), mk('D2', telephone=${J(tel2)})
sortie(dict(a=a.pk, b=b.pk, c=c.pk, d=d.pk, e=e.pk, c2=c2.pk, d2=d2.pk))`)
  apres.push(() => supprimerLeads(Object.values(ids)))
  const r = page.request
  const etat = (pk) => py(`from apps.crm.models import Lead, LeadActivity
from core.models import DeletionRecord
l = Lead.all_objects.get(pk=${pk})
rec = DeletionRecord.objects.filter(object_id=${pk}, content_type__model='lead').order_by('-id').first()
sortie(dict(supprime=l.is_deleted, archive=l.is_archived, entree_ouverte=rec is not None and rec.restored_at is None,
  restaure=LeadActivity.objects.filter(lead_id=${pk}, body__startswith='Lead restauré').count()))`)
  // Given : A (absorbé par B), C (téléphone porté par D vivant), E (sans doublon) mis à la corbeille par la vraie route.
  const corbeille = {}
  for (const cle of ['a', 'c', 'e']) {
    const d = await r.delete(`${API}/crm/leads/${ids[cle]}/`, T)
    expect(d.status(), `suppression de ${cle} : ${(await d.text()).slice(0, 200)}`).toBe(200)
    corbeille[cle] = (await d.json()).corbeille_id
    expect(corbeille[cle], `entrée de corbeille de ${cle}`).toBeTruthy()
  }
  // When : POST core/corbeille/<id>/restaurer/ (le geste du toast « Annuler »).
  const refus = async (cle, motif) => {
    const rep = await r.post(`${API}/core/corbeille/${corbeille[cle]}/restaurer/`, T)
    const corps = await rep.text()
    expect(rep.status(), `${cle} : ${corps.slice(0, 300)}`).toBe(409)
    expect(corps, `${cle} : motif nommé`).toContain(motif)
    expect(await etat(ids[cle]), `${cle} : toujours supprimé, entrée ouverte, aucune ligne « Lead restauré »`)
      .toMatchObject({ supprime: true, entree_ouverte: true, restaure: 0 })
  }
  await refus('a', `absorbé par le lead #${ids.b}`)
  await refus('c', `doublon vivant : lead #${ids.d}`)
  const ok = await r.post(`${API}/core/corbeille/${corbeille.e}/restaurer/`, T)
  expect(ok.status(), `E : ${(await ok.text()).slice(0, 300)}`).toBe(200)
  expect(await etat(ids.e), 'E : restauré, entrée fermée, UNE ligne « Lead restauré »').toMatchObject({ supprime: false, entree_ouverte: false, restaure: 1 })
  // Persistance : relire A et C par all_objects ⇒ toujours supprimés (déjà relus ci-dessus après le refus).
  expect(await etat(ids.a), 'persistance A').toMatchObject({ supprime: true, entree_ouverte: true })
  expect(await etat(ids.c), 'persistance C').toMatchObject({ supprime: true, entree_ouverte: true })
  // Écran : /crm/leads (liste) — supprimer C2 (doublon vivant D2), cliquer « Annuler » du toast ⇒ échec, C2 toujours absent.
  suivi.attendre(/\/core\/corbeille\/\d+\/restaurer\/$/, 409)
  await page.goto(`/crm/leads?view=liste&q=${m}`)
  const ligne = (n) => page.locator('tr.lv-row').filter({ hasText: `ASUP56 ${n} ${m}` })
  await expect(ligne('C2'), 'C2 listé').toBeVisible({ timeout: 60_000 })
  await expect(ligne('D2'), 'D2 (doublon vivant) listé').toBeVisible()
  await fermerVisite(page)
  await presser(page, ligne('C2').getByRole('button', { name: 'Supprimer', exact: true }))
  await page.getByRole('alertdialog').getByRole('button', { name: 'Supprimer', exact: true }).click()
  const t = toast(page, 'Lead supprimé.')
  await expect(t, 'toast « Lead supprimé. »').toBeVisible({ timeout: 30_000 })
  await t.getByRole('button', { name: 'Annuler' }).click()
  await expect(toast(page, 'Restauration impossible.'), '« Annuler » échoue : message d\'échec affiché').toBeVisible({ timeout: 30_000 })
  expect(await etat(ids.c2), 'C2 : toujours supprimé après « Annuler »').toMatchObject({ supprime: true, entree_ouverte: true, restaure: 0 })
  await page.reload()
  await expect(ligne('D2'), 'après rechargement : D2 (vivant) toujours dans le pipeline').toBeVisible({ timeout: 60_000 })
  await expect(ligne('C2'), 'après rechargement : C2 toujours absent du pipeline').toHaveCount(0)
  await auRepos(suivi)
})
