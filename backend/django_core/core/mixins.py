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
    """

    #: Noms des champs FK à valider même-société (déclaratif : lu par la garde).
    same_company_fields = ()

    #: Message unique — ne jamais nommer l'objet voisin (ce serait l'oracle que
    #: la validation existe précisément pour fermer).
    MESSAGE_AUTRE_SOCIETE = (
        "Cette référence n'appartient pas à votre société.")

    def _company_id_courante(self):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return getattr(user, 'company_id', None)

    def _verifier_meme_societe(self, nom_champ, valeur):
        """Lève un 400 porté par ``nom_champ`` si ``valeur`` est d'ailleurs."""
        if valeur is None:
            return valeur
        company_id = self._company_id_courante()
        if company_id is None:
            return valeur
        cible = getattr(valeur, 'company_id', None)
        if cible is not None and cible != company_id:
            raise serializers.ValidationError(
                {nom_champ: self.MESSAGE_AUTRE_SOCIETE})
        return valeur

    def to_internal_value(self, data):
        """Le contrôle vit ici, PAS dans ``validate()``.

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


class TenantMixin:
    """
    Filters querysets to the current user's company.
    Superusers WITH a company are scoped to that company (ERP usage).
    Superusers WITHOUT a company see all data (platform-level admin).
    """
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            return qs.filter(company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

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
