/**
 * Production solaire annuelle via PVGIS (API PVcalc de la Commission
 * européenne, JRC — gratuite, sans clé, couvre le Maroc). Appelée UNIQUEMENT
 * côté serveur (la route /api/roof-estimate) : le navigateur ne touche jamais
 * PVGIS. Paramétrée par fetchFn → testable hors réseau.
 *
 * Robustesse avant tout : toute panne (timeout, statut, JSON malformé,
 * coordonnées absurdes) renvoie `null` en silence. L'appelant bascule alors
 * sur le repli local (fallbackAnnualKwh) — le visiteur n'a jamais d'erreur.
 */

const PVGIS_ENDPOINT = 'https://re.jrc.ec.europa.eu/api/v5_2/PVcalc';
const DEFAULT_TILT_DEG = 15; // inclinaison « sensée » (pose Maroc, conservatrice)
const SYSTEM_LOSS_PCT = 14; // pertes système PVGIS par défaut
const TIMEOUT_MS = 6000;

/**
 * @param aspect azimut PVGIS (0=Sud, -90=Est, 90=Ouest, 180=Nord).
 * @returns production annuelle (kWh) ou null si indisponible.
 */
export async function fetchPvgisAnnualKwh(
  lat: number,
  lon: number,
  kwc: number,
  aspect: number,
  fetchFn: typeof fetch = fetch,
): Promise<number | null> {
  if (!Number.isFinite(kwc) || kwc <= 0) return null;
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return null;
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) return null;

  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    peakpower: String(kwc),
    loss: String(SYSTEM_LOSS_PCT),
    angle: String(DEFAULT_TILT_DEG),
    aspect: String(aspect),
    pvtechchoice: 'crystSi',
    mountingplace: 'building',
    outputformat: 'json',
  });

  try {
    const res = await fetchFn(`${PVGIS_ENDPOINT}?${params.toString()}`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: { accept: 'application/json' },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { outputs?: { totals?: { fixed?: { E_y?: unknown } } } };
    const eY = data?.outputs?.totals?.fixed?.E_y;
    if (typeof eY !== 'number' || !Number.isFinite(eY) || eY <= 0) return null;
    return eY;
  } catch {
    return null;
  }
}

/**
 * Variante PARAMÉTRÉE PAR L'INCLINAISON pour l'estimateur « cerveau »
 * (/preview/toiture-3d-pro-3) : même API PVGIS, même robustesse (null en silence),
 * mais l'angle est fourni (la table committée reste le repli instantané). N'altère
 * PAS fetchPvgisAnnualKwh (route /api/roof-estimate inchangée).
 *
 * @param tilt inclinaison en degrés.
 * @param aspect azimut PVGIS (0=Sud, -90=Est, 90=Ouest, 180=Nord).
 */
export async function fetchPvgisAnnualKwhAtTilt(
  lat: number,
  lon: number,
  kwc: number,
  aspect: number,
  tilt: number,
  fetchFn: typeof fetch = fetch,
  mountingplace: 'building' | 'free' = 'building',
): Promise<number | null> {
  if (!Number.isFinite(kwc) || kwc <= 0) return null;
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return null;
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) return null;
  if (!Number.isFinite(tilt) || tilt < 0 || tilt > 90) return null;

  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    peakpower: String(kwc),
    loss: String(SYSTEM_LOSS_PCT),
    angle: String(tilt),
    aspect: String(aspect),
    pvtechchoice: 'crystSi',
    // 'building' (pose intégrée, moins ventilée) par défaut — inchangé pour
    // pro-3/4/5/6 ; 'free' (panneaux sur racks aérés) pour le toit PLAT de pro-7,
    // PVGIS comme source de vérité (W20).
    mountingplace,
    outputformat: 'json',
  });

  try {
    const res = await fetchFn(`${PVGIS_ENDPOINT}?${params.toString()}`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: { accept: 'application/json' },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { outputs?: { totals?: { fixed?: { E_y?: unknown } } } };
    const eY = data?.outputs?.totals?.fixed?.E_y;
    if (typeof eY !== 'number' || !Number.isFinite(eY) || eY <= 0) return null;
    return eY;
  } catch {
    return null;
  }
}
