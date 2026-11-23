/**
 * ACAL1423 — « Effacer » rend à la carte l'épingle du lead que la fermeture du toit avait masquée (ACAL972) :
 * le repère n'est jamais retiré, le document garde `pin` et `pinSource` (rien n'est écrit ici).
 */
import { masquerMarqueur, type MarqueurEpingle } from './epingleClient';

export function reafficherEpingleApresEffacement(marqueur: MarqueurEpingle | null): void {
  masquerMarqueur(marqueur, false);
}
