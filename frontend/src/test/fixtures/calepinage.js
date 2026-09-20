/* CAL223 — les échantillons de contrat du module Calepinage, nommés une fois
   pour tous les tests d'écran (PACT10/13 : jamais une charge utile retapée à la
   main). Chaque export lit le fichier committé sous
   backend/django_core/apps/calepinage/contract_samples/ via `contractSamples.js`
   — si un échantillon disparaît ou change de nom, ce module casse AVANT les
   écrans qui s'en servent. */
import { exempleContrat, reponseContrat } from './contractSamples'

export const ECHANTILLONS_CALEPINAGE = Object.freeze([
  'calepinage_design_context',
  'calepinage_detail',
  'calepinage_equipements',
  'calepinage_horizon',
  'calepinage_pompage',
  'calepinage_resultat',
  'calepinage_sorties',
  'dossiers_reglementaires',
  'lead_layout_public',
  'moteur_calculer',
  'parametres_calepinage',
  'pose',
  'site_imagerie',
  'variantes_comparer',
  'zones',
])

/** L'exemple (`exemple` par défaut, ou `exemple_vide`) d'un échantillon du module. */
export const exempleCalepinage = (nom, variante = 'exemple') =>
  exempleContrat('calepinage', nom, variante)

/** La réponse axios `{ data }` mockée depuis l'échantillon, pour `mockResolvedValue`. */
export const reponseCalepinage = (nom, variante = 'exemple') =>
  reponseContrat('calepinage', nom, variante)
