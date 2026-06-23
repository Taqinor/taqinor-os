from rest_framework import serializers
from .models import (
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
    Avoir, LigneAvoir, DevisActivity,
)


class LigneDevisSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = LigneDevis
        fields = '__all__'

    def create(self, validated_data):
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
                from apps.ventes.utils.company_settings import tva_standard
                company = getattr(validated_data.get('devis'), 'company', None)
                validated_data['taux_tva'] = tva_standard(company)
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
    # Contexte « quote-aware » du lead lié (profil énergétique) — lecture seule,
    # pour un aperçu au survol dans la liste des devis. None si pas de lead.
    lead_facture_hiver = serializers.SerializerMethodField()
    lead_type_installation = serializers.SerializerMethodField()

    def get_lead_facture_hiver(self, obj):
        return str(obj.lead.facture_hiver) if obj.lead_id and \
            obj.lead.facture_hiver is not None else None

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
        return [
            {
                'id': f.id,
                'reference': f.reference,
                'statut': f.statut,
                'statut_display': f.get_statut_display(),
                'type_facture': f.type_facture,
            }
            for f in obj.factures.all().order_by('reference')
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

    class Meta:
        model = Devis
        fields = '__all__'
        read_only_fields = ['reference', 'created_by', 'fichier_pdf', 'date_creation']


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
        read_only_fields = ['created_by', 'date_creation', 'company']
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
                from apps.ventes.utils.company_settings import tva_standard
                company = getattr(validated_data.get('facture'), 'company', None)
                validated_data['taux_tva'] = tva_standard(company)
        return super().create(validated_data)


class PaiementSerializer(serializers.ModelSerializer):
    mode_display = serializers.CharField(source='get_mode_display', read_only=True)
    # Champs d'affichage (lecture seule) pour la page Encaissements : référence
    # de la facture, nom du client et auteur de l'encaissement (« par qui »).
    facture_reference = serializers.CharField(
        source='facture.reference', read_only=True, default=None)
    client_nom = serializers.CharField(
        source='facture.client.nom', read_only=True, default=None)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

    class Meta:
        model = Paiement
        fields = '__all__'
        # company/created_by forcés côté serveur — jamais depuis le corps.
        read_only_fields = ['company', 'created_by', 'date_creation', 'facture']


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
        read_only_fields = ['reference', 'created_by', 'fichier_pdf', 'date_emission']

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
        read_only_fields = ['created_by', 'date_emission', 'company']


class LigneAvoirSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = LigneAvoir
        fields = ['id', 'produit', 'designation', 'quantite', 'prix_unitaire',
                  'remise', 'taux_tva', 'total_ht']


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


class FollowupLevelSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import FollowupLevel
        model = FollowupLevel
        fields = ['id', 'ordre', 'nom', 'delai_jours', 'message']


class RelanceLogSerializer(serializers.ModelSerializer):
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

    class Meta:
        from .models import RelanceLog
        model = RelanceLog
        fields = ['id', 'facture', 'niveau', 'niveau_nom', 'note', 'date',
                  'created_by_nom']
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
