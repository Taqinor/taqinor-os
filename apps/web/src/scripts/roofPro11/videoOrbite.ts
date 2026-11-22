/**
 * ACAL896 — « Vidéo 10 s » : une orbite de la scène enregistrée, téléchargée par la commerciale
 * pour son WhatsApp. Le canvas de la carte est enregistré tel quel : AUCUN texte, prix ni chiffre
 * n'est ajouté à l'image ; rien n'est posté ni rangé (D-ACAL-38 b, hors `/proposal`).
 *
 * La durée, la cadence et le tour complet sont des constantes d'INTERACTION nommées (aucune
 * valeur de données). Sans `MediaRecorder` ou canvas non capturable : un motif français, aucun
 * fichier vide.
 */
export const DUREE_ORBITE_S = 10;
export const IMAGES_PAR_SECONDE = 30;
export const TOUR_COMPLET_DEG = 360;

/** Formats essayés dans l'ordre : MP4 si le navigateur sait l'enregistrer, sinon WebM. */
const FORMATS: ReadonlyArray<{ mime: string; extension: 'mp4' | 'webm' }> = [
  { mime: 'video/mp4;codecs=avc1', extension: 'mp4' },
  { mime: 'video/mp4', extension: 'mp4' },
  { mime: 'video/webm;codecs=vp9', extension: 'webm' },
  { mime: 'video/webm', extension: 'webm' },
];

/** Les caps (degrés) de chaque image : de `capDepart` à `capDepart` + 360 moins un pas. PUR. */
export function planOrbite(secondes: number, fps: number, capDepart: number): number[] {
  const n = Math.max(1, Math.round(secondes * fps));
  return Array.from({ length: n }, (_, i) => capDepart + (TOUR_COMPLET_DEG * i) / n);
}

/** Le premier format que le navigateur sait enregistrer, ou `null`. PUR. */
export function choisirFormat(
  ctor: { isTypeSupported?: (mime: string) => boolean } | null | undefined,
): { mime: string; extension: 'mp4' | 'webm' } | null {
  if (!ctor || typeof ctor.isTypeSupported !== 'function') return null;
  return FORMATS.find((f) => ctor.isTypeSupported!(f.mime)) ?? null;
}

export interface CarteOrbitable {
  getBearing: () => number;
  jumpTo: (o: { bearing: number }) => unknown;
  getCanvas: () => HTMLCanvasElement;
}

export type ResultatOrbite =
  | { ok: true; blob: Blob; extension: 'mp4' | 'webm'; mime: string }
  | { ok: false; motif: string };

export interface OptionsOrbite {
  secondes?: number;
  fps?: number;
  /** Appelé chaque seconde écoulée : « Enregistrement… (n s) ». */
  surProgres?: (secondesEcoulees: number) => void;
  /** Injectable en test. */
  MediaRecorderCtor?: typeof MediaRecorder;
}

const INDISPONIBLE = 'Enregistrement vidéo indisponible sur ce navigateur — aucun fichier produit.';

/** Fait tourner la carte d'un tour complet pendant l'enregistrement de son canvas ; restaure le cap. */
export async function enregistrerOrbite(map: CarteOrbitable, options: OptionsOrbite = {}): Promise<ResultatOrbite> {
  const secondes = options.secondes ?? DUREE_ORBITE_S;
  const fps = options.fps ?? IMAGES_PAR_SECONDE;
  const Ctor = options.MediaRecorderCtor ?? (typeof MediaRecorder === 'undefined' ? undefined : MediaRecorder);
  const format = choisirFormat(Ctor);
  const canvas = map.getCanvas();
  if (!Ctor || !format || typeof canvas?.captureStream !== 'function') return { ok: false, motif: INDISPONIBLE };
  const capDepart = map.getBearing();
  const caps = planOrbite(secondes, fps, capDepart);
  const morceaux: Blob[] = [];
  let enregistreur: MediaRecorder;
  try {
    enregistreur = new Ctor(canvas.captureStream(fps), { mimeType: format.mime });
  } catch {
    return { ok: false, motif: INDISPONIBLE };
  }
  enregistreur.ondataavailable = (e) => { if (e.data && e.data.size > 0) morceaux.push(e.data); };
  const fini = new Promise<void>((resolve) => { enregistreur.onstop = () => resolve(); });
  enregistreur.start();
  const debut = Date.now();
  let derniereSeconde = 0;
  await new Promise<void>((resolve) => {
    const pas = setInterval(() => {
      const t = (Date.now() - debut) / 1000;
      const i = Math.min(caps.length - 1, Math.floor((t / secondes) * caps.length));
      map.jumpTo({ bearing: caps[i] });
      const s = Math.floor(t);
      if (s > derniereSeconde) { derniereSeconde = s; options.surProgres?.(s); }
      if (t >= secondes) { clearInterval(pas); resolve(); }
    }, 1000 / fps);
  });
  map.jumpTo({ bearing: capDepart });
  enregistreur.stop();
  await fini;
  const blob = new Blob(morceaux, { type: format.mime.split(';')[0] });
  return blob.size > 0 ? { ok: true, blob, extension: format.extension, mime: format.mime }
    : { ok: false, motif: 'La vidéo est restée vide — aucun fichier produit.' };
}
