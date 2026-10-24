// ENF22 — logique pure de l'onglet Devis, séparée du composant (la règle
// react-refresh/only-export-components interdit de mêler constantes/fonctions
// exportées et composant dans un même fichier). Importée par DevisTab.jsx ;
// testée à part (DevisTab.test.jsx). Aucune logique modifiée : déplacement pur.
import { formatDateTime, normalizePhoneE164 } from '../../../lib/format'
import { todayLocalIso } from '../../../lib/dateLocale'

// Mini-piste DOCUMENT (règle #4) devis→facture→chantier — JAMAIS les stages
// STAGES.py du funnel lead (règle #2). N'est rendue QUE sur une carte devis
// ACCEPTÉE. `Lead.devis[]` (serializers.get_devis) n'expose ni BC ni facture
// liée (contrairement à la requête dédiée de DevisList.jsx) — seul `chantier`
// est disponible : la piste avance donc directement de « Accepté » à
// « Chantier » quand un chantier existe, sans distinguer un état
// intermédiaire « Facturé » (limitation de donnée documentée, pas un choix
// arbitraire — voir le rapport de fin de lane).
export const DEVIS_MINI_TRACK = [
  { key: 'brouillon', label: 'Brouillon' },
  { key: 'envoye', label: 'Envoyé' },
  { key: 'accepte', label: 'Accepté' },
  { key: 'facture', label: 'Facturé' },
  { key: 'chantier', label: 'Chantier' },
]


export function devisTrackCurrent(d) {
  return d?.chantier ? 'chantier' : 'accepte'
}

// ── L-SECT (fondateur 24/08/2026) — « le commercial choisit ce que le client
// reçoit avant d'envoyer la page devis ». Les 7 sections cochables du dialogue
// « Envoyer au client », dans l'ordre où elles apparaissent sur la page client.
// Les clés sont EXACTEMENT la whitelist serveur (ShareLink.SECTIONS_CLES) : une
// clé inconnue est refusée en 400, donc les deux listes ne peuvent pas diverger
// en silence.
export const SECTIONS_ENVOI = [
  { key: 'roof3d', label: 'Calepinage 3D' },
  { key: 'sld', label: 'Schéma unifilaire' },
  { key: 'pdf', label: 'PDF téléchargeable' },
  { key: 'bankable', label: 'Étude bancable' },
  { key: 'economies', label: "Synthèse d'économies" },
  { key: 'jour_type', label: 'Journée type & courbes' },
  { key: 'gammes', label: 'Comparatif de gammes' },
]

// L-SECT — les 7 cases sont COCHÉES par défaut (le client reçoit tout), et
// l'état d'un lien déjà envoyé prime : une clé absente du serveur vaut « servie »
// (même sémantique à trois états que `ShareLink.section_servie`), une clé à
// False décoche la case. Fonction pure → testable sans rendu.
export function sectionsDepuisServeur(sections) {
  const src = sections && typeof sections === 'object' ? sections : {}
  return Object.fromEntries(
    SECTIONS_ENVOI.map(({ key }) => [key, src[key] !== false]),
  )
}

// ── LANE E (fondateur 28/08/2026, spec_3_options.md) — 1/2/3 options servies.
// Backend contract (ShareLink.SECTIONS_CLES étendu) : `taille_eco`/`taille_max`
// sont deux clés supplémentaires, MÊME sémantique trois-états que les 7 clés
// ci-dessus (absente/true → servie, false → retirée). `recommande` n'a AUCUNE
// clé — c'est le devis, elle est toujours servie. On étend donc la MÊME
// machinerie (`sections`) plutôt qu'un état parallèle : ces deux clés
// voyagent dans le même objet `sections` posté à `shareLinkDevis`.
export const TAILLES_ENVOI = [
  { key: 'taille_eco', label: 'Éco' },
  { key: 'taille_max', label: 'Max' },
]

export function taillesDepuisServeur(sections) {
  const src = sections && typeof sections === 'object' ? sections : {}
  return Object.fromEntries(
    TAILLES_ENVOI.map(({ key }) => [key, src[key] !== false]),
  )
}

// Nombre d'options présentées au client = Recommandé (toujours) + les tailles
// encore cochées.
export function optionsCountFromTailles(tailles) {
  return 1 + (tailles?.taille_eco ? 1 : 0) + (tailles?.taille_max ? 1 : 0)
}

// Le curseur 1/2/3 dérive les deux cases depuis un compte cible, en essayant
// de PRÉSERVER le choix courant : 1 = les deux décochées ; 3 = les deux
// cochées ; 2 = si une seule était déjà cochée on la garde telle quelle,
// sinon (on arrivait de 1 ou de 3) le défaut est Max — un rétrécissement
// depuis 3 tranche donc en faveur de Max, comme un agrandissement depuis 1.
export function taillesFromOptionsCount(count, tailles) {
  if (count <= 1) return { taille_eco: false, taille_max: false }
  if (count >= 3) return { taille_eco: true, taille_max: true }
  const cur = tailles || {}
  const nbCochees = (cur.taille_eco ? 1 : 0) + (cur.taille_max ? 1 : 0)
  if (nbCochees === 1) return { taille_eco: !!cur.taille_eco, taille_max: !!cur.taille_max }
  return { taille_eco: false, taille_max: true }
}

export function waArmed(phone, selectedCount) {
  return !!normalizePhoneE164(phone) && selectedCount > 0
}

// EZ5 — intention d'ouverture du panneau devis. Sans puissance cible saisie on
// renvoie la CHAÎNE de mode historique (aucun appelant existant ne bouge :
// IdentityRail, palette de commandes, tests) ; avec une cible on renvoie
// l'objet { mode, targetKwc } que LeadWorkspace sait aussi lire. La cible ne
// concerne que les modes qui DIMENSIONNENT (auto/remise/onepage/premium) —
// « edit » ouvre le générateur, qui a son propre champ kWc (EZ5, 1ʳᵉ moitié).
export function devisIntent(mode, kwcCible) {
  const cible = String(kwcCible ?? '').trim()
  if (!cible || mode === 'edit') return mode
  return { mode, targetKwc: cible }
}

// QJ-VUES (fondateur 09/09/2026 — « un endroit où je vois combien de fois le
// devis a été consulté, sur chaque fiche lead ») — libellé du compteur de
// lectures CLIENT, TOUJOURS affiché sur chaque carte devis. `lecture` vient de
// la fiche lead (`Lead.devis[].lecture`, agrégé serveur sur TOUS les ShareLink
// du devis — expirés compris, robots d'aperçu WhatsApp/crawlers exclus par
// QJ-ROBOTS côté backend). Trois états, jamais de chiffre inventé :
//   · null  → aucun lien client n'a jamais été créé (rien n'a été envoyé) ;
//   · 0 vue → lien envoyé mais jamais ouvert ;
//   · N vues → N lectures humaines + horodatage de la dernière.
export function lectureClientLabel(lecture, corrigeLe = null) {
  if (!lecture) return 'Pas encore envoyé au client'
  const vues = Number(lecture.nombre_vues ?? 0)
  if (!vues) return 'Jamais ouvert par le client'
  const quand = lecture.derniere_consultation
    ? ` · dernière lecture ${formatDateTime(lecture.derniere_consultation)}`
    : ''
  // QJR566 — une lecture ANTÉRIEURE à la correction après envoi n'a pas vu la
  // version corrigée : on le dit au lieu d'un « lu le » trompeur.
  const avantCorrection = corrigeLe && lecture.derniere_consultation
    && new Date(lecture.derniere_consultation) < new Date(corrigeLe)
    ? ` — avant la correction du ${formatDateTime(corrigeLe)}`
    : ''
  return `Ouvert ${vues} fois par le client${quand}${avantCorrection}`
}

// ALEA50 (D-ACI-6=a) — « prêt » inclut le CATALOGUE : pour un lead C&I, le
// serveur sert `devis_auto.catalogue_ci` = { pret, manquants: [libellés] } (les
// postes fixes sans prix : forfaits société, coffrets, protection AC, comptage).
// `null` (hors C&I, lecture en échec) ne bloque jamais : seul `pret === false`.
export function catalogueCiBloque(devisAuto) {
  return devisAuto?.catalogue_ci?.pret === false
}

// « 3 postes sans prix — à régler par l'administrateur » (singulier géré).
export function raisonCatalogueCi(devisAuto) {
  const n = devisAuto?.catalogue_ci?.manquants?.length ?? 0
  return `${n} poste${n > 1 ? 's' : ''} sans prix — à régler par l'administrateur`
}

// Le texte de la note chatter « Demander au responsable » : nomme les postes.
export function noteDemandeCatalogueCi(devisAuto) {
  const postes = devisAuto?.catalogue_ci?.manquants ?? []
  return 'Demande au responsable : le devis automatique C&I est bloqué, '
    + `${raisonCatalogueCi(devisAuto)}. Postes à chiffrer : ${postes.join(' ; ')}.`
}

// ALEA55 — « Proposer une relance J+3 » : la date de relance du lead (DateField
// `relance_date`, 'YYYY-MM-DD') trois jours après AUJOURD'HUI à Casablanca (jamais
// le fuseau du navigateur — même ancrage que le journal d'appel).
export function dateRelanceJ3(maintenant = new Date()) {
  const jour = todayLocalIso(maintenant)
  const d = new Date(`${jour}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + 3)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`
}
