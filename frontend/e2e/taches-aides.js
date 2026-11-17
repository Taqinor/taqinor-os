// Aides PARTAGÉES des specs « Tâches » (taches-journee / taches-saisie / taches-projets / taches-a11y).
//
// Ce que ce module garantit à chaque spec :
//   - un état de départ connu : `reinitialiser` efface les tâches du compte `demo_admin` par la vraie route
//     « Tout effacer » (`POST tout-effacer/ {confirmation: "EFFACER"}`, un seul compte, une seule société) ;
//   - des données qu'elle CRÉE elle-même par l'API (titres uniques) : aucune dépendance à `seed_taches_demo`
//     (dont la journée du 24/11 suppose une horloge figée que la pile de CI n'a pas) ni à l'ordre des specs ;
//   - aucune attente fixe : on attend des états visibles ou des réponses observées.
// Les hooks DOM lus ici sont ceux que les écrans posent déjà : `.tch[data-ecran]`, `data-ligne`, `data-fiche`,
// `data-jeton`, les rôles et noms accessibles (voir `frontend/src/features/taches/**`).
import { randomUUID } from 'node:crypto'
import { expect } from '@playwright/test'

export const API = '/api/django/taches'

let _seq = 0
/** Suffixe UNIQUE fait de lettres seules : « k3 » ou « 2h » seraient lus comme une heure ou une durée par l'analyse de la saisie. */
export function suffixe() {
  _seq += 1
  return `${String(Date.now()).slice(-8)}${_seq}`.replace(/\d/g, (c) => 'abcdefghij'[Number(c)])
}
/** Un titre unique : « Appeler le fournisseur bcdfhgaeab ». */
export const titreUnique = (prefixe) => `${prefixe} ${suffixe()}`

async function json(res, quoi) {
  expect(res.ok(), `${quoi} → HTTP ${res.status()} ${await res.text()}`).toBeTruthy()
  return res.json()
}

const cle = () => ({ 'Idempotency-Key': randomUUID() })

/** Efface les tâches du compte connecté (la route que l'écran « Mes données » appelle). */
export async function reinitialiser(page) {
  await json(await page.request.post(`${API}/tout-effacer/`, { data: { confirmation: 'EFFACER' } }), 'tout-effacer')
}

/** Le jour du SERVEUR (`AAAA-MM-JJ`) : celui de `aujourdhui/`, jamais l'horloge du test. */
export async function jourServeur(page) {
  return (await json(await page.request.get(`${API}/aujourdhui/`), 'aujourdhui')).jour
}

/** Crée un projet ; rend l'objet projet (`{id, nom, …}`). */
export async function creerProjet(page, nom, priorite = 0) {
  const corps = await json(
    await page.request.post(`${API}/projets/`, { data: { nom, priorite }, headers: cle() }), `créer le projet « ${nom} »`)
  return corps.projet ?? corps
}

/** Crée des tâches (une par titre, dans l'ordre) par `saisie-rapide/` ; `commun` = champs de ligne communs
 *  (`projet_id`, `jour_prevu`…). Rend `[{id, titre, …}]` dans l'ordre des titres. */
export async function creerTaches(page, titres, commun = {}) {
  const lignes = titres.map((titre, index) => ({ index, client_id: `${randomUUID()}:${index}`, titre, ...commun }))
  const corps = await json(
    await page.request.post(`${API}/saisie-rapide/`, { data: { lignes, apercu: false }, headers: cle() }),
    `créer ${titres.length} tâche(s)`)
  const creees = corps.creees ?? []
  expect(creees, 'les tâches créées sont rendues').toHaveLength(titres.length)
  return titres.map((titre) => {
    const trouvee = creees.find((t) => t.titre === titre)
    expect(trouvee, `la tâche « ${titre} » est rendue par la création`).toBeTruthy()
    return trouvee
  })
}

/** La tâche complète (forme TACHE : `lock_version`, `statut`, `jour_prevu`, `projet`, `reports`…). */
export async function lireTache(page, id) {
  return json(await page.request.get(`${API}/taches/${id}/`), `lire la tâche ${id}`)
}

/** Les tâches dont le titre contient ces mots (faites comprises). */
export async function chercherTaches(page, mots) {
  const corps = await json(
    await page.request.get(`${API}/taches/`, { params: { q: mots, inclure_faites: 'true' } }), `chercher « ${mots} »`)
  return Array.isArray(corps) ? corps : (corps.results ?? [])
}

/** Les projets du compte (toutes les pages utiles aux specs : moins de 50). */
export async function listerProjets(page) {
  const corps = await json(await page.request.get(`${API}/projets/`), 'lister les projets')
  return Array.isArray(corps) ? corps : (corps.results ?? [])
}

/** Ouvre un écran de l'app et attend sa coquille (`.tch[data-ecran]`). */
export async function ouvrirEcran(page, chemin, ecran) {
  await page.goto(chemin)
  await expect(page.locator(`.tch[data-ecran="${ecran}"]`)).toBeVisible()
}

/** La ligne d'une tâche (Aujourd'hui, Projet, À trier : même hook `data-ligne`). */
export const ligne = (page, id) => page.locator(`[data-ligne="tache:${id}"]`)

/** Le toast « … · Annuler » (un seul à la fois). */
export const toast = (page) => page.getByRole('group', { name: 'Geste effectué' })

/** La région `role=status` qui annonce chaque geste au lecteur d'écran. */
export const annonce = (page) => page.locator('.tch .annonce')

/** Ouvre le menu « Actions pour « titre » » d'une ligne. Le bouton n'est cliquable qu'au survol (bureau) ou au
 *  focus : on survole donc la ligne d'abord, comme le fait la personne. */
export async function ouvrirActions(page, laLigne, titre) {
  await laLigne.hover()
  await laLigne.getByRole('button', { name: `Actions pour « ${titre} »` }).click()
}

/** Attend qu'Aujourd'hui ait lu sa journée (la ligne de progression est là). */
export async function attendreAujourdhui(page) {
  await ouvrirEcran(page, '/taches/aujourdhui', 'aujourdhui')
  await expect(page.getByRole('button', { name: /Détail de la journée$/ })).toBeVisible()
}

/** La section d'Aujourd'hui qui porte ce titre (Essentiel, Prévu, Ce soir). */
export const section = (page, titre) => page.locator('section.section')
  .filter({ has: page.getByRole('heading', { name: titre, exact: true }) })
