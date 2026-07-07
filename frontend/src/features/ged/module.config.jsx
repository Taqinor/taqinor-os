/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (donnees + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (meme contrat que
   router/moduleRoutes.jsx). */
import { lazy } from 'react'
import { FileSignature, ShieldCheck, Tags, ScanLine } from 'lucide-react'

/* ============================================================================
   UX45-UX47 - Config du module GED avancee (approbation, retention, tags).
   ----------------------------------------------------------------------------
   S'auto-enregistre via le glob des module.config du dossier features - SANS
   toucher au routeur, a la Sidebar ni a routes.meta. Le navigateur de base
   (/ged, DocumentsPage) reste intact : ce module N'AJOUTE que les ecrans
   avances sous une section GESTION DOCUMENTAIRE distincte de la section
   DOCUMENTS existante. On NE pose PAS de sectionLabels (le 1er segment "ged"
   est deja pris). Tout est gate responsable/admin.

   XGED12 - Ecran "Numeriser" (capture mobile photo -> PDF multi-pages classe
   en GED, cf. frontend/src/features/ged/NumeriserPage.jsx). Meme gating
   responsable/admin que le televerser existant (l'action serveur
   assembler-photos partage la meme permission que televerser/scan-lot).
   ========================================================================== */

const ApprobationPage = lazy(() => import('./advanced/ApprobationPage.jsx'))
const RetentionPage = lazy(() => import('./advanced/RetentionPage.jsx'))
const TagsPage = lazy(() => import('./advanced/TagsPage.jsx'))
const NumeriserPage = lazy(() => import('./NumeriserPage.jsx'))

const ROLES = ['responsable', 'admin']

export default {
  key: 'ged_advanced',
  order: 80,
  nav: {
    label: 'GESTION DOCUMENTAIRE',
    items: [
      { to: '/ged/numeriser', label: 'Numériser', icon: <ScanLine size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ged/approbation', label: 'Approbation & signature', icon: <FileSignature size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ged/retention', label: 'Rétention & archivage', icon: <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ged/tags', label: 'Tags & liens', icon: <Tags size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  titles: [
    ['/ged/numeriser', 'Numériser'],
    ['/ged/approbation', 'Approbation & signature'],
    ['/ged/retention', 'Rétention & archivage'],
    ['/ged/tags', 'Tags & liens'],
  ],
  sectionLabels: {},
  routes: [
    { path: '/ged/numeriser', component: NumeriserPage, roles: ROLES },
    { path: '/ged/approbation', component: ApprobationPage, roles: ROLES },
    { path: '/ged/retention', component: RetentionPage, roles: ROLES },
    { path: '/ged/tags', component: TagsPage, roles: ROLES },
  ],
}
