import { useCallback, useEffect, useState } from 'react'
import { Button, Input } from '../../../ui'
import { PageHeader } from '../../../ui/PageHeader'
import { INVENTAIRE_ACCENT } from '../../../features/stock/inventaireAccent'
import entrepotCasiersApi from '../../../features/stock/api/entrepotCasiersApi'
import {
  messageServeur, messageServeurBlob, ouvrirBlob,
} from '../../../features/stock/api/erreurs'

/* ASTK215 — Casiers de l'entrepôt : seuils de réappro par casier, tâches de
   réappro (« Exécuter »), casiers sous seuil, historique d'un casier,
   planche d'étiquettes, suggestions de reslotting.

   L'écran ne garde AUCUN état persistant local : chaque geste recharge le
   serveur. Les erreurs serveur sont affichées mot pour mot (role="alert").
   Aucune boîte native : la suppression se confirme en ligne.
   Le tableau de bord (CockpitEntrepot) garde la lecture agrégée ; cet écran
   porte les gestes. */

const liste = (data) => (Array.isArray(data) ? data : data?.results ?? [])

const STATUTS_TACHE = { a_faire: 'À faire', faite: 'Faite', terminee: 'Terminée', annulee: 'Annulée' }

const Section = ({ id, titre, children }) => (
  <section
    aria-labelledby={id}
    className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4"
  >
    <h2 id={id} className="mb-3 text-sm font-semibold">{titre}</h2>
    {children}
  </section>
)

const Vide = ({ children }) => (
  <p className="text-sm text-[var(--muted-foreground)]">{children}</p>
)

const TH = ({ children }) => (
  <th className="px-2 py-1.5 text-left text-xs font-semibold text-[var(--muted-foreground)]">{children}</th>
)
const TD = ({ children, ...p }) => <td className="px-2 py-1.5 text-sm" {...p}>{children}</td>

const selectCls = 'h-9 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-sm'

export default function CasiersPage() {
  const [seuils, setSeuils] = useState([])
  const [taches, setTaches] = useState([])
  const [sousSeuil, setSousSeuil] = useState([])
  const [reslotting, setReslotting] = useState([])
  const [emplacements, setEmplacements] = useState([])
  const [produits, setProduits] = useState([])
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)
  const [enCours, setEnCours] = useState(null)
  const [confirmeSeuil, setConfirmeSeuil] = useState(null)
  const [historique, setHistorique] = useState(null)
  const [form, setForm] = useState({ bin: '', produit: '', seuil: '', quantite_cible: '' })
  const [etiquettesBin, setEtiquettesBin] = useState('')

  const charger = useCallback(async () => {
    const [a, b, c, d] = await Promise.allSettled([
      entrepotCasiersApi.listSeuils(),
      entrepotCasiersApi.listTaches({ statut: 'a_faire' }),
      entrepotCasiersApi.casiersSousSeuil(),
      entrepotCasiersApi.reslotting(),
    ])
    if (a.status === 'fulfilled') setSeuils(liste(a.value.data))
    if (b.status === 'fulfilled') setTaches(liste(b.value.data))
    if (c.status === 'fulfilled') setSousSeuil(c.value.data?.casiers ?? [])
    if (d.status === 'fulfilled') setReslotting(d.value.data?.suggestions ?? [])
    const echec = [a, b, c, d].find((r) => r.status === 'rejected')
    setErreur(echec ? messageServeur(echec.reason, 'Chargement impossible.') : null)
  }, [])

  useEffect(() => {
    Promise.resolve().then(charger)
    entrepotCasiersApi.listEmplacements()
      .then((r) => setEmplacements(liste(r.data))).catch(() => {})
    entrepotCasiersApi.listProduits()
      .then((r) => setProduits(liste(r.data))).catch(() => {})
  }, [charger])

  const nomProduit = (id) => produits.find((p) => p.id === id)?.nom ?? `Produit #${id}`
  const libEmplacement = (e) => e.code || e.nom

  // Un geste : appelle l'API, relit le serveur, affiche l'erreur telle quelle.
  const geste = async (cle, action, repli, succes) => {
    setEnCours(cle); setErreur(null); setInfo(null)
    try {
      const res = await action()
      if (succes) setInfo(succes(res))
      await charger()
      return true
    } catch (err) {
      setErreur(messageServeur(err, repli))
      return false
    } finally { setEnCours(null) }
  }

  const ajouterSeuil = (ev) => {
    ev.preventDefault()
    const corps = {
      bin: Number(form.bin), produit: Number(form.produit), seuil: Number(form.seuil),
      actif: true,
    }
    if (form.quantite_cible !== '') corps.quantite_cible = Number(form.quantite_cible)
    return geste('seuil', () => entrepotCasiersApi.createSeuil(corps),
      "Le seuil n'a pas pu être enregistré.")
      .then((ok) => { if (ok) setForm({ bin: '', produit: '', seuil: '', quantite_cible: '' }) })
  }

  const supprimerSeuil = (id) => geste(`del-${id}`, () => entrepotCasiersApi.deleteSeuil(id),
    'Suppression impossible.').then(() => setConfirmeSeuil(null))

  const executer = (t) => geste(`exe-${t.id}`, () => entrepotCasiersApi.executerTache(t.id),
    "L'exécution de la tâche a échoué.", () => `Tâche #${t.id} exécutée.`)

  const generer = () => geste('gen', () => entrepotCasiersApi.genererTaches(),
    'Génération impossible.', (res) => {
      const n = res.data?.taches_creees ?? 0
      return `${n} tâche${n > 1 ? 's' : ''} créée${n > 1 ? 's' : ''}.`
    })

  const ouvrirHistorique = async (bin) => {
    setErreur(null)
    try {
      const { data } = await entrepotCasiersApi.historiqueCasier(bin)
      setHistorique(data)
    } catch (err) { setErreur(messageServeur(err, "Historique indisponible.")) }
  }

  const telechargerEtiquettes = async () => {
    if (!etiquettesBin) { setErreur('Choisissez un emplacement.'); return }
    setErreur(null)
    try {
      const { data } = await entrepotCasiersApi.etiquettesPdf(etiquettesBin)
      ouvrirBlob(data)
    } catch (err) {
      setErreur(await messageServeurBlob(err, 'Étiquettes indisponibles.'))
    }
  }

  const champ = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  return (
    <div className="space-y-4">
      <PageHeader
        style={{ '--module-accent': INVENTAIRE_ACCENT }}
        className="app-accent-rail mb-0"
        headingAs="h1"
        title="Casiers de l'entrepôt"
        subtitle="Seuils de réappro, tâches de réappro, étiquettes et suggestions de reslotting."
      />

      {erreur && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {erreur}
        </div>
      )}
      {info && (
        <div role="status" className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
          {info}
        </div>
      )}

      <Section id="casiers-sous-seuil" titre="Casiers à réapprovisionner">
        <div className="mb-3">
          <Button onClick={generer} disabled={enCours === 'gen'}>Générer les tâches</Button>
        </div>
        {sousSeuil.length === 0 ? <Vide>Aucun casier sous son seuil.</Vide> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem]">
              <thead><tr>
                <TH>Casier</TH><TH>Produit</TH><TH>Présent</TH><TH>Seuil</TH>
                <TH>À transférer</TH><TH>Depuis</TH><TH><span className="sr-only">Actions</span></TH>
              </tr></thead>
              <tbody>
                {sousSeuil.map((c) => (
                  <tr key={c.seuil_id} className="border-t border-[var(--border)]">
                    <TD>{c.bin_code}</TD><TD>{c.produit_nom}</TD>
                    <TD>{c.quantite_presente}</TD><TD>{c.seuil}</TD>
                    <TD>{c.quantite_a_transferer}</TD><TD>{c.bin_source_code ?? '—'}</TD>
                    <TD>
                      <Button size="sm" variant="outline" onClick={() => ouvrirHistorique(c.bin)}>
                        Historique
                      </Button>
                    </TD>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {historique && (
          <div className="mt-3 rounded-md border border-[var(--border)] p-3">
            <h3 className="mb-2 text-sm font-medium">Historique du casier {historique.bin_code}</h3>
            {historique.lignes.length === 0 ? <Vide>Aucune modification.</Vide> : (
              <ul className="space-y-1 text-sm">
                {historique.lignes.map((l) => (
                  <li key={l.id}>
                    {new Date(l.date).toLocaleString('fr-FR')} — {l.action}
                    {l.champ ? ` (${l.champ} : ${l.ancienne_valeur} → ${l.nouvelle_valeur})` : ''}
                    {' · '}<strong>{l.auteur}</strong>
                  </li>
                ))}
              </ul>
            )}
            <Button size="sm" variant="ghost" className="mt-2" onClick={() => setHistorique(null)}>
              Fermer
            </Button>
          </div>
        )}
      </Section>

      <Section id="taches-reappro" titre="Tâches de réappro">
        {taches.length === 0 ? <Vide>Aucune tâche à faire.</Vide> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem]">
              <thead><tr>
                <TH>Produit</TH><TH>De</TH><TH>Vers</TH><TH>Quantité</TH><TH>Statut</TH>
                <TH><span className="sr-only">Actions</span></TH>
              </tr></thead>
              <tbody>
                {taches.map((t) => (
                  <tr key={t.id} className="border-t border-[var(--border)]">
                    <TD>{nomProduit(t.produit)}</TD>
                    <TD>{t.bin_source_code ?? '—'}</TD><TD>{t.bin_cible_code}</TD>
                    <TD>{t.quantite}</TD><TD>{STATUTS_TACHE[t.statut] ?? t.statut}</TD>
                    <TD>
                      {t.statut === 'a_faire' && (
                        <Button size="sm" onClick={() => executer(t)} disabled={enCours === `exe-${t.id}`}>
                          Exécuter
                        </Button>
                      )}
                    </TD>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section id="seuils-reappro" titre="Seuils de réappro par casier">
        <form onSubmit={ajouterSeuil} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Casier</span>
            <select value={form.bin} onChange={champ('bin')} className={selectCls}>
              <option value="">—</option>
              {emplacements.map((e) => <option key={e.id} value={e.id}>{libEmplacement(e)}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Produit</span>
            <select value={form.produit} onChange={champ('produit')} className={selectCls}>
              <option value="">—</option>
              {produits.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Seuil</span>
            <Input type="number" step="any" value={form.seuil} onChange={champ('seuil')} className="w-28" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Quantité cible</span>
            <Input type="number" step="any" value={form.quantite_cible} onChange={champ('quantite_cible')} className="w-28" />
          </label>
          <Button type="submit" disabled={enCours === 'seuil'}>Ajouter le seuil</Button>
        </form>
        {seuils.length === 0 ? <Vide>Aucun seuil défini.</Vide> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[32rem]">
              <thead><tr>
                <TH>Casier</TH><TH>Produit</TH><TH>Seuil</TH><TH>Cible</TH><TH>Actif</TH>
                <TH><span className="sr-only">Actions</span></TH>
              </tr></thead>
              <tbody>
                {seuils.map((s) => (
                  <tr key={s.id} className="border-t border-[var(--border)]">
                    <TD>{s.bin_code}</TD><TD>{nomProduit(s.produit)}</TD>
                    <TD>{s.seuil}</TD><TD>{s.quantite_cible ?? '—'}</TD>
                    <TD>{s.actif ? 'Oui' : 'Non'}</TD>
                    <TD>
                      {confirmeSeuil === s.id ? (
                        <span className="flex gap-1">
                          <Button size="sm" variant="destructive" onClick={() => supprimerSeuil(s.id)}>
                            Confirmer
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setConfirmeSeuil(null)}>
                            Annuler
                          </Button>
                        </span>
                      ) : (
                        <span className="flex gap-1">
                          <Button size="sm" variant="outline"
                            onClick={() => geste(`act-${s.id}`,
                              () => entrepotCasiersApi.updateSeuil(s.id, { actif: !s.actif }),
                              'Modification impossible.')}>
                            {s.actif ? 'Désactiver' : 'Activer'}
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => setConfirmeSeuil(s.id)}>
                            Supprimer
                          </Button>
                        </span>
                      )}
                    </TD>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section id="etiquettes" titre="Étiquettes de casiers">
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Emplacement</span>
            <select value={etiquettesBin} onChange={(e) => setEtiquettesBin(e.target.value)} className={selectCls}>
              <option value="">—</option>
              {emplacements.map((e) => <option key={e.id} value={e.id}>{libEmplacement(e)}</option>)}
            </select>
          </label>
          <Button variant="outline" onClick={telechargerEtiquettes}>Télécharger la planche</Button>
        </div>
      </Section>

      <Section id="reslotting" titre="Suggestions de reslotting">
        {reslotting.length === 0 ? <Vide>Aucune suggestion.</Vide> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[32rem]">
              <thead><tr>
                <TH>Produit</TH><TH>Classe</TH><TH>Casier actuel</TH><TH>Casier suggéré</TH><TH>Quantité</TH>
              </tr></thead>
              <tbody>
                {reslotting.map((r) => (
                  <tr key={r.produit_id} className="border-t border-[var(--border)]">
                    <TD>{r.produit_nom}</TD><TD>{r.classe_abc}</TD>
                    <TD>{r.bin_actuel_code}</TD><TD>{r.bin_suggere_code}</TD><TD>{r.quantite}</TD>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  )
}
