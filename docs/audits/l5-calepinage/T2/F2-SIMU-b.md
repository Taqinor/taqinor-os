# Rapport F2-SIMU-b — contre-vérification, tour 2 (23/11/2026, compte rev_b7)

## 1. Verdict
23 corrections rejouées sur la pile réelle (22 de la liste + ACAL712) : 19 ok, 4 partielles, aucune fausse ni régression.
Le moteur est solide (batterie, hors réseau, plafonds, ombrage) ; les trous sont aux bords : un champ de fiche que personne ne peut saisir (optimiseur), une liste calculée jamais affichée (« Ce qui est supposé »), une fonction inutilisable avec la météo réglée de la société (objectif de couverture), un contrôle de saisie qui laisse passer « oui ».

## 2. Comptes
ok 19 · partiel 4 · non-fait 0 · faux 0 · régression 0 · déjà-présent 0 · non essayé : voir §5.
- ok : 712, 713, 716, 722, 724, 730, 770, 771, 787, 793, 794, 796, 797, 798, 800, 801, 802, 828, 829.
- partiel : ACAL723 (rendement de fiche optimiseur non saisissable : l'étape ne peut jamais calculer), ACAL733 (« oui » accepté et stocké au lieu d'un 400), ACAL835 (marche en fenêtre d'un an, toujours refusée avec la fenêtre 2014-2023 de la société), ACAL980 (serveur ok, aucun écran ne l'affiche).
- Verdicts : registre/evenements/T2-F2-SIMU-b-cv.jsonl.

## 3. Constats neufs (registre/constats/T2-F2-SIMU-b.jsonl)
- T2-F2-SIMU-b-001 (S3) : optimiseur: « oui » accepté en 200 et stocké dans l'affectation manuelle (ACAL733).
- T2-F2-SIMU-b-002 (S3) : opt_rendement_pct, opt_modules_par_optimiseur, opt_pmax_in_w, opt_v_in_* n'ont ni champ de formulaire Stock ni champ d'API ; le résultat réclame pourtant « FicheTechnique.opt_rendement_pct » (nom interne).
- T2-F2-SIMU-b-003 (S3) : objectif de couverture refusé en 409 « série agrégée au jour » dès que la fenêtre météo dépasse un an (série persistée limitée à 366 jours) ; le message ne dit pas quoi faire.
- T2-F2-SIMU-b-004 (S3) : la section « Ce qui est supposé » (ACAL980) n'est rendue nulle part.
- Petits défauts sans ligne de registre : messages de refus « reçu : « None » » pour un champ absent (coupures, groupe) ; chevauchement et début ≥ fin d'une plage d'injection répondent 409 au lieu de 400.

## 4. Ce qui est bien
Carte « chaîne touchée par l'ombre » claire (parades fixes, sans chiffre de gain, lien de 44 px) et absente quand les bornes sont égales ; hypothèse paysage / placement libre bien dite ; verdict batterie jamais prononcé sans seuils sourcés ; refus de saisie nommés champ par champ ; groupe électrogène qui ramène la défaillance de 647 kWh à 0 ; tmy grisé avec son motif et valeur enregistrée conservée avec avertissement.

## 5. Non essayé
- Fond de carte / clé d'IA : sans objet ici.
- ACAL712 : la phrase « N module(s) sous le seuil… le plus ombré reçoit X % » (sur ce toit, quand les bornes diffèrent aucun module n'est sous le seuil). ACAL722 : l'exemple chiffré 9,09 %. ACAL723 : le 0,20 % à 99 % (champ non saisissable, voir constat 002). ACAL716 : l'état « vide » (la société porte déjà 0,6 / 5 / 10 du profil de départ ; je n'ai pas effacé un réglage partagé). ACAL730 : fuseau absent (409) et autre société (404). ACAL771 : l'ordre réglages/plans/épingle avec réglages vides. ACAL794 : mots « adaptée » et « trop grande ». ACAL800 : actif:false / groupe:null. ACAL802 : cas « raison de l'absence ». ACAL828 : pas ≠ 60 min. ACAL829 : charge 9 kW.
- Placement libre (ACAL713) joué en écrivant angleDeg par l'API layout, pas par un glisser dans l'atelier.

## 6. Réglages partagés touchés (tous remis)
Borne « courante » 12 puis 5 ; seuil de dérivation 0,6 / 0,82 puis 0,85 ; seuils batterie posés puis effacés ; fenêtre d'années 2022 puis 2014-2023 ; mode météo trouvé sur « tmy » vers 06 h 40 (posé par un autre relecteur) et remis sur « pluriannuel » (2014-2023). Constaté : des enregistrements concurrents du formulaire Réglages écrasent les valeurs des autres (seuil de dérivation repassé à 0,6 sans mon geste). Aucune simulation bloquée plus de 6 minutes. Calepinages créés : 2014-2017, 2029 ; produits d'essai 22988 (optimiseur) et 22990 (module à fiche incomplète).
