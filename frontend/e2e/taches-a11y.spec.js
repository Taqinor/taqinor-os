// TCH134 (2/2) — Tâches : ACCESSIBILITÉ MESURÉE dans le navigateur, sur chaque écran du cœur.
//
// Critères de `conception/spec-7-ecrans.md` « Accessibilité » (N10) mesurés ici, à 390 × 844 (iPhone) et à 1440 × 900 :
//   (5) texte à 130 % (rem) : aucun débordement horizontal ; sur Aujourd'hui à 390 × 844, la 1re tâche est visible
//       sans défiler ;
//   (6) axe-core : 0 violation WCAG A/AA par écran (toute gravité, périmètre `.tch`) ;
//   (7) toute cible interactive ≥ 44 × 44 px CSS (la boîte de l'étiquette pour une case native).
// Les critères (1)-(4) et (8) sont joués dans taches-journee.spec.js (annonce « Fait : … », focus sur « Prévu »).
//
// Chaque test repart d'un compte effacé, y crée le même petit jeu (un projet de 4 tâches, 2 tâches à trier, une
// tâche supprimée) et mesure UN écran à UNE largeur : un rouge NOMME l'écran, la largeur et les éléments fautifs.
// Les assertions sont « soft » : les trois mesures d'un écran sont toujours toutes rendues.
import AxeBuilder from '@axe-core/playwright'
import { test, expect } from '@playwright/test'
import {
  API, attendreAujourdhui, creerProjet, creerTaches, ouvrirEcran, reinitialiser, titreUnique,
} from './taches-aides'

const VIEWPORTS = [
  { nom: '390x844', width: 390, height: 844 },
  { nom: '1440x900', width: 1440, height: 900 },
]
const BARRE_AJOUT = (page) => page.getByRole('button', { name: 'Ajouter une tâche', exact: true }).first()

/** Le jeu de départ commun : de quoi qu'aucun écran ne soit vide. */
async function semer(page) {
  await reinitialiser(page)
  const projet = await creerProjet(page, titreUnique('Chantier'), 3)
  const dansLeProjet = await creerTaches(
    page, ['Appeler le fournisseur', 'Commander les rails', 'Relire le contrat', 'Envoyer le devis'].map((t) => titreUnique(t)),
    { projet_id: projet.id })
  const enVrac = await creerTaches(page, ['Passer à la banque', 'Répondre au syndic'].map((t) => titreUnique(t)))
  const [supprimee] = await creerTaches(page, [titreUnique('Payer le parking')])
  const res = await page.request.delete(`${API}/taches/${supprimee.id}/`)
  expect(res.ok(), `supprimer la tâche → ${res.status()}`).toBeTruthy()
  return { projet, dansLeProjet, enVrac, supprimee }
}

const titreH1 = (page, titre) => expect(page.locator('h1.entete-titre')).toHaveText(titre)

/** Les écrans du cœur (et leurs états ouverts) : comment on y arrive et ce qu'on attend d'y voir. */
const ECRANS = [
  { nom: 'aujourdhui', premiereLigne: true, ouvrir: async (page) => { await attendreAujourdhui(page) } },
  {
    nom: 'aujourdhui-gardee',
    ouvrir: async (page) => {
      await attendreAujourdhui(page)
      // le nombre proposé dépend de ce que le compte a DÉJÀ fait ce jour (activités ERP closes) : « Garder ces N » ou « Garder celle-ci »
      await page.getByRole('button', { name: /^Garder (ces \d+|celle-ci)$/ }).first().click()
      await expect(page.getByRole('heading', { name: 'Prévu', exact: true })).toBeVisible()
    },
  },
  {
    nom: 'saisie',
    ouvrir: async (page) => {
      await attendreAujourdhui(page)
      await BARRE_AJOUT(page).click()
      await expect(page.getByRole('dialog', { name: 'Ajouter une tâche' })).toBeVisible()
    },
  },
  {
    nom: 'saisie-liste',
    ouvrir: async (page) => {
      await attendreAujourdhui(page)
      await BARRE_AJOUT(page).click()
      const feuille = page.getByRole('dialog', { name: 'Ajouter une tâche' })
      await feuille.getByRole('textbox', { name: 'Ajouter une tâche', exact: true })
        .fill(`${titreUnique('Salon')}\nRéserver le stand\nImprimer les kakémonos\nPréparer la démo`)
      await expect(feuille.getByText('3 tâches · 1 projet', { exact: true })).toBeVisible()
      await expect(feuille.getByRole('button', { name: 'Créer 3 tâches' })).toBeVisible()
    },
  },
  {
    nom: 'fiche',
    ouvrir: async (page, d) => {
      await ouvrirEcran(page, `/taches/aujourdhui?tache=${d.dansLeProjet[0].id}`, 'aujourdhui')
      await expect(page.locator(`[data-fiche="${d.dansLeProjet[0].id}"]`).getByRole('textbox', { name: 'Titre' }))
        .toHaveValue(d.dansLeProjet[0].titre)
    },
  },
  {
    nom: 'a-trier',
    ouvrir: async (page, d) => {
      await ouvrirEcran(page, '/taches/a-trier', 'a-trier')
      await expect(page.locator(`[data-ligne="tache:${d.enVrac[0].id}"]`)).toBeVisible()
    },
  },
  {
    nom: 'projets',
    ouvrir: async (page, d) => {
      await ouvrirEcran(page, '/taches/projets', 'projets')
      await expect(page.locator(`[data-projet="${d.projet.id}"]`)).toBeVisible()
    },
  },
  {
    nom: 'projet',
    ouvrir: async (page, d) => {
      await ouvrirEcran(page, `/taches/projets/${d.projet.id}`, 'projet')
      await titreH1(page, d.projet.nom)
      await expect(page.locator(`[data-ligne="tache:${d.dansLeProjet[0].id}"]`)).toBeVisible()
    },
  },
  {
    nom: 'planifier-le-projet',
    ouvrir: async (page, d) => {
      await ouvrirEcran(page, `/taches/projets/${d.projet.id}?planifier=1`, 'projet')
      await expect(page.getByRole('region', { name: 'Planifier le projet' })).toBeVisible()
    },
  },
  {
    nom: 'agenda-jour',
    ouvrir: async (page) => {
      await ouvrirEcran(page, '/taches/agenda', 'agenda')
      await titreH1(page, 'Agenda')
      await expect(page.getByRole('complementary', { name: 'À placer' })).toBeVisible()
    },
  },
  {
    nom: 'agenda-semaine',
    ouvrir: async (page) => {
      await ouvrirEcran(page, '/taches/agenda?vue=semaine', 'agenda')
      await expect(page.getByRole('button', { name: 'Planifier ma semaine', exact: true })).toBeVisible()
    },
  },
  {
    nom: 'planifier-ma-semaine',
    ouvrir: async (page) => {
      await ouvrirEcran(page, '/taches/agenda?vue=semaine&placer=1', 'agenda')
      await titreH1(page, 'Planifier ma semaine')
      await expect(page.getByRole('list', { name: 'Jours de la semaine' })).toBeVisible()
    },
  },
  {
    nom: 'revue',
    ouvrir: async (page, d) => {
      await ouvrirEcran(page, '/taches/revue', 'revue')
      await expect(page.getByRole('region', { name: d.projet.nom })).toBeVisible()
    },
  },
  {
    nom: 'rythme',
    ouvrir: async (page) => {
      await ouvrirEcran(page, '/taches/rythme', 'rythme')
      await expect(page.getByText('Sans objectif', { exact: false }).first()).toBeVisible()
    },
  },
  {
    nom: 'recherche',
    ouvrir: async (page) => {
      await ouvrirEcran(page, '/taches/recherche', 'recherche')
      await expect(page.getByRole('searchbox', { name: 'Chercher dans mes tâches' })).toBeVisible()
    },
  },
  {
    nom: 'supprimees',
    ouvrir: async (page, d) => {
      await ouvrirEcran(page, '/taches/supprimees', 'supprimees')
      await expect(page.getByText(d.supprimee.titre, { exact: true })).toBeVisible()
    },
  },
  {
    nom: 'reglages-vie-privee',
    ouvrir: async (page) => {
      await ouvrirEcran(page, '/taches/reglages/vie-privee', 'reglages')
      await expect(page.getByRole('heading', { name: 'Ce que tu dois savoir sur tes tâches' })).toBeVisible()
    },
  },
  {
    nom: 'reglages-donnees',
    ouvrir: async (page) => {
      await ouvrirEcran(page, '/taches/reglages/donnees', 'reglages')
      await expect(page.getByRole('button', { name: /^Exporter mes données/ })).toBeVisible()
    },
  },
  {
    nom: 'reglages-avance',
    ouvrir: async (page) => {
      await ouvrirEcran(page, '/taches/reglages/avance', 'reglages')
      await expect(page.getByRole('heading', { name: 'Mes agendas' })).toBeVisible()
    },
  },
]

/** Les cibles interactives visibles de `.tch` plus petites que 44 × 44 px (critère 7). */
function ciblesTropPetites() {
  const SEUIL = 43.5 // 44 px CSS, moins l'arrondi de la mesure
  const SELECTEUR = [
    'button', 'a[href]', 'input:not([type="hidden"])', 'select', 'textarea', 'summary',
    '[role="checkbox"]', '[role="radio"]', '[role="switch"]', '[role="tab"]', '[role="menuitem"]', '[role="option"]',
  ].join(',')
  const fautives = []
  for (const el of document.querySelectorAll('.tch')) {
    for (const cible of el.querySelectorAll(SELECTEUR)) {
      if (cible.closest('[aria-hidden="true"], [hidden], .sr')) continue
      const style = getComputedStyle(cible)
      if (style.display === 'none' || style.visibility === 'hidden') continue
      // une case ou un bouton radio NATIF : la cible est son étiquette (zone cliquable), jamais le carré de 13 px
      const natif = cible.matches('input[type="checkbox"], input[type="radio"]')
      const boite = (natif ? cible.closest('label') : null) ?? cible
      const r = boite.getBoundingClientRect()
      if (r.width === 0 && r.height === 0) continue
      // la zone cliquable compte, pas seulement la boîte dessinée : le design étend la cible par un `::after`
      // absolu (puces, copilote, segments, interrupteur, « Garder », ligne entière) — c'est elle qui reçoit le doigt
      const apres = getComputedStyle(boite, '::after')
      const etendue = apres.content !== 'none' && apres.position === 'absolute'
      const largeur = Math.max(r.width, etendue ? parseFloat(apres.width) || 0 : 0)
      const hauteur = Math.max(r.height, etendue ? parseFloat(apres.height) || 0 : 0)
      if (largeur < SEUIL || hauteur < SEUIL) {
        const nom = cible.getAttribute('aria-label') || cible.textContent.trim().slice(0, 40) || cible.getAttribute('placeholder') || ''
        fautives.push(`${cible.tagName.toLowerCase()}.${String(cible.className).trim().split(/\s+/).join('.')} « ${nom} » ${Math.round(largeur)}×${Math.round(hauteur)}`)
      }
    }
  }
  return fautives
}

for (const vp of VIEWPORTS) {
  test.describe(`Tâches — accessibilité mesurée à ${vp.nom}`, () => {
    for (const ecran of ECRANS) {
      test(`${ecran.nom}`, async ({ page }) => {
        await page.setViewportSize({ width: vp.width, height: vp.height })
        const donnees = await semer(page)
        await ecran.ouvrir(page, donnees)

        // (6) axe-core : 0 violation WCAG A/AA, quelle que soit la gravité
        const axe = await new AxeBuilder({ page })
          .include('.tch')
          .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
          .analyze()
        expect.soft(
          axe.violations.map((v) => `${v.id} (${v.impact}) : ${v.nodes.map((n) => n.target.join(' ')).slice(0, 5).join(' | ')}`),
          `${ecran.nom} @ ${vp.nom} : violations axe-core`,
        ).toEqual([])

        // (7) toute cible ≥ 44 × 44 px CSS
        expect.soft(
          await page.evaluate(ciblesTropPetites),
          `${ecran.nom} @ ${vp.nom} : cibles de moins de 44 × 44 px`,
        ).toEqual([])

        // (5) texte à 130 % : rien ne déborde ; Aujourd'hui à 390 × 844 : la 1re tâche reste visible sans défiler
        await page.evaluate(() => {
          document.documentElement.style.setProperty('font-size', '130%', 'important')
          window.scrollTo(0, 0)
        })
        await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))))
        const debordement = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
        expect.soft(debordement, `${ecran.nom} @ ${vp.nom} : débordement horizontal à 130 % (px)`).toBeLessThanOrEqual(1)
        if (ecran.premiereLigne && vp.width === 390) {
          const premiere = await page.locator('[data-ligne^="tache:"]').first().boundingBox()
          expect.soft(premiere, 'une tâche est affichée').not.toBeNull()
          expect.soft(
            (premiere?.y ?? Infinity) + (premiere?.height ?? 0),
            `${ecran.nom} @ ${vp.nom} : la 1re tâche doit tenir dans les ${vp.height} px sans défiler (texte à 130 %)`,
          ).toBeLessThanOrEqual(vp.height)
        }
      })
    }
  })
}
