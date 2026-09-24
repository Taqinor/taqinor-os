"""Serializers en LECTURE SEULE de l'API publique (N89).

Champs explicitement choisis (jamais `__all__`) pour exposer une vue publique
propre des objets métier. Aucun prix d'achat / marge n'est jamais sérialisé :
les lignes n'exposent que prix_unitaire (prix de VENTE) et totaux, jamais
`Produit.prix_achat`.
"""
from rest_framework import serializers

from apps.crm.models import Lead
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.uxviews.models import FavoriUtilisateur, SavedView

from .models import BulkJob


class PublicLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            'id', 'nom', 'prenom', 'societe', 'email', 'telephone',
            'ville', 'stage', 'canal', 'priorite', 'type_installation',
            'perdu', 'source', 'date_creation', 'date_modification',
        ]
        read_only_fields = fields


class PublicLigneDevisSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = LigneDevis
        # prix_unitaire = prix de VENTE ; jamais de prix d'achat ici.
        fields = [
            'id', 'designation', 'quantite', 'prix_unitaire', 'remise',
            'taux_tva', 'total_ht',
        ]
        read_only_fields = fields


class PublicDevisSerializer(serializers.ModelSerializer):
    lignes = PublicLigneDevisSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    client = serializers.PrimaryKeyRelatedField(read_only=True)
    lead = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Devis
        fields = [
            'id', 'reference', 'client', 'lead', 'statut',
            'date_creation', 'date_validite', 'taux_tva', 'remise_globale',
            'mode_installation', 'total_ht', 'total_tva', 'total_ttc',
            'lignes',
        ]
        read_only_fields = fields


class PublicLigneFactureSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneFacture
        fields = [
            'id', 'designation', 'quantite', 'prix_unitaire', 'remise',
            'taux_tva',
        ]
        read_only_fields = fields


class PublicFactureSerializer(serializers.ModelSerializer):
    lignes = PublicLigneFactureSerializer(many=True, read_only=True)
    client = serializers.PrimaryKeyRelatedField(read_only=True)
    devis = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Facture
        fields = [
            'id', 'reference', 'client', 'devis', 'statut', 'type_facture',
            'pourcentage', 'libelle', 'montant_ht', 'montant_tva',
            'montant_ttc', 'date_emission', 'date_echeance', 'taux_tva',
            'remise_globale', 'lignes',
        ]
        read_only_fields = fields


class PublicProduitSerializer(serializers.ModelSerializer):
    """XSTK23 — disponibilité produit UNIQUEMENT : SKU/nom/marque/catégorie/
    quantité disponible. JAMAIS `prix_achat` ni `prix_vente` ni aucun coût."""
    categorie = serializers.SlugRelatedField(
        slug_field='nom', read_only=True)
    quantite_disponible = serializers.SerializerMethodField()

    class Meta:
        model = Produit
        fields = [
            'id', 'sku', 'nom', 'marque', 'categorie', 'quantite_disponible',
        ]
        read_only_fields = fields

    def get_quantite_disponible(self, obj):
        from apps.stock.services import available_quantity
        return available_quantity(obj)


class BulkJobSerializer(serializers.ModelSerializer):
    """NTAPI16 — suivi d'un `BulkJob` : statut/progression/compteurs/liens.

    `resultat_url`/`erreurs_url` sont des liens présignés COURTE durée (15 min,
    comme les notifications « export prêt » existantes) — jamais l'URL MinIO
    interne brute, jamais permanents. `resultat_url` n'apparaît qu'une fois
    `termine` ; `erreurs_url` dès qu'au moins une ligne a échoué (même job
    encore `en_cours`, pour un import partiel)."""
    progression_pct = serializers.IntegerField(read_only=True)
    resultat_url = serializers.SerializerMethodField()
    erreurs_url = serializers.SerializerMethodField()

    class Meta:
        model = BulkJob
        fields = [
            'id', 'type', 'entite', 'statut', 'progression_pct',
            'total', 'traites', 'succes', 'erreurs',
            'resultat_url', 'erreurs_url', 'message_erreur',
            'created_at', 'updated_at', 'termine_le',
        ]
        read_only_fields = fields

    def get_resultat_url(self, obj):
        if obj.statut != BulkJob.STATUT_TERMINE or not obj.resultat_file_key:
            return None
        from apps.records.storage import presign_export_result
        return presign_export_result(obj.resultat_file_key, expires=900)

    def get_erreurs_url(self, obj):
        if not obj.erreurs_file_key:
            return None
        from apps.records.storage import presign_export_result
        return presign_export_result(obj.erreurs_file_key, expires=900)


class PublicChantierSerializer(serializers.ModelSerializer):
    """Installation = « Chantier » (verbose_name) côté métier."""
    client = serializers.PrimaryKeyRelatedField(read_only=True)
    devis = serializers.PrimaryKeyRelatedField(read_only=True)
    lead = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Installation
        fields = [
            'id', 'reference', 'client', 'devis', 'lead', 'statut',
            'site_ville', 'puissance_installee_kwc', 'raccordement',
            'type_installation',
            # FG104 — exposé pour la synchro incrémentale (?updated_since=).
            'date_creation', 'date_modification',
        ]
        read_only_fields = fields


class PublicSavedViewSerializer(serializers.ModelSerializer):
    """NTUX33 — vue sauvegardée (apps.uxviews.SavedView, NTUX1), LECTURE
    SEULE. Sans `?owner=`, seules les vues d'ÉQUIPE (déjà visibles en
    interne de toute la société) atteignent ce serializer — voir
    `public_uxviews_views.PublicSavedViewViewSet.get_queryset`."""
    owner = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = SavedView
        fields = [
            'id', 'ecran', 'nom', 'configuration', 'visibilite',
            'est_defaut_role', 'owner', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class PublicFavoriSerializer(serializers.ModelSerializer):
    """NTUX33 — favori épinglé (apps.uxviews.FavoriUtilisateur, NTUX12),
    LECTURE SEULE. STRICTEMENT scopé à `?owner=` (jamais servi sans, voir
    `public_uxviews_views.PublicFavoriViewSet.get_queryset`) : un favori
    d'un collègue ne doit jamais fuiter, même par clé d'API."""
    modele = serializers.SerializerMethodField()
    libelle = serializers.SerializerMethodField()
    owner = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FavoriUtilisateur
        fields = [
            'id', 'modele', 'object_id', 'libelle', 'ordre', 'owner',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_modele(self, obj) -> str:
        return obj.cle_modele

    def get_libelle(self, obj) -> str | None:
        cible = obj.cible
        return str(cible) if cible is not None else None


class PublicCalepinageSerializer(serializers.Serializer):
    """CAL214 — un calepinage du module autonome, en LECTURE SEULE publique.

    **Serializer PLAT (pas un ``ModelSerializer``), volontairement.** La
    frontière inter-apps veut que toute lecture de ``apps.calepinage`` passe
    par son ``selectors.py`` ; un ``ModelSerializer`` exigerait
    ``model = Calepinage``, c'est-à-dire exactement l'import de modèle que
    cette frontière interdit. Les champs sont donc déclarés un par un — ce qui
    a un second effet utile : la liste ci-dessous EST le contrat, et rien ne
    peut s'y ajouter par inadvertance parce qu'un champ est apparu au modèle.

    CE QUI N'EST JAMAIS PUBLIÉ (gardes testées, `tests_cal214_calepinage.py`) :

    * la GÉOMÉTRIE brute — ni ``roof_layout``, ni les plans/rangées/tables du
      ``resultat`` du moteur : l'empreinte ``layout_hash`` suffit à une
      intégration pour savoir qu'une conception a changé, le dessin lui-même
      reste dans l'atelier ;
    * tout COÛT interne — ``Produit.prix_achat`` n'entre dans aucune de ces
      clés, même règle que ``PublicProduitSerializer`` (XSTK23) ;
    * le contrat publié du détail interne
      (``apps/calepinage/contract_samples/calepinage_detail.json``) reste le
      plafond : cette vue publique en expose un SOUS-ENSEMBLE, jamais une clé
      de plus.

    ``kwc`` et ``modules`` sont LUS du résultat réellement calculé par le
    moteur (clés ``kwc`` / ``total_modules`` de
    ``contract_samples/moteur_calculer.json``). Tant qu'aucun calcul n'a été
    joué ils valent ``null``, JAMAIS ``0`` : publier un zéro ferait lire
    « toiture vide » là où rien n'a encore été calculé.
    """
    id = serializers.IntegerField(read_only=True)
    titre = serializers.CharField(read_only=True)
    statut = serializers.CharField(read_only=True)
    statut_libelle = serializers.SerializerMethodField()
    lead_id = serializers.IntegerField(read_only=True, allow_null=True)
    client_id = serializers.IntegerField(read_only=True, allow_null=True)
    devis_id = serializers.IntegerField(read_only=True, allow_null=True)
    appel_offre_id = serializers.IntegerField(read_only=True, allow_null=True)
    layout_hash = serializers.CharField(read_only=True, allow_blank=True)
    version_moteur = serializers.CharField(read_only=True, allow_blank=True)
    kwc = serializers.SerializerMethodField()
    modules = serializers.SerializerMethodField()
    liens = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def get_statut_libelle(self, obj) -> str:
        libelle = getattr(obj, 'get_statut_display', None)
        if callable(libelle):
            return libelle()
        return str(getattr(obj, 'statut', '') or '')

    def get_kwc(self, obj) -> float | None:
        return _nombre_calepinage(_resultat_calepinage(obj).get('kwc'))

    def get_modules(self, obj) -> int | None:
        valeur = _nombre_calepinage(
            _resultat_calepinage(obj).get('total_modules'))
        return int(valeur) if valeur is not None else None

    def get_liens(self, obj) -> dict:
        """Les SORTIES du calepinage : aujourd'hui l'aperçu rendu.

        Lien présigné COURTE durée (1 h), comme les autres liens d'image du
        dépôt — jamais la clé de stockage brute. Sans rendu enregistré, ou si
        le stockage ne répond pas, la clé reste PRÉSENTE à ``null`` : une
        intégration ne doit jamais avoir à deviner si une clé manque parce
        qu'il n'y a pas d'image ou parce que le serveur l'a omise.
        """
        return {'apercu': _url_apercu_calepinage(obj)}


def _resultat_calepinage(obj):
    """Le résultat du moteur, TOUJOURS un dict (jamais ``None`` à lire)."""
    valeur = getattr(obj, 'resultat', None)
    return valeur if isinstance(valeur, dict) else {}


def _nombre_calepinage(valeur):
    """Un nombre RÉEL, ou ``None`` — jamais une valeur inventée, jamais 0."""
    if valeur is None or isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    return None


def _url_apercu_calepinage(obj):
    cle = (getattr(obj, 'roof_image', None) or '').strip()
    if not cle:
        return None
    try:
        from apps.ventes.utils.pdf import roof_image_signed_url
        return roof_image_signed_url(cle)
    except Exception:  # noqa: BLE001 — best-effort : jamais un 500 sur un lien
        return None


# ── CALX369 — le RÉSULTAT DE SIMULATION d'un calepinage, en lecture ────────

#: Le motif publié quand aucune simulation n'est servie (jamais simulée). Une
#: simulation PÉRIMÉE publie, elle, le motif du module, qui nomme la date du
#: calcul (CALX70).
MOTIF_RESULTAT_NON_SIMULE = (
    "Ce calepinage n'a pas été simulé : aucune production n'est publiée — "
    'les grandeurs valent null, jamais 0.')


class PublicPostePerteSerializer(serializers.Serializer):
    """CALX369 — UN poste de la chaîne de pertes, champ par champ.

    ``pourcentage`` vaut ``null`` quand l'étape a été OMISE (son ``motif`` dit
    pourquoi) ; ``gain`` est vrai pour une étape qui AJOUTE de l'énergie (le
    froid, par exemple) ; ``source`` dit d'où vient la valeur (``pvgis``,
    ``fiche``, ``saisie``, ``mesure``…) et vaut ``null`` pour un poste non
    sourcé — il est publié tel quel, jamais masqué.
    """
    code = serializers.CharField(read_only=True)
    libelle = serializers.CharField(read_only=True, allow_blank=True)
    pourcentage = serializers.FloatField(read_only=True, allow_null=True)
    source = serializers.CharField(read_only=True, allow_null=True)
    gain = serializers.BooleanField(read_only=True)
    motif = serializers.CharField(read_only=True, allow_blank=True)


class PublicCalepinageResultatSerializer(serializers.Serializer):
    """CALX369 — ``GET calepinages/<pk>/resultat/`` : serializer PLAT.

    Chaque champ qui sort est déclaré ci-dessous — la liste EST le contrat,
    et rien ne s'y ajoute parce qu'un bloc est apparu dans le résultat
    interne. Elle est un sous-ensemble renommé du contrat interne
    ``apps/calepinage/contract_samples/calepinage_resultat.json`` (plafond) :
    ni ``roof_layout``, ni pose/rangées, ni électrique, ni coût.

    * ``production_annuelle_kwh`` — l'énergie annuelle SIMULÉE, c'est-à-dire
      l'année médiane : c'est la même grandeur que ``p50_kwh``, publiée sous
      son nom métier (le résultat ne porte aucune autre énergie annuelle) ;
    * ``rendement_specifique_kwh_kwc`` — kWh produits par kWc installé ;
    * ``ratio_performance`` — le PR, en FRACTION (0,80 = 80 %) ;
    * ``p50_kwh``/``p75_kwh``/``p90_kwh`` — quantiles annuels ;
    * ``pertes`` — la chaîne de pertes réellement appliquée ;
    * ``calcule_le`` — l'horodatage enregistré PAR la simulation servie.

    Non simulé (ou simulation périmée) ⇒ ``simule`` faux, toutes les
    grandeurs à ``null`` (jamais ``0``), ``pertes`` à ``null`` et ``motif``
    dit pourquoi.
    """
    calepinage_id = serializers.IntegerField(read_only=True)
    simule = serializers.BooleanField(read_only=True)
    production_annuelle_kwh = serializers.FloatField(read_only=True,
                                                     allow_null=True)
    rendement_specifique_kwh_kwc = serializers.FloatField(read_only=True,
                                                          allow_null=True)
    ratio_performance = serializers.FloatField(read_only=True,
                                               allow_null=True)
    p50_kwh = serializers.FloatField(read_only=True, allow_null=True)
    p75_kwh = serializers.FloatField(read_only=True, allow_null=True)
    p90_kwh = serializers.FloatField(read_only=True, allow_null=True)
    pertes = PublicPostePerteSerializer(many=True, read_only=True,
                                        allow_null=True)
    calcule_le = serializers.CharField(read_only=True, allow_null=True)
    simulation_perimee = serializers.BooleanField(read_only=True)
    motif = serializers.CharField(read_only=True, allow_blank=True)


def _texte_ou_null(valeur):
    texte = str(valeur).strip() if valeur is not None else ''
    return texte or None


def _postes_de_pertes_publics(servi):
    """La chaîne de pertes SERVIE, aplatie poste par poste.

    La cascade de la simulation (CALX147) fait foi : c'est elle qui a produit
    le P50. Un résultat plus ancien, sans cascade, publie la liste plate des
    postes saisis qu'il porte (forme CAL139). Aucun poste n'est inventé.
    """
    cascade = servi.get('cascade')
    etapes = cascade.get('etapes') if isinstance(cascade, dict) else None
    if isinstance(etapes, list) and etapes:
        return [{
            'code': str(etape.get('etape') or ''),
            'libelle': str(etape.get('libelle') or ''),
            'pourcentage': _nombre_calepinage(etape.get('perte_pct')),
            'source': _texte_ou_null(etape.get('source')),
            'gain': etape.get('gain') is True,
            'motif': str(etape.get('motif_omission') or ''),
        } for etape in etapes if isinstance(etape, dict)]
    postes = servi.get('pertes')
    if not isinstance(postes, list):
        return []
    return [{
        'code': str(poste.get('poste') or ''),
        'libelle': str(poste.get('libelle') or ''),
        'pourcentage': _nombre_calepinage(poste.get('pct')),
        'source': _texte_ou_null(poste.get('source')),
        'gain': False,
        'motif': '',
    } for poste in postes if isinstance(poste, dict)]


def resultat_calepinage_public(calepinage_id, servi):
    """Aplatit le résultat SERVI par le module (``selectors.resultat_servi``).

    ``simule`` est le verdict du module (CALX70 : vrai seulement si la
    production est un nombre ET que la simulation décrit encore ce toit) —
    il n'est jamais recalculé ici.
    """
    servi = servi if isinstance(servi, dict) else {}
    simule = servi.get('simule') is True
    production = servi.get('production') if simule else None
    total = production.get('total') if isinstance(production, dict) else None
    total = total if isinstance(total, dict) else {}

    def lire(cle):
        return _nombre_calepinage(total.get(cle)) if simule else None

    p50 = lire('p50_kwh')
    return {
        'calepinage_id': calepinage_id,
        'simule': simule,
        'production_annuelle_kwh': p50,
        'rendement_specifique_kwh_kwc': lire('specific_yield_kwh_kwc'),
        'ratio_performance': lire('performance_ratio'),
        'p50_kwh': p50,
        'p75_kwh': lire('p75_kwh'),
        'p90_kwh': lire('p90_kwh'),
        'pertes': _postes_de_pertes_publics(servi) if simule else None,
        'calcule_le': (_texte_ou_null(servi.get('calcule_le'))
                       if simule else None),
        'simulation_perimee': servi.get('simulation_perimee') is True,
        'motif': ('' if simule else
                  (str(servi.get('motif') or '').strip()
                   or MOTIF_RESULTAT_NON_SIMULE)),
    }
