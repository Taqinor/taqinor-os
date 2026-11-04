// APRF45 — acceptation en direct de la contre-visite APRF du 04/11/2026 : export asynchrone des mouvements livré par un
// lien SERVI PAR DJANGO (APRF43 : cloche → téléchargement ; même lien au compte d'une autre société → 404) et vente
// signée en vigueur comptée au portefeuille / aux comptes dormants (APRF44). Pile locale, seuil NTPLT30 abaissé
// (`NTPLT30_EXPORT_ROW_THRESHOLD=1` sur django_core) pour forcer l'asynchrone. Données posées par l'API (dates reculées
// au shell Django pour vieillir le compte), nettoyées en fin d'étape.
import { test, expect, request as pwRequest } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout, MDP_ESSAI } from './_django.js'
import { lireJson, listeDe, telephoneMobileUnique, assurerSessionPage, connexionApi, API_DJANGO as API } from '../helpers.js'

const etape = groupe('APRF', ['APRF43', 'APRF44', 'APRF45'])
fermerDjangoApresTout()
const T = { timeout: 180_000 }
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

/** Compte admin d'essai dans une AUTRE société que demo_admin (société B). */
async function compteB(testInfo) {
  const b = await py(`a = U.objects.get(username='demo_admin')
from authentication.models import Company
co = Company.objects.exclude(pk=a.company_id).filter(users__role__isnull=False).order_by('pk').first()
modele = U.objects.filter(company=co, role__isnull=False, is_active=True).order_by('pk').first()
u = compte('aprf45_societe_b', role=modele.role_id, societe=co.pk)
sortie(dict(societe=co.pk, societe_a=a.company_id, role=modele.role_id))`)
  expect(b.societe).not.toBe(b.societe_a)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: 'aprf45_societe_b', password: MDP_ESSAI })
  return ctx
}

// ── (1)+(2) APRF43 — export xlsx depuis l'écran Mouvements, tâche Celery, lien de la cloche ; même lien au compte B ──
etape('P1.export_lien_cloche', ['APRF43', 'APRF45'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const seuil = await py(`import os
sortie(os.environ.get('NTPLT30_EXPORT_ROW_THRESHOLD'))`)
  expect(seuil, 'seuil NTPLT30 abaissé sur la pile locale').toBe('1')
  const avant = new Set(listeDe(await lireJson(await r.get(`${API}/notifications/notifications/?page_size=100`, T), 'notifications')).map((n) => n.id))
  await page.goto('/stock/mouvements')
  const bouton = page.getByRole('button', { name: /Exporter Excel/ }).first()
  await expect(bouton).toBeVisible({ timeout: 60_000 })
  const [rep] = await Promise.all([
    page.waitForResponse((x) => /\/stock\/mouvements\/export-xlsx\/?/.test(new URL(x.url()).pathname)),
    bouton.click(),
  ])
  expect(rep.status(), 'export asynchrone (202)').toBe(202)
  await expect(page.getByText(/Export en préparation/)).toBeVisible({ timeout: 30_000 })
  // La tâche Celery range le fichier et notifie : on attend la notification « Export des mouvements de stock prêt ».
  let notif = null
  await expect.poll(async () => {
    const l = listeDe(await lireJson(await r.get(`${API}/notifications/notifications/?page_size=100`, T), 'notifications'))
    notif = l.find((n) => !avant.has(n.id) && /Export des mouvements de stock prêt/.test(n.title || n.titre || ''))
    return Boolean(notif)
  }, { timeout: 180_000, intervals: [2_000] }).toBe(true)
  const lien = notif.link || notif.lien || ''
  expect(lien, `lien servi par Django (${lien})`).toMatch(/^\/api\/django\/stock\/mouvements\/telecharger-export\/[^/]+\/$/)
  expect(lien).not.toMatch(/minio|9000|X-Amz/i)
  // Le geste : la cloche → la notification → téléchargement (chargement complet du navigateur).
  await page.goto('/stock/mouvements')
  await page.getByRole('button', { name: /^Notifications \(/ }).click()
  const item = page.getByText('Export des mouvements de stock prêt').first()
  await expect(item).toBeVisible({ timeout: 30_000 })
  const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 60_000 }), item.click()])
  expect(dl.suggestedFilename()).toBe('mouvements-stock.xlsx')
  const chemin = await dl.path()
  const octets = readFileSync(chemin)
  expect(octets.subarray(0, 2).toString('latin1'), 'fichier xlsx (zip PK)').toBe('PK')
  expect(octets.length).toBeGreaterThan(1000)
  // Persistance : relu par l'API ⇒ 200, mêmes octets ; le SignedDownload garde sa clé exports/<société>/<job>.xlsx, 24 h.
  const relu = await r.get(lien, T)
  expect(relu.status()).toBe(200)
  expect((relu.headers()['content-disposition'] || '')).toContain('mouvements-stock.xlsx')
  expect(Buffer.compare(Buffer.from(await relu.body()), octets)).toBe(0)
  const jeton = lien.split('/').filter(Boolean).pop()
  const sd = await py(`from core.models import SignedDownload
s = SignedDownload.objects.get(token='${jeton}')
sortie(dict(cle=s.object_key, societe=s.company_id, heures=round((s.expires_at - s.created_at).total_seconds() / 3600, 1) if getattr(s, 'expires_at', None) and getattr(s, 'created_at', None) else None))`)
  expect(sd.cle).toMatch(new RegExp(`^exports/${sd.societe}/\\d+\\.xlsx$`))
  if (sd.heures !== null) expect(sd.heures).toBeCloseTo(24, 0)
  // (2) Le même lien au compte de la société B ⇒ 404.
  const b = await compteB(testInfo)
  suivi.attendre(/telecharger-export/, 404)
  const autre = await b.get(lien, T)
  expect(autre.status(), 'société B : 404').toBe(404)
  await b.dispose()
})

// ── (3) APRF44 — V1 acceptée révisée en V2 brouillon : « Mon portefeuille » et « Comptes dormants » ──────────────────
etape('P3.vente_en_vigueur_portefeuille_dormants', ['APRF44', 'APRF45'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const moi = await lireJson(await r.get(`${API}/auth/me/`, T), 'moi')
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `APRF44 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid`, type_installation: 'residentiel', facture_hiver: '1200', ...(moi?.id ? { owner: moi.id } : {}) } }), 'lead')
  const pan = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Panneau mono 550W APRF44 ${m}`, prix_vente: '1000.00', prix_achat: '321.09' } }), 'panneau')
  const ond = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur réseau 6kW APRF44 ${m}`, prix_vente: '9000.00', prix_achat: '321.09' } }), 'onduleur')
  const L = (p, q, pu, o) => ({ produit: p.id, designation: p.nom, quantite: q, prix_unitaire: pu, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: o })
  const v1 = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes: [L(pan, '10', '1000.00', 0), L(ond, '1', '9000.00', 1)] } }), 'V1')
  let v2 = null
  try {
    await lireJson(await r.post(`${API}/ventes/devis/${v1.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi V1')
    await lireJson(await r.post(`${API}/ventes/devis/${v1.id}/accepter/`, { ...T, data: { nom: 'Client APRF44' } }), 'V1 acceptée')
    v2 = await lireJson(await r.post(`${API}/ventes/devis/${v1.id}/reviser/`, T), 'révision V2')
    const v1lu = await lireJson(await r.get(`${API}/ventes/devis/${v1.id}/`, T), 'V1 relue')
    expect([v1lu.statut, v1lu.is_active, v2.statut]).toEqual(['accepte', false, 'brouillon'])
    const clientId = v1lu.client
    // Le compte a vieilli : V1 il y a 200 jours, activités du lead aussi (le seul moyen de jouer un compte dormant aujourd'hui).
    const info = await py(`import datetime
from django.utils import timezone
from apps.ventes.models import Devis
from apps.crm.models import LeadActivity, Lead
vieux = timezone.now() - datetime.timedelta(days=200)
Devis.objects.filter(pk=${v1.id}).update(date_creation=vieux)
LeadActivity.objects.filter(lead_id=${lead.id}).update(created_at=vieux)
try:
    from apps.crm.models import PointContact
    PointContact.objects.filter(lead_id=${lead.id}).delete()
except Exception:
    pass
sortie(dict(date_v1=str(vieux.date())))`)
    // « Comptes dormants » (API de l'écran + widget).
    const dorm = listeDe(await lireJson(await r.get(`${API}/crm/clients/dormants/?seuil=90&page_size=500`, T), 'dormants'))
    const entree = dorm.find((e) => (e.client?.id ?? e.client_id ?? e.id) === clientId)
    expect(entree, `client présent aux comptes dormants (vente en vigueur comptée) — ${dorm.length} lignes`).toBeTruthy()
    expect(String(entree.derniere_activite).slice(0, 10), 'dernière activité = date de la V1 en vigueur').toBe(info.date_v1)
    // « Mon portefeuille » : la V1 acceptée compte (1 devis actif, 1 accepté) ; score servi = calcul unitaire.
    const porte = listeDe(await lireJson(await r.get(`${API}/crm/clients/mon-portefeuille/`, T), 'portefeuille'))
    const ligneP = porte.find((e) => e.client_id === clientId)
    expect(ligneP, `client au portefeuille du commercial (${porte.length} lignes)`).toBeTruthy()
    const sig = await py(`from django.utils import timezone
from authentication.models import Company
from apps.crm.models import Client
from apps.crm.engagement import _signaux_pour_clients, compute_engagement_score
c = Client.objects.get(pk=${clientId})
s = _signaux_pour_clients(c.company_id, [c.pk], timezone.now())[c.pk]
sortie(dict(actifs=s['d_actifs'], acceptes=s['d_acceptes'], score=compute_engagement_score(c)))`)
    expect([sig.actifs, sig.acceptes], 'la V1 en vigueur compte un devis accepté').toEqual([1, 1])
    expect(ligneP.score, 'score du portefeuille = calcul unitaire').toBe(sig.score)
    // Écran : cockpit CRM (widgets « Comptes dormants » et « Mon portefeuille »).
    await page.goto('/crm/cockpit')
    await expect(page.getByTestId('dormant-accounts-widget')).toBeVisible({ timeout: 60_000 })
    // Persistance : relu ⇒ identique.
    await page.reload()
    const dorm2 = listeDe(await lireJson(await r.get(`${API}/crm/clients/dormants/?seuil=90&page_size=500`, T), 'dormants relus'))
    expect(dorm2.some((e) => (e.client?.id ?? e.client_id ?? e.id) === clientId)).toBe(true)
  } finally {
    if (v2) await r.delete(`${API}/ventes/devis/${v2.id}/`, T).catch(() => null)
    await r.patch(`${API}/ventes/devis/${v1.id}/`, { ...T, data: { is_active: false } }).catch(() => null)
    await r.delete(`${API}/crm/leads/${lead.id}/`, T).catch(() => null)
  }
})
