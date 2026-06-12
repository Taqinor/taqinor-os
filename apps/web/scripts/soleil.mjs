/**
 * Outil de session : simule la lecture en plein soleil (voile de reflet
 * clair + perte de saturation) sur une capture, pour vérifier la
 * discipline de contraste du thème sombre.
 *
 *   node scripts/soleil.mjs <capture.png> [sortie.png]
 */
import sharp from 'sharp';

const [file, outArg] = process.argv.slice(2);
const out = outArg ?? file.replace(/\.png$/, '-soleil.png');
const { width, height } = await sharp(file).metadata();
const haze = Buffer.from(
  `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="#e8e8e4" fill-opacity="0.38"/></svg>`,
);
await sharp(file)
  .composite([{ input: haze }])
  .modulate({ brightness: 0.92, saturation: 0.82 })
  .png()
  .toFile(out);
console.log(out);
