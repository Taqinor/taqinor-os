// LANE Q-B — Logique PURE du questionnaire client public.
// Aucune dépendance DOM ni réseau : parsing de la réponse GET, construction
// du corps POST par section, sanitisation des champs, photos.
import { describe, expect, it } from 'vitest';
import {
  ECRANS,
  QUESTIONNAIRE_SECTIONS,
  buildQuestionnairePostBody,
  buildSectionReponses,
  champDemande,
  ecransActifs,
  initialEcranIndex,
  initialSectionIndex,
  isEmptyPostBody,
  isInternalPreview,
  isPhotoSection,
  isQuestionnaireSectionId,
  isValidPhotoDataUrl,
  parseQuestionnaireGet,
  parseQuestionnairePostResponse,
  progressLabel,
  questionnaireEndpoint,
  type QuestionnaireGetResponse,
} from '../src/lib/questionnaire';

// ── Verrous de source (contrat backend, ne changent jamais sans le savoir) ──
describe('verrous de source — contrat backend', () => {
  it('QUESTIONNAIRE_SECTIONS = exactement les 12 clés du contrat, dans cet ordre', () => {
    // Ordre = crm.QuestionnaireLien.SECTIONS_CLES (recherche 25/08/2026) :
    // engagement croissant, `contact` TOUJOURS en dernier. AGW408 — AGR411 y a
    // ajouté `pompage`, `photo_pompe` et `photo_forage` (segment agricole).
    expect(QUESTIONNAIRE_SECTIONS).toEqual([
      'occupation',
      'equipements',
      'energie',
      'pompage',
      'toiture',
      'gps',
      'photo_facture',
      'photo_compteur',
      'photo_tableau',
      'photo_pompe',
      'photo_forage',
      'contact',
    ]);
  });

  it('`contact` est la DERNIÈRE section — données personnelles en dernier', () => {
    expect(QUESTIONNAIRE_SECTIONS[QUESTIONNAIRE_SECTIONS.length - 1]).toBe('contact');
  });

  it("questionnaireEndpoint pointe le chemin exact du contrat", () => {
    expect(questionnaireEndpoint('https://api.taqinor.ma', 'abc123')).toBe(
      'https://api.taqinor.ma/api/django/crm/public/questionnaire/abc123/',
    );
  });

  it('questionnaireEndpoint retombe sur https://api.taqinor.ma sans base fournie', () => {
    expect(questionnaireEndpoint('', 'tok')).toBe('https://api.taqinor.ma/api/django/crm/public/questionnaire/tok/');
  });

  it('questionnaireEndpoint encode le token (segment de chemin)', () => {
    expect(questionnaireEndpoint('https://api.taqinor.ma', 'a/b c')).toBe(
      'https://api.taqinor.ma/api/django/crm/public/questionnaire/a%2Fb%20c/',
    );
  });

  it('isPhotoSection distingue les 5 sections photo des autres', () => {
    expect(isPhotoSection('photo_facture')).toBe(true);
    expect(isPhotoSection('photo_compteur')).toBe(true);
    expect(isPhotoSection('photo_tableau')).toBe(true);
    expect(isPhotoSection('photo_pompe')).toBe(true);
    expect(isPhotoSection('photo_forage')).toBe(true);
    expect(isPhotoSection('pompage')).toBe(false);
    expect(isPhotoSection('contact')).toBe(false);
    expect(isPhotoSection('gps')).toBe(false);
    expect(isPhotoSection('energie')).toBe(false);
    expect(isPhotoSection('toiture')).toBe(false);
    expect(isPhotoSection('occupation')).toBe(false);
    expect(isPhotoSection('equipements')).toBe(false);
  });
});

// ── parseQuestionnaireGet ────────────────────────────────────────────────
describe('parseQuestionnaireGet', () => {
  const validBody = {
    entreprise: 'Taqinor',
    prenom: 'Yassine',
    sections: ['contact', 'gps', 'energie'],
    prefill: { ville: 'Casablanca', email: null },
    repondu: { contact: true },
  };

  it('parse une réponse valide', () => {
    const data = parseQuestionnaireGet(validBody);
    expect(data).not.toBeNull();
    expect(data!.entreprise).toBe('Taqinor');
    expect(data!.prenom).toBe('Yassine');
    expect(data!.sections).toEqual(['contact', 'gps', 'energie']);
    expect(data!.prefill).toEqual({ ville: 'Casablanca', email: null });
    expect(data!.repondu).toEqual({ contact: true });
    expect(data!.interne).toBe(false);
  });

  it('ADDENDUM — interne:true est repris tel quel', () => {
    const data = parseQuestionnaireGet({ ...validBody, interne: true });
    expect(data!.interne).toBe(true);
  });

  it('interne absent ⇒ false (jamais undefined, jamais deviné vrai)', () => {
    const data = parseQuestionnaireGet(validBody);
    expect(data!.interne).toBe(false);
  });

  it('interne non-booléen est ignoré (⇒ false)', () => {
    const data = parseQuestionnaireGet({ ...validBody, interne: 'oui' });
    expect(data!.interne).toBe(false);
  });

  it('filtre les sections inconnues sans planter', () => {
    const data = parseQuestionnaireGet({ ...validBody, sections: ['contact', 'inconnue', 'gps'] });
    expect(data!.sections).toEqual(['contact', 'gps']);
  });

  it('repondu ne garde que les clés de sections réellement actives', () => {
    const data = parseQuestionnaireGet({ ...validBody, repondu: { contact: true, toiture: true } });
    // toiture absent de `sections` de ce fixture ⇒ écarté
    expect(data!.repondu).toEqual({ contact: true });
  });

  it('sections vide/absente ⇒ null (rien d’exploitable)', () => {
    expect(parseQuestionnaireGet({ ...validBody, sections: [] })).toBeNull();
    expect(parseQuestionnaireGet({ ...validBody, sections: undefined })).toBeNull();
  });

  it('corps non-objet / null / tableau ⇒ null', () => {
    expect(parseQuestionnaireGet(null)).toBeNull();
    expect(parseQuestionnaireGet('nope')).toBeNull();
    expect(parseQuestionnaireGet([1, 2, 3])).toBeNull();
  });

  it('prefill/repondu malformés retombent sur un objet vide (jamais un throw)', () => {
    const data = parseQuestionnaireGet({ ...validBody, prefill: 'nope', repondu: 42 });
    expect(data!.prefill).toEqual({});
    expect(data!.repondu).toEqual({});
  });

  it('`champs` est repris tel quel, filtré aux sections actives', () => {
    const data = parseQuestionnaireGet({
      ...validBody,
      champs: { contact: ['email', 'ville'], toiture: ['type_toiture'] },
    });
    // 'toiture' n'est pas dans `sections` de ce fixture ⇒ écarté.
    expect(data!.champs).toEqual({ contact: ['email', 'ville'] });
  });

  it('`champs` absent ⇒ carte vide, donc AUCUNE restriction (repli sûr)', () => {
    const data = parseQuestionnaireGet(validBody);
    expect(data!.champs).toEqual({});
    expect(champDemande(data!.champs, 'contact', 'adresse')).toBe(true);
  });

  it('`champs` malformé n’éteint jamais un écran entier', () => {
    const data = parseQuestionnaireGet({ ...validBody, champs: { contact: 'nope' } });
    expect(data!.champs).toEqual({});
    expect(champDemande(data!.champs, 'contact', 'adresse')).toBe(true);
  });
});

// ── champDemande — « on ne redemande JAMAIS » au grain du CHAMP ──────────
describe('champDemande', () => {
  it("l'adresse disparaît quand le serveur ne la liste plus (GPS déjà donné)", () => {
    const champs = { contact: ['email', 'ville'] };
    expect(champDemande(champs, 'contact', 'adresse')).toBe(false);
    expect(champDemande(champs, 'contact', 'email')).toBe(true);
    expect(champDemande(champs, 'contact', 'ville')).toBe(true);
  });

  it('une section non listée n’est pas restreinte — mieux une question de trop qu’un champ perdu', () => {
    expect(champDemande({}, 'toiture', 'roof_age')).toBe(true);
  });

  it('une liste VIDE explicite cache bien tout (le serveur l’a décidé)', () => {
    expect(champDemande({ contact: [] }, 'contact', 'email')).toBe(false);
  });

  it('isQuestionnaireSectionId rejette les valeurs hors vocabulaire', () => {
    expect(isQuestionnaireSectionId('contact')).toBe(true);
    expect(isQuestionnaireSectionId('n_importe_quoi')).toBe(false);
    expect(isQuestionnaireSectionId(42)).toBe(false);
  });
});

// ── initialSectionIndex / progressLabel ──────────────────────────────────
describe('initialSectionIndex', () => {
  const sections = QUESTIONNAIRE_SECTIONS as unknown as (typeof QUESTIONNAIRE_SECTIONS)[number][];

  it('reprend à la première section NON répondue', () => {
    expect(initialSectionIndex(sections, { occupation: true, equipements: true })).toBe(2); // 'energie'
  });

  it('aucune section répondue ⇒ index 0', () => {
    expect(initialSectionIndex(sections, {})).toBe(0);
  });

  it('toutes répondues ⇒ la dernière (relisible, jamais hors bornes)', () => {
    const all: Partial<Record<(typeof sections)[number], boolean>> = {};
    for (const s of sections) all[s] = true;
    expect(initialSectionIndex(sections, all)).toBe(sections.length - 1);
  });

  it('liste vide ⇒ 0 (garde-fou)', () => {
    expect(initialSectionIndex([], {})).toBe(0);
  });
});

// ── ÉCRANS — « the number of pages those questions should be in » ────────
describe('ECRANS / ecransActifs', () => {
  const toutes = QUESTIONNAIRE_SECTIONS as unknown as (typeof QUESTIONNAIRE_SECTIONS)[number][];

  it('les 12 sections tiennent sur 7 écrans au maximum, jamais 12', () => {
    expect(ECRANS).toHaveLength(7);
    expect(ecransActifs(toutes)).toHaveLength(7);
  });

  it('chaque section est couverte par exactement UN écran', () => {
    const vues = ECRANS.flatMap((e) => e.sections);
    expect([...vues].sort()).toEqual([...toutes].sort());
    expect(new Set(vues).size).toBe(vues.length);
  });

  it('INVARIANT — les sections d’un écran sont CONSÉCUTIVES dans l’ordre servi', () => {
    for (const ecran of ECRANS) {
      const positions = ecran.sections.map((s) => toutes.indexOf(s));
      expect(positions.every((p) => p >= 0)).toBe(true);
      for (let i = 1; i < positions.length; i += 1) {
        expect(positions[i]).toBe(positions[i - 1] + 1);
      }
    }
  });

  it('les trois photos tiennent sur UN écran, toiture+GPS sur un autre', () => {
    const photos = ECRANS.find((e) => e.id === 'photos');
    expect(photos!.sections).toEqual(['photo_facture', 'photo_compteur', 'photo_tableau', 'photo_pompe', 'photo_forage']);
    expect(ECRANS.find((e) => e.id === 'toit')!.sections).toEqual(['toiture', 'gps']);
  });

  it('les coordonnées sont le DERNIER écran', () => {
    expect(ECRANS[ECRANS.length - 1].id).toBe('coordonnees');
  });

  it('un écran n’existe que s’il porte une section servie', () => {
    const ecrans = ecransActifs(['energie', 'contact']);
    expect(ecrans.map((e) => e.id)).toEqual(['electricite', 'coordonnees']);
    expect(ecrans.map((e) => e.actives)).toEqual([['energie'], ['contact']]);
  });

  it('un écran ne porte QUE les sections réellement servies', () => {
    const ecrans = ecransActifs(['photo_compteur', 'contact']);
    expect(ecrans[0].id).toBe('photos');
    expect(ecrans[0].actives).toEqual(['photo_compteur']);
  });

  it('le cas du fondateur : GPS et ville déjà connus ⇒ 3 écrans, aucun pour l’adresse', () => {
    // Le serveur ne sert plus `gps` (renseigné) ; `contact` ne porte plus que
    // l’e-mail (l’adresse est couverte par le GPS, la ville est connue).
    const ecrans = ecransActifs(['occupation', 'equipements', 'contact']);
    expect(ecrans.map((e) => e.id)).toEqual(['presence', 'equipements', 'coordonnees']);
    expect(champDemande({ contact: ['email'] }, 'contact', 'adresse')).toBe(false);
  });

  it('une section inconnue des ECRANS obtient son propre écran plutôt que de disparaître', () => {
    const ecrans = ecransActifs(['contact', 'inconnue' as never]);
    expect(ecrans).toHaveLength(2);
    expect(ecrans[1].actives).toEqual(['inconnue']);
  });

  it('aucune section ⇒ aucun écran (jamais un throw)', () => {
    expect(ecransActifs([])).toEqual([]);
  });
});

describe('initialEcranIndex', () => {
  const ecrans = ecransActifs(
    QUESTIONNAIRE_SECTIONS as unknown as (typeof QUESTIONNAIRE_SECTIONS)[number][],
  );

  it('reprend au premier écran dont une section reste sans réponse', () => {
    expect(initialEcranIndex(ecrans, { occupation: true, equipements: true })).toBe(2);
  });

  it('un écran multi-sections reste ouvert tant qu’UNE de ses sections manque', () => {
    const repondu: Record<string, boolean> = {};
    for (const s of QUESTIONNAIRE_SECTIONS) repondu[s] = true;
    repondu.photo_tableau = false;
    expect(ecrans[initialEcranIndex(ecrans, repondu)].id).toBe('photos');
  });

  it('tout répondu ⇒ le dernier écran (relisible, jamais hors bornes)', () => {
    const repondu: Record<string, boolean> = {};
    for (const s of QUESTIONNAIRE_SECTIONS) repondu[s] = true;
    expect(initialEcranIndex(ecrans, repondu)).toBe(ecrans.length - 1);
  });

  it('aucun écran ⇒ 0 (garde-fou)', () => {
    expect(initialEcranIndex([], {})).toBe(0);
  });
});

describe('progressLabel', () => {
  it('formate "Étape N sur TOTAL" (index 0-based)', () => {
    expect(progressLabel(0, 9)).toBe('Étape 1 sur 9');
    expect(progressLabel(8, 9)).toBe('Étape 9 sur 9');
  });
});

// ── buildSectionReponses — un cas par section ────────────────────────────
describe('buildSectionReponses', () => {
  it('contact : email/adresse/ville nettoyés, champs vides omis', () => {
    expect(buildSectionReponses('contact', { email: 'client@exemple.com', adresse: '  12 rue X  ', ville: 'Rabat' })).toEqual({
      email: 'client@exemple.com',
      adresse: '12 rue X',
      ville: 'Rabat',
    });
    expect(buildSectionReponses('contact', { email: 'pas-un-email', adresse: '', ville: '' })).toEqual({});
  });

  it('gps : lat/lng acceptés seulement dans les bornes Maroc', () => {
    expect(buildSectionReponses('gps', { gps_lat: 33.57, gps_lng: -7.59 })).toEqual({
      gps_lat: 33.57,
      gps_lng: -7.59,
    });
    // Paris — hors bornes Maroc, écarté silencieusement
    expect(buildSectionReponses('gps', { gps_lat: 48.85, gps_lng: 2.35 })).toEqual({});
  });

  it('énergie (QJR632) : conso_mensuelle_kwh gardée, nettoyée comme facture_hiver', () => {
    expect(buildSectionReponses('energie', { conso_mensuelle_kwh: '1200' })).toEqual({ conso_mensuelle_kwh: 1200 });
    expect(buildSectionReponses('energie', { conso_mensuelle_kwh: '1200.5' })).toEqual({ conso_mensuelle_kwh: 1200.5 });
    expect(buildSectionReponses('energie', { conso_mensuelle_kwh: '-3' })).toEqual({});
    expect(buildSectionReponses('energie', { conso_mensuelle_kwh: '' })).toEqual({});
  });

  it("énergie : facture_ete seulement si ete_differente='oui', raccordement en liste fermée", () => {
    expect(
      buildSectionReponses('energie', {
        facture_hiver: '850',
        ete_differente: 'oui',
        facture_ete: '1400',
        raccordement: 'mono',
      }),
    ).toEqual({ facture_hiver: 850, ete_differente: true, facture_ete: 1400, raccordement: 'mono' });

    // ete_differente='non' ⇒ facture_ete jamais repris même si fourni
    expect(
      buildSectionReponses('energie', { facture_hiver: '850', ete_differente: 'non', facture_ete: '1400' }),
    ).toEqual({ facture_hiver: 850, ete_differente: false });

    // raccordement inconnu ⇒ écarté
    expect(buildSectionReponses('energie', { raccordement: 'satellite' })).toEqual({});
  });

  it('sections photo_* ne produisent jamais de reponses', () => {
    expect(buildSectionReponses('photo_facture', { anything: 'x' })).toEqual({});
    expect(buildSectionReponses('photo_compteur', {})).toEqual({});
    expect(buildSectionReponses('photo_tableau', {})).toEqual({});
  });

  it('toiture : « je ne sais pas » omet la surface, jamais un 0 fabriqué', () => {
    expect(
      buildSectionReponses('toiture', {
        type_toiture: 'villa',
        surface_toiture_m2: '120',
        surface_inconnue: true,
        roof_age: '8',
        ownership: 'proprietaire',
      }),
    ).toEqual({ type_toiture: 'villa', roof_age: 8, ownership: 'proprietaire' });

    expect(buildSectionReponses('toiture', { surface_toiture_m2: '120', surface_inconnue: false })).toEqual({
      surface_toiture_m2: 120,
    });
  });

  it('occupation : occupation_jour restreint à present/absent/partiel', () => {
    expect(buildSectionReponses('occupation', { occupation_jour: 'present' })).toEqual({ occupation_jour: 'present' });
    expect(buildSectionReponses('occupation', { occupation_jour: 'ailleurs' })).toEqual({});
  });

  it('équipements : booléens explicites oui/non, jamais pré-remplis (undefined omis)', () => {
    expect(
      buildSectionReponses('equipements', {
        equip_piscine: 'oui',
        equip_voiture_electrique: 'non',
        equip_clim: undefined,
        equip_chauffe_eau_electrique: 'non',
      }),
    ).toEqual({ equip_piscine: true, equip_voiture_electrique: false, equip_chauffe_eau_electrique: false });
  });

  it('équipements : sous-champs seulement quand la case correspondante = oui', () => {
    expect(
      buildSectionReponses('equipements', {
        equip_piscine: 'oui',
        equip_piscine_pompe_kw: '0.75',
        equip_voiture_electrique: 'non',
        equip_ve_km_semaine: '200', // ignoré : voiture = non
      }),
    ).toEqual({ equip_piscine: true, equip_piscine_pompe_kw: 0.75, equip_voiture_electrique: false });

    expect(
      buildSectionReponses('equipements', { equip_clim: 'oui', equip_clim_pieces: '3.9' }),
    ).toEqual({ equip_clim: true, equip_clim_pieces: 4 });
  });
});

// ── Photos ────────────────────────────────────────────────────────────────
describe('isValidPhotoDataUrl', () => {
  it('accepte un data URL image bien formé et raisonnable', () => {
    expect(isValidPhotoDataUrl('data:image/jpeg;base64,' + 'A'.repeat(1000))).toBe(true);
  });

  it("rejette un type non-image, une chaîne vide, une valeur non-string", () => {
    expect(isValidPhotoDataUrl('data:application/pdf;base64,AAAA')).toBe(false);
    expect(isValidPhotoDataUrl('')).toBe(false);
    expect(isValidPhotoDataUrl(undefined)).toBe(false);
    expect(isValidPhotoDataUrl(null)).toBe(false);
    expect(isValidPhotoDataUrl(1234)).toBe(false);
  });

  it('rejette un data URL sans virgule / sans contenu base64', () => {
    expect(isValidPhotoDataUrl('data:image/jpeg;base64')).toBe(false);
    expect(isValidPhotoDataUrl('data:image/jpeg;base64,')).toBe(false);
  });

  it('rejette une photo au-delà du plafond de 10 Mo (estimation base64)', () => {
    // ~10.7 Mo de base64 décodé — au-delà du plafond de 10 Mo
    const tooBig = 'data:image/jpeg;base64,' + 'A'.repeat(15_000_000);
    expect(isValidPhotoDataUrl(tooBig)).toBe(false);
  });
});

// ── buildQuestionnairePostBody / isEmptyPostBody ─────────────────────────
describe('buildQuestionnairePostBody', () => {
  it('section normale : reponses seules, jamais de champ photo', () => {
    const body = buildQuestionnairePostBody('contact', { ville: 'Fès' }, 'data:image/jpeg;base64,AAAA');
    expect(body).toEqual({ section: 'contact', reponses: { ville: 'Fès' } });
    expect(body.photo).toBeUndefined();
  });

  it('QJR633 : prefill_vu = sous-ensemble du prefill limité à la section', () => {
    const body = buildQuestionnairePostBody('energie', { facture_hiver: '900' }, null, 'id', {
      facture_hiver: 900,
      gps_lat: 1,
    });
    expect(body.prefill_vu).toEqual({ facture_hiver: 900 });
    const photo = 'data:image/jpeg;base64,' + 'A'.repeat(1000);
    expect(buildQuestionnairePostBody('photo_facture', {}, photo, 'id', { facture_hiver: 900 })).not.toHaveProperty('prefill_vu');
    expect(buildQuestionnairePostBody('energie', { facture_hiver: '900' })).not.toHaveProperty('prefill_vu');
  });

  it('section photo_* : reponses vide, photo reprise si valide', () => {
    const photo = 'data:image/jpeg;base64,' + 'A'.repeat(1000);
    const body = buildQuestionnairePostBody('photo_facture', {}, photo);
    expect(body).toEqual({ section: 'photo_facture', reponses: {}, photo });
  });

  it('section photo_* sans photo valide : le champ photo est omis (jamais envoyé malformé)', () => {
    const body = buildQuestionnairePostBody('photo_facture', {}, 'pas-un-data-url');
    expect(body).toEqual({ section: 'photo_facture', reponses: {} });
    expect(body.photo).toBeUndefined();
  });
});

describe('isEmptyPostBody', () => {
  it('vrai quand ni reponses ni photo', () => {
    expect(isEmptyPostBody({ section: 'contact', reponses: {} })).toBe(true);
  });

  it('faux dès qu’il y a au moins une réponse ou une photo', () => {
    expect(isEmptyPostBody({ section: 'contact', reponses: { ville: 'Rabat' } })).toBe(false);
    expect(isEmptyPostBody({ section: 'photo_facture', reponses: {}, photo: 'data:image/jpeg;base64,AAAA' })).toBe(
      false,
    );
  });
});

// ── parseQuestionnairePostResponse ────────────────────────────────────────
describe('parseQuestionnairePostResponse', () => {
  it('200 + ok:true ⇒ ok, enregistrees reprises', () => {
    const r = parseQuestionnairePostResponse(200, { ok: true, enregistrees: ['ville', 'email'] });
    expect(r).toEqual({ ok: true, enregistrees: ['ville', 'email'] });
  });

  it('404 (token invalide/expiré) ⇒ ok:false, detail repris', () => {
    const r = parseQuestionnairePostResponse(404, { detail: 'Introuvable' });
    expect(r.ok).toBe(false);
    expect(r.enregistrees).toEqual([]);
    expect(r.detail).toBe('Introuvable');
  });

  it('corps upstream illisible/non-objet ⇒ jamais un throw', () => {
    expect(parseQuestionnairePostResponse(502, null)).toEqual({ ok: false, enregistrees: [] });
    expect(parseQuestionnairePostResponse(502, 'erreur brute')).toEqual({ ok: false, enregistrees: [] });
  });

  it('enregistrees filtre les entrées non-string', () => {
    const r = parseQuestionnairePostResponse(200, { ok: true, enregistrees: ['ville', 42, null, 'email'] });
    expect(r.enregistrees).toEqual(['ville', 'email']);
  });
});

// ── isInternalPreview ─────────────────────────────────────────────────────
describe('isInternalPreview', () => {
  it('reflète interne tel que parsé', () => {
    expect(isInternalPreview({ interne: true })).toBe(true);
    expect(isInternalPreview({ interne: false })).toBe(false);
  });
});

// Sanity : tout accessoire du contrat GET reste bien typé (compile-time only,
// mais on garde un mini smoke-test runtime pour la forme complète attendue).
describe('QuestionnaireGetResponse — forme complète', () => {
  it('round-trip minimal', () => {
    const raw = {
      entreprise: 'Taqinor',
      prenom: 'Salma',
      sections: ['contact'],
      prefill: {},
      repondu: {},
      interne: false,
    };
    const parsed = parseQuestionnaireGet(raw) as QuestionnaireGetResponse;
    expect(parsed.entreprise).toBe('Taqinor');
    expect(parsed.sections).toEqual(['contact']);
  });
});

// ———————————————————————————————————————————————————————————————————————————
// AGW408 — section pompage et photos plaque/forage (FR/EN/AR) : parité avec le
// contrat `questionnaire_lead.json`, corps POST attendu, et « la page ne dessine
// que ce que le serveur sert ».
// ———————————————————————————————————————————————————————————————————————————
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  IRRIGATION_METHODE_VALUES,
  POMPE_ALIM_VALUES,
  SECTION_META,
  SOURCE_EAU_VALUES,
  cleanMoisIrrigation,
} from '../src/lib/questionnaire';

const lireContrat = () =>
  JSON.parse(
    readFileSync(
      fileURLToPath(new URL('../../../backend/django_core/apps/crm/contract_samples/questionnaire_lead.json', import.meta.url)),
      'utf-8',
    ),
  ) as {
    sections: string[];
    champs_par_section: Record<string, string[]>;
    colonnes_ecrites: Record<string, string[]>;
    exemple_agricole: { sections: string[]; champs: Record<string, string[]>; prefill: Record<string, unknown> };
  };

describe('AGW408 — parité avec le contrat questionnaire_lead.json', () => {
  it('les sections de la page sont EXACTEMENT celles du contrat, dans le même ordre', () => {
    expect([...QUESTIONNAIRE_SECTIONS]).toEqual(lireContrat().sections);
    for (const s of QUESTIONNAIRE_SECTIONS) expect(SECTION_META[s]).toBeDefined();
  });

  it('les colonnes écrites par le pompage sont celles que le corps POST peut porter', () => {
    const contrat = lireContrat();
    expect(contrat.champs_par_section.pompage).toEqual(contrat.colonnes_ecrites.pompage);
    const plein = buildSectionReponses('pompage', {
      source_eau: 'forage', niveau_statique_m: '35', besoin_eau_m3j: '120', surface_irriguee_ha: '4.5',
      culture: 'agrumes', irrigation_methode: 'goutte', pompe_alim_actuelle: 'butane',
      butane_bouteilles_jour: '3.5', carburant_prix_unitaire_mad: '45', depense_carburant_mad_mois: '2700',
      mois_irrigation: '3,4,5,6', compteur_eau: 'oui',
    });
    expect(Object.keys(plein).sort()).toEqual([...contrat.colonnes_ecrites.pompage].sort());
  });

  it('les choix fermés de la page sont ceux de crm.Lead', () => {
    expect([...SOURCE_EAU_VALUES]).toEqual(['puits', 'forage', 'bassin', 'riviere']);
    expect([...IRRIGATION_METHODE_VALUES]).toEqual(['goutte', 'aspersion', 'gravitaire']);
    expect([...POMPE_ALIM_VALUES]).toEqual(['aucune', 'diesel', 'butane', 'electrique']);
  });
});

describe('AGW408 — corps POST de la section pompage', () => {
  it('corps attendu : nombres tels que saisis (step="any"), choix fermés, mois triés, oui/non en booléen', () => {
    const body = buildQuestionnairePostBody('pompage', {
      source_eau: 'forage', niveau_statique_m: '35.5', besoin_eau_m3j: '120,5'.replace(',', '.'), surface_irriguee_ha: '4.25',
      culture: '  agrumes ', irrigation_methode: 'goutte', pompe_alim_actuelle: 'butane',
      butane_bouteilles_jour: '3.5', carburant_prix_unitaire_mad: '45', depense_carburant_mad_mois: '2700.5',
      mois_irrigation: '6,3,4,5,3', compteur_eau: 'non',
    });
    expect(body).toEqual({
      section: 'pompage',
      reponses: {
        source_eau: 'forage', niveau_statique_m: 35.5, besoin_eau_m3j: 120.5, surface_irriguee_ha: 4.25,
        culture: 'agrumes', irrigation_methode: 'goutte', pompe_alim_actuelle: 'butane',
        butane_bouteilles_jour: 3.5, carburant_prix_unitaire_mad: 45, depense_carburant_mad_mois: 2700.5,
        mois_irrigation: [3, 4, 5, 6], compteur_eau: false,
      },
    });
  });

  it('« je ne sais pas » ⇒ clés ABSENTES, jamais un 0 ni un défaut ; valeurs hors liste écartées', () => {
    const r = buildSectionReponses('pompage', {
      source_eau: '', niveau_statique_m: '', besoin_eau_m3j: '0', surface_irriguee_ha: '-3', culture: '   ',
      irrigation_methode: 'inondation', pompe_alim_actuelle: 'solaire', mois_irrigation: '13,0,x', compteur_eau: undefined,
    });
    expect(r).toEqual({});
  });

  it('cleanMoisIrrigation : entiers 1-12 distincts, triés ; sinon null', () => {
    expect(cleanMoisIrrigation('12,1,6,6')).toEqual([1, 6, 12]);
    expect(cleanMoisIrrigation([3, '4', 4.5, 99])).toEqual([3, 4]);
    expect(cleanMoisIrrigation('')).toBeNull();
    expect(cleanMoisIrrigation(undefined)).toBeNull();
  });

  it('prefill_vu limité aux colonnes du pompage ; sections photo_pompe/photo_forage : photo reprise, jamais de reponses', () => {
    const vu = buildQuestionnairePostBody('pompage', { culture: 'agrumes' }, null, undefined, {
      culture: 'agrumes', surface_irriguee_ha: 4, gps_lat: null, facture_hiver: 900,
    });
    expect(vu.prefill_vu).toEqual({ culture: 'agrumes', surface_irriguee_ha: 4 });
    const photo = 'data:image/jpeg;base64,AAAA';
    for (const section of ['photo_pompe', 'photo_forage'] as const) {
      expect(buildSectionReponses(section, { anything: 'x' })).toEqual({});
      expect(buildQuestionnairePostBody(section, {}, photo)).toEqual({ section, reponses: {}, photo });
      expect(buildQuestionnairePostBody(section, {}, 'pas-un-data-url')).toEqual({ section, reponses: {} });
    }
  });
});

describe('AGW408 — la page ne dessine que ce que le serveur sert', () => {
  it('un lead agricole : pompage + toit/GPS + photos + coordonnées, jamais présence/équipements/électricité', () => {
    const agricole = lireContrat().exemple_agricole.sections as (typeof QUESTIONNAIRE_SECTIONS)[number][];
    const ids = ecransActifs(agricole).map((e) => e.id);
    expect(ids).toEqual(['pompage', 'toit', 'photos']);
    for (const interdit of ['presence', 'equipements', 'electricite']) expect(ids).not.toContain(interdit);
  });

  it('un questionnaire résidentiel (sans section de pompage servie) n\'a aucun écran de pompage', () => {
    const ids = ecransActifs(['occupation', 'equipements', 'energie', 'toiture', 'gps', 'contact']).map((e) => e.id);
    expect(ids).not.toContain('pompage');
  });

  it('la page ne dessine une section QUE si le serveur la sert (boucle sur `sections`, champs par `demande`)', () => {
    const src = readFileSync(fileURLToPath(new URL('../src/pages/questionnaire/[token].astro', import.meta.url)), 'utf-8');
    expect(src).toMatch(/sections\.map\(\(id, i\) =>/);
    expect(src).toContain("{id === 'pompage' && (");
    expect(src).toContain("demande('pompage', 'source_eau')");
    // chaque colonne du pompage est dessinée sous le garde `demande`
    for (const col of lireContrat().colonnes_ecrites.pompage) {
      expect(src).toContain(`demande('pompage', '${col}')`);
    }
    // numériques en step="any", mois en 12 boutons
    expect(src).toContain('id="q-niveau-statique" type="number" min="0" step="any"');
    expect(src).toContain('class="q-mois-btn');
    expect(src).toContain('MOIS_COURTS.map');
  });

  it('chaque question reprend le help_text de la colonne, en FR, EN et AR', () => {
    const src = readFileSync(fileURLToPath(new URL('../src/pages/questionnaire/[token].astro', import.meta.url)), 'utf-8');
    for (const fr of [
      "L'eau vient d'où : un puits, un forage, un bassin ou une rivière ?",
      "À quelle profondeur est l'eau quand la pompe est arrêtée ?",
      "Combien de m³ d'eau par jour en pleine saison ?",
      "Qu'est-ce que vous cultivez ?",
      "Combien d'hectares irriguez-vous ?",
      'Vous arrosez comment : goutte-à-goutte, aspersion ou à la raie ?',
      'Vous irriguez quels mois ?',
      "Avez-vous un compteur d'eau ?",
    ]) expect(src).toContain(fr);
    for (const en of [
      'Where does the water come from', 'How deep is the water when the pump is stopped', 'What do you grow?',
      'How many hectares do you irrigate?', 'Which months do you irrigate?', 'Do you have a water meter?',
    ]) expect(src).toContain(en);
    for (const ar of ['من أين يأتي الماء', 'ماذا تزرعون؟', 'كم هكتاراً تسقون؟', 'في أي أشهر تسقون؟', 'هل لديكم عداد ماء؟']) {
      expect(src).toContain(ar);
    }
  });

  it('les photos plaque de pompe et tête de forage suivent le patron des sections photo_*', () => {
    const src = readFileSync(fileURLToPath(new URL('../src/pages/questionnaire/[token].astro', import.meta.url)), 'utf-8');
    expect(src).toContain('isPhotoSection(id) && (');
    expect(src).toContain("(['photo_facture', 'photo_compteur', 'photo_tableau', 'photo_pompe', 'photo_forage'] as const)");
    expect(src).toContain('Prenez une photo de la plaque de votre pompe');
    expect(src).toContain('Prenez une photo de la tête du forage.');
  });
});
