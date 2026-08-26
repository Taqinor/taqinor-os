// WIR256 — le lien « Voir l'écriture comptable » (WIR24) existait comme
// composant réutilisable (EcritureSourceLink, testé et fonctionnel — voir
// components/EcritureSourceLink.test.jsx pour les 2 cas présent/absent) mais
// n'était monté NULLE PART : ni sur la facture, ni sur un paiement, ni sur un
// avoir. Ce test SOURCE (comme wir180/181/254/255) vérifie le CÂBLAGE réel
// dans les 3 écrans ventes, avec le `sourceType` EXACT que le serveur écrit
// (`apps/compta/services.py` : `source_type='facture'|'paiement'|'avoir'`,
// jamais un pluriel ou une variante inventée qui casserait le lien en silence).
//   node --test src/features/compta/wir256-ecriture-source-link.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const FACTURE_SRC = readFileSync(join(HERE, '../../pages/ventes/FactureForm.jsx'), 'utf8')
const AVOIRS_SRC = readFileSync(join(HERE, '../../pages/ventes/AvoirsPage.jsx'), 'utf8')
const PAIEMENTS_SRC = readFileSync(join(HERE, '../../pages/ventes/PaiementsPage.jsx'), 'utf8')

const IMPORT_RE = /import EcritureSourceLink from ['"]([^'"]+)['"]/

function verifieImport(src, cheminAttendu) {
  const m = src.match(IMPORT_RE)
  assert.ok(m, 'import de EcritureSourceLink introuvable')
  assert.equal(m[1], cheminAttendu)
}

test('FactureForm : EcritureSourceLink monté sur le détail (isEdit), sourceType="facture"', () => {
  verifieImport(FACTURE_SRC, '../../features/compta/components/EcritureSourceLink.jsx')
  assert.match(FACTURE_SRC, /<EcritureSourceLink sourceType="facture" sourceId={facture\.id} \/>/)
  // Jamais monté en création (pas encore de facture.id à interroger).
  const bloc = FACTURE_SRC.match(
    /\{isEdit && facture\?\.id && \(\s*<EcritureSourceLink[\s\S]*?\)\}/)[0]
  assert.match(bloc, /isEdit && facture\?\.id/)
})

test('AvoirsPage : EcritureSourceLink monté par ligne, sourceType="avoir"', () => {
  verifieImport(AVOIRS_SRC, '../../features/compta/components/EcritureSourceLink.jsx')
  assert.match(AVOIRS_SRC, /<EcritureSourceLink sourceType="avoir" sourceId={a\.id} \/>/)
})

test('PaiementsPage : EcritureSourceLink monté par ligne, sourceType="paiement"', () => {
  verifieImport(PAIEMENTS_SRC, '../../features/compta/components/EcritureSourceLink.jsx')
  assert.match(PAIEMENTS_SRC, /<EcritureSourceLink sourceType="paiement" sourceId={p\.id} \/>/)
})

test('les 3 sourceType correspondent EXACTEMENT à apps/compta/services.py (jamais un pluriel inventé)', () => {
  // Épingle la régression la plus probable : "factures"/"paiements"/"avoirs"
  // (pluriel du nom d'écran) au lieu du singulier réellement écrit en base.
  assert.doesNotMatch(FACTURE_SRC, /sourceType="factures"/)
  assert.doesNotMatch(AVOIRS_SRC, /sourceType="avoirs"/)
  assert.doesNotMatch(PAIEMENTS_SRC, /sourceType="paiements"/)
})
