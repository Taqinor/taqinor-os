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
const fontfile = path.join(root, 'scripts', 'assets', 'archivo-800.ttf');
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

/** Bloc de texte rendu en Archivo via Pango (fontfile locale). */
function text(str, sizePx, color, { spacing = 0 } = {}) {
  return {
    input: {
      text: {
        text: `<span foreground="${color}" letter_spacing="${spacing}">${esc(str)}</span>`,
        font: `Archivo ExtraBold ${Math.round(sizePx * 0.75)}`,
        fontfile,
        rgba: true,
        align: 'left',
        spacing: 8,
      },
    },
  };
}

// Fond « L'Étude » : voile Majorelle calme, barre laiton, soleil-éclair du
// logo, et UNE empreinte zellige à échelle de signature (jamais de maillage).
const backdrop = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">
  <rect width="1200" height="630" fill="#152870" fill-opacity="0.9"/>
  <rect x="0" y="614" width="1200" height="16" fill="#E8B54A"/>
  <rect x="80" y="92" width="36" height="4" fill="#E8B54A"/>
  <g fill="none" stroke="#ffffff" stroke-opacity="0.55" stroke-width="1.4">
    <rect x="84" y="572" width="20" height="20"/>
    <rect x="84" y="572" width="20" height="20" transform="rotate(45 94 582)"/>
  </g>
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
