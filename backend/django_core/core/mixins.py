"""Mixins de scoping tenant partagés (vues ET sérialiseurs).

``TenantMixin`` scope les QUERYSETS d'une vue ; ``SameCompanyFKSerializerMixin``
scope les FK ÉCRITES par un sérialiseur — deux moitiés du même contrat, d'où
leur cohabitation ici (AUD601).
"""
import copy
from contextlib import contextmanager

from django.db import transaction
from rest_framework import serializers

from core.serializer_mixins import NullableDottedSourcesMixin
from core.verrou_optimiste import (
    CHAMP_VERSION, CODE_CONFLIT_VERSION, MESSAGE_CONFLIT_VERSION, ConflitVersion,
    version_envoyee)


class SameCompanyFKSerializerMixin(NullableDottedSourcesMixin):
    """AUD601 — refuse toute FK cross-app pointant la ligne d'une AUTRE société.

    ``TenantMixin.get_queryset`` scope ce qu'un utilisateur LIT ; il ne dit rien
    de ce qu'il ÉCRIT. Une ``PrimaryKeyRelatedField`` générée par DRF depuis un
    ``ModelSerializer`` accepte par défaut n'importe quelle clé primaire de la
    table cible — donc, sur une FK cross-app (``stock.Produit``,
    ``records.Attachment``, ``crm.Client``…), la ligne d'une société VOISINE.
    Sur les surfaces AO ces valeurs ressortent dans un document remis à
    l'ACHETEUR (bordereau des prix, onglet équipements) : la fuite se lit chez
    le client final, pas dans un log.

    Le patron était déjà écrit à la main deux fois dans ``apps/cpq`` (
    ``ProduitEquivalentSerializer._meme_societe``,
    ``SeuilMargeFamilleSerializer.validate_categorie``) ; il est ici UNE fois,
    déclaratif, pour que la garde CI (``scripts/check_fk_scoping.py``) puisse le
    reconnaître mécaniquement sur un nouveau sérialiseur.

    Usage — déclarer les champs concernés, rien d'autre::

        class LigneBordereauSerializer(SameCompanyFKSerializerMixin,
                                       serializers.ModelSerializer):
            same_company_fields = ('produit',)

    Un superutilisateur PLATEFORME (sans société, cf. ``TenantMixin``) et un
    appel hors requête (services, seeds, tests unitaires du modèle) ne sont pas
    concernés : la garde n'a alors aucune société de référence et laisse passer,
    exactement comme le scoping de lecture.

    ACAL298 — un id d'une autre société reçoit la MÊME réponse qu'un id
    absent (« objet inexistant » de DRF) : le champ est borné dans
    ``get_fields`` ; aucun message propre ne distingue plus les deux cas.
    """

    #: Noms des champs FK à valider même-société (déclaratif : lu par la garde).
    same_company_fields = ()

    def _company_id_courante(self):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return getattr(user, 'company_id', None)

    def get_fields(self):
        """ACAL298 — chaque champ déclaré naît BORNÉ à la société de la requête.

        Le queryset du champ est filtré sur ``company_id`` de l'utilisateur
        (promotion sur place par ``core.serializers.scope_related_field``) :
        l'id d'une société voisine échoue alors à la RÉSOLUTION, avec l'erreur
        standard « objet inexistant » de DRF — octet-identique à celle d'un id
        qui n'existe pas. Avant, il était résolu puis refusé par un message
        PROPRE (« n'appartient pas à votre société ») : deux réponses
        différentes, donc un oracle d'existence inter-sociétés.

        Superutilisateur plateforme sans société et appel hors requête :
        ``request_company_id`` rend ``None`` et le queryset reste inchangé,
        exactement comme avant.
        """
        # Import local : ``core.serializers`` importe ``core.models`` ; le
        # mixin, lui, est importé par les sérialiseurs de toutes les apps.
        from core.serializers import scope_related_field

        fields = super().get_fields()
        for nom in self.same_company_fields:
            champ = fields.get(nom)
            if champ is not None:
                scope_related_field(champ)
        return fields

    def _verifier_meme_societe(self, nom_champ, valeur):
        """Filet : lève l'erreur « objet inexistant » du champ si ``valeur``
        est d'ailleurs (champ non promu par ``get_fields``, sous-classe
        métier). JAMAIS un message propre : la réponse doit rester celle d'un
        id absent (ACAL298)."""
        if valeur is None:
            return valeur
        company_id = self._company_id_courante()
        if company_id is None:
            return valeur
        cible = getattr(valeur, 'company_id', None)
        if cible is not None and cible != company_id:
            champ = self.fields.get(nom_champ)
            messages = getattr(champ, 'error_messages', None) or {}
            gabarit = messages.get(
                'does_not_exist',
                serializers.PrimaryKeyRelatedField.default_error_messages[
                    'does_not_exist'])
            raise serializers.ValidationError(
                {nom_champ: [str(gabarit).format(
                    pk_value=getattr(valeur, 'pk', valeur))]},
                code='does_not_exist')
        return valeur

    def to_internal_value(self, data):
        """Le filet vit ici, PAS dans ``validate()``.

        ``validate()`` est très souvent redéfini par le sérialiseur concret
        (règles métier) : accrocher la garde là l'aurait rendue silencieusement
        inopérante dès qu'une sous-classe oublie ``super().validate()`` — une
        fuite qui ne se voit sur aucun gate. ``to_internal_value`` est toujours
        traversé.
        """
        attrs = super().to_internal_value(data)
        for nom in self.same_company_fields:
            champ = self.fields.get(nom)
            cle = getattr(champ, 'source', None) or nom
            if cle in attrs:
                self._verifier_meme_societe(nom, attrs[cle])
        return attrs


def company_qs(qs, user):
    """QJR655 — LA règle de portée société d'un queryset (une seule copie).

    Un utilisateur rattaché voit sa société ; un superuser SANS société voit
    tout (acteur plateforme) ; tout autre utilisateur sans société ne voit
    rien. ``TenantMixin.get_queryset`` l'applique ; une vue qui n'en hérite pas
    (lecture seule, lecture ad hoc) l'appelle directement.
    """
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()


def _instantane(obj):
    """ACNC41 — valeurs des colonnes CHARGÉES à la lecture (copie des JSON)."""
    noms = {f.attname for f in obj._meta.concrete_fields}
    return {k: copy.deepcopy(v) if isinstance(v, (dict, list)) else v
            for k, v in obj.__dict__.items() if k in noms}


def _relire_non_ecrits(instance, champs):
    """ACNC41 — les colonnes chargées que la borne n'écrit PAS reprennent leur
    valeur en base AVANT ``pre_save`` : sans cela l'instance garde la valeur lue
    (périmée si un collègue a commité entre-temps) que les receveurs (journal
    d'audit, webhooks, notifications de transition) et la réponse prendraient pour
    une transition jamais écrite."""
    autres = {f.attname: f for f in instance._meta.concrete_fields
              if not f.primary_key and f.attname not in champs and f.attname in instance.__dict__}
    if not autres:
        return
    base = type(instance)._base_manager.filter(pk=instance.pk).values(*autres).first()
    for nom, valeur in (base or {}).items():
        champ = autres[nom]
        if champ.is_relation and instance.__dict__[nom] != valeur and champ.is_cached(instance):
            champ.delete_cached_value(instance)  # objet lié périmé : relu à la demande
        instance.__dict__[nom] = valeur


@contextmanager
def _ecriture_bornee(instance, lu):
    """ACNC41 — borne le ``save()`` NU de ``ModelSerializer.update`` (patron CRX25,
    ``apps/crm/views.py::_save_borne_aux_champs``) aux colonnes que CETTE requête a
    changées depuis sa lecture (sérialiseur, surcharge, ``save()`` du modèle —
    calculé dans ``save_base``, après les dérivations) + ``auto_now`` + ``company`` :
    une transition commitée entre ``get_object()`` et ``save()`` n'est plus
    réécrite. Borne vide ou lecture inconnue ⇒ aucune borne."""
    if lu is None:
        yield
        return
    original = instance.save_base

    def _save_base(*args, **kwargs):
        if kwargs.get('update_fields') is None and not instance._state.adding:
            champs = {f.attname for f in instance._meta.concrete_fields if not f.primary_key and (
                getattr(f, 'auto_now', False) or f.name == 'company' or (
                    f.attname in instance.__dict__ and (
                        f.attname not in lu or instance.__dict__[f.attname] != lu[f.attname]
                        or getattr(instance.__dict__[f.attname], '_committed', True) is False)))}
            if champs:
                kwargs['update_fields'] = frozenset(champs)
                _relire_non_ecrits(instance, champs)
        return original(*args, **kwargs)

    instance.save_base = _save_base
    try:
        yield
    finally:
        del instance.save_base


class TenantMixin:
    """
    Filters querysets to the current user's company.
    Superusers WITH a company are scoped to that company (ERP usage).
    Superusers WITHOUT a company see all data (platform-level admin).
    """
    def get_queryset(self):
        return company_qs(super().get_queryset(), self.request.user)

    def initial(self, request, *args, **kwargs):
        # ENF2 (C6) — unicité PAR SOCIÉTÉ contrôlée AVANT l'écriture : DRF ne
        # peut pas générer ce validateur lui-même (``company`` n'est jamais un
        # champ du serializer). Un doublon répond 409 ``unique_conflict`` au
        # lieu d'un IntegrityError 500. Voir ``core.unicite``.
        # Branché sur l'INSTANCE, pour la requête d'écriture en cours
        # seulement : surcharger ``get_serializer`` au niveau de la classe
        # ferait appeler à drf-spectacular le chemin complet (contexte de
        # requête réel) au lieu de ``get_serializer_class()``.
        super().initial(request, *args, **kwargs)
        origine = getattr(self, 'get_serializer', None)
        if origine is None or request.method not in ('POST', 'PUT', 'PATCH'):
            return
        from core.unicite import brancher_unicite_societe

        def get_serializer(*a, **kw):
            serializer = origine(*a, **kw)
            brancher_unicite_societe(serializer, request)
            return serializer

        self.get_serializer = get_serializer

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def get_object(self):
        obj = super().get_object()
        if self.request.method in ('PUT', 'PATCH'):  # ACNC41 — lecture de référence
            obj._acnc41_lu = _instantane(obj)
        return obj

    def perform_update(self, serializer):
        with _ecriture_bornee(serializer.instance, getattr(serializer.instance, '_acnc41_lu', None)):
            self._perform_update_tenant(serializer)

    def _perform_update_tenant(self, serializer):
        # Un utilisateur tenant : la société est forcée côté serveur (jamais lue
        # du corps) — identique à avant, et elle vaut déjà celle de l'instance
        # scopée par ``get_queryset``. Un superuser SANS société (acteur
        # plateforme supporté, cf. docstring) NE doit PAS voir ``company=None``
        # écrasé sur la ligne éditée : sur un modèle à ``company`` nullable la
        # ligne se détacherait de son tenant (elle disparaîtrait des listes
        # scopées), et sur un modèle NON-NULL cela lèverait IntegrityError (500).
        # On préserve alors la société PROPRE de l'objet.
        if self.request.user.company_id:
            serializer.save(company=self.request.user.company)
        else:
            serializer.save()


class VerrouOptimisteSerializerMixin:
    """NTPLT17 — verrou optimiste OPT-IN (voir ``core.verrou_optimiste``).

    À placer AVANT ``serializers.ModelSerializer`` dans les bases.

    N'agit qu'en mise à jour (``self.instance`` posé) et seulement si le corps
    porte ``lock_version`` ; ne modifie ni les champs ni la validation des
    sous-classes."""

    def _version_en_base(self, verrouiller=False):
        modele = type(self.instance)
        qs = modele._base_manager.filter(pk=self.instance.pk)
        if verrouiller:
            qs = qs.select_for_update()
        return qs.values_list(CHAMP_VERSION, flat=True).first()

    def _conflit(self, actuelle):
        frais = type(self.instance)._base_manager.get(pk=self.instance.pk)
        return ConflitVersion({
            'detail': MESSAGE_CONFLIT_VERSION,
            'code': CODE_CONFLIT_VERSION,
            CHAMP_VERSION: actuelle,
            'actuel': type(self)(frais, context=self.context).data,
        })

    def _verifier_version(self, verrouiller=False):
        """``None`` si rien n'est demandé ; sinon la version en base (lève
        ``ConflitVersion`` si elle diffère de celle envoyée)."""
        if self.instance is None or getattr(self.instance, 'pk', None) is None:
            return None
        envoyee = version_envoyee(getattr(self, 'initial_data', None))
        if envoyee is None:
            return None
        actuelle = self._version_en_base(verrouiller=verrouiller)
        if actuelle is not None and actuelle != envoyee:
            raise self._conflit(actuelle)
        return actuelle

    def is_valid(self, *args, **kwargs):
        valide = super().is_valid(*args, **kwargs)
        if valide:
            self._verifier_version()
        return valide

    def save(self, **kwargs):
        if version_envoyee(getattr(self, 'initial_data', None)) is None \
                or self.instance is None:
            return super().save(**kwargs)
        with transaction.atomic():
            actuelle = self._verifier_version(verrouiller=True)
            if actuelle is not None:
                # La version d'où l'on repart est celle de la base (verrouillée),
                # jamais celle d'une instance chargée plus tôt.
                setattr(self.instance, CHAMP_VERSION, actuelle)
            return super().save(**kwargs)
