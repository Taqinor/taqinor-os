// RWEB17-M6 — SECTION « ESTIMATION RÉSIDENTIELLE ET DOCUMENT » du tunnel
// « mon-toit », en UN module pour FR/EN/AR (extraite de la page FR ; AR/EN
// comparées ligne à ligne : leurs écarts sont des TEXTES, des formats de nombre
// et de date, et le lien de réalisation — tout est dans `TEXTES_RESIDENTIEL`).
// Livrée SEULE : aucune page ne l'importe encore (M16 la câble).
//
// Possède (voir l'en-tête d'`etat.ts`) : lastKwcLabel, lastSavingsLabel, lastKwc,
// docRendered, estimateShown. Elle LIT mode et lastProTarifMadKwh (écrit par la
// section pro). `PUBLIC_ESTIMATE_GATED` arrive par `config.estimationGatee` ;
// `GATED_ANNOUNCE` est `TEXTES_RESIDENTIEL[locale].annonceGatee`.
//
// CROCHETS REQUIS : `resolveMonthlyBill` (sélections), `isProMode`, `modeLabel`,
// `modeDocSubtitle` (parcours : `MODE_LABEL[m]` / `MODE_DOC_SUBTITLE[m]`, `undefined`
// si absent), `langueActive` (parcours, seulement si `config.dateSuitLangue`),
// `tryRoofSnapshot`, `updatePanels3dVisibility` (carte), `computeProEstimate`,
// `computeAgricoleEstimate`, `renderAgricoleEstimate` (pro/agricole),
// `hasReachedConsentStep`, `sendFunnelBeacon` (funnel).
// CROCHETS INSCRITS ICI : `announceEstimate`, `showEstimateTeaser`, `setCard`,
// `renderMonthlyChart`, `fillDocChrome`, `resetDocZones`, `computeEstimate`.
//
// Le texte de l'estimation reste celui de la page : `payEl.textContent =
// est.paybackLabel` À L'IDENTIQUE (la correction du libellé affiché est en C2).

import { estimateFromBill, formatMad, formatMadRange } from '../billEstimate';
import { formatKwc } from '../proposition';
import { nearestRealisation, REALISATIONS } from '../realisations';
import type { ConfigLocale, ContexteTunnel } from './contexte';
import type { LocaleTunnel } from './etat';

export interface TextesResidentiel {
  /** `GATED_ANNOUNCE` de la page. */
  annonceGatee: string;
  /** Légende du graphique mensuel. */
  moyenneMensuelle: (avg: string) => string;
  /** Langue de la date du document (hors bascule arabe). */
  localeDate: string;
  /** Ligne « projet » du bandeau du document. */
  projet: (label: string | undefined) => string;
  toitRepere: string;
  pompageRappel: string;
  verifierMontantChamp: string;
  indispoMontant: string;
  indispoFacture: string;
  parMois: string;
  proche: (ville: string, kwc: string, km: number) => string;
  lienRealisation: (slug: string) => string;
  annonceOk: (kwc: string, monthly: string, payback: string) => string;
}

const fr: TextesResidentiel = {
  annonceGatee: 'Votre estimation est prête. Renseignez vos coordonnées pour recevoir votre étude complète et personnalisée.',
  moyenneMensuelle: (a) => `≈ ${a} kWh/mois en moyenne`,
  localeDate: 'fr-FR',
  projet: (l) => `Projet ${(l || 'Résidentiel').toLowerCase()}`,
  toitRepere: 'toit repéré sur carte satellite',
  pompageRappel: 'Le pompage se dimensionne sur votre profondeur et votre besoin en eau — un ingénieur vous rappelle avec un calcul adapté.',
  verifierMontantChamp: 'Vérifiez le montant saisi.',
  indispoMontant: 'Estimation indisponible — vérifiez le montant saisi.',
  indispoFacture: 'Estimation indisponible : indiquez votre facture mensuelle pour la calculer.',
  parMois: '/mois',
  proche: (v, k, km) => `${v} — ${k} — à environ ${km} km de vous`,
  lienRealisation: (s) => `/realisations/${s}`,
  annonceOk: (k, m, p) => `Votre estimation : ${k} kWc, économies estimées ${m}/mois, amortissement ${p}.`,
};

const ar: TextesResidentiel = {
  annonceGatee: 'تقديركم جاهز. أدخلوا معلوماتكم لاستلام دراستكم الكاملة والمخصّصة.',
  moyenneMensuelle: (a) => `≈ ${a} kWh/شهر`,
  localeDate: 'fr-FR',
  projet: (l) => `مشروع ${l || 'سكني'}`,
  toitRepere: 'السطح محدَّد على خريطة الأقمار الصناعية',
  pompageRappel: 'يُحسب الضخ على أساس عمقكم وحاجتكم إلى الماء — سيعاود مهندس الاتصال بكم بحساب مناسب.',
  verifierMontantChamp: 'تحققوا من المبلغ المُدخَل.',
  indispoMontant: 'التقدير غير متوفر — تحققوا من المبلغ المُدخَل.',
  indispoFacture: 'التقدير غير متوفر: أدخلوا فاتورتكم الشهرية لحسابه.',
  parMois: '/شهر',
  proche: (v, k, km) => `${v} — ${k} — على بعد حوالي ${km} كلم منكم`,
  lienRealisation: (s) => `/realisations/${s}`,
  annonceOk: (k, m, p) => `تقديركم: ${k} kWc، توفير مقدَّر ${m}/شهر، استرداد التكلفة ${p}.`,
};

const en: TextesResidentiel = {
  annonceGatee: 'Your estimate is ready. Enter your details to receive your complete, personalised study.',
  moyenneMensuelle: (a) => `≈ ${a} kWh/month on average`,
  localeDate: 'en-GB',
  projet: (l) => `${l || 'Residential'} project`,
  toitRepere: 'roof located on the satellite map',
  pompageRappel: 'Pumping is sized on your depth and water need — an engineer will call you back with an adapted calculation.',
  verifierMontantChamp: 'Please check the amount entered.',
  indispoMontant: 'Estimate unavailable — please check the amount entered.',
  indispoFacture: 'Estimate unavailable: enter your monthly bill to calculate it.',
  parMois: '/month',
  proche: (v, k, km) => `${v} — ${k} — about ${km} km from you`,
  lienRealisation: (s) => `/en/realisations/${s}`,
  annonceOk: (k, m, p) => `Your estimate: ${k} kWc, estimated savings ${m}/month, payback ${p}.`,
};

export const TEXTES_RESIDENTIEL: Record<LocaleTunnel, TextesResidentiel> = { fr, ar, en };

/** Locale de `toLocaleString` pour `fmtNum`/`fmtYears` : `fr-FR` pour FR et AR,
 *  `en-GB` pour EN, tel qu'aujourd'hui. */
export const LOCALE_NOMBRE: Record<LocaleTunnel, string> = { fr: 'fr-FR', ar: 'fr-FR', en: 'en-GB' };

export const fmtNumLocale = (locale: LocaleTunnel) => (n: number): string =>
  (Math.round(n * 10) / 10).toLocaleString(LOCALE_NOMBRE[locale]);

export interface ConfigEstimationResidentielle {
  /** `PUBLIC_ESTIMATE_GATED` de la page. */
  estimationGatee: boolean;
  /** AR seulement : la date du document suit la langue affichée
   *  (`ar-MA-u-nu-latn` quand elle est arabe). FR et EN : date fixe. */
  dateSuitLangue: boolean;
}

export type ContexteEstimationResidentielle = Omit<ContexteTunnel, 'config'> & {
  config: ConfigLocale & ConfigEstimationResidentielle;
};

type VarianteTeaser = 'standard' | 'etude' | 'rappel';

// Répartition mensuelle INDICATIVE de l'irradiation au Maroc (profil PVGIS type
// Casablanca, normalisé à 1,00) : sert UNIQUEMENT à répartir sur 12 mois une
// production ANNUELLE déjà calculée — jamais à créer un chiffre nouveau.
const MONTH_LETTERS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
const GHI_MONTHLY_SHARE = [0.057, 0.062, 0.084, 0.094, 0.105, 0.108, 0.113, 0.105, 0.089, 0.075, 0.057, 0.051];

function construireResidentiel(ctx: ContexteEstimationResidentielle) {
  const { etat, dom, crochets, config } = ctx;
  const { $, num, val, setText, setFieldError, maxBillFor } = dom;
  const T = TEXTES_RESIDENTIEL[config.locale];
  const GATED = config.estimationGatee;
  const REALISATIONS_WITH_KWC = REALISATIONS.filter((r) => r.kwc);
  const h = (nom: string, ...args: any[]) => crochets.appeler(nom, ...args);

  /** WJ88 — annonce UNIQUE du résultat (jamais pendant la phase squelette). */
  function announceEstimate(message: string) {
    const el = $('mt-estimate-announce');
    if (el) el.textContent = message;
  }

  /** Affiche/masque un élément par son id (absent → rien). */
  const cacher = (id: string, cache: boolean) => {
    const el = $(id);
    if (el) el.hidden = cache;
  };
  /** L'estimation vient d'échouer ou n'existe pas : plus aucun chiffre en mémoire. */
  const viderEstimation = () => {
    etat.lastKwcLabel = '';
    etat.lastSavingsLabel = '';
    etat.lastKwc = null;
    etat.estimateShown = null;
    cacher('mt-print-estimate', true);
  };
  /** Les chiffres calculés, exactement ceux du payload lead. */
  const chiffresResidentiel = (e: NonNullable<ReturnType<typeof estimateFromBill>>) => ({
    kwc: e.kwc,
    prodKwh: e.productionKwhYr,
    ecoMadMonthLow: e.savingsMonthlyLow,
    ecoMadMonthHigh: e.savingsMonthlyHigh,
    paybackLabel: e.paybackLabel,
  });

  /** WJ125 — bascule le parcours public en mode gaté : masque le document chiffré
   *  ET les zones qui fuiraient des chiffres, puis révèle la carte teaser
   *  verrouillée. WJ127 — variantes 'standard' | 'etude' | 'rappel'. */
  function showEstimateTeaser(m: string, variante: VarianteTeaser = 'standard') {
    etat.docRendered = true;
    for (const id of ['mt-doc', 'mt-print-estimate', 'mt-nearest-install', 'mt-cost-of-waiting']) cacher(id, true);
    cacher('mt-teaser', false);
    const isAgri = m === 'agricole';
    const standard = variante === 'standard';
    cacher('mt-teaser-hook-roof', isAgri || !standard);
    cacher('mt-teaser-hook-pump', !isAgri || !standard);
    cacher('mt-teaser-hook-etude', variante !== 'etude');
    cacher('mt-teaser-hook-rappel', variante !== 'rappel');
  }

  /** Carte KPI honnête : valeur inconnue → la carte DISPARAÎT (jamais un tiret). */
  function setCard(cardId: string, valueId: string, text: string | null) {
    cacher(cardId, text == null);
    if (text != null) setText(valueId, text);
  }

  function renderMonthlyChart(annualKwh: number) {
    const zone = $('mt-doc-chart-wrap');
    const conteneur = $('mt-doc-chart');
    if (!zone || !conteneur) return;
    if (!Number.isFinite(annualKwh) || annualKwh <= 0) {
      zone.hidden = true;
      return;
    }
    const valeurs = GHI_MONTHLY_SHARE.map((part) => annualKwh * part);
    const vMax = Math.max(...valeurs);
    const [largeur, hauteur, marge, ligneBase] = [560, 168, 8, 140];
    const colonne = (largeur - marge * 2) / 12;
    const largeurBarre = Math.min(30, colonne - 8);
    let barres = '';
    valeurs.forEach((v, i) => {
      const hb = vMax > 0 ? Math.max(3, (v / vMax) * 108) : 3;
      const x = marge + colonne * i + (colonne - largeurBarre) / 2;
      const cx = marge + colonne * i + colonne / 2;
      barres += `<rect x="${x.toFixed(1)}" y="${(ligneBase - hb).toFixed(1)}" width="${largeurBarre.toFixed(1)}" height="${hb.toFixed(1)}" rx="3" fill="#F5A623"/>`;
      barres += `<text x="${cx.toFixed(1)}" y="${ligneBase + 17}" text-anchor="middle" font-size="11" fill="#6b7280" font-family="DM Sans, system-ui, sans-serif">${MONTH_LETTERS[i]}</text>`;
    });
    const moyenne = Math.round(annualKwh / 12);
    conteneur.innerHTML =
      `<svg viewBox="0 0 ${largeur} ${hauteur}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">` +
      `<line x1="${marge}" y1="${ligneBase}" x2="${largeur - marge}" y2="${ligneBase}" stroke="#E5E7EB" stroke-width="1"/>` +
      barres +
      `<text x="${largeur - marge}" y="14" text-anchor="end" font-size="11" fill="#1A2B4A" font-family="DM Sans, system-ui, sans-serif">${T.moyenneMensuelle(formatMad(moyenne))}</text>` +
      '</svg>';
    zone.hidden = false;
  }

  /** Habillage commun du document (date, sous-titre par profil, ville, ligne
   *  client/site — uniquement des faits CONNUS, jamais un tiret). */
  function fillDocChrome() {
    etat.docRendered = true;
    const localeDate = config.dateSuitLangue && h('langueActive') === 'ar' ? 'ar-MA-u-nu-latn' : T.localeDate;
    const dateEl = $('mt-doc-date');
    if (dateEl) dateEl.textContent = new Date().toLocaleDateString(localeDate, { day: 'numeric', month: 'long', year: 'numeric' });
    const m = etat.mode || 'residentiel';
    const subEl = $('mt-doc-subtitle');
    if (subEl) subEl.textContent = h('modeDocSubtitle', m) || h('modeDocSubtitle', 'residentiel');
    const adresseCarte = $('rp9-address') as HTMLInputElement | null;
    const adresseRepli = $('mt-fallback-address') as HTMLInputElement | null;
    const city = (val('mt-city') || adresseCarte?.value || adresseRepli?.value || '').trim();
    const villeSpan = $('mt-doc-city');
    if (villeSpan) villeSpan.textContent = city;
    cacher('mt-doc-city-line', !city);
    const metaEl = $('mt-doc-meta');
    if (metaEl) {
      const parts: string[] = [];
      if (city) parts.push(city);
      parts.push(T.projet(h('modeLabel', m)));
      if (etat.capturePin) parts.push(T.toitRepere);
      metaEl.textContent = parts.join(' · ');
      metaEl.hidden = false;
    }
    void h('tryRoofSnapshot');
  }

  /** QX — remise à zéro des zones transverses du document ; chaque branche
   *  (résidentiel/pro/agricole) ré-affiche ensuite uniquement les siennes. */
  const ZONES_DOCUMENT = [
    'mt-estimate-toolarge-pro', 'mt-estimate-pro-missing',
    'mt-doc-kpis-pro', 'mt-doc-kpis-agri', 'mt-pro-capped',
    'mt-doc-chart-wrap', 'mt-doc-flow', 'mt-doc-hypo-wrap',
    'mt-nearest-install', 'mt-cost-of-waiting', 'mt-climate-band',
  ];
  function resetDocZones() {
    ZONES_DOCUMENT.forEach((id) => cacher(id, true));
  }

  /** @returns true si une estimation réelle a été calculée et affichée (false si
   *  indisponible — facture absente/non chiffrable/hors plafond). WJ46 — le SEUL
   *  appelant qui agit sur cette valeur est le clic « Voir mon estimation ». */
  function computeEstimate(): boolean {
    const exact = num('mt-facture-hiver');
    const bill = h('resolveMonthlyBill') as number | null;
    const mode = etat.mode;
    const erreurFacture = (message: string | null) => setFieldError('mt-facture-hiver', 'mt-facture-hiver-err', message);
    resetDocZones();
    // WJ125 — parcours public gaté : teaser verrouillé AVANT tout rendu ; les
    // chemins « succès » s'arrêtent avant d'écrire le moindre chiffre à l'écran.
    if (GATED) showEstimateTeaser(mode);
    if (mode === 'agricole') {
      // WJ111 — jamais estimateFromBill ici : le pompage se dimensionne sur l'hydraulique.
      for (const id of ['mt-estimate-body', 'mt-estimate-note', 'mt-estimate-unavailable', 'mt-estimate-toolarge']) cacher(id, true);
      erreurFacture(null);
      const ag = h('computeAgricoleEstimate');
      if (!ag) {
        // Hydraulique manquante → carte chaleureuse (WJ127 : l'accroche du teaser
        // porte le MÊME message que l'annonce ci-dessous), aucun chiffre divulgué.
        cacher('mt-estimate-agricole', false);
        if (GATED) showEstimateTeaser(mode, 'rappel');
        viderEstimation();
        fillDocChrome();
        h('updatePanels3dVisibility');
        announceEstimate(T.pompageRappel);
        return true;
      }
      cacher('mt-estimate-agricole', true);
      h('renderAgricoleEstimate', ag);
      return true;
    }
    cacher('mt-estimate-agricole', true);
    if (h('isProMode', mode)) {
      cacher('mt-estimate-body', true);
      cacher('mt-estimate-note', true);
      erreurFacture(null);
      return h('computeProEstimate');
    }
    // ——— RÉSIDENTIEL (défaut) — moteur billEstimate inchangé (WJ1/WJ112) ———
    // WJ65 — montant exact au-delà du plafond : message honnête dédié + erreur
    // inline, sans jamais BLOQUER l'étape.
    if (exact != null && exact > maxBillFor('residentiel')) {
      for (const id of ['mt-estimate-body', 'mt-estimate-note', 'mt-estimate-unavailable']) cacher(id, true);
      cacher('mt-estimate-toolarge', false);
      // WJ127 — `#mt-doc` est masqué en parcours public : l'accroche dit la même chose.
      if (GATED) showEstimateTeaser(mode, 'etude');
      erreurFacture(T.verifierMontantChamp);
      viderEstimation();
      fillDocChrome();
      h('updatePanels3dVisibility');
      announceEstimate(T.indispoMontant);
      return false;
    }
    erreurFacture(null);
    cacher('mt-estimate-toolarge', true);
    const lat = etat.capturePin?.lat;
    const champAdresse = $('rp9-address') as HTMLInputElement | null;
    const city = (val('mt-city') || champAdresse?.value || '').trim() || undefined;
    // Coupe fondateur 18/08 + ordre fondateur 21/08 : ni `exactKwhMonthly` ni
    // `ombrage` ne sont transmis (le tunnel ne pose plus ces questions).
    const est = bill != null ? estimateFromBill(bill, { lat, city }) : null;
    if (!est) {
      cacher('mt-estimate-body', true);
      cacher('mt-estimate-note', true);
      cacher('mt-estimate-unavailable', false);
      viderEstimation();
      fillDocChrome();
      h('updatePanels3dVisibility');
      announceEstimate(T.indispoFacture);
      return false;
    }
    // WJ125 — chiffres calculés (payload lead) + labels (deeplink WhatsApp / CRM),
    // construits AVANT tout rendu.
    etat.lastKwc = est.kwc;
    etat.lastKwcLabel = `${formatKwc(est.kwc)} kWc`;
    etat.lastSavingsLabel = `${formatMadRange(est.savingsMonthlyLow, est.savingsMonthlyHigh)}${T.parMois}`;
    etat.estimateShown = chiffresResidentiel(est);
    // WJ129 (finding 6) — DÉCALAGE SÉMANTIQUE ASSUMÉ : en parcours gaté,
    // « estimation/viewed » part alors qu'aucun chiffre n'est rendu, puis
    // « contact/reached » au même instant.
    if (h('hasReachedConsentStep')) h('sendFunnelBeacon', 'estimation', 'viewed');
    if (GATED) {
      h('updatePanels3dVisibility');
      if (h('hasReachedConsentStep')) h('sendFunnelBeacon', 'contact', 'reached');
      announceEstimate(T.annonceGatee);
      return true;
    }
    cacher('mt-estimate-body', false);
    cacher('mt-estimate-note', false);
    cacher('mt-doc-hypo-wrap', false);
    cacher('mt-doc-hypotheses', true);
    cacher('mt-estimate-unavailable', true);
    // WJ104 — « estimation VUE » (dédupliquée une fois par visite, jamais avant le consentement).
    if (h('hasReachedConsentStep')) h('sendFunnelBeacon', 'estimation', 'viewed');
    const monthly = formatMadRange(est.savingsMonthlyLow, est.savingsMonthlyHigh);
    setText('mt-est-kwc', formatKwc(est.kwc));
    setText('mt-est-prod', formatMad(est.productionKwhYr));
    setText('mt-est-savings', monthly);
    setText('mt-est-payback', est.paybackLabel);
    etat.lastKwcLabel = `${formatKwc(est.kwc)} kWc`;
    etat.lastSavingsLabel = `${monthly}${T.parMois}`;
    etat.lastKwc = est.kwc;
    // WJ71 — bande de confiance climatique, SEULEMENT quand elle dit vraiment quelque chose.
    const bandeClimat = $('mt-climate-band');
    if (bandeClimat) {
      const valeurBande = $('mt-climate-band-value');
      const showBand = est.savingsLowBand < est.savingsHigh;
      bandeClimat.hidden = !showBand;
      if (showBand && valeurBande) {
        valeurBande.textContent = formatMadRange(est.savingsLowBand, est.savingsLowBand);
      }
    }
    // QX — exactement les chiffres affichés dans le document (payload lead).
    etat.estimateShown = chiffresResidentiel(est);
    // W342 — « installation la plus proche » : UNIQUEMENT si un repère GPS a été
    // posé et qu'un vrai chantier est à proximité honnête (≤ 80 km).
    const proche = etat.capturePin
      ? nearestRealisation(etat.capturePin.lat, etat.capturePin.lng, 80, REALISATIONS_WITH_KWC)
      : null;
    if (proche) {
      const { realisation: r, distanceKm } = proche;
      const texteProche = $('mt-nearest-install-text');
      const lienProche = $('mt-nearest-install-link') as HTMLAnchorElement | null;
      if (texteProche) texteProche.textContent = T.proche(r.ville, String(r.kwc), Math.round(distanceKm));
      if (lienProche) lienProche.href = T.lienRealisation(r.slug);
    }
    cacher('mt-nearest-install', !proche);
    // W360 — coût de l'attente DÉRIVÉ de la même borne basse déjà affichée.
    if ($('mt-cost-of-waiting')) {
      const coutAttente = $('mt-cost-of-waiting-value');
      if (coutAttente) coutAttente.textContent = `${formatMad(est.savingsMonthlyLow)} MAD`;
      cacher('mt-cost-of-waiting', est.savingsMonthlyLow <= 0);
    }
    // QX — répartition mensuelle de la production annuelle déjà calculée.
    renderMonthlyChart(est.productionKwhYr);
    cacher('mt-print-estimate', false);
    fillDocChrome();
    h('updatePanels3dVisibility');
    // WJ59/WB30 — l'estimation réelle rend le formulaire de contact pertinent.
    if (h('hasReachedConsentStep')) h('sendFunnelBeacon', 'contact', 'reached');
    announceEstimate(T.annonceOk(formatKwc(est.kwc), monthly, est.paybackLabel));
    return true;
  }

  return {
    brancherAffichage: () => {
      crochets.installer('announceEstimate', announceEstimate);
      crochets.installer('showEstimateTeaser', showEstimateTeaser);
      crochets.installer('setCard', setCard);
      crochets.installer('renderMonthlyChart', renderMonthlyChart);
      crochets.installer('fillDocChrome', fillDocChrome);
    },
    brancherZones: () => crochets.installer('resetDocZones', resetDocZones),
    brancherCalcul: () => crochets.installer('computeEstimate', computeEstimate),
  };
}

// Une seule construction par contexte : les installeurs par plage partagent les mêmes fermetures.
const construits = new WeakMap<object, ReturnType<typeof construireResidentiel>>();
const residentielDe = (ctx: ContexteEstimationResidentielle) => {
  let c = construits.get(ctx);
  if (!c) { c = construireResidentiel(ctx); construits.set(ctx, c); }
  return c;
};

/** FR l. 3342-3496 : état d'affichage, teaser, annonce, cartes, graphique, habillage du document. */
export function installerEstimationResidentielleAffichage(ctx: ContexteEstimationResidentielle): void {
  residentielDe(ctx).brancherAffichage();
}
/** FR l. 3529-3556 : remise à zéro des zones du document. */
export function installerEstimationResidentielleZones(ctx: ContexteEstimationResidentielle): void {
  residentielDe(ctx).brancherZones();
}
/** FR l. 3865-4092 : `computeEstimate`. */
export function installerEstimationResidentielleCalcul(ctx: ContexteEstimationResidentielle): void {
  residentielDe(ctx).brancherCalcul();
}
/** Les trois plages, dans l'ordre de la page. */
export function installerEstimationResidentielle(ctx: ContexteEstimationResidentielle): void {
  installerEstimationResidentielleAffichage(ctx);
  installerEstimationResidentielleZones(ctx);
  installerEstimationResidentielleCalcul(ctx);
}
