// RWEB17-M5 — SECTION « ESTIMATION PRO ET AGRICOLE » du tunnel « mon-toit », en UN
// module pour FR/EN/AR (extraite de la page FR ; AR/EN comparées ligne à ligne :
// leurs seuls écarts sont des TEXTES, regroupés dans `TEXTES_ESTIMATION_PRO`).
// Livrée SEULE : aucune page ne l'importe encore (M15 la câble).
//
// Les calculs restent dans `lib/estimatorPro.ts` et `lib/estimatorAgricole.ts`
// (APPELS, jamais recopiés). Écritures d'état : lastKwc, lastKwcLabel,
// lastSavingsLabel, estimateShown, lastProTarifMadKwh (voir `etat.ts`) ; le reste
// de l'état est LU.
//
// CROCHETS REQUIS (autres sections) : `setCard`, `announceEstimate`,
// `showEstimateTeaser`, `fillDocChrome`, `renderMonthlyChart` (estimation
// résidentielle, M6) ; `updatePanels3dVisibility` (carte, M4) ;
// `hasReachedConsentStep`, `sendFunnelBeacon` (persistance/funnel).
// CROCHETS INSCRITS ICI : `computeProEstimate`, `computeAgricoleEstimate`,
// `renderAgricoleEstimate`, `proBillId`, `proBillErrId`, `proBillUnit`.
//
// `config.formatNombre` sert pour `fmtNum` ET `fmtYears` (identiques sur les trois
// pages : arrondi à 0,1 puis `toLocaleString`, `fr-FR` pour FR/AR, `en-GB` pour EN).

import { formatMad, formatMadRange } from '../billEstimate';
import { estimatePro } from '../estimatorPro';
import { estimateAgricole } from '../estimatorAgricole';
import { monthlyWaterDemand } from '../agronomy';
import { formatKwc } from '../proposition';
import type { ConfigLocale, ContexteTunnel } from './contexte';
import type { LocaleTunnel } from './etat';

export interface TextesEstimationPro {
  /** Langue passée à `toLocaleString` pour le tarif des hypothèses. */
  localeNombre: string;
  // — messages annoncés (aria-live) —
  indispoConso: string;
  etudeDedie: string;
  indispoVerif: string;
  annonceOk: (labelKwc: string, eco: string | null) => string;
  annonceAgri: (pompe: string | null, champ: string | null) => string;
  // — libellés pro —
  unAns: (n: string) => string;
  fourchetteAns: (a: string, b: string) => string;
  hypTarif: (tarif: string) => string;
  hypPartDiurne: (pct: number) => string;
  hypInvest: (low: string, high: string) => string;
  hypothesesPro: (parts: string) => string;
  // — libellés agricoles —
  eauPointe: (n: string) => string;
  champPv: (kwc: string) => string;
  uniteCv: string;
  panneaux: (n: number) => string;
  eauHmt: (m3: string, hmt: string | null, estimee: boolean) => string;
  carburant: (n: string) => string;
  fluxEau: (n: string) => string;
  hypPompage: (pct: number) => string;
  hypChamp: (facteur: string) => string;
  hypothesesAgri: (parts: string) => string;
}

const fr: TextesEstimationPro = {
  localeNombre: 'fr-FR',
  indispoConso: 'Estimation indisponible : indiquez votre consommation mensuelle (MAD ou kWh).',
  etudeDedie: "À cette échelle, votre site relève d'une étude dédiée — un ingénieur vous contacte.",
  indispoVerif: 'Estimation indisponible : vérifiez la consommation saisie.',
  annonceOk: (l, eco) => `Votre estimation : ${l || 'calculée'}${eco ? `, économies estimées ${eco}/an` : ''}.`,
  annonceAgri: (p, c) => `Votre estimation pompage : ${p ? `pompe ${p}` : 'calculée'}${c ? `, champ ${c}` : ''}.`,
  unAns: (n) => `${n} ans`,
  fourchetteAns: (a, b) => `${a} – ${b} ans`,
  hypTarif: (t) => `tarif utilisé ${t} MAD/kWh`,
  hypPartDiurne: (p) => `part diurne estimée ${p} %`,
  hypInvest: (lo, hi) => `investissement ${lo} – ${hi} MAD/kWc (fourchette marché)`,
  hypothesesPro: (p) => `Hypothèses : ${p} — autoconsommation loi 82-21, sans revente.`,
  eauPointe: (n) => `${n} m³/jour`,
  champPv: (k) => `${k} kWc (champ PV)`,
  uniteCv: 'CV',
  panneaux: (n) => ` · ${n} panneaux`,
  eauHmt: (m3, hmt, est) => `${m3} m³${hmt != null ? ` à HMT ${hmt} m${est ? ' (estimée)' : ''}` : ''}`,
  carburant: (n) => `${n} MAD/mois`,
  fluxEau: (n) => `${n} m³/jour`,
  hypPompage: (p) => `rendement de pompage estimé ${p} %`,
  hypChamp: (f) => `champ PV ≈ ${f} × la puissance de la pompe`,
  hypothesesAgri: (p) => `Hypothèses : ${p} — dimensionnement affiné après visite du forage.`,
};

const ar: TextesEstimationPro = {
  localeNombre: 'fr-FR',
  indispoConso: 'التقدير غير متوفر: أدخلوا استهلاككم الشهري (درهم أو kWh).',
  etudeDedie: 'عند هذا الحجم، يستدعي موقعكم دراسة مخصّصة — سيتواصل معكم مهندس.',
  indispoVerif: 'التقدير غير متوفر: تحققوا من الاستهلاك المُدخَل.',
  annonceOk: (l, eco) => `تقديركم: ${l || 'محسوب'}${eco ? `، توفير مقدَّر ${eco}/سنة` : ''}.`,
  annonceAgri: (p, c) => `تقدير الضخ: ${p ? `مضخة ${p}` : 'محسوب'}${c ? `، حقل ${c}` : ''}.`,
  unAns: (n) => `${n} سنة`,
  fourchetteAns: (a, b) => `${a} – ${b} سنة`,
  hypTarif: (t) => `التعرفة المعتمدة ${t} MAD/kWh`,
  hypPartDiurne: (p) => `الحصة النهارية المقدَّرة ${p} %`,
  hypInvest: (lo, hi) => `الاستثمار ${lo} – ${hi} MAD/kWc (نطاق السوق)`,
  hypothesesPro: (p) => `الفرضيات: ${p} — استهلاك ذاتي وفق القانون 82-21، دون إعادة بيع.`,
  eauPointe: (n) => `${n} m³/j`,
  champPv: (k) => `${k} kWc (حقل كهروضوئي)`,
  uniteCv: 'CV',
  panneaux: (n) => ` · ${n} لوحة`,
  eauHmt: (m3, hmt, est) => `${m3} m³${hmt != null ? ` عند HMT ${hmt} m${est ? ' (مُقدَّر)' : ''}` : ''}`,
  carburant: (n) => `${n} درهم/شهر`,
  fluxEau: (n) => `${n} m³/يوم`,
  hypPompage: (p) => `مردود الضخ المقدَّر ${p} %`,
  hypChamp: (f) => `الحقل الكهروضوئي ≈ ${f} × قدرة المضخة`,
  hypothesesAgri: (p) => `الفرضيات: ${p} — يُحسَّن الحجم بعد زيارة الثقب المائي.`,
};

const en: TextesEstimationPro = {
  localeNombre: 'en-GB',
  indispoConso: 'Estimate unavailable: enter your monthly consumption (MAD or kWh).',
  etudeDedie: 'At this scale, your site needs a dedicated study — an engineer will contact you.',
  indispoVerif: 'Estimate unavailable: please check the consumption entered.',
  annonceOk: (l, eco) => `Your estimate: ${l || 'calculated'}${eco ? `, estimated savings ${eco}/year` : ''}.`,
  annonceAgri: (p, c) => `Your pumping estimate: ${p ? `pump ${p}` : 'calculated'}${c ? `, array ${c}` : ''}.`,
  unAns: (n) => `${n} years`,
  fourchetteAns: (a, b) => `${a} – ${b} years`,
  hypTarif: (t) => `tariff used ${t} MAD/kWh`,
  hypPartDiurne: (p) => `estimated daytime share ${p}%`,
  hypInvest: (lo, hi) => `investment ${lo} – ${hi} MAD/kWc (market range)`,
  hypothesesPro: (p) => `Assumptions: ${p} — self-consumption under law 82-21, no resale.`,
  eauPointe: (n) => `${n} m³/day`,
  champPv: (k) => `${k} kWc (PV array)`,
  uniteCv: 'HP',
  panneaux: (n) => ` · ${n} panels`,
  eauHmt: (m3, hmt, est) => `${m3} m³${hmt != null ? ` at TDH ${hmt} m${est ? ' (estimated)' : ''}` : ''}`,
  carburant: (n) => `${n} MAD/month`,
  fluxEau: (n) => `${n} m³/day`,
  hypPompage: (p) => `estimated pumping efficiency ${p}%`,
  hypChamp: (f) => `PV array ≈ ${f} × the pump's power`,
  hypothesesAgri: (p) => `Assumptions: ${p} — sizing refined after a borehole site visit.`,
};

export const TEXTES_ESTIMATION_PRO: Record<LocaleTunnel, TextesEstimationPro> = { fr, ar, en };

export interface ConfigEstimationPro {
  /** Estimation publique gatée (constante de la page). */
  estimationGatee: boolean;
  /** Message annoncé quand l'estimation est gatée (`GATED_ANNOUNCE` de la page). */
  annonceGatee: string;
}

export type ContexteEstimationPro = Omit<ContexteTunnel, 'config'> & {
  config: ConfigLocale & ConfigEstimationPro;
};

type ProEstimateOk = { ok: true; surfaceCapped: boolean }
  & Record<'kwc' | 'nbPanneaux' | 'prodAnnuelleKwh' | 'consoAnnuelleKwh' | 'tauxAutoconso' | 'tauxCouverture', number>
  & Record<'ecoAnnuelleMadLow' | 'ecoAnnuelleMadHigh' | 'paybackYearsLow' | 'paybackYearsHigh', number>
  & { hypotheses: { tarifMadKwh: number; dayShare: number; prixKwcLow: number; prixKwcHigh: number } };

export type AgricoleEstimateOk = { ok: true; hmtEstimated: boolean }
  & Record<'hmtM' | 'debitM3h' | 'pompeKw' | 'pompeCv' | 'champKwc' | 'nbPanneaux' | 'm3Jour' | 'heures', number>
  & { hypotheses: { pumpEff: number; pvFactor: number } };

/** FR l. 3557-3864 (une seule plage) : alias nommé `installerEstimationPro`. */
export function installerEstimationPro(ctx: ContexteEstimationPro): void {
  const { etat, dom, crochets, config } = ctx;
  const { $, num, val, pct, setText, maxBillFor, setFieldError } = dom;
  const T = TEXTES_ESTIMATION_PRO[config.locale];
  const GATED = config.estimationGatee;
  const fmtNum = config.formatNombre;
  const fmtYears = config.formatNombre;
  const h = (nom: string, ...args: any[]) => crochets.appeler(nom, ...args);

  // WJ122 — la facture C&I vient du panneau ACTIF : 'commercial' a son propre
  // champ (mt-cc-bill / ccUnit), 'industriel' garde mt-pro-bill / proUnit.
  const proBillId = () => (etat.mode === 'commercial' ? 'mt-cc-bill' : 'mt-pro-bill');
  const proBillErrId = () => (etat.mode === 'commercial' ? 'mt-cc-bill-err' : 'mt-pro-bill-err');
  const proBillUnit = () => (etat.mode === 'commercial' ? etat.ccUnit : etat.proUnit);

  function computeProEstimate(): boolean {
    const indispo = $('mt-estimate-unavailable');
    const tropGrand = $('mt-estimate-toolarge');
    const toolargePro = $('mt-estimate-toolarge-pro');
    const proMissing = $('mt-estimate-pro-missing');
    const printBtn = $('mt-print-estimate');
    if (indispo) indispo.hidden = true;
    if (tropGrand) tropGrand.hidden = true;
    const clearShown = () => {
      etat.lastKwcLabel = '';
      etat.lastSavingsLabel = '';
      etat.lastKwc = null;
      etat.estimateShown = null;
      // CIW404 — un tarif périmé ne survit pas à une estimation en échec.
      etat.lastProTarifMadKwh = null;
      if (printBtn) printBtn.hidden = true;
    };
    const proBill = num(proBillId());
    if (proBill == null || proBill <= 0) {
      if (proMissing) proMissing.hidden = false;
      clearShown();
      h('fillDocChrome');
      h('updatePanels3dVisibility');
      h('announceEstimate', T.indispoConso);
      return false;
    }
    // WJ121 — plafond du mode C&I actif (industriel et commercial partagent 1 M MAD).
    if (proBillUnit() === 'mad' && proBill > maxBillFor(etat.mode)) {
      if (toolargePro) toolargePro.hidden = false;
      // WJ127 — l'accroche « étude dédiée » rétablit la parité, sans chiffre.
      if (GATED) h('showEstimateTeaser', etat.mode, 'etude');
      clearShown();
      h('fillDocChrome');
      h('updatePanels3dVisibility');
      h('announceEstimate', T.etudeDedie);
      return true;
    }
    setFieldError(proBillId(), proBillErrId(), null);
    const raw = estimatePro({
      monthlyKwh: proBillUnit() === 'kwh' ? proBill : undefined,
      monthlyMad: proBillUnit() === 'mad' ? proBill : undefined,
      raccordement: etat.tension === 'mt' ? 'mt' : 'bt',
      activityProfile: etat.activity === 'day_evening' || etat.activity === 'continuous' ? etat.activity : 'day',
      surfaceType: etat.surfaceType ? (etat.surfaceType as 'bac_acier' | 'terrasse' | 'ombriere' | 'terrain') : undefined,
      surfaceM2: num('mt-surface-m2') ?? undefined,
      // WJ122 — la catégorie commerciale (day-share par archétype) prime sur le profil d'activité.
      categorieCommerciale: etat.mode === 'commercial' && etat.commercialCategory ? etat.commercialCategory : undefined,
      // WJ123 — le pattern d'équipes industriel impose son plafond honnête.
      equipes: (etat.mode === 'industriel' || etat.mode === 'professionnel') && etat.equipes ? etat.equipes : undefined,
    }) as unknown as ProEstimateOk | { ok: false; reason: 'missing_conso' | 'too_large' | 'invalid' };
    if (!raw.ok) {
      if (raw.reason === 'too_large') {
        if (toolargePro) toolargePro.hidden = false;
        // WJ127 — même repli honnête (cf. ci-dessus).
        if (GATED) h('showEstimateTeaser', etat.mode, 'etude');
        clearShown();
        h('fillDocChrome');
        h('updatePanels3dVisibility');
        h('announceEstimate', T.etudeDedie);
        return true;
      }
      if (proMissing) proMissing.hidden = false;
      clearShown();
      h('fillDocChrome');
      h('updatePanels3dVisibility');
      h('announceEstimate', T.indispoVerif);
      return false;
    }
    const est = raw;
    etat.lastProTarifMadKwh = est.hypotheses && est.hypotheses.tarifMadKwh > 0 ? est.hypotheses.tarifMadKwh : null;
    if (h('hasReachedConsentStep')) h('sendFunnelBeacon', 'estimation', 'viewed');
    // WJ125 — labels construits AVANT tout rendu ; en parcours public gaté on
    // s'arrête ici SANS écrire un chiffre.
    {
      // CIW404 — en modes commercial/industriel, AUCUN chiffre d'hypothèse ne part au
      // CRM ni dans le message WhatsApp ; seul le moteur serveur parle (D-CIQ-0).
      const kOk = Number.isFinite(est.kwc) && est.kwc > 0;
      etat.estimateShown = null; // CIW404 — aucun chiffre vers le CRM
      // `lastKwc` ne sert qu'à l'aperçu 3D local : il ne part jamais au CRM.
      etat.lastKwc = kOk ? est.kwc : null;
      etat.lastKwcLabel = '';
      etat.lastSavingsLabel = '';
    }
    if (GATED) {
      h('updatePanels3dVisibility');
      if (h('hasReachedConsentStep')) h('sendFunnelBeacon', 'contact', 'reached');
      h('announceEstimate', config.annonceGatee);
      return true;
    }
    const kpis = $('mt-doc-kpis-pro');
    if (kpis) kpis.hidden = false;
    const shown: Record<string, number | string> = {};
    const kwcOk = Number.isFinite(est.kwc) && est.kwc > 0;
    h('setCard', 'mt-pro-kwc-card', 'mt-pro-kwc', kwcOk ? formatKwc(est.kwc) : null);
    if (kwcOk) shown.kwc = est.kwc;
    if (Number.isFinite(est.nbPanneaux) && est.nbPanneaux > 0) shown.nbPanneaux = est.nbPanneaux;
    const prodOk = Number.isFinite(est.prodAnnuelleKwh) && est.prodAnnuelleKwh > 0;
    h('setCard', 'mt-pro-prod-card', 'mt-pro-prod', prodOk ? formatMad(Math.round(est.prodAnnuelleKwh)) : null);
    if (prodOk) shown.prodKwh = Math.round(est.prodAnnuelleKwh);
    const autocOk = Number.isFinite(est.tauxAutoconso) && est.tauxAutoconso > 0;
    h('setCard', 'mt-pro-autoconso-card', 'mt-pro-autoconso', autocOk ? String(pct(est.tauxAutoconso)) : null);
    if (autocOk) shown.tauxAutoconso = pct(est.tauxAutoconso);
    const couvOk = Number.isFinite(est.tauxCouverture) && est.tauxCouverture > 0;
    h('setCard', 'mt-pro-couverture-card', 'mt-pro-couverture', couvOk ? String(pct(est.tauxCouverture)) : null);
    if (couvOk) shown.tauxCouverture = pct(est.tauxCouverture);
    const ecoOk = est.ecoAnnuelleMadLow > 0 && est.ecoAnnuelleMadHigh > 0;
    const ecoLabel = ecoOk ? formatMadRange(est.ecoAnnuelleMadLow, est.ecoAnnuelleMadHigh) : null;
    h('setCard', 'mt-pro-eco-card', 'mt-pro-eco', ecoLabel);
    if (ecoOk) Object.assign(shown, { ecoMadYearLow: est.ecoAnnuelleMadLow, ecoMadYearHigh: est.ecoAnnuelleMadHigh });
    const paybackOk = est.paybackYearsLow > 0 && est.paybackYearsHigh > 0;
    const retourLabel = paybackOk
      ? (est.paybackYearsLow === est.paybackYearsHigh
        ? T.unAns(fmtYears(est.paybackYearsLow))
        : T.fourchetteAns(fmtYears(est.paybackYearsLow), fmtYears(est.paybackYearsHigh)))
      : null;
    h('setCard', 'mt-pro-retour-card', 'mt-pro-retour', retourLabel);
    if (retourLabel) shown.paybackLabel = retourLabel;
    const capped = $('mt-pro-capped');
    if (capped) capped.hidden = est.surfaceCapped !== true;
    if (prodOk) h('renderMonthlyChart', est.prodAnnuelleKwh);
    // Hypothèses honnêtes — uniquement celles que le moteur fournit.
    const hypEl = $('mt-doc-hypotheses');
    const hypWrap = $('mt-doc-hypo-wrap');
    const noteEl = $('mt-estimate-note');
    const hy = est.hypotheses;
    const hypParts: string[] = [];
    if (hy && hy.tarifMadKwh > 0) hypParts.push(T.hypTarif(hy.tarifMadKwh.toLocaleString(T.localeNombre)));
    if (hy && hy.dayShare > 0) hypParts.push(T.hypPartDiurne(pct(hy.dayShare)));
    if (hy && hy.prixKwcLow > 0 && hy.prixKwcHigh > 0) hypParts.push(T.hypInvest(formatMad(hy.prixKwcLow), formatMad(hy.prixKwcHigh)));
    if (hypEl) {
      hypEl.textContent = hypParts.length > 0 ? T.hypothesesPro(hypParts.join(' · ')) : '';
      hypEl.hidden = hypParts.length === 0;
    }
    if (noteEl) noteEl.hidden = true;
    if (hypWrap) hypWrap.hidden = false;
    // CIW404 — même règle côté écran non gaté : rien de chiffré vers le CRM ni WhatsApp.
    etat.estimateShown = null; // CIW404 — aucun chiffre vers le CRM
    etat.lastKwc = kwcOk ? est.kwc : null;
    etat.lastKwcLabel = '';
    etat.lastSavingsLabel = '';
    if (printBtn) printBtn.hidden = false;
    h('fillDocChrome');
    h('updatePanels3dVisibility');
    if (h('hasReachedConsentStep')) h('sendFunnelBeacon', 'contact', 'reached');
    h('announceEstimate', T.annonceOk(etat.lastKwcLabel, ecoLabel));
    return true;
  }

  // ——— QX : moteur AGRICOLE (contrat estimatorAgricole) — JAMAIS estimateFromBill. ———
  function computeAgricoleEstimate(): AgricoleEstimateOk | null {
    const debitM3h = etat.waterUnit === 'm3h' ? (num('mt-water-need') ?? undefined) : undefined;
    let besoinM3j = etat.waterUnit === 'm3j' ? (num('mt-water-need') ?? undefined) : undefined;
    // WJ124 — sans débit/besoin explicite, on DÉDUIT le besoin du mois de pointe
    // via le moteur agronomique FAO-56 (culture + région + surface).
    let agroPeak: number | null = null;
    if (debitM3h == null && besoinM3j == null) {
      const crop = val('mt-culture');
      const surfaceHa = num('mt-surface-ha');
      if (crop && etat.regionAgricole && surfaceHa != null && surfaceHa > 0) {
        const md = monthlyWaterDemand(crop, etat.regionAgricole, surfaceHa);
        if (md.peak_m3_farm_day > 0) { besoinM3j = md.peak_m3_farm_day; agroPeak = md.peak_m3_farm_day; }
      }
    }
    // WJ125 — le besoin de pointe est DIMENSIONNANT : jamais affiché avant l'envoi
    // du lead (parcours public gaté). Il alimente le calcul (et le CRM) en silence.
    const waterNote = $('mt-agri-water-note');
    if (waterNote) waterNote.hidden = agroPeak == null || GATED;
    if (!GATED && agroPeak != null) {
      const waterVal = $('mt-agri-water-value');
      if (waterVal) waterVal.textContent = T.eauPointe(fmtNum(Math.round(agroPeak)));
    }
    const raw = estimateAgricole({
      debitM3h,
      besoinM3j,
      hmtM: num('mt-hmt') ?? undefined,
      profondeurM: num('mt-profondeur') ?? undefined,
      refoulementM: undefined,
      heuresPompage: num('mt-heures-pompage') ?? undefined,
      pompeType: etat.waterSource === 'puits' || etat.waterSource === 'forage' ? 'immergee' : etat.waterSource ? 'surface' : undefined,
      fuelSpendMadMonth: num('mt-fuel-spend') ?? undefined,
    }) as unknown as AgricoleEstimateOk | { ok: false; reason: string };
    return raw && raw.ok === true ? raw : null;
  }

  function renderAgricoleEstimate(ag: AgricoleEstimateOk) {
    if (h('hasReachedConsentStep')) h('sendFunnelBeacon', 'estimation', 'viewed');
    // WJ125 — payload lead (chiffres pompage) + labels construits AVANT tout rendu.
    {
      const s: Record<string, number | string> = {};
      const cOk = ag.champKwc > 0;
      // Ordre des clés = celui du payload de la page (pompeCv, champKwc, nbPanneaux, m3Jour, bassinM3).
      // WJ124 — bassin suggéré = besoin journalier (1×), borne basse de la fourchette 1-3×.
      const candidats: Array<[string, number]> = [
        ['pompeCv', ag.pompeCv], ['champKwc', ag.champKwc], ['nbPanneaux', ag.nbPanneaux],
        ['m3Jour', ag.m3Jour], ['bassinM3', ag.m3Jour],
      ];
      for (const [cle, valeur] of candidats) if (valeur > 0) s[cle] = valeur;
      etat.estimateShown = s;
      etat.lastKwc = null;
      etat.lastKwcLabel = cOk ? T.champPv(formatKwc(ag.champKwc)) : '';
      // AGW404 — aucune économie carburant dans le payload ni dans le message WhatsApp.
      etat.lastSavingsLabel = '';
    }
    if (GATED) {
      h('updatePanels3dVisibility');
      if (h('hasReachedConsentStep')) h('sendFunnelBeacon', 'contact', 'reached');
      h('announceEstimate', config.annonceGatee);
      return;
    }
    const kpis = $('mt-doc-kpis-agri');
    if (kpis) kpis.hidden = false;
    const shown: Record<string, number | string> = {};
    const pompeOk = ag.pompeCv > 0;
    const pompeLabel = pompeOk ? `${fmtNum(ag.pompeCv)} ${T.uniteCv}${ag.pompeKw > 0 ? ` · ${fmtNum(ag.pompeKw)} kW` : ''}` : null;
    h('setCard', 'mt-agri-pompe-card', 'mt-agri-pompe', pompeLabel);
    if (pompeOk) shown.pompeCv = ag.pompeCv;
    const champOk = ag.champKwc > 0;
    const champLabel = champOk ? `${formatKwc(ag.champKwc)} kWc${ag.nbPanneaux > 0 ? T.panneaux(ag.nbPanneaux) : ''}` : null;
    h('setCard', 'mt-agri-champ-card', 'mt-agri-champ', champLabel);
    if (champOk) shown.champKwc = ag.champKwc;
    if (ag.nbPanneaux > 0) shown.nbPanneaux = ag.nbPanneaux;
    const eauOk = ag.m3Jour > 0;
    const eauLabel = eauOk
      ? T.eauHmt(fmtNum(ag.m3Jour), ag.hmtM > 0 ? fmtNum(ag.hmtM) : null, ag.hmtEstimated)
      : null;
    h('setCard', 'mt-agri-eau-card', 'mt-agri-eau', eauLabel);
    if (eauOk) shown.m3Jour = ag.m3Jour;
    if (eauOk) shown.bassinM3 = ag.m3Jour;
    // AGW404 — la valeur DÉCLARÉE du visiteur, telle quelle, masquée si vide.
    const depenseDeclaree = num('mt-fuel-spend');
    const fuelLabel = depenseDeclaree != null && depenseDeclaree > 0 ? T.carburant(fmtNum(depenseDeclaree)) : null;
    h('setCard', 'mt-agri-fuel-card', 'mt-agri-fuel', fuelLabel);
    // Bande de flux soleil → pompe → eau : uniquement si les 3 chiffres existent.
    const bandeFlux = $('mt-doc-flow');
    const flowOk = ag.heures > 0 && pompeLabel != null && eauOk;
    if (bandeFlux) bandeFlux.hidden = !flowOk;
    if (flowOk) {
      setText('mt-flow-heures', `${fmtNum(ag.heures)} h`);
      setText('mt-flow-pompe', pompeLabel as string);
      setText('mt-flow-eau', T.fluxEau(fmtNum(ag.m3Jour)));
    }
    // Hypothèses pompage honnêtes (rendement, facteur champ/pompe).
    const hypEl = $('mt-doc-hypotheses');
    const hypWrap = $('mt-doc-hypo-wrap');
    const noteEl = $('mt-estimate-note');
    const hypParts: string[] = [];
    if (ag.hypotheses && ag.hypotheses.pumpEff > 0) hypParts.push(T.hypPompage(pct(ag.hypotheses.pumpEff)));
    if (ag.hypotheses && ag.hypotheses.pvFactor > 0) hypParts.push(T.hypChamp(fmtNum(ag.hypotheses.pvFactor)));
    if (hypEl) {
      hypEl.textContent = hypParts.length > 0 ? T.hypothesesAgri(hypParts.join(' · ')) : '';
      hypEl.hidden = hypParts.length === 0;
    }
    if (noteEl) noteEl.hidden = true;
    if (hypWrap) hypWrap.hidden = false;
    etat.estimateShown = shown;
    // Pas d'aperçu « panneaux sur votre toit » pour un champ au sol.
    etat.lastKwc = null;
    etat.lastKwcLabel = champLabel ? T.champPv(formatKwc(ag.champKwc)) : '';
    etat.lastSavingsLabel = '';
    const printBtn = $('mt-print-estimate');
    if (printBtn) printBtn.hidden = false;
    h('fillDocChrome');
    h('updatePanels3dVisibility');
    if (h('hasReachedConsentStep')) h('sendFunnelBeacon', 'contact', 'reached');
    h('announceEstimate', T.annonceAgri(pompeLabel ? pompeLabel : null, champLabel));
  }

  crochets.installer('proBillId', proBillId);
  crochets.installer('proBillErrId', proBillErrId);
  crochets.installer('proBillUnit', proBillUnit);
  crochets.installer('computeProEstimate', computeProEstimate);
  crochets.installer('computeAgricoleEstimate', computeAgricoleEstimate);
  crochets.installer('renderAgricoleEstimate', renderAgricoleEstimate);
}
