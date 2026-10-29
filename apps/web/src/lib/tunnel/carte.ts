// RWEB17-M4 — SECTION « CARTE ET TOITURE » du tunnel « mon-toit », en UN module
// pour FR/EN/AR (extraite de la page FR ; les écarts de locale vivent dans
// `ConfigCarte`). Livrée SEULE : aucune page ne l'importe encore (M14 la câble).
//
// Possède (voir l'en-tête d'`etat.ts`) : capturePin, captureOutline, capturePans,
// captureLayout, started, mapFetchDone, roofInputMode, confirmedPinKey,
// roofImageSpecPromise, panels3dStarted. Elle LIT cityTouched, lastKwc.
//
// CROCHETS REQUIS (inscrits par d'autres sections) : `syncCityRequirement`
// (parcours), `markDataEntered` et `saveWizardState` (persistance),
// `langueActive` (parcours ; seulement si `config.langueBasculable`).
// CROCHETS INSCRITS ICI : `ensureMapBooted`, `updatePanels3dVisibility`,
// `tryRoofSnapshot`.
//
// Les imports lourds (MapLibre/captureBoot, Three/viewerOnly) restent DYNAMIQUES :
// la page les fournit par `config.chargeurs` (`() => import('…/roofPro11/…')`).
// Aucun type de scripts/roofPro11 n'entre ainsi dans la garde `tsc` de src/lib.

import type { ContexteTunnel, ConfigLocale } from './contexte';
import type { LocaleTunnel, RoofImageSpecEtat } from './etat';

type Langue = 'fr' | 'ar' | 'en';

export interface TextesCarte {
  /** Statut après passage au geste « dessiner ». */
  tracer: string;
  /** Statut après passage au geste « pointer ». */
  pointer: string;
  /** Statut après confirmation du repère. */
  confirme: string;
  /** Statut après « ajuster » le repère. */
  ajuster: string;
  /** Libellé du bouton 3D quand l'aperçu échoue. */
  apercu3dIndisponible: string;
}

/** Textes de la page FR (par défaut sur FR ; AR bascule sur `ar`). */
export const TEXTES_CARTE: Record<Langue, TextesCarte> = {
  fr: {
    tracer: 'Tracez le contour de votre toit : appuyez sur chaque coin, puis « Terminer le tracé ».',
    pointer: 'Appuyez sur votre toit pour y poser le repère.',
    confirme: 'Repère confirmé. Continuez avec vos coordonnées ci-dessous.',
    ajuster: 'Appuyez sur le bon endroit de votre toit pour déplacer le repère.',
    apercu3dIndisponible: 'Aperçu 3D indisponible sur cet appareil',
  },
  ar: {
    tracer: 'ارسموا محيط سطحكم: اضغطوا على كل زاوية، ثم « إنهاء الرسم ».',
    pointer: 'اضغطوا على سطحكم لوضع العلامة عليه.',
    confirme: 'تم تأكيد العلامة. تابعوا بمعلومات الاتصال أدناه.',
    ajuster: 'اضغطوا على المكان الصحيح من سطحكم لتحريك العلامة.',
    apercu3dIndisponible: 'المعاينة ثلاثية الأبعاد غير متوفرة',
  },
  en: {
    tracer: 'Trace your roof outline: tap each corner, then "Finish tracing".',
    pointer: 'Tap your roof to drop the pin on it.',
    confirme: 'Pin confirmed. Carry on with your contact details below.',
    ajuster: 'Tap the right spot on your roof to move the pin.',
    apercu3dIndisponible: '3D preview unavailable on this device',
  },
};

/** Chargeurs des modules lourds, fournis par la page (imports dynamiques). */
export interface ChargeursCarte {
  captureBoot: () => Promise<{ bootCaptureOnly: (opts: any) => unknown }>;
  viewerOnly: () => Promise<{
    buildPublicRoofImageSpec?: (a: { outline: Array<[number, number]> }) => Promise<any>;
    createRoofViewer: (stage: HTMLElement, model: any, opts: any) => unknown;
  }>;
}

export interface ConfigCarte {
  doc: Document;
  reducedMotion: boolean;
  /** Estimation publique gatée (constante de la page). */
  estimationGatee: boolean;
  /** Aperçu 3D autorisé même en parcours gaté (constante de la page). */
  apercu3dPublic: boolean;
  /** AR seulement : les statuts suivent la langue affichée (fr/ar). Sinon les
   *  textes sont ceux de la locale de la page (fr pour FR, en pour EN). */
  statutsSuiventLangue: boolean;
  /** Options propres à la locale passées à `bootCaptureOnly` : `strings`, `dir`,
   *  `geolocateErrorMsg`, `panStrings` (absentes sur FR). */
  optionsBootLocale: Record<string, unknown>;
  chargeurs: ChargeursCarte;
}

export type ContexteCarte = Omit<ContexteTunnel, 'config'> & { config: ConfigLocale & ConfigCarte };

export const FETCH_TIMEOUT_MS = 10_000;

export const pinKey = (p: { lat: number; lng: number } | null) =>
  p ? `${p.lat.toFixed(6)},${p.lng.toFixed(6)}` : '';

function langueTextes(ctx: ContexteCarte, pourStatut: boolean): Langue {
  const loc: LocaleTunnel = ctx.config.locale;
  if (loc === 'en') return 'en';
  if (pourStatut && !ctx.config.statutsSuiventLangue) return 'fr';
  return ctx.crochets.a('langueActive') && ctx.crochets.appeler('langueActive') === 'ar' ? 'ar' : 'fr';
}

function construireCarte(ctx: ContexteCarte) {
  const { etat, dom, config } = ctx;
  const { $ } = dom;
  const doc = config.doc;
  const reducedMotion = config.reducedMotion;
  const cityEl = $('mt-city') as HTMLInputElement | null;
  const addressEl = $('rp9-address') as HTMLInputElement | null;
  const fallback = $('mt-fallback');
  const mapEl = $('rp9-map');
  const pinConfirmEl = $('mt-pin-confirm');
  const pinConfirmAddrEl = $('mt-pin-confirm-address');
  const panels3dBlock = $('mt-panels3d') as HTMLElement | null;
  const panels3dStage = $('mt-panels3d-stage') as HTMLElement | null;
  const panels3dOverlay = $('mt-panels3d-overlay') as HTMLElement | null;
  const panels3dStart = $('mt-panels3d-start') as HTMLButtonElement | null;
  const panels3dHint = $('mt-panels3d-hint') as HTMLElement | null;

  const statut = () => TEXTES_CARTE[langueTextes(ctx, true)];

  function clearMapSkeleton() { mapEl?.classList.remove('mt-skeleton-shimmer'); }

  function setMapStatus(msg: string) {
    const el = $('rp9-status');
    if (el) el.textContent = msg;
  }
  function syncRoofModeCards() {
    doc.querySelectorAll<HTMLButtonElement>('.mt-roof-mode').forEach((b) => {
      const on = b.dataset.value === etat.roofInputMode;
      b.setAttribute('aria-pressed', String(on));
      b.classList.toggle('border-brass-400', on);
      b.classList.toggle('border-white/15', !on);
    });
    // « Terminer le tracé » ne veut rien dire quand on ne trace pas.
    const finishBtn = $('rp9-finish');
    if (finishBtn) finishBtn.hidden = etat.roofInputMode !== 'draw';
  }
  /** Montre la confirmation UNIQUEMENT quand elle a un sens : geste « pointer »,
   *  un repère posé, aucun contour tracé, et pas déjà confirmé pour ce repère. */
  function syncPinConfirm() {
    if (!pinConfirmEl) return;
    pinConfirmEl.hidden = !(
      etat.roofInputMode === 'point'
      && etat.capturePin != null
      && etat.captureOutline.length < 3
      && pinKey(etat.capturePin) !== etat.confirmedPinKey
    );
  }
  /** Adresse du repère — affichée seulement si le géocodage inverse en a rendu
   *  une : jamais une adresse devinée, jamais une ligne vide. */
  function setPinConfirmAddress(addr?: string | null) {
    if (!pinConfirmAddrEl) return;
    const a = (addr || '').trim();
    pinConfirmAddrEl.textContent = a;
    pinConfirmAddrEl.hidden = a === '';
  }

  // Repli carte : champ d'adresse en clair, suite ouverte, bloc carte masqué.
  function showFallback() {
    const masquer = (id: string) => {
      const el = $(id);
      if (el) el.hidden = true;
    };
    clearMapSkeleton();
    if (fallback) fallback.hidden = false;
    masquer('mt-stage');
    masquer('mt-roof-mode-group');
  }

  async function boot(key: string, mapboxToken: string) {
    if (etat.started) return;
    etat.started = true;
    try {
      const { bootCaptureOnly } = await config.chargeurs.captureBoot();
      bootCaptureOnly({
        maptilerKey: key,
        mapboxToken: mapboxToken || undefined,
        reducedMotion,
        onReady: clearMapSkeleton,
        ...config.optionsBootLocale,
        roofInputMode: () => etat.roofInputMode,
        hydratePans: etat.capturePans.length >= 2 ? etat.capturePans : undefined,
        hydrate: etat.capturePin
          ? { lead: { roof_point: etat.capturePin, roof_outline: etat.captureOutline.length >= 3 ? etat.captureOutline : null } }
          : undefined,
        onCaptureChange: (s: any) => {
          etat.capturePin = s.pin;
          etat.captureOutline = s.outline;
          etat.capturePans = s.pans;
          etat.captureLayout = s.layout;
          ctx.crochets.appeler('syncCityRequirement');
          etat.roofImageSpecPromise = null;
          if (cityEl && !etat.cityTouched) {
            const depuisCarte = (s.address && s.address.trim()) || addressEl?.value.trim() || '';
            if (depuisCarte) cityEl.value = depuisCarte;
          }
          [() => setPinConfirmAddress(s.address), syncPinConfirm, updatePanels3dVisibility].forEach((f) => f());
        },
      });
    } catch {
      etat.started = false;
      showFallback();
    }
  }

  // Un seul fetch /api/roof-config par visite, et seulement quand l'étape 0 est active.
  function ensureMapBooted() {
    if (etat.mapFetchDone) return;
    etat.mapFetchDone = true;
    (async () => {
      try {
        const reponse = await fetch('/api/roof-config', { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
        const cfg = (await reponse.json()) as { available?: boolean; maptilerKey?: string; mapboxToken?: string };
        const cleCarte = cfg.maptilerKey;
        if (!cfg.available || !cleCarte) {
          showFallback();
          return;
        }
        void boot(cleCarte, cfg.mapboxToken || '');
      } catch {
        showFallback();
      }
    })();
  }

  const brancherBoot = () => {
  doc.querySelectorAll<HTMLButtonElement>('.mt-roof-mode').forEach((b) => {
    b.addEventListener('click', () => {
      const v: 'point' | 'draw' = b.dataset.value === 'draw' ? 'draw' : 'point';
      if (v === etat.roofInputMode) return;
      etat.roofInputMode = v;
      syncRoofModeCards();
      syncPinConfirm();
      setMapStatus(etat.roofInputMode === 'draw' ? statut().tracer : statut().pointer);
      ctx.crochets.appeler('markDataEntered');
      ctx.crochets.appeler('saveWizardState');
    });
  });
  $('mt-pin-confirm-yes')?.addEventListener('click', () => {
    etat.confirmedPinKey = pinKey(etat.capturePin);
    syncPinConfirm();
    setMapStatus(statut().confirme);
  });
  $('mt-pin-confirm-adjust')?.addEventListener('click', () => {
    // On ne SUPPRIME pas le repère : le visiteur en pose simplement un autre.
    etat.confirmedPinKey = '';
    if (pinConfirmEl) pinConfirmEl.hidden = true;
    setMapStatus(statut().ajuster);
    $('rp9-map')?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'center' });
  });
  syncRoofModeCards();
  ctx.crochets.installer('ensureMapBooted', ensureMapBooted);
  };

  // Instantané satellite du toit, mis en cache jusqu'à ce que le contour change.
  function fetchRoofImageSpec(): Promise<RoofImageSpecEtat | null> {
    if (!etat.roofImageSpecPromise) {
      etat.roofImageSpecPromise = (async () => {
        if (etat.captureOutline.length < 3) return null;
        const mod = await config.chargeurs.viewerOnly();
        if (typeof mod.buildPublicRoofImageSpec !== 'function') return null;
        const spec = await mod.buildPublicRoofImageSpec({ outline: etat.captureOutline });
        return spec && spec.image ? (spec as RoofImageSpecEtat) : null;
      })().catch(() => null);
    }
    return etat.roofImageSpecPromise;
  }
  /** « Votre toit » dans le document : photo satellite + attribution fournisseur,
   *  UNIQUEMENT quand un contour ≥ 3 sommets existe. */
  async function tryRoofSnapshot() {
    const fig = $('mt-doc-roof');
    const img = $('mt-doc-roof-img') as HTMLImageElement | null;
    if (!fig || !img) return;
    if (etat.captureOutline.length < 3) {
      fig.hidden = true;
      return;
    }
    const instantane = await fetchRoofImageSpec();
    if (!instantane) return;
    img.src = instantane.image.src;
    const attribution = $('mt-doc-roof-attr');
    if (attribution) attribution.textContent = instantane.attribution || '';
    fig.hidden = false;
  }

  /** Le bouton 3D n'apparaît QUE si un contour (≥ 3 sommets) a été tracé ET qu'un
   *  kWc est disponible. */
  function updatePanels3dVisibility() {
    if (!panels3dBlock) return;
    if (config.estimationGatee && !config.apercu3dPublic) { panels3dBlock.hidden = true; return; }
    const eligible = etat.captureOutline.length >= 3 && etat.lastKwc != null;
    panels3dBlock.hidden = !eligible;
  }

  async function startPanels3d() {
    if (etat.panels3dStarted || !panels3dStage || etat.lastKwc == null) return;
    etat.panels3dStarted = true;
    try {
      const [{ capturePreviewLayout, buildViewerModel }, { createRoofViewer }] = await Promise.all([
        import('../proposition'),
        config.chargeurs.viewerOnly(),
      ]);
      const layout = capturePreviewLayout(etat.captureOutline, etat.lastKwc);
      const model = layout ? buildViewerModel(layout) : null;
      if (!model) throw new Error(config.locale === 'en' ? 'model unavailable' : 'modèle indisponible');
      const roofImage = await fetchRoofImageSpec().catch(() => null);
      const navig = (doc.defaultView?.navigator ?? ({} as Navigator)) as Navigator & { deviceMemory?: number };
      const lowEnd = (navig.deviceMemory != null && navig.deviceMemory <= 4) || (navig.hardwareConcurrency || 8) <= 4;
      const handle = createRoofViewer(panels3dStage, model, {
        roofImage,
        lowEnd,
        reducedMotion,
        onReady: () => {
          if (panels3dOverlay) panels3dOverlay.hidden = true;
          if (panels3dHint) panels3dHint.hidden = false;
        },
        onFail: () => { etat.panels3dStarted = false; },
      });
      if (!handle) throw new Error(config.locale === 'en' ? 'WebGL unavailable' : 'WebGL indisponible');
    } catch {
      // Repli gracieux : le bouton reste, avec un message sobre — jamais de blocage.
      etat.panels3dStarted = false;
      if (panels3dOverlay) {
        const btn = panels3dStart;
        if (btn) {
          btn.disabled = true;
          btn.textContent = TEXTES_CARTE[langueTextes(ctx, false)].apercu3dIndisponible;
        }
      }
    }
  }
  const brancherApercu3d = () => {
    panels3dStart?.addEventListener('click', () => { void startPanels3d(); });
    // « Imprimer / Enregistrer en PDF » : le document s'imprime tel quel.
    $('mt-print-estimate')?.addEventListener('click', () => {
      doc.defaultView?.print();
    });
    ctx.crochets.installer('updatePanels3dVisibility', updatePanels3dVisibility);
  };
  const brancherInstantane = () => {
    ctx.crochets.installer('tryRoofSnapshot', tryRoofSnapshot);
  };
  return { brancherBoot, brancherInstantane, brancherApercu3d };
}

// Une seule construction par contexte : les installeurs par plage partagent les
// mêmes fermetures (état, éléments) quel que soit l'ordre où la page les appelle.
const construits = new WeakMap<object, ReturnType<typeof construireCarte>>();
const carteDe = (ctx: ContexteCarte) => {
  let c = construits.get(ctx);
  if (!c) { c = construireCarte(ctx); construits.set(ctx, c); }
  return c;
};

/** FR l. 2809-2925 + 3127-3197 : boot de la carte, repli, mode point/tracé,
 *  confirmation du repère (et crochet `ensureMapBooted`). */
export function installerCarteBoot(ctx: ContexteCarte): void { carteDe(ctx).brancherBoot(); }
/** FR l. 3497-3528 : instantané satellite du document (crochet `tryRoofSnapshot`). */
export function installerCarteInstantane(ctx: ContexteCarte): void { carteDe(ctx).brancherInstantane(); }
/** FR l. 4198-4270 : aperçu 3D, impression (crochet `updatePanels3dVisibility`). */
export function installerCarteApercu3d(ctx: ContexteCarte): void { carteDe(ctx).brancherApercu3d(); }
/** Les trois plages, dans l'ordre de la page. */
export function installerCarte(ctx: ContexteCarte): void {
  installerCarteBoot(ctx);
  installerCarteInstantane(ctx);
  installerCarteApercu3d(ctx);
}
