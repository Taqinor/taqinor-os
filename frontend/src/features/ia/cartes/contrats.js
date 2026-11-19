// Copilote vague 2 (B0, 19/11/2026) — QUEL échantillon de contrat nourrit
// chaque carte du vocabulaire (plan R4 §C.0-a ; cartes du registre
// `apps/agent/registry.py`, CARTES). Une carte → `[app, nom]`, lu par les tests
// au moment de l'exécution : `exempleContrat(...CONTRATS_CARTES.niveau_stock)`
// (`test/fixtures/contractSamples.js`, fichier
// `backend/django_core/apps/<app>/contract_samples/<nom>.json`). Un test de
// carte n'écrit JAMAIS sa charge utile à la main (PACT13). Module PUR.

/** Carte → [app, nom de l'échantillon sans « .json »]. */
export const CONTRATS_CARTES = Object.freeze({
  lien_ecran: Object.freeze(['agent', 'assistant_ouvrir']),
  fiche_calepinage: Object.freeze(['calepinage', 'calepinage_assistant_resume']),
  liste_calepinages: Object.freeze(['calepinage', 'calepinage_assistant_a_traiter']),
  contenance: Object.freeze(['calepinage', 'calepinage_assistant_contenance']),
  liste_visites: Object.freeze(['visites', 'assistant_agenda']),
  fiche_visite: Object.freeze(['visites', 'assistant_visite_resume']),
  charge_equipe: Object.freeze(['visites', 'assistant_charge']),
  liste_chantiers: Object.freeze(['installations', 'assistant_chantiers']),
  fiche_chantier: Object.freeze(['installations', 'assistant_chantier_etat']),
  vente_etat: Object.freeze(['ventes', 'assistant_vente_etat']),
  liste_impayes: Object.freeze(['ventes', 'assistant_impayes']),
  liste_factures: Object.freeze(['ventes', 'assistant_factures']),
  facture_brouillon: Object.freeze(['ventes', 'devis_facturer']),
  niveau_stock: Object.freeze(['stock', 'assistant_niveaux']),
  parc_client: Object.freeze(['sav', 'assistant_parc']),
  liste_tickets: Object.freeze(['sav', 'assistant_tickets']),
  fiche_ticket: Object.freeze(['sav', 'assistant_ticket_fiche']),
  chiffres_ca: Object.freeze(['reporting', 'assistant_ca']),
})

/** Carte → variante de l'échantillon quand ce n'est pas `exemple`. */
export const VARIANTES_CARTES = Object.freeze({
  facture_brouillon: 'exemple_brouillon_assistant',
})

/** Échantillons de la même forme qu'une carte, servis par une AUTRE action. */
export const CONTRATS_JUMEAUX = Object.freeze({
  fiche_calepinage: Object.freeze(['calepinage', 'calepinage_assistant_du_lead']),
  fiche_visite: Object.freeze(['visites', 'visite_annuler']),
  fiche_chantier: Object.freeze(['installations', 'chantier_planifier_pose']),
})

// Moitié CLIENTE de la citation exigée par
// scripts/check_contrats_calepinage_deux_moities.py (CALX385) ; la moitié
// serveur est `apps/calepinage/contrats_assistant.py` (même liste, même ordre).
export const CONTRATS_CALEPINAGE_ASSISTANT = Object.freeze([
  'calepinage_assistant_resume.json',
  'calepinage_assistant_du_lead.json',
  'calepinage_assistant_a_traiter.json',
  'calepinage_assistant_contenance.json',
  'calepinage_assistant_preparer.json',
  'calepinage_assistant_publier_apercu.json',
  'calepinage_assistant_publier_devis.json',
])
