"""YSERV13 — Contrôles d'intégrité inter-documents planifiés.

Aucun contrôle transverse d'états orphelins n'existait entre apps (les
receivers domain-event M6 sont BEST-EFFORT et les statuts multi-apps peuvent
diverger silencieusement, ex. un receiver raté). Ce module liste, PAR
SOCIÉTÉ, des familles de cas orphelins CONSTRUITES sur des règles métier déjà
en place ailleurs (M6 `devis_accepted`, sweep de parc FG70…) — LECTURE SEULE,
ne corrige RIEN automatiquement.

Multi-tenant : chaque famille est bornée à la société appelante. Import LOCAL
des modèles des autres apps (même pattern historique que `reports.py`) — pas
de mutation, jamais d'exception qui casserait les autres familles."""


def devis_acceptes_sans_chantier(company):
    """Devis `accepte` sans aucune `Installation` liée (receiver M6
    `devis_accepted` -> `crm`/`installations` raté). Renvoie une liste
    d'ids de devis."""
    from apps.ventes.models import Devis

    return list(
        Devis.objects.filter(company=company, statut=Devis.Statut.ACCEPTE)
        .filter(installations__isnull=True)
        .values_list('id', flat=True)
    )


def chantiers_receptionnes_sans_parc(company):
    """Chantier `receptionne`/`cloture` sans AUCUN `sav.Equipement` au parc
    (sweep FG70 raté). Renvoie une liste d'ids d'``Installation``."""
    from apps.installations.models import Installation

    return list(
        Installation.objects.filter(
            company=company,
            statut__in=[Installation.Statut.RECEPTIONNE,
                        Installation.Statut.CLOTURE],
            annule=False,
        ).filter(equipements__isnull=True)
        .values_list('id', flat=True)
    )


def reservations_non_liberees_orphelines(company):
    """`StockReservation` ACTIVE non consommée d'un chantier CLOS ou ANNULÉ
    (devrait avoir été libérée à la clôture/annulation). Renvoie une liste
    d'ids de ``StockReservation``."""
    from apps.installations.models import Installation, StockReservation

    return list(
        StockReservation.objects.filter(
            company=company, active=True, consomme=False,
        ).filter(
            installation__statut=Installation.Statut.CLOTURE,
        ).values_list('id', flat=True)
    ) + list(
        StockReservation.objects.filter(
            company=company, active=True, consomme=False,
            installation__annule=True,
        ).values_list('id', flat=True)
    )


def interventions_non_terminees_chantier_clos(company):
    """Intervention NON terminée (statut hors TERMINEE/VALIDEE) d'un chantier
    CLOTURE ou ANNULÉ. Renvoie une liste d'ids d'``Intervention``."""
    from apps.installations.models import Installation, Intervention

    termine_statuts = [Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE]
    return list(
        Intervention.objects.filter(company=company)
        .exclude(statut__in=termine_statuts)
        .filter(
            installation__statut=Installation.Statut.CLOTURE,
        ).values_list('id', flat=True)
    ) + list(
        Intervention.objects.filter(company=company)
        .exclude(statut__in=termine_statuts)
        .filter(installation__annule=True)
        .values_list('id', flat=True)
    )


def tickets_clotures_avec_intervention_ouverte(company):
    """Ticket SAV `cloture` avec au moins une `Intervention` liée encore
    NON terminée. Renvoie une liste d'ids de ``Ticket``."""
    from apps.installations.models import Intervention
    from apps.sav.models import Ticket

    termine_statuts = [Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE]
    return list(
        Ticket.objects.filter(company=company, statut=Ticket.Statut.CLOTURE)
        .filter(interventions__company=company)
        .exclude(interventions__statut__in=termine_statuts)
        .distinct()
        .values_list('id', flat=True)
    )


def contrats_maintenance_actifs_expires(company):
    """`ContratMaintenance` `actif=True` dont `date_renouvellement` est
    DÉPASSÉE (devrait avoir été renouvelé ou désactivé). Renvoie une liste
    d'ids de ``ContratMaintenance``."""
    from django.utils import timezone
    from apps.sav.models import ContratMaintenance

    today = timezone.localdate()
    return list(
        ContratMaintenance.objects.filter(
            company=company, actif=True,
            date_renouvellement__isnull=False,
            date_renouvellement__lt=today,
        ).values_list('id', flat=True)
    )


def factures_payees_avec_solde(company):
    """Facture `payee` dont `montant_du` (propriété calculée) reste ≠ 0
    (règlement partiel comptabilisé à tort comme payée). Renvoie une liste
    d'ids de ``Facture``."""
    from decimal import Decimal
    from apps.ventes.models import Facture

    out = []
    for f in Facture.objects.filter(company=company, statut=Facture.Statut.PAYEE):
        try:
            if f.montant_du != Decimal('0') and f.montant_du != 0:
                out.append(f.id)
        except Exception:  # pragma: no cover - dégradation défensive
            continue
    return out


# Catalogue des familles (label actionnable + fonction) — utilisé par
# l'endpoint et la commande de gestion pour rester en un seul point de vérité.
FAMILIES = [
    ('devis_acceptes_sans_chantier',
     "Devis acceptés sans chantier créé", devis_acceptes_sans_chantier),
    ('chantiers_receptionnes_sans_parc',
     "Chantiers réceptionnés/clôturés sans équipement au parc",
     chantiers_receptionnes_sans_parc),
    ('reservations_non_liberees',
     "Réservations de stock non libérées d'un chantier clos/annulé",
     reservations_non_liberees_orphelines),
    ('interventions_non_terminees_chantier_clos',
     "Interventions non terminées d'un chantier clôturé/annulé",
     interventions_non_terminees_chantier_clos),
    ('tickets_clotures_intervention_ouverte',
     "Tickets clôturés avec une intervention liée encore ouverte",
     tickets_clotures_avec_intervention_ouverte),
    ('contrats_maintenance_expires',
     "Contrats de maintenance actifs dont l'échéance de renouvellement est "
     "dépassée", contrats_maintenance_actifs_expires),
    ('factures_payees_avec_solde',
     "Factures payées avec un solde dû non nul", factures_payees_avec_solde),
]


def controle_integrite(company):
    """YSERV13 — exécute TOUTES les familles pour une société.

    Renvoie ``{famille: {label, ids}}`` ; chaque famille est isolée (une
    erreur dans une famille n'empêche pas les autres — dégradation à liste
    vide)."""
    result = {}
    for key, label, fn in FAMILIES:
        try:
            ids = fn(company)
        except Exception:  # pragma: no cover - dégradation défensive
            ids = []
        result[key] = {'label': label, 'ids': ids}
    return result


def total_anomalies(result):
    """Nombre total d'anomalies détectées, toutes familles confondues."""
    return sum(len(v['ids']) for v in result.values())
