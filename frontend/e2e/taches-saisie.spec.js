// TCH133 (2/2) — Tâches, bout en bout : SAISIE, À TRIER, FICHE, CONFLIT sur la vraie pile.
//
// Parcours joués ici (spec-7 « Parcours chiffrés » 1, 2, 9, 14, 20, 22) :
//   une phrase (puces lues, retirables) · « Coller mes listes » (4 collages) · vider À trier (3 projets, 2 dates) ·
//   brouillon repris · fiche (notes, Fait) · conflit entre deux appareils (Garder la mienne / Prendre l'autre).
// NON joués ici (horloge ou push) : bilan d'hier, rappel reçu — acceptation en direct (TCH136/TCH137/TCH144).
//
// Chaque test repart d'un compte effacé et crée ses propres données (titres uniques) : rejouable, indépendant de
// l'ordre. « Le deuxième appareil » du conflit est joué par l'API (`page.request`), qui écrit exactement ce
// qu'écrirait l'autre navigateur.
import { readFileSync } from 'node:fs'
import { test, expect } from '@playwright/test'
import {
  API, attendreAujourdhui, boutonGarder, chercherTaches, creerProjet, creerTaches, etatJournee, jourServeur, ligne, listerProjets,
  lireTache, ouvrirEcran, reinitialiser, suffixe, titreUnique, toast,
} from './taches-aides'

const boutonAjouter = (page) => page.getByRole('button', { name: 'Ajouter une tâche', exact: true }).first()
const feuilleSaisie = (page) => page.getByRole('dialog', { name: 'Ajouter une tâche' })
const champSaisie = (page) => feuilleSaisie(page).getByRole('textbox', { name: 'Ajouter une tâche', exact: true })

/** Un projet actif de 2 tâches, pour que la journée ne soit pas vide (la carte « Reprendre » n'existe que sur une journée remplie). */
async function journeeNonVide(page) {
  await reinitialiser(page)
  const projet = await creerProjet(page, titreUnique('Chantier'))
  const taches = await creerTaches(page, [titreUnique('Appeler le fournisseur'), titreUnique('Relire le contrat')],
    { projet_id: projet.id })
  return { projet, taches }
}

test.describe('Tâches — saisie', () => {
  test('une phrase : le jour et le projet lus sont des puces, la tâche arrive rangée', async ({ page }) => {
    await reinitialiser(page)
    const nomProjet = `Projet${suffixe()}`
    const projet = await creerProjet(page, nomProjet)
    const titre = titreUnique('Appeler le fournisseur')
    await ouvrirEcran(page, '/taches/aujourdhui', 'aujourdhui')

    await boutonAjouter(page).click()
    await expect(feuilleSaisie(page)).toBeVisible()
    await champSaisie(page).fill(`${titre} demain #${nomProjet}`)

    // l'analyse n'ajoute que des PUCES : jour et projet lus, le texte tapé reste tel quel
    await expect(feuilleSaisie(page).locator('[data-jeton="jour"]')).toBeVisible()
    await expect(feuilleSaisie(page).locator('[data-jeton="projet"]')).toBeVisible()
    await expect(champSaisie(page)).toHaveValue(`${titre} demain #${nomProjet}`)

    await champSaisie(page).press('Enter')
    // chaîne (spec-2 §1) : le champ se vide, la feuille reste ouverte pour la suivante ; Échap ferme
    await expect(champSaisie(page)).toHaveValue('')
    await expect(toast(page)).toContainText('Ajoutée')
    await page.keyboard.press('Escape')
    await expect(feuilleSaisie(page)).toHaveCount(0)

    const jour = await jourServeur(page)
    await expect.poll(async () => (await chercherTaches(page, titre)).length).toBe(1)
    const [creee] = await chercherTaches(page, titre)
    const lue = await lireTache(page, creee.id)
    expect(lue.titre, 'les jetons lus sortent du titre').toBe(titre)
    expect(lue.projet?.id, 'rangée dans le projet nommé').toBe(projet.id)
    expect(lue.jour_prevu > jour, 'prévue demain').toBeTruthy()
  })

  test('R2-001 — taper vite après Entrée : le serveur retenu, aucune phrase n\'est perdue ni tronquée', async ({ page }) => {
    await reinitialiser(page)
    // chaque création est RETENUE sur une porte que le test lâche après la saisie des trois phrases (le réseau
    // d'un iPhone dans la rue) ; l'aperçu, lui, passe tout de suite
    let lacher
    const porte = new Promise((r) => { lacher = r })
    await page.route('**/api/django/taches/saisie-rapide/', async (route) => {
      if (route.request().postDataJSON()?.apercu === false) await porte
      await route.continue()
    })
    const titres = [titreUnique('Test un'), titreUnique('Rappeler Karim'), titreUnique('Meryem sur les leads')]
    await ouvrirEcran(page, '/taches/aujourdhui', 'aujourdhui')
    await boutonAjouter(page).click()
    for (const titre of titres) {
      await champSaisie(page).pressSequentially(titre, { delay: 10 })
      await champSaisie(page).press('Enter')
      // le champ se vide AU TOUCHER, avant le retour du serveur
      await expect(champSaisie(page)).toHaveValue('')
    }
    lacher() // seulement maintenant le serveur reçoit les trois créations
    for (const titre of titres) {
      await expect.poll(async () => (await chercherTaches(page, titre)).filter((t) => t.titre === titre).length,
        `« ${titre} » créée entière, une fois`).toBe(1)
    }
  })

  test('R2-009 — au bureau, `n` ouvre la saisie EN PLACE sous « Ajouter une tâche » : sans voile, la liste reste dessous', async ({ page }) => {
    await journeeNonVide(page)
    await attendreAujourdhui(page)
    await page.keyboard.press('n')
    const feuille = feuilleSaisie(page)
    await expect(feuille).toBeVisible()
    await expect(feuille).toHaveAttribute('aria-modal', 'false')
    expect(await feuille.evaluate((f) => Boolean(f.closest('.saisie-ancre'))), 'rendue à la place de la ligne').toBe(true)
    await expect(page.locator('.tch .voile')).toHaveCount(0)
    await expect(champSaisie(page)).toBeFocused()
    const titre = titreUnique('Relancer le transporteur')
    await champSaisie(page).fill(titre)
    await champSaisie(page).press('Enter')
    await expect(champSaisie(page)).toHaveValue('')
    await expect(champSaisie(page)).toBeFocused()
    await expect.poll(async () => (await chercherTaches(page, titre)).length).toBe(1)
    await page.keyboard.press('Escape')
    await expect(feuille).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Ajouter une tâche', exact: true }).first()).toBeVisible()
  })

  test('R2-003 — « #Sal » propose « Salon Solaire Expo » : la tâche y va, aucun projet en double', async ({ page }) => {
    await reinitialiser(page)
    const nom = `Salon Solaire Expo ${suffixe()}`
    const projet = await creerProjet(page, nom)
    const titre = titreUnique('Réserver le stand')
    await ouvrirEcran(page, '/taches/aujourdhui', 'aujourdhui')
    await boutonAjouter(page).click()
    await champSaisie(page).pressSequentially(`${titre} #Sal`, { delay: 10 })
    await expect(feuilleSaisie(page).getByRole('listbox', { name: 'Projets' }).getByRole('option', { name: nom })).toBeVisible()
    await champSaisie(page).press('Enter')
    // R3-047 — le nom s'insère avec ses espaces ; le serveur lit en entier le nom d'un projet existant
    await expect(champSaisie(page)).toHaveValue(`${titre} #${nom} `)
    await expect(feuilleSaisie(page).locator('[data-jeton="projet"]')).toContainText(nom)
    await champSaisie(page).press('Enter')
    await expect.poll(async () => (await chercherTaches(page, titre)).length).toBe(1)
    expect((await lireTache(page, (await chercherTaches(page, titre))[0].id)).projet?.id).toBe(projet.id)
    expect((await listerProjets(page)).map((p) => p.nom), 'aucun « Nouveau projet : Sal »').toEqual([nom])
  })

  test('retirer une puce : le mot reste dans le titre, rien n\'est corrigé', async ({ page }) => {
    await reinitialiser(page)
    const titre = titreUnique('Appeler le fournisseur')
    await ouvrirEcran(page, '/taches/aujourdhui', 'aujourdhui')

    await boutonAjouter(page).click()
    await champSaisie(page).fill(`${titre} demain`)
    const puceJour = feuilleSaisie(page).locator('[data-jeton="jour"]')
    await expect(puceJour).toBeVisible()
    await puceJour.getByRole('button', { name: /^Retirer / }).click()
    await expect(puceJour).toHaveCount(0)

    await champSaisie(page).press('Enter')
    await expect(champSaisie(page)).toHaveValue('')
    await expect.poll(async () => (await chercherTaches(page, titre)).length).toBe(1)
    const [creee] = await chercherTaches(page, titre)
    const lue = await lireTache(page, creee.id)
    expect(lue.titre).toBe(`${titre} demain`)
    // R2-002 — la puce « demain » retirée, c'est le jour de l'écran (Aujourd'hui) qui reste
    expect(lue.jour_prevu, 'le jour lu a été retiré : la tâche part sur le jour de l\'écran').toBe(await jourServeur(page))
  })

  test('R2-002 — ajoutée depuis Aujourd\'hui, elle arrive dans Aujourd\'hui (et la puce du jour se retire)', async ({ page }) => {
    await reinitialiser(page)
    const [titre, sansJour] = [titreUnique('Rappeler M. Benjelloun'), titreUnique('Idée à trier')]
    await ouvrirEcran(page, '/taches/aujourdhui', 'aujourdhui')
    await boutonAjouter(page).click()
    await expect(feuilleSaisie(page).getByRole('button', { name: 'Retirer le jour choisi' })).toBeVisible()
    await champSaisie(page).fill(titre)
    await champSaisie(page).press('Enter')
    await expect(toast(page)).toContainText("Ajoutée à Aujourd'hui")
    await feuilleSaisie(page).getByRole('button', { name: 'Retirer le jour choisi' }).click()
    await champSaisie(page).fill(sansJour)
    await champSaisie(page).press('Enter')
    const jour = await jourServeur(page)
    await expect.poll(async () => (await chercherTaches(page, titre)).length).toBe(1)
    await expect.poll(async () => (await chercherTaches(page, sansJour)).length).toBe(1)
    expect((await lireTache(page, (await chercherTaches(page, titre))[0].id)).jour_prevu).toBe(jour)
    expect((await lireTache(page, (await chercherTaches(page, sansJour))[0].id)).jour_prevu, 'jour retiré : À trier').toBeNull()
  })

  test('Coller mes listes : 4 collages deviennent 4 « Nouveau projet » (Moyenne) et 12 tâches', async ({ page }) => {
    await reinitialiser(page)
    const s = suffixe()
    const listes = [
      [`Salon ${s}`, 'Réserver le stand', 'Imprimer les kakémonos', 'Préparer la démo onduleur'],
      [`Recrutement ${s}`, "Publier l'annonce", 'Trier les CV reçus', 'Valider le budget du poste'],
      [`Administratif ${s}`, 'Payer la CNSS', 'Envoyer les factures', 'Payer le loyer du dépôt'],
      [`Site web ${s}`, 'Choisir les photos', "Rédiger la page d'accueil", 'Relire les textes'],
    ]
    await ouvrirEcran(page, '/taches/aujourdhui', 'aujourdhui')

    // journée sans aucune tâche : l'invitation à coller ses listes (spec-7 §8)
    await expect(page.getByText('Colle ou dicte tes listes', { exact: false })).toBeVisible()
    await page.getByRole('button', { name: 'Coller mes listes' }).click()
    await expect(feuilleSaisie(page)).toBeVisible()

    for (const [rang, liste] of listes.entries()) {
      if (rang > 0) await feuilleSaisie(page).getByRole('button', { name: 'Coller encore' }).click()
      await champSaisie(page).fill(liste.join('\n'))
      const n = rang + 1
      await expect(feuilleSaisie(page).getByText(`${3 * n} tâches · ${n} projet${n > 1 ? 's' : ''}`, { exact: true })).toBeVisible()
    }

    // chaque première ligne est un « Nouveau projet », priorité Moyenne par défaut
    for (const [nom] of listes) {
      await expect(feuilleSaisie(page).getByText(`Nouveau projet : ${nom}`)).toBeVisible()
      // passe visuelle n° 33 : la priorité est la puce « Moyenne ⌄ » de l'en-tête du projet
      await expect(feuilleSaisie(page).getByRole('button', { name: `Priorité du projet ${nom} : moyenne` })).toHaveText('Moyenne')
    }

    await feuilleSaisie(page).getByRole('button', { name: 'Créer 12 tâches' }).click()
    await expect(feuilleSaisie(page)).toHaveCount(0)
    await expect(toast(page)).toContainText('12 tâches créées')

    // le serveur : 4 projets (les noms collés) et 12 tâches ; Proposé est rempli aussitôt (objectif − déjà faites, lu sur le serveur)
    const projets = await listerProjets(page)
    expect(projets.map((p) => p.nom).sort()).toEqual(listes.map(([nom]) => nom).sort())
    for (const [, ...titres] of listes) {
      for (const titre of titres) {
        const trouvees = await chercherTaches(page, titre)
        expect(trouvees.filter((t) => t.titre === titre), `« ${titre} » créée une fois`).toHaveLength(1)
      }
    }
    const etat = await etatJournee(page)
    expect(etat.lignes, 'le serveur propose au moins une tâche').toBeGreaterThan(0)
    await expect(boutonGarder(page, etat.lignes)).toBeVisible()
  })

  test('R2-004 — coller une liste « comme dans Notes » (titres sans « : ») : 7 groupes nommés AVANT « Créer »', async ({ page }) => {
    await reinitialiser(page)
    const liste = readFileSync(new URL('../../backend/django_core/apps/taches/tests/donnees/liste30.txt', import.meta.url), 'utf8')
    await ouvrirEcran(page, '/taches/aujourdhui', 'aujourdhui')
    await page.getByRole('button', { name: 'Coller mes listes' }).click()
    await champSaisie(page).fill(liste.trim())
    for (const nom of ['Villa Benjelloun Dar Bouazza', 'Hôtel Atlas Marrakech', 'Pompage Ferme Berrechid',
      'Boulangerie Ain Sebaa', 'Admin', 'Recrutement', 'Divers']) {
      await expect(feuilleSaisie(page).getByText(`Nouveau projet : ${nom}`, { exact: true })).toBeVisible()
    }
    await expect(feuilleSaisie(page).getByText('28 tâches · 7 projets', { exact: true })).toBeVisible()
    await expect(feuilleSaisie(page).getByRole('button', { name: 'Créer 28 tâches' })).toBeVisible()
  })

  test('brouillon : fermer la saisie en cours de frappe, la rouvrir, tout est repris', async ({ page }) => {
    await journeeNonVide(page)
    await attendreAujourdhui(page)
    const brouillon = titreUnique('Penser à rappeler le syndic')

    await boutonAjouter(page).click()
    await champSaisie(page).fill(brouillon)
    await page.keyboard.press('Escape')
    await expect(feuilleSaisie(page)).toHaveCount(0)

    const carte = page.getByRole('region', { name: 'Brouillon' })
    await expect(carte).toContainText("Ta saisie de tout à l'heure t'attend.")
    await carte.getByRole('button', { name: 'Reprendre' }).click()
    await expect(champSaisie(page)).toHaveValue(brouillon)
    // rien n'a été créé pendant ce temps
    expect(await chercherTaches(page, brouillon)).toHaveLength(0)
  })
})

test.describe('Tâches — À trier', () => {
  test('vider À trier : 5 tâches, 2 dates, 3 projets', async ({ page }) => {
    await reinitialiser(page)
    const projets = []
    for (const nom of ['Salon', 'Recrutement', 'Administratif']) projets.push(await creerProjet(page, titreUnique(nom)))
    const titres = ['Répondre au syndic', 'Passer à la banque', 'Commander des gants', 'Payer le parking', 'Envoyer les photos']
      .map((t) => titreUnique(t))
    const taches = await creerTaches(page, titres)
    await ouvrirEcran(page, '/taches/a-trier', 'a-trier')
    await expect(page.locator('[data-ligne^="tache:"]')).toHaveCount(5)

    // deux dates : Aujourd'hui, Demain
    await ligne(page, taches[0].id).getByRole('button', { name: "Aujourd'hui", exact: true }).click()
    await expect(ligne(page, taches[0].id)).toHaveCount(0)
    await expect(toast(page)).toContainText("Mise à aujourd'hui")
    await ligne(page, taches[1].id).getByRole('button', { name: 'Demain', exact: true }).click()
    await expect(ligne(page, taches[1].id)).toHaveCount(0)

    // trois projets : « Projet… » puis le projet
    for (const [rang, projet] of projets.entries()) {
      const tache = taches[rang + 2]
      await ligne(page, tache.id).getByRole('button', { name: 'Projet…', exact: true }).click()
      const feuille = page.getByRole('dialog', { name: 'Projet', exact: true })
      await feuille.getByRole('option', { name: projet.nom }).click()
      await expect(ligne(page, tache.id)).toHaveCount(0)
    }

    await expect(page.getByText('Rien à trier')).toBeVisible()

    // le serveur : les deux dates et les trois projets. La ligne quitte la liste AVANT la
    // réponse du serveur (écran optimiste) : on attend l'écriture au lieu de lire une fois.
    const jour = await jourServeur(page)
    await expect.poll(async () => (await lireTache(page, taches[0].id)).jour_prevu).toBe(jour)
    await expect.poll(async () => (await lireTache(page, taches[1].id)).jour_prevu > jour).toBeTruthy()
    for (const [rang, projet] of projets.entries()) {
      await expect.poll(async () => (await lireTache(page, taches[rang + 2].id)).projet?.id).toBe(projet.id)
    }
  })
})

test.describe('Tâches — la fiche et le conflit entre deux appareils', () => {
  /** Une tâche seule dans un projet, et sa fiche ouverte par l'adresse `?tache=`. */
  async function ouvrirFiche(page) {
    const { taches } = await journeeNonVide(page)
    const tache = taches[0]
    await ouvrirEcran(page, `/taches/aujourdhui?tache=${tache.id}`, 'aujourdhui')
    const fiche = page.locator(`[data-fiche="${tache.id}"]`)
    await expect(fiche.getByRole('textbox', { name: 'Titre' })).toHaveValue(tache.titre)
    return { tache, fiche }
  }

  test('la fiche : une ligne l\'ouvre, les notes s\'enregistrent d\'elles-mêmes, « Fait » la clôt', async ({ page }) => {
    const { taches } = await journeeNonVide(page)
    const tache = taches[0]
    await attendreAujourdhui(page)

    await ligne(page, tache.id).locator('.ligne-corps-bouton').click()
    await expect(page).toHaveURL(new RegExp(`tache=${tache.id}`))
    const fiche = page.locator(`[data-fiche="${tache.id}"]`)
    await expect(fiche.getByRole('textbox', { name: 'Titre' })).toHaveValue(tache.titre)

    const notes = `Appeler avant 11 h ${suffixe()}`
    await fiche.getByLabel('Notes').fill(notes)
    await fiche.getByLabel('Notes').blur()
    await expect.poll(async () => (await lireTache(page, tache.id)).notes).toBe(notes)

    await fiche.getByRole('button', { name: 'Fait', exact: true }).click()
    await expect(toast(page)).toContainText('Faite')
    await expect.poll(async () => (await lireTache(page, tache.id)).statut).toBe('fait')
    await expect(fiche.getByRole('button', { name: 'Rouvrir', exact: true })).toBeVisible()

    // Échap ferme la fiche : on retrouve Aujourd'hui, l'adresse n'a plus `tache=`
    await page.keyboard.press('Escape')
    await expect(page.locator(`[data-fiche="${tache.id}"]`)).toHaveCount(0)
    await expect(page).not.toHaveURL(/tache=/)
  })

  test('conflit : « Garder la mienne » renvoie ma saisie, rien n\'est perdu', async ({ page }) => {
    const { tache, fiche } = await ouvrirFiche(page)
    const autre = titreUnique('Titre venu de lautre appareil')
    const mienne = titreUnique('Ma version du titre')

    // le deuxième appareil écrit d'abord (même version lue que la mienne)
    const lue = await lireTache(page, tache.id)
    const res = await page.request.patch(`${API}/taches/${tache.id}/`, { data: { titre: autre, lock_version: lue.lock_version } })
    expect(res.ok(), `PATCH de l'autre appareil → ${res.status()} ${await res.text()}`).toBeTruthy()

    const titreChamp = fiche.getByRole('textbox', { name: 'Titre' })
    await titreChamp.fill(mienne)
    await titreChamp.press('Enter')

    const bandeau = page.getByRole('group', { name: 'Conflit entre appareils' })
    await expect(bandeau).toContainText('Modifiée sur ton autre appareil')
    // ma saisie est gardée tant que je n'ai pas choisi, et le serveur a encore la version de l'autre appareil
    await expect(titreChamp).toHaveValue(mienne)
    expect((await lireTache(page, tache.id)).titre).toBe(autre)

    await bandeau.getByRole('button', { name: 'Garder la mienne' }).click()
    await expect(bandeau).toHaveCount(0)
    await expect.poll(async () => (await lireTache(page, tache.id)).titre).toBe(mienne)
  })

  test('conflit : « Prendre l\'autre » adopte la version de l\'autre appareil', async ({ page }) => {
    const { tache, fiche } = await ouvrirFiche(page)
    const autre = titreUnique('Titre venu de lautre appareil')
    const mienne = titreUnique('Ma version du titre')

    const lue = await lireTache(page, tache.id)
    const res = await page.request.patch(`${API}/taches/${tache.id}/`, { data: { titre: autre, lock_version: lue.lock_version } })
    expect(res.ok(), `PATCH de l'autre appareil → ${res.status()} ${await res.text()}`).toBeTruthy()

    const titreChamp = fiche.getByRole('textbox', { name: 'Titre' })
    await titreChamp.fill(mienne)
    await titreChamp.press('Enter')

    const bandeau = page.getByRole('group', { name: 'Conflit entre appareils' })
    await expect(bandeau).toBeVisible()
    await bandeau.getByRole('button', { name: "Prendre l'autre" }).click()
    await expect(bandeau).toHaveCount(0)
    // le serveur n'a pas bougé : c'est la version de l'autre appareil
    expect((await lireTache(page, tache.id)).titre).toBe(autre)
  })
})

/** Ce que le doigt toucherait au CENTRE du bouton : le bouton lui-même (ou un de ses enfants), jamais la barre
 *  d'onglets de l'ERP posée par-dessus (acceptation F2, P136.2 : « Coller encore » passait sous les onglets). */
async function recoitLeDoigt(bouton) {
  return bouton.evaluate((el) => {
    const r = el.getBoundingClientRect()
    const touche = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)
    return Boolean(touche) && (touche === el || el.contains(touche))
  })
}

test.describe('Tâches — iPhone : le pied des feuilles passe au-dessus de la barre d\'onglets', () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })

  test('feuille de saisie : « Coller encore » et « Créer 3 tâches » reçoivent le doigt', async ({ page }) => {
    await reinitialiser(page)
    const nom = `Salon ${suffixe()}`
    await ouvrirEcran(page, '/taches/aujourdhui', 'aujourdhui')
    await expect(page.locator('nav.bottom-tabbar'), "la barre d'onglets de l'ERP est là").toBeVisible()
    await page.getByRole('button', { name: 'Coller mes listes' }).click()
    await champSaisie(page).fill([nom, 'Réserver le stand', 'Imprimer les kakémonos', 'Préparer la démo'].join('\n'))
    const encore = feuilleSaisie(page).getByRole('button', { name: 'Coller encore' })
    const creer = feuilleSaisie(page).getByRole('button', { name: 'Créer 3 tâches' })
    await expect(creer).toBeVisible()
    await expect.poll(() => recoitLeDoigt(encore), '« Coller encore » sous le doigt').toBe(true)
    await expect.poll(() => recoitLeDoigt(creer), '« Créer 3 tâches » sous le doigt').toBe(true)
    await creer.tap()
    await expect(feuilleSaisie(page)).toHaveCount(0)
    // R2-001 : l'envoi part EN ARRIÈRE-PLAN (la feuille se ferme au toucher) — on attend que le serveur l'ait écrit
    await expect.poll(async () => (await listerProjets(page)).map((p) => p.nom)).toEqual([nom])
  })

  test('fiche : « Fait » reçoit le doigt', async ({ page }) => {
    const { taches } = await journeeNonVide(page)
    const tache = taches[0]
    await ouvrirEcran(page, `/taches/aujourdhui?tache=${tache.id}`, 'aujourdhui')
    const fiche = page.locator(`[data-fiche="${tache.id}"]`)
    const fait = fiche.getByRole('button', { name: 'Fait', exact: true })
    await expect(fait).toBeVisible()
    await expect.poll(() => recoitLeDoigt(fait), '« Fait » sous le doigt').toBe(true)
    await fait.tap()
    await expect.poll(async () => (await lireTache(page, tache.id)).statut).toBe('fait')
  })
})
