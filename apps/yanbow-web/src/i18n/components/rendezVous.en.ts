/** “Book a meeting” form (YBW55) — same keys as the FR. */
import type { DictEn } from '../config';
import type { fr } from './rendezVous.fr';

export const en: DictEn<typeof fr> = {
  formulaire: 'Meeting request',
  champs: {
    nom: 'Full name',
    societe: 'Company',
    email: 'Email',
    telephone: 'Phone (optional)',
    produit: 'Meeting topic',
    produitChoisir: 'Choose a topic',
    message: 'Message (optional)',
  },
  obligatoire: 'required',
  consentement: 'I agree that this information is used to answer my meeting request.',
  potDeMiel: 'Do not fill in this field',
  envoyer: 'Send the request',
  envoiEnCours: 'Sending',
  bandeau: 'Please check the following fields:',
  erreurReseau: 'The request could not be sent. Check your connection and try again.',
  erreurLimite: 'Too many requests at once. Please try again in a moment.',
  succesTitre: 'Request sent',
  succesTexte: 'Thank you. A person from the team will get back to you.',
  whatsapp: 'Message us on WhatsApp',
};
