import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Input } from '../../../ui'
import { EnteteStock, BandeauxStock } from '../EnteteStock'
import rfaApi from '../../../features/stock/api/rfaApi'
import { messageServeur } from '../../../features/stock/api/erreurs'
import { useVoitPrixAchat } from '../../../features/stock/useVoitPrixAchat'

/* ASTK222 — Remises arrière fournisseur (RFA) : accords, calcul de
   progression, génération de l'avoir — UNE seule fois.

   Le bouton « Générer l'avoir » est désactivé pendant l'envoi ET après
   génération (l'accord relu porte `avoir_deja_genere`) ; un second POST
   refusé par le serveur affiche son message mot pour mot. Argent fournisseur
   interne : jamais client-facing. L'avoir apparaît aussi dans la fiche 360 du
   fournisseur — lien, pas de doublon de liste. */

const liste = (d) => (Array.isArray(d) ? d : d?.results ?? [])
const selectCls = 'h-9 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-sm'
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR') : '—')
const VIDE = { fournisseur: '', debut: '', fin: '', seuil: '', taux: '', fixe: '', note: '' }

const Carte = ({ titre, children }) => (
  <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
    {titre && <h2 className="mb-3 text-sm font-semibold">{titre}</h2>}
    {children}
  </section>
)

export default function RfaPage() {
  const [accords, setAccords] = useState([])
  const [fournisseurs, setFournisseurs] = useState([])
  const [form, setForm] = useState(VIDE)
  const [calculs, setCalculs] = useState({})
  const [avoirs, setAvoirs] = useState({}) // accord.id → avoir généré dans cette session
  const [enCours, setEnCours] = useState(null) // id de l'accord en cours d'envoi
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)
  // ERR-STK-PRIX-ACHAT-SUITE — calcul (CA d'achat, montant dû) réservé à
  // prix_achat_voir : jamais un bouton que le serveur refuse (403).
  const voitPrix = useVoitPrixAchat()

  const charger = useCallback(async () => {
    try {
      const { data } = await rfaApi.listAccords()
      setAccords(liste(data))
    } catch (err) { setErreur(messageServeur(err, 'Chargement des accords impossible.')) }
  }, [])

  useEffect(() => {
    Promise.resolve().then(charger)
    rfaApi.listFournisseurs().then((r) => setFournisseurs(liste(r.data))).catch(() => {})
  }, [charger])

  const creer = async (ev) => {
    ev.preventDefault()
    if (!form.fournisseur || !form.debut || !form.fin) {
      setErreur('Choisissez le fournisseur et la période.'); return
    }
    const corps = {
      fournisseur: Number(form.fournisseur),
      periode_debut: form.debut, periode_fin: form.fin,
    }
    if (form.seuil !== '') corps.seuil_ca_achat = form.seuil
    if (form.taux !== '') corps.taux_pct = form.taux
    if (form.fixe !== '') corps.montant_fixe = form.fixe
    setOccupe(true); setErreur(null)
    try {
      await rfaApi.creerAccord(corps)
      setForm(VIDE)
      await charger()
    } catch (err) { setErreur(messageServeur(err, "L'accord n'a pas pu être créé.")) } finally { setOccupe(false) }
  }

  const voirCalcul = async (id) => {
    setErreur(null)
    try {
      const { data } = await rfaApi.calcul(id)
      setCalculs((c) => ({ ...c, [id]: data }))
    } catch (err) { setErreur(messageServeur(err, 'Calcul indisponible.')) }
  }

  const genererAvoir = async (accord) => {
    if (enCours != null) return
    setEnCours(accord.id); setErreur(null)
    try {
      const { data } = await rfaApi.genererAvoir(accord.id)
      setAvoirs((a) => ({ ...a, [accord.id]: data }))
      await charger()
    } catch (err) { setErreur(messageServeur(err, "La génération de l'avoir a échoué.")) } finally { setEnCours(null) }
  }

  const champ = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  return (
    <div className="space-y-4">
      <EnteteStock
                title="Remises arrière (RFA)"
        subtitle="Accords fournisseur, progression et génération de l'avoir."
      />
      <BandeauxStock erreur={erreur} />

      <Carte titre="Nouvel accord">
        <form onSubmit={creer} noValidate className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Fournisseur</span>
            <select className={selectCls} value={form.fournisseur} onChange={champ('fournisseur')}>
              <option value="">—</option>
              {fournisseurs.map((f) => <option key={f.id} value={f.id}>{f.nom}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Début de période</span>
            <Input type="date" value={form.debut} onChange={champ('debut')} className="w-40" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Fin de période</span>
            <Input type="date" value={form.fin} onChange={champ('fin')} className="w-40" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Seuil de CA d&apos;achat</span>
            <Input type="number" step="any" value={form.seuil} onChange={champ('seuil')} className="w-32" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Taux (%)</span>
            <Input type="number" step="any" value={form.taux} onChange={champ('taux')} className="w-24" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Montant fixe</span>
            <Input type="number" step="any" value={form.fixe} onChange={champ('fixe')} className="w-28" />
          </label>
          <Button type="submit" disabled={occupe}>Créer l&apos;accord</Button>
        </form>
      </Carte>

      <Carte titre="Accords">
        {accords.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">Aucun accord de remise arrière.</p>
        ) : (
          <ul className="space-y-3 text-sm">
            {accords.map((a) => {
              const calcul = calculs[a.id]
              const avoir = avoirs[a.id]
              const dejaGenere = a.avoir_deja_genere || !!avoir
              return (
                <li key={a.id} className="rounded-md border border-[var(--border)] p-3">
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                    <strong>{a.fournisseur_nom}</strong>
                    <span>{fmtDate(a.periode_debut)} → {fmtDate(a.periode_fin)}</span>
                    <span>{a.statut === 'actif' ? 'Actif' : 'Clos'}</span>
                    <span>
                      {/* Clé absente = montant masqué sans prix_achat_voir (jamais « undefined »). */}
                      {a.taux_pct != null ? `${a.taux_pct} %` : (a.montant_fixe != null ? `${a.montant_fixe} fixe`
                        : ('montant_fixe' in a ? '—' : 'Montant fixe'))}
                    </span>
                    <Link className="underline" to={`/stock/fournisseurs/${a.fournisseur}/360`}>Fiche fournisseur</Link>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {voitPrix && (
                      <Button size="sm" variant="outline" onClick={() => voirCalcul(a.id)}>Voir le calcul</Button>
                    )}
                    {dejaGenere ? (
                      <Button size="sm" disabled>Avoir déjà généré</Button>
                    ) : (
                      <Button size="sm" disabled={enCours != null} onClick={() => genererAvoir(a)}>
                        Générer l&apos;avoir
                      </Button>
                    )}
                    {(avoir?.reference ?? a.avoir_reference) && (
                      <span role="status" className="text-success">Avoir {avoir?.reference ?? a.avoir_reference} généré.</span>
                    )}
                  </div>
                  {calcul && (
                    <p className="mt-2 text-[var(--muted-foreground)]">
                      {calcul.seuil_atteint ? 'Seuil atteint' : 'Seuil non atteint'} — Progression : {calcul.progression_pct} %
                      {' · '}CA d&apos;achat {calcul.ca_achat} · Montant dû {calcul.montant_du}
                    </p>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </Carte>
    </div>
  )
}
