/**
 * SolarBow page (YBW62) — same keys as the French one, translated from the
 * approved French (YBWM13, YBW70). No new statement.
 */
import type { DictEn } from '../config';
import type { fr } from './solarbow.fr';

export const en: DictEn<typeof fr> = {
  titre: 'SolarBow — the software for solar installers',
  description:
    'SolarBow: prospects and follow-ups, panel layout, prior declaration, Enedis and Consuel files, quotes and commercial proposal.',
  surtitre: 'For solar installers',
  cta: 'Book a meeting',
  secondaire: 'See what SolarBow does',
  modules: {
    surtitre: 'What SolarBow does',
    titre: 'From first contact to the proposal',
    prospects: 'Prospects and follow-ups',
    calepinage: 'Panel layout',
    dossiers: 'Prior declaration, Enedis and Consuel files',
    devis: 'Quotes and proposal',
  },
  appel: {
    titre: 'Let’s see SolarBow on your projects',
    bouton: 'Book a meeting',
  },
};
