// SPL202 — auto-remplissage du catalogue (ordre des lignes PVORD, marques
// épinglées PVMRQ, table par défaut, rôle/produit de structure STKCAT10,
// _hasPrix) déplacé tel quel de solar.js (move only : aucune ligne de logique
// modifiée). Feuille : lit la classification dans calc/classification.js et
// ligneProduitCatalogue/tauxTvaOf dans solar.js ; solar.js n'en lit rien.
import { _norm, classifyProduct } from './classification.js'
import { ligneProduitCatalogue, tauxTvaOf } from '../solar.js'

// ── PVORD (fondateur 19/08/2026) — ordre PAR DÉFAUT des lignes de devis ──────
// Frontend de `ParametresGammes.ordre_lignes` (apps/ventes/models.py) : une
// liste de rôles PRODUCT_CATEGORIES/ROLES_AUTO_COMPOSITION dans l'ordre voulu
// pour les PROCHAINS devis. Sans préférence (absente/vide) : ordre CANONIQUE
// de composition inchangé — zéro régression tant que rien n'est enregistré.

// Trie une liste de lignes TAGUÉES `[role, ligne]` par préférence de rôle.
// Un rôle PRÉSENT dans `ordreLignes` est classé à sa position ; un rôle
// ABSENT garde son rang canonique mais TOUJOURS après tout rôle
// explicitement préféré — tri STABLE (jamais un ex-æquo aléatoire) : les
// deux lignes « batterie » (5 kWh / 10 kWh) gardent leur ordre relatif entre
// elles quand leur rôle est préféré, ou l'un envers l'autre à la fin sinon.
export function orderLinesByRolePreference(taggedLines, ordreLignes) {
  if (!Array.isArray(ordreLignes) || !ordreLignes.length) {
    return taggedLines.map(([, ligne]) => ligne)
  }
  const rang = (role) => {
    const idx = ordreLignes.indexOf(role)
    return idx === -1 ? Infinity : idx
  }
  return taggedLines
    .map((entree, i) => ({ entree, i }))
    .sort((a, b) => {
      const ra = rang(a.entree[0])
      const rb = rang(b.entree[0])
      return ra !== rb ? ra - rb : a.i - b.i
    })
    .map(({ entree }) => entree[1])
}

// Dérive la séquence de rôles depuis les lignes COURANTES de l'écran (bouton
// « Enregistrer cet ordre comme ordre par défaut ») : classification RÉUTILISÉE
// (aucun nouveau mot-clé — même classifyProduct que groupProduitsByCategory),
// dédupliquée en gardant la PREMIÈRE occurrence (l'ordre écran des DEUX lignes
// batterie 5/10 kWh ne compte que pour un seul rang « batterie »), et les
// lignes sans classification reconnue (section/note, désignation libre) sont
// simplement ignorées — jamais un rôle inventé.
export function deriveRoleOrderFromLines(lines) {
  const seen = new Set()
  const order = []
  for (const l of (lines ?? [])) {
    let role = classifyProduct(l.designation)
    if (!role) continue
    // STKCAT10 — MÊME règle d'émission que la composition (écran ET serveur) :
    // un libellé qui ne dit ni « acier » ni « alu » (une pergola) donne le rôle
    // GÉNÉRIQUE `structure`, jamais `structure_acier` par défaut — sinon
    // l'ordre enregistré ne retrouverait jamais la ligne réellement composée.
    if (role === 'structure') role = structureRoleForName(l.designation)
    if (seen.has(role)) continue
    seen.add(role)
    order.push(role)
  }
  return order
}

// ── PVMRQ — marque préférée par gamme/rôle (fondateur 18/08/2026) ────────────
// Frontend de `ParametresGammes.marques` (backend, ROLES_AUTO_COMPOSITION —
// MIROIR EXACT des clés `PRODUCT_CATEGORIES` ci-dessus) : quand une marque est
// épinglée pour un rôle, elle GAGNE TOUJOURS — le vivier de candidats de ce
// rôle est restreint À ELLE SEULE avant toute autre logique (wattage/prix/
// compatibilité). Sans marque réglée pour ce rôle (clé absente ou vide),
// comportement byte-identique à l'historique.

// Marque épinglée pour ce rôle dans la carte `marques` ({role: marque}) de la
// gamme active, ou '' si aucune préférence — ne lève jamais.
function _marqueEpinglee(marques, role) {
  const carte = marques && typeof marques === 'object' ? marques : null
  const m = carte ? carte[role] : null
  return typeof m === 'string' ? m.trim() : ''
}

// Le produit porte-t-il la marque épinglée ? MIROIR EXACT de
// `_marque_correspond` (apps/ventes/services.py) : `produit.marque` (champ
// structuré) prioritaire, égalité EXACTE une fois normalisée ; à défaut (marque
// non renseignée sur la fiche), son `nom` DOIT seulement CONTENIR la marque,
// jamais l'égaler. Réutilise `_norm` (accents/casse) — le backend ne compare
// que la casse (`casefold`), mais un accent divergent ne doit pas non plus
// faire manquer une marque bien réelle côté écran.
function _marqueCorrespond(produit, marque) {
  const cible = _norm(marque)
  if (!cible) return false
  const marqueProduit = _norm(produit?.marque)
  if (marqueProduit) return marqueProduit === cible
  return _norm(produit?.nom).includes(cible)
}

// Restreint un vivier de candidats à la marque épinglée pour `role` (carte
// `marques` de la gamme active). Sans préférence réglée : vivier RENVOYÉ TEL
// QUEL (comportement historique). Marque réglée mais AUCUN candidat ne la
// porte : vivier VIDE — JAMAIS un repli silencieux sur une autre marque — et
// l'entrée `{ role, marque }` est consignée dans `manquantes` (dédupliquée par
// rôle, même patron que `onduleursIncomplets`).
function _filtrerParMarque(pool, role, marques, manquantes, vusRoles) {
  const source = pool ?? []
  const marque = _marqueEpinglee(marques, role)
  if (!marque) return source
  const filtres = source.filter(p => _marqueCorrespond(p, marque))
  if (!filtres.length && vusRoles && !vusRoles.has(role)) {
    vusRoles.add(role)
    manquantes.push({ role, marque })
  }
  return filtres
}

// ── Indexation par type des produits du stock ─────────────────────────────────
// STKCAT24 — même repli que `groupProduitsByCategory` : `role_devis_effectif`
// (STKCAT21) d'abord, mots-clés du nom ENSUITE, seulement quand le champ est
// absent/null — un produit sans ce champ indexe exactement comme avant.
function indexProduits(produits) {
  const byType = {}
  for (const p of produits) {
    const type = p.role_devis_effectif ?? classifyProduct(p.nom)
    if (!type) continue
    if (!byType[type]) byType[type] = []
    byType[type].push(p)
  }
  return byType
}

const lineFrom = (p, quantite, ttcOverride = null) => ((p && ttcOverride == null)
  // ATOT28 — prix catalogue repris tel quel (HT d'origine porté).
  ? ligneProduitCatalogue(p, quantite)
  : {
      produit: p ? String(p.id) : '',
      designation: p ? p.nom : '',
      quantite,
      prix_unit_ttc: p || ttcOverride != null ? ttcOverride : 0,
      taux_tva: p ? tauxTvaOf(p) : 20,
    })

// Ligne vide placeholder (désignation canonique, pas de produit)
const placeholder = (designation, quantite) => ({
  produit: '', designation, quantite, prix_unit_ttc: 0, taux_tva: 20,
})

// ── Table par défaut au chargement (port de getDefaultProductLines) ──────────
// Quantités par défaut du simulateur ; les lignes « spéciales » (onduleurs,
// panneaux, batteries) restent à choisir, les autres pointent sur le produit
// canonique du stock avec son prix TTC (équivalent de autofillRowPrice).
// PVORD — `ordreLignes` (optionnel, `ParametresGammes.ordre_lignes`) réordonne
// le résultat par rôle préféré ; absent/vide = ordre canonique ci-dessous,
// byte-identique à l'historique (voir `orderLinesByRolePreference`).
export function defaultProductLines(produits, ordreLignes) {
  const byType = indexProduits(produits)
  // AGNR27 — garde « aucun produit sans prix » : un rôle pointe le premier
  // produit PRIX CONNU, ou reste sans produit (placeholder) — jamais un
  // article à 0 MAD (ex. « Structure bac acier C&I » du seed C&I).
  const first = (type) => (byType[type] ?? []).find(_hasPrix) ?? null
  const exactOr = (type, needle) => {
    const pool = byType[type] ?? []
    return pool.find(p => _hasPrix(p) && _norm(p.nom).includes(needle)) ?? null
  }
  const row = (p, designation, quantite) =>
    p ? lineFrom(p, quantite) : placeholder(designation, quantite)

  const tagged = [
    ['onduleur_reseau', placeholder('Onduleur réseau', 1)],
    ['onduleur_hybride', placeholder('Onduleur hybride', 1)],
    ['smart_meter', row(first('smart_meter'), 'Smart Meter', 0)],
    ['wifi_dongle', row(first('wifi_dongle'), 'Wifi Dongle', 0)],
    ['panneau', placeholder('Panneaux', 0)],
    ['batterie', placeholder('Batterie', 1)],
    ['batterie', placeholder('Batterie', 0)],
    ['structure_acier', row(exactOr('structure', 'acier'), 'Structures acier', 0)],
    ['structure_alu', row(exactOr('structure', 'alu'), 'Structures aluminium', 0)],
    ['socle', row(first('socle'), 'Socles', 0)],
    ['accessoires', row(first('accessoires'), 'Accessoires', 1)],
    ['tableau', row(first('tableau'), 'Tableau De Protection AC/DC', 1)],
    ['installation', row(first('installation'), 'Installation', 1)],
    ['transport', row(first('transport'), 'Transport', 1)],
    ['suivi', row(first('suivi'), 'Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 1)],
  ]
  return orderLinesByRolePreference(tagged, ordreLignes)
}

/* STKCAT10 — LE RÔLE ÉMIS POUR LA LIGNE STRUCTURE, MIROIR EXACT DU SERVEUR
   (`apps/ventes/domain/composition.py::role_structure_du_produit`, règle
   d'émission écrite au contrat `contract_samples/devis_composition.json`) :
   le rôle suit le NOM DU PRODUIT RETENU, jamais le bouton demandé.
     · le nom porte encore « acier »          ⇒ `structure_acier` ;
     · le nom porte encore « alu »/« aluminium » ⇒ `structure_alu` ;
     · ni l'un ni l'autre (pergola, carport, bac lesté…) ⇒ le rôle GÉNÉRIQUE
       `structure` (déjà inscrit dans PRODUCT_CATEGORIES par STKCAT2).
   `voulu` départage un nom qui porterait LES DEUX mots-clés, et c'est aussi
   le rôle rendu quand aucun nom n'est lisible — comportement d'hier, au
   caractère près. */
export function structureRoleForName(nom, voulu = 'acier') {
  const prefere = _norm(voulu).startsWith('alu') ? 'alu' : 'acier'
  const autre = prefere === 'alu' ? 'acier' : 'alu'
  const role = { alu: 'structure_alu', acier: 'structure_acier' }
  const n = _norm(nom)
  if (!n) return role[prefere]
  if (n.includes(prefere)) return role[prefere]
  if (n.includes(autre)) return role[autre]
  return 'structure'
}

/* STKCAT10 — LE PRODUIT DE STRUCTURE EXPLICITEMENT CHOISI, résolu comme le
   serveur le résout : dans le catalogue COMPLET déjà scopé société (pas dans
   le vivier « structures nommées », sinon une pergola resterait invisible) et
   APRÈS la garde de prix — un id qui désignerait un produit non tarifé, ou
   celui d'une autre société, ne résout RIEN et la composition retombe sur le
   bouton acier/alu. Ni le filtre par mot-clé ni la marque épinglée du rôle ne
   s'y appliquent : un choix explicite ne se re-choisit pas. */
export function structureChoisie(produits, structureProduitId) {
  if (structureProduitId == null || structureProduitId === '') return null
  const cible = String(structureProduitId)
  return (produits ?? []).find(
    (p) => String(p?.id) === cible && _hasPrix(p)) ?? null
}

// ADEV69 — `autoFillLines`, le second composeur résidentiel (sans appelant de
// production depuis CIQ126/CIQ128), est SUPPRIMÉ : D-QJR5-9 « un seul
// composeur, côté serveur » — le survivant est `apps/ventes/domain/composition.py`
// (dry-run `POST /ventes/devis/composition/`, appliqué par useCompositionEcran).
// Son absence est épinglée par `solar.codeMortAdev69.test.mjs`.

// QJR546 — exporté : le générateur saute (et nomme) les lignes d'un modèle
// dont le produit n'a plus de prix, avec la MÊME garde que l'auto-remplissage.
export const _hasPrix = (p) => (parseFloat(p.prix_vente) || 0) > 0
