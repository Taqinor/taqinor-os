"""Sérialiseurs du module « calepinage » — CAL16.

RAPPEL multi-tenant : ``company`` n'est JAMAIS exposée en écriture — elle est
toujours forcée côté serveur (``CompanyScopedModelViewSet.perform_create``).
Un ``company`` envoyé dans le corps est donc ignoré, pas « refusé » : il
n'existe simplement pas pour ce sérialiseur.

LE RATTACHEMENT : AU MOINS UN, ET COHÉRENT (ACAL179)
---------------------------------------------------
La base garantit qu'un calepinage a un lead et/ou un client (``CheckConstraint``
``calepinage_lead_ou_client``, OU INCLUSIF), mais une contrainte de base rend
une ``IntegrityError`` — un « non enregistré » générique côté écran. Le
sérialiseur refuse donc AVANT, en français, en NOMMANT le champ fautif (règle
fondateur « erreurs → le champ fautif »). Lead ET client à la fois sont
ADMIS — c'est ce que posent depuis-lead, la création pour un devis,
``lier_devis`` et la duplication — à une condition : le client est CELUI DU
LEAD (un calepinage retrouvé depuis deux fiches doit parler du même client).
La règle n'agit que sur les champs ÉCRITS : renommer (``{titre}``) ou confier
(``{responsable}``) un calepinage lead+client passe toujours.

PATCH STRICT (ACAL179) : une clé en lecture seule (``nom``, dérivé du titre ;
``devis``, écrit par ``lier_devis`` seul…) ou inconnue dans le corps d'une
modification est REFUSÉE en la nommant — jamais un 200 silencieux qui
n'écrit rien. ``company`` (et ``id``) restent ignorés, jamais lus : la société
est forcée côté serveur.

Les lectures cross-app passent par les ``selectors.py`` des apps cibles
(``apps.crm.selectors``) — jamais un import de leurs modèles.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.mixins import SameCompanyFKSerializerMixin

from .models import Calepinage, CalepinageVariante
from .services.presentation import image_apercu, reference_calepinage


def _lead_apercu(lead):
    """``{id, nom, ville}`` du lead déjà résolu, ou ``None`` — même forme que
    ``views/calepinages.py::_lead`` (le détail)."""
    if lead is None:
        return None
    nom = ' '.join(p for p in [getattr(lead, 'nom', ''),
                               getattr(lead, 'prenom', '') or ''] if p).strip()
    ville = (getattr(lead, 'ville', '') or '').strip() or None
    return {'id': lead.pk, 'nom': nom or f'Lead #{lead.pk}', 'ville': ville}


def peremption_du_calepinage(devis, calepinage):
    """ACAL47 (C-ACAL-112) — ``{layout_stale, layout_nb_panneaux}`` du badge du
    MODULE, lus sur LE sélecteur ventes ``peremption_layout_devis`` AVEC le
    calepinage (jamais une seconde règle) :

    * ``layout_stale`` — périmé si la règle des comptes le dit OU si la
      conception imprimée du calepinage a divergé du devis
      (``conception_divergente``, empreintes) : un calepinage passé de 12 à
      16 panneaux sans resynchronisation n'est plus « à jour » ;
    * ``layout_nb_panneaux`` — le compte du DOCUMENT DU CALEPINAGE (ce que
      l'écran du module montre), pas celui de la copie du devis ; repli sur
      celui du devis seulement quand le calepinage n'en porte aucun.

    Clés et forme INCHANGÉES (seules les valeurs) ; le devis est déjà borné
    société par l'appelant.
    """
    from apps.ventes.selectors import peremption_layout_devis

    brut = peremption_layout_devis(devis, calepinage=calepinage)
    stale_comptes = brut.get('layout_stale')
    divergente = brut.get('conception_divergente')
    if stale_comptes is None and divergente is None:
        layout_stale = None
    else:
        layout_stale = bool(stale_comptes) or bool(divergente)
    nb_calepinage = brut.get('calepinage_nb_panneaux')
    document = getattr(calepinage, 'roof_layout', None)
    if not (isinstance(document, dict) and document):
        # Aucun document sur le calepinage : rien à compter de son côté.
        nb_calepinage = None
    return {
        'layout_stale': layout_stale,
        'layout_nb_panneaux': (nb_calepinage if nb_calepinage is not None
                               else brut.get('layout_nb_panneaux')),
    }


class _CalepinageListSerializer(serializers.ListSerializer):
    """CALX407 — la PAGE précharge tous ses leads en UNE requête.

    Le cache mémo posé par ``CalepinageSerializer._lead_de_la_societe`` (sur
    ``self``, le ``child``) suffit déjà quand plusieurs lignes de la page
    PARTAGENT un même lead — le cas mesuré par CALX390. Il ne suffit PAS
    quand la page porte ``N`` calepinages sur ``N`` leads DIFFÉRENTS (le cas
    réel) : sans préchargement, chaque lead reste une première lecture, donc
    ``N`` requêtes (plus ``N`` de plus pour le repli ``.owner``).

    ``ListSerializer.to_representation`` (DRF) délègue à ``self.child`` —
    CE MÊME enfant pour toute la page — donc on résout ICI, AVANT de laisser
    DRF itérer, la liste ENTIÈRE des ``lead_id`` distincts de la page via
    ``apps.crm.selectors.get_company_leads_by_ids`` (UNE requête,
    ``select_related('owner')`` inclus), et on SEED le dict mémo du child
    avec le résultat. L'itération ligne-par-ligne
    (``CalepinageSerializer._lead_de_la_societe``) ne trouve plus alors que
    des cache-hits, jamais une lecture de plus — le comportement PAR LIGNE
    (garde même-société, repli ``responsable``) reste rigoureusement
    identique, seule la SOURCE du lead change (déjà en mémoire, jamais un
    second calcul).
    """

    def to_representation(self, data):
        lignes = list(data.all() if hasattr(data, 'all') else data)
        request = self.child.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None:
            ids = {lid for lid in
                   (getattr(ligne, 'lead_id', None) for ligne in lignes)
                   if lid}
            if ids:
                from apps.crm.selectors import get_company_leads_by_ids

                cache = self.child.__dict__.setdefault(
                    '_calx407_cache_leads', {})
                for lead_id, lead in get_company_leads_by_ids(
                        company, ids).items():
                    cache[(company.pk, lead_id)] = lead
        return [self.child.to_representation(ligne) for ligne in lignes]


class CalepinageSerializer(SameCompanyFKSerializerMixin,
                           serializers.ModelSerializer):
    """Le calepinage en liste et en écriture (le DÉTAIL agrégé est CAL17).

    ``lead`` est un identifiant OPAQUE (``PositiveIntegerField``) : il est
    exposé sous le nom ``lead`` côté API — celui que l'écran emploie — et
    VALIDÉ contre ``apps.crm.selectors.get_company_lead`` pour qu'un lead
    d'une autre société soit refusé comme « introuvable » (jamais un 403 qui
    confirmerait son existence).
    """

    lead = serializers.IntegerField(source='lead_id', required=False,
                                    allow_null=True)
    statut_libelle = serializers.CharField(source='get_statut_display',
                                           read_only=True)
    #: CAL189 — le calepinage décrit-il encore ce que le devis vend ?
    layout_stale = serializers.SerializerMethodField()
    layout_nb_panneaux = serializers.SerializerMethodField()
    #: CALX406 — le NOM du responsable, pour la colonne de la liste (le champ
    #: ``responsable`` lui-même reste l'identifiant, en lecture-écriture).
    responsable_nom = serializers.SerializerMethodField()
    #: ACAL196 — ce que la LISTE affiche, DÉRIVÉ et en lecture seule : la
    #: référence (la même que le détail), l'aperçu (chemin RELATIF du proxy
    #: Django, aucune signature par ligne), l'instant de dernière
    #: modification, et l'aperçu du client rattaché (le champ ``client`` reste
    #: l'identifiant, clé d'écriture inchangée).
    reference = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    modifie_le = serializers.DateTimeField(source='updated_at',
                                           read_only=True)
    client_apercu = serializers.SerializerMethodField()

    #: AUD601 — une FK cross-app ne pointe jamais la ligne d'une autre société.
    #: CALX406 — le responsable non plus : un compte d'une société voisine est
    #: refusé sous le champ ``responsable``, sans jamais être nommé.
    same_company_fields = ('client', 'devis', 'responsable')

    class Meta:
        model = Calepinage
        #: CALX407 — la LISTE (``many=True``) précharge tous ses leads en
        #: une requête (voir ``_CalepinageListSerializer``) ; le détail et
        #: l'écriture (``many=False``) ne passent jamais par cette classe.
        list_serializer_class = _CalepinageListSerializer
        fields = [
            'id', 'titre', 'statut', 'statut_libelle',
            'lead', 'client', 'devis',
            'layout_hash', 'roof_image', 'version_moteur',
            'layout_stale', 'layout_nb_panneaux',
            'cree_par', 'created_at', 'updated_at',
            'responsable', 'responsable_nom',  # CALX406
            'reference', 'image', 'modifie_le', 'client_apercu',  # ACAL196
            'contraintes_site',  # CIQ136
        ]
        #: ACAL33 — ``devis`` est LU, jamais écrit par le CRUD : le seul
        #: écrivain est ``services.liens.lier_devis`` (refus nommés, journal,
        #: unicité « un calepinage par devis »).
        read_only_fields = [
            'layout_hash', 'roof_image', 'version_moteur', 'cree_par',
            'created_at', 'updated_at', 'devis',
        ]

    # YAPIC6 — la nature est DÉCLARÉE (même patron que le jumeau côté ventes,
    # `apps/ventes/serializers.py`) : sans cela drf-spectacular ne sait pas
    # typer un SerializerMethodField et publie un contrat muet.
    def validate_contraintes_site(self, value):
        """CIQ136 — normalisées ; une valeur sans source → 400 FR."""
        from .services.degagements import (
            ContraintesSiteInvalides, normaliser_contraintes_site,
        )

        try:
            return normaliser_contraintes_site(value)
        except ContraintesSiteInvalides as refus:
            raise serializers.ValidationError(refus.message)

    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_layout_stale(self, calepinage):
        """``True``/``False`` d'après le DEVIS lié — ``None`` sans devis.

        SANS devis, la péremption est INCONNUE, pas fausse : il n'y a rien à
        quoi comparer la conception. Publier ``False`` ferait afficher « à
        jour » sur un calepinage dont personne ne peut le dire (l'écran affiche
        « — », CAL188).
        """
        return self._peremption(calepinage)['layout_stale']

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_layout_nb_panneaux(self, calepinage):
        return self._peremption(calepinage)['layout_nb_panneaux']

    @extend_schema_field(serializers.CharField())
    def get_reference(self, calepinage):
        """ACAL196 — « CAL-AAMM-NNNN », la même que le détail."""
        return reference_calepinage(calepinage)

    @extend_schema_field(serializers.DictField())
    def get_image(self, calepinage):
        """ACAL196 — ``{url, genere_le, expire_le}`` ; chemin relatif du
        proxy Django, trois ``null`` sans rendu enregistré."""
        return image_apercu(calepinage)

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_client_apercu(self, calepinage):
        """ACAL196 — ``{id, nom, ville}`` du client rattaché, ``None`` sans
        client. Lu sur le client DÉJÀ CHARGÉ par la liste
        (``select_related('client')``) : aucune requête par ligne."""
        client = getattr(calepinage, 'client', None)
        if client is None:
            return None
        ville = (getattr(client, 'ville', '') or '').strip() or None
        # ``Client.__str__`` ajoute une espace finale sans prénom : rognée.
        return {'id': client.pk, 'nom': str(client).strip(), 'ville': ville}

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_responsable_nom(self, calepinage):
        """CALX406 — ``None`` sans responsable, jamais un nom deviné.

        Lu sur l'utilisateur DÉJÀ CHARGÉ par la liste
        (``select_related('responsable')`` du viewset) : aucune requête par
        ligne (budget CALX390).
        """
        user = getattr(calepinage, 'responsable', None)
        if user is None:
            return None
        nom = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
        return nom or getattr(user, 'username', '') or None

    def _peremption(self, calepinage):
        """Le MÊME helper serveur que le détail devis et la page publique.

        CALX390 — calculé UNE fois par calepinage (les deux champs le lisent)
        et sur le devis DÉJÀ CHARGÉ par la liste (``select_related('devis')``
        et ``prefetch_related('devis__lignes')`` du viewset) : relire le devis
        par ``get_devis_by_pk`` et la société par ``calepinage.company`` coûtait
        cinq requêtes PAR LIGNE de la liste. La garde de société compare les
        identifiants, sans charger la société.
        """
        memo = getattr(calepinage, '_calx390_peremption', None)
        if memo is not None:
            return memo
        vide = {'layout_stale': None, 'layout_nb_panneaux': None}
        if not getattr(calepinage, 'devis_id', None):
            memo = vide
        else:
            devis = getattr(calepinage, 'devis', None)
            company_id = getattr(calepinage, 'company_id', None)
            if devis is None or (company_id is not None
                                 and devis.company_id != company_id):
                memo = vide
            else:
                memo = peremption_du_calepinage(devis, calepinage)
        try:
            calepinage._calx390_peremption = memo
        except AttributeError:  # objet figé (essais) : pas de mémo, rien de faux
            pass
        return memo

    def _lead_de_la_societe(self, company, lead_id):
        """CALX407 — le lead rattaché, borné société, ou ``None``.

        BUDGET (CALX390) — mémorisé UNE fois PAR LEAD et PAR SÉRIALISEUR :
        ``ListSerializer.to_representation`` appelle ``self.child`` (CE MÊME
        sérialiseur) pour CHAQUE ligne de la page — jamais une instance par
        ligne — donc un dict tenu sur ``self`` survit toute la liste. Un lead
        rattaché à PLUSIEURS calepinages de la page (le cas courant : un même
        prospect, plusieurs études) ne le relit qu'une fois, et l'accès
        ``.owner`` (repli ``responsable``, plus bas) n'est payé qu'à la
        PREMIÈRE lecture de ce lead — Django mémorise ensuite la relation sur
        l'objet ``Lead`` réutilisé du cache, jamais une requête de plus pour
        les lignes suivantes du même lead. Sans ce cache, chaque ligne
        relisait son lead PUIS son responsable : deux requêtes de plus par
        ligne (30 requêtes à 10 lignes, 60 à 25 — le N+1 d'ERR-QAH-CALEPINAGE-
        LISTE-SANS-RATTACHEMENT, réintroduit par ce même correctif).
        """
        # ``company`` : l'objet Company OU son identifiant (``company_id``).
        # La liste passe l'IDENTIFIANT lu sur la ligne (``instance.company_id``,
        # jamais ``instance.company`` : la FK n'est pas jointe par le queryset
        # de liste et coûtait UNE requête PAR LIGNE — le +1/ligne mesuré par
        # CALX390 : 21 requêtes à 10 lignes, 36 à 25).
        if not lead_id or company is None:
            return None
        company_id = getattr(company, 'pk', company)
        cache = self.__dict__.setdefault('_calx407_cache_leads', {})
        cle = (company_id, lead_id)
        if cle in cache:
            return cache[cle]
        from apps.crm.selectors import get_company_lead

        if not hasattr(company, 'pk'):
            # Chemin RARE (détail hors liste, ou lead absent du préchargement) :
            # on résout l'objet société une fois, depuis la requête si c'est
            # la même, sinon par lecture.
            request = self.context.get('request')
            candidate = getattr(getattr(request, 'user', None), 'company', None)
            if candidate is not None and candidate.pk == company_id:
                company = candidate
            else:
                from authentication.models import Company
                company = Company.objects.filter(pk=company_id).first()
                if company is None:
                    cache[cle] = None
                    return None
        lead = get_company_lead(company, lead_id)
        cache[cle] = lead
        return lead

    def to_representation(self, instance):
        """CALX407 — la LISTE (et la bibliothèque des modèles) publient le
        MÊME nom et le MÊME rattachement que le détail agrégé
        (``views/calepinages.py::detail_calepinage``) : la lecture ne change
        pas, seule la REPRÉSENTATION est complétée après coup.

        * ``nom`` — ERR-QAH-CALEPINAGE-NOM-CREATION-PERDU : le champ SAISI
          est ``titre`` — la liste ne rendait que lui, sous sa propre clé ;
          l'écran (atelier ET liste) lit ``nom``, exactement le même calcul
          que le détail (``_texte(titre) or str(calepinage)``, ici
          ``str(instance)`` — ``Calepinage.__str__`` fait le même repli).
        * ``lead`` — ERR-QAH-CALEPINAGE-LISTE-SANS-RATTACHEMENT : la liste ne
          publiait que l'identifiant OPAQUE ; l'écran affichait « Sans
          rattachement » faute du nom. Rendu en ``{id, nom, ville}``, comme
          le détail — jamais un second calcul : lu via
          ``apps.crm.selectors.get_company_lead`` (cross-app, jamais le
          modèle), et mémorisé par lead — voir ``_lead_de_la_societe``
          (budget CALX390).
        * ``responsable``/``responsable_nom`` — MÊME bug : une étude SANS
          responsable SAISI (``Calepinage.responsable`` vide) retombait sur
          ``null`` alors que le détail sait retomber sur le responsable du
          lead rattaché (CALX406, ``views/calepinages.py::_responsable``).
          Le CHAMP saisi garde la priorité (inchangé, aucune requête de plus
          quand il est posé) ; SEUL le repli manquant est ajouté ici, sur le
          lead déjà résolu (mémorisé) ci-dessus.
        """
        data = super().to_representation(instance)
        data['nom'] = str(instance)
        company_id = getattr(instance, 'company_id', None)
        lead_id = getattr(instance, 'lead_id', None)
        lead = self._lead_de_la_societe(company_id, lead_id)
        data['lead'] = _lead_apercu(lead)
        if data.get('responsable') is None and lead is not None:
            proprietaire = getattr(lead, 'owner', None)
            if proprietaire is not None:
                nom = (getattr(proprietaire, 'get_full_name', lambda: '')()
                       or '').strip()
                data['responsable'] = proprietaire.pk
                data['responsable_nom'] = (
                    nom or getattr(proprietaire, 'username', ''))
        return data

    #: ACAL179 — clés ignorées (jamais lues, jamais refusées) d'un PATCH :
    #: la société est forcée côté serveur, l'id est celui de l'URL.
    CLES_IGNOREES = frozenset({'company', 'id'})

    def validate(self, attrs):
        """Au moins un rattachement, un client COHÉRENT avec le lead (règle
        appliquée aux seuls champs écrits), un lead qui existe VRAIMENT dans
        la société, et un PATCH strict sur ses clés (ACAL179)."""
        self._refuser_cles_non_inscriptibles()
        attrs = super().validate(attrs)
        instance = getattr(self, 'instance', None)
        lead_id = attrs.get('lead_id', getattr(instance, 'lead_id', None))
        client = attrs.get('client', getattr(instance, 'client', None))

        if not lead_id and client is None:
            raise serializers.ValidationError({
                'client': (
                    "Rattachez ce calepinage à un lead ou à un client : "
                    "renseignez « Client » ou « Lead »."
                ),
            })
        lead = None
        if lead_id and 'lead_id' in attrs:
            lead = self._exiger_lead_de_la_societe(lead_id)
        ecrit = 'lead_id' in attrs or 'client' in attrs
        if ecrit and lead_id and client is not None:
            if lead is None:
                lead = self._lead_de_la_requete(lead_id)
            if lead is not None and lead.client_id != client.pk:
                raise serializers.ValidationError({
                    'client': (
                        "Le client doit être celui du lead : ce lead "
                        + (f"est rattaché à un autre client (#{lead.client_id})"
                           if lead.client_id else "n'a pas de client")
                        + ". Laissez « Client » vide, ou choisissez le "
                        "client du lead."
                    ),
                })
        return attrs

    def _refuser_cles_non_inscriptibles(self):
        """ACAL179 — un PATCH qui écrit une clé en lecture seule ou inconnue
        est refusé EN LA NOMMANT (jamais un 200 qui n'écrit rien)."""
        if getattr(self, 'instance', None) is None:
            return
        corps = getattr(self, 'initial_data', None)
        if not isinstance(corps, dict):
            return
        inscriptibles = {nom for nom, champ in self.fields.items()
                         if not champ.read_only}
        erreurs = {}
        for cle in corps:
            if cle in inscriptibles or cle in self.CLES_IGNOREES:
                continue
            if cle == 'nom':
                erreurs[cle] = "Champ en lecture seule : renommez par titre."
            elif cle in self.fields:
                erreurs[cle] = "Champ en lecture seule : il ne s'écrit pas ici."
            else:
                erreurs[cle] = "Champ inconnu : il ne s'écrit pas ici."
        if erreurs:
            raise serializers.ValidationError(erreurs)

    def _lead_de_la_requete(self, lead_id):
        from apps.crm.selectors import get_company_lead

        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return None
        return get_company_lead(company, lead_id)

    def _exiger_lead_de_la_societe(self, lead_id):
        """Un lead d'une AUTRE société est « introuvable », jamais « interdit ».

        Lecture cross-app par le sélecteur crm uniquement : ce module
        n'importe jamais ``apps.crm.models``. Rend le lead (ou ``None`` sans
        société connue).
        """
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return None
        lead = self._lead_de_la_requete(lead_id)
        if lead is None:
            raise serializers.ValidationError({
                'lead': f"Lead introuvable (#{lead_id}).",
            })
        return lead


class CalepinageVarianteSerializer(serializers.ModelSerializer):
    """CAL21 — une variante en lecture et en écriture, SAUF ``retenue``.

    ``retenue`` est en LECTURE SEULE ici : elle n'a qu'un seul chemin
    d'écriture (``services.variantes.retenir_variante``, bascule atomique
    gardée par ``garde_retenue``). Un sérialiseur qui l'écrirait ouvrirait la
    seconde porte par laquelle on se retrouve avec deux retenues, ou zéro.
    """

    class Meta:
        model = CalepinageVariante
        fields = ['id', 'nom', 'roof_layout', 'resultat', 'retenue',
                  'layout_hash', 'cree_par', 'created_at', 'updated_at']
        read_only_fields = ['retenue', 'layout_hash', 'cree_par',
                            'created_at', 'updated_at']
