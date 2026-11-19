// « Batteries au départ » — banque de batteries en deux temps (C&I).
// Fondateur 17/11/2026 : on CHOISIT de 1 au maximum calculé par le moteur ; le
// serveur réécrit les lignes de l'option batterie du brouillon (panneaux
// redimensionnés pour ce nombre, onduleur hybride conservé pour le maximum) et
// l'écran RELIT le devis par le chargeur `?edit=` (`recharger` =
// `rechargerDevisRecompose`, useChargeurEdition.js) — aucune fusion de lignes ici.
import { useState } from 'react'
import {
  Label, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import { useConfirmDialog } from '../../../ui/confirm'
import ventesApi from '../../../api/ventesApi'
import { formatNumber } from '../../../lib/format'
import { peutEditerDevis } from '../../../features/ventes/devisStatuts'
import {
  ligneBatterieUnique, quantiteRecommandee, phraseOnduleurExtension,
} from '../../../features/ventes/calc/batteriesDepart.js'

/** Message du refus serveur, en français, jamais générique. */
function messageRefus(err) {
  const data = err?.response?.data
  const champ = data?.nb_batteries
  const premier = Array.isArray(champ) ? champ[0] : champ
  const texte = premier ?? data?.detail
  if (texte) return String(texte)
  if (!err?.response) return 'Le serveur ne répond pas : le nombre de batteries n’a pas été modifié.'
  return `Le serveur a refusé le recalcul (code ${err.response.status}) : le nombre de batteries n’a pas été modifié.`
}

const pluriel = (n) => `${formatNumber(n)} batterie${n > 1 ? 's' : ''}`

const CONFIRMER_RELECTURE = 'Les modifications non enregistrées des lignes seront perdues.'

/**
 * Fondateur 19/11/2026 — la case « démarrer avec une seule batterie » : l'entrée
 * `etude_params.options.phrase_une_batterie` (PATCH fusionnant `etude-params`, objet
 * `options` complet). Le PRIX et les PANNEAUX viennent du serveur
 * (`etude_ci.depart_une_batterie`, contrat `devis_depart_une_batterie.json`) ; s'il ne
 * peut pas les calculer, son refus (`depart_une_batterie_refus`) est dit ici, jamais au
 * client. Aucun chiffre calculé à l'écran.
 */
function CasePhraseUneBatterie({ ecran, raison, occupe, setOccupe, confirmer }) {
  const { editDevis, recharger } = ecran || {}
  const [refus, setRefus] = useState(null)
  const options = editDevis?.etude_params?.options || {}
  const cochee = options.phrase_une_batterie === true
  const etudeCi = editDevis?.etude_params?.etude_ci || {}
  const depart = etudeCi.depart_une_batterie || null
  const refusServeur = etudeCi.depart_une_batterie_refus?.message || null

  async function basculer(coche) {
    setRefus(null)
    if (!(await confirmer('Enregistrer ce choix tout de suite ?'))) return
    const suivantes = { ...options }
    if (coche) suivantes.phrase_une_batterie = true
    else delete suivantes.phrase_une_batterie
    setOccupe(true)
    try {
      await ventesApi.patchEtudeParams(editDevis.id, { options: suivantes })
      recharger?.()
    } catch (err) {
      setRefus(messageRefus(err))
    } finally {
      setOccupe(false)
    }
  }

  return (
    <div className="grid gap-1" data-testid="gen-phrase-une-batterie-bloc">
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input type="checkbox" data-testid="gen-phrase-une-batterie" checked={cochee}
               disabled={occupe || raison != null}
               onChange={(e) => basculer(e.target.checked)} />
        Indiquer au client le prix pour démarrer avec une seule batterie
      </label>
      {cochee && depart && (
        <p className="text-xs text-muted-foreground" data-testid="gen-phrase-une-batterie-apercu">
          Phrase imprimée : 1 batterie, {formatNumber(depart.nb_panneaux)} panneaux
          ({formatNumber(depart.kwc, { decimals: 2 })} kWc) — {formatNumber(depart.total_ttc)} MAD TTC
          ({formatNumber(depart.total_ht)} MAD HT)
        </p>
      )}
      {cochee && !depart && (
        <p className="text-xs text-destructive" role="alert" data-testid="gen-phrase-une-batterie-non-imprimee">
          {refusServeur || 'Phrase non imprimée : le prix à une batterie n’est pas encore calculé (il se calcule avec l’étude du devis).'}
        </p>
      )}
      {refus && <p className="text-xs text-destructive" role="alert" data-testid="gen-phrase-une-batterie-refus">{refus}</p>}
    </div>
  )
}

export default function ControleBatteriesDepart({ lines, produits, ecran }) {
  const { editDevis, dirty, recharger, optionAvec } = ecran || {}
  const { confirm } = useConfirmDialog()
  const [occupe, setOccupe] = useState(false)
  const [refus, setRefus] = useState(null)
  const [resultat, setResultat] = useState(null)
  const ligne = ligneBatterieUnique(lines, produits)
  if (!ligne) return null

  const banque = editDevis?.etude_params?.banque_recommandee ?? null
  const reco = resultat?.quantite_recommandee
    ?? quantiteRecommandee(ligne, banque, optionAvec?.batterie)
  const saisie = parseFloat(ligne.quantite)
  const courant = Number.isInteger(saisie) && saisie > 0 ? saisie : null
  const maxChoix = Math.max(reco ?? 0, courant ?? 0, 1)
  const extension = resultat?.onduleur_extension
    ?? editDevis?.etude_params?.etude_ci?.option_avec?.onduleur_extension
    ?? optionAvec?.onduleur_extension ?? null
  const phraseExt = phraseOnduleurExtension(extension, courant)

  let raison = null
  if (!editDevis?.id) raison = 'Enregistrez le devis pour choisir le nombre de batteries'
  else if (!peutEditerDevis(editDevis)) raison = 'Devis envoyé : utilisez Réviser'
  // Brouillon local modifié : la relecture qui suit l'écriture serveur le perdrait.
  const confirmerRelecture = async (title) => !dirty || confirm({
    title, description: CONFIRMER_RELECTURE, confirmLabel: 'Enregistrer',
  })
  const phraseCochee = editDevis?.etude_params?.options?.phrase_une_batterie === true

  async function choisir(valeur) {
    const nb = Number(valeur)
    if (!nb || nb === courant) return
    setRefus(null)
    if (dirty) {
      const ok = await confirm({
        title: 'Recalculer les lignes de l’option batterie ?',
        description: `Les lignes de l'option batterie vont être recalculées pour ${pluriel(nb)}. `
          + 'Les modifications non enregistrées des lignes seront perdues.',
        confirmLabel: 'Recalculer',
      })
      if (!ok) return
    }
    setOccupe(true)
    try {
      const { data } = await ventesApi.recomposerBatteriesCi(editDevis.id, nb)
      setResultat(data)
      recharger?.()
    } catch (err) {
      setRefus(messageRefus(err))
    } finally {
      setOccupe(false)
    }
  }

  const options = Array.from({ length: maxChoix }, (_, i) => i + 1)
  return (
    <div className="grid gap-1.5" data-testid="gen-batteries-depart-bloc" aria-busy={occupe || undefined}>
      <Label htmlFor="gen-batteries-depart">Batteries au départ</Label>
      <Select value={courant != null ? String(courant) : ''} onValueChange={choisir}
              disabled={occupe || raison != null}>
        <SelectTrigger id="gen-batteries-depart" data-testid="gen-batteries-depart">
          <SelectValue placeholder="Choisir" />
        </SelectTrigger>
        <SelectContent>
          {options.map(n => (
            <SelectItem key={n} value={String(n)}>
              {n === reco ? `${pluriel(n)} (maximum calculé)` : pluriel(n)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {raison && <p className="text-xs text-muted-foreground" data-testid="gen-batteries-depart-raison">{raison}</p>}
      {reco == null && !raison && (
        <p className="text-xs text-muted-foreground" data-testid="gen-batteries-depart-inconnu">
          Maximum calculé inconnu sur ce devis — choisir un nombre le recalcule
        </p>
      )}
      {reco != null && courant != null && (
        <p className="text-xs text-muted-foreground" data-testid="gen-batteries-depart-reco">
          Recommandé : {reco}
          {reco > courant && ` — ${reco - courant} à ajouter plus tard (panneaux réduits, onduleur déjà dimensionné pour ${reco})`}
          {reco < courant && ` — au-delà de la recommandation (${reco})`}
        </p>
      )}
      {resultat && !refus && (
        <p className="text-xs text-success" role="status" data-testid="gen-batteries-depart-ok">
          {pluriel(resultat.nb_batteries)} sur {formatNumber(resultat.quantite_recommandee)} — panneaux de
          l’option batterie : {formatNumber(resultat.nb_panneaux_avec)} ({formatNumber(resultat.kwc_avec, { decimals: 2 })} kWc)
        </p>
      )}
      {refus && <p className="text-xs text-destructive" role="alert" data-testid="gen-batteries-depart-refus">{refus}</p>}
      {phraseExt && (
        <p className="text-xs text-muted-foreground" data-testid="gen-onduleur-extension">{phraseExt}</p>
      )}
      {((courant != null && courant >= 2) || phraseCochee) && (
        <CasePhraseUneBatterie ecran={ecran} raison={raison} occupe={occupe} setOccupe={setOccupe}
                               confirmer={confirmerRelecture} />
      )}
    </div>
  )
}
