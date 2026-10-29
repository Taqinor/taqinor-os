// QJW3 — `construireCorps` : LE seul constructeur de corps du tunnel.
//
// Ce que ces tests protègent n'est pas « la fonction marche » mais la
// DISCIPLINE que les trois `buildBody()` appliquaient chacun de leur côté et
// qu'un module partagé doit reproduire à l'identique : « nettoyer ou omettre,
// jamais fabriquer ». Une question qu'on n'a pas posée est une clé ABSENTE —
// jamais un `false`, un `0` ou une chaîne vide inventés à sa place.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
      activiteTouchee: true,
    });
    expect(indus.tensionRaccordement).toBe('bt');
    expect(indus.activityProfile).toBe('day');
  });

  it("CIW408 — en mode COMMERCIAL, tensionRaccordement et activityProfile ne partent JAMAIS (panneau caché)", () => {
    const comm = corps({ ...etatResidentiel(), mode: 'commercial', tension: 'bt', activite: 'day' });
    expect(comm).not.toHaveProperty('tensionRaccordement');
    expect(comm).not.toHaveProperty('activityProfile');
    // même avec des valeurs non par défaut posées par un ancien état
    const comm2 = corps({ ...etatResidentiel(), mode: 'commercial', tension: 'mt', activite: 'continuous' });
    expect(comm2).not.toHaveProperty('tensionRaccordement');
    expect(comm2).not.toHaveProperty('activityProfile');
  });

  it("CIW408 — le payload INDUSTRIEL (et l'alias professionnel) est inchangé", () => {
    for (const mode of ['industriel', 'professionnel'] as const) {
      const indus = corps({ ...etatResidentiel(), mode, tension: 'mt', activite: 'continuous', tensionTouchee: true, activiteTouchee: true });
      expect(indus.tensionRaccordement).toBe('mt');
      expect(indus.activityProfile).toBe('continuous');
    }
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

// ———————————————————————————————————————————————————————————————————————————
// AGW403 — les heures de pompage ne partent que si le visiteur a touché le
// curseur (data-touche="1"), dans les trois locales.
// ———————————————————————————————————————————————————————————————————————————
import { readFileSync } from 'node:fs';
import { lireSourceTunnel } from './astroBlocsHelper';
import { fileURLToPath } from 'node:url';
import { lireChampsDomTunnel } from '../src/lib/tunnel/lecture';

/** Un Document minimal : seul `getElementById` + value/checked/getAttribute servent à la lecture. */
function fauxDocument(els: Record<string, { value?: string; touche?: boolean }>): Document {
  return {
    getElementById: (id: string) =>
      els[id]
        ? {
            value: els[id].value ?? '',
            checked: false,
            getAttribute: (n: string) => (n === 'data-touche' && els[id].touche ? '1' : null),
          }
        : null,
  } as unknown as Document;
}

describe('AGW403 — heuresPompage seulement si le curseur a été touché', () => {
  it('curseur non touché (value=7) → aucune clé heuresPompage dans le corps', () => {
    const lus = lireChampsDomTunnel(fauxDocument({ 'mt-heures-pompage': { value: '7' } }));
    expect(lus.heuresPompage).toBeNull();
    const body = corps({ ...etatResidentiel(), ...lus, mode: 'agricole' });
    expect(body).not.toHaveProperty('heuresPompage');
  });

  it('curseur touché à 7 → heuresPompage=7', () => {
    const lus = lireChampsDomTunnel(fauxDocument({ 'mt-heures-pompage': { value: '7', touche: true } }));
    expect(lus.heuresPompage).toBe(7);
    const body = corps({ ...etatResidentiel(), ...lus, mode: 'agricole' });
    expect(body.heuresPompage).toBe(7);
  });

  it('curseur touché à 9 → 9 ; touché mais résidentiel → toujours gaté', () => {
    const lus = lireChampsDomTunnel(fauxDocument({ 'mt-heures-pompage': { value: '9', touche: true } }));
    expect(corps({ ...etatResidentiel(), ...lus, mode: 'agricole' }).heuresPompage).toBe(9);
    expect(corps({ ...etatResidentiel(), ...lus })).not.toHaveProperty('heuresPompage');
  });

  for (const [lang, rel] of [
    ['FR', '../src/pages/devis/mon-toit.astro'],
    ['EN', '../src/pages/en/devis/mon-toit.astro'],
    ['AR', '../src/pages/ar/devis/mon-toit.astro'],
  ] as const) {
    it(`${lang} — la page pose data-touche au premier input/change du curseur`, () => {
      const src = lireSourceTunnel(fileURLToPath(new URL(rel, import.meta.url)));
      expect(src).toContain("heuresInput.dataset.touche = '1'");
      expect(src).toContain("heuresInput?.addEventListener('change', marquerHeuresTouchees);");
      expect(src).toContain('marquerHeuresTouchees();\n    syncHeuresLabel();'.replace(/\n/g, src.includes('\r\n') ? '\r\n' : '\n'));
      // le curseur lui-même ne porte aucun data-touche au chargement
      expect(src).not.toMatch(/id="mt-heures-pompage"[^>]*data-touche/);
    });
  }
});

// ———————————————————————————————————————————————————————————————————————————
// CIW404 — aucun chiffre d'hypothèse C&I ne part au CRM ; un gros compte en kWh
// prend la tranche gt10000 ; « ~1,01 DH/kWh » retiré des 3 langues.
// ———————————————————————————————————————————————————————————————————————————
import { trancheFactureProfessionnelle } from '../src/lib/tunnel/champs';

describe('CIW404 — estimateShown des modes commercial/industriel', () => {
  const chiffres = {
    kwc: 120, nbPanneaux: 170, prodKwh: 200000, tauxAutoconso: 99, tauxCouverture: 60,
    ecoMadYearLow: 90000, ecoMadYearHigh: 110000, paybackLabel: '3 – 5 ans',
  };
  const valeursNumeriques = (o: unknown) =>
    Object.values((o ?? {}) as Record<string, unknown>).filter((v) => typeof v === 'number');

  for (const mode of ['commercial', 'industriel'] as const) {
    it(`${mode} — le payload n'a plus de clé estimateShown : aucun chiffre d'hypothèse (kWc, éco, retour, taux) vers le CRM`, () => {
      const body = corps({
        ...etatResidentiel(), mode, factureProValeur: 30000, factureProUnite: 'mad', estimationAffichee: chiffres,
      });
      expect(body).not.toHaveProperty('estimateShown');
      expect(valeursNumeriques(body.estimateShown)).toEqual([]);
      const json = JSON.stringify(body);
      for (const k of ['ecoMadYearLow', 'tauxAutoconso', 'tauxCouverture', 'paybackLabel', 'prodKwh']) {
        expect(json).not.toContain(k);
      }
    });

    it(`${mode} — sans estimation, la clé est absente (rien n'est inventé)`, () => {
      const body = corps({ ...etatResidentiel(), mode, factureProValeur: 30000, factureProUnite: 'mad', estimationAffichee: null });
      expect(body).not.toHaveProperty('estimateShown');
    });
  }

  it('le résidentiel et l\'agricole gardent leurs chiffres montrés, inchangés', () => {
    const resid = corps({ ...etatResidentiel(), estimationAffichee: { kwc: 6, ecoMadYearLow: 9000 } });
    expect(resid.estimateShown).toEqual({ kwc: 6, ecoMadYearLow: 9000 });
    const agri = corps({ ...etatResidentiel(), mode: 'agricole', estimationAffichee: { pompeCv: 5.5, m3Jour: 70 } });
    expect(agri.estimateShown).toEqual({ pompeCv: 5.5, m3Jour: 70 });
  });
});

describe('CIW404 — gros compte en kWh : tranche gt10000, jamais d\'erreur sur un champ caché', () => {
  const etatPro = (over: Partial<EtatTunnel>): EtatTunnel => ({
    ...etatResidentiel(), mode: 'industriel', trancheFacture: '', factureHiverMad: null, ...over,
  });

  it('industriel à 300 000 kWh/mois sans estimation valide (aucun tarif) → gt10000', () => {
    const etat = etatPro({ factureProValeur: 300_000, factureProUnite: 'kwh', tarifProMadKwh: null });
    expect(trancheFactureProfessionnelle(etat)).toBe('gt10000');
    const { body, errors } = construireCorps(etat, { messages: MESSAGES });
    expect(body.billRange).toBe('gt10000');
    expect(errors).not.toHaveProperty('billRange');
  });

  it('même chose pour un commercial', () => {
    expect(trancheFactureProfessionnelle(etatPro({ mode: 'commercial', factureProValeur: 250_000, factureProUnite: 'kwh', tarifProMadKwh: null }))).toBe('gt10000');
  });

  it('sous le plafond technique et sans tarif : toujours pas de tranche fabriquée', () => {
    expect(trancheFactureProfessionnelle(etatPro({ factureProValeur: 150_000, factureProUnite: 'kwh', tarifProMadKwh: null }))).toBe('');
  });

  it('avec un tarif connu, la conversion habituelle est inchangée', () => {
    expect(trancheFactureProfessionnelle(etatPro({ factureProValeur: 50_000, factureProUnite: 'kwh', tarifProMadKwh: 1.4 }))).toBe('gt10000');
    expect(trancheFactureProfessionnelle(etatPro({ factureProValeur: 5_000, factureProUnite: 'mad' }))).not.toBe('');
  });

  for (const [lang, rel] of [
    ['FR', '../src/pages/devis/mon-toit.astro'],
    ['EN', '../src/pages/en/devis/mon-toit.astro'],
    ['AR', '../src/pages/ar/devis/mon-toit.astro'],
  ] as const) {
    const src = lireSourceTunnel(fileURLToPath(new URL(rel, import.meta.url)));
    it(`${lang} — plus de « 1,01 » ; tarif périmé remis à null ; erreur de tranche sur le champ visible`, () => {
      expect(src).not.toMatch(/1[,.]01/);
      expect(src).toContain('lastProTarifMadKwh = null;');
      expect(src).toMatch(/if \(isProMode\(mode\)\) setFieldError\(proBillId\(\), proBillErrId\(\)/);
    });
    it(`${lang} — le bloc pro n'écrit plus ni payload chiffré ni libellé WhatsApp (kWc, économie)`, () => {
      const debut = src.indexOf('estimateShown = null; // CIW404 — aucun chiffre vers le CRM');
      expect(debut).toBeGreaterThan(-1);
      const fin = src.indexOf('announceEstimate(', debut);
      const apres = src.slice(debut, fin);
      expect(apres).not.toMatch(/lastSavingsLabel = (?!'')/);
      expect(apres).not.toMatch(/lastKwcLabel = (?!'')/);
      expect(src.match(/estimateShown = null; \/\/ CIW404 — aucun chiffre vers le CRM/g)?.length).toBe(2);
      expect(src).not.toMatch(/s\.ecoMadYearLow = est\.ecoAnnuelleMadLow/);
      expect(src).not.toMatch(/s\.paybackLabel = rLabel/);
    });
  }
});

// CIW410 — la tension, l'activité et les équipes ne partent comme DÉCLARÉES que si
// le visiteur les a touchées : BT et « Journée » sont présélectionnés VISIBLEMENT
// (WJ123) et ne doivent pas se confondre avec une réponse.
describe('CIW410 — tensionSource et activityProfile : déclaré seulement si touché', () => {
  const industriel = (extra: Partial<EtatTunnel> = {}) =>
    corps({ ...etatResidentiel(), mode: 'industriel', tension: 'bt', activite: 'day', ...extra });

  it('industriel SANS clic : tensionSource « defaut_visible », pas d’activityProfile, BT toujours émise', () => {
    const b = industriel();
    expect(b.tensionSource).toBe('defaut_visible');
    expect(b.tensionRaccordement).toBe('bt');
    expect(b).not.toHaveProperty('activityProfile');
  });

  it('clic sur MT (ou BT) : tensionSource « touchee »', () => {
    const mt = industriel({ tension: 'mt', tensionTouchee: true });
    expect(mt.tensionRaccordement).toBe('mt');
    expect(mt.tensionSource).toBe('touchee');
    expect(industriel({ tensionTouchee: true }).tensionSource).toBe('touchee');
  });

  it('activité touchée : activityProfile part ; équipes inchangées (déjà sans défaut)', () => {
    const b = industriel({ activite: 'continuous', activiteTouchee: true, equipes: '3x8' });
    expect(b.activityProfile).toBe('continuous');
    expect(b.equipes).toBe('3x8');
    expect(industriel({ equipes: '' })).not.toHaveProperty('equipes');
  });

  it('jamais de tensionSource hors panneau industriel (commercial, résidentiel, agricole)', () => {
    for (const mode of ['commercial', 'residentiel', 'agricole'] as const) {
      const b = corps({ ...etatResidentiel(), mode, tension: 'bt', tensionTouchee: true });
      expect(b, mode).not.toHaveProperty('tensionSource');
    }
  });

  it('la liste blanche de lead.ts accepte tensionSource et écarte toute autre valeur', async () => {
    const { validateLead } = await import('../src/lib/lead');
    const base = { ...corps(etatResidentiel()) } as Record<string, unknown>;
    const ok = validateLead({ ...base, tensionSource: 'touchee' });
    expect(ok.lead.tensionSource).toBe('touchee');
    expect(validateLead({ ...base, tensionSource: 'defaut_visible' }).lead.tensionSource).toBe('defaut_visible');
    expect(validateLead({ ...base, tensionSource: 'declare' }).lead.tensionSource).toBeUndefined();
  });

  it('le registre déclare la clé du contrat CIQ400 (tunnel_webhook_keys.json)', async () => {
    const { readFileSync } = await import('node:fs');
    const { fileURLToPath } = await import('node:url');
    const contrat = JSON.parse(readFileSync(
      fileURLToPath(new URL('../../../backend/django_core/apps/crm/contract_samples/tunnel_webhook_keys.json', import.meta.url)),
      'utf-8',
    )) as { ajout_ciq400: { cle_nouvelle: { tensionSource: { cle_registre: string; groupe: string; valeurs: string[] } } } };
    const c = contrat.ajout_ciq400.cle_nouvelle.tensionSource;
    expect(CHAMPS_TUNNEL.some((d) => d.cle === c.cle_registre && d.webhookKey === 'tensionSource')).toBe(true);
    expect(c.groupe).toBe('G_PRO');
    expect(c.valeurs).toEqual(['touchee', 'defaut_visible']);
  });
});

// ———————————————————————————————————————————————————————————————————————————
// WEBERR-TUNNEL-PAYBACK-FR — le libellé d'amortissement envoyé au CRM suit la
// langue de la page : les bandes (`billRange`) le portent en français, une page
// EN/AR envoyait « 4 à 6 ans ». Une seule source : les nombres de la bande.
// ———————————————————————————————————————————————————————————————————————————
import { ERREURS, libelleRetourLocale } from '../src/lib/tunnel/i18n';
import { BILL_RANGES, LOCAL_PAYBACK_BY_KWC, localEstimateBand } from '../src/lib/billRange';

describe('WEBERR-TUNNEL-PAYBACK-FR — estimateShown.paybackLabel dans la langue de la page', () => {
  const avec = (messages: MessagesErreurs) => construireCorps(
    { ...etatResidentiel(), estimationAffichee: { kwc: 6, paybackLabel: '4 à 6 ans' } }, { messages },
  ).body.estimateShown as Record<string, unknown>;

  it('FR garde « 4 à 6 ans », EN envoie « 4 – 6 years », AR « 4 – 6 سنة » — chiffres inchangés', () => {
    expect(avec(ERREURS.fr)).toEqual({ kwc: 6, paybackLabel: '4 à 6 ans' });
    expect(avec(ERREURS.en)).toEqual({ kwc: 6, paybackLabel: '4 – 6 years' });
    expect(avec(ERREURS.ar)).toEqual({ kwc: 6, paybackLabel: '4 – 6 سنة' });
  });

  it('chaque libellé de bande billRange se traduit (aucun reste en français)', () => {
    const libelles = [
      ...BILL_RANGES.map((r) => localEstimateBand(r.id).paybackLabel),
      ...LOCAL_PAYBACK_BY_KWC.map((h) => h.paybackLabel),
    ];
    for (const l of libelles) {
      expect(libelleRetourLocale(l, 'en')).toMatch(/^\d+ – \d+ years$/);
      expect(libelleRetourLocale(l, 'ar')).toMatch(/^\d+ – \d+ سنة$/);
      expect(libelleRetourLocale(l, 'fr')).toBe(l);
    }
  });

  it('un libellé déjà localisé (parcours pro) ou inconnu passe tel quel — jamais réécrit', () => {
    expect(libelleRetourLocale('3 – 5 years', 'en')).toBe('3 – 5 years');
    expect(libelleRetourLocale('8 سنة', 'ar')).toBe('8 سنة');
    expect(avec(MESSAGES).paybackLabel).toBe('4 à 6 ans');
  });
});

// ———————————————————————————————————————————————————————————————————————————
// RWEB17-M7 — `lireEtatTunnel` (lib/tunnel/validation.ts) : sur un DOM rempli
// comme chaque parcours des goldens tunnelExecution, `construireCorps` rend le
// corps du golden (jetons masqués), dans les trois locales.
// ———————————————————————————————————————————————————————————————————————————
import { JSDOM } from 'jsdom';
import { readFileSync as lireGolden } from 'node:fs';
import { dirname, join as joinM7 } from 'node:path';
import { creerContexte } from '../src/lib/tunnel/contexte';
import { creerDom } from '../src/lib/tunnel/dom';
import { creerEtat, type LocaleTunnel as LocaleM7 } from '../src/lib/tunnel/etat';
import { installerValidation } from '../src/lib/tunnel/validation';

const IDS_M7 = [
  'mt-name', 'mt-phone', 'mt-city', 'mt-email', 'mt-consent', 'mt-contact-phone', 'mt-facture-hiver', 'mt-bill',
  'mt-raison-sociale', 'mt-surface-m2', 'mt-profondeur', 'mt-hmt', 'mt-water-need', 'mt-heures-pompage', 'mt-culture',
  'mt-surface-ha', 'mt-fuel-spend', 'mt-equip-ve', 'mt-equip-ve-km', 'mt-hp', 'mt-pro-bill', 'mt-cc-bill',
];
interface ParcoursM7 {
  champs: Record<string, string>; coches: string[]; touche?: string[];
  etat: Record<string, unknown>; proBillId?: string; proUnite?: string;
  tracking?: Record<string, string>; consentement?: boolean;
}
const CONTACT_M7 = { 'mt-name': 'Karim Benali', 'mt-phone': '0612345678', 'mt-city': 'Casablanca, Maarif', 'mt-email': 'karim@example.com' };
const PARCOURS_M7: Record<string, ParcoursM7> = {
  residentiel: {
    champs: { ...CONTACT_M7, 'mt-facture-hiver': '1800', 'mt-bill': '1500-3000', 'mt-equip-ve-km': '250' },
    coches: ['mt-consent', 'mt-contact-phone', 'mt-equip-ve'],
    etat: { mode: 'residentiel', occupationJour: 'present' }, consentement: true,
    tracking: { fbclid: 'fb.1.123', utm_source: 'facebook', utm_campaign: 'toit-casa' },
  },
  residentiel_tranche: {
    champs: { ...CONTACT_M7, 'mt-bill': '1500-3000' }, coches: ['mt-consent'], etat: { mode: 'residentiel' },
  },
  industriel: {
    champs: { ...CONTACT_M7, 'mt-pro-bill': '42000', 'mt-surface-m2': '900', 'mt-raison-sociale': 'Atlas Plast SARL' },
    coches: ['mt-consent'], proBillId: 'mt-pro-bill', proUnite: 'mad',
    etat: { mode: 'industriel', tension: 'mt', tensionTouched: true, activity: 'continuous', activityTouched: true, equipes: '3x8', surfaceType: 'terrasse' },
  },
  commercial: {
    champs: { ...CONTACT_M7, 'mt-cc-bill': '9000', 'mt-raison-sociale': 'Hôtel Les Palmiers' },
    coches: ['mt-consent'], proBillId: 'mt-cc-bill', proUnite: 'kwh',
    etat: { mode: 'commercial', commercialCategory: 'hotel', lastProTarifMadKwh: 1.3 },
  },
  agricole: {
    champs: { ...CONTACT_M7, 'mt-profondeur': '60', 'mt-hmt': '85', 'mt-water-need': '30', 'mt-heures-pompage': '9', 'mt-culture': 'agrumes', 'mt-surface-ha': '4', 'mt-fuel-spend': '2500' },
    coches: ['mt-consent'], touche: ['mt-heures-pompage'],
    etat: { mode: 'agricole', waterSource: 'forage', regionAgricole: 'souss-massa' },
  },
};

describe('RWEB17-M7 — lireEtatTunnel → construireCorps = corps des goldens tunnelExecution', () => {
  // Ce module reste en environnement node (autres tests) : le DOM est un JSDOM local.
  beforeEach(() => {
    const dom = new JSDOM('<!doctype html><body></body>', { url: 'https://taqinor.ma/devis/mon-toit' });
    dom.window.matchMedia = (() => ({ matches: false })) as unknown as typeof dom.window.matchMedia;
    vi.stubGlobal('window', dom.window);
    vi.stubGlobal('document', dom.window.document);
    vi.stubGlobal('sessionStorage', dom.window.sessionStorage);
    vi.stubGlobal('localStorage', dom.window.localStorage);
  });
  afterEach(() => vi.unstubAllGlobals());

  // Fragment minimal : validation d'étape et blur, messages de CHAQUE locale.
  const MESSAGES_M7: Record<LocaleM7, { type: string; nom: string; facture: string }> = {
    fr: { type: 'Choisissez votre type de projet pour continuer.', nom: 'Nom complet requis', facture: 'Indiquez votre facture : montant exact ou tranche.' },
    en: { type: 'Choose your project type to continue.', nom: 'Full name required', facture: 'Enter your bill: exact amount or a range.' },
    ar: { type: 'اختاروا نوع مشروعكم للمتابعة.', nom: 'الاسم الكامل مطلوب', facture: 'أدخلوا فاتورتكم: المبلغ الدقيق أو شريحة.' },
  };
  for (const locale of ['fr', 'en', 'ar'] as LocaleM7[]) {
    it(`validateStep0/1 et blur — messages ${locale}`, () => {
      document.body.innerHTML = '<button class="mt-mode"></button><p id="mt-mode-err" hidden></p>'
        + '<input id="mt-name"><p id="mt-name-err" hidden></p>'
        + '<input id="mt-facture-hiver"><p id="mt-facture-hiver-err" hidden></p><select id="mt-bill"></select><p id="mt-bill-err" hidden></p>';
      (document.defaultView as unknown as { Element: typeof Element }).Element.prototype.scrollIntoView = () => {};
      const ctx = creerContexte(creerDom(document), creerEtat(null, locale), { locale, langueBasculable: locale !== 'en', formatNombre: String });
      ctx.crochets.installer('isProMode', () => false);
      const s = installerValidation(ctx, document);
      expect(s.validateStep0()).toBe(false);
      expect(document.getElementById('mt-mode-err')!.textContent).toBe(MESSAGES_M7[locale].type);
      ctx.etat.mode = 'residentiel';
      expect(s.validateStep0()).toBe(true);
      expect(s.validateStep1()).toBe(false);
      expect(document.getElementById('mt-facture-hiver-err')!.textContent).toBe(MESSAGES_M7[locale].facture);
      (document.getElementById('mt-name') as HTMLInputElement).value = 'x';
      document.getElementById('mt-name')!.dispatchEvent(new (document.defaultView as unknown as { Event: typeof Event }).Event('blur'));
      expect(document.getElementById('mt-name-err')!.textContent).toBe(MESSAGES_M7[locale].nom);
    });
  }
  for (const [nom, p] of Object.entries(PARCOURS_M7)) {
    for (const locale of ['fr', 'en', 'ar'] as LocaleM7[]) {
      it(`${nom} · ${locale}`, () => {
        const golden = JSON.parse(lireGolden(joinM7(dirname(fileURLToPath(import.meta.url)), '__snapshots__', 'tunnelExecution', `${nom}.${locale}.json`), 'utf-8'));
        sessionStorage.clear();
        localStorage.clear();
        if (p.consentement) localStorage.setItem('tq_consent', 'granted');
        for (const [k, v] of Object.entries(p.tracking ?? {})) sessionStorage.setItem('tq_' + k, v);
        const casesM7 = ['mt-consent', 'mt-contact-phone', 'mt-equip-ve'];
        document.body.innerHTML = IDS_M7.map((id) => `<input id="${id}"${casesM7.includes(id) ? ' type="checkbox"' : ''}>`).join('');
        for (const [id, v] of Object.entries(p.champs)) (document.getElementById(id) as HTMLInputElement).value = v;
        for (const id of p.coches) (document.getElementById(id) as HTMLInputElement).checked = true;
        for (const id of p.touche ?? []) document.getElementById(id)!.setAttribute('data-touche', '1');
        const etat = creerEtat(null, locale);
        Object.assign(etat, p.etat, { currentLang: locale === 'ar' ? 'ar' : 'fr', estimateShown: golden.estimateShown ?? null });
        const ctx = creerContexte(creerDom(document), etat, { locale, langueBasculable: locale !== 'en', formatNombre: (n) => String(n) });
        ctx.crochets.installer('langueActive', () => (locale === 'en' ? 'en' : etat.currentLang));
        ctx.crochets.installer('isProMode', (m: string) => m === 'industriel' || m === 'commercial');
        ctx.crochets.installer('proBillId', () => p.proBillId ?? 'mt-pro-bill');
        ctx.crochets.installer('proBillErrId', () => `${p.proBillId ?? 'mt-pro-bill'}-err`);
        ctx.crochets.installer('proBillUnit', () => p.proUnite ?? 'mad');
        ctx.crochets.installer('getOrCreateClientRef', () => 'TQ-ABCD1');
        ctx.crochets.installer('getOrCreateDedupTokens', () => ({ idempotencyKey: 'idem-12345678', eventId: 'evt-12345678' }));
        ctx.crochets.installer('readTrackingParams', () => p.tracking ?? {});
        const { corpsDuLead } = installerValidation(ctx, document);
        const { body, errors } = corpsDuLead();
        expect(errors).toEqual({});
        const masque: Record<string, unknown> = { ...body };
        for (const cle of ['idempotencyKey', 'eventId', 'clientRef', 'appareilId']) if (cle in masque) masque[cle] = `<${cle}>`;
        const trie = (o: Record<string, unknown>) => Object.fromEntries(Object.keys(o).sort().map((k) => [k, o[k]]));
        expect(trie(masque)).toEqual(trie(golden));
      });
    }
  }
});
