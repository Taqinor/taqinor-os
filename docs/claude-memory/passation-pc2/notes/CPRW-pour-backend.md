# CPRW → propriétaire du payload /proposition (CPRS ou repreneur), 28/10/2026

Données à vérifier, pas des ordres. Ce sont des demandes de contrat, à servir d'abord (règle PACT10) ; la page CPRW les lira une fois sur `main`.

1. **Catégorie commerciale trilingue.** `synthese_ci.categorie.{libelle, accroche, bloc.titre}` ne sont servis que dans une seule langue (`quote_engine/ci/categories.py:605-607`, `_langue(meta[...], langue)`). Un visiteur EN ou AR lit donc le bloc « Votre secteur » en français.
   - Seules `bloc.lignes[].textes` sont trilingues.
   - Proposition : servir aussi `libelle_textes`, `accroche_textes` et `bloc.titre_textes` en {fr,en,ar}.
   - À faire dans le payload et dans les deux copies de `proposal_data.json`.
2. **Autres textes servis dans une seule langue** : `energie.definitions` et `financement.libelle_client`. Pour `energie.definitions`, la page a déjà un palliatif : une constante gardée en parité avec `synthese.py` (CPRW21).
3. **Garanties** : servir `annees` en numérique dans `services.garanties[]`. La page extrait aujourd'hui la durée du texte avec une expression régulière (CPRW15).
4. **Exemple du contrat** : `services.om_option` sans `lignes`, alors que le moteur sert toujours `lignes` (`synthese.py:708-731`). L'exemple diverge de la forme réelle.
5. **Motif de base HT/TTC** : `synthese_ci.argent.motif_base` est une note interne (« … D-CIQ-3 »), non affichée côté page. Il faut le servir en {fr,en,ar} sans code interne pour qu'il apparaisse.
6. **Activités du tunnel public** : le serveur a 23 catégories (`moteur_ci/talons.py`), le tunnel web `lib/commercialCategories.ts` n'en a que 10. Il manque : café, salle de sport, station-service, garage, atelier, imprimerie, pharmacie, coiffure, pressing, supermarché, boucherie, entrepôt, mosquée.
   - Avant de les ajouter côté web, confirmer que `crm.Lead.CategorieCommerciale` et le webhook les acceptent.
