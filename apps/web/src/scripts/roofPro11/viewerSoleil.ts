/**
 * LOT 6 (D-ACAL-132 à 138) — la visionneuse au SOLEIL QUI BOUGE des liens de confiance.
 *
 * Relie la barre `components/proposition/BarreSoleil.astro` à la poignée de la visionneuse pleine
 * (`viewerFullBoot.ts`) : lecture de la journée, curseur d'heure (lever → coucher), Hiver / Été, teinte de
 * chaque panneau du pan actif par son accès solaire ENREGISTRÉ, carte bornée au toit. AUCUN second moteur :
 * le soleil est `sunDirection` (via `scene3d.ts` et `soleilPlay.ts`, les modules de l'atelier), la teinte
 * est `scene3d.setSolarAccessHeatmap` avec la palette « atelier », la lecture est `createSoleilPlayer`.
 *
 * Chargé par `import()` APRÈS le démarrage de la visionneuse pleine : jamais dans le premier rendu.
 * Tout échec ici masque la barre et laisse la visionneuse telle quelle (jamais un throw vers la page).
 */
import { couleurAccesActive } from '../../lib/shadingEngine';
import type { RoofLayout } from '../../lib/proposition';
import { bornesCarte, JOUR_ETE, JOUR_HIVER, libelleInstant, libelleJournee, type LangueSoleil, type VisionneuseSoleil } from '../../lib/visionneuseSoleil';
import { createSoleilPlayer, sunriseSunsetHours, type SunriseSunset } from './soleilPlay';
import type { ViewerFullHandle } from './viewerFullBoot';

export interface OptionsSoleil {
  barre: HTMLElement;
  poignee: ViewerFullHandle;
  soleil: VisionneuseSoleil;
  /** Le layout que la visionneuse rejoue (bornes de carte). */
  layout: RoofLayout;
  /** Faux quand le client regarde une autre taille que celle du devis : les valeurs ne décrivent pas ces panneaux. */
  avecTeinte: boolean;
  reducedMotion: boolean;
}

/** Pas de la lecture et du curseur (h) — le pas du curseur d'heure de l'atelier. */
const PAS_HEURE = 1;
/** Inclinaison maximale de la visionneuse de confiance (D-ACAL-138). */
const INCLINAISON_MAX = 60;

const langue = (): LangueSoleil => {
  const l = document.documentElement.lang;
  return l === 'ar' || l === 'en' ? l : 'fr';
};

/** Lever/coucher arrondis aux heures pleines de l'intérieur ; `null` si le soleil ne se lève pas. */
export function bornesJournee(lat: number, jour: number): SunriseSunset | null {
  const b = sunriseSunsetHours(lat, jour);
  if (!b) return null;
  const r = { riseHour: Math.ceil(b.riseHour), setHour: Math.floor(b.setHour) };
  return r.setHour > r.riseHour ? r : null;
}

/** Fonction cellule → couleur du pan actif, ou `null` quand aucune valeur enregistrée ne le décrit. */
export function couleurParPanneau(soleil: VisionneuseSoleil, indexActif: number) {
  const zone = soleil.zones.find((z) => z.index === indexActif);
  if (!zone) return null;
  // Module non calculé (`null`) ou absent : `null`, la scène y garde la teinte d'origine (jamais un blanc gainé).
  return (cellule: number) => {
    const a = zone.acces[cellule];
    return typeof a === 'number' ? couleurAccesActive(a, 'atelier') : null;
  };
}

/** Branche la barre ; renvoie la fonction qui la débranche (appelée au démontage de la visionneuse). */
export function attacherSoleil(o: OptionsSoleil): () => void {
  const { barre, poignee, soleil } = o;
  const arret = new AbortController();
  const q = <T extends Element>(sel: string) => barre.querySelector<T>(sel);
  const lecture = q<HTMLButtonElement>('[data-soleil-lecture]');
  const curseur = q<HTMLInputElement>('[data-soleil-heure]');
  const quand = q<HTMLElement>('[data-soleil-quand]');
  const saisons = [...barre.querySelectorAll<HTMLButtonElement>('[data-soleil-saison]')];
  const controles: Array<HTMLButtonElement | HTMLInputElement> = [...saisons, ...(lecture ? [lecture] : []), ...(curseur ? [curseur] : [])];
  const lat = (o.layout.zones[0]?.vertices[0] ?? [0, 0])[1];
  const player = createSoleilPlayer({
    schedule: (cb) => window.setTimeout(cb, 700),
    cancel: (h) => window.clearTimeout(h),
    reducedMotion: o.reducedMotion,
  });
  let jour = soleil.ouverture.jour;
  let heure = soleil.ouverture.heure;
  let bornes = bornesJournee(lat, jour);

  const afficher = () => {
    const texte = libelleInstant(jour, heure, langue());
    if (quand) quand.textContent = texte;
    if (curseur && bornes) {
      curseur.min = String(bornes.riseHour);
      curseur.max = String(bornes.setHour);
      curseur.value = String(Math.round(heure));
      curseur.setAttribute('aria-valuetext', texte);
      const rempli = ((Number(curseur.value) - bornes.riseHour) / (bornes.setHour - bornes.riseHour)) * 100;
      curseur.style.setProperty('--soleil-rempli', `${Math.max(0, Math.min(100, rempli))}%`);
    }
    const journee = q<HTMLElement>('[data-soleil-journee]');
    if (journee) journee.textContent = bornes ? libelleJournee(bornes.riseHour, bornes.setHour, langue()) : '';
    for (const b of saisons) b.setAttribute('aria-pressed', String((b.dataset.soleilSaison === 'ete' ? JOUR_ETE : JOUR_HIVER) === jour));
    if (lecture) {
      lecture.setAttribute('aria-pressed', String(player.playing));
      lecture.disabled = !bornes;
    }
  };
  const poser = (j: number, h: number) => {
    jour = j;
    heure = h;
    try {
      poignee.poserInstant(j, h);
    } catch (e) {
      console.warn('[visionneuse-soleil] rendu :', e);
    }
    afficher();
  };

  try {
    const couleur = o.avecTeinte ? couleurParPanneau(soleil, poignee.indexActif) : null;
    if (couleur) poignee.teinter(couleur);
    q<HTMLElement>('[data-soleil-legende]')?.toggleAttribute('data-soleil-visible', !!couleur);
    const b = bornesCarte(o.layout, poignee.zoomInitial);
    if (b) {
      poignee.carte.setMaxBounds(b.bornes);
      poignee.carte.setMinZoom(b.zoomMin);
    }
    poignee.carte.setMaxPitch(INCLINAISON_MAX);
  } catch (e) {
    console.warn('[visionneuse-soleil] teinte / carte :', e);
  }

  lecture?.addEventListener('click', () => {
    if (player.playing) {
      player.stop();
      afficher();
      return;
    }
    if (!bornes) return;
    // Refus d'animation : UN pas (l'heure suivante, retour au lever après le coucher), jamais une boucle.
    const suivante = heure + PAS_HEURE <= bornes.setHour ? Math.max(bornes.riseHour, Math.round(heure) + PAS_HEURE) : bornes.riseHour;
    const depart = o.reducedMotion ? { riseHour: suivante, setHour: bornes.setHour } : bornes;
    player.playDay({ sunDay: jour, sunHour: heure }, depart, PAS_HEURE, (s) => poser(s.sunDay, s.sunHour));
    afficher();
  }, { signal: arret.signal });
  curseur?.addEventListener('input', () => {
    const h = Number(curseur.value);
    if (!Number.isFinite(h)) return;
    player.stop();
    poser(jour, h);
  }, { signal: arret.signal });
  for (const b of saisons) {
    b.addEventListener('click', () => {
      player.stop();
      const j = b.dataset.soleilSaison === 'ete' ? JOUR_ETE : JOUR_HIVER;
      bornes = bornesJournee(lat, j);
      poser(j, bornes ? Math.max(bornes.riseHour, Math.min(bornes.setHour, heure)) : heure);
    }, { signal: arret.signal });
  }
  // La langue de la page change par `applyLang` (attribut `lang` du document) : le libellé suit.
  const observateur = new MutationObserver(afficher);
  observateur.observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });

  for (const c of controles) c.disabled = false;
  barre.dataset.soleilPret = '';
  afficher();

  return () => {
    player.stop();
    arret.abort();
    observateur.disconnect();
    for (const c of controles) c.disabled = true;
    delete barre.dataset.soleilPret;
  };
}
