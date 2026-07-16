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
