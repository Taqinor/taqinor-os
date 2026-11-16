// Acceptation en direct — groupe ACON, second lot (vague 6, tour 2, runner GitHub) : preuves dues d'ACON85 et ACON92.
// ACON85 : (a) ÉCRAN — l'atelier `/calepinage/<id>` (clé carte factice + style MapTiler refusé, montage d'acal4/ACAL377)
//   sur un calepinage OMBRÉ simulé : clic sur le VRAI bouton « Générer le devis » (BoutonDevis.jsx), bloc horaire rangé
//   AVEC `ombrage`, envoi par la VRAIE route (`share-link {envoi:true}` = mark_devis_sent), PDF `/proposal`, charge
//   publique et page `/proposition/<jeton>` au même kWh/an ; `simuler {forcer:true}` sur le calepinage du devis ENVOYÉ =
//   202 strict. (a bis) la sonde commitée C-ACON-020-L2 (section F) rejouée, repro=false. (b) verrou « devis accepté » 409.
// ACON92 : contenance d'un toit de 1 200 modules non bornée à 600 (fonction réelle) puis la page publique du devis qui
//   porte ce toit : le NOMBRE lu sur la carte « Max » à l'écran est ≥ 1 200.
import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, textePdf, telephoneMobileUnique, API_DJANGO as API } from '../helpers.js'

const etape = groupe('ACON', ['ACON85', 'ACON92'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 900_000 })
test.use({ viewport: { width: 1600, height: 1000 }, actionTimeout: 60_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const T = { timeout: 180_000 }
const J = JSON.stringify
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()
const chiffres = (s) => String(s).replace(/[\s  ]/g, '')
const webBase = () => {
  const w = process.env.E2E_WEB_BASE
  expect(w, 'E2E_WEB_BASE absent : apps/web (page publique) non servie').toBeTruthy()
  expect(w, 'jamais la prod').toMatch(/^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?/)
  return w.replace(/\/$/, '')
}
const STATUT_IMAGERIE = 'Imagerie satellite indisponible'

// ── ACON85 (a) — ÉCRAN « Générer le devis » sur un calepinage ombré + envoi RÉEL ──────────────────────────────
etape('PA2.ACON85-ecran-generer-devis-envoi-reel', ['ACON85'], async ({ page, context, suivi }) => {
  const m = marque()
  // Calepinage ombré (solarAccess 0,9) posé au shell ; réglages de simulation de la société posés par l'API.
  const c = await py(`import copy
from decimal import Decimal
from rest_framework.test import APIClient
from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
from apps.calepinage.tests.test_acal_multi_pans import _layout, _zone
from apps.calepinage.tests.test_calx5_simulation import REGLAGES
from apps.parametres.models import CompanyProfile
from apps.ventes.domain.geometrie import layout_hash
adm = U.objects.get(username='demo_admin'); co = adm.company
CompanyProfile.get(company=co)
api = APIClient(); api.force_authenticate(adm)
sim0 = copy.deepcopy(REGLAGES['simulation'])
for v in sim0.values():
    v['source'] = 'societe'
r = api.put('/api/django/calepinage/parametres/', {'simulation': sim0}, format='json', HTTP_HOST='localhost')
lead = Lead.objects.create(company=co, nom='ACC ACON85 ${m}', facture_hiver=Decimal('900'), ville='Casablanca', type_installation='residentiel')
lay = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
for zone in lay['zones']:
    zone['geometry']['solarAccess'] = {'values': [0.9] * zone['geometry']['count'],
        'method': {'horizon': False, 'rangees': False, 'resolution': 'annuelle', 'description': 'Accès solaire annuel'},
        'assumptions': {'periode': 'annee'}, 'computedAt': '2026-10-01T10:00:00Z'}
lay.update({'scenario': 'reseau', 'panelWatt': 710, 'result': {'panels': 24, 'kwc': 17.04}})
cal = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='ACC ACON85 ${m}', roof_layout=lay, layout_hash=layout_hash(lay))
sortie({'put': r.status_code, 'id': cal.pk, 'lead': lead.pk})`)
  expect(c.put, 'réglages de simulation de la société posés').toBeLessThan(300)
  // Atelier : clé carte factice + style MapTiler refusé (même montage qu'acal4, ACAL377).
  await context.route(new RegExp(`/calepinage/calepinages/${c.id}/design-context/`), async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: 'cle-factice-acon85', mapboxToken: null }
    await route.fulfill({ response: reelle, json: corps })
  })
  suivi.attendre(/api\.maptiler\.com/, 403)
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => route.fulfill({ status: 403, contentType: 'application/json', body: '{"message":"Invalid key"}' }))
  const ouvrir = async () => {
    await page.goto(`/calepinage/${c.id}`)
    await expect(page.getByText(STATUT_IMAGERIE).first()).toBeVisible({ timeout: 120_000 })
    await expect(page.getByRole('button', { name: 'Enregistrer le calepinage' })).toBeEnabled({ timeout: 120_000 })
  }
  await ouvrir()
  // 1. la conception est ENREGISTRÉE par l'écran (le bouton réécrit le document).
  const sauve = page.waitForResponse((x) => x.request().method() === 'POST'
    && new RegExp(`/calepinage/calepinages/${c.id}/layout/(?:$|\\?)`).test(x.url()), { timeout: 60_000 })
  await page.getByRole('button', { name: 'Enregistrer le calepinage' }).click()
  expect((await sauve).status(), 'enregistrement du calepinage : 200').toBe(200)
  // 2. simulation ombrée posée SUR le document enregistré (météo rejouée, matériel du catalogue réel).
  const sim = await py(`from apps.calepinage.models import Calepinage
from apps.calepinage.services.simulation import simuler_calepinage
from apps.calepinage.tests.test_acal_multi_pans import _ClientParOrientation
cal = Calepinage.objects.get(pk=${Number(c.id)})
try:
    simuler_calepinage(cal, client=_ClientParOrientation(), enregistrer=True)
    cal.refresh_from_db()
    sortie({'ok': True, 'sim': bool((cal.resultat or {}).get('simulation'))})
except Exception:
    import traceback
    sortie({'ok': False, 'err': traceback.format_exc()[-1500:]})`)
  expect(sim.ok, `simulation ombrée posée (${sim.err || ''})`).toBe(true)
  await ouvrir()
  // 3. LE BOUTON « Générer le devis » de l'écran.
  const bouton = page.getByTestId('cal-generer-devis')
  await expect(bouton, 'bouton « Générer le devis » présent').toBeVisible({ timeout: 60_000 })
  await expect(bouton).toHaveText('Générer le devis')
  const gen = page.waitForResponse((x) => x.request().method() === 'POST' && new RegExp(`/calepinages/${c.id}/generer-devis/`).test(x.url()), { timeout: 120_000 })
  await bouton.click()
  const rg = await gen
  const dg = await rg.json().catch(() => ({}))
  expect(rg.status(), `« Générer le devis » (bouton) : 201 (${J(dg).slice(0, 300)})`).toBe(201)
  const devisId = dg.devis?.id ?? dg.devis ?? dg.id
  expect(devisId, 'devis né').toBeTruthy()
  // L'écran quitte l'atelier vers le devis ou affiche « Ouvrir le devis ».
  await expect.poll(async () => page.url().includes(`/ventes/devis/${devisId}`) || (await page.getByText(/Ouvrir le devis/).count()) > 0, { timeout: 60_000 }).toBe(true)
  // 4. le bloc horaire RANGÉ porte l'ombrage.
  const x = await py(`from apps.ventes.models import Devis
from apps.calepinage.models import Calepinage
d = Devis.objects.get(pk=${Number(devisId)})
bloc = (d.etude_params or {}).get('etude_horaire') or {}
sortie({'lie': str(Calepinage.objects.get(pk=${Number(c.id)}).devis_id) == str(d.pk), 'ombrage': bloc.get('ombrage'),
        'prod_range': (bloc.get('annuel') or {}).get('production_kwh'), 'statut': d.statut})`)
  expect(x.lie, 'le devis né est lié au calepinage').toBe(true)
  expect(x.ombrage && typeof x.ombrage === 'object', `bloc rangé AVEC \`ombrage\` (${J(x.ombrage)})`).toBeTruthy()
  expect(Number(x.ombrage.perte_pct), 'perte d’ombrage rangée > 0').toBeGreaterThan(0)
  const prod = Number(x.prod_range)
  expect(prod, 'production annuelle rangée').toBeGreaterThan(0)
  // 5. ENVOI par la VRAIE route (celle du bouton « Envoyer » / mark_devis_sent), jamais un .update().
  const envoi = await lireJson(await page.request.post(`${API}/ventes/devis/${devisId}/share-link/`, { ...T, data: { envoi: true } }), 'envoi réel')
  expect(envoi.token, 'lien client émis par l’envoi').toBeTruthy()
  const apres = await lireJson(await page.request.get(`${API}/ventes/devis/${devisId}/`, T), 'devis envoyé')
  expect(apres.statut, 'statut « envoyé » posé par la vraie route').toBe('envoye')
  expect(apres.date_envoi, 'date_envoi posée par mark_devis_sent').toBeTruthy()
  // 6. PDF, charge publique et PAGE PUBLIQUE au même kWh/an.
  const rp = await page.request.get(`${API}/ventes/devis/${devisId}/proposal/`, T)
  expect(rp.status(), 'GET /proposal 200').toBe(200)
  expect(chiffres(await textePdf(await rp.body())), `le PDF affiche ${Math.round(prod)} kWh/an`).toContain(String(Math.round(prod)))
  const pub = await lireJson(await page.request.get(`${API}/public/proposal/${envoi.token}/data/`, T), 'charge publique')
  const prodPage = Number(pub?.dimensionnement_options?.sans?.production_annuelle_kwh)
  expect(Math.abs(prodPage - prod), `page publique ${prodPage} = bloc rangé ${prod}`).toBeLessThan(1)
  const lecteur = await context.newPage()
  for (const passage of ['ouverture', 'rechargement']) {
    if (passage === 'ouverture') await lecteur.goto(`${webBase()}/proposition/${envoi.token}`)
    else await lecteur.reload()
    await expect(lecteur.locator('body'), `(${passage}) page publique : le kWh/an rangé est affiché`)
      .toContainText(new RegExp(String(Math.round(prod)).replace(/(\d)(?=(\d{3})+$)/g, '$1[\\s\\u00a0\\u202f]?')), { timeout: 120_000 })
  }
  console.log(`[ACON85] prod rangée ${prod} ; page publique ${prodPage} ; PDF et page contiennent ${Math.round(prod)}`)
  // 7. cas « envoyé » : `simuler {forcer:true}` reste ACCEPTÉ — 202 STRICT, jamais le motif du verrou.
  const ok = await page.request.post(`${API}/calepinage/calepinages/${c.id}/simuler/`, { ...T, data: { forcer: true } })
  const corpsOk = await ok.text()
  expect(ok.status(), `calepinage d'un devis ENVOYÉ : simuler {forcer:true} = 202 (${corpsOk.slice(0, 300)})`).toBe(202)
  expect(corpsOk).not.toContain('Devis accepté')
})

// ── ACON85 (a bis) — la sonde commitée C-ACON-020-L2 rejouée (section F) ────────────────────────────────────
function sondeEnLigne(groupeSonde, constat) {
  const src = readFileSync(join(RACINE, 'docs', 'audits', 'sondes', groupeSonde, `${constat}.py`), 'utf8')
  return py(`import io, contextlib
import json as _json
from django.conf import settings
from django.db import transaction
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver', 'localhost']
class _Entier(str):
    def __getitem__(self, k):
        return str(self) if isinstance(k, slice) else str.__getitem__(self, k)
_vrai_dumps = _json.dumps
def _dumps(*a, **k):
    return _Entier(_vrai_dumps(*a, **k))
def _noop(self, *a, **k):
    return type('R', (), {'id': 'noop'})()
ns = {'__name__': '__sonde__'}
exec(compile(${J(src)}, 'sonde', 'exec'), ns)
tampon = io.StringIO()
ret, err = None, None
with mock.patch('celery.app.task.Task.apply_async', new=_noop), mock.patch('celery.app.task.Task.delay', new=_noop), \\
        mock.patch.object(_json, 'dumps', new=_dumps):
    try:
        with transaction.atomic():
            try:
                with contextlib.redirect_stdout(tampon):
                    ret = ns['sonde']({'celery': [], 'racine': '.', 'args': None})
            finally:
                transaction.set_rollback(True)
    except BaseException:
        import traceback
        err = traceback.format_exc()[-2500:]
sortie({'ret': ret, 'stdout': str(tampon.getvalue())[-200000:], 'err': err})`)
}
etape('PA2.ACON85-sonde-C-ACON-020-L2-section-F', ['ACON85'], async () => {
  const s = await sondeEnLigne('ACON', 'C-ACON-020-L2')
  expect(s.err, `sonde rejouée sans erreur : ${s.err}`).toBeNull()
  const ligne = s.stdout.split('\n').map((l) => l.trim()).filter((l) => l.startsWith('{')).pop()
  expect(ligne, 'observation imprimée par la sonde').toBeTruthy()
  const obs = JSON.parse(ligne)
  console.log(`[ACON85] sonde : ret=${J(s.ret)} F_generer_http=${obs.F_generer_http}`)
  expect(obs.F_generer_http, 'sonde F : generer-devis 201').toBe(201)
  expect(obs.F_lien, 'sonde F : devis lié').toBe(true)
  expect(obs.F1_ne_bloc_ombrage && typeof obs.F1_ne_bloc_ombrage === 'object', `sonde F : bloc rangé AVEC ombrage (${J(obs.F1_ne_bloc_ombrage)})`).toBeTruthy()
  expect(Number(obs.F1_ne_bloc_ombrage.perte_pct)).toBeGreaterThan(0)
  expect(obs.F2_pdf?.http, 'sonde F : /proposal 200').toBe(200)
  expect(Math.abs(Number(obs.F2_pdf.prod_kwh) - Number(obs.F1_ne_bloc_production_kwh)), 'sonde F : PDF = bloc rangé').toBeLessThan(1)
  expect(Math.abs(Number(obs.F2_public_production_options?.sans) - Number(obs.F1_ne_bloc_production_kwh)), 'sonde F : page = bloc rangé').toBeLessThan(1)
  expect(s.ret?.repro, 'sonde : repro=false (aucun rafraîchisseur ne périme plus la simulation)').toBe(false)
})

// ── ACON85 (b) — le verrou « devis accepté » ──────────────────────────────────────────────────────────────────
etape('PA2.ACON85-simuler_calepinage_fige_409', ['ACON85'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const x = await py(`a = U.objects.get(username='demo_admin'); co = a.company
from decimal import Decimal as D
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.calepinage.models import Calepinage
SIMULE = {'simulation': {'hash_entree': 'a' * 64, 'calcule_le': '2026-10-01T10:00:00Z'}}
cl = Client.objects.create(company=co, nom='ACC ACON85', prenom='${m}', email='acc-acon85b-${m.toLowerCase()}@example.invalid')
lead = Lead.objects.create(company=co, nom='ACC ACON85 verrou ${m}')
d = Devis.objects.create(company=co, reference='DEV-ACC-ACON85B-ACCEPTE-${m}', client=cl, lead=lead, taux_tva=D('20'))
Devis.objects.filter(pk=d.pk).update(statut=Devis.Statut.ACCEPTE)
c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='ACC ACON85 verrou ${m}', resultat=SIMULE)
Calepinage.objects.filter(pk=c.pk).update(devis=d)
sortie({'accepte': c.id})`)
  const jobs = () => py(`from core.models import BackgroundJob
sortie(BackgroundJob.objects.filter(company=U.objects.get(username='demo_admin').company).count())`)
  const avant = await jobs()
  const refus = await r.post(`${API}/calepinage/calepinages/${x.accepte}/simuler/`, { ...T, data: { forcer: true } })
  const corps = await refus.json().catch(() => ({}))
  expect(refus.status(), `simuler {forcer:true} sur un calepinage de devis accepté : 409 (${J(corps)})`).toBe(409)
  expect(J(corps.simulation), 'motif de ventes nommé sous `simulation`').toContain('Devis accepté : révisez-le')
  expect(await jobs(), 'aucun job créé par le refus').toBe(avant)
  const rec = await lireJson(await r.post(`${API}/calepinage/parametres/recalculer-simulations/`, { ...T, data: {} }), 'recalcul de masse')
  const soumis = (rec.jobs || []).map((j) => j.calepinage)
  expect(soumis, `recalcul : le calepinage du devis accepté n'est pas soumis (${J(rec).slice(0, 300)})`).not.toContain(x.accepte)
  expect(Number(rec.soumis), '`soumis` = nombre de jobs rendus').toBe(soumis.length)
  const relu = await py(`from apps.calepinage.models import Calepinage
sortie((Calepinage.objects.get(pk=${x.accepte}).resultat or {}).get('simulation', {}).get('hash_entree'))`)
  expect(relu, 'résultat du calepinage figé inchangé').toBe('a'.repeat(64))
})

// ── ACON92 — contenance d'un toit de 1 200 modules ────────────────────────────────────────────────────────────
etape('PA2.ACON92-contenance-1200', ['ACON92'], async () => {
  const o = await py(`from apps.ventes import calepinage_options as co_
from apps.ventes.tests.test_calepinage_options import toit, _DevisFactice, offres
out = {'plafond': co_._MAX_PANNEAUX_DESSINES}
for cle, (rangees, colonnes, dl, dh) in {'1200': (30, 40, 95.0, 40.0), '2400': (40, 60, 140.0, 48.0)}.items():
    layout = toit(rangees=rangees, colonnes=colonnes, demi_largeur=dl, demi_hauteur=dh)
    cap = co_.capacite_du_layout(layout)
    bloc = co_.deriver(_DevisFactice(layout), offres(recommande=rangees * colonnes, max=cap), layout)
    out[cle] = {'poses': rangees * colonnes, 'capacite': cap, 'dessines': bloc['offres']['max']['sans']['nb_panneaux_dessines']}
petit = toit(rangees=3, colonnes=6)
with mock.patch.object(co_, '_MAX_PANNEAUX_DESSINES', 600):
    avant = co_.capacite_du_layout(petit)
out['petit'] = {'apres': co_.capacite_du_layout(petit), 'avec_plafond_600': avant}
sortie(out)`)
  expect(o.plafond, 'constante _MAX_PANNEAUX_DESSINES alignée sur la visionneuse (2 000)').toBe(2000)
  expect(o['1200'].capacite, `toit de 1 200 modules : contenance ≥ 1 200, plus bornée à 600 (${J(o['1200'])})`).toBeGreaterThanOrEqual(1200)
  expect(o['1200'].capacite, 'contenance ≤ 2 000').toBeLessThanOrEqual(2000)
  expect(o['1200'].dessines, 'le dessin dit le même nombre que la contenance').toBe(o['1200'].capacite)
  expect(o['2400'].capacite, `toit de 2 400 modules : 2 000 (${J(o['2400'])})`).toBe(2000)
  expect(o['2400'].dessines, 'dessin = contenance (2 000)').toBe(2000)
  expect(o.petit.apres, 'zone de 300 extensible : inchangée').toBe(o.petit.avec_plafond_600)
})

// ── ACON92 — la carte « Max » de la page publique d'un toit de 1 200 modules ──────────────────────────────────
etape('PA2.ACON92-page-publique-max', ['ACON92'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: {
    nom: `ACC ACON92 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `acon92${m.toLowerCase()}@example.invalid`,
    type_installation: 'residentiel', facture_hiver: '3000' } }), 'lead')
  const pan = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Panneau mono 550W ACON92 ${m}`, prix_vente: '1000.00', prix_achat: '111.11' } }), 'panneau')
  const ond = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur réseau 10kW ACON92 ${m}`, prix_vente: '10000.00', prix_achat: '111.11' } }), 'onduleur')
  const ligne = (p, q, ordre) => ({ produit: p.id, designation: p.nom, quantite: String(q), prix_unitaire: p.prix_vente, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre })
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: {
    taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes: [ligne(pan, 12, 0), ligne(ond, 1, 1)] } }), 'devis')
  const x = await py(`from apps.ventes.models import Devis, ShareLink
from apps.ventes.tests.test_calepinage_options import toit
layout = toit(rangees=30, colonnes=40, demi_largeur=95.0, demi_hauteur=40.0)
Devis.objects.filter(pk=${Number(d.id)}).update(roof_layout=layout, statut='envoye')
lien = ShareLink.objects.create(company=Devis.objects.get(pk=${Number(d.id)}).company, devis=Devis.objects.get(pk=${Number(d.id)}))
sortie({'jeton': str(lien.token)})`)
  const pub = await lireJson(await r.get(`${API}/public/proposal/${x.jeton}/data/`, T), 'charge publique')
  const trouves = []
  const parcourir = (v, chemin) => {
    if (Array.isArray(v)) v.forEach((e, i) => parcourir(e, `${chemin}[${i}]`))
    else if (v && typeof v === 'object') {
      for (const [k, e] of Object.entries(v)) {
        if (typeof e === 'number' && /^nb_panneaux/.test(k) && /max/i.test(chemin)) trouves.push([`${chemin}.${k}`, e])
        else if (e && typeof e === 'object') parcourir(e, `${chemin}.${k}`)
      }
    }
  }
  parcourir(pub, 'pub')
  console.log(`[ACON92] valeurs « max » dans la charge publique : ${J(trouves).slice(0, 600)}`)
  const nb = trouves.map(([, v]) => v)
  expect(nb.length, 'la charge publique porte une taille « Max »').toBeGreaterThan(0)
  expect(Math.max(...nb), 'charge publique : Max ≥ 1 200 modules (plus bornée à 600)').toBeGreaterThanOrEqual(1200)
  // ÉCRAN : le NOMBRE lu sur la carte « Max » de la page publique.
  await page.goto(`${webBase()}/proposition/${x.jeton}`)
  const carteMax = page.locator('[data-taille-carte][data-taille-cle="max"]')
  await expect(carteMax, 'carte « Max » présente à l’écran').toHaveCount(1, { timeout: 120_000 })
  const nbEcran = carteMax.locator('[data-taille-bloc]:not([hidden]) [data-taille-panneaux-value]').first()
  await expect(nbEcran, 'nombre de panneaux de la carte « Max » lisible').toBeVisible({ timeout: 60_000 })
  const lu = Number(chiffres(await nbEcran.innerText()).replace(/\D/g, ''))
  console.log(`[ACON92] carte « Max » à l’écran : ${lu} panneaux`)
  expect(lu, 'carte « Max » AFFICHE ≥ 1 200 panneaux (plus bornée à 600)').toBeGreaterThanOrEqual(1200)
})
