/**
 * WJ123 / CIW403 — Constantes du surplus d'autoproduction (loi 82-21).
 *
 * Jumeau WEB aligné sur D-CIQ-4 (décisions fondateur du 03/10/2026 : ni
 * déduction de frais réseau, ni revente en basse tension). Le jumeau Python
 * (`backend/django_core/apps/ventes/quote_engine/constants_82_21.py`) et celui de
 * `frontend/src/features/ventes/solar.js` sont alignés par la partie D2 du plan :
 * cette tâche WEB ne touche que `apps/web`.
 *
 * SOURCES (chaque constante porte la sienne ci-dessous) :
 *  - plafond du surplus : loi 82-21 art. 12 ;
 *  - tarif d'excédent : décision ANRE 04/26 art. 6-7, période 01/03/2026-28/02/2027,
 *    indexé, HORS TAXES, rémunéré en MT/HT/THT SEULEMENT (jamais en BT).
 * Plus aucun frais d'accès réseau (TURD/TURT) n'est retranché du tarif :
 * D-CIQ-4 exclut toute déduction pour l'autoproduction sur site.
 *
 * Module PUR : aucun DOM, aucune dépendance.
 */

// ── Tarif d'excédent ANRE (01/03/2026 → 28/02/2027), DH/kWh HORS TAXES ────────
// Décision ANRE 04/26 art. 6-7 : 0,18 hors pointe / 0,21 en pointe, indexé.
export const ANRE_TARIF_POINTE = 0.21; // DH/kWh HT — ANRE 04/26 art. 7
export const ANRE_TARIF_HORS_POINTE = 0.18; // DH/kWh HT — ANRE 04/26 art. 7

// ── Plafond du surplus = part MAX de la production ANNUELLE injectable ─────────
// Loi 82-21 art. 12 ; décision ANRE 04/26 : 20 % — EN VIGUEUR.
export const PLAFOND_INJECTION_PCT = 20; // % de la production annuelle

/** Raccordements dont le surplus est rémunéré (MT/HT/THT seulement, jamais BT). */
export const RACCORDEMENTS_REMUNERES = ['mt', 'ht', 'tht'] as const;

/** Vrai quand le surplus d'un raccordement est rémunéré (BT / inconnu ⇒ faux). */
export function surplusRemunere(raccordement: string | null | undefined): boolean {
  return (RACCORDEMENTS_REMUNERES as readonly string[]).includes(String(raccordement ?? '').toLowerCase());
}

// ── Mention réglementaire OBLIGATOIRE affichée avec TOUTE ligne d'injection ────
export const MENTION_82_21 =
  "Surplus plafonné à 20 % de la production annuelle (loi 82-21 art. 12, ANRE décision 04/26) ; " +
  "tarif 0,18 DH/kWh hors pointe / 0,21 DH/kWh en pointe, hors taxes, en MT/HT/THT seulement " +
  "(01/03/2026-28/02/2027, indexé) ; aucune revente en basse tension";

/**
 * Tarif d'excédent HT (DH/kWh) — SANS aucun frais réseau retranché (D-CIQ-4).
 * L'injection solaire est DIURNE → valorisée par défaut au tarif HORS POINTE,
 * choix prudent et honnête (jamais promettre la pointe sans stockage).
 */
export function tarifExcedentDhKwh(pointe = false): number {
  return pointe ? ANRE_TARIF_POINTE : ANRE_TARIF_HORS_POINTE;
}

/**
 * Surplus injectable (kWh) plafonné à 20 % de la production annuelle + sa valeur
 * (DH, hors taxes). En BASSE TENSION (ou raccordement inconnu) : RIEN n'est
 * valorisé — `{ kwh: 0, dh: 0 }`. En MT/HT/THT : surplus = max(0, production −
 * autoconsommé), borné au plafond, valeur = surplus × tarif d'excédent, sans frais
 * réseau. Retourne { kwh, dh } ≥ 0 arrondis. Défensif : jamais d'exception.
 */
export function injectionAnnuelle(
  productionKwh: number | null | undefined,
  autoconsommeKwh: number | null | undefined,
  raccordement: string | null | undefined,
  pointe = false,
): { kwh: number; dh: number } {
  if (!surplusRemunere(raccordement)) return { kwh: 0, dh: 0 };
  const prod = Math.max(0, Number(productionKwh) || 0);
  const auto = Math.max(0, Number(autoconsommeKwh) || 0);
  if (!Number.isFinite(prod) || !Number.isFinite(auto)) return { kwh: 0, dh: 0 };
  const surplus = Math.max(0, prod - auto);
  const plafond = (prod * PLAFOND_INJECTION_PCT) / 100.0;
  const kwh = Math.min(surplus, plafond);
  const dh = kwh * tarifExcedentDhKwh(pointe);
  return { kwh: Math.round(kwh), dh: Math.round(dh) };
}
