/**
 * Génère les images Open Graph 1200×630 dans public/og/.
 * Template de marque composité sur de vraies photos d'installation
 * (public/photos/, produites par process-photos.mjs) quand la page en a une ;
 * fond navy uni sinon. Utilise sharp (déjà fourni par Astro).
 *
 *   node scripts/generate-og.mjs
 */
import sharp from 'sharp';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const outDir = path.join(root, 'public', 'og');
const photosDir = path.join(root, 'public', 'photos');

const PAGES = [
  { slug: 'accueil', title: 'Installations solaires au Maroc', subtitle: 'Dimensionnées par l’ingénierie — conformes loi 82-21', photo: 'toit-terrasse-panneaux.webp' },
  { slug: 'residentiel', title: 'Solaire résidentiel', subtitle: 'Villas et appartements — retour en 3 à 7 ans', photo: 'installation-crepuscule.webp' },
  { slug: 'professionnel', title: 'Solaire professionnel', subtitle: 'Industriels, hôtels, cliniques — moyenne tension', photo: 'equipe-pose-structure.webp' },
  { slug: 'equipement', title: 'Équipement en stock', subtitle: 'Deye · Solis · Dyness — garanties constructeur', photo: 'batteries-onduleur.webp' },
  { slug: 'loi-82-21', title: 'Loi 82-21 : quel régime ?', subtitle: 'Déclaration, accord de raccordement, autorisation', photo: null },
  { slug: 'article-33', title: 'Régularisation Article 33', subtitle: 'Installations existantes — la fenêtre est ouverte', photo: null },
  { slug: 'contact', title: 'Étude gratuite', subtitle: 'Estimation immédiate — réponse sous 24 h ouvrées', photo: 'equipe-pose-structure.webp' },
];

function escapeXml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function overlay({ title, subtitle }, withPhoto) {
  const scrim = withPhoto
    ? `<rect width="1200" height="630" fill="#0d1b3e" fill-opacity="0.78"/>`
    : `<rect width="1200" height="630" fill="#0d1b3e"/>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">
  ${scrim}
  <rect x="0" y="610" width="1200" height="20" fill="#F5C100"/>
  <circle cx="1040" cy="140" r="90" fill="#F5C100"/>
  <polygon points="1047 85 990 162 1040 162 1033 195 1090 118 1040 118 1047 85" fill="#0d1b3e"/>
  <text x="80" y="130" font-family="Arial Black, Arial, sans-serif" font-weight="900" font-size="56" fill="#ffffff" letter-spacing="2">TAQINOR</text>
  <text x="80" y="340" font-family="Arial, sans-serif" font-weight="bold" font-size="64" fill="#ffffff">${escapeXml(title)}</text>
  <text x="80" y="420" font-family="Arial, sans-serif" font-size="34" fill="#c6d0e8">${escapeXml(subtitle)}</text>
  <text x="80" y="560" font-family="Arial, sans-serif" font-size="28" fill="#F5C100">taqinor.ma</text>
</svg>`;
}

await mkdir(outDir, { recursive: true });
for (const page of PAGES) {
  const file = path.join(outDir, `${page.slug}.png`);
  const svg = Buffer.from(overlay(page, Boolean(page.photo)));
  if (page.photo) {
    await sharp(path.join(photosDir, page.photo))
      .resize(1200, 630, { fit: 'cover' })
      .composite([{ input: svg }])
      .png()
      .toFile(file);
  } else {
    await sharp(svg).png().toFile(file);
  }
  console.log(`og: ${file}`);
}
