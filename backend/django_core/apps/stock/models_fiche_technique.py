"""SPL113 — fiche technique (datasheet) d'un produit : ``FicheTechnique`` et
les validateurs de courbe CALX60, déplacés tels quels depuis ``models.py``
(move only). ``apps.stock.models`` les ré-exporte."""
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


# ── CALX60 — CONTRÔLE DES COURBES DE FICHE TECHNIQUE ────────────────────────
#
# Deux champs de ``FicheTechnique`` portent une COURBE (une liste de points),
# pas une valeur : le rendement du module à éclairement partiel et le
# rendement de l'onduleur en fonction de sa charge. Les deux se lisent par
# INTERPOLATION — et une abscisse qui recule (ou se répète) rend
# l'interpolation ambiguë : deux ordonnées pour une même entrée, donc un
# chiffre de production indéfendable. La courbe est donc REFUSÉE À LA SAISIE
# en nommant l'INDEX du point fautif, et jamais re-triée en silence : un tri
# changerait la courbe saisie par le fournisseur sans que personne le voie.
#
# Une liste VIDE est refusée elle aussi — ce n'est pas « non publié » (le
# champ vide le dit déjà), et ce serait une courbe sans aucun point à
# interpoler, donc une perte de 0 % inventée (D-CALX 7).
#
# Les deux fonctions vivent au niveau MODULE parce qu'un validateur de champ
# doit être importable par son chemin pour entrer dans une migration.
# ``ValidationError`` s'importe DANS les fonctions, comme le bloc d'imports de
# fin de fichier : une ligne ajoutée en tête de ce fichier décalerait les
# gardes qui le référencent par ``path:lineno``.

def _est_nombre(valeur):
    """Un nombre saisissable dans une courbe — le booléen n'en est pas un."""
    return (isinstance(valeur, (int, float, Decimal))
            and not isinstance(valeur, bool))


def _valider_courbe(valeur, libelle, cle_abscisse, cles_requises,
                    cle_serie=None):
    """Contrôle commun des courbes de fiche : liste non vide de points, clés
    requises numériques, abscisse STRICTEMENT croissante.

    ``cle_serie`` nomme la clé qui sépare plusieurs courbes dans une même
    liste (la tension d'entrée d'un onduleur, par exemple) : la croissance
    est alors exigée À L'INTÉRIEUR de chaque courbe, pas entre elles.
    Chaque refus nomme l'index du point fautif."""
    from django.core.exceptions import ValidationError

    if valeur is None or valeur == '':
        return
    if not isinstance(valeur, list):
        raise ValidationError(
            f'« {libelle} » attend une LISTE de points, pas un(e) '
            f'{type(valeur).__name__}.')
    if not valeur:
        raise ValidationError(
            f'« {libelle} » : une liste vide n\'est pas une courbe. Laisser '
            'le champ VIDE si la donnée n\'est pas publiée.')

    vues = {}
    for index, point in enumerate(valeur):
        if not isinstance(point, dict):
            raise ValidationError(
                f'« {libelle} » : le point d\'index {index} n\'est pas un '
                f'objet mais un(e) {type(point).__name__}.')
        for cle in cles_requises:
            if cle not in point:
                raise ValidationError(
                    f'« {libelle} » : le point d\'index {index} n\'a pas de '
                    f'« {cle} ».')
            if not _est_nombre(point[cle]):
                raise ValidationError(
                    f'« {libelle} » : « {cle} » du point d\'index {index} '
                    f'n\'est pas un nombre ({point[cle]!r}).')
        serie = point.get(cle_serie) if cle_serie else None
        if serie is not None and not _est_nombre(serie):
            raise ValidationError(
                f'« {libelle} » : « {cle_serie} » du point d\'index {index} '
                f'n\'est pas un nombre ({serie!r}).')
        precedent = vues.get(str(serie))
        courante = float(point[cle_abscisse])
        if precedent is not None and courante <= precedent[0]:
            raise ValidationError(
                f'« {libelle} » : « {cle_abscisse} » du point d\'index '
                f'{index} ({point[cle_abscisse]}) ne dépasse pas celui du '
                f'point d\'index {precedent[1]} ({precedent[2]}) — une '
                'courbe s\'interpole, son abscisse ne peut ni reculer ni se '
                'répéter.')
        vues[str(serie)] = (courante, index, point[cle_abscisse])


def valider_courbe_irradiance(valeur):
    """CALX60 — ``FicheTechnique.rendement_par_irradiance`` : des paires
    (W/m², % du rendement STC), abscisse strictement croissante."""
    _valider_courbe(
        valeur, 'rendement_par_irradiance',
        cle_abscisse='w_m2',
        cles_requises=('w_m2', 'rendement_relatif_pct'))


def valider_courbe_rendement_onduleur(valeur):
    """CALX60 — ``FicheTechnique.ond_courbe_rendement`` : des paires
    (% de PNom, η %), éventuellement une courbe par tension d'entrée."""
    _valider_courbe(
        valeur, 'ond_courbe_rendement',
        cle_abscisse='charge_pct',
        cles_requises=('charge_pct', 'rendement_pct'),
        cle_serie='tension_v')


class FicheTechnique(models.Model):
    """DC35 / FG254 — Fiche technique (datasheet) d'un produit.

    Référence le ``Produit`` par FK et NE RE-STOCKE PAS l'identité ni les
    caractéristiques déjà portées par le produit : marque, garantie, courbe de
    pompe, description, prix, TVA vivent sur ``Produit`` et sont lus là-bas. La
    fiche ne porte QUE :

      • des paramètres ÉLECTRIQUES normalisés (Pmax / Voc / Isc / Vmp / Imp /
        rendement) qui n'existent pas encore sur ``Produit`` — utiles pour le
        dimensionnement / la comparaison sans dépendre du texte libre ;
      • le PDF constructeur d'origine.

    Un produit a au plus UNE fiche (OneToOne). Tout est optionnel : une fiche
    peut ne porter que le PDF, ou que des paramètres. Entièrement additif —
    aucun produit existant n'est impacté.

    PV5 — ``type_fiche`` distingue trois blocs de champs supplémentaires,
    tous optionnels et sans effet sur les 6 champs électriques historiques
    ci-dessus : dimensions/coefficients MODULE, entrées MPPT/tensions/
    rendement ONDULEUR, capacité/DoD/tension BATTERIE."""

    company = models.ForeignKey(
        # on_delete: cascade tenant standard — la fiche technique suit sa société.
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='fiches_techniques')
    produit = models.OneToOneField(
        'stock.Produit', on_delete=models.PROTECT, related_name='fiche_technique')  # on_delete: PROTECT — fiche technique constructeur (paramètres saisis + PDF) = catalogue RÉEL non reconstructible

    # ── Paramètres électriques normalisés (Wc / V / A) — tous optionnels ──
    pmax_wc = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Puissance crête Pmax (Wc).')
    voc_v = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Tension circuit ouvert Voc (V).')
    isc_a = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Courant court-circuit Isc (A).')
    vmp_v = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Tension au point de puissance max Vmp (V).')
    imp_a = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Courant au point de puissance max Imp (A).')
    rendement_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Rendement du module (%).')

    # ── PV5 — type de fiche (détermine quel bloc de champs ci-dessous
    # s'applique) — optionnel, vide par défaut sur les fiches existantes ──
    class TypeFiche(models.TextChoices):
        MODULE = 'module', 'Module (panneau)'
        ONDULEUR = 'onduleur', 'Onduleur'
        BATTERIE = 'batterie', 'Batterie'
        # CAL116 — optimiseur de puissance / micro-onduleur : PVsyst
        # modélise les optimiseurs comme composants avec leur propre perte
        # de conversion, PV*SOL les micro-onduleurs. Choix ADDITIF : aucune
        # fiche existante ne change de type.
        OPTIMISEUR = 'optimiseur', 'Optimiseur / micro-onduleur'
        # AGR101 — pompe et variateur de pompage : valeurs PUBLIÉES par la
        # fiche constructeur du modèle exact (additif).
        POMPE = 'pompe', 'Pompe'
        VARIATEUR_POMPAGE = 'variateur_pompage', 'Variateur de pompage'
        AUTRE = 'autre', 'Autre'

    type_fiche = models.CharField(
        max_length=24, choices=TypeFiche.choices, blank=True, default='',
        help_text='Type de fiche technique (détermine les champs applicables).')

    # ── PV5 — Module : dimensions & coefficients de température ──
    longueur_mm = models.PositiveIntegerField(
        null=True, blank=True, help_text='Longueur du module (mm).')
    largeur_mm = models.PositiveIntegerField(
        null=True, blank=True, help_text='Largeur du module (mm).')
    epaisseur_mm = models.PositiveIntegerField(
        null=True, blank=True, help_text='Épaisseur du module (mm).')
    poids_kg = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Poids du module (kg).')
    techno_cellule = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Technologie de cellule (ex. N-type TOPCon, PERC…).')
    bifacial = models.BooleanField(
        default=False, help_text='Module bifacial (production face arrière).')
    # ── CAL112 — facteur de bifacialité. ──
    #
    # Le booléen ci-dessus ne dit QUE « bifacial ou non » : impossible d'en
    # tirer un gain face arrière. PVsyst modélise un facteur de bifacialité
    # publié par le fabricant (généralement 65-90 %) combiné à un albédo de
    # site — l'albédo se saisit côté projet de calepinage (hors fiche
    # produit, tâche séparée), pas ici. Le booléen reste, non supprimé.
    #
    # Optionnel — vide = « non publié », AUCUN gain bifacial calculé (ni 0,
    # qui affirmerait à tort une bifacialité nulle mesurée).
    bifacialite_pct = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text='Facteur de bifacialité publié par le fabricant (%). '
                  'Vide = non publié : aucun gain bifacial calculé.')
    temp_coeff_voc_pct_c = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True,
        help_text='Coefficient de température de Voc (%/°C).')
    temp_coeff_pmax_pct_c = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True,
        help_text='Coefficient de température de Pmax (%/°C).')

    # ── CAL111 — Modèle thermique du module (NOCT / coefficients Uc-Uv). ──
    #
    # La fiche portait déjà les coefficients de température Voc/Pmax
    # ci-dessus, mais AUCUN paramètre de température de cellule : le calcul
    # solaire (``apps/ventes/solar_design.py``) fixait la température cellule
    # en dur (``DEFAULT_COLD_TEMP_C``/``DEFAULT_HOT_TEMP_C``). PVsyst rend le
    # modèle thermique sélectionnable et paramétré par Uc (perte constante)
    # et Uv (perte proportionnelle au vent), NOCT étant la température
    # nominale de fonctionnement en cellule (« Nominal Operating Cell
    # Temperature », condition 800 W/m², 20 °C, 1 m/s).
    #
    # TOUS OPTIONNELS — vide = « non publié », JAMAIS 0 (un 0 W/m²K serait
    # une perte thermique nulle inventée). Purement additif : aucune fiche
    # existante n'est modifiée, aucun calcul ne lit encore ces champs (ils
    # ne sont pas encore servis par ``specs_for_produit`` — cf. CAL114).
    noct_c = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text='NOCT — température nominale de fonctionnement en '
                  'cellule (°C, condition 800 W/m², 20 °C, 1 m/s). '
                  'Vide = non publié.')
    uc_w_m2k = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Coefficient thermique constant Uc du modèle Uc-Uv '
                  '(W/m²K). Vide = non publié.')
    uv_w_m3sk = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Coefficient thermique proportionnel au vent Uv du '
                  'modèle Uc-Uv (W/m³sK — « /(m/s)/m²/K »). Vide = non '
                  'publié.')

    # ── CAL113 — dégradation annuelle & paliers de garantie du module. ──
    #
    # Ces valeurs vivaient en constantes de code
    # (``apps/ventes/solar_design.py`` : ``DEFAULT_WARRANTY_FLOORS =
    # {10: 0.90, 25: 0.80}``, ``DEFAULT_YEAR1_DEGRADATION = 0.02``) alors que
    # la datasheet les publie. Optionnels — vides = « non publié » : le
    # moteur ventes retombe alors sur son hypothèse de référence et LE DIT
    # (discipline déjà appliquée au rendement aller-retour batterie).
    degradation_annuelle_pct = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        help_text='Dégradation annuelle linéaire publiée (%/an), années '
                  '2+. Vide = non publié.')
    degradation_annee1_pct = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        help_text='Dégradation de la première année publiée (%). Vide = '
                  'non publié.')
    garantie_pct_a_10_ans = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text='Palier de garantie de production à 10 ans publié (% de '
                  'Pmax nominal). Vide = non publié.')
    garantie_pct_a_25_ans = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text='Palier de garantie de production à 25 ans publié (% de '
                  'Pmax nominal). Vide = non publié.')

    # ── CALX60 — ce que la CHAÎNE DE PERTES lit sur un MODULE et qui
    # n'existait nulle part en base. ──
    #
    # Deux étapes de la chaîne séquentielle étaient condamnées à sortir
    # OMISES à vie faute de champ pour les alimenter :
    #   * « niveau d'irradiance » (CALX162) veut la courbe de rendement à
    #     éclairement partiel — la fiche ne portait QUE le rendement STC
    #     (``rendement_pct``), c'est-à-dire un seul point de cette courbe ;
    #   * « qualité module » (CALX165) veut les DEUX bornes de tolérance de
    #     puissance de la datasheet (« 0/+3 % ») — aucun champ ne les
    #     portait (``tolerance_prix_pct``/``tolerance_quantite_pct`` sont des
    #     tolérances d'ACHAT, sans rapport).
    #
    # PV*SOL fait de chaque grandeur de datasheet un champ saisissable
    # (https://help.valentin-software.com/pvsol/en/databases/components/pv-modules/).
    # TOUS OPTIONNELS — vide = « non publié » : l'étape s'omet en nommant le
    # champ et le produit, JAMAIS un forfait ni un 0 (D-CALX 7). Aucune
    # valeur par défaut n'est posée ici : une courbe absente n'est pas une
    # courbe plate, et une tolérance absente n'est pas une tolérance nulle.
    rendement_par_irradiance = models.JSONField(
        null=True, blank=True,
        validators=[valider_courbe_irradiance],
        help_text='Courbe de rendement à éclairement partiel publiée : '
                  '[{"w_m2": 200, "rendement_relatif_pct": 97.5}, …] — le '
                  'rendement RELATIF (% du rendement STC) à chaque niveau '
                  "d'irradiance. Vide = non publiée : l'étape « niveau "
                  "d'irradiance » est omise en le disant.")
    tolerance_pmax_min_pct = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        help_text='Tolérance de puissance Pmax publiée — borne BASSE (%, '
                  'ex. 0 pour un tri « 0/+3 % », −3 pour « ±3 % »). Vide = '
                  'non publiée.')
    tolerance_pmax_max_pct = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        help_text='Tolérance de puissance Pmax publiée — borne HAUTE (%, '
                  'ex. 3 pour un tri « 0/+3 % »). Vide = non publiée.')

    # ── PV5 — Onduleur ──
    ond_n_mppt = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Nombre d'entrées MPPT.")
    ond_mppt_v_min = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Tension MPPT minimale (V).')
    ond_mppt_v_max = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Tension MPPT maximale (V).')
    ond_v_max_abs = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Tension DC maximale absolue (V).')
    ond_i_max_mppt_a = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text='Courant maximal par entrée MPPT (A).')
    ond_ac_kw = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Puissance AC nominale (kW).')

    class Phases(models.IntegerChoices):
        MONOPHASE = 1, 'Monophasé'
        TRIPHASE = 3, 'Triphasé'

    ond_phases = models.PositiveSmallIntegerField(
        choices=Phases.choices, null=True, blank=True,
        help_text='Nombre de phases (1 = monophasé, 3 = triphasé).')
    ond_rendement_euro_pct = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text='Rendement européen de l\'onduleur (%).')

    # ── PVOND-H (fondateur 19/08/2026) — « i was expecting to get battery
    # voltage... have a place for every one of this information ». Trois
    # variables que le moteur électrique (core.electrique.types.SpecOnduleur)
    # sait déjà lire mais qui n'avaient AUCUN champ dédié :
    #   • la plage de tension batterie vivait en texte libre dans
    #     Produit.description (ligne « Plage batterie : … », cf.
    #     apps/stock/selectors.py::plage_batterie_onduleur) ;
    #   • tension de démarrage et Isc max par MPPT n'étaient nulle part —
    #     seedées en commentaire (« NON seedés faute de champ »), jamais
    #     saisissables. Tout optionnel/additif : une fiche existante n'est pas
    #     impactée, et ``plage_batterie_onduleur`` garde son repli sur
    #     l'ancienne ligne de description pour une fiche pas encore migrée.
    ond_v_demarrage_v = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text="Tension de démarrage (V). À défaut, le bas de la plage MPPT fait foi.")
    ond_isc_max_mppt_a = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text='Courant de court-circuit (Isc) maximal admissible par entrée MPPT (A) '
                  '— borne matérielle, distincte du courant maximal de fonctionnement '
                  "ci-dessus. À défaut, c'est ce dernier qui fait foi.")
    ond_bat_aucune = models.BooleanField(
        default=False,
        help_text='Déclaration explicite : cet onduleur ne prend AUCUNE batterie '
                  '(réseau / string on-grid). Prioritaire sur la plage min/max ci-dessous.')
    ond_bat_v_min = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Plage de tension batterie compatible — borne basse (V). '
                  'Onduleur hybride uniquement.')
    ond_bat_v_max = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Plage de tension batterie compatible — borne haute (V). '
                  'Onduleur hybride uniquement.')

    # ── L-DECH (fondateur 24/08/2026) — « mais l'onduleur aussi a un max de
    # charge et de décharge, cherche bien et rajoute aussi ces numéros ».
    #
    # LE PORT BATTERIE EST UN GOULOT À PART ENTIÈRE. Deux packs qui rendent
    # 5,12 kW chacun derrière un onduleur dont le port n'admet que 6,14 kW ne
    # servent PAS 10,24 kW à la pointe : le chemin batterie vaut
    # ``min(Σ packs, port onduleur)``, dans LES DEUX SENS (un surplus de 8 kW
    # ne charge pas plus vite que le port ne l'accepte non plus).
    #
    # Les datasheets Deye publient ces bornes en AMPÈRES sur la ligne
    # « Max. Charging/Discharging Current » du bloc « Battery Input Data » ;
    # ``seed_catalogue`` les convertit en kW à 51,2 V — la MÊME convention de
    # tension que ``bat_v_nominal`` des packs du catalogue, pour que les deux
    # bornes soient comparables par un ``min()`` (le détail de la conversion et
    # de son choix de tension est écrit SKU par SKU dans le seeder).
    ond_bat_max_charge_kw = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Puissance de CHARGE maximale du port batterie (kW). '
                  'Onduleur hybride uniquement.')
    ond_bat_max_decharge_kw = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Puissance de DÉCHARGE maximale du port batterie (kW). '
                  'Onduleur hybride uniquement.')

    # ── CAL115 — chaînes par MPPT, entrées par MPPT, puissance apparente
    # max. de l'onduleur. ──
    #
    # ``ond_n_mppt``, les plages MPPT, ``ond_v_max_abs``,
    # ``ond_i_max_mppt_a``, ``ond_isc_max_mppt_a`` existent déjà — mais rien
    # ne dit COMBIEN de chaînes une entrée accepte, ni la puissance
    # apparente (kVA), ni la puissance DC maximale recommandée. PVsyst
    # modélise 8-12 entrées MPPT avec limitation de courant PAR entrée.
    #
    # TOUS OPTIONNELS — vide = non publié.
    ond_entrees_par_mppt = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Nombre d'entrées (chaînes physiques) par tracker MPPT. "
                  'Vide = non publié.')
    ond_chaines_max_par_mppt = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Nombre maximal de chaînes acceptées par tracker MPPT. '
                  'Vide = non publié.')
    ond_s_max_kva = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Puissance apparente AC maximale (kVA). Vide = non '
                  'publié.')
    ond_dc_max_kwc = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Puissance DC maximale recommandée (kWc). Vide = non '
                  'publié.')

    # ── CALX60 — le RENDEMENT de l'onduleur n'est pas UN nombre, et sa
    # consommation de veille n'est pas une perte en pourcentage. ──
    #
    # La fiche ne portait qu'un rendement européen unique
    # (``ond_rendement_euro_pct``) : une moyenne pondérée, pas le rendement
    # de l'heure qu'on calcule. PV*SOL écrit la conversion
    # ``P_AC = P_DC · η_nominal · η_relatif``, où η_relatif est une COURBE de
    # la puissance d'entrée, publiée par tension d'entrée
    # (https://help.valentin-software.com/pvsol/en/calculation/inverters/) —
    # c'est ce que l'étape « onduleur » (CALX170) veut lire, avec le
    # rendement européen en second recours et l'omission en troisième.
    # La consommation de VEILLE/nuit (CALX175) est une énergie réellement
    # soutirée en watts, jamais un pourcentage : elle a son propre champ.
    #
    # ``ond_s_max_kva`` demandé par l'énoncé « si absent » EXISTE DÉJÀ
    # (CAL115, juste au-dessus) : rien n'est ajouté pour lui.
    #
    # TOUS OPTIONNELS — vide = non publié, l'étape s'omet en nommant le
    # champ et le produit (D-CALX 7).
    ond_courbe_rendement = models.JSONField(
        null=True, blank=True,
        validators=[valider_courbe_rendement_onduleur],
        help_text='Courbe de rendement publiée : [{"charge_pct": 30, '
                  '"rendement_pct": 97.2, "tension_v": 360}, …] — le '
                  'rendement à chaque taux de charge, et la tension '
                  "d'entrée de la courbe (facultative : plusieurs courbes "
                  'peuvent coexister, une par tension). Vide = non '
                  'publiée.')
    ond_rendement_max_pct = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal('1')),
                    MaxValueValidator(Decimal('100'))],
        help_text='Rendement MAXIMAL publié (%, « peak efficiency »). '
                  'Vide = non publié.')
    ond_rendement_cec_pct = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal('1')),
                    MaxValueValidator(Decimal('100'))],
        help_text='Rendement pondéré CEC publié (%, pondération '
                  'californienne). Vide = non publié.')
    ond_conso_nuit_w = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Consommation de NUIT / veille publiée (W). Énergie '
                  'réellement soutirée, jamais un pourcentage. Vide = non '
                  'publiée.')

    # ── PV5 — Batterie ──
    bat_kwh_nominal = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Capacité nominale (kWh).')
    bat_kwh_usable = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Capacité utilisable (kWh).')
    bat_dod_pct = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text='Profondeur de décharge (DoD, %).')
    bat_v_nominal = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text='Tension nominale (V).')
    bat_max_charge_kw = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Puissance de charge maximale (kW).')
    # ── L-DECH (fondateur 24/08/2026) — « pour la décharge, source-la, mais en
    # général c'est 100 A multiplié par les 52 V ».
    #
    # LA PUISSANCE QUI MANQUAIT. ``bat_max_charge_kw`` existait seul, et le
    # moteur horaire (L-GLITCH, ``apps/ventes/etude_horaire.py``) le disait
    # noir sur blanc : sans décharge PUBLIÉE, il applique une règle
    # conservatrice et laisse la pointe partir au réseau. Ce champ est celui
    # qu'il attendait. Il ne se DÉDUIT jamais de la charge — un pack peut
    # accepter 75 A et en rendre 100 (c'est exactement le cas du DL5.0C) :
    # recopier l'une dans l'autre inventerait une équivalence que le
    # constructeur ne publie pas.
    #
    # PAR PACK, et ADDITIF EN PARALLÈLE (précision fondateur du même jour :
    # « n'oublie pas de considérer le cas avec deux batteries où c'est 100 A
    # par batterie ») : la borne d'une composition vaut Σ (valeur de fiche ×
    # quantité de la ligne), chaque unité à SA valeur.
    bat_max_decharge_kw = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Puissance de décharge maximale (kW), par pack.')
    # BATHOMO (fondateur 26/08/2026) — « add it as parameter... for now keep
    # it very high for 5kwh — maybe 200 ». Le PLAFOND fondateur du nombre de
    # modules IDENTIQUES qu'un même banc peut empiler pour CE produit (une
    # limite fabricant d'assemblage série/parallèle, jamais une limite
    # inventée par le moteur). ``None`` = ILLIMITÉ (repli byte-identique à
    # l'historique — aucun produit n'était borné avant ce champ). Une banque
    # candidate qui exigerait plus de modules que cette limite est REJETÉE en
    # sélection (``apps.ventes.services.composition_residentielle``), jamais
    # tronquée à la limite (une banque tronquée n'atteindrait plus la cible).
    # F3 (revue 26/08/2026) — LE CHAMP SIGNIFIE « limite ≥ 1, vide =
    # illimité » : 0 n'est pas une limite, c'est une banque IMPOSSIBLE (toute
    # candidate serait rejetée, y compris via un pin — un « avec batterie »
    # muet). ``MinValueValidator(1)`` l'interdit à la saisie (formulaire ET
    # API) plutôt que de le laisser produire un vivier vide silencieux.
    bat_max_modules_par_banc = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1)],
        help_text='Nombre MAXIMUM de modules identiques dans un même banc '
                  '(limite ≥ 1). Vide = illimité.')
    # QJR137 (audit QJR79) — LE RENDEMENT ALLER-RETOUR, ENFIN SOURÇABLE.
    #
    # La CAPACITÉ était déjà lue sur la fiche (``bat_kwh_usable``, sinon
    # ``bat_kwh_nominal × bat_dod_pct``) : la profondeur de décharge était donc
    # SOURCÉE. Le rendement aller-retour, lui, restait un forfait de code
    # (``quote_engine.pricing.BATTERY_ROUNDTRIP`` = 0,90) qu'aucun champ ne
    # pouvait porter — alors qu'il borne ``restitue_kwh`` du simulateur, donc
    # l'ÉCONOMIE « avec batterie » montrée au client. Les datasheets le
    # publient (« Round-trip efficiency », « System efficiency ») ; ce champ est
    # celui qui manquait pour le saisir.
    #
    # Vide = NON PUBLIÉ, jamais 0 : le moteur applique alors l'hypothèse de
    # référence 0,90 et l'ÉCRIT dans les hypothèses affichées — la discipline
    # déjà appliquée à la provision de remplacement onduleur. La borne haute
    # est 100 % (un rendement > 100 % n'existe pas ; la borne basse ≥ 1 %
    # écarte la saisie de 0 qui rendrait toute restitution nulle en silence).
    bat_rendement_ar_pct = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal('1')),
                    MaxValueValidator(Decimal('100'))],
        help_text='Rendement aller-retour publié (%, « round-trip '
                  'efficiency »). Vide = non publié : le moteur applique '
                  'alors son hypothèse de référence et le dit.')

    # ── CAL118 — nombre de cycles publié & vieillissement calendaire. ──
    #
    # Le bloc batterie porte capacité/DoD/tension/puissances/rendement
    # aller-retour mais AUCUN nombre de cycles ni courbe de vieillissement ;
    # SAM (NREL) modélise explicitement la dégradation calendaire ET
    # cyclique. TOUS OPTIONNELS — vides = « non publiés ».
    bat_cycles_publies = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Nombre de cycles publié par le fabricant (à la '
                  'rétention de fin de vie ci-dessous). Vide = non publié.')
    bat_retention_fin_de_vie_pct = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal('1')),
                    MaxValueValidator(Decimal('100'))],
        help_text='Rétention de capacité publiée en fin de vie garantie '
                  '(% de la capacité nominale, ex. 80 %). Vide = non '
                  'publié.')
    bat_garantie_annees = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Durée de garantie publiée (années). Vide = non publié.')

    # ── CALX60 — le C-RATE, la CHIMIE et la PLAGE DE TEMPÉRATURE. ──
    #
    # Le bloc batterie portait des PUISSANCES en kW
    # (``bat_max_charge_kw``/``bat_max_decharge_kw``) mais aucun C-rate, et
    # les deux ne se déduisent pas l'un de l'autre : un C-rate se rapporte à
    # la capacité NOMINALE, une puissance publiée peut être bornée par
    # l'électronique du pack. Le déduire des kW déjà saisis fabriquerait un
    # chiffre que le constructeur ne publie pas (D-CALX 7) — ce champ se
    # SAISIT, il ne se calcule jamais.
    #
    # ``bat_eol_pct`` demandé par l'énoncé n'est PAS créé :
    # ``bat_retention_fin_de_vie_pct`` (CAL118, juste au-dessus) porte
    # exactement cette grandeur — la rétention de capacité publiée en fin de
    # vie garantie. Une seconde colonne aurait donné deux vérités pour une
    # seule donnée ; le sélecteur publie la clé ``eol_pct`` depuis ce champ
    # unique.
    #
    # TOUS OPTIONNELS — vide = non publié.
    class ChimieBatterie(models.TextChoices):
        LFP = 'lfp', 'LFP (lithium fer phosphate)'
        NMC = 'nmc', 'NMC (lithium nickel manganèse cobalt)'
        NCA = 'nca', 'NCA (lithium nickel cobalt aluminium)'
        LMO = 'lmo', 'LMO (lithium manganèse)'
        LTO = 'lto', 'LTO (titanate de lithium)'
        PLOMB_OUVERT = 'plomb_ouvert', 'Plomb ouvert (à entretien)'
        PLOMB_AGM = 'plomb_agm', 'Plomb AGM (étanche)'
        PLOMB_GEL = 'plomb_gel', 'Plomb gel (étanche)'
        AUTRE = 'autre', 'Autre (préciser sur la fiche produit)'

    bat_c_rate_charge = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='C-rate de CHARGE publié (ex. 0,50 C). Vide = non '
                  "publié : il n'est jamais déduit des kW saisis.")
    bat_c_rate_decharge = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='C-rate de DÉCHARGE publié (ex. 1,00 C). Vide = non '
                  "publié : il n'est jamais déduit des kW saisis.")
    bat_chimie = models.CharField(
        max_length=16, choices=ChimieBatterie.choices, blank=True,
        default='',
        help_text='Chimie de cellule publiée. Vide = non publiée.')
    bat_temp_min_c = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text='Température de fonctionnement MINIMALE publiée (°C). '
                  'Vide = non publiée.')
    bat_temp_max_c = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text='Température de fonctionnement MAXIMALE publiée (°C). '
                  'Vide = non publiée.')

    # ── CAL116 — Optimiseur de puissance / micro-onduleur
    # (``type_fiche='optimiseur'``). ──
    #
    # Aucun bloc n'existait pour ce composant : ``grep -n "optimiseur"
    # apps/ventes`` ne rendait que ``composition_deux_optimiseurs`` (un
    # comparateur de dimensionnement, sans rapport avec un optimiseur de
    # puissance). TOUS OPTIONNELS — vide = non publié.
    opt_pmax_in_w = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        help_text="Puissance d'entrée max. de l'optimiseur (Wc). Vide = "
                  'non publié.')
    opt_v_in_min = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text="Tension d'entrée minimale (V). Vide = non publié.")
    opt_v_in_max = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text="Tension d'entrée maximale (V). Vide = non publié.")
    opt_i_in_max_a = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text="Courant d'entrée maximal (A). Vide = non publié.")
    opt_rendement_pct = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text="Rendement de conversion publié (%). Vide = non publié.")
    opt_modules_par_optimiseur = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Nombre de modules gérés par optimiseur (1 ou 2, '
                  'typiquement). Vide = non publié.')

    # ── CALX60 — LA SORTIE de l'optimiseur / du micro-onduleur. ──
    #
    # Les six champs CAL116 ci-dessus décrivent tous l'ENTRÉE continue du
    # composant : ce qu'il accepte des modules. Rien ne décrit ce qu'il REND,
    # alors que c'est la sortie qui décide du câblage — combien d'unités
    # tiennent sur une branche, quelle tension de chaîne un optimiseur
    # construit, quel courant alternatif une branche de micro-onduleurs
    # transporte. OpenSolar traite d'ailleurs le micro-onduleur comme un
    # chemin de conception à part entière
    # (https://support.opensolar.com/hc/en-us/articles/4406931180313-Stringing-Micro-Inverters-and-Power-Optimizers).
    #
    # UN SEUL bloc pour les deux composants, comme ``type_fiche='optimiseur'``
    # les réunit déjà : les champs ``opt_ac_*`` ne se remplissent que sur un
    # micro-onduleur (sortie alternative), les ``opt_v_out_*``/``opt_i_out_*``
    # que sur un optimiseur (sortie continue). Vide = non publié ; aucune
    # conversion n'est déduite de l'autre famille.
    opt_ac_kw = models.DecimalField(
        max_digits=7, decimal_places=3, null=True, blank=True,
        help_text='Micro-onduleur — puissance AC nominale (kW ; trois '
                  'décimales parce que ces fiches se publient en watts, '
                  'ex. 0,365 kW). Vide = non publiée.')
    opt_ac_tension_v = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Micro-onduleur — tension AC nominale de sortie (V). '
                  'Vide = non publiée.')
    opt_ac_i_max_a = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Micro-onduleur — courant AC maximal de sortie (A). '
                  'Vide = non publié.')
    opt_ac_unites_max_par_branche = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)],
        help_text="Micro-onduleur — nombre maximal d'unités admises sur une "
                  'même branche AC. Vide = non publié.')
    opt_v_out_nominal_v = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Optimiseur — tension de sortie NOMINALE (V). Vide = non '
                  'publiée.')
    opt_v_out_min = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Optimiseur — tension de sortie minimale (V). Vide = non '
                  'publiée.')
    opt_v_out_max = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Optimiseur — tension de sortie maximale (V). Vide = non '
                  'publiée.')
    opt_i_out_max_a = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text='Optimiseur — courant de sortie maximal (A). Vide = non '
                  'publié.')
    opt_pmax_out_w = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        help_text='Optimiseur — puissance de sortie maximale (W). Vide = '
                  'non publiée.')
    opt_modules_max_par_chaine = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)],
        help_text='Nombre maximal de modules équipés admis sur une même '
                  'chaîne. Vide = non publié.')

    # ── AGR101 — fiche « pompe » (type_fiche='pompe'). Chaque champ est la
    # valeur PUBLIÉE par la fiche du modèle EXACT ; vide = « non publié »,
    # jamais 0 ni une constante codée. ──
    pompe_i_nominal_a = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Pompe — courant nominal (A). Vide = non publié.')
    pompe_diametre_ext_mm = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Pompe — diamètre extérieur (mm). Vide = non publié.')
    pompe_nb_etages = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Pompe — nombre d'étages. Vide = non publié.")
    pompe_immersion_min_m = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Pompe — immersion minimale (m). Vide = non publié.')
    pompe_rendement_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Pompe — rendement au point nominal (%). Vide = non publié.')
    pompe_q_nominal_m3h = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        help_text='Pompe — débit nominal (m³/h). Vide = non publié.')
    pompe_hmt_nominale_m = models.DecimalField(
        max_digits=7, decimal_places=1, null=True, blank=True,
        help_text='Pompe — HMT au débit nominal (m). Vide = non publié.')

    # ── AGR101 — fiche « variateur de pompage » (type_fiche=
    # 'variateur_pompage'). Réutilise les champs onduleur ``ond_*`` que
    # ``core.electrique.chaines`` lit déjà (fenêtre MPPT, V max, I max,
    # phases, démarrage) ; n'ajoute que ceux-ci. Aucune plage VEICHI codée. ──
    var_voc_reco_min_v = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Variateur — Voc recommandée mini du champ (V).')
    var_voc_reco_max_v = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Variateur — Voc recommandée maxi du champ (V).')
    var_v_sortie_v = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Variateur — tension de sortie vers la pompe (V).')
    var_i_sortie_nominal_a = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text='Variateur — courant de sortie nominal (A).')
    var_protection_marche_a_sec = models.BooleanField(
        null=True, blank=True,
        help_text='Variateur — protection marche à sec intégrée '
                  '(vide = non publié).')
    var_rendement_mppt_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Variateur — rendement MPPT (%). Vide = non publié.')

    # ── PDF constructeur d'origine (optionnel) ──
    #
    # AUD835 — LEGACY, jamais réécrit : ce ``FileField`` écrivait sur le disque
    # du conteneur, sans ``MEDIA_URL``/``MEDIA_ROOT``, sans route ``/media/``,
    # sans ``location /media/`` nginx — le PDF n'était téléchargeable par
    # personne. Le contenu vit désormais dans MinIO (``records.storage``),
    # désigné par ``pdf_key``.
    pdf = models.FileField(
        upload_to='stock/fiches_techniques/%Y/%m/', null=True, blank=True,
        help_text='Fiche technique PDF du constructeur (legacy, hors MinIO).')
    pdf_key = models.CharField(
        max_length=500, blank=True, default='', verbose_name='Clé de stockage')
    pdf_filename = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Nom du fichier')
    pdf_size = models.PositiveIntegerField(
        default=0, verbose_name='Taille (octets)')
    pdf_mime = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Type MIME')

    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Fiche technique'
        verbose_name_plural = 'Fiches techniques'
        ordering = ['-date_mise_a_jour']

    def __str__(self):
        return f'Fiche technique — {self.produit_id}'
