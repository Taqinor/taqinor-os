"""Mixins de scoping tenant partagés (vues ET sérialiseurs).

``TenantMixin`` scope les QUERYSETS d'une vue ; ``SameCompanyFKSerializerMixin``
scope les FK ÉCRITES par un sérialiseur — deux moitiés du même contrat, d'où
leur cohabitation ici (AUD601).
"""
from rest_framework import serializers


class SameCompanyFKSerializerMixin:
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


class TenantMixin:
    """
    Filters querysets to the current user's company.
    Superusers WITH a company are scoped to that company (ERP usage).
    Superusers WITHOUT a company see all data (platform-level admin).
    """
    def get_queryset(self):
        return company_qs(super().get_queryset(), self.request.user)

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
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
