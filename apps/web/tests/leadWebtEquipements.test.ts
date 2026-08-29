// L-WEBT — occupation_jour + équipements (script d'appel commercial,
// `crm.Lead`) sur /devis/mon-toit. Ces champs sont FACULTATIFS, jamais
// bloquants (même discipline WJ30 que le reste de lib/lead.ts) : une case
// décochée ne doit jamais devenir un booléen `false` fabriqué côté serveur.
//
// Ces tests couvrent le CONTRAT DE FIL (validateLead) — c'est lui qui
// détermine ce qui atteint réellement le CRM. L'interaction DOM (clic sur une
// silhouette → hidden input `occupation_jour`, case cochée → détail révélé)
// est câblée dans src/pages/devis/mon-toit.astro ; on en pince ici le
// SOURCE (comme l4EquipementsCourbe.test.ts le fait déjà pour la page
// proposition) pour prouver que buildBody() omet bien la clé tant que la
// case correspondante n'est pas cochée — le comportement visuel complet
// (survol, sélection, repli) reste couvert par la suite Playwright E1-16.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { validateLead } from '../src/lib/lead';
import { etatVide, type EtatTunnel } from '../src/lib/tunnel/champs';
import { construireCorps } from '../src/lib/tunnel/corps';

// mon-toit.astro is CRLF (Windows-authored) — normalize before pinning
// source snippets so this test is line-ending-agnostic.
const PAGE = readFileSync(
  fileURLToPath(new URL('../src/pages/devis/mon-toit.astro', import.meta.url)),
  'utf-8',
).replace(/\r\n/g, '\n');

const validBody = {
  fullName: 'Karim Benali',
  phone: '06 12 34 56 78',
  whatsappOptIn: true,
  city: 'Casablanca',
  roofType: 'villa',
  billRange: '1500-3000',
  consent: true,
};

describe('validateLead — occupation_jour (L-WEBT)', () => {
  it('accepte les trois valeurs servies par la sélection de silhouette', () => {
    for (const v of ['present', 'absent', 'partiel'] as const) {
      const r = validateLead({ ...validBody, occupation_jour: v });
      expect(r.ok).toBe(true);
      if (r.ok) expect(r.lead.occupation_jour).toBe(v);
    }
  });

  it('écarte une valeur hors vocabulaire (jamais bloquant, jamais une erreur)', () => {
    const r = validateLead({ ...validBody, occupation_jour: 'toute-la-journee' });
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.lead.occupation_jour).toBeUndefined();
  });

  it('absente de la saisie ⇒ absente du lead validé (jamais un défaut fabriqué ici)', () => {
    const r = validateLead(validBody);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.lead.occupation_jour).toBeUndefined();
  });
});

describe('validateLead — équipements du script d\'appel (L-WEBT)', () => {
  it('accepte piscine + sa puissance de pompe (kW)', () => {
    const r = validateLead({ ...validBody, equip_piscine: true, equip_piscine_pompe_kw: 1.1 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_piscine).toBe(true);
    expect(r.lead.equip_piscine_pompe_kw).toBe(1.1);
  });

  it('accepte véhicule électrique + km/semaine', () => {
    const r = validateLead({ ...validBody, equip_voiture_electrique: true, equip_ve_km_semaine: 150 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_voiture_electrique).toBe(true);
    expect(r.lead.equip_ve_km_semaine).toBe(150);
  });

  it('accepte climatisation + nombre de pièces (entier)', () => {
    const r = validateLead({ ...validBody, equip_clim: true, equip_clim_pieces: 3.9 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_clim).toBe(true);
    expect(r.lead.equip_clim_pieces).toBe(4); // arrondi — un nombre de pièces est un entier
  });

  it('accepte le chauffe-eau électrique (booléen seul — aucune couche/puissance/créneau)', () => {
    const r = validateLead({ ...validBody, equip_chauffe_eau_electrique: true });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_chauffe_eau_electrique).toBe(true);
  });

  it('un booléen équipement absent de la saisie reste ABSENT du lead — jamais `false` fabriqué', () => {
    const r = validateLead(validBody);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_piscine).toBeUndefined();
    expect(r.lead.equip_voiture_electrique).toBeUndefined();
    expect(r.lead.equip_clim).toBeUndefined();
    expect(r.lead.equip_chauffe_eau_electrique).toBeUndefined();
  });

  it('un `false` explicite reste écarté (le champ n\'est jamais qu\'un `true` ou absent)', () => {
    const r = validateLead({ ...validBody, equip_piscine: false, equip_clim: false });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_piscine).toBeUndefined();
    expect(r.lead.equip_clim).toBeUndefined();
  });

  it('une grandeur hors bornes est écartée (anti-garbage, jamais bloquant)', () => {
    const r = validateLead({ ...validBody, equip_piscine: true, equip_piscine_pompe_kw: -3 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_piscine).toBe(true);
    expect(r.lead.equip_piscine_pompe_kw).toBeUndefined();
  });
});

describe('validateLead — détails kW/créneau facultatifs (L-WEBT2, 24/08/2026)', () => {
  it('accepte le chauffe-eau : puissance + créneau', () => {
    const r = validateLead({
      ...validBody, equip_chauffe_eau_electrique: true,
      equip_chauffe_eau_kw: 2.4, equip_chauffe_eau_creneau: 'nuit',
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_chauffe_eau_kw).toBe(2.4);
    expect(r.lead.equip_chauffe_eau_creneau).toBe('nuit');
  });

  it('accepte le VE : puissance du chargeur + créneau', () => {
    const r = validateLead({
      ...validBody, equip_voiture_electrique: true, equip_ve_km_semaine: 150,
      equip_ve_chargeur_kw: 7.4, equip_ve_creneau: 'soir',
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_ve_chargeur_kw).toBe(7.4);
    expect(r.lead.equip_ve_creneau).toBe('soir');
  });

  it('accepte la clim : puissance réelle + créneau', () => {
    const r = validateLead({
      ...validBody, equip_clim: true, equip_clim_pieces: 3,
      equip_clim_kw: 3.5, equip_clim_creneau: 'matin',
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_clim_kw).toBe(3.5);
    expect(r.lead.equip_clim_creneau).toBe('matin');
  });

  it('accepte la piscine : heures/jour + créneau', () => {
    const r = validateLead({
      ...validBody, equip_piscine: true, equip_piscine_pompe_kw: 1.1,
      equip_piscine_heures_jour: 6.5, equip_piscine_creneau: 'soir',
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_piscine_heures_jour).toBe(6.5);
    expect(r.lead.equip_piscine_creneau).toBe('soir');
  });

  it('un créneau hors des 4 choix réels est écarté (jamais bloquant, jamais un défaut)', () => {
    const r = validateLead({
      ...validBody, equip_clim: true,
      equip_clim_creneau: 'minuit', equip_ve_creneau: 'apres_midi',
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_clim_creneau).toBeUndefined();
    expect(r.lead.equip_ve_creneau).toBeUndefined();
  });

  it('une puissance kW hors bornes (> 1000) est écartée', () => {
    const r = validateLead({ ...validBody, equip_clim: true, equip_clim_kw: 50_000 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_clim_kw).toBeUndefined();
  });

  it('des heures/jour piscine > 24 sont écartées (physiquement impossible)', () => {
    const r = validateLead({ ...validBody, equip_piscine: true, equip_piscine_heures_jour: 30 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_piscine_heures_jour).toBeUndefined();
  });

  it('absents de la saisie ⇒ absents du lead validé (jamais un défaut fabriqué)', () => {
    const r = validateLead(validBody);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.equip_chauffe_eau_kw).toBeUndefined();
    expect(r.lead.equip_chauffe_eau_creneau).toBeUndefined();
    expect(r.lead.equip_ve_chargeur_kw).toBeUndefined();
    expect(r.lead.equip_ve_creneau).toBeUndefined();
    expect(r.lead.equip_clim_kw).toBeUndefined();
    expect(r.lead.equip_clim_creneau).toBeUndefined();
    expect(r.lead.equip_piscine_heures_jour).toBeUndefined();
    expect(r.lead.equip_piscine_creneau).toBeUndefined();
  });
});

describe('tunnel — la case décochée omet la clé du corps envoyé', () => {
  // QJW5 — cette garde épinglait le TEXTE du ternaire `checked ? … : undefined`
  // dans le `buildBody()` de la page FR. Le corps venant désormais du registre
  // partagé (`src/lib/tunnel/champs.ts`), on épingle ce qui compte vraiment :
  // le COMPORTEMENT, et pour les trois locales à la fois.
  const corps = (etat: Partial<EtatTunnel>) =>
    construireCorps({ ...etatVide(), ...etat }, { messages: { nomComplet: 'Nom complet requis' } })
      .body;

  it('chaque grandeur équipement est gatée sur sa case cochée', () => {
    // Le cas réel : le visiteur coche, saisit, puis DÉCOCHE. La saisie reste
    // dans le champ masqué — elle ne doit jamais partir.
    const saisies: Partial<EtatTunnel> = {
      equipPiscinePompeKw: 1.1,
      equipVeKmSemaine: 150,
      equipClimPieces: 4,
    };
    const decoche = corps(saisies);
    expect(decoche).not.toHaveProperty('equip_piscine_pompe_kw');
    expect(decoche).not.toHaveProperty('equip_ve_km_semaine');
    expect(decoche).not.toHaveProperty('equip_clim_pieces');

    const coche = corps({
      ...saisies,
      equipPiscine: true,
      equipVoitureElectrique: true,
      equipClim: true,
    });
    expect(coche.equip_piscine_pompe_kw).toBe(1.1);
    expect(coche.equip_ve_km_semaine).toBe(150);
    expect(coche.equip_clim_pieces).toBe(4);
  });

  it("le hidden input occupation_jour existe et la sélection d'une silhouette l'alimente", () => {
    expect(PAGE).toContain('id="mt-occupation-jour" name="occupation_jour"');
    expect(PAGE).toContain("const hidden = $('mt-occupation-jour')");
    // La table de traduction OCC_TO_LEAD_FIELD est la SEULE couture entre les
    // identifiants d'affichage (presence_jour/absence_jour/presence_partielle,
    // lib/dayProfiles.ts) et le vocabulaire réel de crm.Lead.occupation_jour.
    expect(PAGE).toContain("presence_jour: 'present', absence_jour: 'absent', presence_partielle: 'partiel'");
  });

  it('les trois couleurs validées fondateur sont exactement celles câblées', () => {
    expect(PAGE).toContain("presence_jour: { stroke: '#2a78d6', dash: null, fill: 'rgba(42,120,214,0.10)' }");
    expect(PAGE).toContain("absence_jour: { stroke: '#eb6834', dash: '6,3' }");
    expect(PAGE).toContain("presence_partielle: { stroke: '#1baf7a', dash: '2,3' }");
  });
});

describe('mon-toit.astro — détails kW/créneau (L-WEBT2) gatés sur la case parente', () => {
  it('chaque détail kW/créneau est gaté sur sa case équipement', () => {
    // Même discipline que le bloc L-WEBT ci-dessus : jamais une saisie fantôme
    // héritée d'une case décochée après coup.
    const corps = (etat: Partial<EtatTunnel>) =>
      construireCorps({ ...etatVide(), ...etat }, { messages: { nomComplet: 'Nom complet requis' } })
        .body;
    const saisies: Partial<EtatTunnel> = {
      equipChauffeEauKw: 2.4, equipChauffeEauCreneau: 'nuit',
      equipVeChargeurKw: 7.4, equipVeCreneau: 'soir',
      equipClimKw: 3.5, equipClimCreneau: 'matin',
      equipPiscineHeuresJour: 6.5, equipPiscineCreneau: 'soir',
    };
    const decoche = corps(saisies);
    for (const cle of [
      'equip_chauffe_eau_kw', 'equip_chauffe_eau_creneau',
      'equip_ve_chargeur_kw', 'equip_ve_creneau',
      'equip_clim_kw', 'equip_clim_creneau',
      'equip_piscine_heures_jour', 'equip_piscine_creneau',
    ]) {
      expect(decoche, cle).not.toHaveProperty(cle);
    }

    const coche = corps({
      ...saisies,
      equipChauffeEau: true, equipVoitureElectrique: true,
      equipClim: true, equipPiscine: true,
    });
    expect(coche.equip_chauffe_eau_kw).toBe(2.4);
    expect(coche.equip_chauffe_eau_creneau).toBe('nuit');
    expect(coche.equip_ve_chargeur_kw).toBe(7.4);
    expect(coche.equip_ve_creneau).toBe('soir');
    expect(coche.equip_clim_kw).toBe(3.5);
    expect(coche.equip_clim_creneau).toBe('matin');
    expect(coche.equip_piscine_heures_jour).toBe(6.5);
    expect(coche.equip_piscine_creneau).toBe('soir');
  });

  it('les 4 <select> créneau existent avec une option vide neutre par défaut', () => {
    for (const id of [
      'mt-equip-chauffe-eau-creneau', 'mt-equip-ve-creneau',
      'mt-equip-clim-creneau', 'mt-equip-piscine-creneau',
    ]) {
      const re = new RegExp(`<select id="${id}"[\\s\\S]*?<option value="">—</option>`);
      expect(PAGE).toMatch(re);
    }
  });

  it("le détail chauffe-eau (kW/créneau) est désormais révélé par le toggle EQUIP_TOGGLES", () => {
    expect(PAGE).toContain("{ checkId: 'mt-equip-chauffe-eau', detailId: 'mt-equip-chauffe-eau-kw' }");
  });
});
