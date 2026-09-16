import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Radar, ShieldAlert } from 'lucide-react'
import crmApi from '../../api/crmApi'
import {
  Card, CardContent, Badge, Spinner, Button, Input, Label,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, toast,
} from '../../ui'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { frenchError } from '../../lib/frenchError'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   VIS1 (fondateur 14/09/2026) — écran « Visiteurs & alertes » (`/crm/
   visiteurs`) : les notifications anti-fraude (« un même appareil consulte
   plusieurs prospects », « devis ouvert par le client »…) n'avaient AUCUN
   écran derrière elles. Ici on revoit qui a ouvert quoi, et on marque un
   appareil « équipe » (Reda/le staff) en un clic pour que SES propres
   consultations arrêtent de déclencher de fausses alertes concurrence —
   l'exclusion est posée côté SERVEUR, permanente et rétroactive.

   `GET crm/visites-externes/appareils/` porte déjà le signal : `equipe: bool`
   (posé côté serveur, jamais recalculé ici) et `leads: [{id, nom}]` — un
   appareil qui a touché ≥2 leads et n'est PAS équipe est le cas suspect
   (« Multi-prospects »), le reste est du bruit normal (un commercial qui
   revient sur SES propres prospects touche rarement 2 leads DIFFÉRENTS
   depuis le même lien externe).
   ========================================================================== */

// Humanise une durée en secondes → « 45 s » / « 12 min » / « 2 h 05 » — jamais
// de décimales, le chiffre affiché reste lisible d'un coup d'œil.
function humaniserDuree(secondes) {
  const s = Number(secondes)
  if (!Number.isFinite(s) || s <= 0) return '—'
  if (s < 60) return `${Math.round(s)} s`
  const minutesTotales = Math.round(s / 60)
  if (minutesTotales < 60) return `${minutesTotales} min`
  const heures = Math.floor(minutesTotales / 60)
  const minutes = minutesTotales % 60
  return minutes ? `${heures} h ${String(minutes).padStart(2, '0')}` : `${heures} h`
}

// Raccourcit l'identifiant d'appareil (souvent un UUID/hash long) à ses 8
// premiers caractères pour la colonne — l'identifiant complet reste dans le
// `title` HTML pour qui a besoin de le copier.
function raccourcirAppareil(appareilId) {
  if (!appareilId) return '—'
  return appareilId.length > 8 ? `${appareilId.slice(0, 8)}…` : appareilId
}

// Tronque le user-agent affiché dans la colonne « Navigateur » — la chaîne
// complète reste dans le `title` HTML.
function tronquerNavigateur(userAgent) {
  if (!userAgent) return '—'
  return userAgent.length > 40 ? `${userAgent.slice(0, 40)}…` : userAgent
}

// VIS-LEAD (14-16/09/2026) — la notification `devis_opened` pointe désormais
// `/crm/visiteurs?lead=<id>` : ce texte résume les lectures CLIENT de chaque
// devis du lead, à partir de `lecture` (forme exacte de
// `apps.ventes.selectors.share_link_lecture_map` — jamais un chiffre
// inventé : une clé absente du serveur est simplement omise ici).
function texteLecture(lecture) {
  if (!lecture) return 'Jamais partagé'
  const morceaux = []
  if (lecture.nombre_vues != null) morceaux.push(`Ouvert ${lecture.nombre_vues} fois`)
  if (lecture.premiere_consultation) morceaux.push(`première le ${formatDateTime(lecture.premiere_consultation)}`)
  if (lecture.derniere_consultation) morceaux.push(`dernière le ${formatDateTime(lecture.derniere_consultation)}`)
  return morceaux.length > 0 ? morceaux.join(' · ') : 'Envoyé, jamais ouvert'
}

const MAX_LEADS_AFFICHES = 5

export default function VisiteursPage() {
  const isResponsableOuAdmin = useIsAdminOrResponsable()
  const [searchParams, setSearchParams] = useSearchParams()
  const appareilFiltre = searchParams.get('appareil') || ''
  // VIS-LEAD — `?lead=<id>` bascule tout l'écran en mode « historique des
  // accès de CE lead » (voir le rendu conditionnel plus bas).
  const leadId = searchParams.get('lead') || ''

  const [appareils, setAppareils] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)

  const [equipe, setEquipe] = useState([])
  const [loadingEquipe, setLoadingEquipe] = useState(true)

  const [busyAppareil, setBusyAppareil] = useState(null)
  const [dialogAppareil, setDialogAppareil] = useState(null)
  const [libelle, setLibelle] = useState('')
  const [saving, setSaving] = useState(false)

  const [ouvertId, setOuvertId] = useState(null)
  const [visitesDetail, setVisitesDetail] = useState([])
  const [loadingDetail, setLoadingDetail] = useState(false)

  // VIS-LEAD — fiche du lead (dont `devis[].lecture`) et ses visites brutes.
  const [lead, setLead] = useState(null)
  const [loadingLead, setLoadingLead] = useState(true)
  const [erreurLead, setErreurLead] = useState(false)
  const [visitesLead, setVisitesLead] = useState([])
  const [loadingVisitesLead, setLoadingVisitesLead] = useState(true)
  const [erreurVisitesLead, setErreurVisitesLead] = useState(false)

  const chargerAppareils = () => {
    // setState différé au prochain microtask (jamais synchrone dans l'effet) —
    // évite react-hooks/set-state-in-effect, même patron que
    // `RelancesSuiviPage.jsx`.
    queueMicrotask(() => { setLoading(true); setErreur(false) })
    const params = appareilFiltre ? { appareil_id: appareilFiltre } : {}
    return crmApi.getAppareilsVisites(params)
      .then((r) => setAppareils(r.data?.results ?? r.data ?? []))
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  const chargerEquipe = () => {
    // Même différé que `chargerAppareils` (react-hooks/set-state-in-effect).
    queueMicrotask(() => setLoadingEquipe(true))
    return crmApi.getAppareilsEquipe()
      .then((r) => setEquipe(r.data?.results ?? r.data ?? []))
      .catch(() => setEquipe([]))
      .finally(() => setLoadingEquipe(false))
  }

  useEffect(() => {
    // Mode lead : la liste agrégée par appareil n'a pas sa place ici (voir
    // les deux effets VIS-LEAD ci-dessous) — on évite l'appel inutile.
    if (leadId) return
    chargerAppareils()
  },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chargerAppareils referme déjà appareilFiltre ; l'ajouter provoquerait une recréation d'effet identique.
    [appareilFiltre, leadId])

  useEffect(() => { chargerEquipe() }, [])

  // VIS-LEAD — fiche du lead (nom/prénom + devis[].lecture).
  useEffect(() => {
    if (!leadId) return
    queueMicrotask(() => { setLoadingLead(true); setErreurLead(false) })
    crmApi.getLead(leadId)
      .then((r) => setLead(r.data))
      .catch(() => setErreurLead(true))
      .finally(() => setLoadingLead(false))
  }, [leadId])

  // VIS-LEAD — visites brutes de ce lead (tableau « Accès »).
  useEffect(() => {
    if (!leadId) return
    queueMicrotask(() => { setLoadingVisitesLead(true); setErreurVisitesLead(false) })
    crmApi.getVisitesExternes({ lead: leadId })
      .then((r) => setVisitesLead(r.data?.results ?? r.data ?? []))
      .catch(() => setErreurVisitesLead(true))
      .finally(() => setLoadingVisitesLead(false))
  }, [leadId])

  const equipeParAppareil = useMemo(() => {
    const map = new Map()
    for (const e of equipe) map.set(e.appareil_id, e)
    return map
  }, [equipe])

  // Les plus récentes d'abord — le serveur ne garantit pas l'ordre.
  const visitesLeadTriees = useMemo(
    () => [...visitesLead].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)),
    [visitesLead],
  )

  const toggleDetail = (appareilId) => {
    if (ouvertId === appareilId) { setOuvertId(null); return }
    setOuvertId(appareilId)
    setLoadingDetail(true)
    crmApi.getVisitesExternes({ appareil_id: appareilId })
      .then((r) => setVisitesDetail(r.data?.results ?? r.data ?? []))
      .catch(() => setVisitesDetail([]))
      .finally(() => setLoadingDetail(false))
  }

  const ouvrirDialogueEquipe = (appareilId) => {
    setDialogAppareil(appareilId)
    setLibelle('')
  }

  const confirmerMarquerEquipe = async () => {
    if (!dialogAppareil) return
    setSaving(true)
    try {
      await crmApi.createAppareilEquipe({
        appareil_id: dialogAppareil,
        libelle: libelle.trim() || undefined,
      })
      toast.success('Appareil marqué équipe — il ne déclenchera plus d’alertes.')
      setDialogAppareil(null)
      await Promise.all([chargerAppareils(), chargerEquipe()])
    } catch (err) {
      toast.error(frenchError(err, "Impossible de marquer cet appareil équipe."))
    } finally {
      setSaving(false)
    }
  }

  const retirerDeLEquipe = async (appareilId) => {
    const entree = equipeParAppareil.get(appareilId)
    if (!entree) return
    setBusyAppareil(appareilId)
    try {
      await crmApi.deleteAppareilEquipe(entree.id)
      toast.success('Appareil retiré de l’équipe. S’il se connecte encore à l’ERP, il sera reconnu à nouveau automatiquement.')
      await Promise.all([chargerAppareils(), chargerEquipe()])
    } catch (err) {
      toast.error(frenchError(err, "Impossible de retirer cet appareil."))
    } finally {
      setBusyAppareil(null)
    }
  }

  const effacerFiltre = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('appareil')
    setSearchParams(next)
  }

  // VIS-LEAD — retire `?lead=` pour revenir à la vue agrégée par appareil.
  const effacerFiltreLead = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('lead')
    setSearchParams(next)
  }

  // VIS-LEAD (14-16/09/2026) — la notification `devis_opened` pointe
  // désormais `/crm/visiteurs?lead=<id>` : un écran DÉDIÉ (bandeau + lectures
  // des devis + accès bruts de CE lead), distinct de la vue agrégée par
  // appareil ci-dessous (mode `?appareil=` ou sans filtre, INCHANGÉE).
  if (leadId) {
    const nomComplet = lead ? `${lead.nom || ''} ${lead.prenom || ''}`.trim() : ''
    return (
      <div className="page">
        <div className="lp-controlbar crm-controlbar mb-3">
          <h1 className="lp-cb-title flex items-center gap-2">
            <Radar className="h-5 w-5" aria-hidden="true" />
            Historique des accès{nomComplet ? ` — ${nomComplet}` : ''}
          </h1>
        </div>
        <div className="mb-3 flex items-center gap-2 text-sm">
          <Link to={`/crm/leads/${leadId}`}>Voir la fiche</Link>
          <Button variant="ghost" size="sm" onClick={effacerFiltreLead}>Tous les appareils</Button>
        </div>

        <Card className="mb-3">
          <CardContent className="pt-4">
            <h2 style={{ fontSize: 15, fontWeight: 600, marginTop: 0 }}>Lectures des devis</h2>
            {loadingLead ? (
              <Spinner />
            ) : erreurLead ? (
              <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
            ) : (lead?.devis || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun devis pour ce lead.</p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {lead.devis.map((d) => (
                  <li key={d.id}>
                    <strong>{d.reference}</strong> · {texteLecture(d.lecture)}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <h2 style={{ fontSize: 15, fontWeight: 600, marginTop: 0 }}>Accès</h2>
            {loadingVisitesLead ? (
              <Spinner />
            ) : erreurVisitesLead ? (
              <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
            ) : visitesLeadTriees.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun accès enregistré pour ce lead.</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left' }}>Date</th>
                    <th style={{ textAlign: 'left' }}>Quoi</th>
                    <th style={{ textAlign: 'right' }}>Durée</th>
                    <th style={{ textAlign: 'left' }}>Appareil</th>
                    <th style={{ textAlign: 'left' }}>IP</th>
                    <th style={{ textAlign: 'left' }}>Navigateur</th>
                    {isResponsableOuAdmin && <th />}
                  </tr>
                </thead>
                <tbody>
                  {visitesLeadTriees.map((v) => {
                    const estEquipe = !!v.appareil_id && equipeParAppareil.has(v.appareil_id)
                    return (
                      <tr key={v.id}>
                        <td>{formatDateTime(v.created_at)}</td>
                        <td>
                          {v.point_display || v.point}
                          {v.contexte ? ` — ${v.contexte}` : ''}
                        </td>
                        <td style={{ textAlign: 'right' }}>{humaniserDuree(v.duree_s)}</td>
                        <td title={v.appareil_id || undefined}>
                          {raccourcirAppareil(v.appareil_id)}{' '}
                          {estEquipe && <Badge tone="success">Équipe</Badge>}
                        </td>
                        <td>{v.ip || '—'}</td>
                        <td title={v.user_agent || ''}>{tronquerNavigateur(v.user_agent)}</td>
                        {isResponsableOuAdmin && (
                          <td>
                            {v.appareil_id && (
                              estEquipe ? (
                                <Button
                                  variant="outline" size="sm"
                                  disabled={busyAppareil === v.appareil_id}
                                  onClick={() => retirerDeLEquipe(v.appareil_id)}
                                >
                                  Retirer
                                </Button>
                              ) : (
                                <Button
                                  variant="outline" size="sm"
                                  onClick={() => ouvrirDialogueEquipe(v.appareil_id)}
                                >
                                  Marquer équipe
                                </Button>
                              )
                            )}
                          </td>
                        )}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>

        <Dialog open={!!dialogAppareil} onOpenChange={(o) => { if (!o) setDialogAppareil(null) }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Marquer cet appareil équipe</DialogTitle>
            </DialogHeader>
            <div className="flex flex-col gap-2">
              <p className="text-sm text-muted-foreground">
                Ses visites ne compteront plus dans les alertes concurrence, dès
                maintenant et rétroactivement.
              </p>
              <Label htmlFor="vis-lead-libelle">Libellé (optionnel)</Label>
              <Input
                id="vis-lead-libelle"
                placeholder="ex. Téléphone du commercial"
                value={libelle}
                onChange={(e) => setLibelle(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogAppareil(null)} disabled={saving}>
                Annuler
              </Button>
              <Button onClick={confirmerMarquerEquipe} disabled={saving} loading={saving}>
                Marquer équipe
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="lp-controlbar crm-controlbar mb-3">
        <h1 className="lp-cb-title flex items-center gap-2">
          <Radar className="h-5 w-5" aria-hidden="true" />
          Visiteurs & alertes
        </h1>
      </div>
      <p className="mb-3 text-sm text-muted-foreground">
        Qui a ouvert quels devis/liens externes, et depuis quel appareil — les
        appareils marqués « équipe » sont exclus du comptage et des alertes,
        de façon permanente et rétroactive.
      </p>

      {appareilFiltre && (
        <div className="mb-3 flex items-center gap-2 text-sm">
          <Badge tone="outline">Filtré sur l’appareil {raccourcirAppareil(appareilFiltre)}</Badge>
          <Button variant="ghost" size="sm" onClick={effacerFiltre}>Retirer le filtre</Button>
        </div>
      )}

      <Card>
        <CardContent className="pt-4">
          {loading ? (
            <Spinner />
          ) : erreur ? (
            <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
          ) : appareils.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun appareil observé pour le moment.</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Appareil</th>
                  <th style={{ textAlign: 'right' }}>Visites</th>
                  <th style={{ textAlign: 'right' }}>Propositions ouvertes</th>
                  <th style={{ textAlign: 'right' }}>Durée totale</th>
                  <th style={{ textAlign: 'left' }}>Leads touchés</th>
                  <th style={{ textAlign: 'left' }}>Première</th>
                  <th style={{ textAlign: 'left' }}>Dernière</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {appareils.map((a) => {
                  const suspect = !a.equipe && (a.leads?.length ?? 0) >= 2
                  const leadsAffiches = (a.leads || []).slice(0, MAX_LEADS_AFFICHES)
                  const leadsRestants = (a.leads?.length ?? 0) - leadsAffiches.length
                  return (
                    <Fragment key={a.appareil_id}>
                      <tr>
                        <td title={a.appareil_id}>
                          <button
                            type="button"
                            onClick={() => toggleDetail(a.appareil_id)}
                            style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', font: 'inherit', color: 'inherit', textDecoration: 'underline' }}
                          >
                            {raccourcirAppareil(a.appareil_id)}
                          </button>{' '}
                          {a.equipe && <Badge tone="success">Équipe</Badge>}{' '}
                          {suspect && (
                            <Badge tone="danger">
                              <ShieldAlert className="mr-1 inline size-3" aria-hidden="true" />
                              Multi-prospects
                            </Badge>
                          )}
                        </td>
                        <td style={{ textAlign: 'right' }}>{a.visites ?? 0}</td>
                        <td style={{ textAlign: 'right' }}>{a.propositions ?? 0}</td>
                        <td style={{ textAlign: 'right' }}>{humaniserDuree(a.duree_totale_s)}</td>
                        <td>
                          {leadsAffiches.map((l) => (
                            <Link
                              key={l.id}
                              to={`/crm/leads/${l.id}`}
                              style={{ marginRight: 6, whiteSpace: 'nowrap' }}
                            >
                              {l.nom}
                            </Link>
                          ))}
                          {leadsRestants > 0 && <span> +{leadsRestants}</span>}
                          {(a.leads?.length ?? 0) === 0 && '—'}
                        </td>
                        <td>{formatDateTime(a.premiere)}</td>
                        <td>{formatDateTime(a.derniere)}</td>
                        <td>
                          {isResponsableOuAdmin && (
                            a.equipe ? (
                              <Button
                                variant="outline" size="sm"
                                disabled={busyAppareil === a.appareil_id}
                                onClick={() => retirerDeLEquipe(a.appareil_id)}
                              >
                                Retirer de l’équipe
                              </Button>
                            ) : (
                              <Button
                                variant="outline" size="sm"
                                onClick={() => ouvrirDialogueEquipe(a.appareil_id)}
                              >
                                Marquer appareil équipe
                              </Button>
                            )
                          )}
                        </td>
                      </tr>
                      {ouvertId === a.appareil_id && (
                        <tr>
                          <td colSpan={8} style={{ background: 'var(--muted, #f8fafc)', padding: 12 }}>
                            {loadingDetail ? (
                              <Spinner />
                            ) : visitesDetail.length === 0 ? (
                              <p className="text-sm text-muted-foreground">Aucune visite détaillée.</p>
                            ) : (
                              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                <thead>
                                  <tr>
                                    <th style={{ textAlign: 'left' }}>Date</th>
                                    <th style={{ textAlign: 'left' }}>Écran</th>
                                    <th style={{ textAlign: 'left' }}>Contexte</th>
                                    <th style={{ textAlign: 'left' }}>Lead</th>
                                    <th style={{ textAlign: 'right' }}>Durée</th>
                                    <th style={{ textAlign: 'left' }}>IP</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {visitesDetail.map((v) => (
                                    <tr key={v.id}>
                                      <td>{formatDateTime(v.created_at)}</td>
                                      <td>{v.point_display || v.point}</td>
                                      <td>{v.contexte || '—'}</td>
                                      <td>
                                        {v.lead
                                          ? <Link to={`/crm/leads/${v.lead}`}>{v.lead_nom || `#${v.lead}`}</Link>
                                          : '—'}
                                      </td>
                                      <td style={{ textAlign: 'right' }}>{humaniserDuree(v.duree_s)}</td>
                                      <td>{v.ip || '—'}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {isResponsableOuAdmin && (
        <Card className="mt-3">
          <CardContent className="pt-4">
            <h2 style={{ fontSize: 15, fontWeight: 600, marginTop: 0 }}>Appareils équipe</h2>
            {loadingEquipe ? (
              <Spinner />
            ) : equipe.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun appareil équipe enregistré.</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left' }}>Libellé</th>
                    <th style={{ textAlign: 'left' }}>Appareil</th>
                    <th style={{ textAlign: 'left' }}>Ajouté le</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {equipe.map((e) => (
                    <tr key={e.id}>
                      <td>{e.libelle || '—'}</td>
                      <td title={e.appareil_id}>{raccourcirAppareil(e.appareil_id)}</td>
                      <td>{formatDateTime(e.created_at)}</td>
                      <td>
                        <Button
                          variant="ghost" size="sm"
                          disabled={busyAppareil === e.appareil_id}
                          onClick={() => retirerDeLEquipe(e.appareil_id)}
                        >
                          Retirer
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      <Dialog open={!!dialogAppareil} onOpenChange={(o) => { if (!o) setDialogAppareil(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Marquer cet appareil équipe</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <p className="text-sm text-muted-foreground">
              Ses visites ne compteront plus dans les alertes concurrence, dès
              maintenant et rétroactivement.
            </p>
            <Label htmlFor="vis-libelle">Libellé (optionnel)</Label>
            <Input
              id="vis-libelle"
              placeholder="ex. Téléphone du commercial"
              value={libelle}
              onChange={(e) => setLibelle(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogAppareil(null)} disabled={saving}>
              Annuler
            </Button>
            <Button onClick={confirmerMarquerEquipe} disabled={saving} loading={saving}>
              Marquer équipe
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
