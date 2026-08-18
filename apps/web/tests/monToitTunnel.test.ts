// Tunnel /devis/mon-toit — épinglé sur les TROIS variantes de langue (FR / EN /
// AR), qui partagent le même contrat DOM+payload :
//
//  1. LA COUPE DU TUNNEL (décision fondateur, 18/08). Avant l'estimation, on ne
//     pose plus QUE les questions qui NOURRISSENT l'estimation ; les coordonnées
//     viennent en dernier. Tout le reste sort du tunnel — le commercial le
//     complète dans l'ERP. Le contrat /api/capture-lead est INCHANGÉ : une
//     question retirée = une clé simplement ABSENTE du corps, jamais un champ
//     cassé côté validation.
//  2. Plus rien de collecté ne se perd en route : les champs qui étaient gatés
//     sur le profil ACTIF au moment de l'envoi, les jetons de dédoublonnage, et
//     le nombre de panneaux annoncé.
//  3. Repérer son toit est un CHOIX explicite (pointer / dessiner), et le geste
//     « pointer » se termine par une confirmation visuelle.
//
// On lit les SOURCES .astro : ces trois pages ne sont pas montables en unité
// (script Astro inline + import lazy de MapLibre), mais leurs invariants de
// contrat sont textuels et doivent rester vrais sur les trois à la fois — c'est
// exactement le genre de divergence FR/EN/AR qui passe inaperçue autrement.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { COMMERCIAL_QUESTION_WEBHOOK_KEY } from '../src/lib/commercialCategories';
import { validateLead } from '../src/lib/lead';
import { estimateFromBill } from '../src/lib/billEstimate';
import { estimateAgricole } from '../src/lib/estimatorAgricole';
import { monthlyWaterDemand } from '../src/lib/agronomy';

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const LOCALES: Array<[string, string]> = [
  ['FR', '../src/pages/devis/mon-toit.astro'],
  ['EN', '../src/pages/en/devis/mon-toit.astro'],
  ['AR', '../src/pages/ar/devis/mon-toit.astro'],
];

/** Retire les commentaires HTML : un id cité dans un commentaire d'explication
 *  ne doit jamais faire passer (ni échouer) une épingle de contrat. */
const stripHtmlComments = (s: string) => s.replace(/<!--[\s\S]*?-->/g, '');
/** Idem côté script : une clé RETIRÉE est justement expliquée par un commentaire
 *  qui la NOMME — sans ce filtrage, l'épingle « la clé ne part plus » se
 *  déclencherait sur sa propre explication. */
const stripLineComments = (s: string) => s.replace(/^[ \t]*\/\/.*$/gm, '');

/** Texte entre deux bornes (bornes incluses), ou '' si l'ouverture manque. */
function slice(src: string, open: string, close: string): string {
  const a = src.indexOf(open);
  if (a < 0) return '';
  const b = src.indexOf(close, a + open.length);
  return b < 0 ? src.slice(a) : src.slice(a, b + close.length);
}

/** L'objet littéral construit par buildBody() — le corps RÉELLEMENT envoyé. */
const payloadSrc = (src: string) =>
  stripLineComments(slice(src, 'const body: Record<string, unknown> = {', "website_url: val('mt-hp'),"));

/** La ligne du payload qui porte `key:` (une seule par corps). Le `^[ \t]*`
 *  garantit qu'on ne confond jamais une clé avec le SUFFIXE d'une autre
 *  (`raccordement` vs `tensionRaccordement`, qui lui reste envoyé). */
function payloadLine(src: string, key: string): string {
  const m = payloadSrc(src).match(new RegExp(`^[ \\t]*${key}: .*$`, 'm'));
  return m ? m[0] : '';
}

const persistedText = (src: string) =>
  stripLineComments(slice(src, 'const PERSISTED_TEXT_FIELDS = [', '];'));
const persistedChecks = (src: string) =>
  stripLineComments(slice(src, 'const PERSISTED_CHECK_FIELDS = [', '];'));
const contactForm = (src: string) =>
  stripHtmlComments(slice(src, '<form id="mt-form"', '</form>'));

// ———————————————————————————————————————————————————————————————————————————
// Les questions RETIRÉES du tunnel, par profil. `dom` = l'id (ou la classe)
// qui ne doit plus exister ; `key` = la clé de payload qui ne doit plus partir.
// Un `key` à null = la question n'avait pas de clé propre (ou elle est
// mutualisée avec un champ conservé).
const CUT_RESIDENTIEL: Array<{ dom: string; key: string | null }> = [
  { dom: 'id="mt-roof"', key: null }, // roofType reste envoyé, mais DÉRIVÉ
  { dom: 'mt-roof-card', key: null },
  { dom: 'id="mt-raccordement"', key: 'raccordement' },
  { dom: 'id="mt-facture-ete"', key: 'factureEte' },
  { dom: 'id="mt-facture-ete-wrap"', key: null },
  { dom: 'id="mt-distributeur"', key: 'distributeur' },
  { dom: 'id="mt-bill-kwh"', key: 'billKwh' },
  { dom: 'id="mt-roof-age"', key: 'roofAgeYears' },
  { dom: 'id="mt-meter-photo"', key: null },
  { dom: 'mt-future-load', key: 'futureLoads' },
  { dom: 'id="mt-battery-interest"', key: 'batteryInterest' },
  { dom: 'id="mt-occupant-type"', key: 'occupantType' },
  { dom: 'id="mt-project-timing"', key: 'projectTiming' },
  { dom: 'id="mt-financing-intent"', key: 'financingIntent' },
  // Les trois accordéons qui les portaient disparaissent entièrement.
  { dom: 'id="mt-more-size"', key: null },
  { dom: 'id="mt-more-needs"', key: null },
  { dom: 'id="mt-more-financing"', key: null },
];
const CUT_PRO: Array<{ dom: string; key: string | null }> = [
  { dom: 'id="mt-puissance-kva"', key: 'puissanceKva' },
  { dom: 'id="mt-cos-phi"', key: 'cosPhiConnu' },
  { dom: 'id="mt-weekend"', key: 'weekend' },
  { dom: 'id="mt-pro-context"', key: null },
  { dom: 'mt-generator', key: 'hasGenerator' },
  { dom: 'id="mt-groupe-kva"', key: 'groupeKva' },
  { dom: 'id="mt-diesel-dh"', key: 'dieselDhMois' },
  { dom: 'id="mt-facility-type"', key: 'facilityType' },
  { dom: 'id="mt-site-count"', key: 'siteCount' },
  // Questions PAR CATÉGORIE commerciale : purement informatives (estimatePro ne
  // lit que la catégorie elle-même), donc sorties du tunnel avec leur lecteur.
  { dom: 'mt-cc-questions', key: null },
];
const CUT_AGRICOLE: Array<{ dom: string; key: string | null }> = [
  { dom: 'mt-irrigation', key: 'irrigation' },
  { dom: 'id="mt-agri-pompe-acc"', key: null },
  { dom: 'id="mt-pompe-actuelle"', key: 'pompeActuelle' },
  { dom: 'id="mt-pompe-cv"', key: 'pompeCvActuelle' },
];
const ALL_CUT = [...CUT_RESIDENTIEL, ...CUT_PRO, ...CUT_AGRICOLE];

/** Ce qui RESTE avant l'estimation : uniquement ce que les moteurs lisent. */
const KEPT_DOM = [
  // Résidentiel : facture exacte OU tranche, + ombrage (1 clic, il dérate).
  'id="mt-facture-hiver"', 'id="mt-bill"', 'mt-ombrage',
  // Industriel / commercial : facture, BT/MT, activité, équipes, surface, catégorie.
  'id="mt-pro-bill"', 'mt-pro-unit', 'mt-tension', 'mt-activity', 'mt-equipes',
  'id="mt-surface-m2"', 'mt-surface-type', 'mt-commercial-cat', 'id="mt-cc-bill"',
  // Agricole : le bloc de dimensionnement complet + la dépense carburant.
  'mt-culture-card', 'mt-region-card', 'id="mt-surface-ha"', 'mt-water-source',
  'id="mt-profondeur"', 'id="mt-hmt"', 'id="mt-water-need"', 'id="mt-heures-pompage"',
  'id="mt-fuel-spend"',
  // Contact, en DERNIER.
  'id="mt-name"', 'id="mt-phone"', 'id="mt-city"', 'id="mt-email"', 'id="mt-consent"',
  'mt-visit-part', 'mt-visit-week',
];

describe('Chantier 1 — la coupe du tunnel (fondateur, 18/08)', () => {
  for (const [lang, rel] of LOCALES) {
    const src = read(rel);
    // Chaque retrait laisse derrière lui un commentaire qui NOMME la question
    // retirée (pour l'archéologie) : on retire donc les commentaires HTML *et*
    // les commentaires de ligne du script avant toute épingle d'absence, sinon
    // l'explication du retrait ferait échouer la preuve du retrait.
    const dom = stripLineComments(stripHtmlComments(src));

    it(`${lang} — les questions coupées ont quitté le DOM`, () => {
      for (const { dom: id } of ALL_CUT) expect(dom, id).not.toContain(id);
    });

    it(`${lang} — leurs clés ne partent plus dans le corps du lead`, () => {
      for (const { key } of ALL_CUT) {
        if (key) expect(payloadLine(src, key), key).toBe('');
      }
      // `eteDifferente` et `hasMeterPhoto` étaient des raccourcis d'objet
      // (`eteDifferente,`) : ils n'ont pas de ligne `clé: valeur` à chercher.
      expect(payloadSrc(src)).not.toContain('eteDifferente');
      expect(payloadSrc(src)).not.toContain('hasMeterPhoto');
      // …et la surface commerciale par catégorie n'est plus lue du tout.
      expect(payloadSrc(src)).not.toContain('readCommercialAnswers');
    });

    it(`${lang} — le brouillon ne les persiste plus`, () => {
      const text = persistedText(src);
      for (const id of [
        'mt-facture-ete', 'mt-roof', 'mt-raccordement', 'mt-distributeur', 'mt-bill-kwh',
        'mt-roof-age', 'mt-occupant-type', 'mt-project-timing', 'mt-financing-intent',
        'mt-facility-type', 'mt-site-count', 'mt-puissance-kva', 'mt-cos-phi',
        'mt-groupe-kva', 'mt-diesel-dh', 'mt-pompe-actuelle', 'mt-pompe-cv',
      ]) {
        expect(text, id).not.toContain(`'${id}'`);
      }
      const checks = persistedChecks(src);
      expect(checks).not.toContain('mt-ete-differente');
      expect(checks).not.toContain('mt-battery-interest');
      expect(checks).not.toContain('mt-weekend');
      // Ce qui reste EST toujours persisté (un rafraîchissement ne perd rien).
      expect(text).toContain("'mt-facture-hiver'");
      expect(text).toContain("'mt-raison-sociale'");
      expect(text).toContain("'mt-fuel-spend'");
    });

    it(`${lang} — tout ce qui NOURRIT l'estimation est toujours posé`, () => {
      for (const id of KEPT_DOM) expect(dom, id).toContain(id);
    });

    it(`${lang} — l'ombrage a quitté l'accordéon pour la carte facture`, () => {
      // Plus AUCUN accordéon « affiner » : l'ombrage est visible d'emblée,
      // juste sous la facture, parce qu'il change vraiment le chiffre.
      expect(dom).not.toContain('<details id="mt-more');
      const card = slice(dom, 'id="mt-facture-hiver"', '</fieldset>');
      expect(card).toContain('mt-ombrage');
      expect(payloadLine(src, 'ombrage')).not.toBe('');
    });

    it(`${lang} — la raison sociale est passée sur l'écran CONTACT`, () => {
      const form = contactForm(src);
      expect(form).toContain('id="mt-raison-sociale-wrap"');
      expect(form).toContain('id="mt-raison-sociale"');
      expect(form).toContain('name="raisonSociale"');
      // …et elle part toujours au webhook, id/name inchangés.
      expect(payloadLine(src, 'raisonSociale')).not.toBe('');
      // Affichée aux seuls profils professionnels (un particulier n'en a pas).
      expect(src).toContain('function syncRaisonSociale()');
      expect(src).toContain('wrap.hidden = !isProMode(mode)');
    });

    it(`${lang} — roofType est DÉRIVÉ, plus jamais demandé`, () => {
      // validateLead EXIGE roofType : la question part, la valeur reste — et
      // reste honnête ('autre', jamais une toiture précise inventée).
      const fn = stripLineComments(slice(src, 'function resolveRoofType()', '\n  }'));
      expect(fn).toContain("return 'autre';");
      expect(fn).not.toContain("val('mt-roof')");
      expect(payloadLine(src, 'roofType')).toContain('resolveRoofType()');
    });

    it(`${lang} — l'étape 2 n'exige plus qu'une facture (résidentiel)`, () => {
      const fn = stripLineComments(slice(src, 'function validateStep1()', '\n  }\n'));
      expect(fn).not.toContain("val('mt-roof')");
      expect(fn).not.toContain('mt-puissance-kva');
      expect(fn).not.toContain('mt-pompe-cv');
      expect(fn).toContain("val('mt-bill')");
    });
  }

  // ——— Le CONTRAT SERVEUR est intact : retirer une question du site ne doit
  // RIEN casser côté validation — d'autres sources alimentent encore ces champs.
  const base = {
    fullName: 'Karim Benali',
    phone: '06 12 34 56 78',
    city: 'Casablanca',
    roofType: 'villa',
    billRange: '1500-3000',
    consent: true,
  };

  it('validateLead accepte TOUJOURS les champs retirés du tunnel', () => {
    const r = validateLead({
      ...base,
      financingIntent: 'comptant',
      occupantType: 'decideur',
      projectTiming: 'maintenant',
      billKwh: 700,
      roofAgeYears: 8,
      batteryInterest: true,
      raccordement: 'triphase',
      eteDifferente: true,
      factureEte: 2500,
      puissanceKva: 400,
      cosPhiConnu: 0.92,
      irrigation: 'goutte',
      pompeActuelle: 'diesel',
      pompeCvActuelle: 7.5,
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.financingIntent).toBe('comptant');
    expect(r.lead.occupantType).toBe('decideur');
    expect(r.lead.billKwh).toBe(700);
    expect(r.lead.pompeActuelle).toBe('diesel');
  });

  it("un lead SANS aucun des champs coupés reste parfaitement valide", () => {
    // Exactement ce que le tunnel envoie désormais côté résidentiel : facture,
    // ombrage, coordonnées, consentement — et roofType dérivé ('autre').
    const r = validateLead({
      fullName: 'Karim Benali',
      phone: '06 12 34 56 78',
      city: 'Casablanca',
      roofType: 'autre',
      billRange: '1500-3000',
      ombrage: 'partiel',
      consent: true,
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.roofType).toBe('autre');
    expect(r.lead.ombrage).toBe('partiel');
  });
});

// ———————————————————————————————————————————————————————————————————————————
describe("Chantier 1 bis — l'estimation tient debout sans les questions coupées", () => {
  it('RÉSIDENTIEL : la FACTURE SEULE suffit (plus de kWh/mois saisi)', () => {
    // La conso exacte en kWh a quitté le tunnel : estimateFromBill retombe sur
    // sa propre conversion MAD → kWh, exactement comme pour tout visiteur qui
    // laissait ce champ vide — donc aucun trou dans le chiffre affiché.
    const est = estimateFromBill(1200);
    expect(est).not.toBeNull();
    if (!est) return;
    expect(est.kwc).toBeGreaterThan(0);
    expect(est.productionKwhYr).toBeGreaterThan(0);
    expect(est.savingsMonthlyLow).toBeGreaterThan(0);
  });

  it("RÉSIDENTIEL : l'ombrage, lui, agit toujours sur le calcul", () => {
    const shaded = estimateFromBill(1200, { ombrage: 'important' });
    expect(shaded).not.toBeNull();
    if (!shaded) return;
    expect(shaded.kwc).toBeGreaterThan(0);
    expect(shaded.productionKwhYr).toBeGreaterThan(0);
  });

  for (const [lang, rel] of LOCALES) {
    const src = read(rel);
    it(`${lang} — le tunnel appelle bien le moteur SANS conso kWh`, () => {
      expect(stripLineComments(src))
        .toContain('estimateFromBill(bill, { lat, city, ombrage: ombrage || undefined })');
    });
    it(`${lang} — le moteur eau est appelé SANS méthode d'irrigation`, () => {
      expect(stripLineComments(src))
        .toContain('monthlyWaterDemand(crop, regionAgricole, surfaceHa)');
    });
  }

  it("AGRICOLE : un dossier complet passe toujours (le bloc conservé suffit)", () => {
    const r = estimateAgricole({
      hmtM: 60,
      debitM3h: 10,
      heuresPompage: 7,
      pompeType: 'immergee',
      fuelSpendMadMonth: 3000,
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.pompeCv).toBeGreaterThan(0);
    expect(r.champKwc).toBeGreaterThan(0);
    expect(r.m3Jour).toBeGreaterThan(0);
    // La dépense carburant — SEUL rescapé de l'accordéon « pompe actuelle » —
    // continue de produire l'économie annoncée.
    expect(r.fuelSavingMadYearLow ?? 0).toBeGreaterThan(0);
  });

  it("AGRICOLE : le besoin en eau se calcule sans la question d'irrigation", () => {
    const md = monthlyWaterDemand('agrumes', 'souss-massa', 5);
    expect(md.peak_m3_farm_day).toBeGreaterThan(0);
  });
});

// ———————————————————————————————————————————————————————————————————————————
describe('Chantier 2 — tout ce qui est collecté atteint bien l’ERP', () => {
  const base = {
    fullName: 'Karim Benali',
    phone: '06 12 34 56 78',
    city: 'Casablanca',
    roofType: 'villa',
    billRange: '1500-3000',
    consent: true,
  };

  it('la surface des catégories commerciales garde sa destination webhook', () => {
    // Le mapping reste dans lib/commercialCategories (le backend s'en sert) —
    // seul le TUNNEL a cessé de poser ces questions.
    expect(COMMERCIAL_QUESTION_WEBHOOK_KEY.surface_m2).toBe('surfaceM2');
    const r = validateLead({ ...base, surfaceM2: 240 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.surfaceM2).toBe(240);
  });

  it('les jetons de dédoublonnage traversent la validation (format crypto.randomUUID)', () => {
    // `crypto.randomUUID()` produit exactement la forme que valide lib/lead.ts
    // (^[A-Za-z0-9_-]{8,64}$) : on le prouve avec un vrai UUID généré ici.
    const idempotencyKey = crypto.randomUUID();
    const eventId = crypto.randomUUID();
    expect(idempotencyKey).not.toBe(eventId); // deux systèmes, deux jetons
    const r = validateLead({ ...base, idempotencyKey, eventId });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.idempotencyKey).toBe(idempotencyKey);
    expect(r.lead.eventId).toBe(eventId);
  });

  it("le nombre de panneaux annoncé entre dans la liste blanche d'estimateShown", () => {
    const r = validateLead({ ...base, estimateShown: { kwc: 6.4, nbPanneaux: 9 } });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.estimateShown?.nbPanneaux).toBe(9);
    // …et la liste reste une VRAIE liste blanche : rien d'autre ne passe.
    const r2 = validateLead({ ...base, estimateShown: { kwc: 6.4, margeInterne: 4200 } });
    expect(r2.ok).toBe(true);
    if (!r2.ok) return;
    expect(r2.lead.estimateShown).not.toHaveProperty('margeInterne');
  });

  for (const [lang, rel] of LOCALES) {
    const src = read(rel);

    it(`${lang} — les jetons de dédoublonnage sont bien ENVOYÉS et persistés`, () => {
      expect(payloadSrc(src)).toContain('idempotencyKey:');
      expect(payloadSrc(src)).toContain('eventId:');
      // …et repris du brouillon, sinon un rafraîchissement fabriquerait un
      // second jeton pour la même saisie — le doublon qu'ils doivent empêcher.
      expect(src).toContain('idempotencyKey: dedupIdempotencyKey');
      expect(src).toContain('eventId: dedupEventId');
      expect(src).toContain("savedWizard?.idempotencyKey ||");
      expect(src).toContain("savedWizard?.eventId ||");
    });

    // Un visiteur qui a décrit son site industriel puis rebasculé sur un autre
    // profil ne doit plus perdre ses réponses : ce qui est SAISI part, point.
    // (La liste a maigri avec la coupe du 18/08 — weekend / cos φ / groupe
    // électrogène / diesel ne sont tout simplement plus demandés.)
    const UNGATED = ['equipes', 'surfaceToitureM2', 'ombriere', 'terrain', 'heuresPompage'];
    for (const key of UNGATED) {
      it(`${lang} — ${key} ne dépend plus du profil actif au moment de l'envoi`, () => {
        const line = payloadLine(src, key);
        expect(line.length).toBeGreaterThan(0);
        expect(line).not.toContain("mode === 'industriel'");
        expect(line).not.toContain("mode === 'professionnel'");
        expect(line).not.toContain("mode === 'agricole'");
        expect(line).not.toContain('isProMode(mode)');
      });
    }

    it(`${lang} — mais le gate SÉMANTIQUE sur le type de surface est conservé`, () => {
      // surface_toiture_m2 = surface de TOIT au sens strict : une ombrière ou un
      // terrain ne doit jamais être décrit comme une toiture.
      expect(payloadLine(src, 'surfaceToitureM2')).toContain("surfaceType === 'bac_acier'");
      expect(payloadLine(src, 'ombriere')).toContain("surfaceType === 'ombriere'");
      expect(payloadLine(src, 'terrain')).toContain("surfaceType === 'terrain'");
    });
  }
});

// ———————————————————————————————————————————————————————————————————————————
describe('Chantier 3 — pointer OU dessiner, avec confirmation visuelle', () => {
  for (const [lang, rel] of LOCALES) {
    const src = read(rel);
    const dom = stripHtmlComments(src);

    it(`${lang} — les deux gestes sont proposés explicitement`, () => {
      expect(dom).toContain('id="mt-roof-mode-point"');
      expect(dom).toContain('id="mt-roof-mode-draw"');
      expect(dom).toContain('data-value="point"');
      expect(dom).toContain('data-value="draw"');
      // Repères visuels demandés (épingle/crayon) présents dans les deux libellés.
      expect(dom).toContain('📍');
      expect(dom).toContain('✏️');
    });

    it(`${lang} — la confirmation « C'est bien votre toit ? » existe avec sa sortie « ajuster »`, () => {
      expect(dom).toContain('id="mt-pin-confirm"');
      expect(dom).toContain('id="mt-pin-confirm-address"');
      expect(dom).toContain('id="mt-pin-confirm-yes"');
      expect(dom).toContain('id="mt-pin-confirm-adjust"');
    });

    it(`${lang} — le geste choisi est bien transmis à la carte`, () => {
      // La carte ne peut pas deviner le choix : il lui est passé en FONCTION
      // (relue à chaque clic — le visiteur peut changer d'avis en cours de route).
      expect(src).toContain('roofInputMode: () => roofInputMode');
      // …et le repère confirmé se resynchronise sur chaque notification carte,
      // car l'adresse arrive APRÈS le repère (géocodage inverse asynchrone).
      expect(src).toContain('setPinConfirmAddress(s.address)');
      expect(src).toContain('syncPinConfirm()');
    });
  }

  it('FR et AR portent les traductions arabes des nouveaux libellés (data-i18n)', () => {
    for (const rel of ['../src/pages/devis/mon-toit.astro', '../src/pages/ar/devis/mon-toit.astro']) {
      const src = read(rel);
      expect(src).toContain('data-ar="📍 تحديد سطحي بنقطة"');
      expect(src).toContain('data-ar="✏️ رسم سطحي"');
      expect(src).toContain('data-ar="هل هذا هو سطحكم؟"');
    }
  });

  it('EN porte ses libellés en anglais (cette route n’a pas de bascule data-i18n)', () => {
    const src = read('../src/pages/en/devis/mon-toit.astro');
    expect(src).toContain('📍 Point at my roof');
    expect(src).toContain('✏️ Draw my roof');
    expect(src).toContain('Is this your roof?');
  });

  it("l'option roofInputMode est bien exposée par le boot capture", () => {
    const boot = read('../src/scripts/roofPro11/captureBoot.ts');
    expect(boot).toContain('roofInputMode?: () =>');
    // Sans l'option, le flux historique reste intact (comportement par défaut) :
    // les deux branches sont gardées par `opts.roofInputMode?.()`.
    expect(boot).toContain("opts.roofInputMode?.() === 'draw'");
    expect(boot).toContain("opts.roofInputMode?.() === 'point'");
  });
});
