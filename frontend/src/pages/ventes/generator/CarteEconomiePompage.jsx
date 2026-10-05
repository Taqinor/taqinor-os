// AGR213 — carte « Économie déclarée » du générateur agricole, servie par le
// SERVEUR (`POST /ventes/economie-pompage/preview/`, AGR206) : le JS ne calcule
// rien. Le corps est construit par `economiePompagePreviewPur.js` et l'appel
// est temporisé (~500 ms) et annulable, comme `etudeHorairePreview.js`.
//
// La carte rend SANS recalcul : dépense actuelle et son détail déclaré, charges
// et remplacements (ou leur motif), économie nette, retour SANS aide, coût du
// m³, sensibilité au prix et seuil de rentabilité — chaque chiffre étiqueté
// « estimation — calculée sur les chiffres déclarés » ; les omissions avec leur
// motif ; les avertissements de cohérence regroupés par champ ; le bandeau de
// couverture non vérifiable et le motif de non-publication. La clé
// `vue_interne` n'est lue QUE par le volet interne (AGR214).
import { useEffect, useState } from 'react'
import { useDebouncedValue } from '../../../lib/debounce'
import ventesApi from '../../../api/ventesApi'
import { formatNumber } from '../../../lib/format'
import {
  construireCorpsEconomiePompage, vueCarteEconomie,
} from '../../../features/ventes/economiePompagePreviewPur'
import { saisiesEconomiePompage } from '../../../features/ventes/quote/etudeMarcheBloc'
import CarteEconomiePompageInterne from './CarteEconomiePompageInterne'

const mad = (v) => `${formatNumber(v)} MAD`

/** Appel temporisé et annulable ; résultat effacé au début de chaque appel. */
function useEconomiePompageCarte(corps) {
  const corpsKey = corps ? JSON.stringify(corps) : null
  const debouncedKey = useDebouncedValue(corpsKey, 500)
  const [donnees, setDonnees] = useState(null)
  const [erreur, setErreur] = useState(null)
  useEffect(() => {
    if (!debouncedKey || typeof ventesApi.economiePompagePreview !== 'function') {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reflète l'absence de corps
      setDonnees(null)
      setErreur(null)
      return undefined
    }
    let cancelled = false
    const controller = new AbortController()
    setDonnees(null)
    setErreur(null)
    ventesApi.economiePompagePreview(JSON.parse(debouncedKey), { signal: controller.signal })
      .then((res) => { if (!cancelled) setDonnees(res.data) })
      .catch((err) => {
        if (cancelled || err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
        setErreur("Aperçu de l'économie indisponible pour le moment.")
      })
    return () => { cancelled = true; controller.abort() }
  }, [debouncedKey])
  return { donnees, erreur }
}

function Chiffre({ libelle, valeur, testid, unite = mad }) {
  return (
    <div className="grid gap-0.5" data-testid={testid}>
      <span className="text-xs text-muted-foreground">{libelle}</span>
      <span className="text-sm font-semibold">{valeur === null || valeur === undefined
        ? 'non calculé' : unite(valeur)}</span>
    </div>
  )
}

/** La vue CLIENT de la carte, sur une réponse du contrat (aucun calcul). */
export function CarteEconomiePompageVue({ reponse }) {
  const v = vueCarteEconomie(reponse)
  if (!v) return null
  return (
    <div className="grid gap-3" data-testid="carte-economie-vue">
      <p className="text-xs italic text-muted-foreground">{v.etiquette}</p>
      {v.couvertureNonVerifiee && (
        <p className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs"
           data-testid="bandeau-couverture">{v.couvertureNonVerifiee}</p>
      )}
      {v.motifsNonPubliable.length > 0 && (
        <div className="rounded-md border p-2 text-xs" data-testid="motifs-non-publiable">
          Non publiable au client : {v.motifsNonPubliable.join(' ; ')}
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Chiffre libelle="Dépense actuelle (an)" valeur={v.depenseAnnuelle} testid="depense-actuelle" />
        <Chiffre libelle="Économie nette (année 1)" valeur={v.economieNette} testid="economie-nette" />
        <Chiffre libelle="Retour sans aide" valeur={v.retourAns} testid="retour-ans"
                 unite={(x) => `${formatNumber(x)} ans`} />
        <Chiffre libelle="Coût du m³ (actuel / solaire)"
                 valeur={v.madParM3 && v.madParM3.actuel !== null ? v.madParM3 : null}
                 testid="cout-m3"
                 unite={(m) => `${formatNumber(m.actuel)} / ${m.solaire === null
                   ? 'non calculé' : formatNumber(m.solaire)} MAD`} />
      </div>
      {v.detailDeclare && (
        <p className="text-xs" data-testid="detail-declare">{v.detailDeclare}</p>
      )}
      {v.charges && (
        <ul className="text-xs" data-testid="charges-solaires">
          {v.charges.lignes.map((l) => (
            <li key={l.libelle}>{l.libelle} : {mad(l.montant)}{l.source ? ` (${l.source})` : ''}</li>
          ))}
        </ul>
      )}
      {v.remplacements.length > 0 && (
        <ul className="text-xs" data-testid="remplacements">
          {v.remplacements.map((r) => (
            <li key={r.composant}>{r.composant} : {r.montant === null
              ? (r.motif || 'omis') : `${mad(r.montant)} en année ${r.annee}`}</li>
          ))}
        </ul>
      )}
      {v.sensibilite.length > 0 && (
        <ul className="text-xs" data-testid="sensibilite">
          {v.sensibilite.map((s) => (
            <li key={s.libelle}>{s.libelle} : économie nette {mad(s.economie)}, retour {s.retourAns} ans</li>
          ))}
        </ul>
      )}
      {v.seuil && v.seuil.valeur !== null && (
        <p className="text-xs" data-testid="seuil-rentabilite">
          Seuil de rentabilité : {formatNumber(v.seuil.valeur)} {v.seuil.unite}
        </p>
      )}
      {Object.entries(v.coherenceParChamp).map(([champ, bloc]) => (
        <div key={champ} className="text-xs text-amber-700" data-champ={champ}
             data-testid="coherence-champ">
          <span className="font-semibold">{bloc.libelle}</span>
          {bloc.messages.map((m) => <p key={m}>{m}</p>)}
        </div>
      ))}
      {v.omissions.length > 0 && (
        <ul className="text-xs text-muted-foreground" data-testid="omissions">
          {v.omissions.map((o) => <li key={`${o.cle}-${o.motif}`}>{o.motif}</li>)}
        </ul>
      )}
    </div>
  )
}

/** La carte montée dans PanneauAgricole : corps → aperçu serveur → vue. */
export default function CarteEconomiePompage({ eco, moisCalendrier, sortieEtude, lignes, majEco }) {
  const saisies = saisiesEconomiePompage(eco, {
    moisCalendrier, aujourdhui: new Date().toISOString().slice(0, 10) })
  const corps = construireCorpsEconomiePompage({ saisies, sortieEtude, lignes })
  const { donnees, erreur } = useEconomiePompageCarte(corps)
  return (
    <div className="mt-4 grid gap-3 rounded-lg border p-3" data-testid="carte-economie-pompage">
      <span className="font-display text-sm font-semibold">Économie déclarée</span>
      {!corps && (
        <p className="text-xs text-muted-foreground">
          Déclarez l'énergie actuelle et la dépense pour voir l'économie.
        </p>
      )}
      {erreur && <p className="text-xs text-destructive" role="alert">{erreur}</p>}
      <CarteEconomiePompageVue reponse={donnees} />
      {/* AGR214 — volet INTERNE (jamais imprimé), replié par défaut. */}
      <CarteEconomiePompageInterne reponse={donnees} eco={eco} majEco={majEco} />
    </div>
  )
}
