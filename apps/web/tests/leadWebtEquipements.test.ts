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

describe('mon-toit.astro — la case décochée omet la clé du corps envoyé (source pin)', () => {
  it('buildBody() gate chaque grandeur équipement sur la case cochée correspondante', () => {
    // Preuve que la page n'envoie JAMAIS une grandeur sans que la case ait
    // été cochée : chaque `equip_*_kw`/`equip_*_pieces`/`equip_*_km_semaine`
    // du corps est construit par un ternaire `checked ? num(...) : undefined`,
    // jamais un num() nu qui enverrait une saisie fantôme.
    expect(PAGE).toMatch(
      /equip_piscine_pompe_kw:\s*\(\$\('mt-equip-piscine'\)[^)]*\)\?\.checked \? \(num\('mt-equip-piscine-kw'\) \?\? undefined\) : undefined/,
    );
    expect(PAGE).toMatch(
      /equip_ve_km_semaine:\s*\(\$\('mt-equip-ve'\)[^)]*\)\?\.checked \? \(num\('mt-equip-ve-km'\) \?\? undefined\) : undefined/,
    );
    expect(PAGE).toMatch(
      /equip_clim_pieces:\s*\(\$\('mt-equip-clim'\)[^)]*\)\?\.checked \? \(num\('mt-equip-clim-pieces'\) \?\? undefined\) : undefined/,
    );
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
