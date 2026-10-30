// RWEB17-M2 — SECTION « PARCOURS » du tunnel « mon-toit » (FR/EN/AR) : modes,
// étapes, langue affichée, rappel téléphonique, squelette et clic « estimation ».
//
// Extrait À L'IDENTIQUE de la page FR. Le code est identique sur les trois
// locales ; seules diffèrent (1) les trois tables de libellés (ci-dessous,
// `TABLES_PARCOURS`) et (2) la langue AFFICHÉE au chargement : FR → 'fr',
// AR → 'ar' (la route /ar/ s'ouvre en arabe, WJ38), EN → sans bascule
// (`config.langueBasculable` faux : ni `prepareI18n` ni `applyLang`).
// Possède `mode`, `cityTouched`, `currentLang`, `step`, `revealed`,
// `firstRender` (de `ctx.etat`). Aucune page ne l'importe encore (M12).
//
// CROCHETS REQUIS (autres sections) : `saveWizardState`, `markDataEntered`,
// `hasReachedConsentStep`, `sendFunnelBeacon` (persistance) ; `ensureMapBooted`
// (carte) ; `validateStep0`, `validateStep1` (validation) ; `computeEstimate`,
// `showWhatsappOffer` (estimation). INSCRITS ICI : `goStep`, `renderStep`,
// `syncStepLabels`, `syncStep2Panels`, `syncRaisonSociale`, `syncModeCards`,
// `isProMode`, `syncCityRequirement`, `syncCallbackSla`, `applyLang`,
// `langueActive`, `showEstimateSkeleton`, `thinkingDelayMs`, `modeLabel`,
// `modeDocSubtitle` (RWEB17-M12 : lus par le document d'estimation, M6).
//
// PHASES. Les instructions de haut niveau d'origine sont réparties dans la page
// (l. 2257-2342, 2508-2645, 2926-3014, 3031-3039, 4093-4180 du FR) : `installer…`
// exécute la première (ville + langue) ; la page appelle ensuite, à la place
// d'origine, `brancherModes`, `brancherEtapes`, `brancherRappel`,
// `brancherEstimation`. Le décompte `docEngaged` (focusin / impression) reste
// à la section « estimation résidentielle » (M6).

import type { ContexteTunnel } from './contexte';
import type { LocaleTunnel, WizardSnapshot } from './etat';

export interface TablesParcours {
  stepLabelsByMode: Record<string, [string, string]>;
  modeLabel: Record<string, string>;
  modeDocSubtitle: Record<string, string>;
  /** Langue affichée au chargement quand la bascule existe. */
  langueInitiale: 'fr' | 'ar';
}

export const TABLES_PARCOURS: Record<LocaleTunnel, TablesParcours> = {
  fr: {
    stepLabelsByMode: {
      residentiel: ['Votre toit', 'Votre estimation'],
      industriel: ['Votre site', 'Votre estimation'],
      commercial: ['Votre établissement', 'Votre estimation'],
      agricole: ['Votre terrain', 'Votre estimation'],
    },
    modeLabel: {
      residentiel: 'Résidentiel', industriel: 'Industriel', commercial: 'Commercial', agricole: 'Agricole',
    },
    modeDocSubtitle: {
      residentiel: 'Résidentielle', industriel: 'Autoconsommation Industrielle',
      commercial: 'Autoconsommation Commerciale', agricole: 'Pompage Agricole',
    },
    langueInitiale: 'fr',
  },
  en: {
    stepLabelsByMode: {
      residentiel: ['Your roof', 'Your estimate'],
      industriel: ['Your site', 'Your estimate'],
      commercial: ['Your premises', 'Your estimate'],
      agricole: ['Your land', 'Your estimate'],
    },
    modeLabel: {
      residentiel: 'Residential', industriel: 'Industrial', commercial: 'Commercial', agricole: 'Agricultural',
    },
    modeDocSubtitle: {
      residentiel: 'Residential', industriel: 'Industrial Self-Consumption',
      commercial: 'Commercial Self-Consumption', agricole: 'Agricultural Pumping',
    },
    langueInitiale: 'fr',
  },
  ar: {
    stepLabelsByMode: {
      residentiel: ['سطحك', 'تقديرك'],
      industriel: ['موقعك', 'تقديرك'],
      commercial: ['مؤسستك', 'تقديرك'],
      agricole: ['أرضك', 'تقديرك'],
    },
    modeLabel: {
      residentiel: 'سكني', industriel: 'صناعي', commercial: 'تجاري', agricole: 'فلاحي',
    },
    modeDocSubtitle: {
      residentiel: 'سكني', industriel: 'استهلاك ذاتي صناعي',
      commercial: 'استهلاك ذاتي تجاري', agricole: 'ضخ فلاحي',
    },
    langueInitiale: 'ar',
  },
};

/** WJ121 — les deux modes C&I partagent le sous-panneau/moteur pro existant ;
 *  'professionnel' couvert par défense en profondeur. */
export function isProMode(m: string): boolean {
  return m === 'industriel' || m === 'commercial' || m === 'professionnel';
}

const THINKING_MIN_MS = 250;
const THINKING_MAX_MS = 450;

export interface Parcours {
  tables: TablesParcours;
  /** Langue affichée : `currentLang` en FR et AR, 'en' en EN. */
  langueActive: () => 'fr' | 'ar' | 'en';
  applyLang: (lang: 'fr' | 'ar') => void;
  syncCityRequirement: () => void;
  syncStepLabels: () => void;
  syncStep2Panels: () => void;
  syncRaisonSociale: () => void;
  syncModeCards: () => void;
  syncCallbackSla: () => void;
  renderStep: () => void;
  goStep: (n: number, fromPopstate?: boolean) => void;
  showEstimateSkeleton: () => void;
  thinkingDelayMs: () => number;
  brancherModes: () => void;
  brancherEtapes: () => void;
  brancherRappel: () => void;
  brancherEstimation: () => void;
}

export function installerParcours(ctx: ContexteTunnel, savedWizard: WizardSnapshot | null): Parcours {
  const { etat, dom, crochets } = ctx;
  const { $, doc } = dom;
  const tables = TABLES_PARCOURS[ctx.locale];
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;
  const fallback = $('mt-fallback');
  const cityEl = $('mt-city') as HTMLInputElement | null;

  cityEl?.addEventListener('input', () => { etat.cityTouched = true; });

  // ORDRE FONDATEUR (24/08/2026) — le GPS est la source de vérité de localisation.
  function syncCityRequirement() {
    const hasGps = etat.capturePin != null;
    if (cityEl) {
      cityEl.required = !hasGps;
      cityEl.setAttribute('aria-required', hasGps ? 'false' : 'true');
    }
    const hint = $('mt-city-hint');
    if (hint) hint.hidden = !hasGps;
  }
  syncCityRequirement();

  // ——— WJ6/WJ33 : bascule de langue FR/AR (data-i18n), FR et AR seulement ———
  // WJ30 — la langue active est transmise au webhook (langue_preferee).
  //
  // WJ33 — FIX : `el.textContent = v` APLATISSAIT toute balise imbriquée à
  // l'intérieur d'un élément `data-i18n` (ex. un futur <strong>/<a> perdu au
  // premier passage AR→FR→AR). On bascule désormais par PAIRE DE NŒUDS
  // show/hide : au premier appel, chaque élément `data-i18n` est ENVELOPPÉ de
  // deux <span> — un FR (markup ORIGINAL, capturé une fois via innerHTML avant
  // toute mutation) et un AR (texte simple depuis data-ar) — puis on
  // masque/affiche la bonne paire. Aucune balise n'est plus jamais perdue, quel
  // que soit le nombre d'allers-retours FR↔AR. (Commentaire repris de la page
  // au câblage RWEB17-M12.)
  const i18nPairs: Array<{ fr: HTMLElement; ar: HTMLElement }> = [];
  function prepareI18n() {
    doc.querySelectorAll<HTMLElement>('[data-i18n]').forEach((el) => {
      const arText = el.dataset.ar;
      if (typeof arText !== 'string') return;
      const frSpan = doc.createElement('span');
      // Le markup FR ORIGINAL est préservé tel quel — capturé UNE SEULE fois.
      frSpan.innerHTML = el.innerHTML;
      const arSpan = doc.createElement('span');
      arSpan.textContent = arText;
      arSpan.hidden = true;
      el.textContent = '';
      el.append(frSpan, arSpan);
      i18nPairs.push({ fr: frSpan, ar: arSpan });
    });
  }
  function applyLang(lang: 'fr' | 'ar') {
    const isAr = lang === 'ar';
    etat.currentLang = lang;
    i18nPairs.forEach(({ fr, ar }) => {
      fr.hidden = isAr;
      ar.hidden = !isAr;
    });
    // WJ33 — RTL/langue au niveau DOCUMENT.
    doc.documentElement.lang = isAr ? 'ar' : 'fr';
    doc.documentElement.dir = isAr ? 'rtl' : 'ltr';
    const root = doc.querySelector('section') as HTMLElement | null;
    if (root) {
      root.dir = isAr ? 'rtl' : 'ltr';
      root.style.lineHeight = isAr ? '1.75' : '';
    }
    const frBtn = $('mt-lang-fr');
    const arBtn = $('mt-lang-ar');
    frBtn?.setAttribute('aria-pressed', String(!isAr));
    arBtn?.setAttribute('aria-pressed', String(isAr));
    for (const [btn, on] of [[frBtn, !isAr], [arBtn, isAr]] as const) {
      if (!btn) continue;
      btn.className = on
        ? 'px-3 py-1.5 text-sm font-semibold text-azur-950 bg-brass-400 transition-colors'
        : 'px-3 py-1.5 text-sm font-semibold text-lune-soft transition-colors hover:text-white';
    }
  }
  if (ctx.config.langueBasculable) {
    prepareI18n();
    // WJ38 — la route /ar/ affiche l'arabe PAR DÉFAUT.
    if (tables.langueInitiale === 'ar') applyLang('ar');
    $('mt-lang-fr')?.addEventListener('click', () => applyLang('fr'));
    $('mt-lang-ar')?.addEventListener('click', () => applyLang('ar'));
  }
  const langueActive = (): 'fr' | 'ar' | 'en' => (ctx.locale === 'en' ? 'en' : etat.currentLang);

  // AGW401 — `?mode=` (liste FERMÉE des 4 modes) présélectionne VISIBLEMENT la carte.
  try {
    const wantedMode = new URLSearchParams(window.location.search).get('mode');
    if (wantedMode && ['residentiel', 'industriel', 'commercial', 'agricole'].includes(wantedMode)) etat.mode = wantedMode;
  } catch { /* URL illisible : aucun mode présélectionné */ }
  // WJ121 — migration des sessions en cours : 'professionnel' → 'industriel'.
  if (etat.mode === 'professionnel') etat.mode = 'industriel';

  function syncStepLabels() {
    const labels = tables.stepLabelsByMode[etat.mode] || tables.stepLabelsByMode.residentiel;
    doc.querySelectorAll<HTMLElement>('.mt-step-label').forEach((el, i) => {
      if (labels[i]) el.textContent = labels[i];
    });
    [0, 1].forEach((i) => {
      const h = $(`mt-h2-${i}`);
      if (h && labels[i]) h.textContent = labels[i];
    });
  }
  function syncStep2Panels() {
    const m = etat.mode || 'residentiel';
    const res = $('mt-sub-residentiel');
    const pro = $('mt-sub-professionnel');
    const commercial = $('mt-sub-commercial');
    const agri = $('mt-sub-agricole');
    if (res) res.hidden = m !== 'residentiel';
    // WJ122 — 'commercial' a son PROPRE panneau ; 'industriel' (et l'alias hérité) gardent le panneau pro.
    if (pro) pro.hidden = !(m === 'industriel' || m === 'professionnel');
    if (commercial) commercial.hidden = m !== 'commercial';
    if (agri) agri.hidden = m !== 'agricole';
    // AGW401 — étape 0 en mode agricole : repère « forage / parcelle ».
    const introStd = $('mt-step0-intro');
    const introAgri = $('mt-step0-intro-agri');
    if (introStd) introStd.hidden = m === 'agricole';
    if (introAgri) introAgri.hidden = m !== 'agricole';
    const roofModeGrp = $('mt-roof-mode-group');
    if (roofModeGrp) roofModeGrp.hidden = m === 'agricole' || !!(fallback && !fallback.hidden);
    syncRaisonSociale();
  }
  function syncRaisonSociale() {
    const wrap = $('mt-raison-sociale-wrap');
    if (wrap) wrap.hidden = !isProMode(etat.mode);
  }
  function syncModeCards() {
    doc.querySelectorAll<HTMLButtonElement>('.mt-mode').forEach((b) => {
      const on = etat.mode !== '' && b.dataset.mode === etat.mode;
      b.setAttribute('aria-pressed', String(on));
      b.classList.toggle('border-brass-400', on);
      b.classList.toggle('border-white/15', !on);
    });
  }
  function brancherModes() {
    doc.querySelectorAll<HTMLButtonElement>('.mt-mode').forEach((btn) => {
      btn.addEventListener('click', () => {
        etat.mode = btn.dataset.mode || '';
        syncModeCards();
        const modeErr = $('mt-mode-err');
        if (modeErr) { modeErr.textContent = ''; modeErr.hidden = true; }
        syncStepLabels();
        syncStep2Panels();
        crochets.appeler('markDataEntered');
        crochets.appeler('saveWizardState');
        // WJ111 — si l'estimation a déjà été calculée, mise à jour IMMÉDIATE.
        if (!$('mt-estimate-body')?.hidden || !$('mt-estimate-agricole')?.hidden) crochets.appeler('computeEstimate');
        else if (etat.docRendered) crochets.appeler('computeEstimate');
      });
    });
    // état initial : réhydraté depuis l'instantané, sinon AUCUN mode marqué.
    syncModeCards();
    syncStepLabels();
    syncStep2Panels();
  }

  // ——— étapes ———
  function renderStep() {
    const panels = [0, 1].map((i) => $(`mt-panel-${i}`));
    const revealEl = $('mt-reveal');
    panels.forEach((p, i) => { if (p) p.hidden = i !== etat.step; });
    // La révélation vit DANS l'écran 1.
    if (revealEl) revealEl.hidden = !(etat.step === 1 && etat.revealed);
    doc.querySelectorAll<HTMLElement>('.mt-step').forEach((li, i) => {
      const bar = li.querySelector<HTMLElement>('.mt-step-bar');
      const label = li.querySelector<HTMLElement>('.mt-step-label');
      const active = i <= etat.step;
      if (bar) bar.className = `h-1.5 w-full rounded-full mt-step-bar transition-colors ${active ? 'bg-brass-400' : 'bg-white/10'}`;
      if (label) label.classList.toggle('text-white', i === etat.step);
    });
    // W324 — c'est ICI qu'on engage le fetch de config + l'import lazy de maplibre-gl.
    if (etat.step === 0) crochets.appeler('ensureMapBooted');
    // WJ59/WB30 — 'toit' = écran 0 ; 'facture' = écran 1 avant révélation ; 'estimation' = après.
    if (crochets.appeler('hasReachedConsentStep')) crochets.appeler('sendFunnelBeacon', etat.step === 0 ? 'toit' : etat.revealed ? 'estimation' : 'facture', 'reached');
    // WJ61 — au tout premier rendu, ne pas imposer de défilement.
    if (etat.firstRender) { etat.firstRender = false; return; }
    const root = doc.querySelector('section');
    root?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' });
  }
  // WJ61 — pushState PAR ÉTAPE ; `fromPopstate` évite de repousser un état.
  function goStep(n: number, fromPopstate = false) {
    etat.step = Math.max(0, Math.min(1, n));
    renderStep();
    crochets.appeler('saveWizardState');
    if (!fromPopstate) {
      history.pushState({ mtStep: etat.step, mtRevealed: etat.revealed }, '', location.href);
    }
  }
  function brancherEtapes() {
    // L'historique porte la PAIRE (étape, révélation) ; une entrée héritée
    // (`mtStep === 2`) vaut « estimation affichée ».
    window.addEventListener('popstate', (e) => {
      const st = e.state as { mtStep?: number; mtRevealed?: boolean } | null;
      const n = st?.mtStep != null ? st.mtStep : Math.max(0, etat.step - 1);
      etat.revealed = st?.mtRevealed === true || st?.mtStep === 2;
      goStep(n, true);
    });
    // QX — l'étape carte exige un PROFIL choisi.
    $('mt-next-0')?.addEventListener('click', () => {
      if (crochets.appeler('validateStep0')) goStep(1);
    });
    $('mt-back-1')?.addEventListener('click', () => goStep(0));
    // WJ61 — première entrée d'historique dès le chargement.
    history.replaceState({ mtStep: etat.step, mtRevealed: etat.revealed }, '', location.href);
    renderStep();
    // WJ96(c) — préchauffe la carte pour un visiteur qui reprend à l'écran 1.
    if (savedWizard?.step != null && savedWizard.step > 0) crochets.appeler('ensureMapBooted');
  }

  // WJ105 — SLA de rappel concret : visible UNIQUEMENT quand « Un conseiller peut m'appeler » est actif.
  const contactPhoneRadio = $('mt-contact-phone') as HTMLInputElement | null;
  const contactWhatsappRadio = $('mt-contact-whatsapp') as HTMLInputElement | null;
  const callbackSla = $('mt-callback-sla') as HTMLElement | null;
  function syncCallbackSla(): void {
    if (callbackSla) callbackSla.hidden = contactPhoneRadio?.checked !== true;
  }
  function brancherRappel() {
    contactPhoneRadio?.addEventListener('change', syncCallbackSla);
    contactWhatsappRadio?.addEventListener('change', syncCallbackSla);
    syncCallbackSla();
  }

  // WJ34 — squelette bref pendant le calcul (performance perçue).
  function showEstimateSkeleton() {
    // Le squelette chiffres ne concerne que la grille RÉSIDENTIELLE.
    if (etat.mode && etat.mode !== 'residentiel') return;
    const card = $('mt-estimate-body');
    const unavail = $('mt-estimate-unavailable');
    const toolarge = $('mt-estimate-toolarge');
    if (unavail) unavail.hidden = true;
    if (toolarge) toolarge.hidden = true;
    if (card) card.hidden = false;
    for (const id of ['mt-est-kwc', 'mt-est-prod', 'mt-est-savings']) {
      const el = $(id);
      if (el) el.innerHTML = '<span class="mt-est-skeleton mt-skeleton-shimmer"></span>';
    }
    const payEl = $('mt-est-payback');
    if (payEl) payEl.innerHTML = '<span class="mt-est-skeleton mt-skeleton-shimmer"></span>';
  }
  // WJ48/WJ112 — anticipation BRANDÉE ≤ 500 ms ; reduced-motion → INSTANTANÉ.
  function thinkingDelayMs(): number {
    if (reducedMotion) return 0;
    return THINKING_MIN_MS + Math.random() * (THINKING_MAX_MS - THINKING_MIN_MS);
  }
  function brancherEstimation() {
    const revealEl = $('mt-reveal');
    $('mt-estimate')?.addEventListener('click', (e) => {
      // QX — validation de l'étape AVANT le calcul.
      if (!crochets.appeler('validateStep1')) return;
      showEstimateSkeleton();
      const thinkingEl = $('mt-estimate-thinking');
      if (thinkingEl) thinkingEl.hidden = false;
      // COUPE FONDATEUR 21/08 — RÉVÉLATION SUR PLACE.
      etat.revealed = true;
      if (revealEl) revealEl.hidden = false;
      crochets.appeler('saveWizardState');
      history.pushState({ mtStep: etat.step, mtRevealed: true }, '', location.href);
      // WJ59 — 'estimation' / 'reached' émis ICI (dédupliqué par sendFunnelBeacon).
      if (crochets.appeler('hasReachedConsentStep')) crochets.appeler('sendFunnelBeacon', 'estimation', 'reached');
      revealEl?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' });
      const triggerEl = e.currentTarget as HTMLElement | null;
      requestAnimationFrame(() => {
        setTimeout(() => {
          if (thinkingEl) thinkingEl.hidden = true;
          const hasEstimate = crochets.appeler('computeEstimate');
          // WJ46 — pic d'intérêt : offre WhatsApp après 12 s, sauf visiteur déjà ENGAGÉ.
          if (hasEstimate) {
            setTimeout(() => {
              if (!etat.docEngaged) crochets.appeler('showWhatsappOffer', triggerEl);
            }, 12_000);
          }
        }, thinkingDelayMs());
      });
    });
  }

  const section: Parcours = {
    tables, langueActive, applyLang, syncCityRequirement, syncStepLabels, syncStep2Panels,
    syncRaisonSociale, syncModeCards, syncCallbackSla, renderStep, goStep,
    showEstimateSkeleton, thinkingDelayMs,
    brancherModes, brancherEtapes, brancherRappel, brancherEstimation,
  };
  crochets.installer('syncCityRequirement', syncCityRequirement);
  crochets.installer('syncCallbackSla', syncCallbackSla);
  crochets.installer('syncStepLabels', syncStepLabels);
  crochets.installer('syncStep2Panels', syncStep2Panels);
  crochets.installer('syncRaisonSociale', syncRaisonSociale);
  crochets.installer('syncModeCards', syncModeCards);
  crochets.installer('isProMode', isProMode);
  crochets.installer('renderStep', renderStep);
  crochets.installer('goStep', goStep);
  crochets.installer('applyLang', applyLang);
  crochets.installer('langueActive', langueActive);
  crochets.installer('showEstimateSkeleton', showEstimateSkeleton);
  crochets.installer('thinkingDelayMs', thinkingDelayMs);
  // RWEB17-M12 — libellés de mode lus par le document d'estimation (M6) : `undefined` hors table,
  // comme `MODE_LABEL[m]` / `MODE_DOC_SUBTITLE[m]` de la page.
  crochets.installer('modeLabel', (m: string): string | undefined => tables.modeLabel[m]);
  crochets.installer('modeDocSubtitle', (m: string): string | undefined => tables.modeDocSubtitle[m]);
  return section;
}
