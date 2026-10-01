// QJR667 (décision fondateur 01/10/2026 : construire l'écran) — bloc
// « Lots / multi-sites » de l'Édition complète, sur l'action existante
// `lots` (NTCPQ18). Contrat partagé (PACT10) :
// `apps/ventes/contract_samples/devis_lots.json`.
//
// Replié par défaut : rien n'est lu tant que le vendeur ne l'ouvre pas.
// Ouvert, il lit les sous-totaux par lot (GET) et les lignes ENREGISTRÉES du
// devis (leurs ids serveur — l'écran peut porter des lignes pas encore
// enregistrées), puis crée un lot en y rattachant des lignes (POST). Après
// une création, `onChange` demande au parent de relire le devis.
// Jamais prix d'achat ni marge à l'écran.
import { useState } from 'react'
import { Building2 } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { Button, Card, CardContent, Checkbox, Input, Label } from '../../ui'
import { formatMAD } from '../../lib/format'
import { corpsCreationLot, messageErreurLots } from './lotsBoq'

const FORM_VIDE = { nom_lot: '', adresse_site: '', ordre: '', lignes: [] }

function LigneTotaux({ libelle, totaux, testid }) {
  if (!totaux) return null
  return (
    <li className="flex flex-wrap items-center gap-2 px-3 py-2" data-testid={testid}>
      <span className="font-medium">{libelle}</span>
      <span className="ml-auto text-muted-foreground">{formatMAD(totaux.ht_net)} HT</span>
      <span>{formatMAD(totaux.ttc)} TTC</span>
    </li>
  )
}

/**
 * @param {number}   devisId     devis rouvert en Édition complète
 * @param {boolean}  modifiable  verdict servi (QJR516) : sinon lecture seule
 * @param {function} [onChange]  après une création : le parent relit le devis
 */
export default function LotsMultiSites({ devisId, modifiable, onChange }) {
  const [ouvert, setOuvert] = useState(false)
  const [lots, setLots] = useState(null)
  const [lignes, setLignes] = useState([])
  const [form, setForm] = useState(FORM_VIDE)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const charger = async () => {
    setErreur('')
    try {
      const [rLots, rDevis] = await Promise.all([
        ventesApi.getLotsDevis(devisId), ventesApi.getDevisById(devisId)])
      setLots(rLots?.data ?? null)
      setLignes((rDevis?.data?.lignes ?? [])
        .filter(l => (l.type_ligne ?? 'produit') === 'produit'))
    } catch (err) {
      setLots(null)
      setErreur(messageErreurLots(err))
    }
  }

  const basculer = () => {
    const suivant = !ouvert
    setOuvert(suivant)
    if (suivant) charger()
  }

  const cocher = (id, coche) => setForm(f => ({
    ...f,
    lignes: coche ? [...f.lignes, id] : f.lignes.filter(x => x !== id),
  }))

  const creer = async (e) => {
    e.preventDefault()
    const corps = corpsCreationLot(form)
    if (!corps.nom_lot) { setErreur('Nom de lot requis.'); return }
    setEnCours(true)
    setErreur('')
    try {
      const { data } = await ventesApi.creerLotDevis(devisId, corps)
      setLots(data ?? null)
      setForm(FORM_VIDE)
      onChange?.()
    } catch (err) {
      setErreur(messageErreurLots(err))
    } finally {
      setEnCours(false)
    }
  }

  const nomLot = Object.fromEntries((lots?.lots ?? []).map(l => [l.id, l.nom_lot]))

  return (
    <Card data-testid="lots-multi-sites">
      <CardContent className="pt-4 space-y-3">
        <div className="flex items-center gap-2">
          <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Building2 className="size-4" aria-hidden="true" /> Lots / multi-sites
          </p>
          <Button type="button" size="xs" variant="outline" className="ml-auto"
                  aria-expanded={ouvert} onClick={basculer}>
            {ouvert ? 'Masquer' : 'Afficher'}
          </Button>
        </div>

        {ouvert && (
          <>
            {lots && lots.lots.length === 0 && (
              <p className="text-xs text-muted-foreground">
                Aucun lot : le devis est mono-site.
              </p>
            )}
            {lots && lots.lots.length > 0 && (
              <ul className="divide-y divide-border rounded-md border border-border text-sm">
                {lots.lots.map(lot => (
                  <LigneTotaux key={lot.id} testid={`lot-${lot.id}`}
                    libelle={lot.adresse_site ? `${lot.nom_lot} — ${lot.adresse_site}` : lot.nom_lot}
                    totaux={lot.totaux} />
                ))}
                <LigneTotaux libelle="Hors lot" totaux={lots.hors_lot} testid="lot-hors-lot" />
                <LigneTotaux libelle="Total consolidé" totaux={lots.total_consolide}
                             testid="lot-total-consolide" />
              </ul>
            )}

            {modifiable && (
              <form className="space-y-2" noValidate onSubmit={creer} data-testid="lot-formulaire">
                <p className="text-xs text-muted-foreground">
                  Enregistrez d’abord vos modifications en cours : l’écran est
                  rechargé après la création du lot.
                </p>
                <div className="grid gap-2 sm:grid-cols-3">
                  <div>
                    <Label htmlFor="lot-nom">Nom du lot</Label>
                    <Input id="lot-nom" value={form.nom_lot}
                           onChange={e => setForm(f => ({ ...f, nom_lot: e.target.value }))} />
                  </div>
                  <div>
                    <Label htmlFor="lot-adresse">Adresse du site</Label>
                    <Input id="lot-adresse" value={form.adresse_site}
                           onChange={e => setForm(f => ({ ...f, adresse_site: e.target.value }))} />
                  </div>
                  <div>
                    <Label htmlFor="lot-ordre">Ordre</Label>
                    <Input id="lot-ordre" type="number" step="any" inputMode="numeric"
                           value={form.ordre}
                           onChange={e => setForm(f => ({ ...f, ordre: e.target.value }))} />
                  </div>
                </div>
                {lignes.length > 0 && (
                  <fieldset className="space-y-1">
                    <legend className="text-xs font-medium">Lignes rattachées à ce lot</legend>
                    {lignes.map(l => (
                      <label key={l.id} className="flex items-center gap-2 text-sm">
                        <Checkbox checked={form.lignes.includes(l.id)}
                                  aria-label={l.designation}
                                  onCheckedChange={v => cocher(l.id, v === true)} />
                        <span>{l.designation}</span>
                        {l.lot && nomLot[l.lot] && (
                          <span className="text-xs text-muted-foreground">({nomLot[l.lot]})</span>
                        )}
                      </label>
                    ))}
                  </fieldset>
                )}
                <Button type="submit" size="sm" disabled={enCours}>
                  Créer le lot
                </Button>
              </form>
            )}
            {erreur && <p className="text-xs text-destructive" role="alert">{erreur}</p>}
          </>
        )}
      </CardContent>
    </Card>
  )
}
