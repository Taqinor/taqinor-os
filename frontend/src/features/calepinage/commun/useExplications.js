import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber } from '../../../lib/format'

/* ACAL872 — le registre des explications (ACAL871, contrat
   `calepinage_explications.json`), lu UNE fois par page : tous les « ? »
   d'un écran partagent la même promesse. Un échec n'est pas gardé (relu au
   prochain montage) ; un « ? » sans registre ne s'ouvre simplement pas. */
let promesse = null
const charger = () => {
  promesse ??= Promise.resolve()
    .then(() => calepinageApi.calepinages.explications())
    .then((r) => r.data)
    .catch((e) => { promesse = null; throw e })
  return promesse
}

export default function useExplications() {
  const { data } = useResource(charger, 'explications')
  return data?.entrees ?? null
}

/** Valeur SERVIE au chemin `a.b[code].c` (`[x]` = l'élément dont `code` vaut x). */
export function lireChemin(source, chemin) {
  return chemin.split('.').reduce((noeud, morceau) => {
    if (noeud === null || noeud === undefined) return undefined
    const [, cle, code] = morceau.match(/^([^[]+)(?:\[([^\]]+)\])?$/) || []
    const valeur = noeud[cle]
    return code === undefined ? valeur : (valeur || []).find?.((e) => e?.code === code)
  }, source)
}

export const NON_PUBLIEE = 'valeur non publiée'

/** La phrase de l'entrée, trous remplis par les valeurs servies (absente ⇒ « valeur non publiée », jamais 0). */
export function remplirPhrase(entree, source) {
  return entree.phrase.replace(/\{([^{}]+)\}/g, (_, nom) => {
    const chemin = entree.valeurs?.[nom]
    const v = chemin ? lireChemin(source, chemin) : undefined
    if (v === null || v === undefined || v === '') return NON_PUBLIEE
    return typeof v === 'number' ? formatNumber(v) : String(v)
  })
}

/* La garde de rendu (ACAL872 (c)) : tout `dd`, `.stat-value-solidify` ou `.fig`
   qui contient un chiffre doit avoir, dans son parent (ou sa carte `Stat`), un
   `[data-grandeur]` ou une dérogation `[data-sans-grandeur="<raison>"]`.
   Rend les TEXTES des chiffres orphelins (liste vide = écran conforme). */
export function chiffresSansGrandeur(racine) {
  const explique = (el) => el?.querySelector('[data-grandeur]')
    || el?.querySelector('[data-sans-grandeur]:not([data-sans-grandeur=""])')
    || el?.matches?.('[data-sans-grandeur]:not([data-sans-grandeur=""])')
  return [...racine.querySelectorAll('dd, .stat-value-solidify, .fig')]
    .filter((el) => /\d/.test(el.textContent))
    .filter((el) => !explique(el) && !explique(el.parentElement))
    .map((el) => el.textContent.trim())
}
