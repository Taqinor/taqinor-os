"""Sélecteurs SAV lus par la supervision (monitoring) — AMON43.

Module à part : ``selectors.py`` est un fichier mur (garde C20). Lecture
seule, bornée à ``company`` ; monitoring les lit en import local.
"""


def heures_immobilisation(downtimes, debut, fin):
    """Heures d'immobilisation dans ``[debut ; fin]`` : UNION des fenêtres
    (deux équipements arrêtés en même temps comptent une fois) ; une
    fenêtre en cours (``fin`` NULL) court jusqu'à ``fin``."""
    segments = sorted(
        (max(dt.debut, debut), min(dt.fin or fin, fin)) for dt in downtimes)
    total, courant_debut, courant_fin = 0.0, None, None
    for seg_debut, seg_fin in segments:
        if seg_fin <= seg_debut:
            continue
        if courant_fin is None or seg_debut > courant_fin:
            if courant_fin is not None:
                total += (courant_fin - courant_debut).total_seconds() / 3600
            courant_debut, courant_fin = seg_debut, seg_fin
        else:
            courant_fin = max(courant_fin, seg_fin)
    if courant_fin is not None:
        total += (courant_fin - courant_debut).total_seconds() / 3600
    return total


def disponibilite_installation(company, installation_id, *, debut, fin):
    """AMON43 — disponibilité % d'un système sur ``[debut ; fin]`` (datetimes
    aware) : union des immobilisations SAV de ses équipements. ``None`` quand
    le système n'a aucun équipement au parc (l'appelant garde l'indice
    relevés)."""
    from django.db.models import Q

    from .models import Equipement, EquipementDowntime

    equipements = Equipement.objects.filter(
        company=company, installation_id=installation_id)
    if not equipements.exists():
        return None
    duree = (fin - debut).total_seconds() / 3600
    if duree <= 0:
        return 100.0
    downtimes = EquipementDowntime.objects.filter(
        equipement__in=equipements, debut__lte=fin,
    ).filter(Q(fin__gte=debut) | Q(fin__isnull=True))
    heures = min(heures_immobilisation(downtimes, debut, fin), duree)
    return round((1 - heures / duree) * 100, 2)


def alarmes_onduleur_ouvertes(company, installation_id):
    """AMON43 — nombre d'alarmes onduleur OUVERTES (active, escaladée) des
    équipements du système."""
    from .models import AlarmeOnduleur

    statut = AlarmeOnduleur.Statut
    return AlarmeOnduleur.objects.filter(
        company=company, equipement__installation_id=installation_id,
        statut__in=[statut.ACTIVE, statut.ESCALADEE]).count()


def dernier_nettoyage_sav(company, installation_id, avant):
    """AMON44 — date (locale) de la dernière étape de nettoyage des panneaux
    cochée sur un ticket SAV du système, au plus tard le jour ``avant`` ;
    ``None`` sinon. Clés = celles des modèles d'entretien SAV."""
    from datetime import datetime, time, timedelta

    from django.db.models import Max
    from django.utils import timezone

    from .models import TicketChecklistItem
    from .services import (
        MODELE_ENTRETIEN_CI_ETAPES, MODELE_ENTRETIEN_POMPAGE_ETAPES,
    )

    cles = [cle for cle, _libelle in (MODELE_ENTRETIEN_POMPAGE_ETAPES
                                      + MODELE_ENTRETIEN_CI_ETAPES)
            if 'nettoyage' in cle]
    borne = timezone.make_aware(
        datetime.combine(avant + timedelta(days=1), time.min))
    dernier = TicketChecklistItem.objects.filter(
        company=company, ticket__installation_id=installation_id,
        cle__in=cles, coche=True, date_coche__lt=borne,
    ).aggregate(d=Max('date_coche'))['d']
    return None if dernier is None else timezone.localtime(dernier).date()
