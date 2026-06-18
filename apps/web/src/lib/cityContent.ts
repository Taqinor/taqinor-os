/**
 * Prose éditoriale PAR VILLE pour les pages `/installation-solaire-*`.
 *
 * Pourquoi ce module existe : la route `installation-solaire-[city].astro` est
 * une seule route dynamique. Sans contenu par ville, les cinq pages partagent
 * une prose identique — exactement ce que STYLE.md interdit (règle 1 :
 * « chaque formule signature n'apparaît qu'UNE fois » ; règle 2 : « chaque page
 * famille porte au moins un fait qui n'est qu'à elle »). On déporte donc la
 * prose ici, clé par clé, pour que chaque ville se lise comme écrite pour elle.
 *
 * INTÉGRITÉ : aucun chiffre inventé. Les seules données chiffrées admises
 * viennent de `realisations.ts` (kWc/production réels, ensoleillement indicatif
 * « ≈ » des CITIES) et de la géographie/climat publics et non controversés de
 * chaque ville. Pas de prix, pas de rendement promis, pas d'opérateur réseau
 * nommé — on cadre en régime / barème / étude.
 *
 * Clés = slugs de `CITIES` (casablanca, rabat, marrakech, tanger, agadir).
 */

export interface CityContent {
  /** Paragraphe d'accroche du hero (après le H1). */
  heroLead: string;
  /** Phrase qui replace l'ensoleillement indicatif dans le contexte de la ville. */
  sunshineContext: string;
  /** Les trois piliers de service, réexprimés DANS le contexte de la ville. */
  pillars: {
    /** Pilier « étude / dimensionnement » — angle propre à la ville. */
    study: { heading: string; body: string };
    /** Pilier « production mesurée / monitoring » — angle propre à la ville. */
    measure: { heading: string; body: string };
    /** Pilier « conformité loi 82-21 » — angle propre à la ville. */
    compliance: { heading: string; body: string };
  };
  /** Titre de la bande CTA finale (le « closer »), propre à la ville. */
  closer: string;
  /** <title> unique. */
  title: string;
  /** meta description unique. */
  description: string;
}

/**
 * Repli sûr pour tout slug sans entrée dédiée : prose neutre, sans fait
 * géographique inventé, qui reste conforme à STYLE.md. Le placeholder
 * `{intro}` (« à <ville> ») est remplacé par l'appelant.
 */
export const FALLBACK_CITY_CONTENT: CityContent = {
  heroLead:
    "Taqinor conçoit, pose et déclare des installations solaires {intro} et partout au Maroc. " +
    'On part de votre dernière facture, pas d’un catalogue : la consommation réelle fixe la puissance, ' +
    'et le devis ne vient qu’ensuite.',
  sunshineContext:
    'Cette durée d’ensoleillement situe le potentiel de la zone. Ce que produira vraiment votre toiture {intro} ' +
    'dépend de son orientation, de son ombrage et de sa surface utile — l’étude lit ces trois paramètres avant de chiffrer quoi que ce soit.',
  pillars: {
    study: {
      heading: 'Dimensionner avant de chiffrer',
      body:
        'On lit votre facture et votre toiture {intro}, puis on en déduit la puissance. ' +
        'Aucune référence n’est posée tant que le calcul ne l’a pas justifiée ; le fondateur, docteur-ingénieur, valide chaque étude.',
    },
    measure: {
      heading: 'Une production qu’on relève',
      body:
        'Chaque installation est suivie sur Deye Cloud, accès client compris. ' +
        'Vous lisez les kWh réellement produits mois après mois, au lieu de croire un chiffre commercial.',
    },
    compliance: {
      heading: 'Le dossier loi 82-21, déposé pour vous',
      body:
        'Déclaration ou régularisation : nous montons le dossier et le déposons. ' +
        '<a href="/loi-82-21" class="border-b border-brass-400 pb-0.5 font-semibold text-brass-300 transition-colors hover:text-brass-200">Voir les régimes →</a>',
    },
  },
  closer: 'Faites étudier votre toiture {intro} avant de signer quoi que ce soit.',
  title: 'Installation solaire {intro} — étude, pose et loi 82-21 | Taqinor',
  description:
    'Installation solaire {intro} : dimensionnement par l’ingénierie sur votre facture, pose, monitoring Deye Cloud et conformité loi 82-21. Étude gratuite.',
};

export const CITY_CONTENT: Record<string, CityContent> = {
  casablanca: {
    heroLead:
      'À Casablanca, nous avons déjà posé : une villa de 11,36 kWc face à la skyline produit 14 271 kWh par an, ' +
      'relevés sur Deye Cloud. C’est ce chantier-là, pas une brochure, qui dit ce qu’une toiture de la ville rend vraiment.',
    sunshineContext:
      'Sur la côte, l’air marin et la brume matinale tempèrent les pics : ces ≈ 2 950 h restent un ordre de grandeur, ' +
      'pas une garantie. La production réelle d’un toit casablancais se calcule sur son orientation et son ombrage, jamais sur la seule durée d’ensoleillement.',
    pillars: {
      study: {
        heading: 'Calculé sur votre consommation, pas standardisé',
        body:
          'Une villa du quartier d’affaires et un riad de l’ancienne médina n’ont ni le même toit ni la même facture. ' +
          'On dimensionne sur la vôtre ; le fondateur, docteur-ingénieur, signe l’étude avant la pose.',
      },
      measure: {
        heading: 'Les 14 271 kWh, on les relève',
        body:
          'Notre installation de 11,36 kWc à Casablanca est suivie sur Deye Cloud, accès client inclus — ' +
          'la même transparence sur chaque chantier de la ville : vous lisez la production, vous ne la prenez pas sur parole.',
      },
      compliance: {
        heading: 'Régime loi 82-21 monté et déposé',
        body:
          'Pour une installation casablancaise, déclaration ou régularisation, nous préparons le dossier et le déposons. ' +
          '<a href="/loi-82-21" class="border-b border-brass-400 pb-0.5 font-semibold text-brass-300 transition-colors hover:text-brass-200">Voir les régimes →</a>',
      },
    },
    closer: 'Votre toiture casablancaise mérite d’être chiffrée sur vos kWh, pas sur une moyenne.',
    title: 'Installation solaire à Casablanca — étude, pose et loi 82-21 | Taqinor',
    description:
      'Installation solaire à Casablanca : une villa de 11,36 kWc y produit 14 271 kWh/an, mesurés sur Deye Cloud. Étude dimensionnée sur votre facture, pose et déclaration loi 82-21.',
  },

  rabat: {
    heroLead:
      'Capitale administrative, Rabat additionne villas de l’Agdal, maisons de Hay Riad et toits-terrasses du bord de mer. ' +
      'Taqinor y intervient comme partout au Maroc : on lit d’abord votre facture, puis on dimensionne — le devis ne précède jamais le calcul.',
    sunshineContext:
      'Avec ≈ 2 900 h, le littoral atlantique de Rabat offre un potentiel solide sans la fournaise de l’intérieur. ' +
      'Mais c’est l’orientation de votre terrasse et l’ombre des immeubles voisins qui décident de la production, pas cette moyenne météo.',
    pillars: {
      study: {
        heading: 'L’étude lit la toiture rbatie',
        body:
          'Toits plats accessibles, copropriétés, contraintes d’urbanisme du centre : chaque cas se dimensionne à part. ' +
          'On part de vos relevés, jamais d’un kit posé d’avance — et le fondateur, docteur-ingénieur, valide.',
      },
      measure: {
        heading: 'Deye Cloud, du premier jour',
        body:
          'Sur chaque pose à Rabat, le monitoring Deye Cloud est ouvert avec votre accès. ' +
          'Vous suivez les kWh produits en continu ; un écart se voit, il ne se devine pas.',
      },
      compliance: {
        heading: 'Conformité loi 82-21 prise en charge',
        body:
          'Déclaration ou régularisation d’une installation à Rabat : nous montons et déposons le dossier. ' +
          '<a href="/loi-82-21" class="border-b border-brass-400 pb-0.5 font-semibold text-brass-300 transition-colors hover:text-brass-200">Voir les régimes →</a>',
      },
    },
    closer: 'À Rabat, faites dimensionner votre toiture par l’ingénierie avant d’engager un budget.',
    title: 'Installation solaire à Rabat — étude, pose et loi 82-21 | Taqinor',
    description:
      'Installation solaire à Rabat : Taqinor dimensionne sur votre facture, pose et déclare au titre de la loi 82-21. Monitoring Deye Cloud, chantiers réels mesurés dans la région.',
  },

  marrakech: {
    heroLead:
      'Marrakech compte parmi les villes les plus ensoleillées du pays : ≈ 3 000 h par an. ' +
      'Ce gisement est réel — reste à le convertir sans surdimensionner. Taqinor part de votre facture pour fixer la puissance juste, ni plus, ni moins.',
    sunshineContext:
      'L’intérieur sec et la forte chaleur estivale poussent la climatisation — et la facture diurne — vers le haut. ' +
      'Ces ≈ 3 000 h disent le potentiel ; la production effective dépend de votre toiture, de la poussière et de l’ombrage, que l’étude mesure une à une.',
    pillars: {
      study: {
        heading: 'Le surdimensionnement coûte cher, ici aussi',
        body:
          'Sous le soleil marrakchi, la tentation est de poser large. On résiste : la puissance suit votre consommation réelle, ' +
          'pas l’ensoleillement de la ville. Étude validée par le fondateur, docteur-ingénieur.',
      },
      measure: {
        heading: 'La chaleur, ça se surveille',
        body:
          'Forte température et poussière font baisser le rendement d’un panneau ; Deye Cloud le rend visible. ' +
          'Avec votre accès, vous voyez ce que la toiture produit vraiment l’été comme l’hiver.',
      },
      compliance: {
        heading: 'Dossier loi 82-21 monté de bout en bout',
        body:
          'Déclaration ou régularisation d’une installation à Marrakech : nous nous chargeons du dossier complet. ' +
          '<a href="/loi-82-21" class="border-b border-brass-400 pb-0.5 font-semibold text-brass-300 transition-colors hover:text-brass-200">Voir les régimes →</a>',
      },
    },
    closer: 'À Marrakech, le bon dimensionnement vaut mieux qu’un grand champ : faites étudier votre toiture.',
    title: 'Installation solaire à Marrakech — étude, pose et loi 82-21 | Taqinor',
    description:
      'Installation solaire à Marrakech : ≈ 3 000 h de soleil par an, mais on dimensionne sur votre facture, pas sur la météo. Pose, monitoring Deye Cloud et conformité loi 82-21.',
  },

  tanger: {
    heroLead:
      'Tanger reçoit ≈ 2 800 h de soleil par an — la valeur la plus basse de nos cinq villes, et un détroit balayé par le vent. ' +
      'Raison de plus pour calculer au lieu de promettre : Taqinor dimensionne votre installation sur votre facture, pas sur une moyenne flatteuse.',
    sunshineContext:
      'Plus au nord, plus humide, plus venté : le Nord tangérois ensoleille un peu moins que le centre du pays, et ces ≈ 2 800 h le reflètent. ' +
      'C’est précisément pourquoi l’orientation et l’inclinaison de votre toit pèsent ici davantage — l’étude les optimise.',
    pillars: {
      study: {
        heading: 'Moins de soleil : encore plus de calcul',
        body:
          'Quand le gisement est plus mesuré, chaque watt mal orienté se paie. On cale l’inclinaison et l’azimut sur votre toiture tangéroise, ' +
          'sur vos relevés — et le fondateur, docteur-ingénieur, valide avant la pose.',
      },
      measure: {
        heading: 'Du vent, mais des chiffres fermes',
        body:
          'Structure ancrée pour les rafales du détroit, production suivie sur Deye Cloud avec votre accès : ' +
          'vous lisez les kWh réels, mois après mois, sans avoir à les croire sur parole.',
      },
      compliance: {
        heading: 'Loi 82-21 : déclaration et dépôt',
        body:
          'Pour une installation à Tanger, déclaration ou régularisation, nous préparons et déposons le dossier. ' +
          '<a href="/loi-82-21" class="border-b border-brass-400 pb-0.5 font-semibold text-brass-300 transition-colors hover:text-brass-200">Voir les régimes →</a>',
      },
    },
    closer: 'À Tanger, un toit bien orienté vaut un grand champ mal posé : faisons l’étude d’abord.',
    title: 'Installation solaire à Tanger — étude, pose et loi 82-21 | Taqinor',
    description:
      'Installation solaire à Tanger : ≈ 2 800 h de soleil et un détroit venté — d’où un dimensionnement calculé au degré près sur votre facture. Pose, Deye Cloud et loi 82-21.',
  },

  agadir: {
    heroLead:
      'Agadir est la plus ensoleillée de nos cinq villes : ≈ 3 400 h par an sur le Souss. ' +
      'Le gisement est exceptionnel pour le pays — mais une installation se juge à ce qu’elle produit chez vous, pas au soleil de la baie. On dimensionne sur votre facture.',
    sunshineContext:
      'Climat semi-aride, ciel dégagé une grande partie de l’année : ces ≈ 3 400 h placent Agadir en tête sur le littoral. ' +
      'Reste que votre toiture, son orientation et son ombrage déterminent la production réelle — c’est ce que l’étude chiffre, le soleil ne suffit pas.',
    pillars: {
      study: {
        heading: 'Le meilleur gisement ne dispense pas de calculer',
        body:
          'Sous les ≈ 3 400 h du Souss, on pourrait être tenté de poser sans réfléchir. On dimensionne quand même sur votre consommation, ' +
          'pas sur le climat — étude validée par le fondateur, docteur-ingénieur.',
      },
      measure: {
        heading: 'Un fort potentiel, vérifié au compteur',
        body:
          'Beaucoup de soleil ne vaut que confirmé : chaque pose à Agadir est suivie sur Deye Cloud, accès client inclus. ' +
          'Vous lisez les kWh réellement produits, et l’écart éventuel se voit tout de suite.',
      },
      compliance: {
        heading: 'Dossier loi 82-21 pris en main',
        body:
          'Déclaration ou régularisation d’une installation à Agadir : nous montons et déposons le dossier pour vous. ' +
          '<a href="/loi-82-21" class="border-b border-brass-400 pb-0.5 font-semibold text-brass-300 transition-colors hover:text-brass-200">Voir les régimes →</a>',
      },
    },
    closer: 'À Agadir, le soleil est acquis ; ce qui compte, c’est le dimensionnement. Faites étudier votre toiture.',
    title: 'Installation solaire à Agadir — étude, pose et loi 82-21 | Taqinor',
    description:
      'Installation solaire à Agadir : ≈ 3 400 h de soleil par an, le meilleur gisement de nos villes — mais on dimensionne sur votre facture. Pose, monitoring Deye Cloud et loi 82-21.',
  },
};

/**
 * Renvoie la prose d'une ville par slug, avec repli sûr. Le placeholder
 * `{intro}` du repli est résolu par l'appelant (qui connaît `c.intro`).
 */
export const cityContentBySlug = (slug: string): CityContent =>
  CITY_CONTENT[slug] ?? FALLBACK_CITY_CONTENT;
