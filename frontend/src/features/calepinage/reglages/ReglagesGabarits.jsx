import { useCallback, useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { formatDateTime } from '../../../lib/format'
import { Button, Card } from '../../../ui'

/* ============================================================================
   ACAL242 — « RÉGLAGES › CALEPINAGE › GABARITS » : LE DÉPÔT DES GABARITS.
   ----------------------------------------------------------------------------
   La porte serveur existe (ACAL238, `gabarits-dossiers/`, contrat
   `gabarits_dossier_reglementaire.json`) mais aucun écran ne la servait :
   aucune société ne pouvait déposer le document fourni par l'administration,
   donc aucun dossier réglementaire n'apparaissait jamais.

   AUCUN FORMULAIRE OFFICIEL INVENTÉ. L'intitulé, les pièces attendues (avec
   leur RÉFÉRENCE) et les champs sont SAISIS par la société, le fichier est SON
   PDF : l'écran ne propose aucun gabarit pré-rempli. Le refus 400 du serveur
   NOMME le champ fautif (`code`, `fichier`, `pieces_attendues[1].source_
   reference`…) : il est rendu SOUS ce champ, jamais en « non enregistré »
   générique ; un 409 (gabarit utilisé) est rendu sur la ligne du gabarit.
   ========================================================================== */

//: Les types de champ admis par le serveur (`GabaritDossierReglementaire.TYPES_CHAMP`).
const TYPES_CHAMP = ['texte', 'nombre', 'date']
//: Les préremplissages admis (`GabaritDossierReglementaire.CLES_PREREMPLISSAGE`).
const CLES_PREREMPLISSAGE = [
  ['', 'aucun (saisie seule)'],
  ['societe_nom', 'nom de la société'],
  ['client_nom', 'nom du client'],
  ['adresse', 'adresse du site'],
  ['puissance_kwc', 'puissance (kWc)'],
  ['nombre_modules', 'nombre de modules'],
  ['orientation_deg', 'orientation (°)'],
  ['inclinaison_deg', 'inclinaison (°)'],
]

const PIECE_VIDE = { code: '', intitule: '', source_reference: '', obligatoire: true }
const CHAMP_VIDE = { code: '', libelle: '', type: 'texte', cle_calepinage: '', obligatoire: false }
const FORMULAIRE_VIDE = { pays: '', code: '', genre: '', intitule: '', version: '' }

function messageDe(valeur) {
  return Array.isArray(valeur) ? valeur.join(' ') : String(valeur)
}

function Erreur({ erreurs, cle }) {
  if (!erreurs?.[cle]) return null
  return (
    <p className="text-xs text-destructive" data-testid={`acal242-erreur-${cle}`}>
      {messageDe(erreurs[cle])}
    </p>
  )
}

function Champ({ id, libelle, valeur, onChange, erreurs, cle, ...attributs }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm">{libelle}</label>
      <input
        id={id}
        value={valeur}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-border px-2 py-1 text-sm"
        {...attributs}
      />
      <Erreur erreurs={erreurs} cle={cle} />
    </div>
  )
}

/** Les champs d'une ligne vides sont retirés : seule la saisie part au serveur. */
function nettoyer(lignes) {
  return lignes
    .filter((ligne) => Object.values(ligne).some((v) => typeof v === 'string' && v.trim()))
    .map((ligne) => {
      const copie = { ...ligne }
      if ('cle_calepinage' in copie && !copie.cle_calepinage) delete copie.cle_calepinage
      return copie
    })
}

function FormulaireGabarit({ onCree }) {
  const [valeurs, setValeurs] = useState(FORMULAIRE_VIDE)
  const [pieces, setPieces] = useState([{ ...PIECE_VIDE }])
  const [champs, setChamps] = useState([])
  const [fichier, setFichier] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [enVol, setEnVol] = useState(false)

  const poser = (cle) => (valeur) => setValeurs((v) => ({ ...v, [cle]: valeur }))
  const poserLigne = (setter, rang, cle, valeur) => setter((lignes) => lignes.map(
    (ligne, i) => (i === rang ? { ...ligne, [cle]: valeur } : ligne),
  ))

  const deposer = (e) => {
    e.preventDefault()
    setErreurs({})
    setEnVol(true)
    const corps = new FormData()
    Object.entries(valeurs).forEach(([cle, valeur]) => corps.append(cle, valeur))
    corps.append('pieces_attendues', JSON.stringify(nettoyer(pieces)))
    corps.append('champs', JSON.stringify(nettoyer(champs)))
    if (fichier) corps.append('fichier', fichier)
    calepinageApi.gabarits.creer(corps)
      .then((r) => {
        setValeurs(FORMULAIRE_VIDE)
        setPieces([{ ...PIECE_VIDE }])
        setChamps([])
        setFichier(null)
        if (onCree) onCree(r.data?.gabarit)
      })
      .catch((err) => {
        const donnees = err?.response?.data
        setErreurs(donnees && typeof donnees === 'object'
          ? donnees
          : { detail: 'Dépôt refusé par le serveur.' })
      })
      .finally(() => setEnVol(false))
  }

  const connus = new Set(['pays', 'code', 'genre', 'intitule', 'version', 'fichier',
    'pieces_attendues', 'champs'])
  pieces.forEach((_p, i) => ['code', 'intitule', 'source_reference'].forEach(
    (c) => connus.add(`pieces_attendues[${i}].${c}`)))
  champs.forEach((_c, i) => ['code', 'libelle', 'type', 'cle_calepinage'].forEach(
    (c) => connus.add(`champs[${i}].${c}`)))

  return (
    <form noValidate onSubmit={deposer} className="flex flex-col gap-3" data-testid="acal242-formulaire">
      <h2 className="text-base font-semibold">Déposer un gabarit</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <Champ id="acal242-pays" libelle="Pays (code à deux lettres)" valeur={valeurs.pays} onChange={poser('pays')} erreurs={erreurs} cle="pays" />
        <Champ id="acal242-code" libelle="Code" valeur={valeurs.code} onChange={poser('code')} erreurs={erreurs} cle="code" />
        <Champ id="acal242-genre" libelle="Genre (dp_mairie, enedis, consuel, raccordement…)" valeur={valeurs.genre} onChange={poser('genre')} erreurs={erreurs} cle="genre" />
        <Champ id="acal242-intitule" libelle="Intitulé" valeur={valeurs.intitule} onChange={poser('intitule')} erreurs={erreurs} cle="intitule" />
        <Champ id="acal242-version" libelle="Version" valeur={valeurs.version} onChange={poser('version')} erreurs={erreurs} cle="version" />
        <div className="flex flex-col gap-1">
          <label htmlFor="acal242-fichier" className="text-sm">Fichier du gabarit (PDF)</label>
          <input
            id="acal242-fichier"
            type="file"
            accept="application/pdf"
            data-testid="acal242-fichier"
            onChange={(e) => setFichier(e.target.files?.[0] || null)}
          />
          <Erreur erreurs={erreurs} cle="fichier" />
        </div>
      </div>

      <fieldset className="flex flex-col gap-2" data-testid="acal242-pieces">
        <legend className="text-sm font-medium">Pièces attendues (avec leur référence)</legend>
        {pieces.map((piece, i) => (
          <div key={i} className="grid gap-2 sm:grid-cols-4">
            <Champ id={`acal242-piece-${i}-code`} libelle="Code" valeur={piece.code} onChange={(v) => poserLigne(setPieces, i, 'code', v)} erreurs={erreurs} cle={`pieces_attendues[${i}].code`} />
            <Champ id={`acal242-piece-${i}-intitule`} libelle="Intitulé" valeur={piece.intitule} onChange={(v) => poserLigne(setPieces, i, 'intitule', v)} erreurs={erreurs} cle={`pieces_attendues[${i}].intitule`} />
            <Champ id={`acal242-piece-${i}-reference`} libelle="Référence (source)" valeur={piece.source_reference} onChange={(v) => poserLigne(setPieces, i, 'source_reference', v)} erreurs={erreurs} cle={`pieces_attendues[${i}].source_reference`} />
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={piece.obligatoire} onChange={(e) => poserLigne(setPieces, i, 'obligatoire', e.target.checked)} />
              obligatoire
            </label>
          </div>
        ))}
        <Erreur erreurs={erreurs} cle="pieces_attendues" />
        <Button type="button" variant="outline" onClick={() => setPieces((l) => [...l, { ...PIECE_VIDE }])}>
          Ajouter une pièce
        </Button>
      </fieldset>

      <fieldset className="flex flex-col gap-2" data-testid="acal242-champs">
        <legend className="text-sm font-medium">Champs du gabarit</legend>
        {champs.map((champ, i) => (
          <div key={i} className="grid gap-2 sm:grid-cols-4">
            <Champ id={`acal242-champ-${i}-code`} libelle="Code" valeur={champ.code} onChange={(v) => poserLigne(setChamps, i, 'code', v)} erreurs={erreurs} cle={`champs[${i}].code`} />
            <Champ id={`acal242-champ-${i}-libelle`} libelle="Libellé" valeur={champ.libelle} onChange={(v) => poserLigne(setChamps, i, 'libelle', v)} erreurs={erreurs} cle={`champs[${i}].libelle`} />
            <div className="flex flex-col gap-1">
              <label htmlFor={`acal242-champ-${i}-type`} className="text-sm">Type</label>
              <select id={`acal242-champ-${i}-type`} value={champ.type} onChange={(e) => poserLigne(setChamps, i, 'type', e.target.value)} className="rounded border border-border px-2 py-1 text-sm">
                {TYPES_CHAMP.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <Erreur erreurs={erreurs} cle={`champs[${i}].type`} />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor={`acal242-champ-${i}-cle`} className="text-sm">Prérempli depuis le calepinage</label>
              <select id={`acal242-champ-${i}-cle`} value={champ.cle_calepinage} onChange={(e) => poserLigne(setChamps, i, 'cle_calepinage', e.target.value)} className="rounded border border-border px-2 py-1 text-sm">
                {CLES_PREREMPLISSAGE.map(([cle, libelle]) => <option key={cle || 'aucun'} value={cle}>{libelle}</option>)}
              </select>
              <Erreur erreurs={erreurs} cle={`champs[${i}].cle_calepinage`} />
            </div>
          </div>
        ))}
        <Erreur erreurs={erreurs} cle="champs" />
        <Button type="button" variant="outline" onClick={() => setChamps((l) => [...l, { ...CHAMP_VIDE }])}>
          Ajouter un champ
        </Button>
      </fieldset>

      {/* Une clé que ce formulaire ne rend pas champ par champ reste AFFICHÉE. */}
      {Object.entries(erreurs).filter(([cle]) => !connus.has(cle)).map(([cle, message]) => (
        <p key={cle} className="text-xs text-destructive" data-testid={`acal242-erreur-${cle}`}>
          {messageDe(message)}
        </p>
      ))}
      <Button type="submit" disabled={enVol} data-testid="acal242-deposer">
        {enVol ? 'Dépôt…' : 'Déposer le gabarit'}
      </Button>
    </form>
  )
}

function LigneGabarit({ gabarit, peutGerer, onChange }) {
  const [erreur, setErreur] = useState(null)
  const refus = (err) => {
    const donnees = err?.response?.data
    setErreur(donnees && typeof donnees === 'object'
      ? Object.values(donnees).map(messageDe).join(' ')
      : 'Action refusée par le serveur.')
  }
  const basculer = () => {
    setErreur(null)
    calepinageApi.gabarits.modifier(gabarit.id, { actif: !gabarit.actif }).then(onChange).catch(refus)
  }
  const supprimer = () => {
    setErreur(null)
    calepinageApi.gabarits.supprimer(gabarit.id).then(onChange).catch(refus)
  }
  return (
    <li className="flex flex-col gap-1 border-t border-border/60 pt-2" data-testid={`acal242-gabarit-${gabarit.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{gabarit.intitule}</span>
        <span className="text-xs text-muted-foreground">
          {`${gabarit.pays} · ${gabarit.code}${gabarit.genre ? ` · ${gabarit.genre}` : ''}`}
          {gabarit.version ? ` · version ${gabarit.version}` : ''}
        </span>
        <span className="text-xs" data-testid={`acal242-fichier-${gabarit.id}`}>
          {gabarit.fichiers
            ? `fichier présent — ${gabarit.fichiers.nom}`
            : 'fichier manquant'}
        </span>
        {!gabarit.actif && <span className="text-xs text-muted-foreground">désactivé</span>}
      </div>
      {gabarit.depose_le && (
        <p className="text-xs text-muted-foreground">
          {`Déposé le ${formatDateTime(gabarit.depose_le)}`}
          {gabarit.depose_par?.nom_complet ? ` par ${gabarit.depose_par.nom_complet}` : ''}
        </p>
      )}
      {peutGerer && (
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={basculer} data-testid={`acal242-basculer-${gabarit.id}`}>
            {gabarit.actif ? 'Désactiver' : 'Réactiver'}
          </Button>
          <Button type="button" variant="outline" onClick={supprimer} data-testid={`acal242-supprimer-${gabarit.id}`}>
            Supprimer
          </Button>
        </div>
      )}
      {erreur && (
        <p className="text-xs text-destructive" data-testid={`acal242-erreur-gabarit-${gabarit.id}`}>{erreur}</p>
      )}
    </li>
  )
}

export default function ReglagesGabarits() {
  const peutGerer = useHasPermission('calepinage_gerer')
  const [gabarits, setGabarits] = useState(null)
  const [erreurChargement, setErreurChargement] = useState(null)

  const charger = useCallback(() => {
    calepinageApi.gabarits.liste()
      .then((r) => { setGabarits(r.data?.gabarits || []); setErreurChargement(null) })
      .catch(() => setErreurChargement('Gabarits indisponibles.'))
  }, [])
  useEffect(() => { charger() }, [charger])

  return (
    <div className="page flex flex-col gap-4" data-testid="acal242-ecran">
      <div className="flex flex-col gap-1">
        <a href="/calepinage/reglages" className="text-xs underline">← Réglages simulation</a>
        <h1 className="text-lg font-semibold text-foreground">Gabarits des dossiers réglementaires</h1>
        <p className="text-sm text-muted-foreground">
          Le gabarit est le document fourni par l’administration, déposé par la société :
          l’ERP n’en fabrique aucun. Ses pièces et ses champs apparaissent ensuite dans
          les dossiers réglementaires de chaque calepinage.
        </p>
      </div>
      <Card className="p-4">
        {erreurChargement && <p className="text-sm text-destructive">{erreurChargement}</p>}
        {gabarits && gabarits.length === 0 && (
          <p className="text-sm text-muted-foreground" data-testid="acal242-vide">
            Aucun gabarit déposé pour cette société.
          </p>
        )}
        {gabarits && gabarits.length > 0 && (
          <ul className="flex flex-col gap-2" data-testid="acal242-liste">
            {gabarits.map((gabarit) => (
              <LigneGabarit key={gabarit.id} gabarit={gabarit} peutGerer={peutGerer} onChange={charger} />
            ))}
          </ul>
        )}
      </Card>
      {peutGerer && (
        <Card className="p-4">
          <FormulaireGabarit onCree={charger} />
        </Card>
      )}
    </div>
  )
}
