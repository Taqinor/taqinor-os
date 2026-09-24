// CALX400 — Contrat de hooks DOM `data-testid="cal-*"`.
// Zéro dépendance (node:test + node:fs, patron `frontend/parked/features/ao/e2eHooks.test.mjs`) :
// exécutable via `node --test` sans npm/vitest installés.
//
// Trois garanties :
//  1. Aucun hook du contrat ne peut disparaître de `E2E_HOOKS.md` ni y perdre
//     sa sémantique (les deux listes sont tenues égales).
//  2. `E2E_HOOKS.md` ne documente aucun hook hors d'`ALL_HOOKS`.
//  3. Aucun fichier de `features/calepinage/**` (hors tests) n'introduit un
//     `data-testid="cal-*"` hors contrat — un hook dynamique (`${id}` au
//     milieu ou en fin du gabarit) est normalisé à sa base fixe avant le test,
//     exactement comme le contrat le documente.
//
// Mesuré à l'exécution de CALX400 : 406 hooks distincts — davantage
// que la mesure de tête du lot 8 (200), le module ayant grandi entre l'écriture
// de la tâche et son exécution (onglets documents/pompage/production/équipements).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative, sep } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DOC_PATH = join(HERE, 'E2E_HOOKS.md')
const FEATURE_ROOT = HERE

// Source de vérité normative (CALX400) — la SEULE liste qui grandit le contrat ;
// toute extension passe par une nouvelle entrée ICI + dans E2E_HOOKS.md, dans le
// MÊME commit (le test 3 compare les deux listes et refuse la divergence). Ordre :
// un groupe par fichier propriétaire, alphabétique à l'intérieur.
export const ALL_HOOKS = [
  // ── AtelierPanneaux.jsx ──
  'cal-atelier-actions',
  'cal-atelier-panneaux',
  'cal-bandeau-lecture-seule',
  'cal-cible-panneaux',
  'cal-deverrouiller',
  'cal-deverrouiller-annuler',
  'cal-deverrouiller-confirmation',
  'cal-deverrouiller-confirmer',
  'cal-deverrouiller-refus',
  'cal-lien-photos-calage',
  'cal-lien-variantes',
  // ── BadgePerime.jsx ──
  'cal-badge-perime',
  // ── Bibliotheque.jsx ──
  'cal-biblio',
  'cal-biblio-erreur',
  'cal-biblio-favori',
  'cal-biblio-favori-ajouter',
  'cal-biblio-favori-erreur',
  'cal-biblio-favori-ids',
  'cal-biblio-favori-ligne',
  'cal-biblio-favori-retirer',
  'cal-biblio-favori-role',
  'cal-biblio-favoris-edition',
  'cal-biblio-favoris-enregistrer',
  'cal-biblio-favoris-erreur',
  'cal-biblio-favoris-liste',
  'cal-biblio-kit',
  'cal-biblio-kits-liste',
  'cal-biblio-lecture-seule',
  'cal-biblio-lien-reglages',
  'cal-biblio-modele',
  'cal-biblio-modele-annuler',
  'cal-biblio-modele-client',
  'cal-biblio-modele-creer',
  'cal-biblio-modele-depart',
  'cal-biblio-modele-erreur',
  'cal-biblio-modele-lead',
  'cal-biblio-modele-ouvrir',
  'cal-biblio-modele-partir',
  'cal-biblio-modeles-liste',
  'cal-biblio-preset',
  'cal-biblio-preset-ajouter',
  'cal-biblio-preset-champs',
  'cal-biblio-preset-cle',
  'cal-biblio-preset-erreur',
  'cal-biblio-preset-ligne',
  'cal-biblio-preset-retirer',
  'cal-biblio-preset-source',
  'cal-biblio-presets-edition',
  'cal-biblio-presets-enregistrer',
  'cal-biblio-presets-erreur',
  'cal-biblio-presets-liste',
  'cal-biblio-profil',
  'cal-biblio-profil-ajouter',
  'cal-biblio-profil-cle',
  'cal-biblio-profil-courbe',
  'cal-biblio-profil-erreur',
  'cal-biblio-profil-famille',
  'cal-biblio-profil-libelle',
  'cal-biblio-profil-provenance',
  'cal-biblio-profil-repli',
  'cal-biblio-profil-retirer',
  'cal-biblio-profils-enregistrer',
  'cal-biblio-profils-erreur',
  'cal-biblio-profils-liste',
  'cal-bibliotheque',
  // ── BoutonDevis.jsx ──
  'cal-bouton-devis',
  'cal-devis-conflit',
  'cal-devis-refus',
  'cal-devis-reviser',
  'cal-devis-variante-manquante',
  'cal-generer-devis',
  'cal-resynchroniser-devis',
  // ── CalepinageList.jsx ──
  'cal-vignette',
  'cal-vignette-image',
  'cal-vignette-sans-image',
  // ── CourseSoleil.jsx ──
  'cal-course-soleil',
  'cal-course-soleil-hauteur-toit',
  'cal-course-soleil-hauteur-toit-champ',
  'cal-course-soleil-hauteur-toit-provenance',
  'cal-course-soleil-hauteur-toit-valeur',
  'cal-course-soleil-loading',
  'cal-course-soleil-obstruction-hauteur',
  'cal-course-soleil-obstructions-hauteur',
  'cal-course-soleil-scene',
  // ── FicheCalepinage.jsx ──
  'cal-fiche',
  'cal-fiche-actions',
  'cal-fiche-archivage-erreur',
  'cal-fiche-archiver',
  'cal-fiche-archiver-annuler',
  'cal-fiche-archiver-confirmation',
  'cal-fiche-bandeau-archive',
  'cal-fiche-bandeau-nom',
  'cal-fiche-bloc',
  'cal-fiche-calepinage',
  'cal-fiche-dupliquer',
  'cal-fiche-dupliquer-annuler',
  'cal-fiche-dupliquer-confirmation',
  'cal-fiche-dupliquer-confirmer',
  'cal-fiche-dupliquer-erreur',
  'cal-fiche-dupliquer-variantes',
  'cal-fiche-modele',
  'cal-fiche-modele-erreur',
  'cal-fiche-nom-annuler',
  'cal-fiche-nom-champ',
  'cal-fiche-nom-editer',
  'cal-fiche-nom-enregistrer',
  'cal-fiche-nom-erreur',
  'cal-fiche-restaurer',
  // ── HorizonPanel.jsx ──
  'cal-horizon',
  'cal-horizon-champ-azimut',
  'cal-horizon-champ-hauteur',
  'cal-horizon-hauteur-max',
  'cal-horizon-heures-masquees',
  'cal-horizon-loading',
  'cal-horizon-points',
  // ── ModeTerrain.jsx ──
  'cal-terrain',
  'cal-terrain-calculer',
  'cal-terrain-contour',
  'cal-terrain-cote',
  'cal-terrain-cote-pas',
  'cal-terrain-emprise',
  'cal-terrain-enregistrer',
  'cal-terrain-message',
  'cal-terrain-modules',
  'cal-terrain-nonmesure',
  'cal-terrain-pas',
  'cal-terrain-rangee',
  'cal-terrain-svg',
  'cal-terrain-table',
  'cal-terrain-tables',
  'cal-terrain-taux',
  'cal-terrain-trait-pas',
  'cal-terrain-vue',
  'cal-terrain-vue-indisponible',
  // ── Ombriere.jsx ──
  'cal-ombriere',
  'cal-ombriere-altitude',
  'cal-ombriere-buildingId',
  'cal-ombriere-calculer',
  'cal-ombriere-cote',
  'cal-ombriere-cote-hauteur',
  'cal-ombriere-coupe',
  'cal-ombriere-couverture',
  'cal-ombriere-ecoulement',
  'cal-ombriere-emprise',
  'cal-ombriere-emprise-tracee',
  'cal-ombriere-enregistrer',
  'cal-ombriere-hauteur',
  'cal-ombriere-message',
  'cal-ombriere-modules',
  'cal-ombriere-nonmesure',
  'cal-ombriere-pas',
  'cal-ombriere-rangee',
  'cal-ombriere-sol',
  'cal-ombriere-svg',
  'cal-ombriere-total',
  'cal-ombriere-totaux',
  'cal-ombriere-trait-hauteur',
  'cal-ombriere-travee',
  'cal-ombriere-travees',
  'cal-ombriere-vue',
  'cal-ombriere-vue-indisponible',
  // ── PanneauAllees.jsx ──
  'cal-allees-actuelle',
  'cal-allees-appliquer-suggestion',
  'cal-allees-champ',
  'cal-allees-enregistrer',
  'cal-allees-message',
  'cal-allees-non-reglee',
  'cal-allees-rechercher',
  'cal-allees-refus',
  'cal-allees-sans-plateau',
  'cal-allees-suggestion',
  'cal-panneau-allees',
  // ── PhotoSiteCalage.jsx ──
  'cal-photo-calage',
  'cal-photo-calage-canvas',
  'cal-photo-calage-carte',
  'cal-photo-calage-effacer',
  'cal-photo-calage-enregistrer',
  'cal-photo-calage-message',
  'cal-photo-calage-opacite',
  'cal-photo-calage-select',
  'cal-photo-calage-vide',
  'cal-photo-depot',
  'cal-photo-depot-date',
  'cal-photo-depot-erreur-date',
  'cal-photo-depot-erreur-genre',
  'cal-photo-depot-erreur-photo',
  'cal-photo-depot-fichier',
  'cal-photo-depot-genre',
  'cal-photo-depot-legende',
  // ── PlanImporteCalage.jsx ──
  'cal-calage-aimantation',
  'cal-calage-analyse',
  'cal-calage-analyser',
  'cal-calage-bandeau-import',
  'cal-calage-calque',
  'cal-calage-champ',
  'cal-calage-champ-calque',
  'cal-calage-convertir',
  'cal-calage-distance-plan',
  'cal-calage-echelle',
  'cal-calage-enregistrer',
  'cal-calage-erreur',
  'cal-calage-erreur-calque',
  'cal-calage-erreur-fichier',
  'cal-calage-facteur',
  'cal-calage-fichier',
  'cal-calage-import',
  'cal-calage-message',
  'cal-calage-motif-echelle',
  'cal-calage-plan',
  'cal-calage-proposer',
  'cal-calage-sans-plan',
  'cal-calage-sommets',
  'cal-calage-source',
  'cal-calage-unite',
  // ── RaccourcisAtelier.jsx ──
  'cal-raccourci',
  'cal-raccourci-aide',
  'cal-raccourcis',
  'cal-raccourcis-aide',
  'cal-raccourcis-bouton',
  // ── RemplissageProuve.jsx ──
  'cal-remplissage',
  'cal-remplissage-appliquer',
  'cal-remplissage-avancement',
  'cal-remplissage-lancer',
  'cal-remplissage-methode',
  'cal-remplissage-refus',
  'cal-remplissage-regime',
  'cal-remplissage-sans-preuve',
  // ── SaisiePente.jsx ──
  'cal-pente',
  'cal-pente-champ',
  'cal-pente-enregistrer',
  'cal-pente-equivalent',
  'cal-pente-lidar',
  'cal-pente-lidar-accepter',
  'cal-pente-lidar-decalage',
  'cal-pente-lidar-jeter',
  'cal-pente-lidar-mention',
  'cal-pente-lidar-message',
  'cal-pente-lidar-source',
  'cal-pente-lidar-suggerer',
  'cal-pente-lidar-suggestion',
  'cal-pente-message',
  'cal-pente-mode',
  'cal-pente-source',
  'cal-pente-valeur',
  // ── SunDiagram.jsx ──
  'cal-sundiagram-obstruction',
  'cal-sundiagram-soleil-courant',
  // ── VariantesCompare.jsx ──
  'cal-cote-a-cote',
  'cal-cote-a-cote-vide',
  'cal-introuvables',
  'cal-p50',
  'cal-pr',
  'cal-retenue',
  'cal-tableau-variantes',
  'cal-variante-confirmer',
  'cal-variante-dupliquer',
  'cal-variante-formulaire',
  'cal-variante-nom',
  'cal-variante-nom-erreur',
  'cal-variante-nouvelle',
  // ── atelier/OngletCoupeRangees.jsx ──
  'cal-coupe-alerte-ombrage',
  'cal-coupe-chargement',
  'cal-coupe-cote-pas',
  'cal-coupe-hauteur',
  'cal-coupe-inclinaison',
  'cal-coupe-longueur-ombre',
  'cal-coupe-non-calculee',
  'cal-coupe-ombre',
  'cal-coupe-panel',
  'cal-coupe-pas',
  'cal-coupe-rangee',
  'cal-coupe-rayon-solaire',
  'cal-coupe-rayon-solaire-valeur',
  'cal-coupe-sol',
  'cal-coupe-svg',
  'cal-coupe-vide',
  // ── atelier/PanneauActivite.jsx ──
  'cal-activite',
  'cal-activite-erreur',
  'cal-activite-note-ajouter',
  'cal-activite-note-texte',
  // ── atelier/PanneauPertes.jsx ──
  'cal-pertes--mois',
  'cal-pertes-bandeau',
  'cal-pertes-champ',
  'cal-pertes-chargement',
  'cal-pertes-enregistrer',
  'cal-pertes-erreur',
  'cal-pertes-mention',
  'cal-pertes-message',
  'cal-pertes-motif-non-simulable',
  'cal-pertes-panel',
  'cal-pertes-poste',
  'cal-pertes-source',
  'cal-pertes-total',
  // ── atelier/PanneauReleve.jsx ──
  'cal-releve-ajouter-chaine',
  'cal-releve-bandeau',
  'cal-releve-chaine',
  'cal-releve-chaine--ajouter-cote',
  'cal-releve-chaine--cote',
  'cal-releve-chaine--cote--retirer',
  'cal-releve-chaine--retirer',
  'cal-releve-champ-notes',
  'cal-releve-envoyer',
  'cal-releve-erreur-chaine',
  'cal-releve-erreur-precision_azimut_deg',
  'cal-releve-message',
  'cal-releve-panel',
  'cal-releve-resultat',
  'cal-releve-resultat-chaine',
  'cal-releve-resultat-chaine--a-confirmer',
  'cal-releve-resultat-chaine--fermee',
  'cal-releve-resultat-chaine--manquante',
  'cal-releve-resultat-chaine--rupture',
  // ── atelier/PanneauSeries.jsx ──
  'cal-series',
  'cal-series-depot',
  'cal-series-depot-bandeau',
  'cal-series-depot-envoyer',
  'cal-series-depot-fichier',
  'cal-series-depot-fournisseur',
  'cal-series-depot-motif-fichier',
  'cal-series-depot-motif-fournisseur',
  'cal-series-depot-provenance',
  'cal-series-fichier',
  'cal-series-ligne',
  'cal-series-motif',
  'cal-series-rappel',
  'cal-series-telecharger',
  // ── atelier/PanneauVersions.jsx ──
  'cal-versions',
  'cal-versions-annuler',
  'cal-versions-confirmer',
  'cal-versions-courante',
  'cal-versions-erreur',
  'cal-versions-ligne',
  'cal-versions-rappel',
  'cal-versions-restaurer',
  // ── atelier/PoseReelle.jsx ── (CALX367)
  'cal-pose-bandeau',
  'cal-pose-champ-releve_le',
  'cal-pose-chargement',
  'cal-pose-creer-version',
  'cal-pose-ecart',
  'cal-pose-enregistrer',
  'cal-pose-erreur-creer_version',
  'cal-pose-erreur-detail',
  'cal-pose-erreur-lecture',
  'cal-pose-erreur-modules',
  'cal-pose-erreur-pan',
  'cal-pose-erreur-releve_le',
  'cal-pose-grille',
  'cal-pose-ligne',
  'cal-pose-mention',
  'cal-pose-message',
  'cal-pose-modules',
  'cal-pose-position',
  'cal-pose-prevu',
  'cal-pose-reelle',
  'cal-pose-source',
  'cal-pose-version',
  'cal-pose-vide',
  // ── atelier/Rail.jsx ──
  'cal-onglet',
  'cal-onglet-erreur',
  'cal-onglet-panneau',
  'cal-rail-onglets',
  // ── atelier/RepriseVisite.jsx ── (CALX365)
  'cal-reprise-bandeau',
  'cal-reprise-bouton',
  'cal-reprise-chargement',
  'cal-reprise-erreur',
  'cal-reprise-erreur-lecture',
  'cal-reprise-mesure',
  'cal-reprise-mesures',
  'cal-reprise-mesures-vide',
  'cal-reprise-photo',
  'cal-reprise-photos',
  'cal-reprise-photos-vide',
  'cal-reprise-raison',
  'cal-reprise-refus-bandeau',
  'cal-reprise-vide',
  'cal-reprise-visite',
  'cal-reprise-visite-entete',
  // ── atelier/RetourAtelier.jsx ──
  'cal-retour-atelier',
  'cal-retour-atelier-lien',
  'cal-retour-atelier-onglet',
  // ── documents/PanneauDocuments.jsx ──
  'cal-doc-bouton',
  'cal-doc-bouton-export-layout',
  'cal-doc-bouton-import-layout',
  'cal-doc-bouton-joindre-ombrage',
  'cal-doc-bouton-joindre-pertes',
  'cal-doc-conception',
  'cal-doc-conception-confirmation',
  'cal-doc-empreinte',
  'cal-doc-erreur',
  'cal-doc-erreurs',
  'cal-doc-fichier-import-layout',
  'cal-doc-image',
  'cal-doc-images',
  'cal-doc-images-confirmation',
  'cal-doc-images-confirmation-pertes',
  'cal-doc-images-jointes',
  'cal-doc-images-outil-absent',
  'cal-doc-manque',
  'cal-doc-manque-item',
  'cal-doc-manque-lien',
  'cal-doc-motif',
  'cal-doc-panneau',
  'cal-doc-sortie',
  'cal-doc-version',
  'cal-doc-version-telecharger',
  'cal-doc-versions',
  'cal-doc-vide',
  // ── equipements/FichesIncompletes.jsx ──
  'cal-fiche-manquant',
  'cal-fiche-requis',
  'cal-fiches',
  'cal-fiches-complet',
  'cal-fiches-erreur',
  'cal-fiches-incompletes',
  'cal-fiches-lien',
  'cal-fiches-sans-devis',
  // ── pompage/PompagePanel.jsx ──
  'cal-pompage-autonomie',
  'cal-pompage-avertissements',
  'cal-pompage-bandeau',
  'cal-pompage-calculer',
  'cal-pompage-champ',
  'cal-pompage-courbe',
  'cal-pompage-courbe-absente',
  'cal-pompage-debit',
  'cal-pompage-erreur',
  'cal-pompage-form',
  'cal-pompage-groupe',
  'cal-pompage-hmt',
  'cal-pompage-irradiation',
  'cal-pompage-mois',
  'cal-pompage-panel',
  'cal-pompage-point',
  'cal-pompage-pompe',
  'cal-pompage-refus',
  'cal-pompage-variateur',
  'cal-pompage-volumes',
  'cal-pompage-volumes-absents',
  // ── production/TapisHoraire.jsx ──
  'cal-tapis',
  'cal-tapis-grandeur',
  'cal-tapis-grille',
  'cal-tapis-jour',
  'cal-tapis-journee-type',
  'cal-tapis-legende',
  'cal-tapis-mois',
  'cal-tapis-pic',
  'cal-tapis-tronquee',
  'cal-tapis-vide',
]

function readDoc() {
  return readFileSync(DOC_PATH, 'utf8')
}

// Extrait les lignes de tableau markdown `| \`cal-x\` | sémantique |`.
function parseHookRows(doc) {
  const rows = new Map()
  const lineRe = /^\|\s*`(cal-[a-zA-Z0-9_-]*)`\s*\|\s*(.+?)\s*\|\s*$/gm
  let m
  while ((m = lineRe.exec(doc)) !== null) {
    rows.set(m[1], m[2])
  }
  return rows
}

test('E2E_HOOKS.md publie chaque hook normatif avec une sémantique', () => {
  const rows = parseHookRows(readDoc())
  for (const hook of ALL_HOOKS) {
    assert.ok(rows.has(hook), `hook manquant dans E2E_HOOKS.md : ${hook}`)
    assert.ok(rows.get(hook).length > 0, `${hook} : sémantique vide`)
  }
})

test("E2E_HOOKS.md ne documente aucun hook hors de la liste normative (pas de dérive silencieuse)", () => {
  const rows = parseHookRows(readDoc())
  const documented = [...rows.keys()].sort()
  assert.deepEqual(documented, [...new Set(ALL_HOOKS)].sort())
})

// ── Garde anti-invention ─────────────────────────────────────────────────
// Parcourt features/calepinage/** (ce dossier), ignore les fichiers de test et
// ce contrat lui-même. Les interpolations `${...}` sont retirées AVANT analyse
// (un hook dynamique se réduit à sa base fixe, séparateurs conservés) — la
// MÊME normalisation que celle qui a produit ALL_HOOKS.
function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    const st = statSync(full)
    if (st.isDirectory()) {
      walk(full, out)
    } else if (/\.(jsx?|mjs)$/.test(entry) && !/\.test\.jsx$|\.test\.mjs$/.test(entry) && entry !== 'e2eHooks.test.mjs') {
      out.push(full)
    }
  }
  return out
}

test('aucun data-testid="cal-*" hors contrat dans features/calepinage/** (garde anti-invention)', () => {
  const allowed = new Set(ALL_HOOKS)
  const offenders = []
  for (const file of walk(FEATURE_ROOT)) {
    let src = readFileSync(file, 'utf8')
    src = src.replace(/\$\{[^}]*\}/g, '')
    const re = /data-testid=\{?[`'"]([^`'"]*)[`'"]\}?/g
    let m
    while ((m = re.exec(src)) !== null) {
      const raw = m[1].trim()
      if (!raw.startsWith('cal-')) continue
      const base = raw.replace(/-+$/, '')
      if (!base || base === 'cal') continue
      if (!allowed.has(base)) {
        offenders.push(`${base} (${relative(FEATURE_ROOT, file).split(sep).join('/')})`)
      }
    }
  }
  assert.deepEqual(offenders, [], `hooks hors contrat : ${offenders.join(', ')}`)
})
