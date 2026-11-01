// ENF19 — les cinq liens WhatsApp de la page contact (FR/EN/AR) : même numéro « leads »,
// textes pré-remplis TOUJOURS en français (ils arrivent à l'équipe commerciale francophone).
// Étaient recopiés à l'identique dans les trois pages ; aucun changement de texte.
import { WHATSAPP_LEADS } from './nap';
import { whatsappLink, regularizationWhatsappText } from './whatsapp';

export function contactWhatsappLinks() {
  return {
    // Étude solaire générale.
    waGeneral: whatsappLink(WHATSAPP_LEADS, 'Bonjour, je souhaite une étude pour une installation solaire.'),
    // Régularisation (loi 82-21 / article 33).
    waRegul: whatsappLink(WHATSAPP_LEADS, regularizationWhatsappText()),
    // W249 — rappel téléphonique : demande explicitement un rappel (plutôt qu'un devis en ligne).
    waRappel: whatsappLink(
      WHATSAPP_LEADS,
      'Bonjour, pouvez-vous me rappeler par téléphone pour parler de mon projet solaire ?',
    ),
    // W285 — visite d'un chantier réel avant de décider.
    waVisite: whatsappLink(
      WHATSAPP_LEADS,
      'Bonjour, je souhaite visiter une installation réelle Taqinor avant de me décider.',
    ),
    // W339 — SAV / panne d'un client existant, distinct des portes d'acquisition ci-dessus.
    waSav: whatsappLink(
      WHATSAPP_LEADS,
      'Bonjour, je suis déjà client Taqinor et je signale un problème sur mon installation existante (SAV). Merci de me recontacter.',
    ),
  };
}
