/**
 * ENF19 — fiches comparées par les pages /équipement (FR / EN / AR).
 * Mêmes quatre fiches partout ; seul le libellé des critères est traduit.
 */
import { ficheBySlug } from './fiches';

export const panneauCanadian = ficheBySlug('canadian-solar-710')!;
export const panneauJinko = ficheBySlug('jinko-710')!;
export const onduleurHuawei = ficheBySlug('onduleur-huawei-reseau')!;
export const onduleurDeye = ficheBySlug('onduleur-deye-hybride')!;
