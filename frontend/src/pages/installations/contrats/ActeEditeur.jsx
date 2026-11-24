// Éditeur d'un acte : modifie UNIQUEMENT les sections que le serveur déclare
// modifiables (`sections_modifiables`) et n'envoie que `{ surcharges: { … } }`
// — une clé par section modifiée, `null` pour rétablir le texte par défaut.
// Aucun montant ne se modifie ici : l'échéancier se corrige sur la vente.
import { createContext, useContext, useEffect, useState } from 'react'
import { Plus, Trash2, RotateCcw } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  Button, Input, Label, Textarea, Spinner, toast,
} from '../../../ui'
import documentsApi from '../../../api/documentsApi'
import { confirmLeaveIfDirty } from '../../../ui/useDirtyGuard'
import { detailErreur, formaterDh } from './outils'
import PiedDialogue from './PiedDialogue'
import { useSoumission } from './useSoumission'
import {
  SECTIONS, ORDRE_SECTIONS, brouillonDe, surchargesModifiees,
} from './sections'

// Langue de saisie : en arabe, champs de droite à gauche (dir="rtl" lang="ar").
const LangueContext = createContext('fr')
const attrsLangue = (langue) => (langue === 'ar' ? { dir: 'rtl', lang: 'ar' } : {})

function Champ({ id, libelle, children }) {
  return (
    <div className="contrats-champ">
      <Label htmlFor={id}>{libelle}</Label>
      {children}
    </div>
  )
}

function Texte({ id, libelle, valeur, onChange, type = 'text', ...reste }) {
  const langue = useContext(LangueContext)
  // Une date ou un nombre reste lisible de gauche à droite.
  const attrs = type === 'text' ? attrsLangue(langue) : {}
  return (
    <Champ id={id} libelle={libelle}>
      <Input id={id} type={type} value={valeur} onChange={(e) => onChange(e.target.value)} {...attrs} {...reste} />
    </Champ>
  )
}

function Zone({ id, libelle, valeur, onChange, lignes = 4, aide }) {
  const langue = useContext(LangueContext)
  return (
    <Champ id={id} libelle={libelle}>
      <Textarea id={id} rows={lignes} value={valeur} onChange={(e) => onChange(e.target.value)}
                {...attrsLangue(langue)} />
      {aide && <p className="contrats-editeur__aide">{aide}</p>}
    </Champ>
  )
}

const AIDE_PARAGRAPHES = 'Une ligne vide sépare deux paragraphes ; une ligne qui commence par « - » devient une puce ; **gras** reste tel quel.'

/** Les champs d'une section. `v` = brouillon courant, `m` = fixe la valeur. */
function ChampsSection({ cle, v, m, contenu }) {
  const langue = useContext(LangueContext)
  const p = `contrats-ed-${cle}`
  switch (cle) {
    case 'titre':
      return <Texte id={p} libelle="Titre" valeur={v} onChange={m} />
    case 'lieu':
      return <Texte id={p} libelle="Lieu" valeur={v} onChange={m} />
    case 'date_document':
      return <Texte id={p} libelle="Date du document" type="date" valeur={v} onChange={m} />
    case 'societe':
      return (
        <Texte id={p} libelle="Représentant de la société (nom et qualité)"
               valeur={v.representant} onChange={(x) => m({ ...v, representant: x })} />
      )
    case 'delais':
      return (
        <>
          {/* En arabe la date limite est commune aux deux langues : lecture seule. */}
          {langue === 'ar'
            ? (
              <p className="contrats-editeur__lecture-seule">
                <span>Date limite (réglée en français)</span>
                <strong dir="ltr">{v.date_limite || 'à préciser'}</strong>
              </p>
            )
            : (
              <Texte id={`${p}-date`} libelle="Date limite" type="date" valeur={v.date_limite}
                     onChange={(x) => m({ ...v, date_limite: x })} />
            )}
          <Zone id={`${p}-detail`} libelle="Détail" lignes={2} valeur={v.detail}
                onChange={(x) => m({ ...v, detail: x })} />
        </>
      )
    case 'echeancier_textes':
      return (
        <>
          <p className="contrats-editeur__aide">
            Les montants et les pourcentages se changent sur la vente (l’échéancier du devis),
            pas ici : un contrat ne doit jamais contredire les factures.
          </p>
          {(contenu.echeancier ?? []).map((t) => (
            <div key={t.cle} className="contrats-editeur__tranche">
              <p className="contrats-editeur__tranche-titre">
                <strong>{t.libelle}</strong>
                <span className="contrats-editeur__lecture">
                  {t.pourcentage} % · {formaterDh(t.montant_ttc)}
                </span>
              </p>
              <Texte id={`${p}-${t.cle}-q`} libelle={`Quand — ${t.libelle}`}
                     valeur={v[t.cle]?.exigibilite ?? ''}
                     onChange={(x) => m({ ...v, [t.cle]: { ...v[t.cle], exigibilite: x } })} />
              <Texte id={`${p}-${t.cle}-n`} libelle={`Note — ${t.libelle}`}
                     valeur={v[t.cle]?.note ?? ''}
                     onChange={(x) => m({ ...v, [t.cle]: { ...v[t.cle], note: x } })} />
            </div>
          ))}
        </>
      )
    case 'articles':
      return v.map((a, i) => (
        <div key={a.cle} className="contrats-editeur__bloc">
          <Texte id={`${p}-${a.cle}-t`} libelle={`Titre de l’article ${i + 1}`} valeur={a.titre}
                 onChange={(x) => m(v.map((r, j) => (j === i ? { ...r, titre: x } : r)))} />
          <Zone id={`${p}-${a.cle}-x`} libelle={`Texte de l’article ${i + 1}`} lignes={6}
                valeur={a.texte} aide={AIDE_PARAGRAPHES}
                onChange={(x) => m(v.map((r, j) => (j === i ? { ...r, texte: x } : r)))} />
        </div>
      ))
    case 'garanties':
      return (
        <>
          {v.map((g, i) => {
            const set = (champ) => (x) => m(v.map((r, j) => (j === i ? { ...r, [champ]: x } : r)))
            return (
              <div key={`${g.cle}-${i}`} className="contrats-editeur__bloc">
                <Texte id={`${p}-${i}-d`} libelle={`Désignation (garantie ${i + 1})`}
                       valeur={g.designation} onChange={set('designation')} />
                <div className="contrats-editeur__duo">
                  {/* En arabe, durée et fin viennent du français : lecture seule. */}
                  {langue === 'ar'
                    ? (
                      <p className="contrats-editeur__lecture-seule">
                        <span>Durée en mois (réglée en français)</span>
                        <strong dir="ltr">{g.duree_mois || 'à préciser'}</strong>
                        {g.fin && <span dir="ltr">Fin : {g.fin}</span>}
                      </p>
                    )
                    : (
                      <Texte id={`${p}-${i}-m`} libelle="Durée en mois" type="number" step="any"
                             valeur={g.duree_mois} onChange={set('duree_mois')} />
                    )}
                  <Texte id={`${p}-${i}-g`} libelle="Garant" valeur={g.garant} onChange={set('garant')} />
                </div>
                <Zone id={`${p}-${i}-c`} libelle="Ce que cela couvre" lignes={2}
                      valeur={g.detail ?? ''} onChange={set('detail')} />
                {langue !== 'ar' && (
                  <Button type="button" size="sm" variant="ghost" className="contrats-acte__bouton"
                          onClick={() => m(v.filter((_, j) => j !== i))}>
                    <Trash2 className="size-4" aria-hidden="true" /> Retirer cette garantie
                  </Button>
                )}
              </div>
            )
          })}
          {langue !== 'ar' && (
            <Button type="button" size="sm" variant="outline" className="contrats-acte__bouton"
                    onClick={() => m([...v, {
                      cle: '', designation: '', duree_mois: '', duree_libelle: '',
                      garant: '', detail: '', fin: null,
                    }])}>
              <Plus className="size-4" aria-hidden="true" /> Ajouter une garantie
            </Button>
          )}
        </>
      )
    case 'conditions_particulieres':
      return <Zone id={p} libelle="Conditions particulières" lignes={5} valeur={v} onChange={m} />
    case 'options':
      return (
        <>
          <label className="contrats-editeur__case">
            <input type="checkbox" checked={v.reserve_propriete}
                   onChange={(e) => m({ ...v, reserve_propriete: e.target.checked })} />
            <span>Réserve de propriété jusqu’au paiement complet</span>
          </label>
          {'delai_execution_jours' in v && (
            <Texte id={`${p}-delai`} libelle="Délai d’exécution (jours après la date du contrat)"
                   type="number" step="any" valeur={v.delai_execution_jours}
                   onChange={(x) => m({ ...v, delai_execution_jours: x })} />
          )}
          <Texte id={`${p}-pen`} libelle="Pénalité de retard (%) — vide : aucune" type="number"
                 step="any" valeur={v.penalite_retard_pct}
                 onChange={(x) => m({ ...v, penalite_retard_pct: x })} />
        </>
      )
    case 'livraison':
      return (
        <>
          <Texte id={`${p}-date`} libelle="Date de livraison" type="date" valeur={v.date}
                 onChange={(x) => m({ ...v, date: x })} />
          <Texte id={`${p}-suite`} libelle="Suite prévue" valeur={v.suite}
                 onChange={(x) => m({ ...v, suite: x })} />
          <Texte id={`${p}-suite-d`} libelle="Détail de la suite" valeur={v.suite_detail}
                 onChange={(x) => m({ ...v, suite_detail: x })} />
        </>
      )
    case 'reception':
      return (
        <>
          <Texte id={`${p}-date`} libelle="Date de mise en service" type="date"
                 valeur={v.date_mise_en_service}
                 onChange={(x) => m({ ...v, date_mise_en_service: x })} />
          <Texte id={`${p}-delai`} libelle="Délai pour lever les réserves" valeur={v.delai_levee_reserves}
                 onChange={(x) => m({ ...v, delai_levee_reserves: x })} />
          <label className="contrats-editeur__case">
            <input type="checkbox" checked={v.prononcee}
                   onChange={(e) => m({ ...v, prononcee: e.target.checked })} />
            <span>Réception prononcée</span>
          </label>
        </>
      )
    case 'constats':
      return v.map((k, i) => (
        <div key={i} className="contrats-editeur__constat">
          <input type="checkbox" aria-label={`Constat ${i + 1} coché`} checked={k.cochee}
                 onChange={(e) => m(v.map((r, j) => (j === i ? { ...r, cochee: e.target.checked } : r)))} />
          <Textarea aria-label={`Constat ${i + 1}`} rows={2} value={k.texte} {...attrsLangue(langue)}
                    onChange={(e) => m(v.map((r, j) => (j === i ? { ...r, texte: e.target.value } : r)))} />
        </div>
      ))
    case 'reserves':
      return <Zone id={p} libelle="Réserves (une par ligne)" lignes={4} valeur={v} onChange={m} />
    case 'quitus':
      return <Zone id={p} libelle="Texte du quitus" lignes={6} valeur={v} aide={AIDE_PARAGRAPHES} onChange={m} />
    case 'sav':
      return (
        <>
          <Texte id={`${p}-tel`} libelle="Téléphone" valeur={v.telephone} onChange={(x) => m({ ...v, telephone: x })} />
          <Texte id={`${p}-wa`} libelle="WhatsApp" valeur={v.whatsapp} onChange={(x) => m({ ...v, whatsapp: x })} />
          <Texte id={`${p}-mail`} libelle="E-mail" valeur={v.email} onChange={(x) => m({ ...v, email: x })} />
          <Texte id={`${p}-h`} libelle="Horaires" valeur={v.horaires} onChange={(x) => m({ ...v, horaires: x })} />
        </>
      )
    case 'conseils':
      return v.map((k, i) => {
        const set = (champ) => (x) => m(v.map((r, j) => (j === i ? { ...r, [champ]: x } : r)))
        return (
          <div key={i} className="contrats-editeur__bloc">
            <Texte id={`${p}-${i}-r`} libelle={`Rubrique (conseil ${i + 1})`} valeur={k.rubrique} onChange={set('rubrique')} />
            <Texte id={`${p}-${i}-t`} libelle={`Titre (conseil ${i + 1})`} valeur={k.titre} onChange={set('titre')} />
            <Zone id={`${p}-${i}-x`} libelle={`Texte (conseil ${i + 1})`} lignes={3} valeur={k.texte} onChange={set('texte')} />
          </div>
        )
      })
    case 'entretien':
      return <Zone id={p} libelle="Conseils d’entretien" lignes={6} valeur={v} aide={AIDE_PARAGRAPHES} onChange={m} />
    default:
      return null
  }
}

export default function ActeEditeur({
  open, onOpenChange, acteId, peutModele = false, onSaved, onApercu,
}) {
  const [acte, setActe] = useState(null)
  const [base, setBase] = useState({})
  const [brouillon, setBrouillon] = useState({})
  const [chargement, setChargement] = useState(true)
  const { occupe, erreur, setErreur, soumettre } = useSoumission()
  const [langue, setLangue] = useState('fr')
  const [langueDemandee, setLangueDemandee] = useState(null)

  const charger = (detail) => {
    const sections = (detail.sections_modifiables ?? []).filter((k) => SECTIONS[k])
    const depart = brouillonDe(detail.contenu, sections)
    setActe(detail)
    setBase(depart)
    setBrouillon(depart)
  }

  useEffect(() => {
    if (!open || !acteId) return undefined
    let annule = false
    documentsApi.acte(acteId, langue)
      .then((res) => {
        if (annule) return
        charger(res.data)
        setChargement(false)
      })
      .catch(async (err) => {
        const detail = await detailErreur(err)
        if (annule) return
        // Aucun brouillon d'une autre langue ne reste sous la nouvelle étiquette.
        setActe(null)
        setBase({})
        setBrouillon({})
        setErreur(detail)
        setChargement(false)
      })
    return () => { annule = true }
  }, [open, acteId, langue, setErreur])

  const sections = ORDRE_SECTIONS.filter((k) => (acte?.sections_modifiables ?? []).includes(k))
  const surcharges = acte ? surchargesModifiees(base, brouillon, sections, langue) : {}
  const modifie = Object.keys(surcharges).length > 0
  const personnalisees = acte?.sections_personnalisees ?? []

  const enregistrer = async () => {
    await soumettre(async () => {
      const res = await documentsApi.modifierActe(acte.id, surcharges, langue)
      charger(res.data)
      toast.success('Modifications enregistrées.')
      onSaved?.(res.data)
    })
  }

  const retablir = async (cle) => {
    await soumettre(async () => {
      const res = await documentsApi.modifierActe(acte.id, { [cle]: null }, langue)
      const detail = res.data
      const frais = brouillonDe(detail.contenu, [cle])
      setActe((a) => ({ ...a, ...detail }))
      setBase((b) => ({ ...b, [cle]: frais[cle] }))
      setBrouillon((b) => ({ ...b, [cle]: frais[cle] }))
      toast.success('Texte par défaut rétabli.')
      onSaved?.(detail)
    })
  }

  const basculer = (code) => {
    setLangueDemandee(null)
    setErreur('')
    setChargement(true)
    setLangue(code)
  }
  const changerLangue = (code) => {
    if (code === langue) return
    if (modifie) { setLangueDemandee(code); return }
    basculer(code)
  }

  // Croix, Échap, clic à côté et bouton « Fermer » passent par ICI : des
  // modifications non enregistrées demandent confirmation avant de partir.
  const demanderFermeture = (ouvert) => {
    if (ouvert) { onOpenChange?.(true); return }
    confirmLeaveIfDirty(modifie).then((ok) => { if (ok) onOpenChange?.(false) })
  }

  const enregistrerModele = async () => {
    await soumettre(async () => {
      const res = await documentsApi.enregistrerModeleActe(acte.id)
      toast.success(res.data?.detail || 'Modèle de la société enregistré.')
    })
  }

  return (
    <Dialog open={open} onOpenChange={demanderFermeture}>
      <DialogContent aria-label="Modifier l’acte" className="contrats-editeur">
        <DialogHeader>
          <DialogTitle>Modifier « {acte?.titre ?? 'l’acte'} »</DialogTitle>
          <DialogDescription>
            {acte?.reference}
            {acte ? ' — ' : ''}
            Seuls les textes se modifient ici. Les montants viennent de la vente.
          </DialogDescription>
        </DialogHeader>

        <div className="contrats-editeur__langue" role="group" aria-label="Langue de l’acte">
          <span>Langue :</span>
          {[['fr', 'Français'], ['ar', 'العربية']].map(([code, libelle]) => (
            <Button key={code} type="button" size="sm" lang={code}
                    variant={langue === code ? 'default' : 'outline'}
                    aria-pressed={langue === code}
                    className="contrats-acte__bouton"
                    disabled={occupe}
                    onClick={() => changerLangue(code)}>
              {libelle}
            </Button>
          ))}
        </div>

        {langueDemandee && (
          <div className="contrats-editeur__confirmer" role="alertdialog" aria-label="Changer de langue">
            <p>Des modifications ne sont pas enregistrées : changer de langue les abandonne.</p>
            <Button type="button" size="sm" variant="outline" className="contrats-acte__bouton"
                    onClick={() => setLangueDemandee(null)}>
              Rester ici
            </Button>
            <Button type="button" size="sm" className="contrats-acte__bouton"
                    onClick={() => basculer(langueDemandee)}>
              Changer de langue
            </Button>
          </div>
        )}

        {chargement && (
          <p role="status"><Spinner /> Chargement de l’acte…</p>
        )}

        {acte && !chargement && !acte.peut_modifier && (
          <p className="contrats-acte__erreur" role="alert">
            Cet acte n’est plus modifiable : rouvrez-le pour le modifier.
          </p>
        )}

        {acte && !chargement && sections.map((cle) => (
          <fieldset key={cle} className="contrats-editeur__section" disabled={!acte.peut_modifier || occupe}>
            <legend>{SECTIONS[cle].libelle}</legend>
            <LangueContext.Provider value={langue}>
              <ChampsSection
                cle={cle}
                v={brouillon[cle]}
                m={(valeur) => setBrouillon((b) => ({ ...b, [cle]: valeur }))}
                contenu={acte.contenu}
              />
            </LangueContext.Provider>
            {personnalisees.includes(cle) && (
              <Button type="button" size="sm" variant="ghost" className="contrats-acte__bouton"
                      onClick={() => retablir(cle)}>
                <RotateCcw className="size-4" aria-hidden="true" />
                Rétablir le texte par défaut
              </Button>
            )}
          </fieldset>
        ))}

        <PiedDialogue
          erreur={erreur}
          annuler={() => demanderFermeture(false)}
          libelleAnnuler="Fermer"
          avant={(
            <>
              {acte && onApercu && (
                <Button variant="ghost" className="contrats-acte__bouton" onClick={() => onApercu(langue)}>
                  Aperçu (PDF)
                </Button>
              )}
              {acte && peutModele && (
                <Button variant="outline" className="contrats-acte__bouton" disabled={occupe || modifie}
                        title={modifie ? 'Enregistrez d’abord vos modifications.' : undefined}
                        onClick={enregistrerModele}>
                  Enregistrer comme modèle de la société
                </Button>
              )}
            </>
          )}
        >
          <Button className="contrats-acte__bouton"
                  disabled={occupe || chargement || !modifie || !acte?.peut_modifier}
                  onClick={enregistrer}>
            Enregistrer
          </Button>
        </PiedDialogue>
      </DialogContent>
    </Dialog>
  )
}
