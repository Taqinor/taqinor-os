"""Sérialiseurs de facturation de ventes (BC, factures, paiements, avoirs,
notes de débit, relances, remises, mandats) — déplacés tels quels de
`serializers.py` par SPL148 (move only, sans ré-export)."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from .models import (
    BonCommande, Facture, LigneFacture, Paiement,
    Avoir, LigneAvoir,
    RemiseEncaissement, LigneRemiseEncaissement,
    MandatPaiement,
)
from .serializers import _fallback_taux_tva


class BonCommandeSerializer(serializers.ModelSerializer):
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    devis_reference = serializers.CharField(source='devis.reference', read_only=True, default=None)
    has_facture = serializers.SerializerMethodField()
    # AUD118 — DISTINCT de `has_facture` : une facture ANNULÉE ne bloque plus
    # rien. `has_facture` reste le prédicat « une facture a déjà été émise »
    # (il gouverne le bouton « Facture », dont la garde serveur ne filtre pas
    # le statut) ; `facture_active` est le prédicat « une facture VIVANTE est
    # attachée », qui gouverne le bouton « Annuler ».
    facture_active = serializers.SerializerMethodField()
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
        # AUD506 — ``statut`` en lecture seule : BonCommandeViewSet n'a AUCUN
        # perform_update, un PATCH brut faisait donc passer un BC directement
        # en_attente→livre sans réservation stock ni preuve de livraison.
        # CONFIRME/LIVRE/ANNULE passent désormais UNIQUEMENT par leurs actions
        # dédiées (confirmer/marquer-livre/annuler), qui posent le statut
        # directement sur le modèle (hors de ce sérialiseur).
        read_only_fields = ['reference', 'date_creation', 'company',
                            'pv_livraison', 'date_livraison_reelle',
                            'statut']

    def get_has_facture(self, obj):
        # AUD115 — lit l'annotation `Exists` posée par le viewset quand elle
        # est là (un seul aller-retour pour toute la page) ; repli sur la
        # requête historique pour les appelants qui sérialisent une instance
        # nue (détail, tests, autres vues).
        annote = getattr(obj, 'has_facture_annote', None)
        if annote is not None:
            return bool(annote)
        return Facture.objects.filter(bon_commande=obj).exists()

    @extend_schema_field(serializers.BooleanField())
    def get_facture_active(self, obj):
        # AUD118 — même annotation servie par le viewset, filtrée sur les
        # factures NON annulées : c'est elle qui décide si l'annulation du BC
        # est encore possible.
        annote = getattr(obj, 'facture_active_annote', None)
        if annote is not None:
            return bool(annote)
        return (Facture.objects
                .filter(bon_commande=obj)
                .exclude(statut=Facture.Statut.ANNULEE)
                .exists())

    def _totaux(self, obj):
        """AUD115 — LES TROIS TOTAUX EN UN SEUL PASSAGE. Chacun des trois
        `get_total_*` traversait la chaîne canonique du devis de bout en bout
        (`_totaux_argent()`), soit trois parcours complets des lignes par bon
        de commande. On mémoïse la chaîne sur l'instance : la SOURCE des
        chiffres ne change pas d'un centime, seul le nombre de parcours."""
        if not obj.devis_id:
            return None
        totaux = getattr(obj, '_aud115_totaux', None)
        if totaux is None:
            from .domain.argent import Vue, totaux as _chaine
            totaux = _chaine(obj.devis, vue=Vue.NET)
            obj._aud115_totaux = totaux
        return totaux

    def get_total_ht(self, obj):
        totaux = self._totaux(obj)
        return str(totaux.ht_net) if totaux is not None else None

    def get_total_tva(self, obj):
        totaux = self._totaux(obj)
        return str(totaux.tva) if totaux is not None else None

    def get_total_ttc(self, obj):
        totaux = self._totaux(obj)
        return str(totaux.ttc) if totaux is not None else None


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
    # AUD132 (PAY-10) — l'écran Encaissements n'avait AUCUNE colonne statut :
    # un paiement rejeté (chèque impayé) y était affiché comme un encaissement
    # valide. Le libellé est servi ici pour que l'écran ne le réinvente pas.
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

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
        #
        # AUD134 — `fields='__all__'` laissait SEPT champs de plus en écriture.
        # `enregistrer-paiement` fait `PaiementSerializer(data=request.data)`
        # puis `save(facture=…, company=…, created_by=…, escompte_montant=…)` :
        # tout champ non surchargé passait tel quel. Concrètement, un corps
        # pouvait poser `statut='rejete'` — contournant l'action `rejeter` et
        # sa permission `IsResponsableOrAdmin` — et un `client` pointant sur
        # une AUTRE société. Chacun de ces champs a son propriétaire serveur :
        #   - `client`             → résolu depuis la facture, ou scopé société
        #                            sur le chemin avance (`enregistrer-avance`
        #                            passe par `crm.selectors.client_base_qs`) ;
        #   - `statut` + `motif_rejet`/`frais_rejet`/`date_rejet`
        #                          → l'action `rejeter` (YLEDG5) et elle seule ;
        #   - `statut_affectation` → le service de ventilation (XFAC1) ;
        #   - `provider_ref`       → le webhook PSP.
        read_only_fields = ['company', 'created_by', 'date_creation', 'facture',
                            'escompte_montant', 'client', 'statut',
                            'statut_affectation', 'provider_ref',
                            'motif_rejet', 'frais_rejet', 'date_rejet']


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
    # ERR-QAH-VENTES-FACTURES-KPI-ENCAISSER — reste dû AFFICHÉ : 0 pour une
    # facture payée ou annulée (plus de « Dû » ni d'« Encaisser » sur une ligne
    # soldée), sinon ``Facture.montant_du``. Même règle que ``kpis_factures``.
    montant_du = serializers.SerializerMethodField()
    # CIQ214 — reste EXIGIBLE (retenue de garantie non libérée exclue).
    montant_exigible = serializers.SerializerMethodField()
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
                            'updated_at', 'updated_by',  # VX98 — server-side only
                            # ARRONDI-100 — hérités du devis côté serveur.
                            'arrondi_pas', 'arrondi_unites',
                            # CIQ214 — posés par la tranche / ``liberer-retenue``.
                            'retenue_garantie_mad', 'retenue_liberee_le',
                            # ATOT5 — clé de tranche posée par le serveur.
                            'cle_tranche']

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))
    def get_montant_du(self, obj):
        from decimal import Decimal
        if obj.statut in (Facture.Statut.PAYEE, Facture.Statut.ANNULEE):
            return '0.00'
        return str(Decimal(obj.montant_du).quantize(Decimal('0.01')))

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))
    def get_montant_exigible(self, obj):
        """CIQ214 — ``montant_du`` moins la retenue de garantie non
        libérée : ce que les relances réclament."""
        from decimal import Decimal
        if obj.statut in (Facture.Statut.PAYEE, Facture.Statut.ANNULEE):
            return '0.00'
        return str(Decimal(obj.montant_exigible).quantize(Decimal('0.01')))

    def get_is_overdue(self, obj):
        # S'appuie sur jours_retard du modèle (échéance dépassée + reste dû,
        # hors payée/annulée) — cohérent avec FactureList, Relances et la
        # balance âgée. ERR-QAH-VENTES-FACTURES-KPI-ENCAISSER : une facture au
        # STATUT « En retard » (même sans échéance) l'est aussi tant qu'un reste
        # est dû — l'onglet « En retard » et la tuile KPI la voient.
        if obj.jours_retard > 0:
            return True
        return obj.statut == Facture.Statut.EN_RETARD and obj.montant_du > 0


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
            # CIQ215 — ventilation posée par le serveur à la création d'une
            # tranche, jamais depuis le corps.
            'ventilation_tva',
            # ATOT5 — clé de tranche posée par le serveur, jamais le corps.
            'cle_tranche',
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
                            'date_emission', 'company',
                            # ARRONDI-100 — repris de la facture côté serveur.
                            'arrondi_pas', 'arrondi_unites']

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
    """XFAC5 — engagement de paiement client (« je paie le 15 »).

    AUD133 — ``date_promise`` n'était BORNÉE nulle part : la valeur du corps
    était écrite telle quelle dans ``facture.exclu_relances_jusquau``, et
    ``relance_reminders`` exclut ``exclu_relances_jusquau__gte=today``. Une
    promesse au 31/12/2030 gelait donc la relance pour toujours. Elle doit
    désormais être FUTURE et rester sous le plafond société
    (``recouvrement.PROMESSE_HORIZON_JOURS_MAX``, 90 j par défaut).
    """
    facture_reference = serializers.CharField(
        source='facture.reference', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

    def validate_date_promise(self, value):
        from datetime import timedelta

        from .recouvrement import PROMESSE_HORIZON_JOURS_MAX
        from .scheduled import casablanca_today

        today = casablanca_today()
        if value <= today:
            raise serializers.ValidationError(
                "Une promesse de paiement porte sur une date FUTURE.")
        plafond = today + timedelta(days=PROMESSE_HORIZON_JOURS_MAX)
        if value > plafond:
            raise serializers.ValidationError(
                f'Une promesse ne peut pas dépasser {PROMESSE_HORIZON_JOURS_MAX} '
                f'jours (soit le {plafond.isoformat()}) : au-delà, elle gèle la '
                f'relance au lieu d\'engager le client.')
        return value

    class Meta:
        from .models import PromessePaiement
        model = PromessePaiement
        fields = '__all__'
        read_only_fields = ['company', 'created_by', 'date_creation', 'statut']


class RelancerFactureSerializer(serializers.Serializer):
    """AUD131 (PAY-18) — validation du corps de l'action ``relancer``.

    Le corps était lu à cru : `niveau` non validé (un ordre inexistant laissait
    `lvl` à None et la relance était consignée quand même) et
    `prochaine_relance` affecté brut à la facture (une chaîne non-date
    remontait en erreur base — un 500 — au lieu d'un 400).

    La société est passée en contexte : un `niveau` est un ORDRE de
    ``FollowupLevel``, résolu et donc scopé à la société de la facture.
    """
    niveau = serializers.IntegerField(required=False, allow_null=True)
    note = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=True,
        max_length=2000)
    prochaine_relance = serializers.DateField(
        required=False, allow_null=True)
    envoyer_email = serializers.BooleanField(default=False)

    def validate_niveau(self, value):
        if value is None:
            return value
        from .models import FollowupLevel
        company = self.context.get('company')
        niveau = FollowupLevel.objects.filter(
            company=company, ordre=value).first()
        if niveau is None:
            raise serializers.ValidationError(
                'Niveau de relance inconnu pour cette société.')
        self.context['followup_level'] = niveau
        return value


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
