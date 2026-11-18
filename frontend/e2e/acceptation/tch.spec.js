// TCH136-TCH140, TCH144 — ACCEPTATION EN DIRECT de la fusion F2 du module « Tâches » (CLAUDE.md 3-bis).
//
// Six parcours rejoués sur la pile locale, compte `demo_taches` semé par `manage.py seed_taches_demo`
// (journée du mardi 24/11/2026 de `docs/taches/maquettes/SCENARIO.md`). Une ÉTAPE = un test = UN oracle du plan
// (`docs/plans/PLAN_TACHES.md`, lignes TCH136-TCH144), recopié mot pour mot ; chiffres de SCENARIO.md.
// Règle d'or : un oracle ne se modifie JAMAIS pour faire passer une étape — l'écart est un défaut (rapport).
//
// Chaque étape est INDÉPENDANTE : elle pose son scénario (semis + horloge du serveur, `taches-acceptation.js`),
// rejoue par l'API les gestes qui la précèdent dans le parcours, puis joue SON geste à l'écran. Horloge du
// navigateur = celle du scénario (`page.clock.install`), fuseau `UTC` (Maroc = GMT toute l'année depuis le
// 20/09/2026 ; Chromium périmé) ; P139.7 rejoue le même geste depuis un navigateur en `Africa/Casablanca` périmé.
// Vues : iPhone (390 × 844, tactile) par défaut, bureau (1440 × 900) pour le clavier (P144.3).
//
// Écarts de LECTURE déjà relevés entre le plan et SCENARIO.md / la référence (ERR-PLAN, dits au rapport — l'oracle
// joué est celui qui fait foi, et le commentaire de l'étape le dit) :
//   - P136.2 : `premier-usage-1-apercu.html` ne montre que 2 listes (Salon Solaire Expo, Recrutement technicien) ;
//     les 2 autres collages sont pris de SCENARIO.md §2 (Administratif, Site web).
//   - P136.5 : le semis CONVERTIT déjà « Envoyer la facture d'acompte » (SCENARIO §1 : elle est dans À trier) ;
//     l'étape la remet à convertir (activité rouverte, tâche du semis retirée) avant de jouer le bandeau.
//   - P137.1 : le plan cite « Relire le contrat de maintenance » dans Proposé ; SCENARIO §3 dit le contraire
//     (« n'est PAS proposé ») et nomme « Rédiger la fiche de poste » : SCENARIO fait foi.
//   - P144.3 : « ≈ 27 touches » du parcours 18 compte 4 touches de palette (Copilote, F3) : ici 23 au plus.
import { readFileSync } from 'node:fs'
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { garderParApi, lireTache, section, toast } from '../taches-aides.js'
import {
  API, aller, appuiLong, balayer, capturer, connecter, itemsDe, lire, liste, ouvrir, pile, poserVisiteTemara, salir, scenario,
  tacheNommee,
} from '../taches-acceptation.js'

const PARCOURS = ['TCH136', 'TCH137', 'TCH138', 'TCH139', 'TCH140', 'TCH144']
const CONSTRUCTION = [
  'TCH36', 'TCH40', 'TCH48', 'TCH49', 'TCH50', 'TCH53', 'TCH54', 'TCH55', 'TCH56', 'TCH57', 'TCH58', 'TCH59', 'TCH60',
  'TCH61', 'TCH63', 'TCH65', 'TCH66', 'TCH67', 'TCH69', 'TCH73', 'TCH74', 'TCH76', 'TCH77', 'TCH78', 'TCH79', 'TCH80',
  'TCH81', 'TCH82', 'TCH83', 'TCH84', 'TCH86', 'TCH87', 'TCH88', 'TCH91', 'TCH92', 'TCH93', 'TCH100', 'TCH104', 'TCH105',
  'TCH106', 'TCH107', 'TCH108', 'TCH119', 'TCH121', 'TCH122', 'TCH130', 'TCH131', 'TCH154', 'TCH169',
]
const etape = groupe('TCH', [...PARCOURS, ...CONSTRUCTION])
test.describe.configure({ timeout: 600_000 })
fermerDjangoApresTout()

// --- Le scénario (SCENARIO.md) ------------------------------------------------------------------------------------
const J24 = '2026-11-24'
const MATIN = ['--jour', J24, '--heure', '08:30', '--historique', '10']
const T = {
  rails: 'Commander les rails de fixation', fournisseur: 'Appeler le fournisseur', fiche: 'Rédiger la fiche de poste',
  contrat: 'Relire le contrat de maintenance', devis: 'Envoyer le devis révisé', stand: 'Confirmer la réservation du stand',
  demo: 'Préparer la démo onduleur hybride', planning: 'Mettre à jour le planning des poses', tva: 'Préparer la déclaration de TVA',
  rappel: 'Rappeler pour le devis', facture: "Envoyer la facture d'acompte", visite: 'Visite — Témara', // SCENARIO §0 errata 5 : une visite venue de l'ERP se nomme « Visite — {lead} »
}
const echapper = (texte) => texte.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const progression = (p) => p.locator('button.progression')
const aujourdhui = async (p) => {
  await aller(p, '/taches/aujourdhui', 'aujourdhui')
  await expect(progression(p)).toBeVisible()
}
const ligneNommee = (p, titre) => p.locator('[data-ligne]').filter({ has: p.locator('.titre', { hasText: new RegExp(`^${echapper(titre)}$`) }) })
const sectionPropose = (p) => p.locator('section.section[aria-label="Proposé pour aujourd\'hui"]')
const replie = (p, titre) => p.locator('button.replie').filter({ hasText: titre })
const feuille = (p, nom) => p.getByRole('dialog', { name: nom })
const saisie = (p) => feuille(p, 'Ajouter une tâche')
const champSaisie = (p) => saisie(p).getByRole('textbox', { name: 'Ajouter une tâche', exact: true })
const idTache = async (p, titre) => (await tacheNommee(p, titre)).id

/** Le compte `demo_taches` vu par le shell Django : `u` (utilisateur) et `soc` (sa société). */
const DEMO = "u = U.objects.get(username='demo_taches'); soc = u.company_id\n"

// =====================================================================================================================
// TCH136 — Parcours « je note tout » (spec-7 « Parcours chiffrés » 2, 9, 14)
// =====================================================================================================================

etape('P136.1', ['TCH136', 'TCH76', 'TCH83'], async (f) => {
  const instant = scenario(['--vide'], `${J24} 08:30`, { lecture: true })
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/aujourdhui', 'aujourdhui')
  // Oracle (plan) : `/taches/aujourdhui` → « Colle ou dicte tes listes. » — texte exact : textes.md §2.2 « Aucun
  // projet, aucune tâche » = « Colle ou dicte tes listes : je les range par projet. » + **Coller mes listes**.
  await expect(p.getByText('Colle ou dicte tes listes : je les range par projet.', { exact: true })).toBeVisible()
  await expect(p.getByRole('button', { name: 'Coller mes listes' })).toBeVisible()
  await capturer(p, 'aujourdhui-vide')
})

/** Les 4 collages : 2 de `premier-usage-1-apercu.html` (les seuls qu'elle montre), 2 de SCENARIO.md §2. */
const COLLAGES = [
  ['Salon Solaire Expo', 'Réserver le stand', 'Imprimer les kakémonos', 'Préparer la démo onduleur hybride'],
  ['Recrutement technicien', "Publier l'annonce", 'Trier les CV reçus', 'Valider le budget du poste'],
  ['Administratif', "Payer la CNSS d'octobre", "Envoyer les factures d'octobre", 'Payer le loyer du dépôt'],
  ['Site web', 'Lister les pages du site', "Choisir l'hébergeur", "Rédiger la page d'accueil"],
]

async function collerLesQuatre(p) {
  await aller(p, '/taches/aujourdhui', 'aujourdhui')
  await p.getByRole('button', { name: 'Coller mes listes' }).click()
  await expect(saisie(p)).toBeVisible()
  for (const [rang, collage] of COLLAGES.entries()) {
    if (rang > 0) await saisie(p).getByRole('button', { name: 'Coller encore' }).click()
    await champSaisie(p).fill(collage.join('\n'))
    await expect(saisie(p).getByText(`Nouveau projet : ${collage[0]}`)).toBeVisible()
    if (rang === 0) await capturer(p, 'apercu-collage')
  }
}

etape('P136.2', ['TCH136', 'TCH83', 'TCH48', 'TCH40'], async (f) => {
  const instant = scenario(['--vide'], `${J24} 08:30`, { lecture: true })
  const p = await ouvrir(f, { instant })
  await collerLesQuatre(p)
  // Oracle : 4 listes → 4 « Nouveau projet », puce Moyenne.
  await expect(saisie(p).getByText(/^Nouveau projet : /)).toHaveCount(4)
  for (const [nom] of COLLAGES) {
    await expect(saisie(p).getByRole('radiogroup', { name: `Priorité du projet ${nom}` })
      .getByRole('radio', { name: 'Moyenne' })).toBeChecked()
  }
  // l'aperçu n'écrit rien
  expect(liste(await lire(p, 'projets/'))).toHaveLength(0)
})

etape('P136.3', ['TCH136', 'TCH48', 'TCH36', 'TCH83'], async (f) => {
  const instant = scenario(['--vide'], `${J24} 08:30`)
  const p = await ouvrir(f, { instant })
  await collerLesQuatre(p)
  await saisie(p).getByRole('button', { name: 'Créer 12 tâches' }).click()
  await expect(saisie(p)).toHaveCount(0)
  // Oracle : Créer → les tâches et 4 projets existent (`GET projets/` count 4).
  const projets = await lire(p, 'projets/')
  expect(projets.count ?? liste(projets).length, 'GET projets/ : count').toBe(4)
  expect(liste(projets).map((x) => x.nom).sort()).toEqual(COLLAGES.map(([nom]) => nom).sort())
  for (const [nom, ...titres] of COLLAGES) {
    for (const titre of titres) expect((await tacheNommee(p, titre)).projet?.nom, `« ${titre} » dans ${nom}`).toBe(nom)
  }
  await p.reload()
  await expect(progression(p)).toBeVisible()
  f.suivi.verifie(5)
})

etape('P136.4', ['TCH136', 'TCH86', 'TCH49', 'TCH169'], async (f) => {
  const instant = scenario(MATIN, `${J24} 08:30`)
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/a-trier', 'a-trier')
  const lignes = p.locator('section.section[aria-label="À trier"] [data-ligne^="tache:"]')
  // Plan TCH136 étape 4 (corrigé) et SCENARIO §0 errata 2 : en fusion 2, À trier porte 4 lignes ; la facture
  // d'acompte est l'à-faire du bandeau, convertie à l'étape 5.
  await expect(lignes).toHaveCount(4)
  await capturer(p, 'a-trier')
  const parTitre = (titre) => p.locator('section.section[aria-label="À trier"] [data-ligne^="tache:"]')
    .filter({ has: p.locator('.titre', { hasText: new RegExp(`^${echapper(titre)}$`) }) })
  // 2 dates
  await parTitre("Acheter des cartouches pour l'imprimante").getByRole('button', { name: "Aujourd'hui", exact: true }).click()
  await expect(parTitre("Acheter des cartouches pour l'imprimante")).toHaveCount(0)
  await parTitre("Demander le devis d'assurance décennale").getByRole('button', { name: 'Demain', exact: true }).click()
  await expect(parTitre("Demander le devis d'assurance décennale")).toHaveCount(0)
  // 2 projets
  for (const [titre, projet] of [['Préparer le chantier du devis accepté', 'Chantier Benali 9 kWc'],
    ['Filmer le chantier pour Instagram', 'Site web']]) {
    await parTitre(titre).getByRole('button', { name: 'Projet…', exact: true }).click()
    await feuille(p, 'Projet').getByRole('option', { name: projet }).click()
    await expect(parTitre(titre)).toHaveCount(0)
  }
  // Oracle : « Rien à trier »
  await expect(p.getByText('Rien à trier', { exact: true })).toBeVisible()
  await p.reload()
  await expect(p.getByText('Rien à trier', { exact: true })).toBeVisible()
  expect((await tacheNommee(p, "Acheter des cartouches pour l'imprimante")).jour_prevu).toBe(J24)
  expect((await tacheNommee(p, "Demander le devis d'assurance décennale")).jour_prevu).toBe('2026-11-25')
  expect((await tacheNommee(p, 'Filmer le chantier pour Instagram')).projet?.nom).toBe('Site web')
})

etape('P136.5', ['TCH136', 'TCH73', 'TCH86'], async (f) => {
  const instant = scenario(MATIN, `${J24} 08:30`)
  // ERR-PLAN : le semis a déjà converti l'à-faire ; on le remet à convertir (activité rouverte, tâche du semis ôtée).
  const act = await py(`${DEMO}
from apps.records.models import Activity
from apps.taches.models.taches import Tache
a = Activity.objects.get(company_id=soc, created_by=u, personnelle=True, summary="${T.facture}")
Tache.all_objects.filter(company_id=soc, proprietaire=u, titre="${T.facture}").delete()
Activity.objects.filter(pk=a.pk).update(done=False, done_at=None, done_by=None)
sortie({'id': a.pk})`)
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/a-trier', 'a-trier')
  const bandeau = p.getByRole('region', { name: 'Activités personnelles' })
  await expect(bandeau).toContainText('1 à-faire personnel dans Activités')
  await bandeau.getByRole('button', { name: 'Tout convertir' }).click()
  await expect(bandeau).toHaveCount(0)
  // Oracle : tâche créée, à-faire clos dans `/activites`.
  await expect(toast(p)).toContainText('Ajoutée')
  // spec-2 §« à-faire convertis » : `due_date` → JOUR PRÉVU (la tâche part donc dans le ven. 27, pas dans À trier)
  expect((await tacheNommee(p, T.facture)).jour_prevu).toBe('2026-11-27')
  // « clos dans /activites » : l'écran Activités lit ce même drapeau `done` (records)
  const close = await py(`from apps.records.models import Activity\nsortie(Activity.objects.get(pk=${act.id}).done)`)
  expect(close, "l'à-faire est clos dans Activités").toBe(true)
})

etape('P136.6', ['TCH136', 'TCH82'], async (f) => {
  const instant = scenario(MATIN, `${J24} 08:30`)
  const p = await ouvrir(f, { instant })
  await aujourdhui(p)
  const brouillon = 'Penser à rappeler le syndic jeudi'
  await p.getByRole('button', { name: 'Ajouter une tâche', exact: true }).first().click()
  await champSaisie(p).pressSequentially(brouillon)
  await capturer(p, 'saisie')
  await p.keyboard.press('Escape')
  await expect(saisie(p)).toHaveCount(0)
  // Oracle : fermer la saisie en cours de frappe puis rouvrir → brouillon repris.
  const carte = p.getByRole('region', { name: 'Brouillon' })
  await expect(carte).toContainText("Ta saisie de tout à l'heure t'attend.")
  await carte.getByRole('button', { name: 'Reprendre' }).click()
  await expect(champSaisie(p)).toHaveValue(brouillon)
  expect(liste(await lire(p, 'taches/', { q: 'rappeler le syndic' })), 'rien de créé').toHaveLength(0)
})

// =====================================================================================================================
// TCH137 — Parcours « ma journée » (SCENARIO.md §3 ; parcours 3-8, 13, 15)
// =====================================================================================================================

etape('P137.1', ['TCH137', 'TCH76', 'TCH77', 'TCH78', 'TCH54', 'TCH56', 'TCH57', 'TCH169'], async (f) => {
  const instant = scenario(MATIN, `${J24} 08:30`, { lecture: true })
  const p = await ouvrir(f, { instant })
  await aujourdhui(p)
  await capturer(p, 'aujourdhui-matin')
  // Oracle : « 0 sur 5 · essentiel 0/2 »
  await expect(progression(p)).toContainText('0 sur 5 · essentiel 0/2')
  // Oracle : Proposé 3 — SCENARIO §3 (fait foi, ERR-PLAN sur le 3e titre) : rails · fournisseur · fiche de poste.
  await expect(sectionPropose(p).locator('[data-ligne] .titre')).toHaveText([T.rails, T.fournisseur, T.fiche])
  // Oracle : carte « Garder ces 3 » (« 3 tâches proposées pour atteindre 5 · Garder ces 3 »)
  const carte = p.locator('.moment[aria-label="Proposé pour aujourd\'hui"]')
  await expect(carte).toContainText('3 tâches proposées')
  await expect(carte).toContainText('pour atteindre 5')
  await expect(carte.getByRole('button', { name: 'Garder ces 3', exact: true })).toBeVisible()
  // Oracle : À revoir 2, En attente 1 (repliés)
  await expect(replie(p, 'À revoir')).toHaveText(/^À revoir\s*2/)
  await expect(replie(p, 'En attente')).toHaveText(/^En attente\s*1/)
})

etape('P137.2', ['TCH137', 'TCH78', 'TCH57'], async (f) => {
  const instant = scenario(MATIN, `${J24} 08:30`)
  const p = await ouvrir(f, { instant })
  const proposees = (await lire(p, 'aujourdhui/')).propose.pour_objectif.map((it) => it.titre)
  await aujourdhui(p)
  // « Garder ces 3 » : celui de la carte du moment (SCENARIO) ou, sans elle, celui de Proposé — le même geste
  await p.getByRole('button', { name: 'Garder ces 3', exact: true }).first().click()
  // Oracle : Garder ces 3 → focus sur Prévu
  await expect(section(p, 'Prévu')).toBeFocused()
  for (const titre of proposees) {
    await expect(section(p, 'Prévu').getByText(titre, { exact: true })).toBeVisible()
    expect((await tacheNommee(p, titre)).jour_prevu, `« ${titre} » gardée aujourd'hui`).toBe(J24)
  }
})

/** Le matin après « Garder ces 3 » (08:31), joué par la vraie route. */
async function matinGarde(p) {
  const journee = await lire(p, 'aujourdhui/')
  const proposees = (journee.propose?.pour_objectif ?? []).filter((it) => it.type === 'tache')
  await garderParApi(p, proposees)
  return proposees
}

etape('P137.3', ['TCH137', 'TCH50', 'TCH77'], async (f) => {
  const instant = scenario(MATIN, `${J24} 08:30`)
  const p = await ouvrir(f, { instant })
  await matinGarde(p)
  await aujourdhui(p)
  await ligneNommee(p, T.rails).getByRole('checkbox', { name: `Marquer « ${T.rails} » comme faite` }).click()
  // Oracle : cocher « Commander les rails » → « 1 sur 5 »
  await expect(progression(p)).toContainText('1 sur 5')
  await expect.poll(async () => (await tacheNommee(p, T.rails)).statut).toBe('fait')
  await p.reload()
  await expect(progression(p)).toContainText('1 sur 5')
})

etape('P137.4', ['TCH137', 'TCH81', 'TCH73'], async (f) => {
  const instant = scenario(MATIN, `${J24} 08:30`)
  const p = await ouvrir(f, { instant })
  await aujourdhui(p)
  const activite = itemsDe(await lire(p, 'aujourdhui/')).find((it) => it.type === 'activite' && it.titre === T.rappel)
  expect(activite, `l'activité ERP « ${T.rappel} » est servie par aujourdhui/`).toBeTruthy()
  const avant = await py(`from apps.taches.models.taches import Tache\nsortie(Tache.objects.filter(activite_origine_id=${activite.id}).count())`)
  // Oracle : appui long sur « Rappeler pour le devis » → Lier une tâche → tâche créée, activité toujours ouverte.
  await appuiLong(p, p.locator(`[data-ligne="activite:${activite.id}"]`), 'Lier une tâche')
  await p.getByRole('menuitem', { name: 'Lier une tâche' }).click()
  await feuille(p, 'Lier une tâche').getByRole('button', { name: 'Lier une tâche' }).click()
  await expect(toast(p)).toContainText("Tâche liée à l'activité")
  const apres = await py(`from apps.records.models import Activity
from apps.taches.models.taches import Tache
sortie({'n': Tache.objects.filter(activite_origine_id=${activite.id}).count(), 'close': Activity.objects.get(pk=${activite.id}).done})`)
  expect(apres.n, 'une tâche liée de plus').toBe(avant + 1)
  expect(apres.close, "l'activité reste ouverte").toBe(false)
})

etape('P137.5', ['TCH137', 'TCH50', 'TCH53'], async (f) => {
  const instant = scenario(MATIN, `${J24} 08:30`)
  const p = await ouvrir(f, { instant })
  const gardees = (await matinGarde(p)).map((it) => it.titre)
  // « une tâche » gardée : le fournisseur (SCENARIO) s'il est dans Prévu, sinon la première gardée
  const titre = gardees.includes(T.fournisseur) ? T.fournisseur : gardees[0]
  await aujourdhui(p)
  const cible = ligneNommee(p, titre)
  await balayer(p, cible, -1)
  // Oracle : balayage gauche → « Reportée à mer. 25 · Annuler »
  await expect(toast(p)).toContainText('Reportée à mer. 25')
  await expect(toast(p).getByRole('button', { name: 'Annuler' })).toBeVisible()
  await expect.poll(async () => (await tacheNommee(p, titre)).jour_prevu).toBe('2026-11-25')
  // Annuler → revenue
  await toast(p).getByRole('button', { name: 'Annuler' }).click()
  await expect.poll(async () => (await tacheNommee(p, titre)).jour_prevu).toBe(J24)
  await p.reload()
  await expect(section(p, 'Prévu').getByText(titre, { exact: true })).toBeVisible()
})

etape('P137.6', ['TCH137', 'TCH58', 'TCH79', 'TCH78', 'TCH77'], async (f) => {
  const instant = scenario([...MATIN.slice(0, 2), '--heure', '15:00', '--historique', '10'], `${J24} 15:00`)
  const p = await ouvrir(f, { instant })
  await aujourdhui(p)
  await capturer(p, 'aujourdhui-15h')
  // Oracle : « 3 sur 5 · essentiel 1/2 », « Objectif couvert par ce que tu as gardé. »
  await expect(progression(p)).toContainText('3 sur 5 · essentiel 1/2')
  await expect(sectionPropose(p)).toContainText('Objectif couvert par ce que tu as gardé.')
  // Alléger en gardant 1 → reste retourné sans report
  await p.getByRole('button', { name: "Plus d'actions" }).click()
  await p.getByRole('menuitem', { name: 'Alléger ma journée' }).click()
  const leger = feuille(p, 'Alléger ma journée')
  const cases = leger.getByRole('checkbox', { name: /^Sélectionner : / })
  await expect(cases.first()).toBeVisible()
  const titres = (await cases.evaluateAll((els) => els.map((e) => e.getAttribute('aria-label')))).map((n) => n.replace('Sélectionner : ', ''))
  expect(titres.length, 'au moins deux gardées ouvertes à alléger').toBeGreaterThanOrEqual(2)
  const gardee = titres.includes(T.stand) ? T.stand : titres[0]
  const avant = Object.fromEntries(await Promise.all(titres.map(async (t) => [t, await tacheNommee(p, t)])))
  await leger.getByRole('checkbox', { name: `Sélectionner : ${gardee}` }).click()
  await leger.getByRole('button', { name: 'Garder celle-ci' }).click()
  await expect(toast(p)).toContainText(/retournées? aux projets/)
  for (const t of titres.filter((x) => x !== gardee)) {
    const lue = await tacheNommee(p, t)
    expect(lue.jour_prevu, `« ${t} » retournée à son projet`).toBeNull()
    expect(lue.reports, `« ${t} » : aucun report compté`).toBe(avant[t].reports)
  }
  expect((await tacheNommee(p, gardee)).jour_prevu).toBe(J24)
})

etape('P137.7', ['TCH137', 'TCH80', 'TCH58'], async (f) => {
  const instant = scenario([...MATIN.slice(0, 2), '--heure', '18:20', '--historique', '10'], `${J24} 18:20`)
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/aujourdhui?ouvrir=bilan', 'aujourdhui')
  const bilan = feuille(p, 'Bilan du soir')
  await expect(bilan.locator('.bilan-compte')).toBeVisible()
  await capturer(p, 'bilan')
  // Oracle : bilan « 4 sur 5 · essentiel 2 sur 2 », « 4 des 5 gardées »
  await expect(bilan.locator('.bilan-compte')).toHaveText('4 sur 5 · essentiel 2 sur 2')
  await expect(bilan).toContainText('4 des 5 gardées')
  // Tout reporter → contrat à mer. 25
  await bilan.getByRole('button', { name: 'Tout reporter à mer. 25' }).click()
  await bilan.getByRole('button', { name: 'Valider', exact: true }).click()
  await expect(toast(p)).toContainText('Bilan enregistré')
  await expect.poll(async () => (await tacheNommee(p, T.contrat)).jour_prevu).toBe('2026-11-25')
})

etape('P137.8', ['TCH137', 'TCH56', 'TCH76'], async (f) => {
  const instant = scenario(['--jour', '2026-12-07', '--absence', '10'], '2026-12-07 08:30')
  const p = await ouvrir(f, { instant })
  await aujourdhui(p)
  await capturer(p, 'aujourdhui-retour')
  // Oracle : carte « Tu reviens après 10 jours… » (textes.md §4.2 `retour`)
  await expect(p.getByRole('region', { name: 'Retour' })).toContainText(/^Tu reviens après 10 jours/)
  await expect(progression(p)).toContainText('Reprise')
})

// =====================================================================================================================
// TCH138 — Parcours « projets » (SCENARIO.md « Les jours passés » ; parcours 10, 19, 20)
// =====================================================================================================================

const ligneProjet = (p, nom) => p.locator('[data-projet]').filter({ has: p.locator('.titre', { hasText: new RegExp(`^${echapper(nom)}$`) }) })

etape('P138.1', ['TCH138', 'TCH60', 'TCH88', 'TCH169'], async (f) => {
  const instant = scenario(['--jour', J24, '--heure', '08:30'], `${J24} 08:30`, { lecture: true })
  const p = await ouvrir(f, { instant })
  // captures d'abord (la vue d'un projet, puis retour à la liste)
  await aller(p, '/taches/projets', 'projets')
  await expect(p.locator('[data-projet]').first()).toBeVisible()
  await capturer(p, 'projets')
  await ligneProjet(p, 'Chantier Benali 9 kWc').locator('.ep-ouvrir').click()
  await expect(p.locator('.tch[data-ecran="projet"]')).toBeVisible()
  await capturer(p, 'projet')
  await aller(p, '/taches/projets', 'projets')
  // Oracle (plan TCH138 étape 1 corrigé, SCENARIO §0 errata 3) : 5 projets, Benali « 12 sur 18 », Site web « 0 sur 4 »
  // (« À planifier » exige zéro tâche ouverte, regles.md)
  await expect(p.locator('[data-projet]')).toHaveCount(5)
  await expect(ligneProjet(p, 'Chantier Benali 9 kWc')).toContainText('12 sur 18')
  await expect(ligneProjet(p, 'Site web')).toContainText('0 sur 4')
})

etape('P138.2', ['TCH138', 'TCH88', 'TCH91', 'TCH63'], async (f) => {
  const instant = scenario(['--jour', J24, '--heure', '08:30'], `${J24} 08:30`)
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/projets', 'projets')
  await p.getByRole('button', { name: 'Nouveau projet', exact: true }).click()
  const nouveau = feuille(p, 'Nouveau projet')
  await nouveau.getByLabel('Nom du projet').fill('Stand partenaire')
  await nouveau.getByRole('button', { name: 'Créer', exact: true }).click()
  await expect(p).toHaveURL(/\/taches\/projets\/\d+\?planifier=1/)
  const idProjet = Number(new URL(p.url()).pathname.split('/').pop())
  const rituel = p.getByRole('region', { name: 'Planifier le projet' })
  await capturer(p, 'planifier-projet')
  // priorité Haute, fini quand, échéance 6 semaines
  await rituel.getByLabel('Ce sera fini quand…').fill('le stand est monté et validé')
  await rituel.getByRole('radio', { name: '6 semaines', exact: true }).click()
  await rituel.getByRole('radio', { name: /^Haute/ }).click()
  await rituel.getByRole('button', { name: 'Suivant', exact: true }).click()
  // 2 actions
  const actions = ['Réserver le camion du stand', 'Imprimer les badges partenaires']
  for (const titre of actions) {
    await rituel.getByLabel('Nouvelle action').fill(titre)
    await rituel.getByRole('button', { name: 'Ajouter', exact: true }).click()
    await expect(rituel.getByText(titre, { exact: true })).toBeVisible()
  }
  await rituel.getByRole('button', { name: 'Terminer', exact: true }).click()
  await expect(p.getByRole('region', { name: 'Planifier le projet' })).toHaveCount(0)
  // Oracle : tâches créées
  for (const titre of actions) expect((await tacheNommee(p, titre)).projet?.id).toBe(idProjet)
  const projet = await lire(p, `projets/${idProjet}/`)
  expect(projet.priorite, 'priorité Haute').toBe(3)
  expect(projet.echeance, 'échéance dans 6 semaines').toBe('2027-01-05')
})

etape('P138.3', ['TCH138', 'TCH92', 'TCH87', 'TCH60', 'TCH61', 'TCH53'], async (f) => {
  const instant = scenario(['--jour', J24, '--heure', '08:30'], `${J24} 08:30`)
  const p = await ouvrir(f, { instant })
  // « Stand partenaire » et ses 2 tâches, posés par les vraies routes
  const cree = await p.request.post(`${API}/projets/`, { data: { nom: 'Stand partenaire', priorite: 3 }, headers: { 'Idempotency-Key': `tch-p1383-${Date.now()}` } })
  expect(cree.ok(), `créer le projet → ${cree.status()}`).toBeTruthy()
  const projet = (await cree.json()).projet ?? (await cree.json())
  const lignes = ['Réserver le camion du stand', 'Imprimer les badges partenaires']
    .map((titre, index) => ({ index, client_id: `p1383-${Date.now()}-${index}`, titre, projet_id: projet.id }))
  const res = await p.request.post(`${API}/saisie-rapide/`, { data: { lignes, apercu: false }, headers: { 'Idempotency-Key': `tch-p1383-t-${Date.now()}` } })
  expect(res.ok(), `créer les tâches → ${res.status()}`).toBeTruthy()

  await aller(p, `/taches/projets/${projet.id}`, 'projet')
  await p.getByRole('button', { name: "Plus d'actions" }).click()
  await p.getByRole('menuitem', { name: 'Supprimer le projet…' }).click()
  // Oracle : dialogue « … et ses N tâches ? »
  const dialogue = feuille(p, 'Supprimer le projet')
  await expect(dialogue).toContainText('Supprimer « Stand partenaire » et ses 2 tâches ?')
  await dialogue.getByRole('button', { name: 'Supprimer', exact: true }).click()
  await expect(dialogue).toHaveCount(0)
  await expect.poll(async () => (await p.request.get(`${API}/projets/${projet.id}/`)).status(), 'projet supprimé').toBe(404)
  // Oracle : Supprimées récemment → une ligne
  await aller(p, '/taches/supprimees', 'supprimees')
  const supprimees = p.getByRole('region', { name: 'Supprimées récemment' })
  await expect(supprimees.getByRole('button', { name: /^Restaurer « / })).toHaveCount(1)
  await expect(supprimees).toContainText('Stand partenaire')
  await capturer(p, 'supprimees')
  // Oracle : Restaurer → projet et tâches revenus
  await supprimees.getByRole('button', { name: 'Restaurer « Stand partenaire »' }).click()
  await expect(toast(p)).toContainText('« Stand partenaire » restauré')
  const revenu = await p.request.get(`${API}/projets/${projet.id}/`)
  expect(revenu.status(), 'le projet est revenu').toBe(200)
  for (const { titre } of lignes) expect((await tacheNommee(p, titre)).projet?.id).toBe(projet.id)
})

etape('P138.4', ['TCH138', 'TCH65', 'TCH93', 'TCH106'], async (f) => {
  // Plan TCH138 étape 4 (corrigé) : semis par défaut (`--jour 2026-11-24`), horloge du serveur ET du navigateur au
  // ven. 20 à 17:40 (semer au 20 décalait toute l'histoire de 4 jours : « 9 tâches en 2 jours »)
  const instant = scenario(['--jour', J24], '2026-11-20 17:40')
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/revue', 'revue')
  await expect(p.locator('.ep-constat').first()).toBeVisible()
  await capturer(p, 'revue')
  // Oracle (plan corrigé) : Revue « 21 tâches en 4 jours » — mots de textes.md §4.5
  await expect(p.locator('.ep-constat').first()).toContainText(/\b21 tâches en 4 jours/)
  // décisions : une carte par projet actif, « Garder » chacune
  for (let n = 0; n < 10; n += 1) {
    const fin = p.locator('.ep-revue-fin')
    if (await fin.isVisible()) break
    const carte = p.locator('section.ep-carte-revue')
    await expect(carte).toBeVisible()
    const nom = await carte.getAttribute('aria-label')
    await carte.getByRole('button', { name: 'Garder', exact: true }).click()
    await expect(p.locator('.tch .annonce')).toContainText(`« ${nom} » : décision enregistrée`)
  }
  // Oracle : fin → Planifier ma semaine
  await p.locator('.ep-revue-fin').getByRole('button', { name: 'Planifier ma semaine' }).click()
  await expect(p).toHaveURL(/\/taches\/agenda\?.*placer=1/)
  await expect(p.locator('h1.entete-titre')).toHaveText('Planifier ma semaine')
})

// =====================================================================================================================
// TCH139 — Parcours « agenda » (SCENARIO.md « La semaine du 23 au 29 » ; parcours 16-17)
// =====================================================================================================================

const AGENDA = ['--jour', J24, '--heure', '09:41', '--rendez-vous']
const volet = (p) => p.getByRole('complementary', { name: 'À placer' })

etape('P139.1', ['TCH139', 'TCH59', 'TCH104'], async (f) => {
  const instant = scenario(AGENDA, `${J24} 09:41`, { lecture: true })
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/agenda', 'agenda')
  await capturer(p, 'agenda-jour')
  await p.getByRole('radio', { name: 'Mois', exact: true }).click()
  await expect(p.getByRole('radio', { name: 'Mois', exact: true })).toHaveAttribute('aria-checked', 'true')
  await capturer(p, 'agenda-mois')
  await p.getByRole('radio', { name: 'Semaine', exact: true }).click()
  const jeudi = p.locator('.ag-sj').filter({ has: p.locator('.ag-sj-date b', { hasText: /^26$/ }) })
  await expect(jeudi).toBeVisible()
  await capturer(p, 'agenda-semaine')
  // Oracle : Agenda Semaine → jeu. 26 « 2 tâches · 2 h pour 4 h »
  await expect(jeudi).toContainText('2 tâches · 2 h pour 4 h')
})

etape('P139.2', ['TCH139', 'TCH106'], async (f) => {
  const instant = scenario(AGENDA, `${J24} 09:41`)
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/agenda?placer=1', 'agenda')
  await expect(p.locator('h1.entete-titre')).toHaveText('Planifier ma semaine')
  await capturer(p, 'planifier-semaine')
  await volet(p).getByRole('button', { name: new RegExp(echapper(T.demo)) }).click()
  const jours = p.getByRole('list', { name: 'Jours de la semaine' })
  await jours.getByRole('button', { name: new RegExp(`^jeu\\.? 26 · .* · placer ${echapper(T.demo)}$`) }).click()
  await expect(toast(p)).toContainText('Placée')
  // Oracle : « 3 · 4 h pour 4 h » (textes.md §2.8 : « {n} tâches · {h} pour {cap} »)
  await expect(jours.getByRole('button', { name: /^jeu\.? 26 · / })).toHaveAccessibleName(/^jeu\.? 26 · 3 tâches · 4 h pour 4 h/)
  expect((await tacheNommee(p, T.demo)).jour_prevu).toBe('2026-11-26')
})

etape('P139.3', ['TCH139', 'TCH105'], async (f) => {
  const instant = scenario(AGENDA, `${J24} 09:41`)
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/agenda', 'agenda')
  // Oracle : placer 4 tâches à une heure (toucher puis créneau) → 4 blocs
  // 4 tâches du volet « À placer » (SCENARIO §4 : Aujourd'hui 3 · À revoir 2 · Mes projets 7) : les 3 d'Aujourd'hui,
  // puis la première qui reste au volet, quelle qu'elle soit
  const poses = [[T.stand, '11:00'], [T.fiche, '13:00'], [T.contrat, '15:00'], [null, '16:00']]
  for (const pose of poses) {
    const [titre, heure] = pose
    if (titre === null) {
      const reste = volet(p).locator('button.ag-lp')
      await expect(reste.first(), 'une 4e tâche à placer dans le volet').toBeVisible()
      pose[0] = (await reste.first().locator('.t').evaluate((el) => el.childNodes[0].textContent)).trim()
      await reste.first().click()
    } else {
      await volet(p).getByRole('button', { name: new RegExp(echapper(titre)) }).click()
    }
    await p.getByRole('button', { name: `Placer à ${heure}`, exact: true }).click()
    await expect(toast(p)).toContainText(`Placée à ${heure}`)
  }
  for (const [titre, heure] of poses) {
    await expect(p.getByRole('checkbox', { name: `Fait : ${titre}` })).toBeVisible()
    expect(String((await tacheNommee(p, titre)).heure_debut).slice(0, 5), `« ${titre} » à ${heure}`).toBe(heure)
  }
})

etape('P139.4', ['TCH139', 'TCH55', 'TCH59', 'TCH104'], async (f) => {
  const instant = scenario(AGENDA, `${J24} 09:41`, { lecture: true })
  // la visite vient de l'ERP : le harnais la pose par la porte des visites (SCENARIO §0 errata 7), avant l'écran
  const posee = await poserVisiteTemara(J24)
  expect(posee.erreurs, 'visite de Témara planifiée').toEqual({})
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/agenda', 'agenda')
  // Oracle : visite de Témara en Toute la journée le 24 — SCENARIO §0 errata 7 : la bande ne porte QUE la visite
  // (les relances sont une ligne de Prévu)
  const bande = p.getByRole('group', { name: 'Toute la journée' }).first()
  await expect(bande).toContainText(T.visite)
  await expect(bande).not.toContainText('relances')
})

etape('P139.5', ['TCH139', 'TCH122', 'TCH121', 'TCH104'], async (f) => {
  const instant = scenario(AGENDA, `${J24} 09:41`, { lecture: true })
  const p = await ouvrir(f, { instant })
  // Oracle : rendez-vous externe affiché (agenda.ics : 24/11 14:30–15:00, 30 min)…
  await aller(p, '/taches/agenda', 'agenda')
  await expect(p.getByRole('button', { name: /^Rendez-vous de démonstration · 14:30.15:00 · Agenda de démonstration/ })).toBeVisible()
  // …temps disponible du jour diminué de sa durée (4 h − 30 min)
  const journee = await lire(p, 'aujourdhui/')
  expect(journee.progression.rendez_vous_minutes, 'durée du rendez-vous').toBe(30)
  expect(journee.progression.disponible_minutes).toBe(journee.progression.capacite_minutes - 30)
  await aujourdhui(p)
  await progression(p).click()
  await expect(p.getByRole('group', { name: 'Détail de la journée' })).toContainText('Temps libre : 3 h 30 (4 h moins 30 min de rendez-vous)')
})

etape('P139.6', ['TCH139', 'TCH108', 'TCH121'], async (f) => {
  const instant = scenario(AGENDA, `${J24} 09:41`)
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/reglages/avance', 'reglages')
  await capturer(p, 'reglages')
  const champ = p.getByRole('textbox', { name: /^Adresse de l'agenda/ })
  const ajouter = async (url) => { await champ.fill(url); await p.getByRole('button', { name: 'Ajouter', exact: true }).click() }
  const erreur = p.locator('p.es-erreur[role="alert"]')
  const nb = async () => liste(await lire(p, 'agendas-externes/')).length
  expect(await nb(), "l'agenda de démonstration du semis").toBe(1)
  // Oracle : adresse `http://…` → « Adresse https publique attendue. »
  f.suivi.attendre(/\/taches\/agendas-externes\/$/, 400)
  await ajouter('http://agenda.example.com/mon-agenda.ics')
  await expect(erreur.filter({ hasText: 'Adresse https publique attendue.' })).toBeVisible()
  // Oracle : adresse vers 127.0.0.1 → refus
  await ajouter('https://127.0.0.1/mon-agenda.ics')
  await expect(erreur.filter({ hasText: /\S/ })).toBeVisible()
  expect(await nb(), 'aucun agenda créé').toBe(1)
  // Oracle : 4e adresse → refus (2 agendas de plus posés en base : leur ajout par l'écran irait sur Internet)
  await py(`${DEMO}from apps.taches.models.agenda import AgendaExterne
for n in (2, 3):
    AgendaExterne.objects.get_or_create(company_id=soc, proprietaire=u, url=f'https://agenda-demo.example.invalid/{n}.ics', defaults={'libelle': f'Agenda {n}'})
sortie(AgendaExterne.objects.filter(company_id=soc, proprietaire=u).count())`)
  await p.reload()
  expect(await nb()).toBe(3)
  // adresse https PUBLIQUE par son IP (la machine d'essai ne résout aucun nom : un nom serait refusé avant le plafond)
  await ajouter('https://1.1.1.1/quatrieme.ics')
  await expect(erreur.filter({ hasText: '3 agendas au plus.' })).toBeVisible()
  expect(await nb(), 'toujours 3 agendas').toBe(3)
})

etape('P139.7', ['TCH139', 'TCH105'], async (f) => {
  const instant = scenario(AGENDA, `${J24} 09:41`)
  // Navigateur « périmé » : Africa/Casablanca encore à +1 dans ce Chromium. Même geste qu'en P139.3.
  const p = await ouvrir(f, { instant, timezoneId: 'Africa/Casablanca' })
  await aller(p, '/taches/agenda', 'agenda')
  await volet(p).getByRole('button', { name: new RegExp(echapper(T.stand)) }).click()
  await p.getByRole('button', { name: 'Placer à 10:00', exact: true }).click()
  await expect(toast(p)).toContainText('Placée à 10:00')
  // Oracle (orchestrateur) : l'heure enregistrée côté serveur reste 10:00 heure du Maroc.
  const lue = await tacheNommee(p, T.stand)
  expect(lue.jour_prevu).toBe(J24)
  expect(String(lue.heure_debut).slice(0, 5)).toBe('10:00')
})

// =====================================================================================================================
// TCH140 — Parcours « rythme » (SCENARIO.md « Les jours passés »)
// =====================================================================================================================

etape('P140.1', ['TCH140', 'TCH66', 'TCH107'], async (f) => {
  const instant = scenario(MATIN, `${J24} 08:30`, { lecture: true })
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/rythme', 'rythme')
  // Oracle : « Les 10 derniers jours travaillés » 5, 5, 4, 6, 3, 5, 4, 7, 5, 4 ; « 6 jours sur 10 »
  await expect(p.getByRole('heading', { name: /^Les 10 derniers jours travaillés/ })).toBeVisible()
  await expect(p.getByRole('img', { name: /^Tâches faites, jour par jour travaillé : 5, 5, 4, 6, 3, 5, 4, 7, 5, 4\./ })).toBeVisible()
  await expect(p.locator('.ep-graph-legende')).toContainText('6 jours sur 10')
  // Oracle : proposition « … On passe à 6 ? » avec « Monter à 6 » · « Pas maintenant »
  await expect(p.getByText('Ces 10 jours travaillés, tu as fait au moins 5 tâches 6 fois. On passe à 6 ?')).toBeVisible()
  await expect(p.getByRole('button', { name: 'Monter à 6', exact: true })).toBeVisible()
  await expect(p.getByRole('button', { name: 'Pas maintenant', exact: true })).toBeVisible()
  await capturer(p, 'mon-rythme')
  // capture de relecture seulement (aucun oracle) : la Recherche
  await aller(p, '/taches/recherche', 'recherche')
  await p.getByRole('searchbox', { name: 'Chercher dans mes tâches' }).fill('devis')
  await expect(p.getByText(T.devis).first()).toBeVisible()
  await capturer(p, 'recherche')
})

etape('P140.2', ['TCH140', 'TCH67', 'TCH77'], async (f) => {
  const instant = scenario(MATIN, `${J24} 08:30`)
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/rythme', 'rythme')
  await p.getByRole('button', { name: 'Monter à 6', exact: true }).click()
  await expect.poll(async () => (await lire(p, 'rythme/')).objectif?.nb).toBe(6)
  // Oracle : Monter à 6 → Aujourd'hui « 0 sur 6 »
  await aujourdhui(p)
  await expect(progression(p)).toContainText('0 sur 6')
})

/** Choisit un mode sur Mon rythme (une confirmation, si l'écran en demande une, est acceptée). */
async function choisirMode(p, nom, cle) {
  await aller(p, '/taches/rythme', 'rythme')
  await p.getByRole('radiogroup', { name: 'Mode du rythme' }).getByRole('radio', { name: new RegExp(`^${nom}`) }).click()
  await expect.poll(async () => (await lire(p, 'rythme/')).mode).toBe(cle)
}

etape('P140.3', ['TCH140', 'TCH66', 'TCH107', 'TCH77'], async (f) => {
  const instant = scenario(MATIN, `${J24} 08:30`)
  const p = await ouvrir(f, { instant })
  // Oracle : Garder ce rythme → zone affichée
  await choisirMode(p, 'Garder ce rythme', 'tenir')
  await aujourdhui(p)
  await expect(progression(p)).toContainText(/ton rythme : \d+ à \d+/)
  // Oracle : Sans objectif → « N faites » (textes.md §2.2 : « 1 faite », accord au nombre)
  await choisirMode(p, 'Sans objectif', 'libre')
  await aujourdhui(p)
  await expect(progression(p).locator('.progression-compte')).toHaveText(/^\d+ faites?$/)
})

etape('P140.4', ['TCH140', 'TCH69', 'TCH107'], async (f) => {
  const instant = scenario(MATIN, `${J24} 08:30`)
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/rythme', 'rythme')
  await expect(p.getByText(/On passe à 6 \?/)).toBeVisible()
  // Oracle : couper « Comprendre mon rythme » → constats et propositions disparus (`GET rythme/` sans profil)
  await p.locator('button.replie', { hasText: 'Comprendre mon rythme' }).click() // l'interrupteur vit dans un repli
  await p.getByRole('switch', { name: 'Comprendre mon rythme' }).click()
  const confirmer = p.getByRole('dialog').getByRole('button', { name: /^(Éteindre|Couper|Confirmer)/ })
  if (await confirmer.count()) await confirmer.click()
  await expect.poll(async () => (await lire(p, 'reglages/')).comprendre_mon_rythme).toBe(false)
  const rythme = await lire(p, 'rythme/')
  expect(rythme.proposition ?? null, 'plus de proposition').toBeNull()
  expect(rythme.constats ?? [], 'plus de constat').toHaveLength(0)
  await p.reload()
  await expect(p.getByText(/On passe à 6 \?/)).toHaveCount(0)
  await expect(p.locator('ul.ep-remarque li')).toHaveCount(0)
})

// =====================================================================================================================
// TCH144 — Parcours « vie privée, deux appareils, hors ligne, clavier, activation » (parcours 18, 22 ; inv. 28)
// =====================================================================================================================

const VIE = ['--jour', J24, '--heure', '10:45']

etape('P144.1', ['TCH144', 'TCH84', 'TCH49'], async (f) => {
  const instant = scenario(VIE, `${J24} 10:45`)
  const a = await ouvrir(f, { instant })
  const b = await ouvrir(f, { instant, vue: 'bureau' })
  const id = await idTache(a, T.tva)
  for (const p of [a, b]) await aller(p, `/taches/aujourdhui?tache=${id}`, 'aujourdhui')
  const titreDe = (p) => p.locator(`[data-fiche="${id}"]`).getByRole('textbox', { name: 'Titre' })
  for (const p of [a, b]) await expect(titreDe(p)).toHaveValue(T.tva)
  await capturer(a, 'fiche')
  // l'autre appareil (bureau) écrit d'abord
  await titreDe(b).fill('Préparer la déclaration de TVA de novembre')
  await titreDe(b).press('Enter')
  await expect.poll(async () => (await lireTache(b, id)).titre).toBe('Préparer la déclaration de TVA de novembre')
  // l'iPhone écrit ensuite sur la version qu'il avait lue : ce 409 est le SUJET de l'étape (seul excusé)
  f.suivi.attendre(new RegExp(`/taches/taches/${id}/$`), 409)
  const mienne = 'Préparer la TVA avec le comptable'
  await titreDe(a).fill(mienne)
  await titreDe(a).press('Enter')
  // Oracle : « Modifiée sur ton autre appareil à … · Garder la mienne · Prendre l'autre », saisie gardée
  const bandeau = a.getByRole('group', { name: 'Conflit entre appareils' })
  await expect(bandeau).toContainText(/Modifiée sur ton autre appareil à \d{2}:\d{2}/)
  await expect(bandeau.getByRole('button', { name: 'Garder la mienne' })).toBeVisible()
  await expect(bandeau.getByRole('button', { name: "Prendre l'autre" })).toBeVisible()
  await expect(titreDe(a)).toHaveValue(mienne)
  await bandeau.getByRole('button', { name: 'Garder la mienne' }).click()
  await expect.poll(async () => (await lireTache(a, id)).titre).toBe(mienne)
})

etape('P144.2', ['TCH144', 'TCH100'], async (f) => {
  const instant = scenario(VIE, `${J24} 10:45`)
  const p = await ouvrir(f, { instant })
  await aujourdhui(p)
  const ajoutee = 'Rappeler le transporteur des panneaux'
  // Hors ligne : les échecs réseau de la page sont INJECTÉS par l'étape (seuls excusés)
  f.suivi.attendre(/./, 'reseau')
  await p.context().setOffline(true)
  await expect(p.getByText(/^Hors ligne/).first()).toBeVisible()
  await capturer(p, 'hors-ligne')
  // ajouter
  await p.getByRole('button', { name: 'Ajouter une tâche', exact: true }).first().click()
  await champSaisie(p).fill(ajoutee)
  await champSaisie(p).press('Enter')
  await expect(saisie(p)).toHaveCount(0)
  // cocher
  await ligneNommee(p, T.stand).getByRole('checkbox', { name: `Marquer « ${T.stand} » comme faite` }).click()
  // reporter (balayage gauche, parcours 4)
  await balayer(p, ligneNommee(p, T.fiche), -1)
  expect(await p.evaluate(() => navigator.onLine), 'toujours hors ligne avant le retour du réseau').toBe(false)
  await expect(p.getByText(/^En attente d'envoi \(\d+\)$/)).toBeVisible()
  // Oracle : puis réseau → rejoués, une seule tâche ajoutée
  await p.context().setOffline(false)
  await expect(p.getByText(/^En attente d'envoi/)).toHaveCount(0, { timeout: 60_000 })
  await expect.poll(async () => liste(await lire(p, 'taches/', { q: ajoutee, inclure_faites: 'true' })).filter((t) => t.titre === ajoutee).length).toBe(1)
  expect((await tacheNommee(p, T.stand)).statut).toBe('fait')
  expect((await tacheNommee(p, T.fiche)).jour_prevu).toBe('2026-11-25')
})

etape('P144.3', ['TCH144', 'TCH119'], async (f) => {
  const instant = scenario(VIE, `${J24} 10:45`)
  const p = await ouvrir(f, { instant, vue: 'bureau' })
  await aller(p, '/taches/projets', 'projets')
  let touches = 0
  const touche = async (k) => { touches += 1; await p.keyboard.press(k) }
  const ligneFocus = () => p.evaluate(() => document.activeElement?.closest?.('[data-ligne]')?.getAttribute('data-ligne') ?? '')
  // `g j` 2
  await touche('g'); await touche('j')
  await expect(p).toHaveURL(/\/taches\/aujourdhui/)
  await expect(progression(p)).toBeVisible()
  // `n` + 3 Entrée + Échap 5 (le texte tapé ne compte pas)
  const ajouts = ['Clavier un acheter du câble', 'Clavier deux appeler le bureau', 'Clavier trois classer les devis']
  // Comme la personne : si la feuille s'est refermée après un ajout, elle retape `n` (compté).
  for (const titre of ajouts) {
    if (!(await saisie(p).isVisible())) await touche('n')
    await expect(champSaisie(p)).toBeFocused()
    await p.keyboard.type(titre)
    await touche('Enter')
    await expect.poll(async () => liste(await lire(p, 'taches/', { q: titre })).filter((t) => t.titre === titre).length,
      `« ${titre} » ajoutée`).toBe(1)
  }
  if (await saisie(p).isVisible()) await touche('Escape')
  await expect(saisie(p)).toHaveCount(0)
  // 2 × `j` Espace 4
  const cochees = []
  for (let n = 0; n < 2; n += 1) {
    await touche('j'); const cle = await ligneFocus(); cochees.push(cle); await touche(' ')
  }
  // 2 × `j d` Entrée 6
  const reportees = []
  for (let n = 0; n < 2; n += 1) {
    await touche('j'); reportees.push(await ligneFocus()); await touche('d'); await touche('Enter')
  }
  // 2 × `j m` Entrée 6
  const deplacees = []
  for (let n = 0; n < 2; n += 1) {
    await touche('j')
    const cle = await ligneFocus()
    const avant = /^tache:\d+$/.test(cle) ? (await lireTache(p, Number(cle.split(':')[1]))).projet?.id ?? null : null
    deplacees.push({ cle, avant })
    await touche('m'); await touche('Enter')
  }
  // Oracle : 3 ajouts, 2 cochées, 2 reportées, 2 déplacées en ≈ 27 touches (parcours 18 ; 4 de palette hors F2)
  expect(touches, 'touches comptées').toBeLessThanOrEqual(27)
  const id = (cle) => Number(String(cle).split(':')[1])
  for (const cle of cochees) {
    expect(cle, 'une ligne de tâche focalisée').toMatch(/^tache:\d+$/)
    expect((await lireTache(p, id(cle))).statut, `${cle} cochée`).toBe('fait')
  }
  for (const cle of reportees) {
    expect(cle).toMatch(/^tache:\d+$/)
    expect((await lireTache(p, id(cle))).jour_prevu > J24, `${cle} reportée`).toBe(true)
  }
  for (const { cle, avant } of deplacees) {
    expect(cle).toMatch(/^tache:\d+$/)
    expect((await lireTache(p, id(cle))).projet?.id ?? null, `${cle} déplacée dans un autre projet`).not.toBe(avant)
  }
})

etape('P144.4', ['TCH144', 'TCH108', 'TCH74'], async (f) => {
  const instant = scenario(VIE, `${J24} 10:45`)
  const p = await ouvrir(f, { instant })
  await aller(p, '/taches/reglages/donnees', 'reglages')
  await capturer(p, 'mes-donnees')
  // Oracle : Exporter (JSON des 21 modèles)
  const [telechargement] = await Promise.all([p.waitForEvent('download'), p.getByRole('button', { name: /^Exporter mes données/ }).click()])
  const exporte = JSON.parse(readFileSync(await telechargement.path(), 'utf8'))
  expect(Object.keys(exporte).filter((k) => k !== 'exporte_le'), 'les modèles exportés').toHaveLength(21)
  // Oracle : Tout effacer sans EFFACER → erreur sous le champ
  await p.getByRole('button', { name: 'Tout effacer', exact: true }).click()
  const dialogue = feuille(p, 'Tout effacer ?')
  f.suivi.attendre(/\/taches\/tout-effacer\/$/, 400)
  await dialogue.getByRole('button', { name: 'Tout effacer', exact: true }).click()
  await expect(dialogue.getByRole('alert')).toContainText('Tape EFFACER pour confirmer.')
  await expect(dialogue.getByRole('textbox', { name: 'Confirmation' })).toHaveAttribute('aria-invalid', 'true')
  expect(liste(await lire(p, 'projets/')).length, 'rien effacé').toBe(5)
  // Oracle : avec → 0 ligne
  await dialogue.getByRole('textbox', { name: 'Confirmation' }).fill('EFFACER')
  const reponse = p.waitForResponse((r) => r.url().endsWith('/taches/tout-effacer/') && r.request().method() === 'POST')
  await dialogue.getByRole('button', { name: 'Tout effacer', exact: true }).click()
  expect((await reponse).ok()).toBeTruthy()
  const lignes = await py(`${DEMO}from django.apps import apps
n = {}
for m in apps.get_app_config('taches').get_models():
    champs = {c.name for c in m._meta.get_fields()}
    if 'proprietaire' in champs:
        mgr = getattr(m, 'all_objects', m.objects)
        n[m.__name__] = mgr.filter(proprietaire=u).count()
sortie(n)`)
  expect(Object.fromEntries(Object.entries(lignes).filter(([, v]) => v > 0)), 'aucune ligne du compte').toEqual({})
})

etape('P144.5', ['TCH144', 'TCH74', 'TCH154'], async (f) => {
  const instant = scenario(VIE, `${J24} 10:45`)
  const email = `lead-efface-${Date.now()}@accept.test`
  const lien = await py(`${DEMO}from apps.crm.models import Lead
from apps.taches.choix import Source
from apps.taches.services.creation import creer_taches
from django.contrib.contenttypes.models import ContentType
from apps.taches.models.taches import Tache
lead = Lead.objects.create(company_id=soc, nom='Lead Acceptation', email='${email}')
r = creer_taches(u, [{'titre': 'Rappeler le lead de la foire'}], source=Source.MANUEL, porte='ecran')
# Lien posé directement (donnée d'essai) : le rôle de test de demo_taches ne lit pas les leads, la route le refuserait
Tache.objects.filter(pk=r.creees[0].pk).update(content_type=ContentType.objects.get_by_natural_key('crm', 'lead'),
    object_id=lead.pk, lien_libelle='Lead Acceptation', lien_etat='')
sortie({'lead': lead.pk, 'tache': r.creees[0].pk})`)
  // Oracle : effacer un lead lié (porte 09-08 de `crm`) → « Lead effacé »
  const effaces = await py(`${DEMO}from authentication.models import Company
from apps.crm.dsr_provider import erase_crm
sortie(erase_crm(Company.objects.get(pk=soc), '${email}'))`)
  expect(effaces, 'le lead est anonymisé par la porte de crm').toBeGreaterThanOrEqual(1)
  const p = await ouvrir(f, { instant })
  await aller(p, `/taches/aujourdhui?tache=${lien.tache}`, 'aujourdhui')
  const fiche = p.locator(`[data-fiche="${lien.tache}"]`)
  await fiche.getByRole('button', { name: 'Plus', exact: true }).click() // « Lié à » vit dans Fiche → Plus (TCH85)
  await expect(fiche).toContainText('Lead effacé')
  await capturer(p, 'fiche-plus')
  const lue = await lireTache(p, lien.tache)
  expect(JSON.stringify(lue)).not.toContain('Lead Acceptation')
})

etape('P144.6', ['TCH144', 'TCH130', 'TCH131'], async (f) => {
  scenario(VIE, 'reel')
  const roles = await py(`from apps.roles.models import Role
r = {x.nom: x.pk for x in Role.objects.filter(company_id=1, nom__in=['Administrateur', 'Directeur', 'Commercial'])}
for nom, cle in (('acc_tch_admin', 'Administrateur'), ('acc_tch_dir', 'Directeur'), ('acc_tch_com', 'Commercial')):
    if cle in r:
        compte(nom, role=r[cle])
from apps.crm.models import Client
c = Client.objects.filter(company_id=1).order_by('pk').first()
sortie({'roles': r, 'client': c.pk if c else None})`)
  expect(Object.keys(roles.roles).sort(), 'rôles Administrateur, Directeur, Commercial de la société 1').toEqual(['Administrateur', 'Commercial', 'Directeur'])
  const ONGLETS = ['/taches/aujourdhui', '/taches/a-trier', '/taches/projets', '/taches/agenda']
  const MDP = 'Accept@2026!'
  // Oracle : compte Administrateur → 4 onglets
  const admin = await ouvrir(f, { vue: 'bureau', username: 'acc_tch_admin', password: MDP })
  await admin.goto('/taches/aujourdhui')
  for (const href of ONGLETS) await expect(admin.locator(`a[href="${href}"]`).first()).toBeVisible()
  expect((await admin.request.get(`${API}/aujourdhui/`)).status()).toBe(200)
  // Oracle : comptes Directeur, Commercial → aucun onglet, API 403
  for (const nom of ['acc_tch_dir', 'acc_tch_com']) {
    const p = await ouvrir(f, { vue: 'bureau', username: nom, password: MDP })
    await p.goto('/apps')
    await expect(p.getByRole('heading', { name: 'Mes applications' })).toBeVisible()
    for (const href of ONGLETS) await expect(p.locator(`a[href="${href}"]`), `${nom} : ${href}`).toHaveCount(0)
    f.suivi.attendre(/\/api\/django\/taches\/aujourdhui\/$/, 403)
    expect((await p.request.get(`${API}/aujourdhui/`)).status(), `${nom} : API`).toBe(403)
  }
  // Oracle : compte portail → aucun onglet, API 403
  expect(roles.client, 'un client de la société 1 pour le compte portail').toBeTruthy()
  const api = await pwRequest.newContext({ baseURL: f.testInfo.project.use.baseURL })
  await connecter(api, 'acc_tch_admin', MDP)
  const comptes = liste(await (await api.get('/api/django/portail/comptes-portail/')).json())
  const compte = comptes.find((c) => c.client === roles.client)
    ?? await (await api.post('/api/django/portail/comptes-portail/', { data: { client: roles.client } })).json()
  const prov = await (await api.post(`/api/django/portail/comptes-portail/${compte.id}/provisionner-acces/`, { data: {} })).json()
  // Compte portail : mot de passe d'essai posé en base, sans « à changer » (le throttle de connexion est de 5/min)
  await py(`u = U.objects.get(username=${JSON.stringify(prov.username)}); u.set_password('${MDP}'); u.must_change_password = False; u.save(); sortie(1)`)
  const portail = await pwRequest.newContext({ baseURL: f.testInfo.project.use.baseURL })
  await connecter(portail, prov.username, MDP)
  expect((await portail.get(`${API}/aujourdhui/`)).status(), 'portail : API').toBe(403)
  await portail.dispose()
  await api.dispose()
  salir()
})

// Pile laissée à l'heure réelle après le dernier parcours (le projet `setup` de la prochaine passe en a besoin).
test.afterAll(() => { try { pile('horloge', 'reel') } catch { /* la pile a pu être arrêtée par l'orchestrateur */ } })
