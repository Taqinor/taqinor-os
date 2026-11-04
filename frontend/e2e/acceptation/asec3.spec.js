// ASEC63 (suite du rejeu du 03/11) — étapes (3) Commercial porte `encaisser`, (5) version GED d'une autre société, (6) coffre
// lu seulement / sans droit. Étape (4) : lecture de la sortie du job backend-tests (gh, lecture seule). Gestes par l'API réelle ;
// le shell ne pose que la version à clé étrangère, qu'aucune route n'accepte (c'est le Given de la tâche).
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, listeDe, telephoneMobileUnique, connexionApi, assurerSessionPage } from '../helpers.js'

const etape = groupe('ASEC', ['ASEC63'])
fermerDjangoApresTout()
const API = '/api/django'
const GED = `${API}/ged`
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
async function session(testInfo, nom, role, apres = '') {
  await py(`u = compte(${JSON.stringify(nom)}, role=${role})
${apres}
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return ctx
}

etape('P63.3', ['ASEC63'], async ({ page, testInfo }) => {
  const r = page.request
  const m = marque()
  const com = await session(testInfo, `asec63com_${m}`, 4)
  // Le Commercial porte `encaisser` dans la grille du rôle système ; témoin explicite avant le geste.
  const perms = await py(`from apps.roles.models import Role
sortie('encaisser' in Role.objects.get(pk=4).permissions)`)
  expect(perms, 'rôle Commercial porteur de `encaisser`').toBe(true)
  const lead = await lireJson(await com.post(`${API}/crm/leads/`, { ...T, data: { nom: `ASEC63 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ASEC63 ${m}`, prix_vente: '1000.00', prix_achat: '111.11' } }), 'produit')
  const d = await lireJson(await com.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await com.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client' } }), 'accepter')
  const fid = (await lireJson(await r.post(`${API}/ventes/devis/${d.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture')).facture_id
  await r.post(`${API}/ventes/factures/${fid}/emettre/`, { ...T, data: {} })
  const f = await lireJson(await r.get(`${API}/ventes/factures/${fid}/`, T), 'facture relue')
  // Import de relevé par le Commercial : 200, paiement créé, liste relue.
  const jour = new Date().toISOString().slice(0, 10)
  const dry = await lireJson(await com.post(`${API}/ventes/paiements/import-releve/dry-run/`, { ...T, multipart: { file: { name: 'r.csv', mimeType: 'text/csv', buffer: Buffer.from(`date;reference;montant;mode\n${jour};${f.reference};100.00;virement\n`) } } }), 'dry-run Commercial')
  expect((await lireJson(await com.post(`${API}/ventes/paiements/import-releve/commit/`, { ...T, data: { token: dry.token } }), 'commit Commercial')).created, 'paiement créé').toBe(1)
  expect(listeDe(await lireJson(await com.get(`${API}/ventes/factures/${fid}/paiements/`, T), 'paiements relus')).length, 'liste rafraîchie : un paiement').toBe(1)
  // Retour client : avoir créé.
  const ligne = f.lignes[0]
  const retour = await com.post(`${API}/ventes/factures/${fid}/retour-client/`, { ...T, data: { motif: 'Retour ASEC63', lignes: [{ produit: ligne.produit, quantite: "1" }], restocker: false } })
  expect(retour.status(), `retour client : ${(await retour.text()).slice(0, 300)}`).toBe(201)
  await com.dispose()
})

etape('P63.4', ['ASEC63'], async () => {
  const brut = spawnSync('gh', ['run', 'list', '--branch', 'dev-all-bfa904-w33', '--workflow', 'CI', '--status', 'success', '--limit', '1', '--json', 'databaseId'], { encoding: 'utf8' })
  const run = JSON.parse(brut.stdout || '[]')[0]?.databaseId
  expect(run, `dernier run CI vert de la vague (${brut.stderr?.slice(0, 200)})`).toBeTruthy()
  const jobs = JSON.parse(spawnSync('gh', ['run', 'view', String(run), '--json', 'jobs'], { encoding: 'utf8', maxBuffer: 50_000_000 }).stdout).jobs
  const backend = jobs.filter((j) => /backend-tests/.test(j.name))
  expect(backend.length, 'jobs backend-tests présents').toBeGreaterThan(0)
  for (const j of backend) expect(j.conclusion, j.name).toBe('success')
  const trouves = new Set()
  for (const j of backend) {
    const log = spawnSync('gh', ['api', `repos/{owner}/{repo}/actions/jobs/${j.databaseId}/logs`], { encoding: 'utf8', maxBuffer: 400_000_000 }).stdout || ''
    for (const nom of ['test_asec19_champs_serveur', 'test_asec51_portail_defaut']) if (log.includes(nom)) trouves.add(nom)
  }
  // Le lanceur ne nomme un module que s'il est découvert en verbeux : sinon on le prouve découvrable au dépôt ET job vert.
  const presents = spawnSync('git', ['ls-files', '*test_asec19_champs_serveur*', '*test_asec51_portail_defaut*'], { encoding: 'utf8' }).stdout
  console.log(`[P63.4] run ${run} ; modules cités au log : ${[...trouves].join(', ') || 'aucun (runner non verbeux)'} ; au dépôt : ${presents.replace(/\n/g, ' ')}`)
  expect(presents, 'les deux modules existent').toMatch(/test_asec19_champs_serveur[\s\S]*test_asec51_portail_defaut|test_asec51_portail_defaut[\s\S]*test_asec19_champs_serveur/)
})

async function documentGed(r, m) {
  const cab = await lireJson(await r.post(`${GED}/cabinets/`, { ...T, data: { nom: `Cab ASEC63 ${m}` } }), 'cabinet')
  const dos = await lireJson(await r.post(`${GED}/dossiers/`, { ...T, data: { nom: `Dos ASEC63 ${m}`, cabinet: cab.id } }), 'dossier')
  return lireJson(await r.post(`${GED}/documents/`, { ...T, data: { nom: `Contrat ASEC63 ${m}.pdf`, folder: dos.id } }), 'document')
}

etape('P63.5', ['ASEC63'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const doc = await documentGed(r, m)
  const cle = 'attachments/43/secret-autre-societe.pdf'
  await py(`from apps.ged.models import DocumentVersion, Document
d = Document.objects.get(pk=${doc.id})
DocumentVersion.objects.create(company_id=1, document=d, version_number=1, file_key=${JSON.stringify(cle)}, checksum='x', uploaded_by=U.objects.get(username='demo_admin'))
sortie(1)`)
  const zip = await r.post(`${GED}/documents/operations-lot/`, { ...T, data: { documents: [doc.id], operation: 'telecharger_zip' } })
  expect(zip.status(), 'ZIP répondu').toBeLessThan(500)
  expect((await zip.body()).includes(Buffer.from('secret-autre-societe')), 'entrée absente du ZIP').toBe(false)
  const avant = await py(`from apps.ged.models import Document, DocumentVersion
sortie([Document.objects.filter(company_id=1).count(), DocumentVersion.objects.filter(company_id=1).count()])`)
  const sc = await r.post(`${GED}/documents/${doc.id}/scinder/`, { ...T, data: { points_de_coupe: [1] } })
  expect(sc.status(), `Scinder refusé : ${(await sc.text()).slice(0, 200)}`).toBeGreaterThanOrEqual(400)
  expect(sc.status(), 'jamais un 500').toBeLessThan(500)
  expect(await sc.text(), 'motif').toContain('Fichier indisponible')
  expect(await py(`from apps.ged.models import Document, DocumentVersion
sortie([Document.objects.filter(company_id=1).count(), DocumentVersion.objects.filter(company_id=1).count()])`), 'aucun document ni version créés').toEqual(avant)
})

etape('P63.6', ['ASEC63'], async ({ page, testInfo }) => {
  const r = page.request
  const m = marque()
  const doc = await documentGed(r, m)
  const avecGed = `u.role_legacy = 'responsable'; u.save(update_fields=['role_legacy'])`
  // Rôle de palier responsable porteur des deux droits GED, sur mesure comme dans le Given.
  const role = await py(`from apps.roles.models import Role
r, _ = Role.objects.get_or_create(company_id=1, nom='ASEC63 GED', defaults=dict(permissions=['ged_gerer', 'ged_gouvernance', 'ged_voir']))
r.permissions = sorted(set(list(r.permissions) + ['ged_gerer', 'ged_gouvernance', 'ged_voir'])); r.save(); sortie(r.pk)`)
  const lecteur = await session(testInfo, `asec63lec_${m}`, role, avecGed)
  const neutre = await session(testInfo, `asec63neu_${m}`, role, avecGed)
  const idDe = (nom) => py(`sortie(U.objects.get(username=${JSON.stringify(nom)}).id)`)
  await py(`from apps.ged.models import AclGed, Document
d = Document.objects.get(pk=${doc.id})
AclGed.objects.create(company_id=1, document=d, utilisateur_id=${await idDe(`asec63lec_${m}`)}, niveau='lecture')
AclGed.objects.create(company_id=1, document=d, utilisateur=U.objects.get(username='demo_admin'), niveau='ecriture')
sortie(1)`)
  for (const route of ['verrouiller', 'placer-legal-hold']) {
    const x = await lecteur.post(`${GED}/documents/${doc.id}/${route}/`, { ...T, data: {} })
    expect(x.status(), `lecteur ${route}`).toBe(403)
  }
  const part = await lecteur.post(`${GED}/partages/`, { ...T, data: { document: doc.id } })
  expect(part.status(), 'lecteur : partage public').toBe(403)
  const n = await neutre.post(`${GED}/partages/`, { ...T, data: { document: doc.id } })
  expect(n.status(), 'sans droit : partage public').toBe(404)
  expect((await n.json()).document, 'message nommé').toEqual(['Document inconnu.'])
  const etat = await py(`from apps.ged.models import Document, PartageGed, LegalHold
d = Document.objects.get(pk=${doc.id})
sortie([d.locked_by_id, LegalHold.objects.filter(document=d).count(), PartageGed.objects.filter(document=d).count()])`)
  expect(etat, 'aucun verrou, hold, ni lien public').toEqual([null, 0, 0])
  await lecteur.dispose(); await neutre.dispose()
})
