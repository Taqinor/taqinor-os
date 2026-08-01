/* APX13 — LA CHAÎNE DOCUMENTAIRE, en un seul endroit.
   ---------------------------------------------------------------------------
   Le stepper `ui/DocumentStageTrack` (VX141) n'était câblé QUE sur la liste
   des devis et l'onglet Devis du workspace : il DISPARAISSAIT aux deux étapes
   suivantes du parcours (bon de commande, facture), là où l'utilisateur se
   demande justement « d'où vient ce document ? ». APX13 le pose sur les trois
   étapes ; la piste et les règles de dérivation vivent ici pour qu'il n'y ait
   qu'UNE définition de la chaîne.

   Couche STATUTS DOCUMENT (règle CLAUDE.md #4) uniquement :
   brouillon/envoyé/accepté puis BC/facturé/chantier. JAMAIS les clés du
   funnel STAGES.py (règle #2) — les deux couches ne se mélangent jamais,
   et aucune clé de stage CRM n'est importée dans ce fichier. */

export const DOC_STATUT_TRACK = [
  { key: 'brouillon', label: 'Brouillon' },
  { key: 'envoye', label: 'Envoyé' },
  { key: 'accepte', label: 'Accepté' },
  { key: 'bc', label: 'BC' },
  { key: 'facture', label: 'Facturé' },
  { key: 'chantier', label: 'Chantier' },
]

/* Position de la piste vue depuis une FACTURE.
   Une facture existe → l'amont (devis accepté, éventuel BC) est franchi par
   construction ; la puce courante est « Facturé ». Une facture ANNULÉE est
   une anomalie de la chaîne, pas un recul : la puce « Facturé » passe en
   rouge (`blocked`) au lieu de faire remonter la piste en arrière. */
export function factureTrack(facture) {
  const annulee = facture?.statut === 'annulee'
  return {
    current: 'facture',
    blocked: annulee ? ['facture'] : [],
  }
}

/* Position de la piste vue depuis un BON DE COMMANDE.
   `has_facture` est déjà servi par `BonCommandeSerializer` (aucun champ
   nouveau) : BC facturé → la piste avance d'un cran. Un BC annulé marque la
   puce « BC » en rouge — exactement la sémantique que DevisList donne déjà à
   `bon_commande_etat.mismatch`. */
export function bonCommandeTrack(bc) {
  const annule = bc?.statut === 'annule'
  return {
    current: bc?.has_facture ? 'facture' : 'bc',
    blocked: annule ? ['bc'] : [],
  }
}
