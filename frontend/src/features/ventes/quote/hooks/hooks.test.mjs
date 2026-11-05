// QJR90 — tests du hook de dimensionnement, par sa moitié PURE (patron maison
// `etudeHorairePreview.js` / `etudeHorairePreviewPur.js`). `node --test`
// uniquement : les fichiers `use*.js` importent React et l'API, ils ne sont
// pas exécutables ici — toute la logique testable vit dans les `*Pur.js`.
import test from 'node:test'
import assert from 'node:assert/strict'
import { decisionSizing, motifRefus, REFUS_GENERIQUE } from './useSizingMoteurPur.js'

// ── useSizingMoteur : la garde de péremption sur les DEUX branches ───────────

const CLE = '{"kwc":8.52}'
const ANCIENNE = '{"kwc":5}'
const RECO = { dimensionnement: { recommandation: { panneaux: 21, kwc: 14.91 } } }

test('hors attente, la décision ne touche à RIEN', () => {
  assert.deepEqual(decisionSizing({ attente: false, donnees: RECO }), { action: 'rien' })
  assert.deepEqual(decisionSizing(), { action: 'rien' })
})

test('une frappe manuelle gagne toujours : l’attente se referme sans rien poser', () => {
  const d = decisionSizing({ attente: true, toucheNbPanneaux: true, donnees: RECO,
    cleServie: CLE, cleCourante: CLE })
  assert.equal(d.action, 'abandonner')
})

test('réponse EN VOL : on attend, on ne décide rien', () => {
  assert.equal(decisionSizing({ attente: true, chargement: true }).action, 'attendre')
})

test('SUCCÈS FRAIS : la recommandation serveur est appliquée', () => {
  const d = decisionSizing({ attente: true, donnees: RECO, cleServie: CLE, cleCourante: CLE })
  assert.equal(d.action, 'appliquer')
  assert.deepEqual(d.recommandation, { panneaux: 21, kwc: 14.91 })
})

test('SUCCÈS PÉRIMÉ : le drapeau reste OUVERT, rien n’est appliqué', () => {
  const d = decisionSizing({ attente: true, donnees: RECO,
    cleServie: ANCIENNE, cleCourante: CLE })
  assert.equal(d.action, 'attendre')
  assert.equal(d.raison, 'reponse-perimee')
})

test('ÉCHEC FRAIS : refus, avec le motif FR VERBATIM du serveur', () => {
  const d = decisionSizing({ attente: true, erreur: 'Aperçu indisponible.',
    cleErreur: CLE, cleCourante: CLE })
  assert.equal(d.action, 'refuser')
  assert.equal(d.motif, 'Aperçu indisponible.')
})

test('ÉCHEC PÉRIMÉ : le drapeau reste OUVERT et AUCUN refus obsolète n’est épinglé', () => {
  // C'EST LE CORRECTIF DE LA TÂCHE : aujourd'hui seule la branche SUCCÈS est
  // gardée, et un échec décrivant l'ANCIENNE facture ferme l'attente.
  const d = decisionSizing({ attente: true, erreur: 'Aperçu indisponible.',
    cleErreur: ANCIENNE, cleCourante: CLE })
  assert.equal(d.action, 'attendre')
  assert.equal(d.raison, 'echec-perime')
})

test('ÉCHEC NON ATTRIBUABLE à un corps : traité comme périmé, jamais comme un refus', () => {
  const d = decisionSizing({ attente: true, erreur: 'Boom', cleErreur: null, cleCourante: CLE })
  assert.equal(d.action, 'attendre')
})

test('réponse fraîche SANS recommandation chiffrée : refus, motif nommé', () => {
  const d = decisionSizing({
    attente: true, cleServie: CLE, cleCourante: CLE,
    donnees: { dimensionnement: { motivation: 'Ville du client manquante.' } },
  })
  assert.equal(d.action, 'refuser')
  assert.equal(d.motif, 'Ville du client manquante.')
})

test('ordre du motif : avertissement, puis motivation, puis erreur, puis générique', () => {
  assert.equal(motifRefus({ avertissements: ['A'], dimensionnement: { motivation: 'B' } }, 'C'), 'A')
  assert.equal(motifRefus({ dimensionnement: { motivation: 'B' } }, 'C'), 'B')
  assert.equal(motifRefus(null, 'C'), 'C')
  assert.equal(motifRefus(null, null), REFUS_GENERIQUE)
})

test('aucune réponse encore arrivée : on attend', () => {
  assert.equal(decisionSizing({ attente: true, cleCourante: CLE }).action, 'attendre')
})

// AGNR58 — `validate()` de usePersistanceDevis annonce la ligne sans produit
// écartée par la SEULE définition de lignesEcran.js (le hook importe React :
// vérifié par sa source + la fonction pure qu'il appelle).
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { lignesNonEnvoyees } from '../lignesEcran.js'

test('validate_annonce_ligne_sans_produit', () => {
  const src = readFileSync(fileURLToPath(new URL('./usePersistanceDevis.js', import.meta.url)), 'utf-8')
  assert.match(src, /lignesNonEnvoyees\(lines\)/)
  assert.match(src, /ligne sans produit ne sera pas enregistrée/)
  assert.equal(/const usableLines = \(\) =>\s*lines\.filter/.test(src), false)
  const { sansProduit } = lignesNonEnvoyees([
    { produit: '', quantite: '2', prix_unit_ttc: '0', designation: 'Câble' },
    { produit: '5', quantite: '1', designation: 'Panneau' },
  ])
  assert.deepEqual(sansProduit.map(l => l.designation), ['Câble'])
})

test('ligne_sans_produit_deux_clics', () => {
  // AGNR73 — le 1er clic « Enregistrer » avec « Câble ×2 » sans produit
  // n'écrit rien (l'avertissement reste lu) ; le 2e, sur les MÊMES lignes,
  // enregistre ; lignes changées ⇒ nouvelle signature, nouvel avertissement.
  const src = readFileSync(fileURLToPath(new URL('./usePersistanceDevis.js', import.meta.url)), 'utf-8')
  const corps = src.slice(src.indexOf('const handleSubmit = async'), src.indexOf('const ouvrirConception3D'))
  assert.match(src, /const lignesEcarteesConfirmeRef = useRef\(null\)/)
  const garde = corps.indexOf('lignesEcarteesConfirmeRef.current !== signature')
  assert.ok(garde > 0, 'la garde des deux clics vit dans handleSubmit')
  assert.ok(garde < corps.indexOf('persisterDevis()'), 'avant toute écriture')
  assert.match(corps, /lignesEcarteesConfirmeRef\.current = signature\s*\n\s*return/)
  assert.match(src, /const ecartees = e\.lines \? \[\] : lignesEcartees\(lines\)/)
  const lignes = [
    { produit: '', quantite: '2', prix_unit_ttc: '0', designation: 'Câble' },
    { produit: '5', quantite: '1', designation: 'Panneau' },
  ]
  const sig = (ls) => lignesNonEnvoyees(ls).sansProduit.filter(l => (l.designation || '').trim())
    .map(l => `${l.designation.trim()}×${l.quantite}`).join('|')
  assert.equal(sig(lignes), 'Câble×2')
  assert.notEqual(sig([{ ...lignes[0], quantite: '3' }, lignes[1]]), sig(lignes))
})
