from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from .models import (
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
    Avoir, LigneAvoir, DevisActivity, DevisPreset, RoofLayout,
    FicheTechnique, RemiseEncaissement, LigneRemiseEncaissement,
    MandatPaiement, ListePrix, LignePrixListe, RegleListePrix,
)


def _fallback_taux_tva(company, designation):
    """DC4 / ARC23 — taux de TVA de repli d'une ligne sans taux ni produit taxé.

    Une ligne PANNEAU retombe sur le défaut société panneaux
    (CompanyProfile.tva_panneaux, 10 %) ; toute autre ligne sur le taux standard.
    `Produit.tva` reste prioritaire côté appelant (DC7) : ce repli ne s'applique
    QUE lorsqu'il n'existe ni taux explicite ni produit portant un taux, donc le
    comportement reste identique tant que les produits portent leur taux (cas
    nominal après seed_catalogue).

    ARC23 — pour une ligne STANDARD, le knob éditable en Paramètres
    (`CompanyProfile.tva_standard`, réglé par l'utilisateur) est PRIORITAIRE :
    on le lit d'abord. Le référentiel `parametres.TauxTVA` (sans UI, seedé à
    20 % pour chaque nouveau tenant par `signup_hooks.seed_taux_tva_hook`) ne
    sert plus que de repli quand ce knob ne donne pas de taux, puis la constante
    historique (20). Ainsi un tenant qui met « TVA standard » à 14 % voit 14 %
    sur ses lignes de repli — le référentiel seedé ne le réprime plus. Un tenant
    qui n'a jamais touché le champ garde sa valeur par défaut (20 %), inchangée.
    Un taux déjà figé sur un document existant n'est JAMAIS réécrit (règle #4).
    """
    from apps.ventes.utils.company_settings import tva_standard, tva_panneaux
    d = (designation or '').lower()
    if 'panneau' in d:
        return tva_panneaux(company)
    # Knob éditable (Paramètres) d'abord — l'édition de l'utilisateur prime.
    standard = tva_standard(company)
    if standard is not None:
        return standard
    # Repli : référentiel TauxTVA (sans UI), puis constante historique.
    try:
        from apps.parametres.models_taxes import TauxTVA
        referentiel = TauxTVA.default_taux(company)
    except Exception:
        referentiel = None
    if referentiel is not None:
        return referentiel
    from decimal import Decimal
    return Decimal('20')


class LigneDevisSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = LigneDevis
        fields = '__all__'

    def validate(self, attrs):
        """XSAL14 — cohérence produit vs section/note.

        • Ligne PRODUIT (défaut) : un produit est requis (comportement
          historique — une LigneDevis produit référence un Produit du stock).
        • Ligne SECTION/NOTE : intertitre/texte sans prix — on NEUTRALISE tout
          produit/prix/quantité éventuellement fournis (jamais comptée dans les
          totaux). Une désignation (le libellé de la section / le texte de la
          note) reste requise."""
        instance = getattr(self, 'instance', None)
        type_ligne = attrs.get(
            'type_ligne',
            getattr(instance, 'type_ligne', LigneDevis.TypeLigne.PRODUIT))
        if type_ligne in (LigneDevis.TypeLigne.SECTION,
                          LigneDevis.TypeLigne.NOTE):
            attrs['produit'] = None
            attrs['quantite'] = None
            attrs['prix_unitaire'] = None
            attrs['taux_tva'] = None
            if not (attrs.get('designation')
                    or getattr(instance, 'designation', '')):
                raise serializers.ValidationError({
                    'designation': 'Un intitulé est requis pour une ligne de '
                                   'section ou de note.'})
        else:
            if attrs.get('produit') is None \
                    and getattr(instance, 'produit_id', None) is None:
                raise serializers.ValidationError({
                    'produit': 'Une ligne produit doit référencer un produit.'})
        return attrs

    def create(self, validated_data):
        # XSAL14 — une ligne section/note n'a pas de produit : pas de copie de
        # taux (le champ est neutralisé par validate). On saute alors la logique
        # de repli TVA (réservée aux lignes produit).
        if validated_data.get('type_ligne', LigneDevis.TypeLigne.PRODUIT) \
                != LigneDevis.TypeLigne.PRODUIT:
            return super(LigneDevisSerializer, self).create(validated_data)
        # Réforme TVA 2024–2026 : toute NOUVELLE ligne porte son propre taux,
        # copié du produit (10 % panneaux PV, 20 % le reste) quand il n'est pas
        # fourni. Repli sur le taux STANDARD éditable de la société (défaut 20 %
        # → comportement identique). Lignes historiques (NULL) inchangées.
        if validated_data.get('taux_tva') is None:
            produit = validated_data.get('produit')
            produit_tva = getattr(produit, 'tva', None)
            if produit_tva is not None:
                validated_data['taux_tva'] = produit_tva
            else:
                company = getattr(validated_data.get('devis'), 'company', None)
                validated_data['taux_tva'] = _fallback_taux_tva(
                    company, validated_data.get('designation'))
        return super().create(validated_data)


class DevisSerializer(serializers.ModelSerializer):
    lignes = LigneDevisSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    # Total d'AFFICHAGE canonique : pour un devis à deux options, le total de
    # l'option 1 (remise incluse) — jamais la somme des deux options.
    total_affiche = serializers.SerializerMethodField()
    nb_options = serializers.SerializerMethodField()
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    lead_nom = serializers.SerializerMethodField()
    # VX98 — auteur de la dernière modification (puce de fraîcheur). Lecture seule.
    updated_by_nom = serializers.CharField(
        source='updated_by.username', read_only=True, default=None)
    # Contexte « quote-aware » du lead lié (profil énergétique) — lecture seule,
    # pour un aperçu au survol dans la liste des devis. None si pas de lead.
    lead_facture_hiver = serializers.SerializerMethodField()
    lead_type_installation = serializers.SerializerMethodField()
    # PUB53 — liens retour Devis → annonce d'origine : id d'attribution ADSENG1
    # du lead lié (même champ que crm.LeadSerializer, lu ici via la relation
    # `lead` déjà déclarée en string-FK 'crm.Lead' — même motif que
    # get_lead_facture_hiver/get_lead_type_installation juste au-dessus, jamais
    # un import de apps.crm.models). None si pas de lead ou lead non-Meta.
    lead_meta_ad_id = serializers.SerializerMethodField()
    # NTCPQ6 — drapeau INTERNE « marge sous seuil » (staff only, jamais côté
    # client). Comme marge_snapshot, la CLÉ elle-même est retirée du payload
    # pour tout rendu non authentifié (voir to_representation).
    marge_sous_seuil = serializers.SerializerMethodField()

    def get_marge_sous_seuil(self, obj):
        from apps.cpq.selectors import devis_marge_sous_seuil
        return devis_marge_sous_seuil(obj)

    def get_lead_facture_hiver(self, obj):
        return str(obj.lead.facture_hiver) if obj.lead_id and \
            obj.lead.facture_hiver is not None else None

    def get_lead_meta_ad_id(self, obj):
        return obj.lead.meta_ad_id if obj.lead_id and \
            obj.lead.meta_ad_id else None

    def get_lead_type_installation(self, obj):
        if not obj.lead_id:
            return None
        return obj.lead.get_type_installation_display() \
            if obj.lead.type_installation else None

    def _display(self, obj):
        if not hasattr(obj, '_display_totals_cache'):
            from .quote_engine.builder import display_totals
            obj._display_totals_cache = display_totals(obj)
        return obj._display_totals_cache

    def get_total_affiche(self, obj):
        return self._display(obj)['total']

    def get_nb_options(self, obj):
        return self._display(obj)['nb_options']

    # Solde du devis : total TTC, montant facturé, payé, restant + avancement
    # de l'échéancier. Calculé par l'unique helper apps.ventes.utils.echeancier.
    solde = serializers.SerializerMethodField()

    def get_lead_nom(self, obj):
        if not obj.lead_id:
            return None
        return f"{obj.lead.nom} {obj.lead.prenom or ''}".strip()

    def get_solde(self, obj):
        from .utils.echeancier import solde_devis
        s = solde_devis(obj)
        return {k: str(v) for k, v in s.items()}

    # Expiration calculée À LA VOLÉE (T7) — jamais persistée, ne touche pas le
    # lead. `is_expired` = en attente + date de validité dépassée.
    is_expired = serializers.SerializerMethodField()
    date_expiration = serializers.SerializerMethodField()

    # Référence de la version qui remplace ce devis (T10) — pour le lien
    # « remplacé par » dans l'UI.
    superseded_by_ref = serializers.SerializerMethodField()
    # Référence du devis parent (version précédente) — pour reconstituer la
    # chaîne de révisions dans l'UI (panneau historique des versions).
    version_parent_ref = serializers.SerializerMethodField()

    def get_superseded_by_ref(self, obj):
        return obj.superseded_by.reference if obj.superseded_by_id else None

    def get_version_parent_ref(self, obj):
        return obj.version_parent.reference if obj.version_parent_id else None

    def get_is_expired(self, obj):
        from .utils.expiry import is_expired
        return is_expired(obj)

    def get_date_expiration(self, obj):
        from .utils.expiry import date_expiration
        d = date_expiration(obj)
        return d.isoformat() if d else None

    # Chantier lié (s'il existe) — pour le lien devis ↔ chantier dans l'UI.
    chantier = serializers.SerializerMethodField()

    def get_chantier(self, obj):
        # N+1 réel corrigé (YOPSB13) : ``installation_for_devis`` exécute une
        # requête PAR devis (Installation.objects.filter(devis=devis).first())
        # — flagrant sur la liste. ``DevisViewSet.queryset`` précharge
        # désormais la relation inverse ``installations`` (FK
        # Installation.devis, related_name='installations' — string-FK
        # cross-app, jamais d'import de apps.installations.models ici) ; on
        # réutilise ce cache prefetch au lieu de rappeler le sélecteur, qui
        # reste la voie d'accès pour un usage hors liste (fiche détail unique).
        installations = getattr(obj, '_prefetched_objects_cache', {}).get(
            'installations')
        if installations is not None:
            inst = installations[0] if installations else None
        else:
            from apps.installations.selectors import installation_for_devis
            inst = installation_for_devis(obj)
        if inst is None:
            return None
        return {'id': inst.id, 'reference': inst.reference,
                'statut': inst.statut}

    # U5 — Factures générées depuis ce devis (échéancier : acompte/tranches),
    # lecture seule. Permet d'afficher des chips cliquables vers la facture dans
    # la liste/le détail. Bornées à la société par le devis lui-même (un Facture
    # partage toujours la company de son devis). Aucun nouveau chemin d'écriture.
    factures_liees = serializers.SerializerMethodField()
    # U5/U8 — Bon de commande lié (OneToOne) : référence + statut, et un drapeau
    # d'incohérence (U8) quand le devis est « accepté » mais que son BC est
    # annulé — ou qu'aucun BC n'existe. Lecture seule, dérivé de la relation
    # existante ; ne change aucun statut.
    bon_commande_etat = serializers.SerializerMethodField()

    def get_factures_liees(self, obj):
        # related_name='factures' depuis Facture.devis (FK). Triées par référence
        # pour un rendu stable. Référence + statut (+ libellé du statut) suffisent
        # pour une chip cliquable ; aucun montant client-sensible ajouté ici.
        # YOPSB13 — ``.order_by()`` sur le manager cloné IGNORE le cache
        # prefetch ('factures' préchargé par DevisViewSet) et ré-exécute une
        # requête par ligne (N+1). On trie en Python la liste déjà en cache.
        return [
            {
                'id': f.id,
                'reference': f.reference,
                'statut': f.statut,
                'statut_display': f.get_statut_display(),
                'type_facture': f.type_facture,
            }
            for f in sorted(obj.factures.all(), key=lambda f: f.reference)
        ]

    def get_bon_commande_etat(self, obj):
        # Reverse OneToOne : l'accès lève RelatedObjectDoesNotExist quand aucun
        # BC n'existe — on le rattrape pour renvoyer un état « absent » propre.
        try:
            bc = obj.bon_commande
        except BonCommande.DoesNotExist:
            bc = None
        # U8 — un devis accepté DOIT normalement avoir un BC actif. On signale
        # l'incohérence quand le BC est annulé OU absent sur un devis accepté.
        is_accepte = obj.statut == 'accepte'
        if bc is None:
            return {
                'exists': False,
                'reference': None,
                'statut': None,
                'statut_display': None,
                'mismatch': is_accepte,
            }
        bc_annule = bc.statut == BonCommande.Statut.ANNULE
        return {
            'exists': True,
            'id': bc.id,
            'reference': bc.reference,
            'statut': bc.statut,
            'statut_display': bc.get_statut_display(),
            'mismatch': is_accepte and bc_annule,
        }

    # FG48 — comparaison deux options (Sans batterie / Avec batterie).
    # Données déjà calculées par build_quote_data ; on les expose ici pour
    # que le frontend puisse afficher la carte de comparaison A vs B avec ROI.
    # Vaut None pour un devis mono-option (pas de deuxième option).
    comparaison_options = serializers.SerializerMethodField()

    def get_comparaison_options(self, obj):
        """Retourne {sans, avec, roi, nb_options} si nb_options=2, sinon None.

        FG48 — expose les totaux des deux options (sans/avec batterie) et le
        ROI pour la carte de comparaison interactive dans DevisGenerator/detail.
        Données calculées par build_quote_data (même source que le PDF) — aucun
        nouveau calcul.
        """
        d = self._display(obj)
        if d.get('nb_options', 1) != 2:
            return None
        try:
            from .quote_engine.builder import build_quote_data
            data = build_quote_data(obj, {'pdf_mode': 'onepage'})
            ts = data.get('totaux_sans') or {}
            ta = data.get('totaux_avec') or {}
            return {
                'nb_options': 2,
                'sans': {
                    'ttc': ts.get('ttc'),
                    'ht_net': ts.get('ht_net'),
                    'remise': ts.get('remise'),
                },
                'avec': {
                    'ttc': ta.get('ttc'),
                    'ht_net': ta.get('ht_net'),
                    'remise': ta.get('remise'),
                },
                'roi': {
                    'prod_kwh': data.get('prod_kwh'),
                    'eco_s_ann': data.get('eco_s_ann'),
                    'eco_a_ann': data.get('eco_a_ann'),
                    'roi_s': data.get('roi_s'),
                    'roi_a': data.get('roi_a'),
                },
            }
        except Exception:
            return None

    # QJ22 — État de signature électronique (loi 53-05). Lecture seule.
    # ``est_signe`` : True si un DevisSignature immuable existe pour ce devis.
    # ``signature_info`` : dict minimal (signataire_nom, signed_at, has_pdf) —
    # jamais d'IP ni d'user_agent dans l'API interne (données personnelles) ;
    # jamais de prix_achat/marge.
    est_signe = serializers.SerializerMethodField()
    signature_info = serializers.SerializerMethodField()

    def get_est_signe(self, obj):
        """True si un DevisSignature (loi 53-05) existe pour ce devis."""
        try:
            return obj.signature is not None
        except Exception:
            return False

    def get_signature_info(self, obj):
        """Informations minimales de signature (sans données personnelles)."""
        try:
            sig = obj.signature
        except Exception:
            return None
        if sig is None:
            return None
        return {
            'signataire_nom': sig.signataire_nom,
            'signed_at': sig.signed_at.isoformat() if sig.signed_at else None,
            'has_pdf': bool(sig.signed_pdf_key),
        }

    # QJ1 — Statistiques de consultation du lien public (lecture seule).
    # Agrégat sur tous les ShareLinks du devis (on prend le lien le plus récent
    # encore valide, ou le dernier tout court). Aucun prix d'achat/marge exposé.
    nombre_vues = serializers.SerializerMethodField()
    derniere_consultation = serializers.SerializerMethodField()
    deja_consulte = serializers.SerializerMethodField()

    def _active_share_link(self, obj):
        """Renvoie le ShareLink le plus récent lié à ce devis (valide en premier).

        YOPSB13 — réutilise le cache prefetch de DevisViewSet.queryset
        ('share_links') au lieu de ``obj.share_links.filter(...)`` : un
        ``.filter()`` sur un related manager ne réutilise JAMAIS le cache
        prefetch (il ré-exécute une requête, et ``.first()``/``.exists()``
        en ré-exécutent chacun une autre) — appelé 4× par ligne
        (nombre_vues/derniere_consultation/deja_consulte/engagement) c'était
        un N+1. Résultat mémoïsé sur l'instance pour ne calculer qu'une fois."""
        if hasattr(obj, '_active_share_link_cache'):
            return obj._active_share_link_cache
        from django.utils import timezone as tz
        cached = getattr(obj, '_prefetched_objects_cache', {}).get('share_links')
        if cached is not None:
            links = [lk for lk in cached if lk.devis_id == obj.id]
        else:
            links = list(obj.share_links.filter(devis=obj))
        links.sort(key=lambda lk: (lk.expires_at, lk.created_at), reverse=True)
        now = tz.now()
        valid = [lk for lk in links if lk.expires_at > now]
        result = valid[0] if valid else (links[0] if links else None)
        obj._active_share_link_cache = result
        return result

    def get_nombre_vues(self, obj):
        link = self._active_share_link(obj)
        return link.view_count if link else 0

    def get_derniere_consultation(self, obj):
        link = self._active_share_link(obj)
        if link and link.last_viewed_at:
            return link.last_viewed_at.isoformat()
        return None

    def get_deja_consulte(self, obj):
        link = self._active_share_link(obj)
        return bool(link and link.first_viewed_at is not None)

    # XSAL16 — résumé d'engagement par section (« a passé 2 min sur le prix,
    # n'a pas ouvert l'étude »). Vide sans beacon — comportement QJ1 inchangé.
    engagement = serializers.SerializerMethodField()

    def get_engagement(self, obj):
        link = self._active_share_link(obj)
        return link.engagement_summary if link else {}

    # QX23be — marge interne figée, exposée UNIQUEMENT au responsable/admin
    # (jamais dans un PDF ni une sortie client — prix_achat rule). Un
    # commercial/lecteur reçoit toujours None ; ``fields='__all__'`` inclut le
    # champ modèle, cette méthode le NEUTRALISE pour les non-managers.
    marge_snapshot = serializers.SerializerMethodField()

    def get_marge_snapshot(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_responsable', False):
            val = obj.marge_snapshot
            return str(val) if val is not None else None
        return None

    def to_representation(self, instance):
        """QX23be / RULE #4 — the ``marge_snapshot`` KEY itself must never reach
        a client-facing / context-less path (a structural prix_achat/marge
        guard flags the mere presence of the key, not just its value). We keep
        the key ONLY when the serializer runs for an AUTHENTICATED internal
        user (commercial → None, responsable → valeur) ; any anonymous /
        context-less / public-token rendering drops the key entirely."""
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        is_auth = bool(user is not None and getattr(user, 'is_authenticated', False))
        if not is_auth:
            data.pop('marge_snapshot', None)
            # NTCPQ6 — la clé marge_sous_seuil (dérivée de prix_achat) ne doit
            # jamais fuiter hors d'un rendu interne authentifié (règle #4).
            data.pop('marge_sous_seuil', None)
        return data

    class Meta:
        model = Devis
        fields = '__all__'
        # SCA47 — prix_par_kwc est DÉRIVÉ et gelé côté serveur (write-once au
        # save) : lecture seule sur l'API interne générateur/BI, JAMAIS accepté
        # du corps de requête (même régime interne que prix_achat, qui n'est
        # jamais exposé côté client/PDF).
        read_only_fields = ['reference', 'created_by', 'fichier_pdf',
                            'date_creation', 'prix_par_kwc',
                            'updated_at', 'updated_by']  # VX98 — server-side only


class DevisWriteSerializer(serializers.ModelSerializer):
    """Création/modification sans lignes imbriquées.

    Le client devient optionnel À LA CRÉATION quand un lead est fourni : il est
    alors résolu côté serveur depuis le lead (apps.crm.services), jamais déduit
    côté navigateur. La vue garantit qu'au moins l'un des deux est présent et
    que lead/client appartiennent à la société de l'utilisateur.
    """
    class Meta:
        model = Devis
        exclude = ['reference', 'fichier_pdf']
        # company is force-assigned in perform_create — never accept it from the body.
        # SCA47 — prix_par_kwc est dérivé/gelé côté serveur (write-once), jamais
        # accepté du corps de requête.
        read_only_fields = ['created_by', 'date_creation', 'company',
                            'prix_par_kwc']
        extra_kwargs = {'client': {'required': False}}


class BonCommandeSerializer(serializers.ModelSerializer):
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    devis_reference = serializers.CharField(source='devis.reference', read_only=True, default=None)
    has_facture = serializers.SerializerMethodField()
    # FG51 — preuve de livraison (lecture seule : capturée par l'action
    # « marquer-livre », jamais par un PUT du corps).
    has_proof_of_delivery = serializers.BooleanField(read_only=True)
    # Totaux du BC dérivés du devis lié (un BC reprend les lignes du devis).
    # Aucun devis → None → l'UI affiche « — ». Affichage seulement.
    total_ht = serializers.SerializerMethodField()
    total_tva = serializers.SerializerMethodField()
    total_ttc = serializers.SerializerMethodField()
    # XSAL12 — état dérivé de livraison partielle (lecture seule, calculé à
    # la demande depuis LigneLivraisonBC ; ne casse pas l'enum de statut).
    reliquat_par_ligne = serializers.ListField(read_only=True)
    est_partiellement_livre = serializers.BooleanField(read_only=True)

    class Meta:
        model = BonCommande
        fields = '__all__'
        # company is force-assigned in perform_create — never accept it from the body.
        # FG51 — pv_livraison/date_livraison_reelle ne se posent QUE via
        # l'action « marquer-livre » (jamais un PUT direct du corps).
        read_only_fields = ['reference', 'date_creation', 'company',
                            'pv_livraison', 'date_livraison_reelle']

    def get_has_facture(self, obj):
        return Facture.objects.filter(bon_commande=obj).exists()

    def get_total_ht(self, obj):
        return str(obj.devis.total_ht) if obj.devis_id else None

    def get_total_tva(self, obj):
        return str(obj.devis.total_tva) if obj.devis_id else None

    def get_total_ttc(self, obj):
        return str(obj.devis.total_ttc) if obj.devis_id else None


class LigneFactureSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = LigneFacture
        fields = '__all__'

    def create(self, validated_data):
        # Réforme TVA : taux par ligne, copié du produit, repli sur le taux
        # STANDARD éditable de la société (défaut 20 % → identique).
        if validated_data.get('taux_tva') is None:
            produit = validated_data.get('produit')
            produit_tva = getattr(produit, 'tva', None)
            if produit_tva is not None:
                validated_data['taux_tva'] = produit_tva
            else:
                company = getattr(validated_data.get('facture'), 'company', None)
                validated_data['taux_tva'] = _fallback_taux_tva(
                    company, validated_data.get('designation'))
        return super().create(validated_data)


class PaiementSerializer(serializers.ModelSerializer):
    mode_display = serializers.CharField(source='get_mode_display', read_only=True)
    # Champs d'affichage (lecture seule) pour la page Encaissements : référence
    # de la facture, nom du client et auteur de l'encaissement (« par qui »).
    facture_reference = serializers.CharField(
        source='facture.reference', read_only=True, default=None)
    client_nom = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True, default=None)
    # XFAC1 — avance non affectée : solde encore disponible pour ventilation.
    montant_disponible = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    statut_affectation_display = serializers.CharField(
        source='get_statut_affectation_display', read_only=True)

    # SCA45 — ``idempotency_key`` est OPTIONNEL : un encaissement MANUEL n'en a
    # pas (seuls les appels idempotents webhook/API en fournissent une). Il DOIT
    # être déclaré EXPLICITEMENT ``required=False`` : la contrainte d'unicité
    # (company, idempotency_key) — CONDITIONNELLE côté DB (WHERE clé non nulle) —
    # fait générer par DRF un validateur unique-together AUTO qui, en ignorant la
    # condition, marque le champ ``required=True`` au MOMENT de la construction du
    # champ (dans ``super().__init__``). Retirer seulement le validateur ensuite
    # (ci-dessous) NE réinitialise PAS ``field.required`` déjà calculé → 400 « Ce
    # champ est obligatoire » sur chaque encaissement manuel. La déclaration
    # explicite court-circuite cette logique auto ; la contrainte DB reste
    # l'arbitre de l'unicité pour les vrais appels idempotents.
    idempotency_key = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Retire AUSSI le validateur unique-together AUTO (en plus de la
        # déclaration explicite ci-dessus) pour qu'il ne tente pas la vérif
        # d'unicité sur la clé nulle d'un paiement manuel ; la contrainte DB
        # conditionnelle reste l'arbitre.
        self.validators = [
            v for v in self.validators
            if not (isinstance(v, UniqueTogetherValidator)
                    and 'idempotency_key' in getattr(v, 'fields', ()))]

    def get_client_nom(self, obj):
        c = obj.facture.client if obj.facture_id else obj.client
        if c is None:
            return None
        return f"{c.nom} {c.prenom or ''}".strip()

    class Meta:
        model = Paiement
        fields = '__all__'
        # company/created_by forcés côté serveur — jamais depuis le corps.
        # escompte_montant (XFAC12) est calculé côté serveur (fenêtre + net
        # réglé), jamais accepté du corps de requête.
        read_only_fields = ['company', 'created_by', 'date_creation', 'facture',
                            'escompte_montant']


class AffectationPaiementSerializer(serializers.ModelSerializer):
    facture_reference = serializers.CharField(
        source='facture.reference', read_only=True)

    class Meta:
        from .models import AffectationPaiement
        model = AffectationPaiement
        fields = ['id', 'paiement', 'facture', 'facture_reference',
                  'montant', 'date_affectation', 'created_by']
        read_only_fields = ['company', 'created_by', 'date_affectation']


class RetenueSubieSerializer(serializers.ModelSerializer):
    """XFAC4 — RAS subie (TVA/IS) constatée sur une facture client."""
    type_retenue_display = serializers.CharField(
        source='get_type_retenue_display', read_only=True)
    facture_reference = serializers.CharField(
        source='facture.reference', read_only=True)

    class Meta:
        from .models import RetenueSubie
        model = RetenueSubie
        fields = '__all__'
        read_only_fields = ['company', 'created_by', 'date_creation', 'facture',
                            'paiement']


class FactureSerializer(serializers.ModelSerializer):
    lignes = LigneFactureSerializer(many=True, read_only=True)
    paiements = PaiementSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    montant_paye = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    montant_du = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    avoirs_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    avoirs = serializers.SerializerMethodField()
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    # L853 — téléphone du client (lecture seule) : permet de valider/désactiver
    # le bouton WhatsApp côté front sans aller-retour 400. Jamais en écriture.
    client_telephone = serializers.CharField(
        source='client.telephone', read_only=True, default=None)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    type_facture_display = serializers.CharField(source='get_type_facture_display', read_only=True)
    devis_reference = serializers.CharField(source='devis.reference', read_only=True, default=None)
    # VX98 — auteur de la dernière modification (puce de fraîcheur). Lecture seule.
    updated_by_nom = serializers.CharField(
        source='updated_by.username', read_only=True, default=None)
    # Ventilation TVA par taux (10 %/20 %), réconciliée au centime.
    tva_par_taux = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    jours_retard = serializers.IntegerField(read_only=True)
    # Conformité Article 145 CGI (N11) : mentions légales manquantes — pur
    # AVERTISSEMENT, ne bloque jamais l'émission.
    mentions_manquantes = serializers.ListField(
        child=serializers.CharField(), read_only=True)

    def get_tva_par_taux(self, obj):
        return [
            {'taux': str(b['taux']), 'base_ht': str(b['base_ht']),
             'montant': str(b['montant'])}
            for b in obj.tva_par_taux
        ]

    def get_avoirs(self, obj):
        return [
            {'id': a.id, 'reference': a.reference, 'statut': a.statut,
             'total_ttc': str(a.total_ttc), 'motif': a.motif}
            for a in obj.avoirs.all()
        ]

    class Meta:
        model = Facture
        fields = '__all__'
        read_only_fields = ['reference', 'created_by', 'fichier_pdf', 'date_emission',
                            'updated_at', 'updated_by']  # VX98 — server-side only

    def get_is_overdue(self, obj):
        # S'appuie sur jours_retard du modèle (échéance dépassée + reste dû,
        # hors payée/annulée) — cohérent avec FactureList, Relances et la
        # balance âgée, et couvre aussi le statut « En retard ».
        return obj.jours_retard > 0


class FactureWriteSerializer(serializers.ModelSerializer):
    """Création/modification sans lignes imbriquées."""
    class Meta:
        model = Facture
        exclude = ['reference', 'fichier_pdf']
        # company is force-assigned in perform_create — never accept it from the body.
        # XFAC29 : dgi_statut/reference/motif_rejet sont posés UNIQUEMENT par
        # `transmettre_facture` (action serveur), jamais depuis le corps.
        read_only_fields = [
            'created_by', 'date_emission', 'company',
            'dgi_statut', 'dgi_reference', 'dgi_motif_rejet',
        ]


class LigneAvoirSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = LigneAvoir
        fields = ['id', 'produit', 'designation', 'quantite', 'prix_unitaire',
                  'remise', 'taux_tva', 'total_ht']
        # DC10 — le produit est REQUIS à la création d'une ligne d'avoir (le FK
        # reste nullable en base pour les lignes historiques ; l'API exige un
        # produit sur toute NOUVELLE ligne).
        extra_kwargs = {'produit': {'required': True, 'allow_null': False}}


class AvoirSerializer(serializers.ModelSerializer):
    lignes = LigneAvoirSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    tva_par_taux = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    facture_reference = serializers.CharField(
        source='facture.reference', read_only=True)
    client_nom = serializers.SerializerMethodField()

    class Meta:
        model = Avoir
        fields = '__all__'
        read_only_fields = ['reference', 'created_by', 'fichier_pdf',
                            'date_emission', 'company']

    def get_tva_par_taux(self, obj):
        return [
            {'taux': str(b['taux']), 'base_ht': str(b['base_ht']),
             'montant': str(b['montant'])}
            for b in obj.tva_par_taux
        ]

    def get_client_nom(self, obj):
        c = obj.client
        return f"{c.nom} {c.prenom or ''}".strip() if c else None


class LigneNoteDebitSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        from .models import LigneNoteDebit
        model = LigneNoteDebit
        fields = ['id', 'produit', 'designation', 'quantite', 'prix_unitaire',
                  'remise', 'taux_tva', 'total_ht']


class NoteDebitSerializer(serializers.ModelSerializer):
    lignes = LigneNoteDebitSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    facture_reference = serializers.CharField(
        source='facture.reference', read_only=True)
    client_nom = serializers.SerializerMethodField()

    class Meta:
        from .models import NoteDebit
        model = NoteDebit
        fields = '__all__'
        read_only_fields = ['reference', 'created_by', 'fichier_pdf',
                            'date_emission', 'company']

    def get_client_nom(self, obj):
        c = obj.client
        return f"{c.nom} {c.prenom or ''}".strip() if c else None


class PromessePaiementSerializer(serializers.ModelSerializer):
    """XFAC5 — engagement de paiement client (« je paie le 15 »)."""
    facture_reference = serializers.CharField(
        source='facture.reference', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

    class Meta:
        from .models import PromessePaiement
        model = PromessePaiement
        fields = '__all__'
        read_only_fields = ['company', 'created_by', 'date_creation', 'statut']


class FollowupLevelSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import FollowupLevel
        model = FollowupLevel
        fields = ['id', 'ordre', 'nom', 'delai_jours', 'message',
                  'taux_interet_annuel', 'frais_fixes', 'canal']


class ParametrageRelanceClientSerializer(serializers.ModelSerializer):
    """ZFAC8 — réglage par client du responsable/mode de relance."""
    mode_display = serializers.CharField(
        source='get_mode_display', read_only=True)
    responsable_username = serializers.CharField(
        source='responsable.username', read_only=True, default=None)

    class Meta:
        from .models import ParametrageRelanceClient
        model = ParametrageRelanceClient
        fields = ['id', 'client', 'responsable', 'responsable_username',
                  'mode', 'mode_display', 'prochaine_relance_manuelle']
        read_only_fields = ['company']


class RelanceLogSerializer(serializers.ModelSerializer):
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

    class Meta:
        from .models import RelanceLog
        model = RelanceLog
        fields = ['id', 'facture', 'niveau', 'niveau_nom', 'note', 'canal',
                  'courrier_pdf_key', 'date', 'created_by_nom']
        read_only_fields = fields


class DevisActivitySerializer(serializers.ModelSerializer):
    """Chatter d'un devis (N25) — lecture seule côté API."""
    user_nom = serializers.CharField(
        source='user.username', read_only=True, default=None)

    class Meta:
        model = DevisActivity
        fields = ['id', 'devis', 'kind', 'field', 'field_label',
                  'old_value', 'new_value', 'body', 'user_nom', 'created_at']
        read_only_fields = fields


class FactureActivitySerializer(serializers.ModelSerializer):
    """Chatter d'une facture — lecture seule côté API."""
    user_nom = serializers.CharField(
        source='user.username', read_only=True, default=None)

    class Meta:
        from .models import FactureActivity
        model = FactureActivity
        fields = ['id', 'facture', 'kind', 'field', 'field_label',
                  'old_value', 'new_value', 'body', 'user_nom', 'created_at']
        read_only_fields = fields


class EmailLogSerializer(serializers.ModelSerializer):
    """Fil des emails (N87/N88) — lecture seule côté API."""
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

    class Meta:
        from .models import EmailLog
        model = EmailLog
        fields = ['id', 'direction', 'statut', 'client', 'devis', 'facture',
                  'to_email', 'from_email', 'sujet', 'corps', 'reference',
                  'piece_jointe', 'erreur', 'created_at', 'created_by_nom']
        read_only_fields = fields


# QJ16 — Preset serializer (company-scoped, read-only company field).
# Company is never accepted from the request body — forced server-side.

class DevisPresetSerializer(serializers.ModelSerializer):
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

    class Meta:
        model = DevisPreset
        fields = [
            'id', 'nom', 'description', 'mode_installation',
            'taux_tva', 'remise_globale', 'lignes_snapshot',
            'etude_params_snapshot', 'created_by_nom', 'created_at',
        ]
        read_only_fields = ['id', 'created_by_nom', 'created_at']


class RoofLayoutSerializer(serializers.ModelSerializer):
    """FG245 — Calepinage toiture (placement panneaux).

    ``panel_count`` et ``puissance_kwc`` sont en lecture seule : le compte est
    recalculé côté serveur depuis la géométrie (jamais accepté du corps de la
    requête). ``company`` et ``created_by`` sont forcés côté serveur dans le
    viewset, jamais désérialisés depuis la requête.
    """
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)
    puissance_kwc = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True)

    class Meta:
        model = RoofLayout
        fields = [
            'id', 'devis', 'nom',
            'largeur_m', 'hauteur_m', 'retrait_m',
            'module_largeur_m', 'module_hauteur_m', 'espacement_m',
            'orientation', 'puissance_module_wc',
            'panels', 'panel_count', 'puissance_kwc',
            'created_by_nom', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'panel_count', 'puissance_kwc',
            'created_by_nom', 'created_at', 'updated_at',
        ]


class FicheTechniqueSerializer(serializers.ModelSerializer):
    """FG254 / DC35 — fiche technique normalisée d'un module/onduleur.

    Ne porte QUE les paramètres électriques normalisés + un PDF datasheet : la
    marque/description/garantie/courbe restent sur ``Produit`` (jamais
    re-stockées ici). ``company`` et ``created_by`` sont forcés côté serveur
    dans le viewset, jamais désérialisés depuis la requête. On expose en
    lecture le nom du produit pour l'affichage, sans aucun prix.
    """
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

    class Meta:
        model = FicheTechnique
        fields = [
            'id', 'produit', 'produit_nom', 'type_fiche',
            'pmax_w', 'voc_v', 'isc_a', 'vmp_v', 'imp_a', 'coef_temp_voc',
            'datasheet_pdf',
            'created_by_nom', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'produit_nom', 'created_by_nom',
            'created_at', 'updated_at',
        ]


class LigneRemiseEncaissementSerializer(serializers.ModelSerializer):
    """XFSM19 — une ligne = un Paiement rattaché à la remise. Lecture seule
    des attributs utiles du paiement (montant/mode/date/facture) pour
    l'écran du responsable, sans jamais dupliquer le modèle Paiement."""
    montant = serializers.DecimalField(
        source='paiement.montant', max_digits=12, decimal_places=2,
        read_only=True)
    mode = serializers.CharField(source='paiement.mode', read_only=True)
    date_paiement = serializers.DateField(
        source='paiement.date_paiement', read_only=True)
    facture_reference = serializers.CharField(
        source='paiement.facture.reference', read_only=True, default=None)

    class Meta:
        model = LigneRemiseEncaissement
        fields = ['id', 'paiement', 'montant', 'mode', 'date_paiement',
                  'facture_reference']
        read_only_fields = ['id']


class RemiseEncaissementSerializer(serializers.ModelSerializer):
    lignes = LigneRemiseEncaissementSerializer(many=True, read_only=True)
    technicien_nom = serializers.CharField(
        source='technicien.username', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    montant_lignes = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    ecart = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = RemiseEncaissement
        fields = '__all__'
        read_only_fields = [
            'id', 'reference', 'fichier_pdf', 'created_by', 'date_creation',
            'company', 'cloture_par', 'date_cloture',
        ]


class MandatPaiementSerializer(serializers.ModelSerializer):
    """XCTR22 — mandat de prélèvement carte. `token` n'est JAMAIS accepté en
    écriture directe (posé uniquement par le service de tokenisation) ; seuls
    les 4 derniers chiffres/expiration sont exposés pour l'affichage."""
    client_nom = serializers.CharField(source='client.nom', read_only=True)

    class Meta:
        model = MandatPaiement
        fields = '__all__'
        read_only_fields = [
            'id', 'token', 'company', 'created_at', 'revoked_at',
        ]


class LignePrixListeSerializer(serializers.ModelSerializer):
    """XSAL1 — jamais `prix_achat` : seul `prix_unitaire` (prix négocié) est
    exposé, `produit` reste une simple string-FK id."""
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)

    class Meta:
        model = LignePrixListe
        fields = ['id', 'liste', 'produit', 'produit_nom', 'prix_unitaire']
        read_only_fields = ['id']


class RegleListePrixSerializer(serializers.ModelSerializer):
    """XSAL2 — règle de prix / palier de quantité."""
    class Meta:
        model = RegleListePrix
        fields = [
            'id', 'liste', 'produit', 'categorie_nom', 'marque',
            'type_regle', 'valeur', 'quantite_min', 'priorite', 'actif',
        ]
        read_only_fields = ['id']


class ListePrixSerializer(serializers.ModelSerializer):
    """XSAL1/XSAL2 — liste de prix clients + ses règles de paliers.
    `company` toujours forcée côté serveur (jamais acceptée du body — voir
    ListePrixViewSet.perform_create)."""
    lignes = LignePrixListeSerializer(many=True, read_only=True)
    regles = RegleListePrixSerializer(many=True, read_only=True)
    est_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = ListePrix
        fields = [
            'id', 'company', 'nom', 'devise', 'date_debut', 'date_fin',
            'archived', 'created_at', 'lignes', 'regles', 'est_active',
        ]
        read_only_fields = ['id', 'company', 'created_at']
