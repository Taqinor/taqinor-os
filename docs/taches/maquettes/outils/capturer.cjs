// Rend une maquette HTML en PNG (iPhone 390x844 et bureau 1440x900, clair et sombre).
// Usage : node capturer.cjs <fichier.html> [dossier de sortie]
// Playwright vient du checkout principal (les worktrees n'ont pas de node_modules).
const path = require('path');
const fs = require('fs');
const pw = require(process.env.PLAYWRIGHT_DIR || 'C:/dev/taqinor-os/frontend/node_modules/playwright');
(async () => {
  const fichier = path.resolve(process.argv[2]);
  const sortie = path.resolve(process.argv[3] || path.join(path.dirname(fichier), 'captures'));
  fs.mkdirSync(sortie, { recursive: true });
  const nom = path.basename(fichier, '.html');
  const navigateur = await pw.chromium.launch();
  const vues = [
    { cle: 'iphone', width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
    { cle: 'bureau', width: 1440, height: 900, deviceScaleFactor: 1 },
  ];
  for (const vue of vues) {
    for (const theme of ['clair', 'sombre']) {
      const { cle, ...viewport } = vue;
      const contexte = await navigateur.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        deviceScaleFactor: viewport.deviceScaleFactor,
        isMobile: !!viewport.isMobile, hasTouch: !!viewport.hasTouch,
        colorScheme: theme === 'sombre' ? 'dark' : 'light',
      });
      const page = await contexte.newPage();
      await page.goto('file:///' + fichier.split(path.sep).join('/') + '?vue=' + cle + '&theme=' + theme);
      await page.evaluate((t) => document.documentElement.classList.toggle('dark', t === 'sombre'), theme);
      await page.waitForTimeout(250);
      const cible = path.join(sortie, `${nom}-${cle}-${theme}.png`);
      await page.screenshot({ path: cible, fullPage: false });
      console.log(cible);
      await contexte.close();
    }
  }
  await navigateur.close();
})().catch((e) => { console.error(e.message); process.exit(1); });
