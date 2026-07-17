/**
 * WJ123 — Constantes du décret 82-21 (injection du surplus d'autoproduction),
 * MIROIR STRICT de la source unique
 * SOURCE: backend/django_core/apps/ventes/quote_engine/constants_82_21.py (QX50).
 *
 * Décret 2-25-100 (loi 82-21), BO 9 mars 2026, en vigueur le 9 juin 2026 : il
 * rend l'injection MT/HT du surplus RÉELLE. TOUTES les valeurs sont ESTIMÉES
 * d'après la recherche 2026-07-16 et portent « à vérifier fondateur » — elles
 * pilotent une ligne OFF PAR DÉFAUT, activée devis par devis, et ne s'affichent
 * JAMAIS sans la mention réglementaire `MENTION_82_21`. Tout changement ici DOIT
 * être répliqué côté Python (test de parité).
 *
 * Module PUR : aucun DOM, aucune dépendance.
 */

// ── Tarif ANRE de rachat (mars 2026 → févr. 2027), DH/kWh ─────────────────────
// Recherche 2026-07-16 : 0,21 en pointe / 0,18 hors pointe. À VÉRIFIER FONDATEUR.
export const ANRE_TARIF_POINTE = 0.21; // DH/kWh — à vérifier fondateur
export const ANRE_TARIF_HORS_POINTE = 0.18; // DH/kWh — à vérifier fondateur

// ── Frais d'accès réseau à DÉDUIRE du tarif (centimes/kWh) ────────────────────
// Recherche 2026-07-16 : ≈ 6,07 + 6,38 c/kWh. À VÉRIFIER FONDATEUR.
export const FRAIS_RESEAU_C_KWH_1 = 6.07; // c/kWh — à vérifier fondateur
export const FRAIS_RESEAU_C_KWH_2 = 6.38; // c/kWh — à vérifier fondateur
export const FRAIS_RESEAU_DH_KWH = (FRAIS_RESEAU_C_KWH_1 + FRAIS_RESEAU_C_KWH_2) / 100.0; // 0,1245 DH/kWh

// ── Plafond d'injection = part MAX de la production injectable ─────────────────
// Recherche 2026-07-16 : 20 % de la production — DÉCRET EN RÉVISION. À vérifier.
export const PLAFOND_INJECTION_PCT = 20; // % de la production — en révision (à vérifier)

// ── Mention réglementaire OBLIGATOIRE affichée avec TOUTE ligne d'injection ────
export const MENTION_82_21 = 'Tarif ANRE 03/2026-02/2027, plafond en révision';

/**
 * Tarif NET (rachat ANRE − frais d'accès réseau), DH/kWh, jamais négatif.
 * L'injection solaire est DIURNE → valorisée par défaut au tarif HORS POINTE
 * net, choix prudent et honnête (jamais promettre la pointe sans stockage).
 * Miroir de net_tarif_dh_kwh().
 */
export function netTarifDhKwh(pointe = false): number {
  const base = pointe ? ANRE_TARIF_POINTE : ANRE_TARIF_HORS_POINTE;
  return Math.max(0, base - FRAIS_RESEAU_DH_KWH);
}

/**
 * Surplus injectable (kWh) plafonné à 20 % de la prod + sa valeur NETTE (DH).
 * surplus = max(0, production − autoconsommé), borné à PLAFOND_INJECTION_PCT de
 * la production ; valeur = surplus × tarif net. Retourne { kwh, dh }, tous deux
 * ≥ 0 et arrondis. Défensif : jamais d'exception. Miroir de injection_annuelle().
 */
export function injectionAnnuelle(
  productionKwh: number | null | undefined,
  autoconsommeKwh: number | null | undefined,
  pointe = false,
): { kwh: number; dh: number } {
  const prod = Math.max(0, Number(productionKwh) || 0);
  const auto = Math.max(0, Number(autoconsommeKwh) || 0);
  if (!Number.isFinite(prod) || !Number.isFinite(auto)) return { kwh: 0, dh: 0 };
  const surplus = Math.max(0, prod - auto);
  const plafond = (prod * PLAFOND_INJECTION_PCT) / 100.0;
  const kwh = Math.min(surplus, plafond);
  const dh = kwh * netTarifDhKwh(pointe);
  return { kwh: Math.round(kwh), dh: Math.round(dh) };
}
