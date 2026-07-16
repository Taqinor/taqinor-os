"""Sélecteurs LECTURE SEULE du module Hôtellerie & restauration."""
from decimal import Decimal

from .models import Chambre, Reservation

# NTHOT11 — statuts jamais comptés dans les nuits vendues/revenus (annulation
# ou no-show : la chambre n'a jamais généré de nuitée facturable).
_STATUTS_EXCLUS_REVENUS = [
    Reservation.Statut.ANNULEE, Reservation.Statut.NO_SHOW,
]


def dashboard_hotellerie(company, debut, fin):
    """NTHOT11 — Tableau de bord RevPAR/ADR/TO sur ``[debut, fin)``.

    - ADR (Average Daily Rate) = revenus chambres / nuits vendues.
    - RevPAR = revenus chambres / nuits disponibles totales (nb chambres ×
      nb jours de la période).
    - Taux d'occupation = nuits vendues / nuits disponibles.
    - No-show rate = réservations no-show / total réservations de la période.

    Les réservations ``annulee``/``no_show`` sont EXCLUES du numérateur revenus
    ET du dénominateur nuits vendues (jamais comptées comme une nuit vendue).
    Renvoie des ``Decimal('0')`` (jamais de division par zéro) sur une fenêtre
    sans données."""
    reservations = Reservation.objects.filter(
        company=company, date_arrivee__lt=fin, date_depart__gt=debut)

    vendables = reservations.exclude(statut__in=_STATUTS_EXCLUS_REVENUS)

    nuits_vendues = 0
    revenus_chambres = Decimal('0')
    for reservation in vendables:
        start = max(reservation.date_arrivee, debut)
        end = min(reservation.date_depart, fin)
        nights = max((end - start).days, 0)
        nuits_vendues += nights
        if reservation.prix_nuit_snapshot:
            revenus_chambres += Decimal(nights) * reservation.prix_nuit_snapshot

    nb_chambres = Chambre.objects.filter(company=company).count()
    nb_jours = max((fin - debut).days, 0)
    nuits_disponibles = nb_chambres * nb_jours

    adr = (
        (revenus_chambres / nuits_vendues) if nuits_vendues else Decimal('0'))
    revpar = (
        (revenus_chambres / nuits_disponibles)
        if nuits_disponibles else Decimal('0'))
    taux_occupation = (
        (Decimal(nuits_vendues) / nuits_disponibles)
        if nuits_disponibles else Decimal('0'))

    total_reservations = reservations.count()
    no_show_count = reservations.filter(
        statut=Reservation.Statut.NO_SHOW).count()
    no_show_rate = (
        (Decimal(no_show_count) / total_reservations)
        if total_reservations else Decimal('0'))

    return {
        'adr': adr,
        'revpar': revpar,
        'taux_occupation': taux_occupation,
        'no_show_rate': no_show_rate,
        'nuits_vendues': nuits_vendues,
        'nuits_disponibles': nuits_disponibles,
        'revenus_chambres': revenus_chambres,
        'total_reservations': total_reservations,
        'no_show_count': no_show_count,
    }
