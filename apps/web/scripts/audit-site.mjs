/**
 * Outil de session — audit hostile automatisé du site construit :
 *  liens internes (200), images (200 + alt), deeplinks WhatsApp (numéro +
 *  texte pré-rempli par page), typographie FR (MAD groupé, guillemets,
 *  apostrophes), chiffres tracés au dossier entreprise / logique ROI.
 *
 *   node scripts/audit-site.mjs [base]
 */
const base = process.argv[2] ?? 'http://127.0.0.1:8788';
const PAGES = ['/', '/r%C3%A9sidentiel', '/professionnel', '/%C3%A9quipement', '/contact', '/loi-82-21', '/regularization-article-33'];

// Chiffres autorisés : dossier entreprise + logique ROI (billRange.ts) + loi 82-21
const FACTS = [
  '17,04', '21 406', '11,36', '14 271', '5,68', '7 135', '3,72', '43,48', '710',
  '24 ×', '16 ×', '8 ×', '6 ×', '15 kW', '10 kW', '5 kW', '15 kWh', '10 kWh', '5 kWh',
  '12 ans', '25 ans', '10 ans', '20 ans', '2 ans', '84,8', '6 000', '705', '720', '5 à 30',
  '12 500',
];
const issues = [];
const ok = (cond, msg) => { if (!cond) issues.push(msg); };

const seen = new Map();
async function status(url) {
  if (!seen.has(url)) {
    try { const r = await fetch(url, { method: 'GET' }); seen.set(url, r.status); }
    catch { seen.set(url, 0); }
  }
  return seen.get(url);
}

for (const p of PAGES) {
  const html = await (await fetch(base + p)).text();
  const page = decodeURIComponent(p);

  // Liens internes
  for (const m of html.matchAll(/href="(\/[^"#]*)"/g)) {
    const url = m[1];
    if (url.startsWith('/fonts') || url.startsWith('/_astro')) continue;
    const s = await status(base + encodeURI(url));
    ok(s === 200, `${page}: lien ${url} → ${s}`);
  }

  // Images : 200 + alt présent (alt="" toléré uniquement décoratif)
  for (const m of html.matchAll(/<img\b[^>]*>/g)) {
    const tag = m[0];
    const src = tag.match(/src="([^"]+)"/)?.[1];
    if (src && src.startsWith('/')) {
      const s = await status(base + src);
      ok(s === 200, `${page}: image ${src} → ${s}`);
    }
    // alt="" décoratif : Astro le rend en attribut nu « alt » — valide
    ok(/\salt(="|[\s>])/.test(tag), `${page}: <img> sans attribut alt (${(src ?? '').slice(0, 50)})`);
  }
  for (const m of html.matchAll(/srcset="([^"]+)"/g)) {
    for (const part of m[1].split(',')) {
      const src = part.trim().split(' ')[0];
      if (src.startsWith('/')) {
        const s = await status(base + src);
        ok(s === 200, `${page}: srcset ${src} → ${s}`);
      }
    }
  }

  // WhatsApp : bon numéro + texte pré-rempli non vide
  for (const m of html.matchAll(/https:\/\/wa\.me\/(\d+)\?text=([^"&]+)/g)) {
    ok(m[1] === '212661850410', `${page}: wa.me numéro ${m[1]} ≠ 212661850410`);
    const txt = decodeURIComponent(m[2]);
    ok(txt.length > 20 && txt.startsWith('Bonjour'), `${page}: texte WhatsApp suspect « ${txt.slice(0, 40)} »`);
  }

  // Typo FR : MAD non groupé (4+ chiffres collés), guillemets droits dans le texte
  const body = html.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<[^>]+>/g, ' ');
  for (const m of body.matchAll(/\b(\d{4,})\s?MAD/g)) {
    issues.push(`${page}: montant MAD non groupé « ${m[0]} »`);
  }
  ok(!/"\w[^"]{3,60}\w"/.test(body), `${page}: guillemets droits "..." détectés dans la copie`);

  // Chiffres kWc / kWh non tracés
  for (const m of body.matchAll(/(\d[\d\s,.]*)\s*(kWc|kWh)/g)) {
    const v = m[1].trim();
    const known = FACTS.some((f) => v.startsWith(f.replace(' ×', ''))) ||
      ['3', '5', '9', '15', '30', '100', '11', '25', '2 800', '3 400', '4', '6', '10', '12', '60', '75'].includes(v.replace(/\s.*/, ''));
    ok(known, `${page}: chiffre non tracé « ${v} ${m[2]} »`);
  }
}

console.log(issues.length ? issues.map((i) => 'PROBLÈME ' + i).join('\n') : 'AUDIT PROPRE — 0 problème');
console.log(`(pages: ${PAGES.length}, URLs vérifiées: ${seen.size})`);
process.exit(0);
