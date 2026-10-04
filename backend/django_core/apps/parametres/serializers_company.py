"""Sérialiseur du profil entreprise (``CompanyProfileSerializer``).

Domaine « Société & identité / Devis & logique métier ». Extrait de l'ancien
``serializers.py`` sans aucun changement de champ, de validation ni de
comportement (mêmes URLs présignées, mêmes contrôles de société)."""
from decimal import Decimal, InvalidOperation

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
        # NTADM7/8 — ``plan``/``nb_sieges_max`` sont des données de LICENCE
        # (assignation réservée au founder, admin Django) : visibles en
        # lecture ici (écran Paramètres/Licences), jamais éditables par le
        # tenant via ce PATCH générique.
        read_only_fields = [
            'logo_key', 'signature_key', 'company', 'plan', 'nb_sieges_max',
            # NTDMO20 — assignation réservée au founder (admin Django /
            # gestion technique) : jamais éditable par le tenant via ce PATCH.
            'essai_expire_le',
        ]

    def validate_responsable_defaut_leads(self, value):
        # Le responsable par défaut doit appartenir à la même société.
        request = self.context.get('request')
        if value and request and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Utilisateur inconnu.')
        return value

    def validate_responsable_leads_pro(self, value):
        # CIQ415 — même règle par société que le responsable par défaut.
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

    # AGR606 — écart de recette pompage toléré : vide accepté (« écart affiché
    # sans verdict »), sinon strictement positif et au plus 100 %.
    def validate_recette_pompage_ecart_max_pct(self, value):
        if value is not None and (value <= 0 or value > 100):
            raise serializers.ValidationError(
                "L'écart de recette pompage toléré doit être compris entre "
                "0 (exclu) et 100 %.")
        return value

    # NTI18N10 — validation contre le registre IANA réel (zoneinfo, stdlib
    # depuis Python 3.9, déjà utilisé par le runtime — aucune dépendance
    # nouvelle) plutôt qu'une liste `choices=` figée : couvre TOUS les fuseaux
    # IANA valides sans maintenance manuelle d'une énumération.
    # NTI18N19 — validateur MA formalisé (framework extensible par
    # pack_pays, apps/parametres/tax_id_validators.py). `pack_pays`
    # (NTI18N16) n'existe pas encore (GATED-founder) : 'MA' est passé en dur
    # en attendant — comportement historique, puisque toute société
    # actuelle EST marocaine. Jamais bloquant pour un champ vide.
    def validate_ice(self, value):
        from .tax_id_validators import validate_tax_id
        resultat = validate_tax_id('MA', 'ice', value)
        if not resultat['valide']:
            raise serializers.ValidationError(resultat['message'])
        return value

    def validate_fuseau_horaire(self, value):
        import zoneinfo
        if value not in zoneinfo.available_timezones():
            raise serializers.ValidationError(
                f'Fuseau horaire inconnu : « {value} ».')
        return value

    # ── ERR55 — forme des champs JSON. Une forme corrompue (liste, scalaire,
    # clés/valeurs invalides) casserait la numérotation ou l'échéancier en
    # silence. NULL reste autorisé (= repli sur le défaut historique).
    _DOC_KEYS = {'devis', 'facture', 'avoir', 'bon_commande'}
    _RESET_VALUES = {'monthly', 'yearly', 'none'}

    # AGR208 — repères énergie agricole {cle: {valeur, source, releve_le}}.
    # Aucune valeur imposée : un repère peut rester vide ; une clé inconnue,
    # une valeur négative ou une date illisible est refusée (400 nommant le
    # champ). Jamais de repli numérique.
    def validate_reperes_energie_agricole(self, value):
        import datetime

        from .selectors import REPERES_ENERGIE_AGRICOLE_CLES
        if value in (None, ''):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'Les repères doivent être un objet {repère: {valeur, source, '
                'releve_le}}.')
        propre = {}
        for cle, repere in value.items():
            if cle not in REPERES_ENERGIE_AGRICOLE_CLES:
                raise serializers.ValidationError(
                    f'Repère inconnu : {cle} (attendus : '
                    f"{', '.join(REPERES_ENERGIE_AGRICOLE_CLES)}).")
            if repere is None:
                repere = {}
            if not isinstance(repere, dict) or set(repere) - {
                    'valeur', 'source', 'releve_le'}:
                raise serializers.ValidationError(
                    f'{cle} : un objet {{valeur, source, releve_le}} est '
                    'attendu.')
            valeur = repere.get('valeur')
            if valeur in ('', None):
                valeur = None
            else:
                try:
                    nombre = Decimal(str(valeur).replace(',', '.'))
                except (InvalidOperation, TypeError, ValueError):
                    nombre = None
                if isinstance(valeur, bool) or nombre is None or \
                        not nombre.is_finite() or nombre < 0:
                    raise serializers.ValidationError(
                        f'{cle} : la valeur doit être un montant positif '
                        '(MAD).')
                valeur = int(nombre) if nombre == nombre.to_integral_value() \
                    else float(nombre)
            source = repere.get('source') or ''
            if not isinstance(source, str):
                raise serializers.ValidationError(
                    f'{cle} : la source doit être un texte.')
            releve = repere.get('releve_le') or None
            if releve is not None:
                try:
                    datetime.date.fromisoformat(str(releve))
                except ValueError:
                    raise serializers.ValidationError(
                        f'{cle} : la date de relevé doit être AAAA-MM-JJ.')
            propre[cle] = {'valeur': valeur, 'source': source.strip(),
                           'releve_le': releve}
        return propre

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
