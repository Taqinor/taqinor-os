// LANE Q-B — Logique PURE du questionnaire client public.
// Aucune dépendance DOM ni réseau : parsing de la réponse GET, construction
// du corps POST par section, sanitisation des champs, photos.
import { describe, expect, it } from 'vitest';
import {
  QUESTIONNAIRE_SECTIONS,
  buildQuestionnairePostBody,
  buildSectionReponses,
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
  it('QUESTIONNAIRE_SECTIONS = exactement les 9 clés du contrat, dans cet ordre', () => {
    expect(QUESTIONNAIRE_SECTIONS).toEqual([
      'contact',
      'gps',
      'energie',
      'photo_facture',
      'photo_compteur',
      'photo_tableau',
      'toiture',
      'occupation',
      'equipements',
    ]);
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

  it('isPhotoSection distingue les 3 sections photo des 6 autres', () => {
    expect(isPhotoSection('photo_facture')).toBe(true);
    expect(isPhotoSection('photo_compteur')).toBe(true);
    expect(isPhotoSection('photo_tableau')).toBe(true);
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
    expect(initialSectionIndex(sections, { contact: true, gps: true })).toBe(2); // 'energie'
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
        roof_age_years: '8',
        ownership: 'proprietaire',
      }),
    ).toEqual({ type_toiture: 'villa', roof_age_years: 8, ownership: 'proprietaire' });

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
