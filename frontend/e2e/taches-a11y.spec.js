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
      // bureau (≥ 1024 px) : `/taches/projets` ouvre le premier projet, la liste est sa colonne de gauche (R2-067)
      await page.goto('/taches/projets')
      await expect(page.locator('.tch[data-ecran="projets"], .tch[data-ecran="projet"]')).toBeVisible()
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
      // R2-125 : « Derniers gestes » nomme aussi la tâche — on lit la section des supprimées
      await expect(page.getByRole('region', { name: 'Supprimées récemment' }).getByText(d.supprimee.titre, { exact: true })).toBeVisible()
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
      await expect(page.getByRole('switch', { name: 'Messages sans délai' })).toBeVisible()
    },
  },
  {
    // « Mes agendas » vit dans Mon iPhone, étape « calendrier » (ouverte par l'adresse)
    nom: 'reglages-iphone-agendas',
    ouvrir: async (page) => {
      await ouvrirEcran(page, '/taches/reglages/iphone?etape=calendrier', 'reglages')
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

/* r2, lane L6 — l'enveloppe du module (coquille + base.css), mesurée dans le navigateur. Les règles qui atteignent la
   coque de l'ERP (en-tête, tiroir, barre d'onglets, bandeau hors ligne) ne valent que dans les pages de Tâches. */
const fondDe = (page, selecteur) => page.locator(selecteur).first().evaluate((el) => getComputedStyle(el).backgroundColor)

test.describe('Tâches — enveloppe sur iPhone (390 × 844, tactile)', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true })

  test('R2-080/083/091 — pas de barre de l\'ERP ; ☰ et cloche dans la rangée du haut ; bord gauche net ; onglet actif lisible', async ({ page }) => {
    await semer(page)
    await attendreAujourdhui(page)
    // R2-080 : l'en-tête de l'ERP n'a plus de boîte visible ; un seul Copilote ; le titre est en haut de l'écran
    await expect(page.locator('.layout-main > .header')).toBeHidden()
    // (le Copilote de l'ERP s'appelle « Ouvrir le Copilote », celui du module « Copilote »)
    await expect(page.getByRole('button', { name: /^(Ouvrir le )?Copilote$/ })).toHaveCount(1)
    expect((await page.locator('h1.entete-titre').boundingBox()).y, 'le titre commence en haut de l\'écran').toBeLessThan(120)
    await page.locator('.tch').getByRole('button', { name: 'Ouvrir le menu' }).click()
    await expect(page.locator('.layout.drawer-open')).toHaveCount(1)
    await page.locator('.drawer-overlay').click({ position: { x: 370, y: 400 } })
    await expect(page.locator('.layout.drawer-open')).toHaveCount(0)
    await page.locator('.tch').getByRole('button', { name: /^Notifications/ }).click()
    await expect(page.locator('.nb-panel')).toBeVisible()
    // R2-083 : le tiroir fermé ne projette plus d'ombre sur le bord gauche
    await page.keyboard.press('Escape')
    expect(await page.locator('.sidebar').evaluate((el) => getComputedStyle(el).boxShadow)).toBe('none')
    // R2-091 : onglet actif ≥ 4,5:1 sur la barre, libellé ≥ 11 px
    const onglet = await page.locator('.bottom-tabbar--app .bottom-tab.active').evaluate((el) => {
      const rgb = (s) => s.match(/[\d.]+/g).slice(0, 3).map(Number)
      const lum = ([r, g, b]) => {
        const c = [r, g, b].map((v) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4 })
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
      }
      const fond = getComputedStyle(el.closest('.bottom-tabbar')).backgroundColor
      const [l1, l2] = [lum(rgb(getComputedStyle(el).color)), lum(rgb(fond))].sort((a, b) => b - a)
      return { contraste: (l1 + 0.05) / (l2 + 0.05), taille: parseFloat(getComputedStyle(el.querySelector('.bottom-tab-label')).fontSize) }
    })
    expect(onglet.contraste, 'contraste de l\'onglet actif').toBeGreaterThanOrEqual(4.5)
    expect(onglet.taille, 'taille du libellé de l\'onglet').toBeGreaterThanOrEqual(11)
  })

  test('R2-081/082 — une surface jusqu\'en bas ; interrupteurs de 51 × 31 au toucher', async ({ page }) => {
    await semer(page)
    await ouvrirEcran(page, '/taches/supprimees', 'supprimees')
    expect(await fondDe(page, 'main.layout-content'), 'le bas de l\'écran a la surface du module').toBe(await fondDe(page, '.tch-page'))
    await ouvrirEcran(page, '/taches/reglages/notifications', 'reglages')
    const boite = await page.locator('.tch .interrupteur').first().boundingBox()
    expect([Math.round(boite.width), Math.round(boite.height)]).toEqual([51, 31])
  })

  test('R2-090 — hors ligne : un seul signal, celui du module', async ({ page, context }) => {
    await semer(page)
    await attendreAujourdhui(page)
    await context.setOffline(true)
    await expect(page.locator('.tch [role="status"]').filter({ hasText: 'Hors ligne' })).toBeVisible()
    await expect(page.locator('.layout-main > [role="status"].bg-warning')).toBeHidden()
    await context.setOffline(false)
  })

  test('R3-080 — journée vide : « ou touche + » désigne un + VISIBLE, de 44 px au moins, qui ouvre la saisie au premier toucher', async ({ page }) => {
    await reinitialiser(page)
    await ouvrirEcran(page, '/taches/aujourdhui', 'aujourdhui')
    await expect(page.getByText('ou touche + pour une tâche')).toBeVisible()
    const plus = page.locator('.tch .fab')
    await expect(plus).toBeVisible()
    const boite = await plus.boundingBox()
    expect(Math.min(boite.width, boite.height), 'taille du +').toBeGreaterThanOrEqual(44)
    await plus.tap()
    await expect(page.getByRole('dialog', { name: 'Ajouter une tâche' })).toBeVisible()
  })

})

test.describe('Tâches — enveloppe au bureau (1440 × 900)', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('R2-085 — le titre est au même pixel sur chaque écran', async ({ page }) => {
    await semer(page)
    const positions = {}
    // R2-067 — « Projets » est, au bureau, la liste à gauche et le projet à droite : son titre est celui du projet, décalé de la
    // colonne ; il n'est donc pas dans cette grille (la colonne est vérifiée à part, dans le parcours « projets » ci-dessus).
    for (const [chemin, ecran] of [['/taches/aujourdhui', 'aujourdhui'], ['/taches/a-trier', 'a-trier'],
      ['/taches/revue', 'revue'], ['/taches/recherche', 'recherche'], ['/taches/supprimees', 'supprimees']]) {
      await ouvrirEcran(page, chemin, ecran)
      const b = await page.locator('h1.entete-titre').boundingBox()
      positions[ecran] = `${Math.round(b.x)},${Math.round(b.y)}`
    }
    expect(new Set(Object.values(positions)).size, JSON.stringify(positions)).toBe(1)
  })

  test('R2-094 — au clavier, la ligne entière est encadrée', async ({ page }) => {
    await semer(page)
    await attendreAujourdhui(page)
    await page.locator('[data-ligne^="tache:"] .case').first().focus()
    await page.keyboard.press('Tab')
    const encadree = page.locator('.tch .ligne:has(.ligne-corps-bouton:focus-visible)')
    await expect(encadree).toHaveCount(1)
    expect(await encadree.evaluate((el) => getComputedStyle(el).boxShadow)).toContain('inset')
  })
})

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
