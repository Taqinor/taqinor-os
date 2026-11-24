/* ACAL1193 — le rangement PAR ÉTAPE de « Prêt à envoyer ? » (maquettes `Documents.dc.html` et
   `Electrique.dc.html`). Le serveur sert une liste PLATE de contrôles (contrat
   `calepinage_pret_a_envoyer.json`, `codes_produits`) ; ce fichier dit seulement dans QUELLE étape
   de l'atelier chacun se règle — jamais un état, jamais un chiffre. */

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
