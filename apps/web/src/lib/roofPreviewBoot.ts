/**
 * ENF19 — activation paresseuse commune aux pages privées /preview/toiture*
 * (2D, 3D volumes, 3D réaliste). MapLibre (et Three.js pour la 3D réaliste) ne sont
 * téléchargés qu'au premier geste réel ; la clé publique MapTiler est lue à
 * l'exécution via /api/roof-config — absente → repli gracieux. Le repli ne s'affiche
 * QUE si la carte n'a jamais pu être créée : une fois créée (onReady), une erreur
 * ultérieure ne la fait jamais disparaître.
 *
 * `p` = préfixe des ids de la page (rt / r3 / rp) ; `load` = import() dynamique du
 * module d'outil (littéral dans la page, pour que le bundler le découpe) ;
 * `init` = nom de la fonction d'initialisation exportée par ce module ;
 * `extra` (facultatif) = options supplémentaires dérivées de la config reçue
 * (ex. jeton Mapbox de la variante pro-11).
 */
type RoofConfig = { available?: boolean; maptilerKey?: string; mapboxToken?: string };

export function startRoofPreview(
  p: string,
  load: () => Promise<Record<string, any>>,
  init: string,
  extra?: (cfg: RoofConfig) => Record<string, unknown>,
): void {
  const fallback = document.getElementById(`${p}-fallback`);
  const stage = document.getElementById(`${p}-stage`);
  const searchForm = document.getElementById(`${p}-search`) as HTMLFormElement | null;
  const addressEl = document.getElementById(`${p}-address`) as HTMLInputElement | null;
  const openBtn = document.getElementById(`${p}-open`);
  const placeholder = document.getElementById(`${p}-map-placeholder`);

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let started = false;
  let key = '';
  let cfgRecue: RoofConfig = {};

  function showFallback() {
    if (fallback) fallback.hidden = false;
    if (stage) stage.hidden = true;
  }

  async function boot(initialQuery?: string) {
    if (started || !key) return;
    started = true;
    let mapCreated = false;
    try {
      const mod = await load();
      placeholder?.remove();
      mod[init]({
        maptilerKey: key,
        ...(extra ? extra(cfgRecue) : {}),
        reducedMotion,
        initialQuery,
        onReady: () => {
          mapCreated = true;
        },
      });
    } catch {
      if (!mapCreated) {
        started = false;
        showFallback();
      }
    }
  }

  (async () => {
    try {
      const res = await fetch('/api/roof-config');
      const cfg = (await res.json()) as RoofConfig;
      if (!cfg.available || !cfg.maptilerKey) {
        showFallback();
        return;
      }
      key = cfg.maptilerKey;
      cfgRecue = cfg;
      searchForm?.addEventListener('submit', (e) => {
        e.preventDefault();
        boot(addressEl?.value.trim() || undefined);
      });
      openBtn?.addEventListener('click', () => boot());
    } catch {
      showFallback();
    }
  })();
}
