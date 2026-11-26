# Choix pris sans le fondateur — CONFIRMÉS par Reda le 26/11/2026

**Réponse de Reda le 26/11/2026, mot pour mot : « all the 18 choices are good ». Les dix-huit choix sont gardés.**

Dix-huit choix pris par l'orchestrateur pendant la nuit du 25 au 26/11 et la journée du 26/11, en l'absence de Reda.
Chacun est écrit dans `docs/audits/decisions.yml` avec sa raison. Reda a demandé cette liste le 26/11 au soir pour dire
lesquels changer. Répondre par le numéro : « garder » ou « changer ».

## Le schéma électrique du devis et de la page du client

1. **Chaque option du devis a son propre schéma** (sans batterie / avec batterie), jamais un schéma commun.
   (D-ACAL-131)
2. **Le client ne reçoit que ce qui est enregistré sur le devis** : rien n'est recalculé quand il ouvre sa page.
   (D-ACAL-140 — complété le 26/11 par la décision de Reda D-ACAL-158 : les deux options sont enregistrées à l'envoi.)
3. **Le schéma du devis reprend les vraies chaînes du calepinage seulement si** le toit, le nombre de panneaux et
   l'onduleur sont les mêmes ; sinon il montre les chaînes calculées pour le devis. (D-ACAL-141)
4. **Rien d'incertain n'est dessiné pour le client** : une partie non calculée ou « à confirmer » n'apparaît pas, sans
   mention « à dimensionner ». (D-ACAL-142)
5. **Le devis propose aussi des chaînes de longueurs différentes** (12 + 12 + 11) quand la répartition égale ne tient
   pas — pour les études neuves ; un devis déjà envoyé garde la sienne. (D-ACAL-139)

## La visionneuse au soleil des clients de confiance

6. **Les liens ordinaires ne changent pas** : seuls les liens « client de confiance » ont le soleil qui bouge.
   (D-ACAL-134)
7. **Elle s'ouvre à l'instant choisi par le commercial**, sinon en été à midi ; deux raccourcis Hiver (20 décembre) et
   Été (20 juin). (D-ACAL-135)
8. **La couleur de chaque panneau est l'ensoleillement mesuré et enregistré** par le calepinage ; un toit dont l'ombre
   n'a pas été mesurée n'est pas coloré (jamais « tout en or » par défaut). (D-ACAL-136)
9. **Les objets voisins saisis (arbres, bâtiments, poteaux) sont dessinés**, forme et hauteur seulement, jamais le nom
   saisi (il peut nommer un voisin). (D-ACAL-137)
10. **La carte satellite reste autour du toit du client** : on ne peut pas dézoomer jusqu'à la ville. (D-ACAL-138)
11. **L'heure est dite « heure solaire »** dans les trois langues, sans conversion en heure de la montre. (D-ACAL-143)

## Phrases et calculs

12. **Un pan en pente tourné au nord dit la vérité** : « On pose 0 », y compris sur le site public (avant : « On pose N
    panneaux » alors que rien n'était posé). (D-ACAL-144)
13. **Toit plat : on ne réécrit pas les anciens documents** ; les calculs ignorent simplement la « pente » mémorisée d'un
    toit plat. (D-ACAL-145 — la suite, pour les documents du client, est la décision de Reda D-ACAL-149.)
14. **Une simulation périmée ne nomme sa cause que si elle est prouvée** : « un réglage de la société a changé » quand la
    trace le montre, sinon « le document ou un réglage de la société a changé ». (D-ACAL-146)
15. **Fichiers météo horizontaux : le soleil est placé à la demi-heure partout**, sans changer le numéro de version (cela
    aurait déclaré périmées toutes les simulations enregistrées). (D-ACAL-147)
16. **Une courbe de consommation de 24 zéros vaut « pas de courbe »** : la consommation vient de la facture du lead si
    elle existe ; une charge déclarée seule (voiture, pompe à chaleur) est comptée sur une base de 0 kWh, avec
    l'avertissement « aucune consommation de base n'est connue ». (D-ACAL-150)

## Droits

17. **Un technicien ne peut plus être mis responsable d'un calepinage qu'il ne pourrait pas ouvrir** (un technicien
    n'ouvre que les calepinages des visites qui lui sont confiées) : le menu ne le propose plus et le serveur refuse.
    Conséquence pour un administrateur : il ne peut plus confier à un technicien un calepinage sans lead, ni un lead où
    il n'a pas de visite. (lot 8, constat T4-X3-016 ; rien ne change dans D-ACAL-106 ni D-ACAL-126.)
18. **L'aperçu du devis dans l'atelier ne nomme aucun devis à qui n'a pas le droit de lire les devis** (référence,
    statut, onduleur d'un devis) — application de « aucun devis ni aucun prix » pour le technicien. (lot 8)
