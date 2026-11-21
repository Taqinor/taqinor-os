import { useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { Card } from '../../../ui'

/* ============================================================================
   ACAL397 (acceptation ACAL490) — LA NORME ÉLECTRIQUE, SAISISSABLE.
   ----------------------------------------------------------------------------
   « Ce qui manque » renvoie la ligne `norme_absente` vers
   `/calepinage/reglages#norme` (`services/parcours_guide.py::MOTIFS`) ; la
   section `norme_electrique` (`services/norme.py::norme_applicable` : `norme`
   + `reference`) n'avait AUCUN champ à l'écran. Le champ d'`id` `norme` est
   celui-ci. Règle D5 : aucune norme n'est supposée ; le jeu français n'est
   retenu que SÉLECTIONNÉ ici.
   ÉCRITURE — le serveur REMPLACE la section en entier : le corps reprend la
   section servie (coefficients compris), seules `norme` et `reference`
   changent.
   ========================================================================== */
const NORMES = [
  { valeur: '', libelle: 'Aucune — calculs dépendant d’une norme omis' },
  { valeur: 'nf_c_15_100', libelle: 'NF C 15-100 / UTE C 15-712-1 / IEC 62548 (jeu français)' },
]

const texte = (v) => (typeof v === 'string' ? v : '')

export default function ReglagesNorme({ normeElectrique = null }) {
  const peutGerer = useHasPermission('calepinage_gerer')
  const [servi, setServi] = useState(normeElectrique && typeof normeElectrique === 'object' ? normeElectrique : {})
  const [norme, setNorme] = useState(texte(servi.norme))
  const [reference, setReference] = useState(texte(servi.reference))
  const [erreur, setErreur] = useState(null)
  const [message, setMessage] = useState(null)
  const [enCours, setEnCours] = useState(false)

  const enregistrer = async () => {
    setMessage(null)
    setErreur(null)
    setEnCours(true)
    try {
      const section = { ...servi, norme: norme || null, reference: reference.trim() || null }
      const res = await calepinageApi.parametres.update({ norme_electrique: section })
      const relu = res?.data?.norme_electrique
      setServi(relu && typeof relu === 'object' ? relu : section)
      setMessage('Norme électrique enregistrée.')
    } catch (e) {
      const corps = e?.response?.data
      const motif = corps && typeof corps === 'object' ? Object.values(corps).flat().join(' ') : ''
      setErreur(motif || 'Le serveur n’a rendu aucun motif : rien n’a été enregistré.')
    } finally {
      setEnCours(false)
    }
  }

  return (
    <Card className="mt-5 p-4" data-testid="acal397-norme">
      <h2 className="text-base font-semibold text-foreground">Norme électrique</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Sans norme choisie, les sections de câble, chutes de tension et la check-list de protections sont omises.
      </p>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="block" htmlFor="norme">
          <span className="text-xs font-medium text-foreground">Norme applicable</span>
          <select id="norme" value={norme} disabled={!peutGerer || enCours}
            onChange={(e) => setNorme(e.target.value)}
            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground">
            {NORMES.map((n) => <option key={n.valeur} value={n.valeur}>{n.libelle}</option>)}
          </select>
        </label>
        <label className="block" htmlFor="norme-reference">
          <span className="text-xs font-medium text-foreground">Référence de la norme</span>
          <input id="norme-reference" type="text" value={reference} disabled={!peutGerer || enCours}
            onChange={(e) => setReference(e.target.value)}
            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
        </label>
      </div>
      {peutGerer && (
        <button type="button" disabled={enCours} data-testid="acal397-norme-enregistrer"
          className="mt-4 text-sm font-semibold underline" onClick={enregistrer}>
          {enCours ? 'Enregistrement…' : 'Enregistrer la norme'}
        </button>
      )}
      {erreur && <p role="alert" className="mt-2 text-xs text-destructive" data-testid="acal397-norme-erreur">{erreur}</p>}
      {message && <p role="status" className="mt-3 text-sm text-muted-foreground" data-testid="acal397-norme-message">{message}</p>}
    </Card>
  )
}
