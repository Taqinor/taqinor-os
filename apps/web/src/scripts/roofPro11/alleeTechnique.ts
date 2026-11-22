// ACAL258 — L'ALLÉE TECHNIQUE DE CE CALEPINAGE (lecture/émission du document ; sorti de `prefill.ts`, ACAL585).
import { type Ctx } from './context';

/** L'allée technique du document relu (`{largeurM > 0, source}`, clés inconnues conservées), ou `null`. */
export function lireAlleeTechnique(doc: unknown): Ctx['alleeTechnique'] {
  const brut = (doc as { alleeTechnique?: unknown } | null | undefined)?.alleeTechnique;
  if (!brut || typeof brut !== 'object' || Array.isArray(brut)) return null;
  const { largeurM, source } = brut as { largeurM?: unknown; source?: unknown };
  if (typeof largeurM !== 'number' || !Number.isFinite(largeurM) || largeurM <= 0) return null;
  if (typeof source !== 'string' || !source) return null;
  return JSON.parse(JSON.stringify(brut)) as NonNullable<Ctx['alleeTechnique']>;
}

/** Fragment du document : `{ alleeTechnique }` quand elle existe, `{}` sinon (aucune clé inventée). */
export function emettreAlleeTechnique(allee: Ctx['alleeTechnique']): { alleeTechnique?: NonNullable<Ctx['alleeTechnique']> } {
  if (!allee || typeof allee.largeurM !== 'number' || !(allee.largeurM > 0)) return {};
  return { alleeTechnique: JSON.parse(JSON.stringify(allee)) as NonNullable<Ctx['alleeTechnique']> };
}
