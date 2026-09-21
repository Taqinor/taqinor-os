/* ============================================================================
   VEILLE AO — constantes et logique PURE partagées entre les écrans du module.
   ----------------------------------------------------------------------------
   Ce fichier existe pour une raison mécanique, pas esthétique : `eslint`
   (`react-refresh/only-export-components`) refuse qu'un fichier d'écran exporte
   autre chose que des composants — un module qui exporte À LA FOIS un écran et
   une constante casse le fast-refresh. Ces valeurs étaient d'abord exportées
   depuis `AvisList.jsx` / `AcheteursCibles.jsx` / `SanteVeille.jsx` ; elles
   vivent ici pour que chaque écran ne publie plus QUE son composant.

   Elles sont DÉPLACÉES À L'IDENTIQUE — aucune valeur, aucun seuil, aucun
   libellé n'a été retouché au passage.
   ========================================================================== */
import { statusPill } from '../../ui/module'

/* VAO33/VAO34 — miroir de `AvisMarche.Statut` côté serveur
   (`nouveau → retenu|ignore ; retenu → converti ; tout → expire`, VAO14).
   Le libellé affiché ne vient JAMAIS d'une chaîne brute du serveur. */
export const STATUT_AVIS = {
  nouveau: { label: 'Nouveau', tone: 'info' },
  retenu: { label: 'Retenu', tone: 'success' },
  ignore: { label: 'Ignoré', tone: 'neutral' },
  converti: { label: 'Converti', tone: 'success' },
  expire: { label: 'Expiré', tone: 'danger' },
}
export const StatutAvis = statusPill(STATUT_AVIS)

// VAO33 (Done=) — « la pastille compte juste (test) » : logique PURE, testable
// hors React. Compte les avis au statut `nouveau` dont l'horodatage de
// création (`cree_le`, convention déjà en vigueur — cf. `ContratDetail.jsx`
// `v.cree_le`) tombe depuis minuit HIER (jamais un « depuis 24 h » glissant :
// « depuis hier » se lit au jour calendaire, comme `daysUntil`/`urgency.js`).
export function avisNouveauxDepuisHier(rows = [], now = new Date()) {
  const base = now instanceof Date ? now : new Date(now)
  if (Number.isNaN(base.getTime())) return 0
  const hier = new Date(base.getFullYear(), base.getMonth(), base.getDate() - 1)
  return rows.filter((r) => {
    if (r?.statut !== 'nouveau' || !r?.cree_le) return false
    const cree = new Date(r.cree_le)
    return !Number.isNaN(cree.getTime()) && cree >= hier
  }).length
}

// VAO29 — les catégories du carnet d'amorçage (jamais un nom d'organisme).
export const TYPES_ACHETEUR = [
  { value: 'fondation', label: 'Fondation' },
  { value: 'universite_privee', label: 'Université privée' },
  { value: 'clinique', label: 'Clinique' },
  { value: 'groupe_hotelier', label: 'Groupe hôtelier' },
  { value: 'industriel', label: 'Industriel' },
  { value: 'cooperative_agricole', label: 'Coopérative agricole' },
  { value: 'promoteur', label: 'Promoteur' },
  { value: 'collectivite', label: 'Collectivité' },
]

// VAO37 (Done=) — logique PURE, testable hors React : « l'âge de la dernière
// collecte est visible sans clic » exige un libellé, pas une date brute.
export function ageLabel(iso, now = new Date()) {
  if (!iso) return null
  const d = new Date(iso)
  const base = now instanceof Date ? now : new Date(now)
  if (Number.isNaN(d.getTime()) || Number.isNaN(base.getTime())) return null
  const ms = base.getTime() - d.getTime()
  if (ms < 0) return 'à l’instant'
  const heures = Math.floor(ms / (1000 * 60 * 60))
  if (heures < 1) return 'à l’instant'
  if (heures < 24) return `il y a ${heures} h`
  const jours = Math.floor(heures / 24)
  return `il y a ${jours} j`
}
