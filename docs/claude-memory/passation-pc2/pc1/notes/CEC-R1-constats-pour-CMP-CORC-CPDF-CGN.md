# CEC R1 — constats qui touchent des fichiers d'autres sessions (27/10, lecture seule, base pr1070 4a72c2ff8)

1. P0 (CMP etude_ci_batterie.py::_bloc + CPDF quote_engine/ci/mentions.py::valeur_option_avec) : le retour de l'option
   « avec batterie » = total HT ÷ économie an 1 (sans dégradation, sans remplacement hybride/batterie, sans entretien),
   alors que l'option « sans » passe par economie_ci.flux_ci (25 ans, 1re année entière où cumul ≥ 0). Imprimés côte à côte,
   le classement peut s'inverser (cas : sans « 5 ans » réel 4,31 ; avec affiché 4,4 mais 4,48 au même flux).
   → CEC livre un module pur `apps/ventes/economie_ci_options.py` (flux de l'option avec, mêmes conventions + remplacement
   batterie au montant de sa ligne) ; CMP/CPDF n'auront qu'un appel à brancher. Je préviens dans ce fichier quand c'est sur main.
2. P1 (CMP/CPDF) : option avec toujours en HT (« Économie annuelle HT », totaux.ht_net) même quand la base est TTC (TVA non récupérable, D-CIQ-3).
3. P1 (CORC etude_ci.py) : devis à deux options, option AVEC acceptée ⇒ economie_ci_pour_devis prend l'investissement avec
   batterie mais l'économie sans batterie (etudier_ci reçoit les onduleurs string, _servir_option_avec_seule ne joue qu'en option unique).
4. P1 (CGN BlocEtudeReseau / etudeMarcheBloc.js:403-421) : un client BT ne peut jamais saisir les prix de sa facture (`bt: null`) ⇒ tout BT valorisé sur la grille de repli 2025.
Rapports complets : scratchpad CEC (r1_calcul.md, r1_tarifs.md) — demander à CEC si besoin.

## Ajout 27/10 (rendu réel, 3 PDF sur la pile locale : boulangerie BT, usine MT, bureau BT)
- Chiffres du PDF = bloc economie_ci au centime (éco an 1, TRI, cumul 25 ans, échéancier) : OK.
- CPDF (quote_engine/ci/couverture.py) : FUITE « (moteur C&I) » au client, PDF industriel p3 « Hypothèses de l'estimation » :
  echapper_textes_client transforme « etude_ci.bilan (moteur C&I) » en « …C&amp;I) » AVANT la recherche exacte dans
  SOURCES_CLIENT, qui échoue ; _CODES_INTERNES ne retire que « etude_ci.bilan ». → chercher sur le texte NON échappé.
  (CEC ne change PAS ses chaînes sources : la table SOURCES_CLIENT est la clé.)
- CPDF : jargon imprimé : « Hypothèses de l'estimation », « VAN non calculée : VAN omise : taux… », « principe IEA PVPS »,
  « P90 : P50 × (1 − 1,282 × σ) », « Jordan & Kurtz NREL/JA-5200-51664 », « ANRE décision 04/26 », « Coût moyen non actualisé »,
  « TVA récupérable non déclarée : économies en HT et en TTC », i18n_labels « tarif de vente constant (hypothèse) ».
- CPDF : commercial A/C : retour « 3 ans » + « scénario prudent : retour ≈ 3 ans » = doublon ; pas de gain 25 ans ni TRI sur le
  commercial alors que le bloc les porte ; économie en HT en gros alors que le prix en gros est TTC (lecture 108 600 ÷ 48 140).
- CPDF : phrase « La pointe (soir/nuit) n'est sécurisée qu'avec un stockage… » imprimée 2 fois (p1 et p2).
- CPRS : synthese_ci.argent (= economie_ci_publique) sert encore des textes internes (sources « etude_ci.bilan (moteur C&I) »,
  motifs « (Paramètres — sensibilités C&I) », tarif.mention « Grille ONEE, repli … estimation ») — à traduire/filtrer côté payload public.
- CEC livré sur branche claude/ci-cec (pas encore sur main) : economie_ci_options.flux_option_avec(base_eco, lignes=…, batterie=annee_remplacement_batterie(garantie_mois, cycles)) et retour_au_dixieme(flux) — pour imprimer les deux options au même calcul.

## Ajout 27/10 — relecture Fable R4 (œil client), pour CPDF surtout
- CPDF industriel/finance.py:266-274 : `en_ht = argent.base == 'ht'` ⇒ en base « deux » (TVA inconnue, cas par défaut) le remplacement onduleur est imprimé TTC (B p3 « 191 399,99 MAD TTC ») alors que le tableau du flux est HT (« −159 499,99 »). Lire la base du flux principal (HT sauf base TTC).
- CPDF : « Prix du kWh : Tarif ONEE BT publié (grille du 16/02/2025) » sans aucun prix imprimé : le client ne peut pas retrouver ses 40 118 MAD/an ; imprimer le prix du poste/tranche utilisé (1,709 TTC / 1,4242 HT).
- CPDF finance._nom_scenario : « Dégradation +0,75 % » se lit 0,5 + 0,75 alors que le scénario REMPLACE 0,5 par 0,75 ⇒ « Dégradation 0,75 %/an ».
- CPDF : retour à l'année entière par excès (2,26 → « 3 ans ») et doublon « scénario prudent : retour ≈ 3 ans » ; `economie_ci_options.retour_au_dixieme(flux)` (branche CEC) donne le dixième.
- CPDF : « VAN non calculée : VAN omise : … » (double), « 0,102836 MAD/kWh » (6 décimales), « devis — total HT de l'option retenue », parenthèse « la page indique TVA 18 %, taux légal 2026 : 20 % » (à garder en interne).
- Décisions possibles (fondateur / CPDF) : base « deux » ⇒ TTC en tête sur le commercial BT (une boulangerie supporte le TTC), HT sur l'industriel ; TRI industriel sans aucune charge d'entretien quand le réglage AMOT96 est vide.

## Ajout 27/10 — R3 CEC (recalcul indépendant de 3 profils : tout concorde à 0,014 %)
- CPRS : le JSON public (synthese_ci.argent = economie_ci_publique) garde des sources/motifs internes en texte brut : « tarif de vente constant (hypothèse) », « etude_ci.bilan (moteur C&I) », « (Paramètres — sensibilités C&I) », « D-CIQ-3/-10/-15 », « conventions Groupe CIQ », « décision Q1 du 20/08/2026 … IEA PVPS », « défaut fondateur (à revoir) » (source du remplacement batterie de flux_option_avec). Le PDF les traduit par égalité exacte (ci/couverture.SOURCES_CLIENT, _RESERVES_INTERNES, `^défaut`) — CEC NE CHANGE PAS ces chaînes ; traduire côté payload public (ou lire `source_code`, AMOT84).
- CPDF : retour « sans » imprimé à l'année entière par excès (5,1 → « 6 ») ; si l'option « avec » passe au dixième (flux_option_avec), imprimer les deux au même format (retour_au_dixieme).
