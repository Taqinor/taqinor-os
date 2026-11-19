// TCH141, TCH171, TCH143 — ACCEPTATION EN DIRECT de la fusion F3 du module « Tâches » (CLAUDE.md 3-bis).
//
// Trois parcours rejoués sur la pile locale, compte `demo_taches` semé par `manage.py seed_taches_demo` (journée du
// mardi 24/11/2026 de `docs/taches/maquettes/SCENARIO.md`). Une ÉTAPE = un test = UN numéro d'oracle du plan
// (`docs/plans/PLAN_TACHES.md`, lignes TCH141, TCH171, TCH143), recopié mot pour mot en tête de l'étape.
// Règle d'or : un oracle ne se modifie JAMAIS pour faire passer une étape — l'écart est un défaut (rapport).
//
// Chaque étape est INDÉPENDANTE : elle pose son scénario (semis + horloge du serveur, `taches-acceptation.js` de la
// fusion 2), rejoue par l'API les gestes qui la précèdent dans le parcours, puis joue SON geste. Horloge du navigateur =
// celle du scénario (`page.clock.install`), fuseau `UTC` (Maroc = GMT toute l'année depuis le 20/09/2026). Vues : iPhone
// (390 × 844, tactile) par défaut ; l'administrateur du coupe-circuit au bureau (1440 × 900).
//
// Ce que le plan écrit et que l'étape joue AUTREMENT, toujours dit (ERR-PLAN au rapport, l'oracle n'est pas touché) :
//   - P141 : le semis ajoute `--rendez-vous` (agenda externe de démonstration) : sans lui, « aucun rendez-vous externe »
//     dans le flux serait vrai d'office ; avec lui, l'absence est une preuve.
//   - P141.2 : le `curl -d '{…}'` du plan part en `application/x-www-form-urlencoded` (pas d'en-tête JSON) et reçoit
//     400 « Dis-moi quoi noter. » ; le raccourci Siri envoie un corps JSON (textes.md §7, étape 3) : l'étape envoie
//     donc le même JSON AVEC `Content-Type: application/json`, et note la réponse du `curl` littéral.
//   - P171.1 : `executer(maintenant='2026-11-24T08:30')` (une CHAÎNE) lève `AttributeError` (`timezone.localtime`
//     attend un datetime) ; l'étape joue la commande littérale, note son échec, puis joue le même instant en datetime
//     AWARE du Maroc (`balayer`).
//
// Base de départ : celle du job (migrate, seed_demo, init_roles, rôle de demo_admin), SANS `demo_taches`. Chaque
// étape sème son scénario AVANT tout `py()` qui lit le compte (`remettreAccueil`, `rallumer`, journal…) : elle se
// joue seule (`-g`) sur une base neuve comme à la suite des autres.
//
// Le Copilote (TCH143) : les étapes 1 à 3 ne demandent aucun modèle (demandes prêtes, routes déterministes) ; les
// étapes 4 à 6 parlent au VRAI assistant (`E2E_IA_URL`, clé du dépôt sur un runner) et, sans lui, échouent ROUGES
// avec le message « vrai assistant requis : E2E_IA_URL + clé du dépôt » — jamais sautées, jamais simulées.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { RACINE } from './_enregistrement.js'
import { toast } from '../taches-aides.js'
import { API, aller, lire, liste, ouvrir, pile, salir, scenario, tacheNommee } from '../taches-acceptation.js'
import {
  VRAI_ASSISTANT_REQUIS, balayer, brancherIA, capturerF3, clientNu, demandePrete, demanderAuCopilote, deplier,
  etapeOuverte, etapesIphone, jetonParEcran, notificationsDe, ouvrirCopilote, relancerIA, viderCloche,
} from '../taches-acceptation-f3.js'

const PARCOURS = ['TCH141', 'TCH171', 'TCH143']
const CONSTRUCTION = [
  'TCH95', 'TCH96', 'TCH97', 'TCH109', 'TCH132', 'TCH11', 'TCH24', 'TCH39',
  'TCH98', 'TCH20', 'TCH30', 'TCH35', 'TCH56', 'TCH155', 'TCH160',
  'TCH161', 'TCH170', 'TCH117', 'TCH165', 'TCH118', 'TCH111', 'TCH115',
]
const etape = groupe('TCH', [...PARCOURS, ...CONSTRUCTION])
test.describe.configure({ timeout: 600_000 })
fermerDjangoApresTout()

// --- Le scénario (SCENARIO.md) ------------------------------------------------------------------------------------
const J24 = '2026-11-24'
const SEMIS_141 = ['--jour', J24, '--heure', '09:41', '--rendez-vous']
const SEMIS_171 = ['--jour', J24, '--heure', '08:29', '--historique', '10']
const SEMIS_143 = ['--jour', J24, '--heure', '08:30']
const T = {
  fournisseur: 'Appeler le fournisseur', kakemonos: 'Imprimer les kakémonos', calepinage: 'Valider le plan de calepinage',
  tva: 'Préparer la déclaration de TVA', contrat: 'Relire le contrat de maintenance',
}
const RDV_EXTERNE = 'Rendez-vous de démonstration' // tests/donnees/agenda.ics (semé par --rendez-vous)
const DEMO = "u = U.objects.get(username='demo_taches'); soc = u.company_id\n"

/** Remet l'accueil mobile de `demo_taches` à rien (le semis ne touche pas le compte) : P141.1 voit 5 « À faire ». */
const remettreAccueil = () => py(`${DEMO}U.objects.filter(pk=u.pk).update(mobile_home_route=None)\nsortie(True)`)
/** Rallume le coupe-circuit de la société de `demo_taches` (une étape interrompue ne doit pas couper les suivantes). */
const rallumer = () => py(`${DEMO}from apps.taches.models.presence import ReglagesSociete
ReglagesSociete.objects.filter(company_id=soc).update(balayage_actif=True)
sortie(True)`)

/** Toutes les tâches du compte (toutes pages) : leurs titres servent à prouver qu'un texte « n'en cite aucune ». */
async function toutesLesTaches(p) {
  const toutes = []
  let page = 1
  for (;;) {
    const corps = await lire(p, 'taches/', { page: String(page), inclure_faites: 'true' })
    toutes.push(...liste(corps))
    if (!corps.next) return toutes
    page += 1
  }
}

/** PATCH d'une tâche (ou d'un projet) avec sa `lock_version` du moment. */
async function modifier(p, chemin, champs) {
  const actuel = await lire(p, chemin)
  const res = await p.request.patch(`${API}/${chemin}`, { data: { ...champs, lock_version: actuel.lock_version ?? actuel.projet?.lock_version } })
  expect(res.ok(), `PATCH ${chemin} → ${res.status()} ${await res.text()}`).toBeTruthy()
  return res.json()
}

/** Forme d'un JSON (clés, récursivement ; une liste = la forme de son premier élément ; null admis pour une valeur). */
function forme(valeur) {
  if (Array.isArray(valeur)) return valeur.length ? [forme(valeur[0])] : []
  if (valeur && typeof valeur === 'object') return Object.fromEntries(Object.keys(valeur).sort().map((k) => [k, forme(valeur[k])]))
  return '·'
}

// =====================================================================================================================
// TCH141 — Parcours « iPhone, depuis un navigateur » (source : textes.md §7 « L'écran Mon iPhone », §8)
// =====================================================================================================================

etape('P141.1', ['TCH141', 'TCH109', 'TCH95'], async (f) => {
  const instant = scenario(SEMIS_141, `${J24} 09:41`)
  await remettreAccueil() // APRÈS le semis : sur une base neuve, `demo_taches` n'existe qu'une fois semé
  const p = await ouvrir(f, { instant })
  await p.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin: new URL(f.testInfo.project.use.baseURL).origin })
  await aller(p, '/taches/reglages/iphone', 'reglages')
  // Oracle (plan) : « Mon iPhone → 5 étapes « À faire » »
  await expect(etapesIphone(p)).toHaveCount(5)
  for (let i = 0; i < 5; i += 1) await expect(etapesIphone(p).nth(i).locator('.etat')).toHaveText('À faire')
  // R3-098 : « Mettre Tâches sur l'écran d'accueil » compte comme une étape : « Six étapes », « 0 sur 6 »
  await expect(p.getByText('0 sur 6', { exact: true })).toBeVisible()
  await capturerF3(p, 'mon-iphone')
  for (const n of [1, 2, 3, 4, 5]) {
    await deplier(p, n)
    await capturerF3(p, `mon-iphone-etape-${n}`)
  }
  // Oracle (plan) : « créer le jeton de capture »
  const { clair, fiche } = await jetonParEcran(p, 3, 'Créer le jeton')
  expect(fiche.usage, 'jeton de capture').toBe('capture')
  const zone = etapeOuverte(p, 3)
  await zone.getByRole('button', { name: 'Copier mon jeton', exact: true }).click()
  await expect(zone.getByText('Copié. Il ne sera plus affiché : colle-le maintenant.', { exact: true })).toBeVisible()
  await expect(p.locator('code.ep-jeton-valeur'), 'le clair disparaît une fois copié').toHaveCount(0)
  // Persistance : le jeton actif est servi (sans clair), l'écran rechargé le montre « Jamais utilisé · préfixe… »
  const actifs = liste(await lire(p, 'jetons/')).filter((j) => j.usage === 'capture' && !j.revoque_le)
  expect(actifs, 'un jeton de capture actif').toHaveLength(1)
  expect(actifs[0].jeton, 'la liste ne rend jamais le clair').toBeUndefined()
  expect(clair.startsWith(actifs[0].prefixe), 'le clair montré est celui du jeton actif').toBe(true)
  await p.reload()
  await deplier(p, 3)
  await expect(p.getByText(`Jamais utilisé · ${actifs[0].prefixe}…`, { exact: true })).toBeVisible()
})

etape('P141.2', ['TCH141', 'TCH96', 'TCH95', 'TCH39'], async (f) => {
  const instant = scenario(SEMIS_141, `${J24} 09:41`)
  await remettreAccueil() // APRÈS le semis : sur une base neuve, `demo_taches` n'existe qu'une fois semé
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/reglages/iphone', 'reglages')
  const capture = (await jetonParEcran(p, 3, 'Créer le jeton')).clair
  const flux = (await jetonParEcran(p, 2, 'Créer le lien du calendrier')).clair
  // Un projet confidentiel (Fiche du projet → confidentiel) : « Administratif ».
  const admin = liste(await lire(p, 'projets/')).find((x) => x.nom === 'Administratif')
  expect(admin, 'projet Administratif du semis').toBeTruthy()
  await modifier(p, `projets/${admin.id}/`, { confidentiel: true })
  const nu = await clientNu(f.testInfo.project.use.baseURL)
  try {
    const url = '/api/django/taches/capture/?reponse=texte'
    const siri = (jeton, titre) => nu.post(url, {
      headers: { Authorization: `Bearer ${jeton}`, 'Content-Type': 'application/json' }, data: JSON.stringify({ titre }),
    })
    // Le `curl -d` littéral du plan (form-urlencoded) : observé, noté (ERR-PLAN), jamais un oracle.
    const litteral = await nu.post(url, {
      headers: { Authorization: `Bearer ${capture}`, 'Content-Type': 'application/x-www-form-urlencoded' },
      data: '{"titre":"appeler le fournisseur demain 10 h"}',
    })
    f.testInfo.annotations.push({ type: 'ERR-PLAN', description: `curl -d littéral du plan → ${litteral.status()} « ${await litteral.text()} »` })
    // Oracle (plan) : « Ajouté pour demain 10 h : appeler le fournisseur »
    const r1 = await siri(capture, 'appeler le fournisseur demain 10 h')
    expect(r1.status(), 'capture créée').toBe(201)
    expect(await r1.text()).toBe('Ajouté pour demain 10 h : appeler le fournisseur')
    const notee = await tacheNommee(p, 'appeler le fournisseur')
    expect([notee.jour_prevu, notee.heure_debut, notee.source], 'tâche notée demain 10:00, source capture').toEqual(['2026-11-25', '10:00', 'capture'])
    // Oracle (plan) : « dans un projet confidentiel → « … dans un projet » » (textes.md §7 : « projet confidentiel :
    // « Ajouté dans un projet : {titre} » (le nom n'est jamais dit, inv. 38) » ; la tâche d'un projet confidentiel est
    // confidentielle par héritage (A6) : le `{titre}` servi est noté, la phrase doit dire « Ajouté dans un projet : »)
    const r2 = await siri(capture, 'projet Administratif relancer la banque')
    expect(r2.status(), 'capture dans le projet confidentiel').toBe(201)
    const phrase = await r2.text()
    f.testInfo.annotations.push({ type: 'observation', description: `capture dans un projet confidentiel → « ${phrase} »` })
    expect(phrase).toMatch(/^Ajouté dans un projet : /)
    expect(phrase, 'le nom du projet confidentiel n\'est jamais dit').not.toContain('Administratif')
    expect((await tacheNommee(p, 'relancer la banque')).projet?.nom, 'rangée dans le projet').toBe('Administratif')
    // Oracle (plan) : « jeton du flux sur capture → 401 »
    const r3 = await siri(flux, 'noter quelque chose')
    expect(r3.status(), 'jeton du flux refusé par capture').toBe(401)
    expect(await r3.text()).toBe("Je n'ai pas pu noter : vérifie ton raccourci dans Mon iPhone.")
  } finally {
    await nu.dispose()
  }
})

etape('P141.3', ['TCH141', 'TCH97', 'TCH24', 'TCH11', 'TCH109'], async (f) => {
  const instant = scenario(SEMIS_141, `${J24} 09:41`)
  await remettreAccueil() // APRÈS le semis : sur une base neuve, `demo_taches` n'existe qu'une fois semé
  const p = await ouvrir(f, { instant })
  // Les rendez-vous externes du compte (--rendez-vous) : servis ou non par `aujourdhui/`, c'est NOTÉ (une absence
  // rendrait « aucun rendez-vous externe » vrai d'office — dit au rapport), jamais un oracle de cette étape.
  const agendas = liste(await lire(p, 'agendas-externes/'))
  expect(agendas.map((a) => a.libelle), 'agenda externe semé (--rendez-vous)').toEqual(['Agenda de démonstration'])
  const servis = ((await lire(p, 'aujourdhui/')).rendez_vous ?? []).length
  f.testInfo.annotations.push({ type: 'observation', description: `rendez-vous externes servis par aujourdhui/ : ${servis}` })
  console.log(`[P141.3] rendez-vous externes servis par aujourdhui/ : ${servis}`)
  // Une tâche confidentielle et une note, toutes deux dans la fenêtre du flux (J à J + 14).
  const kakemonos = await tacheNommee(p, T.kakemonos)
  await modifier(p, `taches/${kakemonos.id}/`, { confidentiel: true })
  const NOTE = 'Note privée : code du portail 4417'
  const calepinage = await tacheNommee(p, T.calepinage)
  await modifier(p, `taches/${calepinage.id}/`, { notes: NOTE })
  await aller(p, '/taches/reglages/iphone', 'reglages')
  const { clair } = await jetonParEcran(p, 2, "Créer le lien du calendrier")
  await expect(p.getByRole('link', { name: "S'abonner", exact: true })).toHaveAttribute('href', /^webcal:\/\/.+\/api\/django\/taches\/flux\/tqf_.+\.ics$/)
  const nu = await clientNu(f.testInfo.project.use.baseURL)
  try {
    const r = await nu.get(`/api/django/taches/flux/${clair}.ics`)
    expect(r.status(), 'flux servi').toBe(200)
    expect(r.headers()['content-type']).toMatch(/^text\/calendar/)
    const ics = await r.text()
    expect(ics).toContain('X-WR-CALNAME:Tâches Taqinor')
    expect(ics, 'la tâche du calepinage est dans le flux').toContain(`SUMMARY:${T.calepinage}`)
    // Oracle (plan) : « flux `.ics` → aucune note »
    expect(ics, 'aucune note').not.toContain('code du portail')
    expect(ics.split(/\r?\n/).filter((l) => l.startsWith('DESCRIPTION:') && l !== 'DESCRIPTION:'), 'description toujours vide').toEqual([])
    // Oracle (plan) : « confidentielle « Tâche confidentielle » »
    expect(ics).toContain('SUMMARY:Tâche confidentielle')
    expect(ics, 'le titre de la confidentielle n\'est jamais servi').not.toContain(T.kakemonos)
    // Oracle (plan) : « aucun rendez-vous externe »
    expect(ics).not.toContain(RDV_EXTERNE)
  } finally {
    await nu.dispose()
  }
})

etape('P141.4', ['TCH141', 'TCH97', 'TCH24', 'TCH109'], async (f) => {
  const instant = scenario(SEMIS_141, `${J24} 09:41`)
  await remettreAccueil() // APRÈS le semis : sur une base neuve, `demo_taches` n'existe qu'une fois semé
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/reglages/iphone', 'reglages')
  const { clair } = await jetonParEcran(p, 4, 'Créer le jeton de la tuile')
  const nu = await clientNu(f.testInfo.project.use.baseURL)
  let tuile
  try {
    const r = await nu.get('/api/django/taches/tuile/', { headers: { Authorization: `Bearer ${clair}` } })
    expect(r.status(), 'tuile servie').toBe(200)
    tuile = await r.json()
  } finally {
    await nu.dispose()
  }
  // Oracle (plan) : « tuile JSON = forme de `tuile.json` »
  const echantillon = JSON.parse(readFileSync(join(RACINE, 'backend/django_core/apps/taches/contract_samples/tuile.json'), 'utf8')).exemple
  expect(forme(tuile)).toEqual(forme(echantillon))
  // Oracle (plan) : « « 1 sur 5 » » (ligne 1 de la tuile, textes.md §8 : « {faites} sur {objectif} » ; SCENARIO §3, 09:41)
  expect(`${tuile.faites} sur ${tuile.objectif}`).toBe('1 sur 5')
  // La tuile a lu avec CE jeton : son « dernier usage » est posé, l'écran le dit.
  await p.reload()
  await deplier(p, 4)
  await expect(etapesIphone(p).nth(3).locator('.etat')).toHaveText('Fait')
})

etape('P141.5', ['TCH141', 'TCH132', 'TCH109'], async (f) => {
  const instant = scenario(SEMIS_141, `${J24} 09:41`)
  await remettreAccueil() // APRÈS le semis : sur une base neuve, `demo_taches` n'existe qu'une fois semé
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/reglages/iphone', 'reglages')
  await deplier(p, 5)
  const rep = p.waitForResponse((r) => r.request().method() === 'POST' && /\/api\/django\/auth\/mobile-home-route\/$/.test(r.url()))
  await p.getByRole('button', { name: 'En faire mon accueil', exact: true }).click()
  expect((await rep).status(), 'POST auth/mobile-home-route/').toBeLessThan(300)
  // Oracle (plan) : « En faire mon accueil → `mobile-home-route` = `/taches/aujourdhui` »
  const moi = await (await p.request.get('/api/django/auth/me/')).json()
  expect(moi.mobile_home_route).toBe('/taches/aujourdhui')
  await expect(etapesIphone(p).nth(4).locator('.etat')).toHaveText('Fait')
  await p.reload()
  await expect(etapesIphone(p).nth(4).locator('.etat'), 'persisté au rechargement').toHaveText('Fait')
  // Oracle (plan) : « ce qui demande l'appareil reste dans GATED » — section GATED de PLAN_TACHES.md (gestes du fondateur)
  const plan = readFileSync(join(RACINE, 'docs/plans/PLAN_TACHES.md'), 'utf8')
  const gated = plan.slice(plan.indexOf('## GATED'), plan.indexOf('## DONE LOG'))
  expect(gated.length, 'section GATED présente').toBeGreaterThan(0)
  for (const geste of ['raccourci Siri', 'Scriptable', "s'abonner au calendrier", 'pastille, notifications, calendrier, Siri, tuile, Aujourd\'hui en accueil']) {
    expect(gated, `GATED garde « ${geste} »`).toContain(geste)
  }
  await remettreAccueil()
})

// =====================================================================================================================
// TCH171 — Parcours « notifications et coupe-circuit » (source : api.md §9 ; regles.md « Les sollicitations »)
// =====================================================================================================================

/** Le scénario du matin (08:29 semé, serveur à 08:30), notifications Tâches effacées, coupe-circuit allumé. */
async function matin171() {
  const instant = scenario(SEMIS_171, `${J24} 08:30`)
  await rallumer() // APRÈS le semis : sur une base neuve, `demo_taches` (et sa société) n'existe qu'une fois semé
  await viderCloche()
  return instant
}
const notifsTaches = async () => (await notificationsDe()).filter((n) => n.type.startsWith('taches_'))

/** La cloche de l'en-tête : ouverte, rend son panneau. */
async function cloche(p) {
  // la cloche de Tâches dit « Notifications : {n} » (axe-core 4.14 : le chiffre visible est un mot du nom lu)
  const bouton = p.getByRole('button', { name: /^Notifications : \d+$/ })
  await expect(bouton, 'la cloche de l\'en-tête').toBeVisible({ timeout: 30_000 })
  await bouton.click()
  const panneau = p.locator('.nb-panel')
  await expect(panneau).toBeVisible()
  return panneau
}

etape('P171.1', ['TCH171', 'TCH98', 'TCH20', 'TCH30'], async (f) => {
  const instant = await matin171()
  // La commande LITTÉRALE du plan (instant en chaîne) : son issue est notée (ERR-PLAN si elle échoue), jamais un oracle.
  let issue
  try {
    pile('manage', 'shell', '-c', "from apps.taches.balayage import executer; executer(maintenant='2026-11-24T08:30')")
    issue = 'passée'
  } catch (e) {
    issue = `échec : ${String(e.stderr || e.message).trim().split('\n').pop()}`
  }
  f.testInfo.annotations.push({ type: 'ERR-PLAN', description: `executer(maintenant='2026-11-24T08:30') → ${issue}` })
  console.log(`[P171.1] commande littérale du plan → ${issue}`)
  if ((await notifsTaches()).length === 0) {
    const bilan = await balayer(`${J24}T08:30`)
    expect(bilan.sollicitations, `passage de 08:30 : ${JSON.stringify(bilan)}`).toBe(1)
  }
  // Oracle (plan) : « une notification « Aujourd'hui » dans la cloche, sans titre »
  const notifs = await notifsTaches()
  expect(notifs.map((n) => [n.type, n.titre]), 'UNE notification du matin').toEqual([['taches_plan_du_jour', "Aujourd'hui"]])
  const p = await ouvrir(f, { instant })
  for (const t of await toutesLesTaches(p)) expect(notifs[0].corps, `« ${t.titre} » n'est pas dans le corps`).not.toContain(t.titre)
  await aller(p, '/taches/aujourdhui', 'aujourdhui')
  const panneau = await cloche(p)
  await expect(panneau.locator('.nb-item').filter({ hasText: /^Aujourd'hui$/ })).toBeVisible()
  await capturerF3(p, 'cloche')
})

etape('P171.2', ['TCH171', 'TCH98'], async () => {
  await matin171()
  const premier = await balayer(`${J24}T08:30`)
  expect(premier.sollicitations, 'premier passage : la notification du matin').toBe(1)
  const avant = await notifsTaches()
  // Oracle (plan) : « rejouer → rien de plus »
  const second = await balayer(`${J24}T08:30`)
  expect(second.sollicitations + second.rappels, `second passage : ${JSON.stringify(second)}`).toBe(0)
  expect((await notifsTaches()).map((n) => n.id)).toEqual(avant.map((n) => n.id))
})

etape('P171.3', ['TCH171', 'TCH98', 'TCH20', 'TCH35'], async (f) => {
  const instant = await matin171()
  const p0 = await ouvrir(f, { instant })
  const fournisseur = await tacheNommee(p0, T.fournisseur)
  // Le rappel posé à 10:00 (route de la fiche → Rappel).
  const pose = await p0.request.post(`${API}/taches/${fournisseur.id}/rappels/`, { data: { jour: J24, heure: '10:00' } })
  expect(pose.ok(), `rappel posé → ${pose.status()} ${await pose.text()}`).toBeTruthy()
  // Oracle (plan) : « rappel posé à 10:00 puis `executer(maintenant='…T10:00')` → `TACHES_RAPPEL` »
  const bilan = await balayer(`${J24}T10:00`)
  expect(bilan.rappels, `passage de 10:00 : ${JSON.stringify(bilan)}`).toBe(1)
  const rappels = (await notifsTaches()).filter((n) => n.type === 'taches_rappel')
  expect(rappels.map((n) => [n.titre, n.lien])).toEqual([['Rappel', `/taches/aujourdhui?tache=${fournisseur.id}`]])
  expect(rappels[0].corps, 'sans titre de tâche').not.toContain(T.fournisseur)
  // Oracle (plan) : « l'ouvrir → fiche « Encore 10 min · 1 h · Demain 9 h » (parcours 11) » (boutons : textes.md §2.4,
  // « Ouverte par un rappel (en tête) | Encore 10 min · Encore 1 h · Demain 9 h »)
  pile('horloge', `${J24} 10:00`)
  salir()
  const p = await ouvrir(f, { instant: `${J24}T10:00:00Z` })
  await aller(p, '/taches/aujourdhui', 'aujourdhui')
  const panneau = await cloche(p)
  await panneau.locator('.nb-item').filter({ hasText: /^Rappel$/ }).click()
  await expect(p).toHaveURL(new RegExp(`/taches/aujourdhui\\?tache=${fournisseur.id}$`))
  const sonne = p.getByRole('group', { name: 'Ce rappel vient de sonner' })
  await expect(sonne).toBeVisible({ timeout: 30_000 })
  await expect(sonne.getByRole('button')).toHaveText(['Encore 10 min', 'Encore 1 h', 'Demain 9 h'])
  await capturerF3(p, 'fiche-rappel')
})

etape('P171.4', ['TCH171', 'TCH56'], async (f) => {
  const instant = await matin171()
  const p = await ouvrir(f, { instant })
  // Oracle (plan) : « `badge/` = 3 »
  const badge = await lire(p, 'badge/')
  expect(badge.n).toBe(3)
  expect(badge.jour).toBe(J24)
})

etape('P171.5', ['TCH171', 'TCH155', 'TCH160', 'TCH98'], async (f) => {
  const instant = await matin171()
  const p = await ouvrir(f, { instant, vue: 'bureau' })
  try {
    await aller(p, '/taches/reglages/notifications', 'reglages')
    await expect(p.getByText('Heures de travail de la société', { exact: false })).toBeVisible()
    await capturerF3(p, 'reglages-notifications')
    // Oracle (plan) : « administrateur : Réglages → Avancé, couper l'envoi »
    await aller(p, '/taches/reglages/avance', 'reglages')
    const interrupteur = p.getByRole('switch', { name: 'Messages et rappels de Tâches dans la société' })
    await expect(interrupteur).toHaveAttribute('aria-checked', 'true')
    await interrupteur.click()
    const dialogue = p.getByRole('dialog', { name: 'Couper tous les messages et rappels de Tâches pour la société ?' })
    await expect(dialogue).toBeVisible()
    await dialogue.getByRole('button', { name: 'Couper', exact: true }).click()
    await expect(toast(p)).toContainText('Messages et rappels coupés')
    await expect(p.getByText(/^Messages et rappels de Tâches coupés pour la société depuis le 24\/11 à \d{2}:\d{2}\.$/)).toBeVisible()
    await capturerF3(p, 'reglages-avance-coupe')
    expect((await lire(p, 'reglages-societe/')).balayage_actif, 'coupé côté serveur').toBe(false)
    // « → `executer` n'émet plus rien »
    const bilan = await balayer(`${J24}T08:30`)
    expect(await notifsTaches(), `aucune notification après la coupure (${JSON.stringify(bilan)})`).toEqual([])
    const fournisseur = await tacheNommee(p, T.fournisseur)
    await p.request.post(`${API}/taches/${fournisseur.id}/rappels/`, { data: { jour: J24, heure: '10:00' } })
    const dix = await balayer(`${J24}T10:00`)
    expect(dix.rappels + dix.sollicitations, 'ni rappel ni sollicitation pendant la coupure').toBe(0)
    expect(await notifsTaches()).toEqual([])
  } finally {
    await rallumer()
  }
})

etape('P171.6', ['TCH171', 'TCH98'], async () => {
  scenario(['--vide'], `${J24} 08:30`)
  await rallumer() // APRÈS le semis (base neuve : le compte n'existe qu'une fois semé)
  await viderCloche()
  // Oracle (plan) : « compte `--vide` → rien »
  await balayer(`${J24}T08:30`)
  await balayer(`${J24}T15:00`)
  await balayer(`${J24}T18:00`)
  expect(await notifsTaches()).toEqual([])
})

// =====================================================================================================================
// TCH143 — Parcours « Copilote » (source : api.md §8 ; arbitrages.md A18-M3 ; textes.md §5)
// =====================================================================================================================

const QUESTIONS = [
  ['Planifie ma journée', 'plan_propose'], ['Aide-moi à prioriser', 'priorites'],
  ['Range ma liste', 'capture_apercu'], ["Où j'en suis ?", 'point'],
]

/** Le matin du Copilote : semis de 08:30, page iPhone connectée, service d'IA branché, panneau ouvert sur Aujourd'hui. */
async function copilote(f, { lecture = false, vue = 'iphone' } = {}) {
  const instant = scenario(SEMIS_143, `${J24} 08:30`, { lecture })
  relancerIA()
  const p = await ouvrir(f, { instant, vue })
  const requetes = await brancherIA(p)
  await aller(p, '/taches/aujourdhui', 'aujourdhui')
  const panneau = await ouvrirCopilote(p)
  return { p, panneau, requetes }
}

etape('P143.1', ['TCH143', 'TCH118', 'TCH161', 'TCH117', 'TCH165'], async (f) => {
  const { p, panneau, requetes } = await copilote(f, { lecture: true })
  await capturerF3(p, 'copilote-panneau', { cadre: panneau })
  // Oracle (plan) : « sans clé d'IA : les 4 demandes rendent leur carte (`plan_propose`, `priorites`, `capture_apercu`, `point`) »
  for (const [question, cle] of QUESTIONS) {
    const carte = await demandePrete(panneau, question, cle)
    await carte.scrollIntoViewIfNeeded()
    await capturerF3(p, `copilote-carte-${cle}`, { cadre: panneau })
  }
  for (const [, cle] of QUESTIONS) await expect(panneau.getByTestId(`carte-taches-${cle}`)).toHaveCount(1)
  // « sans clé d'IA » : aucune des quatre n'a interrogé le modèle (aucune question partie au service d'IA)
  expect(requetes.filter((r) => /\/sql-agent\/query$/.test(r)), 'aucun tour de modèle').toEqual([])
})

etape('P143.2', ['TCH143', 'TCH170', 'TCH161', 'TCH165'], async (f) => {
  const { p, panneau } = await copilote(f, { lecture: true })
  const servi = await lire(p, 'journee/priorites/')
  const carte = await demandePrete(panneau, 'Aide-moi à prioriser', 'priorites')
  const suivantes = carte.getByRole('button', { name: /^Voir les \d+ suivantes$/ })
  if (await suivantes.count()) await suivantes.click()
  // Oracle (plan) : « toutes les ouvertes classées »  (api.md §3 : TOUTES les tâches ouvertes du préfiltre)
  expect(servi.tronque, 'aucune ouverte coupée par le plafond').toBe(false)
  const lignes = carte.getByRole('listitem')
  await expect(lignes).toHaveCount(servi.lignes.length)
  await expect(lignes.locator('.titre')).toHaveText(servi.lignes.map((l) => `${l.rang}. ${l.item.titre}`))
  // Oracle (plan) : « une raison chacune, Essentiel · Aujourd'hui · Plus tard »
  for (let i = 0; i < servi.lignes.length; i += 1) {
    const l = servi.lignes[i]
    const raison = l.item.raison?.texte || l.item.explication || ''
    expect(raison, `raison de « ${l.item.titre} »`).not.toBe('')
    const ligne = lignes.nth(i)
    const texteRaison = ligne.locator('.meta').getByText(raison, { exact: true })
    await expect(texteRaison).toBeVisible()
    // Lisible, pas seulement présent : ni le titre ni la raison ne sont coupés par la carte (« Co… », « procha »).
    // (mesuré sur les blocs `.titre` et `.meta` qui portent la coupe ; un `span` en ligne n'a pas de largeur propre)
    for (const [quoi, el] of [['titre', ligne.locator('.titre')], ['raison', ligne.locator('.meta')]]) {
      const coupe = await el.evaluate((n) => ({ texte: n.textContent, coupe: n.scrollWidth > n.clientWidth + 1 }))
      expect(coupe.coupe, `${quoi} « ${coupe.texte} » coupé à l'écran (${p.viewportSize().width} px)`).toBe(false)
    }
    // R3-150 (C-20) : « Plus tard dans la semaine (→ ven.) » est devenu « Reporter à ven. 20 »
    await expect(ligne.getByRole('button')).toHaveText(['Essentiel', "Aujourd'hui", /^Reporter à \S+ \d+$/])
  }
  await capturerF3(p, 'copilote-carte-priorites-toutes', { cadre: panneau })
})

etape('P143.3', ['TCH143', 'TCH117'], async (f) => {
  const { p, panneau } = await copilote(f)
  // N = Proposé d'Aujourd'hui au même instant (SCENARIO §3 : 3 à 08:30) : « Adopter » = « Garder ces N » (api.md §8).
  const propose = (await lire(p, 'aujourdhui/')).propose.pour_objectif.filter((it) => it.type === 'tache')
  const n = propose.length
  const carte = await demandePrete(panneau, 'Planifie ma journée', 'plan_propose')
  // Oracle (plan) : « Adopter → « Garder ces N » »
  const garder = carte.getByRole('button', { name: n >= 2 ? `Garder ces ${n}` : 'Garder celle-ci', exact: true })
  await expect(garder, `bouton d'adoption du Proposé (${n} : ${propose.map((t) => t.titre).join(' · ')})`).toBeVisible()
  await garder.click()
  await expect(carte.getByRole('status')).toContainText(`${n} gardée`)
  const journee = await lire(p, 'aujourdhui/')
  const gardees = [...journee.essentiel, ...journee.journee].map((it) => it.titre)
  for (const t of propose) expect(gardees, `« ${t.titre} » gardée`).toContain(t.titre)
})

etape('P143.4', ['TCH143', 'TCH111', 'TCH117', 'TCH165'], async (f) => {
  const { p, panneau } = await copilote(f)
  const titres = ['Acheter des câbles solaires', 'Rappeler la banque populaire', 'Imprimer les fiches techniques']
  const avant = (await toutesLesTaches(p)).length
  // Oracle (plan) : « liste collée dans le tour → carte à valider, aucune écriture avant le doigt »
  const corps = await demanderAuCopilote(p, panneau, `Ajoute ma liste :\n${titres.join('\n')}`)
  expect((await toutesLesTaches(p)).length, 'aucune écriture avant le doigt').toBe(avant)
  const cartes = corps.cartes || []
  const aValider = cartes.find((c) => c.carte === 'capture_apercu' || (c.carte === 'tache' && c.donnees?.proposition?.geste === 'ecrire'))
  expect(aValider, `carte à valider : ${JSON.stringify(cartes.map((c) => c.carte))}`).toBeTruthy()
  const carte = panneau.getByTestId(`carte-taches-${aValider.carte}`).last()
  await expect(carte).toBeVisible()
  await capturerF3(p, 'copilote-carte-a-valider', { cadre: panneau })
  const bouton = aValider.carte === 'capture_apercu'
    ? carte.getByRole('button', { name: /^Tout ajouter \(\d+\)$/ })
    : carte.locator('.ep-carte-ia-pied').getByRole('button').first()
  await bouton.click()
  await expect(carte.getByRole('status')).toBeVisible()
  const apres = await toutesLesTaches(p)
  expect(apres.length, 'le doigt écrit').toBeGreaterThan(avant)
  const creees = apres.filter((t) => titres.some((x) => t.titre.toLowerCase() === x.toLowerCase()))
  console.log(`[P143.4] source des tâches validées au doigt : ${JSON.stringify(creees.map((t) => t.source))}`)
})

etape('P143.5', ['TCH143', 'TCH111', 'TCH117'], async (f) => {
  const { p, panneau } = await copilote(f)
  const avant = await tacheNommee(p, T.tva)
  // Oracle (plan) : « « mets la priorité haute à X » → `taches.tache.modifier` »
  const corps = await demanderAuCopilote(p, panneau, `mets la priorité haute à ${T.tva}`)
  expect((corps.cartes || []).map((c) => c.action_key), JSON.stringify(corps.cartes || [])).toContain('taches.tache.modifier')
  const modif = (corps.cartes || []).filter((c) => c.action_key === 'taches.tache.modifier').at(-1)
  const carte = panneau.getByTestId('carte-taches-tache').last()
  // Garde A5 (regles.md) : après une LECTURE dans la conversation (chercher la tâche), l'écriture de l'assistant
  // devient une carte à valider (`proposition.geste: "ecrire"`, bouton « Modifier » de CartesTaches) : rien n'est
  // écrit avant le doigt. Sans lecture préalable, elle s'écrit directement (« Modifiée » d'emblée). Le chemin pris est
  // lu sur la carte SERVIE, jamais deviné : les deux mènent au même oracle.
  if (modif.donnees?.proposition?.geste === 'ecrire') {
    console.log('[P143.5] chemin : carte à valider')
    expect((await tacheNommee(p, T.tva)).priorite, 'rien n\'est écrit avant le doigt').toBe(avant.priorite)
    await carte.locator('.ep-carte-ia-pied').getByRole('button', { name: 'Modifier', exact: true }).click()
  } else {
    console.log('[P143.5] chemin : écriture directe')
  }
  await expect(carte.getByRole('status')).toContainText('Modifiée')
  expect((await tacheNommee(p, T.tva)).priorite, 'priorité haute écrite').toBe(3)
  // « Annuler → restauré »
  await carte.getByRole('button', { name: 'Annuler', exact: true }).click()
  await expect(carte.getByRole('status')).toContainText('Annulé')
  expect((await tacheNommee(p, T.tva)).priorite, 'priorité restaurée').toBe(avant.priorite)
})

etape('P143.6', ['TCH143', 'TCH115', 'TCH11'], async (f) => {
  const { p, panneau } = await copilote(f)
  const SECRET = 'Prendre rendez-vous pour le dossier médical'
  const cree = await p.request.post(`${API}/taches/`, { data: { titre: SECRET, jour_prevu: J24 } })
  expect(cree.ok(), `tâche créée → ${cree.status()} ${await cree.text()}`).toBeTruthy()
  // Rendue confidentielle comme la fiche le fait (Plus → confidentielle : PATCH `confidentiel`).
  const secrete = await tacheNommee(p, SECRET)
  expect((await modifier(p, `taches/${secrete.id}/`, { confidentiel: true })).tache?.confidentielle ?? true).toBe(true)
  expect((await tacheNommee(p, SECRET)).confidentielle, 'tâche confidentielle').toBe(true)
  // Ce que l'assistant LIT (en-tête du relais, api.md §0) : jamais le titre d'une confidentielle.
  for (const chemin of ['aujourdhui/', 'journee/priorites/', 'journee/point/', 'recherche/?q=dossier']) {
    const r = await p.request.get(`${API}/${chemin}`, { headers: { 'X-Taqinor-Assistant': '1' } })
    expect(r.ok(), `${chemin} (assistant) → ${r.status()}`).toBeTruthy()
    expect(await r.text(), `${chemin} servi à l'assistant`).not.toContain(SECRET)
  }
  // Oracle (plan) : « tâche confidentielle jamais citée ; journal de l'assistant : « [tâches — privé] » »
  const corps = await demanderAuCopilote(p, panneau, 'Où en est ma tâche sur le dossier médical ?')
  expect(JSON.stringify(corps), 'réponse et cartes du Copilote').not.toContain(SECRET)
  await expect(panneau).not.toContainText(SECRET)
  const journal = await py(`${DEMO}from apps.agent.models import AssistantEvent
e = AssistantEvent.objects.filter(user=u).order_by('-created_at').first()
sortie(None if e is None else dict(question=e.question, reponse=e.resume_reponse, ecran=e.ecran))`)
  expect(journal, `journal de l'assistant écrit (${VRAI_ASSISTANT_REQUIS})`).toBeTruthy()
  expect(journal.question).toBe('[tâches — privé]')
  expect(journal.reponse).toBe('')
})
