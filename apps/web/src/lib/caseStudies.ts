/**
 * Prose éditoriale PAR ÉTUDE DE CAS pour les pages `/realisations/<slug>`.
 *
 * Pourquoi ce module existe : la route `realisations/[slug].astro` est une seule
 * route dynamique. Sans contenu par slug, les cinq études partagent une prose
 * identique — un relevé de statistiques répété — exactement ce que STYLE.md
 * interdit (règle 1 : « chaque formule signature n'apparaît qu'UNE fois » ;
 * règle 2 : « chaque page porte au moins un fait qui n'est qu'à elle »). On
 * déporte donc la prose ici, slug par slug, pour que chaque chantier se lise
 * comme un récit écrit pour lui : la situation, la toiture et le pourquoi de la
 * taille, la pose, puis le résultat mesuré en temps réel.
 *
 * INTÉGRITÉ ABSOLUE (règle du WEB_PLAN + STYLE.md §2/§6) : aucun fait inventé.
 * Tout ce qui est écrit ici se déduit UNIQUEMENT des données de
 * `realisations.ts` (kWc/production/panneaux/onduleur/batterie/ville/date/photos
 * réels) et de ce que le site publie déjà. Pas de nom de client, pas de
 * citation, pas d'anecdote, pas de date ou de durée non publiée, pas de chiffre
 * absent de `realisations.ts`. Là où un champ vaut `null` (réf. 134 onduleur/
 * batterie, réf. NC-10/25 production), la prose n'énonce NI n'implique de valeur.
 *
 * VOIX (STYLE.md) : retenue d'ingénieur, mener par le chiffre réel, concret
 * avant qualificatif, français natif, rythme varié d'une étude à l'autre. Chaque
 * formule signature (« l'étude décide du matériel », « la production se mesure »)
 * est RÉEXPRIMÉE ici, jamais recopiée.
 *
 * Clés = slugs de `REALISATIONS`.
 *
 * i18n (W67) : `caseStudyBySlug(slug, locale)` renvoie le récit dans la locale
 * demandée. Le FR (`locale='fr'`, défaut) reste STRICTEMENT inchangé ; EN et AR
 * sont des traductions fidèles, ADDITIVES, sans aucun chiffre/production/réf.
 * inventé ni altéré (chiffres en latin, identiques à `realisations.ts`). Pour
 * que `realisations.ts` reste intact, le `resume` traduit (index + [slug]) et
 * les `alt`s de photos traduits vivent ICI, par slug, par locale : où une
 * traduction d'alt manque, l'appelant retombe sur l'alt FR de `realisations.ts`.
 */
import type { Locale } from '../i18n/config';

export interface CaseStudyLink {
  /** Href interne réel et existant. */
  href: string;
  /** Libellé du lien (texte visible, sans la flèche que le template ajoute). */
  label: string;
}

export interface CaseStudyContent {
  /** <title> unique. */
  title: string;
  /** meta description unique. */
  description: string;
  /**
   * Le contexte du chantier, cadré à partir des seuls faits publiés
   * (ville, puissance, segment, profil de toiture déductible des photos/données).
   */
  situation: string;
  /** La logique de dimensionnement : pourquoi cette puissance, propre au cas. */
  sizing: string;
  /** La pose : ce que les photos et le matériel publiés permettent de raconter. */
  install: string;
  /**
   * Le résultat mesuré. Pour une réf. sans production publiée (NC-10/25), ce
   * champ NE cite aucun chiffre de production et ne l'implique pas.
   */
  result: string;
  /**
   * Phrase de contexte (= `resume` traduit), pour le hero du [slug] et la
   * carte de l'index. Le FR vaut EXACTEMENT le `resume` de `realisations.ts`.
   */
  resume: string;
  /**
   * Lien ville contextuel. `null` quand aucune page ville pertinente n'existe
   * (le template gère déjà la ville exacte via `cityPage` ; ce champ sert à
   * proposer la ville de service la PLUS proche pour les chantiers hors zone —
   * El Jadida et Nouaceur, tous deux en région Casablanca-Settat → Casablanca).
   */
  cityLink: CaseStudyLink | null;
  /**
   * `alt`s de photos traduits, indexés par `photo.name` de `realisations.ts`.
   * Permet de localiser les `alt` SANS toucher `realisations.ts`. Un nom absent
   * → l'appelant retombe sur l'alt FR (toujours non vide). Vide en FR : le FR
   * lit directement l'alt de `realisations.ts` (rendu inchangé).
   */
  alts: Record<string, string>;
  /**
   * W327 — citation client optionnelle (voix du client, pas de l'installateur).
   * NO-OP tant que WG6 n'a pas fourni de vraie citation : ce champ reste
   * `undefined` pour les cinq études actuelles et le template n'affiche RIEN
   * dans ce cas (ni guillemets vides, ni placeholder « bientôt »). Quand WG6
   * livre un vrai avis, il est saisi ici, texte + prénom uniquement (jamais de
   * nom de famille ni de coordonnées), par slug et par locale.
   */
  clientQuote?: { text: string; author: string };
}

/** Une entrée étude = la même structure traduite dans les trois locales. */
type LocalizedCaseStudy = Record<Locale, CaseStudyContent>;

/**
 * Repli sûr pour tout slug sans entrée dédiée : prose neutre, sans fait
 * chiffré inventé, conforme à STYLE.md. Aucun lien ville par défaut.
 */
export const FALLBACK_CASE_STUDY: LocalizedCaseStudy = {
  fr: {
    title: 'Étude de cas — installation solaire mesurée | Taqinor',
    description:
      'Une installation solaire réelle posée par Taqinor : la puissance retenue, le matériel sur le toit et la logique de dimensionnement.',
    situation:
      'Une installation solaire réelle posée par Taqinor.',
    sizing:
      'Le matériel posé sur ce chantier est détaillé sur cette page.',
    install:
      'Le matériel listé ci-dessus est ce qui est réellement sur le toit, sourcé via des distributeurs officiels au Maroc, garanties locales activables.',
    result:
      'Les photos de cette page sont celles du chantier.',
    resume:
      'Une installation solaire réelle posée par Taqinor.',
    cityLink: null,
    alts: {},
  },
  en: {
    title: 'Case study — measured solar installation | Taqinor',
    description:
      'A real solar installation fitted by Taqinor: the power chosen, the equipment on the roof and the sizing logic.',
    situation:
      'A real solar installation fitted by Taqinor.',
    sizing:
      'The equipment fitted on this project is detailed on this page.',
    install:
      'The equipment listed above is what is really on the roof, sourced through official distributors in Morocco, with local warranties activatable.',
    result:
      'The photos on this page are those of the site.',
    resume:
      'A real solar installation fitted by Taqinor.',
    cityLink: null,
    alts: {},
  },
  ar: {
    title: 'دراسة حالة — تركيب شمسي مقيس | Taqinor',
    description:
      'تركيب شمسي حقيقي أنجزته تاكينور: القدرة المختارة والعتاد فوق السطح ومنطق تحديد المقاس.',
    situation:
      'تركيب شمسي حقيقي أنجزته تاكينور.',
    sizing:
      'العتاد المركَّب في هذا الورش مُفصَّل في هذه الصفحة.',
    install:
      'العتاد المدرَج أعلاه هو ما يوجد فعلاً فوق السطح، مُورَّد عبر موزّعين رسميين بالمغرب، بضمانات محلية قابلة للتفعيل.',
    result:
      'الصور في هذه الصفحة هي صور الورش.',
    resume:
      'تركيب شمسي حقيقي أنجزته تاكينور.',
    cityLink: null,
    alts: {},
  },
};

export const CASE_STUDIES: Record<string, LocalizedCaseStudy> = {
  // Réf. 468 — la plus grande résidentielle de 2026. Production publiée.
  'el-jadida-17-kwc': {
    fr: {
      title: 'Installation solaire 17,04 kWc à El Jadida (réf. 468) | Taqinor',
      description:
        'Réf. 468 : 17,04 kWc sur une villa d’El Jadida, 24 panneaux Canadian Solar 710 Wc, onduleur Deye 15 kW triphasé, 15 kWh Dyness — notre plus grande résidentielle de 2026.',
      situation:
        'C’est la plus grande installation résidentielle que Taqinor ait livrée en 2026 : 17,04 kWc sur la toiture d’une villa d’El Jadida, en région Casablanca-Settat.',
      sizing:
        'Vingt-quatre Canadian Solar 710 Wc et un onduleur Deye triphasé de 15 kW, avec 15 kWh de batteries Dyness.',
      install:
        'La pose se voit sur les photos du dossier : la longue rangée de modules alignés au cordeau, le coffret de protections et les bornes des batteries Dyness câblées au propre.',
      result:
        'L’installation est livrée : les photos de cette page sont celles du chantier.',
      resume:
        'La plus grande installation résidentielle livrée par Taqinor en 2026 : une toiture de villa d’El Jadida équipée en 24 panneaux, onduleur hybride triphasé et stockage lithium.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'Installation solaire à Casablanca' },
      alts: {},
    },
    en: {
      title: 'Solar installation 17.04 kWc in El Jadida (ref. 468) | Taqinor',
      description:
        'Ref. 468: 17.04 kWc on an El Jadida villa, 24 Canadian Solar 710 Wc panels, Deye 15 kW three-phase inverter, 15 kWh Dyness — our largest residential of 2026.',
      situation:
        'This is the largest residential installation Taqinor delivered in 2026: 17.04 kWc on the roof of an El Jadida villa, in the Casablanca-Settat region.',
      sizing:
        'Twenty-four Canadian Solar 710 Wc panels and a Deye 15 kW three-phase inverter, with 15 kWh of Dyness batteries.',
      install:
        'The install shows on the file’s photos: the long row of modules aligned to the line, the protection box and the terminals of the Dyness batteries wired cleanly.',
      result:
        'The installation is delivered: the photos on this page are those of the site.',
      resume:
        'The largest residential installation delivered by Taqinor in 2026: an El Jadida villa roof fitted with 24 panels, a three-phase hybrid inverter and lithium storage.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'Solar installation in Casablanca' },
      alts: {
        'reflet-468': 'The sun reflects on the row of panels during the install, El Jadida',
        'equipe-trois': 'Taqinor team in front of the long row of panels at the end of the project, El Jadida',
        'detail-cablage': 'Close-up of the Dyness battery terminals and the protection box, clean wiring, El Jadida',
      },
    },
    ar: {
      title: 'تركيب شمسي 17,04 kWc في الجديدة (المرجع 468) | Taqinor',
      description:
        'المرجع 468: 17,04 kWc على فيلا بالجديدة، 24 لوحاً Canadian Solar 710 Wc، عاكس Deye 15 kW ثلاثي الطور، 15 kWh Dyness — أكبر تركيبة سكنية لنا في 2026.',
      situation:
        'هذه أكبر تركيبة سكنية سلّمتها تاكينور في 2026: 17,04 kWc على سطح فيلا بالجديدة، في جهة الدار البيضاء-سطات.',
      sizing:
        'أربعة وعشرون لوحاً Canadian Solar 710 Wc وعاكس Deye ثلاثي الطور بقدرة 15 kW، مع 15 kWh من بطاريات Dyness.',
      install:
        'التركيب يظهر في صور الملف: الصف الطويل من الألواح المُحاذاة بالخيط، صندوق الحماية وأطراف بطاريات Dyness المُوصَّلة بنظافة.',
      result:
        'التركيبة مُسلَّمة: الصور في هذه الصفحة هي صور الورش.',
      resume:
        'أكبر تركيبة سكنية سلّمتها تاكينور في 2026: سطح فيلا بالجديدة مُجهَّز بـ 24 لوحاً وعاكس هجين ثلاثي الطور وتخزين ليثيوم.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'تركيب شمسي في الدار البيضاء' },
      alts: {
        'reflet-468': 'الشمس تنعكس على صف الألواح أثناء التركيب، الجديدة',
        'equipe-trois': 'فريق تاكينور أمام الصف الطويل من الألواح في نهاية الورش، الجديدة',
        'detail-cablage': 'لقطة قريبة لأطراف بطاريات Dyness وصندوق الحماية، توصيل نظيف، الجديدة',
      },
    },
  },

  // Réf. 400 — villa Casablanca face skyline + borne de recharge. Production publiée.
  'casablanca-11-kwc': {
    fr: {
      title: 'Installation solaire 11,36 kWc à Casablanca (réf. 400) | Taqinor',
      description:
        'Réf. 400 : 11,36 kWc sur une villa de Casablanca face à la skyline, 16 panneaux Canadian Solar 710 Wc, onduleur Deye 10 kW, 10 kWh Dyness et borne de recharge, avec suivi de production en temps réel.',
      situation:
        'Une villa de Casablanca, le champ de panneaux dressé face à la skyline et au minaret : 11,36 kWc, avec une borne de recharge pour le véhicule du foyer.',
      sizing:
        'Seize Canadian Solar 710 Wc et un onduleur Deye 10 kW, avec deux batteries Dyness DL5.0C, soit 10 kWh.',
      install:
        'Le mur technique est sur les photos : l’onduleur hybride Deye, les deux Dyness et la borne de recharge alignés sur un même mur, câblage rangé. Le champ devant la skyline n’est pas une carte postale — c’est l’implantation réelle, orientée pour la production, pas pour la vue.',
      result:
        'Cette installation est raccordée au suivi de production : le cumul mesuré indiqué sur cette page vient de son relevé daté.',
      resume:
        'Une villa de Casablanca face à la skyline : 16 panneaux, onduleur hybride Deye et deux batteries Dyness, avec borne de recharge et suivi de production en temps réel.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'Installation solaire à Casablanca' },
      alts: {},
    },
    en: {
      title: 'Solar installation 11.36 kWc in Casablanca (ref. 400) | Taqinor',
      description:
        'Ref. 400: 11.36 kWc on a Casablanca villa facing the skyline, 16 Canadian Solar 710 Wc panels, Deye 10 kW inverter, 10 kWh Dyness and a charging station, with real-time production monitoring.',
      situation:
        'A Casablanca villa, the panel array raised facing the skyline and the minaret: 11.36 kWc, with a charging station for the household’s vehicle.',
      sizing:
        'Sixteen Canadian Solar 710 Wc panels and a Deye 10 kW inverter, with two Dyness DL5.0C batteries, i.e. 10 kWh.',
      install:
        'The technical wall is on the photos: the Deye hybrid inverter, the two Dyness units and the charging station aligned on a single wall, tidy wiring. The array in front of the skyline is no postcard — it is the real layout, oriented for production, not for the view.',
      result:
        'This installation is connected to production monitoring: the measured total shown on this page comes from its dated reading.',
      resume:
        'A Casablanca villa facing the skyline: 16 panels, a Deye hybrid inverter and two Dyness batteries, with a charging station and real-time production monitoring.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'Solar installation in Casablanca' },
      alts: {
        'hero-skyline': 'Row of solar panels in front of the Casablanca skyline and a minaret, golden light',
        'portrait-400': 'The engineer in front of the panel array, Casablanca skyline',
        'mur-technique-dyness': 'Technical wall of a Taqinor installation in Casablanca: Deye hybrid inverter, two Dyness batteries and a charging station',
      },
    },
    ar: {
      title: 'تركيب شمسي 11,36 kWc في الدار البيضاء (المرجع 400) | Taqinor',
      description:
        'المرجع 400: 11,36 kWc على فيلا بالدار البيضاء تواجه الأفق، 16 لوحاً Canadian Solar 710 Wc، عاكس Deye 10 kW، 10 kWh Dyness ومحطة شحن، مع متابعة الإنتاج في الوقت الحقيقي.',
      situation:
        'فيلا بالدار البيضاء، حقل الألواح مرفوع في مواجهة الأفق والمئذنة: 11,36 kWc، مع محطة شحن لسيّارة الأسرة.',
      sizing:
        'ستة عشر لوحاً Canadian Solar 710 Wc وعاكس Deye بقدرة 10 kW، مع بطاريتين Dyness DL5.0C، أي 10 kWh.',
      install:
        'الجدار التقني في الصور: العاكس الهجين Deye، والبطاريتان Dyness ومحطة الشحن مُحاذاة على جدار واحد، توصيل مرتّب. الحقل أمام الأفق ليس بطاقة بريدية — إنه التنصيب الحقيقي، موجَّه للإنتاج، لا للمنظر.',
      result:
        'هذه التركيبة مربوطة بمتابعة الإنتاج: التراكم المقاس المبيَّن في هذه الصفحة مصدره قراءتها المؤرَّخة.',
      resume:
        'فيلا بالدار البيضاء تواجه الأفق: 16 لوحاً، عاكس هجين Deye وبطاريتان Dyness، مع محطة شحن ومتابعة الإنتاج في الوقت الحقيقي.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'تركيب شمسي في الدار البيضاء' },
      alts: {
        'hero-skyline': 'صف من الألواح الشمسية أمام أفق الدار البيضاء ومئذنة، ضوء ذهبي',
        'portrait-400': 'المهندس أمام حقل الألواح، أفق الدار البيضاء',
        'mur-technique-dyness': 'الجدار التقني لتركيبة تاكينور بالدار البيضاء: عاكس هجين Deye وبطاريتان Dyness ومحطة شحن',
      },
    },
  },

  // Réf. 236 — résidentielle compacte toit plat El Jadida. Production publiée.
  'el-jadida-6-kwc': {
    fr: {
      title: 'Installation solaire 5,68 kWc à El Jadida (réf. 236) | Taqinor',
      description:
        'Réf. 236 : 5,68 kWc sur le toit plat d’une villa d’El Jadida, 8 panneaux Canadian Solar 710 Wc, onduleur Deye 5 kW, batterie 5 kWh Dyness.',
      situation:
        'Un toit plat de villa à El Jadida, huit panneaux, 5,68 kWc : le format compact de nos installations résidentielles.',
      sizing:
        'Huit Canadian Solar 710 Wc, un onduleur Deye 5 kW, une batterie de 5 kWh. Le toit plat laisse choisir librement l’inclinaison et l’azimut des modules.',
      install:
        'La photo du dossier montre le champ des huit modules posés sur le toit-terrasse, structure réglée pour l’inclinaison retenue.',
      result:
        'L’installation est livrée : la photo de cette page est celle du chantier.',
      resume:
        'Une installation résidentielle compacte sur toit plat à El Jadida : huit panneaux, onduleur hybride et une batterie 5 kWh.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'Installation solaire à Casablanca' },
      alts: {},
    },
    en: {
      title: 'Solar installation 5.68 kWc in El Jadida (ref. 236) | Taqinor',
      description:
        'Ref. 236: 5.68 kWc on the flat roof of an El Jadida villa, 8 Canadian Solar 710 Wc panels, Deye 5 kW inverter, 5 kWh Dyness battery.',
      situation:
        'A villa’s flat roof in El Jadida, eight panels, 5.68 kWc: the compact format of our residential installations.',
      sizing:
        'Eight Canadian Solar 710 Wc panels, a Deye 5 kW inverter, a 5 kWh battery. The flat roof leaves the modules’ tilt and azimuth free to choose.',
      install:
        'The file’s photo shows the array of eight modules fitted on the roof terrace, structure set for the chosen tilt.',
      result:
        'The installation is delivered: the photo on this page is that of the site.',
      resume:
        'A compact residential installation on a flat roof in El Jadida: eight panels, a hybrid inverter and a 5 kWh battery.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'Solar installation in Casablanca' },
      alts: {
        'champ-villa': 'Array of eight panels on a villa’s flat roof, El Jadida',
      },
    },
    ar: {
      title: 'تركيب شمسي 5,68 kWc في الجديدة (المرجع 236) | Taqinor',
      description:
        'المرجع 236: 5,68 kWc على السطح المستوي لفيلا بالجديدة، 8 ألواح Canadian Solar 710 Wc، عاكس Deye 5 kW، بطارية 5 kWh Dyness.',
      situation:
        'سطح مستوٍ لفيلا بالجديدة، ثمانية ألواح، 5,68 kWc: الصيغة المُدمجة لتركيباتنا السكنية.',
      sizing:
        'ثمانية ألواح Canadian Solar 710 Wc، عاكس Deye بقدرة 5 kW، بطارية 5 kWh. يتيح السطح المستوي اختيار ميل الألواح واتجاهها بحرية.',
      install:
        'صورة الملف تُظهر حقل الألواح الثمانية مُركَّبة على السطح، بنية مضبوطة على الميل المختار.',
      result:
        'التركيبة مُسلَّمة: الصورة في هذه الصفحة هي صورة الورش.',
      resume:
        'تركيبة سكنية مُدمجة على سطح مستوٍ بالجديدة: ثمانية ألواح، عاكس هجين وبطارية 5 kWh.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'تركيب شمسي في الدار البيضاء' },
      alts: {
        'champ-villa': 'حقل من ثمانية ألواح على سطح مستوٍ لفيلا، الجديدة',
      },
    },
  },

  // Réf. 134 — villa Casablanca 8 panneaux. onduleur/batterie = null → JAMAIS cités.
  'casablanca-6-kwc': {
    fr: {
      title: 'Installation solaire 5,68 kWc à Casablanca (réf. 134) | Taqinor',
      description:
        'Réf. 134 : 5,68 kWc sur une villa de Casablanca, 8 panneaux Canadian Solar 710 Wc.',
      situation:
        'Une villa de Casablanca, huit panneaux Canadian Solar 710 Wc, 5,68 kWc.',
      sizing:
        'Huit modules de 710 Wc pour 5,68 kWc, le matériel réellement posé sur ce toit.',
      install:
        'La photo du dossier saisit la pose en cours : l’équipe incline un panneau pour le caler sur sa structure. Les modules Canadian Solar 710 Wc sont le matériel réellement installé sur ce toit casablancais.',
      result:
        'L’installation est livrée : la photo de cette page est celle de la pose.',
      resume:
        'Une villa de Casablanca équipée de huit panneaux Canadian Solar 710 Wc.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'Installation solaire à Casablanca' },
      alts: {},
    },
    en: {
      title: 'Solar installation 5.68 kWc in Casablanca (ref. 134) | Taqinor',
      description:
        'Ref. 134: 5.68 kWc on a Casablanca villa, 8 Canadian Solar 710 Wc panels.',
      situation:
        'A Casablanca villa, eight Canadian Solar 710 Wc panels, 5.68 kWc.',
      sizing:
        'Eight 710 Wc modules for 5.68 kWc, the equipment actually fitted on this roof.',
      install:
        'The file’s photo captures the install in progress: the team tilts a panel to set it on its structure. The Canadian Solar 710 Wc modules are the equipment really installed on this Casablanca roof.',
      result:
        'The installation is delivered: the photo on this page is that of the install.',
      resume:
        'A Casablanca villa fitted with eight Canadian Solar 710 Wc panels.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'Solar installation in Casablanca' },
      alts: {
        'pose-134': 'The team tilts a panel during the install, Casablanca',
      },
    },
    ar: {
      title: 'تركيب شمسي 5,68 kWc في الدار البيضاء (المرجع 134) | Taqinor',
      description:
        'المرجع 134: 5,68 kWc على فيلا بالدار البيضاء، 8 ألواح Canadian Solar 710 Wc.',
      situation:
        'فيلا بالدار البيضاء، ثمانية ألواح Canadian Solar 710 Wc، 5,68 kWc.',
      sizing:
        'ثمانية ألواح بقدرة 710 Wc من أجل 5,68 kWc، وهو العتاد المركَّب فعلاً على هذا السطح.',
      install:
        'صورة الملف تلتقط التركيب جارياً: الفريق يميل لوحاً لضبطه على بنيته. ألواح Canadian Solar 710 Wc هي العتاد المُركَّب فعلاً على هذا السطح البيضاوي.',
      result:
        'التركيبة مُسلَّمة: الصورة في هذه الصفحة هي صورة التركيب.',
      resume:
        'فيلا بالدار البيضاء مُجهَّزة بثمانية ألواح Canadian Solar 710 Wc.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'تركيب شمسي في الدار البيضاء' },
      alts: {
        'pose-134': 'الفريق يميل لوحاً أثناء التركيب، الدار البيضاء',
      },
    },
  },

  // Réf. NC-10/25 — Nouaceur 6 × JA Solar. production/onduleur/batterie = null → JAMAIS de chiffre de prod.
  'nouaceur-4-kwc': {
    fr: {
      title: 'Installation solaire 3,72 kWc à Nouaceur — 6 panneaux JA Solar (réf. NC-10/25) | Taqinor',
      description:
        'Réf. NC-10/25 : 3,72 kWc à Nouaceur, dans la périphérie de Casablanca, 6 panneaux JA Solar posés en octobre 2025 avec le même soin d’implantation que nos plus grands chantiers. Photos et vidéo réelles du chantier.',
      situation:
        'À Nouaceur, dans la périphérie de Casablanca, une installation de 3,72 kWc : six panneaux JA Solar, posés avec le même soin d’implantation que sur nos chantiers de plus grande taille.',
      sizing:
        'Six modules JA Solar pour 3,72 kWc. Le tracé des rails et l’alignement se calculent ici avec la même rigueur qu’à 17 kWc.',
      install:
        'Les photos et la vidéo du dossier montrent le travail de fond : les installateurs Taqinor posent les blocs de lestage et les rails de la structure, une équipe mesure au mètre l’implantation avant la pose des modules, puis le nettoyage au jet du champ une fois les panneaux en place. À l’intérieur, l’onduleur MUST est posé à côté du coffret électrique. C’est cette préparation invisible qui tient une installation sur la durée.',
      result:
        'Posée en octobre 2025, l’installation suit notre standard d’implantation et d’entretien.',
      resume:
        'Une installation à Nouaceur, dans la périphérie de Casablanca : six panneaux JA Solar posés avec le même soin d’implantation que nos chantiers de plus grande taille.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'Installation solaire à Casablanca' },
      alts: {},
    },
    en: {
      title: 'Solar installation 3.72 kWc in Nouaceur — 6 JA Solar panels (ref. NC-10/25) | Taqinor',
      description:
        'Ref. NC-10/25: 3.72 kWc in Nouaceur, on the outskirts of Casablanca, 6 JA Solar panels fitted in October 2025 with the same care of layout as our largest projects. Real photos and video of the project.',
      situation:
        'In Nouaceur, on the outskirts of Casablanca, a 3.72 kWc installation: six JA Solar panels, fitted with the same care of layout as on our larger projects.',
      sizing:
        'Six JA Solar modules for 3.72 kWc. The rail layout and the alignment are computed here with the same rigour as at 17 kWc.',
      install:
        'The file’s photos and video show the groundwork: Taqinor installers set out the ballast blocks and the structure’s rails, a team measures out the layout with a tape before fitting the modules, then the jet cleaning of the array once the panels are in place. Indoors, the MUST inverter sits next to the electrical enclosure. It is this invisible preparation that holds an installation over time.',
      result:
        'Fitted in October 2025, the installation follows our standard of layout and upkeep.',
      resume:
        'An installation in Nouaceur, on the outskirts of Casablanca: six JA Solar panels fitted with the same care of layout as our larger projects.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'Solar installation in Casablanca' },
      alts: {
        'equipe-gilet-taqinor': 'Installer in a Taqinor vest fitting a structure’s rails, Nouaceur',
        'mesure-rails': 'Marking out and tape measurement of the fixing rails on the roof, Nouaceur',
        'entretien-jet': 'Jet cleaning of the panel array, Nouaceur',
        'nouaceur-toit': 'Row of six solar panels at sunset, palm trees in the background, Nouaceur',
        'nouaceur-panneaux-couchant': 'Close-up of the six solar panels aligned at dusk, Nouaceur',
        'nouaceur-structure-lestage': 'Two Taqinor installers set the ballast blocks and rails before fitting the panels, Nouaceur',
        'nouaceur-equipe-rails': 'Taqinor vest and mounting rails being aligned on the roof, Nouaceur',
        'nouaceur-mesure-equipe': 'Three Taqinor installers measure the rail layout on the roof, Nouaceur',
        'nouaceur-onduleur-must': 'MUST solar inverter fitted on an interior wall, next to the electrical enclosure, Nouaceur',
      },
    },
    ar: {
      title: 'تركيب شمسي 3,72 kWc في النواصر — 6 ألواح JA Solar (المرجع NC-10/25) | Taqinor',
      description:
        'المرجع NC-10/25: 3,72 kWc في النواصر، بضواحي الدار البيضاء، 6 ألواح JA Solar مُركَّبة في أكتوبر 2025 بنفس عناية التنصيب التي في أكبر أوراشنا. صور وفيديو حقيقيان من الورش.',
      situation:
        'في النواصر، بضواحي الدار البيضاء، تركيبة بقدرة 3,72 kWc: ستة ألواح JA Solar، مُركَّبة بنفس عناية التنصيب كما في أوراشنا الأكبر حجماً.',
      sizing:
        'ستة ألواح JA Solar من أجل 3,72 kWc. تخطيط السكك والمحاذاة يُحسبان هنا بنفس الصرامة كما عند 17 kWc.',
      install:
        'صور وفيديو الملف تُظهر العمل الأساسي: يضع مُركِّبو تاكينور كتل الإرساء وسكك البنية، ويقيس فريق التنصيب بالمتر تخطيط السكك قبل تركيب الألواح، ثم يُنظَّف الحقل بالماء بمجرّد وضع الألواح. في الداخل، يوجد عاكس MUST إلى جانب اللوحة الكهربائية. هذا التحضير غير المرئي هو ما يُبقي التركيبة على المدى.',
      result:
        'مُركَّبة في أكتوبر 2025، تتبع التركيبة معيارنا في التنصيب والصيانة.',
      resume:
        'تركيبة في النواصر، بضواحي الدار البيضاء: ستة ألواح JA Solar مُركَّبة بنفس عناية التنصيب التي في أوراشنا الأكبر حجماً.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'تركيب شمسي في الدار البيضاء' },
      alts: {
        'equipe-gilet-taqinor': 'مُركِّب بسترة تاكينور يضع سكك بنية، النواصر',
        'mesure-rails': 'تخطيط وقياس بالمتر لسكك التثبيت على السطح، النواصر',
        'entretien-jet': 'تنظيف حقل الألواح بنفث الماء، النواصر',
        'nouaceur-toit': 'صف من ستة ألواح شمسية عند الغروب، نخيل في الخلفية، النواصر',
        'nouaceur-panneaux-couchant': 'لقطة قريبة لمحاذاة الألواح الشمسية الستة عند الغروب، النواصر',
        'nouaceur-structure-lestage': 'مُركِّبان من تاكينور يضعان كتل الإرساء والسكك قبل تركيب الألواح، النواصر',
        'nouaceur-equipe-rails': 'سترة تاكينور وسكك التثبيت أثناء المحاذاة على السطح، النواصر',
        'nouaceur-mesure-equipe': 'ثلاثة مُركِّبين من تاكينور يقيسون تخطيط السكك على السطح، النواصر',
        'nouaceur-onduleur-must': 'عاكس شمسي MUST مُركَّب على جدار داخلي، إلى جانب اللوحة الكهربائية، النواصر',
      },
    },
  },

  // (2026-09) Villa de Bouskoura — chantier FILMÉ le 09/07/2026, puissance et
  // production NON connues (kwc/kwcNum/production restent absents dans
  // realisations.ts). Prose délibérément minimale et méta sur ce qui manque :
  // aucune histoire de dimensionnement/facture n'est inventée pour ce chantier
  // faute de données — seul ce qui est VISIBLE sur les images (onduleur Deye,
  // batterie DYNESS DL5.0C, équipe en gilet Taqinor) est décrit.
  'bouskoura-villa-2026': {
    // Faits fondateur (Reda, 08/09/2026) : 16 panneaux de 715 Wc = 11,44 kWc,
    // 2 batteries DYNESS 5 kWh (DL5.0C), onduleur hybride Deye, mise en
    // service juillet 2026 ; chantier filmé le 09/07/2026. Production non
    // relevée : jamais un chiffre deviné.
    fr: {
      title: 'Installation solaire 11,44 kWc à Bouskoura — villa mise en service en juillet 2026 | Taqinor',
      description:
        'Une villa à Bouskoura équipée de seize panneaux de 715 Wc (11,44 kWc), d’un onduleur hybride Deye et de deux batteries DYNESS de 5 kWh, mise en service en juillet 2026. Photos et vidéo réelles du chantier.',
      situation:
        'À Bouskoura, dans la région de Casablanca-Settat, toute la toiture-terrasse d’une villa a été équipée en panneaux solaires. Le chantier a été filmé le 9 juillet 2026, au moment des derniers réglages : câblage, contrôle au multimètre et mise en route de l’onduleur.',
      sizing:
        'Seize panneaux de 715 Wc, soit 11,44 kWc installés, avec un onduleur hybride Deye et deux batteries DYNESS de 5 kWh (10 kWh de stockage).',
      install:
        'L’équipe Taqinor, reconnaissable à son gilet de travail, a posé les seize panneaux sur la toiture-terrasse, raccordé l’onduleur hybride Deye et installé les deux modules DYNESS DL5.0C, puis effectué les vérifications finales avant la mise en route.',
      result:
        'Installation mise en service en juillet 2026.',
      resume:
        'Une villa à Bouskoura équipée de seize panneaux de 715 Wc (11,44 kWc), onduleur hybride Deye et deux batteries DYNESS de 5 kWh — mise en service en juillet 2026.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'Installation solaire à Casablanca' },
      alts: {},
    },
    en: {
      title: 'Solar installation 11.44 kWc in Bouskoura — villa commissioned in July 2026 | Taqinor',
      description:
        'A villa in Bouskoura fitted with sixteen 715 Wc panels (11.44 kWc), a Deye hybrid inverter and two DYNESS 5 kWh batteries, commissioned in July 2026. Real photos and video of the project.',
      situation:
        'In Bouskoura, in the Casablanca-Settat region, an entire villa roof terrace was fitted with solar panels. The project was filmed on 9 July 2026, during the final adjustments: wiring, multimeter checks and starting up the inverter.',
      sizing:
        'Sixteen 715 Wc panels, i.e. 11.44 kWc installed, with a Deye hybrid inverter and two DYNESS 5 kWh batteries (10 kWh of storage).',
      install:
        'The Taqinor team, recognisable by its work vest, mounted the sixteen panels on the roof terrace, connected the Deye hybrid inverter and installed the two DYNESS DL5.0C modules, then carried out the final checks before start-up.',
      result:
        'Commissioned in July 2026.',
      resume:
        'A villa in Bouskoura with sixteen 715 Wc panels (11.44 kWc), a Deye hybrid inverter and two DYNESS 5 kWh batteries — commissioned in July 2026.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'Solar installation in Casablanca' },
      alts: {
        'bouskoura-toit': 'A villa roof terrace fully covered in solar panels, Bouskoura',
        'bouskoura-toit-large': 'Wide aerial view of the villa’s solar roof and the neighbourhood, Bouskoura',
        'bouskoura-panneaux': 'Close-up of the solar panel array and its mounting structure, Bouskoura',
        'bouskoura-gilet-taqinor': 'A Taqinor work vest worn by an installer on the Bouskoura project',
        'bouskoura-cablage-onduleur': 'Wiring inside the inverter’s connection compartment, Bouskoura project',
        'bouskoura-coffret-technicien': 'A Taqinor technician wiring an electrical enclosure, Bouskoura project',
        'bouskoura-equipe-mur-technique': 'Two Taqinor installers in front of the inverter and electrical panel, Bouskoura project',
        'bouskoura-batterie-dyness': 'DYNESS storage battery (DL5.0C module) fitted on the Bouskoura project',
      },
    },
    ar: {
      title: 'تركيب شمسي 11,44 kWc في بوسكورة — فيلا شُغِّلت في يوليوز 2026 | Taqinor',
      description:
        'فيلا في بوسكورة مجهزة بستة عشر لوحاً بقدرة 715 واط (11,44 kWc)، وعاكس هجين Deye وبطاريتي DYNESS بسعة 5 كيلوواط-ساعة، شُغِّلت في يوليوز 2026. صور وفيديو حقيقيان من الورش.',
      situation:
        'في بوسكورة، بجهة الدار البيضاء-سطات، جُهِّز سطح فيلا بأكمله بألواح شمسية. صُوِّر هذا الورش يوم 9 يوليوز 2026، في لحظة الضبط الأخير: التوصيل، الفحص بالمقياس المتعدد، وتشغيل العاكس.',
      sizing:
        'ستة عشر لوحاً بقدرة 715 واط، أي 11,44 kWc مُركَّبة، مع عاكس هجين Deye وبطاريتين DYNESS بسعة 5 كيلوواط-ساعة (10 كيلوواط-ساعة من التخزين).',
      install:
        'فريق تاكينور، الذي يُعرَف بسترة العمل، ركَّب الألواح الستة عشر على سطح الفيلا، ووصّل العاكس الهجين Deye وثبّت وحدتي DYNESS DL5.0C، ثم أجرى الفحوصات الأخيرة قبل التشغيل.',
      result:
        'شُغِّل التركيب في يوليوز 2026.',
      resume:
        'فيلا في بوسكورة بستة عشر لوحاً بقدرة 715 واط (11,44 kWc)، عاكس هجين Deye وبطاريتي DYNESS بسعة 5 كيلوواط-ساعة — شُغِّلت في يوليوز 2026.',
      cityLink: { href: '/installation-solaire-casablanca/', label: 'تركيب شمسي في الدار البيضاء' },
      alts: {
        'bouskoura-toit': 'سطح فيلا مغطى بالكامل بألواح شمسية، بوسكورة',
        'bouskoura-toit-large': 'منظر جوي واسع لسطح الفيلا الشمسي والحي المحيط، بوسكورة',
        'bouskoura-panneaux': 'لقطة قريبة لمحاذاة الألواح الشمسية وبنية تثبيتها، بوسكورة',
        'bouskoura-gilet-taqinor': 'سترة عمل تاكينور يرتديها مُركِّب في ورش بوسكورة',
        'bouskoura-cablage-onduleur': 'التوصيل داخل حجرة ربط العاكس، ورش بوسكورة',
        'bouskoura-coffret-technicien': 'تقني من تاكينور يوصّل علبة كهربائية، ورش بوسكورة',
        'bouskoura-equipe-mur-technique': 'مُركِّبان من تاكينور أمام العاكس واللوحة الكهربائية، ورش بوسكورة',
        'bouskoura-batterie-dyness': 'بطارية تخزين DYNESS (وحدة DL5.0C) مُركَّبة في ورش بوسكورة',
      },
    },
  },
};

/**
 * Renvoie le récit d'une étude de cas par slug, dans la locale demandée (FR par
 * défaut), avec repli sûr. Le FR (`locale='fr'`) est strictement inchangé.
 */
export const caseStudyBySlug = (slug: string, locale: Locale = 'fr'): CaseStudyContent => {
  const entry = CASE_STUDIES[slug] ?? FALLBACK_CASE_STUDY;
  return entry[locale] ?? entry.fr;
};
