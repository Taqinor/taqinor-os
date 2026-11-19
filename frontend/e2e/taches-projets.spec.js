// TCH134 (1/2) — Tâches, bout en bout : PROJETS, REVUE → PLANIFIER MA SEMAINE, AGENDA, RÉGLAGES sur la vraie pile.
//
// Parcours joués ici (spec-7 « Parcours chiffrés » 10, 16, 17, 20 ; TCH138-TCH140 en acceptation pour le reste) :
//   Nouveau projet → Planifier le projet (7 gestes) · Revue → Planifier ma semaine · placer à une heure ·
//   Réglages (Vie privée, Avancé : adresse refusée, Mes données : Exporter, Tout effacer).
// NON joués ici (horloge, push, réseau sortant) : revue du vendredi à 17 h 40, rappel, 4e agenda externe
// (il exigerait trois créations qui vont chercher l'agenda sur Internet) — acceptation en direct (TCH138/TCH139).
//
// Chaque test repart d'un compte effacé et crée ses propres données (titres uniques) : rejouable, indépendant de
// l'ordre.
import { readFileSync } from 'node:fs'
import { test, expect } from '@playwright/test'
import { isoDansJours } from './helpers'
import {
  API, chercherTaches, creerProjet, creerTaches, jourServeur, lireTache, ouvrirEcran, reinitialiser, titreUnique, toast,
  annonce,
} from './taches-aides'

const echapper = (texte) => texte.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

test.describe('Tâches — projets', () => {
  test('créer et planifier un projet : fini quand, 6 semaines, Haute, 2 actions', async ({ page }) => {
    await reinitialiser(page)
    const nom = titreUnique('Stand partenaire')
    const objectif = 'le stand est monté et validé'
    const actions = [titreUnique('Réserver le camion'), titreUnique('Imprimer les badges')]
    await ouvrirEcran(page, '/taches/projets', 'projets')
    await expect(page.getByText('Aucun projet', { exact: true })).toBeVisible()

    // Projets → Nouveau projet → Créer : on arrive sur le projet, le rituel s'ouvre
    await page.getByRole('button', { name: 'Nouveau projet', exact: true }).click()
    const feuille = page.getByRole('dialog', { name: 'Nouveau projet' })
    await feuille.getByLabel('Nom du projet').fill(nom)
    await feuille.getByRole('button', { name: 'Créer', exact: true }).click()
    await expect(page).toHaveURL(/\/taches\/projets\/\d+\?planifier=1/)
    const idProjet = Number(new URL(page.url()).pathname.split('/').pop())
    const rituel = page.getByRole('region', { name: 'Planifier le projet' })
    await expect(rituel).toContainText('pas 1 sur 2')

    // pas 1 : fini quand…, échéance (6 semaines), priorité Haute
    await rituel.getByLabel('Ce sera fini quand…').fill(objectif)
    await rituel.getByRole('radio', { name: '6 semaines', exact: true }).click()
    await expect(rituel.getByRole('radio', { name: '6 semaines', exact: true })).toBeChecked()
    await rituel.getByRole('radio', { name: /^Haute/ }).click()
    await expect(rituel.getByRole('radio', { name: /^Haute/ })).toBeChecked()
    await rituel.getByRole('button', { name: 'Suivant', exact: true }).click()
    await expect(rituel).toContainText('pas 2 sur 2')

    // pas 2 : deux premières actions, la première pour aujourd'hui
    for (const titre of actions) {
      await rituel.getByLabel('Nouvelle action').fill(titre)
      await rituel.getByRole('button', { name: 'Ajouter', exact: true }).click()
      await expect(rituel.getByText(titre, { exact: true })).toBeVisible()
    }
    await rituel.getByRole('radiogroup', { name: `Quand : ${actions[0]}` }).getByRole('radio', { name: "Aujourd'hui" }).click()

    await rituel.getByRole('button', { name: 'Terminer', exact: true }).click()
    await expect(page.getByRole('region', { name: 'Planifier le projet' })).toHaveCount(0)
    await expect(page).not.toHaveURL(/planifier=1/)
    await expect(annonce(page)).toContainText('Projet planifié')
    for (const titre of actions) await expect(page.getByText(titre, { exact: true })).toBeVisible()

    // le serveur : priorité Haute (3), échéance dans 6 semaines, « fini quand » gardé, 2 tâches (la 1re pour aujourd'hui)
    const projet = await (await page.request.get(`${API}/projets/${idProjet}/`)).json()
    expect(projet.priorite).toBe(3)
    expect(projet.echeance).toBe(isoDansJours(42))
    expect(projet.objectif).toContain(objectif)
    const jour = await jourServeur(page)
    const [premiere] = await chercherTaches(page, actions[0])
    const [seconde] = await chercherTaches(page, actions[1])
    expect((await lireTache(page, premiere.id)).jour_prevu).toBe(jour)
    expect((await lireTache(page, seconde.id)).jour_prevu).toBeNull()
  })

  test('Revue de la semaine → Planifier ma semaine : une tâche posée sur un jour', async ({ page }) => {
    await reinitialiser(page)
    const projet = await creerProjet(page, titreUnique('Salon solaire'), 2)
    const titres = [titreUnique('Préparer la démo'), titreUnique('Commander les kakémonos'), titreUnique('Réserver lhôtel')]
    const taches = await creerTaches(page, titres, { projet_id: projet.id })

    // Revue : une carte par projet, on décide « Garder », puis le chemin mène à Planifier ma semaine
    await ouvrirEcran(page, '/taches/revue', 'revue')
    const carte = page.getByRole('region', { name: projet.nom })
    await expect(carte).toBeVisible()
    await page.getByLabel('Intention de la semaine (facultatif)').fill('Tout commander') // R2-068 : une seule intention, en tête
    await carte.getByRole('button', { name: 'Suivant →', exact: true }).click() // « Garder » est d'office coché
    await expect(annonce(page)).toContainText(`« ${projet.nom} » : décision enregistrée`)
    await page.getByRole('button', { name: 'Planifier ma semaine', exact: true }).click()

    await expect(page).toHaveURL(/\/taches\/agenda\?.*placer=1/)
    await expect(page.locator('h1.entete-titre')).toHaveText('Planifier ma semaine')
    const volet = page.getByRole('complementary', { name: 'À placer' })
    const choisie = volet.getByRole('button', { name: new RegExp(echapper(titres[0])) })
    await choisie.click()
    await expect(choisie).toHaveAttribute('aria-pressed', 'true')
    await expect(volet.getByRole('status')).toContainText(`Touche un jour pour placer ${titres[0]}`)

    // un jour posable (jour passé : grisé ; jour non travaillé : seulement si la semaine n'en offre pas d'autre)
    const jours = page.getByRole('list', { name: 'Jours de la semaine' })
    const candidats = jours.getByRole('button', { name: new RegExp(`placer ${echapper(titres[0])}`) })
    const ouvres = candidats.filter({ hasNotText: /non travaillé|Férié/ })
    await ((await ouvres.count()) > 0 ? ouvres.first() : candidats.first()).click()
    await expect(toast(page)).toContainText('Placée')
    await expect(volet.getByRole('button', { name: new RegExp(echapper(titres[0])) })).toHaveCount(0)

    const jour = await jourServeur(page)
    const lue = await lireTache(page, taches[0].id)
    expect(lue.jour_prevu, 'posée sur un jour de la semaine').toBeTruthy()
    expect(lue.jour_prevu >= jour, 'jamais sur un jour passé').toBeTruthy()
    expect(lue.heure_debut, 'sans heure').toBeNull()

    // Terminer ramène à l'Agenda
    await page.getByRole('button', { name: 'Terminer', exact: true }).click()
    await expect(page.locator('h1.entete-titre')).toHaveText('Agenda')
    await expect(page).not.toHaveURL(/placer=1/)
  })

  test('Agenda : 4 tâches à une heure (toucher la tâche, puis le créneau)', async ({ page }) => {
    await reinitialiser(page)
    const jour = await jourServeur(page)
    const titres = ['Visite de Témara', 'Appel du bureau de contrôle', 'Point avec le comptable', 'Relecture du devis']
      .map((t) => titreUnique(t))
    const taches = await creerTaches(page, titres, { jour_prevu: jour })
    const heures = ['09:00', '10:00', '11:00', '14:00']

    await ouvrirEcran(page, '/taches/agenda', 'agenda')
    await expect(page.locator('h1.entete-titre')).toHaveText('Agenda')
    const volet = page.getByRole('complementary', { name: 'À placer' })
    for (const [rang, titre] of titres.entries()) {
      await volet.getByRole('button', { name: new RegExp(echapper(titre)) }).click()
      await page.getByRole('button', { name: `Placer à ${heures[rang]}`, exact: true }).click()
      await expect(toast(page)).toContainText(`Placée à ${heures[rang]}`)
      await expect(volet.getByRole('button', { name: new RegExp(echapper(titre)) })).toHaveCount(0)
    }
    for (const [rang, tache] of taches.entries()) {
      await expect.poll(async () => String((await lireTache(page, tache.id)).heure_debut).slice(0, 5)).toBe(heures[rang])
    }
    // les quatre blocs sont dans la grille
    for (const titre of titres) await expect(page.getByRole('checkbox', { name: `Fait : ${titre}` })).toBeVisible()

    // la vue Semaine s'ouvre et propose Planifier ma semaine
    await page.getByRole('radio', { name: 'Semaine', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Planifier ma semaine', exact: true })).toBeVisible()
  })
})

test.describe('Tâches — réglages', () => {
  test('Vie privée : le texte de vérité, « Comprendre mon rythme » s\'éteint et se rallume', async ({ page }) => {
    await reinitialiser(page)
    const initial = (await (await page.request.get(`${API}/reglages/`)).json()).comprendre_mon_rythme
    await ouvrirEcran(page, '/taches/reglages/vie-privee', 'reglages')
    await expect(page.getByRole('heading', { name: 'Ce que tu dois savoir sur tes tâches' })).toBeVisible()
    const interrupteur = page.getByRole('switch', { name: 'Comprendre mon rythme' })
    await expect(interrupteur).toHaveAttribute('aria-checked', String(initial))

    await interrupteur.click()
    await expect(interrupteur).toHaveAttribute('aria-checked', String(!initial))
    await expect.poll(async () => (await (await page.request.get(`${API}/reglages/`)).json()).comprendre_mon_rythme).toBe(!initial)
    await interrupteur.click()
    await expect(interrupteur).toHaveAttribute('aria-checked', String(initial))
    await expect.poll(async () => (await (await page.request.get(`${API}/reglages/`)).json()).comprendre_mon_rythme).toBe(initial)
  })

  test('Avancé : « Messages sans délai » ; une adresse d\'agenda refusée l\'est sous le champ', async ({ page }) => {
    await reinitialiser(page)
    const initial = (await (await page.request.get(`${API}/reglages/`)).json()).messages_sans_delai
    await ouvrirEcran(page, '/taches/reglages/avance', 'reglages')
    const sansDelai = page.getByRole('switch', { name: 'Messages sans délai' })
    await expect(sansDelai).toHaveAttribute('aria-checked', String(initial))
    await sansDelai.click()
    await expect(sansDelai).toHaveAttribute('aria-checked', String(!initial))
    await expect.poll(async () => (await (await page.request.get(`${API}/reglages/`)).json()).messages_sans_delai).toBe(!initial)
    await sansDelai.click() // on remet l'état de départ
    await expect.poll(async () => (await (await page.request.get(`${API}/reglages/`)).json()).messages_sans_delai).toBe(initial)

    // « Mes agendas » vit dans Mon iPhone, étape « calendrier » (ouverte par l'adresse)
    await ouvrirEcran(page, '/taches/reglages/iphone?etape=calendrier', 'reglages')

    // une adresse en http:// : refusée, SOUS le champ, avec la phrase du serveur
    const champ = page.getByRole('textbox', { name: /^Adresse de l'agenda/ })
    await expect(page.getByRole('heading', { name: 'Mes agendas' })).toBeVisible()
    await champ.fill('http://exemple.invalid/mon-agenda.ics')
    await page.getByRole('button', { name: 'Ajouter', exact: true }).click()
    // deux `role=alert` portent la phrase (le message sous le champ + la voix sr-only) : on vise celui du champ
    await expect(page.locator('p.es-erreur[role="alert"]').filter({ hasText: 'Adresse https publique attendue.' })).toBeVisible()
    await expect(champ).toHaveAttribute('aria-invalid', 'true')

    // une adresse qui mène à ce serveur lui-même : refusée aussi, aucun agenda n'est créé
    await champ.fill('https://127.0.0.1/mon-agenda.ics')
    await page.getByRole('button', { name: 'Ajouter', exact: true }).click()
    await expect(page.getByRole('alert').filter({ hasText: /\S/ })).toBeVisible()
    await expect(page.getByRole('switch', { name: /^Afficher / })).toHaveCount(0)
    const agendas = await (await page.request.get(`${API}/agendas-externes/`)).json()
    expect(agendas.results ?? agendas).toHaveLength(0)
  })

  test('Mes données : Exporter donne un fichier JSON ; Tout effacer exige EFFACER', async ({ page }) => {
    await reinitialiser(page)
    const projet = await creerProjet(page, titreUnique('Projet à effacer'))
    const [tache] = await creerTaches(page, [titreUnique('Tâche à effacer')], { projet_id: projet.id })
    await ouvrirEcran(page, '/taches/reglages/donnees', 'reglages')

    const [telechargement] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: /^Exporter mes données/ }).click(),
    ])
    expect(telechargement.suggestedFilename()).toMatch(/^mes-donnees-taches-.*\.json$/)
    const exporte = JSON.parse(readFileSync(await telechargement.path(), 'utf8'))
    expect(exporte.exporte_le, 'l\'export est daté').toBeTruthy()

    // Tout effacer : sans EFFACER, l'erreur est SOUS le champ et rien n'est effacé
    await page.getByRole('button', { name: 'Tout effacer', exact: true }).click()
    const dialogue = page.getByRole('dialog', { name: 'Tout effacer ?' })
    await dialogue.getByRole('button', { name: 'Tout effacer', exact: true }).click()
    await expect(dialogue.getByRole('alert')).toContainText('Tape EFFACER pour confirmer.')
    await expect(dialogue.getByRole('textbox', { name: 'Confirmation' })).toHaveAttribute('aria-invalid', 'true')
    expect((await lireTache(page, tache.id)).titre).toBe(tache.titre)

    await dialogue.getByRole('textbox', { name: 'Confirmation' }).fill('EFFACER')
    await dialogue.getByRole('button', { name: 'Tout effacer', exact: true }).click()
    await expect(page).toHaveURL(/\/taches\/aujourdhui/)
    expect(await chercherTaches(page, tache.titre)).toHaveLength(0)
  })
})
