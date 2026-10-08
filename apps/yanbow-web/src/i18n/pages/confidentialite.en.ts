/** Privacy page dictionary (YBW27) — same keys as the FR. `{n}` is replaced by a registry value. */
import type { DictEn } from '../config';
import type { fr } from './confidentialite.fr';

export const en: DictEn<typeof fr> = {
  titre: 'Privacy',
  description: 'How the information sent through the meeting form is used, kept and protected.',
  h1: 'Privacy',
  langue: 'Language',
  responsable: {
    titre: 'Data controller',
    nom: 'Controller',
    siege: 'Address',
    contact: 'Contact for your rights',
  },
  donnees: {
    titre: 'Data collected',
    intro: 'Only the information in the meeting form is collected:',
    donnee: 'Data',
    finalite: 'Why',
    statut: 'Status',
    obligatoire: 'required',
    facultatif: 'optional',
    aucuneIp: 'No IP address or browser identifier is sent with your request.',
    aucunTraceur: 'The site sets no cookie and uses no tracker or audience measurement tool.',
  },
  finalite: {
    titre: 'Purpose',
    texte: 'Answer your meeting request.',
  },
  base: {
    titre: 'Legal basis',
    texte: 'Your consent, given by ticking the box in the form. You can withdraw it at any time by writing to the contact address above.',
  },
  destinataires: {
    titre: 'Recipients and processors',
    equipe: 'Your request is read by the team that answers it. The providers below are involved:',
    nom: 'Provider',
    role: 'Role',
    quand: 'When',
    pays: 'Country',
    conservation: 'Retention',
    jours: '{n} days at most',
    nonPrecise: 'not specified',
  },
  transferts: {
    titre: 'Transfers',
    texte: 'Your information may be processed in the United Kingdom, in the European Union (ERP server) and in Morocco.',
    garanties: 'Safeguards used:',
  },
  duree: {
    titre: 'Retention period',
    texte: '{n} after the last contact, your request is anonymised in the ERP: it no longer identifies you.',
  },
  droits: {
    titre: 'Your rights',
    loiMaroc: 'Moroccan law 09-08: rights of access, rectification and objection.',
    rgpd: 'GDPR (European Union) and UK GDPR (United Kingdom): rights of access, rectification, erasure, restriction, objection and portability, and withdrawal of consent at any time.',
    exercer: 'To exercise these rights, write to:',
  },
  reclamation: {
    titre: 'Complaints',
    texte: 'You can lodge a complaint with a data protection authority: the CNDP (Morocco), the CNIL (France), the ICO (United Kingdom) or the authority of your country in the European Union.',
  },
  representant: {
    titre: 'Representative in the European Union',
  },
  whatsapp: {
    titre: 'WhatsApp',
    texte: 'The WhatsApp button opens WhatsApp only if you click it: no data is sent before the click.',
  },
  prospection: {
    titre: 'No automated prospecting',
    texte: 'Your request triggers no automated prospecting or follow-up.',
  },
  foi: 'The French version of this page prevails.',
};
