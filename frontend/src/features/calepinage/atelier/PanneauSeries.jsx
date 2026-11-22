import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Download, Upload } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { formatDate, formatNumber } from '../../../lib/format'
import { Button, Card, Input, Label } from '../../../ui'
import { downloadBlob } from '../../../utils/downloadBlob'
import { OPTIONS_TELECHARGEMENT, erreurDeTelechargement } from '../documents/telechargement'
import { SelecteurFichier } from '../reglages/ReglagesGabarits'
import { COLONNES_CSV, COLONNES_D_OFFICE, colonnesAEnvoyer } from './colonnesCsv'

/* ============================================================================
   CALX6 — LE PANNEAU « SÉRIES » : les trois exports de la simulation.
   ----------------------------------------------------------------------------
   CONSTAT. La porte `calepinages/<pk>/export-csv/?quoi=…` est servie depuis
   CAL144 (`views/export_csv.py`) et `services/export_csv.py::EXPORTS` offre
   les trois sorties `horaire | mensuel | ombrage` : AUCUN écran ne les
   appelait. Un export construit et injoignable n'existe pas.

   CE PANNEAU NE CALCULE RIEN. Il ne relit ni la série, ni les agrégats : il
   demande le FICHIER au serveur et le remet au navigateur. La série horaire
   elle-même est écrite par la chaîne de pertes (CALX193) et n'est PAS
   recopiée par `GET resultat/` (D-CALX 14, volume) — il n'existe donc aucune
   lecture bon marché qui dirait d'avance « la série est là ».

   POURQUOI LE MOTIF ARRIVE APRÈS LE CLIC, ET PAS AVANT. Sonder les trois
   exports au montage voudrait dire télécharger trois fichiers (dont un de
   8 760 lignes) à chaque ouverture de l'onglet, pour n'en garder que le code
   de statut. Le bouton part donc actif ; au premier refus, il se DÉSACTIVE et
   porte SOUS lui le motif que le serveur a écrit — jamais une phrase
   fabriquée ici, jamais un « export impossible » générique (règle fondateur :
   l'erreur nomme le champ fautif, `points` / `mensuel` / `shading12x24`).

   ZÉRO CHIFFRE (D-CALX 7). Aucune valeur de production n'est affichée ni
   déduite dans ce panneau : il ne montre que des boutons, des motifs de refus
   et le nom du fichier obtenu.
   ========================================================================== */

/** Les exports servis, dans l'ordre où le panneau les propose. */
const EXPORTS = [
  {
    quoi: 'horaire',
    libelle: 'Série horaire (CSV)',
    aide: "Une ligne par heure : production, irradiance sur le plan et "
      + "température de l'air, précédées de leur provenance.",
  },
  {
    quoi: 'mensuel',
    libelle: 'Agrégat mensuel (CSV)',
    aide: 'Les douze mois et le total annuel, avec la même provenance.',
  },
  {
    quoi: 'ombrage',
    libelle: 'Matrice d’ombrage 12 × 24 (CSV)',
    aide: "Le facteur d'ombrage de chaque mois pour chacune des vingt-quatre "
      + 'heures, tel qu’il est tracé sur le toit.',
  },
  {
    quoi: 'ombrage_modules',
    libelle: 'Ombrage module par module (CSV)',
    aide: 'Une ligne par panneau avec son accès solaire sur l’année ; le mois '
      + 'et l’heure par panneau ne sont pas calculés.',
  },
]

const REFUS_SANS_MOTIF = (
  "Le serveur a refusé cet export sans en donner le motif : réessayez, puis "
  + 'signalez-le si le refus persiste.'
)

/**
 * Le refus du serveur, tel qu'il l'a écrit : `{champ, motif}` ou `null`.
 *
 * La réponse d'erreur arrive en BLOB (la requête demande `responseType:
 * 'blob'` pour le fichier) : il faut donc la relire en texte avant de la lire
 * en JSON. Une forme inattendue ne fabrique aucun motif — elle rend `null`,
 * et l'appelant affiche la phrase générique ci-dessus en le DISANT.
 */
async function lireRefus(erreur) {
  if (erreur?.code === 'ECONNABORTED') {
    return { champ: '', motif: (await erreurDeTelechargement(erreur, { delai: true }))[0].message, ligne: null }
  }
  let corps = erreur?.response?.data
  if (corps && typeof corps.text === 'function') {
    try { corps = JSON.parse(await corps.text()) } catch { return null }
  } else if (typeof corps === 'string') {
    try { corps = JSON.parse(corps) } catch { return null }
  }
  if (!corps || typeof corps !== 'object') return null
  // CALX62 — `ligne` accompagne un refus de fichier : elle dit OÙ ouvrir le
  // CSV. Ce n'est pas un champ fautif, elle ne peut donc pas en tenir lieu.
  const ligne = Number.isFinite(corps.ligne) ? corps.ligne : null
  for (const [champ, valeur] of Object.entries(corps)) {
    if (champ === 'exports_disponibles' || champ === 'ligne') continue
    const motif = Array.isArray(valeur) ? valeur[0] : valeur
    if (typeof motif === 'string' && motif.trim()) {
      return { champ, motif, ligne }
    }
  }
  return null
}

/* ============================================================================
   CALX62 — LE DÉPÔT D'UNE SÉRIE MÉTÉO HORAIRE DE LA SOCIÉTÉ.
   ----------------------------------------------------------------------------
   Deux champs, et les deux sont obligatoires : le FICHIER (CSV à colonnes
   nommées, `horodatage` avec fuseau explicite et `gi_w_m2`) et le
   FOURNISSEUR, SAISI — une série météo dont la provenance n'est pas écrite
   devient un chiffre sans origine dès le lendemain, et l'écran n'en invente
   aucune.

   Le serveur est le seul juge du fichier : l'écran ne lit pas le CSV, ne
   compte pas ses lignes et ne devine aucune colonne. Un refus s'affiche SOUS
   le champ qu'il nomme (`fichier` ou `fournisseur` pour le formulaire, sinon
   la COLONNE du CSV), avec la ligne du fichier quand le serveur la donne.
   ========================================================================== */
const CHAMPS_DU_FORMULAIRE = new Set(['fichier', 'fournisseur'])

export default function PanneauSeries({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  // Par export : `{ etat: 'encours' | 'refus' | 'ok', champ, motif, fichier }`.
  const [sorties, setSorties] = useState({})
  // ACAL753 — colonnes cochées de la série horaire (non mémorisées).
  const [cochees, setCochees] = useState(() => new Set(COLONNES_D_OFFICE))
  // ACAL755 — pas de temps de la série horaire : `horaire` (défaut) ou `jour`.
  const [pas, setPas] = useState('horaire')
  const basculer = (nom) => setCochees((avant) => {
    const apres = new Set(avant)
    if (apres.has(nom)) apres.delete(nom)
    else apres.add(nom)
    return apres
  })

  // ACAL147 — le fichier météo RETENU par la simulation : `undefined` tant
  // qu'on lit, `null` = PVGIS, sinon l'objet servi par `GET meteo-fichier/`,
  // `false` si la lecture a échoué (on ne fabrique alors aucune source).
  const [retenu, setRetenu] = useState(undefined)

  const lireRetenu = useCallback(() => Promise.resolve(
    calepinageApi.calepinages.meteoFichier(calepinageId))
    .then((res) => setRetenu(res?.data ?? null))
    .catch(() => setRetenu(false)), [calepinageId])

  useEffect(() => { lireRetenu() }, [lireRetenu])

  const telecharger = useCallback((quoi) => {
    setSorties((precedent) => ({ ...precedent, [quoi]: { etat: 'encours' } }))
    const colonnes = quoi === 'horaire' ? colonnesAEnvoyer(cochees) : null
    const parJour = quoi === 'horaire' && pas === 'jour'
    const appel = parJour
      ? calepinageApi.calepinages.exportCsv(calepinageId, quoi, colonnes, { pas: 'jour', ...OPTIONS_TELECHARGEMENT })
      : calepinageApi.calepinages.exportCsv(calepinageId, quoi, colonnes || null, OPTIONS_TELECHARGEMENT)
    return Promise.resolve(appel)
      .then((res) => {
        const fichier = `calepinage-${calepinageId}-${quoi}.csv`
        downloadBlob(res?.data, fichier)
        setSorties((precedent) => ({
          ...precedent, [quoi]: { etat: 'ok', fichier },
        }))
      })
      .catch(async (erreur) => {
        const refus = await lireRefus(erreur)
        setSorties((precedent) => ({
          ...precedent,
          [quoi]: {
            etat: 'refus',
            champ: refus?.champ || '',
            motif: refus?.motif || REFUS_SANS_MOTIF,
          },
        }))
      })
  }, [calepinageId, cochees, pas])

  return (
    <div className="mt-6" data-testid="cal-series">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Séries</p>
      <p className="mt-2 text-xs text-muted-foreground" data-testid="cal-series-rappel">
        Les trois fichiers sont produits par le serveur à partir de la
        simulation enregistrée. Tant qu’elle n’a pas tourné, l’export est
        refusé avec son motif — aucun fichier de zéros n’est livré à la place.
      </p>

      <div className="mt-3 space-y-2">
        {EXPORTS.map(({ quoi, libelle, aide }) => {
          const sortie = sorties[quoi] || {}
          const refuse = sortie.etat === 'refus'
          return (
            <Card key={quoi} className="p-3" data-testid={`cal-series-ligne-${quoi}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="space-y-0.5">
                  <div className="text-sm text-foreground">{libelle}</div>
                  <div className="text-xs text-muted-foreground">{aide}</div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => telecharger(quoi)}
                  disabled={refuse || sortie.etat === 'encours'}
                  data-testid={`cal-series-telecharger-${quoi}`}
                >
                  <Download className="mr-1 h-4 w-4" aria-hidden="true" />
                  {sortie.etat === 'encours' ? 'Préparation…' : 'Télécharger'}
                </Button>
              </div>

              {quoi === 'horaire' && (
                <div className="mt-2 flex flex-col gap-1">
                  <Label htmlFor="acal755-pas">Pas</Label>
                  <select
                    id="acal755-pas"
                    value={pas}
                    onChange={(e) => setPas(e.target.value)}
                    className="min-h-11 w-full rounded border border-border bg-background px-2 text-sm text-foreground"
                    data-testid="acal755-pas"
                  >
                    <option value="horaire">Pas : heure</option>
                    <option value="jour">Pas : jour</option>
                  </select>
                </div>
              )}

              {quoi === 'horaire' && (
                <fieldset className="mt-2" data-testid="cal-series-colonnes">
                  <legend className="text-xs text-muted-foreground">
                    Colonnes du fichier (la date et l'heure sont toujours là)
                  </legend>
                  <div className="mt-1 grid grid-cols-1 gap-x-4 sm:grid-cols-2">
                    {COLONNES_CSV.map(({ nom, libelle }) => (
                      <label key={nom} className="flex min-h-11 items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={cochees.has(nom)}
                          onChange={() => basculer(nom)}
                          data-testid={`cal-series-colonne-${nom}`}
                        />
                        {libelle}
                      </label>
                    ))}
                  </div>
                </fieldset>
              )}

              {refuse && (
                <p
                  role="alert"
                  className="mt-2 text-sm text-destructive"
                  data-testid={`cal-series-motif-${quoi}`}
                >
                  {sortie.champ ? `${sortie.champ} : ` : ''}{sortie.motif}
                </p>
              )}
              {sortie.etat === 'ok' && (
                <p
                  className="mt-2 text-xs text-muted-foreground"
                  data-testid={`cal-series-fichier-${quoi}`}
                >
                  Fichier téléchargé : {sortie.fichier}
                </p>
              )}
            </Card>
          )
        })}
      </div>

      <SourceMeteo retenu={retenu} calepinageId={calepinageId} onRetire={lireRetenu} />
      <DepotMeteo calepinageId={calepinageId} onDepose={lireRetenu} />
    </div>
  )
}

/** ACAL147 — « Source météo : … » : le fichier retenu avec son nom, son
    fournisseur, sa date et son auteur (tels que servis), ou PVGIS.
    ACAL148 — « Retirer le fichier météo » (avec confirmation) : retour à
    PVGIS tracé au journal par le serveur, la simulation devient périmée. */
function SourceMeteo({ retenu, calepinageId, onRetire }) {
  const peutGerer = useHasPermission('calepinage_gerer')
  const [confirmation, setConfirmation] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const [retrait, setRetrait] = useState(null)
  const [erreur, setErreur] = useState(null)

  let contenu
  if (retenu === undefined) contenu = 'Source météo : lecture en cours…'
  else if (retenu === false) contenu = 'Source météo : indisponible (lecture impossible).'
  else if (retenu === null) contenu = 'Source météo : PVGIS'
  else {
    const details = [
      retenu.fournisseur ? `fournisseur ${retenu.fournisseur}` : null,
      retenu.depose_le
        ? `déposé le ${formatDate(retenu.depose_le)}${retenu.depose_par ? ` par ${retenu.depose_par}` : ''}`
        : null,
    ].filter(Boolean).join(', ')
    contenu = `Source météo : fichier ${retenu.nom || 'sans nom'}${details ? ` (${details})` : ''} — remplace PVGIS`
  }

  const retirer = () => {
    const nom = retenu?.nom || 'sans nom'
    setErreur(null)
    setEnCours(true)
    return Promise.resolve(calepinageApi.calepinages.retirerFichierMeteo(calepinageId))
      .then(() => {
        setConfirmation(false)
        setRetrait(`Fichier météo retiré : ${nom} — retour à PVGIS`)
        onRetire?.()
      })
      .catch((e) => {
        const detail = e?.response?.data?.detail
        setErreur(typeof detail === 'string' && detail
          ? detail : 'Le retrait a été refusé par le serveur : le fichier est conservé.')
      })
      .finally(() => setEnCours(false))
  }

  return (
    <div className="mt-3">
      <p className="text-sm text-foreground" data-testid="acal147-source-meteo">
        {contenu}
      </p>

      {retenu && peutGerer && !confirmation && (
        <Button
          size="sm"
          variant="outline"
          className="mt-2"
          onClick={() => { setRetrait(null); setConfirmation(true) }}
          data-testid="acal148-retirer"
        >
          Retirer le fichier météo
        </Button>
      )}
      {retenu && confirmation && (
        <div className="mt-2 flex flex-wrap items-center gap-2" data-testid="acal148-confirmation">
          <span className="text-xs text-muted-foreground">
            Le fichier part à la corbeille et la simulation repart sur PVGIS.
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={retirer}
            disabled={enCours}
            data-testid="acal148-confirmer"
          >
            {enCours ? 'Retrait…' : 'Confirmer le retrait'}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setConfirmation(false)}
            disabled={enCours}
            data-testid="acal148-annuler"
          >
            Annuler
          </Button>
        </div>
      )}
      {erreur && (
        <p role="alert" className="mt-2 text-sm text-destructive" data-testid="acal148-erreur">
          {erreur}
        </p>
      )}
      {retrait && (
        <p role="status" className="mt-2 text-xs text-muted-foreground" data-testid="acal148-retrait">
          {retrait}
        </p>
      )}
    </div>
  )
}

function DepotMeteo({ calepinageId, onDepose }) {
  const [fichier, setFichier] = useState(null)
  const [fournisseur, setFournisseur] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [refus, setRefus] = useState(null)
  const [depose, setDepose] = useState(null)

  const deposer = (evenement) => {
    evenement.preventDefault()
    setRefus(null)
    setDepose(null)
    setEnvoi(true)
    const corps = new FormData()
    if (fichier) corps.append('fichier', fichier)
    corps.append('fournisseur', fournisseur)
    return Promise.resolve(
      calepinageApi.calepinages.deposerMeteoFichier(calepinageId, corps))
      .then((res) => {
        setDepose(res?.data || {})
        onDepose?.()
      })
      .catch(async (erreur) => {
        setRefus(await lireRefus(erreur) || {
          champ: 'fichier', motif: REFUS_SANS_MOTIF, ligne: null,
        })
      })
      .finally(() => setEnvoi(false))
  }

  const refusDe = (champ) => (refus && refus.champ === champ ? refus : null)
  // Un refus qui nomme une COLONNE du CSV (et non un champ du formulaire)
  // appartient au fichier : c'est sous lui qu'il doit s'afficher.
  const refusFichier = refusDe('fichier')
    || (refus && !CHAMPS_DU_FORMULAIRE.has(refus.champ) ? refus : null)
  const refusFournisseur = refusDe('fournisseur')

  return (
    <Card className="mt-2 p-3" data-testid="cal-series-depot">
      <p className="text-sm text-foreground">Série météo de la société</p>
      <p className="mt-1 text-xs text-muted-foreground">
        Un CSV à colonnes nommées : « horodatage » (ISO, avec son fuseau) et
        « gi_w_m2 » (irradiance sur le PLAN) sont obligatoires ;
        « gb_i_w_m2 », « gd_i_w_m2 », « gr_i_w_m2 », « t2m_c » et « ws10m »
        entrent si elles sont là. Le serveur vérifie le fichier et refuse en
        nommant la colonne — rien n’est deviné ici.
      </p>

      {refus && (
        <p
          role="alert"
          className="mt-2 text-sm text-destructive"
          data-testid="cal-series-depot-bandeau"
        >
          Dépôt refusé : corrigez « {refus.champ} »
          {refus.ligne ? ` (ligne ${refus.ligne} du fichier)` : ''}.
        </p>
      )}

      <form className="mt-3 flex flex-col gap-2" onSubmit={deposer}>
        <div>
          <Label htmlFor="cal-series-depot-fichier">Fichier CSV</Label>
          <SelecteurFichier
            id="cal-series-depot-fichier"
            testId="cal-series-depot-fichier"
            accept=".csv,text/csv"
            fichier={fichier}
            onChange={setFichier}
          />
          {refusFichier && (
            <p
              className="mt-1 text-xs text-destructive"
              data-testid="cal-series-depot-motif-fichier"
            >
              {refusFichier.champ} : {refusFichier.motif}
            </p>
          )}
        </div>

        <div>
          <Label htmlFor="cal-series-depot-fournisseur">Fournisseur</Label>
          <Input
            id="cal-series-depot-fournisseur"
            value={fournisseur}
            onChange={(e) => setFournisseur(e.target.value)}
            placeholder="Station, bureau d’études, éditeur du fichier…"
            data-testid="cal-series-depot-fournisseur"
          />
          {refusFournisseur && (
            <p
              className="mt-1 text-xs text-destructive"
              data-testid="cal-series-depot-motif-fournisseur"
            >
              {refusFournisseur.motif}
            </p>
          )}
        </div>

        <div>
          <Button
            type="submit"
            size="sm"
            variant="outline"
            disabled={envoi}
            data-testid="cal-series-depot-envoyer"
          >
            <Upload className="mr-1 h-4 w-4" aria-hidden="true" />
            {envoi ? 'Dépôt…' : 'Déposer la série météo'}
          </Button>
        </div>
      </form>

      {depose?.remplace && (
        <p
          className="mt-2 text-xs text-muted-foreground"
          data-testid="acal148-remplace"
        >
          Remplace {depose.remplace.nom || 'le fichier précédent'}
          {depose.remplace.depose_le
            ? ` déposé le ${formatDate(depose.remplace.depose_le)}`
            : ''}
          {' '}— l’ancien fichier est à la corbeille.
        </p>
      )}
      {depose && (
        <p
          className="mt-2 text-xs text-muted-foreground"
          data-testid="cal-series-depot-provenance"
        >
          {depose.message}
          {depose.meteo?.fichier?.nom
            ? ` Fichier : ${depose.meteo.fichier.nom}`
            : ''}
          {depose.meteo?.fournisseur
            ? ` · Fournisseur : ${depose.meteo.fournisseur}`
            : ''}
          {depose.serie?.points != null
            ? ` · ${depose.serie.points} heure(s)`
            : ''}
          {depose.meteo?.fenetre_annees
            ? ` · ${depose.meteo.fenetre_annees}`
            : ''}
        </p>
      )}
      {depose?.qualite && <QualiteFichier qualite={depose.qualite} />}
    </Card>
  )
}

const MOIS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
  'septembre', 'octobre', 'novembre', 'décembre']

/** ACAL764 — les quatre lignes de contrôle du fichier déposé (servies par le dépôt, ACAL763) :
    des nombres en mots simples, jamais un verdict ni un blocage. */
function QualiteFichier({ qualite }) {
  const { couverture, decalage, negatifs, extraterrestre, motifs } = qualite
  const nonCalcule = (cle) => `non calculé — ${motifs?.[cle] || 'motif non servi'}`
  const absents = Object.entries(couverture?.mois_absents || {})
    .filter(([, mois]) => mois.length)
    .map(([annee, mois]) => `${annee} : ${mois.map((m) => MOIS_FR[m - 1]).join(', ')}`)
  const colonnes = Object.values(negatifs || {})
  const nbNegatifs = colonnes.reduce((somme, c) => somme + c.nombre, 0)
  const plusPetite = Math.min(...colonnes.map((c) => c.plus_petite).filter((v) => v != null))
  const ecart = decalage?.ecart_median_min
  const lignes = [
    ['couverture', `Couverture : ${formatNumber(couverture.heures_lues)} heures sur ${couverture.annees.join(', ')} ; `
      + `mois sans mesure : ${absents.length ? absents.join(' ; ') : 'aucun'}`],
    ['decalage', decalage
      ? `Décalage horaire : le milieu des journées mesurées tombe ${formatNumber(Math.abs(ecart))} minutes `
        + `${ecart < 0 ? 'avant' : 'après'} le midi solaire calculé (sur ${formatNumber(decalage.jours_mesures)} jours)`
      : `Décalage horaire : ${nonCalcule('decalage')}`],
    ['negatifs', nbNegatifs
      ? `Valeurs négatives : ${formatNumber(nbNegatifs)} valeurs négatives (la plus petite : −${formatNumber(Math.abs(plusPetite))} W/m²)`
      : 'Valeurs négatives : aucune'],
    ['extraterrestre', extraterrestre
      ? `Au-dessus du soleil du jour : ${extraterrestre.heures_au_dessus
        ? `${formatNumber(extraterrestre.heures_au_dessus)} heures au-dessus de l’irradiance extraterrestre `
          + `(la plus forte : ${formatNumber(extraterrestre.plus_forte_w_m2)} W/m²)`
        : 'aucune'}`
      : `Au-dessus du soleil du jour : ${nonCalcule('extraterrestre')}`],
  ]
  return (
    <div className="mt-2" data-testid="acal764-qualite">
      <ul className="text-sm text-foreground">
        {lignes.map(([cle, texte]) => <li key={cle} data-testid={`acal764-${cle}`}>{texte}</li>)}
      </ul>
      <p className="mt-1 text-xs text-muted-foreground">Contrôle fait au dépôt.</p>
    </div>
  )
}
