# Essai de l'outil de toiture du site public — aperçu de pré-fusion vs site en ligne (23/11/2026)

## Verdict
**Non démontré : l'aperçu n'est PAS essayable.** Il répond « 301 → https://taqinor.ma/ » à toute requête (voir ci-dessous) ; aucune comparaison aperçu/en ligne n'a donc été possible. Ce n'est pas une preuve de casse, c'est une absence de preuve.

## Aperçu : ce qui est observé (curl, pas de navigateur nécessaire)
- `GET https://claude-calpinage-module-l5-aadbde-taqinor-web.taqinor.workers.dev/` → HTTP 301, `Location: https://taqinor.ma/`, `X-Robots-Tag: noindex`.
- `GET .../devis/mon-toit/` → HTTP 301, `Location: https://taqinor.ma/devis/mon-toit/`. Même chose avec un User-Agent de navigateur.
- Témoin : `taqinor-web.taqinor.workers.dev/` → 301 identique ; un sous-domaine inexistant → 404. L'hôte de l'aperçu existe donc bien.
- Cause (lue dans `apps/web/worker/redirect-entry.mjs`, étape 1) : le wrapper de production redirige TOUT hôte `*.workers.dev` vers taqinor.ma (chemin et query conservés). Un navigateur suivant la redirection atterrit sur le site en ligne : lancer le script sur l'aperçu aurait comparé le site en ligne à lui-même (faux « identique »). Je ne l'ai donc pas fait.
- Conséquence : l'aperçu de branche d'`apps/web` ne peut pas être vu tel quel tant que ce wrapper redirige les aperçus (piste : exempter les hôtes d'aperçu de branche ; je n'ai rien modifié).

## Outil de toiture (site en ligne)
- Adresse : `https://taqinor.ma/devis/mon-toit/` (aussi `/en/devis/mon-toit/`, `/ar/devis/mon-toit/` au sitemap). Lien trouvé dans le DOM de l'accueil.
- Assistant en 2 étapes : « Votre toit » (type Résidentiel/Industriel/Commercial/Agricole → adresse + carte → Continuer) puis « Votre étude gratuite » (facture MAD/mois exacte ou tranche, bouton « Voir mon étude gratuite »). Carte : MapLibre sur tuiles satellite Mapbox. Boutons de tracé présents dans le DOM : « Pointer mon toit », « Dessiner mon toit », « Terminer le tracé », « Annuler le dernier point », « Ajouter un pan », « Retirer ce pan », « Effacer », « Oui, c'est mon toit ».
- Pas de « Rétablir » trouvé dans le DOM de la page en ligne ; pas de pose de panneaux ni de kWc visibles avant l'étape coordonnées (non vérifié au-delà).

## Parcours réalisé (en ligne seulement, 1440 × 900)
| Geste | En ligne | Aperçu |
|---|---|---|
| Choisir « Résidentiel » | passe à l'écran adresse/carte (capture `live-1440-01-type.png`) | non essayable |
| Adresse « Casablanca » + Localiser | carte MapLibre 894 × 558 px chargée, tuiles satellite demandées | non essayable |
| « Dessiner mon toit » | mode sélectionné (`live-1440-06-terminer.png`) | non essayable |
| 4 clics de tracé, Terminer, coin, Annuler, Rétablir, Ajouter un pan, Effacer | NON ABOUTI : la carte est sous la ligne de flottaison (y ≈ 830–1390 pour un écran de 900) et mon script a cliqué hors écran ; les boutons ont expiré (30 s) | non essayable |
Captures : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/apercu-public/live-1440-*.png` (scripts `journey.mjs`, `explore.mjs` dans le même dossier).

## Erreurs (en ligne, 1440)
- Console : `pageerror` et `console.error` = aucun relevé.
- Requêtes : aucune 4xx/5xx ; seulement des `net::ERR_ABORTED` sur des tuiles `api.mapbox.com/v4/mapbox.satellite/...` (annulations de zoom, attendues). Le jeton public Mapbox apparaît dans les URL (normal pour une clé de carte publique).
- Aperçu : sans objet (redirection).

## Différences aperçu / en ligne
Aucune observable. Aucune capture côté aperçu.

## Non essayé
- Tout l'aperçu (voir ci-dessus) ; la 390 × 844 ; le tracé du toit, la pose des panneaux, la facture/cible, déplacer un coin, Annuler/Rétablir, seconde zone, Effacer (script à relancer avec défilement jusqu'à la carte, `scrollIntoViewIfNeeded` avant chaque clic) ; les versions EN/AR ; l'étape « Votre étude gratuite » au-delà du champ facture (aucun envoi, conformément à la consigne).
