// RWEB17-M19 — POINT D'ENTRÉE UNIQUE du tunnel « mon-toit » (FR/EN/AR).
//
// `demarrerTunnel(CONFIG_<LOCALE>, chargeurs)` enchaîne les installateurs des huit
// sections dans l'ORDRE D'INSTALLATION documenté par `etat.ts` (M0) — celui des
// instructions de haut niveau des anciennes pages, plage par plage (RWEB17-M11…M18) :
// l'ordre des écouteurs et des rendus initiaux est donc celui d'avant la fusion. Chaque
// page se réduit à l'import de sa config et à cet appel ; elle fournit les imports
// DYNAMIQUES des modules lourds de la carte (`chargeurs` : roofPro11/captureBoot et
// roofPro11/viewerOnly), qui restent hors du bundle initial (WJ18) et hors de la garde
// `tsc` de src/lib.

import { creerContexte, type ContexteTunnel } from './contexte';
import { creerDom } from './dom';
import { creerEtat } from './etat';
import { installerPersistance, loadWizardState } from './persistance';
import { installerParcours } from './parcours';
import { installerSelections } from './selections';
import { installerCarteApercu3d, installerCarteBoot, installerCarteInstantane, type ChargeursCarte, type ContexteCarte } from './carte';
import { installerEstimationPro, type ContexteEstimationPro } from './estimationPro';
import {
  installerEstimationResidentielleAffichage, installerEstimationResidentielleCalcul,
  installerEstimationResidentielleSuivi, installerEstimationResidentielleZones,
  type ContexteEstimationResidentielle,
} from './estimationResidentielle';
import { installerCorpsLead, installerValidationChamps } from './validation';
import { installerEnvoi } from './envoi';
import type { ConfigTunnel } from './config';

export function demarrerTunnel(config: ConfigTunnel, chargeurs: ChargeursCarte, doc: Document = document): ContexteTunnel {
  const savedWizard = loadWizardState();
  const ctx = creerContexte(creerDom(doc), creerEtat(savedWizard, config.locale), config);
  const reducedMotion = (doc.defaultView ?? window).matchMedia('(prefers-reduced-motion: reduce)').matches;
  // Le Document, la préférence de mouvement et les chargeurs complètent la config de la carte.
  Object.assign(ctx.config, { doc, reducedMotion, chargeurs });
  const ctxCarte = ctx as unknown as ContexteCarte;
  const ctxResidentiel = ctx as unknown as ContexteEstimationResidentielle;

  // 1. persistance (jeton de funnel, bandeau hors ligne, instantané, beforeunload, crochets)
  const persistance = installerPersistance(ctx, savedWizard);
  // 2. parcours (ville/GPS, langue, `?mode=`) puis modes
  const parcours = installerParcours(ctx, savedWizard);
  parcours.brancherModes();
  // 3. sélections : visite, occupation, équipements, journée type
  const selections = installerSelections(ctx);
  selections.brancherVisiteOccupationEquipements();
  // 4. carte : boot, repli, geste et confirmation (crochet ensureMapBooted avant les étapes)
  installerCarteBoot(ctxCarte);
  parcours.brancherEtapes();
  parcours.brancherRappel();
  persistance.rehydrater();
  persistance.brancherPersistanceSurSaisie();
  selections.brancherGroupes();
  // 5-6. estimation résidentielle (affichage), instantané du toit, zones, pro/agricole, calcul
  installerEstimationResidentielleAffichage(ctxResidentiel);
  installerCarteInstantane(ctxCarte);
  installerEstimationResidentielleZones(ctxResidentiel);
  installerEstimationPro(ctx as unknown as ContexteEstimationPro);
  installerEstimationResidentielleCalcul(ctxResidentiel);
  parcours.brancherEstimation();
  installerEstimationResidentielleSuivi(ctxResidentiel);
  installerCarteApercu3d(ctxCarte);
  // 7. validation et corps du lead
  installerValidationChamps(ctx, doc);
  installerCorpsLead(ctx, doc);
  // 8. envoi et sortie, puis l'état initial après réhydratation complète
  installerEnvoi(ctx, doc);
  return ctx;
}
