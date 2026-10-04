import { useCallback, useEffect, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { Button, FormField, Input } from '../../ui'

/* ============================================================================
   AGR623 — profils saisonniers de réappro (saison d'irrigation) d'un produit.

   L'API existe (contrat `profils_saisonniers.json`, création via le service
   anti-chevauchement) mais aucun écran ne la consommait : le fondateur ne
   pouvait pas saisir la saison. Cette section liste, crée, modifie et supprime
   les profils d'UN produit. RIEN n'est semé et RIEN n'a de défaut : mois,
   seuils et quantité cible sont des données du fondateur, tapées, jamais
   arrondies (`step="any"`, formulaire `noValidate`). Les refus du serveur
   (chevauchement : `{detail}`, ou erreurs par champ) s'affichent SOUS le champ.
   ========================================================================== */

const CHAMPS = ['nom', 'mois_debut', 'mois_fin', 'seuil_min', 'seuil_max', 'quantite_cible']
const VIDE = { nom: '', mois_debut: '', mois_fin: '', seuil_min: '', seuil_max: '', quantite_cible: '' }

const enTexte = (v) => (v === null || v === undefined ? '' : String(v))
const enNombre = (v) => (String(v).trim() === '' ? null : Number(v))

function etatDepuisProfil(profil) {
  const etat = {}
  for (const cle of CHAMPS) etat[cle] = enTexte(profil?.[cle])
  return etat
}

// Les valeurs tapées partent telles quelles : '' → null (jamais 0), nombre → nombre.
function payloadProfil(etat) {
  return {
    nom: etat.nom.trim(),
    mois_debut: enNombre(etat.mois_debut),
    mois_fin: enNombre(etat.mois_fin),
    seuil_min: enNombre(etat.seuil_min),
    seuil_max: enNombre(etat.seuil_max),
    quantite_cible: enNombre(etat.quantite_cible),
  }
}

function erreursDepuisReponse(data) {
  const parChamp = {}
  let detail = null
  if (data && typeof data === 'object') {
    for (const [cle, valeur] of Object.entries(data)) {
      const message = Array.isArray(valeur) ? valeur.find((v) => typeof v === 'string') : valeur
      if (typeof message !== 'string') continue
      if (cle === 'detail' || cle === 'non_field_errors') detail = message
      else parChamp[cle] = message
    }
  }
  return { parChamp, detail }
}

export default function ProfilsSaisonniersSection({ produit, canWrite = false }) {
  const [profils, setProfils] = useState([])
  const [charge, setCharge] = useState(false)
  // `null` = formulaire fermé ; `{ id: null }` = création ; `{ id }` = édition.
  const [edition, setEdition] = useState(null)
  const [etat, setEtat] = useState(VIDE)
  const [erreurs, setErreurs] = useState({ parChamp: {}, detail: null })
  const [saving, setSaving] = useState(false)

  const recharger = useCallback(async () => {
    try {
      const r = await stockApi.getProfilsSaisonniers({ produit: produit.id })
      setProfils(r.data?.results ?? r.data ?? [])
    } catch {
      setProfils([])
    } finally {
      setCharge(true)
    }
  }, [produit.id])

  useEffect(() => {
    let actif = true
    stockApi.getProfilsSaisonniers({ produit: produit.id })
      .then((r) => { if (actif) setProfils(r.data?.results ?? r.data ?? []) })
      .catch(() => { if (actif) setProfils([]) })
      .finally(() => { if (actif) setCharge(true) })
    return () => { actif = false }
  }, [produit.id])

  const ouvrirCreation = () => {
    setEtat(VIDE)
    setErreurs({ parChamp: {}, detail: null })
    setEdition({ id: null })
  }
  const ouvrirEdition = (profil) => {
    setEtat(etatDepuisProfil(profil))
    setErreurs({ parChamp: {}, detail: null })
    setEdition({ id: profil.id })
  }
  const fermer = () => setEdition(null)
  const setChamp = (cle, valeur) => {
    setEtat((e) => ({ ...e, [cle]: valeur }))
    setErreurs((er) => ({ detail: null, parChamp: { ...er.parChamp, [cle]: undefined } }))
  }

  const enregistrer = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErreurs({ parChamp: {}, detail: null })
    try {
      const payload = payloadProfil(etat)
      if (edition?.id) {
        await stockApi.updateProfilSaisonnier(edition.id, payload)
      } else {
        await stockApi.createProfilSaisonnier({ produit: produit.id, ...payload })
      }
      setEdition(null)
      await recharger()
    } catch (err) {
      const refus = erreursDepuisReponse(err?.response?.data)
      setErreurs(refus.detail || Object.keys(refus.parChamp).length
        ? refus
        : { parChamp: {}, detail: "Le profil n'a pas pu être enregistré." })
    } finally {
      setSaving(false)
    }
  }

  const supprimer = async (profil) => {
    try {
      await stockApi.deleteProfilSaisonnier(profil.id)
      await recharger()
    } catch {
      setErreurs({ parChamp: {}, detail: "Le profil n'a pas pu être supprimé." })
    }
  }

  const idErreurSaison = 'psais-erreur-saison'

  return (
    <div className="flex flex-col gap-3" data-testid="profils-saisonniers">
      <p className="text-xs text-muted-foreground">
        Saison de réapprovisionnement de ce produit (par exemple la saison
        d&apos;irrigation) : mois de début et de fin, seuils et quantité cible.
        Aucune valeur n&apos;est proposée — saisissez les vôtres.
      </p>

      {!charge ? null : profils.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucun profil saisonnier pour ce produit.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {profils.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2 text-sm"
                data-testid={`profil-saisonnier-${p.id}`}>
              <span className="font-medium">{p.nom || 'Sans nom'}</span>
              <span>mois {enTexte(p.mois_debut)} → {enTexte(p.mois_fin)}</span>
              <span>seuil min {enTexte(p.seuil_min) || '—'}</span>
              <span>seuil max {enTexte(p.seuil_max) || '—'}</span>
              <span>cible {enTexte(p.quantite_cible) || '—'}</span>
              {canWrite && (
                <span className="ml-auto flex gap-1">
                  <Button type="button" variant="ghost" size="icon"
                          aria-label={`Modifier le profil ${p.nom || p.id}`}
                          onClick={() => ouvrirEdition(p)}>
                    <Pencil className="size-4" aria-hidden="true" />
                  </Button>
                  <Button type="button" variant="ghost" size="icon"
                          aria-label={`Supprimer le profil ${p.nom || p.id}`}
                          onClick={() => supprimer(p)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </Button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {canWrite && !edition && (
        <Button type="button" variant="outline" size="sm" className="self-start"
                onClick={ouvrirCreation}>
          <Plus className="size-4" aria-hidden="true" /> Ajouter un profil
        </Button>
      )}

      {edition && (
        <form noValidate onSubmit={enregistrer} data-testid="profil-saisonnier-form"
              className="grid grid-cols-1 gap-3 rounded-lg border border-border p-3 sm:grid-cols-2">
          <FormField label="Nom" htmlFor="psais-nom" error={erreurs.parChamp.nom}>
            <Input id="psais-nom" value={etat.nom}
                   onChange={(e) => setChamp('nom', e.target.value)} />
          </FormField>
          <FormField label="Mois de début" htmlFor="psais-debut" error={erreurs.parChamp.mois_debut}>
            <Input id="psais-debut" type="number" step="any" inputMode="decimal"
                   value={etat.mois_debut}
                   aria-describedby={erreurs.detail ? idErreurSaison : undefined}
                   onChange={(e) => setChamp('mois_debut', e.target.value)} />
          </FormField>
          <FormField label="Mois de fin" htmlFor="psais-fin" error={erreurs.parChamp.mois_fin}>
            <Input id="psais-fin" type="number" step="any" inputMode="decimal"
                   value={etat.mois_fin}
                   aria-describedby={erreurs.detail ? idErreurSaison : undefined}
                   onChange={(e) => setChamp('mois_fin', e.target.value)} />
          </FormField>
          {erreurs.detail && (
            <p id={idErreurSaison} role="alert" className="sm:col-span-2 text-xs text-destructive">
              {erreurs.detail}
            </p>
          )}
          <FormField label="Seuil minimum" htmlFor="psais-min" error={erreurs.parChamp.seuil_min}>
            <Input id="psais-min" type="number" step="any" inputMode="decimal"
                   value={etat.seuil_min}
                   onChange={(e) => setChamp('seuil_min', e.target.value)} />
          </FormField>
          <FormField label="Seuil maximum" htmlFor="psais-max" error={erreurs.parChamp.seuil_max}>
            <Input id="psais-max" type="number" step="any" inputMode="decimal"
                   value={etat.seuil_max}
                   onChange={(e) => setChamp('seuil_max', e.target.value)} />
          </FormField>
          <FormField label="Quantité cible" htmlFor="psais-cible" error={erreurs.parChamp.quantite_cible}>
            <Input id="psais-cible" type="number" step="any" inputMode="decimal"
                   value={etat.quantite_cible}
                   onChange={(e) => setChamp('quantite_cible', e.target.value)} />
          </FormField>
          <div className="sm:col-span-2 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={fermer}>Annuler</Button>
            <Button type="submit" loading={saving}>Enregistrer le profil</Button>
          </div>
        </form>
      )}
    </div>
  )
}
