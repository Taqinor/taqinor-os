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
 */

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
   * Lien ville contextuel. `null` quand aucune page ville pertinente n'existe
   * (le template gère déjà la ville exacte via `cityPage` ; ce champ sert à
   * proposer la ville de service la PLUS proche pour les chantiers hors zone —
   * El Jadida et Nouaceur, tous deux en région Casablanca-Settat → Casablanca).
   */
  cityLink: CaseStudyLink | null;
}

/**
 * Repli sûr pour tout slug sans entrée dédiée : prose neutre, sans fait
 * chiffré inventé, conforme à STYLE.md. Aucun lien ville par défaut.
 */
export const FALLBACK_CASE_STUDY: CaseStudyContent = {
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
  cityLink: null,
};

export const CASE_STUDIES: Record<string, CaseStudyContent> = {
  // Réf. 468 — la plus grande résidentielle de 2026. Production publiée.
  'el-jadida-17-kwc': {
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
    cityLink: { href: '/installation-solaire-casablanca', label: 'Installation solaire à Casablanca' },
  },

  // Réf. 400 — villa Casablanca face skyline + borne de recharge. Production publiée.
  'casablanca-11-kwc': {
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
    cityLink: { href: '/installation-solaire-casablanca', label: 'Installation solaire à Casablanca' },
  },

  // Réf. 236 — résidentielle compacte toit plat El Jadida. Production publiée.
  'el-jadida-6-kwc': {
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
    cityLink: { href: '/installation-solaire-casablanca', label: 'Installation solaire à Casablanca' },
  },

  // Réf. 134 — villa Casablanca 8 panneaux. onduleur/batterie = null → JAMAIS cités.
  'casablanca-6-kwc': {
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
    cityLink: { href: '/installation-solaire-casablanca', label: 'Installation solaire à Casablanca' },
  },

  // Réf. NC-10/25 — Nouaceur 6 × JA Solar. production/onduleur/batterie = null → JAMAIS de chiffre de prod.
  'nouaceur-4-kwc': {
    title: 'Installation solaire 3,72 kWc à Nouaceur — 6 panneaux JA Solar (réf. NC-10/25) | Taqinor',
    description:
      'Réf. NC-10/25 : 3,72 kWc à Nouaceur, dans la périphérie de Casablanca, 6 panneaux JA Solar posés en octobre 2025 avec le même soin d’implantation que nos plus grands chantiers.',
    situation:
      'À Nouaceur, dans la périphérie de Casablanca, une petite installation de 3,72 kWc : six panneaux JA Solar. Le format est modeste, le soin ne l’est pas — c’est la même méthode d’implantation que sur nos chantiers de plus grande taille, appliquée à une toiture qui n’en demandait pas plus.',
    sizing:
      'Six modules JA Solar pour 3,72 kWc : la puissance répond à un besoin réduit, et l’honnêteté commande de ne pas poser au-delà de ce que la consommation justifie. Petit chantier ne veut pas dire chantier bâclé : le tracé des rails et l’alignement se calculent avec la même rigueur qu’à 17 kWc.',
    install:
      'Les photos du dossier montrent le travail de fond : l’installateur en gilet Taqinor posant les rails de la structure, le traçage et la mesure au mètre des fixations, puis le nettoyage au jet du champ une fois les modules en place. C’est cette préparation invisible qui tient une installation sur la durée.',
    result:
      'Posée en octobre 2025, l’installation suit notre standard d’implantation et d’entretien. Nous ne publions pas de production mesurée pour ce chantier — et nous ne lui en prêtons aucune : seul ce qui est relevé est écrit.',
    cityLink: { href: '/installation-solaire-casablanca', label: 'Installation solaire à Casablanca' },
  },
};

/**
 * Renvoie la prose d'une étude de cas par slug, avec repli sûr.
 */
export const caseStudyBySlug = (slug: string): CaseStudyContent =>
  CASE_STUDIES[slug] ?? FALLBACK_CASE_STUDY;
