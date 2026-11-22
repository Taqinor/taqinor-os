// ACAL896 — « Vidéo 10 s » : le plan d'orbite (10 s à 30 images = 300 images, un tour complet) et le
// choix du format (MP4 d'abord, WebM ensuite, aucun ⇒ rien).
import { describe, expect, it } from 'vitest';
import { choisirFormat, enregistrerOrbite, planOrbite, type CarteOrbitable } from './videoOrbite';

describe('ACAL896 — planOrbite', () => {
  it('10 s à 30 images ⇒ 300 caps, du départ à départ + 360 moins un pas', () => {
    const caps = planOrbite(10, 30, 20);
    expect(caps).toHaveLength(300);
    expect(caps[0]).toBe(20);
    expect(caps[299]).toBeCloseTo(20 + 360 - 360 / 300, 9);
    expect(caps[300 - 1] + 360 / 300).toBeCloseTo(20 + 360, 9); // le pas suivant ferme le tour
    expect(caps.every((c, i) => i === 0 || c > caps[i - 1])).toBe(true);
  });
});

describe('ACAL896 — choisirFormat', () => {
  const ctor = (ok: string[]) => ({ isTypeSupported: (m: string) => ok.includes(m) });
  it('MP4 avant WebM ; l’extension suit le format réellement choisi', () => {
    expect(choisirFormat(ctor(['video/mp4', 'video/webm']))).toEqual({ mime: 'video/mp4', extension: 'mp4' });
    expect(choisirFormat(ctor(['video/webm']))).toEqual({ mime: 'video/webm', extension: 'webm' });
  });
  it('aucun format ou pas de MediaRecorder ⇒ null', () => {
    expect(choisirFormat(ctor([]))).toBeNull();
    expect(choisirFormat(undefined)).toBeNull();
    expect(choisirFormat({})).toBeNull();
  });
});

describe('ACAL896 — enregistrerOrbite sans MediaRecorder ou sans canvas capturable', () => {
  const carte = (canvas: unknown): CarteOrbitable => ({ getBearing: () => 0, jumpTo: () => undefined, getCanvas: () => canvas as HTMLCanvasElement });
  it('un motif français et aucun fichier', async () => {
    const sansCtor = await enregistrerOrbite(carte({ captureStream: () => ({}) }), { MediaRecorderCtor: undefined });
    expect(sansCtor.ok).toBe(false);
    const ctorFactice = { isTypeSupported: () => true } as unknown as typeof MediaRecorder;
    const sansCapture = await enregistrerOrbite(carte({}), { MediaRecorderCtor: ctorFactice });
    expect(sansCapture.ok).toBe(false);
    expect(!sansCapture.ok && sansCapture.motif).toContain('indisponible');
  });
});
