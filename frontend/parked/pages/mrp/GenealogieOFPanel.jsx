// NTMFG20 — Traçabilité amont/aval par lot de fabrication (généalogie),
// vue arbre embarquée dans le détail d'un OF (OrdresFabricationPage.jsx) :
// amont = composants consommés et l'OF qui les a produits ; aval = OF qui
// ont consommé le produit fabriqué par CET OF. Lecture seule.
import { useState } from 'react'
import { GitBranch } from 'lucide-react'
import mrpApi from '../../api/mrpApi'
import { Button, Spinner } from '../../ui'

function AmontTree({ lignes }) {
  if (!lignes?.length) {
    return <div className="text-xs text-muted-foreground">Aucun composant consommé.</div>
  }
  return (
    <ul className="pl-3 border-l ml-1">
      {lignes.map((l, i) => (
        <li key={`${l.produit_id}-${i}`} className="text-sm py-0.5">
          {l.produit_nom} × {l.quantite}
          {l.of_source && (
            <>
              {' '}— produit par OF-{l.of_source.of_id}
              {l.of_source.amont?.length > 0 && <AmontTree lignes={l.of_source.amont} />}
            </>
          )}
        </li>
      ))}
    </ul>
  )
}

function AvalTree({ ofs }) {
  if (!ofs?.length) {
    return <div className="text-xs text-muted-foreground">Aucun OF consommateur en aval.</div>
  }
  return (
    <ul className="pl-3 border-l ml-1">
      {ofs.map((o) => (
        <li key={o.of_id} className="text-sm py-0.5">
          OF-{o.of_id} ({o.statut})
          {o.kit_ordre_assemblage_id && <> — lié à l'assemblage kitting #{o.kit_ordre_assemblage_id}</>}
          {o.aval?.length > 0 && <AvalTree ofs={o.aval} />}
        </li>
      ))}
    </ul>
  )
}

export default function GenealogieOFPanel({ ofId }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [data, setData] = useState(null)

  const toggle = async () => {
    if (open) { setOpen(false); return }
    setOpen(true)
    if (data) return
    setBusy(true)
    try {
      const resp = await mrpApi.getGenealogieOF(ofId)
      setData(resp.data)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-3">
      <Button variant="outline" size="sm" onClick={toggle}
              title="Traçabilité amont (composants) / aval (consommateurs) de cet OF">
        <GitBranch size={14} /> Généalogie
      </Button>
      {open && (
        <div className="mt-2 border rounded-lg p-2">
          {busy && <Spinner />}
          {!busy && data && (
            <>
              <div className="text-xs font-medium uppercase text-muted-foreground mb-1">
                Amont (composants)
              </div>
              <AmontTree lignes={data.amont} />
              <div className="text-xs font-medium uppercase text-muted-foreground mt-2 mb-1">
                Aval (consommateurs)
              </div>
              <AvalTree ofs={data.aval} />
            </>
          )}
        </div>
      )}
    </div>
  )
}
