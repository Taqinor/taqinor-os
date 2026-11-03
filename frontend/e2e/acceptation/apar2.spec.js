// APAR — 2e spec d'acceptation en direct : libellé « Premiers pas » (APAR86), e-mail sans lien (APAR83), {lien_rdv}
// du WhatsApp de devis (APAR84), rejeu APAR90 : conflit de profil à deux navigateurs (APAR74), 250 produits aux kits
// (APAR78), cartes de taille au taux société 14 % (APAR79), blur Sécurité & terrain (APAR82). EMAIL_BACKEND console :
// aucun envoi réel, l'e-mail se relit dans EmailLog. Données posées par l'API, profil rétabli à la fin.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import {
  lireJson, listeDe, telephoneMobileUnique, connexionApi, assurerSessionPage,
} from '../helpers.js'

const etape = groupe('APAR', ['APAR86', 'APAR83', 'APAR84', 'APAR74', 'APAR78', 'APAR79', 'APAR82', 'APAR89'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.beforeEach(async ({ page }, testInfo) => {
  testInfo.setTimeout(420_000)
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const nouveauLead = async (request, nom, extra = {}) => lireJson(await request.post(`${API}/crm/leads/`, {
  ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${marque()}@example.invalid`, ...extra },
}), 'lead')
const profil = async (r) => lireJson(await r.get(`${API}/parametres/`, T), 'profil')

async function factureEmise(request, tag) {
  const lead = await nouveauLead(request, `APAR ${tag} ${marque()}`)
  const p = await lireJson(await request.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ${tag} ${marque()}`, prix_vente: '1000.00', prix_achat: '321.00' } }), 'produit')
  const d = await lireJson(await request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] },
  }), 'devis')
  await lireJson(await request.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await request.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client essai' } }), 'accepter')
  const f = await lireJson(await request.post(`${API}/ventes/devis/${d.id}/facturer/`, { ...T, data: { nature: 'acompte', emettre: true } }), 'facture')
  return { lead, d, facture: f.facture }
}

// ── APAR86 — base migrée avant APAR52 puis `migrate` : l'accueil dit « Envoyer votre 1er devis » ─────
etape('PAR.onboarding_libelle', ['APAR86'], async ({ page, suivi }) => {
  const avant = await py(`from django.core.management import call_command
from apps.onboarding.models import OnboardingChecklistItem as I
call_command('migrate', 'onboarding', '0007', verbosity=0)
I.objects.filter(key='premier_devis').update(libelle='Créer votre 1er devis')
a = list(I.objects.filter(key='premier_devis').values_list('libelle', flat=True))
call_command('migrate', 'onboarding', verbosity=0)
sortie({'a': a, 'b': list(I.objects.filter(key='premier_devis').values_list('libelle', flat=True))})`)
  expect(avant.a[0], 'avant la migration : ancien libellé').toBe('Créer votre 1er devis')
  expect(avant.b[0], 'après : nouveau libellé').toBe('Envoyer votre 1er devis')
  await expect.poll(async () => (await page.request.get(`${API}/auth/me/`, { timeout: 20_000 }).catch(() => ({ status: () => 0 }))).status(),
    { timeout: 180_000, intervals: [2_000, 5_000] }).toBe(200)
  const prog = await lireJson(await page.request.get(`${API}/onboarding/progress/`, T), 'progression')
  expect(JSON.stringify(prog), 'servi par l\'API').toContain('Envoyer votre 1er devis')
  expect(JSON.stringify(prog)).not.toContain('Créer votre 1er devis')
  await page.goto('/dashboard')
  const widget = page.getByText(/Premiers pas/).first()
  if (await widget.isVisible({ timeout: 45_000 }).catch(() => false)) {
    if (!(await page.getByText('Envoyer votre 1er devis').count())) await widget.click().catch(() => undefined)
    await expect(page.getByText('Envoyer votre 1er devis').first(), 'accueil › Premiers pas').toBeVisible({ timeout: 30_000 })
  }
  suivi.verifie(5)
})

// ── APAR83 — modèle Facture réinitialisé : plus de « au lien suivant : » suivi de rien ───────────────
etape('PAR.email_sans_lien', ['APAR83'], async ({ page, suivi }) => {
  const r = page.request
  const eff = await lireJson(await r.get(`${API}/parametres/email-templates/effective/`, T), 'modèles')
  const modele = listeDe(eff).find((x) => x.cle === 'facture')
  const relance = listeDe(eff).find((x) => x.cle === 'relance')
  expect(modele?.corps_defaut, 'le défaut existe').toBeTruthy()
  await lireJson(await r.put(`${API}/parametres/email-templates/bulk/`, { ...T, data: { templates: [
    { cle: 'facture', sujet: modele.sujet_defaut, corps: modele.corps_defaut },
    ...(relance ? [{ cle: 'relance', sujet: relance.sujet_defaut, corps: relance.corps_defaut }] : []),
  ] } }), 'réinitialiser')
  const { facture } = await factureEmise(r, 'APAR83')
  await lireJson(await r.post(`${API}/ventes/factures/${facture.id}/envoyer-email/`, { ...T, data: { email: `apar83${marque()}@example.invalid` } }), 'envoyer')
  const corps = await py(`from apps.ventes.models import EmailLog
e = EmailLog.objects.filter(facture_id=${facture.id}).order_by('-id').first()
sortie(e.corps if e else None)`)
  expect(corps, 'EmailLog écrit').toBeTruthy()
  expect(corps).toContain('Veuillez trouver ci-joint')
  expect(corps, 'pas de lien vide').not.toContain('au lien suivant :')
  await page.goto('/parametres?onglet=emails').catch(() => undefined)
  suivi.verifie(5)
})

// ── APAR84 — {lien_rdv} dans « devis unique » : aperçu et envoi avec le lien de réservation ──────────
etape('PAR.whatsapp_lien_rdv', ['APAR84'], async ({ page, suivi }) => {
  const r = page.request
  const msgs = await lireJson(await r.get(`${API}/parametres/messages/`, T), 'messages')
  const avant = listeDe(msgs).find((x) => x.cle === 'devis_unique')
  try {
    await lireJson(await r.put(`${API}/parametres/messages/`, { ...T, data: { cle: 'devis_unique', corps_fr: 'Bonjour, votre devis {lien}. RDV : {lien_rdv}', corps_darija: avant.corps_darija } }), 'modèle')
    const lead = await nouveauLead(r, `APAR84 ${marque()}`)
    const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur APAR84 ${marque()}`, prix_vente: '1000.00', prix_achat: '321.00' } }), 'produit')
    const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
      ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] },
    }), 'devis')
    await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
    const ap = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/whatsapp-preview/`, { ...T, data: {} }), 'aperçu')
    const texte = JSON.stringify(ap)
    expect(texte, "jamais l'accolade littérale").not.toContain('{lien_rdv}')
    expect(texte, 'le lien de réservation du lead').toMatch(/https?:[^"]*(rdv|booking|rendez-vous|reserver|prendre)/i)
    await page.goto('/ventes/devis')
    await page.getByPlaceholder('Rechercher (référence ou client)…').fill(d.reference, { timeout: 60_000 })
    await expect(page.locator('tr', { has: page.getByTestId(`ref-cell-${d.id}`) }).first()).toBeVisible({ timeout: 60_000 })
  } finally {
    await r.put(`${API}/parametres/messages/`, { ...T, data: { cle: 'devis_unique', corps_fr: avant.corps_fr, corps_darija: avant.corps_darija } })
  }
  suivi.verifie(5)
})

// ── APAR74 — 409 du profil à deux navigateurs : « Recharger les valeurs du serveur » garde la saisie ─
etape('PAR.profil_409', ['APAR74'], async ({ page, suivi }) => {
  const r = page.request
  const base = await profil(r)
  const m = marque()
  suivi.attendre(/\/parametres\/update\//, 409)
  try {
    await page.goto('/parametres')
    const nom = page.locator('input[name="nom"], #nom').first()
    await expect(nom).toBeVisible({ timeout: 60_000 })
    await expect(nom).toHaveValue(base.nom ?? '', { timeout: 30_000 })
    // B (l'API) écrit entre-temps.
    const b = await lireJson(await r.patch(`${API}/parametres/update/`, { ...T, data: { rib: `RIB-B-${m}`, updated_at: base.updated_at } }), 'écriture de B')
    await nom.fill(`Société A ${m}`)
    const [p1] = await Promise.all([
      page.waitForResponse((x) => /\/parametres\/update\/$/.test(new URL(x.url()).pathname) && x.request().method() === 'PATCH', T),
      page.getByRole('button', { name: 'Enregistrer', exact: true }).first().click(),
    ])
    expect(p1.status(), "1er enregistrement d'A : 409").toBe(409)
    await page.getByRole('button', { name: 'Recharger les valeurs du serveur' }).click()
    await expect(nom, 'la saisie d\'A reste').toHaveValue(`Société A ${m}`, { timeout: 30_000 })
    const [p2] = await Promise.all([
      page.waitForResponse((x) => /\/parametres\/update\/$/.test(new URL(x.url()).pathname) && x.request().method() === 'PATCH', T),
      page.getByRole('button', { name: 'Enregistrer', exact: true }).first().click(),
    ])
    expect(p2.status(), '2e enregistrement : 200').toBe(200)
    expect(p2.request().postDataJSON().updated_at, 'porte le updated_at de B').toBe(b.updated_at)
    const relu = await profil(r)
    expect([relu.nom, relu.rib], 'saisie de A et RIB de B').toEqual([`Société A ${m}`, `RIB-B-${m}`])
    await page.reload()
    await expect(page.locator('input[name="nom"], #nom').first()).toHaveValue(`Société A ${m}`, { timeout: 60_000 })
  } finally {
    const cur = await profil(r)
    await r.patch(`${API}/parametres/update/`, { ...T, data: { nom: base.nom, rib: base.rib, updated_at: cur.updated_at } })
  }
  suivi.verifie(5)
})

// ── APAR78 — 250 produits : la liste « composant » d'un kit propose le dernier ───────────────────────
etape('PAR.kits_250', ['APAR78'], async ({ page, suivi }) => {
  const m = marque()
  const n = await py(`from apps.stock.models import Produit
from authentication.models import Company
c = Company.objects.get(pk=1)
manque = max(0, 260 - Produit.objects.filter(company=c, is_archived=False).count())
Produit.objects.bulk_create([Produit(company=c, nom='APAR78 ${m} n%03d' % i, sku='APAR78-${m}-%03d' % i, prix_vente=1, prix_achat=0, quantite_stock=0) for i in range(max(manque, 1))])
sortie(Produit.objects.filter(company=c, is_archived=False).count())`)
  expect(n, 'au moins 250 produits').toBeGreaterThanOrEqual(250)
  await page.goto('/stock/kits')
  await page.getByRole('button', { name: /Nouveau kit/ }).click({ timeout: 60_000 })
  const select = page.getByLabel('Produit du composant 1')
  await expect(select).toBeVisible({ timeout: 30_000 })
  await expect.poll(async () => select.locator('option').count(), { timeout: 60_000, message: 'toutes les pages lues' }).toBeGreaterThan(Math.min(n, 201))
  const compte = await select.locator('option').count()
  expect(compte, `options : ${compte} pour ${n} produits`).toBeGreaterThanOrEqual(n)
  await expect(select.locator('option').filter({ hasText: `APAR78 ${m} n000` })).toHaveCount(1)
  await py(`from apps.stock.models import Produit
Produit.objects.filter(sku__startswith='APAR78-${m}-').delete()
sortie(1)`)
  suivi.verifie(5)
})

// ── APAR79 — société à 14 %, produit sans TVA : la carte de taille compte 14 %, pas 20 % ─────────────
etape('PAR.offres_tailles_14', ['APAR79'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const lead = await nouveauLead(r, `APAR79 ${m}`, { facture_hiver: '1500', type_installation: 'residentiel' })
  const pan = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Panneau mono 550W ${m}`, prix_vente: '1000.00', prix_achat: '111.00' } }), 'panneau')
  const ond = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur réseau 10kW ${m}`, prix_vente: '10000.00', prix_achat: '222.00' } }), 'onduleur')
  expect(ond.tva ?? null, 'produit sans TVA').toBeNull()
  const base = await profil(r)
  try {
    await lireJson(await r.patch(`${API}/parametres/update/`, { ...T, data: { tva_standard: '14.00', updated_at: base.updated_at } }), 'société à 14 %')
    const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
      ...T, data: {
        taux_tva: '14.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel',
        lignes: [
          { produit: pan.id, designation: pan.nom, quantite: '10', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '14.00', type_ligne: 'produit', ordre: 0 },
          { produit: ond.id, designation: ond.nom, quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '14.00', type_ligne: 'produit', ordre: 1 },
        ],
      },
    }), 'devis 14 %')
    const servi = await r.get(`${API}/ventes/devis/${d.id}/offres-tailles/`, T)
    expect(servi.status(), 'offres-tailles').toBe(200)
    const texte = await servi.text()
    expect(texte, 'aucun prix_achat').not.toContain('prix_achat')
    // Le coût de la composition sans taux de ligne suit le repli société, lu sur la pile (fonction réelle, données réelles).
    const c = await py(`from decimal import Decimal
from types import SimpleNamespace
from apps.ventes.dimensionnement import _lire_composition
from apps.stock.models import Produit
from authentication.models import Company
o = Produit.objects.get(pk=${ond.id})
L = type('Compo', (list,), {})([SimpleNamespace(produit=o, designation=o.nom, quantite=1, prix_unitaire=10000)])
L.roles = ['onduleur_hybride']
sortie([_lire_composition(L, None, Company.objects.get(pk=1))['cout_ttc'], _lire_composition(L, Decimal('14'), Company.objects.get(pk=1))['cout_ttc']])`)
    expect(c, '11 400 au repli société et au taux du devis, jamais 12 000').toEqual([11400, 11400])
    await page.goto(`/ventes/devis/nouveau?edit=${d.id}`)
    await expect(page.locator('#gen-form')).toBeVisible({ timeout: 60_000 })
  } finally {
    const cur = await profil(r)
    await r.patch(`${API}/parametres/update/`, { ...T, data: { tva_standard: base.tva_standard, updated_at: cur.updated_at } })
  }
  suivi.verifie(7)
})

// ── APAR82 — blur Sécurité & terrain puis Enregistrer dans Société : 200, jamais 409 ─────────────────
etape('PAR.securite_terrain_blur', ['APAR82'], async ({ page, suivi }) => {
  const r = page.request
  const base = await profil(r)
  const m = marque()
  try {
    await page.goto('/parametres?onglet=securite')
    await page.getByText('Revue des dépassements').first().scrollIntoViewIfNeeded({ timeout: 60_000 })
    const champ = page.locator('div', { hasText: /^Revue des dépassements/ }).locator('input[type="number"]').first()
    const carte = champ.count ? champ : null
    await expect(carte).toBeVisible({ timeout: 30_000 })
    const valeur = String((Number(base.overage_seuil_pct) || 10) + 1)
    const [blur] = await Promise.all([
      page.waitForResponse((x) => /\/parametres\/update\/$/.test(new URL(x.url()).pathname) && x.request().method() === 'PATCH', T),
      (async () => { await carte.fill(valeur); await carte.blur() })(),
    ])
    expect(blur.status(), 'blur : 200').toBe(200)
    const apresBlur = await blur.json()
    await page.getByText('Général', { exact: true }).first().click()
    await page.getByText('Société & identité', { exact: true }).first().click()
    const nom = page.locator('input[name="nom"], #nom').first()
    await nom.fill(`Société B ${m}`)
    const [p] = await Promise.all([
      page.waitForResponse((x) => /\/parametres\/update\/$/.test(new URL(x.url()).pathname) && x.request().method() === 'PATCH', T),
      page.getByRole('button', { name: 'Enregistrer', exact: true }).first().click(),
    ])
    expect(p.status(), 'Enregistrer : 200, pas de 409').toBe(200)
    expect(p.request().postDataJSON().updated_at, 'porte le updated_at de la réponse du blur').toBe(apresBlur.updated_at)
    await expect(page.getByText('Profil enregistré').first()).toBeVisible({ timeout: 30_000 })
    await page.reload()
    const relu = await profil(r)
    expect([relu.nom, Number(relu.overage_seuil_pct)], 'les deux valeurs relues').toEqual([`Société B ${m}`, Number(valeur)])
  } finally {
    const cur = await profil(r)
    await r.patch(`${API}/parametres/update/`, { ...T, data: { nom: base.nom, overage_seuil_pct: base.overage_seuil_pct, updated_at: cur.updated_at } })
  }
  suivi.verifie(5)
  void pwRequest
  void MDP_ESSAI
  void connexionApi
})

// ── APAR89 — la garde compte une preuve « pile locale … » même sans id d'étape ───────────────────────
etape('PAR.garde', ['APAR89'], async () => {
  const py3 = (args) => spawnSync('python', args, { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  const t = py3(['-m', 'unittest', 'scripts.tests.test_check_acceptation'])
  expect(t.status, (t.stderr || '').slice(-500)).toBe(0)
  const g = py3(['scripts/check_acceptation.py', '--rapport'])
  expect(g.stdout, 'bilan du groupe').toMatch(/APAR : \d+ cochée\(s\) à preuve/)
})

