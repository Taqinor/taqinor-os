// QJW3 — `construireCorps` : LE seul constructeur de corps du tunnel.
//
// Ce que ces tests protègent n'est pas « la fonction marche » mais la
// DISCIPLINE que les trois `buildBody()` appliquaient chacun de leur côté et
// qu'un module partagé doit reproduire à l'identique : « nettoyer ou omettre,
// jamais fabriquer ». Une question qu'on n'a pas posée est une clé ABSENTE —
// jamais un `false`, un `0` ou une chaîne vide inventés à sa place.

import { describe, expect, it } from 'vitest';
import { construireCorps, type MessagesErreurs } from '../src/lib/tunnel/corps';
import { CHAMPS_TUNNEL, etatVide, type EtatTunnel } from '../src/lib/tunnel/champs';

const MESSAGES: MessagesErreurs = { nomComplet: 'Nom complet requis' };

/** Un état résidentiel minimal et VALIDE — la base des variations ci-dessous. */
function etatResidentiel(): EtatTunnel {
  return {
    ...etatVide(),
    nomComplet: 'Reda Kasri',
    telephone: '0612345678',
    ville: 'Casablanca',
    consentement: true,
    mode: 'residentiel',
    languePreferee: 'fr',
    trancheFacture: '1500-3000',
    factureHiverMad: 2200,
    clientRef: 'KAS-1',
    idempotencyKey: 'idem-1',
    eventId: 'evt-1',
  };
}

const corps = (etat: EtatTunnel) => construireCorps(etat, { messages: MESSAGES }).body;

describe('construireCorps — pureté', () => {
  it("ne modifie pas l'état qu'on lui donne", () => {
    const etat = etatResidentiel();
    const avant = JSON.stringify(etat);
    construireCorps(etat, { messages: MESSAGES });
    expect(JSON.stringify(etat)).toBe(avant);
  });

  it('rend deux corps équivalents pour deux appels sur le même état', () => {
    const etat = etatResidentiel();
    expect(JSON.stringify(corps(etat))).toBe(JSON.stringify(corps(etat)));
  });
});

describe('construireCorps — « nettoyer ou omettre, jamais fabriquer »', () => {
  it("n'émet AUCUNE clé d'équipement quand aucune case n'est cochée", () => {
    const body = corps(etatResidentiel());
    for (const cle of Object.keys(body)) {
      expect(cle.startsWith('equip_')).toBe(false);
    }
    expect(body).not.toHaveProperty('occupation_jour');
  });

  it("un equip_* coché émet `true` — un decoché n'émet RIEN (jamais `false`)", () => {
    const body = corps({ ...etatResidentiel(), equipClim: true });
    expect(body.equip_clim).toBe(true);
    // Les trois autres cases sont décochées : ABSENTES, pas `false`.
    expect(body).not.toHaveProperty('equip_piscine');
    expect(body).not.toHaveProperty('equip_voiture_electrique');
    expect(body).not.toHaveProperty('equip_chauffe_eau_electrique');
  });

  it('un détail kW/créneau saisi puis sa case DÉCOCHÉE ne part pas', () => {
    // Le cas réel : le visiteur coche « climatisation », saisit 3,5 kW, puis
    // décoche. La saisie reste dans le champ masqué — elle ne doit pas partir.
    const body = corps({
      ...etatResidentiel(),
      equipClim: false,
      equipClimKw: 3.5,
      equipClimPieces: 4,
      equipClimCreneau: 'apres_midi',
    });
    expect(body).not.toHaveProperty('equip_clim');
    expect(body).not.toHaveProperty('equip_clim_kw');
    expect(body).not.toHaveProperty('equip_clim_pieces');
    expect(body).not.toHaveProperty('equip_clim_creneau');
  });

  it('les détails partent quand leur case parente EST cochée', () => {
    const body = corps({
      ...etatResidentiel(),
      equipPiscine: true,
      equipPiscinePompeKw: 1.1,
      equipPiscineHeuresJour: 6.5,
      equipPiscineCreneau: 'soir',
    });
    expect(body.equip_piscine).toBe(true);
    expect(body.equip_piscine_pompe_kw).toBe(1.1);
    expect(body.equip_piscine_heures_jour).toBe(6.5);
    expect(body.equip_piscine_creneau).toBe('soir');
  });

  it('un zéro RÉELLEMENT saisi part — il est borné par validateLead, pas inventé ici', () => {
    const body = corps({ ...etatResidentiel(), equipClim: true, equipClimPieces: 0 });
    expect(body.equip_clim_pieces).toBe(0);
  });

  it('un négatif RÉELLEMENT saisi part aussi (jamais corrigé en silence)', () => {
    const body = corps({ ...etatResidentiel(), equipClim: true, equipClimKw: -3 });
    expect(body.equip_clim_kw).toBe(-3);
  });

  it("un nombre absent (`null`) devient une clé ABSENTE, jamais un zéro", () => {
    const body = corps({ ...etatResidentiel(), equipClim: true, equipClimKw: null });
    expect(body).not.toHaveProperty('equip_clim_kw');
  });

  it('une chaîne vide devient une clé ABSENTE, jamais une chaîne vide envoyée', () => {
    const body = corps({ ...etatResidentiel(), email: '', appareilId: '' });
    expect(body).not.toHaveProperty('email');
    expect(body).not.toHaveProperty('appareilId');
  });
});

describe('construireCorps — les clés TOUJOURS présentes', () => {
  it('`factureHiver` garde son `null` explicite quand rien n\'est saisi', () => {
    // `validateLead` distingue « clé absente » de « clé à null » : le tunnel a
    // toujours émis `null` ici, la bascule ne change pas ce contrat.
    const body = corps({ ...etatResidentiel(), factureHiverMad: null });
    expect(Object.prototype.hasOwnProperty.call(body, 'factureHiver')).toBe(true);
    expect(body.factureHiver).toBeNull();
  });

  it('`website_url` (honeypot) part même vide — son absence serait un signal', () => {
    const body = corps(etatResidentiel());
    expect(Object.prototype.hasOwnProperty.call(body, 'website_url')).toBe(true);
    expect(body.website_url).toBe('');
  });

  it('tout descripteur `requis` produit bien une clé, même sur un état VIDE', () => {
    const body = corps(etatVide());
    for (const champ of CHAMPS_TUNNEL) {
      if (!champ.requis) continue;
      expect(
        Object.prototype.hasOwnProperty.call(body, champ.webhookKey),
        `${champ.cle} (${champ.webhookKey})`,
      ).toBe(true);
    }
  });

  it('aucun descripteur `requis` ne peut rendre `undefined` au nettoyage', () => {
    for (const champ of CHAMPS_TUNNEL) {
      if (!champ.requis) continue;
      expect(champ.nettoyer(undefined), champ.cle).not.toBeUndefined();
    }
  });
});

describe('construireCorps — les gates conservés', () => {
  it("`heuresPompage` reste gaté sur le mode agricole (curseur à value=\"7\")", () => {
    // Le curseur part avec « 7 » AVANT toute interaction : sans ce gate un
    // lead résidentiel transporterait 7 h/j que personne n'a saisi.
    const resid = corps({ ...etatResidentiel(), heuresPompage: 7 });
    expect(resid).not.toHaveProperty('heuresPompage');
    const agri = corps({ ...etatResidentiel(), mode: 'agricole', heuresPompage: 7 });
    expect(agri.heuresPompage).toBe(7);
  });

  it("`tensionRaccordement` et `activityProfile` ne partent que pour un profil C&I", () => {
    const resid = corps({ ...etatResidentiel(), tension: 'bt', activite: 'day' });
    expect(resid).not.toHaveProperty('tensionRaccordement');
    expect(resid).not.toHaveProperty('activityProfile');
    const indus = corps({
      ...etatResidentiel(),
      mode: 'industriel',
      tension: 'bt',
      activite: 'day',
    });
    expect(indus.tensionRaccordement).toBe('bt');
    expect(indus.activityProfile).toBe('day');
  });

  it("`categorieCommerciale` ne part qu'en mode commercial", () => {
    const indus = corps({
      ...etatResidentiel(),
      mode: 'industriel',
      categorieCommerciale: 'hotel',
    });
    expect(indus).not.toHaveProperty('categorieCommerciale');
    const comm = corps({
      ...etatResidentiel(),
      mode: 'commercial',
      categorieCommerciale: 'hotel',
    });
    expect(comm.categorieCommerciale).toBe('hotel');
  });

  it("`equipes` part indépendamment du mode ACTIF (aucune réponse effacée)", () => {
    // Le visiteur décrit son site industriel puis rebascule sur « commercial » :
    // sa réponse doit survivre au changement de mode.
    const body = corps({ ...etatResidentiel(), mode: 'commercial', equipes: '3x8' });
    expect(body.equipes).toBe('3x8');
  });

  it('`surfaceToitureM2` ne part que pour une VRAIE toiture', () => {
    const terrain = corps({
      ...etatResidentiel(),
      mode: 'industriel',
      typeSurface: 'terrain',
      surfaceM2: 900,
    });
    expect(terrain).not.toHaveProperty('surfaceToitureM2');
    expect(terrain.terrain).toBe(true);
    expect(terrain.surfaceM2).toBe(900);
    const toit = corps({
      ...etatResidentiel(),
      mode: 'industriel',
      typeSurface: 'bac_acier',
      surfaceM2: 900,
    });
    expect(toit.surfaceToitureM2).toBe(900);
    expect(toit).not.toHaveProperty('terrain');
  });

  it("l'unité d'eau choisit UNE des deux clés — jamais les deux, jamais une conversion", () => {
    const m3h = corps({ ...etatResidentiel(), mode: 'agricole', uniteEau: 'm3h', besoinEau: 12 });
    expect(m3h.debitM3h).toBe(12);
    expect(m3h).not.toHaveProperty('besoinM3j');
    const m3j = corps({ ...etatResidentiel(), mode: 'agricole', uniteEau: 'm3j', besoinEau: 12 });
    expect(m3j.besoinM3j).toBe(12);
    expect(m3j).not.toHaveProperty('debitM3h');
  });
});

describe('construireCorps — billRange dérivé', () => {
  it('résidentiel : la tranche vient du select', () => {
    expect(corps(etatResidentiel()).billRange).toBe('1500-3000');
  });

  it('agricole : plus de tranche du tout (un pompage se dimensionne sur HMT × débit)', () => {
    expect(corps({ ...etatResidentiel(), mode: 'agricole' }).billRange).toBe('');
  });

  it('C&I en MAD : la tranche est dérivée du montant saisi', () => {
    const body = corps({
      ...etatResidentiel(),
      mode: 'industriel',
      factureProUnite: 'mad',
      factureProValeur: 2000,
    });
    expect(body.billRange).toBe('1500-3000');
  });

  it('C&I en kWh SANS tarif connu : aucune tranche fabriquée', () => {
    const body = corps({
      ...etatResidentiel(),
      mode: 'industriel',
      factureProUnite: 'kwh',
      factureProValeur: 1800,
      tarifProMadKwh: null,
    });
    expect(body.billRange).toBe('');
  });

  it('C&I en kWh AVEC le tarif du moteur : la tranche suit le chiffre affiché', () => {
    const body = corps({
      ...etatResidentiel(),
      mode: 'industriel',
      factureProUnite: 'kwh',
      factureProValeur: 1800,
      tarifProMadKwh: 1.2, // 1 800 kWh × 1,2 = 2 160 MAD
    });
    expect(body.billRange).toBe('1500-3000');
  });

  it('au-delà du dernier palier, `gt10000` reste factuellement vrai', () => {
    const body = corps({
      ...etatResidentiel(),
      mode: 'industriel',
      factureProUnite: 'mad',
      factureProValeur: 250_000,
    });
    expect(body.billRange).toBe('gt10000');
  });
});

describe('construireCorps — roofType dérivé, jamais inventé', () => {
  it("un résidentiel non interrogé retombe sur le bucket honnête 'autre'", () => {
    expect(corps(etatResidentiel()).roofType).toBe('autre');
  });

  it('un bac acier devient hangar, une terrasse un toit plat', () => {
    expect(corps({ ...etatResidentiel(), mode: 'industriel', typeSurface: 'bac_acier' }).roofType)
      .toBe('hangar');
    expect(corps({ ...etatResidentiel(), mode: 'industriel', typeSurface: 'terrasse' }).roofType)
      .toBe('toit_plat');
  });
});

describe('construireCorps — carte et tracking', () => {
  it('un repère pose roofPoint + gpsLat + gpsLng ; sans repère, aucune des trois', () => {
    const sans = corps(etatResidentiel());
    expect(sans).not.toHaveProperty('roofPoint');
    expect(sans).not.toHaveProperty('gpsLat');
    expect(sans).not.toHaveProperty('gpsLng');
    const avec = corps({ ...etatResidentiel(), repereToit: { lat: 33.57, lng: -7.59 } });
    expect(avec.roofPoint).toEqual({ lat: 33.57, lng: -7.59 });
    expect(avec.gpsLat).toBe(33.57);
    expect(avec.gpsLng).toBe(-7.59);
  });

  it("un contour de moins de 3 sommets n'est pas un polygone : clé ABSENTE", () => {
    const deux = corps({ ...etatResidentiel(), contourToit: [[1, 2], [3, 4]] });
    expect(deux).not.toHaveProperty('roofOutline');
    const trois = corps({ ...etatResidentiel(), contourToit: [[1, 2], [3, 4], [5, 6]] });
    expect(trois.roofOutline).toHaveLength(3);
  });

  it('seules les clés de tracking PRÉSENTES sont jointes', () => {
    const body = corps({ ...etatResidentiel(), tracking: { utm_source: 'meta' } });
    expect(body.utm_source).toBe('meta');
    expect(body).not.toHaveProperty('fbclid');
    expect(body).not.toHaveProperty('utm_medium');
  });
});

describe('construireCorps — langue_preferee', () => {
  it('part quand la page la transmet (FR/AR)', () => {
    expect(corps({ ...etatResidentiel(), languePreferee: 'ar' }).langue_preferee).toBe('ar');
  });

  it("est ABSENTE quand la page ne la transmet pas (page EN : LEAD_LANGS = fr|ar)", () => {
    expect(corps({ ...etatResidentiel(), languePreferee: '' })).not.toHaveProperty(
      'langue_preferee',
    );
  });
});

describe('construireCorps — le pré-contrôle passe par validateLead', () => {
  it('un état valide ne produit aucune erreur', () => {
    const { errors } = construireCorps(etatResidentiel(), { messages: MESSAGES });
    expect(errors).toEqual({});
  });

  it('un état vide produit les erreurs de champ de validateLead', () => {
    const { errors } = construireCorps(etatVide(), { messages: MESSAGES });
    // Pas d'erreur `roofType` : le type de toit est DÉRIVÉ et retombe sur le
    // bucket honnête 'autre', qui est un id valide — plus aucun écran ne pose
    // la question depuis la coupe fondateur du 18/08.
    expect(Object.keys(errors).sort()).toEqual(
      ['billRange', 'city', 'consent', 'fullName', 'phone'].sort(),
    );
  });

  it('WJ65 — un nom sans AUCUNE lettre est refusé, dans la langue de l\'écran', () => {
    const { errors } = construireCorps(
      { ...etatResidentiel(), nomComplet: '😀😀' },
      { messages: { nomComplet: 'Full name required' } },
    );
    expect(errors.fullName).toBe('Full name required');
  });

  it('WJ65 — un nom arabe passe (\\p{L} couvre tous les alphabets)', () => {
    const { errors } = construireCorps(
      { ...etatResidentiel(), nomComplet: 'رضا قصري' },
      { messages: MESSAGES },
    );
    expect(errors.fullName).toBeUndefined();
  });

  it("traduit un message de validateLead quand la page en fournit un — sinon le laisse", () => {
    const { errors } = construireCorps(etatVide(), {
      messages: { nomComplet: 'Full name required', ville: 'City required' },
    });
    expect(errors.city).toBe('City required');
    // Aucune traduction fournie pour le téléphone : le message CIRCONSTANCIÉ
    // de normalizeMoroccanPhone passe tel quel — jamais remplacé par plus vague.
    expect(errors.phone).toBeTruthy();
    expect(errors.phone).not.toBe('City required');
  });
});
