/* VX154/VX156 — VOIX TAQINOR : une microcopie qui a un point de vue.
   ----------------------------------------------------------------------------
   Guide d'une page (à lire avant d'ajouter une chaîne) :
     • VOUVOIEMENT toujours ("vous", jamais "tu").
     • FIER DU SOLAIRE, sobre : on parle kWc, chantier, mise en service, panneaux
       — le vocabulaire métier, pas le jargon SaaS interchangeable ("workflow",
       "item", "onboarding").
     • CHALEUREUX mais BREF : une phrase, pas un paragraphe ; jamais familier,
       jamais exubérant. On reconnaît le travail réel (poser des panneaux, signer
       une affaire), on ne félicite pas pour un clic.
     • HONNÊTE : une erreur reste une erreur ; on rassure sans minimiser.
   Ce module N'EST PAS un rewrite de toute l'interface (VX45 possède la microcopie
   générale) : il porte SEULEMENT les ~6 moments à forte charge émotionnelle.

   NOTE d'intégration : chaque moment expose une chaîne prête à l'emploi que
   l'écran concerné importe (`import { voice } from '../../lib/voice'`). Le moment
   « première connexion » est câblé par <WelcomeMoment>. */

export const voice = {
  // 1) Première connexion (câblé par WelcomeMoment).
  welcome: {
    title: 'Bienvenue chez Taqinor',
    mission: 'Ici, chaque devis, chaque chantier et chaque mise en service font avancer le solaire au Maroc. On s’occupe de la paperasse — vous, des panneaux.',
    cta: 'Commencer',
    skip: 'Plus tard',
  },
  // 2) File de travail vide (rien en attente).
  emptyQueue: 'Tout est à jour — belle journée pour poser des panneaux.',
  // 3) Devis envoyé au client.
  devisSent: 'Devis envoyé. La balle est dans le camp du client.',
  // 4) Affaire signée (le moment le plus important de l’ERP).
  dealSigned: 'Affaire signée. Un toit de plus qui passe au solaire.',
  // 5) Chantier terminé / mis en service.
  chantierDone: 'Chantier livré. L’installation produit désormais ses kWh.',
  // 6) Erreur réseau (honnête, rassurant, sans minimiser).
  networkError: 'Connexion perdue. Vos saisies sont conservées et repartiront dès le retour du réseau.',
}

/* Les 6 clés de moment (dans l’ordre du guide) : sert de contrat testable —
   chaque moment DOIT porter une chaîne non vide. */
export const VOICE_MOMENTS = [
  'welcome',
  'emptyQueue',
  'devisSent',
  'dealSigned',
  'chantierDone',
  'networkError',
]
