"""Sérialiseur du profil entreprise (``CompanyProfileSerializer``).

Domaine « Société & identité / Devis & logique métier ». Extrait de l'ancien
``serializers.py`` sans aucun changement de champ, de validation ni de
comportement (mêmes URLs présignées, mêmes contrôles de société)."""
from decimal import Decimal, InvalidOperation

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import CompanyProfile


def _valider_jalons(mode, jalons):
    """CIQ212 — un échéancier société en LISTE de jalons ``[{jalon, pct}]``
    (D-CIQ-13) : jalons connus, chaque pct dans [0, 100], somme = 100."""
    from apps.ventes.utils.company_settings import JALONS_CONNUS
    if not jalons:
        raise serializers.ValidationError(
            f"L'échéancier du mode « {mode} » ne peut pas être vide.")
    total = Decimal('0')
    for i, jalon in enumerate(jalons):
        if not isinstance(jalon, dict) or jalon.get('jalon') not in JALONS_CONNUS:
            raise serializers.ValidationError(
                f"« {mode}[{i}].jalon » doit valoir "
                f"{' | '.join(JALONS_CONNUS)}.")
        try:
            pct = Decimal(str(jalon.get('pct')))
            if not pct.is_finite():
                raise InvalidOperation
        except (TypeError, ValueError, ArithmeticError):
            raise serializers.ValidationError(
                f'« {mode}[{i}].pct » doit être un pourcentage numérique.')
        if pct < 0 or pct > 100:
            raise serializers.ValidationError(
                f'« {mode}[{i}].pct » doit être compris entre 0 et 100 %.')
        total += pct
    if total != 100:
        raise serializers.ValidationError(
            f"L'échéancier du mode « {mode} » doit totaliser 100 % "
            f'(total {total}).')


#: CIQ105 — prestations C&I réglables (clés = rôles C&I de prestation,
#: ``core.product_roles.ROLES_CI``). Aucune valeur par défaut.
FORFAITS_CI_PRESTATIONS = (
    'etudes_ingenierie', 'pose_structure', 'pose_modules', 'raccordement_ac',
    'mise_en_service', 'dossier_raccordement', 'levage_acces', 'transport_ci',
)


def _entree_sourcee(champ, entree, cles_montants):
    """Normalise ``{<montants>, source, date}`` ; ``None`` si tout est vide.

    Un montant saisi exige une ``source`` (refus FR nommant ``champ``) ;
    montants ≥ 0, texte décimal ; ``date`` ISO ou null."""
    import datetime

    if entree in (None, '', {}):
        return None
    if not isinstance(entree, dict):
        raise serializers.ValidationError(f'{champ} doit être un objet.')
    permises = set(cles_montants) | {'source', 'date'}
    inconnues = set(entree) - permises
    if inconnues:
        raise serializers.ValidationError(
            f"{champ} : clé(s) inconnue(s) {', '.join(sorted(inconnues))}.")
    montants = {}
    for cle in cles_montants:
        brut = entree.get(cle)
        if brut in (None, ''):
            montants[cle] = None
            continue
        try:
            nombre = Decimal(str(brut).replace(',', '.'))
        except InvalidOperation:
            raise serializers.ValidationError(
                f'{champ}.{cle} doit être un nombre.')
        if not nombre.is_finite() or nombre < 0:
            raise serializers.ValidationError(
                f'{champ}.{cle} doit être un nombre positif ou nul.')
        montants[cle] = str(nombre)
    source = (entree.get('source') or '')
    if not isinstance(source, str):
        raise serializers.ValidationError(f'{champ}.source doit être un texte.')
    source = source.strip()
    date = entree.get('date') or None
    if date is not None:
        try:
            datetime.date.fromisoformat(str(date))
        except ValueError:
            raise serializers.ValidationError(
                f'{champ}.date doit être une date ISO (AAAA-MM-JJ).')
        date = str(date)
    if all(v is None for v in montants.values()):
        # Aucun montant = « prix à renseigner » : la ligne est retirée (une
        # source seule ne chiffre rien).
        return None
    if not source:
        raise serializers.ValidationError(
            f'{champ} : la source est obligatoire (devis fournisseur, offre '
            'écrite…) — jamais un montant sans source.')
    return {**montants, 'source': source, 'date': date}


# AMET16 — UNE table des drapeaux société qui changent la forme d'un parcours
# (contrat `contract_samples/drapeaux_parcours.json`). Le défaut est lu sur le
# modèle, jamais recopié ici.
DRAPEAUX_PARCOURS = (
    ('devis_auto_depuis_tunnel', 'Devis automatique depuis le tunnel', 'PA1',
     'Un lead du site web assez renseigné reçoit un devis brouillon à vérifier, sans création manuelle.'),
    ('round_robin_leads_actif', 'Affectation équilibrée des leads', 'PA1',
     "Un nouveau lead est confié au commercial le moins chargé, sous le plafond de leads ouverts."),
    ('referral_enabled', 'Parrainage', 'PA1',
     'Un parrainage peut être enregistré sur un lead et sa récompense suivie.'),
    ('garantie_production_autorisee', 'Garantie de production imprimée', 'PA3',
     'La garantie de production peut figurer sur le devis, après validation tracée.'),
    ('revue_factures_active', 'Revue à quatre yeux des factures', 'PA4',
     "L'émission d'une facture exige la validation d'une autre personne que son créateur."),
    ('factures_immuables', 'Factures émises immuables', 'PA4',
     "Une facture émise n'est plus modifiable sur ses champs financiers : correction par avoir seulement."),
    ('securite_obligatoire_avant_demarrage', 'Contrôle sécurité avant démarrage', 'PA5',
     "Un chantier ne démarre pas tant que le contrôle de sécurité n'est pas fait."),
    ('reserver_stock_bc', 'Réservation du stock à la commande', 'PA6',
     "Le stock est réservé dès le bon de commande au lieu d'être décrémenté plus tard."),
)


class CompanyProfileSerializer(serializers.ModelSerializer):
    # AMET16 — drapeaux de parcours : lecture seule, l'écriture reste le PATCH
    # de chaque champ.
    drapeaux_parcours = serializers.SerializerMethodField()

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
    # CIQ614 — seuils 82-21 de RÉFÉRENCE (textes, noyau core.reglementaire),
    # exposés à côté des surcharges société ``seuil_regime_*`` (NULL = seuil
    # sourcé). Lecture seule : la société ne saisit qu'une surcharge.
    seuils_sources = serializers.SerializerMethodField()
    # CIQ212 — échéancier RÉSOLU par mode (lecture seule).
    payment_terms_effectifs = serializers.SerializerMethodField()
    # AGNR11 — barème résidentiel EFFECTIF (contrat bareme_effectif.json).
    bareme_effectif = serializers.SerializerMethodField()
    # CIQ622 — délais déclarés sans le MinValueValidator du modèle : le refus
    # (≤ 0) est rendu par ``validate_<champ>`` avec un message français.
    delai_intervention_suivi_heures = serializers.IntegerField(
        required=False, allow_null=True)
    delai_reception_definitive_mois = serializers.IntegerField(
        required=False, allow_null=True)

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_drapeaux_parcours(self, obj):
        return [
            {
                'cle': cle,
                'libelle': libelle,
                'valeur': bool(getattr(obj, cle)),
                'defaut': bool(CompanyProfile._meta.get_field(cle).default),
                'parcours': parcours,
                'effet': effet,
            }
            for cle, libelle, parcours, effet in DRAPEAUX_PARCOURS
        ]

    def get_benchmarking_opt_in(self, obj):
        company = getattr(obj, 'company', None)
        return bool(getattr(company, 'benchmarking_opt_in', False))

    def get_seuils_sources(self, obj) -> dict:
        from core.reglementaire import regime_8221 as r8221
        return {
            'declaration': {
                'valeur_kw': r8221.SEUIL_DECLARATION_KW,
                'source': r8221.SEUIL_DECLARATION_SOURCE,
            },
            'autorisation': {
                'valeur_kw': r8221.SEUIL_AUTORISATION_KW,
                'source': r8221.SEUIL_AUTORISATION_SOURCE,
            },
        }

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_bareme_effectif(self, obj):
        """AGNR11 — tranches réglées + redevance de LA société du profil,
        sinon ``national`` (lu par l'écran au lieu de ses constantes)."""
        from apps.parametres.selectors import bareme_effectif
        return bareme_effectif(getattr(obj, 'company', None))

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_payment_terms_effectifs(self, obj):
        """CIQ212 — pour chaque mode, la liste de jalons RÉSOLUE (réglage
        société, sinon défaut ``PAYMENT_TERMS_BY_MODE``), lue par l'écran au
        lieu de recopier les défauts en dur."""
        from apps.ventes.utils.company_settings import payment_terms_effectifs
        return payment_terms_effectifs(getattr(obj, 'company', None))

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
            # APAR16 — horodatage du verrou optimiste : posé par le serveur
            # (auto_now), renvoyé par l'écran pour comparaison, jamais écrit.
            'updated_at',
            # APAR53 — le fuseau de la société est UN réglage
            # (``fuseau_horaire``, validé IANA) ; l'ancien champ NTOBS23 reste
            # servi en lecture mais n'est plus inscriptible par ce PATCH.
            'timezone_affichage',
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

    # Seuils de régime loi 82-21 (kWc) — CIQ614 : SURCHARGES société, NULL =
    # seuil sourcé (``seuils_sources``) ; une surcharge saisie est non
    # négative.
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

    # ── CIQ622 — réglages C&I de recette / suivi, SANS défaut : vide accepté
    # (« écart affiché sans verdict » / « non engagé »), sinon 0 < % ≤ 100 et
    # heures / mois > 0. Refus 400 en français nommant le réglage.
    def _validate_pct_strict(self, value, label):
        if value is not None and (value <= 0 or value > 100):
            raise serializers.ValidationError(
                f'{label} doit être compris entre 0 (exclu) et 100 %.')
        return value

    def _validate_strict_positif(self, value, label):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                f'{label} doit être strictement positif.')
        return value

    def validate_recette_ecart_pmax_pct(self, value):
        return self._validate_pct_strict(
            value, "L'écart de recette toléré sur la puissance crête")

    def validate_recette_echantillon_iv_pct(self, value):
        return self._validate_pct_strict(
            value, "L'échantillon de courbes I-V")

    def validate_recette_pr_seuil_interne(self, value):
        return self._validate_pct_strict(
            value, 'Le seuil interne de performance ratio')

    def validate_delai_intervention_suivi_heures(self, value):
        return self._validate_strict_positif(
            value, "Le délai d'intervention (heures)")

    def validate_delai_reception_definitive_mois(self, value):
        return self._validate_strict_positif(
            value, 'Le délai de réception définitive (mois)')

    # ── CIQ105 — forfaits des prestations C&I et bande interne prix/kWc. Une
    # valeur saisie SANS source est refusée (400 FR nommant le champ) ; une
    # prestation entièrement vide est retirée (= « prix à renseigner »).
    def validate_forfaits_ci(self, value):
        if value in (None, ''):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                '`forfaits_ci` doit être un objet {prestation: {...}}.')
        inconnues = set(value) - set(FORFAITS_CI_PRESTATIONS)
        if inconnues:
            raise serializers.ValidationError(
                'Prestation C&I inconnue : '
                f"{', '.join(sorted(inconnues))} (attendu : "
                f"{', '.join(FORFAITS_CI_PRESTATIONS)}).")
        propre = {}
        for prestation in FORFAITS_CI_PRESTATIONS:
            if prestation not in value:
                continue
            entree = _entree_sourcee(
                f'forfaits_ci.{prestation}', value[prestation],
                ('fixe_ht', 'par_kwc_ht', 'par_panneau_ht'))
            if entree is not None:
                propre[prestation] = entree
        return propre

    def validate_bande_prix_kwc_ci(self, value):
        if value in (None, '', {}):
            return None
        entree = _entree_sourcee('bande_prix_kwc_ci', value,
                                 ('min_ht', 'max_ht'))
        if entree is None:
            return None
        mini, maxi = entree['min_ht'], entree['max_ht']
        if mini is not None and maxi is not None and (
                Decimal(mini) > Decimal(maxi)):
            raise serializers.ValidationError(
                'bande_prix_kwc_ci : le minimum dépasse le maximum.')
        return entree

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
        # APAR31 — normalisé AVANT validation puis stocké sous sa forme
        # canonique (15 chiffres) : « 001 234 567 000 089 » est accepté.
        from .tax_id_validators import normaliser_ice, validate_tax_id
        value = normaliser_ice(value)
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
            if isinstance(terms, list):
                # CIQ212 — LISTE de jalons [{jalon, pct}] (D-CIQ-13).
                _valider_jalons(mode, terms)
                continue
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
        # CIQ622 — une garantie de production n'est autorisée qu'avec le texte
        # de validation (assureur ou juriste : qui et quand). Valeurs
        # effectives (entrantes OU enregistrées) pour un PATCH partiel.
        autorisee = attrs.get(
            'garantie_production_autorisee',
            getattr(inst, 'garantie_production_autorisee', False))
        if autorisee:
            if 'garantie_production_validation' in attrs:
                texte = attrs.get('garantie_production_validation')
            else:
                texte = getattr(inst, 'garantie_production_validation', '')
            if not (texte or '').strip():
                raise serializers.ValidationError({
                    'garantie_production_validation':
                        "La garantie de production ne peut être autorisée "
                        "qu'avec sa validation écrite (assureur ou juriste : "
                        "qui a validé et quand).",
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
