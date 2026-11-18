"""Lectures du rythme (reference/donnees.md §2.8-§2.12) : société ET propriétaire, toujours.

Mêmes portes que `selectors/base.py` (`_du_compte`) : un compte sans société ne lit rien. Aucune règle
de rythme ici — elles vivent dans `moteur/rythme.py` ; on ne fait que lire les lignes.
"""
import datetime

from django.db.models import Q
from django.utils import timezone

from apps.taches.choix import CanalIncitation, StatutTache, TypeIncitationEcran
from apps.taches.models.journee import PlanJour
from apps.taches.models.rythme import IncitationCoach, Preference, ReglagesRythme
from apps.taches.selectors.base import _du_compte, taches_de

#: Jours calendaires lus au plus pour le rythme (regles.md §6.5 point 8, §6.6 : « ≤ 42 jours »).
FENETRE_JOURS = 42
#: Cartes à réponse qui sont « la proposition » de Mon rythme (une seule à la fois).
TYPES_PROPOSITION = (
    TypeIncitationEcran.PROPOSITION_PALIER,
    TypeIncitationEcran.DERIVE_TENIR,
    TypeIncitationEcran.GARDE_TAILLE,
)


def reglages_de(user, *, verrou=False):
    """La `ReglagesRythme` de `user` (ou `None` : il n'a encore créé aucune tâche, invariant 29)."""
    qs = _du_compte(ReglagesRythme.objects, user)
    if verrou:
        qs = qs.select_for_update()
    return qs.first()


def preferences_de(user):
    """Les préférences DITES de `user`, par clé."""
    return list(_du_compte(Preference.objects, user).order_by('cle'))


def preference_de(user, cle, *, verrou=False):
    qs = _du_compte(Preference.objects, user).filter(cle=cle)
    if verrou:
        qs = qs.select_for_update()
    return qs.first()


def plans_de(user, du, au):
    """Les `PlanJour` de `user` dans `[du, au]`, chronologiques."""
    return list(_du_compte(PlanJour.objects, user).filter(jour__gte=du, jour__lte=au).order_by('jour'))


def plans_du_rythme(user, jour):
    """Les `PlanJour` lus par le rythme : les 42 jours calendaires AVANT `jour` (J exclu)."""
    return plans_de(user, jour - datetime.timedelta(days=FENETRE_JOURS), jour - datetime.timedelta(days=1))


def plan_du_jour(user, jour, *, verrou=False):
    qs = _du_compte(PlanJour.objects, user).filter(jour=jour)
    if verrou:
        qs = qs.select_for_update()
    return qs.first()


def cartes_de(user):
    """Toutes les sollicitations et cartes à réponse de `user` (`IncitationCoach`)."""
    return _du_compte(IncitationCoach.objects, user)


def ouvertes(qs, jour):
    """Cartes d'écran encore ouvertes au `jour` : sans réponse et non expirées."""
    return (qs.filter(canal=CanalIncitation.ECRAN, reponse='', repondu_le__isnull=True)
            .filter(Q(expire_le__isnull=True) | Q(expire_le__gte=jour)))


def proposition_ouverte(user, jour):
    """LA proposition ouverte de Mon rythme (la plus récente), ou `None`."""
    return (ouvertes(cartes_de(user), jour).filter(type__in=TYPES_PROPOSITION)
            .order_by('-jour', '-pk').first())


def constats_ouverts(user, jour):
    """Les constats ouverts (liste de Mon rythme), du plus récent au plus ancien."""
    return list(ouvertes(cartes_de(user), jour).filter(type=TypeIncitationEcran.CONSTAT)
                .order_by('-jour', 'cle'))


def bornes_du_jour(jour):
    """`[début, fin)` du jour local `jour`, en instants (heure murale, invariant 14)."""
    debut = timezone.make_aware(datetime.datetime.combine(jour, datetime.time.min))
    return debut, timezone.make_aware(datetime.datetime.combine(jour + datetime.timedelta(days=1),
                                                                datetime.time.min))


def taches_faites_le(user, jour):
    """Tâches de `user` passées à `fait` le jour local `jour` (sous-tâches et routines comprises :
    c'est `compte_du_jour` qui les compte 0)."""
    debut, fin = bornes_du_jour(jour)
    return list(taches_de(user).filter(statut=StatutTache.FAIT, fait_le__gte=debut, fait_le__lt=fin)
                .select_related('recurrence'))
