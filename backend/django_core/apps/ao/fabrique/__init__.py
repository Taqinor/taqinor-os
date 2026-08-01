"""Fabrique documentaire des appels d'offres (Groupe AOF).

Le paquet est un domaine NEUF, sans AUCUN couplage au moteur de devis
(`apps/ventes/quote_engine`, règle #4) — pas même en lecture de ses jetons
visuels. Il ne contient QUE de la logique pure : les modules ci-dessous
reçoivent des dictionnaires/dataclasses en paramètre et ne touchent ni l'ORM,
ni le réseau, ni le disque. Le câblage Django (viewsets, services, selectors)
vit hors de ce paquet et l'appelle.

Deux règles gravées, valables pour TOUT module ajouté ici :

1. **Une seule source de vérité.** Un chiffre est calculé UNE fois dans
   `contexte.py` / `derivations.py` puis LU ; aucun module ne le re-saisit et
   aucun gabarit ne contient de littéral chiffré.
2. **Aucun coût ne sort.** `prix_achat`, coût de revient, marge et bénéfice ne
   traversent jamais un rendu remis au maître d'ouvrage (ratchet AOF129).
"""
