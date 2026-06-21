/**
 * Pré-remplissage du diagnostic enrichi (handoff vers le formulaire de lead) +
 * l'aire géodésique du tracé. Extrait de roof-tool-pro11.ts (split modulaire
 * 2026-06-20) — comportement INCHANGÉ.
 *
 * GARDE-FOU PERMANENT : ce module ne poste AUCUN lead. Il n'écrit QUE dans les
 * champs du diagnostic existant (`lf-area`, `lf-orient`, `lf-kwc-est`, W110 :
 * `lf-name`/`lf-phone`/`lf-city` quand on les lui fournit + la ville géocodée
 * depuis `rp9-address`, et — pour le diagnostic « une page » de pro-11 — les
 * selects OBLIGATOIRES `billRange`/`roofType` pré-remplis depuis le simulateur)
 * et défile vers `#simulateur` ; toute la plomberie (seuil, consentement,
 * webhook, CAPI) reste celle du formulaire existant. Aucune requête réseau (ni
 * route lead, ni route de simulation) n'est émise ici.
 */
import { DEG2RAD, WGS84_RADIUS } from './constants';
import { $ } from './dom';
import { type Ctx } from './context';
import { type CardData } from './types';
import { BILL_RANGES } from '../../lib/billRange';
import { ROOF_TYPES } from '../../lib/lead';

/** W110 — coordonnées client OPTIONNELLES à reporter dans le diagnostic (handoff, jamais
 *  un POST). Toutes optionnelles : un champ absent/vide n'écrase rien. */
export interface LeadContact {
  name?: string;
  phone?: string;
  city?: string;
}

export interface Prefill {
  geodesicArea: () => number;
  prefillLead: (d: CardData, contact?: LeadContact) => void;
}

// Tranche de facture mensuelle (MAD) ↔ id `BILL_RANGES`. Le simulateur saisit un
// montant LIBRE en MAD/mois ; on le range dans le bon bucket pour pré-remplir le
// select obligatoire `billRange`. Bornes alignées 1:1 sur les libellés de
// `lib/billRange.ts` (lt800 · 800-1000 · 1000-1500 · 1500-3000 · 3000-5000 ·
// 5000-10000 · gt10000). Renvoie '' si le montant n'est pas un nombre fini > 0.
export function billRangeIdForAmount(mad: number): string {
  if (!Number.isFinite(mad) || mad <= 0) return '';
  if (mad < 800) return 'lt800';
  if (mad < 1000) return '800-1000';
  if (mad < 1500) return '1000-1500';
  if (mad < 3000) return '1500-3000';
  if (mad < 5000) return '3000-5000';
  if (mad < 10000) return '5000-10000';
  return 'gt10000';
}

// Type de toit du builder (flat/pitched) ↔ option `ROOF_TYPES` du formulaire.
// Toit plat → 'toit_plat' ; toit en pente → 'villa' (le plus courant en pente).
// Les deux ids existent dans `ROOF_TYPES` (lib/lead.ts) ; repli 'autre' sinon.
export function roofTypeIdForBuilder(t: 'flat' | 'pitched'): string {
  const id = t === 'flat' ? 'toit_plat' : 'villa';
  return ROOF_TYPES.some((r) => r.id === id) ? id : 'autre';
}

export function createPrefill(ctx: Ctx): Prefill {
  function geodesicArea(): number {
    // surface tracée (m²) pour pré-remplir le champ « surface toit »
    const ring = ctx.vertices;
    if (ring.length < 3) return 0;
    let total = 0;
    for (let i = 0; i < ring.length; i++) {
      const [lng1, lat1] = ring[i];
      const [lng2, lat2] = ring[(i + 1) % ring.length];
      total += (lng2 - lng1) * DEG2RAD * (2 + Math.sin(lat1 * DEG2RAD) + Math.sin(lat2 * DEG2RAD));
    }
    return Math.abs((total * WGS84_RADIUS * WGS84_RADIUS) / 2);
  }

  /** W85 — Orientation `enrichment.ORIENTATIONS` déduite de la config GAGNANTE,
   *  pour que le diagnostic reçoive la VRAIE face (et non « sud » en dur). Toit
   *  plat : la famille sud ET la famille est-ouest se rapportent au sud (la liste
   *  d'orientations n'a pas d'« est-ouest »). Toit en pente : on mappe l'azimut de
   *  face réel (180→sud, 135→sud-est, 225→sud-ouest, 90→est, 270→ouest), au plus
   *  proche, avec repli « sud ». Lecture PURE de l'état `ctx` — n'écrit rien dans
   *  le formulaire, ne poste rien. */
  function leadOrientationId(): string {
    if (ctx.roofType === 'pitched') {
      const az = ((ctx.facingAzimuthDeg % 360) + 360) % 360;
      const targets: { az: number; id: string }[] = [
        { az: 180, id: 'sud' },
        { az: 135, id: 'sud-est' },
        { az: 225, id: 'sud-ouest' },
        { az: 90, id: 'est' },
        { az: 270, id: 'ouest' },
      ];
      let best = 'sud';
      let bestDiff = Infinity;
      for (const t of targets) {
        const diff = Math.abs(((az - t.az + 540) % 360) - 180);
        if (diff < bestDiff) {
          bestDiff = diff;
          best = t.id;
        }
      }
      return best;
    }
    // Toit plat : la famille sud ET la famille est-ouest se rapportent au sud.
    return 'sud';
  }

  function prefillLead(d: CardData, contact?: LeadContact) {
    // Pré-remplit le diagnostic enrichi — RÉUTILISE le même formulaire et toute sa
    // plomberie (seuil 1 000 MAD, consentement, webhook, CAPI) : on n'écrit que
    // dans ses champs, on ne poste AUCUN lead ici.
    const area = $<HTMLInputElement>('lf-area');
    const orient = $<HTMLSelectElement>('lf-orient');
    const kwc = $<HTMLInputElement>('lf-kwc-est');
    if (area) {
      // Correction « cos de la pente » : sur un toit incliné, le tracé satellite est la
      // projection HORIZONTALE — il paraît plus petit. La VRAIE surface de toiture =
      // projetée / cos(pente). Toit plat : inchangé (aucune correction). Garde-fou : si
      // cos(pente) ≤ 0 ou non fini (pente aberrante), on retombe sur la projetée.
      const projected = geodesicArea();
      let surface = projected;
      if (ctx.roofType === 'pitched') {
        const cosPitch = Math.cos(ctx.pitchDeg * DEG2RAD);
        if (Number.isFinite(cosPitch) && cosPitch > 0) surface = projected / cosPitch;
      }
      area.value = String(Math.round(surface));
    }
    if (orient) orient.value = leadOrientationId(); // W85 : face réelle de la config gagnante
    if (kwc) kwc.value = String(Math.round(d.kwc * 100) / 100);

    // W110 — flux en une page : reporte Nom / Téléphone / Ville quand fournis, et — à défaut
    // de ville saisie — la VILLE GÉOCODÉE depuis #rp9-address (handoff, jamais un POST). On
    // n'écrase un champ que si on a une vraie valeur (champ vide → on n'efface rien).
    const name = $<HTMLInputElement>('lf-name');
    const phone = $<HTMLInputElement>('lf-phone');
    const city = $<HTMLInputElement>('lf-city');
    const trimmedName = contact?.name?.trim();
    const trimmedPhone = contact?.phone?.trim();
    const trimmedCity = contact?.city?.trim();
    const geocodedAddress = ($<HTMLInputElement>('rp9-address')?.value ?? '').trim();
    if (name && trimmedName) name.value = trimmedName;
    if (phone && trimmedPhone) phone.value = trimmedPhone;
    const cityValue = trimmedCity || geocodedAddress;
    if (city && cityValue && !city.value.trim()) city.value = cityValue;

    // Diagnostic « une page » (pro-11) : le visiteur ne tape que Nom/Téléphone/Adresse.
    // On pré-remplit les selects OBLIGATOIRES (billRange, roofType) depuis le simulateur,
    // pour que la soumission passe sans saisie supplémentaire. On n'écrit que des valeurs
    // sûres (id connu) — sinon le visiteur complète lui-même.
    const billSelect = $<HTMLSelectElement>('lf-bill');
    const billInput = document.getElementById('rp9-bill') as HTMLInputElement | null;
    if (billSelect && billInput) {
      const mad = Number(String(billInput.value).replace(/\s/g, '').replace(',', '.'));
      const id = billRangeIdForAmount(mad);
      if (id && BILL_RANGES.some((r) => r.id === id)) billSelect.value = id;
    }
    const roofSelect = $<HTMLSelectElement>('lf-roof');
    if (roofSelect) roofSelect.value = roofTypeIdForBuilder(ctx.roofType);

    const details = (area?.closest('details') as HTMLDetailsElement | null) ?? null;
    if (details) details.open = true;
    document.getElementById('simulateur')?.scrollIntoView({ behavior: ctx.opts.reducedMotion ? 'auto' : 'smooth', block: 'start' });
  }

  return { geodesicArea, prefillLead };
}
