/**
 * Données et prose communes aux pages ville FR / EN / AR
 * (`installation-solaire-[city].astro` et ses jumeaux localisés) — ENF19 :
 * une seule copie du calcul au lieu d'une par langue. Seuls les libellés
 * (`intro`, `serviceType`, `name`) restent propres à chaque page.
 */
import { REALISATIONS, realisationByRef } from './realisations';
import type { City } from './realisations';
import type { CityContent } from './cityContent';
import { NAP } from './nap';
import { YIELD_TABLE } from './yieldTable';
import { caseStudyBySlug } from './caseStudies';
import { cityContentBySlug } from './cityContent';
import type { Locale } from '../i18n/config';

/** Chantiers affichés : en ville, voisins, et — sans chantier local — les plus proches. */
export function cityInstallLists(c: City) {
  const featured = c.featuredRefs.map((ref) => realisationByRef(ref)).filter(Boolean);
  const inCity = featured.filter((r) => r!.ville === c.name);
  const nearby = featured.filter((r) => r!.ville !== c.name);
  const closest = c.hasLocalInstall ? [] : REALISATIONS.slice(0, 3);
  return { featured, inCity, nearby, closest };
}

/** WJ73 — rendement moyen kWh/kWc/an des chantiers réellement affichés (`null` si aucun relevé publié). */
export function avgYieldPerKwcOf(shownInstalls: ReturnType<typeof realisationByRef>[]) {
  const yieldSamples = shownInstalls
    .filter((r) => r!.productionNum && r!.kwcNum)
    .map((r) => r!.productionNum! / r!.kwcNum!);
  return yieldSamples.length
    ? Math.round(yieldSamples.reduce((sum, y) => sum + y, 0) / yieldSamples.length)
    : null;
}

/** Prose de la ville avec `{intro}` résolu (heroLead, piliers, nuance ROI, notes…). */
export function cityProse(cc: CityContent, intro: string) {
  const fillIntro = (s: string) => s.replaceAll('{intro}', intro);
  return {
    heroLead: fillIntro(cc.heroLead),
    sunshineContext: fillIntro(cc.sunshineContext),
    closer: fillIntro(cc.closer),
    pillarStudy: { heading: fillIntro(cc.pillars.study.heading), body: fillIntro(cc.pillars.study.body) },
    pillarMeasure: { heading: fillIntro(cc.pillars.measure.heading), body: fillIntro(cc.pillars.measure.body) },
    pillarCompliance: { heading: fillIntro(cc.pillars.compliance.heading), body: fillIntro(cc.pillars.compliance.body) },
    roiNuance: fillIntro(cc.roiNuance),
    delegataireNote: cc.delegataireNote ? fillIntro(cc.delegataireNote) : undefined,
    nearestInstallNote: cc.nearestInstallNote ? fillIntro(cc.nearestInstallNote) : undefined,
    title: fillIntro(cc.title),
    description: fillIntro(cc.description),
  };
}

/** JSON-LD `Service` d'une page ville (même fournisseur NAP quelle que soit la langue). */
export function cityServiceJsonLd(serviceType: string, name: string, cityName: string) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Service',
    serviceType,
    name,
    areaServed: { '@type': 'City', name: cityName },
    provider: {
      '@type': 'LocalBusiness',
      name: NAP.name,
      url: NAP.url,
      telephone: NAP.phone,
      email: NAP.email,
      areaServed: NAP.serviceArea.map((n) => (n === 'Maroc' ? { '@type': 'Country', name: n } : { '@type': 'City', name: n })),
    },
  };
}

/** Photo de marque neutre (sans ville identifiable) quand la ville n'a pas de chantier local. */
export const NEUTRAL_CITY_HERO = { name: 'crepuscule-penthouse', widths: [1600, 1024, 640], ratio: 4 / 3 };

/**
 * Tout ce qu'une page ville calcule avant le rendu, identique en FR/EN/AR : listes de chantiers,
 * rendement moyen mesuré, tableau de rendement de la ville, prose (`{intro}` résolu) et alt
 * localisé des cartes chantier. La page ne garde que ses libellés propres.
 */
export function cityPageBase(c: City, intro: string, locale: Locale = 'fr') {
  const lists = cityInstallLists(c);
  const shownInstalls = lists.inCity.length > 0 ? lists.inCity : lists.closest;
  const cardAlt = (r: NonNullable<(typeof lists.featured)[number]>) => {
    const cs = caseStudyBySlug(r.slug, locale);
    return cs.alts[r.photos[0].name] ?? r.photos[0].alt;
  };
  return {
    ...lists,
    shownInstalls,
    avgYieldPerKwc: avgYieldPerKwcOf(shownInstalls),
    cityYieldTable: YIELD_TABLE[c.slug],
    /** Plein sud 29° brut de la table PVGIS (les pages FR le rebasent sur les pertes totales). */
    southOptimalYield: YIELD_TABLE[c.slug]?.grid['0']['29'] as number | undefined,
    cardAlt,
    ...cityProse(cityContentBySlug(c.slug, locale), intro),
  };
}
