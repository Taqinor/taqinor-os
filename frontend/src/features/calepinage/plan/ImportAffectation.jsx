import { useRef, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { Button, Label } from '../../../ui'
import { refusParChamp } from '../electrique/entreeElectrique'

/* ============================================================================
   ACAL631 — « IMPORTER UN PLAN DE CHAÎNES (CSV) » dans l'affectation des chaînes.
   `POST calepinages/<id>/importer-affectation/` (contrat `calepinage_import_affectation.json`,
   ACAL630) lit le fichier (en-tête `module;chaine;mppt;onduleur`) et rend les `lignes` valides,
   les `refus` ligne par ligne et les `bloquants`. Un fichier SANS refus remplit la proposition
   d'affectation (même état que « Affecter la sélection », verdict à chaud relancé par l'écran) ;
   rien n'est enregistré avant « Enregistrer ». Un fichier fautif ne remplit rien.
   ========================================================================== */

const lireTexte = (fichier) => new Promise((resolve, reject) => {
  const lecteur = new FileReader()
  lecteur.onload = () => resolve(String(lecteur.result ?? ''))
  lecteur.onerror = () => reject(lecteur.error)
  lecteur.readAsText(fichier)
})

export default function ImportAffectation({ calepinageId, onProposer, lectureSeule = false }) {
  const [refus, setRefus] = useState([])
  const [bloquants, setBloquants] = useState([])
  const [message, setMessage] = useState(null)
  const [nomFichier, setNomFichier] = useState('')
  const entreeRef = useRef(null)

  const importer = async (evenement) => {
    const fichier = evenement.target.files?.[0]
    evenement.target.value = ''
    if (!fichier) return
    setNomFichier(fichier.name ?? '')
    setRefus([]); setBloquants([]); setMessage(null)
    try {
      const res = await calepinageApi.calepinages.importerAffectation(calepinageId, await lireTexte(fichier))
      const donnees = res?.data ?? {}
      setRefus(donnees.refus ?? [])
      setBloquants(donnees.bloquants ?? [])
      if ((donnees.refus ?? []).length === 0 && (donnees.lignes ?? []).length > 0) {
        onProposer(donnees.lignes)
        setMessage(`${donnees.lignes.length} module(s) proposés : vérifiez le verdict puis enregistrez.`)
      }
    } catch (err) {
      const texte = Object.values(refusParChamp(err?.response?.data))[0]
      setRefus([{ ligne: null, message: texte || 'Import refusé : le serveur n’a pas lu le fichier.' }])
    }
  }

  return (
    <div className="mt-2 flex flex-col gap-1" data-testid="acal631-import">
      <Label htmlFor="acal631-fichier" className="text-sm font-semibold">
        Importer un plan de chaînes (CSV)
      </Label>
      {/* ACAL1541 — l'entrée native (texte du navigateur, en anglais) est masquée : un bouton français la déclenche. */}
      <div className="flex flex-wrap items-center gap-2">
        <input ref={entreeRef} id="acal631-fichier" type="file" accept=".csv,text/csv" disabled={lectureSeule}
          onChange={importer} aria-invalid={refus.length > 0 ? 'true' : undefined} className="hidden"
          data-testid="acal631-fichier" />
        <Button type="button" variant="outline" className="min-h-11" disabled={lectureSeule}
          onClick={() => entreeRef.current?.click()} data-testid="acal1541-choisir">
          Choisir un fichier
        </Button>
        <span className="text-sm text-muted-foreground" data-testid="acal1541-nom">
          {nomFichier || 'Aucun fichier choisi'}
        </span>
      </div>
      {refus.length > 0 && (
        <ul role="alert" className="flex flex-col gap-1 text-sm text-destructive" data-testid="acal631-refus">
          {refus.map((r) => (
            <li key={`${r.ligne}-${r.colonne}-${r.message}`}>{r.ligne == null ? '' : `Ligne ${r.ligne} : `}{r.message}</li>
          ))}
        </ul>
      )}
      {bloquants.map((b) => <p key={b} className="text-sm text-destructive">{b}</p>)}
      {message && <p role="status" className="text-sm text-muted-foreground" data-testid="acal631-message">{message}</p>}
    </div>
  )
}
