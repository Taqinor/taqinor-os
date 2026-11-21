import { useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { Button, Card } from '../../../ui'

/* ============================================================================
   ACAL561 — « RETRAITS PAR TYPE D'ARÊTE (en plus du retrait de pourtour) ».
   ----------------------------------------------------------------------------
   Section `degagements`, clé `retraits_par_arete` (`services/degagements.py`,
   contrat `parametres_calepinage.json`) : une ligne par type d'arête de
   l'atelier (`edges.ts::EDGE_TYPES` sans « inconnue »), mètres + SOURCE, vide
   par défaut — aucun retrait proposé. Le retrait d'une arête s'AJOUTE au
   retrait de pourtour (`roofSetbackEdge.ts`) : la carte le dit.

   LE SERVEUR REMPLACE LA SECTION `degagements` ENTIÈRE : l'envoi repart de la
   section TELLE QUE SERVIE (retrait de rive, allées, dégagements par type…)
   et ne change que `retraits_par_arete` — comme `PanneauAllees.jsx`. Un refus
   `degagements.retraits_par_arete[i].<clé>` se pose sous la ligne envoyée au
   rang `i`. Réglages société, niveau expert.
   ========================================================================== */

//: `services/degagements.py::TYPES_ARETE`, dans le même ordre.
const TYPES = [
  ['faitage', 'Faîtage'], ['noue', 'Noue'], ['arretier', 'Arêtier'],
  ['egout', 'Égout'], ['rive', 'Rive'],
]
const CLE = 'retraits_par_arete'
const CHAMP = 'mt-0.5 block min-h-[44px] w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground'

function lignesDepuis(servi) {
  const saisies = Array.isArray(servi?.[CLE]) ? servi[CLE] : []
  return Object.fromEntries(TYPES.map(([type]) => {
    const e = saisies.find((s) => s?.type === type)
    return [type, {
      retrait: e?.retrait_m == null ? '' : String(e.retrait_m),
      source: e?.source || '',
      reference: e?.reference || '',
    }]
  }))
}

export default function ReglagesRetraitsAretes({ servi, peutGerer }) {
  const [dernierServi, setDernierServi] = useState(servi ?? {})
  const [lignes, setLignes] = useState(() => lignesDepuis(servi))
  const [erreurs, setErreurs] = useState({})
  const [message, setMessage] = useState(null)
  const [envoi, setEnvoi] = useState(false)

  const changer = (type, champ) => (e) => setLignes((l) => ({ ...l, [type]: { ...l[type], [champ]: e.target.value } }))

  const enregistrer = async () => {
    setMessage(null)
    const envoyes = []
    const refus = {}
    for (const [type, libelle] of TYPES) {
      const { retrait, source, reference } = lignes[type]
      if (!retrait.trim() && !source.trim()) continue
      const metres = Number(retrait.trim().replace(',', '.'))
      if (!retrait.trim() || !Number.isFinite(metres)) {
        refus[type] = `« ${libelle} » : saisissez un retrait en mètres.`
        continue
      }
      envoyes.push({ type, retrait_m: metres, source: source.trim(), reference: reference.trim() })
    }
    if (Object.keys(refus).length > 0) { setErreurs(refus); return }
    const section = { ...dernierServi }
    if (envoyes.length > 0) section[CLE] = envoyes
    else delete section[CLE]
    setErreurs({})
    setEnvoi(true)
    try {
      const res = await calepinageApi.parametres.update({ degagements: section })
      const relu = res?.data?.degagements ?? section
      setDernierServi(relu)
      setLignes(lignesDepuis(relu))
      setMessage('Retraits par type d’arête enregistrés.')
    } catch (e) {
      const corps = e?.response?.data && typeof e.response.data === 'object' ? e.response.data : {}
      const parType = {}
      for (const [champ, motif] of Object.entries(corps)) {
        const rang = /retraits_par_arete\[(\d+)\]/.exec(champ)
        const type = rang ? envoyes[Number(rang[1])]?.type : null
        parType[type || '_general'] = Array.isArray(motif) ? motif.join(' ') : String(motif)
      }
      setErreurs(Object.keys(parType).length > 0 ? parType
        : { _general: 'Le serveur n’a rendu aucun motif : rien n’a été enregistré.' })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <Card className="mt-4 p-4" id="retraits-aretes" data-testid="acal561-carte">
      <h2 className="text-base font-semibold">Retraits par type d’arête (en plus du retrait de pourtour)</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Chaque valeur s’ajoute au retrait de pourtour sur les arêtes de ce type, avec sa source.
        Une ligne vide n’ajoute rien.
      </p>
      <ul className="mt-3 flex flex-col gap-3">
        {TYPES.map(([type, libelle]) => (
          <li key={type} className="grid gap-2 sm:grid-cols-3" data-testid={`acal561-ligne-${type}`}>
            <label className="text-sm">
              {`${libelle} (m)`}
              <input className={CHAMP} type="number" step="any" inputMode="decimal" disabled={!peutGerer}
                value={lignes[type].retrait} onChange={changer(type, 'retrait')} data-testid={`acal561-retrait-${type}`} />
            </label>
            <label className="text-sm">
              Source
              <input className={CHAMP} disabled={!peutGerer} value={lignes[type].source}
                onChange={changer(type, 'source')} data-testid={`acal561-source-${type}`} />
            </label>
            <label className="text-sm">
              Référence (facultative)
              <input className={CHAMP} disabled={!peutGerer} value={lignes[type].reference}
                onChange={changer(type, 'reference')} data-testid={`acal561-reference-${type}`} />
            </label>
            {erreurs[type] && (
              <p className="text-xs text-destructive sm:col-span-3" data-testid={`acal561-erreur-${type}`}>{erreurs[type]}</p>
            )}
          </li>
        ))}
      </ul>
      {erreurs._general && <p role="alert" className="mt-2 text-xs text-destructive">{erreurs._general}</p>}
      {message && <p role="status" className="mt-2 text-sm text-muted-foreground">{message}</p>}
      {peutGerer && (
        <Button type="button" className="mt-3" disabled={envoi} onClick={enregistrer} data-testid="acal561-enregistrer">
          {envoi ? 'Enregistrement…' : 'Enregistrer les retraits'}
        </Button>
      )}
    </Card>
  )
}
