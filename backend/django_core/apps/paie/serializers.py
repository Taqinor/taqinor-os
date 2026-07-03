"""Sérialiseurs de la Paie marocaine.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import (
    AdhesionMutuelle,
    AvanceSalarie,
    BaremeIR,
    BulletinPaie,
    CumulAnnuel,
    EcheanceDeclarative,
    ElementVariable,
    LigneBulletin,
    LigneVirement,
    OrdreVirement,
    ParametrePaie,
    PeriodePaie,
    ProfilPaie,
    RegimeMutuelle,
    Rubrique,
    RubriqueEmploye,
    SaisieArret,
    TrancheIR,
)


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur."""
    request = serializer.context.get('request')
    if value is not None and request is not None:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


class ParametrePaieSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametrePaie
        fields = [
            'id', 'date_effet', 'smig', 'smag', 'plafond_cnss',
            'taux_cnss_salarial', 'taux_cnss_patronal', 'taux_amo_salarial',
            'taux_amo_patronal', 'taux_allocations_familiales',
            'taux_formation_pro',
            'seuil_frais_pro', 'taux_frais_pro_bas', 'plafond_frais_pro_bas',
            'taux_frais_pro_haut', 'plafond_frais_pro_haut',
            'deduction_par_personne_a_charge', 'plafond_personnes_a_charge',
            # PAIE14 — Taux de majoration HS (éditables par société).
            'taux_hs_jour', 'taux_hs_nuit', 'taux_hs_ferie',
            'actif', 'valide_par_fondateur', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class RubriqueSerializer(serializers.ModelSerializer):
    """Sérialiseur de la rubrique paramétrable (PAIE6).

    ``company`` n'est jamais exposée : posée côté serveur par le
    ``TenantMixin``. Le couple ``(company, code)`` étant unique, l'unicité du
    ``code`` est validée à l'enregistrement (DB) ; ``code`` reste éditable.
    """
    class Meta:
        model = Rubrique
        fields = [
            'id', 'code', 'libelle', 'type', 'imposable', 'soumis_cnss',
            'soumis_amo', 'soumis_cimr',
            # PAIE16 — avantage en nature + plafond mensuel d'exonération.
            'avantage_nature', 'plafond_exoneration',
            'compte', 'base', 'taux',
            'montant_fixe', 'ordre', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_code(self, value):
        """``code`` unique par société (``company`` posée côté serveur).

        ``company`` n'étant pas un champ du sérialiseur, DRF n'ajoute pas le
        ``UniqueTogetherValidator`` automatique : on vérifie l'unicité ici pour
        renvoyer un 400 propre plutôt qu'une ``IntegrityError`` 500.
        """
        request = self.context.get('request')
        if request is None:
            return value
        qs = Rubrique.objects.filter(
            company=request.user.company_id, code=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'Une rubrique avec ce code existe déjà.')
        return value


class TrancheIRSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrancheIR
        fields = [
            'id', 'borne_min', 'borne_max', 'taux', 'somme_a_deduire', 'ordre',
        ]


class BaremeIRSerializer(serializers.ModelSerializer):
    tranches = TrancheIRSerializer(many=True)

    class Meta:
        model = BaremeIR
        fields = [
            'id', 'libelle', 'date_effet', 'actif', 'valide_par_fondateur',
            'tranches', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def create(self, validated_data):
        tranches = validated_data.pop('tranches', [])
        company = validated_data['company']
        bareme = BaremeIR.objects.create(**validated_data)
        for tranche in tranches:
            TrancheIR.objects.create(
                bareme=bareme, company=company, **tranche)
        return bareme

    def update(self, instance, validated_data):
        tranches = validated_data.pop('tranches', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tranches is not None:
            instance.tranches.all().delete()
            for tranche in tranches:
                TrancheIR.objects.create(
                    bareme=instance, company=instance.company, **tranche)
        return instance


class ProfilPaieSerializer(serializers.ModelSerializer):
    """Profil de paie d'un employé (PAIE8).

    ``company`` posée côté serveur. ``employe`` (FK ``rh.DossierEmploye``) est
    validé comme appartenant à la société de l'utilisateur via le sélecteur RH
    (cross-app), sans importer ``rh.models``.
    """
    employe_nom = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProfilPaie
        fields = [
            'id', 'employe', 'employe_nom', 'type_remuneration', 'salaire_base',
            'jours_travail_mensuel', 'heures_travail_mensuel',
            'affilie_cnss', 'affilie_amo', 'affilie_cimr', 'taux_cimr_salarial',
            'numero_cnss', 'numero_amo', 'numero_cimr', 'rib', 'banque',
            'mode_paiement', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_employe_nom(self, obj):
        emp = obj.employe
        return f'{emp.nom} {emp.prenom}'.strip() if emp else ''

    def validate_employe(self, value):
        """``employe`` doit appartenir à la société de l'utilisateur (RH)."""
        from apps.rh import selectors as rh_selectors

        request = self.context.get('request')
        if value is not None and request is not None:
            if not rh_selectors.dossier_appartient_societe(
                    request.user.company, value.id):
                raise serializers.ValidationError('Employé inconnu.')
        return value


class RegimeMutuelleSerializer(serializers.ModelSerializer):
    """Régime de mutuelle/prévoyance/assurance groupe (XPAI3)."""

    class Meta:
        model = RegimeMutuelle
        fields = [
            'id', 'libelle', 'mode', 'palier', 'part_salariale',
            'part_patronale', 'deductible_net_imposable', 'actif',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class AdhesionMutuelleSerializer(serializers.ModelSerializer):
    """Adhésion d'un profil à un régime de mutuelle (XPAI3).

    ``company`` posée côté serveur ; ``profil`` et ``regime`` validés comme
    appartenant à la société de l'utilisateur.
    """
    regime_libelle = serializers.CharField(
        source='regime.libelle', read_only=True)

    class Meta:
        model = AdhesionMutuelle
        fields = [
            'id', 'profil', 'regime', 'regime_libelle', 'date_debut',
            'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_profil(self, value):
        return _meme_societe(self, value, 'Profil')

    def validate_regime(self, value):
        return _meme_societe(self, value, 'Régime')


class RubriqueEmployeSerializer(serializers.ModelSerializer):
    """Rubrique récurrente rattachée à un profil de paie (PAIE9).

    ``company`` posée côté serveur ; ``profil`` et ``rubrique`` sont validés
    comme appartenant à la société de l'utilisateur.
    """
    rubrique_code = serializers.CharField(
        source='rubrique.code', read_only=True)

    class Meta:
        model = RubriqueEmploye
        fields = [
            'id', 'profil', 'rubrique', 'rubrique_code', 'montant', 'taux',
            'date_debut', 'date_fin', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_profil(self, value):
        return _meme_societe(self, value, 'Profil')

    def validate_rubrique(self, value):
        return _meme_societe(self, value, 'Rubrique')


class PeriodePaieSerializer(serializers.ModelSerializer):
    """Période de paie (run mensuel, PAIE10).

    Le ``statut`` est en LECTURE SEULE depuis le sérialiseur : il n'avance que
    par l'action dédiée ``changer-statut`` (cycle progressif côté service).
    """
    class Meta:
        model = PeriodePaie
        fields = [
            'id', 'annee', 'mois', 'type_run', 'libelle', 'statut',
            'date_paiement', 'date_cloture', 'date_creation',
        ]
        read_only_fields = ['statut', 'date_cloture', 'date_creation']

    def validate(self, attrs):
        """Unicité ``(company, annee, mois, type_run)`` — ``company`` côté serveur.

        ``company`` n'étant pas un champ du sérialiseur, DRF ne pose pas de
        ``UniqueTogetherValidator`` ; on vérifie ici pour renvoyer un 400 propre
        plutôt qu'une ``IntegrityError`` 500. XPAI4 — un run hors-cycle peut
        coexister avec le run mensuel du même (année, mois) : le
        ``type_run`` fait partie de la clé.
        """
        request = self.context.get('request')
        annee = attrs.get('annee', getattr(self.instance, 'annee', None))
        mois = attrs.get('mois', getattr(self.instance, 'mois', None))
        type_run = attrs.get(
            'type_run', getattr(self.instance, 'type_run', PeriodePaie.TYPE_RUN_MENSUEL))
        if request is not None and annee is not None and mois is not None:
            qs = PeriodePaie.objects.filter(
                company=request.user.company_id, annee=annee, mois=mois,
                type_run=type_run)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'Une période existe déjà pour cette année, ce mois et ce type de run.')
        return attrs


class EcheanceDeclarativeSerializer(serializers.ModelSerializer):
    """Échéance déclarative (XPAI6) — générée automatiquement, lecture

    principale ; ``statut`` reste modifiable (progression manuelle du
    traitement réel de la déclaration).
    """
    en_retard = serializers.ReadOnlyField()

    class Meta:
        model = EcheanceDeclarative
        fields = [
            'id', 'periode', 'type_echeance', 'date_limite', 'statut',
            'date_notification', 'date_creation', 'en_retard',
        ]
        read_only_fields = [
            'periode', 'type_echeance', 'date_limite', 'date_notification',
            'date_creation',
        ]


class ElementVariableSerializer(serializers.ModelSerializer):
    """Élément variable du mois (PAIE11).

    ``company`` posée côté serveur ; ``periode``, ``profil`` et ``rubrique``
    validés comme appartenant à la société de l'utilisateur.
    """
    class Meta:
        model = ElementVariable
        fields = [
            'id', 'periode', 'profil', 'type', 'rubrique', 'libelle',
            # PAIE14 — categorie_hs : 'jour'|'nuit'|'ferie' (ignoré hors HS).
            'quantite', 'categorie_hs', 'montant',
            # PAIE26 — drapeaux d'absence (rémunérée / décompte du solde).
            'remunere', 'deduit_solde',
            'source', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_periode(self, value):
        return _meme_societe(self, value, 'Période')

    def validate_profil(self, value):
        return _meme_societe(self, value, 'Profil')

    def validate_rubrique(self, value):
        return _meme_societe(self, value, 'Rubrique')


class LigneBulletinSerializer(serializers.ModelSerializer):
    """Ligne d'un bulletin (PAIE17) — snapshot figé, lecture seule."""

    class Meta:
        model = LigneBulletin
        fields = ['id', 'code', 'libelle', 'type', 'montant', 'ordre']
        read_only_fields = fields


class BulletinPaieSerializer(serializers.ModelSerializer):
    """Bulletin de paie matérialisé (PAIE17).

    Snapshot en LECTURE SEULE : les montants sont posés par
    ``services.generer_bulletin`` (jamais via l'API) et figés à la validation.
    Le bulletin se crée/recalcule par l'action ``generer`` et se fige par
    l'action ``valider`` — pas d'écriture directe des montants.
    """
    lignes = LigneBulletinSerializer(many=True, read_only=True)

    class Meta:
        model = BulletinPaie
        fields = [
            'id', 'periode', 'profil', 'statut',
            'type_bulletin', 'rectifie', 'motif', 'personnes_a_charge',
            'brut', 'brut_imposable', 'cnss_salariale', 'cnss_patronale',
            'amo_salariale', 'amo_patronale', 'allocations_familiales',
            'formation_professionnelle', 'provision_conges', 'cimr_salariale',
            'frais_professionnels', 'net_imposable', 'ir', 'retenues',
            'prime_anciennete', 'charges_patronales', 'net_a_payer',
            'provision_conges',
            'date_validation', 'date_creation', 'lignes',
            'paye', 'date_paiement',
        ]
        read_only_fields = fields


class AvanceSalarieSerializer(serializers.ModelSerializer):
    """Avance / prêt salarié remboursé par déduction mensuelle (PAIE28).

    ``company`` posée côté serveur ; ``profil`` validé comme appartenant à la
    société de l'utilisateur. ``montant_rembourse`` est en LECTURE SEULE : il
    n'est jamais saisi côté client, il est incrémenté par le service à la
    validation des bulletins (``appliquer_remboursements_avances``). Les
    propriétés ``solde_restant`` / ``soldee`` sont exposées en lecture.
    """
    solde_restant = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    soldee = serializers.BooleanField(read_only=True)

    class Meta:
        model = AvanceSalarie
        fields = [
            'id', 'profil', 'type', 'libelle', 'montant_total',
            'montant_echeance', 'nombre_echeances', 'montant_rembourse',
            'solde_restant', 'soldee', 'date_debut', 'actif', 'date_creation',
        ]
        read_only_fields = ['montant_rembourse', 'date_creation']

    def validate_profil(self, value):
        return _meme_societe(self, value, 'Profil')


class LigneVirementSerializer(serializers.ModelSerializer):
    """Ligne d'un ordre de virement (PAIE30) — lecture seule."""

    class Meta:
        model = LigneVirement
        fields = [
            'id', 'bulletin', 'beneficiaire', 'rib', 'montant', 'reference',
            'rejetee', 'motif_rejet', 'date_rejet', 'ligne_correction',
        ]
        read_only_fields = fields


class OrdreVirementSerializer(serializers.ModelSerializer):
    """Ordre de virement des salaires d'une période (PAIE30) — lecture seule.

    Construit/regénéré par l'action ``generer`` (depuis les bulletins validés)
    et figé par ``emettre``. Société scopée, palier paie. Les lignes sont
    imbriquées.
    """
    lignes = LigneVirementSerializer(many=True, read_only=True)
    # DC20 — compte émetteur résolu depuis le référentiel `compta.CompteTresorerie`
    # (libellé + banque) pour l'affichage, sans re-saisir le RIB.
    compte_emetteur_libelle = serializers.CharField(
        source='compte_emetteur.libelle', read_only=True, default='')
    compte_emetteur_banque = serializers.CharField(
        source='compte_emetteur.banque', read_only=True, default='')

    class Meta:
        model = OrdreVirement
        fields = [
            'id', 'periode', 'reference', 'libelle', 'statut',
            'date_execution', 'compte_emetteur', 'compte_emetteur_libelle',
            'compte_emetteur_banque', 'rib_emetteur', 'devise', 'total',
            'nombre_lignes', 'date_emission', 'date_creation', 'lignes',
        ]
        read_only_fields = fields


class SaisieArretSerializer(serializers.ModelSerializer):
    """Saisie-arrêt / cession sur salaire (PAIE29).

    ``company`` posée côté serveur ; ``profil`` validé société. ``montant_retenu``
    est en LECTURE SEULE (cumulé par le service à la validation des bulletins).
    Les propriétés ``solde_restant`` / ``soldee`` sont exposées en lecture.
    """
    solde_restant = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    soldee = serializers.BooleanField(read_only=True)

    class Meta:
        model = SaisieArret
        fields = [
            'id', 'profil', 'type', 'creancier', 'reference', 'montant_total',
            'montant_echeance', 'montant_retenu', 'solde_restant', 'soldee',
            'prioritaire', 'date_debut', 'actif', 'date_creation',
        ]
        read_only_fields = ['montant_retenu', 'date_creation']

    def validate_profil(self, value):
        return _meme_societe(self, value, 'Profil')


class CumulAnnuelSerializer(serializers.ModelSerializer):
    """Cumul annuel de paie d'un employé (PAIE27) — LECTURE SEULE.

    Agrégat recalculé depuis les bulletins validés par
    ``services.recalculer_cumul_annuel`` (jamais saisi via l'API). Société
    scopée, palier paie uniquement (donnée SENSIBLE).
    """
    class Meta:
        model = CumulAnnuel
        fields = [
            'id', 'profil', 'annee', 'brut', 'brut_imposable', 'net_imposable',
            'ir', 'cnss_salariale', 'amo_salariale', 'cimr_salariale',
            'frais_professionnels', 'net_a_payer', 'charges_patronales',
            'provision_conges', 'conges_acquis', 'conges_pris',
            'nombre_bulletins', 'date_calcul', 'date_creation',
        ]
        read_only_fields = fields
