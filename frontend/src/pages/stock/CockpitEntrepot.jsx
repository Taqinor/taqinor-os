import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Boxes, ClipboardList, Send, Timer } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { Badge, Button, Input, Spinner } from '../../ui'
import { PageHeader } from '../../ui/PageHeader'
import { INVENTAIRE_ACCENT } from '../../features/stock/inventaireAccent'

/* NTWMS29 — Tableau de bord entrepôt (cockpit WMS).

   Une seule requête (`/stock/entrepot/cockpit/`) agrège les cinq questions du
   responsable d'entrepôt : remplissage par zone, vagues de prélèvement en
   cours ET EN RETARD, comptages tournants dus, expéditions du jour par
   transporteur, lots proches de péremption (FEFO). Écran LECTURE SEULE — il
   n'écrit rien ; le simulateur de capacité (NTWMS33) y est branché en encart
   what-if, lui aussi en lecture.

   Aucun `useSelector` ici : l'écran se monte sans <Provider> dans ses tests. */

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

function Section({ icon: Icon, titre, compteur, children }) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
        {titre}
        {compteur != null && (
          <span className="text-[var(--muted-foreground)]">({compteur})</span>
        )}
      </h2>
      {children}
    </section>
  )
}

function Vide({ children }) {
  return <p className="text-sm text-[var(--muted-foreground)]">{children}</p>
}

function SimulateurCapacite({ zones }) {
  const [zone, setZone] = useState('')
  const [quantite, setQuantite] = useState('')
  const [resultat, setResultat] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(false)

  const lancer = async (ev) => {
    ev.preventDefault()
    if (!zone) { setErreur('Choisissez une zone.'); return }
    setEnCours(true)
    setErreur(null)
    try {
      const { data } = await stockApi.simulerCapacite({
        zone, quantite: quantite === '' ? 0 : Number(quantite),
      })
      setResultat(data)
    } catch (err) {
      setResultat(null)
      setErreur(frErr(err, 'La simulation a échoué.'))
    } finally { setEnCours(false) }
  }

  return (
    <form onSubmit={lancer} noValidate className="flex flex-wrap items-end gap-2">
      <label className="flex flex-col gap-1 text-xs">
        <span>Zone</span>
        <select
          value={zone}
          onChange={(e) => setZone(e.target.value)}
          className="h-9 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-sm"
        >
          <option value="">—</option>
          {zones.map((z) => <option key={z.zone} value={z.zone}>{z.zone}</option>)}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs">
        <span>Quantité à ajouter</span>
        <Input
          type="number" step="any" inputMode="numeric" value={quantite}
          onChange={(e) => setQuantite(e.target.value)} className="w-36"
        />
      </label>
      <Button type="submit" disabled={enCours}>Simuler</Button>
      {erreur && <span className="text-sm text-[var(--destructive)]">{erreur}</span>}
      {resultat && (
        <span className="text-sm">
          {resultat.taux_projete_pct == null
            ? 'Capacité non renseignée pour cette zone.'
            : `${resultat.taux_actuel_pct ?? '—'} % → ${resultat.taux_projete_pct} %`}
          {resultat.depassement && (
            <Badge tone="danger" className="ml-2">{resultat.avertissement}</Badge>
          )}
        </span>
      )}
    </form>
  )
}

export default function CockpitEntrepot() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)

  const charger = useCallback(async () => {
    setLoading(true)
    try {
      const res = await stockApi.getEntrepotCockpit()
      setData(res.data)
      setErreur(null)
    } catch (err) {
      setErreur(frErr(err, 'Le tableau de bord entrepôt est indisponible.'))
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { charger() }, [charger])

  const zones = data?.zones ?? []
  const vagues = data?.vagues ?? []
  const lots = data?.lots_peremption ?? []

  return (
    <div className="space-y-4">
      <PageHeader
        style={{ '--module-accent': INVENTAIRE_ACCENT }}
        className="app-accent-rail mb-0"
        headingAs="h1"
        icon={Boxes}
        title="Tableau de bord entrepôt"
        subtitle="Remplissage, vagues en retard, comptages dus, expéditions et péremptions."
        actions={<Button variant="outline" onClick={charger}>Rafraîchir</Button>}
      />

      {loading && <Spinner />}
      {erreur && <p className="text-sm text-[var(--destructive)]">{erreur}</p>}

      {!loading && data && (
        <div className="grid gap-4 md:grid-cols-2">
          <Section icon={Boxes} titre="Remplissage par zone" compteur={zones.length}>
            {zones.length === 0 ? <Vide>Aucun casier déclaré.</Vide> : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[var(--muted-foreground)]">
                      <th className="py-1">Zone</th>
                      <th>Casiers</th>
                      <th>Occupé</th>
                      <th>Capacité</th>
                      <th>Taux</th>
                    </tr>
                  </thead>
                  <tbody>
                    {zones.map((z) => (
                      <tr key={z.zone} className="border-t border-[var(--border)]">
                        <td className="py-1">{z.zone}</td>
                        <td>{z.nb_casiers}</td>
                        <td>{z.occupe}</td>
                        <td>{z.capacite ?? '—'}</td>
                        <td>
                          {z.taux_pct == null ? '—' : (
                            <Badge tone={Number(z.taux_pct) >= 95 ? 'danger' : 'neutral'}>
                              {z.taux_pct} %
                            </Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="mt-3 border-t border-[var(--border)] pt-3">
              <p className="mb-2 text-xs text-[var(--muted-foreground)]">
                Simulateur de capacité (what-if) — aucune réservation.
              </p>
              <SimulateurCapacite zones={zones} />
            </div>
          </Section>

          <Section icon={Timer} titre="Vagues de prélèvement" compteur={vagues.length}>
            {data.vagues_en_retard > 0 && (
              <p className="mb-2 flex items-center gap-2 text-sm text-[var(--destructive)]">
                <AlertTriangle size={15} aria-hidden="true" />
                {data.vagues_en_retard} vague(s) en retard.
              </p>
            )}
            {vagues.length === 0 ? <Vide>Aucune vague lancée.</Vide> : (
              <ul className="space-y-1 text-sm">
                {vagues.map((v) => (
                  <li key={v.id} className="flex items-center justify-between gap-2">
                    <span>{v.reference}</span>
                    <span className="text-[var(--muted-foreground)]">
                      reste {v.reste_a_prelever} / {v.quantite_demandee}
                    </span>
                    {v.en_retard && <Badge tone="danger">En retard</Badge>}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section
            icon={ClipboardList} titre="Comptages tournants dus"
            compteur={(data.comptages_dus ?? []).length}
          >
            {(data.comptages_dus ?? []).length === 0
              ? <Vide>Aucun comptage dû aujourd&apos;hui.</Vide>
              : (
                <ul className="space-y-1 text-sm">
                  {data.comptages_dus.map((c) => (
                    <li key={c.id}>
                      Classe {c.classe_abc} — tous les {c.frequence_jours} j
                      {c.date_dernier_comptage
                        ? ` (dernier : ${c.date_dernier_comptage})`
                        : ' (jamais compté)'}
                    </li>
                  ))}
                </ul>
              )}
          </Section>

          <Section
            icon={Send} titre="Expéditions du jour"
            compteur={(data.expeditions_du_jour ?? []).length}
          >
            {(data.expeditions_du_jour ?? []).length === 0
              ? <Vide>Aucune expédition aujourd&apos;hui.</Vide>
              : (
                <ul className="space-y-1 text-sm">
                  {data.expeditions_du_jour.map((e) => (
                    <li key={e.transporteur} className="flex justify-between">
                      <span>{e.transporteur}</span>
                      <span className="text-[var(--muted-foreground)]">{e.nb} envoi(s)</span>
                    </li>
                  ))}
                </ul>
              )}
          </Section>

          <Section
            icon={AlertTriangle}
            titre={`Lots proches de péremption (${data.horizon_peremption_jours} j)`}
            compteur={lots.length}
          >
            {lots.length === 0 ? <Vide>Aucun lot à surveiller.</Vide> : (
              <ul className="space-y-1 text-sm">
                {lots.map((l) => (
                  <li key={l.id} className="flex items-center justify-between gap-2">
                    <span>{l.produit_nom || `Produit ${l.produit}`} — {l.numero_lot}</span>
                    <Badge tone={l.perime ? 'danger' : 'warning'}>
                      {l.perime ? 'Périmé' : `J-${l.jours_restants}`}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      )}
    </div>
  )
}
