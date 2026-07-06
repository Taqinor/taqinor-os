/* ============================================================================
   UX38–UX42 — Constantes partagées de la Gestion de projet.
   ----------------------------------------------------------------------------
   Pastilles de statut (via la fabrique `statusPill` du kit UX1) et listes de
   choix (miroir des `TextChoices` du backend `apps/gestion_projet/models.py`).
   Aucun nom de stage CRM ici — la machine à états projet est PROPRE au module
   (règle #2 : jamais mélangée au tunnel STAGES.py).
   ========================================================================== */
import { statusPill } from '../../ui/module'

// ── Projet.Statut ───────────────────────────────────────────────────────────
export const StatutProjet = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  planifie: { label: 'Planifié', tone: 'info' },
  en_cours: { label: 'En cours', tone: 'primary' },
  en_pause: { label: 'En pause', tone: 'warning' },
  termine: { label: 'Terminé', tone: 'success' },
  annule: { label: 'Annulé', tone: 'danger' },
})

// ── PhaseProjet.Statut / Tache.Statut ───────────────────────────────────────
export const StatutPhase = statusPill({
  a_venir: { label: 'À venir', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'primary' },
  terminee: { label: 'Terminée', tone: 'success' },
})

export const StatutTache = statusPill({
  a_faire: { label: 'À faire', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'primary' },
  termine: { label: 'Terminée', tone: 'success' },
  bloque: { label: 'Bloquée', tone: 'danger' },
})

// ── Jalon.Statut ────────────────────────────────────────────────────────────
export const StatutJalon = statusPill({
  a_venir: { label: 'À venir', tone: 'neutral' },
  atteint: { label: 'Atteint', tone: 'success' },
  manque: { label: 'Manqué', tone: 'danger' },
})

// ── Risque.Statut ───────────────────────────────────────────────────────────
export const StatutRisque = statusPill({
  ouvert: { label: 'Ouvert', tone: 'danger' },
  surveille: { label: 'Surveillé', tone: 'warning' },
  maitrise: { label: 'Maîtrisé', tone: 'info' },
  clos: { label: 'Clos', tone: 'success' },
})

// ── ActionProjet.Statut ─────────────────────────────────────────────────────
export const StatutAction = statusPill({
  a_faire: { label: 'À faire', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'primary' },
  fait: { label: 'Fait', tone: 'success' },
  annule: { label: 'Annulé', tone: 'danger' },
})

// ── ActionProjet.Priorite ───────────────────────────────────────────────────
export const PrioriteAction = statusPill({
  basse: { label: 'Basse', tone: 'neutral' },
  moyenne: { label: 'Moyenne', tone: 'info' },
  haute: { label: 'Haute', tone: 'warning' },
})

// ── Timesheet.Statut (XPRJ1 — cycle de vie propre, jamais STAGES.py) ────────
export const StatutTimesheet = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  soumise: { label: 'Soumise', tone: 'info' },
  approuvee: { label: 'Approuvée', tone: 'success' },
  rejetee: { label: 'Rejetée', tone: 'danger' },
})

// ── BudgetProjet.Statut ─────────────────────────────────────────────────────
export const StatutBudget = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  valide: { label: 'Validé', tone: 'success' },
  archive: { label: 'Archivé', tone: 'info' },
})

// ── LotSousTraitance.Statut ─────────────────────────────────────────────────
export const StatutLot = statusPill({
  prevu: { label: 'Prévu', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'primary' },
  receptionne: { label: 'Réceptionné', tone: 'success' },
  annule: { label: 'Annulé', tone: 'danger' },
})

// ── Listes de choix (miroir backend) ────────────────────────────────────────
export const STATUTS_PROJET = [
  { value: 'brouillon', label: 'Brouillon' },
  { value: 'planifie', label: 'Planifié' },
  { value: 'en_cours', label: 'En cours' },
  { value: 'en_pause', label: 'En pause' },
  { value: 'termine', label: 'Terminé' },
  { value: 'annule', label: 'Annulé' },
]

export const TYPES_PHASE = [
  { value: 'etude', label: 'Étude' },
  { value: 'appro', label: 'Approvisionnement' },
  { value: 'pose', label: 'Pose' },
  { value: 'mes', label: 'Mise en service' },
  { value: 'reception', label: 'Réception' },
]

export const TYPES_CIBLE = [
  { value: 'devis', label: 'Devis' },
  { value: 'facture', label: 'Facture' },
  { value: 'ticket', label: 'Ticket SAV' },
  { value: 'achat', label: 'Achat' },
]

export const TYPES_DEPENDANCE = [
  { value: 'fs', label: 'Fin → Début (FS)' },
  { value: 'ss', label: 'Début → Début (SS)' },
  { value: 'ff', label: 'Fin → Fin (FF)' },
  { value: 'sf', label: 'Début → Fin (SF)' },
]

export const CATEGORIES_BUDGET = [
  { value: 'materiel', label: 'Matériel' },
  { value: 'main_oeuvre', label: "Main-d'œuvre" },
  { value: 'sous_traitance', label: 'Sous-traitance' },
  { value: 'divers', label: 'Divers' },
]

export const CATEGORIES_RISQUE = [
  { value: 'technique', label: 'Technique' },
  { value: 'delai', label: 'Délai' },
  { value: 'cout', label: 'Coût' },
  { value: 'fournisseur', label: 'Fournisseur' },
  { value: 'reglementaire', label: 'Réglementaire' },
  { value: 'securite', label: 'Sécurité' },
  { value: 'autre', label: 'Autre' },
]

export const TYPES_INDISPO = [
  { value: 'conge', label: 'Congé' },
  { value: 'formation', label: 'Formation' },
  { value: 'arret', label: 'Arrêt' },
]

export const TYPES_DOC = [
  { value: 'plan', label: 'Plan' },
  { value: 'note', label: 'Note de calcul' },
  { value: 'photo', label: 'Photo' },
  { value: 'contrat', label: 'Contrat' },
  { value: 'pv', label: 'Procès-verbal' },
  { value: 'autre', label: 'Autre' },
]

export const TYPES_INSTALLATION = [
  { value: 'residentiel', label: 'Résidentiel' },
  { value: 'industriel', label: 'Industriel / Commercial' },
  { value: 'agricole', label: 'Agricole (pompage)' },
  { value: 'autre', label: 'Autre' },
]

export const CIBLE_TYPES = [
  { value: 'projet', label: 'Projet' },
  { value: 'tache', label: 'Tâche' },
  { value: 'risque', label: 'Risque' },
  { value: 'action', label: 'Action' },
  { value: 'jalon', label: 'Jalon' },
  { value: 'document', label: 'Document' },
]

// Transitions de statut autorisées côté serveur (miroir de la machine à états
// du ProjetViewSet). Chaque entrée : { key, label, from:[statuts], apiFn }.
export const PROJET_TRANSITIONS = [
  { key: 'planifier', label: 'Planifier', from: ['brouillon'], api: 'planifierProjet' },
  { key: 'demarrer', label: 'Démarrer', from: ['planifie', 'en_pause'], api: 'demarrerProjet' },
  { key: 'mettre-en-pause', label: 'Mettre en pause', from: ['en_cours'], api: 'mettreEnPauseProjet' },
  { key: 'reprendre', label: 'Reprendre', from: ['en_pause'], api: 'reprendreProjet' },
  { key: 'terminer', label: 'Terminer', from: ['en_cours'], api: 'terminerProjet' },
  { key: 'annuler', label: 'Annuler', from: ['brouillon', 'planifie', 'en_cours', 'en_pause'], api: 'annulerProjet' },
]

// Petit utilitaire de message d'erreur serveur → texte FR lisible.
export function errMessage(err, fallback) {
  const data = err?.response?.data
  if (typeof data === 'string') return data
  if (data?.detail) return data.detail
  if (data && typeof data === 'object') {
    const first = Object.values(data)[0]
    if (Array.isArray(first)) return String(first[0])
    if (typeof first === 'string') return first
  }
  return fallback
}
