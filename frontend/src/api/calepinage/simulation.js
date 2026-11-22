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
    // ACAL446 — `colonnes` OPTIONNEL (CSV de noms, CALX313) : absent ⇒ le
    // serveur sert ses colonnes par défaut, l'appel d'export reste inchangé.
    // ACAL767 — `options.suppressErrorToast` : une lecture que personne n'a
    // demandée garde son refus local (la carte), sans toast global.
    // ACAL755 — `options.pas` (`jour`) : une ligne par jour, envoyé seulement
    // quand il est posé.
    exportCsv: (id, quoi, colonnes, options) =>
      api.get(`${pivot(id)}export-csv/`, {
        responseType: 'blob',
        params: {
          quoi,
          ...(colonnes ? { colonnes } : {}),
          ...(options?.pas ? { pas: options.pas } : {}),
        },
        ...(options?.suppressErrorToast ? { suppressErrorToast: true } : {}),
        ...(options?.timeout ? { timeout: options.timeout } : {}),
      }),

    // CALX62 — le DÉPÔT d'une série météo horaire de la société, à la place
    // de PVGIS (`views/meteo_fichier.py`, contrat
    // `contract_samples/calepinage_meteo_fichier.json`). `corps` est un
    // FormData (`fichier` CSV + `fournisseur` SAISI) : on laisse axios poser
    // sa frontière multipart. La réponse 201 rend la PROVENANCE (`meteo`) et
    // le RÉSUMÉ de la série — jamais ses 8 760 points. Un refus 400 NOMME la
    // colonne fautive du fichier et, quand elle est connue, sa `ligne`.
    deposerMeteoFichier: (id, corps) =>
      api.post(`${pivot(id)}meteo-fichier/`, corps),

    // ACAL147 — le fichier météo RETENU par la simulation (`views/meteo_fichier.py`,
    // GET, ACAL146) : `{piece_jointe, nom, fournisseur, sha256, depose_le,
    // depose_par}`, ou `null` quand la simulation lit PVGIS. Lecture pure.
    meteoFichier: (id) => api.get(`${pivot(id)}meteo-fichier/`),

    // ACAL148 — « Retirer le fichier météo » (`views/meteo_fichier.py`, DELETE) :
    // la pièce part à la corbeille, le retour à PVGIS est tracé au journal, la
    // simulation stockée devient périmée. 204 sans corps ; 404 nommé
    // `{detail}` s'il n'y a aucun fichier retenu. Hors verrou.
    retirerFichierMeteo: (id) => api.delete(`${pivot(id)}meteo-fichier/`),

    // CALX5 — LANCER la simulation (`views/simulation.py`, contrat
    // `contract_samples/calepinage_simulation.json`). Deux réponses, jamais
    // une troisième : 202 `{job_id, kind, nature}` — le travail est parti en
    // tâche de fond, à suivre par `moteur.resultat(jobId)` (UN seul kind,
    // D-CALX 12) — ou 200 `{deja_calcule: true, calcule_le}` quand les
    // entrées n'ont pas bougé. `{ forcer: true }` relance quand même. Un
    // refus 400 NOMME le réglage ou le champ à corriger.
    // ACAL398 — `silencieux` : l'appelant affiche lui-même le refus (relance
    // automatique) ; le pont axios ne lève alors AUCUN toast.
    simuler: (id, { forcer = false, silencieux = false } = {}) =>
      api.post(`${pivot(id)}simuler/`, { forcer }, silencieux ? { suppressErrorToast: true } : undefined),

    // ACAL871 — le registre des explications (contrat `calepinage_explications.json`) :
    // le même pour tous les calepinages, sans `pk`.
    explications: () => api.get('/calepinage/calepinages/explications/'),

    // ACAL392 — l'état du parcours guidé (contrat `calepinage_parcours_guide.json`).
    parcours: (id) => api.get(`${pivot(id)}parcours/`),
    // ACAL860 — « prêt à envoyer ? » (contrat `calepinage_pret_a_envoyer.json`).
    pretAEnvoyer: (id) => api.get(`${pivot(id)}pret-a-envoyer/`),

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

    // ACAL887 — la PRODUCTION MESURÉE (contrat `calepinage_production_mesuree.json`,
    // ACAL886), servie par `views/production_mesuree.py`. `GET` rend les mesures
    // rangées et, par mois, `p50_kwh` / `kwh_mesure` / `ecart_pct` (null sans
    // mesure ou sans simulation fraîche, avec le `motif`) ; `PUT` range
    // `{annee, mesures: [{mois, kwh_mesure}]}` (12 lignes au plus) et rend la
    // même forme. Un refus 400 NOMME le champ (`mesures[i].mois`…). L'écran est
    // ACAL888 ; l'écart est publié, jamais jugé.
    productionMesuree: (id) => api.get(`${pivot(id)}production-mesuree/`),
    enregistrerProductionMesuree: (id, corps) =>
      api.put(`${pivot(id)}production-mesuree/`, corps),

    // CALX235 — le schéma unifilaire en DXF, pour qu'un bureau d'études le
    // reprenne (`views/schema.py`, `url_path='schema-unifilaire.dxf'` — le
    // point fait partie du chemin, comme `export.csv`). Le fichier est
    // transposé du MÊME dessin que le SVG : les deux ne peuvent pas
    // diverger. Réponse BLOB ; une conception incomplète ou bloquée ne
    // produit AUCUN fichier et le serveur refuse en 400 en NOMMANT le champ
    // en cause — l'écran affiche CE motif-là, il n'en invente aucun.
    sldDxf: (id, options) =>
      api.get(`${pivot(id)}schema-unifilaire.dxf/`, { responseType: 'blob',
        ...(options?.suppressErrorToast ? { suppressErrorToast: true } : {}),
        ...(options?.timeout ? { timeout: options.timeout } : {}) }),
}
// ACAL387 — contrat calepinage_profil_depart.json (M0)
// ACAL388 — contrat calepinage_balayage.json (M0)
