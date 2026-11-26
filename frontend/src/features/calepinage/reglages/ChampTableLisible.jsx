import { useState } from 'react'
import { Button } from '../../../ui'
import { SPECS_TABLES, lireTable, ecrireTable, identifiantProduit } from './tablesReglages'

/* ============================================================================
   T4-X3-019 — LES TABLES DES RÉGLAGES, EN CHAMPS LISIBLES (plus de JSON brut).
   ----------------------------------------------------------------------------
   Chaque clé `table` déclare sa forme côté serveur
   (`services/parametres_cles.py::FORMES_TABLES`) ; la ligne « Valeur » reste
   un TEXTE JSON dans l'état de l'écran (validation, envoi, retour d'erreur
   inchangés) : ce composant le LIT en champs étiquetés et le RÉÉCRIT, dans la
   MÊME forme que celle attendue par l'API, à chaque frappe.
     * `lid_par_techno`          {techno: {pct, source?, reference?}}
     * `thermique_par_pose`      {pose: {uc_w_m2k, uv_w_m3sk?, source?, reference?}}
     * `indisponibilite_fenetres` [{debut, fin, motif?}]
     * `regle_bom_structure`     {rails_par_module, pinces_par_module,
                                  pinces_supplement, crochets_par_module,
                                  crochets_minimum, source?}
     * `consigne_dc_plan_cablage` {texte}
     * `correspondances_nomenclature` {repère: identifiant produit, texte OU entier}
                                  — une ligne par correspondance (mode `paires`)
   Une clé dont la forme n'est pas connue avec certitude, ou une
   valeur tapée qui ne se lit pas dans la forme attendue, RESTE sur l'éditeur
   JSON : on ne devine jamais des champs.
   Les nombres : `type="number"` `step="any"`, sans borne HTML — rien ne saute,
   rien n'est refusé à la frappe (le serveur normalise et nomme).
   ========================================================================== */

const CLASSE = 'mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground'

function CaseNombre({ id, label, valeur, disabled, onChange, testid }) {
  // Le brouillon tapé reste tel quel (« 1. », « 0,5 ») tant qu'il dit la même valeur que la table.
  const [brouillon, setBrouillon] = useState('')
  const t = brouillon.trim().replace(',', '.')
  const dit = t === '' ? undefined : (Number.isFinite(Number(t)) ? Number(t) : NaN)
  const affiche = dit === valeur ? brouillon : (valeur === undefined ? '' : String(valeur))
  return (
    <label className="block" htmlFor={id}>
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        id={id}
        type="number"
        step="any"
        value={affiche}
        disabled={disabled}
        data-testid={testid}
        className={CLASSE}
        onChange={(e) => {
          setBrouillon(e.target.value)
          const t = e.target.value.trim().replace(',', '.')
          onChange(t === '' ? undefined : (Number.isFinite(Number(t)) ? Number(t) : undefined))
        }}
      />
    </label>
  )
}

function CaseTexte({ id, label, valeur, disabled, onChange, testid }) {
  return (
    <label className="block" htmlFor={id}>
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        id={id}
        type="text"
        value={valeur ?? ''}
        disabled={disabled}
        data-testid={testid}
        className={CLASSE}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  )
}

function Cases({ idBase, testBase, champs, ligne, disabled, onChamp }) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      {champs.map((c) => {
        const Case = c.nombre ? CaseNombre : CaseTexte
        return (
          <Case
            key={c.k}
            id={`${idBase}-${c.k}`}
            testid={`${testBase}-${c.k}`}
            label={c.label}
            valeur={ligne[c.k]}
            disabled={disabled}
            onChange={(v) => onChamp(c.k, v)}
          />
        )
      })}
    </div>
  )
}

/** Rend `null` quand la forme n'est pas connue / la valeur illisible : l'appelant garde l'éditeur JSON. */
export default function ChampTableLisible({ cle, texte, disabled, onTexte }) {
  const spec = SPECS_TABLES[cle]
  const valeur = lireTable(cle, texte)
  if (!spec || valeur === null) return null
  const id = `calx69-${cle}`

  if (spec.mode === 'objet') {
    return (
      <div id={id} tabIndex={-1} className="mt-0.5" data-testid={`calx69-table-${cle}`}>
        <Cases idBase={id} testBase={id} champs={spec.champs} ligne={valeur} disabled={disabled}
          onChamp={(k, v) => onTexte(ecrireTable(spec, { ...valeur, [k]: v }))} />
      </div>
    )
  }

  if (spec.mode === 'liste') {
    const maj = (i, k, v) => onTexte(ecrireTable(spec, valeur.map((l, j) => (j === i ? { ...l, [k]: v } : l))))
    return (
      <div id={id} tabIndex={-1} className="mt-0.5 space-y-2" data-testid={`calx69-table-${cle}`}>
        {valeur.map((l, i) => (
          <div key={i} className="border border-border/60 p-2" data-testid={`calx69-table-${cle}-${i}`}>
            <p className="text-xs font-semibold text-foreground">{`${spec.nom} ${i + 1}`}</p>
            <Cases idBase={`${id}-${i}`} testBase={`${id}-${i}`} champs={spec.champs} ligne={l} disabled={disabled}
              onChamp={(k, v) => maj(i, k, v)} />
            {!disabled && (
              <Button type="button" size="sm" variant="outline" className="mt-2"
                onClick={() => onTexte(ecrireTable(spec, valeur.filter((_, j) => j !== i)))}>
                Retirer cette ligne
              </Button>
            )}
          </div>
        ))}
        {!disabled && (
          <Button type="button" size="sm" variant="outline" data-testid={`calx69-table-${cle}-ajouter`}
            onClick={() => onTexte(JSON.stringify([...valeur, { debut: '', fin: '' }].map((l) => ({ ...l }))))}>
            {spec.ajout}
          </Button>
        )}
      </div>
    )
  }

  if (spec.mode === 'paires') {
    const lignes = Object.entries(valeur)
    const ecrire = (nouvelles) => onTexte(ecrireTable(spec, Object.fromEntries(nouvelles)))
    return (
      <div id={id} tabIndex={-1} className="mt-0.5 space-y-2" data-testid={`calx69-table-${cle}`}>
        {lignes.map(([k, v], i) => (
          <div key={i} className="border border-border/60 p-2" data-testid={`calx69-table-${cle}-${i}`}>
            <p className="text-xs font-semibold text-foreground">{`${spec.nom} ${i + 1}`}</p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <CaseTexte id={`${id}-${i}-cle`} testid={`${id}-${i}-cle`} label={spec.cle.label} valeur={k} disabled={disabled}
                onChange={(nouvelle) => {
                  // Un repère déjà pris par une autre ligne n'est pas écrit (il effacerait cette ligne).
                  if (nouvelle !== k && nouvelle in valeur) return
                  ecrire(lignes.map(([kk, vv], j) => (j === i ? [nouvelle, vv] : [kk, vv])))
                }} />
              <CaseTexte id={`${id}-${i}-valeur`} testid={`${id}-${i}-valeur`} label={spec.valeur.label} valeur={String(v)}
                disabled={disabled}
                onChange={(t) => ecrire(lignes.map(([kk, vv], j) => (j === i ? [kk, identifiantProduit(t)] : [kk, vv])))} />
            </div>
            {!disabled && (
              <Button type="button" size="sm" variant="outline" className="mt-2"
                onClick={() => ecrire(lignes.filter((_, j) => j !== i))}>
                Retirer cette ligne
              </Button>
            )}
          </div>
        ))}
        {!disabled && (
          <Button type="button" size="sm" variant="outline" data-testid={`calx69-table-${cle}-ajouter`}
            disabled={'' in valeur} onClick={() => ecrire([...lignes, ['', '']])}>
            {spec.ajout}
          </Button>
        )}
      </div>
    )
  }

  // dict : une ligne par famille connue, plus toute clé déjà stockée.
  const cles = [...Object.keys(spec.familles), ...Object.keys(valeur).filter((k) => !(k in spec.familles))]
  return (
    <div id={id} tabIndex={-1} className="mt-0.5 space-y-2" data-testid={`calx69-table-${cle}`}>
      {cles.map((k) => {
        const l = valeur[k] || {}
        return (
          <div key={k} className="border border-border/60 p-2" data-testid={`calx69-table-${cle}-${k}`}>
            <p className="text-xs font-semibold text-foreground">{spec.familles[k] || k}</p>
            <Cases idBase={`${id}-${k}`} testBase={`${id}-${k}`} champs={spec.champs} ligne={l} disabled={disabled}
              onChamp={(champ, v) => onTexte(ecrireTable(spec, { ...valeur, [k]: { ...l, [champ]: v } }))} />
          </div>
        )
      })}
    </div>
  )
}
