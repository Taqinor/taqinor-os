import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Package, ShoppingCart, ClipboardList, TriangleAlert, Boxes } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import { toast } from '../../ui/confirm'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Checkbox, StatusPill } from '../../ui'
import { Skeleton } from '../../ui/Skeleton'
import TableauDefilant from '../../ui/TableauDefilant'

/* Onglet « Matériel & BC » du chantier — UNE réponse serveur
   (`GET chantiers/<id>/approvisionnement/`, contrat
   `contract_samples/chantier_approvisionnement.json`) au lieu du trio
   « Calculer le besoin » / toast BCF / BCF introuvable : ce qui manque, ce qui
   est commandé, ce qui est arrivé, et « prêt à poser ? ». Aucun prix ici
   (prix d'achat masqués, D-ASTK-2).

   Les données sont chargées par la fiche (un seul fetch partagé avec la carte
   « Prêt à poser ? » de l'Aperçu) et passées en props. */

const plur = (n, un, plusieurs) => `${n} ${n > 1 ? plusieurs : un}`

function Bloc({ icon: Icon, title, children }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="flex items-center gap-2 text-sm">
          {Icon && <Icon className="size-4 text-muted-foreground" aria-hidden="true" />}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">{children}</CardContent>
    </Card>
  )
}

const Vide = ({ children }) => <p className="text-sm text-muted-foreground">{children}</p>

function Tableau({ head, children }) {
  return (
    <TableauDefilant enveloppe="overflow-x-auto rounded-lg border border-border" className="w-full border-collapse text-sm">
      <thead className="bg-muted/60">
        <tr>
          {head.map((h) => (
            <th key={h || 'vide'} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </TableauDefilant>
  )
}

/** Cellule « En commande » : brouillon (muted, ne sécurise rien) / en route. */
function EnCommande({ ligne }) {
  const brouillon = Number(ligne.en_commande_brouillon) || 0
  const envoye = Number(ligne.en_commande_envoye) || 0
  if (!brouillon && !envoye) return <span className="text-muted-foreground">—</span>
  return (
    <span className="flex flex-col gap-0.5">
      {envoye > 0 && <span>{envoye} en route</span>}
      {brouillon > 0 && <span className="text-xs text-muted-foreground">brouillon {brouillon}</span>}
    </span>
  )
}

export function ApprovisionnementSkeleton() {
  return (
    <div className="flex flex-col gap-3" role="status" aria-label="Chargement du matériel">
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-20 w-full" />
    </div>
  )
}

/** Chips de synthèse + verdict « Prêt à poser ». Réutilisé par l'Aperçu. */
export function ResumeApprovisionnement({ resume }) {
  if (!resume) return null
  const raisons = resume.raisons ?? []
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={resume.nb_manques > 0 ? 'danger' : 'success'}>
          {resume.nb_manques > 0 ? plur(resume.nb_manques, 'manque', 'manques') : 'Aucun manque'}
        </Badge>
        <Badge tone={resume.nb_en_commande > 0 ? 'info' : 'neutral'}>
          {plur(resume.nb_en_commande, 'article en commande', 'articles en commande')}
        </Badge>
        <Badge tone={resume.nb_recues > 0 ? 'success' : 'neutral'}>
          {plur(resume.nb_recues, 'article reçu', 'articles reçus')}
        </Badge>
        <Badge
          tone={resume.pret_a_poser ? 'success' : 'warning'}
          title={raisons.join(' · ') || undefined}
        >
          {resume.pret_a_poser ? 'Prêt à poser' : 'Pas encore prêt à poser'}
        </Badge>
      </div>
      {!resume.pret_a_poser && raisons.length > 0 && (
        <ul className="list-disc pl-5 text-sm text-muted-foreground">
          {raisons.map((r) => <li key={r}>{r}</li>)}
        </ul>
      )}
    </div>
  )
}

export default function ChantierApprovisionnement({
  chantierId, data, loading = false, error = null, onReload, onChantierChange,
}) {
  const [selection, setSelection] = useState(() => new Set())
  const [busy, setBusy] = useState(false)
  const [resultat, setResultat] = useState(null)
  const [erreurCommande, setErreurCommande] = useState(null)

  const lignes = useMemo(() => {
    const l = [...(data?.lignes ?? [])]
    l.sort((a, b) => (b.manque - a.manque) || String(a.designation).localeCompare(String(b.designation), 'fr'))
    return l
  }, [data])

  if (loading && !data) return <ApprovisionnementSkeleton />
  if (error && !data) {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
        <TriangleAlert className="size-4" aria-hidden="true" />
        <span>{error}</span>
        {onReload && <Button size="sm" variant="outline" onClick={onReload}>Réessayer</Button>}
      </div>
    )
  }
  if (!data) return null

  const afficherSorti = lignes.some((l) => Number(l.deja_sorti) > 0)
  const enManque = lignes.filter((l) => l.manque > 0)
  const nbACommander = selection.size > 0
    ? enManque.filter((l) => selection.has(l.produit_id)).length
    : enManque.length

  const basculer = (produitId, coche) => setSelection((s) => {
    const n = new Set(s)
    if (coche) n.add(produitId); else n.delete(produitId)
    return n
  })

  const commander = async () => {
    const produits = selection.size > 0
      ? enManque.filter((l) => selection.has(l.produit_id)).map((l) => l.produit_id)
      : enManque.map((l) => l.produit_id)
    if (!produits.length) return
    setBusy(true)
    setErreurCommande(null)
    try {
      const r = await installationsApi.commanderBesoin(chantierId, { produits })
      const res = r.data ?? {}
      setResultat(res)
      setSelection(new Set())
      if (res.statut_chantier && res.statut_chantier !== data.statut) {
        toast.success('Chantier passé à Matériel commandé')
        onChantierChange?.()
      }
      onReload?.()
    } catch (e) {
      const msg = e?.response?.data?.detail || 'Création des bons de commande impossible.'
      setErreurCommande(msg)
      toast.error(msg)
    } finally {
      setBusy(false)
    }
  }

  const bons = data.bons_commande ?? []
  const das = data.demandes_achat ?? []
  const resas = data.reservations ?? []

  return (
    <div className="flex flex-col gap-4">
      <ResumeApprovisionnement resume={data.resume} />
      {error && (
        <p role="alert" className="text-sm text-destructive">
          Actualisation impossible : {error}
        </p>
      )}

      <Bloc icon={Package} title="Besoin matériel">
        {lignes.length === 0 ? (
          <Vide>Aucune ligne de matériel : ce chantier n&apos;a pas de nomenclature gelée (créé sans devis ?).</Vide>
        ) : (
          <>
            <Tableau
              head={[
                '',
                'Article',
                'Requis',
                ...(afficherSorti ? ['Déjà sorti'] : []),
                'Réservé (ce chantier)',
                'Dispo',
                'En commande',
                'Reçu',
                'Manque',
                'Fournisseur',
              ]}
            >
              {lignes.map((l) => (
                <tr key={l.produit_id} className={`border-t border-border ${l.manque > 0 ? 'bg-destructive/5' : ''}`}>
                  <td className="px-3 py-2">
                    {l.manque > 0 && (
                      <Checkbox
                        aria-label={`Sélectionner ${l.designation}`}
                        checked={selection.has(l.produit_id)}
                        onCheckedChange={(c) => basculer(l.produit_id, c === true)}
                      />
                    )}
                  </td>
                  <td className="px-3 py-2">{l.designation}</td>
                  <td className="px-3 py-2">{l.requis}</td>
                  {afficherSorti && <td className="px-3 py-2">{l.deja_sorti > 0 ? l.deja_sorti : '—'}</td>}
                  <td className="px-3 py-2">{l.reserve_chantier > 0 ? l.reserve_chantier : '—'}</td>
                  <td className="px-3 py-2">{l.disponible}</td>
                  <td className="px-3 py-2"><EnCommande ligne={l} /></td>
                  <td className="px-3 py-2">{l.recu > 0 ? l.recu : '—'}</td>
                  <td className="px-3 py-2">
                    {l.manque > 0 ? <Badge tone="danger">{l.manque}</Badge> : <span className="text-muted-foreground">—</span>}
                  </td>
                  <td className="px-3 py-2">
                    {l.fournisseur_nom
                      || (l.manque > 0
                        ? <span className="text-xs text-warning">à renseigner</span>
                        : <span className="text-muted-foreground">—</span>)}
                  </td>
                </tr>
              ))}
            </Tableau>
            {enManque.length > 0 ? (
              <Button size="sm" className="self-start" onClick={commander} loading={busy} disabled={nbACommander === 0}>
                <ShoppingCart className="size-4" aria-hidden="true" />
                Commander les manques ({nbACommander})
              </Button>
            ) : (
              <Vide>Aucun manque : tout le matériel est couvert par le stock ou les commandes envoyées.</Vide>
            )}
          </>
        )}

        {erreurCommande && (
          <p role="alert" className="text-sm text-destructive">{erreurCommande}</p>
        )}
        {resultat && (
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3 text-sm" role="status">
            {(resultat.bons_commande ?? []).length > 0 && (
              <>
                <p className="font-medium">
                  {plur(resultat.bons_commande.length, 'bon de commande créé', 'bons de commande créés')} (brouillon, à envoyer au fournisseur) :
                </p>
                <ul className="flex flex-col gap-1">
                  {resultat.bons_commande.map((b) => (
                    <li key={b.id} className="flex flex-wrap items-center gap-2">
                      <Link
                        to="/stock/bons-commande-fournisseur"
                        state={{ ouvrirBcfId: b.id }}
                        className="font-medium text-primary underline-offset-2 hover:underline"
                      >
                        {b.reference}
                      </Link>
                      <span className="text-muted-foreground">— {b.fournisseur_nom ?? 'fournisseur à choisir'}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {(resultat.sans_fournisseur ?? []).length > 0 && (
              <p className="flex items-start gap-2 text-warning">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                <span>
                  Sans fournisseur : {resultat.sans_fournisseur.map((s) => s.designation).join(', ')}
                  {' '}(ajoutez un fournisseur au produit).
                </span>
              </p>
            )}
          </div>
        )}
      </Bloc>

      <Bloc icon={ShoppingCart} title="Bons de commande fournisseur du chantier">
        {bons.length === 0 ? (
          <Vide>Aucun bon de commande fournisseur lié à ce chantier.</Vide>
        ) : (
          <Tableau head={['Référence', 'Statut', 'Fournisseur', 'Commandé / reçu']}>
            {bons.map((b) => {
              const cmd = Number(b.quantite_commandee) || 0
              const recu = Number(b.quantite_recue) || 0
              const pct = cmd > 0 ? Math.min(100, Math.round((recu / cmd) * 100)) : 0
              return (
                <tr key={b.id} className="border-t border-border">
                  <td className="px-3 py-2">
                    <Link
                      to="/stock/bons-commande-fournisseur"
                      state={{ ouvrirBcfId: b.id }}
                      className="font-medium text-primary underline-offset-2 hover:underline"
                    >
                      {b.reference}
                    </Link>
                  </td>
                  <td className="px-3 py-2"><StatusPill status={b.statut} label={b.statut_display ?? b.statut} /></td>
                  <td className="px-3 py-2">{b.fournisseur_nom ?? '—'}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div
                        className="h-2 w-24 overflow-hidden rounded-full bg-muted"
                        role="progressbar"
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={pct}
                        aria-label={`Réception ${b.reference}`}
                      >
                        <div className="h-full bg-success" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-xs text-muted-foreground">{recu} / {cmd}</span>
                    </div>
                  </td>
                </tr>
              )
            })}
          </Tableau>
        )}
      </Bloc>

      <Bloc icon={ClipboardList} title="Demandes d'achat">
        {das.length === 0 ? (
          <Vide>Aucune demande d&apos;achat pour ce chantier.</Vide>
        ) : (
          <Tableau head={['Référence', 'Objet', 'Statut']}>
            {das.map((d) => (
              <tr key={d.id} className="border-t border-border">
                <td className="px-3 py-2">
                  <Link
                    to={`/chantiers/demandes-achat?chantier=${chantierId}`}
                    className="font-medium text-primary underline-offset-2 hover:underline"
                  >
                    {d.reference}
                  </Link>
                </td>
                <td className="px-3 py-2">{d.objet || '—'}</td>
                <td className="px-3 py-2"><StatusPill status={d.statut} label={d.statut_display ?? d.statut} /></td>
              </tr>
            ))}
          </Tableau>
        )}
      </Bloc>

      <Bloc icon={Boxes} title="Réservations">
        {resas.length === 0 ? (
          <Vide>Aucune réservation de stock active pour ce chantier.</Vide>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {resas.map((r) => (
              <li key={`${r.produit_id}-${r.statut}`}>
                <Badge tone="outline">{r.quantite} × {r.designation}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Bloc>
    </div>
  )
}
