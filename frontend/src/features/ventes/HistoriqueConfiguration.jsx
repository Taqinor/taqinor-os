// QJR553 (D-QJR5-7, contrat QJR513 `devis_historique_configuration.json`) —
// l'historique des versions d'un devis, visible dans l'Édition complète :
// liste des instantanés (date, auteur, nombre de lignes, total TTC), diff
// avec la version précédente (lignes ajoutées / retirées / modifiées,
// paramètres) et « Revenir à cette version ». Revenir n'a PAS d'endpoint
// propre : le parent recharge l'écran depuis le contenu de l'instantané puis
// passe par l'enregistrement NORMAL (replace-lines + entete + etude_params +
// jeton, QJR544 / QJR549). Jamais prix d'achat ni marge à l'écran.
import { useCallback, useEffect, useState } from 'react'
import { History } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { Button, Card, CardContent } from '../../ui'
import { formatDateTime, formatMAD, formatNumber } from '../../lib/format'

const LIBELLES = {
  quantite: 'Quantité',
  prix_unitaire: 'Prix unitaire',
  remise: 'Remise',
  taux_tva: 'TVA',
  designation: 'Désignation',
  variante: 'Option',
  optionnelle: 'Optionnelle',
  type_ligne: 'Type de ligne',
  ordre: 'Ordre',
  prix_manuel: 'Prix verrouillé',
  quantite_manuelle: 'Quantité verrouillée',
  groupe_label: 'Groupe',
  remise_globale: 'Remise globale',
  echeancier: 'Échéancier',
  scenario: 'Scénario',
  recommended_option: 'Option recommandée',
}

// Un nom de champ interne (coût, marge) ne s'affiche JAMAIS.
const INTERDIT = /prix_achat|marge/i

const libelle = (cle) => LIBELLES[cle] ?? cle

function valeurLisible(v) {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'boolean') return v ? 'oui' : 'non'
  if (typeof v === 'number' || (typeof v === 'string' && /^-?\d+(\.\d+)?$/.test(v))) {
    return formatNumber(Number(v))
  }
  if (typeof v === 'object') return 'modifié'
  return String(v)
}

function DiffVersions({ diff }) {
  if (!diff) return null
  const ajoutees = diff.ajoutees ?? []
  const retirees = diff.retirees ?? []
  const modifiees = diff.modifiees ?? []
  const parametres = Object.entries(diff.parametres ?? {}).filter(([k]) => !INTERDIT.test(k))
  if (!ajoutees.length && !retirees.length && !modifiees.length && !parametres.length) {
    return <p className="text-xs text-muted-foreground">Aucune différence.</p>
  }
  return (
    <ul className="space-y-1 text-xs" data-testid="historique-diff">
      {ajoutees.map(l => (
        <li key={`a-${l.cle}`}>+ Ajoutée : {l.designation || l.cle}</li>
      ))}
      {retirees.map(l => (
        <li key={`r-${l.cle}`}>− Retirée : {l.designation || l.cle}</li>
      ))}
      {modifiees.flatMap(l => Object.entries(l.champs ?? {})
        .filter(([champ]) => !INTERDIT.test(champ))
        .map(([champ, [avant, apres]]) => (
          <li key={`m-${l.cle}-${champ}`}>
            {l.designation ? `${l.designation} — ` : ''}
            {libelle(champ)} : {valeurLisible(avant)} → {valeurLisible(apres)}
          </li>
        )))}
      {parametres.map(([cle, [avant, apres]]) => (
        <li key={`p-${cle}`}>{libelle(cle)} : {valeurLisible(avant)} → {valeurLisible(apres)}</li>
      ))}
    </ul>
  )
}

/**
 * @param {number}   devisId     devis rouvert en Édition complète
 * @param {boolean}  peutRevenir verdict servi (QJR516) : sinon pas de bouton
 * @param {function} onRevenir   async (snapshot) — recharge l'écran depuis
 *                               `snapshot.contenu` et l'enregistre normalement
 * @param {any}      [rafraichir] change → la liste est relue (après un
 *                               enregistrement)
 */
export default function HistoriqueConfiguration({ devisId, peutRevenir, onRevenir, rafraichir }) {
  const [snapshots, setSnapshots] = useState([])
  const [diffs, setDiffs] = useState({})
  const [enCours, setEnCours] = useState(null)

  const charger = useCallback(() => {
    if (!devisId) return
    // Toute défaillance (réseau, client indisponible) → aucune liste, jamais
    // un écran d'édition cassé : l'historique est une aide, pas un préalable.
    Promise.resolve()
      .then(() => ventesApi.getHistoriqueConfigurationDevis(devisId))
      .then(r => setSnapshots(r?.data?.snapshots ?? []))
      .catch(() => setSnapshots([]))
  }, [devisId])

  useEffect(() => { charger() }, [charger, rafraichir])

  if (!devisId || !snapshots.length) return null

  // Plus récent en premier ; « précédente » = l'instantané juste avant.
  const ordonnes = [...snapshots].sort((a, b) => String(b.date).localeCompare(String(a.date)) || b.id - a.id)

  const comparer = async (snap, precedent) => {
    const { data } = await ventesApi.getHistoriqueConfigurationDevis(
      devisId, { a: precedent.id, b: snap.id })
    setDiffs(d => ({ ...d, [snap.id]: data?.diff ?? null }))
  }

  const revenir = async (snap) => {
    setEnCours(snap.id)
    try { await onRevenir?.(snap) } finally { setEnCours(null) }
  }

  return (
    <Card data-testid="historique-configuration">
      <CardContent className="pt-4 space-y-2">
        <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <History className="size-4" aria-hidden="true" /> Historique des versions
        </p>
        <ul className="divide-y divide-border rounded-md border border-border text-sm">
          {ordonnes.map((snap, i) => {
            const precedent = ordonnes[i + 1]
            const ttc = snap.contenu?.totaux?.ttc
            return (
              <li key={snap.id} className="space-y-1 px-3 py-2" data-testid={`historique-version-${snap.id}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{formatDateTime(snap.date)}</span>
                  <span className="text-muted-foreground">{snap.auteur || '—'}</span>
                  <span className="text-muted-foreground">{snap.nb_lignes} ligne(s)</span>
                  {ttc != null && <span>{formatMAD(ttc)} TTC</span>}
                  <span className="ml-auto flex gap-2">
                    {precedent && (
                      <Button type="button" size="xs" variant="outline"
                              onClick={() => comparer(snap, precedent)}>
                        Voir les différences
                      </Button>
                    )}
                    {peutRevenir && i > 0 && (
                      <Button type="button" size="xs" variant="outline"
                              disabled={enCours != null}
                              onClick={() => revenir(snap)}>
                        Revenir à cette version
                      </Button>
                    )}
                  </span>
                </div>
                {snap.id in diffs && <DiffVersions diff={diffs[snap.id]} />}
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}
