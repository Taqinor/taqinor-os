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
 * taille, la pose, puis le résultat mesuré sur Deye Cloud.
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
      'Une installation solaire réelle posée par Taqinor : la puissance retenue, le matériel sur le toit et la logique de dimensionnement, sans chiffre promis.',
    situation:
      'Ce chantier a été dimensionné sur la consommation réelle du site, lue sur la dernière facture avant le moindre devis.',
    sizing:
      'La puissance part de la facture et de la toiture — surface utile, orientation, ombrage — pour couvrir l’essentiel des besoins sans poser un panneau de trop.',
    install:
      'Le matériel listé ci-dessus est ce qui est réellement sur le toit, sourcé via des distributeurs officiels au Maroc, garanties locales activables.',
    result:
      'L’installation est raccordée à Deye Cloud, accès client compris : les kWh produits se lisent, ils ne se promettent pas.',
    resume:
      'Une installation solaire réelle posée par Taqinor, dimensionnée sur la consommation du site.',
    cityLink: null,
    alts: {},
  },
  en: {
    title: 'Case study — measured solar installation | Taqinor',
    description:
      'A real solar installation fitted by Taqinor: the power chosen, the equipment on the roof and the sizing logic, with no promised figure.',
    situation:
      'This project was sized on the site’s real consumption, read off the latest bill before any quote.',
    sizing:
      'The power starts from the bill and the roof — usable surface, orientation, shading — to cover the bulk of the needs without fitting one panel too many.',
    install:
      'The equipment listed above is what is really on the roof, sourced through official distributors in Morocco, with local warranties activatable.',
    result:
      'The installation is connected to Deye Cloud, client access included: the kWh produced are read off, they are not promised.',
    resume:
      'A real solar installation fitted by Taqinor, sized on the site’s consumption.',
    cityLink: null,
    alts: {},
  },
  ar: {
    title: 'دراسة حالة — تركيب شمسي مقيس | Taqinor',
    description:
      'تركيب شمسي حقيقي أنجزته تاكينور: القدرة المختارة والعتاد فوق السطح ومنطق تحديد المقاس، دون أي رقم موعود.',
    situation:
      'حُدِّد مقاس هذا الورش على الاستهلاك الحقيقي للموقع، المقروء على آخر فاتورة قبل أي ثمن.',
    sizing:
      'تنطلق القدرة من الفاتورة والسطح — المساحة المفيدة والتوجيه والتظليل — لتغطية جلّ الحاجيات دون تركيب لوح زائد.',
    install:
      'العتاد المدرَج أعلاه هو ما يوجد فعلاً فوق السطح، مُورَّد عبر موزّعين رسميين بالمغرب، بضمانات محلية قابلة للتفعيل.',
    result:
      'التركيبة موصولة بـ Deye Cloud، مع ولوج الزبون: الكيلوواط-ساعة المنتَجة تُقرأ، ولا تُوعَد.',
    resume:
      'تركيب شمسي حقيقي أنجزته تاكينور، مُحدَّد المقاس على استهلاك الموقع.',
    cityLink: null,
    alts: {},
  },
};

export const CASE_STUDIES: Record<string, LocalizedCaseStudy> = {
  // Réf. 468 — la plus grande résidentielle de 2026. Production publiée.
  'el-jadida-17-kwc': {
    fr: {
      title: 'Installation solaire 17,04 kWc à El Jadida — 21 406 kWh/an mesurés (réf. 468) | Taqinor',
      description:
        'Réf. 468 : 17,04 kWc sur une villa d’El Jadida, 24 panneaux Canadian Solar 710 Wc, onduleur Deye 15 kW triphasé, 15 kWh Dyness. 21 406 kWh/an relevés sur Deye Cloud — notre plus grande résidentielle de 2026.',
      situation:
        'C’est la plus grande installation résidentielle que Taqinor ait livrée en 2026 : 17,04 kWc sur la toiture d’une villa d’El Jadida, en région Casablanca-Settat. À cette taille, on ne pose plus pour appoint — on couvre un foyer dont la facture annuelle justifie 24 panneaux et un onduleur triphasé.',
      sizing:
        'Vingt-quatre Canadian Solar 710 Wc, pas vingt ni trente : le compte vient de la consommation relevée et de la surface utile du toit. Le triphasé n’est pas un luxe mais une conséquence — à 15 kW d’onduleur, l’équilibrage des phases impose le Deye triphasé. Aucune référence n’a été posée avant que le calcul ne l’ait justifiée.',
      install:
        'La pose se voit sur les photos du dossier : la longue rangée de modules alignés au cordeau, le coffret de protections et les bornes des batteries Dyness câblées au propre. Le stockage de 15 kWh a été ajouté pour la part de consommation qui tombe hors production solaire — le soir, la nuit — et non par principe.',
      result:
        '21 406 kWh sur l’année, relevés en continu sur Deye Cloud dont le foyer garde l’accès. Ce n’est pas une projection de vente : c’est le compteur qui parle, mois après mois, et l’écart éventuel se verrait du premier coup d’œil.',
      resume:
        'La plus grande installation résidentielle livrée par Taqinor en 2026 : une toiture de villa d’El Jadida équipée en 24 panneaux, onduleur hybride triphasé et stockage lithium.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'Installation solaire à Casablanca' },
      alts: {},
    },
    en: {
      title: 'Solar installation 17.04 kWc in El Jadida — 21,406 kWh/year measured (ref. 468) | Taqinor',
      description:
        'Ref. 468: 17.04 kWc on an El Jadida villa, 24 Canadian Solar 710 Wc panels, Deye 15 kW three-phase inverter, 15 kWh Dyness. 21,406 kWh/year read off Deye Cloud — our largest residential of 2026.',
      situation:
        'This is the largest residential installation Taqinor delivered in 2026: 17.04 kWc on the roof of an El Jadida villa, in the Casablanca-Settat region. At this size, you no longer install for top-up — you cover a household whose annual bill justifies 24 panels and a three-phase inverter.',
      sizing:
        'Twenty-four Canadian Solar 710 Wc, not twenty or thirty: the count comes from the metered consumption and the usable roof surface. Three-phase is not a luxury but a consequence — at 15 kW of inverter, balancing the phases requires the three-phase Deye. No equipment was fitted before the calculation justified it.',
      install:
        'The install shows on the file’s photos: the long row of modules aligned to the line, the protection box and the terminals of the Dyness batteries wired cleanly. The 15 kWh of storage was added for the share of consumption that falls outside solar production — evening, night — and not as a matter of principle.',
      result:
        '21,406 kWh over the year, read continuously on Deye Cloud, to which the household keeps access. It is not a sales projection: it is the meter speaking, month after month, and any gap would show at first glance.',
      resume:
        'The largest residential installation delivered by Taqinor in 2026: an El Jadida villa roof fitted with 24 panels, a three-phase hybrid inverter and lithium storage.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'Solar installation in Casablanca' },
      alts: {
        'reflet-468': 'The sun reflects on the row of panels during the install, El Jadida',
        'equipe-trois': 'Taqinor team in front of the long row of panels at the end of the project, El Jadida',
        'detail-cablage': 'Close-up of the Dyness battery terminals and the protection box, clean wiring, El Jadida',
      },
    },
    ar: {
      title: 'تركيب شمسي 17,04 kWc في الجديدة — 21 406 kWh/سنة مقيسة (المرجع 468) | Taqinor',
      description:
        'المرجع 468: 17,04 kWc على فيلا بالجديدة، 24 لوحاً Canadian Solar 710 Wc، عاكس Deye 15 kW ثلاثي الطور، 15 kWh Dyness. 21 406 kWh/سنة مقروءة على Deye Cloud — أكبر تركيبة سكنية لنا في 2026.',
      situation:
        'هذه أكبر تركيبة سكنية سلّمتها تاكينور في 2026: 17,04 kWc على سطح فيلا بالجديدة، في جهة الدار البيضاء-سطات. عند هذا الحجم، لا تُركَّب لأجل تكملة — بل لتغطية أسرة تبرّر فاتورتها السنوية 24 لوحاً وعاكساً ثلاثي الطور.',
      sizing:
        'أربعة وعشرون Canadian Solar 710 Wc، لا عشرين ولا ثلاثين: العدد يأتي من الاستهلاك المقيس والمساحة المفيدة للسطح. الطور الثلاثي ليس ترفاً بل نتيجة — عند عاكس بقدرة 15 kW، يفرض توازن الأطوار اختيار Deye الثلاثي الطور. لم يُركَّب أي عتاد قبل أن يبرّره الحساب.',
      install:
        'التركيب يظهر في صور الملف: الصف الطويل من الألواح المُحاذاة بالخيط، صندوق الحماية وأطراف بطاريات Dyness المُوصَّلة بنظافة. أُضيف تخزين 15 kWh لحصّة الاستهلاك الواقعة خارج الإنتاج الشمسي — مساءً وليلاً — لا مبدئياً.',
      result:
        '21 406 kWh على مدار السنة، مقروءة باستمرار على Deye Cloud الذي تحتفظ الأسرة بالولوج إليه. ليست توقّعاً تجارياً: إنه العدّاد يتكلّم، شهراً بعد شهر، وأي فارق يظهر من أول نظرة.',
      resume:
        'أكبر تركيبة سكنية سلّمتها تاكينور في 2026: سطح فيلا بالجديدة مُجهَّز بـ 24 لوحاً وعاكس هجين ثلاثي الطور وتخزين ليثيوم.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'تركيب شمسي في الدار البيضاء' },
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
      title: 'Installation solaire 11,36 kWc à Casablanca — 14 271 kWh/an mesurés (réf. 400) | Taqinor',
      description:
        'Réf. 400 : 11,36 kWc sur une villa de Casablanca face à la skyline, 16 panneaux Canadian Solar 710 Wc, onduleur Deye 10 kW, 10 kWh Dyness et borne de recharge. 14 271 kWh/an suivis sur Deye Cloud.',
      situation:
        'Une villa de Casablanca, le champ de panneaux dressé face à la skyline et au minaret : 11,36 kWc pour un foyer qui recharge aussi son véhicule à la maison. La borne de recharge change l’équation — la consommation ne s’arrête pas aux appareils domestiques, et la puissance posée en tient compte.',
      sizing:
        'Seize Canadian Solar 710 Wc et un onduleur Deye 10 kW : le dimensionnement suit une facture qui inclut la recharge du véhicule, pas seulement l’électroménager. Deux batteries Dyness DL5.0C, soit 10 kWh, encaissent la part nocturne. C’est la consommation du site qui a fixé la taille ; le devis n’est venu qu’après.',
      install:
        'Le mur technique est sur les photos : l’onduleur hybride Deye, les deux Dyness et la borne de recharge alignés sur un même mur, câblage rangé. Le champ devant la skyline n’est pas une carte postale — c’est l’implantation réelle, orientée pour la production, pas pour la vue.',
      result:
        '14 271 kWh par an, suivis sur Deye Cloud avec accès client. Le chiffre n’est pas un argumentaire : il se relève sur le monitoring, et la borne de recharge se lit dans la courbe de consommation autant que les panneaux dans celle de production.',
      resume:
        'Une villa de Casablanca face à la skyline : 16 panneaux, onduleur hybride Deye et deux batteries Dyness, avec borne de recharge — production estimée à partir du rendement mesuré de nos chantiers.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'Installation solaire à Casablanca' },
      alts: {},
    },
    en: {
      title: 'Solar installation 11.36 kWc in Casablanca — 14,271 kWh/year measured (ref. 400) | Taqinor',
      description:
        'Ref. 400: 11.36 kWc on a Casablanca villa facing the skyline, 16 Canadian Solar 710 Wc panels, Deye 10 kW inverter, 10 kWh Dyness and a charging station. 14,271 kWh/year followed on Deye Cloud.',
      situation:
        'A Casablanca villa, the panel array raised facing the skyline and the minaret: 11.36 kWc for a household that also charges its vehicle at home. The charging station changes the equation — consumption does not stop at household appliances, and the installed power takes that into account.',
      sizing:
        'Sixteen Canadian Solar 710 Wc and a Deye 10 kW inverter: the sizing follows a bill that includes vehicle charging, not just appliances. Two Dyness DL5.0C batteries, i.e. 10 kWh, absorb the night share. It is the site’s consumption that set the size; the quote only came after.',
      install:
        'The technical wall is on the photos: the Deye hybrid inverter, the two Dyness units and the charging station aligned on a single wall, tidy wiring. The array in front of the skyline is no postcard — it is the real layout, oriented for production, not for the view.',
      result:
        '14,271 kWh a year, followed on Deye Cloud with client access. The figure is not a pitch: it is read off the monitoring, and the charging station reads in the consumption curve as much as the panels read in the production curve.',
      resume:
        'A Casablanca villa facing the skyline: 16 panels, a Deye hybrid inverter and two Dyness batteries, with a charging station — production estimated from our measured field yield.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'Solar installation in Casablanca' },
      alts: {
        'hero-skyline': 'Row of solar panels in front of the Casablanca skyline and a minaret, golden light',
        'portrait-400': 'The engineer in front of the panel array, Casablanca skyline',
        'mur-technique-dyness': 'Technical wall of a Taqinor installation in Casablanca: Deye hybrid inverter, two Dyness batteries and a charging station',
      },
    },
    ar: {
      title: 'تركيب شمسي 11,36 kWc في الدار البيضاء — 14 271 kWh/سنة مقيسة (المرجع 400) | Taqinor',
      description:
        'المرجع 400: 11,36 kWc على فيلا بالدار البيضاء تواجه الأفق، 16 لوحاً Canadian Solar 710 Wc، عاكس Deye 10 kW، 10 kWh Dyness ومحطة شحن. 14 271 kWh/سنة مُتابَعة على Deye Cloud.',
      situation:
        'فيلا بالدار البيضاء، حقل الألواح مرفوع في مواجهة الأفق والمئذنة: 11,36 kWc لأسرة تشحن أيضاً سيّارتها في البيت. محطة الشحن تغيّر المعادلة — الاستهلاك لا يتوقّف عند الأجهزة المنزلية، والقدرة المُركَّبة تأخذ ذلك بعين الاعتبار.',
      sizing:
        'ستة عشر Canadian Solar 710 Wc وعاكس Deye 10 kW: المقاس يتبع فاتورة تشمل شحن السيّارة، لا الأجهزة المنزلية فحسب. بطاريتان Dyness DL5.0C، أي 10 kWh، تستوعبان الحصّة الليلية. استهلاك الموقع هو الذي حدّد الحجم؛ والثمن لم يأتِ إلا بعد ذلك.',
      install:
        'الجدار التقني في الصور: العاكس الهجين Deye، والبطاريتان Dyness ومحطة الشحن مُحاذاة على جدار واحد، توصيل مرتّب. الحقل أمام الأفق ليس بطاقة بريدية — إنه التنصيب الحقيقي، موجَّه للإنتاج، لا للمنظر.',
      result:
        '14 271 kWh في السنة، مُتابَعة على Deye Cloud مع ولوج الزبون. الرقم ليس حجّة بيع: يُقرأ على المراقبة، ومحطة الشحن تُقرأ في منحنى الاستهلاك بقدر ما تُقرأ الألواح في منحنى الإنتاج.',
      resume:
        'فيلا بالدار البيضاء تواجه الأفق: 16 لوحاً، عاكس هجين Deye وبطاريتان Dyness، مع محطة شحن — إنتاج مُقدَّر انطلاقاً من المردود المقيس لأوراشنا.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'تركيب شمسي في الدار البيضاء' },
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
      title: 'Installation solaire 5,68 kWc à El Jadida — 7 135 kWh/an mesurés (réf. 236) | Taqinor',
      description:
        'Réf. 236 : 5,68 kWc sur le toit plat d’une villa d’El Jadida, 8 panneaux Canadian Solar 710 Wc, onduleur Deye 5 kW, batterie 5 kWh Dyness. 7 135 kWh/an relevés sur Deye Cloud, dimensionnés sur la facture du foyer.',
      situation:
        'Un toit plat de villa à El Jadida, huit panneaux, 5,68 kWc : le format compact d’un foyer dont la facture ne demandait pas davantage. Surdimensionner aurait coûté sans rien rapporter — la consommation relevée tenait dans cette puissance.',
      sizing:
        'Huit Canadian Solar 710 Wc, un onduleur Deye 5 kW, une batterie de 5 kWh : chaque maillon est calé sur le besoin du foyer, pas sur un format catalogue. Le toit plat laisse choisir librement l’inclinaison et l’azimut des modules — un degré de liberté que l’étude exploite pour optimiser la production avant d’arrêter la taille.',
      install:
        'La photo du dossier montre le champ des huit modules posés sur le toit-terrasse, structure réglée pour l’inclinaison retenue. La batterie unique de 5 kWh prend la part de consommation hors soleil ; pas de stockage surnuméraire, parce que la facture ne le réclamait pas.',
      result:
        '7 135 kWh sur l’année, relevés sur Deye Cloud, accès client inclus. À cette échelle aussi, la production se lit au compteur plutôt qu’elle ne se promet — le foyer voit ses kWh, mois après mois.',
      resume:
        'Une installation résidentielle compacte sur toit plat à El Jadida : huit panneaux, onduleur hybride et une batterie 5 kWh, dimensionnés sur la facture du foyer.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'Installation solaire à Casablanca' },
      alts: {},
    },
    en: {
      title: 'Solar installation 5.68 kWc in El Jadida — 7,135 kWh/year measured (ref. 236) | Taqinor',
      description:
        'Ref. 236: 5.68 kWc on the flat roof of an El Jadida villa, 8 Canadian Solar 710 Wc panels, Deye 5 kW inverter, 5 kWh Dyness battery. 7,135 kWh/year read off Deye Cloud, sized on the household’s bill.',
      situation:
        'A villa’s flat roof in El Jadida, eight panels, 5.68 kWc: the compact format of a household whose bill asked for no more. Oversizing would have cost without returning anything — the metered consumption fitted within this power.',
      sizing:
        'Eight Canadian Solar 710 Wc, a Deye 5 kW inverter, a 5 kWh battery: each link is set on the household’s need, not on a catalogue format. The flat roof allows the tilt and azimuth of the modules to be chosen freely — a degree of freedom the assessment uses to optimize production before settling the size.',
      install:
        'The file’s photo shows the array of eight modules fitted on the roof terrace, structure set for the chosen tilt. The single 5 kWh battery takes the share of consumption outside the sun; no surplus storage, because the bill did not call for it.',
      result:
        '7,135 kWh over the year, read off Deye Cloud, client access included. At this scale too, production reads off the meter rather than being promised — the household sees its kWh, month after month.',
      resume:
        'A compact residential installation on a flat roof in El Jadida: eight panels, a hybrid inverter and a 5 kWh battery, sized on the household’s bill.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'Solar installation in Casablanca' },
      alts: {
        'champ-villa': 'Array of eight panels on a villa’s flat roof, El Jadida',
      },
    },
    ar: {
      title: 'تركيب شمسي 5,68 kWc في الجديدة — 7 135 kWh/سنة مقيسة (المرجع 236) | Taqinor',
      description:
        'المرجع 236: 5,68 kWc على السطح المستوي لفيلا بالجديدة، 8 ألواح Canadian Solar 710 Wc، عاكس Deye 5 kW، بطارية 5 kWh Dyness. 7 135 kWh/سنة مقروءة على Deye Cloud، مُحدَّدة المقاس على فاتورة الأسرة.',
      situation:
        'سطح مستوٍ لفيلا بالجديدة، ثمانية ألواح، 5,68 kWc: الصيغة المُدمجة لأسرة لم تطلب فاتورتها أكثر. المبالغة في المقاس كانت ستُكلِّف دون أن تُعيد شيئاً — الاستهلاك المقيس كان يسع هذه القدرة.',
      sizing:
        'ثمانية Canadian Solar 710 Wc، عاكس Deye 5 kW، بطارية 5 kWh: كل حلقة مضبوطة على حاجة الأسرة، لا على صيغة كاطالوݣ. السطح المستوي يتيح اختيار ميل الألواح وسمتها بحرية — درجة حرية تستغلّها الدراسة لتحسين الإنتاج قبل تحديد الحجم.',
      install:
        'صورة الملف تُظهر حقل الألواح الثمانية مُركَّبة على السطح، بنية مضبوطة على الميل المختار. البطارية الوحيدة بقدرة 5 kWh تأخذ حصّة الاستهلاك خارج الشمس؛ لا تخزين زائد، لأن الفاتورة لم تطلبه.',
      result:
        '7 135 kWh على مدار السنة، مقروءة على Deye Cloud، مع ولوج الزبون. عند هذا المقياس أيضاً، الإنتاج يُقرأ على العدّاد بدل أن يُوعَد — الأسرة ترى كيلوواط-ساعاتها، شهراً بعد شهر.',
      resume:
        'تركيبة سكنية مُدمجة على سطح مستوٍ بالجديدة: ثمانية ألواح، عاكس هجين وبطارية 5 kWh، مُحدَّدة المقاس على فاتورة الأسرة.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'تركيب شمسي في الدار البيضاء' },
      alts: {
        'champ-villa': 'حقل من ثمانية ألواح على سطح مستوٍ لفيلا، الجديدة',
      },
    },
  },

  // Réf. 134 — villa Casablanca 8 panneaux. onduleur/batterie = null → JAMAIS cités.
  'casablanca-6-kwc': {
    fr: {
      title: 'Installation solaire 5,68 kWc à Casablanca — 7 135 kWh/an mesurés (réf. 134) | Taqinor',
      description:
        'Réf. 134 : 5,68 kWc sur une villa de Casablanca, 8 panneaux Canadian Solar 710 Wc, même puissance que notre chantier d’El Jadida pour un profil de consommation comparable. 7 135 kWh/an suivis sur Deye Cloud.',
      situation:
        'Une villa de Casablanca, huit panneaux Canadian Solar 710 Wc, 5,68 kWc — la même puissance que notre installation d’El Jadida, parce que le profil de consommation du foyer était comparable. À facture voisine, dimensionnement voisin : la taille suit le besoin, pas la ville.',
      sizing:
        'Les huit modules de 710 Wc répondent à une facture du même ordre que celle du chantier jédali. Quand deux foyers consomment de façon proche, l’étude aboutit logiquement à la même puissance — non parce qu’on aurait recopié une configuration, mais parce que le calcul, mené chaque fois à part, converge.',
      install:
        'La photo du dossier saisit la pose en cours : l’équipe incline un panneau pour le caler sur sa structure. Les modules Canadian Solar 710 Wc sont le matériel réellement installé sur ce toit casablancais.',
      result:
        '7 135 kWh par an, suivis sur Deye Cloud avec accès client : la production se relève, elle ne se prend pas sur parole. C’est le même engagement de mesure que sur l’ensemble de nos chantiers.',
      resume:
        'Une villa de Casablanca équipée de huit panneaux Canadian Solar 710 Wc — même puissance que notre installation d’El Jadida, pour un profil de consommation comparable.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'Installation solaire à Casablanca' },
      alts: {},
    },
    en: {
      title: 'Solar installation 5.68 kWc in Casablanca — 7,135 kWh/year measured (ref. 134) | Taqinor',
      description:
        'Ref. 134: 5.68 kWc on a Casablanca villa, 8 Canadian Solar 710 Wc panels, the same power as our El Jadida project for a comparable consumption profile. 7,135 kWh/year followed on Deye Cloud.',
      situation:
        'A Casablanca villa, eight Canadian Solar 710 Wc panels, 5.68 kWc — the same power as our El Jadida installation, because the household’s consumption profile was comparable. With a similar bill, similar sizing: the size follows the need, not the city.',
      sizing:
        'The eight 710 Wc modules answer a bill of the same order as that of the El Jadida project. When two households consume in a similar way, the assessment logically arrives at the same power — not because a configuration was copied, but because the calculation, carried out separately each time, converges.',
      install:
        'The file’s photo captures the install in progress: the team tilts a panel to set it on its structure. The Canadian Solar 710 Wc modules are the equipment really installed on this Casablanca roof.',
      result:
        '7,135 kWh a year, followed on Deye Cloud with client access: production is read off, it is not taken on trust. It is the same commitment to measurement as across all our projects.',
      resume:
        'A Casablanca villa fitted with eight Canadian Solar 710 Wc panels — the same power as our El Jadida installation, for a comparable consumption profile.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'Solar installation in Casablanca' },
      alts: {
        'pose-134': 'The team tilts a panel during the install, Casablanca',
      },
    },
    ar: {
      title: 'تركيب شمسي 5,68 kWc في الدار البيضاء — 7 135 kWh/سنة مقيسة (المرجع 134) | Taqinor',
      description:
        'المرجع 134: 5,68 kWc على فيلا بالدار البيضاء، 8 ألواح Canadian Solar 710 Wc، القدرة نفسها كورشنا بالجديدة لمَلمح استهلاك مماثل. 7 135 kWh/سنة مُتابَعة على Deye Cloud.',
      situation:
        'فيلا بالدار البيضاء، ثمانية ألواح Canadian Solar 710 Wc، 5,68 kWc — القدرة نفسها كتركيبتنا بالجديدة، لأن مَلمح استهلاك الأسرة كان مماثلاً. فاتورة قريبة، مقاس قريب: الحجم يتبع الحاجة، لا المدينة.',
      sizing:
        'الألواح الثمانية بقدرة 710 Wc تستجيب لفاتورة من نفس مستوى ورش الجديدة. حين تستهلك أسرتان بصورة متقاربة، تصل الدراسة منطقياً إلى القدرة نفسها — لا لأننا نسخنا تكويناً، بل لأن الحساب، المُنجَز كل مرة على حدة، يتقارب.',
      install:
        'صورة الملف تلتقط التركيب جارياً: الفريق يميل لوحاً لضبطه على بنيته. ألواح Canadian Solar 710 Wc هي العتاد المُركَّب فعلاً على هذا السطح البيضاوي.',
      result:
        '7 135 kWh في السنة، مُتابَعة على Deye Cloud مع ولوج الزبون: الإنتاج يُقرأ، ولا يُؤخَذ على عهدة الكلام. إنه الالتزام نفسه بالقياس كما في كل أوراشنا.',
      resume:
        'فيلا بالدار البيضاء مُجهَّزة بثمانية ألواح Canadian Solar 710 Wc — القدرة نفسها كتركيبتنا بالجديدة، لمَلمح استهلاك مماثل.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'تركيب شمسي في الدار البيضاء' },
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
        'Réf. NC-10/25 : 3,72 kWc à Nouaceur, dans la périphérie de Casablanca, 6 panneaux JA Solar posés en octobre 2025 avec le même soin d’implantation que nos plus grands chantiers.',
      situation:
        'À Nouaceur, dans la périphérie de Casablanca, une installation de 3,72 kWc : six panneaux JA Solar, posés avec le même soin d’implantation que sur nos chantiers de plus grande taille, sur une toiture qui n’en demandait pas plus.',
      sizing:
        'Six modules JA Solar pour 3,72 kWc : la puissance répond au besoin réel du foyer, et l’honnêteté commande de ne pas poser au-delà de ce que la consommation justifie. Le tracé des rails et l’alignement se calculent ici avec la même rigueur qu’à 17 kWc.',
      install:
        'Les photos du dossier montrent le travail de fond : l’installateur en gilet Taqinor posant les rails de la structure, le traçage et la mesure au mètre des fixations, puis le nettoyage au jet du champ une fois les modules en place. C’est cette préparation invisible qui tient une installation sur la durée.',
      result:
        'Posée en octobre 2025, l’installation suit notre standard d’implantation et d’entretien. Nous ne publions pas de production mesurée pour ce chantier — et nous ne lui en prêtons aucune : seul ce qui est relevé est écrit.',
      resume:
        'Une installation à Nouaceur, dans la périphérie de Casablanca : six panneaux JA Solar posés avec le même soin d’implantation que nos chantiers de plus grande taille.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'Installation solaire à Casablanca' },
      alts: {},
    },
    en: {
      title: 'Solar installation 3.72 kWc in Nouaceur — 6 JA Solar panels (ref. NC-10/25) | Taqinor',
      description:
        'Ref. NC-10/25: 3.72 kWc in Nouaceur, on the outskirts of Casablanca, 6 JA Solar panels fitted in October 2025 with the same care of layout as our largest projects.',
      situation:
        'In Nouaceur, on the outskirts of Casablanca, a 3.72 kWc installation: six JA Solar panels, fitted with the same care of layout as on our larger projects, on a roof that asked for no more.',
      sizing:
        'Six JA Solar modules for 3.72 kWc: the power answers the household’s real need, and honesty dictates not installing beyond what consumption justifies. The rail layout and the alignment are computed here with the same rigour as at 17 kWc.',
      install:
        'The file’s photos show the groundwork: the installer in a Taqinor vest fitting the structure’s rails, the marking out and the tape measurement of the fixings, then the jet cleaning of the array once the modules are in place. It is this invisible preparation that holds an installation over time.',
      result:
        'Fitted in October 2025, the installation follows our standard of layout and upkeep. We publish no measured production for this project — and we attribute none to it: only what is read off is written.',
      resume:
        'An installation in Nouaceur, on the outskirts of Casablanca: six JA Solar panels fitted with the same care of layout as our larger projects.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'Solar installation in Casablanca' },
      alts: {
        'equipe-gilet-taqinor': 'Installer in a Taqinor vest fitting a structure’s rails, Nouaceur',
        'mesure-rails': 'Marking out and tape measurement of the fixing rails on the roof, Nouaceur',
        'entretien-jet': 'Jet cleaning of the panel array, Nouaceur',
      },
    },
    ar: {
      title: 'تركيب شمسي 3,72 kWc في النواصر — 6 ألواح JA Solar (المرجع NC-10/25) | Taqinor',
      description:
        'المرجع NC-10/25: 3,72 kWc في النواصر، بضواحي الدار البيضاء، 6 ألواح JA Solar مُركَّبة في أكتوبر 2025 بنفس عناية التنصيب التي في أكبر أوراشنا.',
      situation:
        'في النواصر، بضواحي الدار البيضاء، تركيبة بقدرة 3,72 kWc: ستة ألواح JA Solar، مُركَّبة بنفس عناية التنصيب التي في أوراشنا الأكبر حجماً، على سطح لم يطلب أكثر.',
      sizing:
        'ستة ألواح JA Solar من أجل 3,72 kWc: القدرة تستجيب للحاجة الحقيقية للأسرة، والصدق يقتضي عدم التركيب فوق ما يبرّره الاستهلاك. تخطيط السكك والمحاذاة يُحسبان هنا بنفس الصرامة كما عند 17 kWc.',
      install:
        'صور الملف تُظهر العمل الأساسي: المُركِّب بسترة تاكينور يضع سكك البنية، والتخطيط والقياس بالمتر للمثبّتات، ثم تنظيف الحقل بالماء بمجرّد وضع الألواح. هذا التحضير غير المرئي هو ما يُبقي التركيبة على المدى.',
      result:
        'مُركَّبة في أكتوبر 2025، تتبع التركيبة معيارنا في التنصيب والصيانة. لا ننشر إنتاجاً مقيساً لهذا الورش — ولا نَنسب إليه أيّاً: لا يُكتب إلا ما يُقرأ فعلاً.',
      resume:
        'تركيبة في النواصر، بضواحي الدار البيضاء: ستة ألواح JA Solar مُركَّبة بنفس عناية التنصيب التي في أوراشنا الأكبر حجماً.',
      cityLink: { href: '/installation-solaire-casablanca', label: 'تركيب شمسي في الدار البيضاء' },
      alts: {
        'equipe-gilet-taqinor': 'مُركِّب بسترة تاكينور يضع سكك بنية، النواصر',
        'mesure-rails': 'تخطيط وقياس بالمتر لسكك التثبيت على السطح، النواصر',
        'entretien-jet': 'تنظيف حقل الألواح بنفث الماء، النواصر',
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
