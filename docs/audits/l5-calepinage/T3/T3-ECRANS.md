# T3-ECRANS — rapport (23/11/2026, compte rev_b1, 1440 x 900 clair + sombre, pile l5cal)

Comptes (31 tâches) : ok 8 · partiel 22 · non-fait 1 (ACAL1818) · faux 0 · régression 0 · déjà-présent 0. Parmi les « partiel », 7 contiennent des cas NON ESSAYÉS faute de données sur la pile (voir plus bas).

ok : ACAL1437, 1730, 1731, 1745, 1805, 1822, 1517, 1428.
non-fait : ACAL1818 (zone tactile du curseur Heure du soleil : 17 px en WebKit 390x844, attendu >= 44).
partiel : 1727 (Résultats sans bouton de pied « Préparer les documents » à l'état incomplet), 1800, 1801, 1802, 1803, 1804, 1280, 1617, 1445, 1827, 1829, 1830, 1831, 1833, 1344 (défilement résiduel 11 px), 1708 (non jouable), DC-RESULTAT-INCOMPLET-COMPTE (« Voir les étapes » ouvre le détail mais ne l'amène pas à l'écran), 1832, 1340, 1267, DC-PVGIS-PERTES-EGALES, DC-ECART-DEVIS-SIGNE.

Non essayé (pile) : résultat COMPLET (ACAL1832, DC-PVGIS, DC-ECART : aucun calepinage complet dans cette société), « Voir les valeurs » (ACAL1708 : aucune valeur publiée), carte d'accès solaire en Expert (ACAL1340, clic non joué par script) et /devis/mon-toit, pompage (ACAL1267), planches v1|v2|réel jugées par un relecteur neuf, schéma aux fiches complètes (ACAL1831).

Défauts qui gênent (constats : registre/constats/T3-T3-ECRANS.jsonl) : carte d'adresse qui avale zoom et clics de tracé sur un calepinage sans toit (S2) ; avertissement « cible de calepinage vide » juste après avoir généré un devis (S2) ; pile de zoom cachée par les bandeaux GPS / C&I (S3) ; restes du chrome carte autour du panneau plein en Expert > Résultats (S3) ; « Localiser » doré étiré en Expert (S3) ; barre sombre parasite au-dessus du bandeau (S3). Aucun défaut bloquant (impasse, donnée perdue).

Mesures qui tiennent (v2) : carte 1440x900 ; bandeau 16,16 1408x56 r16 ; rail 16,88 76 r20 ; panneau 1040,88 384x796 r20 ; bouton d'étape 340x52 r14 15/700 ombre dorée ; titre 24 px ; « Étape n sur 5 » 12 px ; barre d'outils 56 r18 ; segments 44 ; jetons --cal-* clair et sombre.

Captures : scratchpad/T3/T3-ECRANS/cap/ ; verdicts : registre/evenements/T3-T3-ECRANS-cv.jsonl.
