// AANA90 — rejeu en direct des gestes qu'AANA74 a laissés sans enregistrement PASS (dette gelée
// `docs/audits/acceptation/AANA/_dette.yml`) : AANA71 (tarif fournisseur exact), AANA70 (migration à statut
// inconnu), AANA65 (`win_rate` de roi-sources = signés ÷ NON perdus), AANA68 (« Contrôle du suivi » : une vente par
// révision), AANA75 (« Mes équipes », objectif CA, roi-sources : la V1 en vigueur gardée), AANA76 (attribution du CA
// après révision), plus l'étape (4) d'AANA90 (`ca_ht` sans brouillon, clause d'AANA61). Chaque étape rejoue AUSSI
// ses gestes au compte de la société B (étape (5) d'AANA90) : rien de A visible depuis B.
// Société A = société de démo (celle de demo_admin) avec un directeur et un commercial d'essai créés ici ; société
// B créée ici (même patron qu'`aana3.spec.js`), un directeur et un commercial. Données posées par l'API (devis,
// acceptations, révisions, imports) ou par le shell (`py`) pour les fixtures sans écran, nettoyées en fin d'étape.
// Contre-épreuve `base_verdict` (32375fe65) : chaque assertion visée porte l'id de sa tâche entre crochets
// (« [AANA71] … ») pour que le rejeu sur la base échoue sur la clause visée, jamais sur la plomberie.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout, MDP_ESSAI } from './_django.js'
import { lireJson, listeDe, connexionApi, uiLoginJusquAuxApps, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('AANA', ['AANA65', 'AANA68', 'AANA70', 'AANA71', 'AANA75', 'AANA76', 'AANA61', 'AANA90'])
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
const m = Date.now().toString(36)
const XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
const plat = (s) => String(s).replace(/[\s\u00a0\u202f]+/g, '')
const chiffresSeuls = (s) => String(s).replace(/[^\d/]/g, '')
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

// ── Monde partagé : sociétés, comptes, contextes navigateur (une connexion par compte) ──────────────
let monde = null
const pagesOuvertes = []
const contextes = []
test.afterAll(async () => {
  for (const c of contextes.splice(0)) await c.close().catch(() => undefined)
  if (!monde) return
  // Comptes d'essai désactivés (jamais supprimés : leurs traces restent attribuées).
  await py(`U.objects.filter(username__in=${J([monde.a.dir, monde.a.com, monde.b.dir, monde.b.com])}).update(is_active=False)
sortie(1)`).catch(() => null)
})
fermerDjangoApresTout()

async function lePlateau(page, testInfo) {
  for (const p of pagesOuvertes.splice(0)) await p.close().catch(() => undefined)
  if (monde) return monde
  const s = await py(`from authentication.models import Company
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS, COMMERCIAL_PERMISSIONS
A = U.objects.get(username='demo_admin').company_id
def role_a(nom):
    r = Role.objects.filter(company_id=A, nom__iexact=nom).first()
    if r is None:
        raise RuntimeError('rôle « %s » absent de la société démo (init_roles)' % nom)
    return r
dA = compte('acc90d_${m}', role=role_a('Directeur').pk, societe=A)
dA.role_legacy = 'admin'; dA.save(update_fields=['role_legacy'])
cA = compte('acc90c_${m}', role=role_a('Commercial').pk, societe=A)
coB = Company.objects.create(slug='acc90-${m}-b', nom='ACC90 ${m} B')
rd = Role.objects.create(company=coB, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
rc = Role.objects.create(company=coB, nom='Commercial', permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
dB = compte('acc90d_${m}_b', role=rd.pk, societe=coB.pk)
dB.role_legacy = 'admin'; dB.save(update_fields=['role_legacy'])
cB = compte('acc90c_${m}_b', role=rc.pk, societe=coB.pk)
sortie(dict(a=dict(co=A, dir=dA.username, dir_id=dA.pk, com=cA.username, com_id=cA.pk),
            b=dict(co=coB.pk, dir=dB.username, dir_id=dB.pk, com=cB.username, com_id=cB.pk)))`)
  const browser = page.context().browser()
  const baseURL = testInfo.project.use.baseURL
  const compteNav = (username) => ({ username, ctx: null, async contexte() {
    if (this.ctx) return this.ctx
    this.ctx = await browser.newContext({ baseURL, storageState: { cookies: [], origins: [] } })
    contextes.push(this.ctx)
    await this.ctx.addInitScript(() => {
      try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
      try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
    })
    return this.ctx
  } })
  monde = { ...s, dA: compteNav(s.a.dir), cA: compteNav(s.a.com), dB: compteNav(s.b.dir), cB: compteNav(s.b.com) }
  return monde
}

/** Page surveillée (oracles 1-4, 8) dans le contexte du compte, connecté à l'écran au premier usage. */
async function ouvrir(u, suivi) {
  const ctx = await u.contexte()
  const p = suivi.surveiller(await ctx.newPage())
  pagesOuvertes.push(p)
  if (!u.connecte) {
    await uiLoginJusquAuxApps(p, { username: u.username, password: MDP_ESSAI })
    u.connecte = true
  }
  return p
}

/** Appel API au compte `u` (cookies de son contexte) ; une session expirée est rouverte une fois. */
async function appel(u, methode, url, opts = {}) {
  const ctx = await u.contexte()
  if (!u.connecte) {
    await connexionApi(ctx.request, { username: u.username, password: MDP_ESSAI })
    u.connecte = true
  }
  let r = await ctx.request[methode](url, { ...T, ...opts })
  if (r.status() === 401) {
    await connexionApi(ctx.request, { username: u.username, password: MDP_ESSAI })
    r = await ctx.request[methode](url, { ...T, ...opts })
  }
  return r
}
const lire = async (u, url, quoi) => lireJson(await appel(u, 'get', url), quoi)

// ═══ (1) Tarif fournisseur à 12.345 + migration devis/facture à statut `won_partial` ═════════════════
etape('P1.tarif_et_migration', ['AANA71', 'AANA70', 'AANA90'], async ({ page, suivi, testInfo }) => {
  const w = await lePlateau(page, testInfo)
  const { a } = w
  const d = await py(`import base64, io
from decimal import Decimal
from openpyxl import Workbook
from apps.stock.models import Fournisseur, Produit
from apps.crm.models import Client
f = Fournisseur.objects.create(company_id=${a.co}, nom='ACC90 Fournisseur ${m}')
pa = Produit.objects.create(company_id=${a.co}, sku='ACC90-A-${m}', nom='ACC90 A ${m}', prix_vente=Decimal('100'), quantite_stock=0)
pb = Produit.objects.create(company_id=${a.co}, sku='ACC90-B-${m}', nom='ACC90 B ${m}', prix_vente=Decimal('100'), quantite_stock=0)
cl = Client.objects.create(company_id=${a.co}, nom='Cli ACC90 ${m}', prenom='X', email='cli${m}@example.invalid')
def classeur(lignes):
    wb = Workbook(); ws = wb.active
    ws.append(['sku', 'produit', 'ref_produit_fournisseur', 'prix_achat', 'date_debut', 'date_fin', 'paliers (qte_min:prix;...)'])
    for l in lignes:
        ws.append(l)
    buf = io.BytesIO(); wb.save(buf)
    return base64.b64encode(buf.getvalue()).decode()
sortie(dict(f=f.pk, pa=pa.pk, pb=pb.pk, cl=cl.pk,
    fautif=classeur([[pa.sku, 'A', '', 12.345, None, None, ''], [pb.sku, 'B', '', 10, None, None, '10:9.5;20:abc'],
                     ['', 'sans sku', '', 8, None, None, ''], [None] * 7]),
    sain=classeur([[pa.sku, 'A', '', 12.34, None, None, '10:9.5']])))`)
  const fichier = (b64, nom = 'tarif-acc90.xlsx') => ({ name: nom, mimeType: XLSX, buffer: Buffer.from(b64, 'base64') })
  const csv = (contenu) => ({ name: 'migration-acc90.csv', mimeType: 'text/csv', buffer: Buffer.from(contenu, 'utf-8') })
  const etatTarif = () => py(`from apps.stock.models import PrixFournisseur, PalierPrixFournisseur
pf = PrixFournisseur.objects.filter(fournisseur_id=${d.f})
sortie(dict(prix=[[x.produit_id, str(x.prix_achat)] for x in pf],
            paliers=[[x.prix_fournisseur.produit_id, x.qte_min, str(x.prix)] for x in PalierPrixFournisseur.objects.filter(prix_fournisseur__in=pf)]))`)
  const docsClient = () => py(`from apps.ventes.models import Devis, Facture
sortie(dict(devis=sorted(Devis.objects.filter(company_id=${a.co}, client_id=${d.cl}).values_list('statut', flat=True)),
            factures=Facture.objects.filter(company_id=${a.co}, client_id=${d.cl}).count()))`)
  try {
    // ── AANA71, API : aperçu puis import réel du fichier fautif — trois lignes nommées, rien d'écrit.
    for (const apercu of [true, false]) {
      const r = await lireJson(await appel(w.dA, 'post', `${API}/stock/prix-fournisseurs/import-xlsx/`, {
        multipart: { fournisseur: String(d.f), file: fichier(d.fautif), ...(apercu ? { apercu: 'true' } : {}) },
      }), `import tarif (aperçu=${apercu})`)
      const errs = r.errors || []
      expect(errs.map((e) => e.row), `[AANA71] lignes refusées 2, 3, 4 (aperçu=${apercu}) : ${J(errs)}`).toEqual([2, 3, 4])
      expect(errs[0].message, '[AANA71] 12.345 refusé, pas arrondi').toContain('plus de 2 décimales')
      expect(errs[1].message, '[AANA71] palier « 20:abc » rapporté').toContain('« 20:abc »')
      expect(errs[2].message, '[AANA71] prix sans SKU rapporté').toContain('SKU manquant')
      expect(r.created, `[AANA71] rien de créé (aperçu=${apercu})`).toBe(0)
    }
    // Persistance : relu par l'API et en base (deux fois) — aucun tarif ni palier, surtout pas 12.35.
    for (let i = 0; i < 2; i++) {
      for (const pid of [d.pa, d.pb]) {
        const l = listeDe(await lire(w.dA, `${API}/stock/prix-fournisseurs/?produit=${pid}`, 'tarifs relus'))
        expect(l.map((x) => x.prix_achat), `[AANA71] aucun tarif écrit pour le produit ${pid}`).toEqual([])
      }
      expect(await etatTarif(), '[AANA71] base : rien d\'écrit').toEqual({ prix: [], paliers: [] })
    }
    // ── AANA71, écran : fiche fournisseur 360 → onglet Tarif → aperçu puis import, les trois lignes nommées.
    const pd = await ouvrir(w.dA, suivi)
    await pd.goto(`/stock/fournisseurs/${d.f}/360`)
    await pd.getByRole('tab', { name: 'Tarif', exact: true }).click()
    const onglet = pd.getByTestId('f360-tab-tarif')
    await onglet.locator('input[type="file"]').setInputFiles(fichier(d.fautif))
    await onglet.getByRole('button', { name: 'Aperçu', exact: true }).click()
    const refus = onglet.getByTestId('tarif-lignes-refusees')
    await expect(refus, '[AANA71] écran : lignes refusées à l\'aperçu').toBeVisible({ timeout: 60_000 })
    const lis = refus.locator('li')
    await expect(lis).toHaveCount(3)
    await expect(lis.nth(0)).toContainText('Ligne 2 :')
    await expect(lis.nth(0)).toContainText('plus de 2 décimales')
    await expect(lis.nth(1)).toContainText('Ligne 3 :')
    await expect(lis.nth(1)).toContainText('« 20:abc »')
    await expect(lis.nth(2)).toContainText('Ligne 4 :')
    await expect(lis.nth(2)).toContainText('SKU manquant')
    await onglet.getByRole('button', { name: 'Importer', exact: true }).click()
    await expect(onglet.getByText(/Import effectué : 0 création\(s\), 0 mise\(s\) à jour, 3 ligne\(s\) refusée\(s\)\./))
      .toBeVisible({ timeout: 60_000 })
    await expect(onglet.getByTestId('tarif-lignes-refusees').locator('li')).toHaveCount(3)
    await pd.reload({ waitUntil: 'domcontentloaded' })
    await expect(pd.getByRole('tab', { name: 'Tarif', exact: true })).toBeVisible({ timeout: 60_000 })
    expect(await etatTarif(), '[AANA71] après l\'import à l\'écran et rechargement : rien d\'écrit').toEqual({ prix: [], paliers: [] })
    // Un fichier sain se comporte comme avant : 12.34 et le palier 10:9.5 écrits EXACTS.
    const sain = await lireJson(await appel(w.dA, 'post', `${API}/stock/prix-fournisseurs/import-xlsx/`, {
      multipart: { fournisseur: String(d.f), file: fichier(d.sain) },
    }), 'import tarif sain')
    expect([sain.created, sain.errors], `fichier sain : 1 création, 0 erreur (${J(sain)})`).toEqual([1, []])
    const relu = listeDe(await lire(w.dA, `${API}/stock/prix-fournisseurs/?produit=${d.pa}`, 'tarif sain relu'))
    expect(relu.map((x) => x.prix_achat), 'fichier sain : 12.34 exact').toEqual(['12.34'])
    expect(await etatTarif(), 'fichier sain : tarif et palier exacts en base').toEqual({ prix: [[d.pa, '12.34']], paliers: [[d.pa, 10, '9.50']] })

    // ── AANA70 : migration devis (won_partial + vide) et factures (won_partial).
    const avant = await docsClient()
    expect(avant, 'témoin : aucun document pour ce client').toEqual({ devis: [], factures: 0 })
    const md = await lireJson(await appel(w.dA, 'post', `${API}/imports/commit/`, {
      multipart: { target: 'devis', file: csv(`reference,client_nom,statut\nACC90-DW-${m},Cli ACC90 ${m},won_partial\nACC90-DV-${m},Cli ACC90 ${m},\n`) },
    }), 'migration devis')
    expect((md.skipped || []).map((x) => x.ligne), `[AANA70] devis : la ligne won_partial (1) refusée (${J(md.skipped)})`).toEqual([1])
    expect(md.skipped[0].raison, '[AANA70] motif nommant la valeur').toMatch(/statut source non reconnu.*won_partial/)
    expect(md.created, '[AANA70] seule la ligne sans statut est créée (vide = brouillon)').toBe(1)
    const mf = await lireJson(await appel(w.dA, 'post', `${API}/imports/commit/`, {
      multipart: { target: 'factures', file: csv(`reference,client_nom,statut\nACC90-FW-${m},Cli ACC90 ${m},won_partial\n`) },
    }), 'migration factures')
    expect((mf.skipped || []).map((x) => x.ligne), `[AANA70] facture won_partial refusée (${J(mf.skipped)})`).toEqual([1])
    expect(mf.skipped[0].raison, '[AANA70] motif nommant la valeur').toMatch(/statut source non reconnu.*won_partial/)
    expect(mf.created, '[AANA70] aucune facture créée').toBe(0)
    for (let i = 0; i < 2; i++) {
      expect(await docsClient(), '[AANA70] relu : un seul devis (brouillon, ligne vide), aucune facture').toEqual({ devis: ['brouillon'], factures: 0 })
    }

    // ── (5) Société B : mêmes gestes, rien de A.
    const rb = await appel(w.dB, 'post', `${API}/stock/prix-fournisseurs/import-xlsx/`, {
      multipart: { fournisseur: String(d.f), file: fichier(d.sain) },
    })
    expect(rb.status(), 'B : le fournisseur de A est introuvable (404)').toBe(404)
    expect((await appel(w.dB, 'get', `${API}/stock/fournisseurs/${d.f}/`)).status(), 'B : fiche fournisseur de A → 404').toBe(404)
    const tb = listeDe(await lire(w.dB, `${API}/stock/prix-fournisseurs/?produit=${d.pa}`, 'tarifs B'))
    expect(tb, 'B : aucun tarif de A').toEqual([])
    const mb = await lireJson(await appel(w.dB, 'post', `${API}/imports/commit/`, {
      multipart: { target: 'devis', file: csv(`reference,client_nom,statut\nACC90-DB-${m},Cli ACC90 ${m},brouillon\n`) },
    }), 'migration devis B')
    expect(mb.created, 'B : le client de A n\'est pas résolu').toBe(0)
    expect(J(mb.skipped), 'B : client introuvable').toContain('client introuvable')
    expect(await docsClient(), 'B n\'a rien écrit chez A').toEqual({ devis: ['brouillon'], factures: 0 })
    expect(await py(`from apps.ventes.models import Devis
sortie(Devis.objects.filter(company_id=${w.b.co}).count())`), 'B : aucun devis créé').toBe(0)
    suivi.verifie(9)
    await page.close() // la capture de l'étape = la fiche fournisseur
  } finally {
    await py(`from apps.stock.models import Fournisseur, Produit, PrixFournisseur, PalierPrixFournisseur
from apps.ventes.models import Devis
from apps.crm.models import Client
PalierPrixFournisseur.objects.filter(prix_fournisseur__fournisseur_id=${d.f}).delete()
PrixFournisseur.objects.filter(fournisseur_id=${d.f}).delete()
for qs in (Devis.objects.filter(company_id=${a.co}, client_id=${d.cl}), Produit.objects.filter(pk__in=[${d.pa}, ${d.pb}]),
           Fournisseur.objects.filter(pk=${d.f}), Client.objects.filter(pk=${d.cl})):
    try:
        qs.delete()
    except Exception as e:
        print('nettoyage incomplet :', e)
sortie(1)`).catch(() => null)
  }
})

// ═══ (2) win_rate de roi-sources = signés ÷ NON perdus (règle de taux_gain), accueil et « Mes chiffres » ═══
etape('P2.taux_de_gain', ['AANA65', 'AANA90'], async ({ page, suivi, testInfo }) => {
  const w = await lePlateau(page, testInfo)
  const { a } = w
  const c2 = `acc90-${m}-roi`
  const c2p = `acc90-${m}-perdu`
  const c2v = `acc90-${m}-vente`
  const tels = [1, 2, 3, 4, 5, 6].map(() => telephoneMobileUnique())
  const ids = await py(`from apps.crm.models import Lead
from apps.crm import stages as S
def lead(i, nom, camp, stage, perdu=False):
    return Lead.objects.create(company_id=${a.co}, nom=nom, telephone=${J(tels)}[i], email='acc90r%d${m}@example.invalid' % i,
        owner_id=${a.com_id}, canal='site_web', utm_campaign=camp, stage=stage, perdu=perdu).pk
sortie([lead(0, 'ACC90 signe ${m}', '${c2}', S.SIGNED), lead(1, 'ACC90 perdu ${m}', '${c2}', S.COLD, True),
        lead(2, 'ACC90 ouvert ${m}', '${c2}', S.NEW), lead(3, 'ACC90 tout perdu ${m}', '${c2p}', S.COLD, True),
        lead(4, 'ACC90 envoye ${m}', '${c2v}', S.NEW), lead(5, 'ACC90 accepte ${m}', '${c2v}', S.NEW)])`)
  // « Mes chiffres » du commercial : deux devis du mois À SON NOM (un envoyé, un envoyé puis accepté), sur une campagne à
  // part (hors des groupes roi-sources ci-dessus), pour que « affiché = servi » se prouve sur des effectifs NON nuls.
  const produit = await py(`from decimal import Decimal
from apps.stock.models import Produit
sortie(Produit.objects.create(company_id=${a.co}, sku='ACC90-MC-${m}', nom='Kit ACC90 MC ${m}', prix_vente=Decimal('1000'), quantite_stock=0).pk)`)
  const devisMc = []
  try {
    for (const [lead, accepte] of [[ids[4], false], [ids[5], true]]) {
      const dv = await lireJson(await appel(w.dA, 'post', `${API}/ventes/devis/atomic/`, { data: { taux_tva: '20.00', remise_globale: '0', lead,
        lignes: [{ produit, designation: 'Kit ACC90 MC', quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), `devis « Mes chiffres » du lead ${lead}`)
      devisMc.push(dv.id)
      await lireJson(await appel(w.dA, 'post', `${API}/ventes/devis/${dv.id}/share-link/`, { data: { envoi: true } }), `envoi ${dv.id}`)
      if (accepte) await lireJson(await appel(w.dA, 'post', `${API}/ventes/devis/${dv.id}/accepter/`, { data: { nom: 'Client ACC90 MC' } }), `acceptation ${dv.id}`)
    }
    await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk__in=${J(devisMc)}).update(created_by_id=${a.com_id})
sortie(1)`)
    const caSigneMc = Number((await lire(w.dA, `${API}/ventes/devis/${devisMc[1]}/`, 'devis accepté relu')).total_ttc)
    const ligne = (rows, camp) => (rows || []).find((r) => r.utm_campaign === camp)
    // ── API, directeur puis commercial de A (deux portées) : 1 signé, 1 perdu, 1 ouvert ⇒ 50.0 ; tout perdu ⇒ null.
    for (const [u, qui] of [[w.dA, 'directeur'], [w.cA, 'commercial']]) {
      for (let i = 0; i < 2; i++) {
        const rows = await lire(u, `${API}/crm/leads/roi-sources/`, `roi-sources (${qui})`)
        const g = ligne(rows, c2)
        expect(g, `roi-sources (${qui}) : groupe ${c2} servi`).toBeTruthy()
        expect([g.lead_count, g.signed_count], `roi-sources (${qui}) : effectifs inchangés`).toEqual([3, 1])
        expect(g.win_rate, `[AANA65] roi-sources (${qui}) : win_rate = 1 ÷ 2 non perdus = 50.0 (pas 33.3)`).toBe(50)
        expect(ligne(rows, c2p)?.win_rate, `[AANA65] roi-sources (${qui}) : groupe tout perdu ⇒ null`).toBeNull()
      }
    }
    // Même règle que LE taux de gain du reporting (apps.reporting.services.taux_gain, D-AANA-1) sur les mêmes leads.
    const tg = await py(`from apps.crm.models import Lead
from apps.reporting.services import taux_gain
sortie([taux_gain(Lead.objects.filter(pk__in=${J(ids.slice(0, 3))})), taux_gain(Lead.objects.filter(pk__in=${J(ids.slice(3))}))])`)
    expect(tg, '[AANA65] taux_gain du reporting sur les mêmes leads = roi-sources').toEqual([50, null])
    // ── Écran : cockpit CRM du directeur, carte « ROI par source » → « 1 (50 %) » ; rechargement ⇒ identique.
    const pd = await ouvrir(w.dA, suivi)
    for (const recharger of [false, true]) {
      if (recharger) await pd.reload({ waitUntil: 'domcontentloaded' })
      else await pd.goto('/crm/cockpit')
      const tr = pd.locator('tr', { hasText: c2 })
      await expect(tr, `cockpit : ligne ${c2}`).toBeVisible({ timeout: 60_000 })
      expect(plat(await tr.innerText()), `[AANA65] écran : « 1 (50 %) » (rechargé=${recharger})`).toContain('1(50%)')
      expect(plat(await pd.locator('tr', { hasText: c2p }).innerText()), '[AANA65] écran : groupe tout perdu « (—) »').toContain('(—)')
    }
    // ── Accueil du commercial : « Mes chiffres » affiche les effectifs et le taux SERVIS (D-AANA-VER-1), identiques au
    // rechargement. On lit les QUATRE cases de chiffres une fois la carte posée sur les valeurs servies (la carte se
    // peint d'abord à 0 puis reçoit le Quote-to-cash ; le bloc « Leads chauds » arrive ensuite) — jamais le texte brut.
    const pc = await ouvrir(w.cA, suivi)
    const kpis = async () => {
      const t = (await pc.getByTestId('mes-chiffres-card').locator('div.grid > div').allInnerTexts()).map((x) => plat(x).toLowerCase())
      return t.length === 4 ? [t[0], t[1], t[2], chiffresSeuls(t[3])] : t
    }
    for (const recharger of [false, true]) {
      const mine = pc.waitForResponse((x) => /\/ventes\/dashboard\//.test(x.url()) && /mine=1/.test(x.url()), { timeout: 60_000 })
      if (recharger) await pc.reload({ waitUntil: 'domcontentloaded' })
      else await pc.goto('/dashboard')
      const q2c = await (await mine).json()
      expect([q2c.devis?.envoyes_periode, q2c.devis?.acceptes_periode], `Quote-to-cash servi au commercial : 2 envoyés, 1 accepté (${J(q2c.devis)})`).toEqual([2, 1])
      await expect(pc.getByTestId('mes-chiffres-card')).toBeVisible({ timeout: 60_000 })
      await expect.poll(kpis, { timeout: 60_000, message: `« Mes chiffres » = valeurs servies (rechargé=${recharger})` }).toEqual([
        `devisenvoyés${q2c.devis.envoyes_periode}`, `devisacceptés${q2c.devis.acceptes_periode}`,
        `tauxdesignature${Math.round(Number(q2c.devis.taux_acceptation_pct))}%`, String(Math.round(caSigneMc)),
      ])
    }
    // ── (5) Société B : ni le directeur ni le commercial de B ne voient les groupes de A.
    for (const [u, qui] of [[w.dB, 'directeur B'], [w.cB, 'commercial B']]) {
      const rows = await lire(u, `${API}/crm/leads/roi-sources/`, `roi-sources ${qui}`)
      expect(J(rows), `${qui} : aucun groupe de A`).not.toContain(`acc90-${m}`)
    }
    expect((await appel(w.dB, 'get', `${API}/crm/leads/${ids[0]}/`)).status(), 'B : lead de A → 404').toBe(404)
    suivi.verifie(9)
    await page.close()
  } finally {
    await py(`from apps.crm.models import Lead
from apps.ventes.models import Devis
Devis.objects.filter(pk__in=${J(devisMc)}).update(is_active=False)
Lead.objects.filter(pk__in=${J(ids)}).update(is_archived=True)
sortie(1)`).catch(() => null)
  }
})

// ═══ (3) Une vente par chaîne de révision, la V1 en vigueur gardée : contrôle du suivi, Mes équipes, objectif, attribution ═══
etape('P3.une_vente_par_revision', ['AANA68', 'AANA75', 'AANA76', 'AANA90'], async ({ page, suivi, testInfo }) => {
  const w = await lePlateau(page, testInfo)
  const { a, b } = w
  const c3 = `acc90-${m}-ca`
  const equipeNom = `ACC90 équipe ${m}`
  const tels = [1, 2, 3, 4, 5].map(() => telephoneMobileUnique())
  const f = await py(`import datetime
from decimal import Decimal
from apps.crm.models import Lead, EquipeCommerciale, ObjectifCommercial
from apps.crm import stages as S
from apps.stock.models import Produit
p = Produit.objects.create(company_id=${a.co}, sku='ACC90-KIT-${m}', nom='Kit ACC90 ${m}', prix_vente=Decimal('1000'), quantite_stock=0)
leads = []
for i, canal in enumerate(['site_web', 'site_web', 'meta_ads']):
    leads.append(Lead.objects.create(company_id=${a.co}, nom='ACC90 vente %d ${m}' % i, telephone=${J(tels)}[i],
        email='acc90v%d${m}@example.invalid' % i, owner_id=${a.com_id}, canal=canal, utm_campaign='${c3}', stage=S.NEW).pk)
eq = EquipeCommerciale.objects.create(company_id=${a.co}, nom='${equipeNom}', responsable_id=${a.dir_id}, actif=True)
eq.membres.add(${a.com_id})
# Le sélecteur « Commercial » du « Contrôle du suivi » ne liste que les responsables ayant une étape de suivi dans la
# période (controle_suivi.py, concernes -> commerciaux) et ne s'affiche qu'à partir de DEUX (ControleSuiviPanel.jsx,
# commerciaux.length > 1) : une étape d'appel FAITE aujourd'hui sur un lead témoin (non signé, sans devis, campagne à
# part) du commercial et une sur un lead témoin du directeur — hors des leads à devis, donc sans effet sur les
# résultats (devis envoyés / acceptés) ni sur le CA ; l'arrêt de cadence à l'acceptation ne peut pas les toucher.
from apps.crm.models_cadence import RelanceEtape
temoins = [Lead.objects.create(company_id=${a.co}, nom='ACC90 temoin %d ${m}' % k, telephone=${J(tels)}[3 + k],
    email='acc90t%d${m}@example.invalid' % k, owner_id=par, canal='site_web', utm_campaign='acc90-${m}-temoin',
    stage=S.CONTACTED).pk for k, par in enumerate((${a.com_id}, ${a.dir_id}))]
maintenant = timezone.now()
etapes = [RelanceEtape.objects.create(company_id=${a.co}, lead_id=lid, cadence='contact', ordre=0, canal='appel',
    due_date=timezone.localdate(), due_at=maintenant, statut='fait', traite_le=maintenant, traite_par_id=par).pk
    for lid, par in zip(temoins, (${a.com_id}, ${a.dir_id}))]
sortie(dict(p=p.pk, leads=leads, equipe=eq.pk, temoins=temoins, etapes=etapes))`)
  const [L1, L2, L3] = f.leads
  const devisCrees = []
  let objectif = null
  const ligne = (qte) => [{ produit: f.p, designation: 'Kit ACC90', quantite: String(qte), prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }]
  const creer = async (lead, qte) => {
    const dv = await lireJson(await appel(w.dA, 'post', `${API}/ventes/devis/atomic/`, { data: { taux_tva: '20.00', remise_globale: '0', lead, lignes: ligne(qte) } }), `devis du lead ${lead}`)
    devisCrees.push(dv.id)
    return dv.id
  }
  const accepter = async (id) => lireJson(await appel(w.dA, 'post', `${API}/ventes/devis/${id}/accepter/`, { data: { nom: 'Client ACC90' } }), `acceptation ${id}`)
  const reviser = async (id) => {
    const r = await appel(w.dA, 'post', `${API}/ventes/devis/${id}/reviser/`, { data: {} })
    const nd = await lireJson(r, `révision ${id}`)
    devisCrees.push(nd.id)
    return nd.id
  }
  const relignes = async (id, qte) => lireJson(await appel(w.dA, 'post', `${API}/ventes/devis/${id}/replace-lines/`, { data: { lignes: ligne(qte) } }), `lignes ${id}`)
  try {
    // Gestes réels : L1 = V1 acceptée, révisée, V2 acceptée ; L2 = un devis accepté jamais révisé ; L3 = V1 acceptée révisée en V2 BROUILLON.
    const D1 = await creer(L1, 1); await accepter(D1)
    const D1v2 = await reviser(D1); await relignes(D1v2, 2); await accepter(D1v2)
    const D2 = await creer(L2, 3); await accepter(D2)
    const D3 = await creer(L3, 5); await accepter(D3)
    const D3v2 = await reviser(D3); await relignes(D3v2, 7)
    const ttc = {}
    for (const id of [D1, D1v2, D2, D3, D3v2]) ttc[id] = Number((await lire(w.dA, `${API}/ventes/devis/${id}/`, `devis ${id} relu`)).total_ttc)
    const attendu = ttc[D1v2] + ttc[D2] + ttc[D3]
    expect(ttc[D3], 'témoin : la V1 de L3 porte un montant').toBeGreaterThan(0)
    const cible = 2 * attendu
    objectif = await py(`import datetime
from apps.crm.models import ObjectifCommercial
t = datetime.date.today()
sortie(ObjectifCommercial.objects.create(company_id=${a.co}, owner_id=${a.com_id}, metric='ca_signe', period_type='month',
    period_year=t.year, period_month=t.month, cible='${cible.toFixed(2)}').pk)`)
    const fond = await py(`import datetime
from apps.crm.models import Lead
from apps.crm.portee_selectors import lead_signe_q
from apps.ventes.selectors import devis_signes_en_vigueur
from apps.ventes.models import Devis
mine = ${J(f.leads)}
sortie(dict(signes=Lead.objects.filter(pk__in=mine).filter(lead_signe_q()).count(),
    signes_com=Lead.objects.filter(company_id=${a.co}, owner_id=${a.com_id}).filter(lead_signe_q()).count(),
    en_vigueur=sorted(devis_signes_en_vigueur(Lead.objects.get(pk=mine[0]).company, lead_ids=mine).values_list('pk', flat=True)),
    envoyes=Devis.objects.filter(lead_id__in=mine, date_envoi__isnull=False).count()))`)
    expect(fond.signes, 'précondition : les trois leads sont signés après acceptation').toBe(3)
    expect(fond.en_vigueur, 'ventes en vigueur (VNT22) : V2 de L1, devis de L2, V1 de L3').toEqual([D1v2, D2, D3].sort((x, y) => x - y))

    // ── AANA68 : « Contrôle du suivi » du commercial — une acceptation par chaîne (3, pas 4).
    for (let i = 0; i < 2; i++) {
      const ctl = await lire(w.dA, `${API}/crm/relance-etapes/controle/?jours=14&owner=${a.com_id}`, 'contrôle du suivi')
      expect(ctl.resultats.devis_acceptes, `[AANA68] devis acceptés = une vente par lead (3) : ${J(ctl.resultats)}`).toBe(3)
      expect(ctl.resultats.devis_envoyes, 'devis envoyés inchangés (définition date_envoi)').toBe(fond.envoyes)
    }
    // ── AANA75 : « Mes équipes », objectif CA, ca_signe_periode, roi-sources — V1 de L3 gardée, V2 brouillon exclue.
    const equipe = async (u) => (await lire(u, `${API}/crm/equipes/statistiques/`, 'Mes équipes')).equipes || []
    for (let i = 0; i < 2; i++) {
      const eq = (await equipe(w.dA)).find((e) => e.id === f.equipe)
      expect(eq, 'Mes équipes : équipe d\'essai servie').toBeTruthy()
      expect(Number(eq.ca_signe_mois), `[AANA75] Mes équipes : CA signé du mois = ${attendu} (V1 en vigueur gardée)`).toBeCloseTo(attendu, 2)
      expect(eq.avancement_pct, '[AANA75] Mes équipes : 50 % de la cible').toBe(50)
      const att = await lire(w.dA, `${API}/crm/objectifs/attainment/?owner=${a.com_id}`, 'objectifs')
      const o = (att || []).find((x) => x.id === objectif)
      expect(o, 'objectif CA servi').toBeTruthy()
      expect(Number(o.realise), `[AANA75] objectif CA : réalisé = ${attendu}`).toBeCloseTo(attendu, 2)
      expect(Number(o.taux), '[AANA75] objectif CA : 50 %').toBeCloseTo(50, 1)
    }
    const csp = await py(`import datetime
from authentication.models import Company
from apps.crm.selectors import ca_signe_periode
t = datetime.date.today()
sortie([str(ca_signe_periode(Company.objects.get(pk=${a.co}), [${a.com_id}], t.replace(day=1), t)),
        str(ca_signe_periode(Company.objects.get(pk=${b.co}), [${a.com_id}], t.replace(day=1), t))])`)
    expect(Number(csp[0]), '[AANA75] ca_signe_periode = ventes en vigueur').toBeCloseTo(attendu, 2)
    const roi = (await lire(w.dA, `${API}/crm/leads/roi-sources/`, 'roi-sources')).filter((r) => r.utm_campaign === c3)
    expect(roi.reduce((s, r) => s + Number(r.signed_value_ttc), 0), '[AANA75] roi-sources : valeur signée = ventes en vigueur').toBeCloseTo(attendu, 2)
    // ── AANA76 : attribution par commercial (route), par source et revenu de campagne (sélecteurs, façade crm).
    for (let i = 0; i < 2; i++) {
      const attr = await lire(w.dA, `${API}/crm/rapports/attribution/`, 'attribution')
      const lc = (attr.par_commercial || []).find((x) => x.commercial === a.com)
      expect(lc, 'attribution : commercial d\'essai servi').toBeTruthy()
      expect(Number(lc.ca_signe), `[AANA76] attribution par commercial : ${attendu}`).toBeCloseTo(attendu, 2)
      expect(lc.nb_signes, 'attribution : nb_signes inchangé (leads signés du commercial)').toBe(fond.signes_com)
    }
    const sel = await py(`from authentication.models import Company
from apps.crm.models import Lead
from apps.crm.selectors import attribution_leads, revenu_attribue_campagne
co = Company.objects.get(pk=${a.co})
r = attribution_leads(co, leads=Lead.objects.filter(pk__in=${J(f.leads)}))
sortie(dict(source={s['canal']: str(s['ca_signe']) for s in r['par_source']}, campagne=revenu_attribue_campagne(co, '${c3}'),
            campagne_b=revenu_attribue_campagne(Company.objects.get(pk=${b.co}), '${c3}')))`)
    expect(Number(sel.source.site_web), '[AANA76] attribution par source site_web = V2 de L1 + L2').toBeCloseTo(ttc[D1v2] + ttc[D2], 2)
    expect(Number(sel.source.meta_ads), '[AANA76] attribution par source meta_ads = V1 en vigueur de L3').toBeCloseTo(ttc[D3], 2)
    expect(Number(sel.campagne.revenu_ttc), `[AANA76] revenu de la campagne = ${attendu}`).toBeCloseTo(attendu, 2)
    expect(sel.campagne.nb_signes, 'revenu de campagne : 3 leads signés').toBe(3)

    // ── Écran : accueil du directeur, carte « Mes équipes » ; cockpit, « Contrôle du suivi » filtré sur le commercial.
    const pd = await ouvrir(w.dA, suivi)
    for (const recharger of [false, true]) {
      const rep = pd.waitForResponse((x) => /\/crm\/equipes\/statistiques\/?/.test(x.url()), { timeout: 60_000 })
      if (recharger) await pd.reload({ waitUntil: 'domcontentloaded' })
      else await pd.goto('/dashboard')
      expect((await rep).status(), 'accueil : Mes équipes lue').toBe(200)
      const carte = pd.locator('div.rounded-lg', { has: pd.getByText(equipeNom, { exact: true }) }).last()
      await expect(carte, 'accueil : carte de l\'équipe d\'essai').toBeVisible({ timeout: 60_000 })
      const ca = carte.getByRole('link', { name: /CA signé \(mois\)/ })
      expect(chiffresSeuls(await ca.innerText()), `[AANA75] écran Mes équipes : ${attendu} / ${cible} (rechargé=${recharger})`)
        .toBe(`${Math.round(attendu)}/${Math.round(cible)}`)
      await expect(carte).toContainText('50% de la cible')
    }
    for (const recharger of [false, true]) {
      const equipeEntiere = pd.waitForResponse((x) => /\/relance-etapes\/controle\//.test(x.url()) && !new URL(x.url()).searchParams.get('owner'), { timeout: 60_000 })
      if (recharger) await pd.reload({ waitUntil: 'domcontentloaded' })
      else await pd.goto('/crm/cockpit')
      const commerciaux = ((await (await equipeEntiere).json()).commerciaux || []).map((c) => c.nom)
      expect(commerciaux, 'contrôle servi : le commercial d\'essai fait partie des responsables proposés au filtre').toContain(a.com)
      const bascule = pd.getByTestId('controle-bascule-detail')
      await expect(bascule).toBeVisible({ timeout: 60_000 })
      if ((await bascule.getAttribute('aria-expanded')) !== 'true') await bascule.click()
      await expect(bascule).toHaveAttribute('aria-expanded', 'true')
      const selecteur = pd.getByTestId('controle-selecteurs').getByRole('combobox', { name: 'Commercial' })
      await expect(selecteur, 'sélecteur « Commercial » affiché (deux responsables concernés)').toBeVisible({ timeout: 60_000 })
      const filtre = pd.waitForResponse((x) => /\/relance-etapes\/controle\//.test(x.url()) && new URL(x.url()).searchParams.get('owner') === String(a.com_id), { timeout: 60_000 })
      await selecteur.click()
      await pd.getByRole('option', { name: a.com, exact: true }).click()
      const servi = await (await filtre).json()
      expect(servi.resultats.devis_acceptes, `[AANA68] écran : le cockpit lit 3 acceptations (rechargé=${recharger})`).toBe(3)
      await expect(pd.getByTestId('controle-resultats'), '[AANA68] écran : « 3 devis acceptés »').toContainText('3 devis acceptés', { timeout: 60_000 })
    }

    // ── (5) Société B : rien de A.
    expect((await appel(w.dB, 'get', `${API}/crm/relance-etapes/controle/?jours=14&owner=${a.com_id}`)).status(), 'B : commercial de A hors portée → 404').toBe(404)
    expect(J(await equipe(w.dB)), 'B : aucune équipe de A').not.toContain(equipeNom)
    const attB = await lire(w.dB, `${API}/crm/objectifs/attainment/`, 'objectifs B')
    expect((attB || []).filter((x) => x.owner === a.com_id || x.id === objectif), 'B : aucun objectif de A').toEqual([])
    expect(J(await lire(w.dB, `${API}/crm/rapports/attribution/`, 'attribution B')), 'B : aucun commercial de A').not.toContain(a.com)
    expect(J(await lire(w.dB, `${API}/crm/leads/roi-sources/`, 'roi-sources B')), 'B : aucune campagne de A').not.toContain(c3)
    expect(Number(csp[1]), 'B : CA signé du commercial de A = 0').toBe(0)
    expect([sel.campagne_b.nb_leads, Number(sel.campagne_b.revenu_ttc)], 'B : campagne de A vide').toEqual([0, 0])
    expect((await appel(w.dB, 'get', `${API}/ventes/devis/${D2}/`)).status(), 'B : devis de A → 404').toBe(404)
    suivi.verifie(9)
    await page.close()
  } finally {
    await py(`from apps.crm.models import Lead, EquipeCommerciale, ObjectifCommercial
from apps.ventes.models import Devis
Devis.objects.filter(pk__in=${J(devisCrees)}).update(is_active=False)
Lead.objects.filter(pk__in=${J(f.leads)}).update(is_archived=True)
EquipeCommerciale.objects.filter(pk=${f.equipe}).update(actif=False)
from apps.crm.models_cadence import RelanceEtape
RelanceEtape.objects.filter(pk__in=${J(f.etapes)}).delete()
Lead.objects.filter(pk__in=${J(f.temoins)}).update(is_archived=True)
ObjectifCommercial.objects.filter(pk=${objectif ?? 0}).delete()
sortie(1)`).catch(() => null)
  }
})

// ═══ (4) Widget `ca_ht` (métrique de la couche sémantique) : une facture brouillon n'y entre pas ═══
etape('P4.widget_ca_ht_brouillon', ['AANA61', 'AANA90'], async ({ page, suivi, testInfo }) => {
  const w = await lePlateau(page, testInfo)
  const { a, b } = w
  await py(`from django.core.management import call_command
call_command('seed_metriques', company=${a.co}, verbosity=0)
call_command('seed_metriques', company=${b.co}, verbosity=0)
sortie(1)`)
  const valeurs = async (u) => {
    const out = {}
    for (const cle of ['ca_ht', 'ca_ttc']) out[cle] = (await lire(u, `${API}/semantic/metriques/${cle}/valeur/`, `métrique ${cle}`)).valeur
    return out
  }
  const num = (v) => (v === null || v === undefined ? 0 : Number(v))
  const creees = []
  const facture = (statut, pu) => py(`from decimal import Decimal
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture
cl, _ = Client.objects.get_or_create(company_id=${a.co}, nom='Cli ACC90 F ${m}', defaults=dict(prenom='X', email='clf${m}@example.invalid'))
p, _ = Produit.objects.get_or_create(company_id=${a.co}, sku='ACC90-F-${m}', defaults=dict(nom='ACC90 F ${m}', prix_vente=Decimal('1'), quantite_stock=0))
f = Facture.objects.create(company_id=${a.co}, reference='FAC-ACC90-${m}-' + '${statut}', client=cl, statut='${statut}', taux_tva=Decimal('20.00'), date_emission=timezone.localdate())
LigneFacture.objects.create(facture=f, produit=p, designation='ACC90', quantite=Decimal('1'), prix_unitaire=Decimal('${pu}'), remise=Decimal('0'), taux_tva=Decimal('20.00'))
sortie(f.pk)`)
  try {
    const v0 = await valeurs(w.dA)
    const fb = await facture('brouillon', '1000'); creees.push(fb)
    for (let i = 0; i < 2; i++) {
      const v1 = await valeurs(w.dA)
      expect(num(v1.ca_ht), `[AANA61] ca_ht : une facture brouillon de 1 000 HT n'entre pas (${J(v0)} → ${J(v1)})`).toBeCloseTo(num(v0.ca_ht), 2)
      expect(num(v1.ca_ttc), '[AANA61] ca_ttc : brouillon exclu').toBeCloseTo(num(v0.ca_ttc), 2)
    }
    expect((await lire(w.dA, `${API}/ventes/factures/${fb}/`, 'brouillon relu')).statut, 'le brouillon est bien en base').toBe('brouillon')
    const fe = await facture('emise', '500'); creees.push(fe)
    for (let i = 0; i < 2; i++) {
      const v2 = await valeurs(w.dA)
      expect(num(v2.ca_ht), 'ca_ht : une facture émise de 500 HT entre (témoin)').toBeCloseTo(num(v0.ca_ht) + 500, 2)
      expect(num(v2.ca_ttc), 'ca_ttc : +600 TTC (témoin)').toBeCloseTo(num(v0.ca_ttc) + 600, 2)
    }
    // ── (5) Société B : sa métrique ne voit aucune facture de A.
    const vb = await valeurs(w.dB)
    expect([vb.ca_ht === null ? null : Number(vb.ca_ht), vb.ca_ttc === null ? null : Number(vb.ca_ttc)].every((x) => x === null || x === 0),
      `B : ca_ht/ca_ttc vides (${J(vb)})`).toBe(true)
    for (const id of creees) expect((await appel(w.dB, 'get', `${API}/ventes/factures/${id}/`)).status(), `B : facture ${id} de A → 404`).toBe(404)
    suivi.verifie(9)
  } finally {
    await py(`from apps.ventes.models import Facture
for pk in ${J(creees)}:
    try:
        Facture.objects.filter(pk=pk).delete()
    except Exception as e:
        Facture.objects.filter(pk=pk).update(statut='annulee')
        print("facture annulée au lieu d'être supprimée :", pk, e)
sortie(1)`).catch(() => null)
  }
})
