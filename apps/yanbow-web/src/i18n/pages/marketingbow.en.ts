/**
 * MarketingBow page (YBW63) — same keys as the French one, translated from the
 * approved French (YBWM13, YBW70). No new statement.
 */
import type { DictEn } from '../config';
import type { fr } from './marketingbow.fr';

export const en: DictEn<typeof fr> = {
  titre: 'MarketingBow — advertising campaigns validated by a person',
  description:
    'MarketingBow: Meta campaigns created paused, every change proposed then approved by a person, guardrails and circuit breaker.',
  surtitre: 'For advertising campaigns',
  cta: 'Book a meeting',
  secondaire: 'See how it works',
  modules: {
    surtitre: 'How it works',
    titre: 'A person decides, always',
    pause: 'Everything is created paused',
    approbation: 'Propose, approve, apply',
    gardeFous: 'Guardrails and circuit breaker',
    textes: 'The figures in generated texts',
  },
  procedure: {
    surtitre: 'How we work',
    titre: 'Your account stays yours',
  },
  appel: {
    titre: 'Let’s see MarketingBow in a demonstration',
    bouton: 'Book a meeting',
  },
};
