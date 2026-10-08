// ALEA4 (D-ALEA-4) — après un envoi réussi, ce que le client a ENVOYÉ devient
// son « vu » : le POST suivant le porte en `prefill_vu`, si bien que le
// serveur (`_sans_ecrasement_equipe`) ne réécrase pas une correction faite par
// l'équipe entre-temps sur un champ que le client n'a pas retouché.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  buildQuestionnairePostBody,
  prefillApresEnvoi,
} from '../src/lib/questionnaire';

describe('prefill_vu après un envoi réussi (ALEA4)', () => {
  it('après un envoi réussi, le corps du POST suivant porte prefill_vu = valeurs envoyées', () => {
    // Le client voit X (facture_hiver 500), envoie Y (800) : enregistré.
    const prefillGet = { facture_hiver: 500, conso_mensuelle_kwh: 300 };
    const body1 = buildQuestionnairePostBody(
      'energie', { facture_hiver: '800', conso_mensuelle_kwh: '300' }, null, undefined, prefillGet,
    );
    expect(body1.prefill_vu?.facture_hiver).toBe(500);

    const apres = prefillApresEnvoi(prefillGet, body1.reponses);
    expect(apres.facture_hiver).toBe(800);
    // L'équipe corrige 800→Z côté ERP ; le client retouche UN AUTRE champ.
    const body2 = buildQuestionnairePostBody(
      'energie', { facture_hiver: '800', conso_mensuelle_kwh: '350' }, null, undefined, apres,
    );
    expect(body2.prefill_vu?.facture_hiver).toBe(800); // = valeur renvoyée → retirée côté serveur
    expect(body2.reponses.conso_mensuelle_kwh).toBe(350);
  });

  it('ne mute pas le prefill reçu et ne touche pas les champs non envoyés', () => {
    const prefill = { facture_hiver: 500, email: 'a@b.ma' };
    const apres = prefillApresEnvoi(prefill, { facture_hiver: 800 });
    expect(prefill.facture_hiver).toBe(500);
    expect(apres).toEqual({ facture_hiver: 800, email: 'a@b.ma' });
  });

  it('la page applique la fusion après un postSection réussi', () => {
    const src = readFileSync(
      fileURLToPath(new URL('../src/pages/questionnaire/[token].astro', import.meta.url)),
      'utf8',
    );
    expect(src).toMatch(/init\.prefill\s*=\s*prefillApresEnvoi\(init\.prefill,\s*body\.reponses\)/);
  });
});
