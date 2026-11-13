// Acceptation en direct — groupe APFS (parcours PF1 « sécurité / multi-société », run 99392c) : preuves dues
// d'APFS117 (écriture des contrats de prix / commandes cadres sous `achats_commander`) et APFS29 (prix d'achat du
// routeur `installations` masqués sans `prix_achat_voir`).
// (1) la sonde commitée `docs/audits/sondes/APFS/C-APFS-082.py` (volets lecture ET écriture) est REJOUÉE sur l'arbre
//     dans le shell Django du runner, transaction annulée — même programme que `scripts/sonde.py`, sans docker ;
// (2) les mêmes gestes par les vraies routes HTTP (cookie de connexion réel) dans la société de demo_admin, avec des
//     comptes d'essai portant les rôles système de la société ; (3) l'écran « Approvisionnement avancé » (Achats).
import { test, expect, request as pwRequest } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, connexionApi, uiLoginJusquAuxApps, API_DJANGO as API } from '../helpers.js'

const etape = groupe('APFS', ['APFS117', 'APFS29'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const T = { timeout: 120_000 }
const J = JSON.stringify
const INST = `${API}/installations`
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()

/** Rejoue une sonde commitée dans le shell Django (transaction ANNULÉE, Celery neutralisé) ; rend `{ret, err}`. */
function sondeEnLigne(groupeSonde, constat) {
  const src = readFileSync(join(RACINE, 'docs', 'audits', 'sondes', groupeSonde, `${constat}.py`), 'utf8')
  return py(`import io, contextlib
from django.conf import settings
from django.db import transaction
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver', 'localhost']
def _noop(self, *a, **k):
    return type('R', (), {'id': 'noop'})()
ns = {'__name__': '__sonde__'}
exec(compile(${J(src)}, 'sonde', 'exec'), ns)
ret, err = None, None
with mock.patch('celery.app.task.Task.apply_async', new=_noop), mock.patch('celery.app.task.Task.delay', new=_noop):
    try:
        with transaction.atomic():
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    ret = ns['sonde']({'celery': [], 'racine': '.', 'args': None})
            finally:
                transaction.set_rollback(True)
    except BaseException:
        import traceback
        err = traceback.format_exc()[-2500:]
sortie({'ret': ret, 'err': err})`)
}

// Clés de prix d'ACHAT (mêmes listes que la sonde C-APFS-082 et la garde test_astk_garde_prix_achat).
const EXACTES = new Set(['prix_achat', 'prix_unitaire_ht', 'prix_convenu', 'montant_achete', 'frais_annexes', 'montant',
  'total_valeur', 'valeur', 'prix_negocie', 'valeur_fob', 'remise_pct', 'prix_achat_unitaire'])
const PREFIXES = ['prix_achat_', 'total_achat', 'montant_', 'cout_', 'budget_']
function clesPrix(d, acc = new Set(), pre = '') {
  if (Array.isArray(d)) d.forEach((x) => clesPrix(x, acc, pre))
  else if (d && typeof d === 'object') {
    for (const [k, v] of Object.entries(d)) {
      if ((EXACTES.has(k) || PREFIXES.some((p) => k.startsWith(p))) && v !== null && v !== '' && !(Array.isArray(v) && !v.length)) acc.add(pre + k)
      clesPrix(v, acc, v && typeof v === 'object' ? `${pre}${k}.` : pre)
    }
  }
  return acc
}

/** Compte d'essai (rôle SYSTÈME de la société démo) + contexte API connecté par la vraie route de connexion. */
const sessions = new Map()
async function session(testInfo, nom, roleNom) {
  if (sessions.has(nom)) return sessions.get(nom)
  const id = await py(`from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from authentication.role_tiers import tier_for_role_fields
co = U.objects.get(username='demo_admin').company_id
r = Role.objects.filter(company_id=co, nom=${J(roleNom)}).order_by('id').first()
if r is None:
    r = Role.objects.create(company_id=co, nom=${J(roleNom)}, est_systeme=True, permissions=list(dict(CANONICAL_SYSTEM_ROLES)[${J(roleNom)}]))
u = compte(${J(nom)}, role=r.pk, societe=co)
u.role_legacy = tier_for_role_fields(r.nom, r.est_systeme, r.permissions); u.save(update_fields=['role_legacy'])
sortie(dict(id=u.id, achats_commander='achats_commander' in (r.permissions or []), prix='prix_achat_voir' in (r.permissions or [])))`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  const s = { ctx, nom, ...id }
  sessions.set(nom, s)
  return s
}
test.afterAll(async () => { for (const s of sessions.values()) await s.ctx.dispose().catch(() => undefined) })

/** Fournisseur, produit, contrat de prix (+ ligne), commande cadre (+ ligne, appel) dans la société démo. */
async function achats() {
  const m = marque()
  return py(`a = U.objects.get(username='demo_admin'); co = a.company
from decimal import Decimal as D
from apps.stock.models import Fournisseur, Produit
from apps.installations.models_contrat_prix import ContratPrixFournisseur, ContratPrixLigne
from apps.installations.models_commande_cadre import CommandeCadre, CommandeCadreLigne, AppelCommande
f = Fournisseur.objects.create(company=co, nom='ACC APFS ${m}')
p = Produit.objects.create(company=co, nom='Onduleur ACC APFS ${m}', sku='ACC-APFS-${m}', prix_vente=D('5000'))
c = ContratPrixFournisseur.objects.create(company=co, reference='CPF-ACC-${m}', intitule='Accord ACC ${m}', fournisseur=f, created_by=a)
cl = ContratPrixLigne.objects.create(contrat=c, produit=p, prix_convenu=D('777.77'), remise_pct=D('5'))
cc = CommandeCadre.objects.create(company=co, reference='CC-ACC-${m}', intitule='Cadre ACC ${m}', fournisseur=f, created_by=a)
ccl = CommandeCadreLigne.objects.create(commande_cadre=cc, produit=p, designation='Onduleur', prix_negocie=D('666.66'), volume_engage=D('100'))
ap = AppelCommande.objects.create(company=co, ligne=ccl, quantite=D('3'), created_by=a)
sortie(dict(m='${m}', f=f.id, p=p.id, c=c.id, c_ref=c.reference, cl=cl.id, cc=cc.id, ccl=ccl.id, ap=ap.id))`)
}
const compter = () => py(`co = U.objects.get(username='demo_admin').company
from apps.installations.models_contrat_prix import ContratPrixFournisseur, ContratPrixLigne
from apps.installations.models_commande_cadre import CommandeCadre, CommandeCadreLigne, AppelCommande
sortie([ContratPrixFournisseur.objects.filter(company=co).count(), ContratPrixLigne.objects.filter(contrat__company=co).count(),
        CommandeCadre.objects.filter(company=co).count(), CommandeCadreLigne.objects.filter(commande_cadre__company=co).count(),
        AppelCommande.objects.filter(company=co).count()])`)

// ═══ (1) Sonde C-APFS-082 rejouée : lecture masquée (Commercial, Viewer, Technicien), écriture refusée (Technicien resp.)
etape('PF1.sonde_C-APFS-082', ['APFS117', 'APFS29'], async () => {
  const s = await sondeEnLigne('APFS', 'C-APFS-082')
  expect(s.err, `sonde rejouée sans erreur : ${s.err}`).toBeNull()
  const o = s.ret
  expect(o.erreurs_creation, `montage de la sonde complet (${J(o.erreurs_creation)})`).toEqual({})
  expect(o.repro, `repro False : aucun rôle sans prix_achat_voir ne lit un prix d'achat installations (${J(o.roles_lisant_prix_installations)})`).toBe(false)
  expect(o.roles_lisant_prix_installations, 'aucun rôle lecteur de prix').toEqual([])
  for (const role of ['Commercial', 'Viewer', 'Technicien']) {
    for (const [route, v] of Object.entries(o[role])) {
      if (route === 'TEMOIN_bcf' || route === 'prix-convenu') continue
      expect(v, `${role} ${route} : aucune clé de prix (${v})`).toMatch(/prix=\[\]$/)
    }
    expect(o[role]['prix-convenu'], `${role} : prix-convenu refusé`).toMatch(/^403/)
  }
  const adm = o['Administrateur (contrôle positif)']
  expect(Object.entries(adm).filter(([k, v]) => k !== 'TEMOIN_bcf' && k !== 'prix-convenu' && !/prix=\[\]$/.test(v)).length,
    `contrôle positif : l'Administrateur lit les prix (${J(adm).slice(0, 400)})`).toBeGreaterThan(0)
  expect(adm['prix-convenu'], 'Administrateur : prix-convenu 200').toMatch(/^200/)
  const w = o.ecriture_Technicien_responsable
  expect([w.installation_gerer, w.achats_commander], 'Technicien responsable : installation_gerer sans achats_commander').toEqual([true, false])
  expect([w['POST contrat'], w['POST commande cadre'], w['TEMOIN POST BCF (ACHT54)']], `écritures refusées (${J(w)})`).toEqual([403, 403, 403])
})

// ═══ (2) APFS117 par les vraies routes : Technicien responsable 403 partout, rien créé ; Administrateur 201/200 ; écran
etape('PF1.ecriture_sous_achats_commander', ['APFS117'], async ({ page, testInfo }) => {
  const tresp = await session(testInfo, 'apfs_tech_resp', 'Technicien responsable')
  expect([tresp.achats_commander], 'rôle Technicien responsable sans achats_commander').toEqual([false])
  const x = await achats()
  const ecritures = [
    ['contrats-prix-fournisseur/', { intitule: `ACC ${x.m}`, fournisseur: x.f }],
    ['contrats-prix-lignes/', { contrat: x.c, produit: x.p, prix_convenu: '1.00' }],
    ['commandes-cadre/', { intitule: `ACC ${x.m}`, fournisseur: x.f }],
    ['commandes-cadre-lignes/', { commande_cadre: x.cc, designation: 'P', prix_negocie: '1.00', volume_engage: '10' }],
    ['appels-commande/', { ligne: x.ccl, quantite: '1' }],
    [`contrats-prix-fournisseur/${x.c}/activer/`, {}],
    [`commandes-cadre/${x.cc}/activer/`, {}],
  ]
  const avant = await compter()
  for (const [chemin, corps] of ecritures) {
    const rep = await tresp.ctx.post(`${INST}/${chemin}`, { ...T, data: corps })
    expect(rep.status(), `Technicien responsable POST ${chemin} (${(await rep.text()).slice(0, 200)})`).toBe(403)
  }
  // Persistance : relire ⇒ aucun contrat, ligne, commande cadre ni appel créé ; statuts restés brouillon.
  expect(await compter(), 'rien créé par les refus').toEqual(avant)
  const statuts = await py(`from apps.installations.models_contrat_prix import ContratPrixFournisseur
from apps.installations.models_commande_cadre import CommandeCadre
sortie([ContratPrixFournisseur.objects.get(pk=${x.c}).statut, CommandeCadre.objects.get(pk=${x.cc}).statut])`)
  expect(statuts, 'activations refusées : brouillon').toEqual(['brouillon', 'brouillon'])
  // Administrateur (demo_admin) : 201/200 sur les mêmes gestes.
  let nouveauContrat = null
  for (const [chemin, corps] of ecritures) {
    const rep = await page.request.post(`${INST}/${chemin}`, { ...T, data: corps })
    expect([200, 201], `Administrateur POST ${chemin} (${(await rep.text()).slice(0, 200)})`).toContain(rep.status())
    if (chemin === 'contrats-prix-fournisseur/') nouveauContrat = await rep.json()
  }
  // Écran : Approvisionnement avancé → « Contrats de prix » : le contrat créé par l'Administrateur y figure.
  await page.goto('/chantiers/approvisionnement')
  await page.getByRole('tab', { name: 'Contrats de prix' }).click({ timeout: 60_000 })
  await expect(page.getByRole('tabpanel').getByText(nouveauContrat.reference, { exact: true }).first()).toBeVisible({ timeout: 60_000 })
  await page.reload()
  await page.getByRole('tab', { name: 'Contrats de prix' }).click({ timeout: 60_000 })
  await expect(page.getByRole('tabpanel').getByText(nouveauContrat.reference, { exact: true }).first(), 'persistance : relu après rechargement').toBeVisible({ timeout: 60_000 })
})

// ═══ (3) APFS29 par les vraies routes : Commercial sans prix (prix-convenu 403), Directeur avec ; écran en Directeur
etape('PF1.lecture_prix_installations', ['APFS29'], async ({ page, suivi, testInfo }) => {
  const com = await session(testInfo, 'apfs_commercial', 'Commercial')
  const dir = await session(testInfo, 'apfs_directeur', 'Directeur')
  expect([com.prix, dir.prix], 'prix_achat_voir : Commercial non, Directeur oui').toEqual([false, true])
  const x = await achats()
  await py(`from apps.installations.models_contrat_prix import ContratPrixFournisseur
ContratPrixFournisseur.objects.filter(pk=${x.c}).update(statut='actif')
sortie(1)`)
  const cibles = {
    'contrats-prix-fournisseur': x.c, 'contrats-prix-lignes': x.cl, 'commandes-cadre': x.cc,
    'commandes-cadre-lignes': x.ccl, 'appels-commande': x.ap,
  }
  const lire = async (ctx) => {
    const out = {}
    for (const [route, id] of Object.entries(cibles)) {
      for (const url of [`${INST}/${route}/${id}/`, `${INST}/${route}/`]) {
        const rep = await ctx.get(url, T)
        const corps = rep.ok() ? await rep.json() : null
        out[url] = { statut: rep.status(), prix: [...clesPrix(corps)] }
      }
    }
    const pc = await ctx.get(`${INST}/contrats-prix-fournisseur/prix-convenu/?produit=${x.p}`, T)
    out['prix-convenu'] = { statut: pc.status() }
    return out
  }
  const vuCom = await lire(com.ctx)
  for (const [url, v] of Object.entries(vuCom)) {
    if (url === 'prix-convenu') continue
    expect([200, 403], `Commercial ${url}`).toContain(v.statut)
    expect(v.prix, `Commercial ${url} : aucune clé de prix d'achat`).toEqual([])
  }
  expect(vuCom['prix-convenu'].statut, 'Commercial : prix-convenu 403').toBe(403)
  const vuDir = await lire(dir.ctx)
  const detail = (route) => vuDir[`${INST}/${route}/${cibles[route]}/`]
  expect(detail('contrats-prix-lignes').prix, `Directeur : prix_convenu servi (${J(detail('contrats-prix-lignes'))})`).toContain('prix_convenu')
  expect(detail('commandes-cadre-lignes').prix, 'Directeur : prix_negocie servi').toContain('prix_negocie')
  expect(vuDir['prix-convenu'].statut, 'Directeur : prix-convenu 200').toBe(200)
  const appel = await lireJson(await dir.ctx.get(`${INST}/appels-commande/${x.ap}/`, T), 'appel en Directeur')
  expect(Number(appel.montant), `montant de l'appel servi au Directeur (${J(appel)})`).toBeGreaterThan(0)
  // Écran : Directeur → Approvisionnement avancé → « Commandes d'appel » : le montant (prix d'achat) est affiché.
  const ctxUi = await page.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block' })
  try {
    const p = suivi.surveiller(await ctxUi.newPage())
    await p.addInitScript(() => {
      try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
      try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
    })
    await uiLoginJusquAuxApps(p, { username: dir.nom, password: MDP_ESSAI })
    await p.goto('/chantiers/approvisionnement')
    await p.getByRole('tab', { name: "Commandes d'appel" }).click({ timeout: 60_000 })
    const chiffres = (s) => String(s).replace(/\D/g, '')
    const attendu = chiffres(Number(appel.montant).toFixed(2))
    await expect.poll(async () => chiffres(await p.getByRole('tabpanel').innerText()), { timeout: 60_000 })
      .toContain(attendu)
    await p.getByRole('tab', { name: 'Contrats de prix' }).click()
    await expect(p.getByRole('tabpanel').getByText(x.c_ref, { exact: true }).first()).toBeVisible({ timeout: 60_000 })
  } finally {
    await ctxUi.close().catch(() => undefined)
  }
})
