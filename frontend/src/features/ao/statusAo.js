import { statusPill } from '../../ui/module'

/* ============================================================================
   AOF10 — Pastilles d'état AO : affaire, pièce, variante, contrôle.
   ----------------------------------------------------------------------------
   AOF9 tokenise la PROVENANCE d'une valeur ; ce fichier tokenise les ÉTATS que
   les écrans du Groupe AOF afficheront. Fabrique UNIQUE sur `statusPill` de
   `@/ui/module` (aucun hex local, aucun `statusPill` réinventé dans
   `features/ao/`) — un ton parmi les 5 déjà thémés clair/sombre par
   `StatusPill`/`design/tokens.css` : neutral / info / success / warning /
   danger. Rendu identique clair/sombre HÉRITÉ gratuitement (aucune couleur
   posée ici, seulement des tons sémantiques).

   `STATUT_AFFAIRE` MIROIRE `apps/ao/models.py` → `AppelOffre.Statut`
   (identifié → en préparation → déposé → gagné/perdu/abandonné) — gardé par
   `statusAo.test.jsx` contre une RÉGRESSION DE DRIFT : un état ajouté côté
   backend sans libellé ici fait rougir ce test.

   `STATUT_PIECE` / `STATUT_VARIANTE` / `STATUT_CONTROLE` anticipent des
   champs pas encore posés côté serveur (fabrique documentaire, atelier de
   variantes — lanes séparées du Groupe AOF) : les clés viennent du TEXTE
   normatif d'AOF10 lui-même, pas encore d'un modèle réel.
   ========================================================================== */

// ── Affaire (AppelOffre.statut) ─────────────────────────────────────────────
// AOF13 a DÉTAILLÉ le cycle : `en_preparation` reste une valeur historique
// valide (aucune migration de données), les six étapes qui l'encadrent la
// remplacent pour toute nouvelle affaire. L'ordre ci-dessous EST l'ordre du
// cycle réel — la garde anti-drift de `statusAo.test.jsx` exige que ces clés
// couvrent EXACTEMENT `AppelOffre.Statut`.
export const STATUT_AFFAIRE = {
  identifie: { label: 'Identifié', tone: 'neutral' },
  analyse_cps: { label: 'Analyse du CPS', tone: 'info' },
  releve: { label: 'Relevé de la toiture', tone: 'info' },
  etude: { label: 'Étude / calepinage', tone: 'info' },
  chiffrage: { label: 'Chiffrage', tone: 'info' },
  dossier: { label: 'Montage du dossier', tone: 'info' },
  pret_a_deposer: { label: 'Prêt à déposer', tone: 'info' },
  en_preparation: { label: 'En préparation (historique)', tone: 'info' },
  depose: { label: 'Déposé', tone: 'warning' },
  gagne: { label: 'Gagné', tone: 'success' },
  perdu: { label: 'Perdu', tone: 'danger' },
  abandonne: { label: 'Abandonné', tone: 'neutral' },
}
export const StatutAffaire = statusPill(STATUT_AFFAIRE)

// ── Pièce du dossier de soumission ──────────────────────────────────────────
export const STATUT_PIECE = {
  a_produire: { label: 'À produire', tone: 'neutral' },
  genere: { label: 'Généré', tone: 'info' },
  a_jour: { label: 'À jour', tone: 'success' },
  perime: { label: 'Périmé', tone: 'danger' },
  fourni: { label: 'Fourni', tone: 'success' },
  signe: { label: 'Signé', tone: 'success' },
  hors_controle: { label: 'Hors contrôle', tone: 'danger' },
}
export const StatutPiece = statusPill(STATUT_PIECE)

// ── Variante d'étude (retenue / alternative / sensibilité) ─────────────────
export const STATUT_VARIANTE = {
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  calcule: { label: 'Calculé', tone: 'info' },
  publiable: { label: 'Publiable', tone: 'success' },
  perime: { label: 'Périmé', tone: 'danger' },
}
export const StatutVariante = statusPill(STATUT_VARIANTE)

// ── Contrôle de la porte de cohérence croisée avant dépôt ──────────────────
export const STATUT_CONTROLE = {
  ok: { label: 'OK', tone: 'success' },
  avertissement: { label: 'Avertissement', tone: 'warning' },
  bloquant: { label: 'Bloquant', tone: 'danger' },
}
export const StatutControle = statusPill(STATUT_CONTROLE)

export default { StatutAffaire, StatutPiece, StatutVariante, StatutControle }
