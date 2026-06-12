/**
 * Génère les images Open Graph 1200×630 dans public/og/ — identité
 * « Ville Blanche » : voile bleu Majorelle, motif zellige abstrait en
 * filets, accent laiton, titres en Syne (TTF locale via l'option fontfile
 * du rendu texte de sharp), photos réelles de public/photos/.
 *
 *   node scripts/generate-og.mjs
 */
import sharp from 'sharp';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const fontfile = path.join(root, 'scripts', 'assets', 'syne-800.ttf');
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

/** Bloc de texte rendu en Syne via Pango (fontfile locale). */
function text(str, sizePx, color, { spacing = 0 } = {}) {
  return {
    input: {
      text: {
        text: `<span foreground="${color}" letter_spacing="${spacing}">${esc(str)}</span>`,
        font: `Syne ExtraBold ${Math.round(sizePx * 0.75)}`,
        fontfile,
        rgba: true,
        align: 'left',
        spacing: 8,
      },
    },
  };
}

// Fond : voile Majorelle + motif zellige (étoiles à 8 pointes en filets) +
// barre laiton + soleil-éclair du logo (sans texte)
function star(cx, cy, r, opacity) {
  const s = r * 2;
  return `<g fill="none" stroke="#ffffff" stroke-opacity="${opacity}" stroke-width="1.2">
    <rect x="${cx - r}" y="${cy - r}" width="${s}" height="${s}"/>
    <rect x="${cx - r}" y="${cy - r}" width="${s}" height="${s}" transform="rotate(45 ${cx} ${cy})"/>
  </g>`;
}
const backdrop = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">
  <rect width="1200" height="630" fill="#152870" fill-opacity="0.88"/>
  ${star(1020, 180, 130, 0.12)}${star(1020, 180, 86, 0.10)}${star(1160, 470, 100, 0.10)}${star(120, 560, 80, 0.08)}
  <rect x="0" y="614" width="1200" height="16" fill="#E8B54A"/>
  <rect x="80" y="92" width="36" height="4" fill="#E8B54A"/>
  <circle cx="1056" cy="140" r="56" fill="#E8B54A"/>
  <polygon points="1061 105 1024 155 1056 155 1051 176 1088 126 1056 126 1061 105" fill="#0a1238"/>
</svg>`);

await mkdir(outDir, { recursive: true });
for (const page of PAGES) {
  const file = path.join(outDir, `${page.slug}.png`);
  const twoLines = page.title.includes('\n');
  await sharp(path.join(photosDir, page.photo))
    .resize(1200, 630, { fit: 'cover' })
    .composite([
      { input: backdrop },
      { ...text('TAQINOR', 42, '#ffffff', { spacing: 3000 }), left: 80, top: 112 },
      { ...text(page.title, 58, '#ffffff'), left: 80, top: twoLines ? 264 : 302 },
      {
        input: {
          text: {
            text: `<span foreground="#c9d4f2">${esc(page.subtitle)}</span>`,
            font: 'sans 24',
            rgba: true,
          },
        },
        left: 80,
        top: twoLines ? 460 : 396,
      },
      { ...text('TAQINOR.MA', 24, '#E8B54A', { spacing: 4000 }), left: 80, top: 540 },
    ])
    .png({ compressionLevel: 9, palette: true })
    .toFile(file);
  console.log(`og: ${page.slug}.png`);
}
