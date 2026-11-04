// AANA74 (suite du rejeu partiel du 04/11) — étapes (2) lignes d'import rapportées, (3) avoir total, (5) un classement et une vente
// par révision, (7) compte de la société B. Deux sociétés propres posées par le shell (même patron que `traces/2026-11-01/scripts/
// setup.py.txt`) ; les gestes passent par les vraies routes, au login réel.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage } from '../helpers.js'

const etape = groupe('AANA', ['AANA74'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const MDP = 'Acc-Aana74-0411!'
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

const m = `${Date.now().toString(36)}`
let cache = null
async function societes(testInfo) {
  if (cache) return cache
  const s = await py(`from decimal import Decimal
from authentication.models import Company
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS, COMMERCIAL_PERMISSIONS
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture
sor = {}
for k in ('a', 'b'):
    co = Company.objects.create(slug=f'acc74-${m}-{k}', nom=f'ACC74 ${m} {k}')
    rd = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
    rc = Role.objects.create(company=co, nom='Commercial', permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
    dir_ = U.objects.create_user(username=f'acc74d_${m}_{k}', password=${JSON.stringify(MDP)}, company=co, role=rd, role_legacy='admin', email=f'd${m}{k}@example.invalid')
    com = U.objects.create_user(username=f'acc74c_${m}_{k}', password=${JSON.stringify(MDP)}, company=co, role=rc, role_legacy='normal', email=f'c${m}{k}@example.invalid')
    sor[k] = dict(co=co.pk, dir=dir_.username, com=com.username, com_id=com.pk)
    if k == 'b':
        continue
    cl = Client.objects.create(company=co, nom='Cli ACC74', prenom='X', email=f'cl${m}@example.invalid')
    p = Produit.objects.create(company=co, sku='ACC74-KIT', nom='Kit ACC74', prix_vente=Decimal('1000'), quantite_stock=0)
    f = Facture.objects.create(company=co, reference='FAC-ACC74-A1', client=cl, statut='emise', taux_tva=Decimal('20.00'))
    LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('1000'), remise=Decimal('0'), taux_tva=Decimal('20.00'))
    sor[k]['facture'] = f.pk
    jour = timezone.localdate() - datetime.timedelta(days=2)
    lead = Lead.objects.create(company=co, nom='ACC74 signe', stage='SIGNED', canal='meta_ads', owner=com)
    d1 = Devis.objects.create(company=co, reference='DEV-ACC74-LEAD', client=cl, lead=lead, statut='accepte', date_acceptation=jour, created_by=com)
    LigneDevis.objects.create(devis=d1, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
    d2 = Devis.objects.create(company=co, reference='DEV-ACC74-SANS', client=cl, statut='accepte', date_acceptation=jour, created_by=com)
    LigneDevis.objects.create(devis=d2, produit=p, designation='Kit', quantite=Decimal('2'), prix_unitaire=Decimal('1000'))
    sor[k].update(d1=d1.pk, debut=(jour - datetime.timedelta(days=5)).isoformat(), fin=timezone.localdate().isoformat())
sortie(sor)`)
  const ctx = async (user) => {
    const c = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
    await connexionApi(c, { username: user, password: MDP })
    return c
  }
  cache = { ...s, da: await ctx(s.a.dir), db: await ctx(s.b.dir) }
  return cache
}
const fichier = (nom, contenu) => ({ name: nom, mimeType: 'text/csv', buffer: Buffer.from(contenu, 'utf-8') })

etape('P2.imports_rapportes', ['AANA74'], async ({ testInfo }) => {
  const { da } = await societes(testInfo)
  const csv = 'Nom,SKU,Prix\nACC74 P1,ACC74-I1,12.345\nACC74 P2,ACC74-I2,"12,345"\nACC74 P3,ACC74-I3,99999999.999\nACC74 P4,ACC74-I4,12.34\n'
  const c = await lireJson(await da.post(`${API}/imports/commit/`, { ...T, multipart: { target: 'products', file: fichier('p.csv', csv) } }), 'commit produits')
  expect(JSON.stringify(c), `lignes rapportées : ${JSON.stringify(c).slice(0, 400)}`).toMatch(/2 d[ée]cimales/)
  const liste = await lireJson(await da.get(`${API}/stock/produits/?search=ACC74-I&page_size=50`, T), 'produits relus')
  const relus = Object.fromEntries((liste.results ?? liste).map((p) => [p.sku, Number(p.prix_vente)]))
  expect(relus, 'rien d\'arrondi : seule la ligne à 2 décimales entre').toEqual({ 'ACC74-I4': 12.34 })
  // Colonne montant_ttc : jamais importée.
  const ap = await lireJson(await da.post(`${API}/imports/dry-run/`, { ...T, multipart: { target: 'factures', file: fichier('f.csv', 'reference,client_nom,statut,montant_ttc\nFAC-IMP,Cli,emise,1200\n') } }), 'aperçu factures')
  expect(JSON.stringify(ap.non_mappees ?? ap), 'montant_ttc non mappée').toContain('montant_ttc')
  // Relevé : mode « traite » et montant à 3 décimales rapportés, aucun paiement.
  const jour = new Date().toISOString().slice(0, 10)
  const dry = await lireJson(await da.post(`${API}/ventes/paiements/import-releve/dry-run/`, { ...T, multipart: { file: fichier('r.csv', `date;reference;montant;mode\n${jour};FAC-ACC74-A1;100.555;virement\n${jour};FAC-ACC74-A1;100.00;traite\n`) } }), 'aperçu relevé')
  const statuts = dry.preview.map((l) => l.statut)
  expect(statuts.includes('a_importer') ? JSON.stringify(dry.preview) : '', `chaque ligne rapportée, rien d'importable : ${JSON.stringify(dry.preview).slice(0, 400)}`).toBe('')
  const nb = await py(`from apps.ventes.models import Paiement, Facture
sortie(Paiement.objects.filter(facture__reference='FAC-ACC74-A1').count())`)
  expect(nb, 'rien écrit').toBe(0)
})

etape('P3.avoir_total', ['AANA74'], async ({ testInfo }) => {
  const { da, a } = await societes(testInfo)
  const kpi = async () => (await lireJson(await da.get(`${API}/reporting/dashboard/`, T), 'tableau')).kpis
  const avant = await kpi()
  expect(Number(avant.ca_attente), 'témoin : la facture est en attente').toBe(1000)
  await lireJson(await da.post(`${API}/ventes/factures/${a.facture}/creer-avoir/`, { ...T, data: { motif: 'Annulation ACC74' } }), 'avoir total')
  for (const lecture of [await kpi(), await kpi()]) {
    expect(Number(lecture.ca_paye), 'CA encaissé 0').toBe(0)
    expect(Number(lecture.ca_attente), 'en attente 0').toBe(0)
  }
})

etape('P5.classement_revision', ['AANA74'], async ({ testInfo }) => {
  const { da, a } = await societes(testInfo)
  const q = `?from=${a.debut}&to=${a.fin}`
  const lire = async () => {
    const cd = await lireJson(await da.get(`${API}/reporting/commercial/dashboard/${q}`, T), 'commercial')
    const lb = await lireJson(await da.get(`${API}/reporting/insights/sales-leaderboard/${q}`, T), 'classement')
    return { cd: cd.leaderboard, lb: lb.rows }
  }
  const trouve = (l) => (l || []).find((x) => JSON.stringify(x).includes(a.com))
  const av = await lire()
  const ca = (x) => Number(x?.ca_ht ?? x?.ca ?? x?.total_ht ?? x?.ca_signe ?? x?.montant)
  expect(ca(trouve(av.cd)), `écran : 3 000 HT (${JSON.stringify(av.cd).slice(0, 200)})`).toBe(3000)
  expect(ca(trouve(av.lb)), `export : 3 000 HT (${JSON.stringify(av.lb).slice(0, 200)})`).toBe(3000)
  // Révision en brouillon : la V1 en vigueur reste comptée, le brouillon jamais, une seule vente.
  await lireJson(await da.post(`${API}/ventes/devis/${a.d1}/reviser/`, { ...T, data: {} }), 'révision V2 brouillon')
  const ap = await lire()
  expect(ca(trouve(ap.cd)), 'écran inchangé après révision en brouillon').toBe(3000)
  expect(ca(trouve(ap.lb)), 'export inchangé après révision en brouillon').toBe(3000)
  const attr = await lireJson(await da.get(`${API}/crm/rapports/attribution/`, T), 'attribution')
  const lc = (attr.par_commercial || []).find((x) => x.commercial === a.com)
  expect(Number(lc?.ca_signe), `attribution : V1 gardée (${JSON.stringify(attr.par_commercial).slice(0, 200)})`).toBe(1000)
})

etape('P7.societe_b', ['AANA74'], async ({ testInfo }) => {
  const { db, a } = await societes(testInfo)
  const tab = await lireJson(await db.get(`${API}/reporting/dashboard/`, T), 'tableau B')
  expect([Number(tab.kpis.ca_paye), Number(tab.kpis.ca_attente)], 'B : 0 / 0').toEqual([0, 0])
  const lb = await lireJson(await db.get(`${API}/reporting/insights/sales-leaderboard/?from=${a.debut}&to=${a.fin}`, T), 'classement B')
  expect(JSON.stringify(lb), 'rien de A').not.toContain(a.com)
  const cd = await lireJson(await db.get(`${API}/reporting/commercial/dashboard/`, T), 'commercial B')
  expect(JSON.stringify(cd), 'rien de A').not.toContain(a.com)
  const pr = await lireJson(await db.get(`${API}/stock/produits/?search=ACC74-`, T), 'produits B')
  expect((pr.results ?? pr).length, 'aucun produit de A').toBe(0)
  expect((await db.get(`${API}/ventes/factures/${a.facture}/`, T)).status(), 'facture de A : 404').toBe(404)
})
