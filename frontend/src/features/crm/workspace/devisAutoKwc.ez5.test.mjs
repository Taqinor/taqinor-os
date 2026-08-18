// EZ5 (2ᵉ moitié) — la puissance cible en kWc atteint le « Devis automatique »
// de la fiche lead.
//
// 1ʳᵉ moitié livrée : le champ « Puissance cible (kWc) » bidirectionnel du
// générateur (`pages/ventes/dimensionnementKwc.ez5.test.mjs`). Restait le
// chemin le plus court du commercial — les ~5 taps du workspace — qui ne
// savait dimensionner QUE d'après la fiche : le client dit « je veux 3 kWc »,
// l'ERP répondait « 4 panneaux, d'après ta facture d'hiver ».
//
// Ce qui bloquait : `onAction('open-devis', mode)` transportait une CHAÎNE
// nue, sans place pour un paramètre. Le contrat est désormais « chaîne OU
// objet » — strictement additif : aucun appelant existant ne change (vérifié
// ci-dessous sur les trois surfaces qui l'appellent avec une chaîne).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { panneauxPourKwc } from '../../ventes/solar.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const read = (p) => readFileSync(path.join(__dirname, p), 'utf8')

const tab = read('DevisTab.jsx')
const workspace = read('LeadWorkspace.jsx')
const panel = read('../../../pages/crm/leads/LeadDevisPanel.jsx')
const autoQuote = read('../../ventes/autoQuote.js')
const rail = read('IdentityRail.jsx')

test('le champ « Puissance cible (kWc) » existe sur le CTA du workspace', () => {
  assert.match(tab, /data-testid="lw-devis-kwc"/)
  assert.match(tab, /Puissance cible \(kWc\)/)
  assert.match(tab, /const \[kwcCible, setKwcCible\] = useState\(''\)/)
  // Étiqueté (le lecteur d'écran nomme le champ) — pas un simple placeholder.
  assert.match(tab, /htmlFor="lw-devis-kwc"/)
  assert.match(tab, /id="lw-devis-kwc"/)
})

test('la saisie n’est JAMAIS rejetée ni arrondie (garde du générateur, portée ici)', () => {
  const champ = tab.slice(tab.indexOf('id="lw-devis-kwc"'), tab.indexOf('id="lw-devis-kwc"') + 400)
  assert.match(champ, /step="any"/)
  assert.doesNotMatch(champ, /step="0\.\d+"/)
  // Aucun `required`/`pattern` : le champ est FACULTATIF, vide = comportement
  // historique — le trajet à 1 clic du commercial reste à 1 clic.
  assert.doesNotMatch(champ, /\brequired\b/)
  assert.match(tab, /placeholder="auto"/)
})

test('le payload reste une CHAÎNE sans cible, et devient un objet avec cible', () => {
  // La règle est isolée dans une fonction pure exportée (testable, un seul
  // endroit où le contrat est décidé).
  assert.match(tab, /export function devisIntent\(mode, kwcCible\) \{/)
  assert.match(tab, /if \(!cible \|\| mode === 'edit'\) return mode/)
  assert.match(tab, /return \{ mode, targetKwc: cible \}/)
  // Les 4 modes qui DIMENSIONNENT passent par elle…
  for (const mode of ['auto', 'remise', 'onepage', 'premium']) {
    assert.match(tab, new RegExp(`devisIntent\\('${mode}', kwcCible\\)`),
      `le mode ${mode} doit passer par devisIntent`)
  }
  // …et « edit » reste la chaîne nue : il ouvre le générateur, qui a son
  // PROPRE champ kWc (1ʳᵉ moitié) — deux cibles rivales seraient un piège.
  assert.match(tab, /onAction\?\.\('open-devis', 'edit'\)/)
})

test('les appelants historiques d’open-devis ne bougent pas', () => {
  // IdentityRail (bouton ⚡ du rail) et la palette de commandes du workspace
  // appellent toujours avec la chaîne 'auto'.
  assert.match(rail, /onAction\('open-devis', 'auto'\)/)
  assert.match(workspace, /onAction\('open-devis', 'auto'\)/)
})

test('LeadWorkspace lit les DEUX formes, sans casser `devisPanel`', () => {
  assert.match(workspace, /const intent = \(payload && typeof payload === 'object'\) \? payload : \{ mode: payload \}/)
  assert.match(workspace, /setDevisKwc\(intent\.targetKwc \|\| null\)/)
  assert.match(workspace, /setDevisPanel\(intent\.mode \|\| 'auto'\)/)
  // `devisPanel` reste une chaîne : la comparaison `=== 'view'` (qui décide
  // du devis existant à afficher) continue de fonctionner telle quelle.
  assert.match(workspace, /devisPanel === 'view' \? panelDevisId : null/)
  // La cible ne survit pas à la fermeture du panneau (pas d'état fantôme).
  assert.match(workspace, /setDevisPanel\(null\); setPanelDevisId\(null\); setDevisKwc\(null\)/)
  assert.match(workspace, /targetKwc=\{devisKwc\}/)
})

test('la cible traverse le panneau jusqu’au calcul partagé', () => {
  assert.match(panel, /targetKwc = null/)
  // PVMRQ (18/08) — `marques` suit `targetKwc` dans l'appel : la cible traverse
  // toujours, accompagnée des marques épinglées.
  assert.match(panel, /createAutoQuote\(\{[\s\S]{0,200}?targetKwc,[\s\S]{0,120}?\}\)/)
  // PVMRQ (18/08) — la signature porte aussi `marques` après `targetKwc`.
  assert.match(autoQuote, /pumpHours, onEtude,\s*\n\s*targetKwc, marques \}\)/)
})

test('la cible prime sur la fiche, mais ne l’écrase jamais', () => {
  // Priorité : cible ponctuelle > taille souhaitée du lead > facture d'hiver.
  assert.match(autoQuote, /const cibleKwc = parseFloat\(targetKwc\) \|\| 0/)
  // Règle des paliers (18/08) : la cible explicite garde sa priorité mais est
  // RAMENÉE au palier de 5 kWc — aucun devis auto hors palier.
  assert.match(autoQuote, /const explicitKwc = cibleKwc > 0 \? cibleKwc : \(parseFloat\(lead\.taille_souhaitee_kwc\) \|\| 0\)/)
  assert.match(autoQuote, /const tailleKwc = explicitKwc > 0 \? arrondirAuPasKwc\(explicitKwc\) : 0/)
  // Rien n'est écrit sur le lead : `taille_souhaitee_kwc` n'apparaît nulle
  // part en écriture dans le chemin du devis auto.
  assert.doesNotMatch(autoQuote, /taille_souhaitee_kwc:/)
})

test('la conversion kWc→panneaux est RÉUTILISÉE, pas réécrite', () => {
  assert.match(autoQuote, /panneauxPourKwc\(tailleKwc, 710\)/)
  // Aucune arithmétique kWc→panneaux recopiée à la main dans autoQuote.
  assert.doesNotMatch(autoQuote, /Math\.ceil\([^)]*\*\s*1000\s*\/\s*710/)
  // La conversion partagée, elle, dit bien ce que le commercial attend :
  // « 3 kWc » en panneaux de 710 W → 4 panneaux.
  assert.equal(panneauxPourKwc(3, 710), 4)
  assert.equal(panneauxPourKwc(6, 710), 8)
})
