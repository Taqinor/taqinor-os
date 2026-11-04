/**
 * Génère les images Open Graph 1200×630 dans public/og/ — identité
 * « Ville Blanche » : voile bleu Majorelle, motif zellige abstrait en
 * filets, accent laiton, titres en Syne (TTF locale via l'option fontfile
 * du rendu texte de sharp), photos réelles de public/photos/.
 *
 *   node scripts/generate-og.mjs            # toutes les cartes
 *   node scripts/generate-og.mjs --manquantes  # seulement les fichiers absents
 *
 * WAUD72 — chaque carte existe en trois langues : `<slug>.png` (FR), `<slug>-en.png`, `<slug>-ar.png`
 * (le Layout choisit la variante de la page via src/lib/ogCartes.ts). Les sous-titres ne portent
 * AUCUN chiffre non sourcé (règle « chiffres vérifiés ») : les anciennes promesses « retour en 3 à
 * 7 ans », « garanties 10 à 25 ans », « 6 000 cycles, garantie 10 ans », « réponse sous 24 h » et
 * l'urgence « la fenêtre est ouverte » sont retirées. Texte arabe rendu par Pango (police système
 * « sans », mise en forme et ordre droite-à-gauche vérifiés à l'œil) ; un nombre en arabe passe dans
 * un isolat LRI…PDI pour ne pas être retourné (« 82-21 », jamais « 21-82 »).
 */
import sharp from 'sharp';
import { access, mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const fontfile = path.join(root, 'scripts', 'assets', 'archivo-800.ttf');
const outDir = path.join(root, 'public', 'og');
const photosDir = path.join(root, 'public', 'photos');
const seulementManquantes = process.argv.includes('--manquantes');

/** Nombre isolé dans un texte arabe (LRI … PDI). */
const iso = (s) => `⁦${s}⁩`;

const PAGES = [
  { slug: 'accueil', photo: 'hero-skyline-1280.webp',
    fr: ['Installations solaires\nau Maroc', 'Dimensionnées par l’ingénierie — conformes loi 82-21'],
    en: ['Solar installations\nin Morocco', 'Engineered sizing — compliant with Law 82-21'],
    ar: ['تركيب الألواح الشمسية\nبالمغرب', `دراسة هندسية — مطابقة للقانون ${iso('82-21')}`] },
  { slug: 'residentiel', photo: 'crepuscule-penthouse-1024.webp',
    fr: ['Solaire résidentiel', 'Villas et appartements — étude sur votre facture'],
    en: ['Residential solar', 'Villas and apartments — a study based on your bill'],
    ar: ['الطاقة الشمسية للمنازل', 'فيلات وشقق — دراسة انطلاقاً من فاتورتكم'] },
  { slug: 'professionnel', photo: 'industriel-couchant-1280.webp',
    fr: ['Solaire professionnel', 'Industriels, hôtels, cliniques — moyenne tension'],
    en: ['Business solar', 'Industry, hotels, clinics — medium voltage'],
    ar: ['الطاقة الشمسية للمهنيين', 'صناعة، فنادق، مصحات — التوتر المتوسط'] },
  { slug: 'equipement', photo: 'mur-technique-dyness-1024.webp',
    fr: ['Équipement posé', 'Canadian Solar · Deye · Dyness — matériel nommé'],
    en: ['Equipment we install', 'Canadian Solar · Deye · Dyness — named hardware'],
    ar: ['التجهيزات المركَّبة', 'Canadian Solar · Deye · Dyness'] },
  { slug: 'loi-82-21', photo: 'champ-villa-1024.webp',
    fr: ['Loi 82-21 :\nquel régime ?', 'Déclaration, accord de raccordement, autorisation'],
    en: ['Law 82-21:\nwhich regime?', 'Declaration, connection agreement, authorisation'],
    ar: [`القانون ${iso('82-21')}:\nأيّ نظام؟`, 'تصريح، اتفاق ربط، ترخيص'] },
  { slug: 'article-33', photo: 'reflet-468-1024.webp',
    fr: ['Régularisation\nArticle 33', 'Installation existante — dossier de régularisation'],
    en: ['Article 33\nregularisation', 'Existing installation — regularisation file'],
    ar: [`تسوية\nالمادة ${iso('33')}`, 'تركيب قائم — ملف التسوية'] },
  { slug: 'contact', photo: 'equipe-trois-1024.webp',
    fr: ['Étude gratuite', 'Sur votre facture — réponse sur WhatsApp'],
    en: ['Free study', 'Based on your bill — we reply on WhatsApp'],
    ar: ['دراسة مجانية', 'انطلاقاً من فاتورتكم — نجيبكم على واتساب'] },
  // WJ76 — image OG neutre dédiée aux propositions tokenisées : AUCUNE
  // référence ni nom de client (c'est tout le sujet de la tâche — un lien de
  // proposition privé, transféré sur WhatsApp par le client, ne doit jamais
  // pousser ces données au-dessus d'une image générique de la page d'accueil).
  { slug: 'proposition', photo: 'installation-crepuscule-1024.webp', sansVariante: true,
    fr: ['Votre proposition\nsolaire', 'Étude personnalisée — chiffrage détaillé Taqinor'] },
  // W292 — catégories de service + génériques guides/blog. Chaque entrée réutilise une photo
  // RÉELLE déjà au catalogue (public/photos/), jamais une image inventée.
  { slug: 'pompage-solaire', photo: 'champ-villa-1024.webp',
    fr: ['Pompage solaire\nagricole', 'Dimensionné sur votre HMT et votre débit'],
    en: ['Solar water\npumping', 'Sized on your head (HMT) and flow rate'],
    ar: ['الضخ الشمسي\nالفلاحي', 'مُحدَّد حسب العلوّ المانومتري والصبيب'] },
  { slug: 'nos-solutions', photo: 'equipe-pose-structure-1024.webp',
    fr: ['Nos solutions\nsolaires', 'Résidentiel, professionnel, pompage — un seul interlocuteur'],
    en: ['Our solar\nsolutions', 'Residential, business, pumping — one contact'],
    ar: ['حلولنا\nالشمسية', 'سكني، مهني، ضخ — مخاطَب واحد'] },
  { slug: 'garanties', photo: 'pose-134-1024.webp',
    fr: ['Garanties\net matériel', 'Par composant — Canadian Solar · Deye · Dyness'],
    en: ['Warranties\nand hardware', 'Per component — Canadian Solar · Deye · Dyness'],
    ar: ['الضمانات\nوالتجهيزات', 'حسب كل مكوّن — Canadian Solar · Deye · Dyness'] },
  { slug: 'financement', photo: 'portrait-400-1024.webp',
    fr: ['Financement\nsolaire', 'Comptant, crédit, leasing — simulation honnête'],
    en: ['Solar\nfinancing', 'Cash, loan, leasing — an honest simulation'],
    ar: ['تمويل\nالطاقة الشمسية', 'نقداً، قرض، إيجار — محاكاة صادقة'] },
  { slug: 'batteries-stockage', photo: 'mur-technique-dyness-1024.webp',
    fr: ['Batteries\net stockage', 'Dyness LFP — dimensionnées sur votre consommation du soir'],
    en: ['Batteries\nand storage', 'Dyness LFP — sized on your evening consumption'],
    ar: ['البطاريات\nوالتخزين', 'Dyness LFP — حسب استهلاككم المسائي'] },
  { slug: 'maintenance-monitoring', photo: 'entretien-jet-1024.webp',
    fr: ['Maintenance\net monitoring', 'Supervision Deye Cloud — SAV avant la réclamation'],
    en: ['Maintenance\nand monitoring', 'Deye Cloud supervision — service before the complaint'],
    ar: ['الصيانة\nوالمراقبة', 'مراقبة Deye Cloud — خدمة قبل الشكوى'] },
  { slug: 'recharge-voiture-electrique-solaire', photo: 'equipe-gilet-taqinor-1024.webp',
    fr: ['Recharger sa voiture\nau solaire', 'Borne 7 à 22 kW — au fil du surplus photovoltaïque'],
    en: ['Charge your car\nwith solar', 'Wallbox charging on your solar surplus'],
    ar: ['شحن سيارتكم\nبالطاقة الشمسية', 'محطة شحن على فائض الإنتاج الشمسي'] },
  { slug: 'guides', photo: 'detail-cablage-1024.webp',
    fr: ['Guides solaires', 'Comprendre avant de signer — réponses factuelles'],
    en: ['Solar guides', 'Understand before you sign — factual answers'],
    ar: ['أدلّة الطاقة الشمسية', 'افهموا قبل التوقيع — أجوبة دقيقة'] },
  { slug: 'blog', photo: 'mesure-rails-1024.webp',
    fr: ['Blog Taqinor', 'Prix, retours de chantier, réglementation 82-21'],
    en: ['Taqinor blog', 'Prices, site feedback, Law 82-21 regulation'],
    ar: ['مدوّنة Taqinor', `الأسعار، تجارب الأوراش، تنظيم ${iso('82-21')}`] },
  // WAUD72 — cartes des pages qui partageaient accueil.png (tunnel, FAQ, réalisations, billets…).
  { slug: 'tunnel', photo: 'equipe-trois-1024.webp',
    fr: ['Votre étude\nsolaire gratuite', 'Adresse et facture — réponse sur WhatsApp'],
    en: ['Your free\nsolar study', 'Address and bill — we reply on WhatsApp'],
    ar: ['دراستكم الشمسية\nالمجانية', 'العنوان والفاتورة — نجيبكم على واتساب'] },
  { slug: 'faq', photo: 'detail-cablage-1024.webp',
    fr: ['Questions\nfréquentes', 'Le solaire au Maroc — réponses factuelles'],
    en: ['Frequently asked\nquestions', 'Solar in Morocco — factual answers'],
    ar: ['الأسئلة\nالشائعة', 'الطاقة الشمسية بالمغرب — أجوبة دقيقة'] },
  { slug: 'marocains-du-monde', photo: 'portrait-400-1024.webp',
    fr: ['Marocains\ndu monde', 'Votre projet au Maroc, suivi à distance'],
    en: ['Moroccans\nabroad', 'Your project in Morocco, followed remotely'],
    ar: ['مغاربة\nالعالم', 'مشروعكم بالمغرب، متابَع عن بُعد'] },
  { slug: 'pourquoi-taqinor', photo: 'equipe-pose-structure-1024.webp',
    fr: ['Pourquoi\nTaqinor', 'Étude sur votre facture, matériel nommé'],
    en: ['Why\nTaqinor', 'A study based on your bill, named hardware'],
    ar: ['لماذا\nTaqinor', 'دراسة انطلاقاً من فاتورتكم وتجهيزات مسمّاة'] },
  { slug: 'realisations', photo: 'installation-crepuscule-1024.webp',
    fr: ['Nos réalisations', 'Installations réellement posées au Maroc'],
    en: ['Our installations', 'Systems actually installed in Morocco'],
    ar: ['إنجازاتنا', 'تركيبات أُنجزت فعلاً بالمغرب'] },
  { slug: 'a-propos', photo: 'equipe-gilet-taqinor-1024.webp',
    fr: ['À propos\nde Taqinor', 'Installateur solaire au Maroc'],
    en: ['About\nTaqinor', 'Solar installer in Morocco'],
    ar: ['من نحن', 'مُركِّب الألواح الشمسية بالمغرب'] },
  { slug: 'prix', photo: 'pose-134-1024.webp',
    fr: ['Prix du solaire\nau Maroc', 'Ce qui compose une installation'],
    en: ['Solar prices\nin Morocco', 'What goes into an installation'],
    ar: ['أسعار الطاقة الشمسية\nبالمغرب', 'ما يتكوّن منه التركيب'] },
  { slug: 'parrainage', photo: 'equipe-trois-1024.webp',
    fr: ['Parrainage', 'Recommandez Taqinor à un proche'],
    en: ['Referral', 'Recommend Taqinor to someone you know'],
    ar: ['الإحالة', 'رشّحوا Taqinor لأحد معارفكم'] },
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

/** Texte arabe (police système, Pango) aligné à droite : rendu d'abord pour connaître sa largeur. */
async function texteDroite(str, font, color, top) {
  const { data, info } = await sharp({
    text: { text: `<span foreground="${color}">${esc(str)}</span>`, font, rgba: true, align: 'right', spacing: 8 },
  }).png().toBuffer({ resolveWithObject: true });
  return { input: data, left: Math.max(80, 1200 - 80 - info.width), top };
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

// WAUD72 — une carte de partage par ville ET par langue (ville-<slug>-<fr|en|ar>), visuel de
// marque + nom de ville, SANS photo de chantier (règle « preuve = vraie ville »). Les villes viennent de
// CITIES (src/lib/realisations.ts) et leur nom arabe d'AR_CITY_NAME (src/lib/cityPageData.ts) :
// jamais une liste recopiée.
const cartes = [];
for (const p of PAGES) {
  cartes.push({ slug: p.slug, photo: p.photo, lang: 'fr', title: p.fr[0], subtitle: p.fr[1] });
  if (p.sansVariante) continue;
  cartes.push({ slug: `${p.slug}-en`, photo: p.photo, lang: 'en', title: p.en[0], subtitle: p.en[1] });
  cartes.push({ slug: `${p.slug}-ar`, photo: p.photo, lang: 'ar', title: p.ar[0], subtitle: p.ar[1] });
}
{
  const src = await readFile(path.join(root, 'src', 'lib', 'realisations.ts'), 'utf-8');
  const bloc = src.slice(src.indexOf('export const CITIES'));
  const data = await readFile(path.join(root, 'src', 'lib', 'cityPageData.ts'), 'utf-8');
  const blocAr = data.slice(data.indexOf('export const AR_CITY_NAME'), data.indexOf('};', data.indexOf('export const AR_CITY_NAME')));
  const nomAr = Object.fromEntries([...blocAr.matchAll(/'?([a-z-]+)'?:\s*'([^']+)'/g)].map((m) => [m[1], m[2]]));
  for (const m of bloc.matchAll(/slug: '([^']+)',\s+name: '([^']+)',\s+intro: '([^']+)'/g)) {
    const [, slug, name, intro] = m;
    cartes.push({ slug: `ville-${slug}-fr`, title: `Installation solaire\n${intro}`, subtitle: 'Installateur solaire au Maroc', lang: 'fr' });
    cartes.push({ slug: `ville-${slug}-en`, title: `Solar installation\nin ${name}`, subtitle: 'Solar installer in Morocco', lang: 'en' });
    cartes.push({ slug: `ville-${slug}-ar`, title: `تركيب شمسي\nفي ${nomAr[slug] ?? name}`, subtitle: 'مُركِّب الألواح الشمسية بالمغرب', lang: 'ar' });
  }
}

await mkdir(outDir, { recursive: true });
for (const page of cartes) {
  const file = path.join(outDir, `${page.slug}.png`);
  if (seulementManquantes) {
    try {
      await access(file);
      continue;
    } catch {
      /* absent : on le génère */
    }
  }
  const twoLines = page.title.includes('\n');
  const titleTop = twoLines ? 264 : 302;
  const subTop = twoLines ? 460 : 396;
  const blocs =
    page.lang === 'ar'
      ? [
          await texteDroite(page.title, 'sans Bold 44', '#ffffff', titleTop),
          await texteDroite(page.subtitle, 'sans 24', '#d6dbe9', subTop),
        ]
      : [
          { ...text(page.title, 58, '#ffffff'), left: 80, top: titleTop },
          {
            input: { text: { text: `<span foreground="#d6dbe9">${esc(page.subtitle)}</span>`, font: 'sans 24', rgba: true } },
            left: 80,
            top: subTop,
          },
        ];
  // WAUD72 — carte de marque sans photo (page.photo absent) : jamais le chantier d'une autre ville.
  await (page.photo
    ? sharp(path.join(photosDir, page.photo)).resize(1200, 630, { fit: 'cover' })
    : sharp({ create: { width: 1200, height: 630, channels: 3, background: '#0a1238' } }))
    .composite([
      { input: backdrop },
      { ...text('TAQINOR', 42, '#ffffff', { spacing: 3000 }), left: 80, top: 112 },
      ...blocs,
      { ...text('TAQINOR.MA', 24, '#E8B54A', { spacing: 4000 }), left: 80, top: 540 },
    ])
    // W325 — palette quantifiée (libimagequant, déjà embarqué dans sharp) + effort maximal :
    // −25 à −45 % de poids sans dégradation visible.
    .png({ compressionLevel: 9, palette: true, effort: 10, quality: 90 })
    .toFile(file);
  console.log(`og: ${page.slug}.png`);
}
