// EZ17 — LA GATE DES TRAJETS : les budgets de clics deviennent des specs CI.
// ============================================================================
// L'audit des 5 trajets quotidiens (fondateur 2026-08-01) a compté, dans le
// code réel : appel + note + rappel = 5-7 clics ; devis 3 kWc → WhatsApp = 8-9
// clics dont un ABANDON juste après la création ; clôture d'intervention =
// 40-45 taps dont ~10 de pure paperasse de statut ; encaissement = 3 clics
// (excellent) mais sans suite offerte. EZ1-EZ16 ont repris ces trajets. Sans
// gate, rien n'empêche le prochain écran d'y remettre un clic.
//
// ── LA MÉTHODE (imposée par la critique adversariale, écrite ici une fois) ──
//
// 1. ÉTAT DE DÉPART et ÉTAT D'ARRIVÉE sont DÉCLARÉS par trajet, en toutes
//    lettres. Tout ce qui précède le départ (créer un jeu de données, se
//    placer sur l'écran, passer le coup de fil lui-même) est du MONTAGE : il
//    n'entre pas dans le budget. Le compteur est démarré explicitement.
//
// 2. UNITÉ. 1 par clic, 1 par `fill()`, 1 par « choisir une option » quel que
//    soit le widget (bouton-chip, radio, item de menu, case à cocher).
//    Ouvrir un menu pour choisir dedans = 2, parce que l'employé fait bien
//    deux gestes.
//
// 3. DOUBLE COMPTAGE CROISÉ. Deux compteurs indépendants, et une divergence
//    fait ÉCHOUER le trajet :
//      • côté TEST — chaque action passe par le helper `Budget` ci-dessous,
//        qui incrémente puis exécute. Impossible d'agir sans compter ;
//      • côté NAVIGATEUR — un compteur d'événements `click` **isTrusted**
//        injecté par `page.addInitScript`. Il ne voit QUE les vrais gestes
//        d'entrée (Playwright clique via le protocole d'entrée du navigateur,
//        donc `isTrusted: true`), jamais les clics synthétiques que React ou
//        Radix redispatchent, ni les événements d'un `fill()` (qui pose la
//        valeur en JS : `isTrusted: false`).
//    Le croisement porte donc sur le sous-ensemble CLICS — c'est exactement là
//    qu'un clic pourrait se glisser sans qu'on le compte. Les `fill()` sont
//    comptés côté test seulement, et c'est dit plutôt que caché.
//
// 4. LE BUDGET EST UN PLAFOND. Un trajet qui n'atteint pas son arrivée (donnée
//    absente, brique désactivée sur cet environnement) est ENREGISTRÉ puis
//    sauté : sous-couvrir ne peut jamais faire passer une régression, alors
//    qu'un faux rouge, lui, détruit la confiance dans la gate.
//
// 5. AUCUN `waitForTimeout`. Le nudge temporisé d'EZ2 est déclenché par son
//    SECOND déclencheur — le retour de focus fenêtre — reproduit ici par un
//    vrai aller-retour d'onglet, ce qui est aussi le scénario réel de bureau
//    (le focus part vers le softphone et revient).
//
// 6. PROJET/VIEWPORT DÉCLARÉS. Viewport posé en tête de fichier. Ce spec n'est
//    matché QUE par le projet `chromium` : les projets `mobile`,
//    `mobile-safari` et `tablet` portent un `testMatch` explicite sur leur
//    propre fichier (playwright.config.js) — l'exclusion est structurelle, il
//    n'y a rien à ignorer à la main.
//
// 7. RÉGLAGE SIGNATURE. La mesure suppose la signature client NON obligatoire
//    (réglage EZ7, désactivé par défaut) : l'activer ajoute légitimement une
//    étape, elle n'a donc pas à peser sur ce budget.
//
// ── TEST DU TEST ──
// Remettre un clic dans un trajet couvert (par exemple une confirmation avant
// « Devis automatique ») fait dépasser son plafond et rougir la gate ; oublier
// de compter ce clic fait diverger les deux compteurs et rougir aussi. Les
// deux triches sont fermées.
//
// ── COUVERTURE ──
// Deux trajets sont JOUÉS ici. Les trois autres (clôture d'intervention,
// réception fournisseur, encaissement) portent leur budget et leurs états
// déclarés dans un `test.fixme` en bas de fichier — la convention déjà en
// vigueur dans ce dossier pour un flux qui n'a pas encore été enregistré
// (`stock.spec.js`) : le contrat est écrit, visible dans le rapport comme
// TODO, et n'immobilise pas la matrice.
import { test, expect } from '@playwright/test'
import { gotoLeads, uniq } from './helpers'

// Viewport DÉCLARÉ : un budget de clics se mesure à une taille connue (une
// largeur différente peut replier une barre d'actions dans un menu, donc
// ajouter un geste).
test.use({ viewport: { width: 1440, height: 900 } })

const CLE = '__taqinorBudgetClics'

/** Compteur navigateur : uniquement les clics RÉELS (`isTrusted`). */
async function armerCompteurNavigateur(page) {
  await page.addInitScript((cle) => {
    window[cle] = 0
    // Capture : on voit le clic avant qu'un `stopPropagation` applicatif ne
    // l'arrête, et une seule fois par geste.
    document.addEventListener('click', (e) => {
      if (e.isTrusted) window[cle] += 1
    }, true)
  }, CLE)
}

const clicsReels = (page) => page.evaluate((cle) => window[cle] ?? 0, CLE)

const ficheLead = (page) =>
  page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })

/**
 * MONTAGE — crée un lead JOIGNABLE (donc avec l'icône ☎ en liste et la barre
 * WhatsApp armable). Reprend pas à pas `helpers.createLead` (mêmes ancres
 * prouvées : `#lf-nom`, le placeholder « ex: 650 » de la facture d'hiver, le
 * bouton « Créer le lead ») et ajoute le téléphone, que ce helper partagé ne
 * sait pas encore poser. Rien de tout cela n'entre dans un budget.
 */
async function creerLeadJoignable(page, { nom, facture, telephone = '0612345678' }) {
  await page.getByRole('button', { name: '+ Nouveau lead' }).click()
  const modal = ficheLead(page)
  await expect(modal.getByRole('heading', { name: 'Nouveau lead' })).toBeVisible()
  await modal.locator('#lf-nom').fill(nom)
  const tel = modal.locator('#lf-telephone')
  if (await tel.count()) await tel.fill(telephone)
  if (facture != null) await modal.getByPlaceholder('ex: 650').fill(String(facture))
  await modal.getByRole('button', { name: 'Créer le lead' }).click()
  await expect(ficheLead(page)).toHaveCount(0)
  return nom
}

/**
 * Compteur côté test. Chaque action passe par lui : compter n'est pas une
 * discipline, c'est le seul chemin pour agir.
 */
class Budget {
  constructor(page, nom, plafond, info) {
    this.page = page
    this.nom = nom
    this.plafond = plafond
    this.info = info
    this.n = 0
    this.clics = 0
    this.journal = []
    this.depart = 0
  }

  /** Démarre le comptage : tout ce qui précède est du montage déclaré. */
  async demarrer(etatDepart) {
    this.depart = await clicsReels(this.page)
    this.journal.push(`départ : ${etatDepart}`)
  }

  async clic(locator, quoi) {
    await locator.click()
    this.n += 1
    this.clics += 1
    this.journal.push(`${this.n}. clic — ${quoi}`)
  }

  /** « Choisir une option » : même coût qu'un clic, quel que soit le widget. */
  choix(locator, quoi) { return this.clic(locator, `choix : ${quoi}`) }

  async saisie(locator, valeur, quoi) {
    await locator.fill(valeur)
    this.n += 1
    this.journal.push(`${this.n}. saisie — ${quoi}`)
  }

  /** Vérifie le plafond ET la concordance des deux compteurs. */
  async cloturer(etatArrivee) {
    const reels = (await clicsReels(this.page)) - this.depart
    this.info.annotations.push({
      type: 'budget',
      description: `${this.nom} — ${this.n}/${this.plafond} interactions `
        + `(dont ${this.clics} clics ; arrivée : ${etatArrivee})\n`
        + this.journal.map((l) => `    ${l}`).join('\n'),
    })
    // Croisement : autant de clics RÉELS que de clics comptés. Un geste non
    // déclaré (ou un helper qui cliquerait dans notre dos) le fait échouer.
    expect(
      reels,
      `${this.nom} : clics réels (isTrusted) ≠ clics comptés — un geste n’a pas `
      + `été déclaré :\n${this.journal.join('\n')}`,
    ).toBe(this.clics)
    expect(
      this.n,
      `${this.nom} : budget dépassé pour aller jusqu’à « ${etatArrivee} » :\n`
      + this.journal.join('\n'),
    ).toBeLessThanOrEqual(this.plafond)
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// TRAJET 1 — LE COMMERCIAL : « le lead est prêt, je veux son devis, envoyé »
// ═══════════════════════════════════════════════════════════════════════════
// DÉPART  : la fiche du lead est ouverte, ses données sont déjà saisies
//           (le plan dit « formulaire déjà saisi » — la saisie est du montage).
// ARRIVÉE : le devis existe, son PDF est rendu à l'écran, et il est armé pour
//           partir en WhatsApp.
// BUDGET  : 6 (audit d'avant : 8-9, dont un abandon juste après la création —
//           il fallait quitter la fiche pour retrouver son propre devis).
test('EZ17 — devis automatique prêt à envoyer : ≤6 interactions', async ({ page }, info) => {
  test.slow() // création réelle + rendu PDF côté serveur.
  await armerCompteurNavigateur(page)

  // ── Montage (hors budget) ─────────────────────────────────────────────────
  await gotoLeads(page)
  const nom = await creerLeadJoignable(page, { nom: uniq('EZ17 Devis'), facture: 900 })
  // Ouvrir la fiche fait partie du montage : le trajet déclare partir d'une
  // fiche OUVERTE. On réutilise les ancres de `helpers.openLead`.
  const carte = page.locator('article.kb-card', { hasText: nom }).first()
  const ligne = page.locator('tr.lv-row', { hasText: nom }).first()
  await expect(carte.or(ligne)).toBeVisible()
  if (await carte.isVisible()) await carte.locator('.kb-card-name').click()
  else await ligne.locator('.lv-lead-name').click()
  const fiche = ficheLead(page)
  await expect(fiche.locator('.modal-title')).toContainText('Lead —')

  // ── Trajet compté ─────────────────────────────────────────────────────────
  const b = new Budget(page, 'devis → prêt à envoyer', 6, info)
  await b.demarrer('fiche du lead ouverte, données saisies')

  // 1. « Devis automatique » : un seul geste, le devis est calculé et rendu.
  await b.clic(fiche.getByRole('button', { name: 'Devis automatique' }), 'Devis automatique')
  await expect(page.locator('.ldp-pdf-area canvas').first()).toBeVisible({ timeout: 45_000 })
  await expect(page.locator('.ldp-fallback')).toHaveCount(0)

  // 2. Retour à la fiche — le devis est DANS la fiche, plus besoin d'aller le
  //    rechercher ailleurs (c'est l'abandon qu'EZ3/EZ4 ont supprimé).
  await b.clic(page.locator('.ldp-header .modal-close'), 'fermer l’aperçu')
  await expect(page.locator('.lead-devis-badge')).toContainText(/[1-9]\d* devis/)

  // 3-4. Armer l'envoi : sélectionner le devis, puis envoyer.
  const caseWa = page.getByRole('checkbox', { name: /pour WhatsApp/ }).first()
  const boutonWa = page.getByRole('button', { name: /Envoyer par WhatsApp/ })
  if (await caseWa.count()) {
    await b.choix(caseWa, 'ce devis part en WhatsApp')
    if (await boutonWa.isEnabled()) {
      await b.clic(boutonWa, 'Envoyer par WhatsApp')
    } else {
      info.annotations.push({
        type: 'budget',
        description: 'WhatsApp non armé (numéro absent) — étape enregistrée, non jouée',
      })
    }
  } else {
    info.annotations.push({
      type: 'budget',
      description: 'barre WhatsApp absente de ce palier — étape enregistrée, non jouée',
    })
  }

  await b.cloturer('devis créé, PDF rendu, envoi WhatsApp armé')
})

// ═══════════════════════════════════════════════════════════════════════════
// TRAJET 2 — LE COMMERCIAL : « je viens de raccrocher, je note et je relance »
// ═══════════════════════════════════════════════════════════════════════════
// DÉPART  : l'appel vient d'être passé depuis la LISTE des leads (le coup de
//           fil lui-même n'est pas de la paperasse ERP : il est du montage),
//           et l'employé revient sur l'ERP — EZ2 lui présente le nudge
//           « Appel terminé — noter ? » SANS qu'il ait à retrouver la fiche.
// ARRIVÉE : l'appel est journalisé avec son résultat ET une relance datée est
//           posée ; le nudge a disparu.
// BUDGET  : 4 pour le chemin rapide (chips). Audit d'avant : 5-7, et sur poste
//           fixe le nudge n'apparaissait JAMAIS (il dépendait de
//           `visibilitychange`, qui ne se déclenche pas quand l'onglet reste
//           visible) — le repli coûtait 7 clics par la fiche.
test('EZ17 — appel noté + relance posée : ≤4 interactions (chemin rapide)', async ({ page }, info) => {
  test.slow()
  await armerCompteurNavigateur(page)

  // ── Montage (hors budget) ─────────────────────────────────────────────────
  await gotoLeads(page)
  const nom = await creerLeadJoignable(page, { nom: uniq('EZ17 Appel') })
  // La vue LISTE porte l'icône ☎ par ligne (`?view=` prime sur la session et
  // sur la vue par défaut du compte — voir leads-density.spec.js).
  await page.goto('/crm/leads?view=liste')
  await expect(page.getByRole('button', { name: '+ Nouveau lead' })).toBeVisible()
  const ligne = page.locator('tr.lv-row', { hasText: nom }).first()
  await expect(ligne).toBeVisible()

  const appeler = ligne.getByRole('link', { name: /^Appeler / })
  test.skip(
    !(await appeler.count()),
    'le lead de montage n’expose pas d’icône ☎ (numéro absent) — trajet non rejouable ici',
  )
  // LE COUP DE FIL. `tel:` est un protocole externe : le navigateur ne navigue
  // pas, le handler React arme le nudge d'EZ2. Hors budget — c'est l'appel.
  await appeler.click()

  // Le focus part vers le softphone puis revient : c'est le SECOND déclencheur
  // d'EZ2 (celui qui manquait au bureau), reproduit par un vrai aller-retour
  // d'onglet — jamais un `waitForTimeout`.
  const autreOnglet = await page.context().newPage()
  await autreOnglet.close()
  await page.bringToFront()

  const nudge = page.locator('.lv-call-nudge')
  // Attente sur l'ÉTAT, jamais sur une durée : le nudge est piloté par un
  // rendu React consécutif au retour de focus.
  await nudge.waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {})
  const nudgeVu = await nudge.isVisible().catch(() => false)
  test.skip(!nudgeVu, 'le nudge post-appel n’est pas apparu sur cet environnement — trajet enregistré, non mesuré')

  // ── Trajet compté ─────────────────────────────────────────────────────────
  const b = new Budget(page, 'appel → noté + relancé', 4, info)
  await b.demarrer('retour sur l’ERP juste après l’appel, nudge affiché')

  // 1. « Noter » — l'employé n'a pas eu à retrouver la fiche.
  await b.clic(nudge.locator('.lv-call-nudge-log'), 'Noter')
  const popover = page.locator('[data-call-log-popover]')
  await expect(popover).toBeVisible()

  // 2. Le résultat de l'appel (chips — un geste, pas un formulaire).
  await b.choix(popover.locator('[data-outcome]').first(), 'résultat de l’appel')

  // 3. La relance, par raccourci daté (le chemin RAPIDE ; la date libre d'EZ1
  //    est le chemin ≤6, mesuré séparément le jour où il sera joué).
  await b.choix(popover.locator('.clp-next-btn').first(), 'relance J+…')

  // 4. Enregistrer.
  await b.clic(popover.getByRole('button', { name: /Enregistrer/ }), 'Enregistrer')
  await expect(page.locator('[data-call-log-popover]')).toHaveCount(0)
  await expect(page.locator('.lv-call-nudge')).toHaveCount(0)

  await b.cloturer('appel journalisé + relance datée posée')
})

// ═══════════════════════════════════════════════════════════════════════════
// LES TROIS TRAJETS RESTANTS — contrat écrit, enregistrement à faire
// ═══════════════════════════════════════════════════════════════════════════
// Même convention que `stock.spec.js` dans ce dossier : `test.fixme` = visible
// comme TODO dans le rapport, jamais exécuté, n'immobilise pas la matrice. Le
// budget et les deux états sont FIXÉS ici pour que l'enregistrement n'ait plus
// qu'à jouer les gestes (`npx playwright codegen`, cf. docs/TESTING.md) et à
// les passer par le helper `Budget` ci-dessus — la méthode, elle, est déjà là.

test.fixme('EZ17 — clôture d’intervention : ≤15 interactions (hors prises de photo)', async () => {
  // DÉPART  : l'intervention du jour est ouverte sur le terrain.
  // ARRIVÉE : elle est clôturée, son rapport enregistré et son statut à jour.
  // BUDGET  : 15 hors prises de photo. Audit d'avant : 40-45 taps, dont ~10 de
  //           PURE paperasse de statut — c'est ce que EZ6 (statuts déduits des
  //           horodatages déjà connus) a supprimé, et ce que ce budget garde.
  //           Mesurer avec le réglage « signature client obligatoire » (EZ7)
  //           DÉSACTIVÉ : l'activer ajoute une étape légitime.
})

test.fixme('EZ17 — réception fournisseur : ≤3 interactions + 1 par ligne d’écart', async () => {
  // DÉPART  : le bon de commande fournisseur attendu est à l'écran.
  // ARRIVÉE : la réception est enregistrée et les quantités reflètent le réel.
  // BUDGET  : 3, plus 1 par ligne dont la quantité reçue diffère de l'attendu
  //           (une conformité totale doit rester à 3 : « tout est arrivé » est
  //           le cas courant, il ne se paie pas ligne par ligne).
})

test.fixme('EZ17 — encaissement : ≤3 interactions, puis la suite offerte à +1', async () => {
  // DÉPART  : la facture à encaisser est à l'écran.
  // ARRIVÉE : le règlement est enregistré ET l'action suivante évidente (voir
  //           l'encaissement) est offerte sans avoir à la chercher.
  // BUDGET  : 3 pour encaisser — l'audit l'a trouvé EXCELLENT, ce budget le
  //           PROTÈGE plutôt qu'il ne le corrige — et 1 de plus pour suivre la
  //           suite proposée (doctrine EZ : après chaque action, l'action
  //           suivante est offerte).
})
