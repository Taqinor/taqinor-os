import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Input } from '../../../ui'
import { EnteteStock, BandeauxStock } from '../EnteteStock'
import negoceApi from '../../../features/stock/api/negoceApi'
import {
  messageServeur, messageServeurBlob, ouvrirBlob,
} from '../../../features/stock/api/erreurs'
import { todayLocalIso } from '../../../lib/dateLocale.js'

/* ASTK221 — Consignation : dépôts chez les clients, déclaration de
   consommation (la facture brouillon créée est affichée avec son lien),
   relevé PDF, export, et les DEUX réglages négoce vivants (consignation
   activée, horizon ATP).

   Aucun état local persistant : chaque geste relit le serveur. Les quantités
   sont des ENTIERS (refus sous le champ, jamais de troncature). Consignation
   désactivée → le 403 du serveur est affiché tel quel. L'écran n'offre PAS
   l'édition des quantités d'un dépôt (champs figés côté serveur). */

const liste = (d) => (Array.isArray(d) ? d : d?.results ?? [])
const STATUTS_DECL = { declaree: 'Déclarée', facturee: 'Facturée', annulee: 'Annulée' }
const aujourdhui = () => todayLocalIso()
const selectCls = 'h-9 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-sm'
const Carte = ({ titre, children }) => (
  <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
    {titre && <h2 className="mb-3 text-sm font-semibold">{titre}</h2>}
    {children}
  </section>
)
const Vide = ({ children }) => <p className="text-sm text-[var(--muted-foreground)]">{children}</p>

function entier(texte) {
  const n = Number(texte)
  if (texte === '' || !Number.isFinite(n)) return { erreur: 'Saisissez une quantité.' }
  if (!Number.isInteger(n)) return { erreur: 'La quantité doit être un nombre entier.' }
  if (n <= 0) return { erreur: 'La quantité doit être positive.' }
  return { n }
}

function Declaration({ d }) {
  return (
    <li>
      {STATUTS_DECL[d.statut] ?? d.statut}
      {d.facture_reference ? (
        <>
          {' — '}
          {d.facture_id
            ? <Link className="underline" to={`/ventes/factures?id=${d.facture_id}`}>{d.facture_reference}</Link>
            : d.facture_reference}
        </>
      ) : ''}
      {' · '}{d.quantite} u. le {new Date(d.date_declaration).toLocaleDateString('fr-FR')}
    </li>
  )
}

function CarteDepot({ depot, onGeste, occupe, onErreur }) {
  const [qte, setQte] = useState('')
  const [erreurQte, setErreurQte] = useState(null)

  const declarer = async () => {
    const { n, erreur } = entier(qte)
    if (erreur) { setErreurQte(erreur); return }
    setErreurQte(null)
    const ok = await onGeste(
      () => negoceApi.declarerConsommation(depot.id, { quantite: n, date_declaration: aujourdhui(), note: '' }),
      'La déclaration a échoué.')
    if (ok) setQte('')
  }
  const ouvrirPdf = async () => {
    try {
      const { data } = await negoceApi.relevePdf(depot.id)
      ouvrirBlob(data)
    } catch (err) { onErreur(await messageServeurBlob(err, 'Relevé indisponible.')) }
  }

  return (
    <div className="rounded-md border border-[var(--border)] p-3 text-sm">
      <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1">
        <strong>{depot.produit_nom}</strong>
        <span>déposé {depot.quantite_deposee}</span>
        <span>consommé {depot.quantite_consommee_declaree}</span>
        <span>restant {depot.quantite_restante}</span>
        <span>{depot.statut === 'actif' ? 'Actif' : 'Clos'}</span>
        {depot.adresse_site && <span className="text-[var(--muted-foreground)]">{depot.adresse_site}</span>}
        <Button size="sm" variant="outline" onClick={ouvrirPdf}>Relevé PDF</Button>
      </div>
      {depot.declarations.length > 0 && (
        <ul className="mb-2 space-y-1">
          {depot.declarations.map((d) => <Declaration key={d.id} d={d} />)}
        </ul>
      )}
      {depot.statut === 'actif' && (
        <div className="flex flex-wrap items-start gap-2">
          <div className="flex flex-col gap-1">
            <Input
              type="number" step="any" className="w-28" value={qte} invalid={!!erreurQte}
              aria-label={`Quantité consommée dépôt ${depot.id}`}
              aria-describedby={erreurQte ? `qte-dep-${depot.id}` : undefined}
              onChange={(e) => setQte(e.target.value)}
            />
            {erreurQte && <span id={`qte-dep-${depot.id}`} className="text-xs text-destructive">{erreurQte}</span>}
          </div>
          <Button size="sm" disabled={occupe} onClick={declarer}>Déclarer la consommation</Button>
        </div>
      )}
    </div>
  )
}

function Reglages({ onErreur }) {
  const [params, setParams] = useState(null)
  const [actif, setActif] = useState(true)
  const [horizon, setHorizon] = useState('')
  const [info, setInfo] = useState(null)

  useEffect(() => {
    negoceApi.getParametres()
      .then(({ data }) => { setParams(data); setActif(!!data.consignation_activee); setHorizon(String(data.atp_horizon_jours ?? '')) })
      .catch((err) => onErreur(messageServeur(err, 'Réglages indisponibles.')))
  }, [onErreur])

  const enregistrer = async () => {
    setInfo(null); onErreur(null)
    try {
      const { data } = await negoceApi.setParametres({
        consignation_activee: actif, atp_horizon_jours: Number(horizon),
      })
      setParams(data); setInfo('Réglages enregistrés.')
    } catch (err) { onErreur(messageServeur(err, "L'enregistrement a échoué.")) }
  }

  if (!params) return <Vide>Chargement…</Vide>
  return (
    <div className="flex flex-wrap items-end gap-4">
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={actif} onChange={(e) => setActif(e.target.checked)} />
        <span>Consignation activée</span>
      </label>
      <label className="flex flex-col gap-1 text-xs">
        <span>Horizon ATP (jours)</span>
        <Input type="number" step="any" className="w-28" value={horizon} onChange={(e) => setHorizon(e.target.value)} />
      </label>
      <Button onClick={enregistrer}>Enregistrer</Button>
      {info && <span role="status" className="text-sm text-success">{info}</span>}
    </div>
  )
}

export default function ConsignationsPage() {
  const [onglet, setOnglet] = useState('depots')
  const [depots, setDepots] = useState([])
  const [clients, setClients] = useState([])
  const [produits, setProduits] = useState([])
  const [form, setForm] = useState({ client: '', produit: '', quantite: '', adresse: '' })
  const [erreurQte, setErreurQte] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const charger = useCallback(async () => {
    try {
      const { data } = await negoceApi.listConsignations()
      setDepots(liste(data))
      setErreur(null)
    } catch (err) { setErreur(messageServeur(err, 'Chargement des dépôts impossible.')) }
  }, [])

  useEffect(() => {
    Promise.resolve().then(charger)
    negoceApi.listClients().then((r) => setClients(liste(r.data))).catch(() => {})
    negoceApi.listProduits().then((r) => setProduits(liste(r.data))).catch(() => {})
  }, [charger])

  const geste = async (action, repli) => {
    setOccupe(true); setErreur(null)
    try { await action(); await charger(); return true } catch (err) {
      setErreur(messageServeur(err, repli)); return false
    } finally { setOccupe(false) }
  }

  const creer = async (ev) => {
    ev.preventDefault()
    if (!form.client || !form.produit) { setErreur('Choisissez un client et un produit.'); return }
    const { n, erreur: e } = entier(form.quantite)
    if (e) { setErreurQte(e); return }
    setErreurQte(null)
    const corps = { client: Number(form.client), produit: Number(form.produit), quantite_deposee: n }
    if (form.adresse.trim()) corps.adresse_site = form.adresse.trim()
    const ok = await geste(() => negoceApi.creerConsignation(corps), "Le dépôt n'a pas pu être créé.")
    if (ok) setForm({ client: '', produit: '', quantite: '', adresse: '' })
  }

  const exporter = async () => {
    try {
      const { data } = await negoceApi.exportXlsx()
      ouvrirBlob(data, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    } catch (err) { setErreur(await messageServeurBlob(err, 'Export indisponible.')) }
  }

  const champ = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  return (
    <div className="space-y-4">
      <EnteteStock
                title="Consignation"
        subtitle="Dépôts chez les clients, déclarations de consommation et réglages négoce."
      />
      <div role="tablist" aria-label="Sections de la consignation" className="flex gap-2">
        {[['depots', 'Dépôts'], ['reglages', 'Réglages']].map(([k, l]) => (
          <Button key={k} role="tab" aria-selected={onglet === k}
            variant={onglet === k ? 'default' : 'outline'} onClick={() => setOnglet(k)}>{l}</Button>
        ))}
      </div>

      <BandeauxStock erreur={erreur} />

      {onglet === 'depots' && (
        <div role="tabpanel" className="space-y-4">
          <Carte titre="Nouveau dépôt">
            <form onSubmit={creer} noValidate className="flex flex-wrap items-start gap-2">
              <label className="flex flex-col gap-1 text-xs">
                <span>Client</span>
                <select className={selectCls} value={form.client} onChange={champ('client')}>
                  <option value="">—</option>
                  {clients.map((c) => <option key={c.id} value={c.id}>{c.nom ?? c.raison_sociale ?? `#${c.id}`}</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs">
                <span>Produit</span>
                <select className={selectCls} value={form.produit} onChange={champ('produit')}>
                  <option value="">—</option>
                  {produits.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
                </select>
              </label>
              <div className="flex flex-col gap-1 text-xs">
                <label className="flex flex-col gap-1">
                  <span>Quantité déposée</span>
                  <Input type="number" step="any" className="w-28" value={form.quantite}
                    invalid={!!erreurQte} onChange={champ('quantite')} />
                </label>
                {erreurQte && <span className="text-xs text-destructive">{erreurQte}</span>}
              </div>
              <label className="flex flex-col gap-1 text-xs">
                <span>Adresse du site</span>
                <Input value={form.adresse} onChange={champ('adresse')} className="w-56" />
              </label>
              <Button type="submit" disabled={occupe} className="mt-5">Créer le dépôt</Button>
            </form>
          </Carte>

          <Carte titre="Dépôts chez les clients">
            <div className="mb-3">
              <Button variant="outline" size="sm" onClick={exporter}>Exporter (Excel)</Button>
            </div>
            {depots.length === 0 ? <Vide>Aucun dépôt de consignation.</Vide> : (
              <div className="space-y-3">
                {depots.map((d) => (
                  <CarteDepot key={d.id} depot={d} onGeste={geste} occupe={occupe} onErreur={setErreur} />
                ))}
              </div>
            )}
          </Carte>
        </div>
      )}

      {onglet === 'reglages' && (
        <div role="tabpanel">
          <Carte titre="Réglages négoce"><Reglages onErreur={setErreur} /></Carte>
        </div>
      )}
    </div>
  )
}
