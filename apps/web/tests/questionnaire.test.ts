// LANE Q-B — Logique PURE du questionnaire client public.
// Aucune dépendance DOM ni réseau : parsing de la réponse GET, construction
// du corps POST par section, sanitisation des champs, photos.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
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
  it('QUESTIONNAIRE_SECTIONS = exactement les 18 clés du contrat, dans cet ordre', () => {
    // Ordre = crm.QuestionnaireLien.SECTIONS_CLES (recherche 25/08/2026) :
    // engagement croissant, `contact` TOUJOURS en dernier.
    expect(QUESTIONNAIRE_SECTIONS).toEqual([
      'occupation',
      'equipements',
      'energie',
      'pompage',
      'reseau',
      'activite',
      'toiture',
      'site',
      'gps',
      'photo_facture',
      'photo_compteur',
      'photo_tableau',
      'photo_pompe',
      'photo_forage',
      'photo_factures',
      'photo_poste',
      'societe',
      'contact',
    ]);
  });

  it('CIW406 — la liste des sections = `sections` du contrat questionnaire_lead.json', () => {
    const contrat = JSON.parse(
      readFileSync(
        fileURLToPath(new URL('../../../backend/django_core/apps/crm/contract_samples/questionnaire_lead.json', import.meta.url)),
        'utf-8',
      ),
    ) as { sections: string[] };
    expect([...QUESTIONNAIRE_SECTIONS]).toEqual(contrat.sections);
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

  it('isPhotoSection distingue les 7 sections photo des autres', () => {
    expect(isPhotoSection('photo_facture')).toBe(true);
    expect(isPhotoSection('photo_compteur')).toBe(true);
    expect(isPhotoSection('photo_tableau')).toBe(true);
    expect(isPhotoSection('photo_pompe')).toBe(true);
    expect(isPhotoSection('photo_forage')).toBe(true);
    expect(isPhotoSection('photo_factures')).toBe(true);
    expect(isPhotoSection('photo_poste')).toBe(true);
    expect(isPhotoSection('reseau')).toBe(false);
    expect(isPhotoSection('societe')).toBe(false);
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

  it('les 18 sections tiennent sur 10 écrans au maximum, jamais 18', () => {
    expect(ECRANS).toHaveLength(10);
    expect(ecransActifs(toutes)).toHaveLength(10);
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

  it('les sept photos tiennent sur UN écran, toiture+site+GPS sur un autre', () => {
    const photos = ECRANS.find((e) => e.id === 'photos');
    expect(photos!.sections).toEqual([
      'photo_facture', 'photo_compteur', 'photo_tableau', 'photo_pompe', 'photo_forage',
      'photo_factures', 'photo_poste',
    ]);
    expect(ECRANS.find((e) => e.id === 'pompage')!.sections).toEqual(['pompage']);
    expect(ECRANS.find((e) => e.id === 'toit')!.sections).toEqual(['toiture', 'site', 'gps']);
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

// ── AGW408 — section pompage (agricole), servie par le serveur ───────────
describe('AGW408 — pompage : corps POST', () => {
  it('construit les réponses typées, mois triés/dédoublonnés, compteur booléen', () => {
    const b = buildQuestionnairePostBody('pompage', {
      source_eau: 'forage',
      niveau_statique_m: '35.5',
      besoin_eau_m3j: '120',
      surface_irriguee_ha: '4',
      culture: ' agrumes ',
      irrigation_methode: 'goutte',
      pompe_alim_actuelle: 'butane',
      butane_bouteilles_jour: '2.5',
      carburant_prix_unitaire_mad: '45',
      depense_carburant_mad_mois: '1800',
      mois_irrigation: [6, 5, 5, 7, 13, 0],
      compteur_eau: 'oui',
    });
    expect(b.section).toBe('pompage');
    expect(b.reponses).toEqual({
      source_eau: 'forage',
      niveau_statique_m: 35.5,
      besoin_eau_m3j: 120,
      surface_irriguee_ha: 4,
      culture: 'agrumes',
      irrigation_methode: 'goutte',
      pompe_alim_actuelle: 'butane',
      butane_bouteilles_jour: 2.5,
      carburant_prix_unitaire_mad: 45,
      depense_carburant_mad_mois: 1800,
      mois_irrigation: [5, 6, 7],
      compteur_eau: true,
    });
    expect(b.photo).toBeUndefined();
  });

  it('un choix hors contrat est écarté, jamais envoyé', () => {
    const b = buildQuestionnairePostBody('pompage', { source_eau: 'lac', irrigation_methode: 'laser', pompe_alim_actuelle: 'solaire' });
    expect(b.reponses).toEqual({});
  });

  it('pompe électrique : aucune question carburant transmise (champs masqués)', () => {
    const b = buildQuestionnairePostBody('pompage', {
      pompe_alim_actuelle: 'electrique',
      butane_bouteilles_jour: '3',
      carburant_prix_unitaire_mad: '40',
      depense_carburant_mad_mois: '900',
    });
    expect(b.reponses).toEqual({ pompe_alim_actuelle: 'electrique' });
  });

  it('diesel : pas de bouteilles de butane', () => {
    const b = buildQuestionnairePostBody('pompage', { pompe_alim_actuelle: 'diesel', butane_bouteilles_jour: '3', carburant_prix_unitaire_mad: '11' });
    expect(b.reponses).toEqual({ pompe_alim_actuelle: 'diesel', carburant_prix_unitaire_mad: 11 });
  });

  it('compteur « non » reste un faux explicite ; non répondu = absent', () => {
    expect(buildQuestionnairePostBody('pompage', { compteur_eau: 'non' }).reponses).toEqual({ compteur_eau: false });
    expect(buildQuestionnairePostBody('pompage', {}).reponses).toEqual({});
  });

  it('photo_pompe / photo_forage : photo seule, aucune réponse', () => {
    const photo = 'data:image/jpeg;base64,/9j/4AAQSkZJRg==';
    for (const s of ['photo_pompe', 'photo_forage'] as const) {
      const b = buildQuestionnairePostBody(s, { source_eau: 'forage' }, photo);
      expect(b.reponses).toEqual({});
      expect(b.photo).toBe(photo);
    }
  });

  it('prefill_vu limité aux colonnes pompage', () => {
    const b = buildQuestionnairePostBody('pompage', { culture: 'blé' }, null, undefined, { culture: 'agrumes', gps_lat: 1 });
    expect(b.prefill_vu).toEqual({ culture: 'agrumes' });
  });

  it('une section pompage servie dessine son propre écran, jamais de section résidentielle en plus', () => {
    const ecrans = ecransActifs(['pompage', 'gps', 'photo_pompe', 'photo_forage']);
    expect(ecrans.map((e) => e.id)).toEqual(['pompage', 'toit', 'photos']);
    expect(ecrans.flatMap((e) => e.actives)).toEqual(['pompage', 'gps', 'photo_pompe', 'photo_forage']);
  });

  it('parseQuestionnaireGet accepte l’exemple agricole du contrat', () => {
    const r = parseQuestionnaireGet({
      entreprise: 'Taqinor', prenom: 'Brahim',
      sections: ['pompage', 'gps', 'photo_pompe', 'photo_forage'],
      champs: { pompage: ['source_eau'], photo_pompe: [], photo_forage: [] },
      prefill: { source_eau: 'forage' }, repondu: {}, interne: false,
    });
    expect(r?.sections).toEqual(['pompage', 'gps', 'photo_pompe', 'photo_forage']);
  });
});

// ── CIW406 — sections PRO (réseau, activité, site, société) ──────────────
describe('CIW406 — sections pro : corps POST', () => {
  it('réseau : tension fermée, kVA/kWh, relevé ≤ 12 mois, registres MT seulement en MT', () => {
    const releve = [
      { mois: '2026-08', kwh: '41000', kwh_pointe: '5000', kwh_pleines: '30000', kwh_creuses: '6000' },
      { mois: '2026-07', kwh: '39000' },
      { mois: '2026-07', kwh: '1' }, // doublon écarté
      { mois: 'juillet', kwh: '10' }, // mois illisible écarté
      { mois: '2026-06', kwh: '' }, // sans kWh : jamais un 0 fabriqué
    ];
    const mt = buildSectionReponses('reseau', {
      tension_raccordement: 'mt', compteur_puissance_kva: '630', conso_mensuelle_kwh: '41000', releve_conso: releve, cos_phi: '0.92',
    });
    expect(mt.tension_raccordement).toBe('mt');
    expect(mt.compteur_puissance_kva).toBe(630);
    expect(mt.conso_mensuelle_kwh).toBe(41000);
    expect(mt.cos_phi).toBe(0.92);
    expect(mt.releve_conso).toEqual({
      mois: [
        { mois: '2026-08', kwh: 41000, kwh_pointe: 5000, kwh_pleines: 30000, kwh_creuses: 6000 },
        { mois: '2026-07', kwh: 39000 },
      ],
      source: 'declare',
    });
    const bt = buildSectionReponses('reseau', { tension_raccordement: 'bt', releve_conso: releve });
    expect((bt.releve_conso as { mois: Array<Record<string, unknown>> }).mois[0]).toEqual({ mois: '2026-08', kwh: 41000 });
  });

  it('réseau : au plus 12 mois, tension hors liste écartée, cos φ > 1 écarté', () => {
    const releve = Array.from({ length: 14 }, (_, i) => ({ mois: `2025-${String((i % 12) + 1).padStart(2, '0')}`, kwh: '100' }));
    const out = buildSectionReponses('reseau', { tension_raccordement: 'ht', releve_conso: releve, cos_phi: '1.4' });
    expect(out.tension_raccordement).toBeUndefined();
    expect(out.cos_phi).toBeUndefined();
    expect((out.releve_conso as { mois: unknown[] }).mois.length).toBeLessThanOrEqual(12);
  });

  it('activité commerciale : catégorie + SEULES ses clés fermées, typées', () => {
    const out = buildSectionReponses('activite', {
      categorie_commerciale: 'hotel',
      reponses_categorie: { chambres: '40', occupation_pct: '62', piscine: 'oui', blanchisserie: 'non', effectif: '9', horaires: 'midi' },
      jours_ouverture: [1, 2, 3, 3, 9],
      heure_debut: '8', heure_fin: '22',
      fermeture_mois: [8, 1],
      groupe_electrogene: 'oui', groupe_kva: '100', groupe_litres_mois: '300', groupe_depense_mad_mois: '2500',
      pv_existant_kwc: '12',
    });
    expect(out.categorie_commerciale).toBe('hotel');
    expect(out.reponses_categorie).toEqual({ chambres: 40, occupation_pct: 62, piscine: true, blanchisserie: false });
    expect(out.jours_ouverture).toEqual([1, 2, 3]);
    expect(out.heure_debut).toBe(8);
    expect(out.heure_fin).toBe(22);
    expect(out.fermeture_mois).toEqual([1, 8]);
    expect(out.groupe_kva).toBe(100);
    expect(out.groupe_litres_mois).toBe(300);
    expect(out.groupe_depense_mad_mois).toBe(2500);
    expect(out.pv_existant_kwc).toBe(12);
  });

  it('activité : horaires incohérents (début ≥ fin) jamais envoyés ; groupe « non » sans détails', () => {
    const out = buildSectionReponses('activite', {
      heure_debut: '20', heure_fin: '8', groupe_electrogene: 'non', groupe_kva: '100', groupe_litres_mois: '300',
    });
    expect(out.heure_debut).toBeUndefined();
    expect(out.heure_fin).toBeUndefined();
    expect(out.groupe_electrogene).toBe('non');
    expect(out.groupe_kva).toBeUndefined();
    expect(out.groupe_litres_mois).toBeUndefined();
  });

  it('activité industrielle : secteur, export UE, équipes ; catégorie hors liste écartée', () => {
    const out = buildSectionReponses('activite', {
      secteur_industriel: '  Conserverie  ', export_ue_declare: 'oui', regime_equipes: '3x8', categorie_commerciale: 'usine',
    });
    expect(out.secteur_industriel).toBe('Conserverie');
    expect(out.export_ue_declare).toBe('oui');
    expect(out.regime_equipes).toBe('3x8');
    expect(out.categorie_commerciale).toBeUndefined();
    expect(out.reponses_categorie).toBeUndefined();
  });

  it('une consigne de froid négative est conservée (−18 °C)', () => {
    const out = buildSectionReponses('activite', {
      categorie_commerciale: 'froid', reponses_categorie: { temperature_consigne: '-18', volume_m3: '900' },
    });
    expect(out.reponses_categorie).toEqual({ temperature_consigne: -18, volume_m3: 900 });
  });

  it('site : surface, type de toiture PRO (liste fermée), m² disponibles', () => {
    const out = buildSectionReponses('site', { type_surface: 'ombriere', type_toiture: 'bac_acier', surface_toiture_m2: '650' });
    expect(out).toEqual({ type_surface: 'ombriere', type_toiture: 'bac_acier', surface_toiture_m2: 650 });
    // le vocabulaire résidentiel (villa…) n'est pas un choix de la section « site »
    expect(buildSectionReponses('site', { type_toiture: 'villa' }).type_toiture).toBeUndefined();
  });

  it('société : identité complète, e-mail secondaire validé, TVA en liste fermée', () => {
    const out = buildSectionReponses('societe', {
      societe: 'Hôtel Exemple SARL', ice: '001234567000089', rc: '12345', if_fiscal: '5566',
      adresse_siege: '1 rue X, Casablanca', fonction_contact: 'Directeur', contact_secondaire_nom: 'Sara',
      contact_secondaire_telephone: '0600000000', contact_secondaire_email: 'pas-un-email', contact_secondaire_fonction: 'DAF',
      tva_recuperable: 'oui',
    });
    expect(out.societe).toBe('Hôtel Exemple SARL');
    expect(out.ice).toBe('001234567000089');
    expect(out.contact_secondaire_email).toBeUndefined();
    expect(out.tva_recuperable).toBe('oui');
    expect(buildSectionReponses('societe', { tva_recuperable: 'peut-être' }).tva_recuperable).toBeUndefined();
  });

  it('photo_factures / photo_poste : photo seule, aucune réponse', () => {
    const photo = 'data:image/jpeg;base64,' + 'A'.repeat(200);
    for (const s of ['photo_factures', 'photo_poste'] as const) {
      const body = buildQuestionnairePostBody(s, {}, photo);
      expect(body.reponses).toEqual({});
      expect(body.photo).toBe(photo);
    }
  });

  it('prefill_vu limité aux colonnes de la section pro', () => {
    const body = buildQuestionnairePostBody(
      'site', { type_surface: 'toiture' }, null, undefined,
      { type_surface: 'toiture', surface_toiture_m2: 650, ice: 'x' },
    );
    expect(body.prefill_vu).toEqual({ type_surface: 'toiture', surface_toiture_m2: 650 });
  });
});

describe('CIW406 — contrat : exemple_pro et choix fermés', () => {
  const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
  const contrat = JSON.parse(
    read('../../../backend/django_core/apps/crm/contract_samples/questionnaire_lead.json'),
  ) as { exemple_pro: Record<string, unknown>; segment_pro: { sections_pro: string[]; refusees_400: string[] } };
  const lp = JSON.parse(
    read('../../../backend/django_core/apps/crm/contract_samples/lead_pro.json'),
  ) as { colonnes_pro: Array<{ nom: string; choix?: string[] }>; reponses_categorie_par_categorie: { cles: Record<string, string[]> } };
  const choix = (nom: string) => lp.colonnes_pro.find((c) => c.nom === nom)?.choix;

  it('l’exemple pro du contrat est exploitable : 7 sections pro, écrans pro seulement', () => {
    const parsed = parseQuestionnaireGet(contrat.exemple_pro);
    expect(parsed).not.toBeNull();
    expect(parsed!.sections).toEqual(contrat.segment_pro.sections_pro);
    const ids = ecransActifs(parsed!.sections).map((e) => e.id);
    expect(ids).toEqual(['reseau', 'activite', 'toit', 'photos', 'societe', 'coordonnees']);
    // Aucune section résidentielle refusée n'est servie ni dessinée.
    for (const refusee of contrat.segment_pro.refusees_400) {
      expect(parsed!.sections).not.toContain(refusee);
    }
  });

  it('choix fermés = contrat lead_pro.json', async () => {
    const lib = await import('../src/lib/questionnaire');
    expect([...lib.TENSION_VALUES]).toEqual(choix('tension_raccordement'));
    expect([...lib.TYPE_SURFACE_VALUES]).toEqual(choix('type_surface'));
    expect([...lib.TYPE_TOITURE_PRO_VALUES]).toEqual(choix('type_toiture'));
    expect([...lib.REGIME_EQUIPES_VALUES]).toEqual(choix('regime_equipes'));
    expect([...lib.TVA_RECUPERABLE_VALUES]).toEqual(choix('tva_recuperable'));
    expect([...lib.CATEGORIE_COMMERCIALE_VALUES]).toEqual(choix('categorie_commerciale'));
  });

  it('questions de catégorie = clés fermées du contrat (par catégorie)', async () => {
    const lib = await import('../src/lib/questionnaire');
    for (const [cat, cles] of Object.entries(lp.reponses_categorie_par_categorie.cles)) {
      expect(lib.REPONSES_CATEGORIE_QUESTIONS[cat].map((q) => q.key), cat).toEqual(cles);
    }
  });
});
