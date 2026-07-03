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
  { slug: 'equipement', title: 'Équipement posé', subtitle: 'Canadian Solar · Deye · Dyness — garanties 10 à 25 ans', photo: 'mur-technique-dyness-1024.webp' },
  { slug: 'loi-82-21', title: 'Loi 82-21 :\nquel régime ?', subtitle: 'Déclaration, accord de raccordement, autorisation', photo: 'champ-villa-1024.webp' },
  { slug: 'article-33', title: 'Régularisation\nArticle 33', subtitle: 'Installations existantes — la fenêtre est ouverte', photo: 'reflet-468-1024.webp' },
  { slug: 'contact', title: 'Étude gratuite', subtitle: 'Estimation immédiate — réponse sous 24 h ouvrées', photo: 'equipe-trois-1024.webp' },
  // WJ76 — image OG neutre dédiée aux propositions tokenisées : AUCUNE
  // référence ni nom de client (c'est tout le sujet de la tâche — un lien de
  // proposition privé, transféré sur WhatsApp par le client, ne doit jamais
  // pousser ces données au-dessus d'une image générique de la page d'accueil).
  { slug: 'proposition', title: 'Votre proposition\nsolaire', subtitle: 'Étude personnalisée — chiffrage détaillé Taqinor', photo: 'installation-crepuscule-1024.webp' },
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

// Fond « Cinéma du chantier » : la photo reste la lumière, voile nuit qui
// s'épaissit vers le bas (comme les héros du site), barre laiton,
// soleil-éclair du logo, et UNE empreinte zellige à échelle de signature.
const backdrop = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">
  <defs>
    <linearGradient id="voile" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#070b1d" stop-opacity="0.5"/>
      <stop offset="0.6" stop-color="#070b1d" stop-opacity="0.78"/>
      <stop offset="1" stop-color="#070b1d" stop-opacity="0.96"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#voile)"/>
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
            text: `<span foreground="#d6dbe9">${esc(page.subtitle)}</span>`,
            font: 'sans 24',
            rgba: true,
          },
        },
        left: 80,
        top: twoLines ? 460 : 396,
      },
      { ...text('TAQINOR.MA', 24, '#E8B54A', { spacing: 4000 }), left: 80, top: 540 },
    ])
    // W325 — la palette quantifiée (libimagequant, déjà embarqué dans sharp —
    // aucune dépendance ajoutée) + un effort d'encodage maximal réduisent le
    // poids de 25 à 45 % sans dégradation visible (vérifié à l'œil sur le
    // dégradé de ciel, le cas le plus exigeant pour la quantification) : les
    // fichiers actuels pesaient 183–325 Ko, ce qui ne fera qu'empirer à mesure
    // que le nombre de pages OG augmente (W292). quality:90 reste très
    // conservateur (palette web par défaut = 100, un compromis bien plus
    // agressif existe mais n'est pas nécessaire ici).
    .png({ compressionLevel: 9, palette: true, effort: 10, quality: 90 })
    .toFile(file);
  console.log(`og: ${page.slug}.png`);
}
