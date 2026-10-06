/* ============================================================================
   CALX68 — BROUILLON LOCAL DE L'ATELIER, ET SA REPRISE.
   ----------------------------------------------------------------------------
   Constat de la tâche : `ToitureDesign.jsx` n'écrivait le document que sur le
   clic « Enregistrer le calepinage » — aucune sauvegarde périodique, rien
   récupérable après un rechargement accidentel ou un onglet fermé par erreur.
   Parité citée par le plan : PV*SOL sauvegarde le projet toutes les 5 minutes.

   CE FICHIER EST DE LA LOGIQUE PURE, SANS DOM NI BUILDER : `storage` (une
   interface `getItem`/`setItem`/`removeItem`, typiquement `window.localStorage`)
   et `obtenirLayout` (typiquement `() => builderApi.current?.serializeLayout()`)
   sont TOUJOURS injectés par l'appelant — c'est ce qui permet à
   `brouillon.test.mjs` de tourner sous `node:test`, sans jsdom, et à
   `ToitureDesign.jsx` de brancher le vrai `localStorage`/constructeur 3D.

   `localStorage` INDISPONIBLE (navigation privée à quota nul, SSR, storage qui
   lève) ⇒ AUCUNE exception ne remonte : toute fonction ci-dessous dégrade en
   silence (une écriture échouée renvoie `false`, une lecture échouée renvoie
   `null`) — jamais un écran cassé pour une fonctionnalité de confort.

   LA CLÉ — `(calepinage_id, utilisateur, layout_hash)`, LITTÉRALEMENT, où
   `layout_hash` est l'empreinte du document SERVEUR au moment où l'atelier a
   ouvert (jamais celle, changeante, du brouillon en cours d'édition) :
   `hashBase` reste donc CONSTANT pour toute une session d'édition, et TOUT
   brouillon trouvé sous cette clé est mécaniquement plus récent que le
   dernier enregistrement serveur connu — un enregistrement réussi change le
   layout servi, donc son empreinte, donc la clé, et rend l'ancien brouillon
   introuvable de lui-même. C'est ce qui satisfait « un brouillon plus récent
   que `updated_at` du serveur » sans avoir besoin de ce champ, absent du
   contrat `calepinage_design_context.json` (CAL231) que `ToitureDesign.jsx`
   lit déjà pour ouvrir l'atelier — et cette tâche ne déclare aucun fichier
   backend pour l'y ajouter. Un horodatage serveur, s'il est un jour
   disponible, reste accepté par `brouillonPertinent` (`misAJourServeur`) en
   filet de sécurité supplémentaire.

   LE REPLI SANS RÉGLAGE — `intervalleSecondes` vient des réglages utilisateur
   (lus par l'appelant, jamais ici) ; AUCUN réglage de ce nom n'existe encore
   dans le produit (grep `uxviews`/`reglages` sous `frontend/src` : rien de
   tel) — ce fichier n'invente donc AUCUN nombre par défaut : sans intervalle,
   `creerGestionnaireBrouillon` bascule sur le repli « à chaque geste ».
   Faute d'un canal d'événement venant du constructeur 3D pour
   `pushWorkshopHistory` (interne à `apps/web/src/scripts/roofPro11`, hors
   périmètre déclaré de cette tâche — seuls des fichiers `frontend/` sont
   listés), le repli est approché par une comparaison d'empreinte à intervalle
   court et FIXE : une écriture n'a lieu que si le document a RÉELLEMENT
   changé depuis la dernière écriture, jamais à chaque tic. `notifierGeste`
   reste aussi appelable DIRECTEMENT par l'appelant pour tout geste qu'il sait
   détecter lui-même (même sémantique, écriture immédiate si le document a
   changé).

   ACAL84 (C-ACAL-048) — QUATRE CORRECTIONS :
   * AUCUNE écriture sans geste : `dernierHashEcrit` est AMORCÉ au hash de la
     première sérialisation vue (au `demarrer()`, ou au premier appel qui
     obtient un document) — la scène hydratée depuis le serveur n'est pas un
     geste. La règle « écrire seulement si le document a changé » vaut dans
     les DEUX modes (minuterie réglée ou repli) et pour `enregistrerMaintenant` ;
   * la CLÉ porte l'empreinte « document » SERVEUR (`empreinte_document`,
     design-context ou réponse d'écriture — contrats
     `calepinage_design_context.json` / `calepinage_layout_section.json`),
     jamais un djb2 de l'objet client (l'ordre des clés jsonb diffère de
     celui de la sérialisation : la clé changeait sans changement réel) ;
   * à l'ouverture, `purgerBrouillonsOrphelins` retire les autres clés
     `calepinage_brouillon:<id>:<user>:*` (brouillons d'empreintes périmées) ;
   * la reprise ne BLOQUE plus le chargement : l'atelier boote sur la
     conception serveur, le bandeau reste non bloquant, et « Reprendre »
     mémorise le brouillon (`memoriserReprise`, sessionStorage) puis recharge —
     le boot suivant le consomme (`consommerReprise`) comme document de départ.
   ========================================================================== */

const PREFIXE_CLE = 'calepinage_brouillon'
const PREFIXE_REPRISE = 'calepinage_reprise'

// Repli sans réglage utilisateur — granularité de DÉTECTION d'un changement,
// PAS une cadence de sauvegarde annoncée à l'utilisateur (voir l'en-tête).
const PERIODE_SONDAGE_REPLI_MS = 4000

/** La clé de stockage — TOUJOURS les trois mêmes segments, dans cet ordre. */
export function construireCle({ calepinageId, utilisateurId, hashBase }) {
  const cal = calepinageId ?? 'sans-id'
  const util = utilisateurId ?? 'anonyme'
  const hash = hashBase ?? 'sans-hash'
  return `${PREFIXE_CLE}:${cal}:${util}:${hash}`
}

/**
 * Hachage déterministe (djb2) d'un objet JSON-sérialisable — repli PUR, sans
 * dépendance au serveur, utilisé pour dériver `hashBase` d'un `roof_layout`
 * quand aucune empreinte serveur n'existe déjà (calepinage jamais posé).
 * Jamais destiné à la sécurité : seulement à distinguer deux documents.
 */
export function hacherLayout(objet) {
  const texte = JSON.stringify(objet ?? null)
  let h = 5381
  for (let i = 0; i < texte.length; i += 1) {
    h = ((h * 33) ^ texte.charCodeAt(i)) >>> 0
  }
  return h.toString(16)
}

/**
 * Vérifie que `storage` est réellement accessible (présent ET utilisable —
 * Safari en navigation privée avec quota nul EXPOSE `localStorage` mais lève
 * à la première écriture). `null` dans tous les cas défaillants : c'est ce
 * qui garantit « aucune erreur, aucun bandeau » plus haut dans la chaîne.
 */
function stockageUtilisable(storage) {
  if (!storage) return null
  try {
    const sonde = '__calepinage_brouillon_sonde__'
    storage.setItem(sonde, '1')
    storage.removeItem(sonde)
    return storage
  } catch {
    return null
  }
}

/** Lit `{layout, horodatage}` sous `cle`, ou `null` — jamais une exception. */
export function lireBrouillon(storage, cle) {
  const s = stockageUtilisable(storage)
  if (!s) return null
  try {
    const brut = s.getItem(cle)
    if (!brut) return null
    const valeur = JSON.parse(brut)
    if (!valeur || typeof valeur !== 'object'
      || !('layout' in valeur) || !('horodatage' in valeur)) return null
    return valeur
  } catch {
    return null
  }
}

/** Écrit `{layout, horodatage}` sous `cle`. `false` sur tout échec — jamais une exception. */
export function ecrireBrouillon(storage, cle, layout, horodatage = new Date().toISOString()) {
  const s = stockageUtilisable(storage)
  if (!s) return false
  try {
    s.setItem(cle, JSON.stringify({ layout, horodatage }))
    return true
  } catch {
    return false
  }
}

/** Efface le brouillon sous `cle` (après un enregistrement serveur réussi). */
export function effacerBrouillon(storage, cle) {
  const s = stockageUtilisable(storage)
  if (!s) return false
  try {
    s.removeItem(cle)
    return true
  } catch {
    return false
  }
}

/**
 * Le brouillon PERTINENT pour ouvrir le bandeau de reprise, ou `null` — que
 * l'appelant décide seul de proposer (JAMAIS réhydraté automatiquement ici).
 * `misAJourServeur` (ISO, optionnel) est un filet de sécurité supplémentaire :
 * la clé (`hashBase`) fait déjà le travail décrit en en-tête, donc son
 * absence ne rend jamais un brouillon pourtant présent introuvable.
 */
export function brouillonPertinent({
  storage, calepinageId, utilisateurId, hashBase, misAJourServeur = null,
}) {
  const cle = construireCle({ calepinageId, utilisateurId, hashBase })
  const brouillon = lireBrouillon(storage, cle)
  if (!brouillon) return null
  if (misAJourServeur) {
    const tBrouillon = Date.parse(brouillon.horodatage)
    const tServeur = Date.parse(misAJourServeur)
    if (Number.isFinite(tBrouillon) && Number.isFinite(tServeur)
      && tBrouillon <= tServeur) return null
  }
  return brouillon
}

/**
 * Le planificateur d'écriture. `demarrer()`/`arreter()` suffisent à
 * l'appelant : le module choisit lui-même son mode.
 *   - `intervalleSecondes` réglé (> 0) : minuterie toutes les N secondes
 *     (parité PV*SOL, D-CALX 7 : ce nombre vient TOUJOURS de l'appelant,
 *     jamais deviné ici) ; ACAL84 : un tic n'écrit QUE si le document a
 *     changé depuis la référence (amorcée à l'ouverture, jamais un geste).
 *   - sinon (repli, aucun réglage) : sondage à `PERIODE_SONDAGE_REPLI_MS`,
 *     écriture SEULEMENT si le document a changé depuis la dernière écriture
 *     — approxime « à chaque geste d'historique » sans canal d'événement
 *     venant du constructeur (voir l'en-tête du fichier). `notifierGeste`
 *     applique la MÊME règle et reste appelable directement, pour tout appel
 *     qui saurait détecter un geste précis sans attendre le sondage.
 *   Les deux modes sont EXCLUSIFS : `notifierGeste()` est un no-op quand une
 *   minuterie est active, pour ne jamais écrire deux fois le même geste.
 */
export function creerGestionnaireBrouillon({
  storage,
  calepinageId,
  utilisateurId,
  hashBase,
  intervalleSecondes,
  obtenirLayout,
  minuteur = {
    definir: (fn, ms) => setInterval(fn, ms),
    annuler: (id) => clearInterval(id),
  },
}) {
  const cle = construireCle({ calepinageId, utilisateurId, hashBase })
  const intervalleActif = Number.isFinite(intervalleSecondes) && intervalleSecondes > 0
  let idMinuteur = null
  // ACAL84 — `null` tant qu'aucune sérialisation n'a été vue : la PREMIÈRE
  // vue AMORCE la référence (la scène telle qu'hydratée), jamais une écriture.
  let dernierHashEcrit = null

  const lireLayout = () => {
    try {
      return obtenirLayout?.() ?? null
    } catch {
      return null
    }
  }

  /* La règle UNIQUE des trois chemins d'écriture : rien sans document, la
     première vue amorce, et seul un document RÉELLEMENT changé s'écrit. */
  const ecrireSiChange = () => {
    const layout = lireLayout()
    if (layout == null) return false
    const h = hacherLayout(layout)
    if (dernierHashEcrit === null) {
      dernierHashEcrit = h
      return false
    }
    if (h === dernierHashEcrit) return false
    dernierHashEcrit = h
    return ecrireBrouillon(storage, cle, layout)
  }

  const enregistrerMaintenant = () => ecrireSiChange()

  const notifierGeste = () => {
    // La minuterie, quand elle est active, possède SEULE l'écriture — sans
    // quoi le même geste écrirait deux fois (une fois par le tic, une fois
    // par l'appel direct).
    if (intervalleActif) return false
    return ecrireSiChange()
  }

  return {
    cle,
    demarrer() {
      if (idMinuteur != null) return
      // ACAL84 — amorce la référence sur la scène d'ouverture (aucune écriture).
      if (dernierHashEcrit === null) {
        const layout = lireLayout()
        if (layout != null) dernierHashEcrit = hacherLayout(layout)
      }
      idMinuteur = intervalleActif
        ? minuteur.definir(enregistrerMaintenant, intervalleSecondes * 1000)
        : minuteur.definir(notifierGeste, PERIODE_SONDAGE_REPLI_MS)
    },
    arreter() {
      if (idMinuteur != null) {
        minuteur.annuler(idMinuteur)
        idMinuteur = null
      }
    },
    notifierGeste,
    enregistrerMaintenant,
    effacer: () => effacerBrouillon(storage, cle),
  }
}

/**
 * ACAL84 — retire les brouillons ORPHELINS de ce calepinage et de cet
 * utilisateur : toute clé `calepinage_brouillon:<id>:<user>:*` autre que celle
 * de l'empreinte serveur courante (`hashBase`). Rend le nombre de clés
 * retirées ; `0` sur tout échec — jamais une exception. Le storage doit
 * exposer `length`/`key(i)` (contrat Web Storage) ; sinon rien n'est purgé.
 */
export function purgerBrouillonsOrphelins({ storage, calepinageId, utilisateurId, hashBase }) {
  const s = stockageUtilisable(storage)
  if (!s || typeof s.key !== 'function') return 0
  const courante = construireCle({ calepinageId, utilisateurId, hashBase })
  const prefixe = courante.slice(0, courante.lastIndexOf(':') + 1)
  try {
    const aRetirer = []
    for (let i = 0; i < s.length; i += 1) {
      const cle = s.key(i)
      if (typeof cle === 'string' && cle.startsWith(prefixe) && cle !== courante) {
        aRetirer.push(cle)
      }
    }
    for (const cle of aRetirer) s.removeItem(cle)
    return aRetirer.length
  } catch {
    return 0
  }
}

/** ACAL84 — la clé de la reprise demandée (sessionStorage, consommée au boot). */
function cleReprise({ calepinageId, utilisateurId }) {
  return `${PREFIXE_REPRISE}:${calepinageId ?? 'sans-id'}:${utilisateurId ?? 'anonyme'}`
}

/** ACAL84 — mémorise le document à reprendre au PROCHAIN boot. `false` sur échec. */
export function memoriserReprise(storage, { calepinageId, utilisateurId }, layout) {
  const s = stockageUtilisable(storage)
  if (!s || layout == null) return false
  try {
    s.setItem(cleReprise({ calepinageId, utilisateurId }), JSON.stringify({ layout }))
    return true
  } catch {
    return false
  }
}

/** ACAL84 — lit ET retire la reprise mémorisée : `{layout}` ou `null`. */
export function consommerReprise(storage, { calepinageId, utilisateurId }) {
  const s = stockageUtilisable(storage)
  if (!s) return null
  const cle = cleReprise({ calepinageId, utilisateurId })
  try {
    const brut = s.getItem(cle)
    s.removeItem(cle)
    if (!brut) return null
    const valeur = JSON.parse(brut)
    return valeur && typeof valeur === 'object' && valeur.layout != null ? valeur : null
  } catch {
    return null
  }
}
