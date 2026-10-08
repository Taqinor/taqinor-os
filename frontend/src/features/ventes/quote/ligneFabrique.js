// SPL43 — LA FABRIQUE DE LIGNES DU GÉNÉRATEUR (déplacée telle quelle de
// DevisGenerator.jsx : aucune ligne de logique n'a changé). Le compteur de
// clés vit dans CE SEUL module : une seconde copie dupliquerait les `_key`.
import { lireLastTva } from './ecranDefauts.js'

let _keyCounter = 0
export const newKey = () => ++_keyCounter

export const withKeys = (rows) => rows.map(r => ({
  _key: newKey(),
  produit: String(r.produit ?? ''),
  designation: r.designation,
  quantite: String(r.quantite),
  prix_unit_ttc: String(r.prix_unit_ttc),
  taux_tva: String(r.taux_tva ?? 20),
  // QJ31 — groupe multi-villa (mode B) : null = ligne mono-système (défaut,
  // comportement historique inchangé). 0 = équipement commun, 1..N = villa N.
  groupeIndex: r.groupeIndex ?? null,
  groupeLabel: r.groupeLabel ?? '',
  // XSAL5 — ligne optionnelle (add-on hors total). Défaut False = ligne normale.
  optionnelle: !!r.optionnelle,
  // XSAL14 — type de ligne : 'produit' (défaut) / 'section' / 'note'.
  typeLigne: r.typeLigne ?? 'produit',
  // N2 — verrou « prix tapé à la main » : préservé au rechargement d'un
  // brouillon (VX62 draft restore), sinon False (chargement serveur/auto-fill —
  // rien n'a encore été tapé sur CES lignes-là).
  prixManuel: !!r.prixManuel,
  // QJR218 — même patron que `prixManuel` juste au-dessus : le verrou
  // « quantité tapée à la main » (posé aujourd'hui côté serveur, ex. une
  // resynchronisation, `domain/lignes`) doit lui aussi survivre au
  // rechargement d'un brouillon/devis, jamais retomber à False en silence.
  quantiteManuelle: !!r.quantiteManuelle,
  // L-2OPT (fondateur 24/08) — '' commun (défaut, comportement historique
  // inchangé) | 'sans' | 'avec' : posée par `fusionnerVariantes` quand les
  // deux optimiseurs résidentiels divergent, préservée au rechargement d'un
  // brouillon/devis (VX62, réouverture ?edit=).
  variante: r.variante ?? '',
  // QJR523 — rôle STOCKÉ de la ligne (`role_devis`) : conservé comme
  // `prixManuel`, sinon `remplacer_lignes` re-devine le rôle et écrase celui
  // posé par la composition (ex. 'onduleur_offgrid').
  role_devis: r.role_devis ?? '',
  lot: r.lot ?? null, // QJR667 — lot multi-sites conservé à l'enregistrement
  // QJR529 — remise PAR LIGNE stockée (%), conservée comme `prixManuel` :
  // jamais remise à '0' en silence (le total client monterait).
  remise: String(r.remise ?? '0'),
  // QJR570 — marqueur d'ÉCRAN « ligne issue d'une composition » (jamais
  // envoyé au serveur) : une recomposition retire une ligne composée hier et
  // absente aujourd'hui, mais garde une ligne ajoutée à la main.
  compose: !!r.compose,
}))

// Nouvelle ligne vide — quantité 0 comme addProductLine() du simulateur
export const emptyLine = () => ({
  _key: newKey(),
  produit: '',
  designation: '',
  quantite: '0',
  prix_unit_ttc: '0',
  taux_tva: lireLastTva(),  // VX93 — dernière TVA saisie (défaut 20 %)
  // VX249(b) — 1 des 4 champs VX93 exactement (avec owner/ville sur
  // LeadForm.jsx et payMode sur FactureList.jsx) : reste « suggéré » (style
  // discret dans DevisLineRow.jsx) tant que l'utilisateur n'a pas changé
  // LUI-MÊME le taux de CETTE ligne — retiré via `setLine` ci-dessous.
  _tvaSuggested: true,
  groupeIndex: null,
  groupeLabel: '',
  // XSAL5 — ligne optionnelle (add-on hors total). Défaut False.
  optionnelle: false,
  // XSAL14 — type de ligne : 'produit' (défaut) / 'section' / 'note'.
  typeLigne: 'produit',
  // N2 — aucun prix tapé à la main pour l'instant.
  prixManuel: false,
  // QJR218 — aucune quantité tapée à la main pour l'instant (ligne neuve).
  quantiteManuelle: false,
  // L-2OPT — ligne ajoutée à la main : commune par défaut.
  variante: '',
})

// XSAL14 — ligne de SECTION (intertitre) ou de NOTE (texte sans prix). Ne porte
// ni produit ni prix ni quantité : exclue de tous les totaux, rendue comme
// intertitre/note à l'écran et sur le PDF premium.
export const structureLine = (typeLigne) => ({
  _key: newKey(),
  produit: '',
  designation: '',
  quantite: '0',
  prix_unit_ttc: '0',
  taux_tva: '20',
  _tvaSuggested: false,
  groupeIndex: null,
  groupeLabel: '',
  optionnelle: false,
  typeLigne,
  prixManuel: false,
  variante: '',
})
