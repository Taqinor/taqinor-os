// RWEB17-M7 — SECTION « VALIDATION ET CORPS DU LEAD » du tunnel « mon-toit ».
//
// Reprend, À L'IDENTIQUE du comportement des trois pages (FR/EN/AR), la
// validation en direct (blur par champ, « Continuer » valide son étape), la
// lecture de l'état de la page (`lireEtatTunnel`), le corps du lead
// (`corpsDuLead`) et l'affichage des erreurs inline. Les textes sont des TABLES
// DE LOCALE (ceux de chaque page, mot pour mot) ; la logique est unique.
//
// Cette section ne possède AUCUN `let` : elle lit `ctx.etat` et appelle, par
// `ctx.crochets`, ce que les autres sections possèdent (voir `CROCHETS_REQUIS`).
// Non câblée dans les pages avant M17.

import { appareilId } from '../visite';
import type { ContexteTunnel } from './contexte';
import { etatVide, type EtatTunnel } from './champs';
import { construireCorps, type MessagesErreurs } from './corps';
import { ERREURS } from './i18n';
import { lireChampsDomTunnel } from './lecture';
import type { LocaleTunnel } from './etat';

/** Crochets que cette section APPELLE (installés par les autres sections). */
export const CROCHETS_REQUIS = [
  'langueActive', // M2 : 'fr' | 'ar' | 'en' — la langue AFFICHÉE
  'isProMode', // M2
  'proBillId', // M5
  'proBillErrId', // M5
  'proBillUnit', // M5
  'getOrCreateClientRef', // M1
  'getOrCreateDedupTokens', // M1
  'readTrackingParams', // M1
] as const;

interface TexteValidation {
  /** `${label} : chiffres uniquement.` — la ponctuation propre à la locale. */
  chiffresSeulement: (label: string) => string;
  /** Libellés des champs numériques facultatifs, dans l'ordre de la page. */
  champsNumeriques: Array<[string, string]>;
  montantInvalide: string;
  verifierMontant: string;
  nomRequis: string;
  telephoneInvalide: string;
  villeRequise: string;
  typeProjet: string;
  consoPro: string;
  factureRequise: string;
  trancheRequise: string;
}

const TEXTES: Record<LocaleTunnel, TexteValidation> = {
  fr: {
    chiffresSeulement: (label) => `${label} : chiffres uniquement.`,
    champsNumeriques: [
      ['mt-surface-m2', 'Surface'],
      ['mt-profondeur', 'Profondeur'],
      ['mt-hmt', 'HMT'],
      ['mt-water-need', 'Besoin en eau'],
      ['mt-surface-ha', 'Surface'],
      ['mt-fuel-spend', 'Dépense carburant'],
    ],
    montantInvalide: 'Montant invalide — chiffres uniquement.',
    verifierMontant: 'Vérifiez le montant saisi.',
    nomRequis: 'Nom complet requis',
    telephoneInvalide: 'Numéro de téléphone invalide',
    villeRequise: 'Adresse / ville requise',
    typeProjet: 'Choisissez votre type de projet pour continuer.',
    consoPro: 'Indiquez votre consommation mensuelle (MAD ou kWh) pour calculer votre estimation.',
    factureRequise: 'Indiquez votre facture : montant exact ou tranche.',
    trancheRequise: 'Choisissez une tranche si vous ne connaissez pas le montant exact.',
  },
  en: {
    chiffresSeulement: (label) => `${label}: numbers only.`,
    champsNumeriques: [
      ['mt-surface-m2', 'Surface'],
      ['mt-profondeur', 'Depth'],
      ['mt-hmt', 'TDH'],
      ['mt-water-need', 'Water need'],
      ['mt-surface-ha', 'Surface'],
      ['mt-fuel-spend', 'Fuel spend'],
    ],
    montantInvalide: 'Invalid amount — numbers only.',
    verifierMontant: 'Please check the amount entered.',
    nomRequis: 'Full name required',
    telephoneInvalide: 'Invalid phone number',
    villeRequise: 'Address / city required',
    typeProjet: 'Choose your project type to continue.',
    consoPro: 'Enter your monthly consumption (MAD or kWh) to calculate your estimate.',
    factureRequise: 'Enter your bill: exact amount or a range.',
    trancheRequise: "Choose a range if you don't know the exact amount.",
  },
  ar: {
    chiffresSeulement: (label) => `${label}: أرقام فقط.`,
    champsNumeriques: [
      ['mt-surface-m2', 'المساحة'],
      ['mt-profondeur', 'العمق'],
      ['mt-hmt', 'HMT'],
      ['mt-water-need', 'الحاجة إلى الماء'],
      ['mt-surface-ha', 'المساحة'],
      ['mt-fuel-spend', 'نفقة الوقود'],
    ],
    montantInvalide: 'مبلغ غير صالح — أرقام فقط.',
    verifierMontant: 'تحققوا من المبلغ المُدخَل.',
    nomRequis: 'الاسم الكامل مطلوب',
    telephoneInvalide: 'رقم هاتف غير صالح',
    villeRequise: 'العنوان / المدينة مطلوب',
    typeProjet: 'اختاروا نوع مشروعكم للمتابعة.',
    consoPro: 'أدخلوا استهلاككم الشهري (درهم أو kWh) لحساب تقديركم.',
    factureRequise: 'أدخلوا فاتورتكم: المبلغ الدقيق أو شريحة.',
    trancheRequise: 'اختاروا شريحة إن لم تعرفوا المبلغ الدقيق.',
  },
};

/** WJ39 — messages de `validateLead` (lib/lead.ts) connus, traduits pour la page
 *  EN : un champ en erreur ne s'y affiche jamais en français. Hors de cet
 *  ensemble, le message brut passe. */
const VALIDATION_ERROR_EN: Record<string, string> = {
  'Nom complet requis': 'Full name required',
  'Numéro invalide': 'Invalid number',
  'Numéro invalide — format attendu : 06 XX XX XX XX ou +212 6 XX XX XX XX':
    'Invalid number — expected format: 06 XX XX XX XX or +212 6 XX XX XX XX',
  'Ville / commune requise': 'City / town required',
  'Type de toiture requis': 'Roof type required',
  'Tranche de facture requise': 'Bill range required',
  'Le consentement est requis pour être recontacté': 'Consent is required so we can contact you back',
};

export interface SectionChamps {
  scrollToInvalid(el: HTMLElement | null): void;
  checkOptionalNumber(id: string, label: string): boolean;
  checkFactureHiver(): boolean;
  validateStep0(): boolean;
  validateStep1(): boolean;
}
export interface SectionCorps {
  lireEtatTunnel(): EtatTunnel;
  corpsDuLead(): { body: Record<string, unknown>; errors: Record<string, string> };
  showInlineErrors(errors: Record<string, string>): void;
}
export type SectionValidation = SectionChamps & SectionCorps;

/** Les deux installeurs d'un coup (ordre de la page : champs, puis corps). */
export function installerValidation(ctx: ContexteTunnel, doc: Document): SectionValidation {
  return { ...installerValidationChamps(ctx, doc), ...installerCorpsLead(ctx, doc) };
}

/**
 * Installe la validation en direct : écouteurs `blur`, puis inscrit dans
 * `ctx.crochets` `validateStep0/1`, `checkFactureHiver`, `scrollToInvalid`
 * (FR l. 4271-4437). `doc` : le Document de la page (injecté).
 */
export function installerValidationChamps(ctx: ContexteTunnel, doc: Document): SectionChamps {
  const { $, val, num, maxBillFor, setFieldError } = ctx.dom;
  const t = TEXTES[ctx.locale];
  const reducedMotion = doc.defaultView?.matchMedia('(prefers-reduced-motion: reduce)').matches ?? false;
  const appeler = (nom: string, ...args: unknown[]) => ctx.crochets.appeler(nom, ...args);

  // ——— QX : VALIDATION EN DIRECT. Les valeurs tapées ne sont JAMAIS
  // corrigées/rejetées automatiquement (règle repo : pas de snap). ———
  function scrollToInvalid(el: HTMLElement | null) {
    if (!el) return;
    el.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'center' });
    if (typeof el.focus === 'function') el.focus({ preventScroll: true });
  }
  /** Champ numérique FACULTATIF : vide = OK ; non-numérique ou négatif = erreur. */
  function checkOptionalNumber(id: string, label: string): boolean {
    const raw = val(id).trim();
    if (raw === '') {
      setFieldError(id, `${id}-err`, null);
      return true;
    }
    const n = num(id);
    if (n == null || n < 0) {
      setFieldError(id, `${id}-err`, t.chiffresSeulement(label));
      return false;
    }
    setFieldError(id, `${id}-err`, null);
    return true;
  }
  const OPTIONAL_NUMBER_FIELDS = t.champsNumeriques;
  for (const [id, label] of OPTIONAL_NUMBER_FIELDS) {
    $(id)?.addEventListener('blur', () => {
      checkOptionalNumber(id, label);
    });
  }
  /** Facture exacte résidentielle au blur : format + plafond de bon sens. */
  function checkFactureHiver(): boolean {
    const raw = val('mt-facture-hiver').trim();
    if (raw === '') {
      setFieldError('mt-facture-hiver', 'mt-facture-hiver-err', null);
      return true;
    }
    const n = num('mt-facture-hiver');
    if (n == null || n <= 0) {
      setFieldError('mt-facture-hiver', 'mt-facture-hiver-err', t.montantInvalide);
      return false;
    }
    if (n > maxBillFor('residentiel')) {
      setFieldError('mt-facture-hiver', 'mt-facture-hiver-err', t.verifierMontant);
      return true; // le document affiche le chemin honnête « vérifiez » — jamais un blocage
    }
    setFieldError('mt-facture-hiver', 'mt-facture-hiver-err', null);
    return true;
  }
  $('mt-facture-hiver')?.addEventListener('blur', () => {
    checkFactureHiver();
  });
  // Factures pro (WJ122 : la commerciale aussi) : validation légère au blur.
  for (const id of ['mt-pro-bill', 'mt-cc-bill']) {
    $(id)?.addEventListener('blur', () => {
      const raw = val(id).trim();
      if (raw === '') {
        setFieldError(id, `${id}-err`, null);
        return;
      }
      const n = num(id);
      setFieldError(id, `${id}-err`, n == null || n <= 0 ? t.montantInvalide : null);
    });
  }
  // Contact : chaque champ se valide dès la perte de focus (miroir léger de
  // validateLead — l'envoi final reste validé par validateLead au complet).
  $('mt-name')?.addEventListener('blur', () => {
    const v = val('mt-name').trim();
    setFieldError('mt-name', 'mt-name-err', v !== '' && (v.length < 2 || !/\p{L}/u.test(v)) ? t.nomRequis : null);
  });
  $('mt-phone')?.addEventListener('blur', () => {
    const digits = val('mt-phone').replace(/\D/g, '');
    setFieldError('mt-phone', 'mt-phone-err', val('mt-phone').trim() !== '' && digits.length < 9 ? t.telephoneInvalide : null);
  });
  $('mt-city')?.addEventListener('blur', () => {
    const v = val('mt-city').trim();
    setFieldError('mt-city', 'mt-city-err', v !== '' && v.length < 2 ? t.villeRequise : null);
  });
  /** Étape carte : un profil doit être choisi (nudge inline sur les cartes). */
  function validateStep0(): boolean {
    if (ctx.etat.mode) return true;
    const err = $('mt-mode-err');
    if (err) {
      err.textContent = t.typeProjet;
      err.hidden = false;
    }
    scrollToInvalid(doc.querySelector<HTMLButtonElement>('.mt-mode'));
    return false;
  }
  /** Étape questions : validation PAR PROFIL avant le calcul. */
  function validateStep1(): boolean {
    const mode = ctx.etat.mode;
    if (appeler('isProMode', mode)) {
      const billId = appeler('proBillId') as string;
      const billErrId = appeler('proBillErrId') as string;
      const raw = val(billId).trim();
      const n = num(billId);
      if (raw === '' || n == null || n <= 0) {
        setFieldError(billId, billErrId, t.consoPro);
        scrollToInvalid($(billId));
        return false;
      }
      setFieldError(billId, billErrId, null);
      return true;
    }
    if (mode === 'agricole') {
      // Rien n'est REQUIS (hydraulique manquante = chemin honnête « un
      // ingénieur vous rappelle ») — mais un nombre saisi doit être un nombre.
      for (const [id, label] of OPTIONAL_NUMBER_FIELDS) {
        if (!['mt-profondeur', 'mt-hmt', 'mt-water-need', 'mt-fuel-spend'].includes(id)) continue;
        if (!checkOptionalNumber(id, label)) {
          scrollToInvalid($(id));
          return false;
        }
      }
      return true;
    }
    // Résidentiel : SEULE la facture est nécessaire (montant exact OU tranche) ;
    // le type de toit est dérivé par le registre (coupe fondateur 18/08).
    const rawF = val('mt-facture-hiver').trim();
    const exact = num('mt-facture-hiver');
    if (rawF !== '' && (exact == null || exact <= 0)) {
      setFieldError('mt-facture-hiver', 'mt-facture-hiver-err', t.montantInvalide);
      scrollToInvalid($('mt-facture-hiver'));
      return false;
    }
    if ((exact == null || exact <= 0) && !val('mt-bill')) {
      setFieldError('mt-facture-hiver', 'mt-facture-hiver-err', t.factureRequise);
      setFieldError('mt-bill', 'mt-bill-err', t.trancheRequise);
      scrollToInvalid($('mt-facture-hiver'));
      return false;
    }
    setFieldError('mt-bill', 'mt-bill-err', null);
    return true;
  }

  const section: SectionChamps = {
    scrollToInvalid, checkOptionalNumber, checkFactureHiver, validateStep0, validateStep1,
  };
  for (const [nom, fn] of Object.entries(section)) ctx.crochets.installer(nom, fn as (...a: any[]) => any);
  return section;
}

/**
 * Installe le corps du lead : `lireEtatTunnel`, `corpsDuLead`, `showInlineErrors`
 * (FR l. 4486-4587). `doc` : le Document de la page (injecté).
 */
export function installerCorpsLead(ctx: ContexteTunnel, doc: Document): SectionCorps {
  const { $, num, setFieldError } = ctx.dom;
  const appeler = (nom: string, ...args: unknown[]) => ctx.crochets.appeler(nom, ...args);

  /** L'état de la page : « un champ ↔ un id » vient du lecteur partagé, le reste
   *  de l'état interne (groupes de cartes, carte, jetons, tracking, mode). */
  function lireEtatTunnel(): EtatTunnel {
    const e = ctx.etat;
    const addressEl = $('rp9-address') as HTMLInputElement | null;
    const fallbackAddrEl = $('mt-fallback-address') as HTMLInputElement | null;
    return {
      ...etatVide(),
      // On lit TOUT, sans condition : les gates sont dans le registre.
      ...lireChampsDomTunnel(doc),
      adresseCarte: addressEl?.value ?? '',
      adresseSecours: fallbackAddrEl?.value ?? '',
      // WJ30 — type de projet et langue active partent au webhook ; la page EN
      // n'envoie pas de langue préférée.
      mode: e.mode,
      languePreferee: ctx.locale === 'en' ? '' : e.currentLang,
      // WJ122 — la conso C&I vient du panneau ACTIF ; le tarif accompagne la valeur.
      factureProValeur: num(appeler('proBillId')),
      factureProUnite: appeler('proBillUnit'),
      tarifProMadKwh: e.lastProTarifMadKwh,
      tension: e.tension,
      activite: e.activity,
      tensionTouchee: e.tensionTouched,
      activiteTouchee: e.activityTouched,
      categorieCommerciale: e.commercialCategory,
      equipes: e.equipes,
      typeSurface: e.surfaceType,
      sourceEau: e.waterSource,
      uniteEau: e.waterUnit,
      regionAgricole: e.regionAgricole,
      creneauVisitePartie: e.visitWindowPart,
      creneauVisiteSemaine: e.visitWindowWeek,
      occupationJour: e.occupationJour,
      clientRef: appeler('getOrCreateClientRef'),
      idempotencyKey: appeler('getOrCreateDedupTokens').idempotencyKey,
      eventId: appeler('getOrCreateDedupTokens').eventId,
      appareilId: appareilId(),
      estimationAffichee: e.estimateShown,
      tracking: appeler('readTrackingParams'),
      repereToit: e.capturePin,
      contourToit: e.captureOutline,
      layoutToit: e.captureLayout,
    };
  }

  /** Le corps du lead + les erreurs client. FR/AR : table de la langue AFFICHÉE
   *  au moment de l'envoi ; EN : table anglaise. */
  function corpsDuLead(): { body: Record<string, unknown>; errors: Record<string, string> } {
    const messages = ERREURS[appeler('langueActive') as LocaleTunnel] as MessagesErreurs;
    return construireCorps(lireEtatTunnel(), { messages });
  }

  // EN : `validateLead` rend du français que la page traduit ; FR/AR : tel quel.
  const traduire = (msg: string | null | undefined): string | null =>
    ctx.locale === 'en' ? (msg == null ? null : (VALIDATION_ERROR_EN[msg] ?? msg)) : (msg ?? null);
  function showInlineErrors(errors: Record<string, string>) {
    setFieldError('mt-name', 'mt-name-err', traduire(errors.fullName));
    setFieldError('mt-phone', 'mt-phone-err', traduire(errors.phone));
    setFieldError('mt-city', 'mt-city-err', traduire(errors.city));
    // `errors.roofType` n'a plus de champ où s'afficher (type de toit retiré).
    // CIW404 — l'erreur de tranche va sur le champ VISIBLE du profil actif.
    if (appeler('isProMode', ctx.etat.mode)) setFieldError(appeler('proBillId'), appeler('proBillErrId'), traduire(errors.billRange));
    else setFieldError('mt-bill', 'mt-bill-err', traduire(errors.billRange));
    const cErr = $('mt-consent-err');
    const consentMsg = traduire(errors.consent);
    if (cErr) {
      cErr.textContent = consentMsg ?? '';
      cErr.hidden = !consentMsg;
    }
  }

  const section: SectionCorps = { lireEtatTunnel, corpsDuLead, showInlineErrors };
  for (const [nom, fn] of Object.entries(section)) ctx.crochets.installer(nom, fn as (...a: any[]) => any);
  return section;
}
