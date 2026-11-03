// Acceptation en direct — groupe ADOC (documents) : preuves dues ADOC184-189. Format : `_format.md`.
// Pile locale : conteneur django `E2E_DJANGO_EXEC`, base jetable erp_live2. Les parcours « API seulement »
// (ADOC186, 187, 189) rejouent la sonde commitée du constat (`scripts/sonde.py`, transaction annulée, mail en
// mémoire, HTTP sortant bloqué) ; ADOC185 et ADOC188 sont joués avec des données persistantes.
import { spawnSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, request as pwRequest, test } from '@playwright/test'
import { groupe } from './_oracles.js'
import { RACINE, aujourdHui } from './_enregistrement.js'
import {
  API_DJANGO, assurerSessionPage, connexionApi, executerDansDjango, lireJson, uiLogin,
} from '../helpers.js'

test.describe.configure({ timeout: 600_000 })
test.use({ viewport: { width: 1920, height: 1080 }, actionTimeout: 60_000 })
const etape = groupe('ADOC', ['ADOC184', 'ADOC185', 'ADOC186', 'ADOC187', 'ADOC188', 'ADOC189'])
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

const GED = `${API_DJANGO}/ged`
const MOT_DE_PASSE = 'Acc@Adoc2026!' // compte de test de la pile locale jetable
const CONTENEUR_DJANGO = (process.env.E2E_DJANGO_EXEC || 'docker exec live2-django').split(' ').pop()
const CONTENEUR_DEPOT = process.env.ACC_CONTENEUR_DEPOT || 'live2-repo' // monte le dépôt entier (docs/meryem)

function py(code) {
  const m = String(executerDansDjango(code)).match(/@@JSON@@(.*)/)
  if (!m) throw new Error('sortie Django sans JSON')
  return JSON.parse(m[1])
}

function rejouerSonde(constat, conteneur) {
  const groupeSonde = constat.split('-')[1]
  // `sonde.py` sort en 1 quand le verdict est ÉCART (le constat n'est plus reproduit) : la sortie est lue quel que soit le code.
  const r = spawnSync('python', ['scripts/sonde.py', `${groupeSonde}/${constat}`, '--conteneur', conteneur],
    { cwd: RACINE, encoding: 'utf8', timeout: 600_000 })
  const sortie = `${r.stdout || ''}${r.stderr || ''}`
  const dossier = join(RACINE, 'docs/qa-explorer/captures', aujourdHui())
  mkdirSync(dossier, { recursive: true })
  writeFileSync(join(dossier, `ACCEPTATION-ADOC-sonde-${constat}.txt`), sortie, 'utf8')
  return sortie
}

// ── ADOC184 : ré-authentification d'un compte portail dans la modale « Session expirée » ────
etape('P184.1', ['ADOC184'], async ({ context, suivi, testInfo }) => {
  py(`
import json
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(username='demo_portail')
u.set_password('${MOT_DE_PASSE}')
u.save()
print('@@JSON@@' + json.dumps({'ok': True, 'username': u.username}))
`)
  const ctx = await context.browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block', viewport: { width: 1920, height: 1080 } })
  try {
    const p = suivi.surveiller(await ctx.newPage())
    const accueil = []
    p.on('request', (r) => { if (/messages-accueil/.test(r.url())) accueil.push(`${r.method()} ${r.url()}`) })
    await uiLogin(p, { username: 'demo_portail', password: MOT_DE_PASSE })
    await expect(p).not.toHaveURL(/\/login/, { timeout: 30_000 })
    await p.waitForLoadState('networkidle')
    const me = await lireJson(await p.request.get(`${API_DJANGO}/auth/me/`), 'profil portail')
    expect(me.portee, 'compte portail').toBe('portail_client')
    // L'accès expire : cookies de session retirés, puis l'événement que la couche axios émet sur un 401 non rejouable.
    suivi.attendre(/\/api\/django\//, 401)
    await ctx.clearCookies()
    await p.evaluate(() => window.dispatchEvent(new Event('taqinor:session-expired')))
    const modale = p.getByRole('dialog').filter({ hasText: 'Session expirée' })
    await expect(modale).toBeVisible({ timeout: 30_000 })
    await modale.getByLabel('Nom d’utilisateur').fill('demo_portail')
    await modale.getByLabel('Mot de passe').fill(MOT_DE_PASSE)
    await modale.getByRole('button', { name: 'Se reconnecter' }).click()
    await expect(modale).toBeHidden({ timeout: 30_000 })
    await p.waitForLoadState('networkidle')
    await p.waitForTimeout(3000)
    expect(accueil, 'aucun appel messages-accueil').toEqual([])
    await expect(p.locator('[data-sonner-toast]'), 'aucun toast').toHaveCount(0)
    await expect(p.getByText('Bienvenue chez Taqinor'), 'aucune bienvenue ERP').toHaveCount(0)
    const apres = await lireJson(await p.request.get(`${API_DJANGO}/auth/me/`), 'profil après reconnexion')
    expect(apres.portee).toBe('portail_client')
    await p.reload() // persistance : identique après rechargement
    await p.waitForLoadState('networkidle')
    expect(accueil).toEqual([])
    await expect(p.getByText('Bienvenue chez Taqinor')).toHaveCount(0)
  } finally { await ctx.close() }
})

// ── ADOC185 : l'approbateur 1 d'une chaîne à 2 étapes laisse la demande chez l'étape 2 ───────
etape('P185.1', ['ADOC185'], async ({ suivi, testInfo }) => {
  const r = py(`
import json
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder, RegleApprobationGed
U = get_user_model()
co = U.objects.get(username='demo_admin').company
tag = timezone.now().strftime('%H%M%S%f')
def u(n):
    x = U.objects.create_user(username='acc185-%s-%s' % (n, tag), password='${MOT_DE_PASSE}', company=co)
    return x
dem, a1, a2 = u('dem'), u('a1'), u('a2')
cab = Cabinet.objects.create(company=co, nom='CAB185 ' + tag)
f = Folder.objects.create(company=co, cabinet=cab, nom='F185 ' + tag)
nom = 'Contrat185-' + tag
RegleApprobationGed.objects.create(company=co, libelle='2 niveaux ' + tag,
    condition_group={'field': 'nom', 'operator': 'eq', 'value': nom}, approbateurs=[a1.pk, a2.pk])
doc = Document.objects.create(company=co, folder=f, nom=nom)
services.add_version(doc, file_key='attachments/acc185-%s.pdf' % tag, company=co, uploaded_by=dem)
d = services.request_review_avec_routage(doc, user=dem)
print('@@JSON@@' + json.dumps({'demande': d.pk, 'doc': doc.pk, 'a1': a1.username, 'a2': a2.username, 'a1_id': a1.pk, 'a2_id': a2.pk}))
`)
  const etat = () => py(`
import json
from apps.ged.models import ChaineApprobationGed, Document
from apps.reporting.models import DemandeApprobation
d = DemandeApprobation.objects.get(pk=${r.demande})
c = ChaineApprobationGed.objects.get(demande=d)
print('@@JSON@@' + json.dumps({'statut': d.statut, 'approbateur': d.approbateur_id, 'etape': c.etape_courante,
    'doc': Document.objects.get(pk=${r.doc}).statut}))
`)
  const baseURL = testInfo.project.use.baseURL
  const decider = async (username) => {
    const api = await pwRequest.newContext({ baseURL })
    try {
      await connexionApi(api, { username, password: MOT_DE_PASSE })
      return api.post(`${API_DJANGO}/reporting/approbations-en-attente/decider/`, {
        data: { source: 'ged', id: r.demande, decision: 'approuver', motif: '' } })
    } finally { /* contexte fermé après lecture */ }
  }
  const rep1 = await decider(r.a1)
  expect(rep1.status()).toBe(200)
  const e1 = etat()
  expect(e1, 'A approuve : la demande reste en attente chez B').toEqual({ statut: 'en_attente', approbateur: r.a2_id, etape: 1, doc: 'revue' })
  expect(etat(), 'persistance : relecture identique').toEqual(e1)
  const rep2 = await decider(r.a2)
  expect(rep2.status()).toBe(200)
  const e2 = etat()
  expect(e2.statut).toBe('approuve')
  expect(e2.doc).toBe('approuve')
  suivi.verifie(5)
})

// ── ADOC186 / 187 / 189 : sondes du constat rejouées (plus de repro) ─────────────────────────
etape('P186.1', ['ADOC186'], async () => {
  const sortie = rejouerSonde('C-ADOC-VER-020', CONTENEUR_DEPOT)
  expect(sortie).toMatch(/versions=2 ; description_en_base='Pompage au fil du soleil, forage immerge'/)
  expect(sortie, 'le mot ajouté sort de la recherche GED').toMatch(/recherche forage \(mot ajoute\) -> 200 trouve=True/)
})
etape('P187.1', ['ADOC187'], async () => {
  const sortie = rejouerSonde('C-ADOC-VER-021', CONTENEUR_DJANGO)
  expect(sortie).toMatch(/extraire_alias='compta.2026' ; documents_crees=1/)
})
etape('P189.1', ['ADOC189'], async () => {
  const sortie = rejouerSonde('C-ADOC-VER-031', CONTENEUR_DJANGO)
  expect(sortie, 'document conservé quand MinIO est en panne').toMatch(/document encore en base=True/)
})

// ── ADOC188 : « CIN.pdf » solde la demande CIN ; « facture.pdf » ne solde rien ───────────────
etape('P188.1', ['ADOC188'], async ({ page }) => {
  const r = py(`
import json
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.ged import services
from apps.ged.models import Cabinet, ExigenceDossier, Folder
co = get_user_model().objects.get(username='demo_admin').company
tag = timezone.now().strftime('%H%M%S%f')
cab = Cabinet.objects.create(company=co, nom='CAB188 ' + tag)
f = Folder.objects.create(company=co, cabinet=cab, nom='Dossier RH188 ' + tag)
out = {}
for lib in ('CIN', 'Attestation CNSS'):
    ex = ExigenceDossier.objects.create(company=co, cabinet=cab, folder=f, libelle=lib)
    services.creer_demande_document(folder=f, company=co, libelle=lib, exigence=ex)
print('@@JSON@@' + json.dumps({'folder': f.pk}))
`)
  const pdf = Buffer.from('%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n')
  const deposer = async (nom) => lireJson(await page.request.post(`${GED}/documents/televerser/`, {
    multipart: { folder: String(r.folder), file: { name: nom, mimeType: 'application/pdf', buffer: pdf } },
  }), `dépôt ${nom}`)
  const checklist = async () => {
    const l = await lireJson(await page.request.get(`${GED}/demandes-document/checklist/?folder=${r.folder}`), 'checklist')
    return Object.fromEntries((Array.isArray(l) ? l : l.results ?? []).map((x) => [x.exigence?.libelle, x.statut]))
  }
  expect(await checklist()).toEqual({ CIN: 'manquant', 'Attestation CNSS': 'manquant' })
  await deposer('facture.pdf')
  expect(await checklist(), '« facture.pdf » ne solde rien').toEqual({ CIN: 'manquant', 'Attestation CNSS': 'manquant' })
  await deposer('CIN.pdf')
  expect(await checklist(), '« CIN.pdf » solde la seule CIN').toEqual({ CIN: 'present', 'Attestation CNSS': 'manquant' })
  await deposer('Attestation_CNSS.pdf')
  expect(await checklist(), '« Attestation_CNSS.pdf » solde la CNSS').toEqual({ CIN: 'present', 'Attestation CNSS': 'present' })
  expect(await checklist(), 'persistance : relue identique').toEqual({ CIN: 'present', 'Attestation CNSS': 'present' })
})
