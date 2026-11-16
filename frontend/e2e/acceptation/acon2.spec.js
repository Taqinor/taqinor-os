// Acceptation en direct — groupe ACON, second lot (vague 6, runner GitHub) : preuves dues d'ACON85 et ACON92.
// ACON85 : (a) « Générer le devis » (route POST calepinage/calepinages/<id>/generer-devis/ — le bouton écran enregistre
//   d'abord la conception du constructeur 3D, qui ne boote pas sans clé de fond de carte : même route que lui) sur un
//   calepinage simulé OMBRÉ → le bloc horaire RANGÉ porte `ombrage {perte_pct}` ; puis envoi, PDF `/proposition`…
//   `/proposal` et PAGE PUBLIQUE `/proposition/<jeton>` (apps/web servie par le runner) affichent le MÊME kWh/an ;
//   (b) verrou : `simuler {forcer:true}` sur le calepinage d'un devis ACCEPTÉ = 409 nommé, aucun job, recalcul de masse
//   qui ne le soumet pas ; calepinage d'un devis ENVOYÉ inchangé.
// ACON92 : contenance d'un toit de 1 200 modules non bornée à 600 (fonction réelle, données persistées) puis la page
//   publique du devis qui porte ce toit.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, textePdf, telephoneMobileUnique, API_DJANGO as API } from '../helpers.js'

const etape = groupe('ACON', ['ACON85', 'ACON92'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 900_000 })
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

// ── ACON85 (a) — « Générer le devis » sur un calepinage simulé ombré ──────────────────────────────────────────
etape('PA2.ACON85-generer_devis_ombre_pdf_page', ['ACON85'], async ({ page }) => {
  const m = marque()
  // Montage = celui de la sonde commitée C-ACON-020-L2 (section F), PERSISTÉ dans la société de demo_admin ; le geste
  // « Générer le devis » est l'appel HTTP réel (client DRF connecté en demo_admin), matériel de simulation injecté.
  const x = await py(`import copy, json
from decimal import Decimal
from unittest import mock
from rest_framework.test import APIClient
from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
from apps.calepinage.services.simulation import simuler_calepinage
from apps.calepinage.tests.test_acal_multi_pans import _ClientParOrientation, _layout, _zone
from apps.calepinage.tests.test_calx5_simulation import MATERIEL, REGLAGES
from apps.parametres.models import CompanyProfile
from apps.ventes.domain.geometrie import layout_hash
from apps.ventes.models import Devis, ShareLink
adm = U.objects.get(username='demo_admin'); co = adm.company
CompanyProfile.get(company=co)
H = {'HTTP_HOST': 'localhost'}
api = APIClient(); api.force_authenticate(adm)
sim0 = copy.deepcopy(REGLAGES['simulation'])
for v in sim0.values():
    v['source'] = 'societe'
r = api.put('/api/django/calepinage/parametres/', {'simulation': sim0}, format='json', **H)
lead = Lead.objects.create(company=co, nom='ACC ACON85 ${m}', facture_hiver=Decimal('900'), ville='Casablanca', type_installation='residentiel')
lay = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
for zone in lay['zones']:
    zone['geometry']['solarAccess'] = {'values': [0.9] * zone['geometry']['count'],
        'method': {'horizon': False, 'rangees': False, 'resolution': 'annuelle', 'description': 'Accès solaire annuel'},
        'assumptions': {'periode': 'annee'}, 'computedAt': '2026-10-01T10:00:00Z'}
lay.update({'scenario': 'reseau', 'panelWatt': 710, 'result': {'panels': 24, 'kwc': 17.04}})
c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='ACC ACON85 ${m}', roof_layout=lay, layout_hash=layout_hash(lay))
with mock.patch('apps.calepinage.services.electrique.resoudre_materiel', return_value=MATERIEL):
    simuler_calepinage(c, client=_ClientParOrientation(), materiel=MATERIEL, enregistrer=True)
    rg = api.post('/api/django/calepinage/calepinages/%s/generer-devis/' % c.pk, {}, format='json', **H)
dg = getattr(rg, 'data', None) or {}
did = dg.get('id') if isinstance(dg, dict) else None
if did is None and isinstance(dg, dict) and isinstance(dg.get('devis'), (int, str)):
    did = dg.get('devis')
if did is None and isinstance(dg, dict) and isinstance(dg.get('devis'), dict):
    did = dg['devis'].get('id')
out = {'put': r.status_code, 'generer_http': rg.status_code, 'corps': str(dg)[:300] if not did else '', 'calepinage': c.pk, 'lead': lead.pk}
if did:
    d = Devis.objects.get(pk=did)
    bloc = (d.etude_params or {}).get('etude_horaire') or {}
    Devis.objects.filter(pk=d.pk).update(statut='envoye')
    lien = ShareLink.objects.create(company=co, devis=Devis.objects.get(pk=d.pk))
    out.update(devis=d.pk, lie=str(Calepinage.objects.get(pk=c.pk).devis_id) == str(d.pk), ombrage=bloc.get('ombrage'),
               prod_range=(bloc.get('annuel') or {}).get('production_kwh'), jeton=str(lien.token))
sortie(out)`)
  expect(x.put, 'réglages de simulation de la société posés').toBeLessThan(300)
  expect(x.generer_http, `« Générer le devis » : 201 (${x.corps})`).toBe(201)
  expect(x.lie, 'le devis né est lié au calepinage').toBe(true)
  // Le bloc horaire RANGÉ porte l'ombrage du calepinage (perte non nulle).
  expect(x.ombrage && typeof x.ombrage === 'object', `bloc rangé AVEC \`ombrage\` (${J(x.ombrage)})`).toBeTruthy()
  expect(Number(x.ombrage.perte_pct), 'perte d’ombrage rangée > 0').toBeGreaterThan(0)
  const prod = Number(x.prod_range)
  expect(prod, 'production annuelle rangée').toBeGreaterThan(0)
  // PDF /proposal.
  const rp = await page.request.get(`${API}/ventes/devis/${x.devis}/proposal/`, T)
  expect(rp.status(), 'GET /proposal 200').toBe(200)
  const textePDF = chiffres(await textePdf(await rp.body()))
  expect(textePDF, `le PDF affiche la production annuelle ${Math.round(prod)} kWh/an`).toContain(String(Math.round(prod)))
  // Charge publique : la production de l'option « sans » = le bloc rangé, au kWh près.
  const pub = await lireJson(await page.request.get(`${API}/public/proposal/${x.jeton}/data/`, T), 'charge publique')
  const prodPage = Number(pub?.dimensionnement_options?.sans?.production_annuelle_kwh)
  expect(Math.abs(prodPage - prod), `page publique ${prodPage} = bloc rangé ${prod}`).toBeLessThan(1)
  // ÉCRAN — la page publique (apps/web) AFFICHE le même kWh/an que le PDF ; persistance : rechargement.
  for (const passage of ['ouverture', 'rechargement']) {
    if (passage === 'ouverture') await page.goto(`${webBase()}/proposition/${x.jeton}`)
    else await page.reload()
    await expect(page.locator('body'), `(${passage}) page publique : le kWh/an rangé est affiché`)
      .toContainText(new RegExp(String(Math.round(prod)).replace(/(\d)(?=(\d{3})+$)/g, '$1[\\s\\u00a0\\u202f]?')), { timeout: 120_000 })
  }
  const corpsPage = chiffres(await page.locator('body').innerText())
  expect(corpsPage, 'page = PDF = bloc rangé').toContain(String(Math.round(prod)))
  console.log(`[ACON85] prod rangée ${prod} ; page publique ${prodPage} ; PDF contient ${Math.round(prod)}`)
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
out = {}
for cle, statut in (('accepte', Devis.Statut.ACCEPTE), ('envoye', Devis.Statut.ENVOYE)):
    d = Devis.objects.create(company=co, reference='DEV-ACC-ACON85B-%s-${m}' % cle.upper(), client=cl, lead=lead, taux_tva=D('20'))
    Devis.objects.filter(pk=d.pk).update(statut=statut)
    c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='ACC ACON85 verrou %s ${m}' % cle, resultat=SIMULE)
    Calepinage.objects.filter(pk=c.pk).update(devis=d)
    out[cle] = c.id
sortie(out)`)
  const jobs = () => py(`from core.models import BackgroundJob
sortie(BackgroundJob.objects.filter(company=U.objects.get(username='demo_admin').company).count())`)
  const avant = await jobs()
  const refus = await r.post(`${API}/calepinage/calepinages/${x.accepte}/simuler/`, { ...T, data: { forcer: true } })
  const corps = await refus.json().catch(() => ({}))
  expect(refus.status(), `simuler {forcer:true} sur un calepinage de devis accepté : 409 (${J(corps)})`).toBe(409)
  expect(J(corps.simulation), 'motif de ventes nommé sous `simulation`').toContain('Devis accepté : révisez-le')
  expect(await jobs(), 'aucun job créé par le refus').toBe(avant)
  const ok = await r.post(`${API}/calepinage/calepinages/${x.envoye}/simuler/`, { ...T, data: { forcer: true } })
  const corpsOk = await ok.text()
  expect([202, 409], `devis envoyé : simuler (${corpsOk.slice(0, 300)})`).toContain(ok.status())
  expect(corpsOk, 'devis envoyé : jamais le motif du verrou').not.toContain('Devis accepté')
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
  // Toute valeur `nb_panneaux*` portée par un objet « max » du bloc des tailles / du calepinage publié.
  const trouves = []
  const parcourir = (v, chemin) => {
    if (Array.isArray(v)) v.forEach((e, i) => parcourir(e, `${chemin}[${i}]`))
    else if (v && typeof v === 'object') {
      for (const [k, e] of Object.entries(v)) {
        if (typeof e === 'number' && /^nb_panneaux/.test(k) && /max/i.test(chemin)) trouves.push([`${chemin}.${k}`, e])
        else if (e && typeof e === 'object') parcourir(e, `${chemin}.${k}`)
        else if (k === 'cle' && e === 'max') trouves.push([`${chemin}.cle`, 'max'])
      }
    }
  }
  parcourir(pub, 'pub')
  console.log(`[ACON92] valeurs « max » dans la charge publique : ${J(trouves).slice(0, 600)}`)
  const nb = trouves.filter(([, v]) => typeof v === 'number').map(([, v]) => v)
  expect(nb.length, `la charge publique porte une taille « Max » (${J(Object.keys(pub)).slice(0, 400)})`).toBeGreaterThan(0)
  expect(Math.max(...nb), 'carte « Max » ≥ 1 200 modules (plus bornée à 600)').toBeGreaterThanOrEqual(1200)
  // ÉCRAN : la page publique est ouverte et affiche l'installation.
  await page.goto(`${webBase()}/proposition/${x.jeton}`)
  await expect(page.locator('body')).toContainText(/Max/, { timeout: 120_000 })
})
