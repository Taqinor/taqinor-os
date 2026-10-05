"""SPL115 — ``FicheTechniqueSerializer`` déplacé tel quel depuis
``serializers.py`` (move only). Même app : aucun ré-export, les appelants
importent ce module."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.records.storage import AttachmentSerializerMixin, attachment_url

from .models import FicheTechnique


class FicheTechniqueSerializer(AttachmentSerializerMixin,
                               serializers.ModelSerializer):
    """DC35 — datasheet rattachée à un produit. Expose en LECTURE quelques
    champs du produit (marque/garantie/nom) pour éviter au front de re-saisir
    ou re-stocker l'identité : elle vit sur ``Produit`` et n'est jamais copiée
    sur la fiche.

    AUD835 — le PDF constructeur part dans MinIO (``records.storage``) : ``pdf``
    est l'entrée d'upload (écriture seule), ``pdf_url`` l'URL présignée de
    relecture (``None`` pour une fiche antérieure à la bascule)."""
    attachment_fields = ('pdf',)

    pdf = serializers.FileField(
        write_only=True, required=False, allow_null=True)
    pdf_url = serializers.SerializerMethodField()
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    produit_marque = serializers.CharField(
        source='produit.marque', read_only=True)
    produit_garantie = serializers.CharField(
        source='produit.garantie', read_only=True)

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
            'pdf', 'pdf_url', 'pdf_filename', 'pdf_size', 'pdf_mime',
            'date_creation', 'date_mise_a_jour',
        ]
        # company is force-assigned in perform_create — never from the body.
        read_only_fields = [
            'company', 'date_creation', 'date_mise_a_jour',
            'pdf_filename', 'pdf_size', 'pdf_mime',
        ]

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
