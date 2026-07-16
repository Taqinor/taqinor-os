"""Services (écriture/orchestration) du module ``apps.sante``.

Comme ``selectors.py`` (lecture), destiné à être importé PAR D'AUTRES APPS
(import local, jamais au niveau module) — toute référence à un document d'une
autre app passe par une FK par chaîne ou par le sélecteur/service dédié de
cette app cible, jamais par un import direct de ses ``models``.
"""


def attribuer_numero_dossier(patient):
    """NTSAN3 — pose ``patient.numero_dossier`` (anti-collision, plus-haut-
    utilisé+1 par société) via le service de numérotation de fondation
    ``core.numbering`` — jamais un ``count()+1`` (collision documentée si des
    dossiers sont supprimés). No-op si déjà posé (idempotent)."""
    if patient.numero_dossier:
        return patient
    from core.numbering import next_reference

    from .models import Patient

    patient.numero_dossier = next_reference(
        Patient, 'PAT', patient.company, padding=5, period='none')
    patient.save(update_fields=['numero_dossier'])
    return patient


def resoudre_client_pour_patient(patient):
    """NTSAN3 — résout/rattache un ``crm.Client`` pour ce patient, SANS jamais
    importer ``apps.crm.models`` (import fonction-local + ``selectors.py``
    de la cible, comme ``apps.crm.services.resolve_client_for_lead``).

    Règle : réutilise le lien existant si déjà posé ; sinon cherche un client
    de la MÊME société par email (si le patient en a un) ; sinon en crée un
    nouveau. Renvoie l'instance ``crm.Client`` (jamais None : un patient a
    toujours un dossier client correspondant une fois résolu).
    """
    if patient.client_id:
        return patient.client

    from apps.crm.selectors import find_client_by_email
    from django.apps import apps as django_apps

    Client = django_apps.get_model('crm', 'Client')

    client = None
    if patient.email:
        client = find_client_by_email(patient.email, company=patient.company)
    if client is None:
        client = Client.objects.create(
            company=patient.company,
            nom=patient.nom,
            prenom=patient.prenom or None,
            email=patient.email or None,
            telephone=patient.telephone or None,
            adresse=patient.adresse or None,
            cin=patient.cin or None,
        )
    patient.client = client
    patient.save(update_fields=['client'])
    return client


def verifier_chevauchement_rdv(
        *, company, praticien, salle, date_heure_debut, duree_min,
        exclude_id=None):
    """NTSAN2/NTSAN4 — garde applicative de non-double-réservation.

    Refuse un `RendezVous` qui chevaucherait un autre RDV actif (statut !=
    annulé) sur le MÊME praticien OU la MÊME salle (si une salle est
    demandée). Renvoie un message FR de blocage, ou ``None`` si le créneau
    est libre. Les durées variant par RDV, le chevauchement est calculé en
    Python (pas une contrainte DB) : ``debut < autre_fin ET fin > autre_debut``.
    """
    from datetime import timedelta

    from .models import RendezVous

    fin = date_heure_debut + timedelta(minutes=duree_min)

    qs = RendezVous.objects.filter(company=company).exclude(
        statut=RendezVous.Statut.ANNULE)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    def _chevauche(autre):
        autre_fin = autre.date_heure_debut + timedelta(minutes=autre.duree_min)
        return date_heure_debut < autre_fin and fin > autre.date_heure_debut

    if praticien is not None:
        for autre in qs.filter(praticien=praticien):
            if _chevauche(autre):
                return (
                    "Ce praticien a déjà un rendez-vous sur ce créneau.")

    if salle is not None:
        for autre in qs.filter(salle=salle):
            if _chevauche(autre):
                return "Cette salle est déjà réservée sur ce créneau."

    return None


def cloturer_admission(admission, *, date_sortie=None):
    """NTSAN6 — clôture une admission (``en_cours`` → ``cloturee``).

    Garde (critère d'acceptation NTSAN6) : une admission ne peut être
    clôturée que si tous ses actes réalisés rattachés sont facturés
    (``facture_sante_id`` posé, NTSAN13) ou explicitement marqués
    non-facturables (``facturable=False``, NTSAN10). La partie « facturé »
    est complétée dans la même passe que NTSAN13 (``FactureSante`` pas
    encore posé à ce stade) — ici, seule la partie « non-facturable » est
    vérifiée : un acte facturable ET pas encore rattaché à une facture
    bloque la clôture.
    """
    from django.utils import timezone

    from .models import Admission

    if admission.statut == Admission.Statut.CLOTUREE:
        raise ValueError('Cette admission est déjà clôturée.')

    actes_bloquants = admission.actes_realises.filter(facturable=True)
    if actes_bloquants.exists():
        raise ValueError(
            "Impossible de clôturer : des actes réalisés ne sont ni "
            "facturés ni marqués non-facturables.")

    admission.statut = Admission.Statut.CLOTUREE
    admission.date_sortie = date_sortie or timezone.now()
    admission.save(update_fields=['statut', 'date_sortie'])
    return admission


def realiser_acte(
        *, admission, patient, praticien, acte, date_realisation,
        quantite=1, facturable=True):
    """NTSAN10 — enregistre un acte réalisé, tarif SNAPSHOTTÉ à la
    réalisation via ``selectors.tarif_applicable`` (convention du patient si
    connue, sinon ``tarif_base_ttc``). Le tarif appliqué ne change JAMAIS
    rétroactivement si ``GrilleTarifaire`` évolue ensuite."""
    from .models import ActeRealise
    from .selectors import tarif_applicable

    tarif = tarif_applicable(acte, getattr(patient, 'convention', None))

    return ActeRealise.objects.create(
        company=admission.company,
        admission=admission,
        patient=patient,
        praticien=praticien,
        acte=acte,
        date_realisation=date_realisation,
        quantite=quantite,
        tarif_applique_ttc=tarif['tarif_ttc'],
        facturable=facturable,
    )


def reste_a_charge_total(acte_realise):
    """NTSAN12 — vrai si cet acte doit basculer en reste-à-charge patient
    total : sa prise en charge (si posée) est refusée, expirée, ou dont la
    ``date_expiration`` est dépassée."""
    from datetime import date as _date

    pec = acte_realise.prise_en_charge
    if pec is None:
        return False
    from .models import PriseEnCharge
    if pec.statut in (PriseEnCharge.Statut.REFUSEE, PriseEnCharge.Statut.EXPIREE):
        return True
    if pec.date_expiration and pec.date_expiration < _date.today():
        return True
    return False


def verifier_prise_en_charge(prise_en_charge, *, user=None):
    """NTSAN12 — à appeler quand une `PriseEnCharge` bascule refusee/expiree :
    journalise (chatter + audit, `records.Activity` via `apps.audit.
    recorder.record_field_change`) le basculement en reste-à-charge patient
    total de chaque `ActeRealise` rattaché. Ne modifie AUCUN champ de
    l'acte : le calcul réel du reste-à-charge se fait au moment de la
    facturation (NTSAN13, via `reste_a_charge_total`) — ceci ne fait que
    tracer l'événement, une seule fois par acte concerné."""
    if prise_en_charge.statut not in (
            prise_en_charge.Statut.REFUSEE, prise_en_charge.Statut.EXPIREE):
        return []

    from apps.audit import recorder

    touches = []
    for acte_realise in prise_en_charge.actes_realises.all():
        recorder.record_field_change(
            acte_realise, 'prise_en_charge', 'accordee',
            prise_en_charge.get_statut_display(),
            user=user, field_label='Prise en charge',
            detail=(
                f'Prise en charge {prise_en_charge.get_statut_display().lower()} '
                '— acte basculé en reste-à-charge patient total.'),
        )
        touches.append(acte_realise)
    return touches
