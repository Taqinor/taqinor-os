import { useHasPermission } from '../../../hooks/useHasPermission'

/* D-ACAL-104 (25/11/2026) — changer un réglage de la SOCIÉTÉ (réglages, préréglages, favoris, gabarits,
   fixation, allées, profils types…) exige le MÊME droit que d'appliquer ou retirer le profil de départ :
   `calepinage_approuver` (serveur : `permissions.py::exiger_droit_reglages_societe`, 403 nommé). Sans lui,
   l'écran se lit mais ne propose aucune saisie ni aucun bouton. UN seul endroit pour le code du droit. */
export const DROIT_REGLAGES_SOCIETE = 'calepinage_approuver'

/** Vrai quand la personne connectée peut CHANGER les réglages de la société. */
export function usePeutReglerSociete() {
  return useHasPermission(DROIT_REGLAGES_SOCIETE)
}

/** L'unique phrase, en mots d'utilisateur, de tous les écrans de réglages en lecture seule. */
export const PHRASE_REGLAGES_LECTURE_SEULE = 'Ces réglages de la société se lisent ici : seules les personnes '
  + 'qui peuvent approuver un calepinage peuvent les changer.'
