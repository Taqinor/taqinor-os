import { useState } from 'react'
import { Button, Input } from '../../../ui'
import { EnteteStock, BandeauxStock } from '../EnteteStock'
import scannerApi from '../../../features/stock/api/scannerApi'
import { messageServeur } from '../../../features/stock/api/erreurs'

/* ASTK216 — Poste scanner : résoudre un code (produit / casier / lot), poser
   un mouvement scanné (entrée / sortie / transfert) et préparer un retour
   fournisseur. Saisie CLAVIER ou douchette seulement (pas de caméra).

   Règles d'écran : la quantité est un ENTIER (7.5 est refusé sous le champ,
   jamais tronqué) ; toute erreur serveur (transfert sans casier, refus
   hazmat, stock insuffisant…) est affichée mot pour mot ; après un geste, la
   ventilation par emplacement et l'historique du produit sont RELUS du
   serveur (aucun état local persistant). */

const TYPES = [
  { v: 'entree', l: 'Entrée' },
  { v: 'sortie', l: 'Sortie' },
  { v: 'transfert', l: 'Transfert' },
]
const liste = (d) => (Array.isArray(d) ? d : d?.results ?? [])
const selectCls = 'h-9 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-sm'

export default function PosteScannerPage() {
  const [mode, setMode] = useState('mouvement') // mouvement | retour
  const [code, setCode] = useState('')
  const [produit, setProduit] = useState(null)
  const [casiers, setCasiers] = useState([]) // casiers résolus
  const [source, setSource] = useState(null)
  const [destination, setDestination] = useState(null)
  const [type, setType] = useState('entree')
  const [quantite, setQuantite] = useState('')
  const [erreur, setErreur] = useState(null)
  const [erreurQte, setErreurQte] = useState(null)
  const [info, setInfo] = useState(null)
  const [ventilation, setVentilation] = useState([])
  const [historique, setHistorique] = useState([])
  const [ligneRetour, setLigneRetour] = useState(null)
  const [enCours, setEnCours] = useState(false)

  const relire = async (produitId) => {
    const [v, h] = await Promise.allSettled([
      scannerApi.ventilationProduit(produitId),
      scannerApi.historiqueProduit(produitId),
    ])
    if (v.status === 'fulfilled') setVentilation(liste(v.value.data))
    if (h.status === 'fulfilled') setHistorique(liste(h.value.data))
  }

  const resoudre = async () => {
    const saisi = code.trim()
    if (!saisi) { setErreur('Scannez ou saisissez un code.'); return }
    setErreur(null); setInfo(null); setEnCours(true)
    try {
      const { data } = await scannerApi.resoudre(saisi)
      if (data.type === 'produit') {
        setProduit(data)
        relire(data.id)
      } else if (data.type === 'casier') {
        setCasiers((l) => (l.some((c) => c.id === data.id) ? l : [...l, data]))
      } else {
        setInfo(`Code reconnu : ${data.type} « ${data.label} ».`)
      }
      setCode('')
    } catch (err) {
      setErreur(messageServeur(err, 'Code illisible.'))
    } finally { setEnCours(false) }
  }

  // Quantité ENTIÈRE strictement positive — jamais de troncature silencieuse.
  const lireQuantite = () => {
    const n = Number(quantite)
    if (quantite === '' || !Number.isFinite(n)) {
      setErreurQte('Saisissez une quantité.'); return null
    }
    if (!Number.isInteger(n)) {
      setErreurQte('La quantité doit être un nombre entier.'); return null
    }
    if (n <= 0) { setErreurQte('La quantité doit être positive.'); return null }
    setErreurQte(null)
    return n
  }

  const valider = async () => {
    setErreur(null); setInfo(null)
    const n = lireQuantite()
    if (n == null || !produit) return
    const corps = { produit: produit.id, type_mouvement: type, quantite: n }
    if (source) corps.bin_source = source.id
    if (destination) corps.bin_destination = destination.id
    setEnCours(true)
    try {
      await scannerApi.poserMouvement(corps)
      setInfo('Mouvement enregistré.')
      setQuantite('')
      await relire(produit.id)
    } catch (err) {
      setErreur(messageServeur(err, "Le mouvement n'a pas pu être enregistré."))
    } finally { setEnCours(false) }
  }

  const preparerRetour = async () => {
    setErreur(null); setInfo(null)
    const n = lireQuantite()
    if (n == null) return
    if (!code.trim()) { setErreur('Scannez ou saisissez un code.'); return }
    setEnCours(true)
    try {
      const { data } = await scannerApi.retourFournisseur(code.trim(), n)
      setLigneRetour(data)
    } catch (err) {
      setLigneRetour(null)
      setErreur(messageServeur(err, 'Code inconnu.'))
    } finally { setEnCours(false) }
  }

  const surEntree = (fn) => (e) => { if (e.key === 'Enter') { e.preventDefault(); fn() } }

  return (
    <div className="space-y-4">
      <EnteteStock
                title="Poste scanner"
        subtitle="Scannez un produit puis un casier, ou préparez un retour fournisseur."
      />

      <div className="flex gap-2" role="group" aria-label="Mode du poste">
        <Button variant={mode === 'mouvement' ? 'default' : 'outline'} onClick={() => setMode('mouvement')}>
          Mouvement
        </Button>
        <Button variant={mode === 'retour' ? 'default' : 'outline'} onClick={() => setMode('retour')}>
          Retour fournisseur
        </Button>
      </div>

      <BandeauxStock erreur={erreur} info={info} />

      <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Code scanné</span>
            <Input
              sanitize="code" value={code} className="w-64" autoFocus
              onChange={(e) => setCode(e.target.value)}
              onKeyDown={surEntree(mode === 'mouvement' ? resoudre : preparerRetour)}
            />
          </label>
          {mode === 'mouvement' ? (
            <Button onClick={resoudre} disabled={enCours}>Résoudre</Button>
          ) : (
            <>
              <label className="flex flex-col gap-1 text-xs">
                <span>Quantité</span>
                <Input
                  type="number" step="any" value={quantite} className="w-28"
                  invalid={!!erreurQte} aria-describedby="qte-erreur"
                  onChange={(e) => setQuantite(e.target.value)}
                />
              </label>
              <Button onClick={preparerRetour} disabled={enCours}>Préparer le retour</Button>
            </>
          )}
        </div>
        {mode === 'retour' && erreurQte && (
          <p id="qte-erreur" className="mt-1 text-xs text-destructive">{erreurQte}</p>
        )}
      </section>

      {mode === 'retour' && ligneRetour && (
        <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 text-sm">
          <h2 className="mb-2 font-semibold">Ligne de retour préparée</h2>
          <p>{ligneRetour.produit_nom} ({ligneRetour.sku}) × {ligneRetour.quantite}</p>
          <p>De {ligneRetour.bin_source_code || '—'} vers {ligneRetour.bin_destination_code || '—'}</p>
          <p>Fournisseur : {ligneRetour.fournisseur_nom || '—'}</p>
          <p className="mt-2 text-xs text-[var(--muted-foreground)]">
            Lecture seule : rien n'est écrit tant que le retour n'est pas validé.
          </p>
        </section>
      )}

      {mode === 'mouvement' && (
        <>
          <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 text-sm">
            <h2 className="mb-2 font-semibold">Produit scanné</h2>
            {produit ? (
              <p>
                <strong>{produit.label}</strong> ({produit.detail?.sku}) — stock {produit.detail?.quantite_stock}
              </p>
            ) : <p className="text-[var(--muted-foreground)]">Aucun produit scanné.</p>}
            {casiers.length > 0 && (
              <ul className="mt-3 space-y-1">
                {casiers.map((c) => (
                  <li key={c.id} className="flex flex-wrap items-center gap-2">
                    <span>Casier {c.label}</span>
                    <Button size="sm" variant="outline" onClick={() => setSource(c)}>
                      Utiliser comme source
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setDestination(c)}>
                      Utiliser comme destination
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-[var(--muted-foreground)]">
              Source : {source?.label ?? '—'} · Destination : {destination?.label ?? '—'}
            </p>
          </section>

          <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex flex-col gap-1 text-xs">
                <span>Type de mouvement</span>
                <select value={type} onChange={(e) => setType(e.target.value)} className={selectCls}>
                  {TYPES.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs">
                <span>Quantité</span>
                <Input
                  type="number" step="any" value={quantite} className="w-28"
                  invalid={!!erreurQte} aria-describedby="qte-erreur"
                  onChange={(e) => setQuantite(e.target.value)}
                />
              </label>
              <Button onClick={valider} disabled={enCours || !produit}>Valider le mouvement</Button>
            </div>
            {erreurQte && <p id="qte-erreur" className="mt-1 text-xs text-destructive">{erreurQte}</p>}
          </section>

          {produit && (
            <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 text-sm">
              <h2 className="mb-2 font-semibold">Ventilation par emplacement</h2>
              <ul className="space-y-1">
                {ventilation.map((v) => (
                  <li key={v.emplacement_id}>{v.emplacement_nom} : {v.quantite}</li>
                ))}
              </ul>
              <h2 className="mb-2 mt-4 font-semibold">Derniers mouvements</h2>
              {historique.length === 0 ? <p className="text-[var(--muted-foreground)]">Aucun mouvement.</p> : (
                <ul className="space-y-1">
                  {historique.slice(0, 10).map((m) => (
                    <li key={m.id}>{m.type_mouvement} × {m.quantite} — {m.reference}</li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </>
      )}
    </div>
  )
}
