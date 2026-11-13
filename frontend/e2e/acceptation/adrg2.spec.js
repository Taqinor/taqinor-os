// Preuves en direct du groupe ADRG, lot 2 (audit PF4 « droits de la grille des rôles », dossier
// docs/audits/2026-11-10-parcours-PF4.md) : ADRG2, 4, 17, 18, 20, 23, 82, 84, 85, 88, 89, 96, 97, 101.
// Chaque étape joue le geste sous de VRAIS comptes des rôles LIVRÉS (registre `CANONICAL_SYSTEM_ROLES`, semés
// par `init_roles` dans la société démo, relus par leur nom — jamais un rôle fabriqué), connectés par la vraie
// route `/token/` : l'écran (navigateur à part, cookies du compte) et/ou la route. Données propres créées par
// l'API de demo_admin ; un compte d'essai « normal » (Commercial, Viewer) ne voit que SES enregistrements
// (`core/scoping.py`, portée « soi ») : les lignes de l'étape lui sont attribuées en base (owner / created_by).
// Clause de persistance : relecture en base ou par l'API après le geste ; écran relu après rechargement.
// Sondes : `docs/audits/sondes/ADRG/C-ADRG-053.py` rejouée par `scripts/sonde.py` (transaction annulée) ; sur un
// runner sans conteneur (`E2E_SONDE_LOCALE=1`), le même programme est envoyé à `manage.py shell` local.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, lireJson, listeDe, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG2', 'ADRG4', 'ADRG17', 'ADRG18', 'ADRG20', 'ADRG23', 'ADRG82', 'ADRG84',
  'ADRG85', 'ADRG88', 'ADRG89', 'ADRG96', 'ADRG97', 'ADRG101'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const J = (x) => JSON.stringify(x)
const SOC = `U.objects.get(username='demo_admin').company_id`
const echapper = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const comptes = []

/** Compte d'essai du rôle LIVRÉ `nomRole` (société démo) ; {id, username}. */
async function compteRole(nomRole, prefixe) {
  const username = `${prefixe}_${marque()}`
  const id = await py(`from apps.roles.models import Role
u = compte(${J(username)}, role=Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}).pk, societe=${SOC})
sortie(u.id)`)
  comptes.push(username)
  return { id, username }
}

/** Contexte API connecté (vraie route /token/) d'un compte du rôle livré. */
async function apiSous(testInfo, nomRole, prefixe) {
  const c = await compteRole(nomRole, prefixe)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: c.username, password: MDP_ESSAI })
  return { ...c, ctx }
}

/** Navigateur à part (aucun cookie de demo_admin) connecté sous un compte du rôle livré ; page observée. */
async function ecranSous(page, suivi, testInfo, nomRole, prefixe, existant = null) {
  const c = existant || await compteRole(nomRole, prefixe)
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
  })
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: c.username, password: MDP_ESSAI })
  const p = suivi.surveiller(await ctx.newPage())
  return { ...c, ctx, p, api: ctx.request }
}

test.afterAll(async () => {
  if (!comptes.length) return
  await py(`U.objects.filter(username__in=${J(comptes)}).update(is_active=False)
sortie(1)`).catch(() => null)
})

/** Attribue à `uid` le lead, le devis et ses factures / BC (portée « soi » des rôles normaux). */
const approprier = (uid, { lead = null, devis = null } = {}) => py(`from django.db.models import Q
from apps.crm.models import Lead
from apps.ventes.models import Devis, Facture
n = 0
if ${lead ?? 'None'}:
    n += Lead.objects.filter(pk=${lead ?? 'None'}).update(owner_id=${uid})
if ${devis ?? 'None'}:
    n += Devis.objects.filter(pk=${devis ?? 'None'}).update(created_by_id=${uid})
    n += Facture.objects.filter(Q(devis_id=${devis ?? 'None'}) | Q(bon_commande__devis_id=${devis ?? 'None'})).update(created_by_id=${uid})
    try:
        from apps.ventes.models import BonCommande
        n += BonCommande.objects.filter(devis_id=${devis ?? 'None'}).update(created_by_id=${uid})
    except Exception:
        pass
sortie(n)`)

/** Vente acceptée par demo_admin : lead (téléphone mobile valide) + produit + devis atomique + envoi + acceptation. */
async function vente(r, m) {
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ADRG ${m}`, prix_vente: '10000.00', prix_achat: '4321.09' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: `Client ADRG ${m}` } }), 'acceptation')
  return { lead, devis: await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu') }
}
const lireFacture = async (r, id) => lireJson(await r.get(`${API}/ventes/factures/${id}/`, T), `facture ${id}`)

/** Facture du BC d'un devis (convertir-bc → confirmer → creer-facture), émise si `emettre`. */
async function factureBc(r, d, emettre = true) {
  const bc = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/convertir-bc/`, { ...T, data: {} }), 'convertir-bc')
  await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/confirmer/`, { ...T, data: {} }), 'confirmer BC')
  const brouillon = await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: {} }), 'facture du BC')
  if (emettre) await lireJson(await r.post(`${API}/ventes/factures/${brouillon.id}/emettre/`, { ...T, data: {} }), 'émission')
  return lireFacture(r, brouillon.id)
}

/** Libellés des entrées d'un menu ouvert (Radix), menu refermé ensuite. */
async function entreesMenu(p) {
  const menu = p.getByRole('menu')
  await expect(menu, 'menu ouvert').toBeVisible({ timeout: 30_000 })
  const textes = (await menu.getByRole('menuitem').allInnerTexts()).map((x) => x.replace(/\s+/g, ' ').trim())
  await p.keyboard.press('Escape')
  await expect(menu).toBeHidden()
  return textes
}

// ── PF4.2 — ADRG23 : gestes d'écriture du navigateur GED sous `ged_gerer` (Viewer vs Commercial) ────────────
const PDF = (n) => Buffer.from(`%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n% version ${n}\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF\n`)

/** Armoire + dossier + document PDF (une version) par demo_admin. */
async function dossierGed(r, m, prefixe) {
  const GED = `${API}/ged`
  const cab = await lireJson(await r.post(`${GED}/cabinets/`, { ...T, data: { nom: `Cab ${prefixe} ${m}` } }), 'armoire')
  const dos = await lireJson(await r.post(`${GED}/dossiers/`, { ...T, data: { nom: `Dos ${prefixe} ${m}`, cabinet: cab.id } }), 'dossier')
  const doc = await lireJson(await r.post(`${GED}/documents/`, { ...T, data: { nom: `Plan ${prefixe} ${m}`, folder: dos.id } }), 'document')
  await lireJson(await r.post(`${GED}/documents/${doc.id}/nouvelle-version/`, { ...T, multipart: { file: { name: 'plan.pdf', mimeType: 'application/pdf', buffer: PDF(1) } } }), 'version PDF')
  return { cab, dos, doc }
}

/** Ouvre /ged, choisit l'armoire (sélecteur présent dès 2 armoires) puis le dossier ; attend la ligne du document. */
async function ouvrirDossierGed(p, { cab, dos, doc }) {
  await p.goto('/ged')
  const choix = p.getByRole('combobox', { name: 'Choisir le cabinet' })
  await expect(p.getByRole('tree', { name: 'Dossiers' }).or(choix).first()).toBeVisible({ timeout: 60_000 })
  if (await choix.count()) {
    await choix.click()
    await p.getByRole('option', { name: cab.nom, exact: true }).click()
  }
  await p.getByRole('treeitem').filter({ hasText: dos.nom }).getByRole('button').first().click()
  await expect(p.getByRole('button', { name: `Aperçu de ${doc.nom}` }), 'document listé').toBeVisible({ timeout: 60_000 })
}

etape('PF4.2-ADRG23', ['ADRG23'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const g = await dossierGed(page.request, m, 'ADRG23')
  const nom = g.doc.nom
  const ECRITURE = [/^Téléverser$/, /^Renommer$/, /^Déplacer$/, /Lien de dépôt/, /Nouvelle armoire/,
    new RegExp(`Mettre ${echapper(nom)} en corbeille`)]
  for (const [nomRole, prefixe, gerer] of [['Viewer', 'adrg23vi', false], ['Commercial', 'adrg23co', true]]) {
    const s = await ecranSous(page, suivi, testInfo, nomRole, prefixe)
    await ouvrirDossierGed(s.p, g)
    await s.p.waitForLoadState('networkidle')
    for (const geste of ECRITURE) {
      await expect(s.p.getByRole('button', { name: geste }), `${nomRole} : ${geste}`).toHaveCount(gerer ? 1 : 0)
    }
    // Lot : ZIP ouvert à tous ; corbeille / étiqueter en lot sous ged_gerer.
    await s.p.getByRole('checkbox', { name: `Sélectionner ${nom}` }).check()
    await expect(s.p.getByRole('button', { name: /Télécharger \(\.zip\)/ }), `${nomRole} : ZIP`).toBeVisible()
    await expect(s.p.getByRole('button', { name: /^Mettre en corbeille$/ }), `${nomRole} : corbeille en lot`).toHaveCount(gerer ? 1 : 0)
    await expect(s.p.getByRole('button', { name: /Étiqueter \/ Déplacer/ }), `${nomRole} : lots`).toHaveCount(gerer ? 1 : 0)
    // Extraction et verrou restent pour les deux (route IsAnyRole) ; nouvelle version / cycle de vie sous ged_gerer.
    await expect(s.p.getByRole('button', { name: `Extraire ${nom}` }), `${nomRole} : extraire`).toBeVisible()
    await s.p.getByRole('button', { name: `Plus d'actions pour ${nom}` }).click()
    const menu = await entreesMenu(s.p)
    expect(menu.some((x) => /Verrouiller \(avertissement\)/.test(x)), `${nomRole} : verrou ${J(menu)}`).toBe(true)
    expect(menu.some((x) => /Nouvelle version/.test(x)), `${nomRole} : nouvelle version ${J(menu)}`).toBe(gerer)
    expect(menu.some((x) => /Cycle de vie/.test(x)), `${nomRole} : cycle de vie ${J(menu)}`).toBe(gerer)
    // Persistance : après rechargement, même rendu pour le Viewer (aucun geste d'écriture).
    if (!gerer) {
      await ouvrirDossierGed(s.p, g)
      await s.p.waitForLoadState('networkidle')
      await expect(s.p.getByRole('button', { name: /^Téléverser$/ }), 'Viewer relu : pas de téléversement').toHaveCount(0)
    }
    await s.ctx.close()
  }
})

// ── PF4.2 — ADRG85 : purge (corbeille) et legal holds (rétention) sous `ged_gouvernance` ──────────────────
etape('PF4.2-ADRG85', ['ADRG85'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const g = await dossierGed(r, m, 'ADRG85')
  await lireJson(await r.post(`${API}/ged/documents/${g.doc.id}/mettre-en-corbeille/`, { ...T, data: {} }), 'mise en corbeille')
  const tenu = await lireJson(await r.post(`${API}/ged/documents/`, { ...T, data: { nom: `Tenu ADRG85 ${m}`, folder: g.dos.id } }), 'document tenu')
  const motif = `Litige ADRG85 ${m}`
  const hold = await lireJson(await r.post(`${API}/ged/legal-holds/`, { ...T, data: { document: tenu.id, motif } }), 'legal hold')
  for (const [nomRole, prefixe, gouv] of [['Commercial responsable', 'adrg85cr', false], ['Directeur', 'adrg85di', true]]) {
    const s = await ecranSous(page, suivi, testInfo, nomRole, prefixe)
    await s.p.goto('/ged/corbeille')
    const ligne = s.p.getByRole('row').filter({ hasText: g.doc.nom })
    await expect(ligne, `${nomRole} : document en corbeille listé`).toBeVisible({ timeout: 60_000 })
    await ligne.getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
    const menu = await entreesMenu(s.p)
    expect(menu.some((x) => /Restaurer/.test(x)), `${nomRole} : Restaurer ${J(menu)}`).toBe(true)
    expect(menu.some((x) => /Supprimer définitivement/.test(x)), `${nomRole} : purge ${J(menu)}`).toBe(gouv)
    await s.p.goto('/ged/retention')
    await s.p.getByRole('tab', { name: 'Legal holds' }).click()
    const lh = s.p.getByRole('row').filter({ hasText: motif })
    await expect(lh, `${nomRole} : hold listé`).toBeVisible({ timeout: 60_000 })
    await expect(s.p.getByRole('button', { name: /Poser un hold/ }), `${nomRole} : Poser un hold`).toHaveCount(gouv ? 1 : 0)
    const kebab = lh.getByRole('button', { name: "Plus d'actions sur la ligne" })
    if (gouv) {
      await kebab.click()
      const actions = await entreesMenu(s.p)
      expect(actions.some((x) => /Lever le hold/.test(x)), `Directeur : Lever ${J(actions)}`).toBe(true)
    } else {
      await expect(kebab, 'Commercial responsable : aucune action sur le hold').toHaveCount(0)
    }
    await s.ctx.close()
  }
  // Persistance : rien n'a été purgé ni levé (document toujours en corbeille, hold toujours actif).
  const etat = await py(`from apps.ged.models import Document, LegalHold
d = Document.all_objects.filter(pk=${g.doc.id}).first() if hasattr(Document, 'all_objects') else Document.objects.filter(pk=${g.doc.id}).first()
sortie([d is not None, LegalHold.objects.get(pk=${hold.id}).actif])`)
  expect(etat, 'document existant, hold actif').toEqual([true, true])
})

// ── PF4.2 — ADRG89 : « Caviarder… » de l'aperçu sous `ged_gouvernance` ──────────────────────────────────────
etape('PF4.2-ADRG89', ['ADRG89'], async ({ page, suivi, testInfo }) => {
  const g = await dossierGed(page.request, marque(), 'ADRG89')
  for (const [nomRole, prefixe, gouv] of [['Commercial', 'adrg89co', false], ['Directeur', 'adrg89di', true]]) {
    const s = await ecranSous(page, suivi, testInfo, nomRole, prefixe)
    await ouvrirDossierGed(s.p, g)
    await s.p.getByRole('button', { name: `Aperçu de ${g.doc.nom}` }).click()
    const dlg = s.p.getByRole('dialog').filter({ hasText: g.doc.nom })
    await expect(dlg, `${nomRole} : aperçu ouvert`).toBeVisible({ timeout: 60_000 })
    await s.p.waitForLoadState('networkidle')
    await expect(dlg.getByRole('button', { name: /Télécharger|Comparer|Fermer/ }).first(), `${nomRole} : aperçu rendu`).toBeVisible({ timeout: 60_000 })
    await expect(dlg.getByRole('button', { name: /Caviarder/ }), `${nomRole} : Caviarder`).toHaveCount(gouv ? 1 : 0)
    await s.ctx.close()
  }
})

// ── PF4.5 — ADRG96 / ADRG97 : compte du portail client (client figé, réactivation réservée à l'admin) ─────────
/** Rejoue une sonde du dossier (transaction annulée) ; renvoie le dict observé. */
function sonde(chemin) {
  const python = process.env.E2E_PYTHON || 'python'
  const args = process.env.E2E_SONDE_LOCALE === '1'
    ? ['-c', [
      'import sys, subprocess',
      "sys.path.insert(0, 'scripts')",
      'import sonde',
      'def ex(cmd, prog, timeout):',
      "    r = subprocess.run([sys.executable, '-u', 'manage.py', 'shell'], input=prog.encode('utf-8'), capture_output=True, timeout=timeout + 60, cwd='backend/django_core')",
      "    return r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')",
      "sys.exit(sonde.main([sys.argv[1], '--sans-fraicheur'], executer=ex))",
    ].join('\n'), chemin]
    : ['scripts/sonde.py', chemin]
  const r = spawnSync(python, args, { cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000 })
  const lignes = (r.stdout || '').split('\n')
  const ligne = lignes.filter((l) => l.startsWith('{')).pop()
  expect(ligne, `sonde ${chemin} : ${(r.stdout || '').slice(-800)} ${(r.stderr || '').slice(-400)}`).toBeTruthy()
  expect(r.stdout, 'base inchangée après la sonde').toContain('base inchangée : oui')
  return JSON.parse(ligne)
}

/** Client CRM de la société démo + compte portail (provisionné par demo_admin) ; {client, compte, jeton}. */
async function comptePortail(r, m, lettre) {
  const c = await py(`from apps.crm.models import Client
c = Client.objects.create(company_id=${SOC}, nom=${J(`ADRG Portail ${lettre} ${m}`)}, prenom='Essai', email=${J(`adrg-${lettre.toLowerCase()}-${m}@example.invalid`)})
sortie(dict(id=c.id, nom=c.nom, email=c.email))`)
  const compte = await lireJson(await r.post(`${API}/portail/comptes-portail/`, { ...T, data: { client: c.id } }), `compte portail ${lettre}`)
  const jeton = await py(`from apps.portail.models import ComptePortailClient
sortie(ComptePortailClient.objects.get(pk=${compte.id}).token_acces)`)
  return { client: c, compte, jeton }
}
/** Compte ACTIF résolu par un jeton (même requête que le sélecteur historique, `test_aud141_jeton_acces`). */
const clientParJeton = (jeton) => py(`from apps.portail.models import ComptePortailClient
c = ComptePortailClient.objects.filter(token_acces=${J(jeton)}, actif=True).first()
sortie(c.client_id if c else None)`)

etape('PF4.5-ADRG96', ['ADRG96'], async ({ page, testInfo }) => {
  // Sonde du constat (rôle « Commercial » semé comme init_roles, transaction annulée).
  const s = sonde('ADRG/C-ADRG-053')
  expect(s.repro, 'sonde : plus de re-pointage du compte').toBe(false)
  expect(s.etape2_patch_client?.[0], `sonde : PATCH {client: B} refusé ${J(s.etape2_patch_client)}`).toBe(409)
  expect(s.etape2_compte_relu?.client_id, 'sonde : compte relu rattaché à A').toBe(s.ids?.A)
  // Geste réel : un Commercial connecté PATCH {client: B} sur le compte de A.
  const r = page.request
  const m = marque()
  const a = await comptePortail(r, m, 'A')
  const b = await py(`from apps.crm.models import Client
sortie(Client.objects.create(company_id=${SOC}, nom=${J(`ADRG Portail B ${m}`)}, prenom='Essai', email=${J(`adrg-b-${m}@example.invalid`)}).id)`)
  const co = await apiSous(testInfo, 'Commercial', 'adrg96co')
  const url = `${API}/portail/comptes-portail/${a.compte.id}/`
  const refus = await co.ctx.patch(url, { ...T, data: { client: b } })
  const corps = await refus.text()
  // Plan : 400 ; le correctif livré répond 409 (`ConflitEtat`, fix-ci api-fuzz PR #1370, test aligné).
  expect(refus.status(), `PATCH {client: B} par le Commercial : ${corps.slice(0, 300)}`).toBe(409)
  expect(corps, 'motif sur `client`').toContain('ne se modifie pas')
  const di = await apiSous(testInfo, 'Directeur', 'adrg96di')
  const refusDir = await di.ctx.patch(url, { ...T, data: { client: b } })
  expect(refusDir.status(), 'PATCH {client: B} par le Directeur : refusé aussi').toBe(409)
  // Le MÊME client reste accepté.
  const meme = await co.ctx.patch(url, { ...T, data: { client: a.client.id } })
  expect(meme.status(), `PATCH {client: A} : ${(await meme.text()).slice(0, 300)}`).toBe(200)
  // Persistance : compte relu rattaché à A ; le jeton de A résout toujours A.
  expect((await lireJson(await r.get(url, T), 'compte relu')).client, 'compte relu : client A').toBe(a.client.id)
  expect(await clientParJeton(a.jeton), 'jeton de A ⇒ client A').toBe(a.client.id)
  for (const x of [co, di]) await x.ctx.dispose()
})

etape('PF4.5-ADRG97', ['ADRG97'], async ({ page, suivi, testInfo }) => {
  const s = sonde('ADRG/C-ADRG-053')
  expect(s.cas2_patch_actif?.[0], `sonde : réactivation par le Commercial ${J(s.cas2_patch_actif)}`).toBe(403)
  expect([s.cas2_actif_relu, s.cas2_acces_rouvert], 'sonde : compte toujours révoqué').toEqual([false, false])
  const r = page.request
  const m = marque()
  const rev = await comptePortail(r, m, 'R')
  const act = await comptePortail(r, m, 'V')
  const urlRev = `${API}/portail/comptes-portail/${rev.compte.id}/`
  await lireJson(await r.patch(urlRev, { ...T, data: { actif: false } }), 'révocation par demo_admin')
  const co = await apiSous(testInfo, 'Commercial', 'adrg97co')
  const refus = await co.ctx.patch(urlRev, { ...T, data: { actif: true } })
  const corps = await refus.text()
  expect(refus.status(), `réactivation par le Commercial : ${corps.slice(0, 300)}`).toBe(403)
  expect(corps, 'motif').toContain("Réactivation réservée à l'administrateur")
  const relu = await py(`from apps.portail.models import ComptePortailClient
c = ComptePortailClient.objects.get(pk=${rev.compte.id})
u = getattr(c, 'utilisateur', None) or getattr(c, 'user', None)
sortie([c.actif, None if u is None else u.is_active])`)
  expect(relu[0], 'compte relu : toujours inactif').toBe(false)
  if (relu[1] !== null) expect(relu[1], 'utilisateur portail : toujours inactif').toBe(false)
  expect(await clientParJeton(rev.jeton), 'jeton toujours refusé').toBeNull()
  // Écran Portail client → Administration (palier responsable) : interrupteur du compte révoqué grisé,
  // celui d'un compte actif toujours actionnable ; le Commercial (palier normal) n'a pas l'écran.
  const cr = await ecranSous(page, suivi, testInfo, 'Commercial responsable', 'adrg97cr')
  await cr.p.goto('/portail/administration')
  const sw = cr.p.getByRole('switch', { name: `Activer le compte ${rev.client.email}` })
  await expect(sw, 'interrupteur du compte révoqué').toBeVisible({ timeout: 60_000 })
  await expect(sw, 'grisé hors administrateur').toBeDisabled()
  await expect(cr.p.getByRole('switch', { name: `Révoquer le compte ${act.client.email}` }), 'révoquer reste offert').toBeEnabled()
  await cr.p.reload()
  await expect(cr.p.getByRole('switch', { name: `Activer le compte ${rev.client.email}` }), 'relu : toujours grisé').toBeDisabled({ timeout: 60_000 })
  await cr.ctx.close()
  const coe = await ecranSous(page, suivi, testInfo, 'Commercial', 'adrg97coe')
  await coe.p.goto('/portail/administration')
  await coe.p.waitForLoadState('networkidle')
  await expect(coe.p.getByRole('switch', { name: `Activer le compte ${rev.client.email}` }), 'Commercial : aucun interrupteur').toHaveCount(0)
  await coe.ctx.close()
  // Révoquer reste au Commercial (200) ; le Directeur rouvre (200).
  const urlAct = `${API}/portail/comptes-portail/${act.compte.id}/`
  const rv = await co.ctx.patch(urlAct, { ...T, data: { actif: false } })
  expect(rv.status(), `révocation par le Commercial : ${(await rv.text()).slice(0, 200)}`).toBe(200)
  const di = await apiSous(testInfo, 'Directeur', 'adrg97di')
  const ro = await di.ctx.patch(urlRev, { ...T, data: { actif: true } })
  expect(ro.status(), `réactivation par le Directeur : ${(await ro.text()).slice(0, 200)}`).toBe(200)
  expect(await clientParJeton(rev.jeton), 'Directeur : jeton rouvert').toBe(rev.client.id)
  for (const x of [co, di]) await x.ctx.dispose()
})

// ── PF4.1 — ADRG2 : exclure des relances exige `encaisser` (Admin Ventes) ────────────────────────────────────
etape('PF4.1-ADRG2', ['ADRG2'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const v = await vente(r, marque())
  const f = await factureBc(r, v.devis)
  expect(f.statut, 'facture émise').toBe('emise')
  const av = await ecranSous(page, suivi, testInfo, 'Admin Ventes', 'adrg2av')
  const refus = await av.api.post(`${API}/ventes/factures/${f.id}/exclure-relance/`, { ...T, data: { exclu: true } })
  const corps = await refus.text()
  // 403 de la garde `PeutEncaisser` (HasPermissionOrLegacy('encaisser'), sans message propre : détail DRF générique).
  expect(refus.status(), `exclure-relance par l'Admin Ventes : ${corps.slice(0, 300)}`).toBe(403)
  expect((await lireFacture(r, f.id)).exclu_relances, 'persistance : exclu_relances reste faux').toBeFalsy()
  // Écran Ventes → Relances : ni « Exclure » ni « Promesse de paiement » dans le menu de la ligne.
  await av.p.goto('/ventes/relances')
  const ligne = av.p.getByRole('row').filter({ hasText: f.reference })
  await expect(ligne, 'facture dans la file des relances').toBeVisible({ timeout: 90_000 })
  await ligne.getByRole('button', { name: `Plus d'actions — ${f.reference}` }).click()
  const menu = await entreesMenu(av.p)
  expect(menu.length, `menu non vide ${J(menu)}`).toBeGreaterThan(0)
  expect(menu.some((x) => /^Exclure$/.test(x)), `Admin Ventes : Exclure ${J(menu)}`).toBe(false)
  expect(menu.some((x) => /Promesse de paiement/.test(x)), `Admin Ventes : Promesse ${J(menu)}`).toBe(false)
  await av.ctx.close()
  // Le Directeur exclut (200).
  const di = await apiSous(testInfo, 'Directeur', 'adrg2di')
  const ok = await di.ctx.post(`${API}/ventes/factures/${f.id}/exclure-relance/`, { ...T, data: { exclu: true } })
  expect(ok.status(), `exclure-relance par le Directeur : ${(await ok.text()).slice(0, 300)}`).toBe(200)
  await di.ctx.dispose()
})

// ── PF4.4 — ADRG17 : drapeaux `peut` du panneau de vente (Admin Ventes / Viewer / Commercial) ────────────────
/** Vente dont une facture de tranche (acompte) est émise et due, attribuée à `uid`. */
async function venteAcompte(r, m) {
  const v = await vente(r, m)
  let factures = listeDe(await lireJson(await r.get(`${API}/ventes/factures/?devis=${v.devis.id}`, T), 'factures du devis'))
  if (!factures.length) {
    const g = await r.post(`${API}/ventes/devis/${v.devis.id}/generer-facture/`, { ...T, data: {} })
    expect(g.status(), `generer-facture : ${(await g.text()).slice(0, 300)}`).toBeLessThan(300)
    factures = listeDe(await lireJson(await r.get(`${API}/ventes/factures/?devis=${v.devis.id}`, T), 'factures du devis'))
  }
  for (const f of factures.filter((x) => x.statut === 'brouillon')) {
    await lireJson(await r.post(`${API}/ventes/factures/${f.id}/emettre/`, { ...T, data: {} }), 'émission acompte')
  }
  const emise = listeDe(await lireJson(await r.get(`${API}/ventes/factures/?devis=${v.devis.id}`, T), 'factures relues')).find((x) => x.statut === 'emise')
  expect(emise, 'facture de tranche émise').toBeTruthy()
  return { ...v, facture: emise }
}
const venteDe = async (ctx, devisId) => (await lireJson(await ctx.get(`${API}/ventes/devis/${devisId}/`, T), `devis ${devisId}`)).vente

etape('PF4.4-ADRG17', ['ADRG17'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const attendus = {
    'Admin Ventes': { encaisser: false, pdf: true },
    Viewer: { encaisser: false, pdf: false, envoyer: false },
    Commercial: { encaisser: true, pdf: true, envoyer: true },
  }
  const vus = {}
  for (const [nomRole, prefixe] of [['Admin Ventes', 'adrg17av'], ['Viewer', 'adrg17vi'], ['Commercial', 'adrg17co']]) {
    const c = await compteRole(nomRole, prefixe)
    const v = await venteAcompte(r, marque())
    const vierge = await vente(r, marque())
    await approprier(c.id, { lead: v.lead.id, devis: v.devis.id })
    await approprier(c.id, { lead: vierge.lead.id, devis: vierge.devis.id })
    const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
    await connexionApi(ctx, { username: c.username, password: MDP_ESSAI })
    const etat = await venteDe(ctx, v.devis.id)
    const ligne = (etat?.factures || []).find((x) => x.id === v.facture.id)
    expect(ligne, `${nomRole} : facture dans etat_vente ${J(etat)?.slice(0, 400)}`).toBeTruthy()
    for (const [cle, val] of Object.entries(attendus[nomRole])) expect(ligne.peut?.[cle], `${nomRole} : peut.${cle} ${J(ligne.peut)}`).toBe(val)
    // facturer_* : l'ÉTAT de la vente décide (acompte avant solde) ; le DROIT ne doit rien retirer à un rôle qui
    // écrit les ventes — témoin = les drapeaux servis à demo_admin sur le même devis.
    const gestes = (await venteDe(ctx, vierge.devis.id))?.peut || {}
    const temoin = (await venteDe(r, vierge.devis.id))?.peut || {}
    expect(temoin.facturer_acompte, `témoin demo_admin : facturer_acompte ${J(temoin)}`).toBe(true)
    for (const cle of ['facturer_acompte', 'facturer_solde', 'facturer_complete']) {
      if (nomRole === 'Viewer') expect(gestes[cle], `Viewer : peut.${cle} ${J(gestes)}`).toBeFalsy()
      else expect(gestes[cle], `${nomRole} : peut.${cle} = témoin ${J(gestes)} / ${J(temoin)}`).toBe(temoin[cle])
    }
    await ctx.dispose()
    vus[nomRole] = { c, v }
  }
  // Écran : fiche lead → onglet Devis. Admin Ventes : aucun « Encaisser » ; Commercial : présent.
  for (const [nomRole, present] of [['Admin Ventes', false], ['Commercial', true]]) {
    const { c, v } = vus[nomRole]
    const s = await ecranSous(page, suivi, testInfo, nomRole, null, c)
    await s.p.goto(`/crm/leads/${v.lead.id}`)
    await s.p.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
    const carte = s.p.getByRole('region', { name: `Vente du devis ${v.devis.reference}` }).getByTestId(`facture-vente-${v.facture.id}`)
    await expect(carte, `${nomRole} : facture au panneau`).toBeVisible({ timeout: 60_000 })
    await expect(carte.getByRole('button', { name: 'PDF', exact: true }), `${nomRole} : PDF`).toBeVisible()
    await expect(carte.getByRole('button', { name: 'Encaisser', exact: true }), `${nomRole} : Encaisser`).toHaveCount(present ? 1 : 0)
    await s.ctx.close()
  }
})

// ── PF4.4 — ADRG18 : gestes de la liste des factures (Admin Ventes / Commercial / Viewer) ──────────────────────
etape('PF4.4-ADRG18', ['ADRG18'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  for (const nomRole of ['Admin Ventes', 'Commercial', 'Viewer']) {
    const c = await compteRole(nomRole, `adrg18${nomRole.slice(0, 2).toLowerCase()}`)
    const va = await vente(r, marque())
    const emise = await factureBc(r, va.devis, true)
    const vb = await vente(r, marque())
    const brouillon = await factureBc(r, vb.devis, false)
    expect([emise.statut, brouillon.statut], 'émise + brouillon').toEqual(['emise', 'brouillon'])
    expect(emise.reference, 'référence légale').not.toMatch(/^BROUILLON-/)
    await approprier(c.id, { lead: va.lead.id, devis: va.devis.id })
    await approprier(c.id, { lead: vb.lead.id, devis: vb.devis.id })
    const s = await ecranSous(page, suivi, testInfo, nomRole, null, c)
    // Brouillon : « Émettre » sous `encaisser`.
    await s.p.goto(`/ventes/factures?q=${encodeURIComponent(brouillon.reference)}`)
    const lb = s.p.locator(`#facture-row-${brouillon.id}`)
    await expect(lb, `${nomRole} : brouillon listé`).toBeVisible({ timeout: 90_000 })
    await expect(lb.getByRole('button', { name: /Émettre/ }), `${nomRole} : Émettre`).toHaveCount(nomRole === 'Commercial' ? 1 : 0)
    if (nomRole === 'Viewer') {
      await expect(lb.getByRole('button', { name: 'Éditer', exact: true }), 'Viewer : Éditer').toHaveCount(0)
      await expect(lb.getByRole('button', { name: /^PDF$/ }), 'Viewer : PDF').toHaveCount(0)
    }
    // Émise à référence légale : menu « Actions ».
    await s.p.goto(`/ventes/factures?q=${encodeURIComponent(emise.reference)}`)
    const le = s.p.locator(`#facture-row-${emise.id}`)
    await expect(le, `${nomRole} : émise listée`).toBeVisible({ timeout: 90_000 })
    await le.getByRole('button', { name: /Actions/ }).click()
    const menu = await entreesMenu(s.p)
    const a = (re) => menu.some((x) => re.test(x))
    if (nomRole === 'Admin Ventes') {
      expect(a(/Annuler la facture/), `Admin Ventes : Annuler la facture ${J(menu)}`).toBe(false)
      await expect(le.getByRole('button', { name: /Encaisser/ }), 'Admin Ventes : Encaisser').toHaveCount(0)
    } else if (nomRole === 'Commercial') {
      expect(a(/Marquer payée/), `Commercial : Marquer payée ${J(menu)}`).toBe(false)
      expect(a(/Note de débit/), `Commercial : Note de débit ${J(menu)}`).toBe(false)
    } else {
      for (const re of [/WhatsApp/, /UBL/, /Note de débit/, /Marquer payée/, /Annuler la facture/, /Export DGI/, /Remettre en brouillon/]) {
        expect(a(re), `Viewer : ${re} ${J(menu)}`).toBe(false)
      }
      for (const nom of [/^PDF$/, /Encaisser/, /^Avoir$/, /Payer en ligne/]) {
        await expect(le.getByRole('button', { name: nom }), `Viewer : ${nom}`).toHaveCount(0)
      }
    }
    await s.ctx.close()
  }
})

// ── PF4.1 — ADRG101 : retour en brouillon fermé après un partage WhatsApp ─────────────────────────────────────
etape('PF4.1-ADRG101', ['ADRG101'], async ({ page, suivi }) => {
  const r = page.request
  const f = await factureBc(r, (await vente(r, marque())).devis, true)
  expect(f.statut).toBe('emise')
  await page.goto(`/ventes/factures?q=${encodeURIComponent(f.reference)}`)
  const ligne = page.locator(`#facture-row-${f.id}`)
  await expect(ligne, 'facture listée').toBeVisible({ timeout: 90_000 })
  // « WhatsApp » : le lien est généré (POST whatsapp/, trace au journal de la facture), aperçu refermé.
  await ligne.getByRole('button', { name: /Actions/ }).click()
  const [wa] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && new RegExp(`/ventes/factures/${f.id}/whatsapp/$`).test(new URL(x.url()).pathname), T),
    page.getByRole('menuitem', { name: /^WhatsApp$/ }).click(),
  ])
  expect(wa.status(), `whatsapp/ : ${(await wa.text()).slice(0, 200)}`).toBe(200)
  const apercu = page.getByRole('dialog').filter({ hasText: 'Aperçu du message WhatsApp' })
  await expect(apercu).toBeVisible({ timeout: 30_000 })
  await apercu.getByRole('button', { name: 'Annuler' }).click()
  await expect(apercu).toBeHidden()
  // L'entrée « WhatsApp » garde le menu ouvert (`onSelect` + preventDefault) : on le referme comme l'utilisateur.
  if (await page.getByRole('menu').count()) {
    await page.keyboard.press('Escape')
    await expect(page.getByRole('menu')).toHaveCount(0)
  }
  // « Remettre en brouillon » ⇒ 409 « Facture déjà envoyée au client », message affiché.
  suivi.attendre(new RegExp(`/ventes/factures/${f.id}/remettre-brouillon/`), 409)
  await ligne.getByRole('button', { name: /Actions/ }).click()
  await page.getByRole('menuitem', { name: /Remettre en brouillon/ }).click()
  const [rb] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && new RegExp(`/ventes/factures/${f.id}/remettre-brouillon/$`).test(new URL(x.url()).pathname), T),
    page.getByRole('alertdialog').or(page.getByRole('dialog')).getByRole('button', { name: 'Confirmer' }).click(),
  ])
  const corps = await rb.json().catch(() => ({}))
  expect(rb.status(), `remettre-brouillon : ${J(corps)}`).toBe(409)
  expect(String(corps.detail || ''), 'motif').toContain('Facture déjà envoyée au client')
  await expect(page.getByText(/Facture déjà envoyée au client/).first(), 'message affiché').toBeVisible({ timeout: 30_000 })
  // Persistance : facture toujours émise, référence inchangée (écran rechargé + API).
  const relue = await lireFacture(r, f.id)
  expect([relue.statut, relue.reference], 'facture relue').toEqual(['emise', f.reference])
  await page.reload()
  await expect(page.locator(`#facture-row-${f.id}`), 'relue à l\'écran').toContainText(f.reference, { timeout: 90_000 })
  // Témoin : sans WhatsApp préalable, la remise en brouillon passe toujours (200).
  const g = await factureBc(r, (await vente(r, marque())).devis, true)
  const ok = await r.post(`${API}/ventes/factures/${g.id}/remettre-brouillon/`, { ...T, data: {} })
  expect(ok.status(), `témoin sans WhatsApp : ${(await ok.text()).slice(0, 200)}`).toBe(200)
  expect((await lireFacture(r, g.id)).statut, 'témoin repassé brouillon').toBe('brouillon')
})

// ── PF4.1 — ADRG4 : supprimer un objet autonome du CRM exige `crm_supprimer` ; « Retirer » des appareils ─────────
etape('PF4.1-ADRG4', ['ADRG4'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const defi = () => py(`from apps.crm.models_clients import Defi, ObjectifCommercial
d = Defi.objects.create(company_id=${SOC}, nom=${J(`Défi ADRG4 ${m}`)}, periode_debut=datetime.date.today(), periode_fin=datetime.date.today() + datetime.timedelta(days=30), metrique=ObjectifCommercial.Metric.choices[0][0])
sortie(d.id)`)
  const existe = (id) => py(`from apps.crm.models_clients import Defi
sortie(Defi.objects.filter(pk=${id}).exists())`)
  const id1 = await defi()
  for (const [nomRole, prefixe] of [['Commercial', 'adrg4co'], ['Responsable', 'adrg4re']]) {
    const s = await apiSous(testInfo, nomRole, prefixe)
    const x = await s.ctx.delete(`${API}/crm/defis/${id1}/`, T)
    expect(x.status(), `${nomRole} DELETE défi : ${(await x.text()).slice(0, 300)}`).toBe(403)
    expect(await existe(id1), `${nomRole} : défi toujours là`).toBe(true)
    await s.ctx.dispose()
  }
  const cr = await apiSous(testInfo, 'Commercial responsable', 'adrg4cr')
  const ok = await cr.ctx.delete(`${API}/crm/defis/${id1}/`, T)
  expect(ok.status(), `Commercial responsable DELETE défi : ${(await ok.text()).slice(0, 300)}`).toBe(204)
  expect(await existe(id1), 'défi supprimé').toBe(false)
  // Écran CRM → Visiteurs, carte « Appareils équipe » : « Retirer » pour le Commercial responsable, pas pour le Responsable.
  const libelle = `Poste ADRG4 ${m}`
  const app = await lireJson(await page.request.post(`${API}/crm/appareils-equipe/`, { ...T, data: { appareil_id: `adrg4-${m}-appareil`, libelle } }), 'appareil équipe')
  try {
    for (const [nomRole, prefixe, retirer, existant] of [['Commercial responsable', null, true, cr], ['Responsable', 'adrg4re2', false, null]]) {
      const s = await ecranSous(page, suivi, testInfo, nomRole, prefixe, existant)
      await s.p.goto('/crm/visiteurs')
      const ligne = s.p.getByRole('row').filter({ hasText: libelle })
      await expect(ligne, `${nomRole} : appareil équipe listé`).toBeVisible({ timeout: 60_000 })
      await expect(ligne.getByRole('button', { name: 'Retirer', exact: true }), `${nomRole} : Retirer`).toHaveCount(retirer ? 1 : 0)
      await s.ctx.close()
    }
  } finally {
    await page.request.delete(`${API}/crm/appareils-equipe/${app.id}/`, T).catch(() => null)
    await cr.ctx.dispose()
  }
})

// ── PF4.4 — ADRG20 : fiche et liste des leads (Commercial : pas de réaffectation ; Viewer : rien d'écrit) ────────
etape('PF4.4-ADRG20', ['ADRG20'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  for (const [nomRole, prefixe] of [['Commercial', 'adrg20co'], ['Viewer', 'adrg20vi']]) {
    const c = await compteRole(nomRole, prefixe)
    const m = marque()
    const leads = []
    for (const k of ['a', 'b']) {
      const l = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG20 ${m}${k}`, ville: 'Casablanca', telephone: telephoneMobileUnique() } }), 'lead')
      await approprier(c.id, { lead: l.id })
      leads.push(l)
    }
    const s = await ecranSous(page, suivi, testInfo, nomRole, null, c)
    const ecrit = nomRole === 'Commercial'
    // Fiche : sélecteur « Responsable » inerte (aucun choix ouvrable) ; menu ⋯ : écriture selon crm_modifier.
    await s.p.goto(`/crm/leads/${leads[0].id}`)
    const picker = s.p.locator('.lw-rail-triade .ap-trigger')
    await expect(picker, `${nomRole} : rail rendu`).toBeVisible({ timeout: 60_000 })
    await expect(picker, `${nomRole} : sélecteur « Responsable » inerte (crm_reassign absent)`).toBeDisabled()
    await s.p.getByRole('button', { name: /Plus d'actions/ }).first().click()
    const menu = s.p.getByRole('menu')
    await expect(menu).toBeVisible({ timeout: 30_000 })
    for (const nom of [/Convertir en client/, /^Archiver$/]) {
      const item = menu.getByRole('menuitem', { name: nom })
      await expect(item, `${nomRole} : ${nom}`).toHaveCount(1)
      if (ecrit) await expect(item, `${nomRole} : ${nom} actif`).not.toHaveAttribute('aria-disabled', 'true')
      else await expect(item, `${nomRole} : ${nom} inerte`).toHaveAttribute('aria-disabled', 'true')
    }
    await s.p.keyboard.press('Escape')
    // Liste : barre de masse sur deux leads.
    await s.p.goto('/crm/leads')
    await s.p.getByRole('radio', { name: 'Vue liste' }).click()
    for (const l of leads) {
      await s.p.getByRole('checkbox', { name: new RegExp(`Sélectionner .*${echapper(l.nom)}`) }).check({ timeout: 60_000 })
    }
    // Barre de masse (`BulkActionBar`, region « Actions en masse ») : « Responsable » = la réaffectation en masse.
    const barre = s.p.getByRole('region', { name: 'Actions en masse' }).first()
    await expect(barre, `${nomRole} : barre de masse`).toContainText(/2\s*sélectionnés/, { timeout: 30_000 })
    await expect(barre.getByRole('button', { name: 'Responsable', exact: true }), `${nomRole} : « Réaffecter » (Responsable)`).toHaveCount(0)
    await expect(barre.getByRole('button', { name: 'Étape', exact: true }), `${nomRole} : Étape`).toHaveCount(ecrit ? 1 : 0)
    await expect(barre.getByRole('button', { name: 'Archiver', exact: true }), `${nomRole} : Archiver`).toHaveCount(ecrit ? 1 : 0)
    await expect(barre.getByRole('button', { name: /Exporter Excel/ }), `${nomRole} : Exporter Excel (masse)`).toHaveCount(ecrit ? 1 : 0)
    // En-tête ⋯ : « Exporter Excel » sous crm_export.
    await s.p.getByRole('button', { name: "Plus d'actions", exact: true }).click()
    const entete = await entreesMenu(s.p)
    expect(entete.some((x) => /Exporter Excel/.test(x)), `${nomRole} : Exporter Excel (en-tête) ${J(entete)}`).toBe(ecrit)
    // Persistance : aucun lead réaffecté (owner relu = le compte).
    const owners = await py(`from apps.crm.models import Lead
sortie(sorted(set(Lead.objects.filter(pk__in=${J(leads.map((l) => l.id))}).values_list('owner_id', flat=True))))`)
    expect(owners, 'owner inchangé').toEqual([c.id])
    await s.ctx.close()
  }
})

// ── PF4.4 — ADRG88 : export RGPD d'un client sous `crm_export` (Commercial : bouton + export 200) ───────────────
etape('PF4.4-ADRG88', ['ADRG88'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  for (const nomRole of ['Commercial', 'Directeur']) {
    const c = await compteRole(nomRole, `adrg88${nomRole.slice(0, 2).toLowerCase()}`)
    const m = marque()
    const nom = `ADRG88 Client ${m}`
    const cli = await py(`from apps.crm.models import Client
sortie(Client.objects.create(company_id=${SOC}, nom=${J(nom)}, prenom='Essai', email=${J(`adrg88-${m}@example.invalid`)}).id)`)
    const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `Lead ${nom}`, ville: 'Casablanca', telephone: telephoneMobileUnique() } }), 'lead')
    await py(`from apps.crm.models import Lead
sortie(Lead.objects.filter(pk=${lead.id}).update(owner_id=${c.id}, client_id=${cli}))`)
    const s = await ecranSous(page, suivi, testInfo, nomRole, null, c)
    await s.p.goto('/crm')
    await s.p.getByPlaceholder('Rechercher nom, email, tél, ICE, IF, RC, CIN…').fill(nom)
    await s.p.getByRole('row').filter({ hasText: nom }).first().click({ timeout: 60_000 })
    const bouton = s.p.getByTestId('rgpd-actions').getByRole('button', { name: /Export RGPD/ })
    await expect(bouton, `${nomRole} : « Export RGPD (JSON) »`).toBeVisible({ timeout: 60_000 })
    const [rep] = await Promise.all([
      s.p.waitForResponse((x) => new RegExp(`/crm/clients/${cli}/data-export/?$`).test(new URL(x.url()).pathname), T),
      bouton.click(),
    ])
    expect(rep.status(), `${nomRole} : data-export`).toBe(200)
    await s.ctx.close()
  }
})

// Écart accepté (base FAIL) des deux étapes Paramètres : défaut ANTÉRIEUR, hors ADRG82/ADRG84, observé au run
// 43505842183 (13/11/2026) sous le Commercial responsable livré.
const ECART_PARAMETRES = {
  base: 'FAIL',
  raison: "frontend/src/pages/parametres/ParametresEntreprise.jsx (useEffect de montage, l. 365-380) charge pour tout palier "
    + "GET /installations/types-intervention/ et /installations/checklist-etapes/ (403 + console.error pour le Commercial "
    + "responsable, sans droit chantiers), et ConfidentialiteSection.jsx (DsrSection.load) lit GET /core/dsr-requests/ (403, "
    + "affiché « refus ») : lectures d'onglets voisins, sans rapport avec le menu « Vues sauvegardées » ni l'écriture des "
    + "modèles brandés / du benchmarking ; présentes avant ADRG82/ADRG84 (montage inchangé par ces tâches)",
}

// ── PF4.4 — ADRG82 : « Vues sauvegardées » des paramètres au seul palier administrateur ────────────────────────
etape('PF4.4-ADRG82', ['ADRG82'], async ({ page, suivi, testInfo }) => {
  for (const [nomRole, prefixe, admin] of [['Commercial responsable', 'adrg82cr', false], ['Directeur', 'adrg82di', true]]) {
    const s = await ecranSous(page, suivi, testInfo, nomRole, prefixe)
    await s.p.goto('/parametres')
    await s.p.waitForLoadState('networkidle')
    await expect(s.p.locator('a[href="/parametres/playbooks"]').first(), `${nomRole} : menu Paramètres rendu (Playbooks)`).toBeVisible({ timeout: 60_000 })
    await expect(s.p.locator('a[href="/parametres/vues"]'), `${nomRole} : entrée « Vues sauvegardées »`).toHaveCount(admin ? 1 : 0)
    // Persistance : après rechargement, même menu.
    await s.p.reload()
    await expect(s.p.locator('a[href="/parametres/playbooks"]').first()).toBeVisible({ timeout: 60_000 })
    await expect(s.p.locator('a[href="/parametres/vues"]'), `${nomRole} : relu`).toHaveCount(admin ? 1 : 0)
    await s.p.waitForLoadState('networkidle')
    await s.ctx.close()
  }
}, { ecart: ECART_PARAMETRES })

// ── PF4.4 — ADRG84 : modèles brandés et consentement de benchmarking sous `parametres_modifier` ────────────────
etape('PF4.4-ADRG84', ['ADRG84'], async ({ page, suivi, testInfo }) => {
  for (const [nomRole, prefixe, modif] of [['Commercial responsable', 'adrg84cr', false], ['Directeur', 'adrg84di', true]]) {
    const s = await ecranSous(page, suivi, testInfo, nomRole, prefixe)
    const [liste] = await Promise.all([
      s.p.waitForResponse((x) => /\/core\/branded-templates\/?$/.test(new URL(x.url()).pathname), T),
      s.p.goto('/parametres?onglet=modeles_brandes'),
    ])
    expect(liste.status(), `${nomRole} : liste des modèles lue`).toBe(200)
    await s.p.waitForLoadState('networkidle')
    await expect(s.p.getByRole('button', { name: /Créer le modèle/ }), `${nomRole} : « Créer le modèle »`).toHaveCount(modif ? 1 : 0)
    await s.p.goto('/parametres?onglet=confidentialite')
    const caseB = s.p.getByRole('checkbox', { name: 'Consentir au benchmarking anonymisé' })
    await expect(caseB, `${nomRole} : interrupteur de benchmarking`).toBeVisible({ timeout: 60_000 })
    await s.p.waitForLoadState('networkidle')
    if (modif) await expect(caseB, 'Directeur : actionnable').toBeEnabled({ timeout: 30_000 })
    else await expect(caseB, 'Commercial responsable : grisé').toBeDisabled()
    await s.ctx.close()
  }
}, { ecart: ECART_PARAMETRES })
