/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (donnees + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (meme contrat que
   router/moduleRoutes.jsx). */
import { lazy } from 'react'
import {
  FolderOpen, FileSignature, ShieldCheck, Tags, ScanLine, Trash2, ClipboardList,
  Files, Vault,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   UX45-UX47 - Config du module GED (base + avance).
   ----------------------------------------------------------------------------
   S'auto-enregistre via le glob des module.config du dossier features - SANS
   toucher au routeur, a la Sidebar ni a routes.meta. VX153 avait scinde ce
   fichier ("DOCUMENTS - AVANCE") de la section DOCUMENTS codee en dur de
   Sidebar.jsx (qui ne portait que /ged, DocumentsPage) faute de config pour
   l'accueillir. ODY22 unifie : `key` reprend TEL QUEL la cle backend `ged`
   (`apps/ged/apps.py` - avant : `ged_advanced` + un alias dans
   scripts/check_modules.py, desormais inutile mais laisse en place) et
   `nav.items` porte AUSSI /ged en tete - ce module est la porte COMPLETE de
   l'app GED, prete a etre consommee par ODY4 quand la section en dur de
   Sidebar.jsx sera retiree (les deux lanes se rejoignent au meme lot, pas
   besoin d'attendre). /ged reste enregistree dans router/index.jsx
   (DocumentsPage) : pas d'entree `routes` ici pour ce chemin, sous peine de le
   declarer deux fois dans l'arbre du routeur - seuls nav/titles/sectionLabels
   pointent dessus (meme patron que /messages dans
   features/messaging/module.config.jsx). Les 6 ecrans avances restent gates
   responsable/admin ; /ged reste ouvert a tous les roles (identique a la
   route reelle : authLoader seul, aucune restriction de role).

   XGED12 - Ecran "Numeriser" (capture mobile photo -> PDF multi-pages classe
   en GED, cf. frontend/src/features/ged/NumeriserPage.jsx). Meme gating
   responsable/admin que le televerser existant (l'action serveur
   assembler-photos partage la meme permission que televerser/scan-lot).
   ========================================================================== */

const ApprobationPage = lazy(() => import('./advanced/ApprobationPage.jsx'))
const RetentionPage = lazy(() => import('./advanced/RetentionPage.jsx'))
const TagsPage = lazy(() => import('./advanced/TagsPage.jsx'))
const NumeriserPage = lazy(() => import('./NumeriserPage.jsx'))
const CorbeillePage = lazy(() => import('./advanced/CorbeillePage.jsx'))
// WIR164 — checklist de pièces (XGED8), validation OCR (XGED13), tampons
// société (XGED16) : groupe (a) monté côté backend sans écran jusqu'ici.
const ChecklistPage = lazy(() => import('./advanced/ChecklistPage.jsx'))
// PACT131 — coffres-forts documentaires (GED8), monté côté backend sans
// écran jusqu'ici.
const CoffresPage = lazy(() => import('./advanced/CoffresPage.jsx'))

const ROLES = ['responsable', 'admin']
const TOUS = ['normal', 'responsable', 'admin']

export default {
  key: 'ged',
  order: 80,
  nav: {
    label: 'DOCUMENTS',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Files),
    accent: 'lune', // VX8 — documentaire = accent lune (dérivé)
    items: [
      // ODY22 — /ged (DocumentsPage) déjà routé ailleurs (router/index.jsx) :
      // AUCUNE entrée `routes` correspondante ici (voir note d'en-tête).
      { to: '/ged', label: 'Documents (GED)', icon: <FolderOpen size={17} strokeWidth={1.75} aria-hidden="true" />, roles: TOUS },
      { to: '/ged/numeriser', label: 'Numériser', icon: <ScanLine size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ged/checklist', label: 'Checklist & tampons', icon: <ClipboardList size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ged/approbation', label: 'Approbation & signature', icon: <FileSignature size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ged/retention', label: 'Rétention & archivage', icon: <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ged/tags', label: 'Tags & liens', icon: <Tags size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ged/corbeille', label: 'Corbeille', icon: <Trash2 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ged/coffres', label: 'Coffres-forts', icon: <Vault size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  titles: [
    ['/ged/numeriser', 'Numériser'],
    ['/ged/checklist', 'Checklist & tampons'],
    ['/ged/approbation', 'Approbation & signature'],
    ['/ged/retention', 'Rétention & archivage'],
    ['/ged/tags', 'Tags & liens'],
    ['/ged/corbeille', 'Corbeille'],
    ['/ged/coffres', 'Coffres-forts'],
    ['/ged', 'Documents (GED)'],
  ],
  sectionLabels: { ged: 'Documents (GED)' },
  routes: [
    { path: '/ged/numeriser', component: NumeriserPage, roles: ROLES },
    { path: '/ged/checklist', component: ChecklistPage, roles: ROLES },
    { path: '/ged/approbation', component: ApprobationPage, roles: ROLES },
    { path: '/ged/retention', component: RetentionPage, roles: ROLES },
    { path: '/ged/tags', component: TagsPage, roles: ROLES },
    { path: '/ged/corbeille', component: CorbeillePage, roles: ROLES },
    { path: '/ged/coffres', component: CoffresPage, roles: ROLES },
  ],
}
