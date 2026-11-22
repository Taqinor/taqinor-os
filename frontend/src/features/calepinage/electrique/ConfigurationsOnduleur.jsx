import { useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { formatNumber } from '../../../lib/format'
import { Badge, Button, Spinner } from '../../../ui'
import { refusParChamp } from './entreeElectrique'

/* ============================================================================
   ACAL617 — « COMPARER AVEC D'AUTRES ONDULEURS » sous le champ Onduleur.
   `GET configurations-onduleur/` (contrat `calepinage_configurations_onduleur.json`, ACAL616)
   rend 1 à 3 cartes évaluées par le serveur : AUCUN chiffre n'est calculé ici (ratio, entrées
   utilisées, phrases `bloquants` / `alertes` / `manquantes` : tels que servis). « Appliquer »
   enregistre CET onduleur par l'entrée électrique existante (les trois désignations de
   l'écran, `onduleur_produit` remplacé), puis l'écran relit l'entrée et les cartes.
   ========================================================================== */

const PASTILLES = {
  conforme: { tone: 'success', texte: 'Conforme' },
  alerte: { tone: 'warning', texte: 'À surveiller' },
  bloquant: { tone: 'danger', texte: 'Ne convient pas' },
  indetermine: { tone: 'neutral', texte: 'Fiche à compléter' },
}

const nombre = (v, decimals) => (v === null || v === undefined ? 'non calculable' : formatNumber(v, { decimals }))

export default function ConfigurationsOnduleur({ calepinageId, designations, lectureSeule = false, apresApplication = null }) {
  const [donnees, setDonnees] = useState(null)
  const [ouvert, setOuvert] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(false)

  const charger = () => calepinageApi.calepinages.configurationsOnduleur(calepinageId)
    .then((res) => { setDonnees(res?.data ?? null); setErreur(null) })
    .catch(() => setErreur('Comparaison indisponible.'))

  const comparer = () => { setOuvert(true); charger() }

  const appliquer = (produitId) => {
    setEnCours(true)
    setErreur(null)
    calepinageApi.calepinages.enregistrerEntreeElectrique(calepinageId, { ...designations, onduleur_produit: produitId })
      .then(() => Promise.all([apresApplication ? apresApplication() : null, charger()]))
      .catch((err) => {
        const parChamp = refusParChamp(err?.response?.data)
        setErreur(parChamp.onduleur_produit || Object.values(parChamp)[0] || 'Onduleur non enregistré : le serveur a refusé ce choix.')
      })
      .finally(() => setEnCours(false))
  }

  return (
    <div data-testid="acal617-comparer">
      <button type="button" onClick={comparer} data-testid="acal617-lien"
        className="inline-flex min-h-11 items-center text-sm font-semibold text-primary-text underline">
        Comparer avec d’autres onduleurs
      </button>
      {ouvert && !donnees && !erreur && <Spinner />}
      {erreur && <p role="alert" className="text-sm text-destructive" data-testid="acal617-erreur">{erreur}</p>}
      {donnees?.motif_vide && <p className="text-sm text-muted-foreground" data-testid="acal617-vide">{donnees.motif_vide}</p>}
      <ul className="mt-2 flex flex-col gap-3">
        {(donnees?.configurations ?? []).map((c) => {
          const pastille = PASTILLES[c.verdict] ?? PASTILLES.indetermine
          const retenue = c.role === 'retenue'
          return (
            <li key={c.produit_id} className="rounded border border-border p-3" data-testid={`acal617-carte-${c.produit_id}`}>
              <div className="flex flex-wrap items-center gap-2">
                <strong className="text-sm text-foreground">{c.libelle}{c.marque ? ` (${c.marque})` : ''}</strong>
                <Badge tone={pastille.tone}>{pastille.texte}</Badge>
                {retenue && <Badge tone="primary" data-testid="acal617-retenu">Retenu</Badge>}
              </div>
              <p className="mt-1 text-sm text-foreground">
                {nombre(c.nombre_onduleurs, 0)} onduleur(s) de {nombre(c.puissance_ac_totale_kw, 1)} kW
                {' · '}Rapport DC/AC {nombre(c.ratio_dc_ac, 2)}
                {' · '}Entrées utilisées {nombre(c.mppt_utilises, 0)} sur {nombre(c.mppt_disponibles, 0)}
              </p>
              {[...(c.bloquants ?? []), ...(c.alertes ?? []), ...(c.manquantes ?? [])].map((phrase) => (
                <p key={phrase} className="text-sm text-muted-foreground">{phrase}</p>
              ))}
              {!retenue && (
                <Button type="button" disabled={lectureSeule || enCours} onClick={() => appliquer(c.produit_id)}
                  className="mt-2 min-h-11" data-testid={`acal617-appliquer-${c.produit_id}`}>
                  Appliquer
                </Button>
              )}
            </li>
          )
        })}
      </ul>
      {(donnees?.fiches_incompletes ?? []).map((f) => (
        <p key={f.produit_id} className="mt-1 text-sm text-muted-foreground" data-testid={`acal617-fiche-${f.produit_id}`}>
          {f.libelle} : fiche à compléter ({(f.champs_manquants ?? []).join(', ')}).
        </p>
      ))}
    </div>
  )
}
