"""Lectures du module GRC & Conformité (NTGRC).

Point d'entrée UNIQUE de lecture pour les autres apps. Toute fonction est
bornée à une société (multi-tenant) — jamais de lecture cross-société.
"""
from __future__ import annotations

#: NTGRC4 — un « mois » de rétention vaut 30 jours. Choix DÉLIBÉRÉ : la
#: rétention se raisonne en ordres de grandeur légaux (24/36/120 mois), et une
#: arithmétique calendaire exacte ferait dépendre le résultat du mois de
#: lancement du balayage — un objet basculerait « échu » ou non selon qu'on
#: passe en février ou en juillet. 30 jours est stable et reproductible.
JOURS_PAR_MOIS = 30


def politiques_retention_actives(types_objet):
    """NTGRC4 — politiques de rétention ACTIVES pour ces types d'objet.

    Balayage SYSTÈME (toutes sociétés) : ``core.retention`` exécute une
    politique par NOM, pas par société, et c'est à chaque politique de scoper
    elle-même. On renvoie donc des tuples explicitement porteurs de leur
    société, jamais un queryset non borné laissé à l'appelant.

    Renvoie une liste de dicts ``{company, type_objet, jours, action}``,
    triée de façon déterministe.
    """
    from .models import PolitiqueRetentionObjet

    if isinstance(types_objet, str):
        types_objet = [types_objet]
    qs = (PolitiqueRetentionObjet.objects
          .filter(actif=True, type_objet__in=list(types_objet))
          .select_related('company')
          .order_by('company_id', 'type_objet', 'id'))
    return [
        {
            'company': p.company,
            'politique_id': p.pk,
            'type_objet': p.type_objet,
            'jours': int(p.duree_conservation_mois) * JOURS_PAR_MOIS,
            'action': p.action_echeance,
        }
        for p in qs
    ]


def politiques_retention_de_societe(company):
    """Politiques de rétention d'UNE société (lecture bornée, écrans GRC)."""
    from .models import PolitiqueRetentionObjet

    return (PolitiqueRetentionObjet.objects
            .filter(company=company)
            .order_by('type_objet', 'id'))


def violations_echeance_72h_depassee(company, now=None):
    """NTGRC6 — violations dont le délai légal de notification est DÉPASSÉ.

    « Dépassée » = échéance (détection + 72 h) passée ET notification CNDP
    requise ET pas encore notifiée. Une violation déjà notifiée, ou pour
    laquelle la notification n'est pas requise, n'est PAS en retard — on ne
    crie pas au dépassement là où il n'y a pas d'obligation.
    """
    from django.utils import timezone

    from .models import ViolationDonnees

    now = now or timezone.now()
    return (ViolationDonnees.objects
            .filter(company=company,
                    notification_cndp_requise=True,
                    date_notification_cndp__isnull=True,
                    date_echeance_72h__lt=now)
            .exclude(statut__in=[ViolationDonnees.STATUT_NOTIFIEE,
                                 ViolationDonnees.STATUT_CLOTUREE])
            .order_by('date_echeance_72h', 'id'))
