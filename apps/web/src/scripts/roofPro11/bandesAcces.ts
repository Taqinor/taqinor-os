/**
 * ACAL721 — L'ENVELOPPE D'ACCÈS SOLAIRE ÉCRITE DANS LE DOCUMENT, et ses BANDES.
 *
 * Extrait de `roof-tool-pro11.ts::activeSolarAccessMeta` (mémo de date + enveloppe) pour y
 * ajouter, par module, l'accès de chaque BANDE (une par sous-chaîne de sa fiche,
 * `zones[].geometry.solarAccess.bandes`). Aucune constante : n vient de la fiche du module du
 * pan, sa géométrie de la fiche ou du module par défaut NOMMÉ de l'atelier. Sans `sousChaines`
 * ≥ 2 sur la fiche, AUCUNE bande n'est écrite — jamais complétée par `values`.
 */
import { centresDeBandes, type SolarAccessSummary } from '../../lib/shadingEngine';
import { cotesPourPan, estRefus, resoudreModuleDuPan, type ModuleDocument } from './moduleSelect';
import type { SerializedSolarAccess } from './prefill';

/** Date du DERNIER calcul écrit, par contenu (deux sérialisations sans geste = la MÊME date). */
export interface MemoAcces {
  cle: string;
  computedAt: string;
}

/** Accès de chaque bande de chaque module posé (aval → amont), ou `null` : fiche sans sous-chaînes. */
export function bandesDuPan(args: {
  catalogue: readonly ModuleDocument[];
  moduleId: string | null | undefined;
  panneaux: ReadonlyArray<{ cx: number; cy: number }>;
  inclinaisonDeg: number;
  azimutFaceDeg: number;
  /** `solarAccessAnnuel` de l'atelier : un accès annuel par point fourni. */
  acces: (points: Array<{ x: number; y: number }>) => SolarAccessSummary | null;
}): Array<number[] | null> | null {
  const module = resoudreModuleDuPan(args.catalogue, args.moduleId);
  const n = estRefus(module) ? 0 : (module.sousChaines ?? 0);
  const cotes = cotesPourPan(args.catalogue, args.moduleId);
  if (n < 2 || estRefus(cotes) || !args.panneaux.length) return null;
  const az = (args.azimutFaceDeg * Math.PI) / 180;
  const aval = { x: Math.sin(az), y: Math.cos(az) }; // aval = vers la face du pan (sud : y négatif)
  const penteH = cotes.courtM * Math.cos((args.inclinaisonDeg * Math.PI) / 180);
  const points = args.panneaux.flatMap((p) => centresDeBandes({ x: p.cx, y: p.cy }, aval, penteH, n));
  const resume = args.acces(points);
  if (!resume) return null;
  return args.panneaux.map((_, i) => resume.perModule.slice(i * n, (i + 1) * n));
}

/** L'enveloppe `solarAccess` d'un pan + le mémo de date mis à jour (+ `bandes` quand elles existent). */
export function enveloppeAccesSolaire(
  s: SolarAccessSummary,
  memo: MemoAcces | null,
  relu: SerializedSolarAccess | undefined,
  bandes: Array<number[] | null> | null,
): { acces: SerializedSolarAccess; memo: MemoAcces } {
  const method = { ...s.method } as Record<string, unknown>;
  const assumptions = {
    periode: 'annee', // ACAL138 — toujours l'année entière (contrat ACAL2)
    hypotheses: s.assumptions,
    moduleLePlusOmbrage: s.min,
    moduleLePlusDegage: s.max,
    moyennePan: s.average,
  };
  const cle = JSON.stringify([s.perModule, method, assumptions, ...(bandes ? [bandes] : [])]);
  let suivant = memo;
  if (!suivant || suivant.cle !== cle) {
    const reluCle = relu && JSON.stringify([relu.values, relu.method, relu.assumptions, ...(bandes ? [relu.bandes] : [])]);
    suivant = { cle, computedAt: reluCle === cle ? relu!.computedAt : new Date().toISOString() };
  }
  const acces: SerializedSolarAccess = { values: s.perModule, method, assumptions, computedAt: suivant.computedAt };
  if (bandes) acces.bandes = bandes;
  return { acces, memo: suivant };
}
