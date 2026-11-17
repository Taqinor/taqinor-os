"""Dates pures partagées par l'analyseur de saisie et la récurrence (sans Django)."""
import calendar
from datetime import date, timedelta


def prochain_jour_semaine(d, jour_semaine, inclure=False):
    """Prochaine date tombant le `jour_semaine` (0 = lundi) ; `d` si `inclure`."""
    ecart = (jour_semaine - d.weekday()) % 7
    if ecart == 0 and not inclure:
        ecart = 7
    return d + timedelta(days=ecart)


def ajouter_mois_borne(d, n):
    """`d` + `n` mois, quantième borné au dernier jour du mois d'arrivée."""
    indice = d.year * 12 + (d.month - 1) + n
    annee, mois = divmod(indice, 12)
    mois += 1
    dernier = calendar.monthrange(annee, mois)[1]
    return date(annee, mois, min(d.day, dernier))


# Nom de regles.md §0.1 ; même fonction.
ajouter_mois = ajouter_mois_borne


def fin_de_mois(d):
    """Dernier jour du mois de `d`."""
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])
