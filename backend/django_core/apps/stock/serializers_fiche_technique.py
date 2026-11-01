"""SPL115 — ``FicheTechniqueSerializer`` déplacé tel quel depuis
``serializers.py`` (move only). Même app : aucun ré-export, les appelants
importent ce module."""
from django.db import models
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.records.storage import AttachmentSerializerMixin, attachment_url
from core.champs_stricts import MOTIF_SANS_NUL, ChaineStricte, IdInconnu404Mixin
from core.serializers import CompanyScopedRelationsMixin
from .erreurs_achats import ConflitEtat

# Import DIRECT du module du modèle (pas la façade ``.models``) : sans cycle
# (``models_fiche_technique`` n'importe rien de stock), et c'est ce que lit
# ``scripts/check_api_shapes.py`` pour garder les ``choices`` de la fiche
# (type_fiche, bat_chimie) dans docs/api-contracts.md — son résolveur ne
# suit pas les ré-exports de façade (deux classes ``FicheTechnique``).
from .models_fiche_technique import FicheTechnique
from .utils.params import UniciteEn409Mixin


class FichierFacultatifField(serializers.FileField):
    """``FileField`` qui lit ``""`` comme « aucun fichier » (``None``).

    Un corps JSON ne peut pas porter de fichier : ``"pdf": ""`` est la seule
    forme d'« absence » qu'un client JSON (ou un formulaire vidé) sait écrire.
    DRF le refusait (« La donnée soumise n'est pas un fichier ») alors que
    ``AttachmentSerializerMixin`` traite déjà ``None``/``''`` comme « pas de
    pièce jointe » ; une VRAIE donnée non vide qui n'est pas un fichier reste
    refusée en 400."""

    def validate_empty_values(self, data):
        if isinstance(data, str) and data == '' and self.allow_null:
            return (True, None)
        return super().validate_empty_values(data)


@extend_schema_field({
    'type': 'object', 'nullable': True, 'additionalProperties': False,
    'properties': {
        'document': {'type': 'string', 'nullable': True,
                     'pattern': MOTIF_SANS_NUL},
        'date': {'type': 'string', 'format': 'date', 'nullable': True},
        'page': {'type': 'integer', 'nullable': True},
    },
    'description': 'Provenance de la masse : {"document": "", "date": null, '
                   '"page": null}.',
})
class NoticeStructureField(serializers.JSONField):
    """api-fuzz PR #1184 (« API rejected schema-compliant request », POST/PUT/
    PATCH ``fiches-techniques`` en multipart) — ``struct_notice`` était publié
    SANS type : le fuzzeur envoyait alors ``null`` comme une pièce brute
    (« None ») que le JSONField ne sait pas lire (« La valeur doit être un JSON
    valide »). Le schéma dit maintenant la forme exacte que
    ``validate_struct_notice`` accepte — un objet ``{document, date, page}``
    ou ``null`` — et une partie multipart d'un objet part en JSON."""


class FicheTechniqueSerializer(IdInconnu404Mixin,
                               UniciteEn409Mixin,
                               AttachmentSerializerMixin,
                               CompanyScopedRelationsMixin,
                               serializers.ModelSerializer):
    """DC35 — datasheet rattachée à un produit. Expose en LECTURE quelques
    champs du produit (marque/garantie/nom) pour éviter au front de re-saisir
    ou re-stocker l'identité : elle vit sur ``Produit`` et n'est jamais copiée
    sur la fiche.

    AUD835 — le PDF constructeur part dans MinIO (``records.storage``) : ``pdf``
    est l'entrée d'upload (écriture seule), ``pdf_url`` l'URL présignée de
    relecture (``None`` pour une fiche antérieure à la bascule)."""
    attachment_fields = ('pdf',)

    # api-fuzz stock B : un texte JSON sans caractère nul (motif publié) —
    # DRF refusait « \u0000 » en 400 alors que le schéma l'autorisait.
    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.CharField: ChaineStricte,
        models.TextField: ChaineStricte,
    }

    pdf = FichierFacultatifField(
        write_only=True, required=False, allow_null=True)
    pdf_url = serializers.SerializerMethodField()
    struct_notice = NoticeStructureField(required=False, allow_null=True)
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    produit_marque = serializers.CharField(
        source='produit.marque', read_only=True, allow_null=True)
    produit_garantie = serializers.CharField(
        source='produit.garantie', read_only=True, allow_null=True)

    class Meta:
        model = FicheTechnique
        fields = [
            'id', 'produit', 'produit_nom', 'produit_marque',
            'produit_garantie', 'pmax_wc', 'voc_v', 'isc_a', 'vmp_v', 'imp_a',
            'rendement_pct',
            # PV5 — type + blocs module/onduleur/batterie (tous optionnels).
            'type_fiche',
            'longueur_mm', 'largeur_mm', 'epaisseur_mm', 'poids_kg',
            'techno_cellule', 'bifacial',
            'temp_coeff_voc_pct_c', 'temp_coeff_pmax_pct_c',
            # CAL111 — modèle thermique NOCT / Uc-Uv (optionnels).
            'noct_c', 'uc_w_m2k', 'uv_w_m3sk',
            # CALX355 — facteur de bifacialité (CAL112) : en base et lu par
            # specs_for_produit, mais jamais exposé ici — une saisie du
            # formulaire produit aurait été ignorée en silence.
            'bifacialite_pct',
            'ond_n_mppt', 'ond_mppt_v_min', 'ond_mppt_v_max', 'ond_v_max_abs',
            'ond_i_max_mppt_a', 'ond_ac_kw', 'ond_phases',
            'ond_rendement_euro_pct',
            # PVOND-H (2026-08-19) — tension de démarrage, Isc max par MPPT,
            # plage de tension batterie : le moteur électrique les sait déjà
            # lire (core.electrique.types.SpecOnduleur), elles n'avaient
            # simplement aucun champ pour les porter jusqu'ici.
            'ond_v_demarrage_v', 'ond_isc_max_mppt_a',
            'ond_bat_aucune', 'ond_bat_v_min', 'ond_bat_v_max',
            # L-DECH (2026-08-24) — les deux bornes du PORT batterie de
            # l'hybride, et la décharge PAR PACK côté batterie : le moteur
            # horaire borne le chemin batterie par le plus petit des deux.
            'ond_bat_max_charge_kw', 'ond_bat_max_decharge_kw',
            'bat_kwh_nominal', 'bat_kwh_usable', 'bat_dod_pct',
            'bat_v_nominal', 'bat_max_charge_kw', 'bat_max_decharge_kw',
            # BATHOMO (2026-08-26) — plafond fondateur du nombre de modules
            # identiques par banque (vide = illimité).
            'bat_max_modules_par_banc',
            # CALX60 (2026-09-21) — tout ce que la chaîne de pertes et
            # l'électrique lisent : la courbe de faible éclairement et la
            # tolérance du module, la courbe η(P) / la veille de l'onduleur,
            # la SORTIE de l'optimiseur / du micro-onduleur, le C-rate et la
            # plage de température du pack. Tous optionnels : une fiche
            # ancienne les rend tous vides, et l'étape qui les lit s'omet en
            # nommant le champ plutôt que de forfaitiser.
            'rendement_par_irradiance', 'tolerance_pmax_min_pct',
            'tolerance_pmax_max_pct',
            'ond_courbe_rendement', 'ond_rendement_max_pct',
            'ond_rendement_cec_pct', 'ond_conso_nuit_w',
            'bat_c_rate_charge', 'bat_c_rate_decharge', 'bat_chimie',
            'bat_temp_min_c', 'bat_temp_max_c',
            'opt_ac_kw', 'opt_ac_tension_v', 'opt_ac_i_max_a',
            'opt_ac_unites_max_par_branche', 'opt_v_out_nominal_v',
            'opt_v_out_min', 'opt_v_out_max', 'opt_i_out_max_a',
            'opt_pmax_out_w', 'opt_modules_max_par_chaine',
            # AGR101 — fiches pompe / variateur de pompage (valeurs constructeur ;
            # vide = non publié).
            'pompe_i_nominal_a', 'pompe_diametre_ext_mm', 'pompe_nb_etages',
            'pompe_immersion_min_m', 'pompe_rendement_pct',
            'pompe_q_nominal_m3h', 'pompe_hmt_nominale_m',
            'var_voc_reco_min_v', 'var_voc_reco_max_v', 'var_v_sortie_v',
            'var_i_sortie_nominal_a', 'var_protection_marche_a_sec',
            'var_rendement_mppt_pct',
            # CIQ101 — fiches C&I (contrat produit_ci.json ; vide = non
            # publié, jamais un défaut).
            'ond_limitation_export', 'ond_compteurs_compatibles',
            'ond_relais_decouplage', 'ond_cos_phi_min', 'ond_cos_phi_max',
            'lim_mode', 'lim_i_max_a', 'lim_onduleurs_max', 'lim_marques',
            'lim_phases',
            # R3.5 / R3.6 (fondateur, 28/10/2026) — calibre du comptage et
            # nature du produit de supervision (dongle | logger).
            'lim_calibre_a', 'log_type',
            'log_onduleurs_max', 'log_marques',
            'prot_type', 'prot_cote', 'prot_calibre_a',
            'prot_pouvoir_coupure_ka', 'prot_poles', 'prot_tension_v',
            'cable_cote', 'cable_section_mm2', 'cable_ame',
            'struct_type_pose', 'struct_masse_kg_m2', 'struct_notice',
            'pdf', 'pdf_url', 'pdf_filename', 'pdf_size', 'pdf_mime',
            'date_creation', 'date_mise_a_jour',
        ]
        # company is force-assigned in perform_create — never from the body.
        read_only_fields = [
            'company', 'date_creation', 'date_mise_a_jour',
            'pdf_filename', 'pdf_size', 'pdf_mime',
        ]
        # Les `validate_<champ>` ci-dessous lisent déjà `None` comme « vide »
        # (liste vide / notice vide) : la colonne reste non nulle, c'est le
        # validateur qui normalise. Sans `allow_null`, DRF refusait ce que le
        # code accepte (api-fuzz #997).
        extra_kwargs = {
            # Validateurs de courbe du modèle rejoués par ``validate_<champ>``
            # (``_courbe``) : la croissance de l'abscisse y devient un 409.
            'rendement_par_irradiance': {'validators': []},
            'ond_courbe_rendement': {'validators': []},
            'ond_compteurs_compatibles': {'allow_null': True},
            'lim_marques': {'allow_null': True},
            'log_marques': {'allow_null': True},
        }

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_pdf_url(self, obj):
        return attachment_url(obj, 'pdf')

    def validate_produit(self, value):
        """Le produit doit appartenir à la société du demandeur (anti
        cross-tenant)."""
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Produit hors de votre entreprise.')
        return value

    # ── CIQ101 — fiches C&I ──────────────────────────────────────────────
    @staticmethod
    def _liste_de_textes(champ, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list) or not all(
                isinstance(v, str) for v in value):
            raise serializers.ValidationError(
                f"`{champ}` doit être une liste de textes.")
        if any('\x00' in v for v in value):
            # Motif publié (sans caractère nul) : jsonb le refuserait en 500.
            raise serializers.ValidationError(
                f"`{champ}` : un texte ne peut pas contenir de caractère nul.")
        return [v.strip() for v in value if v.strip()]

    # ── CALX60 — courbes : forme 400, croissance de l'abscisse 409 ─────────
    CODE_COURBE_NON_CROISSANTE = 'courbe_non_croissante'

    def is_valid(self, *, raise_exception=False):
        """Une requête dont les SEULS refus sont des refus d'état — la
        croissance d'une courbe (règle croisée que le schéma ne dit pas, comme
        ``courbe_pompe`` du produit), seule ou avec le doublon de ``produit``
        (déjà 409 seul, ``UniciteEn409Mixin``) — répond 409 (api-fuzz PR
        #1184). ``.errors`` reste le corps DRF ; sans ``raise_exception`` rien
        ne change."""
        valide = super().is_valid(raise_exception=False)
        if not valide and raise_exception:
            erreurs = self.errors
            codes = {getattr(e, 'code', None)
                     for liste in erreurs.values()
                     for e in (liste if isinstance(liste, list) else [None])}
            if (self.CODE_COURBE_NON_CROISSANTE in codes
                    and codes <= {self.CODE_COURBE_NON_CROISSANTE, 'unique'}):
                raise ConflitEtat(erreurs)
            return super().is_valid(raise_exception=True)
        return valide

    def _courbe(self, champ, value, valider, cles, cle_serie=None):
        """Le validateur du modèle (``valider_courbe_*``) tranche. Un refus
        sur une courbe de FORME publiée (liste non vide de points aux clés
        numériques) ne peut venir que de la croissance de l'abscisse : code
        ``courbe_non_croissante`` (409 via ``is_valid``). Tout autre refus
        reste un 400."""
        from django.core.exceptions import ValidationError as ErreurModele
        from .models_fiche_technique import _est_nombre
        try:
            valider(value)
        except ErreurModele as exc:
            forme_publiee = isinstance(value, list) and value and all(
                isinstance(point, dict)
                and all(_est_nombre(point.get(c)) for c in cles)
                and (cle_serie is None or point.get(cle_serie) is None
                     or _est_nombre(point.get(cle_serie)))
                for point in value)
            raise serializers.ValidationError(
                exc.messages,
                code=self.CODE_COURBE_NON_CROISSANTE if forme_publiee else None)
        return value

    def validate_rendement_par_irradiance(self, value):
        from .models_fiche_technique import valider_courbe_irradiance
        return self._courbe('rendement_par_irradiance', value,
                            valider_courbe_irradiance,
                            ('w_m2', 'rendement_relatif_pct'))

    def validate_ond_courbe_rendement(self, value):
        from .models_fiche_technique import valider_courbe_rendement_onduleur
        return self._courbe('ond_courbe_rendement', value,
                            valider_courbe_rendement_onduleur,
                            ('charge_pct', 'rendement_pct'),
                            cle_serie='tension_v')

    def validate_ond_compteurs_compatibles(self, value):
        return self._liste_de_textes('ond_compteurs_compatibles', value)

    def validate_lim_marques(self, value):
        return self._liste_de_textes('lim_marques', value)

    def validate_log_marques(self, value):
        return self._liste_de_textes('log_marques', value)

    def validate_lim_phases(self, value):
        if value is not None and value not in (1, 3):
            raise serializers.ValidationError(
                '`lim_phases` vaut 1 ou 3 (ou vide = non publié).')
        return value

    def validate_struct_notice(self, value):
        """Normalise en ``{document, date, page}`` ; vide = non publiée."""
        if value is None or value == {}:
            return {'document': '', 'date': None, 'page': None}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                '`struct_notice` doit être un objet '
                '{"document": ..., "date": ..., "page": ...}.')
        inconnues = set(value) - {'document', 'date', 'page'}
        if inconnues:
            raise serializers.ValidationError(
                "`struct_notice` n'accepte que `document`, `date` et `page` "
                f"(reçu en trop : {', '.join(sorted(inconnues))}).")
        document = value.get('document') or ''
        if not isinstance(document, str):
            raise serializers.ValidationError(
                '`struct_notice.document` doit être un texte.')
        if '\x00' in document:
            # Motif publié (sans caractère nul) : jsonb le refuserait en 500.
            raise serializers.ValidationError(
                '`struct_notice.document` ne peut pas contenir de caractère '
                'nul.')
        date = value.get('date') or None
        if date is not None:
            import datetime
            try:
                datetime.date.fromisoformat(str(date))
            except ValueError:
                raise serializers.ValidationError(
                    '`struct_notice.date` doit être une date ISO '
                    '(AAAA-MM-JJ).')
            date = str(date)
        page = value.get('page')
        if page in ('', None):
            page = None
        elif isinstance(page, bool) or not isinstance(page, int):
            raise serializers.ValidationError(
                '`struct_notice.page` doit être un entier.')
        return {'document': document.strip(), 'date': date, 'page': page}

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # Une masse de structure sans notice (document vide) est refusée : une
        # charge de toit non sourcée ne se défend pas devant un bureau de
        # contrôle (contrat produit_ci.json, fiches.structure.regle).
        inst = self.instance
        masse = attrs.get('struct_masse_kg_m2',
                          getattr(inst, 'struct_masse_kg_m2', None))
        notice = attrs.get('struct_notice',
                           getattr(inst, 'struct_notice', None)) or {}
        if masse is not None and not (notice.get('document') or '').strip():
            # Règle croisée (masse ↔ notice, relue sur l'instance en PATCH)
            # que le schéma ne dit pas : 409, plus un 400 sur un corps conforme.
            raise ConflitEtat({
                'struct_notice': (
                    'Masse de structure saisie sans notice : renseignez le '
                    'document fabricant (`struct_notice.document`).')})
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if 'struct_notice' in data:
            src = data['struct_notice'] or {}
            data['struct_notice'] = {
                'document': src.get('document') or '',
                'date': src.get('date') or None,
                'page': src.get('page'),
            }
        for cle in ('ond_compteurs_compatibles', 'lim_marques',
                    'log_marques'):
            if cle in data and data[cle] is None:
                data[cle] = []
        return data


#: Champs JSON de la fiche (courbes, listes, notice). Une partie de
#: formulaire multipart n'a pas de ``null`` ni de structure JSON : le fuzzeur
#: les envoyait en pièce brute (« None ») que le JSONField refuse (« La valeur
#: doit être un JSON valide ») — api-fuzz PR #1184, ``struct_notice`` puis
#: ``log_marques``. Ils se saisissent en corps JSON (l'écran produit), le
#: multipart ne sert qu'au PDF constructeur.
CHAMPS_JSON_FICHE = (
    'rendement_par_irradiance', 'ond_courbe_rendement',
    'ond_compteurs_compatibles', 'lim_marques', 'log_marques',
    'struct_notice',
)


class FicheTechniqueMultipartSerializer(FicheTechniqueSerializer):
    """Corps ``multipart/form-data`` PUBLIÉ de la fiche (schéma seulement) :
    les champs de ``FicheTechniqueSerializer`` moins ``CHAMPS_JSON_FICHE``."""

    struct_notice = None

    class Meta(FicheTechniqueSerializer.Meta):
        fields = [nom for nom in FicheTechniqueSerializer.Meta.fields
                  if nom not in CHAMPS_JSON_FICHE]
