// Acceptation en direct — groupe ASAV, second lot (ASAV121) : écarts de la contre-visite du
// 01/11/2026 (ASAV115-119, ASAV122) + oracle 10 `audit_coherence` réellement exécuté et tracé.
// Format : `_format.md`. S'inscrit dans le même enregistrement ASAV que `asav.spec.js` (même sha,
// même jour : `_enregistrement.ecrire` fusionne). Données posées par l'API (`page.request`) ou, pour
// ce que l'API ne sait pas écrire (horodatage SLA, date de réception), par `manage.py shell`
// (`executerDansDjango`, E2E_DJANGO_EXEC="docker exec <conteneur django>").
import { execFileSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { groupe } from './_oracles.js'
import { RACINE, aujourdHui } from './_enregistrement.js'
import {
  API_DJANGO, assurerSessionPage, executerDansDjango, isoDansJours, lireJson, uniq, telephoneMobileUnique,
} from '../helpers.js'

test.describe.configure({ timeout: 1_000_000 })
const ECRAN = { width: 1920, height: 1080 }
test.use({ viewport: ECRAN, actionTimeout: 60_000 })
const etape = groupe('ASAV', ['ASAV115', 'ASAV116', 'ASAV117', 'ASAV118', 'ASAV119', 'ASAV121', 'ASAV122'])
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

const SAV = `${API_DJANGO}/sav`
const INST = `${API_DJANGO}/installations`

/** Exécute du Python dans le conteneur Django ; renvoie le JSON imprimé après `@@JSON@@`. */
function py(code) {
  const sortie = executerDansDjango(code)
  const m = String(sortie).match(/@@JSON@@(.*)/)
  if (!m) throw new Error(`sortie Django sans JSON : ${String(sortie).slice(-400)}`)
  return JSON.parse(m[1])
}

// `audit_coherence` sur toute la société démo dépasse les 120 s de `executerDansDjango` : délai large.
function pyLong(code) {
  const [cmd, ...args] = (process.env.E2E_DJANGO_EXEC || 'docker compose exec -T django_core').split(' ')
  const sortie = execFileSync(cmd, [...args, 'python', 'manage.py', 'shell', '-c', code],
    { stdio: 'pipe', timeout: 900_000, maxBuffer: 1 << 28 }).toString()
  const m = sortie.match(/@@JSON@@(.*)/)
  if (!m) throw new Error(`sortie Django sans JSON : ${sortie.slice(-400)}`)
  return JSON.parse(m[1])
}

async function creerClient(request) {
  return lireJson(await request.post(`${API_DJANGO}/crm/clients/`, {
    data: { nom: uniq('ACC SAV2'), prenom: 'Acceptation', email: `${uniq('acc.sav2').toLowerCase().replace(/[^a-z0-9.]/g, '')}@example.test`, telephone: telephoneMobileUnique() },
  }), 'client')
}
async function creerProduit(request, extra = {}) {
  return lireJson(await request.post(`${API_DJANGO}/stock/produits/`, {
    data: { nom: uniq('ACC Onduleur2'), prix_vente: '5000.00', garantie_mois: 8, ...extra },
  }), 'produit')
}
async function creerTicket(request, corps) {
  return lireJson(await request.post(`${SAV}/tickets/`, {
    data: { type: 'correctif', priorite: 'normale', description: uniq('ACC panne2'), ...corps },
  }), 'ticket')
}
async function ajouterPiece(request, ticketId, produitId) {
  await lireJson(await request.post(`${SAV}/tickets/${ticketId}/pieces/`, { data: { produit: produitId, quantite: '1' } }), 'pièce')
}
const ficheVisible = (p) => expect(p.getByText(/Ticket SAV — SAV-/).first()).toBeVisible({ timeout: 30_000 })
async function choisir(page, declencheur, option) {
  await declencheur.click()
  await page.getByRole('option', { name: option }).first().click()
}

// ── ASAV115 : le balayage SLA retient l'échéance horodatée dépassée le jour même ────────────
etape('P115.1', ['ASAV115'], async () => {
  const r = py(`
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.crm.models import Client
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
from apps.sav.models import SavSlaSettings, Ticket
from apps.sav.tasks import scan_sla_breaches
U = get_user_model()
co = U.objects.get(username='demo_admin').company
tech = U.objects.get(username='demo_tech')
reg = SavSlaSettings.get(co)
avant = (reg.sla_breach_enabled, reg.sla_heures_ouvrees_actif)
reg.sla_breach_enabled = True
reg.sla_heures_ouvrees_actif = True
reg.save()
cl = Client.objects.create(company=co, nom='ACC115', prenom='SLA')
today = timezone.localdate()
tag = timezone.now().strftime('%H%M%S%f')
def mk(suffixe, delta):
    t = Ticket.objects.create(company=co, reference='SAV-ACC115-%s-%s' % (tag, suffixe), client=cl,
                              type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.EN_COURS,
                              date_ouverture=today, technicien_responsable=tech)
    Ticket.objects.filter(pk=t.pk).update(sla_due_at=today, sla_echeance_at=timezone.now() + delta)
    return t
t1 = mk('A', timedelta(hours=-1))
t2 = mk('B', timedelta(hours=1))
def etat():
    out = {}
    for nom, t in (('depasse', t1), ('futur', t2)):
        t.refresh_from_db()
        n = Notification.objects.filter(event_type=EventType.SAV_TICKET_BREACHING, link='/sav/tickets/%d' % t.pk).count()
        out[nom] = {'sla_breach': t.sla_breach, 'notifs': n}
    return out
scan_sla_breaches()
p1 = etat()
scan_sla_breaches()
p2 = etat()
reg.sla_breach_enabled, reg.sla_heures_ouvrees_actif = avant
reg.save()
print('@@JSON@@' + json.dumps({'p1': p1, 'p2': p2}))
`)
  expect(r.p1.depasse, '1er passage : ticket en retard signalé le jour même').toEqual({ sla_breach: true, notifs: 1 })
  expect(r.p1.futur, 'échéance future : rien').toEqual({ sla_breach: false, notifs: 0 })
  expect(r.p2, '2e passage : idempotent').toEqual(r.p1)
})

// ── ASAV116 : « sans référence » sur la vue parc ───────────────────────────────────────────
etape('P116.1', ['ASAV116'], async ({ page }) => {
  const parc = await lireJson(await page.request.get(`${API_DJANGO}/monitoring/configs/fleet/`), 'parc')
  const sans = parc.systems.filter((s) => s.sans_reference && s.pr_pct == null)
  const avec = parc.systems.filter((s) => s.pr_pct != null)
  expect(sans.length, 'au moins un système servi sans_reference').toBeGreaterThan(0)
  await page.goto('/production/parc')
  const ligne = page.getByRole('row').filter({ hasText: sans[0].reference }).first()
  await expect(ligne).toBeVisible({ timeout: 30_000 })
  await expect(ligne.getByText('sans référence')).toBeVisible()
  if (avec.length) {
    const l2 = page.getByRole('row').filter({ hasText: avec[0].reference }).first()
    await expect(l2).not.toContainText('sans référence')
  }
  await page.getByText('Cartes', { exact: true }).click()
  const carte = page.getByRole('button').filter({ hasText: sans[0].reference }).first()
  await expect(carte).toBeVisible()
  await expect(carte.getByText(/sans référence|Périmé/)).toBeVisible()
  await page.reload()
  await expect(page.getByRole('row').filter({ hasText: sans[0].reference }).first().getByText('sans référence')).toBeVisible({ timeout: 30_000 })
})

// ── ASAV117 : « À confirmer (garantie de chantier) » ───────────────────────────────────────
etape('P117.1', ['ASAV117'], async ({ page, suivi }) => {
  const client = await creerClient(page.request)
  const r = py(`
import json
from django.utils import timezone
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.dateutils import add_months
c = Client.objects.get(pk=${client.id})
today = timezone.localdate()
tag = timezone.now().strftime('%H%M%S%f')
a = Installation.objects.create(company=c.company, reference='CHT-ACC117A-' + tag, client=c,
                                date_reception=add_months(today, -3), garantie_installation_mois=24)
b = Installation.objects.create(company=c.company, reference='CHT-ACC117B-' + tag, client=c,
                                date_reception=add_months(today, -30))
print('@@JSON@@' + json.dumps({'a': a.pk, 'b': b.pk}))
`)
  const produit = await creerProduit(page.request)
  const t1 = await creerTicket(page.request, { client: client.id, installation: r.a })
  const t2 = await creerTicket(page.request, { client: client.id, installation: r.b })
  await ajouterPiece(page.request, t1.id, produit.id)
  const f1 = await lireJson(await page.request.get(`${SAV}/tickets/${t1.id}/`), 'ticket 1')
  expect(f1.sous_garantie_effectif).toBe('a_determiner')
  expect(f1.sous_garantie_effectif_display).toBe('À confirmer (garantie de chantier)')
  const f2 = await lireJson(await page.request.get(`${SAV}/tickets/${t2.id}/`), 'ticket 2')
  expect(f2.sous_garantie_effectif_display).toBe('À déterminer')
  await page.goto(`/sav?id=${t1.id}`)
  await ficheVisible(page)
  await expect(page.getByText('Sous garantie : À confirmer (garantie de chantier)').first()).toBeVisible()
  await page.reload()
  await ficheVisible(page)
  await expect(page.getByText('Sous garantie : À confirmer (garantie de chantier)').first()).toBeVisible()
  suivi.attendre(new RegExp(`/sav/tickets/${t1.id}/facturer/`), 409)
  const fact = await page.request.post(`${SAV}/tickets/${t1.id}/facturer/`, { data: {} })
  expect(fact.status(), 'facturer reste 409 (jamais facturé d’office)').toBe(409)
  // La liste SAV porte la même mention dans la colonne « Sous garantie ».
  await page.goto('/sav')
  suivi.verifie(5)
  await expect(page.getByText('À confirmer (garantie de chantier)').first()).toBeVisible({ timeout: 30_000 })
})

// ── ASAV118 : le fournisseur de la RMA se préremplit ───────────────────────────────────────
etape('P118.1', ['ASAV118'], async ({ page }) => {
  const client = await creerClient(page.request)
  const f1 = await lireJson(await page.request.post(`${API_DJANGO}/stock/fournisseurs/`, { data: { nom: uniq('ACC Fourn A') } }), 'fournisseur A')
  const f2 = await lireJson(await page.request.post(`${API_DJANGO}/stock/fournisseurs/`, { data: { nom: uniq('ACC Fourn B') } }), 'fournisseur B')
  const pAvec = await creerProduit(page.request, { fournisseur_id: f1.id })
  const pSans = await creerProduit(page.request)
  const mk = async (produit) => lireJson(await page.request.post(`${SAV}/equipements/`, {
    data: { produit: produit.id, numero_serie: uniq('ACC-RMA').replace(/\s/g, ''), date_pose: isoDansJours(-100), client_vente: client.id },
  }), 'équipement')
  const e1 = await mk(pAvec)
  const e2 = await mk(pSans)
  const lu = await lireJson(await page.request.get(`${SAV}/equipements/${e1.id}/`), 'équipement relu')
  expect(lu.produit_fournisseur, 'clé servie').toBe(f1.id)
  expect((await lireJson(await page.request.get(`${SAV}/equipements/${e2.id}/`), 'équipement 2')).produit_fournisseur).toBeNull()
  await page.goto('/sav/warranty-claims')
  const form = page.locator('form').first()
  const selEquip = form.getByRole('combobox').nth(0)
  const selFourn = form.getByRole('combobox').nth(1)
  await expect(selEquip).toBeVisible({ timeout: 30_000 })
  await choisir(page, selEquip, new RegExp(e1.numero_serie))
  await expect(selFourn).toContainText(f1.nom)
  await choisir(page, selEquip, new RegExp(e2.numero_serie))
  await expect(selFourn, 'jamais vidé d’office').toContainText(f1.nom)
  await choisir(page, selEquip, new RegExp(e1.numero_serie))
  await choisir(page, selFourn, f2.nom)
  await form.getByRole('textbox').first().fill('Panne ASAV118')
  const rep = page.waitForResponse((r) => r.url().includes('/sav/warranty-claims') && r.request().method() === 'POST')
  await form.getByRole('button', { name: /Créer/ }).click()
  const corps = await (await rep).request().postDataJSON()
  expect(Number(corps.fournisseur_id_ext), 'le choix manuel F2 l’emporte').toBe(f2.id)
  await page.reload()
  await expect(page.getByRole('row').filter({ hasText: f2.nom }).first()).toBeVisible({ timeout: 30_000 })
})

// ── ASAV119 : fin de garantie du neuf à l'écran ────────────────────────────────────────────
etape('P119.1', ['ASAV119'], async ({ page }) => {
  const client = await creerClient(page.request)
  const produit = await creerProduit(page.request, { garantie_mois: 24 })
  const serie = uniq('ACC-OLD').replace(/\s/g, '')
  const eq = await lireJson(await page.request.post(`${SAV}/equipements/`, {
    data: { produit: produit.id, numero_serie: serie, date_pose: isoDansJours(-200), client_vente: client.id },
  }), 'équipement')
  const tk = await creerTicket(page.request, { client: client.id, equipement: eq.id })
  const neuve = uniq('ACC-NEW').replace(/\s/g, '')
  await page.goto(`/sav?id=${tk.id}`)
  await ficheVisible(page)
  await choisir(page, page.getByRole('combobox', { name: 'Produit à retirer' }), new RegExp(produit.nom))
  await page.getByLabel('N° de série du neuf').locator('xpath=preceding::input[1]').fill(serie)
  await page.getByLabel('N° de série du neuf').fill(neuve)
  const rep = page.waitForResponse((r) => r.url().includes(`/sav/tickets/${tk.id}/pieces-retirees/`) && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Retirer une pièce' }).click()
  const r = await rep
  expect(r.status()).toBe(201)
  const corps = await r.json()
  expect(corps.equipement_neuf.fin_garantie, 'fin_garantie servie en ISO').toMatch(/^\d{4}-\d{2}-\d{2}$/)
  await expect(page.getByTestId('equipement-neuf')).toContainText(/garantie jusqu'au \d{2}\/\d{2}\/\d{4}/)
  const neuf = await lireJson(await page.request.get(`${SAV}/equipements/${corps.equipement_neuf.id}/`), 'équipement neuf relu')
  expect(neuf.date_fin_garantie_effective ?? neuf.date_fin_garantie).toBe(corps.equipement_neuf.fin_garantie)
})

// ── ASAV122 : un ticket antérieur au contrat ne consomme pas le déplacement inclus ─────────
etape('P122.1', ['ASAV122'], async ({ page }) => {
  const client = await creerClient(page.request)
  const produit = await creerProduit(page.request)
  const inst = await lireJson(await page.request.post(`${INST}/chantiers/`, { data: { client: client.id, site_ville: 'Casablanca' } }), 'chantier')
  const eq = await lireJson(await page.request.post(`${SAV}/equipements/`, {
    data: { produit: produit.id, numero_serie: uniq('ACC-122').replace(/\s/g, ''), date_pose: isoDansJours(-1500), installation: inst.id },
  }), 'équipement')
  const tk = (jours) => creerTicket(page.request, { client: client.id, installation: inst.id, equipement: eq.id, date_ouverture: isoDansJours(jours) })
  const t0 = await tk(-30)
  const contrat = await lireJson(await page.request.post(`${SAV}/contrats-maintenance/`, {
    data: { client: client.id, installation: inst.id, date_debut: isoDansJours(-20), duree_mois: 12, actif: true, deplacements_inclus_an: 1 },
  }), 'contrat')
  const t1 = await tk(-5)
  const t2 = await tk(-1)
  for (const t of [t0, t1, t2]) await ajouterPiece(page.request, t.id, produit.id)
  const facturer = async (t) => {
    const rep = await lireJson(await page.request.post(`${SAV}/tickets/${t.id}/facturer/`, { data: {} }), `facturer ${t.id}`)
    const f = rep.facture_id ?? rep.facture ?? (await lireJson(await page.request.get(`${SAV}/tickets/${t.id}/`), 'ticket')).facture_id_ext
    const fac = await lireJson(await page.request.get(`${API_DJANGO}/ventes/factures/${f}/`), 'facture')
    return { couverture: rep.couverture, prix: (fac.lignes ?? []).map((l) => Number(l.prix_unitaire)) }
  }
  const r1 = await facturer(t1)
  const r2 = await facturer(t2)
  expect(r1.couverture, 't1 sous contrat').toBe('contrat')
  expect(r1.prix, 't1 ligne à 0').toEqual([0])
  expect(r2.couverture, 't2 : déplacement consommé').toBe('facturable')
  expect(r2.prix).toEqual([5000])
  const c = await lireJson(await page.request.get(`${SAV}/contrats-maintenance/${contrat.id}/`), 'contrat relu')
  const droits = c.droits_restants ?? c.droits ?? c
  expect(JSON.stringify(droits)).toContain('"deplacements_consommes":2')
  await page.goto(`/sav?id=${t2.id}`)
  await ficheVisible(page)
  await expect(page.getByText('Facture générée')).toBeVisible()
})

// ── ASAV121 : oracle 10 — `audit_coherence` exécuté et tracé ───────────────────────────────
etape('P121.1', ['ASAV121', 'ASAV114'], async ({ page, suivi }) => {
  // Société démo de la pile locale (copie de la pile « live ») : elle porte déjà des avertissements
  // de documents posés par d'autres rejeux. L'oracle 10 se juge sur les documents de CE rejeu
  // (clients « ACC SAV… ») ; la sortie complète est commitée, avec le décompte du reste.
  const sortie = pyLong(`
import io, json
from contextlib import redirect_stdout
from django.contrib.auth import get_user_model
from django.core.management import call_command
from apps.ventes.models import Devis, Facture
co = get_user_model().objects.get(username='demo_admin').company
buf = io.StringIO()
with redirect_stdout(buf):
    call_command('audit_coherence', company=co.slug, json=True, no_persist=True)
data = json.loads(buf.getvalue())
def propre(v):
    if v['object_type'] == 'facture':
        return Facture.objects.filter(pk=v['object_id'], client__nom__startswith='ACC SAV').exists()
    if v['object_type'] == 'devis':
        return Devis.objects.filter(pk=v['object_id'], lead__nom__startswith='ACC SAV').exists()
    return False
propres = [v for v in data['violations'] if propre(v)]
from collections import Counter
print('@@JSON@@' + json.dumps({'company': co.pk, 'slug': co.slug, 'violations_total': len(data['violations']),
    'violations_documents_du_rejeu': propres, 'par_regle': dict(Counter(v['rule'] + '/' + v['severity'] for v in data['violations'])),
    'checked': data.get('checked'), 'sortie_complete': data}))
`)
  const dossier = join(RACINE, 'docs/qa-explorer/captures', aujourdHui())
  mkdirSync(dossier, { recursive: true })
  writeFileSync(join(dossier, 'ACCEPTATION-ASAV-audit_coherence.json'), `${JSON.stringify(sortie, null, 2)}
`, 'utf8')
  console.log(`[audit_coherence] société ${sortie.slug} — contrôlés ${JSON.stringify(sortie.checked)} — total ${sortie.violations_total} (hors rejeu) — du rejeu ${sortie.violations_documents_du_rejeu.length} — ${JSON.stringify(sortie.par_regle)}`)
  expect(sortie.violations_documents_du_rejeu, 'aucune violation sur les documents du rejeu').toEqual([])
  suivi.verifie(10)
  await page.goto('/sav')
})
