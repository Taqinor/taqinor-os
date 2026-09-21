// CALX120 — animation pure de la course du soleil. Temps et planificateur INJECTÉS :
// aucun `setTimeout` réel n'est utilisé, un planificateur FAUX est déclenché à la main
// pour dérouler les pas dans l'ordre.
import { describe, expect, it } from 'vitest';
import { createSoleilPlayer, sunriseSunsetHours, type SoleilPlayState } from './soleilPlay';

/** Un planificateur FAUX : `schedule` empile le rappel, le test le déclenche lui-même
 *  en le retirant de la file — ce qui simule un minuteur réel SANS horloge réelle. */
function fakeScheduler() {
  const queue: Array<() => void> = [];
  const canceled: number[] = [];
  let nextHandle = 1;
  return {
    schedule: (cb: () => void): number => {
      queue.push(cb);
      return nextHandle++;
    },
    cancel: (h: number): void => {
      canceled.push(h);
    },
    /** Déroule TOUS les pas actuellement programmés (et ceux qu'ils re-programment),
     *  jusqu'à ce que la file soit vide — la fin naturelle de la lecture. */
    drainAll: (): void => {
      while (queue.length) queue.shift()!();
    },
    /** Déclenche UN SEUL pas programmé, sans dérouler le reste. */
    step: (): void => {
      const cb = queue.shift();
      if (cb) cb();
    },
    queue,
    canceled,
  };
}

describe('CALX120 — sunriseSunsetHours', () => {
  it('trouve un lever/coucher au solstice d’été à une latitude marocaine', () => {
    const bounds = sunriseSunsetHours(33.5, 172, 0.25);
    expect(bounds).not.toBeNull();
    expect(bounds!.riseHour).toBeLessThan(7);
    expect(bounds!.setHour).toBeGreaterThan(17);
    expect(bounds!.setHour).toBeGreaterThan(bounds!.riseHour);
  });

  it('trouve un lever/coucher plus court au solstice d’hiver (même latitude)', () => {
    const ete = sunriseSunsetHours(33.5, 172, 0.25)!;
    const hiver = sunriseSunsetHours(33.5, 355, 0.25)!;
    expect(hiver.setHour - hiver.riseHour).toBeLessThan(ete.setHour - ete.riseHour);
  });
});

describe('CALX120 — lecture JOURNÉE', () => {
  it('parcourt les heures dans l’ordre, s’arrête AUTOMATIQUEMENT au dernier pas', () => {
    const sched = fakeScheduler();
    const player = createSoleilPlayer({ schedule: sched.schedule, cancel: sched.cancel, reducedMotion: false });
    const seen: number[] = [];

    player.playDay({ sunDay: 172, sunHour: 6 }, { riseHour: 6, setHour: 9 }, 1, (s) => seen.push(s.sunHour));
    // Rien n'est rendu tant que le planificateur (le temps) n'a pas avancé.
    expect(seen).toEqual([]);
    expect(player.playing).toBe(true);

    sched.drainAll();
    expect(seen).toEqual([6, 7, 8, 9]);
    expect(player.playing).toBe(false); // dernier pas atteint → arrêt automatique
  });

  it('le jour reste FIXE pendant la lecture (seule l’heure avance)', () => {
    const sched = fakeScheduler();
    const player = createSoleilPlayer({ schedule: sched.schedule, cancel: sched.cancel, reducedMotion: false });
    const seen: SoleilPlayState[] = [];
    player.playDay({ sunDay: 45, sunHour: 8 }, { riseHour: 8, setHour: 10 }, 1, (s) => seen.push(s));
    sched.drainAll();
    expect(seen.every((s) => s.sunDay === 45)).toBe(true);
  });

  it('un GESTE utilisateur (stop) annule le pas programmé restant : l’état affiché reste le dernier pas RENDU', () => {
    const sched = fakeScheduler();
    const player = createSoleilPlayer({ schedule: sched.schedule, cancel: sched.cancel, reducedMotion: false });
    const seen: number[] = [];

    player.playDay({ sunDay: 172, sunHour: 6 }, { riseHour: 6, setHour: 20 }, 1, (s) => seen.push(s.sunHour));
    sched.step(); // pas 1 : 6 h
    sched.step(); // pas 2 : 7 h
    player.stop(); // geste utilisateur — un pas restait programmé

    expect(sched.canceled.length).toBeGreaterThan(0); // le pas suivant a bien été annulé
    expect(seen).toEqual([6, 7]); // aucun pas de plus après l'arrêt
    expect(player.playing).toBe(false);
  });
});

describe('CALX120 — lecture ANNÉE', () => {
  it('avance de mois en mois (pas saisi), même heure solaire conservée', () => {
    const sched = fakeScheduler();
    const player = createSoleilPlayer({ schedule: sched.schedule, cancel: sched.cancel, reducedMotion: false });
    const seen: SoleilPlayState[] = [];
    player.playYear({ sunDay: 1, sunHour: 14 }, (s) => seen.push(s), 90);
    sched.drainAll();
    expect(seen.map((s) => s.sunDay)).toEqual([1, 91, 181, 271, 361]);
    expect(seen.every((s) => s.sunHour === 14)).toBe(true);
    expect(player.playing).toBe(false);
  });
});

describe('CALX120 — prefers-reduced-motion : aucune boucle, lecture pas-à-pas', () => {
  it('reducedMotion actif ⇒ AUCUNE boucle d’animation lancée (schedule jamais appelé)', () => {
    const sched = fakeScheduler();
    const player = createSoleilPlayer({ schedule: sched.schedule, cancel: sched.cancel, reducedMotion: true });
    const seen: number[] = [];

    player.playDay({ sunDay: 172, sunHour: 6 }, { riseHour: 6, setHour: 20 }, 1, (s) => seen.push(s.sunHour));

    expect(sched.queue).toHaveLength(0); // aucune boucle programmée
    expect(seen).toEqual([6]); // un seul pas appliqué (pas-à-pas) — le curseur d'heure
    // existant (W87) reste le contrôle manuel pour avancer plus loin, comme aujourd'hui.
    expect(player.playing).toBe(false);
  });

  it('reducedMotion actif : la lecture ANNÉE se comporte pareil, un seul pas appliqué', () => {
    const sched = fakeScheduler();
    const player = createSoleilPlayer({ schedule: sched.schedule, cancel: sched.cancel, reducedMotion: true });
    const seen: SoleilPlayState[] = [];
    player.playYear({ sunDay: 1, sunHour: 14 }, (s) => seen.push(s), 90);
    expect(sched.queue).toHaveLength(0);
    expect(seen).toEqual([{ sunDay: 1, sunHour: 14 }]);
  });
});

describe('CALX120 — pas vide (lever/coucher inversés ou année déjà à 366) : aucun pas, jamais d’exception', () => {
  it('playDay avec setHour <= riseHour ne rend rien', () => {
    const sched = fakeScheduler();
    const player = createSoleilPlayer({ schedule: sched.schedule, cancel: sched.cancel, reducedMotion: false });
    const seen: number[] = [];
    player.playDay({ sunDay: 172, sunHour: 12 }, { riseHour: 12, setHour: 10 }, 1, (s) => seen.push(s.sunHour));
    expect(seen).toEqual([]);
    expect(player.playing).toBe(false);
  });

  it('playYear depuis le jour 366 ne rend qu’un pas (366)', () => {
    const sched = fakeScheduler();
    const player = createSoleilPlayer({ schedule: sched.schedule, cancel: sched.cancel, reducedMotion: false });
    const seen: SoleilPlayState[] = [];
    player.playYear({ sunDay: 366, sunHour: 12 }, (s) => seen.push(s), 30);
    sched.drainAll();
    expect(seen.map((s) => s.sunDay)).toEqual([366]);
  });
});
