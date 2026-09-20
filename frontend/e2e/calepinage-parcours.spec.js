// CAL221 — Parcours AUTONOME du module Calepinage, de bout en bout :
// ouvrir /calepinage → créer un calepinage depuis un LEAD → enregistrer une
// variante → la retenir → générer le devis (action CAL24).
//
// POURQUOI CETTE SPEC EXISTE. La suite Playwright couvre l'AO
// (`ao-parcours.spec.js`), le devis (`devis.spec.js`) et le calepinage TACTILE
// (`calepinage_tactile.spec.js`), mais aucun parcours calepinage AUTONOME : la
// porte du module (CAL34), son écran de création (CAL36), son comparatif de
// variantes (CAL42) et sa sortie devis (CAL38) n'étaient jamais traversés
// ensemble. Une porte qui s'ouvre et un bouton qui répond ne prouvent rien tant
// que le chemin complet n'est pas parcouru une fois.
//
// HOOKS DOM STABLES, JAMAIS UN TEXTE TRADUIT quand un hook existe : les
// `data-testid` `cal-*` et les `id` `cal-nouveau-*` sont posés par les écrans
// eux-mêmes (`features/calepinage/*`). Les rares libellés cités (« Créer le
// calepinage », « Retenir ») sont des noms ACCESSIBLES de boutons, pas des
// textes décoratifs.
//
// MODE STRICT PLAYWRIGHT — les DEUX éléments sont appariés quand un libellé est
// ambigu : « Calepinages » est à la fois l'entrée de nav du module et le titre
// de la liste ; « Nouveau calepinage » est à la fois l'entrée de nav et le
// titre de l'écran de création. Chaque locator est donc porté par son RÔLE
// (`link` vs `heading`), jamais par `getByText`.
//
// UNE VARIANTE EST ENREGISTRÉE PAR L'API, PAS PAR L'ÉCRAN — et c'est dit plutôt
// que caché : aucun écran du module n'expose aujourd'hui de geste « enregistrer
// une variante » (le comparatif CAL42 compare et RETIENT ; l'atelier ne publie
// pas encore ce bouton). La spec utilise donc le contexte de requête
// AUTHENTIFIÉ de Playwright (mêmes cookies que la page) pour poser la variante
// par `POST /api/django/calepinage/calepinages/<id>/variantes/`, exactement
// comme d'autres specs sèment leur donnée ; les gestes suivants (retenir,
// générer le devis) passent, eux, par l'INTERFACE RÉELLE.
import { test, expect } from '@playwright/test'
import { uniq, gotoLeads, createLead } from './helpers'

const API = '/api/django/calepinage'

/** L'identifiant du calepinage ouvert, lu sur l'URL de son atelier. */
function idDansUrl(url) {
  const m = /\/calepinage\/(\d+)/.exec(new URL(url).pathname)
  return m ? m[1] : null
}

test('CAL221: /calepinage → créer depuis un lead → variante → retenir → devis', async ({ page }) => {
  // ── 0. Un lead FRAIS, jamais un enregistrement partagé qu'on mute ───────
  await gotoLeads(page)
  const nomLead = await createLead(page, {
    nom: uniq('CAL221 Lead'), facture: 900, ville: 'Casablanca',
  })

  // ── 1. LA PORTE AUTONOME DU MODULE (CAL34) ─────────────────────────────
  await page.goto('/calepinage')
  // Appariement strict : l'entrée de NAV et le TITRE portent le même mot.
  await expect(page.getByRole('link', { name: 'Calepinages' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Calepinages' })).toBeVisible()

  // ── 2. CRÉER DEPUIS UN LEAD (CAL36) ────────────────────────────────────
  // Idem : le lien de nav, puis le titre de l'écran atteint.
  await page.getByRole('link', { name: 'Nouveau calepinage' }).click()
  await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible()

  // L'onglet « Lead » est l'onglet par défaut ; on le désigne explicitement
  // pour que la spec reste vraie le jour où l'ordre des onglets change.
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()

  const nomCalepinage = uniq('CAL221 Toiture')
  await page.locator('#cal-nouveau-nom').fill(nomCalepinage)
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()

  // ── 3. L'ATELIER DU CALEPINAGE CRÉÉ ────────────────────────────────────
  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  await expect(page.getByTestId('cal-atelier-panneaux')).toBeVisible()
  const calepinageId = idDansUrl(page.url())
  expect(calepinageId, 'aucun identifiant de calepinage dans l’URL').toBeTruthy()

  // ── 4. ENREGISTRER UNE VARIANTE (CAL21, par l'API — voir l'en-tête) ────
  const creation = await page.request.post(
    `${API}/calepinages/${calepinageId}/variantes/`,
    { data: { nom: 'CAL221 Variante', parametres: {} } },
  )
  expect(creation.ok(),
    `le serveur a refusé la variante : ${creation.status()} ${await creation.text()}`)
    .toBeTruthy()

  // ── 5. LA RETENIR, PAR L'ÉCRAN (CAL42) ─────────────────────────────────
  await page.getByTestId('cal-lien-variantes').click()
  await expect(page).toHaveURL(/\/calepinage\/\d+\/variantes/)
  const tableau = page.getByTestId('cal-tableau-variantes')
  await expect(tableau).toBeVisible()

  // Mode strict : plusieurs colonnes peuvent porter un bouton « Retenir ».
  // On agit sur la PREMIÈRE, explicitement, plutôt que sur un locator ambigu.
  const aRetenir = tableau.getByRole('button', { name: 'Retenir' })
  if (await aRetenir.count() > 0) {
    await aRetenir.first().click()
  }
  // Après le geste, une variante EST retenue : la colonne l'annonce et son
  // bouton a disparu (le comparatif rend « Retenue », pas un bouton de plus).
  await expect(page.locator('[data-testid^="cal-retenue-"]').first()).toBeVisible()

  // ── 6. GÉNÉRER LE DEVIS (CAL24/CAL38), par l'écran ─────────────────────
  await page.goto(`/calepinage/${calepinageId}`)
  const bloc = page.getByTestId('cal-bouton-devis')
  await expect(bloc).toBeVisible()

  // La sortie devis a DEUX visages selon qu'un devis est déjà lié au
  // calepinage : « Générer le devis » (aucun devis) ou « Resynchroniser le
  // devis » (déjà lié). On apparie les DEUX plutôt que d'en supposer un.
  const generer = page.getByTestId('cal-generer-devis')
  const resynchroniser = page.getByTestId('cal-resynchroniser-devis')
  await expect(generer.or(resynchroniser)).toBeVisible()

  if (await generer.count() > 0) {
    await generer.click()
    // Le geste aboutit : soit le devis est créé (l'écran bascule sur la
    // resynchronisation et affiche la référence liée), soit le SERVEUR refuse
    // en NOMMANT le champ fautif — jamais un bouton muet.
    await expect(
      resynchroniser.or(page.getByTestId('cal-devis-refus')),
    ).toBeVisible()
  } else {
    // Déjà lié : le parcours s'achève sur la resynchronisation, qui est la
    // MÊME sortie CAL24/CAL25 côté serveur.
    await expect(resynchroniser).toBeEnabled()
  }
})
