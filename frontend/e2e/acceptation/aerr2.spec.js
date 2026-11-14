// Preuves en direct AERR, lot 2 (audit parcours PF12 « erreurs, pertes de saisie et gestes dangereux à l'écran »,
// dossier docs/audits/2026-11-11-parcours-PF12.md ; METHODE §C.4 points 1 et 7). Chaque étape joue le geste À L'ÉCRAN,
// connectée sous un rôle LIVRÉ du registre (compte d'essai de la société démo, connexion par l'écran de login),
// provoque VRAIMENT la panne (route Playwright déclarée AVANT par `suivi.attendre`, ou refus réel du serveur),
// AFFIRME ce que la clause nomme (avis + Réessayer, saisie gardée, boîte nommée, toast « Annuler »), relit la base,
// recharge et réaffirme. Données propres créées par le shell Django, retirées après la capture.
// Sondes hôtes (`docs/audits/sondes/AERR/`, détecteurs de lecture du source) rejouées : repro False exigé, sauf les
// quatre détecteurs NOMMÉS dans PERIMEES (motif lu sur l'ancienne forme, voir la note) — jamais comptés.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, telephoneMobileUnique, uiLoginJusquAuxApps, connexionApi, PNG_1PX, STAGE_LABELS } from '../helpers.js'

const etape = groupe('AERR', ['AERR100', 'AERR101', 'AERR102', 'AERR103', 'AERR104', 'AERR105', 'AERR106', 'AERR107',
  'AERR108', 'AERR109', 'AERR110', 'AERR111', 'AERR113', 'AERR116', 'AERR117', 'AERR118', 'AERR119', 'AERR120',
  'AERR122', 'AERR23', 'AERR24'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 420_000 })
const INIT = () => {
  try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
}
test.beforeEach(async ({ page }) => { await page.addInitScript(INIT); await assurerSessionPage(page) })
const contextesUi = []
const apres = []
test.afterEach(async () => {
  for (const c of contextesUi.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const pad = (n) => String(n).padStart(2, '0')
const isoJour = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

async function auRepos(suivi) {
  for (const p of suivi.pages.filter((x) => !x.isClosed())) await p.waitForLoadState('networkidle').catch(() => undefined)
}

// ÉCARTS ACCEPTÉS, BORNÉS (décision de l'orchestrateur du lot, METHODE §C.4 point 7 (b)) — observés au run runner
// 43539844228 (8f51a8364, 14/11 à 01 h UTC) : (1) avant 12 h, le pré-chargement matinal de la tournée
// (`frontend/src/features/offlinesync/prechargeMatinale.js`, NTMOB28, 2ad951e296 du 13/08/2026) appelle
// `GET installations/interventions/ma-tournee/` au démarrage de l'app pour TOUT compte, d'où un 403 (oracles 2 et 3)
// pour le Commercial responsable sans droit installations — même famille que les 403 d'arrière-plan d'ADRG110-121,
// antérieur aux tâches AERR, hors de tous leurs Files ; (2) la question avant de quitter une fiche lead en création est
// la boîte NATIVE `window.confirm` de `frontend/src/ui/useDirtyGuard.js::confirmLeaveIfDirty` (oracle 4), appelée
// telle quelle par `useLeadDraft.leaveGuard` avant AERR108, fichier hors des Files d'AERR108. Bornés : le corps de
// l'étape échoue sur TOUT autre incident d'oracle.
const MATIN = new Date().getHours() < 12
const RE_PRECHARGE = /\/api\/django\/installations\/interventions\/ma-tournee\//
const RAISON_PRECHARGE = 'pré-chargement matinal de la tournée (frontend/src/features/offlinesync/prechargeMatinale.js, '
  + 'NTMOB28 2ad951e296 du 13/08/2026, avant 12 h) : GET installations/interventions/ma-tournee/ → 403 au démarrage '
  + 'de l\'app pour un Commercial responsable sans droit installations (oracles 2 et 3) ; antérieur aux tâches AERR, '
  + 'hors de tous leurs Files ; borné : tout autre incident d\'oracle fait échouer l\'étape'
const RAISON_NATIF = 'la question avant de quitter une fiche en création est la boîte NATIVE window.confirm « Modifications '
  + 'non enregistrées — quitter cette page ? » de frontend/src/ui/useDirtyGuard.js::confirmLeaveIfDirty (oracle 4), '
  + 'appelée telle quelle par useLeadDraft.leaveGuard avant AERR108, fichier hors des Files d\'AERR108 (deploy) ; '
  + 'borné : seul cet oracle 4 est excusé, le corps (question posée, fiche gardée, doublon non lu) doit passer'
/** Étape jouée sous le Commercial responsable : écarts bornés ci-dessus seulement. */
function etapeCR(id, taches, corps, { natif = false } = {}) {
  const raisons = [natif ? RAISON_NATIF : '', MATIN ? RAISON_PRECHARGE : ''].filter(Boolean)
  etape(id, taches, async (args) => {
    await corps(args)
    const autres = args.suivi.incidents.filter((i) => !RE_PRECHARGE.test(i.texte)
      && !(natif && i.oracle === '4' && /quitter cette page/.test(i.texte)))
    expect(autres, 'écart borné : aucun autre incident d\'oracle').toEqual([])
  }, raisons.length ? { ecart: { base: 'FAIL', raison: raisons.join(' ; ') } } : {})
}

// Détecteurs dont le motif lit l'ANCIENNE forme et rend `repro` True sur le code corrigé (vérifié à la lecture le
// 14/11 sur 47f925be14) : 044 (`erreur_remplace_liste…` ne voit pas la garde `leads.length`), 047 (journal et report
// restent dans un même `try`, le correctif est un drapeau `appelJournalise`), 050 (`confirmDelete(` non reconnu comme
// confirmation), 053 (le `catch` vide les évènements seulement sur un AUTRE mois, `setLectureEchec` non lu). Nommés,
// jamais comptés : la preuve de ces tâches est l'écran.
const PERIMEES = new Set(['C-AERR-044', 'C-AERR-047', 'C-AERR-050', 'C-AERR-053'])
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'AERR', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}
function sonde(constat) {
  const s = sondeHote(constat)
  expect(s.ok, `sonde ${constat} exécutée : ${s.err || ''}`).toBe(true)
  if (PERIMEES.has(constat)) {
    console.log(`[sonde] ${constat} détecteur périmé, non compté : repro=${s.res.repro} ${J(s.res.observe)}`)
    return
  }
  expect(s.res.repro, `sonde ${constat} : ${J(s.res.observe)}`).toBe(false)
}

/** Compte d'essai du rôle LIVRÉ `nomRole` (société démo) ; renvoie son id. */
const compteRole = (nom, nomRole, prenom = 'Essai', famille = '') => py(`from apps.roles.models import Role
u = compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}).pk, societe=${SOC})
u.first_name = ${J(prenom)}; u.last_name = ${J(famille)}; u.save(update_fields=['first_name', 'last_name'])
sortie(u.id)`)

/** Navigateur À FROID du compte `nom` (connexion par l'écran de login), surveillé par les oracles. */
async function ecran(page, suivi, testInfo, nom) {
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(u.locale ? { locale: u.locale } : {}), ...(u.timezoneId ? { timezoneId: u.timezoneId } : {}), ...(u.viewport ? { viewport: u.viewport } : {}),
  })
  contextesUi.push(ctx)
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  return p
}
/** La capture de l'étape est prise sur la première page ouverte : on ferme la page démo pour capturer l'écran affirmé. */
const montrer = async (page) => { await page.close().catch(() => undefined) }
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte }).first()
const PANNE = { status: 500, contentType: 'application/json', body: J({ detail: 'Panne simulée (acceptation AERR).' }) }
/** Coupe les GET dont le chemin vérifie `cheminOk` (500 JSON) ; les autres méthodes passent. */
async function couperLecture(p, cheminOk) {
  const filtre = (u) => cheminOk(u.pathname, u)
  await p.route(filtre, (route) => (route.request().method() === 'GET' ? route.fulfill(PANNE) : route.fallback()))
  return () => p.unroute(filtre)
}
/** Compteur de requêtes (méthode + chemin) observées par la page. */
function compteur(p, methode, cheminOk) {
  const c = { n: 0, corps: [], urls: [] }
  p.on('request', (r) => {
    if (r.method() !== methode) return
    const u = new URL(r.url())
    if (!cheminOk(u.pathname, u)) return
    c.n += 1
    c.urls.push(`${u.pathname}${u.search}`)
    c.corps.push(r.postData() || '')
  })
  return c
}

/** Leads de la société démo, propriétaire `owner` ; `liste` = champs du modèle. Renvoie leurs pk. */
const creerLeads = (owner, liste) => py(`from apps.crm.models import Lead
out = []
for d in json.loads(${J(J(liste))}):
    out.append(Lead.objects.create(company_id=${SOC}, owner_id=${owner}, **d).pk)
sortie(out)`)
const supprimerLeads = (pks) => py(`from apps.crm.models import Lead
try:
    from apps.ventes.models import Devis
    Devis.all_objects.filter(lead_id__in=${J(pks)}).delete() if hasattr(Devis, 'all_objects') else Devis.objects.filter(lead_id__in=${J(pks)}).delete()
except Exception as exc:
    print('devis', exc)
for pk in ${J(pks)}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`)
/** Étape de relance (RelanceEtape) due aujourd'hui sur le lead. */
const creerEtapes = (lead, etapes) => py(`from apps.crm.models import RelanceEtape, Lead
l = Lead.objects.get(pk=${lead})
out = []
for i, d in enumerate(json.loads(${J(J(etapes))})):
    out.append(RelanceEtape.objects.create(company_id=l.company_id, lead=l, ordre=i + 1, due_at=timezone.now(),
        due_date=timezone.localdate(), **d).pk)
sortie(out)`)

// ═══ PF12 — AERR100 : /crm/leads, fiche ouverte, relecture de la liste coupée ⇒ liste + fiche gardées, avis + Réessayer ;
// une autosauvegarde réussie change sa seule ligne sans relire la liste ═══
etapeCR('PF12.1-AERR100', ['AERR100'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-044')
  const m = marque()
  const nom = `aerr100_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const ids = await creerLeads(cr, ['A', 'B', 'C'].map((x) => ({ nom: `AERR100 ${x} ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' })))
  apres.push(() => supprimerLeads(ids))
  const p = await ecran(page, suivi, testInfo, nom)
  const lignes = p.locator('tr.lv-row').filter({ hasText: m })
  const ligneB = lignes.filter({ hasText: `AERR100 B ${m}` })
  await p.goto(`/crm/leads?view=liste&q=${m}`)
  await expect(lignes, 'les 3 leads sont listés').toHaveCount(3, { timeout: 60_000 })
  await ligneB.locator('button.lv-lead-name').click()
  const fiche = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: new RegExp(`AERR100 B ${m}`) }) })
  await expect(fiche, 'la fiche du 2e lead est ouverte').toBeVisible({ timeout: 60_000 })
  // Panne : la relecture de la liste (GET /crm/leads/?page=…) répond 500 — coupée AVANT tout geste.
  suivi.attendre(/\/api\/django\/crm\/leads\/\?/, 500)
  const retablir = await couperLecture(p, (ch) => ch === `${API}/crm/leads/`)
  const avis = p.getByTestId('leads-pas-a-jour')
  // 1) API coupée puis un champ modifié : l'autosauvegarde réussie change sa seule ligne, AUCUNE relecture de la liste.
  const relectures = compteur(p, 'GET', (ch) => ch === `${API}/crm/leads/`)
  // Ville canonique (le serveur normalise la ville saisie : « Fes x » est servie « Fès ») : on tape un nom déjà canonique.
  const ville = 'Rabat'
  const patchVille = p.waitForResponse((r) => r.url().endsWith(`/crm/leads/${ids[1]}/`) && r.request().method() === 'PATCH'
    && (r.request().postData() || '').includes(ville), T)
  const historique = p.waitForResponse((r) => r.url().includes(`/crm/leads/${ids[1]}/historique/`), T)
  await fiche.locator('#lf-ville').fill(ville)
  expect((await patchVille).status(), 'autosauvegarde réussie').toBe(200)
  await historique
  await expect(ligneB, 'la ligne du lead porte la ville enregistrée').toContainText(ville, { timeout: 15_000 })
  expect(relectures.n, `aucune relecture de toute la liste après l'autosauvegarde : ${relectures.urls.join(', ')}`).toBe(0)
  await expect(avis, 'aucune relecture ⇒ aucun avis').toHaveCount(0)
  // 2) Geste qui relit la liste : changement d'étape au clavier (« 2 » → Contacté) ⇒ relecture en 500.
  await fiche.getByRole('heading', { name: new RegExp(`AERR100 B ${m}`) }).click()
  const patchEtape = p.waitForResponse((r) => r.url().endsWith(`/crm/leads/${ids[1]}/`) && r.request().method() === 'PATCH'
    && (r.request().postData() || '').includes('CONTACTED'), T)
  await p.keyboard.press('2')
  expect((await patchEtape).status(), 'changement d\'étape enregistré').toBe(200)
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis).toContainText('Liste pas à jour')
  // La fiche est modale (Radix) : la liste derrière est `aria-hidden`, d'où un repérage CSS du bouton.
  const reessayer = avis.locator('button', { hasText: 'Réessayer' })
  await expect(reessayer, 'bouton « Réessayer » de l\'avis').toBeVisible()
  await expect(fiche, 'la fiche reste montée').toBeVisible()
  await expect(lignes, 'les 3 lignes restent').toHaveCount(3)
  await expect(ligneB, 'la ligne garde la ville').toContainText(ville)
  await expect(avis, 'l\'avis reste tant que la relecture n\'a pas réussi').toBeVisible()
  // Réessayer après rétablissement (fiche fermée : la liste redevient cliquable) : l'avis s'efface.
  await fiche.getByRole('button', { name: 'Fermer' }).first().click()
  await expect(fiche).toHaveCount(0)
  await retablir()
  await reessayer.click()
  await expect(avis, 'relecture réussie : avis effacé').toHaveCount(0, { timeout: 30_000 })
  const lu = await py(`from apps.crm.models import Lead
l = Lead.objects.get(pk=${ids[1]}); sortie([l.stage, l.ville])`)
  expect(lu, 'en base : étape et ville du 2e lead').toEqual(['CONTACTED', ville])
  // Persistance : recharger relit le serveur.
  await p.goto(`/crm/leads?view=liste&q=${m}`)
  await expect(lignes, 'après rechargement : 3 lignes').toHaveCount(3, { timeout: 60_000 })
  await expect(ligneB).toContainText(ville)
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR101 : /crm/cockpit, « Fait » puis relecture coupée ⇒ file et verdict gardés, avis + Réessayer ═══
etapeCR('PF12.2-AERR101', ['AERR101'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-045')
  const m = marque()
  const nom = `aerr101_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `AERR101 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  apres.push(() => supprimerLeads([lead]))
  const libelles = [1, 2, 3].map((i) => `Appel AERR101-${i} ${m}`)
  await creerEtapes(lead, libelles.map((libelle) => ({ cadence: 'contact', canal: 'appel', libelle })))
  const p = await ecran(page, suivi, testInfo, nom)
  await p.goto('/crm/cockpit')
  const widget = p.getByTestId('relances-du-jour-widget')
  const ligne = (lib) => widget.getByTestId('relance-etape-row').filter({ hasText: lib })
  for (const lib of libelles) await expect(ligne(lib), `touche « ${lib} » affichée`).toBeVisible({ timeout: 60_000 })
  const verdict = p.getByTestId('controle-verdict')
  await expect(verdict, 'verdict du contrôle lu').toBeVisible({ timeout: 60_000 })
  // Panne de la relecture : file et contrôle répondent 500.
  suivi.attendre(/\/api\/django\/crm\/relance-etapes\/(controle\/)?\?/, 500)
  const retablir = await couperLecture(p, (ch) => ch === `${API}/crm/relance-etapes/` || ch === `${API}/crm/relance-etapes/controle/`)
  // Geste : « Fait » sur la 1re touche, réponse « Répondeur », confirmer.
  const l1 = ligne(libelles[0])
  await l1.getByRole('button', { name: 'Fait', exact: true }).click()
  await l1.getByRole('button', { name: 'Répondeur', exact: true }).click()
  const fait = p.waitForResponse((r) => /\/crm\/relance-etapes\/\d+\/fait\/$/.test(r.url()), T)
  await l1.getByRole('button', { name: 'Confirmer', exact: true }).click()
  expect((await fait).status(), '« Fait » enregistré').toBeLessThan(300)
  const avisFile = p.getByTestId('file-pas-a-jour')
  const avisControle = p.getByTestId('controle-pas-a-jour')
  await expect(avisFile, 'file : avis « Pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avisFile).toContainText('Pas à jour')
  await expect(avisControle, 'contrôle : avis « Pas à jour »').toBeVisible({ timeout: 30_000 })
  for (const lib of libelles.slice(1)) await expect(ligne(lib), `touche « ${lib} » toujours affichée`).toBeVisible()
  await expect(verdict, 'le verdict déjà lu reste').toBeVisible()
  await expect(widget.getByText('Indisponible pour le moment.'), 'jamais « Indisponible » quand des touches sont en mémoire').toHaveCount(0)
  // Réessayer réussi : les avis s'effacent.
  await retablir()
  await avisFile.getByRole('button', { name: 'Réessayer' }).click()
  await avisControle.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avisFile, 'file relue : avis effacé').toHaveCount(0, { timeout: 30_000 })
  await expect(avisControle, 'contrôle relu : avis effacé').toHaveCount(0, { timeout: 30_000 })
  const statut = await py(`from apps.crm.models import RelanceEtape
sortie(RelanceEtape.objects.get(lead_id=${lead}, libelle=${J(libelles[0])}).statut)`)
  expect(statut, 'en base : la touche est traitée').not.toBe('a_faire')
  await p.reload()
  await expect(ligne(libelles[1]), 'après rechargement : la 2e touche est due').toBeVisible({ timeout: 60_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR102 : fiche lead → « Appeler », lecture des étapes coupée ⇒ « Étapes de suivi illisibles » + Réessayer ═══
etapeCR('PF12.3-AERR102', ['AERR102'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-046')
  const m = marque()
  const nom = `aerr102_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `AERR102 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  apres.push(() => supprimerLeads([lead]))
  const libelle = `Appel AERR102 ${m}`
  await creerEtapes(lead, [{ cadence: 'contact', canal: 'appel', libelle }])
  const p = await ecran(page, suivi, testInfo, nom)
  const frise = p.waitForResponse((r) => r.url().includes('/crm/relance-etapes/?') && r.url().includes(`lead=${lead}`), T)
  await p.goto(`/crm/leads/${lead}`)
  await frise
  const rail = p.getByTestId('lw-identity-rail')
  await expect(rail).toBeVisible({ timeout: 60_000 })
  suivi.attendre(new RegExp(`/api/django/crm/relance-etapes/\\?.*lead=${lead}`), 500)
  const retablir = await couperLecture(p, (ch, u) => ch === `${API}/crm/relance-etapes/` && u.searchParams.get('lead') === String(lead))
  await rail.getByRole('button', { name: "Plus d'actions" }).click()
  await p.getByRole('menuitem', { name: /Appeler$/ }).click()
  const fenetre = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: /^Appel — / }) })
  await expect(fenetre, 'fenêtre « Appel » ouverte').toBeVisible({ timeout: 30_000 })
  const illisibles = fenetre.getByTestId('lw-appel-etapes-illisibles')
  await expect(illisibles, '« Étapes de suivi illisibles »').toBeVisible({ timeout: 30_000 })
  await expect(illisibles).toContainText('Étapes de suivi illisibles')
  await expect(fenetre.getByText(/Aucune étape de suivi ouverte/), 'jamais « relancez la cadence » sur une panne').toHaveCount(0)
  await retablir()
  await illisibles.getByRole('button', { name: 'Réessayer' }).click()
  await expect(fenetre.getByTestId('lw-appel-touches'), 'Réessayer relit et montre la touche').toContainText(libelle, { timeout: 30_000 })
  await expect(illisibles).toHaveCount(0)
  // Persistance (lecture) : rechargée, la fenêtre montre la touche ouverte.
  await p.keyboard.press('Escape')
  await p.reload()
  await expect(rail).toBeVisible({ timeout: 60_000 })
  await rail.getByRole('button', { name: "Plus d'actions" }).click()
  await p.getByRole('menuitem', { name: /Appeler$/ }).click()
  await expect(p.getByTestId('lw-appel-touches'), 'après rechargement : touche affichée').toContainText(libelle, { timeout: 30_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR103 : journal d'appel, report de relance en 500 ⇒ « Appel journalisé ; la relance n'a pas pu être
// planifiée », 2e essai sans 2e journal ═══
etapeCR('PF12.4-AERR103', ['AERR103'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-047')
  const m = marque()
  const nom = `aerr103_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `AERR103 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  apres.push(() => supprimerLeads([lead]))
  const p = await ecran(page, suivi, testInfo, nom)
  await p.goto(`/crm/leads/${lead}`)
  const rail = p.getByTestId('lw-context-rail')
  await expect(rail).toBeVisible({ timeout: 60_000 })
  const journaux = compteur(p, 'POST', (ch) => ch === `${API}/crm/leads/${lead}/log-interaction/`)
  const reports = compteur(p, 'PATCH', (ch) => ch === `${API}/crm/leads/${lead}/`)
  // Panne : le 1er PATCH du lead (report de relance) répond 500, le suivant passe.
  suivi.attendre(new RegExp(`/api/django/crm/leads/${lead}/$`), 500)
  let premier = true
  await p.route((u) => u.pathname === `${API}/crm/leads/${lead}/`, (route) => {
    if (route.request().method() === 'PATCH' && premier) { premier = false; return route.fulfill(PANNE) }
    return route.fallback()
  })
  await rail.getByRole('button', { name: 'Journaliser', exact: true }).click()
  const pop = p.getByRole('dialog').filter({ hasText: 'Journaliser un appel' })
  await expect(pop).toBeVisible({ timeout: 30_000 })
  await pop.getByRole('group', { name: "Résultat de l'appel" }).getByRole('button', { name: 'Non joint' }).click()
  await pop.getByRole('button', { name: 'Demain', exact: true }).click()
  await pop.getByRole('button', { name: 'Enregistrer', exact: true }).click()
  const MSG = "Appel journalisé ; la relance n'a pas pu être planifiée — réessayez."
  await expect(toast(p, MSG), 'message par étape : appel journalisé, relance non planifiée').toBeVisible({ timeout: 30_000 })
  await expect(p.getByText("L'appel n'a pas pu être journalisé"), 'jamais « L\'appel n\'a pas pu être journalisé »').toHaveCount(0)
  await expect(pop, 'la fenêtre reste ouverte avec la saisie').toBeVisible()
  expect([journaux.n, reports.n], '1er essai : 1 journal, 1 report (refusé)').toEqual([1, 1])
  await pop.getByRole('button', { name: 'Enregistrer', exact: true }).click()
  await expect(toast(p, 'Relance planifiée.'), '2e essai : « Relance planifiée. »').toBeVisible({ timeout: 30_000 })
  expect([journaux.n, reports.n], '2e essai : journal NON rejoué, report rejoué').toEqual([1, 2])
  const lu = await py(`from apps.crm.models import Lead, LeadActivity
l = Lead.objects.get(pk=${lead})
sortie([LeadActivity.objects.filter(lead_id=${lead}, kind='appel').count(), str(l.relance_date)])`)
  const demain = new Date(); demain.setDate(demain.getDate() + 1)
  expect(lu, 'en base : UN appel journalisé, relance au lendemain').toEqual([1, isoJour(demain)])
  // Persistance : rouvrir le chatter ⇒ un seul appel journalisé.
  await p.unrouteAll({ behavior: 'ignoreErrors' })
  await p.reload()
  await expect(rail).toBeVisible({ timeout: 60_000 })
  const histo = await p.request.get(`${API}/crm/leads/${lead}/historique/`, T)
  expect(histo.status()).toBe(200)
  const corps = J(await histo.json())
  expect((corps.match(/"kind":\s*"appel"/g) || []).length, 'historique relu : un seul appel').toBe(1)
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR104 : « Lead express » avec « abc@ » ⇒ refus du serveur sous « E-mail », boîte ouverte, saisie gardée ═══
etapeCR('PF12.5-AERR104', ['AERR104'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-048')
  const m = marque()
  const nom = `aerr104_${m}`
  await compteRole(nom, 'Commercial responsable')
  const p = await ecran(page, suivi, testInfo, nom)
  await p.goto('/crm/leads')
  await p.getByRole('button', { name: "Plus d'actions" }).first().click({ timeout: 60_000 })
  await p.getByRole('menuitem', { name: /Express/ }).click()
  const boite = p.getByRole('dialog').filter({ hasText: 'Nouveau lead express' })
  await expect(boite).toBeVisible({ timeout: 30_000 })
  const nomLead = `AERR104 ${m}`
  const champNom = boite.getByLabel(/^Nom/)
  await champNom.fill(nomLead)
  const email = boite.getByLabel('E-mail')
  await email.fill('abc@')
  suivi.attendre(/\/api\/django\/crm\/leads\/$/, 400)
  const refus = p.waitForResponse((r) => r.url().endsWith('/crm/leads/') && r.request().method() === 'POST', T)
  await boite.getByRole('button', { name: 'Créer le lead' }).click()
  const r = await refus
  expect(r.status(), 'le serveur refuse l\'e-mail mal formé').toBe(400)
  const msg = (await r.json()).email?.[0]
  expect(msg, 'refus nommé sur le champ email').toBeTruthy()
  await expect(email, 'champ E-mail en erreur').toHaveAttribute('aria-invalid', 'true')
  const sous = boite.locator(`[id="${await email.getAttribute('id')}-error"]`)
  await expect(sous, `« ${msg} » sous E-mail`).toContainText(msg)
  await expect(boite, 'la boîte reste ouverte').toBeVisible()
  await expect(champNom, 'nom gardé').toHaveValue(nomLead)
  await expect(email, 'e-mail gardé').toHaveValue('abc@')
  await expect(p.getByText('Erreur lors de la création du lead.'), 'aucun message générique').toHaveCount(0)
  await email.fill('abc@example.invalid')
  await expect(sous, 'corriger l\'e-mail efface le message').toHaveCount(0)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  expect(await py(`from apps.crm.models import Lead
sortie(Lead.all_objects.filter(nom=${J(nomLead)}).count())`), 'rien n\'est écrit sur refus').toBe(0)
  await p.reload()
  await expect(p.getByRole('button', { name: "Plus d'actions" }).first()).toBeVisible({ timeout: 60_000 })
  await expect(p.getByText(nomLead), 'après rechargement : aucun lead créé').toHaveCount(0)
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR105 : fiche → Visite → RDV « Annuler » ⇒ boîte nommée (date, heure), rien sans confirmation ═══
etapeCR('PF12.6-AERR105', ['AERR105'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-049')
  const m = marque()
  const nom = `aerr105_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `AERR105 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  apres.push(() => supprimerLeads([lead]))
  const rdv = await py(`from datetime import timedelta, time
from apps.crm.models import Appointment, Lead
l = Lead.objects.get(pk=${lead})
quand = timezone.make_aware(datetime.datetime.combine(timezone.localdate() + timedelta(days=3), time(10, 0)))
a = Appointment.objects.create(company_id=l.company_id, lead=l, scheduled_at=quand, statut='planifie', notes='RDV AERR105 ${m}')
sortie(dict(id=a.pk, iso=quand.isoformat()))`)
  const p = await ecran(page, suivi, testInfo, nom)
  const ouvrirRdv = async () => {
    await p.goto(`/crm/leads/${lead}`)
    await p.getByRole('navigation', { name: 'Sections du lead' }).getByRole('button', { name: /Visite technique/ }).click({ timeout: 60_000 })
    await p.locator('summary').filter({ hasText: 'Autre rendez-vous' }).click()
  }
  await ouvrirRdv()
  const ligne = p.locator('.lw-booker-row').filter({ hasText: `RDV AERR105 ${m}` })
  await expect(ligne, 'le RDV est listé').toBeVisible({ timeout: 30_000 })
  const [jour, heure] = await p.evaluate((iso) => {
    const d = new Date(iso)
    return [d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }), d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })]
  }, rdv.iso)
  const annulations = compteur(p, 'PATCH', (ch) => ch === `${API}/crm/appointments/${rdv.id}/`)
  // 1er tour : « Annuler » puis « Garder » ⇒ rien ne part.
  await ligne.getByTitle('Annuler ce rendez-vous').click()
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'la boîte nomme la date et l\'heure').toContainText(`Annuler le rendez-vous du ${jour}`)
  await expect(boite).toContainText(heure)
  await boite.getByRole('button', { name: 'Garder' }).click()
  await expect(boite).toHaveCount(0)
  await expect(ligne, '« Garder » : le RDV reste listé').toBeVisible()
  expect(annulations.n, '« Garder » : aucun updateAppointment').toBe(0)
  expect(await py(`from apps.crm.models import Appointment
sortie(Appointment.objects.get(pk=${rdv.id}).statut)`), 'en base : toujours planifié').toBe('planifie')
  // 2e tour : « Annuler le rendez-vous » ⇒ un seul PATCH, le RDV quitte la liste.
  await ligne.getByTitle('Annuler ce rendez-vous').click()
  await boite.getByRole('button', { name: 'Annuler le rendez-vous' }).click()
  await expect(ligne, 'confirmé : le RDV quitte la liste').toHaveCount(0, { timeout: 30_000 })
  expect(annulations.n, 'un seul updateAppointment').toBe(1)
  expect(annulations.corps[0], 'statut annulé').toContain('"annule"')
  expect(await py(`from apps.crm.models import Appointment
sortie(Appointment.objects.get(pk=${rdv.id}).statut)`), 'en base : annulé après confirmation').toBe('annule')
  await ouvrirRdv()
  await expect(p.locator('summary').filter({ hasText: 'Autre rendez-vous' })).toBeVisible()
  await expect(ligne, 'après rechargement : RDV annulé, hors liste').toHaveCount(0)
  await auRepos(suivi)
  await montrer(page)
})

// Visite terrain en cours du compte `owner`, avec une photo « tableau ouvert » envoyée par l'API (MinIO du runner).
async function visiteAvecPhoto(p, owner, m) {
  const [lead] = await creerLeads(owner, [{ nom: `AERR10x ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  const v = await py(`from apps.visites.models import VisiteTerrain
from apps.crm.models import Lead
l = Lead.objects.get(pk=${lead})
v = VisiteTerrain.objects.create(company_id=l.company_id, lead=l, commercial_id=${owner}, statut='en_cours', gabarit='toiture', date_prevue=timezone.localdate())
sortie(v.pk)`)
  const r = await p.request.post(`${API}/visites/visites/${v}/photos/`, {
    ...T, multipart: { slot_code: 'tableau_ouvert', fichier: { name: `tableau-${m}.png`, mimeType: 'image/png', buffer: PNG_1PX } },
  })
  expect(r.status(), `photo envoyée : ${(await r.text()).slice(0, 200)}`).toBeLessThan(300)
  const media = await py(`from apps.visites.models import VisiteMedia
x = VisiteMedia.objects.filter(visite_id=${v}).select_related('attachment').first()
sortie(dict(id=x.pk, filename=x.attachment.filename))`)
  return { lead, visite: v, media }
}
const nbMedias = (v) => py(`from apps.visites.models import VisiteMedia
sortie(VisiteMedia.objects.filter(visite_id=${v}).count())`)

// ═══ PF12 — AERR106 : /visites/<id>, croix d'une photo ⇒ boîte qui nomme le fichier et l'emplacement, rien sans « Supprimer » ═══
etapeCR('PF12.7-AERR106', ['AERR106'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-050')
  const m = marque()
  const nom = `aerr106_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const p = await ecran(page, suivi, testInfo, nom)
  const { lead, visite, media } = await visiteAvecPhoto(p, cr, m)
  apres.push(() => supprimerLeads([lead]))
  const ouvrir = async () => {
    await p.goto(`/visites/${visite}`)
    await p.getByRole('tab', { name: 'Tableau électrique' }).click({ timeout: 60_000 })
  }
  await ouvrir()
  const croix = p.getByRole('button', { name: `Supprimer la photo ${media.filename}` })
  await expect(croix, 'la vignette est affichée').toBeVisible({ timeout: 30_000 })
  const suppressions = compteur(p, 'DELETE', (ch) => ch === `${API}/visites/visites/${visite}/photos/${media.id}/`)
  await croix.click()
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'la boîte nomme le fichier').toContainText(`Supprimer la photo « ${media.filename} »`)
  await expect(boite, 'et l\'emplacement').toContainText('Tableau ouvert')
  await expect(boite).toContainText('Elle ne pourra pas être récupérée.')
  await boite.getByRole('button', { name: 'Garder' }).click()
  await expect(boite).toHaveCount(0)
  await expect(croix, '« Garder » : la vignette reste').toBeVisible()
  expect(suppressions.n, '« Garder » : aucun deleteVisitePhoto').toBe(0)
  expect(await nbMedias(visite), 'en base : photo présente').toBe(1)
  await ouvrir()
  await expect(croix, 'après rechargement : photo présente tant que non confirmé').toBeVisible({ timeout: 30_000 })
  await croix.click()
  const reponseSuppr = p.waitForResponse((r) => r.request().method() === 'DELETE' && r.url().includes(`/visites/visites/${visite}/photos/`), T)
  await boite.getByRole('button', { name: 'Supprimer', exact: true }).click()
  const rs = await reponseSuppr
  expect(rs.status(), `suppression servie : ${(await rs.text()).slice(0, 300)}`).toBe(200)
  await expect(croix, 'confirmé : la vignette disparaît').toHaveCount(0, { timeout: 30_000 })
  expect(suppressions.n, 'un seul deleteVisitePhoto').toBe(1)
  const restants = () => py(`from apps.visites.models import VisiteMedia
sortie([[x.pk, x.slot_code, x.attachment_id] for x in VisiteMedia.objects.filter(visite_id=${visite})])`)
  await expect.poll(restants, { timeout: 15_000, message: `en base : photo ${media.id} supprimée` }).toEqual([])
  await ouvrir()
  await expect(p.getByTestId('visite-slot-tableau_ouvert')).toBeVisible({ timeout: 30_000 })
  await expect(croix, 'après rechargement : photo absente').toHaveCount(0)
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR107 : /visites/<id>, mesure tapée, relecture coupée puis photo envoyée ⇒ saisie et onglets gardés,
// avis + Réessayer ; premier chargement raté ⇒ « Visite introuvable ou inaccessible. » ═══
etapeCR('PF12.8-AERR107', ['AERR107'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-051')
  const m = marque()
  const nom = `aerr107_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const p = await ecran(page, suivi, testInfo, nom)
  const { lead, visite } = await visiteAvecPhoto(p, cr, m)
  apres.push(() => supprimerLeads([lead]))
  await p.goto(`/visites/${visite}`)
  await p.getByRole('tab', { name: 'Toiture' }).click({ timeout: 60_000 })
  const longueur = p.locator('#visite-mesure-toiture-longueur_m')
  await longueur.fill('12.5')
  // Panne : la relecture de la visite (GET /visites/visites/<id>/) répond 500.
  suivi.attendre(new RegExp(`/api/django/visites/visites/${visite}/$`), 500)
  const retablir = await couperLecture(p, (ch) => ch === `${API}/visites/visites/${visite}/`)
  // Photo envoyée depuis l'écran (repli fichier de la caméra) : la page relit la visite après l'envoi.
  await p.getByRole('tab', { name: 'Tableau électrique' }).click()
  const slot = p.getByTestId('visite-slot-tableau_ouvert')
  await slot.getByRole('button', { name: 'Ajouter une photo' }).click()
  const envoi = p.waitForResponse((r) => r.url().endsWith(`/visites/visites/${visite}/photos/`) && r.request().method() === 'POST', T)
  const fichierInput = slot.getByTestId('camera-file-fallback')
  await expect(fichierInput, 'repli fichier de la caméra (navigateur sans caméra)').toBeAttached({ timeout: 30_000 })
  await fichierInput.setInputFiles({ name: `compteur-${m}.png`, mimeType: 'image/png', buffer: PNG_1PX })
  expect((await envoi).status(), 'photo envoyée').toBeLessThan(300)
  const avis = p.getByTestId('visite-pas-a-jour')
  await expect(avis, 'avis « Visite pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis).toContainText('Visite pas à jour')
  await expect(p.getByText('Visite introuvable ou inaccessible.'), 'jamais « introuvable » sur une relecture').toHaveCount(0)
  await expect(p.getByRole('tab', { name: 'Toiture' }), 'les onglets restent').toBeVisible()
  await p.getByRole('tab', { name: 'Toiture' }).click()
  await expect(longueur, 'la mesure tapée reste dans son champ').toHaveValue('12.5')
  await retablir()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis, 'relecture réussie : avis effacé').toHaveCount(0, { timeout: 30_000 })
  await expect(longueur, 'la saisie survit à la relecture réussie').toHaveValue('12.5')
  expect(await nbMedias(visite), 'en base : la photo envoyée est enregistrée (2 photos)').toBe(2)
  // Premier chargement rejeté : « Visite introuvable ou inaccessible. » reste affiché.
  const retablir2 = await couperLecture(p, (ch) => ch === `${API}/visites/visites/${visite}/`)
  await p.reload()
  await expect(p.getByText('Visite introuvable ou inaccessible.'), 'premier chargement raté : message d\'origine').toBeVisible({ timeout: 60_000 })
  await retablir2()
  await p.reload()
  await expect(p.getByRole('tab', { name: 'Toiture' }), 'chargement rétabli').toBeVisible({ timeout: 60_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR108 : frappe < 1,5 s puis démontage (menu latéral) ⇒ PATCH ; « doublon » ⇒ PATCH avant getLead(doublon) ═══
etapeCR('PF12.9-AERR108', ['AERR108'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-052')
  const m = marque()
  const nom = `aerr108_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const tel = telephoneMobileUnique()
  const [a, b] = await creerLeads(cr, [
    { nom: `AERR108 A ${m}`, prenom: 'Essai', telephone: tel, stage: 'NEW' },
    { nom: `AERR108 B ${m}`, prenom: 'Essai', telephone: tel, stage: 'NEW' },
  ])
  apres.push(() => supprimerLeads([a, b]))
  // Une section complète (ville renseignée) se replie à l'ouverture : on la déplie par sa puce de navigation.
  const deplierContact = async (pg) => {
    await pg.getByRole('navigation', { name: 'Sections du lead' }).getByRole('button', { name: 'Contact', exact: true }).click({ timeout: 60_000 })
    await expect(pg.locator('#lf-ville')).toBeVisible({ timeout: 30_000 })
  }
  const villeDe = (pk) => py(`from apps.crm.models import Lead
sortie(Lead.objects.get(pk=${pk}).ville)`)
  const p = await ecran(page, suivi, testInfo, nom)
  // 1) Pleine page : frappe puis clic immédiat sur un menu latéral (débounce de 1,5 s non échu).
  await p.goto(`/crm/leads/${a}`)
  const ville = p.locator('#lf-ville')
  await expect(ville).toBeVisible({ timeout: 60_000 })
  // Villes déjà canoniques (le serveur normalise la ville saisie : « Fes x » est servie « Fès »).
  const v1 = 'Agadir'
  const patch1 = p.waitForRequest((r) => r.url().endsWith(`/crm/leads/${a}/`) && r.method() === 'PATCH' && (r.postData() || '').includes(v1), T)
  const menu = p.locator('aside.sidebar a[href^="/"]:not([href^="/crm/leads"])').filter({ visible: true }).first()
  await ville.fill(v1)
  await menu.click()
  await expect(p, 'la fiche est quittée').not.toHaveURL(new RegExp(`/crm/leads/${a}$`))
  await patch1
  await expect.poll(() => villeDe(a), { timeout: 30_000, message: 'en base : la ville tapée est enregistrée' }).toBe(v1)
  // Rouvrir le lead dans un autre onglet : la ville est servie par le serveur.
  const onglet = await ecran(page, suivi, testInfo, nom)
  await onglet.goto(`/crm/leads/${a}`)
  await deplierContact(onglet)
  await expect(onglet.locator('#lf-ville'), 'autre onglet : ville servie').toHaveValue(v1, { timeout: 60_000 })
  await onglet.close()
  // 2) Liste : frappe puis lien du doublon ⇒ le PATCH part AVANT la lecture du doublon.
  const ordre = []
  p.on('request', (r) => {
    const ch = new URL(r.url()).pathname
    if (r.method() === 'PATCH' && ch === `${API}/crm/leads/${a}/`) ordre.push('patch-a')
    if (r.method() === 'GET' && ch === `${API}/crm/leads/${b}/`) ordre.push('get-b')
  })
  await p.goto(`/crm/leads?lead=${a}`)
  const fiche = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: new RegExp(`AERR108 A ${m}`) }) })
  await deplierContact(p)
  const lien = fiche.locator('.lw-dup-warning .lw-dup-link').filter({ hasText: `AERR108 B ${m}` })
  await expect(lien, 'doublon signalé').toBeVisible({ timeout: 60_000 })
  const v2 = 'Tanger'
  await fiche.locator('#lf-ville').fill(v2)
  await lien.click()
  await expect(p.getByRole('heading', { name: new RegExp(`AERR108 B ${m}`) }), 'la fiche bascule sur le doublon').toBeVisible({ timeout: 30_000 })
  await expect.poll(() => ordre.join(','), { timeout: 30_000 }).toContain('get-b')
  expect(ordre.indexOf('patch-a'), `PATCH du brouillon avant getLead(doublon) : ${ordre.join(',')}`).toBeGreaterThanOrEqual(0)
  expect(ordre.indexOf('patch-a')).toBeLessThan(ordre.indexOf('get-b'))
  await expect.poll(() => villeDe(a), { timeout: 30_000, message: 'en base : 2e frappe enregistrée' }).toBe(v2)
  await p.goto(`/crm/leads/${a}`)
  await deplierContact(p)
  await expect(p.locator('#lf-ville'), 'après rechargement : ville servie').toHaveValue(v2, { timeout: 60_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR108 (création) : fiche en création remplie, lien du doublon ⇒ question avant de quitter ═══
etapeCR('PF12.9b-AERR108-creation', ['AERR108'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr108c_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const tel = telephoneMobileUnique()
  const [a] = await creerLeads(cr, [{ nom: `AERR108C ${m}`, prenom: 'Essai', telephone: tel, stage: 'NEW' }])
  apres.push(() => supprimerLeads([a]))
  const p = await ecran(page, suivi, testInfo, nom)
  const questions = []
  p.on('dialog', (d) => questions.push(`${d.type()} : ${d.message()}`))
  const lectures = compteur(p, 'GET', (ch) => ch === `${API}/crm/leads/${a}/`)
  await p.goto('/crm/leads?new=1')
  const fiche = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: 'Nouveau lead' }) })
  await expect(fiche).toBeVisible({ timeout: 60_000 })
  await fiche.locator('#lf-nom').fill(`AERR108C nouveau ${m}`)
  await fiche.locator('#lf-telephone').fill(tel)
  const lien = fiche.locator('.lw-dup-warning .lw-dup-link').filter({ hasText: `AERR108C ${m}` })
  await expect(lien, 'doublon signalé en création').toBeVisible({ timeout: 30_000 })
  await lien.click()
  await expect.poll(() => questions.length, { timeout: 15_000, message: 'une question est posée avant de quitter' }).toBe(1)
  expect(questions[0], `question posée : ${questions[0]}`).toMatch(/quitter/i)
  // Refusée (l'oracle referme la boîte native par « Annuler ») : la fiche en création reste, le doublon n'est pas ouvert.
  await expect(fiche, 'la fiche en création reste').toBeVisible()
  await expect(fiche.locator('#lf-nom')).toHaveValue(`AERR108C nouveau ${m}`)
  expect(lectures.n, 'le doublon n\'est pas lu').toBe(0)
  expect(await py(`from apps.crm.models import Lead
sortie(Lead.all_objects.filter(nom=${J(`AERR108C nouveau ${m}`)}).count())`), 'rien n\'est créé').toBe(0)
  await auRepos(suivi)
  await montrer(page)
}, { natif: true })

// Évènement d'agenda modifiable (activité du compte, rattachée à son lead) daté du `jour` du mois courant.
const MOIS = new Date()
const jourDuMois = (j) => `${MOIS.getFullYear()}-${pad(MOIS.getMonth() + 1)}-${pad(j)}`
async function activiteAgenda(owner, titre, jour) {
  const [lead] = await creerLeads(owner, [{ nom: `Agenda ${titre}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  const act = await py(`from django.contrib.contenttypes.models import ContentType
from apps.crm.models import Lead
from apps.records.models import Activity
l = Lead.objects.get(pk=${lead})
a = Activity.objects.create(company_id=l.company_id, content_type=ContentType.objects.get_for_model(Lead), object_id=l.pk,
    summary=${J(titre)}, due_date=datetime.date.fromisoformat(${J(jourDuMois(jour))}), done=False,
    created_by_id=${owner}, assigned_to_id=${owner})
sortie(a.pk)`)
  return { lead, act }
}
const dateActivite = (pk) => py(`from apps.records.models import Activity
sortie(str(Activity.objects.get(pk=${pk}).due_date))`)
const cellule = (p, j) => p.locator('.cal-cell:not(.cal-cell-out)').filter({ has: p.locator('.cal-day-number', { hasText: new RegExp(`^${j}$`) }) })

// ═══ PF12 — AERR110 : /calendrier, glisser une activité du 10 au 12 ⇒ boîte « Déplacer « titre » du 10/MM au 12/MM ? » ═══
etapeCR('PF12.11-AERR110', ['AERR110'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr110_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const titre = `Rappel AERR110 ${m}`
  const { lead, act } = await activiteAgenda(cr, titre, 10)
  apres.push(() => supprimerLeads([lead]))
  apres.push(() => py(`from apps.records.models import Activity
Activity.objects.filter(pk=${act}).delete()`))
  const p = await ecran(page, suivi, testInfo, nom)
  await p.goto('/calendrier')
  const evt = (j) => cellule(p, j).locator('.cp-event').filter({ hasText: titre })
  await expect(evt(10), 'l\'activité est au 10').toBeVisible({ timeout: 60_000 })
  const replanifs = compteur(p, 'POST', (ch) => ch === `${API}/reporting/calendar/reschedule/`)
  const mm = pad(MOIS.getMonth() + 1)
  const boite = p.getByRole('alertdialog')
  // 1er tour : « Annuler » ⇒ aucun appel, l'activité reste au 10.
  await evt(10).dragTo(cellule(p, 12))
  await expect(boite, 'la boîte nomme le titre et les deux dates').toContainText(`Déplacer « ${titre} » du 10/${mm} au 12/${mm} ?`, { timeout: 30_000 })
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toHaveCount(0)
  expect(replanifs.n, '« Annuler » : aucun rescheduleCalendar').toBe(0)
  await expect(evt(10), '« Annuler » : toujours au 10').toBeVisible()
  expect(await dateActivite(act), 'en base : date inchangée').toBe(jourDuMois(10))
  // 2e tour : « Déplacer » ⇒ un seul appel, date du 12.
  await evt(10).dragTo(cellule(p, 12))
  await boite.getByRole('button', { name: 'Déplacer' }).click()
  await expect(evt(12), 'déplacée au 12').toBeVisible({ timeout: 30_000 })
  expect(replanifs.n, 'un seul rescheduleCalendar').toBe(1)
  expect(replanifs.corps[0], 'date du 12 envoyée').toContain(jourDuMois(12))
  expect(await dateActivite(act), 'en base : date changée après « Déplacer »').toBe(jourDuMois(12))
  await p.reload()
  await expect(evt(12), 'après rechargement : au 12').toBeVisible({ timeout: 60_000 })
  await expect(evt(10)).toHaveCount(0)
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR109 : /calendrier, lecture coupée ⇒ « Calendrier pas à jour » (évènements gardés) / « Calendrier
// indisponible », jamais « Aucun évènement ce mois-ci » ═══
etapeCR('PF12.10-AERR109', ['AERR109'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-053')
  const m = marque()
  const nom = `aerr109_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const titre = `Rappel AERR109 ${m}`
  const { lead, act } = await activiteAgenda(cr, titre, 10)
  apres.push(() => supprimerLeads([lead]))
  apres.push(() => py(`from apps.records.models import Activity
Activity.objects.filter(pk=${act}).delete()`))
  const p = await ecran(page, suivi, testInfo, nom)
  await p.goto('/calendrier')
  const evt = (j) => cellule(p, j).locator('.cp-event').filter({ hasText: titre })
  await expect(evt(10)).toBeVisible({ timeout: 60_000 })
  suivi.attendre(/\/api\/django\/reporting\/calendar\/\?/, 500)
  const retablir = await couperLecture(p, (ch) => ch === `${API}/reporting/calendar/`)
  // Glisser réussi suivi d'une relecture ratée : les évènements déjà affichés restent.
  await evt(10).dragTo(cellule(p, 12))
  const replanif = p.waitForResponse((r) => r.url().endsWith('/reporting/calendar/reschedule/'), T)
  await p.getByRole('alertdialog').getByRole('button', { name: 'Déplacer' }).click()
  expect((await replanif).status(), 'replanification réussie').toBe(200)
  const avis = p.getByTestId('calendrier-lecture-echec')
  await expect(avis, 'avis « Calendrier pas à jour »').toContainText('Calendrier pas à jour', { timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(p.locator('.cp-event').filter({ hasText: titre }), 'l\'évènement déjà affiché reste').toBeVisible()
  await expect(p.getByText('Aucun évènement ce mois-ci'), 'jamais « Aucun évènement »').toHaveCount(0)
  await retablir()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis, 'relecture réussie : avis effacé').toHaveCount(0, { timeout: 30_000 })
  await expect(evt(12), 'relu : l\'évènement est au 12').toBeVisible()
  expect(await dateActivite(act), 'en base : date du 12').toBe(jourDuMois(12))
  // Premier chargement rejeté : « Calendrier indisponible » + Réessayer, jamais « Aucun évènement ce mois-ci ».
  const retablir2 = await couperLecture(p, (ch) => ch === `${API}/reporting/calendar/`)
  await p.reload()
  await expect(avis, 'premier chargement raté : « Calendrier indisponible »').toContainText('Calendrier indisponible', { timeout: 60_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(p.getByText('Aucun évènement ce mois-ci'), 'jamais « Aucun évènement » sur une panne').toHaveCount(0)
  await retablir2()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(evt(12), 'Réessayer : l\'évènement revient').toBeVisible({ timeout: 30_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR111 : /crm (clients), import puis relecture coupée ⇒ lignes gardées, avis + Réessayer ═══
etape('PF12.12-AERR111', ['AERR111'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr111_${m}`
  await compteRole(nom, 'Directeur')
  const nomClient = `AERR111 ${m}`
  apres.push(() => py(`from apps.crm.models import Client
Client.objects.filter(nom=${J(nomClient)}).delete()`))
  const p = await ecran(page, suivi, testInfo, nom)
  await p.goto('/crm')
  const grille = p.getByRole('grid', { name: 'Liste des clients' })
  const lignes = grille.getByRole('row')
  await expect(lignes.nth(2), 'clients affichés').toBeVisible({ timeout: 60_000 })
  const avant = await lignes.count()
  await p.getByRole('button', { name: 'Importer', exact: true }).click()
  await p.locator('input[type="file"][accept=".csv,.xlsx"]').setInputFiles({
    name: 'clients.csv', mimeType: 'text/csv', buffer: Buffer.from(`Nom,Email\n${nomClient},aerr111-${m}@example.invalid\n`, 'utf-8'),
  })
  const importer = p.getByRole('button', { name: /^Importer 1 ligne/ })
  await expect(importer, 'aperçu de l\'import').toBeEnabled({ timeout: 60_000 })
  suivi.attendre(/\/api\/django\/crm\/clients\/\?/, 500)
  const retablir = await couperLecture(p, (ch) => ch === `${API}/crm/clients/`)
  await importer.click()
  await expect(p.getByText(/créé\(s\)/), 'import terminé').toBeVisible({ timeout: 60_000 })
  await p.getByRole('button', { name: 'Fermer', exact: true }).click()
  const avis = p.getByTestId('clients-pas-a-jour')
  await expect(avis, 'avis « Liste pas à jour »').toContainText('Liste pas à jour', { timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(lignes, 'les lignes restent').toHaveCount(avant)
  await expect(p.getByText('Impossible de charger les clients'), 'pas de bloc d\'erreur tant qu\'il y a des lignes').toHaveCount(0)
  await retablir()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis, 'relecture réussie : avis effacé').toHaveCount(0, { timeout: 30_000 })
  await expect(grille.getByRole('row').filter({ hasText: nomClient }), 'le client importé apparaît').toBeVisible({ timeout: 30_000 })
  expect(await py(`from apps.crm.models import Client
sortie(Client.objects.filter(nom=${J(nomClient)}).count())`), 'en base : client importé').toBe(1)
  // Premier chargement rejeté : le bloc d'erreur d'origine.
  const retablir2 = await couperLecture(p, (ch) => ch === `${API}/crm/clients/`)
  await p.reload()
  await expect(p.getByText('Impossible de charger les clients'), 'aucune ligne : bloc d\'erreur + Réessayer').toBeVisible({ timeout: 60_000 })
  await retablir2()
  await p.reload()
  await expect(grille.getByRole('row').filter({ hasText: nomClient }), 'rechargé : lignes servies').toBeVisible({ timeout: 60_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR113 : /crm/leads vue liste, « Archiver » / « Supprimer » d'une ligne ⇒ boîtes qui nomment le lead ═══
etape('PF12.13-AERR113', ['AERR113'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr113_${m}`
  const dir = await compteRole(nom, 'Directeur')
  const [a, b] = await creerLeads(dir, [
    { nom: `Benali ${m}`, prenom: 'Ahmed', telephone: telephoneMobileUnique(), stage: 'NEW' },
    { nom: `Tazi ${m}`, prenom: 'Salma', telephone: telephoneMobileUnique(), stage: 'NEW' },
  ])
  apres.push(() => supprimerLeads([a, b]))
  const etat = (pk) => py(`from apps.crm.models import Lead
l = Lead.all_objects.get(pk=${pk}); sortie([l.is_archived, bool(getattr(l, 'is_deleted', False))])`)
  const p = await ecran(page, suivi, testInfo, nom)
  await p.goto(`/crm/leads?view=liste&q=${m}`)
  const ligne = (n) => p.locator('tr.lv-row').filter({ hasText: n })
  const nA = `Ahmed Benali ${m}`
  await expect(ligne(`Benali ${m}`), 'lead listé').toBeVisible({ timeout: 60_000 })
  // Compte neuf : la visite guidée de l'écran (ProductTour, bulle non modale) se pose sur la liste ; on la ferme
  // par son bouton, comme un utilisateur.
  const fermerVisite = p.getByRole('button', { name: 'Fermer la visite guidée' })
  await fermerVisite.waitFor({ state: 'visible', timeout: 10_000 }).then(() => fermerVisite.click()).catch(() => undefined)
  await expect(fermerVisite).toHaveCount(0)
  const archivages = compteur(p, 'POST', (ch) => ch === `${API}/crm/leads/${a}/archiver/`)
  const boite = p.getByRole('alertdialog')
  // 1er tour : « Annuler » ⇒ aucun archiveLead.
  // Boutons de ligne hors de la fenêtre visible (cellule d'actions défilante) : focus + Entrée (geste clavier réel).
  const presser = async (bouton) => { await bouton.focus(); await p.keyboard.press('Enter') }
  await presser(ligne(`Benali ${m}`).getByRole('button', { name: 'Archiver', exact: true }))
  await expect(boite, 'la boîte nomme le lead').toContainText(`Archiver « ${nA} » ?`)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toHaveCount(0)
  expect(archivages.n, '« Annuler » : aucun archivage').toBe(0)
  expect(await etat(a), 'en base : non archivé').toEqual([false, false])
  // 2e tour : « Archiver » ⇒ un archivage, toast « Lead archivé. » nommant le lead, avec « Annuler ».
  await presser(ligne(`Benali ${m}`).getByRole('button', { name: 'Archiver', exact: true }))
  await boite.getByRole('button', { name: 'Archiver', exact: true }).click()
  const t = toast(p, 'Lead archivé.')
  await expect(t, 'toast « Lead archivé. »').toBeVisible({ timeout: 30_000 })
  await expect(t, 'le toast nomme le lead').toContainText(nA)
  await expect(t.getByRole('button', { name: 'Annuler' }), '« Annuler » gardé').toBeVisible()
  expect(archivages.n, 'un archivage').toBe(1)
  expect(await etat(a), 'en base : archivé après confirmation').toEqual([true, false])
  // « Supprimer » : la boîte nomme le lead ; « Annuler » ⇒ rien.
  await presser(ligne(`Tazi ${m}`).getByRole('button', { name: 'Supprimer', exact: true }))
  await expect(boite, 'la boîte de suppression nomme le lead').toContainText(`Supprimer ce lead « Salma Tazi ${m} » ?`)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  expect(await etat(b), 'en base : non supprimé').toEqual([false, false])
  await p.reload()
  await expect(ligne(`Tazi ${m}`), 'après rechargement : le lead non supprimé reste').toBeVisible({ timeout: 60_000 })
  await expect(ligne(`Benali ${m}`), 'après rechargement : le lead archivé a quitté les actifs').toHaveCount(0)
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR116 : /crm/profils-site, lecture rejetée ⇒ « Profil illisible » + Réessayer, enregistrement désactivé ;
// refus du serveur sur la surface ⇒ message sous le champ ═══
etapeCR('PF12.14-AERR116', ['AERR116'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr116_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const nomClient = `AERR116 ${m}`
  const cl = await py(`from decimal import Decimal
from apps.crm.models import Client, SiteProfile
from apps.crm.models import Lead
c = Client.objects.create(company_id=${SOC}, nom=${J(nomClient)}, prenom='Essai')
SiteProfile.objects.create(company_id=${SOC}, client=c, surface_toiture_m2=Decimal('120.00'), type_toiture='tole')
# Le client n'a pas de propriétaire : il est visible du commercial par un lead dont il est responsable (core/scoping.py).
Lead.objects.create(company_id=${SOC}, owner_id=${cr}, client=c, nom=${J(nomClient)}, prenom='Lead', telephone=${J(telephoneMobileUnique())}, stage='NEW')
sortie(c.pk)`)
  apres.push(() => py(`from apps.crm.models import Client, Lead, SiteProfile
Lead.all_objects.filter(client_id=${cl}).delete()
SiteProfile.objects.filter(client_id=${cl}).delete(); Client.objects.filter(pk=${cl}).delete()`))
  const profils = () => py(`from apps.crm.models import SiteProfile
sortie([str(x.surface_toiture_m2) for x in SiteProfile.objects.filter(client_id=${cl})])`)
  const p = await ecran(page, suivi, testInfo, nom)
  const choisir = async () => {
    await p.goto('/crm/profils-site')
    await p.locator('#sp-client').click({ timeout: 60_000 })
    await p.getByRole('searchbox').fill(nomClient)
    await p.getByRole('option', { name: new RegExp(nomClient) }).click()
  }
  const creations = compteur(p, 'POST', (ch) => ch === `${API}/crm/site-profiles/`)
  suivi.attendre(/\/api\/django\/crm\/site-profiles\/\?/, 500)
  const retablir = await couperLecture(p, (ch) => ch === `${API}/crm/site-profiles/`)
  await choisir()
  const illisible = p.getByTestId('profil-illisible')
  await expect(illisible, '« Profil illisible »').toContainText('Profil illisible', { timeout: 30_000 })
  const enregistrer = p.getByRole('button', { name: /^(Créer|Enregistrer) le profil$/ })
  await expect(enregistrer, 'enregistrement désactivé').toBeDisabled()
  expect(creations.n, 'aucune création de doublon').toBe(0)
  await retablir()
  await illisible.getByRole('button', { name: 'Réessayer' }).click()
  await expect(illisible).toHaveCount(0, { timeout: 30_000 })
  await expect(p.getByRole('button', { name: 'Enregistrer le profil' }), 'relu : profil existant, enregistrable').toBeEnabled({ timeout: 30_000 })
  await expect(p.locator('#sp-surface')).toHaveValue(/^120(\.0+)?$/)
  // Refus réel du serveur sur la surface (12 chiffres > max_digits=10) ⇒ message sous le champ.
  await p.locator('#sp-surface').fill('12345678901')
  suivi.attendre(/\/api\/django\/crm\/site-profiles\/\d+\/$/, 400)
  const refus = p.waitForResponse((r) => /\/crm\/site-profiles\/\d+\/$/.test(r.url()) && r.request().method() === 'PATCH', T)
  await p.getByRole('button', { name: 'Enregistrer le profil' }).click()
  const r = await refus
  expect(r.status(), 'le serveur refuse la surface').toBe(400)
  const msg = (await r.json()).surface_toiture_m2?.[0]
  expect(msg, 'refus nommé sur surface_toiture_m2').toBeTruthy()
  await expect(p.locator('#sp-surface'), 'champ en erreur').toHaveAttribute('aria-invalid', 'true')
  await expect(p.locator('#sp-surface').locator('xpath=following::p[@role="alert"][1]'), 'message sous le champ de surface').toHaveText(msg)
  expect(creations.n, 'toujours aucune création').toBe(0)
  expect(await profils(), 'en base : un seul profil, surface inchangée').toEqual(['120.00'])
  await choisir()
  await expect(p.locator('#sp-surface'), 'après rechargement : surface d\'origine').toHaveValue(/^120(\.0+)?$/, { timeout: 30_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR117 : fiche lead → « Arrêter la cadence » ⇒ boîte maison (champ Motif), aucun window.prompt ═══
etapeCR('PF12.15-AERR117', ['AERR117'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr117_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `AERR117 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  apres.push(() => supprimerLeads([lead]))
  await creerEtapes(lead, [{ cadence: 'contact', canal: 'appel', libelle: `Appel AERR117 ${m}` }])
  const p = await ecran(page, suivi, testInfo, nom)
  const natifs = []
  p.on('dialog', (d) => natifs.push(d.type()))
  await p.goto(`/crm/leads/${lead}`)
  const rail = p.getByTestId('lw-identity-rail')
  await rail.getByRole('button', { name: "Plus d'actions" }).click({ timeout: 60_000 })
  await p.getByRole('menuitem', { name: 'Arrêter la cadence' }).click()
  const boite = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: 'Arrêter la cadence' }) })
  await expect(boite, 'boîte maison « Arrêter la cadence »').toBeVisible({ timeout: 30_000 })
  const motif = boite.getByLabel("Motif d'arrêt de la cadence")
  await expect(motif, 'champ « Motif »').toBeVisible()
  await expect(boite.getByRole('button', { name: 'Valider' }), 'Valider désactivé tant que le motif est vide').toBeDisabled()
  await motif.fill(`Client injoignable ${m}`)
  const arret = p.waitForResponse((r) => r.url().endsWith(`/crm/leads/${lead}/relance/arreter/`), T)
  await boite.getByRole('button', { name: 'Valider' }).click()
  const r = await arret
  expect(r.status(), 'arrêt enregistré').toBe(200)
  expect(r.request().postData(), 'motif saisi envoyé').toContain(`Client injoignable ${m}`)
  await expect(toast(p, 'Cadence arrêtée.')).toBeVisible({ timeout: 30_000 })
  expect(natifs, 'aucune boîte native (window.prompt)').toEqual([])
  expect(await py(`from apps.crm.models import RelanceEtape
sortie(RelanceEtape.objects.filter(lead_id=${lead}, statut='a_faire').count())`), 'en base : plus aucune touche ouverte').toBe(0)
  await p.reload()
  await expect(rail, 'après rechargement : fiche servie').toBeVisible({ timeout: 60_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR117 (liste) : « Marquer perdu » refusé 400 {motif_perte} ⇒ message sous le motif, une seule notification ;
// « Enregistrer la vue » des leads et des clients ⇒ boîte maison, aucun window.prompt ═══
etapeCR('PF12.15b-AERR117-liste', ['AERR117'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr117l_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `AERR117L ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'CONTACTED' }])
  apres.push(() => supprimerLeads([lead]))
  // Un client rattaché au lead du commercial : la liste des clients (portée par leads visibles) n'est pas vide.
  const cl = await py(`from apps.crm.models import Client, Lead
c = Client.objects.create(company_id=${SOC}, nom='AERR117L client ${m}', prenom='Essai')
Lead.objects.filter(pk=${lead}).update(client=c)
sortie(c.pk)`)
  apres.push(() => py(`from apps.crm.models import Client
Client.objects.filter(pk=${cl}).delete()`))
  const p = await ecran(page, suivi, testInfo, nom)
  const natifs = []
  p.on('dialog', (d) => natifs.push(d.type()))
  await p.goto(`/crm/leads?view=liste&q=${m}`)
  const ligne = p.locator('tr.lv-row').filter({ hasText: `AERR117L ${m}` })
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  suivi.attendre(new RegExp(`/api/django/crm/leads/${lead}/$`), 400)
  await p.route((u) => u.pathname === `${API}/crm/leads/${lead}/`, (route) => (route.request().method() === 'PATCH'
    ? route.fulfill({ status: 400, contentType: 'application/json', body: J({ motif_perte: ['Motif requis.'] }) })
    : route.fallback()))
  await ligne.getByRole('button', { name: 'Marquer perdu' }).click()
  const champ = p.getByPlaceholder('Motif de perte')
  await champ.fill('Prix')
  const refus = p.waitForResponse((r) => r.url().endsWith(`/crm/leads/${lead}/`) && r.request().method() === 'PATCH', T)
  await champ.locator('xpath=ancestor::*[.//button[normalize-space()="Confirmer"]][1]').getByRole('button', { name: 'Confirmer' }).click()
  await refus
  await expect(champ, 'motif en erreur').toHaveAttribute('aria-invalid', 'true')
  await expect(champ.locator('xpath=following::p[@role="alert"][1]'), '« Motif requis. » sous le motif').toHaveText('Motif requis.')
  await expect(champ, 'la saisie reste dans la fenêtre ouverte').toHaveValue('Prix')
  await expect.poll(() => p.locator('[data-sonner-toast]').count(), { timeout: 5_000, message: 'une seule notification au plus' }).toBeLessThanOrEqual(1)
  await p.unrouteAll({ behavior: 'ignoreErrors' })
  expect(await py(`from apps.crm.models import Lead
l = Lead.objects.get(pk=${lead}); sortie([l.stage, bool(getattr(l, 'perdu', False))])`), 'refus : rien d\'écrit').toEqual(['CONTACTED', false])
  await p.keyboard.press('Escape')
  // Vue enregistrée de la liste des leads : boîte maison.
  await p.getByRole('button', { name: /^Vues — vue active/ }).click()
  await p.getByRole('menuitem', { name: /Enregistrer la vue actuelle/ }).click()
  const vue = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: 'Enregistrer la vue' }) })
  await expect(vue, 'leads : boîte maison « Enregistrer la vue »').toBeVisible({ timeout: 30_000 })
  await vue.getByLabel('Nom de la vue enregistrée').fill(`Vue AERR117 ${m}`)
  const creation = p.waitForResponse((r) => r.url().includes('/crm/vues-enregistrees/') && r.request().method() === 'POST', T)
  await vue.getByRole('button', { name: 'Valider' }).click()
  const rv = await creation
  expect(rv.status(), 'vue enregistrée').toBeLessThan(300)
  const idVue = (await rv.json()).id
  apres.push(() => py(`from django.apps import apps as _a
for M in _a.get_models():
    if M.__name__ in ('VueEnregistree', 'SavedView', 'AccountView') and M._meta.app_label == 'crm':
        M.objects.filter(pk=${J(idVue)}).delete()`))
  // Vue enregistrée de la liste des clients : même boîte maison.
  await p.goto('/crm')
  await p.getByRole('button', { name: /Enregistrer cette vue/ }).click({ timeout: 60_000 })
  const vueC = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: 'Enregistrer la vue' }) })
  await expect(vueC, 'clients : boîte maison « Enregistrer la vue »').toBeVisible({ timeout: 30_000 })
  await vueC.getByLabel('Nom de la vue enregistrée').fill(`Vue clients ${m}`)
  await vueC.getByRole('button', { name: 'Valider' }).click()
  await expect(vueC).toHaveCount(0)
  await expect(p.getByText(`Vue clients ${m}`).first(), 'la vue des clients est enregistrée').toBeVisible({ timeout: 15_000 })
  expect(natifs, 'aucune boîte native (window.prompt)').toEqual([])
  await p.reload()
  await expect(p.getByText(`Vue clients ${m}`).first(), 'après rechargement : vue des clients gardée').toBeVisible({ timeout: 60_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR118 : /crm/cockpit-equipe, « Effacer l'objectif » ⇒ boîte nommée (indicateur, membre, période) ═══
etapeCR('PF12.16-AERR118', ['AERR118'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr118_${m}`
  const cr = await compteRole(nom, 'Commercial responsable', 'Resp', `R${m}`)
  const membre = await compteRole(`aerr118m_${m}`, 'Commercial', 'Meryem', `M${m}`)
  const ids = await py(`from decimal import Decimal
from apps.crm.models_clients import EquipeCommerciale, ObjectifCommercial
eq = EquipeCommerciale.objects.create(company_id=${SOC}, nom='Equipe AERR118 ${m}', responsable_id=${cr}, actif=True)
eq.membres.add(${membre})
d = timezone.localdate()
o = ObjectifCommercial.objects.create(company_id=${SOC}, owner_id=${membre}, metric='ca_signe', period_type='month',
    period_year=d.year, period_month=d.month, cible=Decimal('100000.00'))
sortie(dict(eq=eq.pk, obj=o.pk))`)
  apres.push(() => py(`from apps.crm.models_clients import EquipeCommerciale, ObjectifCommercial
ObjectifCommercial.objects.filter(owner_id=${membre}).delete(); EquipeCommerciale.objects.filter(pk=${ids.eq}).delete()`))
  const existe = () => py(`from apps.crm.models_clients import ObjectifCommercial
sortie(ObjectifCommercial.objects.filter(pk=${ids.obj}).exists())`)
  const p = await ecran(page, suivi, testInfo, nom)
  await p.goto('/crm/cockpit-equipe')
  const periode = (await p.getByTestId('cockpit-periode').textContent({ timeout: 60_000 })).trim()
  const ligne = p.getByRole('row').filter({ hasText: `M${m}` })
  const cellule = ligne.getByRole('button').nth(4)
  await expect(cellule, 'cellule « CA signé » du membre').toBeVisible({ timeout: 60_000 })
  const suppressions = compteur(p, 'DELETE', (ch) => ch === `${API}/crm/objectifs/${ids.obj}/`)
  await cellule.click()
  const dlg = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: /^Objectif — / }) })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  const boite = p.getByRole('alertdialog')
  await dlg.getByRole('button', { name: /Effacer l.objectif/ }).click()
  await expect(boite, 'la boîte nomme l\'indicateur, le membre et la période').toContainText(/Effacer l.objectif CA signé/)
  await expect(boite).toContainText(`M${m}`)
  await expect(boite).toContainText(periode)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toHaveCount(0)
  await expect(dlg, '« Annuler » : la boîte de l\'objectif reste ouverte').toBeVisible()
  expect(suppressions.n, '« Annuler » : aucun deleteObjectif').toBe(0)
  expect(await existe(), 'en base : objectif présent').toBe(true)
  await dlg.getByRole('button', { name: /Effacer l.objectif/ }).click()
  await boite.getByRole('button', { name: 'Effacer', exact: true }).click()
  await expect(dlg, 'confirmé : la boîte se ferme').toHaveCount(0, { timeout: 30_000 })
  expect(suppressions.n, 'un seul deleteObjectif').toBe(1)
  await expect.poll(existe, { timeout: 15_000, message: 'en base : objectif effacé' }).toBe(false)
  await p.reload()
  await expect(ligne.getByRole('button').nth(4), 'après rechargement : plus d\'objectif').toContainText('Fixer un objectif', { timeout: 60_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR119 : fiche lead en « Contacté », touche « 3 » ⇒ toast nommé avec « Annuler » ⇒ retour en « Contacté » (undo) ═══
etapeCR('PF12.17-AERR119', ['AERR119'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr119_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `Benali ${m}`, prenom: 'Ahmed', telephone: telephoneMobileUnique(), stage: 'CONTACTED' }])
  apres.push(() => supprimerLeads([lead]))
  const etapeLead = () => py(`from apps.crm.models import Lead
sortie(Lead.objects.get(pk=${lead}).stage)`)
  const p = await ecran(page, suivi, testInfo, nom)
  const patchs = compteur(p, 'PATCH', (ch) => ch === `${API}/crm/leads/${lead}/`)
  await p.goto(`/crm/leads/${lead}`)
  const pastille = p.getByTitle("Changer l'étape du lead")
  await expect(pastille, `fiche en « ${STAGE_LABELS.CONTACTED} »`).toContainText(STAGE_LABELS.CONTACTED, { timeout: 60_000 })
  await p.getByRole('heading', { name: new RegExp(`Benali ${m}`) }).first().click()
  await p.keyboard.press('3')
  const t = toast(p, `Lead « Ahmed Benali ${m} » → ${STAGE_LABELS.QUOTE_SENT}`)
  await expect(t, 'toast nommé avec la nouvelle étape').toBeVisible({ timeout: 30_000 })
  await expect.poll(() => patchs.n, { timeout: 15_000 }).toBe(1)
  expect(JSON.parse(patchs.corps[0]), 'PATCH de l\'avancée').toMatchObject({ stage: 'QUOTE_SENT' })
  await expect(pastille).toContainText(STAGE_LABELS.QUOTE_SENT, { timeout: 30_000 })
  await t.getByRole('button', { name: 'Annuler' }).click()
  await expect.poll(() => patchs.n, { timeout: 15_000 }).toBe(2)
  expect(JSON.parse(patchs.corps[1]), '« Annuler » renvoie l\'étape d\'origine avec undo').toEqual({ stage: 'CONTACTED', undo: true })
  await expect(pastille, 'la fiche revient en « Contacté »').toContainText(STAGE_LABELS.CONTACTED, { timeout: 30_000 })
  await expect.poll(etapeLead, { timeout: 30_000, message: 'en base : étape d\'origine' }).toBe('CONTACTED')
  await p.reload()
  await expect(pastille, 'après rechargement : « Contacté »').toContainText(STAGE_LABELS.CONTACTED, { timeout: 60_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR120 : /crm/leads/<id> → « Signé », acceptation refusée 400 {date} ⇒ dialogue rouvert pré-rempli,
// erreur sous la date, page gardée ═══
etapeCR('PF12.18-AERR120', ['AERR120'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-091')
  const m = marque()
  const nom = `aerr120_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `AERR120 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'QUOTE_SENT' }])
  apres.push(() => supprimerLeads([lead]))
  const devis = await py(`from decimal import Decimal
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import Produit
l = Lead.objects.get(pk=${lead})
cl = Client.objects.create(company_id=l.company_id, nom='AERR120 ${m}', prenom='Essai')
p = Produit.objects.filter(company_id=l.company_id).first()
d = Devis.objects.create(company_id=l.company_id, reference='DEV-AERR120-${m}', client=cl, lead=l, statut='envoye', created_by_id=${cr})
LigneDevis.objects.create(devis=d, produit=p, designation='Kit AERR120', quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
sortie(dict(id=d.pk, client=cl.pk))`)
  apres.push(() => py(`from apps.crm.models import Client
Client.objects.filter(pk=${devis.client}).delete()`))
  const p = await ecran(page, suivi, testInfo, nom)
  await p.goto(`/crm/leads/${lead}`)
  await p.getByTitle("Changer l'étape du lead").click({ timeout: 60_000 })
  await p.getByRole('menuitem', { name: new RegExp(STAGE_LABELS.SIGNED) }).click()
  const dlg = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: /Passer en « Signé »/ }) })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  const hier = new Date(); hier.setDate(hier.getDate() - 1)
  await dlg.locator('#sd-nom').fill('K. Alami')
  await dlg.locator('#sd-date').fill(isoJour(hier))
  suivi.attendre(/\/api\/django\/ventes\/devis\/\d+\/accepter\/$/, 400)
  await p.route(/\/api\/django\/ventes\/devis\/\d+\/accepter\/$/, (route) => route.fulfill({
    status: 400, contentType: 'application/json', body: J({ date: ['Date invalide.'] }),
  }))
  const refus = p.waitForResponse((r) => /\/ventes\/devis\/\d+\/accepter\/$/.test(r.url()), T)
  await dlg.getByRole('button', { name: /Confirmer l.acceptation/ }).click()
  await refus
  const rouvert = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: /Passer en « Signé »/ }) })
  await expect(rouvert, 'le dialogue « Signé » réapparaît').toBeVisible({ timeout: 30_000 })
  await expect(p, 'la page reste la fiche du lead').toHaveURL(new RegExp(`/crm/leads/${lead}$`))
  await expect(rouvert.locator('#sd-nom'), 'signataire gardé').toHaveValue('K. Alami')
  await expect(rouvert.locator('#sd-date'), 'date gardée').toHaveValue(isoJour(hier))
  await expect(rouvert.locator('#sd-date').locator('xpath=following::p[@role="alert"][1]'), '« Date invalide. » sous la date').toHaveText('Date invalide.')
  await p.unrouteAll({ behavior: 'ignoreErrors' })
  const lu = await py(`from apps.ventes.models import Devis
from apps.crm.models import Lead
sortie([Devis.objects.get(pk=${devis.id}).statut, Lead.objects.get(pk=${lead}).stage])`)
  expect(lu, 'refus : rien n\'est accepté').toEqual(['envoye', 'QUOTE_SENT'])
  await p.reload()
  await expect(p.getByTitle("Changer l'étape du lead"), 'après rechargement : toujours « Devis envoyé »').toContainText(STAGE_LABELS.QUOTE_SENT, { timeout: 60_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR122 : /crm/relances → « Décider la suite » → Perdu, lecture des motifs rejetée ⇒ « Motifs illisibles »
// + Réessayer, jamais « Aucun motif » ═══
etapeCR('PF12.19-AERR122', ['AERR122'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-093')
  const m = marque()
  const nom = `aerr122_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `AERR122 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'CONTACTED' }])
  apres.push(() => supprimerLeads([lead]))
  await creerEtapes(lead, [{ cadence: 'generique', canal: 'appel', cle: 'decider_suite', libelle: 'Décider la suite — perdu (motif) ou relance ultérieure' }])
  const p = await ecran(page, suivi, testInfo, nom)
  await p.goto('/crm/relances')
  const ligne = p.getByTestId('relance-etape-row').filter({ hasText: `AERR122 ${m}` })
  await expect(ligne, 'étape « Décider la suite » listée').toBeVisible({ timeout: 60_000 })
  suivi.attendre(/\/api\/django\/crm\/motifs-perte\/\?/, 500)
  const retablir = await couperLecture(p, (ch) => ch === `${API}/crm/motifs-perte/`)
  await ligne.getByRole('button', { name: 'Fait', exact: true }).click()
  await ligne.getByRole('button', { name: /^Perdu/ }).click()
  const illisibles = ligne.getByTestId('motif-perte-illisibles')
  await expect(illisibles, '« Motifs illisibles »').toContainText('Motifs illisibles', { timeout: 30_000 })
  await expect(ligne.getByTestId('motif-perte-aucun'), 'jamais « Aucun motif de perte n\'est paramétré »').toHaveCount(0)
  await retablir()
  await illisibles.getByRole('button', { name: 'Réessayer' }).click()
  const options = ligne.getByTestId('motif-perte').locator('select option')
  await expect.poll(() => options.count(), { timeout: 30_000, message: 'Réessayer relit et propose les motifs' }).toBeGreaterThan(3)
  await expect(illisibles).toHaveCount(0)
  await expect(ligne.getByTestId('motif-perte-aucun')).toHaveCount(0)
  await p.reload()
  await expect(ligne, 'après rechargement : étape toujours ouverte').toBeVisible({ timeout: 60_000 })
  await auRepos(suivi)
  await montrer(page)
})

// ═══ PF12 — AERR23 + AERR24 : /publicite/approbations, « j » puis « a » ⇒ confirmation nommée ; « Annuler » ⇒ rien ;
// « a » sous une boîte ⇒ rien ; « Confirmer » ⇒ approuvée, toast « Annuler » (= désapprouver) ; « Retirer l'approbation » ═══
etape('PF12.20-AERR23-AERR24', ['AERR23', 'AERR24'], async ({ page, suivi, testInfo }) => {
  sonde('C-AERR-021')
  const m = marque()
  const nom = `aerr23_${m}`
  await compteRole(nom, 'Directeur')
  const com = `aerr23c_${m}`
  await compteRole(com, 'Commercial')
  // Créées dans cet ordre : B (« Créatif fatigué ») d'abord, A ensuite ⇒ A en tête (tri -created_at), B en 2e carte.
  const ids = await py(`from apps.adsengine.models import EngineAction
co = ${SOC}
b = EngineAction.objects.create(company_id=co, kind='rotate_creative', payload={}, reason_fr='Créatif fatigué (fréquence 3,2). ${m}')
a = EngineAction.objects.create(company_id=co, kind='pause', payload={}, reason_fr='CPL trop élevé. ${m}')
sortie(dict(a=a.pk, b=b.pk))`)
  apres.push(() => py(`from apps.adsengine.models import EngineAction
EngineAction.objects.filter(pk__in=[${ids.a}, ${ids.b}]).delete()`))
  const lire = (pk) => py(`from apps.adsengine.models import EngineAction
x = EngineAction.objects.get(pk=${pk}); sortie([x.status, x.approved_by_id])`)
  const p = await ecran(page, suivi, testInfo, nom)
  const approbations = compteur(p, 'POST', (ch) => /\/adsengine\/actions\/\d+\/approve\/$/.test(ch))
  const retraits = compteur(p, 'POST', (ch) => /\/adsengine\/actions\/\d+\/desapprouver\/$/.test(ch))
  await p.goto('/publicite/approbations')
  const carteB = p.getByTestId('ae-action-card').filter({ hasText: `Créatif fatigué (fréquence 3,2). ${m}` })
  await expect(p.getByTestId(`ae-approve-${ids.b}`), 'droits chargés : Approuver actif').toBeEnabled({ timeout: 60_000 })
  await p.getByRole('heading', { name: "Boîte d'approbation" }).first().click()
  await p.keyboard.press('j')
  await expect(carteB, '« j » : la 2e carte est focalisée').toHaveAttribute('aria-current', 'true')
  await p.keyboard.press('a')
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'confirmation maison qui nomme le type').toContainText('Approuver : Rotation de créatif ?', { timeout: 30_000 })
  await expect(boite, 'et le libellé de l\'action').toContainText(`Créatif fatigué (fréquence 3,2). ${m}`)
  // « a » tapé alors que la boîte est ouverte par-dessus ⇒ rien (pas de 2e boîte, aucun approve).
  await p.keyboard.press('a')
  await expect(boite).toHaveCount(1)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toHaveCount(0)
  expect(approbations.n, '« Annuler » : aucun approve').toBe(0)
  expect(await lire(ids.b), 'en base : toujours proposée').toEqual(['proposee', null])
  await p.reload()
  await expect(p.getByTestId(`ae-approve-${ids.b}`), 'après rechargement : B toujours à approuver').toBeEnabled({ timeout: 60_000 })
  // « Confirmer » ⇒ approve(B) ; toast « Action approuvée. » avec « Annuler » (= désapprouver).
  await p.getByRole('heading', { name: "Boîte d'approbation" }).first().click()
  await p.keyboard.press('j')
  await expect(carteB).toHaveAttribute('aria-current', 'true')
  await p.keyboard.press('a')
  await boite.getByRole('button', { name: 'Confirmer' }).click()
  await expect(p.getByTestId(`ae-approved-badge-${ids.b}`), 'B approuvée').toContainText("Approuvée — en attente d'application", { timeout: 30_000 })
  expect(approbations.n, 'un seul approve').toBe(1)
  expect((await lire(ids.b))[0], 'en base : approuvée').toBe('approuvee')
  const t = toast(p, 'Action approuvée.')
  await t.getByRole('button', { name: 'Annuler' }).click()
  await expect(p.getByTestId(`ae-approve-${ids.b}`), 'toast « Annuler » : B de nouveau « Approuver / Rejeter »').toBeVisible({ timeout: 30_000 })
  await expect(p.getByTestId(`ae-reject-${ids.b}`)).toBeVisible()
  expect(retraits.n, 'le toast appelle desapprouver').toBe(1)
  expect(await lire(ids.b), 'en base : B proposée, approved_by vide').toEqual(['proposee', null])
  // AERR24 — bouton « Retirer l'approbation » sur la carte A approuvée (clic sur « Approuver »).
  await p.getByTestId(`ae-approve-${ids.a}`).click()
  await expect(p.getByTestId(`ae-approved-badge-${ids.a}`)).toBeVisible({ timeout: 30_000 })
  await p.getByTestId(`ae-desapprouver-${ids.a}`).click()
  await expect(p.getByTestId(`ae-approve-${ids.a}`), '« Retirer l\'approbation » : A de nouveau à approuver').toBeVisible({ timeout: 30_000 })
  expect(await lire(ids.a), 'en base : A proposée, approved_by vide').toEqual(['proposee', null])
  await p.reload()
  await expect(p.getByTestId(`ae-approve-${ids.a}`), 'après rechargement : A proposée').toBeVisible({ timeout: 60_000 })
  await expect(p.getByTestId(`ae-approve-${ids.b}`), 'après rechargement : B proposée').toBeVisible()
  // Route : sans le droit ⇒ 403 ; action appliquée ⇒ 400.
  await py(`from apps.adsengine.models import EngineAction
EngineAction.objects.filter(pk=${ids.a}).update(status='approuvee')`)
  const ctxCom = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  try {
    await connexionApi(ctxCom, { username: com, password: MDP_ESSAI })
    expect((await ctxCom.post(`${API}/adsengine/actions/${ids.a}/desapprouver/`, T)).status(), 'Commercial (sans adsengine_approve) : 403').toBe(403)
  } finally { await ctxCom.dispose() }
  expect((await lire(ids.a))[0], 'refus 403 : toujours approuvée').toBe('approuvee')
  await py(`from apps.adsengine.models import EngineAction
EngineAction.objects.filter(pk=${ids.a}).update(status='appliquee')`)
  expect((await p.request.post(`${API}/adsengine/actions/${ids.a}/desapprouver/`, T)).status(), 'appliquée : 400').toBe(400)
  expect((await lire(ids.a))[0], 'appliquée : inchangée').toBe('appliquee')
  await auRepos(suivi)
  await montrer(page)
})
