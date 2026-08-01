// APX18 — Photo produit : le chemin d'upload du formulaire, vérifié SUR LA
// SOURCE (ce lane n'a pas de node_modules ; ce test tourne aussi en CI, qui
// découvre tout `src/**/*.test.mjs` par glob).
//   node --test src/pages/stock/ProduitFormApx18Photo.test.mjs
//
// Ce qui est verrouillé ici :
//   * la photo passe par la compression cliente VX77 avant l'envoi (une photo
//     d'appareil moderne fait 4-8 Mo : intenable sur la 3G rurale) ;
//   * elle part en multipart APRÈS l'enregistrement du produit, et un échec
//     d'upload ne perd JAMAIS le produit déjà créé ;
//   * la photo n'est jamais rendue à côté du prix d'achat, ni dans un PDF
//     (aucun chemin de rendu client ne la lit — règle #4) ;
//   * l'aperçu local ne fuit pas d'objectURL.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (rel) => readFileSync(join(HERE, rel), 'utf8')

const FORM = read('ProduitForm.jsx')
const TABLE = read('CatalogueTable.jsx')
const DETAIL = read('ProduitDetail.jsx')
const API = read('../../api/stockApi.js')

test('la photo est compressée (VX77) avant tout envoi', () => {
  assert.match(FORM, /import \{ compressImage, validateFile \} from '\.\.\/\.\.\/ui\/file-utils'/)
  assert.match(FORM, /const compresse = await compressImage\(file\)/)
})

test('le fichier est validé (type image + taille) avant compression', () => {
  assert.match(FORM, /const PHOTO_ACCEPT = 'image\/\*'/)
  assert.match(FORM, /const PHOTO_MAX_SIZE = 10 \* 1024 \* 1024/)
  assert.match(FORM, /validateFile\(file, \{ accept: PHOTO_ACCEPT, maxSize: PHOTO_MAX_SIZE \}\)/)
})

test('l\'envoi se fait en multipart, APRÈS l\'enregistrement, sur l\'id connu', () => {
  assert.match(API, /uploadProduitImage: \(id, file\) => \{/)
  assert.match(API, /new FormData\(\)/)
  assert.match(API, /'Content-Type': 'multipart\/form-data'/)
  // L'id vient du produit renvoyé par la création, ou de celui en édition.
  assert.match(FORM, /const cibleId = enregistre\?\.id \?\? produit\?\.id/)
  assert.match(FORM, /await stockApi\.uploadProduitImage\(cibleId, photoFile\)/)
})

test('UN seul aller-retour : l\'action serveur téléverse ET rattache (ARC26)', () => {
  // Jamais deux appels client (POST pièce jointe puis PATCH produit) : ça
  // laisserait une pièce jointe orpheline si le client coupe entre les deux.
  assert.match(API, /api\.post\(`\/stock\/produits\/\$\{id\}\/photo\/`, fd/)
  assert.match(API, /if \(!file\) return api\.delete\(`\/stock\/produits\/\$\{id\}\/photo\/`\)/)
})

test('le plafond client est CALÉ sur celui du serveur (10 Mo)', () => {
  const STORAGE = read('../../../../backend/django_core/apps/records/storage.py')
  assert.match(STORAGE, /_MAX_BYTES\s*=\s*10\s*\*\s*1024\s*\*\s*1024/)
})

test('un échec d\'upload ne perd jamais le produit déjà enregistré', () => {
  // L'appel est dans son propre try/catch : on prévient, on n'annule pas.
  const bloc = FORM.slice(FORM.indexOf('const cibleId'), FORM.indexOf('onSaved?.()'))
  assert.match(bloc, /try \{/)
  assert.match(bloc, /\} catch \(errPhoto\) \{/)
  assert.match(bloc, /toast\.error\(/)
  // Le message serveur (format refusé, trop lourd) est relayé tel quel.
  assert.match(bloc, /errPhoto\?\.response\?\.data\?\.detail/)
})

test('« Créer un autre » repart sans photo (pas de re-téléversement en boucle)', () => {
  const bloc = FORM.slice(FORM.indexOf('if (!isEdit && creerUnAutre)'))
  assert.match(bloc, /retirerPhoto\(\)/)
})

test('l\'aperçu local révoque son objectURL (aucune fuite de blob)', () => {
  assert.match(FORM, /URL\.revokeObjectURL/)
  assert.match(FORM, /useEffect\(\(\) => \(\) => \{ if \(photoApercu\) URL\.revokeObjectURL\(photoApercu\) \}, \[photoApercu\]\)/)
})

test('retirer une photo NON enregistrée ne déclenche pas un PATCH de suppression', () => {
  assert.match(FORM, /setPhotoRetiree\(!!produit\?\.image_url\)/)
})

test('la vignette catalogue a un repli d\'icône de catégorie (jamais de trou)', () => {
  assert.match(TABLE, /import \{ categorieIcone, keySpec, prixTtc, sansPrix \}/)
  assert.match(TABLE, /produit\.image_url\s*\n?\s*\?\s*<img/)
  assert.match(TABLE, /:\s*<Icone className="size-5" \/>/)
})

test('la fiche produit ne rend RIEN quand il n\'y a pas de photo', () => {
  assert.match(DETAIL, /if \(!produit\.image_url\) return null/)
})

test('la photo ne côtoie jamais le prix d\'achat côté client', () => {
  // Aucune des surfaces d'affichage de la photo ne LIT `prix_achat` (les
  // mentions en commentaire — « prix_achat n'est jamais exposé ici » — sont
  // au contraire la documentation de cette règle, on ne les traque pas).
  for (const [nom, src] of [['CatalogueTable', TABLE], ['ProduitDetail', DETAIL]]) {
    assert.ok(!/\.prix_achat|\bprix_achat:/.test(src),
      `${nom} ne doit jamais lire prix_achat`)
  }
  // Le formulaire, lui, édite légitimement le prix d'achat (écran INTERNE du
  // générateur) : on vérifie seulement que la photo n'est pas rendue dans le
  // même bloc — elle vit dans la section « identité », le prix dans « Prix & TVA ».
  const iPhoto = FORM.indexOf('pf-photo-apercu')
  const iPrix = FORM.indexOf('id="pf-achat"')
  assert.ok(iPhoto > 0 && iPrix > 0)
  assert.ok(iPhoto < iPrix, 'la photo reste dans la section identité, avant les prix')
})

test('AUCUN chemin PDF ne lit la photo (règle #4 — le moteur vendorisé seul rend)', () => {
  const engine = read('../../features/ventes/PdfCanvas.jsx')
  assert.ok(!/image_url/.test(engine),
    'le rendu PDF ne doit jamais consommer la photo produit')
})
