// NTMFG26 — Assistant de création d'Ordre de Fabrication en 3 étapes :
// 1) produit (recherche + nomenclature si existante) ; 2) gamme/quantité/date
// souhaitée (calcul auto d'une fin prévisionnelle APPROXIMATIVE — la date
// réelle reste calculée par le planificateur, NTMFG3, à la confirmation) ;
// 3) récapitulatif + vérification NON BLOQUANTE (charge atelier NTMFG18 +
// besoin net stock NTMFG5) avant de créer l'OF (brouillon, NTMFG3).
// Annulable à toute étape (aucun appel d'écriture avant la validation finale).
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, CheckCircle2, Wand2 } from 'lucide-react'
import mrpApi from '../../api/mrpApi'
import stockApi from '../../api/stockApi'
import { Badge, Button, Card, CardContent, Combobox, Input, Label, Spinner } from '../../ui'
import { PageHeader } from '../../ui/PageHeader'

const ETAPES = ['Produit', 'Gamme & quantité', 'Confirmation']

export default function AssistantCreationOF() {
  const navigate = useNavigate()
  const [etape, setEtape] = useState(0)

  // Étape 1 — produit + gammes disponibles.
  const [produitId, setProduitId] = useState('')
  const [produitLabel, setProduitLabel] = useState('')
  const [gammes, setGammes] = useState([])
  const [gammesLoading, setGammesLoading] = useState(false)

  const onSearchProduit = async (query) => {
    const resp = await stockApi.getProduits({ search: query, page_size: 20 })
    const hits = resp.data?.results || resp.data || []
    return hits.map((p) => ({ value: String(p.id), label: p.nom }))
  }

  const choisirProduit = async (id, label) => {
    setProduitId(id || '')
    setProduitLabel(label || '')
    setGammeId('')
    if (!id) { setGammes([]); return }
    setGammesLoading(true)
    try {
      const resp = await mrpApi.getGammes({ produit: id, actif: true })
      setGammes(resp.data?.results || resp.data || [])
    } finally {
      setGammesLoading(false)
    }
  }

  // Étape 2 — gamme + quantité + date souhaitée.
  const [gammeId, setGammeId] = useState('')
  const [quantite, setQuantite] = useState('1')
  const [dateSouhaitee, setDateSouhaitee] = useState('')

  const gammeChoisie = useMemo(
    () => gammes.find((g) => String(g.id) === String(gammeId)),
    [gammes, gammeId])

  const dateFinEstimee = useMemo(() => {
    if (!dateSouhaitee || !gammeChoisie) return null
    const tempsMin = Number(gammeChoisie.temps_total_prevu_1_unite || 0) * (Number(quantite) || 1)
    const jours = Math.max(1, Math.ceil(tempsMin / (8 * 60))) // Estimation 8h/jour.
    const d = new Date(dateSouhaitee)
    d.setDate(d.getDate() + jours)
    return d.toISOString().slice(0, 10)
  }, [dateSouhaitee, gammeChoisie, quantite])

  // Étape 3 — vérification (sans écriture) + création.
  const [verifBusy, setVerifBusy] = useState(false)
  const [verif, setVerif] = useState(null)
  const [creerBusy, setCreerBusy] = useState(false)
  const [creeOf, setCreeOf] = useState(null)
  const [erreur, setErreur] = useState(null)

  const verifierAvantConfirmation = async () => {
    setVerifBusy(true)
    setVerif(null)
    try {
      const [chargeResp, besoinResp] = await Promise.all([
        mrpApi.simulerCharge({
          lignes: [{ produit_id: produitId, quantite }],
          date_souhaitee: dateSouhaitee || undefined,
        }),
        mrpApi.mrpRun({
          produits: [produitId],
          demande_independante: { [produitId]: quantite },
        }),
      ])
      setVerif({
        charge: chargeResp.data,
        besoin: (besoinResp.data || []).find(
          (b) => String(b.produit_id) === String(produitId)),
      })
    } catch {
      setVerif({ erreur: true })
    } finally {
      setVerifBusy(false)
    }
  }

  const allerEtape = (n) => {
    setEtape(n)
    if (n === 2) verifierAvantConfirmation()
  }

  const creerOF = async () => {
    setCreerBusy(true)
    setErreur(null)
    try {
      const resp = await mrpApi.createOrdreFabrication({
        produit: produitId,
        gamme: gammeId || null,
        quantite,
        date_debut_planifiee: dateSouhaitee || undefined,
      })
      setCreeOf(resp.data)
    } catch (err) {
      setErreur(err?.response?.data?.detail || "Création de l'OF impossible.")
    } finally {
      setCreerBusy(false)
    }
  }

  const recommencer = () => {
    setEtape(0)
    setProduitId('')
    setProduitLabel('')
    setGammes([])
    setGammeId('')
    setQuantite('1')
    setDateSouhaitee('')
    setVerif(null)
    setCreeOf(null)
    setErreur(null)
  }

  const chargeAlerte = verif?.charge
    && verif.charge.tenable !== 'sans_gamme' && verif.charge.tenable !== 'tenable'
  const besoinAlerte = verif?.besoin && Number(verif.besoin.besoin_net) > 0

  return (
    <div>
      <PageHeader
        title="Assistant nouvel OF"
        subtitle="Créer un Ordre de Fabrication en 3 étapes guidées."
        icon={Wand2}
      />
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2 mb-4 text-sm">
            {ETAPES.map((label, i) => (
              <Badge key={label} tone={i === etape && !creeOf ? 'info' : 'neutral'}>
                {i + 1}. {label}
              </Badge>
            ))}
          </div>

          {creeOf ? (
            <div className="text-center py-6">
              <CheckCircle2 className="mx-auto mb-2 text-success" size={32} aria-hidden="true" />
              <p className="font-medium">OF-{creeOf.id} créé (brouillon).</p>
              <div className="mt-4 flex justify-center gap-2">
                <Button variant="outline" onClick={recommencer}>Créer un autre OF</Button>
                <Button onClick={() => navigate('/mrp/ordres-fabrication')}>
                  Voir les Ordres de fabrication
                </Button>
              </div>
            </div>
          ) : (
            <>
              {etape === 0 && (
                <div className="grid gap-3 max-w-md">
                  <Label htmlFor="assistant-produit">Produit à fabriquer</Label>
                  <Combobox
                    id="assistant-produit"
                    options={produitId ? [{ value: produitId, label: produitLabel }] : []}
                    value={produitId || null}
                    onSearch={onSearchProduit}
                    onChange={(v, opt) => choisirProduit(v, opt?.label)}
                    placeholder="Rechercher un produit…"
                    searchPlaceholder="Nom du produit…"
                  />
                  {gammesLoading && <Spinner />}
                  {!gammesLoading && produitId && (
                    <p className="text-sm text-muted-foreground">
                      {gammes.length > 0
                        ? `${gammes.length} gamme(s) opératoire(s) trouvée(s) pour ce produit.`
                        : "Aucune gamme opératoire existante pour ce produit — l'OF pourra "
                          + 'être créé sans gamme (suivi seul).'}
                    </p>
                  )}
                  <div className="flex justify-end mt-2">
                    <Button disabled={!produitId} onClick={() => allerEtape(1)}>
                      Suivant <ArrowRight size={16} />
                    </Button>
                  </div>
                </div>
              )}

              {etape === 1 && (
                <div className="grid gap-3 max-w-md">
                  <Label htmlFor="assistant-gamme">Gamme opératoire</Label>
                  <select
                    id="assistant-gamme"
                    className="border rounded-md px-2 py-1.5 text-sm"
                    value={gammeId}
                    onChange={(e) => setGammeId(e.target.value)}
                  >
                    <option value="">— Sans gamme (suivi seul) —</option>
                    {gammes.map((g) => (
                      <option key={g.id} value={g.id}>{g.nom} (v{g.version})</option>
                    ))}
                  </select>

                  <Label htmlFor="assistant-quantite">Quantité</Label>
                  <Input id="assistant-quantite" type="number" min="1" step="any"
                         value={quantite} onChange={(e) => setQuantite(e.target.value)} />

                  <Label htmlFor="assistant-date">Date souhaitée</Label>
                  <Input id="assistant-date" type="date" value={dateSouhaitee}
                         onChange={(e) => setDateSouhaitee(e.target.value)} />

                  {dateFinEstimee && (
                    <p className="text-sm text-muted-foreground">
                      Fin prévisionnelle estimée : {dateFinEstimee} (approximatif — la date
                      réelle est calculée par le planificateur à la confirmation, NTMFG3).
                    </p>
                  )}

                  <div className="flex justify-between mt-2">
                    <Button variant="outline" onClick={() => setEtape(0)}>
                      <ArrowLeft size={16} /> Précédent
                    </Button>
                    <Button disabled={!quantite || Number(quantite) <= 0}
                            onClick={() => allerEtape(2)}>
                      Suivant <ArrowRight size={16} />
                    </Button>
                  </div>
                </div>
              )}

              {etape === 2 && (
                <div className="grid gap-3 max-w-md">
                  <div className="text-sm">
                    <div><strong>Produit :</strong> {produitLabel}</div>
                    <div>
                      <strong>Gamme :</strong>{' '}
                      {gammeChoisie ? `${gammeChoisie.nom} (v${gammeChoisie.version})` : 'Aucune (suivi seul)'}
                    </div>
                    <div><strong>Quantité :</strong> {quantite}</div>
                    <div><strong>Date souhaitée :</strong> {dateSouhaitee || '—'}</div>
                  </div>

                  {verifBusy && <Spinner />}
                  {!verifBusy && verif && !verif.erreur && (
                    <div className="grid gap-2">
                      {chargeAlerte && (
                        <div className="rounded-lg border border-warning/40 bg-warning/10 p-2 text-sm text-warning">
                          Charge atelier : {verif.charge.tenable === 'non_tenable'
                            ? `non tenable sur le poste « ${verif.charge.poste_goulot || '—'} ».`
                            : `tenable avec un retard estimé de ${verif.charge.retard_jours} `
                              + `jour(s) (poste « ${verif.charge.poste_goulot || '—'} »).`}
                        </div>
                      )}
                      {besoinAlerte && (
                        <div className="rounded-lg border border-warning/40 bg-warning/10 p-2 text-sm text-warning">
                          Composant en tension : stock disponible {verif.besoin.stock_disponible},
                          besoin net {verif.besoin.besoin_net}.
                        </div>
                      )}
                      {!chargeAlerte && !besoinAlerte && (
                        <div className="rounded-lg border border-success/30 bg-success/10 p-2 text-sm text-success">
                          Aucun blocage détecté.
                        </div>
                      )}
                    </div>
                  )}

                  {erreur && (
                    <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
                      {erreur}
                    </div>
                  )}

                  <div className="flex justify-between mt-2">
                    <Button variant="outline" onClick={() => setEtape(1)}>
                      <ArrowLeft size={16} /> Précédent
                    </Button>
                    <Button loading={creerBusy} onClick={creerOF}>
                      Créer l'OF
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
