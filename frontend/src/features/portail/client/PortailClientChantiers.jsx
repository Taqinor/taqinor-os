import { useEffect, useState } from 'react'
import { HardHat } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, EmptyState, Input, Label, Spinner,
} from '../../../ui'
import { formatDate } from '../../../lib/format'

/* ============================================================================
   NTPRT14 — « Mes chantiers » (portail client authentifié).
   ----------------------------------------------------------------------------
   Timeline réutilisant la timeline PORTAIL déjà synchronisée (CHT10/CHT11,
   `apps.portail.selectors.jalons_du_chantier` — lecture seule) + galerie
   photos avant/pendant/après filtrée sur `records.Attachment`
   (`apps.installations.selectors.photos_chantier_client_portail`). AUCUNE
   donnée financière (BOM/prix exclus, contrat testé côté serveur). Le
   détail (jalons) et les photos sont chargés à la demande, quand le client
   ouvre le suivi d'un chantier — même patron que « Voir la preuve de
   livraison » (PortailClientLivraisons.jsx).
   ========================================================================== */

const TON_STATUT = {
  signe: 'neutral',
  materiel_commande: 'info',
  planifie: 'info',
  en_cours: 'warning',
  installe: 'info',
  receptionne: 'success',
  cloture: 'neutral',
}

// AGR614 — libellés FR du résultat de l'essai. Pas de traduction arabe
// disponible pour ce bloc : repli français documenté, comme le reste de
// l'onglet « Chantiers » (aucune clé i18n n'existe pour ces écrans).
const LABEL_RESULTAT_ESSAI = {
  en_cours: 'En cours',
  conforme: 'Conforme',
  reserves: 'Conforme avec réserves',
  non_conforme: 'Non conforme',
}

const LABEL_PHASE = { avant: 'Avant', pendant: 'Pendant', apres: 'Après' }
const ORDRE_PHASE = ['avant', 'pendant', 'apres']

function Timeline({ jalons }) {
  if (jalons.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucun jalon publié pour ce chantier pour le moment.
      </p>
    )
  }
  return (
    <ol className="flex flex-col gap-2">
      {jalons.map((j) => (
        <li key={j.id} className="flex items-center gap-2 text-sm">
          <span
            className="size-2.5 shrink-0 rounded-full"
            style={{
              background: j.atteint ? 'var(--success)' : 'var(--border)',
            }}
            aria-hidden="true"
          />
          <span className={j.atteint ? 'text-foreground' : 'text-muted-foreground'}>
            {j.libelle}
          </span>
          {j.date_jalon && (
            <span className="text-xs text-muted-foreground">
              {formatDate(j.date_jalon)}
            </span>
          )}
        </li>
      ))}
    </ol>
  )
}

// AGR614 — « Essai de mise en service » : rendu depuis `recette_pompage`
// (liste blanche client servie par le contrat `mes_chantiers_detail.json`).
// Jamais d'instrument, de prix ni de technicien ; rien quand c'est null.
function EssaiMiseEnService({ essai }) {
  if (!essai) return null
  const valeur = (v, unite) => (v == null ? '—' : `${v} ${unite}`)
  return (
    <section className="flex flex-col gap-1 rounded-lg border border-border p-3"
             data-testid="essai-mise-en-service">
      <h3 className="text-sm font-semibold">Essai de mise en service</h3>
      <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
        <dt className="text-muted-foreground">Date de l’essai</dt>
        <dd>{essai.date_essai ? formatDate(essai.date_essai) : '—'}</dd>
        <dt className="text-muted-foreground">HMT mesurée</dt>
        <dd>{valeur(essai.hmt_mesuree_m, 'm')}</dd>
        <dt className="text-muted-foreground">Débit mesuré</dt>
        <dd>{valeur(essai.debit_mesure_m3h, 'm³/h')}</dd>
        <dt className="text-muted-foreground">Débit estimé au devis</dt>
        <dd>{valeur(essai.debit_promis_m3h, 'm³/h')}</dd>
        <dt className="text-muted-foreground">Écart</dt>
        <dd>{valeur(essai.ecart_debit_pct, '%')}</dd>
        <dt className="text-muted-foreground">Résultat</dt>
        <dd>{LABEL_RESULTAT_ESSAI[essai.resultat] ?? essai.resultat ?? '—'}</dd>
      </dl>
      {essai.commentaire_ecart && (
        <p className="text-sm text-muted-foreground">{essai.commentaire_ecart}</p>
      )}
    </section>
  )
}

function Galerie({ photos }) {
  if (photos.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucune photo pour ce chantier pour le moment.
      </p>
    )
  }
  const parPhase = ORDRE_PHASE
    .map((phase) => ({ phase, items: photos.filter((p) => p.phase === phase) }))
    .concat([{ phase: null, items: photos.filter((p) => !p.phase) }])
    .filter((g) => g.items.length > 0)

  return (
    <div className="flex flex-col gap-3">
      {parPhase.map((groupe) => (
        <div key={groupe.phase || 'autre'}>
          {groupe.phase && (
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              {LABEL_PHASE[groupe.phase] || groupe.phase}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {groupe.items.map((p) => (
              <img
                key={p.id}
                src={p.url}
                alt={p.filename}
                loading="lazy"
                className="size-24 rounded border border-border object-cover"
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// AGR618 — « Relevés de ma pompe » : liste + formulaire. Le serveur calcule la
// moyenne par jour ; l'estimation du devis n'est comparée QUE si elle est
// fournie (jamais un chiffre inventé). Aucun prix.
const LABEL_TYPE_RELEVE = { heures: 'Heures de pompage', m3: 'm³ (compteur d’eau)' }
const UNITE_RELEVE = { heures: 'h', m3: 'm³' }

// Les 400 portail ne portent qu'un `detail` FR : on le range sous le champ
// que le message désigne (type d'abord : il cite aussi l'équipement).
function champDeLErreur(detail) {
  if (/type de relev/i.test(detail)) return 'type'
  if (/date/i.test(detail)) return 'date'
  if (/équipement/i.test(detail)) return 'equipement'
  return 'valeur'
}

function RelevesPompe({ chantierId, donnees, onEnregistre }) {
  const equipements = donnees?.equipements ?? []
  const releves = donnees?.releves ?? []
  const estime = donnees?.m3_jour_estime_devis ?? null
  const [equipement, setEquipement] = useState(equipements[0]?.id ?? '')
  const admis = equipements.find((e) => String(e.id) === String(equipement))
    ?.types_admis ?? []
  const [type, setType] = useState(admis[0] ?? '')
  const [valeur, setValeur] = useState('')
  const [date, setDate] = useState('')
  const [busy, setBusy] = useState(false)
  const [erreurs, setErreurs] = useState({})

  if (equipements.length === 0) return null

  const choisirEquipement = (id) => {
    setEquipement(id)
    const types = equipements.find((e) => String(e.id) === String(id))
      ?.types_admis ?? []
    if (!types.includes(type)) setType(types[0] ?? '')
  }

  const enregistrer = async () => {
    setBusy(true)
    setErreurs({})
    try {
      await portailApi.chantiers.ajouterReleve(chantierId, {
        equipement: Number(equipement),
        type: typeEffectif,
        valeur,
        date: date || undefined,
      })
      setValeur('')
      await onEnregistre()
    } catch (err) {
      const detail = err?.response?.data?.detail
        || 'Le relevé n’a pas pu être enregistré.'
      setErreurs({ [champDeLErreur(detail)]: detail })
    } finally {
      setBusy(false)
    }
  }

  const libelleEquipement = (id) => equipements
    .find((e) => e.id === id)?.libelle ?? ''
  const typeEffectif = admis.includes(type) ? type : (admis[0] ?? '')
  // Moyenne du relevé m³ le plus récent qui en porte une, comparée au m³/jour
  // du devis SEULEMENT quand ce dernier est fourni.
  const dernierM3 = releves.find((r) => r.type === 'm3'
    && r.moyenne_jour_depuis_precedent != null)

  const erreur = (cle) => (erreurs[cle]
    ? <p className="form-error text-xs" role="alert" data-testid={`releve-erreur-${cle}`}>{erreurs[cle]}</p>
    : null)

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border p-3"
             data-testid="releves-pompe">
      <h3 className="text-sm font-semibold">Relevés de ma pompe</h3>

      {releves.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucun relevé pour le moment.</p>
      ) : (
        <ul className="flex flex-col gap-1" data-testid="releves-liste">
          {releves.map((r) => (
            <li key={`${r.equipement}-${r.type}-${r.date}-${r.valeur}`} className="text-sm">
              <span className="font-medium">{libelleEquipement(r.equipement)}</span>
              {' — '}
              {r.valeur} {UNITE_RELEVE[r.type] ?? r.type}
              {' le '}{formatDate(r.date)}
              {r.moyenne_jour_depuis_precedent != null && (
                <span className="text-muted-foreground">
                  {' '}(≈ {r.moyenne_jour_depuis_precedent} {UNITE_RELEVE[r.type] ?? r.type}/jour depuis le relevé précédent)
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {estime != null && dernierM3 && (
        <p className="text-sm" data-testid="releves-comparaison">
          Moyenne relevée : ≈ {dernierM3.moyenne_jour_depuis_precedent} m³/jour
          {' — '}m³/jour estimé au devis : {estime}
        </p>
      )}

      <form noValidate className="grid gap-3 sm:grid-cols-2"
            onSubmit={(e) => e.preventDefault()}>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`rel-eq-${chantierId}`}>Équipement</Label>
          <select id={`rel-eq-${chantierId}`} className="form-control"
                  value={equipement}
                  onChange={(e) => choisirEquipement(e.target.value)}>
            {equipements.map((e) => (
              <option key={e.id} value={e.id}>{e.libelle}</option>
            ))}
          </select>
          {erreur('equipement')}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`rel-type-${chantierId}`}>Type de relevé</Label>
          <select id={`rel-type-${chantierId}`} className="form-control"
                  value={typeEffectif}
                  onChange={(e) => setType(e.target.value)}>
            {admis.map((t) => (
              <option key={t} value={t}>{LABEL_TYPE_RELEVE[t] ?? t}</option>
            ))}
          </select>
          {erreur('type')}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`rel-val-${chantierId}`}>Index du compteur</Label>
          <Input id={`rel-val-${chantierId}`} type="number" step="any"
                 value={valeur} onChange={(e) => setValeur(e.target.value)} />
          {erreur('valeur')}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`rel-date-${chantierId}`}>Date du relevé</Label>
          <Input id={`rel-date-${chantierId}`} type="date" value={date}
                 onChange={(e) => setDate(e.target.value)} />
          {erreur('date')}
        </div>
        <div className="sm:col-span-2">
          <Button type="button" size="sm" loading={busy} onClick={enregistrer}>
            Enregistrer le relevé
          </Button>
        </div>
      </form>
    </section>
  )
}

export default function PortailClientChantiers() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  // État par chantier : { etat: 'chargement'|'ok'|'erreur', jalons, photos }.
  const [suivis, setSuivis] = useState({})

  const charger = () => {
    setLoading(true)
    portailApi.chantiers.liste()
      .then((r) => { setRows(r.data?.results ?? []); setErreur(false) })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  const voirSuivi = (id) => {
    setSuivis((etat) => ({ ...etat, [id]: { etat: 'chargement' } }))
    Promise.all([
      portailApi.chantiers.detail(id),
      portailApi.chantiers.photos(id),
      // AGR618 — les relevés sont un plus : un échec ne casse pas le suivi.
      Promise.resolve()
        .then(() => portailApi.chantiers.releves(id))
        .then((r) => r.data)
        .catch(() => null),
    ])
      .then(([detail, photos, releves]) => setSuivis((etat) => ({
        ...etat,
        [id]: {
          etat: 'ok',
          releves,
          jalons: detail.data?.jalons ?? [],
          recette: detail.data?.recette_pompage ?? null,
          photos: photos.data?.results ?? [],
        },
      })))
      .catch(() => setSuivis((etat) => (
        { ...etat, [id]: { etat: 'erreur' } })))
  }

  const rechargerReleves = async (id) => {
    const r = await portailApi.chantiers.releves(id)
    setSuivis((etat) => ({
      ...etat, [id]: { ...etat[id], releves: r.data },
    }))
  }

  useEffect(() => {
    // Différé d'un microtask : même patron que PortailClientDevis/Factures/
    // Livraisons (évite react-hooks/set-state-in-effect).
    Promise.resolve().then(charger)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de vos chantiers…
      </div>
    )
  }

  if (erreur) {
    return (
      <EmptyState
        title="Chantiers indisponibles"
        description="Vos chantiers n’ont pas pu être chargés. Réessayez plus tard."
      />
    )
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <HardHat className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes chantiers
        </h1>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="Aucun chantier"
          description="Vous n’avez aucun chantier pour le moment."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((c) => (
            <Card key={c.id} className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{c.reference}</p>
                  <p className="text-xs text-muted-foreground">
                    {c.site_ville || 'Ville non renseignée'}
                    {' — '}
                    Créé le {formatDate(c.date_creation)}
                  </p>
                </div>
                <Badge tone={TON_STATUT[c.statut] || 'neutral'}>
                  {c.statut_display}
                </Badge>
              </div>

              {!suivis[c.id] && (
                <div>
                  <Button variant="outline" size="sm"
                          onClick={() => voirSuivi(c.id)}>
                    Voir le suivi
                  </Button>
                </div>
              )}
              {suivis[c.id]?.etat === 'chargement' && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Spinner /> Chargement du suivi…
                </div>
              )}
              {suivis[c.id]?.etat === 'erreur' && (
                <p className="text-sm text-muted-foreground">
                  Le suivi de ce chantier n’a pas pu être affiché.
                </p>
              )}
              {suivis[c.id]?.etat === 'ok' && (
                <div className="flex flex-col gap-4">
                  <Timeline jalons={suivis[c.id].jalons} />
                  <EssaiMiseEnService essai={suivis[c.id].recette} />
                  <RelevesPompe
                    chantierId={c.id}
                    donnees={suivis[c.id].releves}
                    onEnregistre={() => rechargerReleves(c.id)}
                  />
                  <Galerie photos={suivis[c.id].photos} />
                </div>
              )}
            </Card>
          ))}
        </ul>
      )}
    </>
  )
}
