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
l'historique du modèle — et ce service lui passe EXPLICITEMENT le NOUVEAU
rattachement fourni par l'appelant (ACAL184 : le client est celui du lead ;
un lead qui a déjà un calepinage ouvert est refusé, D-ACAL-12). Un calepinage exige au moins un lead ou
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


class RattachementDuModeleIntrouvable(ModeleInvalide):
    """Le lead ou le client de la copie n'existe pas dans cette société : 404
    (lu par ``depuis-modele`` ; les autres appelants gardent ``ModeleInvalide``)."""

    statut_http = 404


class ModeleEnConflit(ModeleInvalide):
    """Refus d'ÉTAT que le schéma du corps ne peut pas dire (modèle archivé ou
    non marqué, couple lead / client qui se contredit, lead sans repère toit) :
    409 (lu par ``depuis-modele``)."""

    statut_http = 409


class DemarquageEnConflit(ModeleEnConflit):
    """ACON5 (D-ACAL-12) — retirer le drapeau rendrait ce calepinage un
    SECOND ouvert de son lead : 409 nommant l'ouvert (``corps``, contrat
    ``calepinage_creation_conflit.json``)."""

    def __init__(self, existant, user=None):
        from .creation import _message_deja_ouvert, corps_conflit

        super().__init__(_message_deja_ouvert(existant), champ='lead')
        self.corps = corps_conflit(existant, user)


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
    from django.db import transaction

    from ..selectors import calepinage_ouvert_du_lead
    from .archivage import est_archive
    from .creation import _verrou_creation

    ct = ContentType.objects.get_for_model(type(calepinage))
    marque = TaggedItem.objects.filter(
        tag=tag, content_type=ct, object_id=calepinage.pk)
    with transaction.atomic(), _verrou_creation(calepinage.company_id,
                                                calepinage.lead_id):
        # ACON5 — relu SOUS le verrou du lead : le modèle (encore marqué)
        # est exclu de « l'ouvert » ; un autre ouvert ⇒ refus nommé.
        if (calepinage.lead_id and marque.exists()
                and not est_archive(calepinage)):
            existant = calepinage_ouvert_du_lead(calepinage.company,
                                                 calepinage.lead_id)
            if existant is not None:
                raise DemarquageEnConflit(existant, user)
        retires, _ = marque.delete()
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
    # ACAL118 — un modèle ARCHIVÉ sort de la bibliothèque.
    from ..selectors import calepinages_actifs

    return (calepinages_actifs(company)
            .filter(pk__in=list(ids))
            .order_by('-created_at', '-id'))


def creer_depuis_modele(modele, *, user=None, lead_id=None, client_id=None,
                        titre='', regler_conception=None):
    """Crée un NOUVEAU calepinage depuis ``modele`` — jamais un troisième
    chemin de copie (appelle ``services.variantes.dupliquer``, CAL14), puis
    détache tout ce qui est commercial.

    ``regler_conception`` (facultatif) : appliqué à la conception préparée
    AVANT la copie (jeu de réglages de ``creation.demarrer_depuis_modele``) —
    la version « Conception d'origine » est donc le document courant.

    Raises:
        ModeleInvalide: modèle absent/non marqué, ou aucun nouveau
            rattachement (lead/client) fourni.
    """
    from .variantes import dupliquer, preparer_pour_cible

    if modele is None or not getattr(modele, 'pk', None):
        raise ModeleInvalide('Modèle introuvable.', champ='modele')
    from .archivage import est_archive

    if est_archive(modele):
        # ACAL118 — un modèle archivé ne sert plus de départ.
        raise ModeleEnConflit(
            'Ce modèle est archivé : restaurez-le avant de vous en servir.',
            champ='modele')
    if not est_modele(modele):
        raise ModeleEnConflit(
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
            raise RattachementDuModeleIntrouvable(
                'Client introuvable dans cette société.', champ='client')
    if lead_id:
        from apps.crm.selectors import repere_toit

        from .creation import lead_en_portee

        lead = lead_en_portee(modele.company, lead_id, user)  # ACON3
        if lead is None:
            raise RattachementDuModeleIntrouvable(
                'Lead introuvable dans cette société.', champ='lead')
        # ACAL184 — le client de la copie est CELUI du lead : un couple
        # lead/client qui se contredit est refusé en nommant ``client`` (UNE
        # règle, partagée avec Dupliquer).
        from .variantes import MESSAGE_CLIENT_PAS_CELUI_DU_LEAD

        client_du_lead = getattr(lead, 'client_id', None)
        if client_id and client_du_lead and int(client_id) != client_du_lead:
            raise ModeleEnConflit(MESSAGE_CLIENT_PAS_CELUI_DU_LEAD,
                                  champ='client')
        client_id = client_du_lead or client_id
        # ACAL117 (D-ACAL-15) — le modèle emporte ses réglages et son
        # implantation RELATIVE : la conception est translatée sur le repère
        # toit du lead cible ; sans repère, refus nommé, rien n'est créé.
        pin, _source, _contour = repere_toit(lead)
        if pin is None:
            raise ModeleEnConflit(
                "Le lead n'a pas de repère toit (GPS ou point de toit) : "
                "placez-le d'abord", champ='lead')
    else:
        pin = None

    def preparer(source):
        # D-ACAL-15 / ACON11 — LA règle partagée avec Dupliquer.
        return preparer_pour_cible(source, pin)

    # ACAL187/ACAL184 — la CIBLE est passée explicitement à ``dupliquer`` :
    # la copie naît sur ce lead/client (jamais sur le rattachement du
    # modèle), et un lead qui a déjà un calepinage OUVERT est refusé
    # (``DuplicationEnConflit``, 409). ``dupliquer`` journalise la création.
    conception = preparer(modele.roof_layout)
    if regler_conception is not None:
        conception = regler_conception(conception)
    return dupliquer(modele, user=user, titre=titre,
                     roof_layout=conception,
                     preparer_document=preparer,
                     lead_id=lead_id or None, client_id=client_id or None)
