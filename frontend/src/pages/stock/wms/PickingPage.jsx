import { useCallback, useEffect, useState } from 'react'
import { Button, Input } from '../../../ui'
import { EnteteStock, BandeauxStock } from '../EnteteStock'
import pickingApi from '../../../features/stock/api/pickingApi'
import { messageServeur } from '../../../features/stock/api/erreurs'

/* ASTK217 — Picking : créer une vague, la lancer, configurer sa libération,
   prélever ligne par ligne, tâche-retour ; onglets Comptages tournants
   (générer) et Productivité / Pertes entrepôt.

   Chaque geste appelle sa route puis RELIT l'état serveur (aucun état local
   persistant) ; une erreur serveur (prélèvement > reste, vague non lancée…)
   est affichée mot pour mot. Le cockpit (/stock/entrepot) garde la lecture
   agrégée ; cet écran porte les gestes. */

const liste = (d) => (Array.isArray(d) ? d : d?.results ?? [])
const STATUTS = { brouillon: 'Brouillon', lancee: 'Lancée', terminee: 'Terminée' }
const selectCls = 'h-9 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-sm'
const Vide = ({ children }) => <p className="text-sm text-[var(--muted-foreground)]">{children}</p>
const Carte = ({ titre, children }) => (
  <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
    {titre && <h2 className="mb-3 text-sm font-semibold">{titre}</h2>}
    {children}
  </section>
)

function Onglets({ onglet, onChange }) {
  const items = [
    ['vagues', 'Vagues'], ['comptages', 'Comptages'], ['productivite', 'Productivité et pertes'],
  ]
  return (
    <div role="tablist" aria-label="Sections du picking" className="flex gap-2">
      {items.map(([k, l]) => (
        <Button
          key={k} role="tab" aria-selected={onglet === k}
          variant={onglet === k ? 'default' : 'outline'} onClick={() => onChange(k)}
        >{l}</Button>
      ))}
    </div>
  )
}

function LigneVague({ vague, ligne, onPrelever, occupe }) {
  const [qte, setQte] = useState('')
  const lancee = vague.statut === 'lancee'
  return (
    <tr className="border-t border-[var(--border)]">
      <td className="px-2 py-1.5 text-sm">{ligne.produit_nom}</td>
      <td className="px-2 py-1.5 text-sm">{ligne.bin_code || '—'}</td>
      <td className="px-2 py-1.5 text-sm">
        {ligne.quantite_prelevee} / {ligne.quantite_demandee} (reste {ligne.reste_a_prelever})
      </td>
      <td className="px-2 py-1.5 text-sm">
        {lancee && ligne.reste_a_prelever > 0 && (
          <span className="flex gap-1">
            <Input
              type="number" step="any" className="w-24" value={qte}
              aria-label={`Quantité prélevée ligne ${ligne.id}`}
              onChange={(e) => setQte(e.target.value)}
            />
            <Button
              size="sm" disabled={occupe || qte === ''}
              onClick={() => onPrelever(vague.id, ligne.id, Number(qte)).then((ok) => ok && setQte(''))}
            >Prélever</Button>
          </span>
        )}
      </td>
    </tr>
  )
}

function CarteVague({ vague, geste, occupe }) {
  const [mode, setMode] = useState(vague.mode_liberation)
  const [seuil, setSeuil] = useState(vague.seuil_lignes ?? '')
  return (
    <div className="rounded-md border border-[var(--border)] p-3">
      <div className="mb-2 flex flex-wrap items-center gap-3 text-sm">
        <strong>{vague.reference}</strong>
        <span>{STATUTS[vague.statut] ?? vague.statut}</span>
        <span className="text-[var(--muted-foreground)]">{vague.nb_lignes} ligne(s)</span>
        {vague.statut === 'brouillon' && (
          <Button size="sm" disabled={occupe}
            onClick={() => geste(() => pickingApi.lancerVague(vague.id), 'Lancement impossible.')}>
            Lancer la vague
          </Button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[32rem]">
          <thead><tr>
            {['Produit', 'Casier', 'Prélevé', ''].map((h) => (
              <th key={h} className="px-2 py-1.5 text-left text-xs font-semibold text-[var(--muted-foreground)]">{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {vague.lignes.map((l) => (
              <LigneVague
                key={l.id} vague={vague} ligne={l} occupe={occupe}
                onPrelever={(vId, lId, q) => geste(
                  () => pickingApi.prelever(vId, lId, q), 'Prélèvement impossible.')}
              />
            ))}
          </tbody>
        </table>
      </div>
      {vague.statut === 'brouillon' && (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Mode de libération</span>
            <select
              className={selectCls} value={mode} aria-label={`Mode de libération vague ${vague.id}`}
              onChange={(e) => setMode(e.target.value)}
            >
              <option value="manuel">Manuel</option>
              <option value="auto_seuil">Automatique au seuil</option>
            </select>
          </label>
          {mode === 'auto_seuil' && (
            <label className="flex flex-col gap-1 text-xs">
              <span>Seuil de lignes</span>
              <Input
                type="number" step="any" className="w-24" value={seuil}
                aria-label={`Seuil de lignes vague ${vague.id}`}
                onChange={(e) => setSeuil(e.target.value)}
              />
            </label>
          )}
          <Button
            size="sm" variant="outline" disabled={occupe}
            onClick={() => geste(() => pickingApi.configurerLiberation(
              vague.id, mode === 'auto_seuil' ? { mode, seuil_lignes: Number(seuil) } : { mode }),
            'Configuration impossible.')}
          >Enregistrer la libération</Button>
        </div>
      )}
    </div>
  )
}

export default function PickingPage() {
  const [onglet, setOnglet] = useState('vagues')
  const [vagues, setVagues] = useState([])
  const [produits, setProduits] = useState([])
  const [plans, setPlans] = useState([])
  const [sessions, setSessions] = useState(null)
  const [productivite, setProductivite] = useState(null)
  const [pertes, setPertes] = useState(null)
  const [retour, setRetour] = useState(null)
  const [zone, setZone] = useState('')
  const [debut, setDebut] = useState('')
  const [fin, setFin] = useState('')
  const [besoins, setBesoins] = useState([])
  const [produit, setProduit] = useState('')
  const [qte, setQte] = useState('')
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const chargerVagues = useCallback(async () => {
    try {
      const { data } = await pickingApi.listVagues()
      setVagues(liste(data))
    } catch (err) { setErreur(messageServeur(err, 'Chargement des vagues impossible.')) }
  }, [])

  useEffect(() => {
    Promise.resolve().then(chargerVagues)
    pickingApi.listProduits().then((r) => setProduits(liste(r.data))).catch(() => {})
  }, [chargerVagues])

  useEffect(() => {
    if (onglet === 'comptages') {
      pickingApi.listPlansComptage().then((r) => setPlans(liste(r.data)))
        .catch((e) => setErreur(messageServeur(e, 'Plans de comptage indisponibles.')))
    }
  }, [onglet])

  const chargerPilotage = useCallback(async () => {
    const params = {}
    if (debut) params.debut = debut
    if (fin) params.fin = fin
    const [a, b] = await Promise.allSettled([
      pickingApi.productivite(params), pickingApi.pertes(params)])
    if (a.status === 'fulfilled') setProductivite(a.value.data)
    if (b.status === 'fulfilled') setPertes(b.value.data)
    const ko = [a, b].find((r) => r.status === 'rejected')
    if (ko) setErreur(messageServeur(ko.reason, 'Indicateurs indisponibles.'))
  }, [debut, fin])

  useEffect(() => {
    if (onglet === 'productivite') Promise.resolve().then(chargerPilotage)
  }, [onglet, chargerPilotage])

  // Un geste : appelle la route, relit le serveur, affiche l'erreur telle quelle.
  const geste = async (action, repli) => {
    setOccupe(true); setErreur(null)
    try {
      await action()
      await chargerVagues()
      return true
    } catch (err) {
      setErreur(messageServeur(err, repli))
      return false
    } finally { setOccupe(false) }
  }

  const ajouterBesoin = () => {
    const n = Number(qte)
    if (!produit || !Number.isFinite(n) || n <= 0) { setErreur('Choisissez un produit et une quantité positive.'); return }
    setErreur(null)
    setBesoins((l) => [...l, { produit_id: Number(produit), quantite: n }])
    setProduit(''); setQte('')
  }

  const creer = async () => {
    if (besoins.length === 0) { setErreur('Ajoutez au moins un besoin.'); return }
    const ok = await geste(() => pickingApi.creerVague({ besoins, note: '' }),
      'Création de la vague impossible.')
    if (ok) setBesoins([])
  }

  const genererComptages = async () => {
    setErreur(null); setOccupe(true)
    try {
      const { data } = await pickingApi.genererComptages()
      setSessions(data)
      const r = await pickingApi.listPlansComptage()
      setPlans(liste(r.data))
    } catch (err) { setErreur(messageServeur(err, 'Génération impossible.')) } finally { setOccupe(false) }
  }

  const chercherRetour = async () => {
    setErreur(null)
    try {
      const { data } = await pickingApi.tacheRetour(zone ? { zone } : {})
      setRetour(data)
    } catch (err) { setErreur(messageServeur(err, 'Tâche-retour indisponible.')) }
  }

  const nomProduit = (id) => produits.find((p) => p.id === id)?.nom ?? `Produit #${id}`

  return (
    <div className="space-y-4">
      <EnteteStock
                title="Picking"
        subtitle="Vagues de prélèvement, comptages tournants, productivité et pertes."
      />
      <Onglets onglet={onglet} onChange={setOnglet} />

      <BandeauxStock erreur={erreur} />

      {onglet === 'vagues' && (
        <>
          <Carte titre="Nouvelle vague">
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex flex-col gap-1 text-xs">
                <span>Produit</span>
                <select className={selectCls} value={produit} onChange={(e) => setProduit(e.target.value)}>
                  <option value="">—</option>
                  {produits.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs">
                <span>Quantité à prélever</span>
                <Input type="number" step="any" className="w-28" value={qte} onChange={(e) => setQte(e.target.value)} />
              </label>
              <Button variant="outline" onClick={ajouterBesoin}>Ajouter le besoin</Button>
              <Button onClick={creer} disabled={occupe}>Créer la vague</Button>
            </div>
            {besoins.length > 0 && (
              <ul className="mt-2 text-sm">
                {besoins.map((b, i) => <li key={i}>{nomProduit(b.produit_id)} × {b.quantite}</li>)}
              </ul>
            )}
          </Carte>

          <Carte titre="Vagues">
            {vagues.length === 0 ? <Vide>Aucune vague.</Vide> : (
              <div className="space-y-3">
                {vagues.map((v) => <CarteVague key={v.id} vague={v} geste={geste} occupe={occupe} />)}
              </div>
            )}
          </Carte>

          <Carte titre="Tâche-retour">
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex flex-col gap-1 text-xs">
                <span>Zone courante</span>
                <Input value={zone} className="w-24" onChange={(e) => setZone(e.target.value)} sanitize="code" />
              </label>
              <Button variant="outline" onClick={chercherRetour}>Suggérer</Button>
            </div>
            {retour && (retour.suggestions.length === 0 ? <Vide>Aucune suggestion.</Vide> : (
              <ul className="mt-2 space-y-1 text-sm">
                {retour.suggestions.map((s) => (
                  <li key={s.ligne_id}>
                    {s.vague_reference} — {s.produit_nom} — casier {s.bin_code} (reste {s.quantite_restante})
                  </li>
                ))}
              </ul>
            ))}
          </Carte>
        </>
      )}

      {onglet === 'comptages' && (
        <Carte titre="Comptages tournants">
          <Button onClick={genererComptages} disabled={occupe}>Générer les comptages</Button>
          {sessions && (
            <p className="mt-2 text-sm">
              {sessions.plans_dus} plan(s) dû(s) — sessions :{' '}
              {sessions.sessions.length ? sessions.sessions.join(', ') : 'aucune'}
            </p>
          )}
          {plans.length === 0 ? <Vide>Aucun plan de comptage.</Vide> : (
            <ul className="mt-3 space-y-1 text-sm">
              {plans.map((p) => (
                <li key={p.id}>
                  Classe {p.classe_abc} — tous les {p.frequence_jours} jours — dernier comptage :{' '}
                  {p.date_dernier_comptage ?? 'jamais'}{p.actif ? '' : ' (inactif)'}
                </li>
              ))}
            </ul>
          )}
        </Carte>
      )}

      {onglet === 'productivite' && (
        <>
          <Carte>
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex flex-col gap-1 text-xs">
                <span>Début</span>
                <Input type="date" value={debut} onChange={(e) => setDebut(e.target.value)} className="w-40" />
              </label>
              <label className="flex flex-col gap-1 text-xs">
                <span>Fin</span>
                <Input type="date" value={fin} onChange={(e) => setFin(e.target.value)} className="w-40" />
              </label>
            </div>
          </Carte>
          <Carte titre="Productivité par opérateur">
            {!productivite || productivite.operateurs.length === 0 ? <Vide>Aucune opération sur la période.</Vide> : (
              <ul className="space-y-1 text-sm">
                {productivite.operateurs.map((o) => (
                  <li key={o.operateur_id}>
                    <strong>{o.operateur}</strong> — {o.total} opération(s)
                    {' '}({Object.entries(o.operations).map(([k, n]) => `${k} ${n}`).join(', ')})
                  </li>
                ))}
              </ul>
            )}
          </Carte>
          <Carte titre="Pertes entrepôt">
            {!pertes || pertes.par_motif.length === 0 ? <Vide>Aucune perte déclarée.</Vide> : (
              <ul className="space-y-1 text-sm">
                {pertes.par_motif.map((m) => (
                  <li key={m.motif}>
                    <span>{m.libelle}</span> — {m.nb_declarations} déclaration(s), quantité {m.quantite}
                  </li>
                ))}
              </ul>
            )}
          </Carte>
        </>
      )}
    </div>
  )
}
