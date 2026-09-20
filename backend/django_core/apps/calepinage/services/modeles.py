"""CAL199 — marquer un calepinage comme MODÈLE réutilisable.

AUCUN TROISIÈME CHEMIN DE DUPLICATION
---------------------------------------
La copie EST déjà le service unique ``services.variantes.dupliquer`` (CAL14
— géométrie + variantes, sans devis ni AO) et l'archivage est CAL208 : ce
module n'ajoute ni un second moteur de copie, ni un second modèle de
suppression.

LE DRAPEAU « MODÈLE », SANS MIGRATION
----------------------------------------
Aucun champ n'est ajouté à ``Calepinage`` : le drapeau est porté par la
primitive plateforme ``records.Tag``/``TaggedItem`` (FG9 — vocabulaire de
tags partagé, ``calepinage.calepinage`` déjà déclaré cible dans
``platform.py``). Un tag SYSTÈME par société (``NOM_TAG_MODELE``), posé et
retiré via ``TaggedItem`` — réversible par construction, et JOURNALISÉ
(CAL26) à chaque bascule.

CRÉER DEPUIS UN MODÈLE
-------------------------
``creer_depuis_modele`` appelle ``dupliquer`` (CAL14) puis DÉTACHE tout ce
qui est commercial : ``dupliquer`` ne recopie déjà ni le devis ni l'image ni
l'historique du modèle — seuls ``lead_id``/``client_id`` sont recopiés par
défaut (duplication ORDINAIRE), donc ce service les ÉCRASE avec un NOUVEAU
rattachement fourni par l'appelant. Un calepinage exige au moins un lead ou
un client (contrainte base) : partir d'un modèle SANS fournir ce nouveau
rattachement est donc refusé, en nommant le champ — jamais une réutilisation
silencieuse du lead/client du modèle.
"""
from __future__ import annotations

#: Nom du tag SYSTÈME (FG9) qui porte le drapeau « modèle réutilisable ».
NOM_TAG_MODELE = 'calepinage:modele'

__all__ = [
    'ModeleInvalide', 'NOM_TAG_MODELE', 'est_modele', 'marquer_modele',
    'demarquer_modele', 'creer_depuis_modele',
]


class ModeleInvalide(ValueError):
    """Erreur métier, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _tag_modele(company, *, creer=False):
    from apps.records.models import Tag

    if company is None:
        return None
    if creer:
        tag, _ = Tag.objects.get_or_create(company=company, nom=NOM_TAG_MODELE)
        return tag
    return Tag.objects.filter(company=company, nom=NOM_TAG_MODELE).first()


def est_modele(calepinage):
    """``True`` si ``calepinage`` porte le drapeau « modèle » — lecture pure."""
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import TaggedItem

    if calepinage is None or not getattr(calepinage, 'pk', None):
        return False
    tag = _tag_modele(getattr(calepinage, 'company', None))
    if tag is None:
        return False
    ct = ContentType.objects.get_for_model(type(calepinage))
    return TaggedItem.objects.filter(
        tag=tag, content_type=ct, object_id=calepinage.pk).exists()


def marquer_modele(calepinage, *, user=None):
    """Pose le drapeau « modèle » — idempotent, journalisé (CAL26)."""
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import TaggedItem

    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise ModeleInvalide(
            "Impossible de marquer un calepinage non enregistré comme "
            'modèle.', champ='calepinage')
    tag = _tag_modele(calepinage.company, creer=True)
    ct = ContentType.objects.get_for_model(type(calepinage))
    _, cree = TaggedItem.objects.get_or_create(
        tag=tag, content_type=ct, object_id=calepinage.pk)
    if cree:
        from .journal import noter

        noter(calepinage, 'Marqué comme modèle réutilisable.', user=user)
    return True


def demarquer_modele(calepinage, *, user=None):
    """Retire le drapeau « modèle » — idempotent, journalisé (CAL26)."""
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import TaggedItem

    if calepinage is None or not getattr(calepinage, 'pk', None):
        return False
    tag = _tag_modele(getattr(calepinage, 'company', None))
    if tag is None:
        return False
    ct = ContentType.objects.get_for_model(type(calepinage))
    retires, _ = TaggedItem.objects.filter(
        tag=tag, content_type=ct, object_id=calepinage.pk).delete()
    if retires:
        from .journal import noter

        noter(calepinage, 'Retiré des modèles réutilisables.', user=user)
    return bool(retires)


def calepinages_modeles(company):
    """Les calepinages marqués MODÈLE de ``company`` — lecture pure, bornée
    société. ``None`` rend un queryset VIDE."""
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import TaggedItem

    from ..models import Calepinage

    if company is None:
        return Calepinage.objects.none()
    tag = _tag_modele(company)
    if tag is None:
        return Calepinage.objects.none()
    ct = ContentType.objects.get_for_model(Calepinage)
    ids = TaggedItem.objects.filter(
        tag=tag, content_type=ct).values_list('object_id', flat=True)
    return (Calepinage.objects
            .filter(company=company, pk__in=list(ids))
            .order_by('-created_at', '-id'))


def creer_depuis_modele(modele, *, user=None, lead_id=None, client_id=None,
                        titre=''):
    """Crée un NOUVEAU calepinage depuis ``modele`` — jamais un troisième
    chemin de copie (appelle ``services.variantes.dupliquer``, CAL14), puis
    détache tout ce qui est commercial.

    Raises:
        ModeleInvalide: modèle absent/non marqué, ou aucun nouveau
            rattachement (lead/client) fourni.
    """
    from .journal import journaliser_creation
    from .variantes import dupliquer

    if modele is None or not getattr(modele, 'pk', None):
        raise ModeleInvalide('Modèle introuvable.', champ='modele')
    if not est_modele(modele):
        raise ModeleInvalide(
            "Ce calepinage n'est pas marqué comme modèle réutilisable.",
            champ='modele')
    if not lead_id and not client_id:
        raise ModeleInvalide(
            "Créer un projet depuis un modèle exige un nouveau lead ou "
            'client : le rattachement du modèle n\'est jamais recopié.',
            champ='client')

    if client_id:
        from apps.crm.selectors import get_company_client

        if get_company_client(modele.company, client_id) is None:
            raise ModeleInvalide('Client introuvable dans cette société.',
                                 champ='client')
    if lead_id:
        from apps.crm.selectors import get_company_lead

        if get_company_lead(modele.company, lead_id) is None:
            raise ModeleInvalide('Lead introuvable dans cette société.',
                                 champ='client')

    copie = dupliquer(modele, user=user, titre=titre)
    copie.lead_id = lead_id or None
    copie.client_id = client_id or None
    copie.full_clean(exclude=['company'])
    copie.save(update_fields=['lead_id', 'client'])

    journaliser_creation(copie, user=user)
    return copie
