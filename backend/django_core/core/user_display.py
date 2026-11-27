"""Nom d'affichage d'un utilisateur : écrit UNE fois, utilisé partout où un
écran montre « qui a fait » (historique/chatter d'un lead, jalon « Devis
signé »). Prénom + nom quand l'un des deux existe ; le login seulement si les
deux sont vides ; ``None`` sans utilisateur.
"""


def nom_affiche(user):
    if user is None:
        return None
    first = (getattr(user, 'first_name', '') or '').strip()
    last = (getattr(user, 'last_name', '') or '').strip()
    complet = f'{first} {last}'.strip()
    if complet:
        return complet
    return getattr(user, 'username', None) or None
