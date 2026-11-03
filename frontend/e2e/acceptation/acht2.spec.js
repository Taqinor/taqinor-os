// Acceptation en direct — groupe ACHT, second lot (preuves dues ACHT124-129) + ASTK255/ASTK256.
// Format : `_format.md`. Données posées par l'API ; ce que l'API ne sait pas écrire (parc SAV
// ordre A/B) passe par `manage.py shell` (`executerDansDjango`, E2E_DJANGO_EXEC).
import { execFileSync } from 'node:child_process'
import { expect, test } from '@playwright/test'
import { groupe } from './_oracles.js'
import {
  API_DJANGO, PNG_1PX, assurerSessionPage, executerDansDjango, lireJson, uniq, telephoneMobileUnique,
} from '../helpers.js'

test.describe.configure({ timeout: 300_000 })
test.use({ viewport: { width: 1920, height: 1080 }, actionTimeout: 60_000 })
const etape = groupe('ACHT', ['ACHT124', 'ACHT125', 'ACHT126', 'ACHT127', 'ACHT128', 'ACHT129'])
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

const INST = `${API_DJANGO}/installations`
const STOCK = `${API_DJANGO}/stock`
const SIGNATURE = `data:image/png;base64,${PNG_1PX.toString('base64')}`

function py(code) {
  const m = String(executerDansDjango(code)).match(/@@JSON@@(.*)/)
  if (!m) throw new Error('sortie Django sans JSON')
  return JSON.parse(m[1])
}
async function creerClient(request) {
  return lireJson(await request.post(`${API_DJANGO}/crm/clients/`, {
    data: { nom: uniq('ACC ACHT2'), prenom: 'Acceptation', email: `${uniq('acc.acht2').toLowerCase().replace(/[^a-z0-9.]/g, '')}@example.test`, telephone: telephoneMobileUnique() },
  }), 'client')
}

// ── ACHT125 : l'ordre « relevé de série / réception » ne change pas la date du parc ────────
etape('PA5.1', ['ACHT125'], async () => {
  const r = py(`
import json
from datetime import date
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.sav.services import assurer_equipement_chantier, sweep_bom_to_parc
from apps.stock.models import Produit
co = get_user_model().objects.get(username='demo_admin').company
tag = timezone.now().strftime('%H%M%S%f')
cl = Client.objects.create(company=co, nom='ACC ACHT125', prenom=tag)
pan = Produit.objects.create(company=co, nom='Panneau ACC125 ' + tag, sku='PAN-125-' + tag, prix_achat=0, prix_vente=10, garantie_mois=120)
POSE, RECEP = date(2026, 10, 5), date(2026, 10, 12)
def chantier(ref):
    return Installation.objects.create(company=co, reference=ref + tag, client=cl, date_pose_reelle=POSE,
        bom=[{'produit_id': pan.id, 'designation': 'Panneau', 'quantite': 12}])
def balayage(c):
    return sweep_bom_to_parc(installation=c, company=co, date_pose=RECEP, created_by=None, resolve_produit={pan.id: pan}.get)
def assurer(c, serie, d):
    return assurer_equipement_chantier(company=co, installation=c, produit=pan, numero_serie=serie, quantite_ligne=12, date_pose=d, created_by=None)
def parc(c, sauf=()):
    return sorted((bool(e.numero_serie), str(e.date_pose), str(e.date_fin_garantie)) for e in
                  Equipement.objects.filter(installation=c, produit=pan).exclude(numero_serie__in=sauf))
a = chantier('CHT-ACC125A-'); balayage(a); assurer(a, 'SN-A1-' + tag, RECEP)
b = chantier('CHT-ACC125B-'); assurer(b, 'SN-B1-' + tag, POSE)
main = Equipement.objects.create(company=co, produit=pan, installation=b, numero_serie='SN-BM-' + tag, date_pose=date(2026, 9, 1))
main.recompute_garanties(); main.save(update_fields=['date_fin_garantie'])
balayage(b)
pa, pb = parc(a), parc(b, sauf=('SN-BM-' + tag,))
avant = parc(b); balayage(b)
main.refresh_from_db()
print('@@JSON@@' + json.dumps({'a': pa, 'b': pb, 'idempotent': parc(b) == avant,
      'main': [str(main.date_pose), str(main.date_fin_garantie)]}))
`)
  const attendu = [[false, '2026-10-12', '2036-10-12'], [true, '2026-10-12', '2036-10-12']]
  expect(r.a, 'ordre A').toEqual(attendu)
  expect(r.b, 'ordre B (relevé avant réception, daté de la pose réelle) : daté de la réception').toEqual(attendu)
  expect(r.main, 'date posée à la main conservée').toEqual(['2026-09-01', '2036-09-01'])
  expect(r.idempotent, 'second balayage identique').toBe(true)
})

// ── ACHT126 : re-signer un BL signé sans motif — 409 qui ne nomme aucun champ ───────────────
etape('PA5.2', ['ACHT126'], async ({ page, suivi }) => {
  const client = await creerClient(page.request)
  const inst = await lireJson(await page.request.post(`${INST}/chantiers/`, { data: { client: client.id, site_ville: 'Casablanca' } }), 'chantier')
  await lireJson(await page.request.post(`${INST}/chantiers/${inst.id}/signer-client/`, {
    data: { signature_client: SIGNATURE, signataire_nom: 'Ancien' },
  }), 'BL signé')
  const avant = await lireJson(await page.request.get(`${INST}/chantiers/${inst.id}/`), 'chantier signé')
  suivi.attendre(new RegExp(`/chantiers/${inst.id}/signer-client/`), 409)
  const r = await page.request.post(`${INST}/chantiers/${inst.id}/signer-client/`, {
    data: { signature_client: SIGNATURE, signataire_nom: 'Nouveau' },
  })
  expect(r.status()).toBe(409)
  const detail = (await r.json()).detail
  expect(detail).toMatch(/^Ce bon de livraison est déjà signé par Ancien le \d{2}\/\d{2}\/\d{4} à \d{2}:\d{2}\. Pour le signer à nouveau, indiquez un motif : il sera journalisé\.$/)
  expect(detail).not.toMatch(/motif_override_signature/)
  const apres = await lireJson(await page.request.get(`${INST}/chantiers/${inst.id}/`), 'chantier relu')
  expect(apres.signe_le, 'rien n’est écrit').toBe(avant.signe_le)
})

// ── ACHT127 : aucun départ de créneau un samedi / dimanche ──────────────────────────────────
etape('PA5.3', ['ACHT127'], async ({ page }) => {
  const client = await creerClient(page.request)
  const inst = await lireJson(await page.request.post(`${INST}/chantiers/`, { data: { client: client.id, site_ville: 'Casablanca' } }), 'chantier')
  const d = new Date()
  d.setDate(d.getDate() + ((6 - d.getDay() + 7) % 7 || 7)) // prochain samedi
  const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  for (const duree of [1, 3]) {
    const rep = await lireJson(await page.request.post(`${INST}/interventions/suggerer-creneau/`, {
      data: { chantier: inst.id, type_intervention: 'depannage', duree_jours: duree, date_cible: iso, },
    }), 'suggerer-creneau')
    const jours = (rep.propositions ?? []).map((p) => new Date(`${p.date}T12:00:00`).getDay())
    expect(jours.length, 'au moins une proposition').toBeGreaterThan(0)
    expect(jours.filter((j) => j === 0 || j === 6), `aucune date de week-end (durée ${duree})`).toEqual([])
  }
})

// ── ACHT129 : séries et lot visibles à la réouverture d'une réception ───────────────────────
async function creerBcf(request, produits) {
  const l = await lireJson(await request.get(`${STOCK}/fournisseurs/?page_size=5`), 'fournisseurs')
  const four = l.results[0].id
  const bcf = await lireJson(await request.post(`${STOCK}/bons-commande-fournisseur/`, {
    data: { fournisseur: four, date_commande: '2026-10-30', lignes: produits.map(([p, q]) => ({ produit: p.id, quantite: q, prix_achat_unitaire: '100.00' })) },
  }), 'BCF')
  await lireJson(await request.post(`${STOCK}/bons-commande-fournisseur/${bcf.id}/envoyer/`), 'envoi BCF')
  return lireJson(await request.get(`${STOCK}/bons-commande-fournisseur/${bcf.id}/`), 'BCF relu')
}
etape('PA6.1', ['ACHT129'], async ({ page, suivi }) => {
  const mk = async (extra) => lireJson(await page.request.post(`${STOCK}/produits/`, {
    data: { nom: uniq('ACC129'), prix_vente: '1000.00', prix_achat: '600.00', quantite_stock: 0, tva: '20.00', ...extra },
  }), 'produit')
  const ond = await mk({ suivi_serie: true })
  const cable = await mk({})
  const autre = await mk({})
  const bcf = await creerBcf(page.request, [[ond, 3], [cable, 10], [autre, 2]])
  const [l1, l2, l3] = bcf.lignes
  const rec = await lireJson(await page.request.post(`${STOCK}/receptions-fournisseur/`, {
    data: {
      bon_commande: bcf.id, date_reception: '2026-10-30',
      lignes: [{ ligne_commande: l1.id, quantite: 3, numeros_serie: ['S1', 'S2', 'S3'] },
        { ligne_commande: l2.id, quantite: 10, numero_lot: 'L-42' }, { ligne_commande: l3.id, quantite: 2 }],
    },
  }), 'réception')
  await lireJson(await page.request.post(`${STOCK}/receptions-fournisseur/${rec.id}/confirmer/`), 'confirmation')
  const ouvrir = async () => {
    await page.goto('/stock/receptions-fournisseur')
    await page.getByText(bcf.reference).first().click()
    const dlg = page.getByRole('dialog')
    await expect(dlg.getByText('Séries / Lot')).toBeVisible({ timeout: 30_000 })
    await expect(dlg.getByRole('row').filter({ hasText: ond.nom })).toContainText('S1, S2, S3')
    await expect(dlg.getByRole('row').filter({ hasText: cable.nom })).toContainText('Lot L-42')
    await expect(dlg.getByRole('row').filter({ hasText: autre.nom })).toContainText('—')
  }
  await ouvrir()
  await ouvrir() // persistance : relecture serveur après rechargement
  suivi.verifie(5)
})

// ── Terrain hors ligne (ACHT124, ACHT128) : patron de `adep.spec.js` (file `taqinor-field-outbox`) ──
const RESEAU = /\/api\/django\//
const jour = () => new Date().toISOString().slice(0, 10)
async function avecIntervention(page, corps, onglet) {
  const { request } = page
  const moi = (await (await request.get('/api/django/auth/me/')).json()).id
  const ch = await request.post(`${INST}/chantiers/`, { data: {} })
  expect(ch.ok(), `chantier créé (${ch.status()})`).toBeTruthy()
  const chantier = (await ch.json()).id
  const iv = await request.post(`${INST}/interventions/`, { data: {
    installation: chantier, type_intervention: 'controle', technicien: moi, date_prevue: jour(),
  } })
  expect(iv.ok(), `intervention créée (${iv.status()})`).toBeTruthy()
  const id = (await iv.json()).id
  await page.context().addInitScript(([ident, tab]) => {
    try {
      localStorage.setItem('taqinor.onboardingTerrain.anonyme', '1')
      sessionStorage.setItem('mj.activeId', String(ident))
      sessionStorage.setItem('mj.tab', tab)
    } catch { /* stockage indisponible */ }
  }, [id, onglet])
  try { await corps(id) } finally {
    await request.delete(`${INST}/interventions/${id}/`).catch(() => null)
    await request.delete(`${INST}/chantiers/${chantier}/`).catch(() => null)
  }
}
const fileLocale = (page) => page.evaluate(() => new Promise((ok) => {
  const req = indexedDB.open('taqinor-field-outbox', 1)
  req.onupgradeneeded = () => req.result.createObjectStore('ops')
  req.onsuccess = () => {
    const get = req.result.transaction('ops', 'readonly').objectStore('ops').get('queue')
    get.onsuccess = () => ok(Array.isArray(get.result) ? get.result : [])
    get.onerror = () => ok([])
  }
  req.onerror = () => ok([])
}))
const CONTENEUR = (process.env.E2E_DJANGO_EXEC || 'docker exec live2-django').split(' ').pop()
const docker = (...args) => execFileSync('docker', args, { stdio: 'pipe', timeout: 120_000 }).toString()

// ── ACHT128 : le serveur injoignable (5xx) devient visible et abandonnable au 3e rejeu ───────
etape('PA5.4', ['ACHT128'], async ({ page, context, suivi }) => {
  suivi.attendre(RESEAU)
  await avecIntervention(page, async () => {
    await page.goto('/ma-journee')
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByPlaceholder(/Réserve à reprendre/)).toBeVisible()
    await context.setOffline(true)
    const texte = uniq('ACHT128')
    await page.getByPlaceholder(/Réserve à reprendre/).fill(texte)
    await page.getByRole('button', { name: 'Ajouter la réserve' }).click()
    await expect(page.getByText('Hors ligne — enregistré').first()).toBeVisible()
    expect((await fileLocale(page)).length).toBe(1)
    docker('stop', CONTENEUR) // le proxy ne joint plus Django : 5xx sans corps JSON
    try {
      const tentatives = []
      for (let i = 1; i <= 3; i += 1) {
        await context.setOffline(false) // `online` : le flush part et reçoit le 5xx
        await expect.poll(async () => (await fileLocale(page))[0]?.attempts ?? 0, { timeout: 60_000 }).toBeGreaterThanOrEqual(i)
        const op = (await fileLocale(page))[0]
        tentatives.push({ attempts: op.attempts, serverError: op.serverError ?? null })
        if (i < 3) { await context.setOffline(true); await expect.poll(() => page.evaluate(() => navigator.onLine)).toBe(false) }
      }
      expect(tentatives[0].serverError, '1er échec : pas encore marquée').toBeNull()
      expect(tentatives[1].serverError, '2e échec : pas encore marquée').toBeNull()
      expect(tentatives[2].serverError, '3e échec : marquée, visible').toMatch(/./)
      await expect(page.getByTestId('sync-status-badge')).toHaveAttribute('data-sync-state', 'erreur', { timeout: 30_000 })
      console.log(`[ACHT128] tentatives : ${JSON.stringify(tentatives)}`)
      // Visible dans le journal terrain et abandonnable, serveur toujours arrêté.
      const indicateur = page.getByTestId('offline-sync-indicator').filter({ visible: true })
      await page.getByRole('tab', { name: 'Photos' }).click()
      await indicateur.getByRole('button', { name: /1 action\(s\) en échec/ }).click()
      await expect(indicateur.getByText(/intervention\.reserve —/)).toBeVisible()
      expect((await fileLocale(page))[0].serverError, 'persisté dans la file').toMatch(/./)
      await indicateur.getByRole('button', { name: 'Abandonner' }).first().click()
      await expect.poll(() => fileLocale(page)).toEqual([])
    } finally { docker('start', CONTENEUR) }
    await expect.poll(async () => (await page.request.get('/api/django/auth/me/').catch(() => null))?.status(), { timeout: 180_000 }).toBe(200)
  }, 'reserves')
})

// ── ACHT124 : une saisie hors ligne sur une ligne corrigée en ligne entre-temps ⇒ « conflit » ──
etape('PA5.5', ['ACHT124'], async ({ page, context, suivi }) => {
  suivi.attendre(RESEAU, 'reseau')
  await avecIntervention(page, async (id) => {
    await lireJson(await page.request.post(`${INST}/interventions/${id}/ajouter-ligne-consommation/`, {
      data: { designation: 'Câble ACC124', quantite_utilisee: '10' } }), 'ligne hors devis')
    const conso = async () => (await lireJson(await page.request.get(`${INST}/interventions/${id}/consommation/`), 'consommation'))
      .lignes.find((l) => l.designation === 'Câble ACC124')
    const T0 = await conso()
    expect(Number(T0.quantite_utilisee)).toBe(10)
    await page.goto('/ma-journee')
    await expect(page.getByRole('dialog')).toBeVisible()
    const carte = page.locator('div.rounded').filter({ hasText: 'Câble ACC124' }).first()
    const champ = carte.locator('input[type="number"]')
    await expect(champ).toHaveValue(/^10(\.0+)?$/, { timeout: 30_000 })
    // Un autre poste corrige la même ligne EN LIGNE (12) après le chargement du terminal.
    await expect.poll(() => Date.now(), { timeout: 10_000 }).toBeGreaterThan(Date.parse(T0.date_modification) + 1000) // horodatage distinct de la version lue
    await lireJson(await page.request.post(`${INST}/interventions/${id}/modifier-ligne-consommation/`, {
      data: { ligne: T0.id, quantite_utilisee: '12' } }), 'correction en ligne')
    await context.setOffline(true)
    await champ.fill('8')
    await champ.blur()
    await expect(page.getByText('Hors ligne — enregistré').first()).toBeVisible()
    const op = (await fileLocale(page))[0]
    expect(op.base_updated_at ?? op.baseUpdatedAt, 'l’op porte la date de la ligne chargée (T0)').toBeTruthy()
    await context.setOffline(false)
    await expect.poll(async () => JSON.stringify((await fileLocale(page))[0] ?? {}), { timeout: 60_000 }).toMatch(/conflit/i)
    expect(Number((await conso()).quantite_utilisee), 'la ligne garde la valeur en ligne').toBe(12)
    await page.reload()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.locator('div.rounded').filter({ hasText: 'Câble ACC124' }).first().locator('input[type="number"]')).toHaveValue(/^12(\.0+)?$/, { timeout: 30_000 })
    expect((await fileLocale(page)).length, 'l’op en conflit reste en file jusqu’à son abandon').toBe(1)
    await page.getByRole('tab', { name: 'Photos' }).click()
    const indicateur = page.getByTestId('offline-sync-indicator').filter({ visible: true })
    await indicateur.getByRole('button', { name: /1 action\(s\) en échec/ }).click()
    await indicateur.getByRole('button', { name: 'Abandonner' }).first().click()
    await expect.poll(() => fileLocale(page)).toEqual([])
  }, 'conso')
})
