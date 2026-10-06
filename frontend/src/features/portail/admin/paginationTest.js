// ADOC32 — aides de TEST partagées des écrans d'administration portail :
// l'API sert l'enveloppe DRF réelle {count, next, results} (jamais un tableau
// nu) ; `pagine` simule une liste de `total` lignes servie par pages de 50.
export const enveloppe = (results) => ({ count: results.length, next: null, previous: null, results })

export const pagine = (total, ligne, taille = 50) => (params) => {
  const page = params?.page ?? 1
  const debut = (page - 1) * taille
  const fin = Math.min(total, debut + taille)
  return Promise.resolve({
    data: {
      count: total,
      next: fin < total ? `/api/django/portail/x/?page=${page + 1}` : null,
      previous: page > 1 ? `/api/django/portail/x/?page=${page - 1}` : null,
      results: Array.from({ length: Math.max(0, fin - debut) }, (_, i) => ligne(debut + i + 1)),
    },
  })
}
