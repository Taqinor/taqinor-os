# Décisions dimensionnement résidentiel (fondateur, 23/10/2026 — lead 1635 Oulkadi)

Origine : lead 1635 (facture d'hiver 6 000 MAD, Casablanca, pas de réponse « présence en journée »).
L'écran générateur recommandait 8 panneaux / 5,68 kWc, le devis automatique du même lead 24 panneaux /
17,04 kWc. Cause : l'aperçu lead (`etude_horaire_view._profil_depuis_lead`) retombait sur le défaut
non résidentiel `absence_jour`, le devis sur le défaut D4 `presence_jour` (PR #1012, mergée 23/10).

Trois décisions de Reda, toutes construites le 23/10/2026 :

1. **Présence en journée = défaut PARTOUT** (« always presume that you are present during the day »).
   `courbes_journalieres._occupation` : le dernier repli est `presence_jour` quel que soit le mode ; la
   réponse réelle du lead (`occupation_jour`) et le profil d'activité pro restent souverains ; la source
   `defaut_non_residentiel` est gardée (bandeau CAD172 « profil supposé ») — PR #1013.
2. **Les gros profils résidentiels (20 000 à 100 000+ MAD/mois) reçoivent une taille.** Choix retenu après
   mesure (0,05-0,10 s par taille sur prod ; catalogue composable jusqu'à 700 panneaux) : **balayage
   adaptatif**, pas une table par tranche de facture (fausse dès que ville, barème, catalogue, phase ou
   occupation diffèrent). `dimensionnement.py` : dense et byte-identique jusqu'à `SEUIL_BALAYAGE_DENSE`
   = 60 panneaux, sinon grille d'≈ 40 tailles puis raffinement panneau par panneau autour des deux
   recommandations — PR #1015.
3. **Au-dessus de 120 panneaux : recommander ET signaler**, pas refuser. `SEUIL_PANNEAUX_RESIDENTIEL`
   = 120 (lignes `hors_residentiel`, « étude sur mesure conseillée » dans la motivation) ;
   `MAX_PANNEAUX_BALAYAGE` = 2 000 reste le garde-fou du zéro de trop (troncature sans recommandation,
   QJR411 inchangé). L'échelle de stockage du devis (`domain/dimensionnement_devis.py`) garde sa borne de
   champ à 120 — hors périmètre.

Non fait, à la demande : cache mémo de l'aperçu (l'adaptatif suffit : ~5-10 s au pire). Point connu : le
chemin lead/devis de l'aperçu ignore une `occupation` envoyée dans le corps (le résolveur ne la lit pas) ;
l'écran n'en envoie pas aujourd'hui.
