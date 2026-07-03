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
 * chaque ville. Pas de prix, pas de rendement promis — on cadre en régime /
 * barème / étude. Exception nommée et verrouillée (`CONTENT_SEO_NOTES.md` §2,
 * 2026-06-21) : le distributeur de Casablanca/Rabat/Tanger (Lydec/Redal/
 * Amendis) dans `delegataireNote`, jamais un tarif chiffré au-delà de ce qui y
 * est déjà publié.
 *
 * W328 — `roiNuance` situe chaque ville dans la bande « 3–7 ans » déjà
 * publiée sur `résidentiel.astro`/`billRange.ts` via son ensoleillement
 * indicatif relatif aux quatre autres, SANS jamais lui attribuer un nouveau
 * chiffre de retour : le payback reste dérivé de la facture/dimensionnement,
 * l'ensoleillement n'en fixe que le potentiel de production.
 *
 * Clés = slugs de `CITIES` (casablanca, rabat, marrakech, tanger, agadir).
 *
 * i18n (W67) : `cityContentBySlug(slug, locale)` renvoie la prose dans la
 * locale demandée. Le FR (`locale='fr'`, défaut) reste STRICTEMENT inchangé ;
 * EN et AR sont des traductions fidèles, ADDITIVES, sans aucun chiffre/claim
 * inventé ni altéré (kWc/kWh/heures « ≈ »/loi 82-21 identiques au chiffre près,
 * en chiffres latins). Le placeholder `{intro}` est conservé dans chaque locale
 * (résolu par l'appelant, qui passe la forme localisée « à <ville> » /
 * « in <city> » / « في <مدينة> »).
 */
import type { Locale } from '../i18n/config';

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
  /**
   * W328 — nuance la bande « retour sur investissement » (3–7 ans, chiffre
   * site-wide déjà utilisé sur `résidentiel.astro` — voir `billRange.ts`) pour
   * cette ville. Le payback dépend de la facture/dimensionnement, pas de la
   * seule durée d'ensoleillement (cf. `CITY_PAGES_NOTES.md`) : cette phrase
   * situe honnêtement la ville dans la bande via son ensoleillement indicatif,
   * sans jamais lui attribuer un nouveau chiffre de retour inventé.
   */
  roiNuance: string;
  /**
   * W328 — ligne de prudence tarifaire, présente UNIQUEMENT pour les 3 villes
   * à délégataire de distribution (Casablanca/Lydec, Rabat/Redal,
   * Tanger/Amendis — mapping verrouillé dans `CONTENT_SEO_NOTES.md` §2).
   * `undefined` pour Marrakech/Agadir (régie locale, pas de délégataire
   * nommé/vérifié dans ce dépôt — on n'invente pas le nom).
   */
  delegataireNote?: string;
  /**
   * W296 — pour les villes `hasLocalInstall:false` : positionnement
   * géographique honnête de la ville par rapport à la région Casablanca-Settat
   * (seule région où Taqinor a des chantiers réels — `CITY_PAGES_NOTES.md`),
   * en repère cardinal public (nord/sud/littoral), JAMAIS en kilomètres
   * inventés. `undefined` pour Casablanca (a un chantier local, section non
   * affichée) et le repli générique (aucune ville précise à situer).
   */
  nearestInstallNote?: string;
}

/** Une entrée ville = la même structure traduite dans les trois locales. */
type LocalizedCityContent = Record<Locale, CityContent>;

/**
 * Lien « Voir les régimes → » du pilier conformité, traduit par locale mais
 * pointant TOUJOURS vers la même cible `/loi-82-21` (un seul fichier source ;
 * le `localizeNavHref` du template gère le repli FR sans lien mort).
 */
const REGIMES_LINK: Record<Locale, string> = {
  fr: '<a href="/loi-82-21" class="border-b border-brass-400 pb-0.5 font-semibold text-brass-300 transition-colors hover:text-brass-200">Voir les régimes →</a>',
  en: '<a href="/loi-82-21" class="border-b border-brass-400 pb-0.5 font-semibold text-brass-300 transition-colors hover:text-brass-200">See the regimes →</a>',
  ar: '<a href="/loi-82-21" class="border-b border-brass-400 pb-0.5 font-semibold text-brass-300 transition-colors hover:text-brass-200">اطّلع على الأنظمة →</a>',
};

/**
 * Repli sûr pour tout slug sans entrée dédiée : prose neutre, sans fait
 * géographique inventé, qui reste conforme à STYLE.md. Le placeholder
 * `{intro}` (« à <ville> ») est remplacé par l'appelant.
 */
export const FALLBACK_CITY_CONTENT: LocalizedCityContent = {
  fr: {
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
          'Déclaration ou régularisation : nous montons le dossier et le déposons. ' + REGIMES_LINK.fr,
      },
    },
    closer: 'Faites étudier votre toiture {intro} avant de signer quoi que ce soit.',
    title: 'Installation solaire {intro} — étude, pose et loi 82-21 | Taqinor',
    description:
      'Installation solaire {intro} : dimensionnement par l’ingénierie sur votre facture, pose, monitoring Deye Cloud et conformité loi 82-21. Étude gratuite.',
    roiNuance:
      'Ce retour sur investissement dépend d’abord de votre facture et du dimensionnement retenu ; ' +
      'l’ensoleillement {intro} en fixe seulement le potentiel de production.',
  },
  en: {
    heroLead:
      'Taqinor designs, installs and declares solar systems {intro} and across Morocco. ' +
      'We start from your latest bill, not from a catalogue: real consumption sets the power, ' +
      'and the quote only comes after.',
    sunshineContext:
      'This sunshine figure places the potential of the area. What your roof will actually produce {intro} ' +
      'depends on its orientation, its shading and its usable surface — the assessment reads those three parameters before pricing anything.',
    pillars: {
      study: {
        heading: 'Size before you price',
        body:
          'We read your bill and your roof {intro}, then deduce the power from them. ' +
          'No equipment is fitted until the calculation has justified it; the founder, a doctor-engineer, validates every assessment.',
      },
      measure: {
        heading: 'A production we read off',
        body:
          'Every installation is monitored on Deye Cloud, client access included. ' +
          'You read the kWh actually produced month after month, instead of trusting a sales figure.',
      },
      compliance: {
        heading: 'The Law 82-21 file, filed for you',
        body:
          'Declaration or regularization: we build the file and submit it. ' + REGIMES_LINK.en,
      },
    },
    closer: 'Have your roof assessed {intro} before you sign anything.',
    title: 'Solar installation {intro} — assessment, install and Law 82-21 | Taqinor',
    description:
      'Solar installation {intro}: engineering-based sizing on your bill, install, Deye Cloud monitoring and Law 82-21 compliance. Free assessment.',
    roiNuance:
      'This payback depends first on your bill and the sizing chosen; ' +
      'the sunshine {intro} only sets the production potential.',
  },
  ar: {
    heroLead:
      'تصمّم تاكينور التركيبات الشمسية وتركّبها وتصرّح بها {intro} وفي كل أنحاء المغرب. ' +
      'ننطلق من آخر فاتورة لك، لا من كاطالوݣ: الاستهلاك الحقيقي هو الذي يحدّد القدرة، ' +
      'والثمن لا يأتي إلا بعد ذلك.',
    sunshineContext:
      'هذه المدة من الإشعاع الشمسي تحدّد إمكانات المنطقة. أمّا ما سينتجه سطحك فعلاً {intro} ' +
      'فيتوقّف على توجيهه وتظليله ومساحته المفيدة — والدراسة تقرأ هذه العوامل الثلاثة قبل تقدير أي ثمن.',
    pillars: {
      study: {
        heading: 'حدّد المقاس قبل تحديد الثمن',
        body:
          'نقرأ فاتورتك وسطحك {intro}، ثم نستنتج القدرة منهما. ' +
          'لا يُركَّب أي عتاد ما لم يبرّره الحساب؛ والمؤسّس، دكتور-مهندس، يصادق على كل دراسة.',
      },
      measure: {
        heading: 'إنتاج نقيسه فعلاً',
        body:
          'كل تركيبة تُراقَب على Deye Cloud، مع ولوج الزبون. ' +
          'تقرأ الكيلوواط-ساعة المنتَجة فعلاً شهراً بعد شهر، بدل تصديق رقم تجاري.',
      },
      compliance: {
        heading: 'ملف القانون 82-21، يُودَع نيابة عنك',
        body:
          'تصريح أو تسوية: نُعدّ الملف ونودعه. ' + REGIMES_LINK.ar,
      },
    },
    closer: 'ادرس سطحك {intro} قبل أن توقّع أي شيء.',
    title: 'تركيب شمسي {intro} — دراسة وتركيب والقانون 82-21 | Taqinor',
    description:
      'تركيب شمسي {intro}: تحديد المقاس بالهندسة انطلاقاً من فاتورتك، تركيب، مراقبة Deye Cloud والامتثال للقانون 82-21. دراسة مجانية.',
    roiNuance:
      'مدّة الاسترداد هذه تتوقّف أولاً على فاتورتك والمقاس المعتمد؛ ' +
      'الإشعاع الشمسي {intro} لا يحدّد سوى إمكان الإنتاج.',
  },
};

export const CITY_CONTENT: Record<string, LocalizedCityContent> = {
  casablanca: {
    fr: {
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
            REGIMES_LINK.fr,
        },
      },
      closer: 'Votre toiture casablancaise mérite d’être chiffrée sur vos kWh, pas sur une moyenne.',
      title: 'Installation solaire à Casablanca — étude, pose et loi 82-21 | Taqinor',
      description:
        'Installation solaire à Casablanca : une villa de 11,36 kWc y produit 14 271 kWh/an, mesurés sur Deye Cloud. Étude dimensionnée sur votre facture, pose et déclaration loi 82-21.',
      roiNuance:
        'Avec ≈ 2 950 h par an, Casablanca se situe dans la moyenne de nos cinq villes : ni le meilleur ni le plus faible ' +
        'gisement, ce qui place la plupart des toitures casablancaises au centre de la bande 3–7 ans — le dimensionnement ' +
        'sur votre facture reste ce qui la resserre vraiment.',
      delegataireNote:
        'Casablanca est distribuée par Lydec : votre facture porte son barème, pas un tarif générique — ' +
        'nous le confirmons sur votre relevé avant de chiffrer quoi que ce soit.',
    },
    en: {
      heroLead:
        'In Casablanca, we have already installed: an 11.36 kWc villa facing the skyline produces 14,271 kWh a year, ' +
        'read off Deye Cloud. It is that project, not a brochure, that tells what a roof in the city really yields.',
      sunshineContext:
        'On the coast, sea air and morning mist temper the peaks: those ≈ 2,950 h remain an order of magnitude, ' +
        'not a guarantee. The real output of a Casablanca roof is computed from its orientation and shading, never from sunshine duration alone.',
      pillars: {
        study: {
          heading: 'Computed on your consumption, not standardized',
          body:
            'A villa in the business district and a riad in the old medina share neither the same roof nor the same bill. ' +
            'We size on yours; the founder, a doctor-engineer, signs the assessment before the install.',
        },
        measure: {
          heading: 'The 14,271 kWh, we read them off',
          body:
            'Our 11.36 kWc installation in Casablanca is monitored on Deye Cloud, client access included — ' +
            'the same transparency on every project in the city: you read the production, you do not take it on trust.',
        },
        compliance: {
          heading: 'Law 82-21 regime built and filed',
          body:
            'For a Casablanca installation, declaration or regularization, we prepare the file and submit it. ' +
            REGIMES_LINK.en,
        },
      },
      closer: 'Your Casablanca roof deserves to be priced on your kWh, not on an average.',
      title: 'Solar installation in Casablanca — assessment, install and Law 82-21 | Taqinor',
      description:
        'Solar installation in Casablanca: an 11.36 kWc villa produces 14,271 kWh/year, measured on Deye Cloud. Assessment sized on your bill, install and Law 82-21 declaration.',
      roiNuance:
        'At ≈ 2,950 h a year, Casablanca sits mid-pack among our five cities: neither the best nor the weakest resource, ' +
        'which puts most Casablanca roofs near the centre of the 3–7 year band — sizing on your bill is what really narrows it.',
      delegataireNote:
        'Casablanca is served by Lydec: your bill carries its own tariff schedule, not a generic rate — ' +
        'we confirm it on your statement before pricing anything.',
    },
    ar: {
      heroLead:
        'في الدار البيضاء، ركّبنا بالفعل: فيلا بقدرة 11,36 kWc تواجه أفق المدينة تنتج 14 271 kWh في السنة، ' +
        'مقيسة على Deye Cloud. هذا الورش، لا أي مطوية، هو الذي يقول ما يعطيه سطح في المدينة حقاً.',
      sunshineContext:
        'على الساحل، يخفّف الهواء البحري والضباب الصباحي من الذُّرى: تبقى هذه الـ ≈ 2 950 ساعة رتبة قدر، ' +
        'لا ضماناً. الإنتاج الحقيقي لسطح بيضاوي يُحسب من توجيهه وتظليله، لا من مدة الإشعاع وحدها.',
      pillars: {
        study: {
          heading: 'محسوب على استهلاكك، لا نمطي',
          body:
            'فيلا في الحي التجاري ورياض في المدينة القديمة لا يشتركان لا في السطح ولا في الفاتورة. ' +
            'نحدّد المقاس على فاتورتك أنت؛ والمؤسّس، دكتور-مهندس، يوقّع الدراسة قبل التركيب.',
        },
        measure: {
          heading: 'الـ 14 271 kWh، نقيسها فعلاً',
          body:
            'تركيبتنا بقدرة 11,36 kWc في الدار البيضاء تُراقَب على Deye Cloud، مع ولوج الزبون — ' +
            'الشفافية نفسها في كل ورش بالمدينة: تقرأ الإنتاج، ولا تأخذه على عهدة الكلام.',
        },
        compliance: {
          heading: 'نظام القانون 82-21 مُعَدّ ومُودَع',
          body:
            'بالنسبة لتركيبة بيضاوية، تصريح أو تسوية، نُعدّ الملف ونودعه. ' +
            REGIMES_LINK.ar,
        },
      },
      closer: 'سطحك البيضاوي يستحقّ أن يُسعَّر على كيلوواط-ساعاتك، لا على معدّل.',
      title: 'تركيب شمسي في الدار البيضاء — دراسة وتركيب والقانون 82-21 | Taqinor',
      description:
        'تركيب شمسي في الدار البيضاء: فيلا بقدرة 11,36 kWc تنتج 14 271 kWh/سنة، مقيسة على Deye Cloud. دراسة محسوبة على فاتورتك، تركيب وتصريح القانون 82-21.',
      roiNuance:
        'بـ ≈ 2 950 ساعة في السنة، تقع الدار البيضاء في الوسط بين مدننا الخمس: لا الأفضل ولا الأضعف مخزوناً، ' +
        'ما يضع معظم أسطح الدار البيضاء قرب مركز بند 3–7 سنوات — والمقاس المحسوب على فاتورتك هو ما يضيّقه فعلاً.',
      delegataireNote:
        'الدار البيضاء توزّعها Lydec: فاتورتك تحمل بارِمها الخاص، لا تعريفة عامة — ' +
        'نتأكّد منه على كشف حسابك قبل تقدير أي ثمن.',
    },
  },

  rabat: {
    fr: {
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
            REGIMES_LINK.fr,
        },
      },
      closer: 'À Rabat, faites dimensionner votre toiture par l’ingénierie avant d’engager un budget.',
      title: 'Installation solaire à Rabat — étude, pose et loi 82-21 | Taqinor',
      description:
        'Installation solaire à Rabat : Taqinor dimensionne sur votre facture, pose et déclare au titre de la loi 82-21. Monitoring Deye Cloud, chantiers réels mesurés dans la région.',
      roiNuance:
        'Avec ≈ 2 900 h par an, Rabat a le deuxième gisement le plus mesuré de nos cinq villes : de quoi tenir dans la ' +
        'bande 3–7 ans, plutôt vers sa partie haute pour un dimensionnement identique — l’étude sur votre facture reste ' +
        'ce qui la précise réellement.',
      delegataireNote:
        'Rabat est distribuée par Redal : votre facture porte son barème propre — nous le vérifions sur votre relevé ' +
        'avant de chiffrer votre installation.',
      nearestInstallNote:
        'Rabat partage le même littoral atlantique que la région Casablanca-Settat, juste au sud, où se trouvent tous ' +
        'nos chantiers déjà en service : mêmes méthodes d’étude, même matériel tier-1, même monitoring Deye Cloud.',
    },
    en: {
      heroLead:
        'The administrative capital, Rabat adds up Agdal villas, Hay Riad houses and seafront roof terraces. ' +
        'Taqinor works here as everywhere in Morocco: first we read your bill, then we size — the quote never precedes the calculation.',
      sunshineContext:
        'At ≈ 2,900 h, Rabat’s Atlantic coast offers solid potential without the furnace of the interior. ' +
        'But it is the orientation of your terrace and the shade of neighbouring buildings that decide the output, not this weather average.',
      pillars: {
        study: {
          heading: 'The assessment reads the Rabat roof',
          body:
            'Accessible flat roofs, co-ownerships, downtown planning constraints: each case is sized on its own. ' +
            'We start from your readings, never from a kit fitted in advance — and the founder, a doctor-engineer, validates.',
        },
        measure: {
          heading: 'Deye Cloud, from day one',
          body:
            'On every install in Rabat, Deye Cloud monitoring is opened with your access. ' +
            'You follow the kWh produced continuously; a gap shows, it is not guessed.',
        },
        compliance: {
          heading: 'Law 82-21 compliance handled',
          body:
            'Declaration or regularization of an installation in Rabat: we build and submit the file. ' +
            REGIMES_LINK.en,
        },
      },
      closer: 'In Rabat, have your roof sized by engineering before you commit a budget.',
      title: 'Solar installation in Rabat — assessment, install and Law 82-21 | Taqinor',
      description:
        'Solar installation in Rabat: Taqinor sizes on your bill, installs and declares under Law 82-21. Deye Cloud monitoring, real projects measured in the region.',
      roiNuance:
        'At ≈ 2,900 h a year, Rabat has the second-lightest resource of our five cities: still well within the 3–7 year ' +
        'band, typically toward its upper half for an identical system size — the assessment on your bill is what really pins it down.',
      delegataireNote:
        'Rabat is served by Redal: your bill carries its own tariff schedule — we check it on your statement before pricing your installation.',
      nearestInstallNote:
        'Rabat shares the same Atlantic coastline as the Casablanca-Settat region, just to the south, where all our ' +
        'already-serviced installations are — same assessment methods, same tier-1 equipment, same Deye Cloud monitoring.',
    },
    ar: {
      heroLead:
        'العاصمة الإدارية، الرباط تجمع بين فيلات أگدال ومنازل حي الرياض وأسطح بحرية. ' +
        'تشتغل تاكينور هنا كما في كل أنحاء المغرب: نقرأ فاتورتك أولاً، ثم نحدّد المقاس — الثمن لا يسبق الحساب أبداً.',
      sunshineContext:
        'بـ ≈ 2 900 ساعة، يوفّر ساحل الرباط الأطلسي إمكانات صلبة دون قيظ الداخل. ' +
        'لكن توجيه سطحك وظلّ العمارات المجاورة هما من يقرّران الإنتاج، لا هذا المعدّل المناخي.',
      pillars: {
        study: {
          heading: 'الدراسة تقرأ السطح الرباطي',
          body:
            'أسطح مستوية يمكن الولوج إليها، ملكيات مشتركة، إكراهات التعمير في المركز: كل حالة تُحدَّد على حدة. ' +
            'ننطلق من قياساتك، لا من طقم مُركَّب سلفاً — والمؤسّس، دكتور-مهندس، يصادق.',
        },
        measure: {
          heading: 'Deye Cloud، منذ اليوم الأول',
          body:
            'في كل تركيب بالرباط، تُفتَح مراقبة Deye Cloud مع ولوجك. ' +
            'تتابع الكيلوواط-ساعة المنتَجة باستمرار؛ أي فارق يظهر، ولا يُخمَّن.',
        },
        compliance: {
          heading: 'الامتثال للقانون 82-21 متكفَّل به',
          body:
            'تصريح أو تسوية لتركيبة بالرباط: نُعدّ الملف ونودعه. ' +
            REGIMES_LINK.ar,
        },
      },
      closer: 'في الرباط، حدّد مقاس سطحك بالهندسة قبل أن تلتزم بميزانية.',
      title: 'تركيب شمسي في الرباط — دراسة وتركيب والقانون 82-21 | Taqinor',
      description:
        'تركيب شمسي في الرباط: تاكينور تحدّد المقاس على فاتورتك، تركّب وتصرّح بموجب القانون 82-21. مراقبة Deye Cloud، أوراش حقيقية مقيسة في الجهة.',
      roiNuance:
        'بـ ≈ 2 900 ساعة في السنة، تملك الرباط ثاني أخفّ مخزون بين مدننا الخمس: يبقى ضمن بند 3–7 سنوات، ' +
        'غالباً في نصفه الأعلى لمقاس مماثل — والدراسة على فاتورتك هي ما يحدّده فعلاً.',
      delegataireNote:
        'الرباط توزّعها Redal: فاتورتك تحمل بارِمها الخاص — نتحقّق منه على كشف حسابك قبل تقدير تركيبتك.',
      nearestInstallNote:
        'تشترك الرباط في الساحل الأطلسي نفسه مع جهة الدار البيضاء سطات، جنوباً مباشرة، حيث توجد كل تركيباتنا العاملة ' +
        'فعلاً — نفس مناهج الدراسة، نفس العتاد من الفئة الأولى، نفس مراقبة Deye Cloud.',
    },
  },

  marrakech: {
    fr: {
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
            REGIMES_LINK.fr,
        },
      },
      closer: 'À Marrakech, le bon dimensionnement vaut mieux qu’un grand champ : faites étudier votre toiture.',
      title: 'Installation solaire à Marrakech — étude, pose et loi 82-21 | Taqinor',
      description:
        'Installation solaire à Marrakech : ≈ 3 000 h de soleil par an, mais on dimensionne sur votre facture, pas sur la météo. Pose, monitoring Deye Cloud et conformité loi 82-21.',
      roiNuance:
        'Avec ≈ 3 000 h par an, Marrakech se classe au-dessus de la moyenne de nos cinq villes : un gisement qui tend la ' +
        'bande 3–7 ans vers sa partie basse pour un dimensionnement comparable — sans jamais dispenser l’étude de vérifier votre toiture.',
      nearestInstallNote:
        'Marrakech se trouve au sud-est de la région Casablanca-Settat, où sont concentrés tous nos chantiers déjà en ' +
        'service : mêmes méthodes d’étude, même matériel tier-1, même monitoring Deye Cloud, quelle que soit la distance.',
    },
    en: {
      heroLead:
        'Marrakech ranks among the sunniest cities in the country: ≈ 3,000 h a year. ' +
        'That resource is real — what remains is to convert it without oversizing. Taqinor starts from your bill to set the right power, no more, no less.',
      sunshineContext:
        'The dry interior and intense summer heat push air conditioning — and the daytime bill — upward. ' +
        'Those ≈ 3,000 h state the potential; actual output depends on your roof, the dust and the shading, which the assessment measures one by one.',
      pillars: {
        study: {
          heading: 'Oversizing is costly here too',
          body:
            'Under the Marrakech sun, the temptation is to install large. We resist: power follows your real consumption, ' +
            'not the city’s sunshine. Assessment validated by the founder, a doctor-engineer.',
        },
        measure: {
          heading: 'Heat is something you monitor',
          body:
            'High temperature and dust lower a panel’s yield; Deye Cloud makes it visible. ' +
            'With your access, you see what the roof really produces in summer as in winter.',
        },
        compliance: {
          heading: 'Law 82-21 file built end to end',
          body:
            'Declaration or regularization of an installation in Marrakech: we take charge of the complete file. ' +
            REGIMES_LINK.en,
        },
      },
      closer: 'In Marrakech, the right sizing beats a large array: have your roof assessed.',
      title: 'Solar installation in Marrakech — assessment, install and Law 82-21 | Taqinor',
      description:
        'Solar installation in Marrakech: ≈ 3,000 h of sun a year, but we size on your bill, not on the weather. Install, Deye Cloud monitoring and Law 82-21 compliance.',
      roiNuance:
        'At ≈ 3,000 h a year, Marrakech ranks above the average of our five cities: a resource that pulls the 3–7 year ' +
        'band toward its lower half for a comparable system size — never a substitute for checking your actual roof.',
      nearestInstallNote:
        'Marrakech lies south-east of the Casablanca-Settat region, where all our already-serviced installations are ' +
        'concentrated — same assessment methods, same tier-1 equipment, same Deye Cloud monitoring, whatever the distance.',
    },
    ar: {
      heroLead:
        'مراكش من أكثر مدن البلاد إشعاعاً شمسياً: ≈ 3 000 ساعة في السنة. ' +
        'هذا المخزون حقيقي — يبقى تحويله دون مبالغة في المقاس. تنطلق تاكينور من فاتورتك لتحديد القدرة المناسبة، لا أكثر ولا أقل.',
      sunshineContext:
        'الداخل الجاف والحرّ الصيفي الشديد يدفعان التكييف — والفاتورة النهارية — إلى الأعلى. ' +
        'هذه الـ ≈ 3 000 ساعة تقول الإمكان؛ أمّا الإنتاج الفعلي فيتوقّف على سطحك والغبار والتظليل، وهو ما تقيسه الدراسة واحداً واحداً.',
      pillars: {
        study: {
          heading: 'المبالغة في المقاس مكلفة هنا أيضاً',
          body:
            'تحت شمس مراكش، الإغراء أن تُركِّب على نطاق واسع. نحن نقاوم: القدرة تتبع استهلاكك الحقيقي، ' +
            'لا إشعاع المدينة. دراسة يصادق عليها المؤسّس، دكتور-مهندس.',
        },
        measure: {
          heading: 'الحرارة تُراقَب',
          body:
            'الحرارة العالية والغبار يخفضان مردود اللوح؛ وDeye Cloud يجعل ذلك مرئياً. ' +
            'مع ولوجك، ترى ما ينتجه السطح فعلاً صيفاً وشتاءً.',
        },
        compliance: {
          heading: 'ملف القانون 82-21 مُعَدّ من أوله إلى آخره',
          body:
            'تصريح أو تسوية لتركيبة بمراكش: نتكفّل بالملف الكامل. ' +
            REGIMES_LINK.ar,
        },
      },
      closer: 'في مراكش، المقاس الصحيح خير من حقل كبير: ادرس سطحك.',
      title: 'تركيب شمسي في مراكش — دراسة وتركيب والقانون 82-21 | Taqinor',
      description:
        'تركيب شمسي في مراكش: ≈ 3 000 ساعة شمس في السنة، لكننا نحدّد المقاس على فاتورتك، لا على الطقس. تركيب، مراقبة Deye Cloud والامتثال للقانون 82-21.',
      roiNuance:
        'بـ ≈ 3 000 ساعة في السنة، تُصنَّف مراكش فوق متوسط مدننا الخمس: مخزون يشدّ بند 3–7 سنوات نحو نصفه الأدنى ' +
        'لمقاس مماثل — دون أن يعفي ذلك أبداً من فحص سطحك فعلياً.',
      nearestInstallNote:
        'تقع مراكش جنوب شرق جهة الدار البيضاء سطات، حيث تتركّز كل تركيباتنا العاملة فعلاً — نفس مناهج الدراسة، ' +
        'نفس العتاد من الفئة الأولى، نفس مراقبة Deye Cloud، مهما كانت المسافة.',
    },
  },

  tanger: {
    fr: {
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
            REGIMES_LINK.fr,
        },
      },
      closer: 'À Tanger, un toit bien orienté vaut un grand champ mal posé : faisons l’étude d’abord.',
      title: 'Installation solaire à Tanger — étude, pose et loi 82-21 | Taqinor',
      description:
        'Installation solaire à Tanger : ≈ 2 800 h de soleil et un détroit venté — d’où un dimensionnement calculé au degré près sur votre facture. Pose, Deye Cloud et loi 82-21.',
      roiNuance:
        'Avec ≈ 2 800 h par an, Tanger a le gisement le plus mesuré de nos cinq villes : à dimensionnement égal, cela ' +
        'pousse plutôt vers la partie haute de la bande 3–7 ans — raison de plus pour caler l’orientation et l’inclinaison ' +
        'au lieu de compter sur la seule météo.',
      delegataireNote:
        'Tanger est distribuée par Amendis : votre facture porte son barème propre — nous le confirmons sur votre relevé ' +
        'avant de chiffrer votre installation.',
      nearestInstallNote:
        'Tanger se trouve au nord de la région Casablanca-Settat, où sont concentrés tous nos chantiers déjà en service : ' +
        'mêmes méthodes d’étude, même matériel tier-1, même monitoring Deye Cloud, quelle que soit la distance.',
    },
    en: {
      heroLead:
        'Tangier receives ≈ 2,800 h of sun a year — the lowest figure of our five cities, and a strait swept by wind. ' +
        'All the more reason to calculate rather than promise: Taqinor sizes your installation on your bill, not on a flattering average.',
      sunshineContext:
        'Further north, more humid, windier: the Tangier North gets a little less sun than the centre of the country, and those ≈ 2,800 h reflect it. ' +
        'That is precisely why the orientation and tilt of your roof weigh more here — the assessment optimizes them.',
      pillars: {
        study: {
          heading: 'Less sun: even more calculation',
          body:
            'When the resource is more measured, every misaligned watt is paid for. We set the tilt and azimuth on your Tangier roof, ' +
            'on your readings — and the founder, a doctor-engineer, validates before the install.',
        },
        measure: {
          heading: 'Wind, but firm figures',
          body:
            'Structure anchored for the gusts of the strait, production followed on Deye Cloud with your access: ' +
            'you read the real kWh, month after month, without having to take them on trust.',
        },
        compliance: {
          heading: 'Law 82-21: declaration and filing',
          body:
            'For an installation in Tangier, declaration or regularization, we prepare and submit the file. ' +
            REGIMES_LINK.en,
        },
      },
      closer: 'In Tangier, a well-oriented roof beats a large, poorly fitted array: let’s do the assessment first.',
      title: 'Solar installation in Tangier — assessment, install and Law 82-21 | Taqinor',
      description:
        'Solar installation in Tangier: ≈ 2,800 h of sun and a windy strait — hence sizing calculated to the degree on your bill. Install, Deye Cloud and Law 82-21.',
      roiNuance:
        'At ≈ 2,800 h a year, Tangier has the lightest resource of our five cities: for an identical system size, that ' +
        'leans toward the upper end of the 3–7 year band — one more reason to get the tilt and orientation right instead ' +
        'of counting on the weather alone.',
      delegataireNote:
        'Tangier is served by Amendis: your bill carries its own tariff schedule — we confirm it on your statement before pricing your installation.',
      nearestInstallNote:
        'Tangier lies north of the Casablanca-Settat region, where all our already-serviced installations are ' +
        'concentrated — same assessment methods, same tier-1 equipment, same Deye Cloud monitoring, whatever the distance.',
    },
    ar: {
      heroLead:
        'تتلقّى طنجة ≈ 2 800 ساعة شمس في السنة — أدنى قيمة بين مدننا الخمس، ومضيق يجتاحه الريح. ' +
        'سبب إضافي للحساب بدل الوعد: تحدّد تاكينور مقاس تركيبتك على فاتورتك، لا على معدّل مُغرٍ.',
      sunshineContext:
        'أكثر شمالاً، أكثر رطوبة، أكثر رياحاً: شمال طنجة أقل إشعاعاً قليلاً من وسط البلاد، وهذه الـ ≈ 2 800 ساعة تعكس ذلك. ' +
        'لهذا بالذات يزن توجيه سطحك وميله أكثر هنا — والدراسة تُحسّنهما.',
      pillars: {
        study: {
          heading: 'شمس أقل: حساب أكثر',
          body:
            'حين يكون المخزون أقل، كل واط سيّئ التوجيه يُدفَع ثمنه. نضبط الميل والسمت على سطحك الطنجي، ' +
            'على قياساتك — والمؤسّس، دكتور-مهندس، يصادق قبل التركيب.',
        },
        measure: {
          heading: 'رياح، لكن أرقام ثابتة',
          body:
            'بنية مُثبَّتة لهبّات المضيق، وإنتاج يُتابَع على Deye Cloud مع ولوجك: ' +
            'تقرأ الكيلوواط-ساعة الحقيقية، شهراً بعد شهر، دون أن تأخذها على عهدة الكلام.',
        },
        compliance: {
          heading: 'القانون 82-21: تصريح وإيداع',
          body:
            'بالنسبة لتركيبة بطنجة، تصريح أو تسوية، نُعدّ الملف ونودعه. ' +
            REGIMES_LINK.ar,
        },
      },
      closer: 'في طنجة، سطح حسن التوجيه خير من حقل كبير سيّئ التركيب: لنبدأ بالدراسة.',
      title: 'تركيب شمسي في طنجة — دراسة وتركيب والقانون 82-21 | Taqinor',
      description:
        'تركيب شمسي في طنجة: ≈ 2 800 ساعة شمس ومضيق ذو رياح — ومن ثَمّ مقاس محسوب بدقة الدرجة على فاتورتك. تركيب، Deye Cloud والقانون 82-21.',
      roiNuance:
        'بـ ≈ 2 800 ساعة في السنة، تملك طنجة أخفّ مخزون بين مدننا الخمس: لمقاس مماثل، يميل ذلك نحو الطرف الأعلى ' +
        'من بند 3–7 سنوات — سبب إضافي لضبط الميل والتوجيه بدل الاعتماد على الطقس وحده.',
      delegataireNote:
        'طنجة توزّعها Amendis: فاتورتك تحمل بارِمها الخاص — نتأكّد منه على كشف حسابك قبل تقدير تركيبتك.',
      nearestInstallNote:
        'تقع طنجة شمال جهة الدار البيضاء سطات، حيث تتركّز كل تركيباتنا العاملة فعلاً — نفس مناهج الدراسة، ' +
        'نفس العتاد من الفئة الأولى، نفس مراقبة Deye Cloud، مهما كانت المسافة.',
    },
  },

  agadir: {
    fr: {
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
            REGIMES_LINK.fr,
        },
      },
      closer: 'À Agadir, le soleil est acquis ; ce qui compte, c’est le dimensionnement. Faites étudier votre toiture.',
      title: 'Installation solaire à Agadir — étude, pose et loi 82-21 | Taqinor',
      description:
        'Installation solaire à Agadir : ≈ 3 400 h de soleil par an, le meilleur gisement de nos villes — mais on dimensionne sur votre facture. Pose, monitoring Deye Cloud et loi 82-21.',
      roiNuance:
        'Avec ≈ 3 400 h par an, Agadir a le meilleur gisement de nos cinq villes : à dimensionnement égal, cela pousse ' +
        'la bande 3–7 ans vers sa partie basse — un avantage réel, que seule l’étude sur votre facture transforme en chiffre exact.',
      nearestInstallNote:
        'Agadir se trouve au sud de la région Casablanca-Settat, où sont concentrés tous nos chantiers déjà en service : ' +
        'mêmes méthodes d’étude, même matériel tier-1, même monitoring Deye Cloud, quelle que soit la distance.',
    },
    en: {
      heroLead:
        'Agadir is the sunniest of our five cities: ≈ 3,400 h a year over the Souss. ' +
        'The resource is exceptional for the country — but an installation is judged by what it produces at your place, not by the sun over the bay. We size on your bill.',
      sunshineContext:
        'Semi-arid climate, clear sky for much of the year: those ≈ 3,400 h put Agadir at the top of the coast. ' +
        'Still, your roof, its orientation and its shading determine the real output — that is what the assessment quantifies; the sun is not enough.',
      pillars: {
        study: {
          heading: 'The best resource does not excuse you from calculating',
          body:
            'Under the ≈ 3,400 h of the Souss, one could be tempted to install without thinking. We still size on your consumption, ' +
            'not on the climate — assessment validated by the founder, a doctor-engineer.',
        },
        measure: {
          heading: 'High potential, verified at the meter',
          body:
            'A lot of sun only counts once confirmed: every install in Agadir is monitored on Deye Cloud, client access included. ' +
            'You read the kWh actually produced, and any gap shows at once.',
        },
        compliance: {
          heading: 'Law 82-21 file taken in hand',
          body:
            'Declaration or regularization of an installation in Agadir: we build and submit the file for you. ' +
            REGIMES_LINK.en,
        },
      },
      closer: 'In Agadir, the sun is a given; what counts is the sizing. Have your roof assessed.',
      title: 'Solar installation in Agadir — assessment, install and Law 82-21 | Taqinor',
      description:
        'Solar installation in Agadir: ≈ 3,400 h of sun a year, the best resource of our cities — but we size on your bill. Install, Deye Cloud monitoring and Law 82-21.',
      roiNuance:
        'At ≈ 3,400 h a year, Agadir has the best resource of our five cities: for an identical system size, that pulls ' +
        'the 3–7 year band toward its lower end — a real edge that only the assessment on your bill turns into an exact figure.',
      nearestInstallNote:
        'Agadir lies south of the Casablanca-Settat region, where all our already-serviced installations are ' +
        'concentrated — same assessment methods, same tier-1 equipment, same Deye Cloud monitoring, whatever the distance.',
    },
    ar: {
      heroLead:
        'أكادير هي الأكثر إشعاعاً بين مدننا الخمس: ≈ 3 400 ساعة في السنة فوق سوس. ' +
        'المخزون استثنائي بالنسبة للبلاد — لكن التركيبة تُحكَم بما تنتجه عندك، لا بشمس الخليج. نحدّد المقاس على فاتورتك.',
      sunshineContext:
        'مناخ شبه قاحل، سماء صافية جزءاً كبيراً من السنة: هذه الـ ≈ 3 400 ساعة تضع أكادير في صدارة الساحل. ' +
        'يبقى أنّ سطحك وتوجيهه وتظليله هي التي تحدّد الإنتاج الحقيقي — وهذا ما تقدّره الدراسة؛ الشمس وحدها لا تكفي.',
      pillars: {
        study: {
          heading: 'أفضل مخزون لا يعفي من الحساب',
          body:
            'تحت الـ ≈ 3 400 ساعة لسوس، قد يُغري المرءُ بالتركيب دون تفكير. ومع ذلك نحدّد المقاس على استهلاكك، ' +
            'لا على المناخ — دراسة يصادق عليها المؤسّس، دكتور-مهندس.',
        },
        measure: {
          heading: 'إمكان عالٍ، مُتحقَّق منه عند العدّاد',
          body:
            'الشمس الكثيرة لا تُحتسب إلا مُؤكَّدة: كل تركيب بأكادير يُراقَب على Deye Cloud، مع ولوج الزبون. ' +
            'تقرأ الكيلوواط-ساعة المنتَجة فعلاً، وأي فارق يظهر فوراً.',
        },
        compliance: {
          heading: 'ملف القانون 82-21 متكفَّل به',
          body:
            'تصريح أو تسوية لتركيبة بأكادير: نُعدّ الملف ونودعه نيابة عنك. ' +
            REGIMES_LINK.ar,
        },
      },
      closer: 'في أكادير، الشمس مضمونة؛ المهمّ هو المقاس. ادرس سطحك.',
      title: 'تركيب شمسي في أكادير — دراسة وتركيب والقانون 82-21 | Taqinor',
      description:
        'تركيب شمسي في أكادير: ≈ 3 400 ساعة شمس في السنة، أفضل مخزون بين مدننا — لكننا نحدّد المقاس على فاتورتك. تركيب، مراقبة Deye Cloud والقانون 82-21.',
      roiNuance:
        'بـ ≈ 3 400 ساعة في السنة، تملك أكادير أفضل مخزون بين مدننا الخمس: لمقاس مماثل، يشدّ ذلك بند 3–7 سنوات ' +
        'نحو طرفه الأدنى — ميزة حقيقية لا تتحوّل إلى رقم دقيق إلا بالدراسة على فاتورتك.',
      nearestInstallNote:
        'تقع أكادير جنوب جهة الدار البيضاء سطات، حيث تتركّز كل تركيباتنا العاملة فعلاً — نفس مناهج الدراسة، ' +
        'نفس العتاد من الفئة الأولى، نفس مراقبة Deye Cloud، مهما كانت المسافة.',
    },
  },
};

/**
 * Renvoie la prose d'une ville par slug, dans la locale demandée (FR par
 * défaut), avec repli sûr. Le FR (`locale='fr'`) est strictement inchangé.
 * Le placeholder `{intro}` du repli est résolu par l'appelant (qui connaît
 * la forme localisée « à <ville> » / « in <city> » / « في <مدينة> »).
 */
export const cityContentBySlug = (slug: string, locale: Locale = 'fr'): CityContent => {
  const entry = CITY_CONTENT[slug] ?? FALLBACK_CITY_CONTENT;
  return entry[locale] ?? entry.fr;
};
