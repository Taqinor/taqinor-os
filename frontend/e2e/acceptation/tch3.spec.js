// TCH142, TCH172 — ACCEPTATION EN DIRECT de la fusion F4 du module « Tâches » (CLAUDE.md 3-bis).
//
// Deux parcours rejoués sur la pile locale, compte `demo_taches` semé par `manage.py seed_taches_demo` (journée du
// mardi 24/11/2026 de `docs/taches/maquettes/SCENARIO.md`). Une ÉTAPE = un test = UN numéro d'oracle du plan
// (`docs/plans/PLAN_TACHES.md`, lignes TCH142 et TCH172), recopié mot pour mot en tête de l'étape.
// Règle d'or : un oracle ne se modifie JAMAIS pour faire passer une étape — l'écart est un défaut (rapport).
//
// Chaque étape est INDÉPENDANTE et jouable seule (`-g "P142.3"`) : elle pose son scénario (semis + horloge du serveur,
// `taches-acceptation.js`) AVANT tout appel au shell Django, puis le harnais (`taches-acceptation-f4.js`) pose ce que
// l'ERP doit contenir : le semis ne pose ni lead, ni devis, ni visite, ni relance dont une étape dépendrait. Horloge du
// navigateur = celle du scénario (`page.clock.install`), fuseau `UTC` (Maroc = GMT toute l'année).
// Vues : iPhone (390 × 844, tactile) par défaut ; bureau (1440 × 900) pour `c t`, `/activites` et le cockpit.
//
// Droits posés par le harnais sur le rôle de TEST de `demo_taches` (le semis le remet à taches_voir, roles_gerer,
// crm_voir, visites_voir) : `ventes_voir` (une suggestion n'est proposée qu'au compte qui VOIT le devis — regles.md §9)
// et `ventes_valider` (la route d'acceptation des devis), pour TCH142 seulement.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { fermerDjangoApresTout, py } from './_django.js'
import { lireTache, toast } from '../taches-aides.js'
import { API, aller, lire, liste, ouvrir, pile, scenario, tacheNommee } from '../taches-acceptation.js'
import { capturerF3 as capturer } from '../taches-acceptation-f3.js'
import {
  DEMO, accepterDevis, accorder, annulerAcceptation, devisEnvoye, leadDeDemo, projetNomme, suggestionsEnBase, tousLesProjets,
} from '../taches-acceptation-f4.js'

const PARCOURS = ['TCH142', 'TCH172']
const CONSTRUCTION = [
  'TCH71', 'TCH72', 'TCH167', 'TCH102', 'TCH123', 'TCH159', 'TCH103', 'TCH125',
  'TCH90', 'TCH64', 'TCH157', 'TCH156', 'TCH166',
]
const etape = groupe('TCH', [...PARCOURS, ...CONSTRUCTION])
test.describe.configure({ timeout: 600_000 })
fermerDjangoApresTout()

// --- Le scénario (SCENARIO.md) ------------------------------------------------------------------------------------
const J24 = '2026-11-24'
const SEMIS_142 = ['--jour', J24, '--heure', '15:02']
const SEMIS_172 = ['--jour', J24, '--heure', '08:30']
const A_15H02 = `${J24}T15:02:00+00:00`
const TITRE_SUGGESTION = 'Préparer le chantier du devis accepté' // receivers.py TITRES, SCENARIO §1
const BENALI = 'Chantier Benali 9 kWc'
const RAILS = 'Commander les rails de fixation'
const DROITS_142 = ['ventes_voir', 'ventes_valider']

/** Le scénario de TCH142 (15:02) et les droits du harnais. */
async function scenario142() {
  const instant = scenario(SEMIS_142, `${J24} 15:02`)
  await accorder(...DROITS_142)
  return instant
}

const feuille = (p, nom) => p.getByRole('dialog', { name: nom })
const saisie = (p) => feuille(p, 'Ajouter une tâche')
const champSaisie = (p) => saisie(p).getByRole('textbox', { name: 'Ajouter une tâche', exact: true })
const sectionSuggestions = (p) => p.locator('section.section[aria-label="Suggéré par l\'ERP"]')
const ligneSuggestion = (p, id) => p.locator(`[data-ligne="suggestion:${id}"]`)
const boutonIci = (p) => p.getByRole('button', { name: /^Tâches liées à cette fiche/ })

/** Les tâches OUVERTES liées à une cible, telles que le ✓+ les compte (`taches/?cible=&cible_id=&ouvertes=1`). */
const tachesLiees = async (p, cible, id) => liste(await lire(p, 'taches/', { cible, cible_id: String(id), ouvertes: '1' }))

/** Une tâche liée au lead par la route de création (le lien est vérifié par le serveur). */
async function tacheLieeAuLead(p, lead, titre) {
  const r = await p.request.post(`${API}/taches/`, { data: { titre, lien: { cible: 'crm.lead', id: lead } } })
  expect(r.ok(), `tâche liée créée → ${r.status()} ${await r.text()}`).toBeTruthy()
}

// =====================================================================================================================
// TCH142 — Parcours « ERP avancé » (source : conception/spec-6a-erp.md « Critères d'acceptation »)
// =====================================================================================================================

etape('P142.1', ['TCH142', 'TCH71', 'TCH72', 'TCH167'], async (f) => {
  const instant = await scenario142()
  const d1 = await devisEnvoye(await leadDeDemo(1))
  const d2 = await devisEnvoye(await leadDeDemo(2)) // un second lead : ventes n'accepte qu'une vente par lead
  // Oracle (plan) : « accepter un devis du lead de démonstration → « Préparer le chantier du devis accepté » dans
  // Suggéré par l'ERP »
  await accepterDevis(d1.id, A_15H02)
  await accepterDevis(d2.id, A_15H02)
  const enBase = await suggestionsEnBase()
  const s1 = enBase.find((s) => s.cle === `devis_accepte:${d1.id}`)
  const s2 = enBase.find((s) => s.cle === `devis_accepte:${d2.id}`)
  expect([s1?.statut, s1?.titre], 'suggestion du devis 1').toEqual(['proposee', TITRE_SUGGESTION])
  expect([s2?.statut, s2?.titre], 'suggestion du devis 2').toEqual(['proposee', TITRE_SUGGESTION])
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/a-trier', 'a-trier')
  const section = sectionSuggestions(p)
  await expect(section.getByRole('heading', { name: "Suggéré par l'ERP" })).toBeVisible({ timeout: 30_000 })
  for (const [s, d] of [[s1, d1], [s2, d2]]) {
    const ligne = ligneSuggestion(p, s.id)
    await expect(ligne.getByRole('textbox')).toHaveValue(TITRE_SUGGESTION)
    await expect(ligne.getByRole('link', { name: new RegExp(`^Lié à : ${d.reference}`) })).toBeVisible()
  }
  await capturer(p, 'a-trier-suggere')
  // Oracle (plan) : « Ajouter → tâche liée »
  await ligneSuggestion(p, s1.id).getByRole('button', { name: 'Ajouter', exact: true }).click()
  await expect(toast(p)).toContainText('Ajoutée')
  await expect(ligneSuggestion(p, s1.id)).toHaveCount(0)
  const acceptee = (await suggestionsEnBase()).find((s) => s.id === s1.id)
  expect(acceptee.statut, 'suggestion acceptée').toBe('acceptee')
  const tache = await lireTache(p, acceptee.tache)
  expect([tache.titre, tache.source], 'tâche née de la suggestion').toEqual([TITRE_SUGGESTION, 'suggestion'])
  expect([tache.lien?.cible, tache.lien?.id, tache.lien?.etat], 'tâche liée au devis accepté').toEqual(['ventes.devis', d1.id, 'ok'])
  // Oracle (plan) : « Pas utile → jamais reproposée »
  await ligneSuggestion(p, s2.id).getByRole('button', { name: 'Pas utile', exact: true }).click()
  await expect(toast(p)).toContainText('Pas utile')
  await expect(ligneSuggestion(p, s2.id)).toHaveCount(0)
  // l'événement revient : acceptation annulée (ventes) puis devis réaccepté par la même route
  expect(await annulerAcceptation(d2.id, A_15H02), 'acceptation du devis 2 annulée').not.toBe('accepte')
  await accepterDevis(d2.id, A_15H02)
  const apres = (await suggestionsEnBase()).filter((s) => s.cle === `devis_accepte:${d2.id}`)
  expect(apres.map((s) => s.statut), 'une seule suggestion du devis 2, toujours refusée').toEqual(['refusee'])
  expect(liste(await lire(p, 'suggestions/')).map((s) => s.id), 'suggestions/ ne la sert plus').not.toContain(s2.id)
  await p.reload()
  await expect(p.locator('.tch[data-ecran="a-trier"]')).toBeVisible({ timeout: 30_000 })
  await expect(p.getByText(TITRE_SUGGESTION).first()).toBeVisible() // la tâche ajoutée (et celle du semis) sont là
  await expect(sectionSuggestions(p), 'aucune suggestion reproposée').toHaveCount(0)
})

etape('P142.2', ['TCH142', 'TCH102', 'TCH123'], async (f) => {
  const instant = await scenario142()
  const { lead } = await leadDeDemo()
  const p = await ouvrir(f, { instant })
  await tacheLieeAuLead(p, lead, 'Rappeler le lead de démonstration')
  await p.goto(`/crm/leads/${lead}`)
  // Oracle (plan) : « fiche lead → ✓+ avec compte »
  await expect(boutonIci(p)).toBeVisible({ timeout: 30_000 })
  await expect(p.getByTestId('tch-ici-nb')).toHaveText('1')
  await expect(boutonIci(p)).toHaveAccessibleName('Tâches liées à cette fiche (1 ouvertes)')
  await boutonIci(p).click()
  const liees = p.getByRole('list', { name: 'Tâches liées à cette fiche' })
  await expect(liees.getByRole('listitem')).toHaveText(['Rappeler le lead de démonstration'])
  await capturer(p, 'fiche-lead-ici')
  // Oracle (plan) : « « Nouvelle tâche liée » pré-liée »
  await p.getByRole('button', { name: 'Nouvelle tâche liée', exact: true }).click()
  await expect(saisie(p)).toBeVisible()
  const puce = saisie(p).getByRole('button', { name: /^Retirer le lien « .+ »$/ })
  await expect(puce).toBeVisible()
  await expect(puce).toContainText('Lié à : ')
  await capturer(p, 'fiche-lead-saisie-liee')
  await champSaisie(p).fill('Envoyer la proposition au lead')
  await saisie(p).getByRole('button', { name: 'Ajouter', exact: true }).click()
  await expect(p.getByTestId('tch-ici-nb')).toHaveText('2', { timeout: 30_000 })
  const titres = (await tachesLiees(p, 'crm.lead', lead)).map((t) => t.titre).sort()
  expect(titres, 'la nouvelle tâche est liée au lead').toEqual(['Envoyer la proposition au lead', 'Rappeler le lead de démonstration'])
})

etape('P142.3', ['TCH142', 'TCH102', 'TCH123'], async (f) => {
  const instant = await scenario142()
  const { lead } = await leadDeDemo()
  const p = await ouvrir(f, { instant, vue: 'bureau' })
  await p.goto(`/crm/leads/${lead}`)
  // La fiche est affichée (en-tête et ✓+ montés) : la personne tape `c t` aussitôt, sans attendre autre chose.
  await expect(boutonIci(p)).toBeVisible({ timeout: 30_000 })
  // Oracle (plan) : « `c t` sur une fiche → puce de lien »
  await p.keyboard.press('c')
  await p.keyboard.press('t')
  await expect(saisie(p)).toBeVisible()
  const puce = saisie(p).getByRole('button', { name: /^Retirer le lien « .+ »$/ })
  await expect(puce).toBeVisible()
  await expect(puce).toContainText('Lié à : ')
  await capturer(p, 'fiche-lead-c-t', { vues: ['bureau'] })
  await champSaisie(p).fill('Préparer la visite du lead')
  await saisie(p).getByRole('button', { name: 'Ajouter', exact: true }).click()
  await expect.poll(async () => (await tachesLiees(p, 'crm.lead', lead)).map((t) => t.titre), { timeout: 30_000 })
    .toEqual(['Préparer la visite du lead'])
})

etape('P142.4', ['TCH142', 'TCH159'], async (f) => {
  const instant = await scenario142()
  const p = await ouvrir(f, { instant, vue: 'bureau' })
  await p.goto('/activites')
  const champ = p.getByRole('textbox', { name: 'Nouvelle tâche à faire' })
  await expect(champ).toBeVisible({ timeout: 30_000 })
  // Oracle (plan) : « `/activites` « + À faire » → feuille de saisie » — la phrase tapée part dans la feuille
  // (TCH159 : « la phrase tapée part dans la feuille de saisie unique ») ; le champ d'Activités, lui, se vide.
  await champ.fill('Rappeler le syndic jeudi')
  await p.locator('form').filter({ has: champ }).getByRole('button', { name: 'Ajouter', exact: true }).click()
  await expect(saisie(p)).toBeVisible()
  await expect(champ).toHaveValue('')
  expect(await py(`${DEMO}from apps.records.models import Activity
sortie(Activity.objects.filter(company_id=soc, created_by=u, summary='Rappeler le syndic jeudi').count())`), 'aucune activité créée').toBe(0)
  await expect(champSaisie(p)).toHaveValue('Rappeler le syndic jeudi')
  await capturer(p, 'activites-a-faire', { vues: ['bureau'] })
})

etape('P142.5', ['TCH142', 'TCH103', 'TCH125'], async (f) => {
  const instant = await scenario142()
  // Le tableau de bord lit aussi les tickets SAV (`sav/tickets/`, hors Tâches) : sans `sav_voir`, 403 (oracle 2).
  await accorder('sav_voir')
  const p = await ouvrir(f, { instant, vue: 'bureau' })
  await p.goto('/dashboard')
  const carte = p.getByRole('region', { name: "Tâches, aujourd'hui" })
  await expect(carte).toBeVisible({ timeout: 30_000 })
  // Oracle (plan) : « cockpit → « 3 sur 5 · 2 à faire » »
  await expect(carte.locator('.ep-cc-compte .chiffres')).toHaveText('3 sur 5 · 2 à faire')
  await capturer(p, 'cockpit-carte', { cadre: carte, vues: ['bureau'] })
})

// =====================================================================================================================
// TCH172 — Parcours « projets avancés » (source : conception/spec-4-projets-planification.md)
// =====================================================================================================================

const scenario172 = () => scenario(SEMIS_172, `${J24} 08:30`)
const vueChoisie = (p, nom) => p.getByRole('button', { name: `Vue : ${nom}, changer` })
const tableau = (p) => p.locator('.ep-vue-tableau')
const chronologie = (p) => p.locator('.ep-frise, .ep-frise-h').filter({ visible: true })

/** Ouvre un projet comme l'utilisateur : la liste des projets, puis sa ligne. */
async function rouvrirProjet(p, projet) {
  await aller(p, '/taches/projets', 'projets')
  await p.locator(`[data-projet="${projet.id}"] .ep-ouvrir`).click()
  await expect(p).toHaveURL(new RegExp(`/taches/projets/${projet.id}$`))
  await expect(p.locator('.tch[data-ecran="projet"]')).toBeVisible()
}

/** Choisit une vue au sélecteur de l'iPhone et attend sa mémorisation par le serveur. */
async function choisirVue(p, projet, actuelle, nom) {
  const ecrite = p.waitForResponse((r) => r.request().method() === 'PATCH' && r.url().endsWith(`/taches/projets/${projet.id}/`))
  await vueChoisie(p, actuelle).click()
  await p.getByRole('menuitem', { name: nom, exact: true }).click()
  expect((await ecrite).status(), `PATCH projets/${projet.id}/ (vue ${nom})`).toBeLessThan(300)
}

/** Le menu ⋯ de l'écran → une action. */
async function menuEcran(p, libelle) {
  await p.getByRole('button', { name: "Plus d'actions", exact: true }).click()
  await p.getByRole('menuitem', { name: libelle, exact: true }).click()
}

/** « Utiliser ce modèle » / « Dupliquer » : un nom, l'aperçu des dates lu, puis Créer. Rend `{ apercu, projet, ouvert }` :
 *  le projet créé (lu par l'API) et si l'écran l'a OUVERT (adresse `/taches/projets/{id}` dans les 10 s).
 *  L'ouverture n'est pas assertée ici : l'étape la note et continue, pour constater aussi la seconde moitié. */
async function creerDepuisDialogue(p, titre, nom) {
  const dialogue = feuille(p, titre)
  await expect(dialogue).toBeVisible()
  await dialogue.getByLabel('Nom du projet', { exact: true }).fill(nom)
  await dialogue.getByLabel('Nom du projet', { exact: true }).press('Tab')
  const apercu = dialogue.locator('.es-resume')
  await expect(apercu).toHaveText(/^\d+ tâches?, première le .+$/, { timeout: 30_000 })
  const texte = (await apercu.textContent()).trim()
  await capturer(p, `${titre === 'Dupliquer' ? 'projet-dupliquer' : 'modeles-utiliser'}-apercu`)
  const ecrit = p.waitForResponse((r) => r.request().method() === 'POST' && /\/(dupliquer|instancier)\/$/.test(r.url())
    && r.request().postDataJSON()?.apercu === false)
  await dialogue.getByRole('button', { name: 'Créer', exact: true }).click()
  const reponse = await ecrit
  expect(reponse.status(), `création (${titre})`).toBe(201)
  const id = (await reponse.json()).projet?.id
  await expect(toast(p)).toContainText('Projet créé')
  const ouvert = await p.waitForURL(new RegExp(`/taches/projets/${id}$`), { timeout: 10_000 }).then(() => true, () => false)
  const projet = (await tousLesProjets(p)).find((x) => x.id === id)
  return { apercu: texte, projet, ouvert, adresse: new URL(p.url()).pathname }
}

etape('P172.1', ['TCH172', 'TCH90'], async (f) => {
  const instant = scenario172()
  const p = await ouvrir(f, { instant })
  const benali = await projetNomme(p, BENALI)
  await aller(p, `/taches/projets/${benali.id}`, 'projet')
  await expect(vueChoisie(p, 'Liste')).toBeVisible()
  // Oracle (plan) : « Benali en Tableau → rouvrir le projet = Tableau »
  await choisirVue(p, benali, 'Liste', 'Tableau')
  await expect(tableau(p)).toBeVisible()
  await capturer(p, 'projet-tableau')
  await rouvrirProjet(p, benali)
  await expect(vueChoisie(p, 'Tableau')).toBeVisible()
  await expect(tableau(p)).toBeVisible()
  await p.reload()
  await expect(vueChoisie(p, 'Tableau'), 'rouvert après rechargement : Tableau').toBeVisible({ timeout: 30_000 })
  await expect(tableau(p)).toBeVisible()
  // Oracle (plan) : « Chronologie »
  await choisirVue(p, benali, 'Tableau', 'Chronologie')
  await expect(chronologie(p)).toHaveCount(1)
  await capturer(p, 'projet-chronologie')
  await rouvrirProjet(p, benali)
  await expect(vueChoisie(p, 'Chronologie')).toBeVisible()
  await expect(chronologie(p)).toHaveCount(1)
})

etape('P172.2', ['TCH172', 'TCH64', 'TCH157'], async (f) => {
  const instant = scenario172()
  const p = await ouvrir(f, { instant })
  const benali = await projetNomme(p, BENALI)
  await aller(p, `/taches/projets/${benali.id}`, 'projet')
  // Oracle (plan) : « Enregistrer comme modèle »
  await menuEcran(p, 'Modèle…')
  const enregistrer = feuille(p, 'Enregistrer comme modèle')
  await expect(enregistrer.getByLabel('Nom du modèle', { exact: true })).toHaveValue(BENALI)
  await expect(enregistrer.locator('.es-resume')).toBeVisible({ timeout: 30_000 })
  await capturer(p, 'projet-enregistrer-modele')
  const ecrit = p.waitForResponse((r) => r.request().method() === 'POST' && r.url().endsWith(`/projets/${benali.id}/enregistrer-modele/`))
  await enregistrer.getByRole('button', { name: 'Créer', exact: true }).click()
  expect((await ecrit).status(), 'modèle enregistré').toBe(201)
  const modeles = liste(await lire(p, 'modeles/'))
  expect(modeles.map((m) => m.nom), 'le modèle est listé').toEqual([BENALI])
  // Oracle (plan) : « → Utiliser le modèle (aperçu des dates) → projet créé »
  await aller(p, '/taches/projets', 'projets')
  await menuEcran(p, 'Modèles')
  await expect(p.locator('.tch[data-ecran="projets-modeles"]')).toBeVisible()
  await p.locator(`[data-modele="${modeles[0].id}"]`).getByRole('button', { name: 'Utiliser ce modèle', exact: true }).click()
  const ecarts = []
  const cree = await creerDepuisDialogue(p, 'Utiliser ce modèle', 'Chantier Durand 6 kWc')
  expect(cree.projet?.nom, 'projet créé depuis le modèle').toBe('Chantier Durand 6 kWc')
  const n = Number(cree.apercu.match(/^(\d+)/)[1])
  expect(n, `l'aperçu annonce les tâches du modèle (${cree.apercu})`).toBe(modeles[0].nb_taches)
  if (!cree.ouvert) ecarts.push(`Utiliser ce modèle → Créer : projet ${cree.projet.id} créé, l'écran reste sur ${cree.adresse}`)
  else await capturer(p, 'projet-depuis-modele')
  // Oracle (plan) : « ; Dupliquer »
  await aller(p, `/taches/projets/${benali.id}`, 'projet')
  await menuEcran(p, 'Dupliquer')
  const double = await creerDepuisDialogue(p, 'Dupliquer', 'Chantier Benali 9 kWc — double')
  expect(double.projet?.nom, 'projet dupliqué').toBe('Chantier Benali 9 kWc — double')
  expect(double.projet.id).not.toBe(benali.id)
  if (!double.ouvert) ecarts.push(`Dupliquer → Créer : projet ${double.projet.id} créé, l'écran reste sur ${double.adresse}`)
  // « projet créé » : le projet tiré du modèle et le double s'ouvrent (ProjetsModeles.jsx : « Un projet créé depuis un
  // modèle s'ouvre » ; Projet.jsx : « Dupliquer : le double s'ouvre »).
  expect(ecarts, "le projet créé s'ouvre").toEqual([])
})

etape('P172.3', ['TCH172', 'TCH156', 'TCH166'], async (f) => {
  const instant = scenario172()
  const p = await ouvrir(f, { instant })
  const rails = await tacheNommee(p, RAILS)
  await aller(p, `/taches/aujourdhui?tache=${rails.id}`, 'aujourdhui')
  const fiche = p.locator(`[data-fiche="${rails.id}"]`)
  await fiche.getByRole('button', { name: 'Plus', exact: true }).click()
  // Oracle (plan) : « étiquette `magasin` posée dans Plus »
  const bloc = fiche.getByRole('region', { name: 'Étiquettes' })
  await bloc.getByRole('textbox', { name: 'Ajouter une étiquette' }).pressSequentially('magasin')
  await bloc.getByRole('textbox', { name: 'Ajouter une étiquette' }).press('Enter')
  await expect(bloc.getByRole('button', { name: 'magasin', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await capturer(p, 'fiche-plus-etiquette')
  expect((await lireTache(p, rails.id)).etiquettes.map((e) => e.nom), 'étiquette posée').toEqual(['magasin'])
  // Oracle (plan) : « filtre par étiquette »
  await aller(p, '/taches/recherche', 'recherche')
  await p.getByRole('button', { name: 'Plus de filtres', exact: true }).click()
  const choix = p.locator('label.champ-etiquette').filter({ hasText: /^Étiquette/ }).locator('select')
  await expect(choix).toBeVisible()
  await choix.selectOption({ label: 'magasin' })
  const ouvertes = p.getByRole('region', { name: /^Ouvertes \(\d+\)$/ })
  await expect(ouvertes).toHaveAttribute('aria-label', 'Ouvertes (1)', { timeout: 30_000 })
  await expect(ouvertes.locator('.titre')).toHaveText([RAILS])
  await capturer(p, 'recherche-etiquette')
})

etape('P172.4', ['TCH172', 'TCH156', 'TCH166'], async (f) => {
  const instant = scenario172()
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/recherche', 'recherche')
  // Oracle (plan) : « Recherche « devis » »
  await p.getByRole('searchbox', { name: 'Chercher dans mes tâches' }).fill('devis')
  await expect(p).toHaveURL(/[?&]q=devis/)
  const ouvertes = p.getByRole('region', { name: /^Ouvertes \(\d+\)$/ })
  await expect(ouvertes.locator('.titre').first()).toBeVisible({ timeout: 30_000 })
  const avant = await ouvertes.locator('.titre').allTextContents()
  // « → Enregistrer la vue »
  await p.getByRole('button', { name: 'Plus de filtres', exact: true }).click()
  await p.getByRole('textbox', { name: 'Nom de la vue' }).fill('Mes devis')
  await p.getByRole('button', { name: 'Enregistrer cette vue', exact: true }).click()
  await expect(toast(p)).toContainText('Vue enregistrée')
  const vues = liste(await lire(p, 'vues/'))
  expect(vues.map((v) => [v.nom, v.filtres]), 'vue enregistrée').toEqual([['Mes devis', { q: 'devis', inclure_faites: false }]])
  await capturer(p, 'recherche-vue-enregistree')
  // « → rouvrir = mêmes filtres »
  await aller(p, '/taches/recherche', 'recherche')
  await expect(p.getByRole('searchbox', { name: 'Chercher dans mes tâches' })).toHaveValue('')
  await p.getByRole('button', { name: 'Plus de filtres', exact: true }).click()
  await p.getByRole('group', { name: 'Mes vues' }).getByRole('button', { name: 'Mes devis', exact: true }).click()
  await expect(p.getByRole('searchbox', { name: 'Chercher dans mes tâches' })).toHaveValue('devis')
  for (const nom of ['Faites aussi', 'Priorité haute']) await expect(p.getByRole('checkbox', { name: nom })).toHaveAttribute('aria-checked', 'false')
  await expect(ouvertes.locator('.titre')).toHaveText(avant, { timeout: 30_000 })
  await capturer(p, 'recherche-vue-rouverte')
})

// Pile laissée à l'heure réelle après le dernier parcours (le projet `setup` de la prochaine passe en a besoin).
test.afterAll(() => { try { pile('horloge', 'reel') } catch { /* la pile a pu être arrêtée par l'orchestrateur */ } })
