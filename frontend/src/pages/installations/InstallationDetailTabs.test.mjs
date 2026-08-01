// APX25 — la fiche chantier passe du mur de 15 sections à 6 onglets.
// Ces tests verrouillent la MATRICE section → onglet (aucun contenu perdu) et
// la bannière de synthèse UNIQUE (les 5 messages d'origine sont conservés,
// hiérarchisés, le reste dans un popover).
//
//   node --test src/pages/installations/InstallationDetailTabs.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'InstallationDetail.jsx'), 'utf8')

// Matrice de référence : chaque section d'origine et l'onglet qui l'accueille.
// APX26 — l'ex-section « Timeline » est fusionnée dans « Parcours & jalons ».
const MATRICE = {
  apercu: ['Liens', 'Chantier', 'Dossier réglementaire (loi 82-21)'],
  jalons: ['Parcours & jalons', "Checklist d'exécution", 'Mise en service'],
  materiel: ['Besoin matériel', 'Équipements'],
  photos: ['Photos & fichiers'],
  interventions: ['Interventions', 'Tickets SAV', 'Suivi & maintenance'],
  documents: ['Documents après-vente', 'Historique'],
}

function panneau(valeur) {
  const start = SRC.indexOf(`<TabsContent value="${valeur}"`)
  assert.notEqual(start, -1, `onglet ${valeur} absent`)
  const end = SRC.indexOf('</TabsContent>', start)
  assert.notEqual(end, -1, `onglet ${valeur} non fermé`)
  return SRC.slice(start, end)
}

test('les 6 onglets existent, chacun avec son déclencheur', () => {
  for (const valeur of Object.keys(MATRICE)) {
    assert.match(SRC, new RegExp(`<TabsTrigger value="${valeur}"`), `déclencheur ${valeur}`)
    assert.match(SRC, new RegExp(`<TabsContent value="${valeur}"`), `panneau ${valeur}`)
  }
  const triggers = SRC.match(/<TabsTrigger value="/g) ?? []
  const panneaux = SRC.match(/<TabsContent value="/g) ?? []
  assert.equal(triggers.length, 6)
  assert.equal(panneaux.length, 6)
})

test('matrice section → onglet : toutes les sections sont placées, aucune perdue', () => {
  const titres = [...SRC.matchAll(/<Section\s[^>]*?title="([^"]+)"/gs)].map((m) => m[1])
    .concat([...SRC.matchAll(/\n\s*title="([^"]+)"/g)].map((m) => m[1]))
  // 14 sections (15 d'origine — APX26 fusionne « Timeline » dans le parcours).
  const attendues = Object.values(MATRICE).flat()
  assert.equal(attendues.length, 14)
  for (const titre of attendues) {
    assert.ok(titres.includes(titre), `section « ${titre} » disparue de la fiche`)
  }
  // …et chacune dans SON onglet, une seule fois.
  for (const [valeur, sections] of Object.entries(MATRICE)) {
    const corps = panneau(valeur)
    for (const titre of sections) {
      const occurrences = corps.split(`title="${titre}"`).length - 1
      assert.equal(occurrences, 1, `« ${titre} » attendue une fois dans l'onglet ${valeur}`)
    }
  }
})

test('aucune section ne reste hors des onglets (mur de sections supprimé)', () => {
  const debut = SRC.indexOf('<Tabs value={tab}')
  const fin = SRC.indexOf('</Tabs>')
  assert.ok(debut !== -1 && fin > debut, 'conteneur Tabs absent')
  const avant = SRC.slice(SRC.indexOf('<SheetContent'), debut)
  assert.equal(avant.includes('<Section'), false, 'une section est restée avant les onglets')
  const apres = SRC.slice(fin)
  assert.equal(apres.includes('<Section'), false, 'une section est restée après les onglets')
})

test('bannière de synthèse UNIQUE : un seul rendu, les 5 messages conservés', () => {
  assert.equal((SRC.match(/<ChantierAlerts/g) ?? []).length, 1)
  // Les 5 alertes d'origine, dans l'ordre de gravité (danger → warning → info).
  const ordre = ['annule', 'action-error', 'devis-divergent', 'bom-absente', 'next-action']
  let curseur = SRC.indexOf('const alerts = [')
  assert.notEqual(curseur, -1, 'liste d\'alertes absente')
  for (const cle of ordre) {
    const at = SRC.indexOf(`key: '${cle}'`, curseur)
    assert.notEqual(at, -1, `alerte ${cle} absente ou mal ordonnée`)
    curseur = at
  }
  // Le reste est COMPTÉ, pas supprimé.
  assert.match(SRC, /\+\$\{rest\.length\} alertes/)
  assert.match(SRC, /<PopoverTrigger asChild>/)
  // Chaque action des anciennes bannières survit (Réactiver / Fermer).
  assert.match(SRC, />Réactiver</)
  assert.match(SRC, /onClick=\{onClearError\}/)
})

test('les onglets restent tactiles (≥ 44 px) et défilent sur mobile', () => {
  const list = SRC.slice(SRC.indexOf('<TabsList'), SRC.indexOf('</TabsList>'))
  assert.match(list, /overflow-x-auto/)
  const triggers = [...list.matchAll(/<TabsTrigger[^>]*className="([^"]*)"/g)].map((m) => m[1])
  assert.equal(triggers.length, 6)
  for (const cls of triggers) assert.match(cls, /min-h-11/)
})
