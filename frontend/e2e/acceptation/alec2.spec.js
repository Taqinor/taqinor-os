// Preuves en direct du groupe ALEC, lot 2 (audit PF6 « lecture des données sensibles », dossier
// docs/audits/2026-11-11-parcours-PF6.md ; décisions D-ALEC du 11/11 : portée du rôle, montants d'achat masqués).
// Chaque étape joue ce que LIT chaque rôle LIVRÉ (rôle système du registre `permissions_registre.py`, relu par
// son nom dans la société démo — jamais un rôle fabriqué) par la VRAIE route, sous un vrai compte connecté par
// /token/ : clé masquée, ligne absente, 403/404. Données propres créées dans le shell Django puis retirées.
// La sonde hôte du constat est rejouée quand elle s'exécute encore sur le code corrigé (`repro` attendu faux) ;
// une sonde dont les bouchons sont périmés par le correctif est NOMMÉE (annotation), jamais comptée comme preuve.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, lireJson, listeDe } from '../helpers.js'

const etape = groupe('ALEC', ['ALEC25', 'ALEC13', 'ALEC38', 'ALEC26', 'ALEC4', 'ALEC14', 'ALEC20', 'ALEC3', 'ALEC7', 'ALEC11', 'ALEC12'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const CO = `CO = U.objects.get(username='demo_admin').company_id\n`
const note = (testInfo, type, description) => {
  testInfo.annotations.push({ type, description })
  console.log(`[ALEC] ${type} : ${description}`)
}

/** Rejoue une sonde HÔTE du dossier (`docs/audits/sondes/ALEC/<c>.py`) ; renvoie {ok, res|err}. */
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'ALEC', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}
/** Sonde qui s'exécute encore : `repro` doit être faux. */
function sondeCorrigee(constat) {
  const s = sondeHote(constat)
  expect(s.ok, `sonde ${constat} exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, `sonde ${constat} : repro`).toBe(false)
}
/** Sonde dont les bouchons ne suivent plus le code corrigé : nommée, jamais comptée. */
function sondePerimee(testInfo, constat, pourquoi) {
  const s = sondeHote(constat)
  note(testInfo, 'sonde périmée (non comptée)', `${constat} — ${pourquoi} ; observé : ${s.ok ? `repro=${s.res.repro}` : s.err}`)
}

/** Compte d'essai du rôle LIVRÉ `nomRole` de la société démo, connecté par /token/ ; {ctx, id, nom}. */
async function session(testInfo, nom, nomRole) {
  const id = await py(`${CO}from apps.roles.models import Role
u = compte(${JSON.stringify(nom)}, role=Role.objects.get(company_id=CO, nom=${JSON.stringify(nomRole)}).pk, societe=CO)
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return { ctx, id, nom }
}
const fermer = async (...sessions) => { for (const s of sessions) await s?.ctx?.dispose().catch(() => undefined) }

/** Écran sous le compte `nom` : contexte navigateur neuf (accueil déjà vu, SW bloqué), observé par le suivi. */
async function ecranDe(page, testInfo, suivi, nom) {
  const ctx = await page.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block' })
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1'); localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  return { ctx, p: suivi.surveiller(await ctx.newPage()) }
}

/** Toutes les lignes d'une liste DRF (paginée ou non), page par page. */
async function toutes(ctx, url) {
  const lignes = []
  for (let n = 1; n < 500; n += 1) {
    const corps = await lireJson(await ctx.get(`${url}${url.includes('?') ? '&' : '?'}page=${n}&page_size=200`, T), `${url} page ${n}`)
    lignes.push(...listeDe(corps))
    if (Array.isArray(corps) || !corps.next) break
  }
  return lignes
}
const ids = (lignes) => lignes.map((x) => x.id)

// ── ALEC25 — lignes de factures bornées à la portée du rôle (deux routes) ─────────────────────────────────
etape('P1.25', ['ALEC25'], async ({ testInfo }) => {
  sondeCorrigee('C-ALEC-021')
  const m = marque()
  const a = await session(testInfo, `alec25a_${m}`, 'Commercial')
  const b = await session(testInfo, `alec25b_${m}`, 'Commercial')
  const cr = await session(testInfo, `alec25cr_${m}`, 'Commercial responsable')
  const di = await session(testInfo, `alec25di_${m}`, 'Directeur')
  const fx = await py(`${CO}from decimal import Decimal
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture
b = U.objects.get(pk=${b.id})
cl = Client.objects.create(company_id=CO, nom='ALEC25 Client ${m}', created_by=b)
p = Produit.objects.create(company_id=CO, nom='Kit ALEC25 ${m}', sku='ALEC25-${m}', prix_vente=Decimal('1000'), quantite_stock=0)
f = Facture.objects.create(company_id=CO, reference='BROUILLON-ALEC25-${m}', client=cl, statut=Facture.Statut.BROUILLON, taux_tva=Decimal('20'), created_by=b)
l = LigneFacture.objects.create(facture=f, produit=p, designation='Ligne de B ${m}', quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
sortie(dict(cl=cl.pk, p=p.pk, f=f.pk, l=l.pk))`)
  try {
    const routes = [`${API}/ventes/factures-lignes/`, `${API}/facturation/factures-lignes/`]
    for (const base of routes) {
      expect(ids(await toutes(a.ctx, base)), `Commercial A : ${base} sans la ligne de B`).not.toContain(fx.l)
      expect((await a.ctx.get(`${base}${fx.l}/`, T)).status(), `Commercial A : détail ${base}`).toBe(404)
      expect((await cr.ctx.get(`${base}${fx.l}/`, T)).status(), `Commercial responsable : détail ${base}`).toBe(404)
      expect((await di.ctx.get(`${base}${fx.l}/`, T)).status(), `Directeur : détail ${base}`).toBe(200)
    }
    expect(ids(await toutes(di.ctx, routes[0])), 'Directeur : la ligne de B listée').toContain(fx.l)
    // PATCH de la ligne de B : 404 (hors portée) pour A, et pour un Commercial responsable hors de son sous-arbre.
    const pa = await a.ctx.patch(`${routes[0]}${fx.l}/`, { ...T, data: { designation: 'Pirate A' } })
    expect(pa.status(), `PATCH Commercial A : ${(await pa.text()).slice(0, 200)}`).toBe(404)
    const pc = await cr.ctx.patch(`${routes[0]}${fx.l}/`, { ...T, data: { designation: 'Pirate CR' } })
    expect(pc.status(), `PATCH Commercial responsable : ${(await pc.text()).slice(0, 200)}`).toBe(404)
    // Persistance : la ligne de B relue en base est inchangée.
    expect(await py(`from apps.ventes.models import LigneFacture
sortie(LigneFacture.objects.get(pk=${fx.l}).designation)`), 'ligne de B inchangée').toBe(`Ligne de B ${m}`)
  } finally {
    await py(`from apps.ventes.models import Facture, LigneFacture
from apps.stock.models import Produit
from apps.crm.models import Client
LigneFacture.objects.filter(pk=${fx.l}).delete(); Facture.objects.filter(pk=${fx.f}).delete()
Produit.objects.filter(pk=${fx.p}).delete(); Client.objects.filter(pk=${fx.cl}).delete()
sortie(1)`).catch(() => undefined)
    await fermer(a, b, cr, di)
  }
})

// ── ALEC13 — « Montant estimé » de la réquisition soumise : seulement aux destinataires à prix_achat_voir ────
etape('P1.13', ['ALEC13'], async ({ testInfo }) => {
  sondeCorrigee('C-ALEC-011')
  const m = marque()
  const cr = await session(testInfo, `alec13cr_${m}`, 'Commercial responsable')
  const di = await session(testInfo, `alec13di_${m}`, 'Directeur')
  const ref = `DA-ALEC13-${m}`
  // Réquisition de 1 640 DH passée à `soumise` : le VRAI post_save (signals.demande_achat_post_save) s'exécute.
  const da = await py(`${CO}from decimal import Decimal
from apps.installations.models import DemandeAchat
from apps.notifications.services import regle_de_routage_active
from apps.notifications.models import EventType
regle = regle_de_routage_active(U.objects.get(username='demo_admin').company, EventType.APPROVAL_REQUESTED)
da = DemandeAchat.objects.create(company_id=CO, reference='${ref}', objet='Onduleurs ${m}', created_by=U.objects.get(username='demo_admin'))
da.lignes.create(designation='Onduleur 5 kW', quantite=Decimal('2'), prix_estime=Decimal('820'))
da.statut = DemandeAchat.Statut.SOUMISE
da.save()
sortie(dict(pk=da.pk, regle=regle, montant=str(da.montant_estime)))`)
  try {
    note(testInfo, 'réquisition', JSON.stringify(da))
    const corps = () => py(`from apps.notifications.models import Notification
sortie({str(n.recipient_id): dict(body=n.body, differee=n.programmee_pour is not None) for n in Notification.objects.filter(recipient_id__in=[${cr.id}, ${di.id}], body__contains='${ref}')})`)
    const base = await corps()
    expect(Object.keys(base).sort(), `une notification par destinataire (règle de routage active : ${da.regle})`).toEqual([String(cr.id), String(di.id)].sort())
    const nCr = base[String(cr.id)]
    const nDi = base[String(di.id)]
    expect(nCr.body, 'Commercial responsable : référence').toContain(ref)
    expect(nCr.body, 'Commercial responsable : objet').toContain(`Onduleurs ${m}`)
    expect(nCr.body, 'Commercial responsable : sans montant').not.toContain('Montant estimé')
    expect(nCr.body, 'Commercial responsable : aucun chiffre du montant').not.toContain('1640')
    expect(nDi.body, 'Directeur : montant estimé').toMatch(/Montant estimé : 1640(\.0+)? DH\./)
    note(testInfo, 'corps relus', JSON.stringify(base))
    // La cloche : la liste in-app de chaque compte sert le même corps (si la notification n'est pas différée
    // par les heures calmes — elle l'est alors en base, livrée à l'ouverture).
    for (const [s, n] of [[cr, nCr], [di, nDi]]) {
      const liste = await toutes(s.ctx, `${API}/notifications/notifications/`)
      const vue = liste.find((x) => String(x.body || '').includes(ref))
      if (n.differee) {
        note(testInfo, 'notification différée', `${s.nom} : heures calmes, ${vue ? 'déjà listée' : 'pas encore listée'} (corps lu en base)`)
        if (vue) expect(vue.body, `${s.nom} : corps servi = base`).toBe(n.body)
      } else {
        expect(vue, `${s.nom} : notification dans la cloche`).toBeTruthy()
        expect(vue.body, `${s.nom} : corps servi = base`).toBe(n.body)
      }
    }
    // Persistance : relire Notification.body de chaque destinataire ⇒ identique.
    expect(await corps(), 'corps relus inchangés').toEqual(base)
  } finally {
    await py(`from apps.installations.models import DemandeAchat
from apps.notifications.models import Notification
Notification.objects.filter(body__contains='${ref}').delete(); DemandeAchat.objects.filter(pk=${da.pk}).delete()
sortie(1)`).catch(() => undefined)
    await fermer(cr, di)
  }
})

// ── ALEC38 — webhook entrant : secret HMAC jamais relu, jeton et URL masqués hors création/rotation ─────────
etape('P1.38', ['ALEC38'], async ({ page, testInfo, suivi }) => {
  const m = marque()
  const di = await session(testInfo, `alec38di_${m}`, 'Directeur')
  const secret = `secret-hmac-alec38-${m}`
  const nomRegle = `ALEC38 webhook ${m}`
  const regle = await lireJson(await di.ctx.post(`${API}/automation/rules/`, {
    ...T, data: { nom: nomRegle, trigger_type: 'webhook_inbound', trigger_config: {}, action_type: 'wait', action_config: {}, enabled: true },
  }), 'règle webhook')
  let hook = null
  let ecran = null
  try {
    const B = `${API}/automation/incoming-webhooks/`
    const cree = await di.ctx.post(B, { ...T, data: { rule: regle.id, hmac_secret: secret } })
    expect(cree.status(), `création : ${(await cree.text()).slice(0, 200)}`).toBe(201)
    hook = await cree.json()
    const enBase = () => py(`from apps.automation.models import IncomingWebhookTrigger
t = IncomingWebhookTrigger.objects.get(pk=${hook.id})
sortie(dict(token=t.token, secret=t.hmac_secret))`)
    const b0 = await enBase()
    expect(hook, 'création : pas de hmac_secret').not.toHaveProperty('hmac_secret')
    expect(hook.token, 'création : jeton complet, une fois').toBe(b0.token)
    expect(hook.url_path, 'création : URL complète').toContain(b0.token)
    const masque = `••••${b0.token.slice(-4)}`
    for (const [quoi, ligne] of [['liste', (await toutes(di.ctx, B)).find((x) => x.id === hook.id)], ['détail', await lireJson(await di.ctx.get(`${B}${hook.id}/`, T), 'détail')]]) {
      expect(ligne, `${quoi} : webhook présent`).toBeTruthy()
      expect(ligne, `${quoi} : pas de hmac_secret`).not.toHaveProperty('hmac_secret')
      expect(ligne.token, `${quoi} : jeton masqué`).toBe(masque)
      expect(ligne.url_path.startsWith('••••'), `${quoi} : URL masquée (${ligne.url_path})`).toBe(true)
      expect(ligne.url_path, `${quoi} : URL sans le jeton`).not.toContain(b0.token)
    }
    // Écran, compte Directeur : la liste montre une URL masquée ; une rotation affiche l'URL complète une fois.
    ecran = await ecranDe(page, testInfo, suivi, di.nom)
    const p = ecran.p
    await p.goto('/parametres?onglet=automatisations')
    const panneau = p.getByTestId('webhook-panel')
    const rangee = panneau.locator('div', { hasText: nomRegle }).filter({ has: p.getByRole('button', { name: 'Rotation du token' }) }).last()
    await expect(rangee.locator('code'), 'URL masquée à l’écran').toHaveText(/^••••/, { timeout: 60_000 })
    await expect(rangee.locator('code')).not.toContainText(b0.token)
    const rot = p.waitForResponse((r) => r.url().includes(`/incoming-webhooks/${hook.id}/rotate/`) && r.request().method() === 'POST')
    await rangee.getByRole('button', { name: 'Rotation du token' }).click()
    expect((await rot).status(), 'rotation 200').toBe(200)
    const b1 = await enBase()
    expect(b1.token, 'jeton régénéré').not.toBe(b0.token)
    const encart = panneau.getByRole('status')
    await expect(encart, 'encart « copiez-la maintenant »').toContainText('copiez-la maintenant')
    await expect(encart.locator('code'), 'URL complète, une fois').toContainText(b1.token)
    await expect(rangee.locator('code'), 'la ligne reste masquée').toHaveText(/^••••/)
    // Rechargement : l'URL complète n'est plus affichée.
    await p.reload()
    await expect(rangee.locator('code')).toHaveText(`${(await lireJson(await di.ctx.get(`${B}${hook.id}/`, T), 'relu')).url_path}`, { timeout: 60_000 })
    await expect(panneau.getByRole('status')).toHaveCount(0)
    await expect(panneau).not.toContainText(b1.token)
    // Rotation par l'API : complète dans la réponse seulement.
    const r2 = await lireJson(await di.ctx.post(`${B}${hook.id}/rotate/`, { ...T, data: {} }), 'rotation API')
    const b2 = await enBase()
    expect([r2.token, r2.url_path.includes(b2.token)], 'rotation : jeton et URL complets').toEqual([b2.token, true])
    expect(r2, 'rotation : pas de hmac_secret').not.toHaveProperty('hmac_secret')
    // Persistance : secret inchangé en base, jeton = celui de la dernière rotation (seule la réponse change).
    expect(b2.secret, 'secret HMAC inchangé en base').toBe(secret)
    expect(b1.secret, 'secret HMAC inchangé après la rotation écran').toBe(secret)
    await page.close()
  } finally {
    if (hook) await di.ctx.delete(`${API}/automation/incoming-webhooks/${hook.id}/`, T).catch(() => undefined)
    await di.ctx.delete(`${API}/automation/rules/${regle.id}/`, T).catch(() => undefined)
    await fermer(di)
  }
})

// ── ALEC26 — tournée préventive bornée à la portée du rôle ──────────────────────────────────────────────
etape('P1.26', ['ALEC26'], async ({ page, testInfo, suivi }) => {
  sondeCorrigee('C-ALEC-022')
  const m = marque()
  const a = await session(testInfo, `alec26a_${m}`, 'Commercial')
  const b = await session(testInfo, `alec26b_${m}`, 'Commercial')
  const di = await session(testInfo, `alec26di_${m}`, 'Directeur')
  const refA = `SAV-ALEC26-A-${m}`
  const refB = `SAV-ALEC26-B-${m}`
  const fx = await py(`${CO}import datetime
from decimal import Decimal
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket
ca = Client.objects.create(company_id=CO, nom='ALEC26 Client A ${m}')
cb = Client.objects.create(company_id=CO, nom='ALEC26 Client B ${m}')
ia = Installation.objects.create(company_id=CO, reference='CHT-ALEC26-A-${m}', client=ca, gps_lat=Decimal('33.589886'), gps_lng=Decimal('-7.603869'))
ib = Installation.objects.create(company_id=CO, reference='CHT-ALEC26-B-${m}', client=cb, gps_lat=Decimal('34.020882'), gps_lng=Decimal('-6.841650'))
ta = Ticket.objects.create(company_id=CO, client=ca, installation=ia, reference='${refA}', type=Ticket.Type.PREVENTIF, statut=Ticket.Statut.NOUVEAU, date_ouverture=datetime.date.today(), created_by=U.objects.get(pk=${a.id}))
tb = Ticket.objects.create(company_id=CO, client=cb, installation=ib, reference='${refB}', type=Ticket.Type.PREVENTIF, statut=Ticket.Statut.NOUVEAU, date_ouverture=datetime.date.today(), created_by=U.objects.get(pk=${b.id}))
sortie(dict(ca=ca.pk, cb=cb.pk, ia=ia.pk, ib=ib.pk, ta=ta.pk, tb=tb.pk))`)
  let ecran = null
  try {
    const URL = `${API}/sav/contrats-maintenance/tournee/`
    const tA = await lireJson(await a.ctx.get(URL, T), 'tournée A')
    expect(tA.results.map((x) => x.reference), 'Commercial A : son seul ticket').toEqual([refA])
    const brut = JSON.stringify(tA)
    for (const x of [refB, `ALEC26 Client B ${m}`, '34.020882', `CHT-ALEC26-B-${m}`]) expect(brut, `aucune clé du ticket de B (${x})`).not.toContain(x)
    const tD = await lireJson(await di.ctx.get(URL, T), 'tournée Directeur')
    const refsD = tD.results.map((x) => x.reference)
    expect(refsD, 'Directeur : ticket de A').toContain(refA)
    expect(refsD, 'Directeur : ticket de B').toContain(refB)
    // Écran, compte Commercial : l'onglet Tournée de ContratsMaintenance sans le ticket du collègue.
    ecran = await ecranDe(page, testInfo, suivi, a.nom)
    const p = ecran.p
    await p.goto('/sav/contrats')
    const charge = p.waitForResponse((r) => r.url().includes('/contrats-maintenance/tournee/'))
    await p.getByRole('radio', { name: 'Tournée' }).click()
    expect((await charge).status(), 'tournée chargée').toBe(200)
    await expect(p.getByText(refA), 'ticket de A affiché').toBeVisible({ timeout: 60_000 })
    await expect(p.getByText(refB), 'ticket de B absent').toHaveCount(0)
    await expect(p.getByText(`ALEC26 Client B ${m}`)).toHaveCount(0)
    await page.close()
  } finally {
    await py(`from apps.sav.models import Ticket
from apps.installations.models import Installation
from apps.crm.models import Client
Ticket.objects.filter(pk__in=[${fx.ta}, ${fx.tb}]).delete(); Installation.objects.filter(pk__in=[${fx.ia}, ${fx.ib}]).delete()
Client.objects.filter(pk__in=[${fx.ca}, ${fx.cb}]).delete()
sortie(1)`).catch(() => undefined)
    await fermer(a, b, di)
  }
}, { ecart: { base: 'FAIL', raison: "l'écran /sav/contrats (frontend/src/pages/sav/ContratsMaintenance.jsx:317, WIR230 du 26/08/2026) appelle GET /api/django/users/ au montage pour TOUT rôle ; réservé à users_gerer, il répond 403 au Commercial (oracles 2-3) — même défaut que ERR-SAV-TECH-USERS-403 (corrigé sur TicketsPage seulement), antérieur et hors d'ALEC26 (portée serveur de la tournée)" } })

// ── ALEC4 — liste sans cible des pièces : la note de révision d'un BCF hors palier admin ─────────────────
etape('P1.4', ['ALEC4'], async ({ testInfo }) => {
  sondePerimee(testInfo, 'C-ALEC-003', 'son bouchon Q réduit `~declarees` à ses feuilles (__invert__ = identité) : l’exclusion des cibles non déclarées n’est pas modélisée')
  const m = marque()
  const co = await session(testInfo, `alec4co_${m}`, 'Commercial')
  const di = await session(testInfo, `alec4di_${m}`, 'Directeur')
  const fx = await py(`${CO}from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from apps.crm.models import Lead
from apps.records.models import Comment
from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit
f = Fournisseur.objects.create(company_id=CO, nom='Fournisseur ALEC4 ${m}')
p = Produit.objects.create(company_id=CO, nom='Onduleur ALEC4 ${m}', sku='ALEC4-${m}', prix_vente=Decimal('300'), prix_achat=Decimal('100'))
bc = BonCommandeFournisseur.objects.create(company_id=CO, reference='BCF-ALEC4-${m}', fournisseur=f, statut=BonCommandeFournisseur.Statut.ENVOYE)
lg = bc.lignes.create(produit=p, quantite=2, prix_achat_unitaire=Decimal('100'))
lead = Lead.objects.create(company_id=CO, nom='Lead ALEC4 ${m}', owner=U.objects.get(pk=${co.id}))
nl = Comment.objects.create(company_id=CO, author=U.objects.get(pk=${di.id}), content_type=ContentType.objects.get_for_model(Lead), object_id=lead.pk, body='Rappeler mardi ${m}')
sortie(dict(f=f.pk, p=p.pk, bc=bc.pk, lg=lg.pk, lead=lead.pk, nl=nl.pk))`)
  try {
    // Révision du BCF par le Directeur (VRAIE route `reviser` → reviser_bcf → note « prix_achat_unitaire : 100 → 120 »).
    await lireJson(await di.ctx.post(`${API}/stock/bons-commande-fournisseur/${fx.bc}/reviser/`, {
      ...T, data: { lignes: [{ id: fx.lg, quantite: 2, prix_achat_unitaire: '120.00' }] },
    }), 'révision BCF')
    const nb = await py(`from django.contrib.contenttypes.models import ContentType
from apps.records.models import Comment
from apps.stock.models import BonCommandeFournisseur
c = Comment.objects.filter(content_type=ContentType.objects.get_for_model(BonCommandeFournisseur), object_id=${fx.bc}).order_by('-pk').first()
sortie(dict(pk=c.pk, body=c.body, ct=c.content_type.app_label + '.' + c.content_type.model) if c else None)`)
    expect(nb, 'note de révision écrite').toBeTruthy()
    expect(nb.body, 'la note porte le prix d’achat').toMatch(/prix_achat_unitaire : .*100.*→.*120/)
    note(testInfo, 'note BCF', JSON.stringify(nb))
    const URL = `${API}/records/comments/`
    const lco = ids(await toutes(co.ctx, URL))
    expect(lco, 'Commercial : note BCF absente de la liste').not.toContain(nb.pk)
    expect(lco, 'Commercial : commentaire de son lead toujours listé').toContain(fx.nl)
    expect((await co.ctx.get(`${URL}${nb.pk}/`, T)).status(), 'Commercial : 404 au détail').toBe(404)
    const ldi = ids(await toutes(di.ctx, URL))
    expect(ldi, 'Directeur : note BCF listée').toContain(nb.pk)
    expect(ldi, 'Directeur : commentaire de lead listé').toContain(fx.nl)
  } finally {
    await py(`from django.contrib.contenttypes.models import ContentType
from apps.records.models import Comment
from apps.crm.models import Lead
from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit
Comment.objects.filter(content_type=ContentType.objects.get_for_model(BonCommandeFournisseur), object_id=${fx.bc}).delete()
Comment.objects.filter(pk=${fx.nl}).delete(); Lead.objects.filter(pk=${fx.lead}).delete()
BonCommandeFournisseur.objects.filter(pk=${fx.bc}).delete(); Produit.objects.filter(pk=${fx.p}).delete(); Fournisseur.objects.filter(pk=${fx.f}).delete()
sortie(1)`).catch(() => undefined)
    await fermer(co, di)
  }
})

// ── ALEC14 — historique d'un objet sans marge ni coût d'achat pour un lecteur sans le droit ──────────────
etape('P1.14', ['ALEC14'], async ({ page, testInfo, suivi }) => {
  sondePerimee(testInfo, 'C-ALEC-012', 'elle compile `get_detail` hors de son module : le nouvel appel `champs_caches` y est indéfini')
  const m = marque()
  const c1 = await session(testInfo, `alec14c1_${m}`, 'Commercial')
  const di = await session(testInfo, `alec14di_${m}`, 'Directeur')
  const COUT = '8471.00'
  const fx = await py(`${CO}import datetime
from decimal import Decimal
from apps.crm.models import Client
from apps.sav.models import Ticket
from apps.ventes.models import Devis
c1 = U.objects.get(pk=${c1.id})
cl = Client.objects.create(company_id=CO, nom='ALEC14 Client ${m}', created_by=c1)
d = Devis.objects.create(company_id=CO, reference='DEV-ALEC14-${m}', client=cl, created_by=c1)
t = Ticket.objects.create(company_id=CO, client=cl, reference='SAV-ALEC14-${m}', type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.NOUVEAU, date_ouverture=datetime.date.today(), created_by=c1, description='Panne ALEC14 ${m}')
sortie(dict(cl=cl.pk, d=d.pk, t=t.pk))`)
  let ecran = null
  try {
    // Ticket : une modification visible par la VRAIE route (journal générique, en requête). `Ticket.cout` n'est écrit
    // par aucune route (lecture seule au PATCH, ASEC34) : ses lignes sont écrites au format du journal générique.
    await lireJson(await di.ctx.patch(`${API}/sav/tickets/${fx.t}/`, { ...T, data: { description: `Panne ALEC14 ${m} — diagnostic fait` } }), 'ticket : description')
    // Devis : statut puis marge figée (4 000) — lignes écrites au format du journal générique (le geste prouvé est
    // la LECTURE ; le ticket ci-dessus, lui, est journalisé par la vraie route).
    const journal = await py(`${CO}from django.contrib.contenttypes.models import ContentType
from apps.audit.models import AuditLog
from apps.sav.models import Ticket
from apps.ventes.models import Devis
ctd = ContentType.objects.get_for_model(Devis); ctt = ContentType.objects.get_for_model(Ticket)
for changes in ([{'field': 'statut', 'old': 'brouillon', 'new': 'envoye'}, {'field': 'marge_snapshot', 'old': None, 'new': '4000.00'}],
                [{'field': 'marge_snapshot', 'old': '4000.00', 'new': '4100.00'}]):
    AuditLog.objects.create(company_id=CO, action=AuditLog.Action.UPDATE, content_type=ctd, object_id=str(${fx.d}), changes=changes)
for changes in ([{'field': 'cout', 'old': None, 'new': '${COUT}'}],
                [{'field': 'priorite', 'old': 'normale', 'new': 'haute'}, {'field': 'cout', 'old': '${COUT}', 'new': '8472.00'}]):
    AuditLog.objects.create(company_id=CO, action=AuditLog.Action.UPDATE, content_type=ctt, object_id=str(${fx.t}), changes=changes)
sortie(dict(ticket=[l.changes for l in AuditLog.objects.filter(content_type=ctt, object_id=str(${fx.t}))]))`)
    note(testInfo, 'journal du ticket', JSON.stringify(journal.ticket))
    expect(JSON.stringify(journal.ticket), 'la description modifiée par la route est journalisée').toContain('diagnostic fait')
    const H = (ct, id) => `${API}/audit/objets/${ct}/${id}/history/`
    // Devis : C1 (créateur, sans marge_voir) ne lit aucune marge ; la ligne qui n'avait qu'elle disparaît.
    const hc = await c1.ctx.get(H('ventes.devis', fx.d), T)
    expect(hc.status(), 'C1 : historique du devis 200').toBe(200)
    const dc = await hc.json()
    expect(dc.count, 'C1 : une seule ligne (statut)').toBe(1)
    expect(dc.results[0].detail, 'C1 : la ligne du statut').toMatch(/envoy/i)
    expect(JSON.stringify(dc), 'C1 : aucune marge').not.toMatch(/4000|4100|marge/i)
    const dd = await lireJson(await di.ctx.get(H('ventes.devis', fx.d), T), 'Directeur : historique du devis')
    expect(dd.count, 'Directeur : deux lignes').toBe(2)
    expect(JSON.stringify(dd), 'Directeur : « Marge HT figée … : — → 4000.00 »').toMatch(/Marge HT fig.*— → 4000\.00/)
    // Ticket : C1 ne lit pas le coût ; le Directeur le lit.
    const tc = await lireJson(await c1.ctx.get(H('sav.ticket', fx.t), T), 'C1 : historique du ticket')
    expect(JSON.stringify(tc), 'C1 : pas de coût').not.toMatch(/847[12]/)
    expect(tc.count, 'C1 : la ligne « coût seul » disparaît, la ligne mixte reste').toBe(journal.ticket.length - 1)
    expect(JSON.stringify(tc), 'C1 : la partie visible de la ligne mixte').toContain('haute')
    expect(JSON.stringify(tc), 'C1 : la modification visible reste').toContain('diagnostic fait')
    expect(JSON.stringify(await lireJson(await di.ctx.get(H('sav.ticket', fx.t), T), 'Directeur : historique du ticket')), 'Directeur : coût').toContain('8471')
    // Écran Tickets → Historique, compte Commercial : pas de coût.
    ecran = await ecranDe(page, testInfo, suivi, c1.nom)
    const p = ecran.p
    await p.goto(`/sav?id=${fx.t}`)
    const histo = p.waitForResponse((r) => r.url().includes(`/audit/objets/sav.ticket/${fx.t}/history/`))
    await p.getByRole('button', { name: 'Historique des modifications' }).click()
    expect((await histo).status(), 'historique chargé à l’écran').toBe(200)
    const dlg = p.getByRole('dialog', { name: 'Historique', exact: true })
    await expect(dlg, 'la modification visible affichée').toContainText('diagnostic fait', { timeout: 60_000 })
    await expect(dlg, 'aucun coût affiché').not.toContainText('8471')
    await page.close()
  } finally {
    await py(`from django.contrib.contenttypes.models import ContentType
from apps.audit.models import AuditLog
from apps.sav.models import Ticket
from apps.ventes.models import Devis
from apps.crm.models import Client
Ticket.objects.filter(pk=${fx.t}).delete(); Devis.objects.filter(pk=${fx.d}).delete(); Client.objects.filter(pk=${fx.cl}).delete()
sortie(1)`).catch(() => undefined)
    await fermer(c1, di)
  }
})

// ── ALEC20 — répertoire des tiers borné au droit et à la portée, coordonnées masquées sans client_pii_voir ────
etape('P1.20', ['ALEC20'], async ({ page, testInfo, suivi }) => {
  sondeCorrigee('C-ALEC-018')
  const m = marque()
  const c1 = await session(testInfo, `alec20c1_${m}`, 'Commercial')
  const c2 = await session(testInfo, `alec20c2_${m}`, 'Commercial')
  const rh = await session(testInfo, `alec20rh_${m}`, 'Admin RH')
  const di = await session(testInfo, `alec20di_${m}`, 'Directeur')
  const cin = `AL${m.slice(-6).toUpperCase()}`
  // Client de C2 miroité en tiers (le VRAI pont crm → tiers, post_save), fournisseur miroité, partenaire.
  const fx = await py(`${CO}from apps.crm.models import Client
from apps.stock.models import Fournisseur
from apps.tiers.models import Tiers
cl = Client.objects.create(company_id=CO, nom='ALEC20 Client ${m}', created_by=U.objects.get(pk=${c2.id}), cin='${cin}', telephone='0661234567')
cl.refresh_from_db()
f = Fournisseur.objects.create(company_id=CO, nom='ALEC20 Fournisseur ${m}')
tf = Tiers.objects.filter(company_id=CO, nom='ALEC20 Fournisseur ${m}', is_fournisseur=True).first()
pa = Tiers.objects.create(company_id=CO, nom='ALEC20 Partenaire ${m}', is_partenaire=True, telephone='0662000000', cin='CD${m.slice(-5)}')
sortie(dict(cl=cl.pk, tc=cl.tiers_id, f=f.pk, tf=tf.pk if tf else None, pa=pa.pk))`)
  let ecran = null
  try {
    expect(fx.tc, 'client miroité en tiers').toBeTruthy()
    expect(fx.tf, 'fournisseur miroité en tiers').toBeTruthy()
    const URL = `${API}/tiers/tiers/`
    const l1 = ids(await toutes(c1.ctx, URL))
    expect(l1, 'Commercial C1 : tiers client absent').not.toContain(fx.tc)
    expect(l1, 'Commercial C1 : fournisseur présent').toContain(fx.tf)
    expect((await c1.ctx.get(`${URL}${fx.tc}/`, T)).status(), 'Commercial C1 : 404 au détail du client').toBe(404)
    const lrh = await toutes(rh.ctx, URL)
    expect(ids(lrh), 'Admin RH : ni tiers client').not.toContain(fx.tc)
    expect(ids(lrh), 'Admin RH : ni fournisseur').not.toContain(fx.tf)
    const prh = lrh.find((x) => x.id === fx.pa)
    expect(prh, 'Admin RH : partenaire servi').toBeTruthy()
    for (const cle of ['telephone', 'whatsapp', 'email', 'adresse', 'gps_lat', 'gps_lng', 'cin', 'rib']) expect(prh, `Admin RH : sans ${cle}`).not.toHaveProperty(cle)
    const ldi = await toutes(di.ctx, URL)
    for (const id of [fx.tc, fx.tf, fx.pa]) expect(ids(ldi), `Directeur : tiers ${id}`).toContain(id)
    expect(ldi.find((x) => x.id === fx.tc).cin, 'Directeur : coordonnées comprises').toBe(cin)
    // Écran `/tiers` en Commercial : aucun tiers client chargé ni affiché.
    ecran = await ecranDe(page, testInfo, suivi, c1.nom)
    const p = ecran.p
    const servis = []
    p.on('response', async (r) => {
      if (r.url().includes('/api/django/tiers/tiers/') && r.request().method() === 'GET' && r.ok()) {
        servis.push(r.json().then((c) => listeDe(c)).catch(() => []))
      }
    })
    await p.goto('/tiers')
    await expect(p.getByText('Nom / Raison sociale').first(), 'page Tiers affichée').toBeVisible({ timeout: 60_000 })
    await expect.poll(() => servis.length, { timeout: 60_000 }).toBeGreaterThan(0)
    await p.waitForLoadState('networkidle')
    const vus = (await Promise.all(servis)).flat()
    expect(vus.length, 'la page charge le répertoire').toBeGreaterThan(0)
    expect(vus.filter((x) => x.is_client === true).map((x) => x.id), 'écran : aucun tiers client chargé').toEqual([])
    expect(ids(vus), 'écran : notre client absent').not.toContain(fx.tc)
    expect(ids(vus), 'écran : notre fournisseur chargé').toContain(fx.tf)
    await expect(p.getByText(`ALEC20 Client ${m}`), 'écran : client non affiché').toHaveCount(0)
    await page.close()
  } finally {
    await py(`from apps.crm.models import Client
from apps.stock.models import Fournisseur
from apps.tiers.models import Tiers
Client.objects.filter(pk=${fx.cl}).delete(); Fournisseur.objects.filter(pk=${fx.f}).delete()
Tiers.objects.filter(pk__in=[x for x in [${fx.tc ?? 'None'}, ${fx.tf ?? 'None'}, ${fx.pa}] if x]).delete()
sortie(1)`).catch(() => undefined)
    await fermer(c1, c2, rh, di)
  }
})

// ── ALEC3 — structure d'un kit : coûts sur prix_achat_voir, marge sur marge_voir ────────────────────────
etape('P1.3', ['ALEC3'], async ({ testInfo }) => {
  sondePerimee(testInfo, 'C-ALEC-002', 'elle compile `structure` hors de son module : la garde `PeutVoirPrixAchat` importée par le correctif y est indéfinie')
  const m = marque()
  const co = await session(testInfo, `alec3co_${m}`, 'Commercial')
  const te = await session(testInfo, `alec3te_${m}`, 'Technicien')
  const di = await session(testInfo, `alec3di_${m}`, 'Directeur')
  const fx = await py(`${CO}from decimal import Decimal
from apps.stock.models import KitComposant, KitProduit, Produit
p1 = Produit.objects.create(company_id=CO, nom='Panneau ALEC3 ${m}', sku='ALEC3-P-${m}', prix_vente=Decimal('150'), prix_achat=Decimal('100'), quantite_stock=4)
p2 = Produit.objects.create(company_id=CO, nom='Câble ALEC3 ${m}', sku='ALEC3-C-${m}', prix_vente=Decimal('80'), prix_achat=Decimal('50'), quantite_stock=6)
k = KitProduit.objects.create(company_id=CO, nom='Kit ALEC3 ${m}', sku='KIT-ALEC3-${m}')
KitComposant.objects.create(kit=k, produit=p1, quantite=Decimal('1')); KitComposant.objects.create(kit=k, produit=p2, quantite=Decimal('1'))
sortie(dict(k=k.pk, p=[p1.pk, p2.pk]))`)
  try {
    const URL = `${API}/stock/kits/${fx.k}/structure/`
    const dd = await lireJson(await di.ctx.get(URL, T), 'Directeur : structure')
    expect(Number(dd.cout_total_roll_up), 'Directeur : coût roll-up 150').toBe(150)
    expect(dd, 'Directeur : marge').toHaveProperty('marge')
    expect(dd.composants[0], 'Directeur : coût unitaire').toHaveProperty('cout_unitaire')
    for (const s of [co, te]) {
      const r = await s.ctx.get(URL, T)
      expect(r.status(), `${s.nom} : 200`).toBe(200)
      const d = await r.json()
      expect(d, `${s.nom} : sans cout_total_roll_up`).not.toHaveProperty('cout_total_roll_up')
      expect(d, `${s.nom} : sans marge`).not.toHaveProperty('marge')
      expect(d.composants.length, `${s.nom} : nomenclature inchangée`).toBe(2)
      for (const c of d.composants) {
        expect(c, `${s.nom} : sans cout_unitaire`).not.toHaveProperty('cout_unitaire')
        expect(c, `${s.nom} : sans cout_total`).not.toHaveProperty('cout_total')
        expect(c, `${s.nom} : disponibilité visible`).toHaveProperty('quantite_disponible')
      }
      expect(d.disponibilite_potentielle, `${s.nom} : disponibilité = Directeur`).toBe(dd.disponibilite_potentielle)
    }
  } finally {
    await py(`from apps.stock.models import KitProduit, Produit
KitProduit.objects.filter(pk=${fx.k}).delete(); Produit.objects.filter(pk__in=${JSON.stringify(fx.p)}).delete()
sortie(1)`).catch(() => undefined)
    await fermer(co, te, di)
  }
})

// ── ALEC7 — taux d'un accord RFA masqué sans prix_achat_voir, « — » à l'écran ─────────────────────────────
etape('P1.7', ['ALEC7'], async ({ page, testInfo, suivi }) => {
  sondeCorrigee('C-ALEC-005')
  const m = marque()
  const co = await session(testInfo, `alec7co_${m}`, 'Commercial')
  const di = await session(testInfo, `alec7di_${m}`, 'Directeur')
  const fx = await py(`${CO}import datetime
from decimal import Decimal
from apps.stock.models import Fournisseur
from apps.stock.models_rfa import AccordRFAFournisseur
an = datetime.date.today().year
f1 = Fournisseur.objects.create(company_id=CO, nom='RFA ALEC7 Taux ${m}')
f2 = Fournisseur.objects.create(company_id=CO, nom='RFA ALEC7 Fixe ${m}')
a1 = AccordRFAFournisseur.objects.create(company_id=CO, fournisseur=f1, periode_debut=datetime.date(an, 1, 1), periode_fin=datetime.date(an, 12, 31), seuil_ca_achat=Decimal('50000'), taux_pct=Decimal('3'))
a2 = AccordRFAFournisseur.objects.create(company_id=CO, fournisseur=f2, periode_debut=datetime.date(an, 1, 1), periode_fin=datetime.date(an, 12, 31), taux_pct=None, montant_fixe=Decimal('5000'))
sortie(dict(f=[f1.pk, f2.pk], a1=a1.pk, a2=a2.pk))`)
  let ecran = null
  try {
    const URL = `${API}/stock/accords-rfa-fournisseur/`
    const r = await co.ctx.get(URL, T)
    expect(r.status(), 'Commercial : 200').toBe(200)
    const lco = (await toutes(co.ctx, URL)).filter((x) => [fx.a1, fx.a2].includes(x.id))
    expect(lco.length, 'Commercial : les deux accords listés').toBe(2)
    const det = await lireJson(await co.ctx.get(`${URL}${fx.a1}/`, T), 'Commercial : détail')
    for (const x of [...lco, det]) for (const cle of ['taux_pct', 'seuil_ca_achat', 'montant_fixe']) expect(x, `Commercial : sans ${cle}`).not.toHaveProperty(cle)
    const ldi = Object.fromEntries((await toutes(di.ctx, URL)).map((x) => [x.id, x]))
    expect(Number(ldi[fx.a1].taux_pct), 'Directeur : 3 %').toBe(3)
    expect(Number(ldi[fx.a2].montant_fixe), 'Directeur : 5 000 fixe').toBe(5000)
    // Écran `/stock/negoce/rfa` en Commercial : « — » pour les deux accords (ni taux, ni « Montant fixe »).
    ecran = await ecranDe(page, testInfo, suivi, co.nom)
    const p = ecran.p
    await p.goto('/stock/negoce/rfa')
    for (const nom of [`RFA ALEC7 Taux ${m}`, `RFA ALEC7 Fixe ${m}`]) {
      const li = p.locator('li', { hasText: nom })
      await expect(li, `écran : accord ${nom}`).toBeVisible({ timeout: 60_000 })
      await expect(li, `écran : « — » pour ${nom}`).toContainText('—')
      await expect(li).not.toContainText('3 %')
      await expect(li).not.toContainText('Montant fixe')
      await expect(li).not.toContainText('5000')
    }
    await page.close()
  } finally {
    await py(`from apps.stock.models import Fournisseur
from apps.stock.models_rfa import AccordRFAFournisseur
AccordRFAFournisseur.objects.filter(pk__in=[${fx.a1}, ${fx.a2}]).delete(); Fournisseur.objects.filter(pk__in=${JSON.stringify(fx.f)}).delete()
sortie(1)`).catch(() => undefined)
    await fermer(co, di)
  }
})

// ── ALEC11 — cockpit entrepôt : cout_total des expéditions du jour à null sans prix_achat_voir ─────────────
etape('P1.11', ['ALEC11'], async ({ testInfo }) => {
  sondeCorrigee('C-ALEC-009')
  const m = marque()
  const co = await session(testInfo, `alec11co_${m}`, 'Commercial')
  const di = await session(testInfo, `alec11di_${m}`, 'Directeur')
  const URL = `${API}/stock/entrepot/cockpit/`
  const amana = (c) => (c.expeditions_du_jour || []).find((x) => x.transporteur === 'amana') || { nb: 0, cout_total: '0' }
  const avant = amana(await lireJson(await di.ctx.get(URL, T), 'cockpit Directeur avant'))
  // Expédition du jour (cout_reel 420) ; SSCC à clé GS1 valide, unique au run.
  const fx = await py(`${CO}from decimal import Decimal
from django.utils import timezone
from apps.stock.models_wms import ExpeditionTransporteur, UniteLogistique
corps = '3' + str(int(timezone.now().timestamp() * 1000))[-16:].rjust(16, '0')
s = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(corps)))
sscc = corps + str((10 - s % 10) % 10)
ul = UniteLogistique.objects.create(company_id=CO, type_unite=UniteLogistique.TypeUnite.PALETTE, sscc=sscc)
e = ExpeditionTransporteur.objects.create(company_id=CO, unite_logistique=ul, transporteur_provider=ExpeditionTransporteur.Provider.AMANA, cout_reel=Decimal('420'), date_expedition=timezone.now())
sortie(dict(ul=ul.pk, e=e.pk, sscc=sscc))`)
  try {
    const rc = await co.ctx.get(URL, T)
    expect(rc.status(), 'Commercial : 200').toBe(200)
    const cc = await rc.json()
    const cd = await lireJson(await di.ctx.get(URL, T), 'cockpit Directeur')
    expect(cc.expeditions_du_jour.length, 'Commercial : des expéditions du jour').toBeGreaterThan(0)
    expect(cc.expeditions_du_jour.map((x) => x.cout_total), 'Commercial : cout_total null partout').toEqual(cc.expeditions_du_jour.map(() => null))
    expect(amana(cc).nb, 'Commercial : nb inchangé (+1)').toBe(avant.nb + 1)
    expect(amana(cd).nb, 'Directeur : nb').toBe(avant.nb + 1)
    expect(Number(amana(cd).cout_total), 'Directeur : coût (+420)').toBe(Number(avant.cout_total || 0) + 420)
    expect(Object.keys(cc).sort(), 'Commercial : autres blocs servis (mêmes clés)').toEqual(Object.keys(cd).sort())
  } finally {
    await py(`from apps.stock.models_wms import ExpeditionTransporteur, UniteLogistique
ExpeditionTransporteur.objects.filter(pk=${fx.e}).delete(); UniteLogistique.objects.filter(pk=${fx.ul}).delete()
sortie(1)`).catch(() => undefined)
    await fermer(co, di)
  }
})

// ── ALEC12 — jetons du portail fournisseur : lecture et création exigent prix_achat_voir ─────────────────
etape('P1.12', ['ALEC12'], async ({ testInfo }) => {
  sondePerimee(testInfo, 'C-ALEC-010', 'elle compile `get_permissions` hors de son module : la garde `PeutVoirPrixAchat` importée par le correctif y est indéfinie')
  const m = marque()
  const av = await session(testInfo, `alec12av_${m}`, 'Admin Ventes')
  const re = await session(testInfo, `alec12re_${m}`, 'Responsable')
  const di = await session(testInfo, `alec12di_${m}`, 'Directeur')
  const fx = await py(`${CO}from apps.stock.models import Fournisseur
from apps.stock.services import generer_token_portail_fournisseur
f = Fournisseur.objects.create(company_id=CO, nom='Portail ALEC12 ${m}')
generer_token_portail_fournisseur(f.company, f, U.objects.get(username='demo_admin'))
sortie(dict(f=f.pk))`)
  const nbJetons = () => py(`from apps.stock.models import Fournisseur
sortie(Fournisseur.objects.get(pk=${fx.f}).portail_tokens.count())`)
  try {
    const URL = `${API}/stock/fournisseurs/${fx.f}/portail-tokens/`
    for (const s of [av, re]) {
      expect((await s.ctx.get(URL, T)).status(), `${s.nom} : GET 403`).toBe(403)
      expect((await s.ctx.post(URL, { ...T, data: {} })).status(), `${s.nom} : POST 403`).toBe(403)
      expect(await nbJetons(), `${s.nom} : aucun jeton créé`).toBe(1)
    }
    const l = await lireJson(await di.ctx.get(URL, T), 'Directeur : liste')
    expect(listeDe(l).length, 'Directeur : 1 jeton').toBe(1)
    const c = await di.ctx.post(URL, { ...T, data: {} })
    expect(c.status(), `Directeur : POST ${(await c.text()).slice(0, 200)}`).toBe(201)
    // Persistance : seul le Directeur a ajouté un jeton.
    expect(await nbJetons(), 'deux jetons (le second du Directeur)').toBe(2)
  } finally {
    await py(`from apps.stock.models import Fournisseur
f = Fournisseur.objects.get(pk=${fx.f}); f.portail_tokens.all().delete(); f.delete()
sortie(1)`).catch(() => undefined)
    await fermer(av, re, di)
  }
})
