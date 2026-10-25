import RetourAtelier from './atelier/RetourAtelier'
import useSurfacePose from './useSurfacePose'
import ActionsSurfacePose from './ActionsSurfacePose'
import TracePlanPose from './TracePlanPose'
import {
  nombre, pasMesure, tauxOccupation, contourTerrain, KIND_SOL, SAISIE_MODULE_VIDE,
} from './surfacePose'
import { demandeMoteur, vueDuChamp } from './ModeTerrain.helpers'

/* ============================================================================
   CAL89 — LE MODE TERRAIN : UNE CENTRALE AU SOL DANS L'ATELIER.
   ----------------------------------------------------------------------------
   Constat : tout le tracé de l'atelier suppose un TOIT (type de toit
   obligatoire, `ToitureDesign.jsx`) ; aucun mode terrain n'existe. Cet écran
   ouvre le mode terrain SANS toucher une ligne du chemin toiture : il écrit
   dans le MÊME document (`roof_layout`, clé additive `poseSurfaces`, contrat
   `roof_layout_v2.schema.json`) et parle à la MÊME porte moteur
   (`POST /calepinage/moteur/pose/`, contrat `pose.json`).

   CE QUI EST SAISI, ET CE QUI VIENT DU MOTEUR — la frontière ne bouge jamais :
     * SAISI : les dimensions du terrain, sa pente, l'orientation des rangées,
       l'inclinaison des tables, le module, et l'allée entre rangées quand elle
       est imposée (`parametres.allee_m`, le paramètre du moteur lui-même).
     * RENDU PAR LE MOTEUR : les tables posées, le compte de modules, et le PAS
       INTER-RANGÉES réellement appliqué — MESURÉ sur les rangées renvoyées
       (`plans[].rangees[].y0` consécutifs). Il n'existe AUCUNE seconde formule
       de pas dans cet écran : c'est la règle de CAL88, qui fait vivre la
       physique anti-ombrage dans le moteur (`core/calepinage/surfaces/sol.py`)
       et nulle part ailleurs. Moins de deux rangées ⇒ pas non mesurable ⇒ on
       affiche « — » et on le DIT.

   LE TAUX D'OCCUPATION DU SOL (GCR) EST UNE SORTIE, jamais une saisie ni un
   objectif : somme des emprises des TABLES RENDUES PAR LE MOTEUR ÷ surface du
   terrain SAISIE. Les deux termes viennent donc du serveur et de la saisie —
   aucun des deux n'est estimé.

   LIMITE CONNUE, DITE PLUTÔT QUE MASQUÉE : le contrat d'échange v1 du moteur ne
   connaît PAS encore le genre de surface « sol » (`core/calepinage/
   serialisation.py` le refuse explicitement, et le test
   `test_le_contrat_v1_refuse_le_sol_explicitement` le fige). Le terrain est
   donc soumis comme une surface de pose HORIZONTALE (`type: "polygone"`,
   `pente_deg: 0`), et le pas affiché est celui que le moteur a APPLIQUÉ. Le
   jour où la porte accepte `sol`, seul le `type` envoyé change ici.
   ========================================================================== */

/** ACAL75 — la mention exacte du champ « Pente du terrain » (jamais reformulée). */
export const MENTION_PENTE_NON_PRISE_EN_COMPTE
  = 'non prise en compte par le calcul — terrain supposé plat'

const SAISIE_VIDE = {
  repere: 'TERRAIN',
  label: 'Champ au sol',
  largeurM: '',
  profondeurM: '',
  penteTerrainDeg: '',
  rowAzimuthDeg: '',
  tiltDeg: '',
  ...SAISIE_MODULE_VIDE,
}

const CHAMPS = [
  ['largeurM', 'Largeur du terrain (m)'],
  ['profondeurM', 'Profondeur du terrain (m)'],
  ['penteTerrainDeg', 'Pente du terrain (°)'],
  ['rowAzimuthDeg', 'Orientation des rangées (°, 180 = sud)'],
  ['tiltDeg', 'Inclinaison des tables (°)'],
  ['moduleLongM', 'Module — grand côté (m)'],
  ['moduleCourtM', 'Module — petit côté (m)'],
  ['puissanceWc', 'Module — puissance (Wc)'],
  ['modulesParTable', 'Modules par table'],
  ['alleeM', 'Allée imposée entre rangées (m) — vide = politique du moteur'],
]

/** ENF19 — les `data-testid` du tracé du champ (le tracé lui-même est `TracePlanPose`). */
const IDS_TRACE = {
  svg: 'cal-terrain-svg',
  contour: 'cal-terrain-contour',
  rangee: 'cal-terrain-rangee',
  table: 'cal-terrain-table',
  cote: 'cal-terrain-cote',
  traitPas: 'cal-terrain-trait-pas',
  cotePas: 'cal-terrain-cote-pas',
  emprise: 'cal-terrain-emprise',
}

function auDixieme(v) {
  return v === null || v === undefined ? '—' : Math.round(v * 10) / 10
}

/** ACAL345 — ce qui distingue cet écran dans `useSurfacePose` (genre, repère, placeur, libellés). */
const POSE_TERRAIN = {
  kind: KIND_SOL,
  repereDefaut: 'TERRAIN',
  saisieVide: SAISIE_VIDE,
  nomPlaceur: 'construireChampPose',
  libelles: {
    enregistre: 'Champ au sol enregistré dans la conception.',
    nonEnregistre: 'Le champ au sol n’a pas pu être enregistré.',
    supprime: 'Surface supprimée de la conception.',
    nonSupprime: 'La surface n’a pas pu être supprimée.',
    echecPose: 'Le moteur n’a pas pu poser ce champ au sol.',
  },
}

export default function ModeTerrain({ calepinageId: idPropose = null, persister = true, documentVivant = null }) {
  // ACAL345 — l'état d'écran (document, placeur CALX50, relecture, liste,
  // enregistrement/suppression PAR id) vient de `useSurfacePose`, l'UNIQUE
  // copie partagée entre le terrain et l'ombrière.
  const pose = useSurfacePose({ idPropose, persister, documentVivant, ...POSE_TERRAIN })
  const { calepinageId, saisie, reponse, placeur, placeurAbsent, plan, majChamp } = pose

  const calculer = () => pose.poser(
    demandeMoteur(saisie),
    'Dimensions du terrain et du module incomplètes : rien n’est '
      + 'envoyé au moteur, et surtout aucune valeur par défaut inventée.',
  )

  const pas = plan ? (pasMesure(plan.rangees) ?? reponse?._pasRecharge ?? null) : null
  const aire = contourTerrain(saisie.largeurM, saisie.profondeurM)
    ? nombre(saisie.largeurM) * nombre(saisie.profondeurM)
    : null
  const taux = plan ? tauxOccupation(plan.tables, aire) : null

  // CALX50 — le champ PLACÉ par le service, à partir du plan du moteur et des
  // seules grandeurs saisies. Pente absente ⇒ le service le dit dans
  // `nonMesure` ; on n'en suppose aucune à sa place.
  const champ = placeur && plan
    ? placeur.construireChampPose(plan, {
      tiltDeg: nombre(saisie.tiltDeg),
      penteTerrainDeg: nombre(saisie.penteTerrainDeg),
      aireTerrainM2: aire,
    })
    : null
  const vue = vueDuChamp(champ, plan, saisie)

  return (
    <>
      <RetourAtelier calepinageId={calepinageId} />
      <div className="cine-card mt-6 p-6" data-testid="cal-terrain">
        <p className="tech-label rule-brass text-brass-300">Mode terrain — centrale au sol</p>
        <p className="mt-2 text-xs text-lune-faint">
          Les dimensions sont saisies ; les tables, le compte et le pas
          inter-rangées viennent du moteur. Le mode toiture n’est pas touché.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {CHAMPS.map(([cle, label]) => (
            // ACAL75 — la pente du terrain n'entre PAS dans le calcul (la demande
            // part avec `pente_deg: 0`) : le champ est grisé et le dit ; la valeur
            // reste persistée pour le rendu 3D.
            <label
              key={cle}
              className={`block text-sm text-lune-soft${cle === 'penteTerrainDeg' ? ' opacity-60' : ''}`}
            >
              <span className="tech-label text-lune-faint">{label}</span>
              <input
                type="number"
                step="any"
                value={saisie[cle]}
                data-testid={`cal-terrain-${cle}`}
                aria-describedby={cle === 'penteTerrainDeg' ? 'cal-terrain-pente-mention' : undefined}
                onChange={(e) => majChamp(cle, e.target.value)}
                className="mt-1 w-full rounded border border-white/15 bg-transparent px-2 py-1 text-white"
              />
              {cle === 'penteTerrainDeg' && (
                <span id="cal-terrain-pente-mention" className="mt-1 block text-xs text-lune-faint">
                  {MENTION_PENTE_NON_PRISE_EN_COMPTE}
                </span>
              )}
            </label>
          ))}
        </div>

        <ActionsSurfacePose
          pose={pose}
          persister={persister}
          prefixe="cal-terrain"
          onCalculer={calculer}
          libelles={{
            calculer: 'Calculer le champ au sol',
            enregistrer: 'Enregistrer le champ',
            groupe: 'Surfaces au sol enregistrées',
            liste: 'Surfaces enregistrées',
            defaut: 'Champ au sol',
            nouvelle: 'Nouvelle surface',
          }}
        />

        {plan && (
          <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-white/10 pt-4 sm:grid-cols-4">
            <div data-testid="cal-terrain-modules">
              <dd className="fig text-lg text-white">{plan.modules ?? '—'}</dd>
              <dt className="tech-label text-lune-faint">Modules posés (moteur)</dt>
            </div>
            <div data-testid="cal-terrain-tables">
              <dd className="fig text-lg text-white">{(plan.tables ?? []).length}</dd>
              <dt className="tech-label text-lune-faint">Tables posées</dt>
            </div>
            <div data-testid="cal-terrain-pas">
              <dd className="fig text-lg text-white">
                {pas === null ? '—' : `${auDixieme(pas)} m`}
              </dd>
              <dt className="tech-label text-lune-faint">
                {pas === null ? 'Pas non mesurable (moins de 2 rangées)' : 'Pas inter-rangées (mesuré sur le plan)'}
              </dt>
            </div>
            <div data-testid="cal-terrain-taux">
              <dd className="fig text-lg text-white">
                {taux === null ? '—' : `${Math.round(taux * 1000) / 10} %`}
              </dd>
              <dt className="tech-label text-lune-faint">
                {taux === null
                  ? 'Taux d’occupation non calculable'
                  : 'Taux d’occupation du sol (sortie)'}
              </dt>
            </div>
          </dl>
        )}

        {/* CALX50 — LE CHAMP DESSINÉ : le plan du moteur, mis en page. */}
        {(plan || placeurAbsent) && (
          <section
            className="mt-5 border-t border-white/10 pt-4"
            data-testid="cal-terrain-vue"
            aria-label="Champ au sol dessiné"
          >
            <p className="tech-label text-lune-faint">
              Champ au sol dessiné — rangées, tables et pas rendus par le moteur
            </p>

            {placeurAbsent && (
              <p className="mt-2 text-sm text-alert-300" data-testid="cal-terrain-vue-indisponible">
                Le tracé du champ n’a pas pu être chargé : les chiffres du moteur
                restent affichés ci-dessus, et rien n’est dessiné à leur place.
              </p>
            )}

            {vue && <TracePlanPose vue={vue} champ={champ} ids={IDS_TRACE} nom="table" titre="Champ au sol" />}

            {champ && champ.nonMesure.length > 0 && (
              <ul
                className="mt-2 list-disc pl-5 text-xs text-lune-faint"
                data-testid="cal-terrain-nonmesure"
              >
                {champ.nonMesure.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </>
  )
}
