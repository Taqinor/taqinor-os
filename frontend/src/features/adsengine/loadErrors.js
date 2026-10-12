// ENF15 — état d'erreur de chargement VISIBLE (jamais un échec avalé en liste vide).
// Un écran garde `const [loadErrors, setLoadErrors] = useState([])`, ajoute dans
// chaque `.catch` : `setLoadErrors(markLoadError('les campagnes'))`, et affiche
// <LoadErrorNotice errors={loadErrors} />.
export const markLoadError = (label) => (prev) => (prev.includes(label) ? prev : [...prev, label])
