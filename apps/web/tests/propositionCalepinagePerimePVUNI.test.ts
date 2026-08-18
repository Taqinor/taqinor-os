// PVUNI — « Calepinage à rejouer » sous la vue 3D (fondateur, 18/08/2026).
//
// Incident : sur la proposition live DEV-202608-0007, la vue 3D montrait le
// calepinage joué pour un certain nombre de panneaux pendant que le bloc
// « Votre installation » (et le PDF) en annonçait un autre — deux comptes de
// panneaux sur une même page, et donc deux coûts, sans que rien ne le dise.
//
// La règle est celle du fondateur : UNE source de vérité (les lignes du devis),
// tout le monde y copie, et rien ne reste périmé en silence quand une info a
// changé. La page ne recalcule donc RIEN ici : le backend compare les deux
// comptes et sert `layout_stale` + `layout_nb_panneaux` ; la page se contente
// de les rendre, et seulement quand le drapeau est levé.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import type { ProposalResponse } from '../src/lib/proposition';

const PAGE = readFileSync(
  fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
  'utf-8',
);

describe('PVUNI — drapeau de calepinage périmé', () => {
  it('le drapeau est LU du payload, jamais recalculé côté page', () => {
    expect(PAGE).toContain("data?.layout_stale === true");
    expect(PAGE).toContain('data?.layout_nb_panneaux');
    // Aucun comptage local de panneaux n'a le droit d'alimenter ce drapeau :
    // deux comptes concurrents seraient exactement le bug qu'on répare.
    expect(PAGE).not.toContain('layoutStale = viewerModel');
  });

  it('le compte affiché n’est servi QUE lorsque le drapeau est levé', () => {
    // `layoutPanneaux` est null hors alerte : impossible d'afficher un nombre
    // de panneaux « du calepinage » sur un devis sain.
    expect(PAGE).toContain('const layoutPanneaux = layoutStale ?');
  });

  it('le libellé vit DANS la section 3D, après la légende', () => {
    const debutSection = PAGE.indexOf('id="roof3d"');
    const legende = PAGE.indexOf('aria-label="Légende de la vue 3D"');
    const label = PAGE.indexOf('id="roof3d-stale"');
    expect(debutSection).toBeGreaterThan(-1);
    expect(label).toBeGreaterThan(legende);
    expect(label).toBeGreaterThan(debutSection);
    // …et avant la section suivante de la page.
    expect(label).toBeLessThan(PAGE.indexOf('id="installation"'));
  });

  it('le bloc est CONDITIONNEL — absent du DOM sur un devis sain', () => {
    expect(PAGE).toContain('{layoutStale && (');
  });

  it('le libellé est trilingue, comme tout le reste de la page', () => {
    const idx = PAGE.indexOf('id="roof3d-stale"');
    const bloc = PAGE.slice(idx, idx + 900);
    expect(bloc).toContain('data-i18n');
    expect(bloc).toContain('data-fr=');
    expect(bloc).toContain('data-en=');
    expect(bloc).toContain('data-ar=');
  });

  it('le libellé dit QUEL chiffre fait foi — le devis, pas la vue', () => {
    const idx = PAGE.indexOf('id="roof3d-stale"');
    const bloc = PAGE.slice(idx, idx + 900);
    expect(bloc).toContain('Calepinage à rejouer');
    expect(bloc).toContain('suivent votre devis');
  });
});

describe('PVUNI — contrat de charge utile', () => {
  it('ProposalResponse accepte le drapeau et son compte', () => {
    const payload: ProposalResponse = {
      reference: 'DEV-202608-0007',
      date: '14/08/2026',
      client_name: 'Mohammed kasri',
      statut: 'brouillon',
      roof_image_url: null,
      layout_stale: true,
      layout_nb_panneaux: 9,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      quote: { nb_panneaux: 8 } as any,
    };
    expect(payload.layout_stale).toBe(true);
    expect(payload.layout_nb_panneaux).toBe(9);
    // La forme de l'incident : la 3D dit 9, les lignes disent 8.
    expect(payload.layout_nb_panneaux).not.toBe(payload.quote.nb_panneaux);
  });

  it('l’absence du drapeau reste un état valide (devis sans calepinage)', () => {
    const payload: ProposalResponse = {
      reference: 'DEV-1',
      date: '14/08/2026',
      client_name: 'X',
      statut: 'brouillon',
      roof_image_url: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      quote: {} as any,
    };
    expect(payload.layout_stale ?? false).toBe(false);
  });
});
