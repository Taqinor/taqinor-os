// QJR523 — UN SEUL couple de mappeurs lignes serveur ⇄ écran du générateur.
//
// Avant : trois constructions divergentes dans DevisGenerator.jsx — le mappeur
// de la réouverture `?edit=` (gardait optionnelle / type / variante / verrous /
// ordre mais PERDAIT groupe_*), celui d'un modèle appliqué (handlePresetApplied :
// l'inverse) et le `lignesPayload` inline de persisterDevis. `role_devis` ne
// survivait à aucun : `remplacer_lignes` re-devinait alors le rôle
// (domain/lignes.py) et écrasait un rôle posé par la composition (ex.
// 'onduleur_offgrid').
//
// Champs portés dans les DEUX sens : produit, designation, quantite, prix
// (HT serveur ⇄ TTC écran), taux_tva, optionnelle, type_ligne, ordre, variante,
// prix_manuel, quantite_manuelle, groupe_index / groupe_label, role_devis,
// remise (QJR529 — la remise PAR LIGNE stockée, '0' par défaut : l'envoyer à
// '0' en dur faisait monter le total client en silence au 1er enregistrement),
// lot (QJR667 — rattachement à un lot multi-sites posé par « Lots /
// multi-sites » ; sans lui, replace-lines recréait les lignes hors lot),
// ligne_composee ⇄ compose (ERR-QJR570 — provenance composée / ajoutée à la
// main, persistée : D-QJR5-4), tva_base_legale ⇄ tvaBaseLegale (AGR218 —
// la base légale d'une exonération à 0 %, saisie, jamais pré-remplie).
//
// Module PUR (aucun React, aucun import.meta) : exécuté par `node --test`.
import { ttcExactFromHt, htFromTtc, tauxTvaOuDefaut } from '../solar.js'

const TYPES_STRUCTURE = new Set(['section', 'note'])

/**
 * ERR-QJR570 (D-QJR5-4) — une ligne serveur est-elle COMPOSÉE par le moteur ?
 * La provenance PERSISTÉE (`ligne_composee`) fait foi : true ⇒ composée (une
 * recomposition la remplace), false ⇒ ajoutée à la main (gardée). Absente ou
 * null (lignes antérieures, aucun backfill) ⇒ règle de repli : une ligne
 * produit relue sans verrou ni option est tenue pour composée.
 */
function composeRelu(l) {
  if ((l.type_ligne ?? 'produit') !== 'produit') return false
  if (l.ligne_composee === true) return true
  if (l.ligne_composee === false) return false
  return !l.prix_manuel && !l.quantite_manuelle && !l.optionnelle
}

/**
 * Lignes servies par l'API (HT, snake_case) → lignes d'écran (TTC, forme
 * attendue par `withKeys` du générateur). Triées par (ordre, id) pour que les
 * sections/notes reviennent à leur place.
 * @param {Array<object>} lignes  lignes serveur (devis ou modèle appliqué)
 * @param {number|string} [tauxDevis]  taux du devis, repli d'une ligne sans taux
 */
export function lignesServeurVersEcran(lignes, tauxDevis) {
  if (!Array.isArray(lignes)) return []
  return lignes
    .slice()
    .sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0) || (a.id ?? 0) - (b.id ?? 0))
    .map((l) => {
      // ATOT20 — UNE règle avec le serveur : une ligne relue SANS taux est
      // chiffrée au taux du DEVIS (le serveur et le PDF lui appliquent ce
      // taux) ; jamais celui de la fiche produit (`produit_tva`), qui changeait
      // le total au premier « Enregistrer » sans saisie. Les lignes NOUVELLES
      // naissent avec le taux de leur produit (serveur `creer_ligne`,
      // TVA-LIGNE). 0 % reste 0 % (AGR216).
      const taux = tauxTvaOuDefaut(l.taux_tva ?? tauxDevis, 20)
      const produit = l.produit ?? l.produit_id
      // Marqueur d'écran `compose` ⇄ provenance persistée `ligne_composee`
      // (ERR-QJR570) : composée ⇒ remplacée par la prochaine recomposition,
      // ajoutée à la main ⇒ gardée.
      const compose = composeRelu(l)
      return {
        produit: String(produit ?? ''),
        designation: l.designation ?? '',
        quantite: l.quantite == null ? '1' : String(parseFloat(l.quantite) || 0),
        // ERR-QAH-FIG-EDITION-PU-TTC-ARRONDI — prix PERSISTÉ : TTC au centime,
        // jamais arrondi au dirham (sinon rouvrir change le total et
        // ré-enregistrer modifie les prix en silence).
        prix_unit_ttc: String(ttcExactFromHt(l.prix_unitaire ?? l.prix_unit_ht ?? 0, taux)),
        taux_tva: String(taux),
        remise: String(parseFloat(l.remise) || 0),
        optionnelle: !!l.optionnelle,
        typeLigne: l.type_ligne ?? 'produit',
        compose,
        variante: l.variante ?? '',
        prixManuel: !!l.prix_manuel,
        quantiteManuelle: !!l.quantite_manuelle,
        // AGNR16 — prix RELU du serveur : l'effet de tarif de l'écran
        // (`[clientId, lines.length]`) ne le réécrit jamais sans geste. Marqueur
        // d'écran seulement, jamais envoyé (absent de `lignesEcranVersPayload`).
        prixRelu: true,
        groupeIndex: l.groupe_index ?? null,
        groupeLabel: l.groupe_label ?? '',
        role_devis: l.role_devis ?? '',
        lot: l.lot ?? null,
        // AGR218 (contrat AGR200) — base légale d'un taux à 0 %, telle que
        // saisie (vide = aucune).
        tvaBaseLegale: l.tva_base_legale ?? '',
        // R2 (fondateur 28/10/2026) — groupe CLIENT servi par le serveur
        // (`groupe_client` : 'tableau_ci' | 'installation_ci' | null), calculé
        // du rôle C&I du produit. Marqueur d'écran seulement : l'écran regroupe
        // à l'AFFICHAGE (`sequenceGroupesClient`), jamais envoyé.
        groupeClient: l.groupe_client ?? null,
      }
    })
}

// ── R2 — en-têtes de groupe client du tableau des lignes ─────────────────────
// Les composants d'un même `groupe_client` (Tableau de protection AC/DC,
// Installation clé en main) s'affichent SOUS un en-tête de section qui dit le
// total HT du groupe, chaque composant restant éditable ligne à ligne. L'ordre
// PERSISTÉ (`ordre` = index du state) ne bouge pas : seule la séquence
// d'affichage rapproche les composants à la place du premier.
export const LIBELLES_GROUPE_CLIENT = Object.freeze({
  tableau_ci: 'Tableau de protection AC/DC',
  installation_ci: 'Installation clé en main',
})

// Total HT d'une ligne pour l'en-tête de groupe : APRÈS remise globale quand
// le miroir de répartition (`lignesRemiseesTtc[i]`, TTC de ligne remisé,
// aligné sur `lines`) en donne une, comme le PDF ; sinon le catalogue.
function htLigne(l, ttcRemise) {
  const taux = l.taux_tva ?? 20
  if (Number.isFinite(ttcRemise)) return parseFloat(htFromTtc(ttcRemise, taux)) || 0
  const qte = parseFloat(l.quantite) || 0
  return qte * (parseFloat(htFromTtc(l.prix_unit_ttc, taux)) || 0)
}

/**
 * Séquence d'affichage des lignes d'écran : `{ kind: 'entete', groupe,
 * libelle, totalHt, nb }` avant la PREMIÈRE ligne d'un groupe, suivi de ses
 * `{ kind: 'ligne', index }` (index dans `lines`, pour les gestes et la remise
 * répartie), puis les lignes hors groupe à leur place. Sans aucun
 * `groupeClient` : une ligne par index, dans l'ordre — DOM inchangé.
 * @param {Array<object>} lines  lignes d'écran
 * @param {Array<number|null>} [lignesRemiseesTtc]  TTC de ligne après remise
 *   globale, aligné sur `lines` (null = ligne hors totaux) ; absent = catalogue
 */
export function sequenceGroupesClient(lines, lignesRemiseesTtc) {
  const liste = Array.isArray(lines) ? lines : []
  const remises = Array.isArray(lignesRemiseesTtc) ? lignesRemiseesTtc : []
  const groupes = new Map()
  liste.forEach((l, index) => {
    const g = l && l.groupeClient && LIBELLES_GROUPE_CLIENT[l.groupeClient] ? l.groupeClient : null
    if (!g) return
    if (!groupes.has(g)) groupes.set(g, { indexes: [], totalHt: 0 })
    const entree = groupes.get(g)
    entree.indexes.push(index)
    entree.totalHt += estStructure(l) ? 0 : htLigne(l, remises[index])
  })
  if (groupes.size === 0) return liste.map((_l, index) => ({ kind: 'ligne', index }))
  const sequence = []
  const places = new Set()
  liste.forEach((l, index) => {
    if (places.has(index)) return
    const g = l && l.groupeClient && groupes.has(l.groupeClient) ? l.groupeClient : null
    if (!g) {
      sequence.push({ kind: 'ligne', index })
      return
    }
    const entree = groupes.get(g)
    sequence.push({ kind: 'entete', groupe: g, libelle: LIBELLES_GROUPE_CLIENT[g],
      totalHt: Math.round(entree.totalHt * 100) / 100, nb: entree.indexes.length })
    entree.indexes.forEach((i) => { places.add(i); sequence.push({ kind: 'ligne', index: i }) })
  })
  return sequence
}

// ── R2 (revue coordinatrice) — Monter/Descendre sur la SÉQUENCE AFFICHÉE ──
// Les composants d'un groupe forment un BLOC à l'écran. Un geste travaille sur
// ce que l'utilisateur voit : un composant monte/descend DANS son bloc ; au
// bord du bloc, c'est le bloc entier qui passe par-dessus la ligne voisine ;
// une ligne hors groupe saute un bloc entier. Après le geste, l'ordre PERSISTÉ
// devient l'ordre affiché (ce qui se voit est ce qui s'enregistre). Sans
// groupe : l'échange de voisins d'hier, à l'identique.

/** Unités affichées : `[{ groupe, indexes }]` — un bloc par groupe, un singleton par ligne libre. */
function unitesAffichees(lines) {
  const unites = []
  for (const pas of sequenceGroupesClient(lines)) {
    if (pas.kind === 'entete') { unites.push({ groupe: pas.groupe, indexes: [] }); continue }
    const derniere = unites[unites.length - 1]
    const g = lines[pas.index]?.groupeClient
    if (derniere && derniere.groupe && derniere.groupe === g) derniere.indexes.push(pas.index)
    else unites.push({ groupe: null, indexes: [pas.index] })
  }
  return unites
}

/**
 * Nouvelle liste de lignes (ordre persisté = ordre affiché) après « monter »
 * (`delta` = -1) ou « descendre » (+1) la ligne `key` ; la même liste si le
 * geste est hors bornes ou la clé inconnue.
 */
export function deplacerDansSequence(lines, key, delta) {
  const liste = Array.isArray(lines) ? lines : []
  const idx = liste.findIndex((l) => l._key === key)
  if (idx < 0 || !delta) return liste
  const unites = unitesAffichees(liste)
  const u = unites.findIndex((un) => un.indexes.includes(idx))
  if (u < 0) return liste
  const unite = unites[u]
  const pos = unite.indexes.indexOf(idx)
  const cible = pos + delta
  if (unite.groupe && cible >= 0 && cible < unite.indexes.length) {
    const indexes = unite.indexes.slice()
    ;[indexes[pos], indexes[cible]] = [indexes[cible], indexes[pos]]
    unites[u] = { ...unite, indexes }
  } else {
    const cu = u + delta
    if (cu < 0 || cu >= unites.length) return liste
    ;[unites[u], unites[cu]] = [unites[cu], unites[u]]
  }
  return unites.flatMap((un) => un.indexes).map((i) => liste[i])
}

/**
 * Bornes des gestes par index de `lines` : `{ haut, bas }` — vrai quand
 * « monter » / « descendre » déplace réellement quelque chose à l'écran.
 */
export function bornesDeplacement(lines) {
  const liste = Array.isArray(lines) ? lines : []
  const unites = unitesAffichees(liste)
  const bornes = liste.map(() => ({ haut: false, bas: false }))
  unites.forEach((un, u) => {
    un.indexes.forEach((i, pos) => {
      bornes[i] = { haut: pos > 0 || u > 0, bas: pos < un.indexes.length - 1 || u < unites.length - 1 }
    })
  })
  return bornes
}

const estStructure = (l) => TYPES_STRUCTURE.has(l.typeLigne)

// Les lignes d'écran qui PARTENT au serveur (même filtre que le payload) :
// l'index `lignes[i]` d'un refus serveur se lit dans CETTE liste.
const lignesEnvoyees = (lines) => (lines || []).filter((l) => (estStructure(l)
  ? !!(l.designation || '').trim()
  : (l.produit && parseFloat(l.quantite) > 0)))

/**
 * Lignes d'écran → corps `lignes` de replace-lines / devis atomique.
 * Retient les produits utilisables (produit + quantité > 0) et les
 * sections/notes à intitulé non vide ; `ordre` = position visuelle.
 * @param {Array<object>} lines  lignes d'écran
 * @param {{multiMode?: string}} [opts]  groupes villa envoyés seulement en mode 'villas'
 */
// ATOT28 — le HT ENVOYÉ d'une ligne : le HT catalogue d'origine tel quel
// (`prixHtOrigine`) tant que le vendeur n'a pas tapé de prix et que le TTC
// affiché est toujours celui qui en dérive (même taux) ; sinon le HT re-dérivé
// du TTC saisi au taux DE LA LIGNE, comme avant.
function prixUnitaireEnvoye(l) {
  const taux = l.taux_tva ?? 20
  const origine = l.prixHtOrigine
  if (!l.prixManuel && origine != null && origine !== '') {
    const ttcOrigine = ttcExactFromHt(origine, taux)
    if (Math.abs(ttcOrigine - (parseFloat(l.prix_unit_ttc) || 0)) < 0.005) {
      return (parseFloat(origine) || 0).toFixed(2)
    }
  }
  return htFromTtc(l.prix_unit_ttc, taux)
}

export function lignesEcranVersPayload(lines, { multiMode } = {}) {
  const villas = multiMode === 'villas'
  const gardees = lignesEnvoyees(lines)
  return gardees.map((l, idx) => {
    if (estStructure(l)) {
      // Une ligne section/note ne porte ni produit ni prix (ni provenance).
      return {
        type_ligne: l.typeLigne, ordre: idx, designation: l.designation,
        ligne_composee: null,
      }
    }
    return {
      produit: parseInt(l.produit, 10),
      designation: l.designation,
      quantite: l.quantite,
      prix_unitaire: prixUnitaireEnvoye(l),
      remise: String(parseFloat(l.remise) || 0),
      taux_tva: String(l.taux_tva ?? 20),
      groupe_index: villas ? (l.groupeIndex ?? null) : null,
      groupe_label: villas ? (l.groupeLabel || '') : '',
      optionnelle: !!l.optionnelle,
      type_ligne: 'produit',
      ordre: idx,
      variante: l.variante || '',
      prix_manuel: !!l.prixManuel,
      quantite_manuelle: !!l.quantiteManuelle,
      // Rôle STOCKÉ de la ligne : renvoyé tel quel (vide ⇒ le serveur le
      // déduit du produit, comportement historique).
      role_devis: l.role_devis || '',
      // QJR667 — le lot de la ligne (id d'un lot de CE devis, sinon null).
      lot: l.lot ?? null,
      // ERR-QJR570 (D-QJR5-4) — la provenance PERSISTÉE : true = posée par
      // le moteur (une recomposition la remplace), false = ajoutée à la main
      // (« Ajouter une ligne », jamais remplacée, même après réouverture).
      ligne_composee: !!l.compose,
      // AGR218 — base légale de l'exonération (obligatoire à 0 %, refus 400
      // serveur sinon) ; vide = aucune. Jamais de texte proposé par défaut.
      tva_base_legale: String(l.tvaBaseLegale ?? ''),
    }
  })
}

/**
 * AGR218 — une ligne PRODUIT à 0 % de TVA sans base légale saisie ? (Même
 * règle que le serveur, `domain/lignes.exiger_base_legale_tva`.) Le taux
 * n'est jamais changé ici : on signale, on ne corrige pas.
 */
export function baseLegaleManquante(l) {
  if (!l || estStructure(l)) return false
  const taux = parseFloat(l.taux_tva)
  if (!Number.isFinite(taux) || taux !== 0) return false
  return !String(l.tvaBaseLegale ?? '').trim()
}

const CHAMP_BASE_LEGALE = /^lignes\[(\d+)\]\.tva_base_legale$/

/**
 * AGR218 — refus 400 du serveur (`{detail, champ: 'lignes[i].tva_base_legale'}`,
 * contrat `exemple_400_tva_base_legale`) → `{ [_key de la ligne]: detail }`,
 * l'index étant celui des lignes ENVOYÉES. Tout autre refus → `{}`.
 */
export function erreursBaseLegaleServeur(data, lines) {
  const m = CHAMP_BASE_LEGALE.exec(String(data?.champ ?? ''))
  if (!m) return {}
  const ligne = lignesEnvoyees(lines)[Number(m[1])]
  if (!ligne || ligne._key == null) return {}
  return { [ligne._key]: String(data.detail ?? '') }
}
