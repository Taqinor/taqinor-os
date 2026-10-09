/**
 * Dictionnaire NEUTRE du tour design (YBW42) — le MÊME pour les trois
 * candidats `/_design/a|b|c` : seuls les jetons et la mise en page diffèrent.
 *
 * AUCUN texte final, aucun chiffre, aucune affirmation : chaque chaîne décrit
 * l'emplacement qu'elle occupe, à une longueur réaliste, pour juger la mise en
 * page. Le vrai texte est écrit après le choix du design (YBW44 → YBW61).
 * Supprimé avec les routes `/_design/*` par YBW44.
 */
export const fr = {
  meta: {
    titre: 'Tour design — accueil candidat (page privée)',
    description: 'Page privée de comparaison des candidats de design. Texte neutre, non définitif.',
  },
  candidats: {
    a: 'Candidat A — Encre et papier',
    b: 'Candidat B — Nuit',
    c: 'Candidat C — Continuité du deck',
  },
  ruban: 'Page privée de comparaison. Texte neutre, non définitif.',
  nav: {
    aria: 'Navigation principale',
    ariaMobile: 'Navigation (mobile)',
    menu: 'Menu',
    surMesure: 'Sur mesure',
    societe: 'Société',
    rdv: 'Prendre rendez-vous',
    langue: 'English',
  },
  hero: {
    surtitre: 'Surtitre court de l’accueil',
    titre: 'Titre principal de l’accueil, une phrase forte sur deux lignes',
    intro:
      'Paragraphe d’introduction : ce que construit la société, pour qui, et l’action proposée. Deux ou trois lignes, jamais plus. Le texte définitif est écrit après le choix du design.',
    cta: 'Prendre rendez-vous',
    secondaire: 'Découvrir les produits',
  },
  capture: {
    attente: 'Emplacement d’une capture produit',
    note: 'Vrai écran, société fictive, recadré sur la zone utile.',
  },
  produits: {
    surtitre: 'Produits',
    titre: 'Titre de la section produits, sur une ligne',
    intro: 'Une phrase qui présente les produits construits, sans chiffre ni promesse.',
  },
  produit: {
    surtitre: 'Produit',
    description:
      'Description courte du produit : à qui il s’adresse et ce qu’il fait, en deux ou trois lignes de texte simple.',
    point1: 'Première capacité du produit, décrite en une ligne',
    point2: 'Deuxième capacité, avec un mot plus précis',
    point3: 'Troisième capacité, la plus concrète des trois',
    lien: 'Parler de ce produit',
  },
  surMesure: {
    surtitre: 'Sur mesure',
    titre: 'Titre du bloc sur mesure : ce que la société construit pour une entreprise',
    texte:
      'Paragraphe sur la démarche : partir du besoin réel, montrer vite quelque chose qui fonctionne, puis l’exploiter ensemble.',
    etape1: 'Premier temps de la démarche',
    etape2: 'Deuxième temps',
    etape3: 'Troisième temps',
    etape4: 'Quatrième temps',
    detail: 'Une ligne qui précise ce temps.',
  },
  societe: {
    surtitre: 'Société',
    titre: 'Bloc société : le sens du nom et l’ancrage Maroc et France',
    texte:
      'Deux phrases sur la société, sans date, sans chiffre et sans portrait. La phrase sur l’entreprise d’installation viendra ici.',
  },
  rdv: {
    titre: 'Appel final : prendre rendez-vous',
    texte: 'Une phrase sur ce qui se passe après la demande : une réponse par une personne.',
    bouton: 'Prendre rendez-vous',
  },
  pied: {
    note: 'Pied de page. Les liens juridiques s’affichent dès que leurs pages sont complètes.',
    aria: 'Pied de page',
  },
} as const;
