"""Sélecteurs (lecture seule) du module ``apps.sante``.

Fonctions utilitaires que d'autres apps peuvent importer **via import local**
(dans le corps d'une fonction, jamais au niveau module) pour éviter les
dépendances cycliques et respecter les contrats d'import CI-enforced.
"""


def _plages_ouverture(praticien, date):
    """NTSAN29/NTSAN30 — plages ``(début, fin)`` timezone-aware d'ouverture
    d'un praticien pour ``date``. Retombe sur 08:00-18:00 tant qu'aucun
    ``HoraireOuverturePraticien`` (NTSAN30) n'est configuré pour ce
    praticien+jour — additif, jamais de régression pour un praticien déjà en
    service avant paramétrage des horaires."""
    from datetime import datetime, time

    from django.apps import apps as django_apps
    from django.utils import timezone

    jour_semaine = date.weekday()
    try:
        HoraireOuverturePraticien = django_apps.get_model(
            'sante', 'HoraireOuverturePraticien')
    except LookupError:  # pragma: no cover - avant migration NTSAN30
        HoraireOuverturePraticien = None

    if HoraireOuverturePraticien is not None:
        horaires = list(HoraireOuverturePraticien.objects.filter(
            company=praticien.company, praticien=praticien,
            jour_semaine=jour_semaine))
        if horaires:
            return [
                (timezone.make_aware(datetime.combine(date, h.heure_debut)),
                 timezone.make_aware(datetime.combine(date, h.heure_fin)))
                for h in horaires
            ]

    return [(
        timezone.make_aware(datetime.combine(date, time(8, 0))),
        timezone.make_aware(datetime.combine(date, time(18, 0))),
    )]


def _indisponibilites_du_jour(praticien, date):
    """NTSAN30 — ``IndisponibilitePraticien`` qui recoupent ``date``. Liste
    vide tant que le modèle n'existe pas (avant migration NTSAN30)."""
    from datetime import datetime, time

    from django.apps import apps as django_apps
    from django.utils import timezone

    try:
        IndisponibilitePraticien = django_apps.get_model(
            'sante', 'IndisponibilitePraticien')
    except LookupError:  # pragma: no cover - avant migration NTSAN30
        return []

    debut_jour = timezone.make_aware(datetime.combine(date, time.min))
    fin_jour = timezone.make_aware(datetime.combine(date, time.max))
    qs = IndisponibilitePraticien.objects.filter(
        company=praticien.company, praticien=praticien,
        date_debut__lt=fin_jour, date_fin__gt=debut_jour)
    return [(i.date_debut, i.date_fin) for i in qs]


def creneaux_disponibles(*, company, praticien, date, duree_min=30):
    """NTSAN29 — créneaux libres d'un praticien pour un jour donné (lecture
    seule, endpoint interne SANS exposition publique ni auth patient en v1 —
    fondation d'un futur module de prise de RDV en ligne, NTCOL, hors
    périmètre de ce lot). Retire les créneaux couverts par un ``RendezVous``
    actif (statut != annulé) et par une ``IndisponibilitePraticien``
    (NTSAN30). Renvoie une liste de ``datetime`` (début de créneau,
    timezone-aware) triée chronologiquement."""
    from datetime import timedelta

    from .models import RendezVous

    plages = _plages_ouverture(praticien, date)
    if not plages:
        return []

    occupes = list(RendezVous.objects.filter(
        company=company, praticien=praticien, date_heure_debut__date=date,
    ).exclude(statut=RendezVous.Statut.ANNULE))
    indisponibilites = _indisponibilites_du_jour(praticien, date)

    creneaux = []
    for debut_plage, fin_plage in plages:
        cursor = debut_plage
        while cursor + timedelta(minutes=duree_min) <= fin_plage:
            fin_creneau = cursor + timedelta(minutes=duree_min)
            bloque_rdv = any(
                cursor < (rdv.date_heure_debut + timedelta(minutes=rdv.duree_min))
                and fin_creneau > rdv.date_heure_debut
                for rdv in occupes)
            bloque_indispo = any(
                cursor < fin_indispo and fin_creneau > debut_indispo
                for debut_indispo, fin_indispo in indisponibilites)
            if not bloque_rdv and not bloque_indispo:
                creneaux.append(cursor)
            cursor = fin_creneau
    return creneaux


def statistiques_actes_et_conventions(company, *, date_debut=None, date_fin=None):
    """NTSAN28 — rapport agrégé : actes les plus facturés (volume + CA) et
    répartition du CA par convention (CNOPS/CNSS/mutuelle/cash), utile pour
    négocier les grilles tarifaires. ``date_debut``/``date_fin`` (optionnels,
    ``date``) filtrent respectivement sur ``ActeRealise.date_realisation``
    (par acte) et ``FactureSante.date_emission`` (par convention).

    Les totaux par convention correspondent EXACTEMENT à la somme de
    ``FactureSante.part_tiers_payant_ttc`` groupée par convention (garde
    testée) — jamais un recalcul indépendant qui pourrait diverger."""
    from django.db.models import Count, F, Sum

    from .models import ActeRealise, FactureSante

    actes_qs = ActeRealise.objects.filter(company=company)
    if date_debut:
        actes_qs = actes_qs.filter(date_realisation__date__gte=date_debut)
    if date_fin:
        actes_qs = actes_qs.filter(date_realisation__date__lte=date_fin)

    par_acte = list(
        actes_qs.annotate(ligne_ttc=F('tarif_applique_ttc') * F('quantite'))
        .values('acte_id', 'acte__libelle')
        .annotate(volume=Count('id'), chiffre_affaires=Sum('ligne_ttc'))
        .order_by('-chiffre_affaires'))

    factures_qs = FactureSante.objects.filter(company=company)
    if date_debut:
        factures_qs = factures_qs.filter(date_emission__date__gte=date_debut)
    if date_fin:
        factures_qs = factures_qs.filter(date_emission__date__lte=date_fin)

    par_convention = list(
        factures_qs.values('convention_id', 'convention__nom')
        .annotate(
            ca_tiers_payant=Sum('part_tiers_payant_ttc'),
            ca_total=Sum('total_ttc'),
            nb_factures=Count('id'))
        .order_by('-ca_total'))

    return {'par_acte': par_acte, 'par_convention': par_convention}


def tarif_applicable(acte, convention):
    """NTSAN8 — tarif TTC applicable pour un acte, pour une convention
    donnée (ou ``None``).

    Lit ``GrilleTarifaire`` pour (convention, acte) si une ligne existe,
    sinon retombe sur ``ActeMedical.tarif_base_ttc``. Renvoie un dict
    ``{'tarif_ttc': Decimal, 'taux_prise_charge_pct': Decimal, 'source':
    'grille'|'base'}``.
    """
    from .models import GrilleTarifaire

    if convention is not None:
        grille = GrilleTarifaire.objects.filter(
            company=acte.company, convention=convention, acte=acte).first()
        if grille is not None:
            return {
                'tarif_ttc': grille.tarif_convention_ttc,
                'taux_prise_charge_pct': grille.taux_prise_charge_pct,
                'source': 'grille',
            }
    return {
        'tarif_ttc': acte.tarif_base_ttc,
        'taux_prise_charge_pct': 0,
        'source': 'base',
    }
