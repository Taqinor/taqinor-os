/* SPL294 — fragment simulation et electrique de calepinageApi.js (move only). */
import api from '../axios'
import { pivot } from './_base'

export const simulation = {
    // CALX6 — le TÉLÉCHARGEMENT d'une série de la simulation. La porte
    // existe depuis CAL144 (`views/export_csv.py`, `url_path='export-csv'`)
    // et n'avait AUCUN consommateur : `quoi` vaut `horaire`, `mensuel` ou
    // `ombrage` (`services/export_csv.py::EXPORTS`). La réponse est un
    // FICHIER (blob) ; quand la donnée manque, le serveur refuse en 400 et
    // NOMME le champ absent (`points`, `mensuel`, `shading12x24`) — l'écran
    // affiche ce motif-là sous le bouton, il n'en invente aucun.
    exportCsv: (id, quoi) =>
      api.get(`${pivot(id)}export-csv/`, { responseType: 'blob', params: { quoi } }),

    // CALX62 — le DÉPÔT d'une série météo horaire de la société, à la place
    // de PVGIS (`views/meteo_fichier.py`, contrat
    // `contract_samples/calepinage_meteo_fichier.json`). `corps` est un
    // FormData (`fichier` CSV + `fournisseur` SAISI) : on laisse axios poser
    // sa frontière multipart. La réponse 201 rend la PROVENANCE (`meteo`) et
    // le RÉSUMÉ de la série — jamais ses 8 760 points. Un refus 400 NOMME la
    // colonne fautive du fichier et, quand elle est connue, sa `ligne`.
    deposerMeteoFichier: (id, corps) =>
      api.post(`${pivot(id)}meteo-fichier/`, corps),

    // CALX5 — LANCER la simulation (`views/simulation.py`, contrat
    // `contract_samples/calepinage_simulation.json`). Deux réponses, jamais
    // une troisième : 202 `{job_id, kind, nature}` — le travail est parti en
    // tâche de fond, à suivre par `moteur.resultat(jobId)` (UN seul kind,
    // D-CALX 12) — ou 200 `{deja_calcule: true, calcule_le}` quand les
    // entrées n'ont pas bougé. `{ forcer: true }` relance quand même. Un
    // refus 400 NOMME le réglage ou le champ à corriger.
    simuler: (id, { forcer = false } = {}) =>
      api.post(`${pivot(id)}simuler/`, { forcer }),

    // CALX229 — le métré et la chute, TRONÇON PAR TRONÇON (contrat
    // `contract_samples/calepinage_troncons.json`, CALX203). ÉTAT DU SERVEUR
    // À L'ÉCRITURE DE CETTE LIGNE : la route n'existe pas encore — son
    // producteur est `services/troncons.py` (CALX224-226) et sa vue arrive
    // avec la suite de la vague ÉLECTRIQUE PRO ; l'échantillon est déclaré
    // `POSES_AVANT_LEUR_ROUTE` dans `tests/test_cal223_contrats.py`
    // (mécanisme PACT10 déjà posé). `CheminementCables.jsx` traite un 404 de
    // CETTE porte comme un état « pas encore calculable », jamais une panne.
    troncons: (id) => api.get(`${pivot(id)}troncons/`),

    // CALX244 — le POINT DE RACCORDEMENT réseau (contrat
    // `contract_samples/calepinage_raccordement.json`, CALX205), servi par
    // `views/raccordement.py`. UNE SEULE URL, deux méthodes : `GET` lit,
    // `POST` enregistre la saisie ET REND le raccordement recalculé —
    // l'écran n'enchaîne aucun second appel. Les deux réponses portent les
    // trois blocs `{saisie, calcul, verdicts}` et les CINQ verdicts, même
    // quand rien n'est saisi. Un refus 400 NOMME le champ fautif
    // (`source_limite`, `phases`… — les noms du bloc `saisie`, comme
    // `refus_limite_sans_source` du contrat) : une limite ou un cos φ sans
    // leur provenance n'entre jamais en base.
    raccordement: (id) => api.get(`${pivot(id)}raccordement/`),
    enregistrerRaccordement: (id, corps) =>
      api.post(`${pivot(id)}raccordement/`, corps),

    // CALX235 — le schéma unifilaire en DXF, pour qu'un bureau d'études le
    // reprenne (`views/schema.py`, `url_path='schema-unifilaire.dxf'` — le
    // point fait partie du chemin, comme `export.csv`). Le fichier est
    // transposé du MÊME dessin que le SVG : les deux ne peuvent pas
    // diverger. Réponse BLOB ; une conception incomplète ou bloquée ne
    // produit AUCUN fichier et le serveur refuse en 400 en NOMMANT le champ
    // en cause — l'écran affiche CE motif-là, il n'en invente aucun.
    sldDxf: (id) =>
      api.get(`${pivot(id)}schema-unifilaire.dxf/`, { responseType: 'blob' }),
}
