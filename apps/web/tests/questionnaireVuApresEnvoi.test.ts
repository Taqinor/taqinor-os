// ALEA4 (D-ALEA-4) — après un envoi réussi, ce que le client a ENVOYÉ devient
// son « vu » : le POST suivant le porte en `prefill_vu`, si bien que le
// serveur (`_sans_ecrasement_equipe`) ne réécrase pas une correction faite par
// l'équipe entre-temps sur un champ que le client n'a pas retouché.
import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  buildQuestionnairePostBody,
  envoyerSectionQuestionnaire,
  prefillApresEnvoi,
  QUESTIONNAIRE_PROXY_PATH,
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

  // ALEA46 — l'envoi + la fusion sont jugés par leur COMPORTEMENT (seul le `fetch` est simulé).
  it('un envoi refusé ne fusionne pas le vu ; le POST suivant porte le vu du dernier envoi réussi', async () => {
    const statuts = [200, 400, 200];
    const corps: Array<Record<string, unknown>> = [];
    const fetchSimule = vi.fn(async (url: string, init?: RequestInit) => {
      expect(url).toBe(QUESTIONNAIRE_PROXY_PATH);
      corps.push(JSON.parse(String(init?.body)) as Record<string, unknown>);
      const status = statuts[corps.length - 1];
      return new Response(JSON.stringify(status === 200 ? { ok: true, enregistrees: ['energie'] } : { ok: false }), { status });
    });
    let prefill: Record<string, unknown> = { facture_hiver: 500, conso_mensuelle_kwh: 300 };
    const envoyer = async (raw: Record<string, string>) => {
      const body = buildQuestionnairePostBody('energie', raw, null, undefined, prefill);
      const envoi = await envoyerSectionQuestionnaire(fetchSimule as unknown as typeof fetch, 'jeton-1', body, prefill);
      prefill = envoi.prefill;
      return envoi.result;
    };
    expect((await envoyer({ facture_hiver: '800' })).ok).toBe(true);
    expect((await envoyer({ conso_mensuelle_kwh: '350' })).ok).toBe(false);
    expect((await envoyer({ conso_mensuelle_kwh: '350' })).ok).toBe(true);
    expect(corps[0].token).toBe('jeton-1');
    expect((corps[1].prefill_vu as Record<string, unknown>).facture_hiver).toBe(800);
    expect((corps[2].prefill_vu as Record<string, unknown>).conso_mensuelle_kwh).toBe(300); // le 400 n'a rien fusionné

    // Panne réseau : rien n'est fusionné, le message de la page est rendu.
    const panne = await envoyerSectionQuestionnaire(
      vi.fn(async () => { throw new TypeError('Failed to fetch'); }) as unknown as typeof fetch,
      'jeton-1', buildQuestionnairePostBody('energie', { facture_hiver: '900' }, null, undefined, prefill), prefill,
    );
    expect(panne.prefill).toBe(prefill);
    expect(panne.result).toEqual({ ok: false, enregistrees: [], detail: 'Connexion impossible. Vérifiez votre réseau et réessayez.' });
  });

  it('la page envoie par envoyerSectionQuestionnaire et en reprend le prefill', () => {
    const src = readFileSync(
      fileURLToPath(new URL('../src/pages/questionnaire/[token].astro', import.meta.url)),
      'utf8',
    );
    expect(src).toMatch(/const envoi = await envoyerSectionQuestionnaire\(fetch, init\.token, body, init\.prefill\);/);
    expect(src).toMatch(/init\.prefill = envoi\.prefill;/);
  });
});
