// COP-F4 — texte « Copier pour Claude Code » de la carte diagnostic : un bloc
// prêt à coller dans une session de code. Routes, statuts, identifiants de
// requête, erreurs — JAMAIS de donnée client (ni corps de requête, ni question
// posée, ni nom). PUR : testé avec l'échantillon `assistant_diagnostic.json`.

const lignesRequetes = (requetes) => (Array.isArray(requetes) ? requetes : []).map((r) => {
  const id = r.request_id ? ` request_id=${r.request_id}` : ''
  const duree = r.duree_ms != null ? ` ${r.duree_ms} ms` : ''
  return `- ${r.methode} ${r.route} → ${r.statut}${duree}${id}`
})

const lignesErreurs = (erreurs) => (Array.isArray(erreurs) ? erreurs : [])
  .map((e) => `- [${e.genre}] ${e.message}`)

function blocProbleme(p) {
  const id = p.exemple_request_id ? ` request_id=${p.exemple_request_id}` : ''
  const classe = p.classe ? ` classe=${p.classe}` : ''
  return `- ${p.methode ?? ''} ${p.route ?? ''} → ${p.statut_reponse ?? ''} `
    + `(${p.occurrences} fois, ${p.personnes} pers.)${classe}${id} écran=${p.ecran ?? ''}`
}

function blocSignalement(s) {
  const d = s.diagnostic
  const tete = `- ${s.intention} sur ${s.ecran ?? '?'} (événement ${s.evenement_id})`
  if (!d) return [tete]
  const version = d.version ? ` version=${d.version}` : ''
  return [
    `${tete}${version} navigateur=${d.navigateur ?? '?'} en_ligne=${d.en_ligne}`,
    ...lignesRequetes(d.requetes).map((l) => `  ${l}`),
    ...lignesErreurs(d.erreurs).map((l) => `  ${l}`),
  ]
}

/** `donnees` = corps de la carte diagnostic ; `instantane` = tampon de CE navigateur. */
export function texteDiagnostic(donnees, instantane = null) {
  const out = [`Diagnostic TAQINOR OS — ${donnees?.jours ?? 1} dernier(s) jour(s), généré le ${donnees?.genere_le ?? ''}`]
  const problemes = donnees?.problemes ?? []
  out.push('', `Problèmes vécus (${problemes.length}) :`)
  out.push(...(problemes.length ? problemes.map(blocProbleme) : ['- aucun']))
  const a = donnees?.assistant
  if (a) {
    out.push('', `Assistant : ${a.questions} questions, ${a.erreurs} erreurs, repli ${Math.round((a.part_repli || 0) * 100)} %`)
    for (const s of a.signalements ?? []) out.push(...blocSignalement(s))
  }
  if (instantane) {
    out.push('', `Navigateur (cette session) : écran=${instantane.ecran ?? ''} en_ligne=${instantane.en_ligne}`)
    out.push(...lignesRequetes(instantane.requetes), ...lignesErreurs(instantane.erreurs))
  }
  return out.join('\n')
}
