# CPRW — état final PC1 (28/10/2026, 01:21 UTC)

1. **Mergé sur main** : 4 PR.
   - #1104 : extraction des blocs C&I/agricoles.
   - #1116 : round 1, CPRW2-14.
   - #1119 : round 2, CPRW15-24 et le correctif de doublon.
   - #1122 : round 3, CPRW25-29.

   Trois rounds L3 complets, chacun relu par Fable avec une passe « œil client ». Rien de CPRW ne reste non mergé.
2. **Reste pour le PC2, hors fichiers CPRW** :
   - RWEB : brancher `installerPrefillEntreprise` et `messageEntreprise` dans la page de devis ; corriger le commentaire ICE de `lib/proposition.ts` ; placer les services avant l'échéancier (voir CPRW-pour-RWEB.md).
   - Backend ou contrat : catégorie trilingue, `annees` des garanties, `motif_base` en FR/EN/AR, exemple `om_option.lignes`, les 13 activités du tunnel (voir CPRW-pour-backend.md).
3. **Optionnel pour CPRW** : jusqu'à deux rounds de vérification à sec.

   Non vérifié faute de serveur local : rendu dans un vrai navigateur, mobile et arabe (RTL).

   Les versions EN/AR de /professionnel ont été alignées dans la même session (décision « à revoir »).
