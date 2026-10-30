// RWEB17-M19 — CONFIGURATION PAR LOCALE du tunnel « mon-toit » : tout ce qui différait
// encore entre les trois pages (langue basculable, format des nombres, textes de la carte,
// date du document, statuts de la carte) vit ici, en trois objets `CONFIG_FR`, `CONFIG_EN`,
// `CONFIG_AR`. Chaque page n'importe que la sienne et la passe à `demarrerTunnel`
// (lib/tunnel/tunnel.ts). Les imports DYNAMIQUES des modules lourds (roofPro11 : MapLibre,
// Three) restent fournis par la page (`ChargeursCarte`) : aucun type de scripts/roofPro11
// n'entre dans la garde `tsc` de src/lib.

import type { ConfigLocale } from './contexte';
import type { ConfigCarte } from './carte';
import type { ConfigEstimationPro } from './estimationPro';
import { fmtNumLocale, TEXTES_RESIDENTIEL, type ConfigEstimationResidentielle } from './estimationResidentielle';

/** Forme de `CaptureStrings` (scripts/roofPro11/mapDraw) — recopiée structurellement pour
 *  rester hors de la garde `tsc` de src/lib. */
type TextesCapture = Record<string, string | ((n: number) => string)>;

/** Configuration complète d'une locale (le `doc`, `reducedMotion` et les chargeurs de la
 *  carte sont ajoutés au démarrage par `demarrerTunnel`). */
export type ConfigTunnel = ConfigLocale
  & Omit<ConfigCarte, 'doc' | 'reducedMotion' | 'chargeurs'>
  & ConfigEstimationPro
  & ConfigEstimationResidentielle;

// ——— WJ125 — RÈGLE FONDATEUR anti-concurrent : en parcours public, le
// document d'estimation chiffré (#mt-doc), l'« installation la plus proche »
// (kWc + km) et le « coût de l'attente » (MAD) NE SE RENDENT PLUS. Le calcul
// continue en silence (estimateShown + labels partent au CRM et au deeplink
// WhatsApp) mais AUCUN chiffre précis n'est écrit dans le DOM public : une
// carte teaser verrouillée (aperçu flouté SANS le moindre chiffre) renvoie au
// formulaire. Le document complet + « Imprimer » vivent UNIQUEMENT sur
// /proposition/<token> (envoyé par le commercial). ———
const PUBLIC_ESTIMATE_GATED: boolean = true;
// ——— Décision fondateur 13/09/2026 (modèle « Palmetto ») : l'aperçu 3D des
// panneaux redevient visible AVANT la porte de contact — VISUEL SEUL, aucun
// chiffre dans le DOM (ni kWc, ni nombre de panneaux, ni prix : vérifié dans
// le bloc #mt-panels3d et viewerOnly). Le wow pré-contact aide la conversion
// (les meilleurs tunnels mondiaux montrent l'implantation et verrouillent le
// PRIX) ; WJ125 reste intact pour tous les chiffres, qui vivent sur
// /proposition/<token>. Repasser à false pour ré-masquer le 3D public.
const PUBLIC_3D_PREVIEW: boolean = true;

// WJ41 — map/geocoder system messages (roofPro11/mapDraw.ts + captureBoot.ts
// default to French); this page passes English strings so the single most
// interactive moment of the funnel never speaks French to EN visitors.
const ROOF_TOOL_STRINGS_EN: TextesCapture = {
  searchAddressThenPin: 'Search for your address, then drop a pin on your roof.',
  pinPlaced: 'Pin placed. You can adjust it, or trace the outline (optional), then fill in your details.',
  outlineTraced: 'Outline traced. Fill in your details below, then submit.',
  traceOutline: 'Trace the outline of your roof. Double-click to close it (optional).',
  outlineCrosses: 'Your trace crosses itself — fix it ("Clear") before closing.',
  pointWouldCross: 'This point would cross your trace — place it elsewhere to keep a simple outline.',
  doubleClickToClose: 'Double-click (or "Finish") to close the roof and start the calculation.',
  cornerPlaced: (n) => `Corner ${n} placed — keep tracing the outline.`,
  lastPointUndone: (n) => `Last point undone — ${n} corner(s) remaining. Keep tracing.`,
  clickCornersToClose: 'Click the corners of your roof. Double-click to close it and start the calculation.',
  searchingAddress: 'Searching for the address…',
  addressNotFound: 'Address not found. Specify the city or move the map by hand.',
  chooseFromList: 'Choose your address from the list, then click the corners of your roof.',
  searchUnavailable: 'Search unavailable. Move the map by hand to find your roof.',
};

// WJ41 — رسائل نظام الخريطة/محدد المواقع (roofPro11/mapDraw.ts + captureBoot.ts
// تكون افتراضياً بالفرنسية) — هذه الصفحة تمرر نصوصاً عربية حتى لا تتحدث اللحظة
// الأكثر تفاعلاً في المسار بالفرنسية مع الزوار الناطقين بالعربية.
const ROOF_TOOL_STRINGS_AR: TextesCapture = {
  searchAddressThenPin: 'ابحثوا عن عنوانكم، ثم ضعوا علامة على سطحكم.',
  pinPlaced: 'تم وضع العلامة. يمكنكم تعديلها، أو رسم محيط السطح (اختياري)، ثم ملء بياناتكم.',
  outlineTraced: 'تم رسم المحيط. املؤوا بياناتكم أدناه، ثم أرسلوا.',
  traceOutline: 'ارسموا محيط سطحكم. انقروا نقراً مزدوجاً للإغلاق (اختياري).',
  outlineCrosses: 'رسمكم يتقاطع مع نفسه — صححوه (« مسح ») قبل الإغلاق.',
  pointWouldCross: 'هذه النقطة ستقاطع رسمكم — ضعوها في مكان آخر للحفاظ على محيط بسيط.',
  doubleClickToClose: 'انقروا نقراً مزدوجاً (أو « إنهاء ») لإغلاق السطح وبدء الحساب.',
  cornerPlaced: (n) => `تم وضع الزاوية ${n} — واصلوا رسم المحيط.`,
  lastPointUndone: (n) => `تم التراجع عن آخر نقطة — ${n} زاوية (زوايا) متبقية. واصلوا الرسم.`,
  clickCornersToClose: 'انقروا زوايا سطحكم. انقروا نقراً مزدوجاً للإغلاق وبدء الحساب.',
  searchingAddress: 'جارٍ البحث عن العنوان…',
  addressNotFound: 'العنوان غير موجود. حددوا المدينة أو حرّكوا الخريطة يدوياً.',
  chooseFromList: 'اختاروا عنوانكم من القائمة، ثم انقروا زوايا سطحكم.',
  searchUnavailable: 'البحث غير متوفر. حرّكوا الخريطة يدوياً للعثور على سطحكم.',
};

export const CONFIG_FR: ConfigTunnel = {
  locale: 'fr',
  langueBasculable: true,
  formatNombre: fmtNumLocale('fr'),
  estimationGatee: PUBLIC_ESTIMATE_GATED, apercu3dPublic: PUBLIC_3D_PREVIEW,
  annonceGatee: TEXTES_RESIDENTIEL.fr.annonceGatee,
  dateSuitLangue: false,
  statutsSuiventLangue: false,
  optionsBootLocale: {},
};

export const CONFIG_EN: ConfigTunnel = {
  locale: 'en',
  langueBasculable: false,
  formatNombre: fmtNumLocale('en'),
  estimationGatee: PUBLIC_ESTIMATE_GATED, apercu3dPublic: PUBLIC_3D_PREVIEW,
  annonceGatee: TEXTES_RESIDENTIEL.en.annonceGatee,
  dateSuitLangue: false,
  statutsSuiventLangue: false,
  optionsBootLocale: {
    strings: ROOF_TOOL_STRINGS_EN,
    geolocateErrorMsg: 'Location denied — search for your address or drop the pin by hand.',
    panStrings: { panAdded: 'Section added. Draw the next one (double-click to close) or send.', panRemoved: 'Section removed.', maxPans: 'Maximum number of sections reached.' },
  },
};

export const CONFIG_AR: ConfigTunnel = {
  locale: 'ar',
  langueBasculable: true,
  formatNombre: fmtNumLocale('ar'),
  estimationGatee: PUBLIC_ESTIMATE_GATED, apercu3dPublic: PUBLIC_3D_PREVIEW,
  annonceGatee: TEXTES_RESIDENTIEL.ar.annonceGatee,
  // WJ38 — la date du document et les statuts de la carte suivent la langue affichée.
  dateSuitLangue: true,
  statutsSuiventLangue: true,
  optionsBootLocale: {
    strings: ROOF_TOOL_STRINGS_AR,
    // WJ62 — RTL : les contrôles de la carte passent en haut à gauche.
    dir: 'rtl',
    geolocateErrorMsg: 'تم رفض تحديد الموقع — ابحثوا عن عنوانكم أو ضعوا العلامة يدوياً.',
    panStrings: { panAdded: 'تمت إضافة جزء. ارسم الجزء التالي (انقر مرتين للإغلاق) أو أرسل.', panRemoved: 'تمت إزالة الجزء.', maxPans: 'تم بلوغ الحد الأقصى لعدد الأجزاء.' },
  },
};
