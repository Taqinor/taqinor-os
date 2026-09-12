"""Écritures / orchestration du module ``apps.datarooms`` (groupe NTDOC, P2).

La société est TOUJOURS fournie par l'appelant (résolue côté serveur depuis
``request.user.company``) — jamais lue d'un corps de requête.
"""
from django.db import transaction

from .models import SalleDeDonnees, SalleDeDonneesDocument


class SalleFermee(ValueError):
    """Action impossible : la salle est fermée (message français)."""


@transaction.atomic
def ajouter_documents(salle, documents, *, visible=True):
    """NTDOC11 — Ajoute des documents GED à une salle (idempotent).

    ``documents`` est un itérable d'instances ``ged.Document`` DÉJÀ résolues et
    vérifiées côté appelant comme appartenant à la société de la salle (la vue
    le garantit ; ce service ne fait jamais confiance à un id brut de requête).

    Un document déjà présent n'est PAS dupliqué (contrainte d'unicité + ``
    get_or_create``) et son ordre existant est conservé. Renvoie la liste des
    lignes créées."""
    if not salle.est_ouverte:
        raise SalleFermee("Cette salle est fermée : son contenu est figé.")
    prochain = (SalleDeDonneesDocument.objects
                .filter(salle=salle)
                .order_by('-ordre')
                .values_list('ordre', flat=True)
                .first() or 0)
    creees = []
    for document in documents:
        prochain += 1
        ligne, cree = SalleDeDonneesDocument.objects.get_or_create(
            salle=salle, document=document,
            defaults={'company': salle.company, 'ordre': prochain,
                      'visible': visible})
        if cree:
            creees.append(ligne)
        else:
            prochain -= 1
    return creees


@transaction.atomic
def retirer_document(salle, document):
    """NTDOC11 — Retire un document de la salle SANS jamais toucher à la GED.

    Seule la ligne d'appartenance disparaît : le ``ged.Document`` reste intact,
    à sa place, avec ses versions. Renvoie True si une ligne a été retirée."""
    if not salle.est_ouverte:
        raise SalleFermee("Cette salle est fermée : son contenu est figé.")
    supprimees, _ = SalleDeDonneesDocument.objects.filter(
        salle=salle, document=document).delete()
    return bool(supprimees)


def creer_salle(*, company, nom, created_by=None, description='',
                deal_type='', dossier_source=None, expires_at=None):
    """NTDOC11 — Crée une salle de données (société posée côté serveur)."""
    return SalleDeDonnees.objects.create(
        company=company, nom=nom, description=description,
        deal_type=deal_type, dossier_source=dossier_source,
        expires_at=expires_at, created_by=created_by)
