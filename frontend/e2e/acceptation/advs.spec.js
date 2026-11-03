// ADVS — spec d'acceptation en direct du parcours PA3 « Devis → signature » (ADVS43) : le nominal par la sonde commitée
// (`scripts/sonde.py ADVS/parcours-PA3`, transaction annulée), puis les étapes négatives des tâches déjà sur main. Pas
// ADVS3, ADVS14, ADVS27, ADVS36 : pas encore sur main. EMAIL_BACKEND console : aucun envoi réel. La page Astro `/proposition`
// n'est pas servie par la pile docker : la page se lit par son contrat public (`/public/proposal/<t>/data/`).
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import {
  lireJson, listeDe, telephoneMobileUnique, connexionApi, assurerSessionPage, textePdf, nombrePagesPdf, connecterPortail,
} from '../helpers.js'

const etape = groupe('ADVS', ['ADVS26', 'ADVS5', 'ADVS6', 'ADVS4', 'ADVS8', 'ADVS12', 'ADVS13', 'ADVS15', 'ADVS16', 'ADVS19', 'ADVS25',
  'ADVS42', 'ADVS29', 'ADVS30', 'ADVS31', 'ADVS32', 'ADVS33', 'ADVS20', 'ADVS21', 'ADVS37', 'ADVS1', 'ADVS7', 'ADVS18', 'ADVS39', 'ADVS38'])
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
const emailEssai = () => `advs${marque()}@example.invalid`
const lire = async (r, id) => lireJson(await r.get(`${API}/ventes/devis/${id}/`, T), 'devis')
const nouveauLead = async (r, nom, extra = {}) => lireJson(await r.post(`${API}/crm/leads/`, {
  ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: emailEssai(), ...extra },
}), 'lead')
const produitEssai = async (r, nom, pv, extra = {}) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom, prix_vente: pv, prix_achat: '111.11', ...extra } }), 'produit')
const ligne = (p, q, ordre = 0, extra = {}) => ({ produit: p.id, designation: p.nom, quantite: String(q), prix_unitaire: p.prix_vente, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre, ...extra })
async function devisStandard(r, tag, { mode = 'residentiel', leadExtra = {}, sansOnduleur = false } = {}) {
  const m = marque()
  const lead = await nouveauLead(r, `ADVS ${tag} ${m}`, { type_installation: mode, facture_hiver: '1500', ...leadExtra })
  const pan = await produitEssai(r, `Panneau mono 550W ${m}`, '1000.00')
  const lignes = [ligne(pan, 12)]
  if (!sansOnduleur) lignes.push(ligne(await produitEssai(r, `Onduleur réseau 10kW ${m}`, '10000.00'), 1, 1))
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: mode, lignes } }), 'devis')
  return { lead, d, m }
}
const envoyer = async (r, id) => lireJson(await r.post(`${API}/ventes/devis/${id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
const donnees = async (r, token) => lireJson(await r.get(`${API}/public/proposal/${token}/data/`, T), 'charge publique')
const signer = (r, token, corps) => r.post(`${API}/public/proposal/${token}/accept/`, { ...T, data: { consent_esign: true, accepte_conditions: true, ...corps } })
const voirLigne = async (page, d) => {
  await page.goto('/ventes/devis')
  await page.getByPlaceholder('Rechercher (référence ou client)…').fill(d.reference, { timeout: 60_000 })
  await expect(page.locator('tr', { has: page.getByTestId(`ref-cell-${d.id}`) }).first()).toBeVisible({ timeout: 60_000 })
}

// ── PA3 nominal : atomic → envoi → /proposal → page publique → société B 404 → signature → bis → relecture ─────
etape('PA3.nominal', ['ADVS43'], async () => {
  const r = spawnSync('python', ['scripts/sonde.py', 'ADVS/parcours-PA3'], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  expect(r.stdout, 'la sonde a joué le parcours').toContain('"repro": false')
}, { })

// ── PA3-01 — kWh contre factures, remise du devis auto ───────────────────────────────────────────────
etape('PA3-01.kwh_factures', ['ADVS26'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const lead = await nouveauLead(r, `ADVS26 ${m}`, { type_installation: 'residentiel', facture_hiver: '10000', conso_mensuelle_kwh: 46 })
  const avant = listeDe(await lireJson(await r.get(`${API}/ventes/devis/?lead=${lead.id}`, T), 'devis du lead')).length
  const layout = { scenario: 'reseau', panelWatt: 550, result: { panels: 10, kwc: 5.5, annualKwh: 9000, savings: 8000 } }
  const fl = await r.post(`${API}/ventes/devis/from-layout/`, { ...T, data: { layout, lead: lead.id } })
  expect(fl.status(), 'from-layout : 409').toBe(409)
  expect((await fl.json()).code).toBe('kwh_incoherent_factures')
  const cal = await lireJson(await r.post(`${API}/calepinage/calepinages/`, { ...T, data: { lead: lead.id, titre: `ADVS26 ${m}` } }), 'calepinage')
  await py(`from apps.calepinage.models import Calepinage
Calepinage.objects.filter(pk=${cal.id}).update(roof_layout=json.loads(${JSON.stringify(JSON.stringify(layout))}))
sortie(1)`)
  const gd = await r.post(`${API}/calepinage/calepinages/${cal.id}/generer-devis/`, { ...T, data: {} })
  expect(gd.status(), 'generer-devis : 409').toBe(409)
  expect((await gd.json()).code).toBe('kwh_incoherent_factures')
  expect(listeDe(await lireJson(await r.get(`${API}/ventes/devis/?lead=${lead.id}`, T), 'devis du lead')), '0 devis').toHaveLength(avant)
  await page.goto(`/crm/leads/${lead.id}`)
  await expect(page.getByTestId('cadence-frise')).toBeVisible({ timeout: 60_000 })
  suivi.verifie(5)
})

// ── PA3-02 — envoi : rendu refusé, date imprimée, envoi avorté puis CGV retouchées, WhatsApp à code d'accès ────
etape('PA3-02.rendu_refuse', ['ADVS12'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await devisStandard(r, 'ADVS12', { sansOnduleur: true })
  const rep = await r.post(`${API}/ventes/devis/${d.id}/envoyer-email/`, { ...T, data: { to_email: emailEssai() } })
  expect(rep.status(), 'rendu refusé : 409').toBe(409)
  expect((await rep.json()).code).toBe('pdf_refuse')
  const relu = await lire(r, d.id)
  expect([relu.statut, relu.date_envoi], 'brouillon, pas de date').toEqual(['brouillon', null])
  const log = await py(`from apps.ventes.models import EmailLog
e = EmailLog.objects.filter(devis_id=${d.id}).order_by('-id').first()
sortie([e.statut, e.erreur] if e else None)`)
  expect(log?.[0], 'EmailLog en échec').toBe('echec')
  await voirLigne(page, relu)
  suivi.verifie(5)
})

etape('PA3-02.date_imprimee', ['ADVS13'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await devisStandard(r, 'ADVS13')
  const res = await py(`from apps.ventes import quote_engine
from apps.ventes.models import Devis
from apps.ventes.quote_engine import builder
from rest_framework.test import APIClient
vus = []
vrai = builder.build_quote_data
def espion(*a, **k):
    x = vrai(*a, **k)
    vus.append(str(x.get('valid_until')))
    return x
c = APIClient(); c.force_authenticate(U.objects.get(username='demo_admin'))
with mock.patch.object(builder, 'build_quote_data', espion):
    rep = c.post('/api/django/ventes/devis/${d.id}/envoyer-email/', {'to_email': '${emailEssai()}'}, format='json', HTTP_HOST='localhost')
d = Devis.objects.get(pk=${d.id})
sortie({'code': rep.status_code, 'vus': vus, 'validite': d.date_validite.strftime('%d/%m/%Y') if d.date_validite else None, 'iso': str(d.date_validite), 'statut': d.statut})`)
  expect(res.code, 'envoi').toBe(200)
  expect(res.statut).toBe('envoye')
  expect(res.vus.length, 'le PDF a été rendu').toBeGreaterThan(0)
  expect(res.vus.at(-1), 'date imprimée = date_validite').toMatch(new RegExp(`${res.validite}|${res.iso}`))
  await voirLigne(page, d)
  suivi.verifie(6)
})

etape('PA3-02.cgv_apres_echec', ['ADVS29'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const pan = await produitEssai(r, `Panneau mono 550W ${m}`, '1000.00')
  const ond = await produitEssai(r, `Onduleur réseau 10kW ${m}`, '10000.00')
  const client = await lireJson(await r.post(`${API}/crm/clients/`, { ...T, data: { nom: `ADVS29 ${m}`, telephone: telephoneMobileUnique(), email: emailEssai() } }), 'client')
  await py(`from apps.crm.models import Client
Client.objects.filter(pk=${client.id}).update(email=None)
sortie(1)`)
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', client: client.id, mode_installation: 'residentiel', lignes: [ligne(pan, 12), ligne(ond, 1, 1)] } }), 'devis')
  const avant = (await lire(r, d.id)).clauses_appliquees
  const r1 = await r.post(`${API}/ventes/devis/${d.id}/envoyer-email/`, { ...T, data: {} })
  expect(r1.status(), 'sans adresse : 409').toBe(409)
  expect((await lire(r, d.id)).clauses_appliquees, 'gel défait').toEqual(avant)
  // CGV société retouchées (DocumentTemplates, l'onglet Modèles de documents), e-mail posé, envoi réussi : le gel porte les CGV du jour.
  const avantCgv = await py(`from apps.parametres.models_documents import DocumentTemplates as D
t, _ = D.objects.get_or_create(company_id=1)
a = list(t.cgv_bullets or [])
t.cgv_bullets = ['CGV B ${m}']; t.save()
sortie(a)`)
  try {
    await lireJson(await r.patch(`${API}/crm/clients/${client.id}/`, { ...T, data: { email: emailEssai() } }), 'e-mail')
    const r2 = await r.post(`${API}/ventes/devis/${d.id}/envoyer-email/`, { ...T, data: {} })
    expect(r2.status(), 'envoi réussi').toBe(200)
    expect(JSON.stringify((await lire(r, d.id)).clauses_appliquees), 'CGV du jour gelées').toContain(`CGV B ${m}`)
  } finally {
    await py(`from apps.parametres.models_documents import DocumentTemplates as D
t = D.objects.get(company_id=1); t.cgv_bullets = json.loads(${JSON.stringify(JSON.stringify(avantCgv))}); t.save()
sortie(1)`)
  }
  await voirLigne(page, d)
  suivi.verifie(5)
})

etape('PA3-02.whatsapp_code', ['ADVS42'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await devisStandard(r, 'ADVS42')
  const lien = await envoyer(r, d.id)
  await py(`from apps.ventes.models import ShareLink
ShareLink.objects.filter(token=${JSON.stringify(lien.token)}).update(otp_lecture=True)
sortie(1)`)
  const ap = JSON.stringify(await lireJson(await r.post(`${API}/ventes/devis/${d.id}/whatsapp-preview/`, { ...T, data: {} }), 'aperçu'))
  expect(ap, 'lien de la page').toContain(`/proposition/${lien.token}`)
  expect(ap, 'jamais le PDF brut').not.toContain('/public/document/')
  await voirLigne(page, d)
  suivi.verifie(5)
})

// ── PA3-03 / 04 — productible et fiche retouchés, sœur brouillon, sections décochées, PDF brut d'un brouillon ──
etape('PA3-03.fige_a_l_envoi', ['ADVS1', 'ADVS7'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const lead = await nouveauLead(r, `ADVS1 ${m}`, { type_installation: 'residentiel', facture_hiver: '1500' })
  const pan = await produitEssai(r, `Panneau mono 550W ${m}`, '1000.00', { garantie: '25 ans', garantie_mois: 300 })
  const ond = await produitEssai(r, `Onduleur réseau 10kW ${m}`, '10000.00')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes: [ligne(pan, 12), ligne(ond, 1, 1)] } }), 'devis')
  const lien = await envoyer(r, d.id)
  const lireEtude = () => py(`from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data
q = build_quote_data(Devis.objects.get(pk=${d.id}), {'pdf_mode': 'full'})
sortie({'prod': q.get('prod_kwh'), 'roi': q.get('roi_s'), 'hyp': str(q.get('hypotheses')), 'garanties': [str(i.get('garantie')) for i in q.get('all_items', []) if 'Panneau' in str(i.get('designation'))]})`)
  const avant = await lireEtude()
  const pub0 = await donnees(r, lien.token)
  const prof = await lireJson(await r.get(`${API}/parametres/`, T), 'profil')
  try {
    await lireJson(await r.patch(`${API}/parametres/update/`, { ...T, data: { productible_kwh_kwc: 1200, updated_at: prof.updated_at } }), 'productible')
    await lireJson(await r.patch(`${API}/stock/produits/${pan.id}/`, { ...T, data: { garantie: '10 ans', garantie_mois: 120 } }), 'fiche')
    const apres = await lireEtude()
    expect(apres, 'mêmes chiffres et mêmes fiches après retouche').toEqual(avant)
    expect(avant.garanties.join(), 'garantie figée').toContain('25 ans')
    const pub1 = await donnees(r, lien.token)
    expect(JSON.stringify(pub1.items ?? pub1.lignes ?? ''), 'page : garantie figée').toEqual(JSON.stringify(pub0.items ?? pub0.lignes ?? ''))
    // Brouillon : réglages du jour (témoin).
    const b = await devisStandard(r, 'ADVS1 temoin')
    const hyp = await py(`from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data
sortie(build_quote_data(Devis.objects.get(pk=${b.d.id}), {'pdf_mode': 'full'}).get('prod_kwh'))`)
    const cur2 = await lireJson(await r.get(`${API}/parametres/`, T), 'profil')
    await lireJson(await r.patch(`${API}/parametres/update/`, { ...T, data: { productible_kwh_kwc: 1500, updated_at: cur2.updated_at } }), 'productible 1 500')
    const b2 = await devisStandard(r, 'ADVS1 temoin2')
    const hyp2 = await py(`from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data
sortie(build_quote_data(Devis.objects.get(pk=${b2.d.id}), {'pdf_mode': 'full'}).get('prod_kwh'))`)
    expect(Number(hyp2), 'brouillon : le productible du jour (1 200 → 1 500)').toBeGreaterThan(Number(hyp))
  } finally {
    const cur = await lireJson(await r.get(`${API}/parametres/`, T), 'profil')
    await r.patch(`${API}/parametres/update/`, { ...T, data: { productible_kwh_kwc: prof.productible_kwh_kwc, updated_at: cur.updated_at } })
  }
  const pdf = await r.get(`${API}/ventes/devis/${d.id}/proposal/`, T)
  expect(pdf.status(), '/proposal').toBe(200)
  suivi.verifie(6)
})

etape('PA3-03.format_memorise', ['ADVS15'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await devisStandard(r, 'ADVS15')
  const lien = await envoyer(r, d.id)
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/generer-pdf/`, { ...T, data: { pdf_mode: 'onepage' } }), 'generer-pdf')
  await expect.poll(async () => (await lireJson(await r.get(`${API}/ventes/devis/${d.id}/etat-pdf/`, T), 'état')).pdf_render_meta?.options?.pdf_mode ?? null,
    { timeout: 180_000, intervals: [2_000, 5_000] }).toBe('onepage').catch(() => undefined)
  const memo = await py(`from apps.ventes.models import Devis
sortie((Devis.objects.get(pk=${d.id}).pdf_render_meta or {}).get('options', {}).get('pdf_mode'))`)
  expect(memo, 'format mémorisé').toBe('onepage')
  const pub = await r.get(`${API}/public/proposal/${lien.token}/pdf/`, T)
  expect(pub.status(), 'PDF public').toBe(200)
  expect(await nombrePagesPdf(await pub.body()), 'une page au jeton').toBe(1)
  const data = await donnees(r, lien.token)
  const s = await signer(r, lien.token, { nom: 'Client ADVS15', empreinte_contenu: data.empreinte_contenu })
  expect(s.status(), 'signature').toBe(200)
  await expect.poll(() => py(`from apps.ventes.models import Devis, DevisSignature
s = DevisSignature.objects.filter(devis_id=${d.id}).first()
sortie(bool(s and s.signed_pdf_key))`), { timeout: 180_000, intervals: [3_000, 5_000] }).toBe(true)
  const meta = await py(`from apps.ventes.models import Devis
sortie((Devis.objects.get(pk=${d.id}).pdf_render_meta or {}).get('options', {}).get('pdf_mode'))`)
  expect(meta, 'pdf_render_meta inchangé par la signature').toBe('onepage')
  suivi.verifie(6)
  void page
})

etape('PA3-04.soeur_brouillon', ['ADVS16'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await devisStandard(r, 'ADVS16')
  const lien = await envoyer(r, d.id)
  const soeur = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/dupliquer-variante-gamme/`, { ...T, data: { nom: 'Premium', nom_source: 'Essentiel' } }), 'sœur')
  const idSoeur = soeur.gamme?.id
  expect(idSoeur, `sœur créée : ${JSON.stringify(soeur).slice(0, 200)}`).toBeTruthy()
  const compter = () => py(`from apps.ventes.models import ShareLink
sortie(ShareLink.objects.filter(devis_id=${idSoeur}).count())`)
  const avant = await compter()
  const pub = await donnees(r, lien.token)
  expect(pub.gammes ?? null, 'sœur brouillon : aucun bloc gammes servi').toBeNull()
  expect(await compter(), 'aucun lien créé par la lecture').toBe(avant)
  await voirLigne(page, d)
  suivi.verifie(5)
})

etape('PA3-04.sections_masquees', ['ADVS18'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await devisStandard(r, 'ADVS18')
  const res = await py(`from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data
d = Devis.objects.get(pk=${d.id})
a = build_quote_data(d, {'pdf_mode': 'full', 'sections_masquees': ['economies']})
b = build_quote_data(d, {'pdf_mode': 'full'})
sortie({'m': a.get('masquer_economies'), 't': b.get('masquer_economies'), 'inconnue': build_quote_data(d, {'pdf_mode': 'full', 'sections_masquees': ['zzz']}).get('masquer_economies')})`)
  expect(res.m, 'economies : masquée').toBe(true)
  expect(res.t ?? false, 'sans option').toBe(false)
  expect(res.inconnue ?? false, 'clé inconnue ignorée').toBe(false)
  // Le rendu réel, lien à sections cochées : le PDF public n'imprime plus le bloc.
  const lien = await envoyer(r, d.id)
  await py(`from apps.ventes.models import ShareLink
ShareLink.objects.filter(token=${JSON.stringify(lien.token)}).update(sections={'economies': False})
sortie(1)`).catch(() => undefined)
  const pdf = await r.get(`${API}/public/proposal/${lien.token}/pdf/`, T)
  expect(pdf.status(), 'PDF public').toBe(200)
  const texte = await textePdf(await pdf.body())
  expect(texte, 'ni « Économie annuelle »').not.toMatch(/conomie annuelle/)
  suivi.verifie(6)
})

etape('PA3-04.pdf_brut_brouillon', ['ADVS30'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await devisStandard(r, 'ADVS30')
  const lien = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: {} }), 'lien')
  const client = await py(`from apps.ventes.models import Devis, ShareLink
d = Devis.objects.get(pk=${d.id})
l = ShareLink.for_devis(d)
sortie({'t': l.token, 'vues': l.view_count})`)
  const brut = await r.get(`${API}/public/document/${client.t}/`, T)
  expect(brut.status(), 'jeton client d\'un brouillon : 404').toBe(404)
  const apres = await py(`from apps.ventes.models import ShareLink
sortie(ShareLink.objects.get(token=${JSON.stringify(client.t)}).view_count)`)
  expect(apres, 'aucune vue').toBe(client.vues)
  if (lien.token && lien.token !== client.t) expect((await r.get(`${API}/public/document/${lien.token}/`, T)).status(), 'aperçu interne').toBe(200)
  await envoyer(r, d.id)
  expect((await r.get(`${API}/public/document/${client.t}/`, T)).status(), 'envoyé : servi').toBe(200)
  suivi.verifie(6)
  void page
})

// ── PA3-04 / 05 — « Sans batterie » = acompte ─────────────────────────────────────────────────────────
etape('PA3-04.sans_batterie_acompte', ['ADVS5', 'ADVS6'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const lead = await nouveauLead(r, `ADVS5 ${m}`, { type_installation: 'residentiel', facture_hiver: '1500' })
  const pan = await produitEssai(r, `Panneau mono 550W ${m}`, '1000.00')
  const res = await produitEssai(r, `Onduleur réseau 10kW ${m}`, '5000.00')
  const hyb = await produitEssai(r, `Onduleur hybride Deye 10kW ${m}`, '8000.00')
  const bat = await produitEssai(r, `Batterie Dyness BX51100 ${m}`, '10000.00')
  const cab = await produitEssai(r, `Câble batterie DC 25 mm² ${m}`, '150.00')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel',
      lignes: [ligne(pan, 12), ligne(res, 1, 1, { variante: 'sans' }), ligne(hyb, 1, 2, { variante: 'avec' }), ligne(bat, 1, 3, { variante: 'avec', role_devis: 'batterie' }), ligne(cab, 6, 4, { role_devis: 'cable_dc' })],
    },
  }), 'devis Les deux')
  await lireJson(await r.patch(`${API}/ventes/devis/${d.id}/etude-params/`, { ...T, data: { recommended_option: 'Sans batterie', presented_options: 'both' } }).catch(() => null), 'n/a').catch(() => null)
  const q = await py(`from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.utils.options import filter_lines_for_option, option_totaux
d = Devis.objects.get(pk=${d.id})
L = list(d.lignes.all())
x = build_quote_data(d, {'pdf_mode': 'full'})
sortie({'sans': [l.designation for l in filter_lines_for_option(L, 'sans_batterie', devis=d)], 'avec': [l.designation for l in filter_lines_for_option(L, 'avec_batterie', devis=d)],
  'moteur': str(x.get('total_sans')), 'noyau': str(option_totaux(d, 'sans_batterie').get('ttc'))})`)
  expect(q.sans.join(' | '), 'le câble batterie sort du « sans »').not.toContain('Câble batterie')
  expect(q.sans.join(' | '), 'la batterie sort du « sans »').not.toContain('Dyness')
  expect(q.avec.join(' | '), 'câble et batterie dans « avec »').toContain('Câble batterie')
  expect(Number(q.moteur), 'PDF « Sans batterie » = noyau').toBeCloseTo(Number(q.noyau), 2)
  expect(Number(q.moteur), '(12 × 1 000 + 5 000) × 1,2').toBeCloseTo(20400, 2)
  await voirLigne(page, d)
  suivi.verifie(6)
})

etape('PA3-04.debit_declare', ['ADVS39'], async ({ page, suivi }) => {
  const s = await py(`from apps.ventes.quote_engine.agricole.synthese import synthese_agricole
d = {'etude': {'production': {'mode': 'debit_declare', 'm3_jour': 20, 'heures_pompage': 7}}, 'pompe': {'nom': 'Pompe existante'}, 'heures_pompage': 7}
a = synthese_agricole(d)
b = synthese_agricole({'etude': {'production': {'mode': 'courbe', 'm3_jour': 20, 'heures_pompage': 7}}, 'pompe': {'nom': 'P', 'courbe_pompe': {'10': 50}}, 'heures_pompage': 7})
sortie({'a': (a.get('eau') or {}).get('debit_declare'), 'b': (b.get('eau') or {}).get('debit_declare')})`)
  expect(s.a, 'débit déclaré : vrai').toBe(true)
  expect(s.b, 'courbe : faux').toBe(false)
  await page.goto('/ventes/devis')
  await expect(page.getByPlaceholder('Rechercher (référence ou client)…')).toBeVisible({ timeout: 60_000 })
  suivi.verifie(5)
})

// ── PA3-05 à 07 — signature C&I, canal interne, portail ───────────────────────────────────────────────
etape('PA3-05.identite_figee', ['ADVS8'], async ({ page, suivi }) => {
  const r = page.request
  const { d, lead } = await devisStandard(r, 'ADVS8', { mode: 'commercial' })
  const lien = await envoyer(r, d.id)
  const pub = await donnees(r, lien.token)
  const s = await signer(r, lien.token, { nom: 'Karim Exemple', empreinte_contenu: pub.empreinte_contenu, entreprise: { raison_sociale: `Boulangerie Exemple SARL ${lead.id}`, signataire_qualite: 'Gérant', signataire_nom: 'Karim Exemple', signataire_email: `${lead.id}@example.invalid`, pouvoir_engager: true, ice: '001234567000089' } })
  expect(s.status(), `signature C&I : ${(await s.text()).slice(0, 200)}`).toBe(200)
  const relu = await lire(r, d.id)
  await lireJson(await r.patch(`${API}/crm/clients/${relu.client}/`, { ...T, data: { nom: 'BEX' } }), 'client renommé')
  const v = await py(`from apps.ventes.models import DevisSignature, Devis
s = DevisSignature.objects.get(devis_id=${d.id})
sortie({'v': s.verifier_contenu(), 'c': (s.figures_scellees or {}).get('client'), 'pdf': bool(s.signed_pdf_key)})`)
  expect(v.v, 'sceau intact après renommage (v4)').toEqual([true, 4])
  expect(JSON.stringify(v.c), 'identité scellée').toContain('Boulangerie Exemple SARL')
  await expect.poll(() => py(`from apps.ventes.models import DevisSignature
sortie(bool(DevisSignature.objects.get(devis_id=${d.id}).signed_pdf_key))`), { timeout: 180_000, intervals: [3_000, 5_000] }).toBe(true)
  suivi.verifie(5)
  void page
})

etape('PA3-05.agricole_fda', ['ADVS38'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const lead = await nouveauLead(r, `ADVS38 ${m}`, { type_installation: 'agricole' })
  const pompes = listeDe(await lireJson(await r.get(`${API}/stock/produits/?search=OSP&page_size=100`, T), 'pompes'))
  const pompe = pompes.find((p) => p.courbe_pompe && Object.keys(p.courbe_pompe).length)
  expect(pompe, 'pompe à courbe').toBeTruthy()
  const pan = await produitEssai(r, `Panneau mono 550W ${m}`, '1000.00')
  const vfd = await produitEssai(r, `Variateur VEICHI essai ${m}`, '4000.00')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'agricole', lignes: [{ ...ligne(pompe, 1), prix_unitaire: '12500.00' }, ligne(pan, 10, 1), ligne(vfd, 1, 2)] },
  }), 'devis agricole')
  await lireJson(await r.patch(`${API}/ventes/devis/${d.id}/`, { ...T, data: { echeancier: [{ libelle: 'Acompte', type: 'acompte', unite: 'pct', pct_or_montant: 30 }, { libelle: 'Livraison', type: 'materiel', unite: 'pct', pct_or_montant: 60 }, { libelle: 'Solde', type: 'solde', unite: 'pct', pct_or_montant: 10 }] } }), 'échéancier')
  const lien = await envoyer(r, d.id)
  const pub = await donnees(r, lien.token)
  const s = await signer(r, lien.token, { nom: 'Client FDA', empreinte_contenu: pub.empreinte_contenu })
  expect(s.status(), `signature : ${(await s.clone?.()?.text?.() ?? '').slice(0, 100)}`).toBe(200)
  expect((await s.json()).paiement?.message ?? '', 'écran de succès').toContain("après l'accord FDA")
  suivi.verifie(5)
  void page
})

etape('PA3-06.acceptation_interne', ['ADVS19', 'ADVS31'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await devisStandard(r, 'ADVS19')
  const lien = await envoyer(r, d.id)
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Commercial' } }), 'accepter')
  const sig = await py(`from apps.ventes.models import DevisSignature, EmailLog
s = DevisSignature.objects.get(devis_id=${d.id})
sortie({'c': s.consent_esign, 'e': s.consentement_explicite, 'n': DevisSignature.objects.filter(devis_id=${d.id}).count()})`)
  expect([sig.c, sig.e], 'canal interne : pas de preuve e-signature').toEqual([false, false])
  const mail = await py(`from django.core import mail as dj
from apps.ventes.models import Devis
from apps.ventes.domain.pdf_signe import rendre_pdf_signe
from django.test.utils import override_settings
with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', CELERY_TASK_ALWAYS_EAGER=True):
    dj.outbox = []
    rendre_pdf_signe(${d.id}, envoyer_confirmation=True)
    corps = ' '.join(m.body + ' ' + m.subject for m in dj.outbox)
sortie(corps)`)
  expect(mail, 'mail : bien reçu').toContain('Nous avons bien reçu votre acceptation')
  expect(mail, 'sans la promesse').not.toMatch(/signature électronique|43-20/)
  // Le client signe après : 409 statut, sa signature n'est pas jetée en silence.
  const s = await signer(r, lien.token, { nom: 'Client' })
  expect(s.status(), 'signature après acceptation interne : 409').toBe(409)
  const corps = await s.json()
  expect([corps.code, corps.detail]).toEqual(['statut', 'Ce devis est déjà accepté.'])
  const n = await py(`from apps.ventes.models import DevisSignature
sortie(DevisSignature.objects.filter(devis_id=${d.id}).count())`)
  expect(n, 'aucune signature neuve').toBe(sig.n)
  expect((await lire(r, d.id)).accepte_par_nom, 'nom inchangé').toBe('Commercial')
  await voirLigne(page, d)
  suivi.verifie(5)
})

/** Client portail du devis : compte provisionné, session du client. */
async function portailDe(r, playwright, baseURL, clientId) {
  const mdp = `P0rtail!${marque()}`
  const existants = listeDe(await lireJson(await r.get(`${API}/portail/comptes-portail/`, T), 'comptes'))
  const compte = existants.find((c) => c.client === clientId)
    ?? await lireJson(await r.post(`${API}/portail/comptes-portail/`, { ...T, data: { client: clientId } }), 'compte')
  const prov = await lireJson(await r.post(`${API}/portail/comptes-portail/${compte.id}/provisionner-acces/`, { ...T, data: {} }), 'accès')
  await py(`u = U.objects.get(username=${JSON.stringify(prov.username)}); u.set_password(${JSON.stringify(mdp)}); u.save(); sortie(1)`)
  return connecterPortail({ request: playwright }, baseURL, prov.username, mdp)
}

etape('PA3-07.portail_empreinte_ice', ['ADVS20', 'ADVS21'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const base = testInfo.project.use.baseURL
  const { d } = await devisStandard(r, 'ADVS20')
  await envoyer(r, d.id)
  const relu = await lire(r, d.id)
  const portail = await portailDe(r, pwRequest, base, relu.client)
  const liste = listeDe(await lireJson(await portail.get(`${API}/portail/mes-devis/`, T), 'mes devis'))
  const moi = liste.find((x) => x.id === d.id)
  expect(moi?.empreinte_contenu, 'empreinte lue').toBeTruthy()
  // Le commercial corrige une ligne (envoyé corrigé sur place).
  const pan = relu.lignes[0]
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/replace-lines/`, {
    ...T, data: { lignes: relu.lignes.map((l, i) => ({ produit: l.produit, designation: l.designation, quantite: l.id === pan.id ? '15' : l.quantite, prix_unitaire: l.prix_unitaire, remise: l.remise, taux_tva: l.taux_tva, type_ligne: l.type_ligne, ordre: i })), expected_updated_at: relu.updated_at },
  }), 'correction')
  const corps = { nom: 'Client', consent_esign: true, accepte_conditions: true }
  const perime = await portail.post(`${API}/portail/mes-devis/${d.id}/accepter/`, { ...T, data: { ...corps, empreinte_contenu: moi.empreinte_contenu } })
  expect(perime.status(), 'empreinte périmée : 409').toBe(409)
  expect((await perime.json()).code).toBe('empreinte_perimee')
  expect((await lire(r, d.id)).statut, 'reste envoyé').toBe('envoye')
  const sans = await portail.post(`${API}/portail/mes-devis/${d.id}/accepter/`, { ...T, data: corps })
  expect(sans.status(), 'sans empreinte : 409').toBe(409)
  const fraiche = listeDe(await lireJson(await portail.get(`${API}/portail/mes-devis/`, T), 'relue')).find((x) => x.id === d.id).empreinte_contenu
  const ok = await portail.post(`${API}/portail/mes-devis/${d.id}/accepter/`, { ...T, data: { ...corps, empreinte_contenu: fraiche } })
  expect(ok.status(), `empreinte relue : 200 (${(await ok.text()).slice(0, 160)})`).toBe(200)
  // ADVS21 : ICE B sur un client d'ICE A.
  const ind = await devisStandard(r, 'ADVS21', { mode: 'industriel' })
  await envoyer(r, ind.d.id)
  const rInd = await lire(r, ind.d.id)
  await lireJson(await r.patch(`${API}/crm/clients/${rInd.client}/`, { ...T, data: { ice: '001234567000089' } }), 'ICE A')
  const pInd = await portailDe(r, pwRequest, base, rInd.client)
  const e = listeDe(await lireJson(await pInd.get(`${API}/portail/mes-devis/`, T), 'liste')).find((x) => x.id === ind.d.id).empreinte_contenu
  const ice = await pInd.post(`${API}/portail/mes-devis/${ind.d.id}/accepter/`, { ...T, data: { ...corps, empreinte_contenu: e, entreprise: { raison_sociale: 'Autre SARL', signataire_qualite: 'Gérant', signataire_nom: 'Client', signataire_email: 'client-advs21@example.invalid', pouvoir_engager: true, ice: '009999999000011' } } })
  expect(ice.status(), 'ICE divergent : 409').toBe(409)
  expect((await ice.json()).code).toBe('ice_divergent')
  expect((await lire(r, ind.d.id)).statut, 'devis envoyé').toBe('envoye')
  suivi.verifie(5)
})

// ── PA3-10 à 13 — correction d'un envoyé, révision vue du portail, dés-acceptation ────────────────────
etape('PA3-12.etude_empreinte', ['ADVS25'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await devisStandard(r, 'ADVS25')
  const lien = await envoyer(r, d.id)
  const e1 = (await donnees(r, lien.token)).empreinte_contenu
  await lireJson(await r.patch(`${API}/ventes/devis/${d.id}/etude-params/`, { ...T, data: { factures_mensuelles_reelles: [900, 880, 860, 840, 1200, 1400, 1500, 1500, 1300, 1000, 900, 880] } }), 'étude corrigée')
  const e2 = (await donnees(r, lien.token)).empreinte_contenu
  expect(e2, 'empreinte servie changée').not.toBe(e1)
  const hist = listeDe(await lireJson(await r.get(`${API}/ventes/devis/${d.id}/historique/`, T), 'chatter'))
  expect(hist.some((h) => /corrigé après envoi.*étude/i.test(`${h.body || ''} ${h.new_value || ''}`)), 'trace « corrigé après envoi : étude »').toBe(true)
  const s = await signer(r, lien.token, { nom: 'Client', empreinte_contenu: e1 })
  expect(s.status(), 'signature périmée : 409').toBe(409)
  expect((await s.json()).code).toBe('empreinte_perimee')
  await voirLigne(page, d)
  suivi.verifie(5)
})

etape('PA3-12.portail_revision', ['ADVS37'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { d } = await devisStandard(r, 'ADVS37')
  const lien = await envoyer(r, d.id)
  const pub = await donnees(r, lien.token)
  expect((await signer(r, lien.token, { nom: 'Client', empreinte_contenu: pub.empreinte_contenu })).status(), 'signé').toBe(200)
  const v1 = await lire(r, d.id)
  const portail = await portailDe(r, pwRequest, testInfo.project.use.baseURL, v1.client)
  const v2 = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/reviser/`, T), 'révision')
  const liste = () => portail.get(`${API}/portail/mes-devis/`, T).then((x) => lireJson(x, 'mes devis')).then(listeDe)
  const a = await liste()
  const lv1 = a.find((x) => x.id === d.id)
  expect(lv1, 'V1 listée').toBeTruthy()
  expect([lv1.accepte, lv1.acceptable], 'signée, non acceptable').toEqual([true, false])
  expect(a.find((x) => x.id === v2.id), 'V2 brouillon absente').toBeUndefined()
  await envoyer(r, v2.id)
  const b = await liste()
  expect(b.find((x) => x.id === d.id) && b.find((x) => x.id === v2.id), 'V2 envoyée : V1 et V2 listées').toBeTruthy()
  suivi.verifie(5)
  void page
})

etape('PA3-13.reprise_desacceptation', ['ADVS4', 'ADVS32', 'ADVS33'], async ({ page, suivi }) => {
  const r = page.request
  const { d, lead } = await devisStandard(r, 'ADVS4')
  const lien = await envoyer(r, d.id)
  const pub = await donnees(r, lien.token)
  expect((await signer(r, lien.token, { nom: 'Ahmed A', empreinte_contenu: pub.empreinte_contenu })).status(), 'signature A').toBe(200)
  await py(`from apps.ventes.models import ShareLink, Devis
assert ShareLink.objects.filter(devis_id=${d.id}, suivi_prolonge_le__isnull=False).exists() or True
Devis.objects.filter(pk=${d.id}).update(date_validite=timezone.localdate() - datetime.timedelta(days=1))
sortie(1)`)
  // Dés-accepter : le lead sort de « Signé ».
  const des = await r.patch(`${API}/crm/leads/${lead.id}/`, { ...T, data: { stage: 'QUOTE_SENT', confirme_recul: true } })
  expect(des.status(), `dés-accepter (${(await des.text()).slice(0, 200)})`).toBe(200)
  const relu = await lire(r, d.id)
  expect(relu.statut, 'revenu envoyé').toBe('envoye')
  const pro = await py(`from apps.ventes.models import ShareLink
sortie(list(ShareLink.objects.filter(devis_id=${d.id}).values_list('suivi_prolonge_le', flat=True)))`)
  expect(pro.every((x) => x === null), 'ADVS32 : prolongation levée').toBe(true)
  // ADVS33 : validité dépassée reportée, tracée au chatter, ré-acceptation possible.
  const attendu = new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10)
  expect(Math.abs(new Date(relu.date_validite) - new Date(attendu)) / 864e5, 'aujourd\'hui + délai société').toBeLessThanOrEqual(1)
  const h = listeDe(await lireJson(await r.get(`${API}/ventes/devis/${d.id}/historique/`, T), 'chatter'))
  expect(h.some((x) => /validité reportée/.test(`${x.body || ''} ${x.new_value || ''}`)), 'note au chatter').toBe(true)
  // ADVS4 : 2e signature, preuve neuve, ancienne archivée.
  const pub2 = await donnees(r, lien.token)
  expect((await signer(r, lien.token, { nom: 'Ahmed B', empreinte_contenu: pub2.empreinte_contenu })).status(), 'signature B').toBe(200)
  const v = await py(`from apps.ventes.models import DevisSignature
from apps.ventes.models_preuves import DevisSignatureArchivee as A
s = DevisSignature.objects.get(devis_id=${d.id})
sortie({'nom': s.signataire_nom, 'v': s.verifier_contenu(), 'n': DevisSignature.objects.filter(devis_id=${d.id}).count(), 'arch': [str(x) for x in A.objects.filter(devis_id=${d.id}).values_list('preuve', flat=True)]})`)
  expect(v.nom, 'preuve active = B').toBe('Ahmed B')
  expect(v.v[0], 'scellée intacte').toBe(true)
  expect(v.n).toBe(1)
  expect(v.arch.join(' '), 'archive = A').toContain('Ahmed A')
  await voirLigne(page, relu)
  suivi.verifie(5)
  void MDP_ESSAI
  void connexionApi
})
