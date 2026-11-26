/* ACAL1193 — le rangement PAR ÉTAPE de « Prêt à envoyer ? » (maquettes `Documents.dc.html` et
   `Electrique.dc.html`). Le serveur sert une liste PLATE de contrôles (contrat
   `calepinage_pret_a_envoyer.json`, `codes_produits`) ; ce fichier dit seulement dans QUELLE étape
   de l'atelier chacun se règle — jamais un état, jamais un chiffre. */

import { libelleEtat } from '../electrique/etatVerdict'

export const GROUPES = [
  { cle: 'toit', libelle: 'Toit' },
  { cle: 'panneaux', libelle: 'Panneaux' },
  { cle: 'electrique', libelle: 'Électrique' },
  { cle: 'resultats', libelle: 'Résultats' },
]
export const GROUPE_AUTRES = { cle: 'autres', libelle: 'Autres contrôles' }

export const ETAPE_DU_CODE = {
  visite_validee: 'toit',
  approbation_a_jour: 'toit',
  conception_perimee: 'toit',
  pentes_confirmees: 'toit',
  obstacle_hors_pan: 'toit',
  pans_vides: 'toit',
  kwc_coherent: 'panneaux',
  taille_sans_facture: 'panneaux',
  ombrage_chiffre: 'panneaux',
  un_seul_chiffre: 'panneaux',
  kwh_declare: 'panneaux',
  hypotheses_conso: 'panneaux',
  verdict_electrique: 'electrique',
  materiel_designe: 'electrique',
  tension_froid: 'electrique',
  tension_chaud: 'electrique', // T4-U4-012 — jumeau du froid : « Tension des chaînes par forte chaleur »
  courant_entree: 'electrique', // R5C-N3 — le courant des panneaux face à l'entrée de l'onduleur (jumeau de la chaleur)
  orientation_mppt: 'electrique',
  ratio_dc_ac: 'electrique',
  chutes_tension: 'electrique',
  terre_protections: 'electrique',
  compatibilite_equipements: 'electrique',
  ecart_pvgis: 'resultats',
  simulation_fraiche: 'resultats',
  dossier_pieces: 'resultats',
}

/** La clé d'étape (`toit|panneaux|electrique|resultats|autres`) d'un contrôle servi : la table
    ci-dessus, sinon l'étape que NOMME sa cible servie, sinon « autres ». */
export function groupeDuControle(controle) {
  const parCode = ETAPE_DU_CODE[controle.code]
  if (parCode) return parCode
  const parCible = controle.cible?.etape
  return GROUPES.some((g) => g.cle === parCible) ? parCible : GROUPE_AUTRES.cle
}

/** « 9 contrôles sur 10 sont bons. » — seuls les contrôles qui portent un verdict (ok, à régler,
    bloquant) comptent ; une valeur `info` (sans seuil, sans verdict) n'est ni bonne ni mauvaise. */
export function phraseDesBons(bons, total) {
  const contr = (n) => `contrôle${n > 1 ? 's' : ''}`
  return `${bons} ${contr(bons)} sur ${total} ${bons > 1 ? 'sont bons' : 'est bon'}.`
}

/* H3 (tour 3) — lent n'est pas échoué : le délai dépassé du client (axios `ECONNABORTED`, 20 s) se dit
   à part d'un refus du serveur. */
export const MESSAGE_ECHEC = 'Le contrôle « Prêt à envoyer ? » n’a pas pu être lu.'
export const MESSAGE_LENT = 'Le contrôle prend plus de temps que prévu.'
export const estDelaiDepasse = (err) => err?.code === 'ECONNABORTED' || /timeout/i.test(String(err?.message ?? ''))
/** L'heure d'une lecture servie, « HH:MM » (l'heure locale du poste). */
export const heureDe = (date) => date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })

/** H3 — l'ordre d'une liste : bloquant, à régler, bon, puis info ; STABLE à état égal. */
const RANG_LISTE = { bloquant: 0, a_regler: 1, ok: 2, info: 3 }
export function rangerControles(controles) {
  return controles
    .map((c, i) => [c, i])
    .sort(([a, i], [b, j]) => ((RANG_LISTE[a.etat] ?? 4) - (RANG_LISTE[b.etat] ?? 4)) || (i - j))
    .map(([c]) => c)
}

/* T4-U4-007 (moitié serveur, pli 4cb986f8d2) — « Dossier électrique » SERT ses points (`controles[].points[]` =
   {code, phrase, geste, cible}). Une phrase servie peut finir par une clé interne entre parenthèses
   (« … (terre.justification_continuite) ») : retirée avant affichage, jamais imprimée. */
const CLE_INTERNE_FINALE = /\s*\((?:[A-Za-z_][\w-]*\.)+[\w-]+\)(?=[.\s]*$)/

export const sansCleInterne = (phrase) => (typeof phrase === 'string' ? phrase.replace(CLE_INTERNE_FINALE, '').trim() : '')

/** Les points servis d'un contrôle (phrase nettoyée), `[]` quand le serveur n'en sert pas. */
export function pointsServis(controle) {
  return (Array.isArray(controle?.points) ? controle.points : [])
    .filter((p) => p && typeof p === 'object')
    .map((p) => ({ ...p, phrase: sansCleInterne(p.phrase) }))
    .filter((p) => p.phrase)
}

/* R6-N3 — « Dossier électrique — Bloquant : 2 » compte les POINTS DU DOSSIER (les motifs de son verdict), alors que
   « 6 points à régler », « N à régler » du rail et « Contrôles · 4 bons » comptent des CONTRÔLES (une ligne chacun) : la
   même formule « N points » désignait deux choses sur le même écran. Le mot « points du dossier » vit dans
   `electrique/etatVerdict.js` (source unique du libellé, lue par tous les écrans) ; le NOMBRE est celui du champ structuré
   `controle.points` (sa longueur), à défaut le chiffre du texte servi (« Bloquant : N »). */
const CHIFFRE_DU_TEXTE = /\d+/

/** Le nombre de points du dossier électrique d'un contrôle servi (0 si rien n'est lisible). */
export function nombreDePointsDuDossier(controle) {
  if (Array.isArray(controle?.points) && controle.points.length > 0) return controle.points.length
  return Number(String(controle?.valeur_texte ?? '').match(CHIFFRE_DU_TEXTE)?.[0] ?? 0)
}

/** La valeur affichée à droite du titre d'un contrôle : celle du serveur, sauf le décompte du dossier électrique bloquant. */
export function valeurAffichee(controle) {
  const texte = controle?.valeur_texte
  if (controle?.code !== 'verdict_electrique' || controle?.etat !== 'bloquant') return texte
  const n = nombreDePointsDuDossier(controle)
  return n > 0 ? libelleEtat('bloquant', n).libelle : texte
}

/** La cible de « Régler » : celle du premier point servi quand il en porte une, sinon celle du contrôle. */
export function cibleDuReglage(controle) {
  return pointsServis(controle).find((p) => p.cible?.onglet)?.cible ?? controle?.cible
}
