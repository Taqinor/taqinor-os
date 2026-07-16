"""Sérialiseur du profil entreprise (``CompanyProfileSerializer``).

Domaine « Société & identité / Devis & logique métier ». Extrait de l'ancien
``serializers.py`` sans aucun changement de champ, de validation ni de
comportement (mêmes URLs présignées, mêmes contrôles de société)."""
from decimal import Decimal

from rest_framework import serializers

from .models import CompanyProfile


class CompanyProfileSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    signature_url = serializers.SerializerMethodField()
    responsable_defaut_leads_nom = serializers.CharField(
        source='responsable_defaut_leads.username', read_only=True
    )
    default_installer_nom = serializers.CharField(
        source='default_installer.username', read_only=True
    )
    # SCA46 — consentement au benchmarking anonymisé agrégé. Le champ VIT sur
    # ``authentication.Company`` (le consentement est une donnée du tenant, pas
    # du profil d'affichage) ; exposé ici en LECTURE pour l'écran Paramètres.
    # L'écriture passe par ``views_profile.update_profile`` (posée côté serveur
    # sur la société de l'appelant, auditée) — jamais par un setattr nested.
    benchmarking_opt_in = serializers.SerializerMethodField()

    def get_benchmarking_opt_in(self, obj):
        company = getattr(obj, 'company', None)
        return bool(getattr(company, 'benchmarking_opt_in', False))

    class Meta:
        model = CompanyProfile
        fields = '__all__'
        # ERR25 — ``company`` est l'ancre multi-tenant du profil : la repointer
        # via un PATCH `{"company": <autre_id>}` détournerait le profil de
        # l'appelant. Elle est posée côté serveur (jamais depuis le corps).
        read_only_fields = ['logo_key', 'signature_key', 'company']

    def validate_responsable_defaut_leads(self, value):
        # Le responsable par défaut doit appartenir à la même société.
        request = self.context.get('request')
        if value and request and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Utilisateur inconnu.')
        return value

    def validate_default_installer(self, value):
        # L'installateur par défaut doit appartenir à la même société.
        request = self.context.get('request')
        if value and request and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Utilisateur inconnu.')
        return value

    def _validate_tva(self, value, label):
        # Garde-fou TVA (L769) : un taux ne peut pas être laissé VIDE et
        # re-snappé silencieusement au défaut (20/10). Un 0 DÉLIBÉRÉ est
        # parfaitement valide et préservé tel quel ; seul le vide est rejeté.
        if value is None:
            raise serializers.ValidationError(
                f'Le taux de {label} est obligatoire (laissez 0 pour exonéré).')
        if value < 0 or value > 100:
            raise serializers.ValidationError(
                f'Le taux de {label} doit être compris entre 0 et 100 %.')
        return value

    def validate_tva_standard(self, value):
        return self._validate_tva(value, 'TVA standard')

    def validate_tva_panneaux(self, value):
        return self._validate_tva(value, 'TVA panneaux')

    # ── ERR55 — garde-fous de plage sur les pourcentages éditables. Un taux
    # négatif ou > 100 % entrerait sinon directement dans le calcul des
    # devis/factures. NULL reste autorisé (champ optionnel/désactivé) ; seules
    # les valeurs RENSEIGNÉES sont bornées à [0, 100].
    def _validate_pct(self, value, label):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError(
                f'{label} doit être compris entre 0 et 100 %.')
        return value

    def validate_remise_max_pct(self, value):
        return self._validate_pct(value, 'La limite de remise')

    def validate_discount_approval_threshold(self, value):
        return self._validate_pct(value, "Le seuil d'approbation de remise")

    def validate_overage_seuil_pct(self, value):
        return self._validate_pct(value, 'Le seuil de dépassement')

    # Seuils de régime loi 82-21 (kWc) : non négatifs (NULL non permis par le
    # modèle, mais on borne défensivement les valeurs entrantes).
    def _validate_non_negative(self, value, label):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                f'{label} ne peut pas être négatif.')
        return value

    def validate_seuil_regime_declaration_kwc(self, value):
        return self._validate_non_negative(
            value, 'Le seuil de déclaration (kWc)')

    def validate_seuil_regime_anre_kwc(self, value):
        return self._validate_non_negative(value, 'Le seuil ANRE (kWc)')

    # ── ERR55 — forme des champs JSON. Une forme corrompue (liste, scalaire,
    # clés/valeurs invalides) casserait la numérotation ou l'échéancier en
    # silence. NULL reste autorisé (= repli sur le défaut historique).
    _DOC_KEYS = {'devis', 'facture', 'avoir', 'bon_commande'}
    _RESET_VALUES = {'monthly', 'yearly', 'none'}

    def validate_doc_prefixes(self, value):
        if value is None:
            return value
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'Les préfixes doivent être un objet {clé: préfixe}.')
        for key, prefix in value.items():
            if key not in self._DOC_KEYS:
                raise serializers.ValidationError(
                    f'Clé de préfixe inconnue : {key}.')
            if not isinstance(prefix, str):
                raise serializers.ValidationError(
                    f'Le préfixe « {key} » doit être une chaîne.')
        return value

    def validate_doc_numbering(self, value):
        if value is None:
            return value
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'La numérotation doit être un objet {clé: {padding, reset}}.')
        for key, cfg in value.items():
            if key not in self._DOC_KEYS:
                raise serializers.ValidationError(
                    f'Clé de numérotation inconnue : {key}.')
            if not isinstance(cfg, dict):
                raise serializers.ValidationError(
                    f'La configuration « {key} » doit être un objet.')
            padding = cfg.get('padding')
            if padding is not None and (
                    not isinstance(padding, int) or isinstance(padding, bool)
                    or padding < 1 or padding > 12):
                raise serializers.ValidationError(
                    f'Le remplissage (padding) de « {key} » doit être un '
                    'entier entre 1 et 12.')
            reset = cfg.get('reset')
            if reset is not None and reset not in self._RESET_VALUES:
                raise serializers.ValidationError(
                    f'La réinitialisation de « {key} » doit valoir '
                    'monthly, yearly ou none.')
        return value

    def validate_payment_terms(self, value):
        if value is None:
            return value
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "L'échéancier doit être un objet {mode: {acompte, materiel, "
                'solde}}.')
        for mode, terms in value.items():
            if not isinstance(terms, dict):
                raise serializers.ValidationError(
                    f"L'échéancier du mode « {mode} » doit être un objet.")
            total = Decimal('0')
            for part, pct in terms.items():
                try:
                    pct_d = Decimal(str(pct))
                except (TypeError, ValueError, ArithmeticError):
                    raise serializers.ValidationError(
                        f'« {mode}.{part} » doit être un pourcentage numérique.')
                if pct_d < 0 or pct_d > 100:
                    raise serializers.ValidationError(
                        f'« {mode}.{part} » doit être compris entre 0 et '
                        '100 %.')
                total += pct_d
            if total > 100:
                raise serializers.ValidationError(
                    f"L'échéancier du mode « {mode} » dépasse 100 % "
                    f'(total {total}).')
        return value

    def validate(self, attrs):
        # Commission (L788) : dès qu'un mode actif est choisi (pct_devis /
        # par_kwc), la valeur de commission devient obligatoire — sinon on
        # aurait un mode actif sans barème (commission silencieusement nulle).
        # On résout le mode/valeur effectifs (entrants OU déjà enregistrés)
        # pour rester correct en PATCH partiel.
        inst = self.instance
        mode = attrs.get('commission_mode',
                         getattr(inst, 'commission_mode', 'off'))
        if mode and mode != 'off':
            if 'commission_valeur' in attrs:
                valeur = attrs.get('commission_valeur')
            else:
                valeur = getattr(inst, 'commission_valeur', None)
            if valeur is None:
                raise serializers.ValidationError({
                    'commission_valeur':
                        'La valeur de commission est obligatoire quand un '
                        'mode de commission est actif.',
                })
        return attrs

    def _presign(self, key):
        if not key:
            return None
        try:
            from apps.ventes.utils.minio_client import get_minio_client
            from django.conf import settings
            client = get_minio_client()
            return client.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.MINIO_BUCKET_UPLOADS, 'Key': key},
                ExpiresIn=3600,
            )
        except Exception:
            return None

    def get_logo_url(self, obj):
        return self._presign(obj.logo_key)

    def get_signature_url(self, obj):
        return self._presign(obj.signature_key)
