/**
 * Dictionnaire de la page Confidentialité (YBW27). Libellés et phrases fixes
 * seulement : les identités viennent de `src/lib/legal.ts`, les données
 * collectées du registre `src/lib/rdv/champs.ts`, les destinataires du registre
 * `src/lib/subprocessors.ts`, la durée de `CONSERVATION_PROSPECTS`.
 * `{n}` est remplacé par une valeur de ces registres.
 */
export const fr = {
  titre: 'Confidentialité',
  description: 'Comment les informations envoyées par le formulaire de rendez-vous sont utilisées, conservées et protégées.',
  h1: 'Confidentialité',
  langue: 'Langue',
  responsable: {
    titre: 'Responsable du traitement',
    nom: 'Responsable',
    siege: 'Adresse',
    contact: 'Contact pour vos droits',
  },
  donnees: {
    titre: 'Données collectées',
    intro: 'Seules les informations du formulaire de rendez-vous sont collectées :',
    donnee: 'Donnée',
    finalite: 'Pourquoi',
    statut: 'Statut',
    obligatoire: 'obligatoire',
    facultatif: 'facultatif',
    aucuneIp: "Aucune adresse IP ni identifiant de navigateur n’est transmis avec votre demande.",
    aucunTraceur: "Le site ne dépose aucun cookie et n’utilise aucun traceur ni outil de mesure d’audience.",
  },
  finalite: {
    titre: 'Finalité',
    texte: 'Répondre à votre demande de rendez-vous.',
  },
  base: {
    titre: 'Base légale',
    texte: "Votre consentement, donné en cochant la case du formulaire. Vous pouvez le retirer à tout moment en écrivant à l’adresse de contact ci-dessus.",
  },
  destinataires: {
    titre: 'Destinataires et sous-traitants',
    equipe: "Votre demande est lue par l’équipe qui y répond. Les prestataires ci-dessous interviennent :",
    nom: 'Prestataire',
    role: 'Rôle',
    quand: 'Quand',
    pays: 'Pays',
    conservation: 'Conservation',
    jours: '{n} jours au plus',
    nonPrecise: 'non précisé',
  },
  transferts: {
    titre: 'Transferts',
    texte: "Vos informations peuvent être traitées au Royaume-Uni, dans l’Union européenne (serveur de l’ERP) et au Maroc.",
    garanties: 'Garanties utilisées :',
  },
  duree: {
    titre: 'Durée de conservation',
    texte: "{n} après le dernier contact, votre demande est anonymisée dans l’ERP : elle ne permet plus de vous identifier.",
  },
  droits: {
    titre: 'Vos droits',
    loiMaroc: "Loi marocaine 09-08 : droits d’accès, de rectification et d’opposition.",
    rgpd: "RGPD (Union européenne) et UK GDPR (Royaume-Uni) : droits d’accès, de rectification, d’effacement, de limitation, d’opposition et de portabilité, et retrait du consentement à tout moment.",
    exercer: 'Pour exercer ces droits, écrivez à :',
  },
  reclamation: {
    titre: 'Réclamation',
    texte: "Vous pouvez adresser une réclamation à une autorité de protection des données : la CNDP (Maroc), la CNIL (France), l’ICO (Royaume-Uni) ou l’autorité de votre pays dans l’Union européenne.",
  },
  representant: {
    titre: "Représentant dans l’Union européenne",
  },
  whatsapp: {
    titre: 'WhatsApp',
    texte: "Le bouton WhatsApp ouvre WhatsApp seulement si vous cliquez dessus : aucune donnée n’est transmise avant le clic.",
  },
  prospection: {
    titre: 'Aucune prospection automatique',
    texte: 'Votre demande ne déclenche aucune prospection ni relance automatique.',
  },
  foi: 'La version française de cette page fait foi.',
} as const;
