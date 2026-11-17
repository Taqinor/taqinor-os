# `apps/taches/contract_samples/` — les 60 contrats PACT10 de l'app `taches`

Même doctrine que `apps/agent/contract_samples/README.md` : chaque fichier porte `endpoint`, `pourquoi` et `exemple` (un objet). L'`exemple` est recopié mot pour mot de l'annexe A de `docs/taches/reference/api.md` (révision 3) ; aucun export dans `contractSamples.js` (lecteur générique `exempleContrat`). Posés AVANT leurs vues (TCH2 puis TCH3) : la garde `check_api_shapes.py` s'abstient tant que la route n'est pas lisible.

Pour les formes qui ne sont pas une route (`carte_du_moment`, `item`, `proposition`, `rendez_vous`, `erreurs`, `liens_cibles`), `endpoint` désigne la route qui porte la forme ; le détail est dans `docs/taches/reference/api.md` §6 et annexe A.

## 1/2 — agenda → planification (TCH2)

`agenda`, `agenda_externe`, `agendas_externes`, `ailleurs`, `aujourdhui`, `badge`, `capture`, `carte_du_moment`, `coach_entete`, `convertir_activite`, `decalage`, `erreurs`, `etiquettes`, `geste_annuler`, `gestes`, `item`, `jeton`, `jetons_liste`, `journee_cloture`, `journee_cloturee`, `journee_ecrite`, `journee_proposition`, `liens_cibles`, `lier_activite`, `lot`, `mes_donnees`, `modele`, `modele_instancier`, `modeles_liste`, `planification`.

## 2/2 — planification_apercu → vues (TCH3)

`planification_apercu`, `point`, `priorites`, `projet`, `projet_ecrit`, `projet_vue`, `projets_liste`, `proposition`, `proposition_repondue`, `rappel_repeter`, `recherche`, `reglages`, `reglages_societe`, `rendez_vous`, `revue_decision`, `revue_projets`, `rythme`, `saisie_apercu`, `saisie_rapide`, `suggestion_refusee`, `suggestions`, `supprimees`, `tache`, `tache_changement`, `tache_ecrite`, `tache_recurrente_ecrite`, `tout_effacer`, `tuile`, `vu`, `vues`.
