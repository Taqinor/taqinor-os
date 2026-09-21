/**
 * CALX120 — animation PURE de la course du soleil, sur une JOURNÉE ou sur l'ANNÉE.
 * ----------------------------------------------------------------------------
 * Constat de la tâche : le soleil ne bouge qu'au geste sur le curseur d'heure
 * (`roof-tool-pro11.ts`, W87), un pas à la fois — aucune lecture continue n'existe,
 * alors que la scène 3D projette déjà de vraies ombres (`scene3d.ts castShadow`).
 *
 * Ce module ne CALCULE aucune position solaire lui-même (aucune deuxième formule) :
 * `sunriseSunsetHours` délègue entièrement à `sunDirection` (`apps/web/src/lib/
 * roofPro2.ts`, LA fonction canonique déjà utilisée par `scene3d.ts`/le curseur
 * d'heure W87) pour trouver le lever et le coucher du jour affiché.
 * `createSoleilPlayer` ne fait qu'avancer `sunDay`/`sunHour` PAS À PAS et DÉLÈGUE
 * l'écriture + le re-rendu à l'appelant (`onStep`) — exactement comme le curseur
 * d'heure existant écrit `ctx.sunHour` puis appelle `renderActive()`.
 *
 * Temps et planificateur INJECTÉS (`schedule`/`cancel`) : aucun `setTimeout`/
 * `requestAnimationFrame` réel n'est touché ici, donc testable sans mock de minuteur
 * — l'appelant réel (`roof-tool-pro11.ts`) injecte `window.setTimeout`/`clearTimeout`,
 * les tests injectent un planificateur FAUX qu'ils déclenchent à la main.
 */
import { sunDirection } from '../../lib/roofPro2';

/** L'état minimal animé : le jour de l'année (1–366) et l'heure solaire (0–24). */
export interface SoleilPlayState {
  sunDay: number;
  sunHour: number;
}

export interface SunriseSunset {
  /** Heure solaire décimale du lever (première heure d'élévation > 0). */
  riseHour: number;
  /** Heure solaire décimale du coucher (dernière heure d'élévation > 0). */
  setHour: number;
}

/**
 * Lever/coucher (heure solaire décimale) d'un jour donné à une latitude donnée,
 * échantillonnés tous les `stepH` — MÊME formule que `sunDirection`, jamais une
 * seconde. `null` si le soleil ne se lève pas sur l'échantillonnage (latitude
 * polaire, jour entièrement sous l'horizon) — jamais une plage inventée.
 */
export function sunriseSunsetHours(latDeg: number, dayOfYear: number, stepH = 0.25): SunriseSunset | null {
  let riseHour: number | null = null;
  let setHour: number | null = null;
  for (let h = 0; h <= 24; h += stepH) {
    const { elevationDeg } = sunDirection(latDeg, dayOfYear, h);
    if (elevationDeg > 0) {
      if (riseHour === null) riseHour = h;
      setHour = h;
    }
  }
  if (riseHour === null || setHour === null || setHour <= riseHour) return null;
  return { riseHour, setHour };
}

export interface SoleilPlayOptions {
  /** Planifie l'exécution de `cb`, renvoie un identifiant pour `cancel`. Jamais
   *  `requestAnimationFrame`/`setTimeout` en dur ici : l'appelant réel injecte
   *  `window.setTimeout`/`clearTimeout`, un test injecte un planificateur FAUX. */
  schedule: (cb: () => void) => number;
  cancel: (handle: number) => void;
  /** `true` quand l'utilisateur/le navigateur refuse les animations
   *  (`prefers-reduced-motion`, déjà transmis au builder via `opts.reducedMotion`) :
   *  la lecture bascule alors en PAS-À-PAS — UN SEUL pas est appliqué, jamais de
   *  boucle programmée. */
  reducedMotion: boolean;
}

export interface SoleilPlayer {
  /** Lecture JOUR : de `bounds.riseHour` à `bounds.setHour`, par pas de `stepHour`
   *  (SAISI par l'utilisateur — le pas du curseur d'heure existant), jour fixe. */
  playDay(from: SoleilPlayState, bounds: SunriseSunset, stepHour: number, onStep: (s: SoleilPlayState) => void): void;
  /** Lecture ANNÉE : même heure solaire, `sunDay` avance de `stepDays` (défaut : un
   *  pas mensuel) à chaque pas, jusqu'à 366. */
  playYear(from: SoleilPlayState, onStep: (s: SoleilPlayState) => void, stepDays?: number): void;
  /** Arrête toute lecture en cours (geste utilisateur) — le DERNIER pas rendu reste
   *  l'état affiché, rien n'est ré-écrit ni annulé. */
  stop(): void;
  /** `true` tant qu'une boucle d'animation est programmée (jamais vrai en
   *  `reducedMotion`, puisqu'aucune boucle n'y est lancée). */
  readonly playing: boolean;
}

/** Convention de dessin — pas par défaut de la lecture ANNÉE (≈ un mois). */
const PAS_ANNEE_JOURS_DEFAUT = 30;

export function createSoleilPlayer(opts: SoleilPlayOptions): SoleilPlayer {
  let handle: number | null = null;
  let playingFlag = false;

  function stop(): void {
    if (handle !== null) opts.cancel(handle);
    handle = null;
    playingFlag = false;
  }

  /** Fait dérouler `steps` un par un, via le planificateur injecté. Le drapeau
   *  `playing` et le handle courant sont TOUJOURS cohérents avec ce que `stop()`
   *  observerait — y compris pendant le tout dernier pas, où ils basculent AVANT
   *  `onStep` (pour que l'appelant, dans son propre callback, voie déjà l'arrêt). */
  function runSteps(steps: SoleilPlayState[], onStep: (s: SoleilPlayState) => void): void {
    stop();
    if (!steps.length) return;
    if (opts.reducedMotion) {
      // Refus d'animation (D-CALX/lot 2) : UN SEUL pas appliqué, aucune boucle —
      // la lecture suivante se fera au prochain geste (pas-à-pas).
      onStep(steps[0]);
      return;
    }
    playingFlag = true;
    let i = 0;
    const tick = (): void => {
      const s = steps[i];
      const isLast = i === steps.length - 1;
      i += 1;
      if (isLast) {
        handle = null;
        playingFlag = false;
      } else {
        handle = opts.schedule(tick);
      }
      onStep(s);
    };
    handle = opts.schedule(tick);
  }

  function playDay(from: SoleilPlayState, bounds: SunriseSunset, stepHour: number, onStep: (s: SoleilPlayState) => void): void {
    const step = stepHour > 0 ? stepHour : 1;
    const steps: SoleilPlayState[] = [];
    for (let h = bounds.riseHour; h <= bounds.setHour; h += step) {
      steps.push({ sunDay: from.sunDay, sunHour: h });
    }
    runSteps(steps, onStep);
  }

  function playYear(from: SoleilPlayState, onStep: (s: SoleilPlayState) => void, stepDays = PAS_ANNEE_JOURS_DEFAUT): void {
    const step = stepDays > 0 ? stepDays : PAS_ANNEE_JOURS_DEFAUT;
    const steps: SoleilPlayState[] = [];
    for (let d = from.sunDay; d <= 366; d += step) {
      steps.push({ sunDay: d, sunHour: from.sunHour });
    }
    runSteps(steps, onStep);
  }

  return {
    playDay,
    playYear,
    stop,
    get playing() {
      return playingFlag;
    },
  };
}
