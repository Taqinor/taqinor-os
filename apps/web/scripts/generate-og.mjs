/**
 * Génère les images Open Graph 1200×630 dans public/og/ — identité
 * « lumière marocaine, précision d'ingénieur » : nuit chaude, quadrillage
 * technique, ambre solaire, titres en Bricolage Grotesque (TTF locale via
 * l'option fontfile du rendu texte de sharp), photos réelles de
 * public/photos/ (produites par process-photos.mjs).
 *
 *   node scripts/generate-og.mjs
 */
import sharp from 'sharp';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const fontfile = path.join(root, 'scripts', 'assets', 'bricolage-800.ttf');
const outDir = path.join(root, 'public', 'og');
const photosDir = path.join(root, 'public', 'photos');

const PAGES = [
  { slug: 'accueil', title: 'Installations solaires\nau Maroc', subtitle: 'Dimensionnées par l’ingénierie — conformes loi 82-21', photo: 'hero-skyline-1280.webp' },
  { slug: 'residentiel', title: 'Solaire résidentiel', subtitle: 'Villas et appartements — retour en 3 à 7 ans', photo: 'crepuscule-penthouse-1024.webp' },
  { slug: 'professionnel', title: 'Solaire professionnel', subtitle: 'Industriels, hôtels, cliniques — moyenne tension', photo: 'industriel-couchant-1280.webp' },
  { slug: 'equipement', title: 'Équipement en stock', subtitle: 'Deye · Solis · Dyness — garanties constructeur', photo: 'mur-technique-dyness-1024.webp' },
  { slug: 'loi-82-21', title: 'Loi 82-21 :\nquel régime ?', subtitle: 'Déclaration, accord de raccordement, autorisation', photo: 'champ-villa-1024.webp' },
  { slug: 'article-33', title: 'Régularisation\nArticle 33', subtitle: 'Installations existantes — la fenêtre est ouverte', photo: 'terrasse-terre-cuite-1024.webp' },
  { slug: 'contact', title: 'Étude gratuite', subtitle: 'Estimation immédiate — réponse sous 24 h ouvrées', photo: 'equipe-trois-1024.webp' },
];

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** Bloc de texte rendu en Bricolage via Pango (fontfile locale). */
function text(str, sizePx, color, { spacing = 0 } = {}) {
  return {
    input: {
      text: {
        text: `<span foreground="${color}" letter_spacing="${spacing}">${esc(str)}</span>`,
        font: `Bricolage Grotesque Ultra-Bold ${Math.round(sizePx * 0.75)}`,
        fontfile,
        rgba: true,
        align: 'left',
        spacing: 6,
      },
    },
  };
}

// Fond : voile nuit + quadrillage + barre ambre + soleil-éclair (sans texte)
const grid =
  Array.from({ length: 38 }, (_, i) => `<line x1="${i * 32}" y1="0" x2="${i * 32}" y2="630" stroke="#faf6ef" stroke-opacity="0.05"/>`).join('') +
  Array.from({ length: 20 }, (_, i) => `<line x1="0" y1="${i * 32}" x2="1200" y2="${i * 32}" stroke="#faf6ef" stroke-opacity="0.05"/>`).join('');
const backdrop = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">
  <rect width="1200" height="630" fill="#181410" fill-opacity="0.84"/>
  ${grid}
  <rect x="0" y="614" width="1200" height="16" fill="#F5C100"/>
  <rect x="80" y="92" width="36" height="4" fill="#F5C100"/>
  <circle cx="1056" cy="140" r="64" fill="#F5C100"/>
  <polygon points="1061 100 1020 156 1056 156 1051 180 1092 124 1056 124 1061 100" fill="#181410"/>
</svg>`);

await mkdir(outDir, { recursive: true });
for (const page of PAGES) {
  const file = path.join(outDir, `${page.slug}.png`);
  const twoLines = page.title.includes('\n');
  await sharp(path.join(photosDir, page.photo))
    .resize(1200, 630, { fit: 'cover' })
    .composite([
      { input: backdrop },
      { ...text('TAQINOR', 42, '#faf6ef', { spacing: 3000 }), left: 80, top: 112 },
      { ...text(page.title, 60, '#faf6ef'), left: 80, top: twoLines ? 268 : 304 },
      {
        input: {
          text: {
            text: `<span foreground="#d8d2c4">${esc(page.subtitle)}</span>`,
            font: 'sans 24',
            rgba: true,
          },
        },
        left: 80,
        top: twoLines ? 452 : 396,
      },
      { ...text('TAQINOR.MA', 24, '#F5C100', { spacing: 4000 }), left: 80, top: 540 },
    ])
    .png({ compressionLevel: 9, palette: true })
    .toFile(file);
  console.log(`og: ${page.slug}.png`);
}
