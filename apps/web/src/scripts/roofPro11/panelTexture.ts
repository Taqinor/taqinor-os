/**
 * Texture procédurale du panneau Canadian Solar (grille demi-cellules + couture
 * centrale + cadre alu), bakée une fois sur un canvas 512×280 et mappée sur chaque
 * panneau. Extraite de roof-tool-pro11.ts (split modulaire 2026-06-20) — INCHANGÉE.
 */
import * as THREE from 'three';

/** ACAL433 — canevas, colonnes et demi-rangées pour un panneau de rapport longueur/largeur
 *  donné. 1,83 (Canadian Solar 720 W) = EXACTEMENT 512 × 280, 24 × 3 (rendu d'origine) ;
 *  ailleurs, grand côté 512 et couple (colonnes, demi-rangées) au pas de cellule le plus
 *  carré. Pure, sans DOM. */
export function dimensionsTexture(rapport: number): { w: number; h: number; cols: number; rowsHalf: number } {
  const r = Math.round(rapport * 100) / 100;
  if (!(r > 0) || r === 1.83) return { w: 512, h: 280, cols: 24, rowsHalf: 3 };
  const w = r >= 1 ? 512 : Math.max(64, Math.round(512 * r));
  const h = r >= 1 ? Math.max(64, Math.round(512 / r)) : 512;
  const W = w - 28;
  const H = (h - 34) / 2;
  let best = { w, h, cols: 24, rowsHalf: 3 };
  let ecart = Infinity;
  for (let cols = 6; cols <= 32; cols++) {
    const rowsHalf = Math.max(1, Math.round((H * cols) / W));
    const e = Math.abs(W / cols / (H / rowsHalf) - 1);
    if (e < ecart - 1e-9) { ecart = e; best = { w, h, cols, rowsHalf }; }
  }
  return best;
}

/** ACAL1839 — le jeu « presentation » (vue client, maquettes TelephoneClient / Presentation) : verre bleu nuit, cellules
 *  et cadre clairs, couleurs en sRGB ; « atelier » : le verre de travail d'origine, octet pour octet. */
export type JeuPanneau = 'atelier' | 'presentation';
const TEINTES_VERRE: Record<JeuPanneau, { haut: string; bas: string; cellules: string; couture: string; cadre: string }> = {
  atelier: { haut: '#0c0c0f', bas: '#050507', cellules: 'rgba(40,46,60,0.55)', couture: 'rgba(20,24,34,0.9)', cadre: 'rgba(150,156,168,0.85)' },
  presentation: { haut: '#22306d', bas: '#0f1a48', cellules: 'rgba(223,229,243,0.3)', couture: 'rgba(223,229,243,0.55)', cadre: '#dfe5f3' },
};

export function makeCanadianPanelTexture(rapport = 1.83, jeu: JeuPanneau = 'atelier'): THREE.Texture {
  const t = TEINTES_VERRE[jeu];
  const { w: cW, h: cH, cols, rowsHalf } = dimensionsTexture(rapport);
  const c = document.createElement('canvas');
  c.width = cW;
  c.height = cH;
  const ctx = c.getContext('2d')!;
  const g = ctx.createLinearGradient(0, 0, cW, cH);
  g.addColorStop(0, t.haut);
  g.addColorStop(1, t.bas);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, cW, cH);
  const pad = 14;
  const seam = 6;
  const w = cW - pad * 2;
  const hHalf = (cH - pad * 2 - seam) / 2;
  const cw = w / cols;
  const ch = hHalf / rowsHalf;
  ctx.strokeStyle = t.cellules;
  ctx.lineWidth = 1;
  for (let half = 0; half < 2; half++) {
    const y0 = half === 0 ? pad : pad + hHalf + seam;
    for (let i = 0; i <= cols; i++) {
      const x = pad + i * cw;
      ctx.beginPath();
      ctx.moveTo(x, y0);
      ctx.lineTo(x, y0 + hHalf);
      ctx.stroke();
    }
    for (let j = 0; j <= rowsHalf; j++) {
      const y = y0 + j * ch;
      ctx.beginPath();
      ctx.moveTo(pad, y);
      ctx.lineTo(pad + w, y);
      ctx.stroke();
    }
  }
  ctx.strokeStyle = t.couture;
  ctx.lineWidth = seam;
  ctx.beginPath();
  ctx.moveTo(pad, cH / 2);
  ctx.lineTo(cW - pad, cH / 2);
  ctx.stroke();
  ctx.strokeStyle = t.cadre;
  ctx.lineWidth = 10;
  ctx.strokeRect(5, 5, cW - 10, cH - 10);
  const tex = new THREE.Texture(c);
  tex.needsUpdate = true;
  tex.anisotropy = 8;
  if (jeu === 'presentation') tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
