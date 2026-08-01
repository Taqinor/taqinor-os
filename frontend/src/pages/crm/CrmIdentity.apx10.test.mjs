// APX10 — Le reste du CRM rejoint le niveau des Leads.
// ----------------------------------------------------------------------------
// Etat verifie avant : ClientList ouvrait sur un `<h2>` nu dans un
// `page-header` generique, Forecast et Ma file sur des `Card` nues, et
// `ModuleHero` (VX15) n'etait consomme par AUCUN ecran crm — l'app la plus
// travaillee de l'ERP n'avait d'identite que sur son board.
//
// Ce fichier verrouille la CONSEQUENCE structurelle : plus AUCUN `page-header`
// legacy dans pages/crm/, et deux grammaires seulement (hero de module pour
// une destination, ligne de controle LB43 pour une liste) — jamais une
// troisieme reinventee sur le prochain ecran.
//   node --test src/pages/crm/CrmIdentity.apx10.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const lire = (p) => lf(readFileSync(p, 'utf8'))

const CLIENTS = lire(join(HERE, 'ClientList.jsx'))
const FORECAST = lire(join(HERE, 'forecast/ForecastPage.jsx'))
const MAFILE = lire(join(HERE, '../activities/MesActivitesPage.jsx'))
const CSS = lf(readFileSync(join(HERE, '../../index.css'), 'utf8'))

/** Tous les .jsx de pages/crm/ (recursif), hors tests. */
function fichiersCrm(dir = HERE, acc = []) {
  for (const nom of readdirSync(dir)) {
    const p = join(dir, nom)
    if (statSync(p).isDirectory()) { fichiersCrm(p, acc); continue }
    if (nom.endsWith('.jsx') && !nom.includes('.test.')) acc.push(p)
  }
  return acc
}

test('APX10 : ZERO `page-header` legacy dans pages/crm/ (h2 nu sans grammaire)', () => {
  const coupables = []
  for (const p of fichiersCrm()) {
    for (const ligne of lire(p).split('\n')) {
      const m = ligne.match(/className="([^"]*\bpage-header\b[^"]*)"/)
      if (!m) continue
      const classes = m[1].split(/\s+/)
      // `page-header` n'est plus legitime qu'ACCOMPAGNE de la grammaire de
      // ligne de controle LB43 (`lp-controlbar`) — ou comme conteneur
      // d'actions (`page-header-actions`), qui n'est pas un en-tete.
      const ok = classes.includes('lp-controlbar') || classes.includes('page-header-actions')
      if (!ok) coupables.push(`${p.slice(p.indexOf('pages'))}: ${ligne.trim()}`)
    }
  }
  assert.deepEqual(coupables, [], `page-header legacy restant :\n${coupables.join('\n')}`)
})

test('APX10 : ModuleHero (VX15) est enfin consomme par des ecrans CRM', () => {
  // Le constat qui a motive la tache : il ne l'etait par AUCUN.
  assert.match(FORECAST, /import \{ ModuleHero \} from '\.\.\/\.\.\/\.\.\/ui\/module'/)
  assert.match(MAFILE, /import \{ ModuleHero \} from '\.\.\/\.\.\/ui\/module'/)
  assert.match(FORECAST, /<ModuleHero\s/)
  assert.match(MAFILE, /<ModuleHero\s/)
})

test('APX10 : UN SEUL accent de module sur tout le CRM (azur), jamais une couleur inventee', () => {
  for (const [nom, src] of [['Forecast', FORECAST], ['Ma file', MAFILE]]) {
    assert.match(src, /accent="var\(--module-accent-azur\)"/, `${nom} : accent CRM absent`)
  }
  assert.match(CSS, /\.crm-controlbar \.crm-accent-dot \{[^}]*background: var\(--module-accent-azur\);/s)
  // La pastille est decorative : jamais un nom accessible parasite (le piege
  // classique quand un ecran gagne une puce de couleur).
  for (const src of [CLIENTS, MAFILE]) {
    assert.match(src, /<span className="crm-accent-dot" aria-hidden="true" \/>/)
  }
})

test('APX10 : un ecran n\'a QU\'UNE identite de module (pas deux heros empiles)', () => {
  assert.equal((MAFILE.match(/<ModuleHero\s/g) || []).length, 1)
  assert.equal((FORECAST.match(/<ModuleHero\s/g) || []).length, 1)
  // La sous-section « Mes activites » utilise la ligne de controle, pas un 2e hero.
  assert.match(MAFILE, /<div className="lp-controlbar crm-controlbar mt-2">/)
})

test('APX10 : la ligne de controle Clients reprend la grammaire LB43 des leads', () => {
  assert.match(CLIENTS, /className="page-header lp-controlbar crm-controlbar"/)
  assert.match(CLIENTS, /<h2 className="lp-cb-title">/)
  assert.match(CLIENTS, /className="page-header-actions lp-header-actions"/)
  // ... la MEME que LeadsPage (jamais une seconde mise en page).
  const leads = lire(join(HERE, 'leads/LeadsPage.jsx'))
  assert.match(leads, /className="page-header lp-header lp-controlbar"/)
  assert.match(CSS, /\.lp-controlbar \{[^}]*display: flex;/s)
})

test('APX10 : Forecast passe a la grammaire des cartes a ACCENT (VX149), plus des Card nues', () => {
  assert.match(FORECAST, /import StatusAccentCard from '\.\.\/\.\.\/\.\.\/ui\/StatusAccentCard'/)
  assert.match(FORECAST, /<StatusAccentCard\s/)
  assert.match(FORECAST, /variant="compact"/)
  assert.doesNotMatch(FORECAST, /<Card\b/)
  assert.doesNotMatch(FORECAST, /\bCard,|, Card\b/)
})

test('APX10 : DataTable reste intouche (il est deja sur useDensity) et le contenu est preserve', () => {
  // ClientList rend son tableau via le moteur partage : APX10 ne touche QUE
  // l'en-tete de page, jamais le tableau (sa densite appartient a APX34).
  assert.match(CLIENTS, /<DataTable\b/)
  assert.doesNotMatch(CSS.slice(CSS.indexOf('APX10 — LE RESTE DU CRM')), /\.data-table/)
  // Rien n'a ete retire : le resume VX83 de Ma file, les totaux Forecast et le
  // compteur Clients sont toujours rendus.
  assert.match(MAFILE, /resume\.en_retard \? `\$\{resume\.en_retard\} en retard` : null/)
  assert.match(FORECAST, /Sous-total équipe/)
  assert.match(CLIENTS, /<span className="count-badge">\{clients\.length\}<\/span>/)
})

test('APX10 : le mois du Forecast garde un nom accessible en montant dans le hero', () => {
  // Deplacer un champ dans `actions` lui ferait perdre son etiquette visuelle :
  // on la remplace explicitement par un aria-label (jamais un champ muet).
  assert.match(FORECAST, /aria-label="Période du forecast"/)
})
