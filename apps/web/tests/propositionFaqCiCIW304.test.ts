// CIW304 — FAQ d'un devis C&I : des questions d'entreprise, sans chiffre ni promesse, et plus
// « si je déménage ».
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { objectionFaq, syntheseCi, type ProposalResponse } from '../src/lib/proposition';

const texteDe = (faq: ReturnType<typeof objectionFaq>) =>
  faq.map((f) => [f.id, f.question, f.questionEn, f.questionAr, f.answer, f.answerEn, f.answerAr].join(' ')).join(' | ');
// chiffres latins ET arabes-indiens
const CHIFFRE = /[0-9٠-٩۰-۹]/;

describe('CIW304 — objectionFaq(mode) C&I', () => {
  for (const mode of ['industriel', 'commercial']) {
    it(`${mode} : ni « déménage » ni aucun chiffre, ni promesse d'aide`, () => {
      const t = texteDe(objectionFaq(mode));
      expect(t).not.toMatch(/déménag/i);
      expect(t).not.toMatch(/move house|relocat|moving/i);
      expect(t).not.toMatch(CHIFFRE);
      expect(t).not.toMatch(/subvention|aide|subsid|grant|دعم/i);
      expect(t).not.toMatch(/loi\s|law\s|القانون/i); // jamais la loi citée
    });

    it(`${mode} : les trois langues sont présentes sur chaque ligne`, () => {
      const faq = objectionFaq(mode);
      expect(faq.length).toBeGreaterThanOrEqual(5);
      for (const f of faq) {
        for (const champ of [f.question, f.questionEn, f.questionAr, f.answer, f.answerEn, f.answerAr]) {
          expect(typeof champ).toBe('string');
          expect(champ.trim().length).toBeGreaterThan(3);
        }
        expect(f.questionAr).toMatch(/[؀-ۿ]/);
        expect(f.answerAr).toMatch(/[؀-ۿ]/);
      }
    });
  }

  it('couvre TVA, travaux, coupure du réseau, raccordement et entretien', () => {
    const ids = objectionFaq('commercial').map((f) => f.id);
    for (const attendu of ['tva', 'travaux', 'coupure-reseau', 'raccordement', 'entretien']) {
      expect(ids).toContain(attendu);
    }
    const raccord = objectionFaq('industriel').find((f) => f.id === 'raccordement')!;
    expect(raccord.answer).toContain('TAQINOR prépare le dossier de raccordement et d’autorisations du site quand il est requis');
    const tva = objectionFaq('industriel').find((f) => f.id === 'tva')!;
    expect(tva.answer).toContain('à confirmer avec votre comptable');
  });

  it('le suivi de production n\'apparaît que si le délai est servi ; l\'entretien nomme l\'option O&M servie', () => {
    expect(objectionFaq('industriel').some((f) => f.id === 'suivi-production')).toBe(false);
    const p = {
      mode_installation: 'industriel',
      quote: {},
      synthese_ci: {
        services: {
          om_option: { statut: 'propose', libelle: 'Contrat O&M : nettoyages et inspection' },
          suivi_production: { delai_intervention: 48 },
        },
      },
    } as unknown as ProposalResponse;
    const faq = objectionFaq('industriel', syntheseCi(p));
    const suivi = faq.find((f) => f.id === 'suivi-production')!;
    expect(suivi.answer).toContain('48 h');
    expect(faq.find((f) => f.id === 'entretien')!.answer).toContain('Contrat O&M : nettoyages et inspection');
  });
});

describe('CIW304 — le résidentiel est inchangé', () => {
  it('sans mode, résidentiel ou agricole : la FAQ de propriétaire (déménagement inclus)', () => {
    for (const m of [undefined, null, 'residentiel', 'agricole']) {
      const ids = objectionFaq(m as string | undefined).map((f) => f.id);
      expect(ids).toContain('demenagement');
      expect(ids).toContain('panne-reseau');
    }
  });
  it('la page passe le mode et la synthèse C&I', () => {
    const page = readFileSync(fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)), 'utf-8');
    expect(page).toContain('const faq = objectionFaq(installMode, ci);');
  });
});
