// Complément ÉCRAN des preuves en direct ASUP (audit PF10, dossier docs/audits/2026-11-11-parcours-PF10.md).
// La relecture adverse du lot asup.spec.js a refusé huit tâches dont la clause « Preuve en direct » nomme un
// ÉCRAN que la spec n'ouvrait que pour les oracles : chaque étape ci-dessous joue le geste À L'ÉCRAN, connecté
// sous le rôle LIVRÉ du registre (compte d'essai de la société démo, connexion UI), AFFIRME ce que la clause
// nomme (message, ligne gardée ou partie, badge, compteur), recharge puis réaffirme. Données propres créées par
// le shell Django (ce qu'aucun geste ne pose : fusion, archivage daté, garantie commencée) et retirées en fin.
// Sondes hôtes rejouées quand elles s'exécutent encore ; une sonde aux bouchons périmés est NOMMÉE, jamais comptée.
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, telephoneMobileUnique, uiLoginJusquAuxApps, lireJson } from '../helpers.js'

const etape = groupe('ASUP', ['ASUP7', 'ASUP9', 'ASUP10', 'ASUP11', 'ASUP12', 'ASUP15', 'ASUP43', 'ASUP45'])
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

// Écart accepté NON déclaré : le run runner c6bec748c n'a observé AUCUN des 403 d'arrière-plan connus du shell
// (stock/produits, installations/*, core/dsr-requests, crm/assignable-users) sur ces étapes ; toute incidence
// d'oracle fait donc échouer l'étape. `auRepos` attend le repos réseau pour que les oracles voient TOUT l'écran.
async function auRepos(suivi) {
  for (const p of suivi.pages.filter((x) => !x.isClosed())) await p.waitForLoadState('networkidle').catch(() => undefined)
}

/** Rejoue une sonde HÔTE (`docs/audits/sondes/ASUP/<c>.py`) ; {ok, res|err}. */
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'ASUP', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}
function sondeFausse(constat) {
  const s = sondeHote(constat)
  expect(s.ok, `sonde ${constat} exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, `sonde ${constat} : ${J(s.res.observe)}`).toBe(false)
}

/** Compte d'essai du rôle LIVRÉ `nomRole` (société démo) ; renvoie son id. */
const compteRole = (nom, nomRole, prenom = 'Essai') => py(`from apps.roles.models import Role
u = compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}).pk, societe=${SOC})
u.first_name = ${J(prenom)}; u.save(update_fields=['first_name'])
sortie(u.id)`)

/** Navigateur À FROID du compte `nom` (connexion par l'écran de login), surveillé par les oracles. */
async function ecran(page, suivi, testInfo, nom) {
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(u.locale ? { locale: u.locale } : {}), ...(u.timezoneId ? { timezoneId: u.timezoneId } : {}), ...(u.viewport ? { viewport: u.viewport } : {}),
  })
  contextesUi.push(ctx)
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  return p
}
/** La capture de l'étape est prise sur la première page ouverte : on ferme la page démo pour capturer l'écran affirmé. */
const montrer = async (page) => { await page.close().catch(() => undefined) }
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte }).first()

// Entrée ouverte de la corbeille commune (/parametres/corbeille) d'un lead.
const ENTREE = (pk) => `from django.contrib.contenttypes.models import ContentType
from apps.trash.models import ElementSupprime
from apps.crm.models import Lead
_e = ElementSupprime.objects.filter(content_type=ContentType.objects.get_for_model(Lead), object_id=${pk}).order_by('-pk').first()
`
const supprimerLeads = (pks) => py(`from apps.crm.models import Lead
for pk in ${J(pks)}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`)

// ═══ PF10.1 — ASUP7 : /production/garanties, « Supprimer » d'une garantie en cours ⇒ message affiché, ligne gardée ═══
etape('PF10.1-ASUP7-ecran', ['ASUP7'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-ASUP-004')
  const m = marque()
  const ids = await py(`from decimal import Decimal
from datetime import date
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import ProductionReading, ProductionWarranty
CO = ${SOC}
cl = Client.objects.create(company_id=CO, nom='ASUP7 Client ${m}')
annee = timezone.localdate().year
i1 = Installation.objects.create(company_id=CO, reference='ASUP7-${m}-1', client=cl, puissance_installee_kwc=Decimal('10'))
g1 = ProductionWarranty.objects.create(company_id=CO, installation=i1, start_year=annee, guaranteed_year1_kwh=Decimal('12000'), degradation_pct_per_year=Decimal('0'))
ProductionReading.objects.create(company_id=CO, installation=i1, date=date(annee, 1, 1), period_days=1, energy_kwh=Decimal('40'))
i2 = Installation.objects.create(company_id=CO, reference='ASUP7-${m}-2', client=cl, puissance_installee_kwc=Decimal('10'))
g2 = ProductionWarranty.objects.create(company_id=CO, installation=i2, start_year=annee + 1, guaranteed_year1_kwh=Decimal('12000'), degradation_pct_per_year=Decimal('0'))
sortie(dict(client=cl.pk, inst=[i1.pk, i2.pk], g1=g1.pk, g2=g2.pk))`)
  try {
    const nom = `asup7te_${m}`
    await compteRole(nom, 'Technicien')
    const p = await ecran(page, suivi, testInfo, nom)
    suivi.attendre(/\/api\/django\/monitoring\/warranties\/\d+\/$/, 409)
    const MSG = 'Garantie en cours : modifiez-la ou clôturez-la, elle fonde la compensation due.'
    const table = p.locator('[aria-label="Garanties de production"]')
    const ligne = (ref) => table.getByRole('row').filter({ hasText: ref })
    await p.goto('/production/garanties')
    await expect(ligne(`ASUP7-${m}-1`), 'la garantie en cours est listée').toBeVisible({ timeout: 60_000 })
    await expect(ligne(`ASUP7-${m}-2`), 'la garantie à venir est listée').toBeVisible()
    // Le Technicien clique « Supprimer » sur la garantie commencée (relevé de production) puis confirme.
    await ligne(`ASUP7-${m}-1`).getByRole('button', { name: 'Supprimer' }).click()
    const dlg = p.getByRole('alertdialog')
    await expect(dlg).toContainText('Supprimer cette garantie ?')
    await dlg.getByRole('button', { name: 'Supprimer' }).click()
    await expect(toast(p, MSG), 'le message du refus s\'affiche').toBeVisible({ timeout: 30_000 })
    await expect(ligne(`ASUP7-${m}-1`), 'la ligne reste').toBeVisible()
    // Témoin : la garantie à venir sans relevé se supprime comme avant (ligne partie).
    await ligne(`ASUP7-${m}-2`).getByRole('button', { name: 'Supprimer' }).click()
    await p.getByRole('alertdialog').getByRole('button', { name: 'Supprimer' }).click()
    await expect(toast(p, 'Garantie supprimée.')).toBeVisible({ timeout: 30_000 })
    await expect(ligne(`ASUP7-${m}-2`), 'témoin supprimé : ligne partie').toHaveCount(0)
    const reste = await py(`from apps.monitoring.models import ProductionWarranty
sortie([ProductionWarranty.objects.filter(pk=${ids.g1}).exists(), ProductionWarranty.objects.filter(pk=${ids.g2}).exists()])`)
    expect(reste, 'persistance en base : la garantie en cours reste, le témoin est parti').toEqual([true, false])
    // Persistance à l'écran : recharger.
    await p.reload()
    await expect(ligne(`ASUP7-${m}-1`), 'après rechargement : la garantie en cours est toujours listée').toBeVisible({ timeout: 60_000 })
    await expect(ligne(`ASUP7-${m}-2`)).toHaveCount(0)
    await montrer(page)
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import ProductionReading, ProductionWarranty
ProductionReading.objects.filter(installation_id__in=${J(ids.inst)}).delete()
ProductionWarranty.objects.filter(installation_id__in=${J(ids.inst)}).delete()
Installation.objects.filter(pk__in=${J(ids.inst)}).delete()
Client.objects.filter(pk=${ids.client}).delete()`).catch(() => undefined)
    })
  }
})

// ═══ PF10.3 — ASUP9 : fiche d'un lead fusionné, « Restaurer » ⇒ message nommant le survivant ═══
etape('PF10.3-ASUP9-ecran', ['ASUP9'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-ASUP-006')
  const m = marque()
  const nom = `asup9cr_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [ta, tb, tc] = [telephoneMobileUnique(), telephoneMobileUnique(), telephoneMobileUnique()]
  const ids = await py(`from apps.crm.models import Lead
from apps.crm.leads_fusion import merge_leads
own = U.objects.get(pk=${cr})
mk = lambda nom, tel, **k: Lead.objects.create(company_id=${SOC}, nom=nom + ' ${m}', telephone=tel, owner=own, stage='NEW', **k)
b = mk('Survivant', '${tb}')
a = mk('Absorbe', '${ta}')
merge_leads(b, [a], own)
c = mk('Archive doublon', '${tc}', is_archived=True)
d = mk('Doublon vivant', '${tc}')
sortie(dict(a=a.pk, b=b.pk, c=c.pk, d=d.pk))`)
  const archives = (pks) => py(`from apps.crm.models import Lead
sortie([Lead.all_objects.get(pk=pk).is_archived for pk in ${J(pks)}])`)
  try {
    const p = await ecran(page, suivi, testInfo, nom)
    suivi.attendre(/\/api\/django\/crm\/leads\/\d+\/restaurer\/$/, 409)
    const restaurer = async (pk, attendu) => {
      await p.goto(`/crm/leads/${pk}`)
      await expect(p.locator('.lw-archived-badge'), `lead #${pk} : fiche marquée « Archivé »`).toBeVisible({ timeout: 60_000 })
      await p.getByRole('button', { name: "Plus d'actions", exact: true }).first().click()
      await p.getByRole('menuitem', { name: 'Restaurer' }).click()
      await expect(toast(p, attendu), `lead #${pk} : message « ${attendu} »`).toBeVisible({ timeout: 30_000 })
      await expect(p, 'la fiche reste ouverte').toHaveURL(new RegExp(`/crm/leads/${pk}(\\?|$)`))
      await expect(p.locator('.lw-archived-badge'), 'toujours archivé à l\'écran').toBeVisible()
    }
    await restaurer(ids.a, `absorbé par le lead #${ids.b}`)
    await restaurer(ids.c, `doublon vivant : lead #${ids.d}`)
    expect(await archives([ids.a, ids.c]), 'persistance en base : A et C toujours archivés').toEqual([true, true])
    // Persistance à l'écran : recharger la fiche de l'absorbé.
    await p.goto(`/crm/leads/${ids.a}`)
    await p.reload()
    await expect(p.locator('.lw-archived-badge'), 'après rechargement : toujours « Archivé »').toBeVisible({ timeout: 60_000 })
    await montrer(page)
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await supprimerLeads([ids.a, ids.b, ids.c, ids.d])
    })
  }
})

// ═══ PF10.3 — ASUP10 : lead archivé puis supprimé, restauré depuis /parametres/corbeille ⇒ « Archivés », pas le pipeline ═══
etape('PF10.3-ASUP10-ecran', ['ASUP10'], async ({ page, suivi, testInfo }) => {
  const s = sondeHote('C-ASUP-007')
  if (!s.ok) console.log(`[ASUP10] sonde C-ASUP-007 non exécutable (bouchons périmés, non comptée) : ${s.err}`)
  else expect(s.res.repro, `sonde C-ASUP-007 : ${J(s.res.observe)}`).toBe(false)
  const m = marque()
  const nomCompte = `asup10cr_${m}`
  const cr = await compteRole(nomCompte, 'Commercial responsable')
  const nomLead = `ASUP10 ${m}`
  const ids = await py(`from datetime import timedelta
from apps.crm.models import Lead
own = U.objects.get(pk=${cr})
quand = timezone.now() - timedelta(days=2)
l = Lead.objects.create(company_id=${SOC}, nom=${J(nomLead)}, telephone='${telephoneMobileUnique()}', owner=own, stage='NEW')
Lead.objects.filter(pk=l.pk).update(is_archived=True, archived_at=quand, archived_by=own)
Lead.objects.get(pk=l.pk).soft_delete(user=own)
${ENTREE('l.pk')}
sortie(dict(lead=l.pk, entree=_e.pk))`)
  try {
    const p = await ecran(page, suivi, testInfo, nomCompte)
    await p.goto('/parametres/corbeille')
    const ligne = p.getByTestId('corbeille-row').filter({ hasText: nomLead })
    await expect(ligne, 'entrée du lead dans la corbeille').toBeVisible({ timeout: 60_000 })
    await ligne.getByRole('button', { name: 'Restaurer' }).click()
    await p.getByRole('alertdialog').getByRole('button', { name: 'Restaurer' }).click()
    await expect(toast(p, 'Élément restauré.')).toBeVisible({ timeout: 30_000 })
    await expect(ligne, 'ligne marquée « Restauré »').toContainText('Restauré')
    const lu = await py(`from apps.crm.models import Lead
l = Lead.all_objects.get(pk=${ids.lead}); sortie([l.is_deleted, l.is_archived])`)
    expect(lu, 'en base : non supprimé, toujours archivé').toEqual([false, true])
    // « Archivés » : le lead y est ; le pipeline (leads actifs) ne le montre pas.
    const q = encodeURIComponent(nomLead)
    const verifier = async () => {
      await p.goto(`/crm/leads?archived=seuls&view=liste&q=${q}`)
      const row = p.locator('tr.lv-row').filter({ hasText: nomLead })
      await expect(row, 'visible dans « Archivés »').toBeVisible({ timeout: 60_000 })
      await expect(row, 'ligne marquée archivée').toHaveClass(/lv-row-archived/)
      await p.goto(`/crm/leads?q=${q}`)
      await expect(p.getByRole('status').filter({ hasText: `Aucun lead actif ne correspond à « ${nomLead} ».` }),
        'pipeline : aucun lead actif de ce nom').toBeVisible({ timeout: 60_000 })
      await expect(p.locator('article.kb-card').filter({ hasText: nomLead }), 'aucune carte au pipeline').toHaveCount(0)
    }
    await verifier()
    // Persistance : recharger puis réaffirmer.
    await p.reload()
    await verifier()
    await auRepos(suivi)
    await montrer(page)
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await supprimerLeads([ids.lead])
    })
  }
})

// ═══ PF10.3 — ASUP11 : /parametres/corbeille — doublon vivant ⇒ 409 affiché ; sans doublon ⇒ restauré + historique ═══
etape('PF10.3-ASUP11-ecran', ['ASUP11'], async ({ page, suivi, testInfo }) => {
  const s = sondeHote('C-ASUP-007')
  if (!s.ok) console.log(`[ASUP11] sonde C-ASUP-007 non exécutable (bouchons périmés, non comptée) : ${s.err}`)
  else expect(s.res.repro, `sonde C-ASUP-007 : ${J(s.res.observe)}`).toBe(false)
  const m = marque()
  const tel = telephoneMobileUnique()
  const nomCompte = `asup11cr_${m}`
  const cr = await compteRole(nomCompte, 'Commercial responsable')
  const ids = await py(`from apps.crm.models import Lead
own = U.objects.get(pk=${cr})
ancien = Lead.objects.create(company_id=${SOC}, nom='Ancien ${m}', telephone='${tel}', owner=own, stage='NEW')
ancien.soft_delete(user=own)
vivant = Lead.objects.create(company_id=${SOC}, nom='Nouveau ${m}', telephone='${tel}', owner=own, stage='NEW')
seul = Lead.objects.create(company_id=${SOC}, nom='Seul ${m}', telephone='${telephoneMobileUnique()}', owner=own, stage='NEW')
seul.soft_delete(user=own)
${ENTREE('ancien.pk')}
e1 = _e.pk
${ENTREE('seul.pk')}
sortie(dict(ancien=ancien.pk, vivant=vivant.pk, seul=seul.pk, e1=e1, e2=_e.pk))`)
  try {
    const p = await ecran(page, suivi, testInfo, nomCompte)
    suivi.attendre(/\/api\/django\/trash\/corbeille\/\d+\/restaurer\/$/, 409)
    await p.goto('/parametres/corbeille')
    const ligne = (n) => p.getByTestId('corbeille-row').filter({ hasText: `${n} ${m}` })
    await expect(ligne('Ancien'), 'entrée du lead à doublon').toBeVisible({ timeout: 60_000 })
    await expect(ligne('Seul'), 'entrée du lead sans doublon').toBeVisible()
    await ligne('Ancien').getByRole('button', { name: 'Restaurer' }).click()
    await p.getByRole('alertdialog').getByRole('button', { name: 'Restaurer' }).click()
    await expect(toast(p, `doublon vivant : lead #${ids.vivant}`), 'message 409 nommant le doublon vivant').toBeVisible({ timeout: 30_000 })
    await expect(ligne('Ancien').getByRole('button', { name: 'Restaurer' }), 'refusé : l\'entrée reste à restaurer').toBeVisible()
    await ligne('Seul').getByRole('button', { name: 'Restaurer' }).click()
    await p.getByRole('alertdialog').getByRole('button', { name: 'Restaurer' }).click()
    await expect(toast(p, 'Élément restauré.')).toBeVisible({ timeout: 30_000 })
    await expect(ligne('Seul'), 'sans doublon : ligne marquée « Restauré »').toContainText('Restauré')
    const lu = await py(`from apps.crm.models import Lead, LeadActivity
from apps.trash.models import ElementSupprime
a = Lead.all_objects.get(pk=${ids.ancien}); s = Lead.all_objects.get(pk=${ids.seul})
sortie(dict(ancien=[a.is_deleted, ElementSupprime.objects.get(pk=${ids.e1}).restaure_le is None],
  seul=[s.is_deleted, s.is_archived, ElementSupprime.objects.get(pk=${ids.e2}).restaure_le is not None],
  chatter=LeadActivity.objects.filter(lead_id=${ids.seul}, body__startswith='Lead restauré').count()))`)
    expect(lu.ancien, 'en base : refusé, lead toujours supprimé, entrée ouverte').toEqual([true, true])
    expect(lu.seul, 'en base : restauré, archivage inchangé, entrée fermée').toEqual([false, false, true])
    expect(lu.chatter, 'une ligne d\'historique « Lead restauré »').toBe(1)
    // Persistance à l'écran : recharger — l'entrée refusée reste active, la restaurée a quitté les actives.
    await p.reload()
    await expect(ligne('Ancien').getByRole('button', { name: 'Restaurer' }), 'après rechargement : entrée refusée toujours active').toBeVisible({ timeout: 60_000 })
    await expect(ligne('Seul'), 'après rechargement : entrée restaurée hors des actives').toHaveCount(0)
    await auRepos(suivi)
    await montrer(page)
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await supprimerLeads([ids.ancien, ids.vivant, ids.seul])
    })
  }
})

// ═══ PF10.4 — ASUP12 : fiche client → « Anonymiser (RGPD) » ⇒ ses leads s'affichent anonymisés ═══
etape('PF10.4-ASUP12-ecran', ['ASUP12'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-ASUP-008')
  const m = marque()
  const tel = telephoneMobileUnique()
  const nomClient = `Jean ${m}`
  const ids = await py(`from apps.crm.models import Client, Lead
CO = ${SOC}
cl = Client.objects.create(company_id=CO, nom=${J(nomClient)}, prenom='', type_client='particulier', telephone='${tel}', email='asup12-${m}@asup.invalid', adresse='12 rue ${m}, Casablanca')
l1 = Lead.objects.create(company_id=CO, nom=${J(nomClient)}, client=cl, telephone='${tel}', email='asup12-${m}@asup.invalid', gps_lat='33.5731', gps_lng='-7.5898')
l2 = Lead.objects.create(company_id=CO, nom='Jean archive ${m}', client=cl, email='arch_${m}@asup.invalid', is_archived=True)
sortie(dict(client=cl.pk, leads=[l1.pk, l2.pk]))`)
  try {
    const nom = `asup12di_${m}`
    await compteRole(nom, 'Directeur')
    const p = await ecran(page, suivi, testInfo, nom)
    // Clients → fiche du client → « Anonymiser (RGPD) » → « Anonymiser définitivement ».
    await p.goto('/crm')
    await p.getByPlaceholder('Rechercher nom, email, tél, ICE, IF, RC, CIN…').fill(nomClient)
    await p.getByRole('row').filter({ hasText: nomClient }).first().click({ timeout: 60_000 })
    await expect(p.getByText(`Fiche client — ${nomClient}`)).toBeVisible({ timeout: 30_000 })
    await p.getByRole('button', { name: 'Anonymiser (RGPD)' }).click()
    const dlg = p.getByRole('alertdialog')
    await expect(dlg).toContainText('Anonymiser ce client ?')
    await dlg.getByRole('button', { name: 'Anonymiser définitivement' }).click()
    await expect(toast(p, 'Client anonymisé (données personnelles effacées)')).toBeVisible({ timeout: 30_000 })
    // Les leads du client (vivant et archivé) s'affichent anonymisés sur leur fiche.
    const ficheAnonyme = async (pk) => {
      await p.goto(`/crm/leads/${pk}`)
      await expect(p.getByRole('heading', { level: 1, name: 'Lead — Anonymisé' }), `lead #${pk} : titre « Lead — Anonymisé »`).toBeVisible({ timeout: 60_000 })
      await expect(p.locator('body'), `lead #${pk} : plus le nom d'origine`).not.toContainText(`Jean ${m}`)
      await expect(p.locator('body')).not.toContainText(`Jean archive ${m}`)
      await expect(p.locator('a[href^="tel:"], a[href^="mailto:"]'), `lead #${pk} : ni téléphone ni e-mail`).toHaveCount(0)
    }
    for (const pk of ids.leads) await ficheAnonyme(pk)
    // Persistance : recharger la fiche.
    await p.reload()
    await expect(p.getByRole('heading', { level: 1, name: 'Lead — Anonymisé' }), 'après rechargement : toujours anonymisé').toBeVisible({ timeout: 60_000 })
    await ficheAnonyme(ids.leads[0])
    await montrer(page)
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await py(`from apps.crm.models import Client, Lead
for pk in ${J(ids.leads)}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception: pass
try: Client.objects.filter(pk=${ids.client}).delete()
except Exception: pass`).catch(() => undefined)
    })
  }
})

// ═══ PF10.3 — ASUP15 : supprimer un lead, « Annuler », /parametres/corbeille ⇒ entrée absente des actives ═══
etape('PF10.3-ASUP15-ecran', ['ASUP15'], async ({ page }) => {
  const m = marque()
  const nomLead = `ASUP15 ${m}`
  const ids = await py(`from apps.crm.models import Lead
own = U.objects.get(username='demo_admin')
l = Lead.objects.create(company_id=${SOC}, nom=${J(nomLead)}, telephone='${telephoneMobileUnique()}', owner=own, stage='NEW')
sortie(dict(lead=l.pk))`)
  try {
    // Administrateur (demo_admin) : liste des leads → « Supprimer » → toast « Lead supprimé. » → « Annuler ».
    const q = encodeURIComponent(nomLead)
    // Écran large : la colonne d'actions de la vue liste (« Supprimer ») sort de la fenêtre en 1280 px (run 1).
    await page.setViewportSize({ width: 2200, height: 1100 })
    await page.goto(`/crm/leads?view=liste&q=${q}`)
    const row = page.locator('tr.lv-row').filter({ hasText: nomLead })
    await expect(row).toBeVisible({ timeout: 60_000 })
    await row.getByRole('button', { name: 'Supprimer' }).click()
    const dlg = page.getByRole('alertdialog')
    await expect(dlg).toContainText('Supprimer ce lead ?')
    await dlg.getByRole('button', { name: 'Supprimer' }).click()
    const t = toast(page, 'Lead supprimé.')
    await expect(t).toBeVisible({ timeout: 30_000 })
    await t.getByRole('button', { name: 'Annuler' }).click()
    await expect(row, 'le lead revient dans la liste').toBeVisible({ timeout: 30_000 })
    const lu = await py(`from apps.crm.models import Lead
${ENTREE(ids.lead)}
sortie([Lead.all_objects.get(pk=${ids.lead}).is_deleted, _e is not None and _e.restaure_le is not None])`)
    expect(lu, 'en base : lead vivant, l\'entrée ElementSupprime porte restaure_le').toEqual([false, true])
    // /parametres/corbeille : l'entrée n'est plus parmi les actives ; elle n'apparaît qu'avec « déjà restaurés ».
    await page.goto('/parametres/corbeille')
    await expect(page.getByTestId('corbeille-table').or(page.getByText('Corbeille vide')).first()).toBeVisible({ timeout: 60_000 })
    await page.waitForLoadState('networkidle')
    const entree = page.getByTestId('corbeille-row').filter({ hasText: nomLead })
    await expect(entree, 'entrée absente des actives').toHaveCount(0)
    await page.getByLabel('Inclure les éléments déjà restaurés').click()
    await page.getByRole('button', { name: 'Filtrer' }).click()
    await expect(entree, 'témoin : l\'entrée existe, marquée restaurée').toBeVisible({ timeout: 30_000 })
    await expect(entree).toContainText('Restauré')
    await expect(entree.getByRole('button', { name: 'Restaurer' })).toHaveCount(0)
    // Persistance : recharger (filtre par défaut) — toujours absente des actives.
    await page.reload()
    await expect(page.getByTestId('corbeille-table').or(page.getByText('Corbeille vide')).first()).toBeVisible({ timeout: 60_000 })
    await page.waitForLoadState('networkidle')
    await expect(page.getByTestId('corbeille-row').filter({ hasText: nomLead }), 'après rechargement : absente des actives').toHaveCount(0)
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await supprimerLeads([ids.lead])
    })
  }
})

// ═══ PF10.2 — ASUP43 : la cloche affiche le même nombre que la liste (12 non lues archivées ignorées) ═══
etape('PF10.2-ASUP43-ecran', ['ASUP43'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-ASUP-017')
  const m = marque()
  const nom = `asup43co_${m}`
  const co = await compteRole(nom, 'Commercial')
  const ids = await py(`from datetime import timedelta
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
u = U.objects.get(pk=${co})
Notification.objects.filter(recipient=u).delete()
mk = lambda t: Notification.objects.create(company_id=u.company_id, recipient=u, event_type=EventType.LEAD_ASSIGNED, title=t)
vieilles = [mk('ASUP43 archivée %d ${m}' % i) for i in range(12)]
Notification.objects.filter(pk__in=[n.pk for n in vieilles]).update(archived=True, created_at=timezone.now() - timedelta(days=70))
recentes = [mk('ASUP43 récente %d ${m}' % i) for i in range(3)]
sortie(dict(vieilles=[n.pk for n in vieilles], recentes=[n.pk for n in recentes]))`)
  try {
    const p = await ecran(page, suivi, testInfo, nom)
    const derive = async () => {
      const d = await lireJson(await p.request.get(`${API}/reporting/notifications/`, T), 'alertes dérivées de la cloche')
      return d.total ?? 0
    }
    const cloche = p.getByRole('button', { name: /^Notifications \(\d+\)$/ }).first()
    const nombre = async () => Number((await cloche.getAttribute('aria-label')).match(/\((\d+)\)/)[1])
    const panneau = p.locator('.nb-panel')
    const recentes = panneau.locator('.nb-item').filter({ hasText: `ASUP43 récente` })
    await p.goto('/apps')
    const base = await derive()
    await expect(cloche, 'cloche : alertes dérivées + 3 non lues récentes (les 12 archivées ignorées)')
      .toHaveAttribute('aria-label', `Notifications (${base + 3})`, { timeout: 60_000 })
    await cloche.click()
    await expect(recentes, 'liste : les 3 récentes').toHaveCount(3, { timeout: 30_000 })
    await expect(panneau.locator('.nb-item.nb-item-unread').filter({ hasText: 'ASUP43 récente' }), 'liste : 3 non lues').toHaveCount(3)
    await expect(panneau.locator('.nb-item').filter({ hasText: 'ASUP43 archivée' }), 'liste : aucune archivée').toHaveCount(0)
    const avant = await nombre()
    expect(avant - base, 'la cloche compte exactement les non lues que la liste montre').toBe(3)
    // La liste servie à la cloche (non lues, tous types) = ce que « tout marquer lu » doit marquer ; jamais les 12 archivées.
    const listeNonLues = await lireJson(await p.request.get(`${API}/notifications/notifications/?unread=1&page_size=100`, T), 'liste des non lues')
    const nl = (Array.isArray(listeNonLues) ? listeNonLues : listeNonLues.results)
    expect(nl.filter((x) => ids.vieilles.includes(x.id)), 'liste : aucune archivée').toEqual([])
    expect(nl.filter((x) => ids.recentes.includes(x.id)).length, 'liste : les 3 récentes').toBe(3)
    const compte = await lireJson(await p.request.get(`${API}/notifications/notifications/unread-count/`, T), 'compteur')
    expect(compte.unread, 'compteur non lues = la liste (les 12 archivées ignorées)').toBe(nl.length)
    // « Tout marquer lu » : exactement les non lues de la liste.
    await panneau.getByRole('button', { name: 'Tout marquer lu', exact: true }).first().click()
    await expect.poll(() => p.locator('[data-sonner-toast]').allInnerTexts(), { message: '« tout lu » porte sur les non lues de la liste', timeout: 30_000 })
      .toEqual(expect.arrayContaining([expect.stringContaining(`${nl.length} marqué${nl.length > 1 ? 's' : ''} lu.`)]))
    await expect(cloche).toHaveAttribute('aria-label', `Notifications (${base})`, { timeout: 30_000 })
    const lu = await py(`from apps.notifications.models import Notification
sortie([Notification.objects.filter(pk__in=${J(ids.vieilles)}, read=False, archived=True).count(), Notification.objects.filter(pk__in=${J(ids.recentes)}, read=True).count()])`)
    expect(lu, 'en base : 12 archivées non lues intouchées, 3 récentes lues').toEqual([12, 3])
    // Persistance : recharger — la cloche ne remonte pas, la liste ne montre plus de non lue du jeu.
    await p.reload()
    await expect(cloche, 'après rechargement : cloche = alertes dérivées seules').toHaveAttribute('aria-label', `Notifications (${await derive()})`, { timeout: 60_000 })
    await cloche.click()
    await expect(recentes, 'après rechargement : les 3 toujours listées').toHaveCount(3, { timeout: 30_000 })
    await expect(panneau.locator('.nb-item.nb-item-unread').filter({ hasText: 'ASUP43' }), 'après rechargement : 0 non lue du jeu').toHaveCount(0)
    await auRepos(suivi)
    await montrer(page)
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await py(`from apps.notifications.models import Notification
Notification.objects.filter(recipient_id=${co}).delete()`).catch(() => undefined)
    })
  }
})

// ═══ PF10.2 — ASUP45 : archiver (à l'écran) un lead à à-faire manuel ⇒ l'à-faire quitte Ma file et le Calendrier ═══
etape('PF10.2-ASUP45-ecran', ['ASUP45'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-ASUP-019')
  const m = marque()
  const nom = `asup45co_${m}`
  const co = await compteRole(nom, 'Commercial')
  const ids = await py(`import datetime
from django.contrib.contenttypes.models import ContentType
from apps.crm.models import Lead
from apps.records.models import Activity
u = U.objects.get(pk=${co})
ct = ContentType.objects.get_for_model(Lead)
hier = datetime.date.today() - datetime.timedelta(days=1)
leads = [Lead.objects.create(company_id=${SOC}, nom='ASUP45 %s ${m}' % n, owner=u, stage='NEW') for n in ('A1', 'A2', 'A3')]
acts = [Activity.objects.create(company_id=${SOC}, content_type=ct, object_id=l.pk, summary='Rappeler %s ${m}' % n, assigned_to=u, due_date=hier) for l, n in zip(leads, ('A1', 'A2', 'A3'))]
sortie(dict(leads=[l.pk for l in leads], acts=[a.pk for a in acts]))`)
  const af = (n) => `Rappeler ${n} ${m}`
  try {
    const p = await ecran(page, suivi, testInfo, nom)
    const file = p.locator('table[aria-label="Ma file"]')
    // Témoin d'abord : les trois à-faire sont dans Ma file.
    await p.goto('/activites')
    for (const n of ['A1', 'A2', 'A3']) await expect(file.getByRole('row').filter({ hasText: af(n) }), `avant : ${n} dans Ma file`).toBeVisible({ timeout: 60_000 })
    // Le commercial ARCHIVE le lead de A1 à l'écran (fiche → « Plus d'actions » → « Archiver ») ; le lead de A2 est mis à la corbeille.
    await p.goto(`/crm/leads/${ids.leads[0]}`)
    await expect(p.getByRole('heading', { level: 1, name: `Lead — ASUP45 A1 ${m}` })).toBeVisible({ timeout: 60_000 })
    await p.getByRole('button', { name: "Plus d'actions", exact: true }).first().click()
    await p.getByRole('menuitem', { name: 'Archiver' }).click()
    await p.getByRole('alertdialog').getByRole('button', { name: 'Archiver' }).click()
    await expect(toast(p, 'archivé.'), 'archivage confirmé').toBeVisible({ timeout: 30_000 })
    const del = await page.request.delete(`${API}/crm/leads/${ids.leads[1]}/`, T)
    expect(del.status(), `suppression du lead de A2 : ${(await del.text()).slice(0, 200)}`).toBeLessThan(300)
    const etat = await py(`from apps.crm.models import Lead
from apps.records.models import Activity
sortie(dict(leads=[[l.is_archived, l.is_deleted] for l in (Lead.all_objects.get(pk=pk) for pk in ${J(ids.leads)})],
  ouverts=Activity.objects.filter(pk__in=${J(ids.acts)}, done=False).count()))`)
    expect(etat.leads, 'en base : A1 archivé (par l\'écran), A2 supprimé, A3 actif').toEqual([[true, false], [false, true], [false, false]])
    expect(etat.ouverts, 'les à-faire ne sont ni clos ni modifiés').toBe(3)
    const verifier = async (quand) => {
      await p.goto('/activites')
      await expect(file.getByRole('row').filter({ hasText: af('A3') }), `${quand} : A3 dans Ma file`).toBeVisible({ timeout: 60_000 })
      await expect(file.getByRole('row').filter({ hasText: af('A1') }), `${quand} : A1 (lead archivé) hors de Ma file`).toHaveCount(0)
      await expect(file.getByRole('row').filter({ hasText: af('A2') }), `${quand} : A2 (lead supprimé) hors de Ma file`).toHaveCount(0)
      await expect(p.getByText(/^1 en retard/), `${quand} : « 1 en retard » (A3 seul)`).toBeVisible()
      // Observation (hors clause) : le bloc « Mes activités » de la même page.
      const mes = await p.getByRole('table').filter({ hasText: af('A1') }).count()
      console.log(`[ASUP45] ${quand} : bloc « Mes activités » montre encore A1 (lead archivé) : ${mes > 0}`)
      await p.goto('/calendrier')
      const ev = (n) => p.locator('.cp-event').filter({ hasText: af(n) })
      await expect(ev('A3'), `${quand} : A3 au Calendrier`).toBeVisible({ timeout: 60_000 })
      await expect(ev('A1'), `${quand} : A1 absent du Calendrier`).toHaveCount(0)
      await expect(ev('A2'), `${quand} : A2 absent du Calendrier`).toHaveCount(0)
    }
    await verifier('après archivage')
    await p.reload()
    await verifier('après rechargement')
    await auRepos(suivi)
    await montrer(page)
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await py(`from apps.records.models import Activity
Activity.objects.filter(pk__in=${J(ids.acts)}).delete()`).catch(() => undefined)
    await supprimerLeads(ids.leads)
    })
  }
})
