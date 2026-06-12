/**
 * Outil de session (passe 1 du tri approfondi) : écrit l'inventaire scoré
 * de photos-raw/ dans .curation/inventory.json. Notes 1-10 sur netteté,
 * exposition/brume, composition, valeur du sujet — issues de la revue
 * visuelle complète (14 planches-contacts + 28 lectures haute résolution).
 * Les séries en rafale partagent une note de base ; les meilleures vues de
 * chaque série sont notées individuellement.
 *
 *   node scripts/build-inventory.mjs
 */
import { readFileSync, writeFileSync } from 'node:fs';

const idx = JSON.parse(readFileSync('.curation/index.json', 'utf8'));

// [plage, netteté, expo, compo, sujet, note]
const SERIES = [
  [[1, 2], 5, 5, 4, 4, 'ouvriers accroupis, loin, fouillis'],
  [[3, 4], 8, 7, 7, 8, 'assemblage des rails au sol, gros plan — retenu #3 (mesure-rails)'],
  [[5, 6], 6, 5, 4, 4, 'onduleur MUST au mur, lumière plate, marque hors gamme'],
  [[7, 8], 7, 6, 6, 6, 'champ au crépuscule, seau rose dans le cadre (7 = recadré retenu)'],
  [[9, 9], 8, 7, 7, 8, 'nettoyage au jet, palmiers — retenu (entretien-jet)'],
  [[10, 12], 6, 5, 5, 5, 'écrans onduleur MUST, sombres, marque hors gamme'],
  [[13, 13], 7, 6, 6, 7, 'tableau de protections — ANNOTÉ au marqueur : inutilisable tel quel'],
  [[14, 15], 7, 7, 6, 7, 'équipe en pose, gilet TAQINOR visible'],
  [[16, 16], 8, 7, 8, 9, 'gilet TAQINOR net au premier plan — retenu (equipe-gilet)'],
  [[17, 17], 7, 7, 7, 8, 'pose de structure — retenu (equipe-pose, hérité)'],
  [[18, 18], 9, 8, 9, 10, 'rangée + skyline + minaret, heure dorée — retenu (hero-skyline)'],
  [[19, 19], 8, 7, 8, 9, 'mur technique Dyness + borne — retenu (mur-technique)'],
  [[20, 20], 8, 7, 7, 7, 'quasi-doublon de 73, chauffe-eau coupé'],
  [[21, 21], 6, 6, 5, 6, 'mur technique avec vélo d’appartement dans le cadre'],
  [[22, 24], 6, 6, 5, 6, 'portage de panneau, rafale, cadrages serrés'],
  [[25, 25], 7, 6, 6, 7, 'équipe inclinant un panneau — bon geste, clim au premier plan (réserve GBP)'],
  [[26, 33], 6, 6, 5, 5, 'poses de groupe en rafale, midi dur'],
  [[34, 36], 7, 7, 5, 6, 'champ sur gravier, clims visibles'],
  [[37, 40], 8, 7, 7, 7, 'champ noir villa, rafale — 41 retenu'],
  [[41, 41], 8, 8, 8, 8, 'champ noir villa, le plus net — retenu (champ-villa)'],
  [[42, 43], 8, 7, 7, 7, 'variantes de 41'],
  [[44, 48], 6, 6, 5, 6, 'mur garage, étagère et câbles, rafale'],
  [[49, 58], 6, 6, 5, 5, 'ancien champ poly bleu, toits délavés, rafale'],
  [[59, 59], 7, 6, 9, 9, 'longue pente + pyramide zellige + palmiers — retenu (pente-zellige)'],
  [[60, 60], 7, 6, 8, 8, 'variante de 59, cadrage moins tendu'],
  [[61, 64], 7, 6, 8, 8, 'villa pavillon zellige turquoise — 62 retenu (villa-zellige)'],
  [[65, 65], 7, 7, 6, 7, 'grand champ, terrasse pavée'],
  [[66, 72], 7, 7, 7, 7, 'pose devant champ + minaret, heure dorée, rafale (66 réserve sociale)'],
  [[73, 73], 8, 7, 9, 9, 'penthouse blanc + chauffe-eau au crépuscule — retenu (crepuscule-penthouse)'],
  [[74, 85], 7, 7, 7, 7, 'rafale du même site, avec/sans pose'],
  [[86, 86], 7, 6, 7, 8, 'mur Dyness frontal — doublon plus sombre de 19'],
  [[87, 101], 6, 5, 5, 6, 'mur technique en rafale, sols de chantier'],
  [[102, 103], 7, 6, 7, 8, 'chantier industriel, contre-jour'],
  [[104, 104], 7, 6, 9, 10, 'double rangée industrielle au couchant — retenu (industriel-couchant)'],
  [[105, 116], 6, 5, 6, 7, 'même site, rafale, tuyau rouge / contre-jour'],
  [[117, 117], 7, 7, 7, 8, 'équipe de trois + longue rangée — retenu (equipe-trois)'],
  [[118, 121], 7, 7, 6, 6, 'portraits d’équipe — casquette « POLICE » lisible'],
  [[122, 125], 6, 6, 5, 6, 'équipe au loin, rafale'],
  [[126, 140], 6, 6, 5, 6, 'local technique brut, rafale, plâtre nu'],
  [[141, 141], 8, 7, 7, 9, 'bornes Dyness + coffret Güneş, gros plan câblage — retenu (detail-cablage)'],
  [[142, 146], 6, 6, 5, 6, 'variantes du local technique'],
  [[147, 148], 7, 7, 6, 7, 'terrasse terre cuite, variantes'],
  [[149, 149], 8, 8, 8, 8, 'rangée de 7 sur terre cuite — retenu (terrasse-terre-cuite)'],
  [[150, 152], 7, 7, 7, 7, 'variantes de 149'],
  [[153, 158], 6, 6, 5, 5, 'linge étendu dans le cadre / cadrages lâches'],
  [[159, 159], 8, 8, 9, 8, 'panneau + chauffe-eau sur acrotère, graphique — retenu (silhouette-acrotere)'],
  [[160, 161], 7, 7, 7, 7, 'variantes de 159/149'],
  [[162, 162], 7, 6, 6, 7, 'mur technique blanc, câble au sol'],
];

const VIDEOS = [
  ['20251018_104855000_iOS.MOV', 7, 6, 5, 'V1 1080p paysage 7 s — mesure des rails, court'],
  ['20251020_133423000_iOS.MP4', 7, 6, 8, 'V2 vertical — écran onduleur + gilet TAQINOR : RETENU montage (monitoring)'],
  ['20251020_133438000_iOS.MP4', 6, 7, 5, 'V3 vertical crépuscule, seau rose'],
  ['20251020_133457000_iOS.MP4', 6, 7, 5, 'V4-V5 verticaux champ, statiques'],
  ['20251020_133512000_iOS.MP4', 6, 7, 5, 'idem'],
  ['20251020_133535000_iOS.MP4', 7, 7, 6, 'V6 vertical visseuse, geste net mais vertical'],
  ['20251020_133547000_iOS.MP4', 6, 6, 6, 'V7 vertical portage au crépuscule'],
  ['20251020_133925000_iOS.MP4', 5, 6, 5, 'V8 848x480, sombre'],
  ['20251020_133944000_iOS.MP4', 5, 7, 5, 'V9 464x832'],
  ['20251020_133956000_iOS.MP4', 5, 7, 5, 'V10'],
  ['20251020_134008000_iOS.MP4', 5, 7, 5, 'V11'],
  ['20251020_134025000_iOS.MP4', 6, 7, 7, 'V12 848x480 paysage — portage panneau gilets : RETENU montage'],
  ['20251020_140851000_iOS.MP4', 5, 6, 5, 'V13-V23 rafale chantier, majorité verticaux'],
  ['20251020_140910000_iOS.MP4', 5, 6, 5, ''],
  ['20251020_140920000_iOS.MP4', 5, 6, 5, ''],
  ['20251020_140944000_iOS.MP4', 5, 6, 5, ''],
  ['20251020_141152000_iOS.MP4', 5, 6, 5, ''],
  ['20251020_141202000_iOS.MP4', 5, 6, 5, ''],
  ['20251020_141206000_iOS.MP4', 5, 6, 5, ''],
  ['20251020_141235000_iOS.MP4', 6, 7, 6, 'V20 vertical pose de rails, long'],
  ['20251020_141255000_iOS.MP4', 6, 7, 6, 'V21 vertical'],
  ['20251020_141512000_iOS.MP4', 5, 6, 5, 'V22-V23'],
  ['20251020_141513000_iOS.MP4', 5, 6, 5, ''],
  ['IMG_1702.MOV', 8, 6, 9, 'V24 1080p — deux poseurs fixent un panneau : RETENU montage (pose)'],
  ['IMG_1836.MOV', 6, 7, 5, 'V25 57 s pano ancien champ poly bleu'],
  ['IMG_1837.MOV', 6, 7, 5, 'V26 idem'],
  ['IMG_1844.MOV', 6, 7, 5, 'V27 43 s idem'],
  ['IMG_2198.MOV', 8, 7, 10, 'V28 1080p pano grand champ + ville blanche : RETENU héros + final montage'],
  ['IMG_2210.MOV', 6, 5, 6, 'V29 contre-jour'],
  ['IMG_2232.MOV', 4, 5, 3, 'V30 2,7 s, inutilisable'],
];

const photos = [];
for (const [range, net, expo, compo, sujet, note] of SERIES) {
  for (let n = range[0]; n <= range[1]; n++) {
    photos.push({ n, file: idx[n], scores: { nettete: net, exposition: expo, composition: compo, sujet }, note });
  }
}
const videos = VIDEOS.map(([file, stab, lum, sujet, note]) => ({ file, scores: { stabilite: stab, lumiere: lum, sujet }, note }));

writeFileSync('.curation/inventory.json', JSON.stringify({ photos, videos }, null, 2));
console.log(`inventaire : ${photos.length} photos + ${videos.length} vidéos scorées`);
