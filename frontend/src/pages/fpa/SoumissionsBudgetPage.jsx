import { useCallback, useEffect, useState } from 'react'
import { Badge, Button, Card, EmptyState, Textarea, toast } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import ChatterTimeline from '../../components/ChatterTimeline'
import fpaApi from '../../api/fpaApi'

/* ============================================================================
   PACT53 — Écran « Soumissions budgétaires » (`/fpa/soumissions`).
   ----------------------------------------------------------------------------
   `fpa.SoumissionBudgetDepartement` (NTFPA5) porte le workflow de validation
   d'un budget de département — en saisie → soumis → validé ou rejeté — avec
   son fil de discussion horodaté. Le module FP&A existait entièrement
   (tableau de bord, saisie, prévisions, scénarios, écarts) mais AUCUNE de ses
   5 pages ne mentionnait « soumission » : la saisie fonctionnait, son statut
   de validation formel était invisible.

   Cet écran rend le workflow visible et son fil UTILISABLE : on liste les
   soumissions de la société (lecture seule côté ViewSet — les transitions
   restent portées par les actions de `lignes-budget-departement`), on ouvre
   une soumission, on lit son fil et on y ajoute une note. L'auteur et
   l'horodatage viennent du SERVEUR (jamais du client) et sont rendus par le
   composant de chatter commun `ChatterTimeline`, comme partout ailleurs.
   ========================================================================== */

const STATUT_LABELS = {
  en_saisie: 'En saisie',
  soumis: 'Soumis',
  valide: 'Validé',
  rejete: 'Rejeté',
}

const STATUT_TONS = {
  en_saisie: 'neutral',
  soumis: 'info',
  valide: 'success',
  rejete: 'danger',
}

function listeDe(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}

function messageErreur(err, repli) {
  const data = err?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (typeof data === 'string' && data) return data
  return repli
}

/* Le contrat de chatter du serveur (ARC8/9) est
   `kind/body/user_username/created_at` ; `ChatterTimeline` lit `user_nom` —
   même adaptation que `features/ao/AffaireDetail.jsx`. */
function enEntreesChatter(data) {
  return listeDe(data).map((a) => ({
    id: a.id,
    kind: a.kind,
    field: a.field,
    field_label: a.field_label,
    old_value: a.old_value,
    new_value: a.new_value,
    body: a.body,
    user_nom: a.user_username,
    created_at: a.created_at,
  }))
}

function libelle(collection, id, prefixe) {
  const item = collection.find((x) => String(x.id) === String(id))
  return item ? (item.nom || `${prefixe} #${id}`) : `${prefixe} #${id}`
}

export default function SoumissionsBudgetPage() {
  const [soumissions, setSoumissions] = useState([])
  const [departements, setDepartements] = useState([])
  const [cycles, setCycles] = useState([])
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState('')
  const [ouverte, setOuverte] = useState(null)
  const [fil, setFil] = useState([])
  const [note, setNote] = useState('')
  const [occupe, setOccupe] = useState(false)

  const charger = useCallback(async () => {
    setChargement(true)
    try {
      const res = await fpaApi.getSoumissions()
      setSoumissions(listeDe(res?.data))
      setErreur('')
    } catch (err) {
      setErreur(messageErreur(err, 'Soumissions indisponibles.'))
      setSoumissions([])
    } finally {
      setChargement(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { charger() }, [charger])

  useEffect(() => {
    let vivant = true
    fpaApi.getDepartements()
      .then((res) => { if (vivant) setDepartements(listeDe(res?.data)) })
      .catch(() => { if (vivant) setDepartements([]) })
    fpaApi.getCycles()
      .then((res) => { if (vivant) setCycles(listeDe(res?.data)) })
      .catch(() => { if (vivant) setCycles([]) })
    return () => { vivant = false }
  }, [])

  const ouvrir = useCallback(async (soumission) => {
    setOuverte(soumission)
    setNote('')
    try {
      const res = await fpaApi.getSoumissionHistorique(soumission.id)
      setFil(enEntreesChatter(res?.data))
    } catch (err) {
      setFil([])
      toast.error(messageErreur(err, 'Fil de discussion indisponible.'))
    }
  }, [])

  async function ajouterNote() {
    if (!ouverte || occupe) return
    const texte = note.trim()
    if (!texte) {
      toast.error('Écrivez une note avant de la publier.')
      return
    }
    setOccupe(true)
    try {
      const res = await fpaApi.noterSoumission(ouverte.id, texte)
      const creee = enEntreesChatter([res?.data])
      // La note publiée rejoint immédiatement le HAUT du fil (le serveur trie
      // du plus récent au plus ancien) avec son auteur et son horodatage tels
      // que le serveur les a posés.
      setFil((f) => [...creee, ...f])
      setNote('')
      toast.success('Note publiée.')
    } catch (err) {
      toast.error(messageErreur(err, 'Publication impossible.'))
    } finally {
      setOccupe(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Soumissions budgétaires"
        subtitle="Statut de validation du budget de chaque département (en saisie → soumis → validé/rejeté) et son fil de discussion (NTFPA5)."
      />

      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="text-sm font-medium text-foreground">Soumissions</h3>
        {chargement && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {!chargement && erreur && <EmptyState title="Erreur" description={erreur} />}
        {!chargement && !erreur && soumissions.length === 0 && (
          <EmptyState
            title="Aucune soumission"
            description="Aucun budget de département n'a encore été soumis à validation."
          />
        )}
        {!chargement && !erreur && soumissions.length > 0 && (
          <ul className="flex flex-col gap-2" data-testid="fpa-soum-liste">
            {soumissions.map((s) => (
              <li
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">
                    {libelle(departements, s.departement, 'Département')}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {libelle(cycles, s.cycle, 'Cycle')}
                  </span>
                  <Badge tone={STATUT_TONS[s.statut] || 'neutral'}>
                    {STATUT_LABELS[s.statut] || s.statut}
                  </Badge>
                  {s.statut === 'rejete' && s.motif_rejet && (
                    <span className="text-xs text-muted-foreground">{s.motif_rejet}</span>
                  )}
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => ouvrir(s)}
                  data-testid={`fpa-soum-ouvrir-${s.id}`}
                >
                  Ouvrir le fil
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {ouverte && (
        <Card className="flex flex-col gap-3 p-4 sm:p-5" data-testid="fpa-soum-fil">
          <h3 className="text-sm font-medium text-foreground">
            Fil — {libelle(departements, ouverte.departement, 'Département')}
          </h3>

          <div className="flex flex-col gap-2">
            <Textarea
              placeholder="Ajouter une note au fil…"
              aria-label="Nouvelle note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
            <div>
              <Button onClick={ajouterNote} disabled={occupe} data-testid="fpa-soum-noter">
                Publier la note
              </Button>
            </div>
          </div>

          <ChatterTimeline
            entries={fil}
            emptyLabel="Aucune entrée dans ce fil pour le moment."
          />
        </Card>
      )}
    </div>
  )
}
