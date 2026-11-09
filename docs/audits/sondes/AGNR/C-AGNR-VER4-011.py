# flake8: noqa  (sonde de contre-visite vérifie AGNR du 04/11, rejouable par scripts/sonde.py — AMET93)
"""AGNR34 (écran, pur JS — rien de rejouable dans le conteneur Django) : hiver 500 / été 1 200 posent 12 mois
'derivee' ; le vendeur corrige UN mois (Mars → 900, `DevisGenerator.jsx::setMonth` le marque 'tapee').
`useApercuEtude.js` : `facturesSaisies` = aucune case 'exemple' ⇒ vrai, et `consoEcran` dérive la conso des 12 cases
(Mars 900 compris) pour l'aperçu. `etatDevis.js::entreesDeEtat` : `tapees` exige 12 'tapee' ⇒ null ⇒ `emises` null ⇒
`deux = facturesHiverEte(fHiver, fEte)` ⇒ le corps n'envoie que `factures_hiver_ete {500, 1200}` : le mois tapé est
perdu sans avertissement (`moisNonSaisis` ne nomme que les cases 'exemple'), la conso enregistrée (marches serveur)
≠ celle de l'aperçu, et la réouverture (`devisVersEtat` → `estimerMois`) remet Mars à 500. Second cas (note du lot 1) :
vider une case dérivée la repasse 'exemple' ⇒ `facturesSaisies` faux ⇒ ni `factures_hiver_ete` ni série envoyés,
hiver/été tapés non enregistrés (avertissement « Mois non saisis » affiché). Lecture du code à 4cd568403."""
SONDE = {"constat": "C-AGNR-VER4-011", "sha": "4cd568403",
         "attendu": "STATIQUE : mois tapé parmi des mois dérivés jamais envoyé ; aperçu ≠ conso enregistrée",
         "modeles": ["ventes.Devis"]}


def sonde(ctx):
    return ("STATIQUE — frontend/src/features/ventes/quote/etatDevis.js:360-367 (entreesDeEtat : tapees null sauf 12 "
            "'tapee', repli factures_hiver_ete), frontend/src/pages/ventes/generator/hooks/useApercuEtude.js:88,101 "
            "(facturesSaisies / consoEcran sur les 12 cases), frontend/src/pages/ventes/DevisGenerator.jsx:1436-1440 "
            "(setMonth : 'tapee' / 'exemple'). Mixte derivee+tapee : corps = factures_hiver_ete seul.")
