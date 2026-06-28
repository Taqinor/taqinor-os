"""Services de la Paie marocaine — valeurs légales par défaut (PAIE3/PAIE5).

``ensure_defaults(company)`` provisionne, pour une société, le jeu de
constantes sociales (``ParametrePaie``) et le barème IR mensuel
(``BaremeIR`` + ``TrancheIR``) **officiels 2026**, à la ``date_effet`` du
1ᵉʳ janvier 2026. Les valeurs sont préremplies mais restent ÉDITABLES :
le drapeau ``valide_par_fondateur`` part à ``False`` jusqu'à confirmation
explicite du fondateur (qui peut aussi les surcharger via l'API).

L'opération est IDEMPOTENTE et purement additive : elle est ancrée sur la
clé stable ``(company, date_effet=2026-01-01)``. Re-jouée, elle ne crée aucun
doublon et ne touche jamais une ligne existante (une valeur éditée par le
fondateur survit donc à un re-seed).

PAIE5 — ``compute_ir(...)`` calcule l'Impôt sur le Revenu mensuel : il applique
le barème par tranche (taux × base − somme à déduire de la tranche couvrante),
puis retranche la **déduction pour charges de famille** (montant par personne à
charge × nombre de personnes, plafonné au nombre maximal). L'IR ne descend
jamais sous zéro.

DÉCISION (consentement permanent du fondateur) : les chiffres ci-dessous sont
les valeurs couramment citées du cadre social marocain 2026 (y compris la
déduction pour charges de famille — ≈ 30 MAD/mois et par personne, plafond 6).
Ils servent de DÉFAUTS éditables — ``valide_par_fondateur=False`` matérialise
qu'ils restent à confirmer.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from .models import (
    BaremeIR,
    ElementVariable,
    ParametrePaie,
    PeriodePaie,
    Rubrique,
    TrancheIR,
)

# ── Date d'effet des valeurs légales par défaut ────────────────────────────
DATE_EFFET_2026 = date(2026, 1, 1)

# ── Constantes sociales 2026 (ParametrePaie) ───────────────────────────────
# SMIG/SMAG, plafond & taux CNSS/AMO, taxe de formation pro, frais pro.
PARAMETRES_DEFAUT_2026 = {
    'smig': Decimal('3111.39'),          # SMIG mensuel (169 h)
    'smag': Decimal('2828.71'),          # SMAG mensuel agricole
    'plafond_cnss': Decimal('6000'),     # plafond CNSS mensuel
    'taux_cnss_salarial': Decimal('4.48'),
    'taux_cnss_patronal': Decimal('8.98'),
    'taux_amo_salarial': Decimal('2.26'),
    'taux_amo_patronal': Decimal('2.26'),
    'taux_formation_pro': Decimal('1.6'),
    # Frais professionnels (déduction IR) :
    'seuil_frais_pro': Decimal('6500'),
    'taux_frais_pro_bas': Decimal('35'),
    'plafond_frais_pro_bas': Decimal('2500'),
    'taux_frais_pro_haut': Decimal('25'),
    'plafond_frais_pro_haut': Decimal('2916.67'),
    # Déduction pour charges de famille (PAIE5) — déduction directe sur l'IR :
    # 30 MAD/mois par personne à charge, plafonnée à 6 personnes (→ 360 MAD/mois).
    'deduction_par_personne_a_charge': Decimal('30'),
    'plafond_personnes_a_charge': 6,
    # PAIE14 — Taux de majoration des heures supplémentaires (cadre marocain).
    # Code du travail : 25 % HS jour semaine, 50 % HS nuit, 100 % HS férié/dim.
    'taux_hs_jour': Decimal('25'),
    'taux_hs_nuit': Decimal('50'),
    'taux_hs_ferie': Decimal('100'),
    # PAIE15 — Barème d'ancienneté (cadre marocain standard).
    # 5 % après 2 ans, 10 % après 5 ans, 15 % après 12 ans,
    # 20 % après 20 ans, 25 % après 25 ans.
    'anciennete_seuil_1': 2,
    'anciennete_taux_1': Decimal('5'),
    'anciennete_seuil_2': 5,
    'anciennete_taux_2': Decimal('10'),
    'anciennete_seuil_3': 12,
    'anciennete_taux_3': Decimal('15'),
    'anciennete_seuil_4': 20,
    'anciennete_taux_4': Decimal('20'),
    'anciennete_seuil_5': 25,
    'anciennete_taux_5': Decimal('25'),
}

# ── Barème IR mensuel 2026 (TrancheIR) ──────────────────────────────────────
# (borne_min, borne_max, taux %, somme_à_déduire). La dernière tranche a une
# ``borne_max`` nulle (sans plafond supérieur).
TRANCHES_IR_2026 = [
    (Decimal('0'),        Decimal('2500'),  Decimal('0'),  Decimal('0')),
    (Decimal('2500.01'),  Decimal('4166.67'), Decimal('10'), Decimal('250')),
    (Decimal('4166.68'),  Decimal('5000'),  Decimal('20'), Decimal('666.67')),
    (Decimal('5000.01'),  Decimal('6666.67'), Decimal('30'), Decimal('1166.67')),
    (Decimal('6666.68'),  Decimal('15000'), Decimal('34'), Decimal('1433.33')),
    (Decimal('15000.01'), None,             Decimal('38'), Decimal('2033.33')),
]


def ensure_defaults(company):
    """Provisionne (idempotent) les valeurs légales 2026 pour ``company``.

    Crée, si absents, le ``ParametrePaie`` et le ``BaremeIR`` (+ ses
    ``TrancheIR``) au 1ᵉʳ janvier 2026, ``valide_par_fondateur=False``.
    Ne touche jamais une ligne déjà présente. Retourne un dict du nombre
    d'objets créés ::

        {'parametre': 0|1, 'bareme': 0|1, 'tranches': N}

    Réutilisable comme helper depuis d'autres modules de paie.
    """
    created = {'parametre': 0, 'bareme': 0, 'tranches': 0}

    _, param_new = ParametrePaie.objects.get_or_create(
        company=company,
        date_effet=DATE_EFFET_2026,
        defaults={**PARAMETRES_DEFAUT_2026, 'valide_par_fondateur': False},
    )
    if param_new:
        created['parametre'] = 1

    bareme, bareme_new = BaremeIR.objects.get_or_create(
        company=company,
        date_effet=DATE_EFFET_2026,
        defaults={
            'libelle': 'Barème IR 2026',
            'valide_par_fondateur': False,
        },
    )
    if bareme_new:
        created['bareme'] = 1
        for ordre, (bmin, bmax, taux, somme) in enumerate(
                TRANCHES_IR_2026, start=1):
            TrancheIR.objects.create(
                company=company,
                bareme=bareme,
                borne_min=bmin,
                borne_max=bmax,
                taux=taux,
                somme_a_deduire=somme,
                ordre=ordre,
            )
            created['tranches'] += 1

    return created


# ── PAIE5 — Calcul de l'IR + déduction pour charges de famille ──────────────

def _tranche_couvrante(bareme, base):
    """Renvoie la ``TrancheIR`` de ``bareme`` couvrant ``base`` (ou ``None``).

    Une tranche couvre ``base`` quand ``borne_min <= base`` et
    (``borne_max is None`` ou ``base <= borne_max``). Les tranches sont
    parcourues dans l'ordre du barème ; la dernière tranche, sans plafond
    supérieur, capte tous les revenus élevés.
    """
    for tranche in bareme.tranches.order_by('ordre'):
        if base < tranche.borne_min:
            continue
        if tranche.borne_max is None or base <= tranche.borne_max:
            return tranche
    return None


def ir_bareme(bareme, base):
    """IR brut (avant charges de famille) pour ``base`` selon ``bareme``.

    Formule par tranche du barème marocain : ``base × taux% −
    somme_a_deduire`` de la tranche couvrante. Jamais négatif. Sans tranche
    couvrante (base sous la 1ʳᵉ borne), l'IR est nul.
    """
    base = Decimal(base)
    tranche = _tranche_couvrante(bareme, base)
    if tranche is None:
        return Decimal('0.00')
    impot = base * (tranche.taux / Decimal('100')) - tranche.somme_a_deduire
    if impot < 0:
        return Decimal('0.00')
    return impot.quantize(Decimal('0.01'))


def deduction_charges_famille(parametre, personnes_a_charge):
    """Déduction mensuelle pour charges de famille (PAIE5).

    ``min(personnes_a_charge, plafond) × montant_par_personne``. Le nombre de
    personnes pris en compte est borné par ``plafond_personnes_a_charge`` du
    ``parametre`` (un nombre négatif est traité comme 0).
    """
    nombre = max(0, int(personnes_a_charge or 0))
    plafond = int(parametre.plafond_personnes_a_charge or 0)
    retenu = min(nombre, plafond)
    montant = parametre.deduction_par_personne_a_charge * Decimal(retenu)
    return montant.quantize(Decimal('0.01'))


def compute_ir(base, bareme, parametre, personnes_a_charge=0):
    """IR net mensuel = barème(base) − déduction charges de famille.

    Applique le barème par tranche puis retranche la déduction pour charges de
    famille (plafonnée). L'IR net ne descend jamais sous zéro. ``base`` est le
    revenu net imposable mensuel ; ``personnes_a_charge`` le nombre de personnes
    à charge du salarié.
    """
    brut = ir_bareme(bareme, base)
    deduction = deduction_charges_famille(parametre, personnes_a_charge)
    net = brut - deduction
    if net < 0:
        return Decimal('0.00')
    return net.quantize(Decimal('0.01'))


# ── PAIE6 — Rubriques de paie standard (catalogue par défaut) ───────────────
# Jeu standard de rubriques de bulletin marocain. Chaque entrée :
# code, libellé, type, (imposable, soumis_cnss, soumis_amo, soumis_cimr),
# compte comptable, ordre. Valeurs ÉDITABLES — pures défauts.
RUBRIQUES_DEFAUT = [
    # code, libelle, type, imposable, cnss, amo, cimr, compte, ordre
    ('SB', 'Salaire de base', Rubrique.TYPE_GAIN,
     True, True, True, True, '6411', 10),
    ('PRIME', 'Prime', Rubrique.TYPE_GAIN,
     True, True, True, True, '6411', 20),
    ('HS', 'Heures supplémentaires', Rubrique.TYPE_GAIN,
     True, True, True, True, '6411', 30),
    ('CNSS', 'Cotisation CNSS (part salariale)', Rubrique.TYPE_COTISATION,
     False, False, False, False, '4441', 40),
    ('AMO', 'Cotisation AMO (part salariale)', Rubrique.TYPE_COTISATION,
     False, False, False, False, '4441', 50),
    ('IR', 'Impôt sur le Revenu', Rubrique.TYPE_RETENUE,
     False, False, False, False, '4452', 60),
    ('AVANCE', 'Avance / acompte', Rubrique.TYPE_RETENUE,
     False, False, False, False, '3431', 70),
]

# ── PAIE7 — Catalogue de rubriques STANDARD additionnelles ──────────────────
# Rubriques usuelles du bulletin marocain non encore au catalogue de base :
# indemnités/primes (transport, panier, ancienneté, représentation, logement,
# responsabilité) avec leur régime fiscal/social usuel, et la cotisation CIMR.
# Indemnité de transport et de panier sont non imposables et non soumises CNSS
# dans la limite des plafonds réglementaires (régime simplifié ici : exonérées).
# Valeurs ÉDITABLES — pures défauts, additif et idempotent.
RUBRIQUES_STANDARD = [
    # code, libelle, type, imposable, cnss, amo, cimr, compte, ordre
    ('TRANSPORT', 'Indemnité de transport', Rubrique.TYPE_GAIN,
     False, False, False, False, '6411', 22),
    ('PANIER', 'Indemnité de panier', Rubrique.TYPE_GAIN,
     False, False, False, False, '6411', 24),
    ('ANCIENNETE', "Prime d'ancienneté", Rubrique.TYPE_GAIN,
     True, True, True, True, '6411', 26),
    ('REPRESENT', 'Indemnité de représentation', Rubrique.TYPE_GAIN,
     False, False, False, False, '6411', 28),
    ('LOGEMENT', 'Indemnité de logement', Rubrique.TYPE_GAIN,
     True, True, True, True, '6411', 29),
    ('RESPONSAB', 'Prime de responsabilité', Rubrique.TYPE_GAIN,
     True, True, True, True, '6411', 32),
    ('RENDEMENT', 'Prime de rendement', Rubrique.TYPE_GAIN,
     True, True, True, True, '6411', 34),
    ('CIMR', 'Cotisation CIMR (part salariale)', Rubrique.TYPE_COTISATION,
     False, False, False, False, '4443', 55),
]


def _ensure_rubriques(company, catalogue):
    """Crée (idempotent, additif) les rubriques d'un ``catalogue`` pour la société.

    Clé stable ``(company, code)`` : une rubrique déjà présente (éventuellement
    éditée par le fondateur) n'est jamais modifiée. Retourne le nombre créé.
    """
    cree = 0
    for (code, libelle, type_, imposable, cnss, amo, cimr,
         compte, ordre) in catalogue:
        _, new = Rubrique.objects.get_or_create(
            company=company,
            code=code,
            defaults={
                'libelle': libelle,
                'type': type_,
                'imposable': imposable,
                'soumis_cnss': cnss,
                'soumis_amo': amo,
                'soumis_cimr': cimr,
                'compte': compte,
                'ordre': ordre,
            },
        )
        if new:
            cree += 1
    return cree


def ensure_rubriques_defaut(company):
    """Provisionne (idempotent) les rubriques de BASE pour ``company``.

    Crée, si absentes, les rubriques du catalogue ``RUBRIQUES_DEFAUT`` (clé
    stable ``(company, code)``). Purement additif : une rubrique déjà présente
    (éventuellement éditée par le fondateur) n'est jamais modifiée. Retourne le
    nombre de rubriques créées ::

        {'rubriques': N}
    """
    return {'rubriques': _ensure_rubriques(company, RUBRIQUES_DEFAUT)}


def ensure_rubriques_standard(company):
    """Provisionne (idempotent) le catalogue de rubriques STANDARD (PAIE7).

    Sème les rubriques usuelles supplémentaires (transport, panier, ancienneté,
    CIMR…) du catalogue ``RUBRIQUES_STANDARD`` EN PLUS des rubriques de base.
    Strictement additif et idempotent (clé ``(company, code)``) : une rubrique
    déjà présente — de base ou éditée — n'est jamais touchée. Retourne ::

        {'rubriques': N}   # nombre total de rubriques créées (base + standard)
    """
    cree = _ensure_rubriques(company, RUBRIQUES_DEFAUT)
    cree += _ensure_rubriques(company, RUBRIQUES_STANDARD)
    return {'rubriques': cree}


# ── PAIE10 — Cycle de statuts d'une période de paie ────────────────────────

class TransitionPeriodeInterdite(Exception):
    """Transition de statut de période non autorisée (retour arrière interdit)."""


def changer_statut(periode, nouveau_statut):
    """Fait AVANCER une ``PeriodePaie`` vers ``nouveau_statut`` (PAIE10).

    Le cycle ``brouillon → calculee → validee → cloturee`` est strictement
    progressif : on ne peut qu'avancer (ou rester au même statut, no-op). Tout
    retour en arrière — ou un statut inconnu — lève
    ``TransitionPeriodeInterdite``. Pose ``date_cloture`` à la clôture. Renvoie
    la période rafraîchie.
    """
    ordre = PeriodePaie.ORDRE_STATUTS
    if nouveau_statut not in ordre:
        raise TransitionPeriodeInterdite(
            f"Statut inconnu : {nouveau_statut!r}.")
    courant = ordre.index(periode.statut)
    cible = ordre.index(nouveau_statut)
    if cible < courant:
        raise TransitionPeriodeInterdite(
            f"Retour en arrière interdit : "
            f"{periode.statut} → {nouveau_statut}.")
    if cible == courant:
        return periode
    periode.statut = nouveau_statut
    if nouveau_statut == PeriodePaie.STATUT_CLOTUREE:
        periode.date_cloture = timezone.now()
    periode.save(update_fields=['statut', 'date_cloture'])
    return periode


# ── PAIE11 — Import des éléments variables depuis RH ───────────────────────

def importer_elements_rh(periode):
    """Importe les éléments variables RH du mois pour une ``PeriodePaie`` (PAIE11).

    Pour chaque collaborateur ACTIF de la société DISPOSANT d'un profil de paie,
    matérialise ses éléments variables RH du mois (heures, heures sup, absences,
    primes) en ``ElementVariable`` de ``source='rh'``. La lecture RH passe par
    ``apps.rh.selectors`` (jamais ``rh.models`` directement).

    Idempotent par re-jouabilité : les éléments ``source='rh'`` de la période
    sont d'abord purgés puis recréés à partir de RH, de sorte qu'un ré-import
    reflète l'état RH courant sans dupliquer. La saisie manuelle
    (``source='manuel'``) n'est jamais touchée. La période doit être au statut
    ``brouillon`` (sinon ``TransitionPeriodeInterdite``). Renvoie le nombre
    d'éléments importés.

    NB : le détail des modèles d'heures/absences RH (FG192) n'étant pas encore
    posé, l'import s'appuie sur le sélecteur ``apps.rh.selectors`` et reste
    inerte (0 importé) tant que RH n'expose pas de données — il ne plante jamais.
    """
    from apps.rh import selectors as rh_selectors  # import paresseux (cross-app)

    if periode.statut != PeriodePaie.STATUT_BROUILLON:
        raise TransitionPeriodeInterdite(
            "L'import RH n'est possible qu'en statut brouillon.")

    from .models import ProfilPaie

    with transaction.atomic():
        ElementVariable.objects.filter(
            periode=periode, source=ElementVariable.SOURCE_RH).delete()

        profils = {
            p.employe_id: p
            for p in ProfilPaie.objects.filter(
                company=periode.company, actif=True)
        }
        importes = 0
        for dossier in rh_selectors.dossiers_actifs(periode.company):
            profil = profils.get(dossier.id)
            if profil is None:
                continue
            elements = _elements_rh_du_dossier(periode, dossier)
            for type_, libelle, quantite, montant in elements:
                ElementVariable.objects.create(
                    company=periode.company,
                    periode=periode,
                    profil=profil,
                    type=type_,
                    libelle=libelle,
                    quantite=quantite,
                    montant=montant,
                    source=ElementVariable.SOURCE_RH,
                )
                importes += 1
        return importes


def _elements_rh_du_dossier(periode, dossier):
    """Éléments variables RH d'un dossier pour la période — liste de tuples.

    Renvoie ``[(type, libelle, quantite, montant), …]``. Point d'extension de
    l'import RH (FG192) : tant que RH n'expose pas d'heures/absences du mois, on
    renvoie une liste vide (import inerte, jamais d'erreur).
    """
    return []


# ── PAIE13 — Calcul du salaire de base proraté selon le type de rémunération ─

def calculer_salaire_base_periode(profil, periode, elements=None):
    """Salaire de base proraté pour ``profil`` sur ``periode`` (PAIE13).

    Prend en compte le ``type_remuneration`` du profil :

    * **mensuel** — Le salaire mensuel contractuel est proraté quand l'employé
      n'a pas travaillé le mois complet : on déduit les jours d'absence
      (``ElementVariable.TYPE_ABSENCE``, exprimée en quantité = nombre de jours)
      et le résultat est borné à zéro.
      Formula : ``salaire_base × (jours_normes − jours_absence) / jours_normes``.

    * **journalier** — Le ``salaire_base`` est le taux JOURNALIER. Le brut est
      ``taux_journalier × jours_travailles``, où les jours travaillés proviennent
      soit d'un élément variable ``TYPE_HEURES`` (``quantite`` = jours), soit
      d'une déduction depuis les jours normes moins les absences.
      Formula : ``salaire_base × max(0, jours_normes − jours_absence)``.

    * **horaire** — Le ``salaire_base`` est le taux HORAIRE. Le brut est
      ``taux_horaire × heures_travaillees``, où les heures travaillées proviennent
      d'un élément variable ``TYPE_HEURES`` (``quantite`` = heures) ou d'une
      déduction depuis les heures normes moins les absences (converties en heures
      par le ratio ``heures_normes / jours_normes``).
      Formula : ``salaire_base × max(0, heures_normes − heures_absence)``.

    * **forfait** — Le ``salaire_base`` est un montant forfaitaire fixe, versé
      intégralement sans proration.

    ``elements`` est la liste des ``ElementVariable`` de la période pour ce profil
    (passée pour éviter un re-hit DB depuis ``calculer_bulletin``). Si ``None``,
    les éléments sont chargés depuis la base.

    Renvoie un ``Decimal`` arrondi au centime, >= 0.
    """
    from .models import ProfilPaie  # évite l'import circulaire au niveau module

    salaire_base = Decimal(profil.salaire_base or 0)
    type_rem = profil.type_remuneration

    if type_rem == ProfilPaie.TYPE_FORFAIT:
        # Forfait fixe : aucune proration.
        return _q(salaire_base)

    if elements is None:
        elements = list(
            ElementVariable.objects.filter(periode=periode, profil=profil)
        )

    # Comptabiliser les absences et les heures travaillées déclarées.
    jours_absence = Decimal('0')
    heures_travaillees_declares = None

    for el in elements:
        if el.type == ElementVariable.TYPE_ABSENCE:
            # Les absences sont en jours par convention dans ElementVariable.
            jours_absence += Decimal(el.quantite or 0)
        elif el.type == ElementVariable.TYPE_HEURES:
            # Des heures travaillées déclarées explicitement.
            heures_travaillees_declares = (
                (heures_travaillees_declares or Decimal('0'))
                + Decimal(el.quantite or 0)
            )

    jours_normes = Decimal(max(1, profil.jours_travail_mensuel or 26))
    heures_normes = Decimal(max(1, profil.heures_travail_mensuel or 191))

    if type_rem == ProfilPaie.TYPE_MENSUEL:
        # Proration : déduit les jours d'absence du plein mois.
        jours_effectifs = max(Decimal('0'), jours_normes - jours_absence)
        brut = salaire_base * jours_effectifs / jours_normes
        return _q(brut)

    if type_rem == ProfilPaie.TYPE_JOURNALIER:
        # Taux journalier × jours effectivement travaillés.
        if heures_travaillees_declares is not None:
            # Si des heures ont été déclarées, convertir en jours.
            ratio = heures_normes / jours_normes
            jours_de_heures = (
                heures_travaillees_declares / ratio if ratio else Decimal('0')
            )
            jours_effectifs = max(Decimal('0'), jours_de_heures - jours_absence)
        else:
            jours_effectifs = max(Decimal('0'), jours_normes - jours_absence)
        brut = salaire_base * jours_effectifs
        return _q(brut)

    if type_rem == ProfilPaie.TYPE_HORAIRE:
        # Taux horaire × heures effectivement travaillées.
        if heures_travaillees_declares is not None:
            heures_effectifs = heures_travaillees_declares
        else:
            # Déduit les absences (en jours) converties en heures.
            ratio = heures_normes / jours_normes if jours_normes else Decimal('1')
            heures_absence_h = jours_absence * ratio
            heures_effectifs = max(Decimal('0'), heures_normes - heures_absence_h)
        brut = salaire_base * heures_effectifs
        return _q(brut)

    # Fallback de sécurité (ne devrait pas arriver).
    return _q(salaire_base)


# ── PAIE15 — Prime d'ancienneté ───────────────────────────────────────────

def taux_anciennete(parametre, annees):
    """Taux d'ancienneté (%) applicable pour ``annees`` années de présence.

    Barème marocain par défaut (éditable sur ``ParametrePaie``) :

    * < seuil 1  → 0 %
    * >= seuil 1 → taux_1  (par défaut 5 % après 2 ans)
    * >= seuil 2 → taux_2  (par défaut 10 % après 5 ans)
    * >= seuil 3 → taux_3  (par défaut 15 % après 12 ans)
    * >= seuil 4 → taux_4  (par défaut 20 % après 20 ans)
    * >= seuil 5 → taux_5  (par défaut 25 % après 25 ans)

    Renvoie un ``Decimal``. Renvoie 0 si ``annees < seuil_1`` ou si
    ``parametre`` est ``None``.
    """
    if parametre is None:
        return Decimal('0')
    annees = int(annees or 0)
    # On parcourt les seuils du plus élevé au plus bas pour trouver le palier.
    niveaux = [
        (int(parametre.anciennete_seuil_5 or 25), Decimal(parametre.anciennete_taux_5 or 25)),
        (int(parametre.anciennete_seuil_4 or 20), Decimal(parametre.anciennete_taux_4 or 20)),
        (int(parametre.anciennete_seuil_3 or 12), Decimal(parametre.anciennete_taux_3 or 15)),
        (int(parametre.anciennete_seuil_2 or 5),  Decimal(parametre.anciennete_taux_2 or 10)),
        (int(parametre.anciennete_seuil_1 or 2),  Decimal(parametre.anciennete_taux_1 or 5)),
    ]
    for seuil, taux in niveaux:
        if annees >= seuil:
            return taux
    return Decimal('0')


def calculer_anciennete_annees(date_embauche, le_jour):
    """Nombre d'années COMPLÈTES d'ancienneté à la date ``le_jour``.

    Renvoie 0 si ``date_embauche`` est ``None`` ou postérieure à ``le_jour``.
    Calcul exact : on compare l'anniversaire pour tenir compte des années
    bissextiles (pas une simple division par 365).
    """
    if date_embauche is None or date_embauche > le_jour:
        return 0
    annees = le_jour.year - date_embauche.year
    # Soustraire 1 si l'anniversaire de cette année n'est pas encore atteint.
    # Gestion du 29 fév (embauche en année bissextile) : en année non-bissextile,
    # l'anniversaire est ramené au 28 fév.
    try:
        anniversaire_cette_annee = date_embauche.replace(year=le_jour.year)
    except ValueError:
        # 29 fév → 28 fév dans une année non-bissextile.
        anniversaire_cette_annee = date_embauche.replace(year=le_jour.year, day=28)
    if anniversaire_cette_annee > le_jour:
        annees -= 1
    return max(0, annees)


def calculer_prime_anciennete(profil, base, anciennete_annees, parametre):
    """Prime d'ancienneté pour un profil sur une base donnée (PAIE15).

    Formule : ``base × taux_anciennete(annees) / 100``.

    * ``profil`` — ``ProfilPaie`` de l'employé.
    * ``base`` — salaire de base servant d'assiette (brut de base, *avant*
      éléments variables) ; généralement ``profil.salaire_base`` ou le salaire
      proraté déjà calculé.
    * ``anciennete_annees`` — nombre d'années d'ancienneté complètes.
    * ``parametre`` — ``ParametrePaie`` en vigueur (barème).

    Renvoie un ``Decimal`` >= 0 arrondi au centime. Retourne 0 quand le taux
    résolu est 0 (ancienneté insuffisante) — aucun effet sur le bulletin.
    """
    taux = taux_anciennete(parametre, anciennete_annees)
    if taux == 0:
        return Decimal('0.00')
    prime = Decimal(base) * taux / Decimal('100')
    return _q(prime)


# ── PAIE14 — Heures supplémentaires majorées ───────────────────────────────

def taux_majoration_hs(parametre, categorie_hs):
    """Taux de majoration (%) pour une catégorie d'HS et un ``parametre``.

    Renvoie le ``Decimal`` correspondant à la catégorie :

    * ``'jour'``  → ``parametre.taux_hs_jour``  (défaut réglementaire : 25 %)
    * ``'nuit'``  → ``parametre.taux_hs_nuit``  (défaut : 50 %)
    * ``'ferie'`` → ``parametre.taux_hs_ferie`` (défaut : 100 %)
    * Valeur manquante / None → taux jour (25 %)
    """
    from .models import ElementVariable as EV

    if categorie_hs == EV.HS_NUIT:
        return Decimal(parametre.taux_hs_nuit or 50)
    if categorie_hs == EV.HS_FERIE:
        return Decimal(parametre.taux_hs_ferie or 100)
    # Défaut : HS jour (catégorie 'jour' ou valeur absente/inconnue).
    return Decimal(parametre.taux_hs_jour or 25)


def calculer_gain_hs(heures, taux_horaire_base, taux_majoration):
    """Gain brut pour des heures supplémentaires majorées (PAIE14).

    Formule : ``heures × taux_horaire_base × (1 + taux_majoration / 100)``.

    * ``heures`` — nombre d'heures supplémentaires effectuées.
    * ``taux_horaire_base`` — taux horaire de référence du salarié (MAD/h).
      Pour un salarié mensuel, il doit être calculé AVANT cet appel :
      ``salaire_base / heures_travail_mensuel``.
    * ``taux_majoration`` — taux de majoration en % (p. ex. 25, 50, 100).

    Renvoie un ``Decimal`` >= 0 arrondi au centime.
    """
    heures = Decimal(heures or 0)
    taux_h = Decimal(taux_horaire_base or 0)
    taux_m = Decimal(taux_majoration or 0)
    if heures <= 0 or taux_h <= 0:
        return Decimal('0.00')
    gain = heures * taux_h * (Decimal('1') + taux_m / Decimal('100'))
    return _q(gain)


def taux_horaire_base_profil(profil):
    """Taux horaire de base d'un profil (MAD/h), utilisé pour majorer les HS.

    * **horaire** : ``salaire_base`` est déjà le taux horaire.
    * **mensuel / journalier / forfait** : on dérive un taux horaire à partir du
      salaire mensuel divisé par la norme d'heures mensuelle du profil.
      Pour les types JOURNALIER et FORFAIT, ``salaire_base`` est traité comme
      un salaire mensuel de référence (comportement raisonnable en l'absence
      d'autres informations).

    Renvoie un ``Decimal``. Si la norme d'heures est nulle, retourne 0.
    """
    from .models import ProfilPaie

    salaire = Decimal(profil.salaire_base or 0)
    heures_normes = Decimal(max(1, profil.heures_travail_mensuel or 191))

    if profil.type_remuneration == ProfilPaie.TYPE_HORAIRE:
        return salaire  # déjà le taux horaire
    # Mensuel / journalier / forfait → dériver le taux horaire.
    return (salaire / heures_normes).quantize(
        Decimal('0.000001'), rounding=ROUND_HALF_UP)


# ── PAIE12 — Moteur de calcul du bulletin ──────────────────────────────────

_CENT = Decimal('0.01')


def _q(montant):
    """Arrondit un ``Decimal`` au centime (demi-supérieur)."""
    return Decimal(montant).quantize(_CENT, rounding=ROUND_HALF_UP)


def parametre_en_vigueur(company, le_jour):
    """``ParametrePaie`` en vigueur pour ``company`` au ``le_jour`` (ou None)."""
    return (
        ParametrePaie.objects
        .filter(company=company, date_effet__lte=le_jour)
        .order_by('-date_effet')
        .first()
    )


def bareme_en_vigueur(company, le_jour):
    """``BaremeIR`` en vigueur pour ``company`` au ``le_jour`` (ou None)."""
    return (
        BaremeIR.objects
        .filter(company=company, date_effet__lte=le_jour)
        .order_by('-date_effet')
        .first()
    )


def calculer_bulletin(profil, periode, personnes_a_charge=0):
    """Calcule le bulletin de paie d'un employé pour une période (PAIE12).

    Moteur de calcul conforme au cadre marocain (additif, sans effet de bord —
    ne crée aucun objet, renvoie un dict) :

    1. **Brut** = salaire de base du profil + gains des éléments variables du
       mois (primes/HS) − retenues d'éléments (avances/absences saisies en
       retenue).
    2. **CNSS** salariale = ``taux_cnss_salarial`` × ``min(brut, plafond_cnss)``
       si le profil est affilié CNSS.
    3. **AMO** salariale = ``taux_amo_salarial`` × brut (non plafonnée) si
       affilié AMO.
    4. **CIMR** salariale = ``taux_cimr_salarial`` du profil × brut si affilié
       CIMR.
    5. **Frais professionnels** : 35 % du brut imposable plafonné (≤ seuil) sinon
       25 % plafonné — d'après ``ParametrePaie``.
    6. **Net imposable** = brut imposable − (CNSS + AMO + CIMR + frais pro).
    7. **IR** = ``compute_ir`` (barème par tranche − déductions charges famille).
    8. **Net à payer** = brut − CNSS − AMO − CIMR − IR.

    Renvoie un dict détaillé (toutes valeurs ``Decimal`` au centime) prêt à être
    matérialisé en bulletin (PAIE17) : ::

        {'brut', 'brut_imposable', 'cnss_salariale', 'amo_salariale',
         'cimr_salariale', 'frais_professionnels', 'net_imposable', 'ir',
         'net_a_payer', 'lignes': [...]}

    Donnée SENSIBLE (salaires) — usage interne paie uniquement.
    """
    le_jour = date(periode.annee, periode.mois, 1)
    parametre = parametre_en_vigueur(profil.company, le_jour)
    bareme = bareme_en_vigueur(profil.company, le_jour)

    elements = list(
        ElementVariable.objects.filter(periode=periode, profil=profil)
        .select_related('rubrique')
    )

    # PAIE13 — salaire de base proraté selon le type de rémunération.
    salaire_base = calculer_salaire_base_periode(profil, periode, elements)
    gains_variables = Decimal('0')
    retenues_variables = Decimal('0')
    gains_imposables = Decimal('0')
    lignes = [{
        'code': 'SB', 'libelle': 'Salaire de base',
        'type': Rubrique.TYPE_GAIN, 'montant': _q(salaire_base),
    }]
    # PAIE14 — Taux horaire de base pour la majoration des HS.
    _taux_h_base = taux_horaire_base_profil(profil)

    # PAIE15 — Prime d'ancienneté : calculée sur le salaire de base proraté,
    # à partir de la date d'embauche lue via le sélecteur RH (cross-app).
    prime_anciennete = Decimal('0')
    if parametre is not None:
        from apps.rh import selectors as rh_selectors  # import paresseux cross-app
        date_embauche = rh_selectors.date_embauche_employe(
            profil.company, profil.employe_id)
        anciennete_annees = calculer_anciennete_annees(date_embauche, le_jour)
        prime_anciennete = calculer_prime_anciennete(
            profil, salaire_base, anciennete_annees, parametre)
    if prime_anciennete > 0:
        gains_variables += prime_anciennete
        gains_imposables += prime_anciennete  # la prime d'ancienneté est imposable
        lignes.append({
            'code': 'ANCIENNETE',
            'libelle': "Prime d'ancienneté",
            'type': Rubrique.TYPE_GAIN,
            'montant': prime_anciennete,
        })

    for el in elements:
        montant = Decimal(el.montant or 0)
        imposable = el.rubrique.imposable if el.rubrique_id else True
        if el.type == ElementVariable.TYPE_RETENUE or \
                el.type == ElementVariable.TYPE_ABSENCE:
            retenues_variables += montant
            lignes.append({
                'code': el.rubrique.code if el.rubrique_id else el.type,
                'libelle': el.libelle or el.get_type_display(),
                'type': Rubrique.TYPE_RETENUE, 'montant': _q(montant),
            })
        else:
            # PAIE14 — Heures supplémentaires : si la quantité est renseignée
            # et que les paramètres de paie sont disponibles, on CALCULE le
            # gain majoré depuis la quantité (heures) et le taux horaire de
            # base. Le ``montant`` stocké sert de SURCHARGE EXPLICITE :
            # si l'opérateur a saisi un montant non-nul, il prime sur le calcul.
            if (el.type == ElementVariable.TYPE_HS
                    and parametre is not None
                    and Decimal(el.quantite or 0) > 0
                    and montant == 0):
                taux_maj = taux_majoration_hs(parametre, el.categorie_hs)
                montant = calculer_gain_hs(el.quantite, _taux_h_base, taux_maj)
            gains_variables += montant
            if imposable:
                gains_imposables += montant
            lignes.append({
                'code': el.rubrique.code if el.rubrique_id else el.type,
                'libelle': el.libelle or el.get_type_display(),
                'type': Rubrique.TYPE_GAIN, 'montant': _q(montant),
            })

    brut = salaire_base + gains_variables
    # Le salaire de base est imposable et soumis aux cotisations.
    brut_imposable = salaire_base + gains_imposables

    # 2. CNSS plafonnée.
    cnss = Decimal('0')
    if parametre and profil.affilie_cnss:
        assiette_cnss = min(brut, Decimal(parametre.plafond_cnss or 0))
        cnss = assiette_cnss * Decimal(parametre.taux_cnss_salarial) / Decimal('100')
    cnss = _q(cnss)

    # 3. AMO (non plafonnée).
    amo = Decimal('0')
    if parametre and profil.affilie_amo:
        amo = brut * Decimal(parametre.taux_amo_salarial) / Decimal('100')
    amo = _q(amo)

    # 4. CIMR (taux propre au profil).
    cimr = Decimal('0')
    if profil.affilie_cimr:
        cimr = brut * Decimal(profil.taux_cimr_salarial or 0) / Decimal('100')
    cimr = _q(cimr)

    # 5. Frais professionnels.
    frais_pro = Decimal('0')
    if parametre:
        if brut_imposable <= Decimal(parametre.seuil_frais_pro or 0):
            frais_pro = brut_imposable * Decimal(parametre.taux_frais_pro_bas) / Decimal('100')
            plafond = Decimal(parametre.plafond_frais_pro_bas or 0)
        else:
            frais_pro = brut_imposable * Decimal(parametre.taux_frais_pro_haut) / Decimal('100')
            plafond = Decimal(parametre.plafond_frais_pro_haut or 0)
        if plafond and frais_pro > plafond:
            frais_pro = plafond
    frais_pro = _q(frais_pro)

    # 6. Net imposable.
    net_imposable = brut_imposable - cnss - amo - cimr - frais_pro
    if net_imposable < 0:
        net_imposable = Decimal('0')
    net_imposable = _q(net_imposable)

    # 7. IR.
    ir = Decimal('0')
    if bareme and parametre:
        ir = compute_ir(net_imposable, bareme, parametre, personnes_a_charge)
    ir = _q(ir)

    # 8. Net à payer (− retenues variables type avances).
    net_a_payer = brut - cnss - amo - cimr - ir - retenues_variables
    net_a_payer = _q(net_a_payer)

    return {
        'brut': _q(brut),
        'brut_imposable': _q(brut_imposable),
        'cnss_salariale': cnss,
        'amo_salariale': amo,
        'cimr_salariale': cimr,
        'frais_professionnels': frais_pro,
        'net_imposable': net_imposable,
        'ir': ir,
        'retenues': _q(retenues_variables),
        'net_a_payer': net_a_payer,
        'prime_anciennete': prime_anciennete,
        'lignes': lignes,
    }
