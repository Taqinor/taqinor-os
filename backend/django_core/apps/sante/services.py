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
