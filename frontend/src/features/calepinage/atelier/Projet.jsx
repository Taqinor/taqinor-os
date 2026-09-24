import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Download, Upload } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import { Button, Card } from '../../../ui'
import { downloadBlob } from '../../../utils/downloadBlob'

/* ============================================================================
   CALX371 — MONTER L'EXPORT ET L'IMPORT DE PROJET EN ONGLET DE L'ATELIER.
   ----------------------------------------------------------------------------
   Constat (a3 §1) : `export-layout`/`import-layout` (le document de pose
   SEUL, CAL216/CALX28) ont déjà leur bouton dans le panneau Documents ;
   `export-projet.json`/`import-projet` (CALX312/CALX370 — le PROJET complet :
   site, équipements, résultat, postes de pertes, variantes) n'avaient AUCUN
   consommateur — le transfert d'un projet entier était impossible sans passer
   par un client HTTP externe.

   L'EXPORT télécharge TEL QUEL le document du contrat
   `contract_samples/export_projet.json` (`GET .../export-projet.json/`,
   CALX312/CALX370, déjà servi) — aucune transformation ici.

   L'IMPORT EST UN APERÇU AVANT TOUTE ÉCRITURE (`POST
   calepinages/import-projet/`, contrat `calepinage_projet_json.json`,
   CALX370) : choisir un fichier envoie `apercu: true` — LE SERVEUR N'ÉCRIT
   RIEN — et rend ce qui SERAIT écrit (modules, postes de pertes, variantes,
   blocs REPRIS et blocs IGNORÉS avec leur motif). Seul le clic explicite sur
   « Confirmer l'import » renvoie `apercu: false` et CRÉE un nouveau
   calepinage. Un refus (JSON illisible, champ invalide, rattachement
   manquant) s'affiche SOUS le champ de dépôt, en NOMMANT le chemin fautif —
   jamais une phrase générique (règle fondateur du 08/09/2026).

   LE RATTACHEMENT (`lead` OU `client`, EXACTEMENT un des deux —
   `services/export_projet.py::importer_projet` refuse sinon, en nommant
   `lead`) est celui du calepinage OUVERT, lu une fois par `GET .../<pk>/` :
   le fichier importé peut venir d'une AUTRE société, ses identifiants ne sont
   JAMAIS repris.
   ========================================================================== */

const REFUS_SANS_MOTIF = 'Le serveur a refusé la demande sans en donner le motif.'

/** Les blocs REPRIS, en français — jamais une clé technique affichée telle
    quelle (`repris`/`ignores[].bloc` du contrat `calepinage_projet_json.json`). */
const LIBELLE_BLOC = {
  roof_layout: 'Conception (roof_layout)',
  postes_pertes: 'Postes de pertes',
  variantes: 'Variantes',
  resultat: 'Résultat de simulation',
  equipements: 'Équipements',
  site: 'Site',
  provenance: 'Provenance',
  calepinage: 'Identifiants du calepinage',
}

/** Le refus du serveur — `{champ, motif}` ou `null` — depuis un corps JSON
    ordinaire (`import-projet/`) ou un corps BLOB (l'export demande
    `responseType: 'blob'`) — même discipline que
    `documents/deposerImage.js::erreursDeRefusBlob`. */
async function lireRefus(erreur) {
  let corps = erreur?.response?.data
  if (typeof Blob !== 'undefined' && corps instanceof Blob) {
    try { corps = JSON.parse(await corps.text()) } catch { return null }
  }
  if (!corps || typeof corps !== 'object') return null
  for (const [champ, valeur] of Object.entries(corps)) {
    const motif = Array.isArray(valeur) ? valeur[0] : valeur
    if (typeof motif === 'string' && motif.trim()) return { champ, motif }
  }
  return null
}

export default function Projet({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl
  const entreeFichier = useRef(null)

  /* ── Export ────────────────────────────────────────────────────────── */
  const [exportEnCours, setExportEnCours] = useState(false)
  const [exportErreur, setExportErreur] = useState(null)

  const exporter = useCallback(() => {
    setExportErreur(null)
    setExportEnCours(true)
    return Promise.resolve(calepinageApi.calepinages.exporterProjet(calepinageId))
      .then((res) => downloadBlob(res?.data, `calepinage-${calepinageId}-projet.json`))
      .catch(async (erreur) => {
        const refus = await lireRefus(erreur)
        setExportErreur(refus?.motif || REFUS_SANS_MOTIF)
      })
      .finally(() => setExportEnCours(false))
  }, [calepinageId])

  /* ── Le rattachement du calepinage OUVERT, lu UNE fois ───────────────
     `null` tant qu'il n'est pas connu (le bouton « choisir » reste
     désactivé, jamais un envoi sans rattachement deviné). */
  const [rattachement, setRattachement] = useState(null)
  useEffect(() => {
    if (!calepinageId) { setRattachement({}); return }
    Promise.resolve(calepinageApi.calepinages.get(calepinageId))
      .then((res) => {
        const detail = res?.data || {}
        if (detail.lead?.id) setRattachement({ lead: detail.lead.id })
        else if (detail.client?.id) setRattachement({ client: detail.client.id })
        else setRattachement({})
      })
      .catch(() => setRattachement({}))
  }, [calepinageId])

  const corpsRattachement = () => (rattachement?.lead
    ? { lead: rattachement.lead }
    : rattachement?.client ? { client: rattachement.client } : {})

  /* ── Import : APERÇU d'abord, ÉCRITURE seulement sur confirmation ──── */
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [projetChoisi, setProjetChoisi] = useState(null) // le JSON déjà lu
  const [apercu, setApercu] = useState(null)
  const [resultat, setResultat] = useState(null)

  const choisir = async (evenement) => {
    const fichier = evenement.target.files?.[0] || null
    evenement.target.value = '' // même fichier ré-choisi deux fois de suite
    setErreur(null)
    setApercu(null)
    setResultat(null)
    setProjetChoisi(null)
    if (!fichier) return

    let projet
    try {
      projet = JSON.parse(await fichier.text())
    } catch {
      setErreur({ champ: 'projet', motif: 'Le fichier n’est pas un JSON valide.' })
      return
    }

    setEnCours(true)
    try {
      const reponse = await calepinageApi.calepinages.importerProjet({
        projet, ...corpsRattachement(), apercu: true,
      })
      setProjetChoisi(projet)
      setApercu(reponse?.data || null)
    } catch (err) {
      setErreur(await lireRefus(err) || { champ: 'projet', motif: REFUS_SANS_MOTIF })
    } finally {
      setEnCours(false)
    }
  }

  const confirmer = async () => {
    if (!projetChoisi) return
    setEnCours(true)
    setErreur(null)
    try {
      const reponse = await calepinageApi.calepinages.importerProjet({
        projet: projetChoisi, ...corpsRattachement(), apercu: false,
      })
      setResultat(reponse?.data || null)
      setApercu(null)
      setProjetChoisi(null)
    } catch (err) {
      setErreur(await lireRefus(err) || { champ: 'projet', motif: REFUS_SANS_MOTIF })
    } finally {
      setEnCours(false)
    }
  }

  const annuler = () => {
    setApercu(null)
    setProjetChoisi(null)
    setErreur(null)
  }

  return (
    <div className="mt-6" data-testid="cal-projet">
      <p className="tech-label rule-brass text-brass-300">Projet</p>
      <p className="mt-2 text-xs text-lune-faint" data-testid="cal-projet-rappel">
        L’export reprend le projet ET ses résultats. L’import montre d’abord un
        APERÇU de ce qui SERAIT écrit — rien n’est écrit avant confirmation
        explicite.
      </p>

      <Card className="mt-3 p-3" data-testid="cal-projet-export">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-white">Exporter ce projet (JSON)</p>
          <Button
            size="sm"
            variant="outline"
            loading={exportEnCours}
            onClick={exporter}
            data-testid="cal-projet-telecharger"
          >
            <Download className="mr-1 h-4 w-4" aria-hidden="true" />
            Télécharger
          </Button>
        </div>
        {exportErreur && (
          <p role="alert" className="mt-2 text-sm text-destructive" data-testid="cal-projet-export-erreur">
            {exportErreur}
          </p>
        )}
      </Card>

      <Card className="mt-3 p-3" data-testid="cal-projet-import">
        <p className="text-sm text-white">Importer un projet (JSON)</p>
        <p className="mt-1 text-xs text-muted-foreground" data-testid="cal-projet-import-rattachement">
          {rattachement === null
            ? 'Rattachement en cours de lecture…'
            : `Rattaché au même ${rattachement.lead ? 'lead' : rattachement.client ? 'client' : '—'} que ce calepinage — les identifiants du fichier ne sont jamais repris.`}
        </p>

        <div className="mt-2">
          <Button
            size="sm"
            variant="outline"
            loading={enCours}
            disabled={rattachement === null}
            onClick={() => entreeFichier.current?.click()}
            data-testid="cal-projet-choisir"
          >
            <Upload className="mr-1 h-4 w-4" aria-hidden="true" />
            Choisir un fichier
          </Button>
          <input
            ref={entreeFichier}
            type="file"
            accept="application/json"
            className="hidden"
            aria-label="Importer un projet de calepinage (JSON)"
            data-testid="cal-projet-fichier"
            onChange={choisir}
          />
        </div>

        {erreur && (
          <p role="alert" className="mt-2 text-sm text-destructive" data-testid="cal-projet-erreur">
            {erreur.champ ? `${erreur.champ} : ` : ''}{erreur.motif}
          </p>
        )}

        {apercu && (
          <div className="mt-3 border-t border-border/60 pt-3" data-testid="cal-projet-apercu">
            <p className="text-sm text-white">Aperçu — rien n’est encore écrit</p>
            <ul className="mt-2 space-y-1 text-xs text-lune-soft">
              <li data-testid="cal-projet-apercu-modules">Modules : {apercu.modules ?? '—'}</li>
              <li data-testid="cal-projet-apercu-postes">Postes de pertes : {apercu.postes_pertes}</li>
              <li data-testid="cal-projet-apercu-variantes">
                Variantes : {apercu.variantes}
                {apercu.variante_retenue ? ` (retenue : ${apercu.variante_retenue})` : ''}
              </li>
            </ul>

            <p className="mt-2 text-xs text-lune-faint">Blocs repris :</p>
            <ul className="list-disc pl-4 text-xs text-lune-soft" data-testid="cal-projet-apercu-repris">
              {(apercu.repris || []).map((bloc) => (
                <li key={bloc}>{LIBELLE_BLOC[bloc] || bloc}</li>
              ))}
            </ul>

            {(apercu.ignores || []).length > 0 && (
              <>
                <p className="mt-2 text-xs text-lune-faint">Blocs ignorés :</p>
                <ul className="list-disc pl-4 text-xs text-muted-foreground" data-testid="cal-projet-apercu-ignores">
                  {apercu.ignores.map((item) => (
                    <li key={item.bloc}>{LIBELLE_BLOC[item.bloc] || item.bloc} — {item.motif}</li>
                  ))}
                </ul>
              </>
            )}

            <div className="mt-3 flex gap-2">
              <Button size="sm" loading={enCours} onClick={confirmer} data-testid="cal-projet-confirmer">
                Confirmer l’import
              </Button>
              <Button size="sm" variant="ghost" onClick={annuler} data-testid="cal-projet-annuler">
                Annuler
              </Button>
            </div>
          </div>
        )}

        {resultat && (
          <p role="status" className="mt-3 text-sm text-foreground" data-testid="cal-projet-resultat">
            Projet importé : calepinage n° {resultat.calepinage}
            {resultat.modules != null ? ` — ${resultat.modules} modules` : ''}.
          </p>
        )}
      </Card>
    </div>
  )
}
