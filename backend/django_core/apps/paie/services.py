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
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from .models import (
    BaremeIR,
    EcheanceDeclarative,
    ElementVariable,
    ParametrePaie,
    PeriodePaie,
    Rubrique,
    TrancheIR,
    TypeEntreePonctuelle,
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
    # PAIE23 — Allocations familiales (charge patronale, non plafonnée, ~6,4 %).
    'taux_allocations_familiales': Decimal('6.4'),
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

# ── PAIE7 / PAIE16 — Catalogue de rubriques STANDARD additionnelles ─────────
# Rubriques usuelles du bulletin marocain non encore au catalogue de base :
# indemnités/primes (transport, panier, ancienneté, représentation, logement,
# responsabilité), avantages en nature (logement/voiture de fonction) et la
# cotisation CIMR, avec leur régime fiscal/social usuel.
#
# PAIE16 — Plafond d'exonération : transport, panier, déplacement et certains
# avantages sont EXONÉRÉS d'IR DANS LA LIMITE d'un plafond mensuel ; l'excédent
# est réintégré dans la base imposable. La 10ᵉ colonne ``plafond`` porte ce
# plafond (``None`` = pas de plafond, régime tout-ou-rien). La 11ᵉ colonne
# ``avantage_nature`` marque un avantage en nature (logé/voiture). Valeurs
# ÉDITABLES — pures défauts (à confirmer par le fondateur), additif et idempotent.
RUBRIQUES_STANDARD = [
    # code, libelle, type, imposable, cnss, amo, cimr, compte, ordre,
    #   plafond_exoneration, avantage_nature
    ('TRANSPORT', 'Indemnité de transport', Rubrique.TYPE_GAIN,
     False, False, False, False, '6411', 22, Decimal('500'), False),
    ('PANIER', 'Indemnité de panier', Rubrique.TYPE_GAIN,
     False, False, False, False, '6411', 24, Decimal('2200'), False),
    ('DEPLACEMENT', 'Indemnité de déplacement', Rubrique.TYPE_GAIN,
     False, False, False, False, '6411', 25, Decimal('5000'), False),
    ('ANCIENNETE', "Prime d'ancienneté", Rubrique.TYPE_GAIN,
     True, True, True, True, '6411', 26, None, False),
    ('REPRESENT', 'Indemnité de représentation', Rubrique.TYPE_GAIN,
     False, False, False, False, '6411', 28, Decimal('5000'), False),
    ('LOGEMENT', 'Indemnité de logement', Rubrique.TYPE_GAIN,
     True, True, True, True, '6411', 29, None, False),
    ('AV_LOGEMENT', 'Avantage en nature — logement', Rubrique.TYPE_GAIN,
     True, True, True, True, '6411', 30, None, True),
    ('AV_VOITURE', 'Avantage en nature — voiture de fonction',
     Rubrique.TYPE_GAIN, True, True, True, True, '6411', 31, None, True),
    ('RESPONSAB', 'Prime de responsabilité', Rubrique.TYPE_GAIN,
     True, True, True, True, '6411', 32, None, False),
    ('RENDEMENT', 'Prime de rendement', Rubrique.TYPE_GAIN,
     True, True, True, True, '6411', 34, None, False),
    ('CIMR', 'Cotisation CIMR (part salariale)', Rubrique.TYPE_COTISATION,
     False, False, False, False, '4443', 55, None, False),
]


def _ensure_rubriques(company, catalogue):
    """Crée (idempotent, additif) les rubriques d'un ``catalogue`` pour la société.

    Clé stable ``(company, code)`` : une rubrique déjà présente (éventuellement
    éditée par le fondateur) n'est jamais modifiée. Retourne le nombre créé.

    Chaque entrée du catalogue est un tuple de 9 colonnes ::

        (code, libelle, type, imposable, cnss, amo, cimr, compte, ordre)

    ou de 11 colonnes (PAIE16) avec, en plus ::

        … , plafond_exoneration, avantage_nature
    """
    cree = 0
    for entree in catalogue:
        code, libelle, type_, imposable, cnss, amo, cimr, compte, ordre = \
            entree[:9]
        # PAIE16 — colonnes optionnelles plafond d'exonération / avantage nature.
        plafond = entree[9] if len(entree) > 9 else None
        avantage_nature = entree[10] if len(entree) > 10 else False
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
                'plafond_exoneration': plafond,
                'avantage_nature': avantage_nature,
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


# ── ZPAI9 — Catalogue de types d'entrées ponctuelles (Other Input Types) ───

# Types COURANTS (DÉCISION — défaut éditable, consentement fondateur) :
# (code, libelle, sens, imposable, soumis_cnss, soumis_amo).
TYPES_ENTREE_PONCTUELLE_DEFAUT = [
    ('POURBOIRE', 'Pourboire', 'gain', True, True, True),
    ('REMB_FRAIS_NI', 'Remboursement de frais (non imposable)', 'gain',
     False, False, False),
    ('DEDUCTION_PONCT', 'Déduction ponctuelle', 'retenue', False, False, False),
]


def ensure_types_entree_ponctuelle_standard(company):
    """Provisionne (idempotent) le catalogue standard de types d'entrées (ZPAI9).

    Sème ``TYPES_ENTREE_PONCTUELLE_DEFAUT`` pour ``company`` — clé stable
    ``(company, code)`` : un type déjà présent (éventuellement édité) n'est
    JAMAIS modifié. Purement additif. Renvoie ``{'types': N}`` (nombre créé).
    """
    from .models import TypeEntreePonctuelle

    cree = 0
    for code, libelle, sens, imposable, cnss, amo in \
            TYPES_ENTREE_PONCTUELLE_DEFAUT:
        _, new = TypeEntreePonctuelle.objects.get_or_create(
            company=company, code=code,
            defaults={
                'libelle': libelle, 'sens': sens, 'imposable': imposable,
                'soumis_cnss': cnss, 'soumis_amo': amo,
            },
        )
        if new:
            cree += 1
    return {'types': cree}


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
    if nouveau_statut == PeriodePaie.STATUT_VALIDEE:
        # ARC39 — le run devient PRÊT (tous les bulletins validés) : notifie
        # les gestionnaires paie. Best-effort, jamais bloquant pour la
        # transition elle-même (déjà persistée ci-dessus).
        try:
            notifier_run_pret(periode)
        except Exception:  # pragma: no cover - défensif, best-effort
            pass
    return periode


def notifier_run_pret(periode):
    """Notifie (best-effort) les gestionnaires paie qu'un run est PRÊT (ARC39).

    Déclenché quand une ``PeriodePaie`` atteint le statut ``validee`` (tous
    ses bulletins sont validés — le run peut passer à la génération de
    l'ordre de virement / la clôture). Résout les destinataires via
    ``apps.notifications.resolve_recipients`` (repli Responsable/Admin),
    comme les autres notifications paie (ARC25, XPAI6, ZPAI12). Jamais
    bloquant : toute erreur est avalée par l'appelant (``changer_statut``).
    """
    from apps.notifications import services as notif_services

    company = periode.company
    recipients = notif_services.resolve_recipients(company, 'paie_run_pret')
    titre = f'Run de paie prêt ({periode.mois:02d}/{periode.annee})'
    corps = (
        f'La période {periode.mois:02d}/{periode.annee} est validée '
        '(tous les bulletins sont validés) — prête pour l\'ordre de '
        'virement / la clôture.')
    notif_services.notify_many(
        recipients, 'paie_run_pret', title=titre, body=corps,
        company=company)


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
            elements = _elements_rh_du_dossier(periode, dossier, profil)
            for el in elements:
                ElementVariable.objects.create(
                    company=periode.company,
                    periode=periode,
                    profil=profil,
                    type=el['type'],
                    libelle=el['libelle'],
                    quantite=el['quantite'],
                    montant=el['montant'],
                    categorie_hs=el.get(
                        'categorie_hs') or ElementVariable.HS_JOUR,
                    remunere=el.get('remunere', False),
                    deduit_solde=el.get('deduit_solde', False),
                    source=ElementVariable.SOURCE_RH,
                )
                importes += 1
        return importes


# ── ZPAI11 — Duplication des rubriques récurrentes vers une nouvelle période ─

def _mois_precedent(annee, mois):
    """``(annee, mois)`` du mois précédent."""
    if mois == 1:
        return annee - 1, 12
    return annee, mois - 1


def reporter_elements_periode(periode_cible):
    """Reconduit les éléments ``reconduire=True`` de M-1 vers ``periode_cible`` (ZPAI11).

    Cherche la ``PeriodePaie`` du mois calendaire précédent, même société et
    même ``type_run`` que ``periode_cible`` (aucune période précédente trouvée
    → no-op, renvoie ``[]``). Pour chaque ``ElementVariable`` de cette période
    marqué ``reconduire=True``, crée une COPIE dans ``periode_cible`` (même
    profil/type/rubrique/libellé/quantité/montant/flags, ``source='manuel'``,
    ``reconduit_depuis`` posé sur l'original) — IDEMPOTENT : la contrainte
    ``(periode, reconduit_depuis)`` empêche toute double-copie d'un même
    élément d'origine vers la même période cible (re-run silencieusement
    ignoré). Un élément NON reconductible n'est jamais copié. Renvoie la
    liste des nouvelles copies créées par CET appel (vide si toutes les
    copies existaient déjà).
    """
    annee_prec, mois_prec = _mois_precedent(
        periode_cible.annee, periode_cible.mois)
    periode_precedente = (
        PeriodePaie.objects
        .filter(
            company=periode_cible.company, annee=annee_prec, mois=mois_prec,
            type_run=periode_cible.type_run)
        .first()
    )
    if periode_precedente is None:
        return []

    a_reconduire = ElementVariable.objects.filter(
        periode=periode_precedente, reconduire=True)
    deja_copies = set(
        ElementVariable.objects
        .filter(periode=periode_cible, reconduit_depuis__isnull=False)
        .values_list('reconduit_depuis_id', flat=True)
    )

    copies = []
    with transaction.atomic():
        for original in a_reconduire:
            if original.id in deja_copies:
                continue
            copie = ElementVariable.objects.create(
                company=periode_cible.company,
                periode=periode_cible,
                profil=original.profil,
                type=original.type,
                rubrique=original.rubrique,
                libelle=original.libelle,
                quantite=original.quantite,
                categorie_hs=original.categorie_hs,
                montant=original.montant,
                remunere=original.remunere,
                deduit_solde=original.deduit_solde,
                categorie_absence=original.categorie_absence,
                type_entree=original.type_entree,
                reconduire=original.reconduire,
                reconduit_depuis=original,
                source=ElementVariable.SOURCE_MANUEL,
            )
            copies.append(copie)
    return copies


def _elements_rh_du_dossier(periode, dossier, profil=None):
    """Éléments variables RH d'un dossier pour la période — liste de tuples.

    YHIRE1 — câble réellement l'import (l'ancien stub renvoyait toujours
    ``[]``) : RH expose TOUT depuis trois sélecteurs fins de
    ``apps.rh.selectors`` (jamais ``rh.models`` directement) —

    * heures supplémentaires VALORISÉES (``heures_supp_pour_paie``, FG192) →
      une ligne ``TYPE_HS`` par tranche non nulle (jour/nuit/férié),
      ``montant`` déjà majoré. Si RH renvoie un ``montant_majore`` à 0 (le
      ``cout_horaire`` interne du dossier RH n'est pas configuré — donnée
      RH facultative) alors que des heures existent bel et bien, on retombe
      sur le taux horaire dérivé du PROFIL DE PAIE lui-même
      (``taux_horaire_base_profil`` + ``taux_majoration_hs``, PAIE14) : le
      salarié a un salaire de paie même sans coût horaire RH renseigné ;
    * demandes de congé VALIDÉES d'un ``TypeAbsence.remunere = False``
      (``absences_non_remunerees_pour_paie``) → une ligne ``TYPE_ABSENCE``
      (``remunere=False``, ``deduit_solde`` reprise du type) — la proration
      PAIE13 existante s'applique automatiquement (une absence RÉMUNÉRÉE
      n'a, par construction, aucune ligne ici : elle ne doit avoir aucun
      impact sur le net) ;
    * primes ``PrimeAttribuee`` VALIDÉES du mois
      (``primes_validees_pour_paie``) → une ligne ``TYPE_PRIME``.

    Renvoie une liste de dicts : ``{'type', 'libelle', 'quantite', 'montant',
    'categorie_hs'?, 'remunere'?, 'deduit_solde'?}``.
    """
    import calendar

    from apps.rh import selectors as rh_selectors

    date_debut = date(periode.annee, periode.mois, 1)
    date_fin = date(
        periode.annee, periode.mois,
        calendar.monthrange(periode.annee, periode.mois)[1])

    elements = []

    # ── Heures supplémentaires (FG168) ──────────────────────────────────
    hs_tranches = (
        ('hs_25', ElementVariable.HS_JOUR, 'Heures sup jour (25 %)'),
        ('hs_50', ElementVariable.HS_NUIT, 'Heures sup nuit (50 %)'),
        ('hs_100', ElementVariable.HS_FERIE,
         'Heures sup férié/dimanche (100 %)'),
    )
    parametre = parametre_en_vigueur(dossier.company, date_fin)
    taux_h_base_profil = (
        taux_horaire_base_profil(profil) if profil is not None else None)
    for ligne in rh_selectors.heures_supp_pour_paie(
            dossier.company, date_debut, date_fin, employe_id=dossier.id):
        total_tranches = sum(
            (ligne[cle] for cle, _cat, _lib in hs_tranches), Decimal('0'))
        for cle, categorie, libelle in hs_tranches:
            quantite = ligne.get(cle) or Decimal('0')
            if quantite <= 0:
                continue
            # Le montant déjà majoré est ventilé au prorata de la tranche
            # (le sélecteur ne renvoie qu'un montant total par employé).
            montant = ligne['montant_majore']
            if total_tranches > 0:
                montant = _q(
                    ligne['montant_majore'] * quantite / total_tranches)
            if (not montant) and parametre is not None \
                    and taux_h_base_profil:
                # RH n'a pas de coût horaire configuré pour ce dossier —
                # dérive le gain majoré du taux horaire du PROFIL DE PAIE.
                taux_maj = taux_majoration_hs(parametre, categorie)
                montant = calculer_gain_hs(
                    quantite, taux_h_base_profil, taux_maj)
            elements.append({
                'type': ElementVariable.TYPE_HS, 'libelle': libelle,
                'quantite': quantite, 'montant': montant,
                'categorie_hs': categorie,
            })

    # ── Absences non rémunérées validées (FG163/FG164) ──────────────────
    for absence in rh_selectors.absences_non_remunerees_pour_paie(
            dossier.company, date_debut, date_fin, employe_id=dossier.id):
        elements.append({
            'type': ElementVariable.TYPE_ABSENCE,
            'libelle': absence['type_absence_libelle'],
            'quantite': absence['jours'], 'montant': Decimal('0'),
            'remunere': False,
            'deduit_solde': absence['deduit_solde'],
        })

    # ── Primes validées du mois (FG193) ─────────────────────────────────
    for prime in rh_selectors.primes_validees_pour_paie(
            dossier.company, periode.annee, periode.mois,
            employe_id=dossier.id):
        elements.append({
            'type': ElementVariable.TYPE_PRIME,
            'libelle': prime['type_prime_libelle'],
            'quantite': Decimal('1'), 'montant': prime['montant'],
        })

    return elements


# ── ZPAI8 — Règle d'arrondi des jours d'absence, par rubrique ───────────────

def _arrondir_jours_absence(jours, rubrique):
    """Applique la règle d'arrondi ``Rubrique.arrondi``/``sens_arrondi`` (ZPAI8).

    ``rubrique`` peut être ``None`` (élément sans rubrique catalogue) → renvoie
    ``jours`` inchangé (comportement historique). ``arrondi='aucun'`` (défaut)
    → inchangé aussi. ``demi_journee``/``journee`` arrondissent au multiple de
    0,5 ou 1 jour le plus proche dans le sens choisi (``sup``/``inf``).
    """
    from .models import Rubrique

    jours = Decimal(jours or 0)
    if rubrique is None or not getattr(rubrique, 'arrondi', None):
        return jours
    if rubrique.arrondi == Rubrique.ARRONDI_AUCUN:
        return jours

    pas = Decimal('1') if rubrique.arrondi == Rubrique.ARRONDI_JOURNEE \
        else Decimal('0.5')
    unites = jours / pas
    if rubrique.sens_arrondi == Rubrique.SENS_INF:
        unites_arrondies = unites.to_integral_value(rounding='ROUND_FLOOR')
    else:
        unites_arrondies = unites.to_integral_value(rounding='ROUND_CEILING')
    return unites_arrondies * pas


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
            # PAIE26 — une absence RÉMUNÉRÉE (congé payé) ne réduit pas le
            # salaire proraté : le salarié est payé comme présent. Seules les
            # absences NON rémunérées sont décomptées des jours travaillés.
            if getattr(el, 'remunere', False):
                continue
            # Les absences sont en jours par convention dans ElementVariable.
            # ZPAI8 — arrondi selon la rubrique catalogue de l'élément (si
            # rattachée), sinon quantité brute (comportement historique).
            jours_absence += _arrondir_jours_absence(
                el.quantite, getattr(el, 'rubrique', None))
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


# ── XPAI14 — Indemnités journalières CNSS (maladie/maternité) ──────────────

LIBELLES_ARRET_CNSS = {
    'maladie': 'arrêt maladie',
    'maternite': 'arrêt maternité',
}


def arrets_cnss_periode(profil, periode, *, elements=None):
    """Éléments d'arrêt CNSS (maladie/maternité) d'un profil/période (XPAI14).

    Filtre les ``ElementVariable`` ``TYPE_ABSENCE`` dont
    ``categorie_absence`` est ``maladie``/``maternite``. Lecture seule.
    Renvoie une liste de dicts ``{'categorie', 'jours', 'remunere'}`` (un par
    élément — plusieurs arrêts possibles dans le mois).
    """
    from .models import ElementVariable

    if elements is None:
        elements = list(
            ElementVariable.objects.filter(periode=periode, profil=profil))
    return [
        {
            'categorie': el.categorie_absence,
            'jours': Decimal(el.quantite or 0),
            'remunere': bool(el.remunere),
        }
        for el in elements
        if el.type == ElementVariable.TYPE_ABSENCE
        and el.categorie_absence in LIBELLES_ARRET_CNSS
    ]


def attestation_salaire_ij_cnss(profil, periode):
    """Prépare le contexte de l'attestation de salaire IJ CNSS (XPAI14).

    Agrège les arrêts CNSS de la période (total jours, catégorie dominante)
    et le brut de RÉFÉRENCE (salaire de base du profil, non proraté — base
    du calcul IJ CNSS). Lecture seule. Renvoie ``{'jours_arret',
    'type_arret_libelle', 'brut_reference'}`` — ``jours_arret=0`` si aucun
    arrêt CNSS sur la période.
    """
    arrets = arrets_cnss_periode(profil, periode)
    total_jours = sum((a['jours'] for a in arrets), Decimal('0'))
    categorie = arrets[0]['categorie'] if arrets else 'maladie'
    return {
        'jours_arret': total_jours,
        'type_arret_libelle': LIBELLES_ARRET_CNSS.get(categorie, 'maladie'),
        'brut_reference': _q(Decimal(profil.salaire_base or 0)),
    }


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


# ── PAIE16 — Avantages en nature & indemnités : imposable vs non, plafonds ──

def repartir_avantage(rubrique, montant):
    """Répartit le ``montant`` d'une indemnité/avantage en part exonérée / part imposable.

    Cadre marocain : de nombreuses indemnités/avantages (transport, panier,
    déplacement, logement, voiture de fonction…) sont EXONÉRÉS d'IR tant que
    leur montant mensuel reste SOUS un plafond réglementaire ; la fraction qui
    EXCÈDE le plafond est réintégrée dans la base imposable.

    Règles (toutes pilotées par les drapeaux de la ``Rubrique``) :

    * ``rubrique`` absente (``None``) → tout est imposable (un élément variable
      sans rubrique catalogue est traité comme un gain imposable, comportement
      historique).
    * ``rubrique.imposable`` vrai ET pas de plafond → tout imposable.
    * ``rubrique`` non imposable ET pas de plafond (``plafond_exoneration`` à
      ``None``) → tout exonéré (comportement historique d'une indemnité
      entièrement exonérée).
    * ``plafond_exoneration`` renseigné → ``min(montant, plafond)`` est exonéré,
      l'excédent ``max(0, montant − plafond)`` est imposable. Ceci s'applique
      que la rubrique soit marquée imposable ou non : le plafond prime.

    Renvoie un tuple ``(part_exoneree, part_imposable)`` de ``Decimal`` au
    centime, dont la somme vaut toujours ``montant``.
    """
    montant = Decimal(montant or 0)
    if montant <= 0:
        return Decimal('0.00'), _q(montant)

    if rubrique is None:
        return Decimal('0.00'), _q(montant)

    plafond = getattr(rubrique, 'plafond_exoneration', None)
    if plafond is None:
        # Pas de plafond : tout imposable ou tout exonéré selon le drapeau.
        if rubrique.imposable:
            return Decimal('0.00'), _q(montant)
        return _q(montant), Decimal('0.00')

    plafond = Decimal(plafond)
    part_exoneree = min(montant, plafond)
    part_imposable = max(Decimal('0'), montant - plafond)
    return _q(part_exoneree), _q(part_imposable)


# ── PAIE18 / PAIE19 — Cotisations CNSS & AMO (salariale & patronale) ────────

def cnss_salariale(parametre, brut, affilie=True):
    """Cotisation CNSS PLAFONNÉE — part SALARIALE (PAIE18).

    Assiette = ``min(brut, plafond_cnss)`` ; cotisation =
    ``assiette × taux_cnss_salarial / 100``. Renvoie 0 si non affilié ou si
    ``parametre`` est ``None``. Decimal au centime.
    """
    if parametre is None or not affilie:
        return Decimal('0.00')
    assiette = min(Decimal(brut or 0), Decimal(parametre.plafond_cnss or 0))
    cot = assiette * Decimal(parametre.taux_cnss_salarial or 0) / Decimal('100')
    return _q(cot)


def cnss_patronale(parametre, brut, affilie=True):
    """Cotisation CNSS PLAFONNÉE — part PATRONALE (PAIE18).

    Charge employeur, même assiette plafonnée que la part salariale :
    ``min(brut, plafond_cnss) × taux_cnss_patronal / 100``. N'entre pas dans le
    net du salarié (c'est un coût employeur) ; figure au bulletin pour
    information et déclaration CNSS. Renvoie 0 si non affilié ou ``parametre``
    absent. Decimal au centime.
    """
    if parametre is None or not affilie:
        return Decimal('0.00')
    assiette = min(Decimal(brut or 0), Decimal(parametre.plafond_cnss or 0))
    cot = assiette * Decimal(parametre.taux_cnss_patronal or 0) / Decimal('100')
    return _q(cot)


def amo_salariale(parametre, brut, affilie=True):
    """Cotisation AMO NON PLAFONNÉE — part SALARIALE (PAIE19).

    Assiette = brut intégral (l'AMO n'a pas de plafond) ; cotisation =
    ``brut × taux_amo_salarial / 100``. Renvoie 0 si non affilié ou
    ``parametre`` absent. Decimal au centime.
    """
    if parametre is None or not affilie:
        return Decimal('0.00')
    cot = Decimal(brut or 0) * Decimal(parametre.taux_amo_salarial or 0) / Decimal('100')
    return _q(cot)


def amo_patronale(parametre, brut, affilie=True):
    """Cotisation AMO NON PLAFONNÉE — part PATRONALE (PAIE19).

    Charge employeur sur le brut intégral (sans plafond) :
    ``brut × taux_amo_patronal / 100``. N'entre pas dans le net du salarié ;
    figure au bulletin pour information et déclaration. Renvoie 0 si non
    affilié ou ``parametre`` absent. Decimal au centime.
    """
    if parametre is None or not affilie:
        return Decimal('0.00')
    cot = Decimal(brut or 0) * Decimal(parametre.taux_amo_patronal or 0) / Decimal('100')
    return _q(cot)


# ── PAIE23 — Allocations familiales (charge patronale, non plafonnée) ───────

def allocations_familiales_patronale(parametre, brut, affilie=True):
    """Allocations familiales (prestations familiales CNSS) — charge PATRONALE (PAIE23).

    Cotisation EMPLOYEUR NON PLAFONNÉE sur le brut intégral :
    ``brut × taux_allocations_familiales / 100`` (taux réglementaire ≈ 6,4 %,
    éditable par société). C'est une charge 100 % PATRONALE : elle figure au
    bulletin pour information et déclaration CNSS, mais N'ENTRE JAMAIS dans le
    net du salarié (aucune part salariale, aucune retenue).

    Le drapeau ``affilie`` reprend l'affiliation CNSS de l'employé
    (``ProfilPaie.affilie_cnss``) — les allocations familiales sont collectées
    avec la CNSS. Renvoie ``0`` si non affilié ou ``parametre`` absent. Decimal
    au centime.
    """
    if parametre is None or not affilie:
        return Decimal('0.00')
    taux = Decimal(parametre.taux_allocations_familiales or 0)
    cot = Decimal(brut or 0) * taux / Decimal('100')
    return _q(cot)


# ── PAIE24 — Taxe de formation professionnelle (charge patronale) ───────────

def formation_professionnelle_patronale(parametre, brut, affilie=True):
    """Taxe de formation professionnelle (TFP) — charge PATRONALE (PAIE24).

    Taxe EMPLOYEUR NON PLAFONNÉE sur le brut intégral :
    ``brut × taux_formation_pro / 100`` (taux réglementaire 1,6 %, éditable par
    société). C'est une charge 100 % PATRONALE, collectée avec la CNSS : elle
    figure au bulletin pour information et déclaration, mais N'ENTRE JAMAIS dans
    le net du salarié (aucune part salariale, aucune retenue).

    Le drapeau ``affilie`` reprend l'affiliation CNSS de l'employé
    (``ProfilPaie.affilie_cnss``) — la TFP est collectée avec la CNSS. Renvoie
    ``0`` si non affilié ou ``parametre`` absent. Decimal au centime.
    """
    if parametre is None or not affilie:
        return Decimal('0.00')
    taux = Decimal(parametre.taux_formation_pro or 0)
    cot = Decimal(brut or 0) * taux / Decimal('100')
    return _q(cot)


# ── PAIE25 — Provision pour congés payés (charge patronale, consomme RH) ─────

# Droit légal marocain : 1,5 jour ouvrable de congé payé acquis par mois de
# service (18 jours/an). La provision mensuelle valorise ces jours acquis au
# taux journalier du salarié. Éditable (constante de module — pas de migration).
JOURS_CP_ACQUIS_PAR_MOIS = Decimal('1.5')


def solde_conge_disponible(company, employe_id, annee):
    """Jours de congés payés DISPONIBLES d'un employé pour une année (PAIE25).

    Lecture du solde de congés RH (FG162) SANS importer ``rh.models`` : la paie
    lit le ``SoldeConge`` (report + acquis − pris) par une référence STRING-FK
    (``apps.get_model('rh', 'SoldeConge')``), toujours cadrée société. Renvoie
    ``Decimal('0')`` si la société/employé manque ou si aucun solde n'existe
    pour l'année.
    """
    from django.apps import apps as django_apps

    if company is None or employe_id is None or annee is None:
        return Decimal('0')
    SoldeConge = django_apps.get_model('rh', 'SoldeConge')
    solde = (
        SoldeConge.objects
        .filter(company=company, employe_id=employe_id, annee=annee)
        .first()
    )
    if solde is None:
        return Decimal('0')
    disponible = (
        (solde.report or Decimal('0'))
        + (solde.acquis or Decimal('0'))
        - (solde.pris or Decimal('0'))
    )
    return _q(disponible)


def taux_journalier_profil(profil):
    """Taux journalier de référence d'un profil (MAD/jour) — base de provision.

    * **journalier** : ``salaire_base`` est déjà le taux journalier.
    * **mensuel / forfait / horaire** : on dérive le taux journalier en divisant
      le salaire mensuel de référence par la norme de jours travaillés du profil.
      Pour un profil HORAIRE, ``salaire_base`` est un taux horaire → on le
      ramène d'abord à un mensuel via la norme d'heures.

    Renvoie un ``Decimal`` >= 0. Norme de jours nulle → 0.
    """
    from .models import ProfilPaie

    salaire = Decimal(profil.salaire_base or 0)
    jours_normes = Decimal(max(1, profil.jours_travail_mensuel or 26))

    if profil.type_remuneration == ProfilPaie.TYPE_JOURNALIER:
        return _q(salaire)
    if profil.type_remuneration == ProfilPaie.TYPE_HORAIRE:
        heures_normes = Decimal(max(1, profil.heures_travail_mensuel or 191))
        mensuel = salaire * heures_normes
        return _q(mensuel / jours_normes)
    # Mensuel / forfait : salaire mensuel ÷ jours norme.
    return _q(salaire / jours_normes)


def provision_conges_payes(profil, periode, jours_acquis=None):
    """Provision mensuelle pour congés payés d'un profil (PAIE25).

    Engagement social PATRONAL : chaque mois, l'employeur provisionne le coût
    des jours de CP acquis (par défaut ``JOURS_CP_ACQUIS_PAR_MOIS`` = 1,5 j/mois,
    droit légal marocain) valorisés au taux journalier du salarié
    (``taux_journalier_profil``). C'est une charge employeur informative — elle
    n'est JAMAIS déduite du net du salarié.

    ``jours_acquis`` permet de surcharger le nombre de jours acquis dans le mois
    (p. ex. proraté pour un mois incomplet) ; sinon le droit standard s'applique.

    Renvoie un ``Decimal`` >= 0 arrondi au centime.
    """
    if jours_acquis is None:
        jours_acquis = JOURS_CP_ACQUIS_PAR_MOIS
    jours_acquis = Decimal(jours_acquis or 0)
    if jours_acquis <= 0:
        return Decimal('0.00')
    taux_jour = taux_journalier_profil(profil)
    if taux_jour <= 0:
        return Decimal('0.00')
    return _q(jours_acquis * taux_jour)


# ── PAIE28 — Avance / prêt salarié : échéance mensuelle déduite du bulletin ──

# ── YHIRE5 — Réconciliation rh.AvanceSalaire (guichet) ↔ paie.AvanceSalarie
# (moteur de retenue). ``rh.AvanceSalaire`` reste le GUICHET de demande
# (portail, approbation superviseur/RH) ; ``paie.AvanceSalarie`` reste le
# SEUL moteur câblé au bulletin (``echeances_avances_periode``/
# ``appliquer_remboursements_avances``). Une avance approuvée côté RH est
# désormais MATÉRIALISÉE ici, une seule fois, pour être réellement retenue.

def creer_avance_depuis_rh(rh_avance):
    """Matérialise une ``paie.AvanceSalarie`` depuis une ``rh.AvanceSalaire``
    APPROUVÉE (YHIRE5). Appelée fonction-localement par ``apps.rh.services``
    à l'approbation (écriture cross-app par la couche ``services``, conforme
    CLAUDE.md — la paie ne lit jamais ``rh.models`` en retour, elle reçoit
    l'instance ``rh_avance`` en argument).

    Idempotent : si ``rh_avance.paie_avance_id`` est déjà posé, renvoie
    l'``AvanceSalarie`` existante SANS EN RECRÉER UNE 2ᵉ. Sinon crée une
    avance PONCTUELLE (``nombre_echeances=1``, échéance = montant total,
    retenue au mois ``annee_deduction``/``mois_deduction`` de la demande RH)
    liée au ``ProfilPaie`` de l'employé.

    Lève ``ValueError`` si l'employé n'a aucun ``ProfilPaie`` (rien à retenir
    sans profil de paie). Renvoie l'``AvanceSalarie`` créée ou existante.
    """
    from .models import AvanceSalarie, ProfilPaie

    if rh_avance.paie_avance_id:
        return AvanceSalarie.objects.filter(
            pk=rh_avance.paie_avance_id).first()

    profil = ProfilPaie.objects.filter(
        company_id=rh_avance.company_id,
        employe_id=rh_avance.employe_id).first()
    if profil is None:
        raise ValueError(
            "Aucun profil de paie pour cet employé : impossible de "
            "matérialiser l'avance.")

    annee = rh_avance.annee_deduction or timezone.localdate().year
    mois = rh_avance.mois_deduction or timezone.localdate().month
    montant = Decimal(rh_avance.montant or 0)
    avance = AvanceSalarie.objects.create(
        company=profil.company,
        profil=profil,
        type=AvanceSalarie.TYPE_AVANCE,
        libelle=(rh_avance.motif or 'Avance sur salaire (RH)')[:120],
        montant_total=montant,
        montant_echeance=montant,
        nombre_echeances=1,
        date_debut=date(annee, mois, 1),
    )
    rh_avance.paie_avance_id = avance.id
    rh_avance.save(update_fields=['paie_avance_id'])
    return avance


def echeance_avance(avance, le_jour):
    """Échéance retenue sur le bulletin pour une avance, au mois ``le_jour``.

    Renvoie le montant à retenir pour le mois donné :

    * ``0`` si l'avance est inactive, soldée, ou si sa retenue n'a pas encore
      commencé (``date_debut`` postérieure au mois) ;
    * sinon ``min(montant_echeance, solde_restant)`` — la dernière échéance ne
      retient jamais plus que ce qui reste dû.

    Pur (aucun effet de bord). Decimal au centime.
    """
    if avance is None or not avance.actif:
        return Decimal('0.00')
    if avance.solde_restant <= 0:
        return Decimal('0.00')
    if avance.date_debut is not None and avance.date_debut > le_jour:
        return Decimal('0.00')
    echeance = Decimal(avance.montant_echeance or 0)
    if echeance <= 0:
        return Decimal('0.00')
    return _q(min(echeance, avance.solde_restant))


def echeances_avances_periode(profil, periode):
    """Total des échéances d'avances/prêts à retenir pour ``profil`` sur ``periode``.

    Somme des ``echeance_avance`` de toutes les avances ACTIVES non soldées du
    profil au 1ᵉʳ du mois de la période. Pur (lecture seule). Renvoie un
    ``Decimal`` >= 0 au centime, et la liste des lignes
    ``[(avance, montant), …]`` pour traçabilité.
    """
    from .models import AvanceSalarie

    le_jour = date(periode.annee, periode.mois, 1)
    total = Decimal('0')
    lignes = []
    avances = AvanceSalarie.objects.filter(
        company=profil.company, profil=profil, actif=True)
    for avance in avances:
        montant = echeance_avance(avance, le_jour)
        if montant > 0:
            total += montant
            lignes.append((avance, montant))
    return _q(total), lignes


def appliquer_remboursements_avances(profil, periode):
    """Impute les échéances d'avances du mois (incrémente ``montant_rembourse``).

    Effet de bord : pour chaque avance active non soldée, ajoute l'échéance du
    mois à ``montant_rembourse`` (bornée au solde restant). À appeler UNE fois,
    au moment où le bulletin est validé (jamais au simple recalcul d'un
    brouillon, pour ne pas double-compter). Opération atomique. Renvoie le total
    imputé (``Decimal``).
    """
    from .models import AvanceSalarie

    le_jour = date(periode.annee, periode.mois, 1)
    total = Decimal('0')
    with transaction.atomic():
        avances = (
            AvanceSalarie.objects
            .select_for_update()
            .filter(company=profil.company, profil=profil, actif=True)
        )
        for avance in avances:
            montant = echeance_avance(avance, le_jour)
            if montant > 0:
                avance.montant_rembourse = _q(
                    Decimal(avance.montant_rembourse or 0) + montant)
                avance.save(update_fields=['montant_rembourse'])
                total += montant
    return _q(total)


# ── PAIE29 — Saisie-arrêt / cession : quotité saisissable ──────────────────

# Barème de la quotité saisissable (DECISION — défaut éditable, consentement
# fondateur). Cadre marocain (Code de procédure civile) : le salaire n'est
# saisissable que par tranches progressives. Liste ordonnée de tuples
# ``(borne_max, fraction)`` : pour la part du salaire NET comprise dans chaque
# tranche, seule ``fraction`` est saisissable. La dernière tranche a une
# ``borne_max`` à ``None`` (sans plafond). Valeurs ÉDITABLES — pur défaut.
BAREME_QUOTITE_SAISISSABLE = [
    (Decimal('2000'),  Decimal('0.05')),   # ≤ 2 000 : 1/20
    (Decimal('4000'),  Decimal('0.10')),   # 2 000–4 000 : 1/10
    (Decimal('6000'),  Decimal('0.20')),   # 4 000–6 000 : 1/5
    (Decimal('10000'), Decimal('0.25')),   # 6 000–10 000 : 1/4
    (None,             Decimal('0.333333')),  # > 10 000 : 1/3
]


def quotite_saisissable(net, bareme=None):
    """Part SAISISSABLE d'un salaire net selon le barème progressif (PAIE29).

    Applique ``bareme`` (défaut ``BAREME_QUOTITE_SAISISSABLE``) tranche par
    tranche : pour la fraction du ``net`` comprise dans chaque tranche, seule la
    ``fraction`` de cette tranche est saisissable ; on cumule. Le reste constitue
    la part insaisissable (toujours versée au salarié). ``net`` négatif ou nul →
    0. Renvoie un ``Decimal`` >= 0 au centime.
    """
    net = Decimal(net or 0)
    if net <= 0:
        return Decimal('0.00')
    if bareme is None:
        bareme = BAREME_QUOTITE_SAISISSABLE
    saisissable = Decimal('0')
    borne_basse = Decimal('0')
    for borne_max, fraction in bareme:
        if borne_max is None or net <= borne_max:
            saisissable += (net - borne_basse) * fraction
            break
        saisissable += (borne_max - borne_basse) * fraction
        borne_basse = borne_max
    return _q(saisissable)


def retenues_saisies_periode(profil, periode, net_a_payer):
    """Retenues de saisies/cessions du mois, plafonnées à la quotité (PAIE29).

    Pour ``profil`` sur ``periode``, parcourt les saisies ACTIVES non soldées
    (prioritaires d'abord), et alloue à chacune une retenue dans la limite :

    * de son ``montant_echeance`` souhaité (sinon tout le solde restant) ET de
      son solde restant ;
    * du PLAFOND GLOBAL = quotité saisissable du ``net_a_payer`` (la somme de
      toutes les saisies du mois ne dépasse jamais la quotité — la fraction
      insaisissable reste versée au salarié).

    Calcul PUR (aucun effet de bord) : l'imputation effective de
    ``montant_retenu`` se fait à la validation (``appliquer_saisies``). Renvoie
    ``(total, lignes)`` où ``lignes = [(saisie, montant), …]``.
    """
    from .models import SaisieArret

    le_jour = date(periode.annee, periode.mois, 1)
    plafond = quotite_saisissable(net_a_payer)
    restant_plafond = plafond
    total = Decimal('0')
    lignes = []
    saisies = SaisieArret.objects.filter(
        company=profil.company, profil=profil, actif=True
    ).order_by('-prioritaire', 'date_debut', 'id')
    for saisie in saisies:
        if restant_plafond <= 0:
            break
        if saisie.solde_restant <= 0:
            continue
        if saisie.date_debut is not None and saisie.date_debut > le_jour:
            continue
        souhaite = saisie.montant_echeance
        if souhaite is None or Decimal(souhaite) <= 0:
            souhaite = saisie.solde_restant
        montant = min(
            Decimal(souhaite), saisie.solde_restant, restant_plafond)
        montant = _q(montant)
        if montant > 0:
            total += montant
            restant_plafond -= montant
            lignes.append((saisie, montant))
    return _q(total), lignes


def appliquer_saisies(profil, periode, net_a_payer):
    """Impute les retenues de saisies du mois (incrémente ``montant_retenu``).

    Effet de bord : pour chaque saisie servie ce mois (cf.
    ``retenues_saisies_periode``), ajoute le montant retenu à ``montant_retenu``.
    À appeler UNE fois, à la validation du bulletin. Opération atomique. Renvoie
    le total imputé (``Decimal``).
    """
    from .models import SaisieArret

    _, lignes = retenues_saisies_periode(profil, periode, net_a_payer)
    total = Decimal('0')
    with transaction.atomic():
        for saisie, montant in lignes:
            verrou = (
                SaisieArret.objects
                .select_for_update()
                .get(pk=saisie.pk)
            )
            verrou.montant_retenu = _q(
                Decimal(verrou.montant_retenu or 0) + montant)
            champs = ['montant_retenu']
            # ZPAI6 — bascule auto `en_cours` -> `soldee` dès que le solde
            # restant est épuisé par cette imputation (jamais l'inverse : une
            # saisie soldée ne redevient jamais `en_cours` automatiquement).
            if verrou.soldee and verrou.statut == SaisieArret.STATUT_EN_COURS:
                verrou.statut = SaisieArret.STATUT_SOLDEE
                champs.append('statut')
            verrou.save(update_fields=champs)
            total += montant
    return _q(total)


# ── ZPAI6 — Cycle de vie explicite des saisies-arrêt ────────────────────────

def annuler_saisie_arret(saisie, *, motif=''):
    """Annule une saisie-arrêt/cession — stoppe les retenues futures (ZPAI6).

    N'efface JAMAIS l'historique : ``montant_retenu`` déjà imputé reste
    inchangé, seule la saisie passe ``actif=False`` + ``statut='annulee'``
    (elle sort donc de ``retenues_saisies_periode``/``appliquer_saisies``).
    Idempotent : annuler une saisie déjà annulée est un no-op. Refuse
    d'annuler une saisie déjà ``soldee`` (rien à arrêter, historique clos).
    Renvoie la saisie.
    """
    from .models import SaisieArret

    if saisie.statut == SaisieArret.STATUT_ANNULEE:
        return saisie
    if saisie.statut == SaisieArret.STATUT_SOLDEE:
        raise ValueError('Une saisie déjà soldée ne peut pas être annulée.')
    saisie.statut = SaisieArret.STATUT_ANNULEE
    saisie.actif = False
    saisie.date_annulation = timezone.now()
    saisie.motif_annulation = motif or ''
    saisie.save(update_fields=[
        'statut', 'actif', 'date_annulation', 'motif_annulation'])
    return saisie


def saisies_arret_du_bulletin(bulletin):
    """Saisies-arrêt/cessions servies par un ``BulletinPaie`` donné (ZPAI6).

    Relit les lignes ``SAISIE`` du bulletin (snapshot figé, ``LigneBulletin``)
    et les relie à leur ``SaisieArret`` d'origine par correspondance
    créancier/type (même clé que celle utilisée pour libeller la ligne dans
    ``calculer_bulletin``) — lecture seule, aucun effet de bord. Renvoie une
    liste de dicts ``{'saisie': SaisieArret, 'ligne': LigneBulletin,
    'montant': Decimal}``.
    """
    from .models import SaisieArret

    lignes_saisie = [
        ligne for ligne in bulletin.lignes.all() if ligne.code == 'SAISIE']
    if not lignes_saisie:
        return []
    saisies = list(
        SaisieArret.objects.filter(
            company=bulletin.company, profil=bulletin.profil)
    )
    by_label = {}
    for saisie in saisies:
        label = saisie.creancier or saisie.get_type_display()
        by_label.setdefault(label, []).append(saisie)

    resultats = []
    for ligne in lignes_saisie:
        candidats = by_label.get(ligne.libelle, [])
        saisie = candidats[0] if candidats else None
        resultats.append({
            'saisie': saisie,
            'ligne': ligne,
            'montant': ligne.montant,
        })
    return resultats


def creer_saisies_arret_lot(
        company, profils, *, type_saisie=None, montant_total,
        montant_echeance=None, date_debut, creancier='', reference='',
        prioritaire=False, cle_lot):
    """Éclate une saisie-arrêt en N fiches individuelles, une par profil (ZPAI7).

    Façon Odoo « Create Individual Attachments » : au lieu d'une saisie
    couvrant plusieurs employés, crée une ``SaisieArret`` DISTINCTE par
    profil, mêmes montant/type/quotité, en UNE transaction. Toutes les
    ``SaisieArret`` créées portent la même ``cle_lot`` (posée dans
    ``lot_reference``) — IDEMPOTENT : un re-run avec la MÊME ``cle_lot`` ne
    duplique rien, il renvoie les saisies déjà créées pour ce lot. Chaque
    ``profil`` doit être de la MÊME société que ``company`` (sinon
    ``ValueError``).

    ``cle_lot`` est un identifiant STABLE fourni par l'appelant (jamais généré
    ici par ``count()+1`` — cf. CLAUDE.md, la numérotation par comptage a déjà
    causé des collisions en production). Renvoie la liste des ``SaisieArret``
    du lot (nouvellement créées ou déjà existantes si re-run).
    """
    from .models import SaisieArret

    if not cle_lot:
        raise ValueError("cle_lot requis (idempotence du lot).")
    if type_saisie is None:
        type_saisie = SaisieArret.TYPE_SAISIE

    existantes = list(
        SaisieArret.objects.filter(company=company, lot_reference=cle_lot))
    if existantes:
        return existantes

    profils = list(profils)
    for profil in profils:
        if profil.company_id != company.id:
            raise ValueError("Un profil du lot appartient à une autre société.")

    with transaction.atomic():
        creees = [
            SaisieArret.objects.create(
                company=company, profil=profil, type=type_saisie,
                creancier=creancier, reference=reference,
                montant_total=montant_total,
                montant_echeance=montant_echeance,
                prioritaire=prioritaire, date_debut=date_debut,
                lot_reference=cle_lot,
            )
            for profil in profils
        ]
    return creees


# ── PAIE20 — Cotisation CIMR OPTIONNELLE (taux par employé adhérent) ─────────

def cimr_salariale(brut, affilie=False, taux=Decimal('0')):
    """Cotisation CIMR — part SALARIALE, OPTIONNELLE par employé (PAIE20).

    La CIMR (régime de retraite complémentaire) est FACULTATIVE : seuls les
    employés ADHÉRENTS cotisent, et chacun avec SON propre taux. Contrairement
    à la CNSS/AMO, le taux n'est pas une constante de société mais une valeur
    portée par le ``ProfilPaie`` de l'employé (``taux_cimr_salarial``) — deux
    adhérents peuvent avoir des taux différents.

    Assiette = brut intégral (non plafonnée) ; cotisation = ``brut × taux / 100``.
    Renvoie ``0`` quand l'employé n'est PAS adhérent (``affilie=False``, le
    défaut), ce qui matérialise « pas d'adhésion → pas de CIMR ». Renvoie aussi
    ``0`` si le taux est nul ou négatif. Decimal au centime.

    ``affilie`` est le drapeau d'adhésion de l'employé
    (``ProfilPaie.affilie_cimr``) ; ``taux`` son taux salarial propre
    (``ProfilPaie.taux_cimr_salarial``).
    """
    if not affilie:
        return Decimal('0.00')
    taux = Decimal(taux or 0)
    if taux <= 0:
        return Decimal('0.00')
    cot = Decimal(brut or 0) * taux / Decimal('100')
    return _q(cot)


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


# ── XPAI3 — Mutuelle / prévoyance / assurance groupe ────────────────────────

def mutuelle_du_profil(profil, brut):
    """Cotisations mutuelle (salariale + patronale) d'un profil (XPAI3).

    Lit l'adhésion mutuelle ACTIVE du profil (``AdhesionMutuelle``, OneToOne)
    et calcule les parts salariale/patronale selon le mode du régime :
    ``pourcentage`` (× ``brut``) ou ``fixe`` (montant tel quel). Renvoie
    ``(part_salariale, part_patronale, deductible)`` — deux ``Decimal`` au
    centime et un booléen. ``(0, 0, False)`` si le profil n'est pas adhérent
    (pas d'``AdhesionMutuelle`` active).
    """
    adhesion = getattr(profil, 'adhesion_mutuelle', None)
    if adhesion is None or not adhesion.actif:
        return Decimal('0.00'), Decimal('0.00'), False
    regime = adhesion.regime
    if regime is None or not regime.actif:
        return Decimal('0.00'), Decimal('0.00'), False
    if regime.mode == regime.MODE_POURCENTAGE:
        salariale = Decimal(brut or 0) * Decimal(regime.part_salariale or 0) / Decimal('100')
        patronale = Decimal(brut or 0) * Decimal(regime.part_patronale or 0) / Decimal('100')
    else:
        salariale = Decimal(regime.part_salariale or 0)
        patronale = Decimal(regime.part_patronale or 0)
    return _q(salariale), _q(patronale), bool(regime.deductible_net_imposable)


# ── XPAI18 — Régimes stagiaire / ANAPEC / TAHFIZ (exonération IR) ──────────

def regime_actif_a_la_date(profil, le_jour):
    """Vrai si le profil a un régime d'exonération ACTIF à ``le_jour`` (XPAI18).

    Un régime est actif quand ``regime_exoneration != aucun`` ET que
    ``le_jour`` tombe dans la fenêtre ``[regime_date_debut, regime_date_fin]``
    (bornes incluses ; une borne ``None`` est considérée ouverte de ce côté).
    """
    from .models import ProfilPaie

    if profil.regime_exoneration == ProfilPaie.REGIME_AUCUN:
        return False
    if profil.regime_date_debut and le_jour < profil.regime_date_debut:
        return False
    if profil.regime_date_fin and le_jour > profil.regime_date_fin:
        return False
    return True


def montant_exonere_regime_profil(profil, le_jour, net_imposable):
    """Fraction EXONÉRÉE d'IR du net imposable au titre du régime (XPAI18).

    ``min(net_imposable, regime_plafond_mensuel)`` si le régime est actif à
    ``le_jour`` (cf. ``regime_actif_a_la_date``), sinon 0. L'excédent au-delà
    du plafond reste imposable (géré par l'appelant, jamais ici).
    """
    if not regime_actif_a_la_date(profil, le_jour):
        return Decimal('0.00')
    plafond = Decimal(profil.regime_plafond_mensuel or 0)
    base = Decimal(net_imposable or 0)
    if base <= 0 or plafond <= 0:
        return Decimal('0.00')
    return _q(min(base, plafond))


def expirer_regimes_echus(company, *, today=None):
    """Bascule au régime NORMAL les profils dont la fenêtre est EXPIRÉE (XPAI18).

    Un profil avec ``regime_exoneration != aucun`` dont ``regime_date_fin`` est
    dépassée (strictement avant ``today``) repasse à ``REGIME_AUCUN`` — la
    réintégration au régime normal est IMMÉDIATE (le prochain bulletin calculé
    n'aura plus d'exonération) — et une notification best-effort est envoyée
    (rôle ``paie_gerer``, repli Responsable/Admin). Idempotent : un profil déjà
    ``aucun`` n'est jamais retraité. Renvoie la liste des profils basculés.
    """
    from .models import ProfilPaie

    if today is None:
        today = timezone.localdate()

    profils = ProfilPaie.objects.filter(
        company=company,
        regime_date_fin__lt=today,
    ).exclude(regime_exoneration=ProfilPaie.REGIME_AUCUN)

    bascules = []
    for profil in profils:
        ancien_regime = profil.get_regime_exoneration_display()
        profil.regime_exoneration = ProfilPaie.REGIME_AUCUN
        profil.save(update_fields=['regime_exoneration'])
        try:
            from apps.notifications import services as notif_services

            recipients = notif_services.resolve_recipients(
                company, 'paie_regime_expire')
            nom = ''
            if profil.employe_id:
                emp = profil.employe
                nom = f'{emp.nom} {emp.prenom}'.strip()
            notif_services.notify_many(
                recipients, 'paie_regime_expire',
                title=f'Régime {ancien_regime} expiré',
                body=(f'{nom or "Profil #" + str(profil.id)} — le régime '
                      f'{ancien_regime} a expiré et a été réintégré au '
                      'régime normal.'),
                company=company)
        except Exception:  # pragma: no cover - défensif, best-effort
            pass
        bascules.append(profil)
    return bascules


# ── XPAI25 — Notes de frais (indemnités chantier) remboursées sur le bulletin

def remboursements_frais_periode(profil, periode):
    """Notes de frais (indemnités chantier) remboursables du profil (XPAI25).

    Lecture PURE (aucun effet de bord — jamais appelée hors calcul/aperçu) :
    résout l'utilisateur applicatif lié (``profil.employe.user``) puis lit,
    via ``compta.selectors.indemnites_chantier_remboursables_par_paie``
    (fonction fine, cross-app lecture seule), les ``IndemniteChantier``
    VALIDÉES non remboursées de la période. Sans utilisateur lié, renvoie
    ``(Decimal('0'), [])``. Renvoie ``(total, [(indemnite, montant), ...])``.
    """
    employe = profil.employe if profil.employe_id else None
    user = getattr(employe, 'user', None) if employe else None
    if user is None:
        return Decimal('0.00'), []

    from apps.compta import selectors as compta_selectors  # cross-app READ

    date_debut, date_fin = _bornes_periode(periode)
    indemnites = compta_selectors.indemnites_chantier_remboursables_par_paie(
        profil.company, user.id, date_debut, date_fin)

    total = Decimal('0')
    lignes = []
    for indem in indemnites:
        montant = Decimal(indem.montant_total or 0)
        if montant <= 0:
            continue
        total += montant
        lignes.append((indem, _q(montant)))
    return _q(total), lignes


def appliquer_remboursement_frais(profil, periode):
    """Marque REMBOURSÉES (côté compta) les notes de frais du bulletin (XPAI25).

    Appelé UNE SEULE FOIS, à la validation du bulletin (jamais au recalcul
    d'un brouillon — même patron que les avances/saisies) : pour chaque
    ``IndemniteChantier`` retenue par ``remboursements_frais_periode``, appelle
    ``compta.services.marquer_indemnite_remboursee_par_paie`` (idempotent —
    une indemnité déjà remboursée, y compris par trésorerie entre-temps,
    n'est jamais recomptée : DOUBLE COMPTAGE IMPOSSIBLE). Renvoie la liste des
    indemnités marquées.
    """
    from apps.compta import services as compta_services  # cross-app WRITE

    _, lignes = remboursements_frais_periode(profil, periode)
    marquees = []
    for indem, _montant in lignes:
        indem_a_jour = compta_services.marquer_indemnite_remboursee_par_paie(
            indem)
        marquees.append(indem_a_jour)
    return marquees


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
    4. **CIMR** salariale (PAIE20, OPTIONNELLE) = ``taux_cimr_salarial`` du
       profil × brut, UNIQUEMENT si le profil est adhérent (``affilie_cimr``) ;
       sinon 0 (le taux est propre à chaque employé adhérent).
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
        .select_related('rubrique', 'type_entree')
    )

    # PAIE13 — salaire de base proraté selon le type de rémunération.
    salaire_base = calculer_salaire_base_periode(profil, periode, elements)
    gains_variables = Decimal('0')
    retenues_variables = Decimal('0')
    gains_imposables = Decimal('0')
    # ZPAI9 — cumul des entrées ponctuelles TYPÉES hors bases CNSS/IR
    # (ex. remboursement de frais non imposable) : ajouté DIRECTEMENT au net,
    # jamais à ``brut``/``brut_imposable``. Positif = gain, négatif = retenue.
    hors_bases = Decimal('0')
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
        rubrique = el.rubrique if el.rubrique_id else None
        # PAIE26 — une absence RÉMUNÉRÉE (congé payé) ne génère aucune retenue :
        # elle est déjà neutralisée dans la proration du salaire de base. On la
        # saute ici pour ne pas la décompter une seconde fois.
        if (el.type == ElementVariable.TYPE_ABSENCE
                and getattr(el, 'remunere', False)):
            continue
        if el.type == ElementVariable.TYPE_RETENUE or \
                el.type == ElementVariable.TYPE_ABSENCE:
            retenues_variables += montant
            lignes.append({
                'code': el.rubrique.code if el.rubrique_id else el.type,
                'libelle': el.libelle or el.get_type_display(),
                'type': Rubrique.TYPE_RETENUE, 'montant': _q(montant),
            })
        elif (el.type_entree_id and not el.type_entree.imposable
                and not el.type_entree.soumis_cnss):
            # ZPAI9 — Entrée ponctuelle TYPÉE, hors bases CNSS/IR (ex. « frais
            # non imposable ») : ne rejoint NI ``gains_variables`` (base
            # CNSS/AMO) NI ``gains_imposables`` (base IR) — versée directement
            # au net (comme le remboursement de frais XPAI25), qu'elle soit un
            # gain ou une retenue (``sens`` du type catalogue).
            if el.type_entree.sens == TypeEntreePonctuelle.SENS_RETENUE:
                hors_bases -= montant
            else:
                hors_bases += montant
            lignes.append({
                'code': el.type_entree.code,
                'libelle': el.libelle or el.type_entree.libelle,
                'type': Rubrique.TYPE_GAIN
                if el.type_entree.sens != TypeEntreePonctuelle.SENS_RETENUE
                else Rubrique.TYPE_RETENUE,
                'montant': _q(montant),
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
            # PAIE16 — Avantages en nature & indemnités : la part qui dépasse le
            # plafond d'exonération de la rubrique (ou la totalité d'une rubrique
            # imposable sans plafond) entre dans la base imposable ; la part sous
            # le plafond reste exonérée. Sans rubrique catalogue, l'élément est
            # imposable (comportement historique).
            _, part_imposable = repartir_avantage(rubrique, montant)
            if part_imposable > 0:
                gains_imposables += part_imposable
            lignes.append({
                'code': el.rubrique.code if el.rubrique_id else el.type,
                'libelle': el.libelle or el.get_type_display(),
                'type': Rubrique.TYPE_GAIN, 'montant': _q(montant),
            })

    brut = salaire_base + gains_variables
    # Le salaire de base est imposable et soumis aux cotisations.
    brut_imposable = salaire_base + gains_imposables

    # 2. CNSS plafonnée — PAIE18 (part salariale ET patronale).
    cnss = cnss_salariale(parametre, brut, profil.affilie_cnss)
    cnss_pat = cnss_patronale(parametre, brut, profil.affilie_cnss)

    # 3. AMO non plafonnée — PAIE19 (part salariale ET patronale).
    amo = amo_salariale(parametre, brut, profil.affilie_amo)
    amo_pat = amo_patronale(parametre, brut, profil.affilie_amo)

    # 3bis. Allocations familiales — PAIE23 (charge 100 % PATRONALE, non
    # plafonnée). Collectée avec la CNSS → suit l'affiliation CNSS du profil.
    # N'entre JAMAIS dans le net du salarié (aucune part salariale).
    alloc_fam = allocations_familiales_patronale(
        parametre, brut, profil.affilie_cnss)

    # 3ter. Taxe de formation professionnelle — PAIE24 (charge 100 % PATRONALE,
    # non plafonnée, 1,6 %). Collectée avec la CNSS → suit l'affiliation CNSS du
    # profil. N'entre JAMAIS dans le net du salarié (aucune part salariale).
    formation_pro = formation_professionnelle_patronale(
        parametre, brut, profil.affilie_cnss)

    # 3quater. Provision pour congés payés — PAIE25 (charge 100 % PATRONALE,
    # informative). Engagement social mensuel = jours CP acquis dans le mois ×
    # taux journalier du salarié. N'entre JAMAIS dans le net du salarié.
    provision_conges = provision_conges_payes(profil, periode)

    # 4. CIMR (PAIE20) — OPTIONNELLE : seuls les profils adhérents cotisent,
    # chacun avec SON taux propre. Non adhérent → 0 (défaut).
    cimr = cimr_salariale(brut, profil.affilie_cimr, profil.taux_cimr_salarial)

    # 4bis. Mutuelle / prévoyance / assurance groupe (XPAI3) — OPTIONNELLE :
    # seuls les profils avec une adhésion active cotisent. La part salariale
    # se déduit du net imposable AVANT IR quand le régime est déductible ; la
    # part patronale rejoint les charges patronales (jamais le net du
    # salarié).
    mutuelle_sal, mutuelle_pat, mutuelle_deductible = mutuelle_du_profil(
        profil, brut)

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

    # 6. Net imposable (XPAI3 : − part salariale mutuelle si déductible).
    net_imposable = brut_imposable - cnss - amo - cimr - frais_pro
    if mutuelle_deductible:
        net_imposable -= mutuelle_sal
    if net_imposable < 0:
        net_imposable = Decimal('0')
    net_imposable = _q(net_imposable)

    # 7. IR — XPAI18 : exonération régime stagiaire/ANAPEC/TAHFIZ. La fraction
    # du net imposable SOUS le plafond mensuel du régime (dans sa fenêtre
    # d'éligibilité) est retirée de la base IR avant application du barème ;
    # l'excédent reste imposable normalement. Régime normal → 0 (inchangé).
    montant_exonere_regime = montant_exonere_regime_profil(
        profil, le_jour, net_imposable)
    base_ir = net_imposable - montant_exonere_regime
    if base_ir < 0:
        base_ir = Decimal('0')
    ir = Decimal('0')
    if bareme and parametre:
        ir = compute_ir(base_ir, bareme, parametre, personnes_a_charge)
    ir = _q(ir)

    # PAIE28 — Échéances d'avances/prêts salariés du mois : retenues nettes
    # (après IR, comme toute retenue de net). Calcul PUR ici — l'imputation
    # effective de ``montant_rembourse`` se fait à la validation du bulletin
    # (``valider_bulletin`` → ``appliquer_remboursements_avances``).
    _, lignes_avances = echeances_avances_periode(profil, periode)
    for avance, montant in lignes_avances:
        retenues_variables += montant
        lignes.append({
            'code': 'AVANCE',
            'libelle': avance.libelle or avance.get_type_display(),
            'type': Rubrique.TYPE_RETENUE,
            'montant': _q(montant),
        })

    # XPAI3 — Ligne mutuelle salariale (retenue nette, comme la CIMR).
    if mutuelle_sal > 0:
        retenues_variables += mutuelle_sal
        lignes.append({
            'code': 'MUTUELLE_SAL',
            'libelle': 'Mutuelle (part salariale)',
            'type': Rubrique.TYPE_RETENUE,
            'montant': mutuelle_sal,
        })

    # 8. Net à payer (− retenues variables type avances, mutuelle incluse).
    # ZPAI9 — entrées ponctuelles hors bases CNSS/IR (+ gain / − retenue).
    net_a_payer = brut - cnss - amo - cimr - ir - retenues_variables \
        + hors_bases
    net_a_payer = _q(net_a_payer)
    # Net AVANT saisie : base de calcul de la quotité saisissable (conservé pour
    # rejouer la même allocation à la validation).
    net_avant_saisie = net_a_payer

    # PAIE29 — Saisie-arrêt / cession : retenue PLAFONNÉE à la quotité
    # saisissable du net à payer (la fraction insaisissable reste versée au
    # salarié). Calculée sur le net AVANT saisie, puis défalquée. Calcul PUR —
    # l'imputation effective (``montant_retenu``) se fait à la validation.
    saisies_total, lignes_saisies = retenues_saisies_periode(
        profil, periode, net_avant_saisie)
    if saisies_total > 0:
        retenues_variables += saisies_total
        for saisie, montant in lignes_saisies:
            lignes.append({
                'code': 'SAISIE',
                'libelle': saisie.creancier or saisie.get_type_display(),
                'type': Rubrique.TYPE_RETENUE,
                'montant': _q(montant),
            })
        net_a_payer = _q(net_a_payer - saisies_total)

    # XPAI25 — Remboursement de notes de frais (IndemniteChantier validées
    # non payées de la période) : ligne HORS bases CNSS/IR, ajoutée au net à
    # payer (jamais imposable/cotisable). Calcul PUR ici — l'imputation
    # effective (marquage « remboursée par paie » côté compta) se fait à la
    # validation (``appliquer_remboursement_frais``), jamais au brouillon.
    remboursements_frais, lignes_remboursements = remboursements_frais_periode(
        profil, periode)
    if remboursements_frais > 0:
        net_a_payer = _q(net_a_payer + remboursements_frais)
        for indem, montant in lignes_remboursements:
            lignes.append({
                'code': 'REMB_FRAIS',
                'libelle': f'Remboursement frais — {indem.libelle_chantier}'.strip(' —'),
                'type': Rubrique.TYPE_GAIN,
                'montant': _q(montant),
            })

    # PAIE18/PAIE19/PAIE23/PAIE24/XPAI3 — Total des charges patronales (coût
    # employeur), informatif : CNSS + AMO + allocations familiales + taxe de
    # formation professionnelle + mutuelle patronales.
    charges_patronales = _q(
        cnss_pat + amo_pat + alloc_fam + formation_pro + mutuelle_pat)

    # XPAI3 — Ligne EMPLOYEUR informative pour la mutuelle. Type cotisation,
    # marquée part patronale ; ne diminue jamais le net du salarié.
    if mutuelle_pat > 0:
        lignes.append({
            'code': 'MUTUELLE_PAT',
            'libelle': 'Mutuelle (part patronale)',
            'type': Rubrique.TYPE_COTISATION,
            'montant': mutuelle_pat,
        })

    # PAIE23 — Ligne EMPLOYEUR informative pour les allocations familiales.
    # Type cotisation, marquée part patronale ; comme toute charge patronale
    # elle ne diminue PAS le net (cf. calcul du net à payer plus haut).
    if alloc_fam > 0:
        lignes.append({
            'code': 'ALLOC_FAM',
            'libelle': 'Allocations familiales (part patronale)',
            'type': Rubrique.TYPE_COTISATION,
            'montant': alloc_fam,
        })

    # PAIE24 — Ligne EMPLOYEUR informative pour la taxe de formation
    # professionnelle (1,6 % patronal). Comme toute charge patronale elle ne
    # diminue PAS le net (cf. calcul du net à payer plus haut).
    if formation_pro > 0:
        lignes.append({
            'code': 'FORMATION_PRO',
            'libelle': 'Taxe de formation professionnelle (part patronale)',
            'type': Rubrique.TYPE_COTISATION,
            'montant': formation_pro,
        })

    return {
        'brut': _q(brut),
        'brut_imposable': _q(brut_imposable),
        'cnss_salariale': cnss,
        'cnss_patronale': cnss_pat,
        'amo_salariale': amo,
        'amo_patronale': amo_pat,
        'allocations_familiales': alloc_fam,
        'formation_professionnelle': formation_pro,
        'provision_conges': provision_conges,
        'cimr_salariale': cimr,
        'frais_professionnels': frais_pro,
        'net_imposable': net_imposable,
        'ir': ir,
        'montant_exonere_regime': _q(montant_exonere_regime),
        'retenues': _q(retenues_variables),
        'net_a_payer': net_a_payer,
        'prime_anciennete': prime_anciennete,
        'charges_patronales': charges_patronales,
        'mutuelle_salariale': mutuelle_sal,
        'mutuelle_patronale': mutuelle_pat,
        'lignes': lignes,
        # Interne (PAIE29) : net avant saisie, base de la quotité saisissable.
        # Non persisté en bulletin — sert à rejouer l'imputation à la validation.
        'net_avant_saisie': net_avant_saisie,
    }


# ── XPAI16 — Simulateur de bulletin + calcul net→brut ──────────────────────

def _simuler_montant_net(brut, *, parametre, bareme, personnes_a_charge=0,
                         affilie_cnss=True, affilie_amo=True,
                         affilie_cimr=False, taux_cimr=Decimal('0')):
    """Calcul PUR brut → net (XPAI16) : le cœur du simulateur, sans DB.

    Réplique les étapes CNSS/AMO/CIMR/frais pro/IR de ``calculer_bulletin``
    sur un ``brut`` DONNÉ (pas de proration, pas d'éléments variables — un
    what-if simple). Renvoie un dict ``{'brut', 'cnss_salariale',
    'amo_salariale', 'cimr_salariale', 'frais_professionnels',
    'net_imposable', 'ir', 'net_a_payer'}``.
    """
    brut = _q(Decimal(brut or 0))
    cnss = cnss_salariale(parametre, brut, affilie_cnss) if parametre \
        else Decimal('0.00')
    amo = amo_salariale(parametre, brut, affilie_amo) if parametre \
        else Decimal('0.00')
    cimr = cimr_salariale(brut, affilie_cimr, taux_cimr)

    frais_pro = Decimal('0')
    if parametre:
        if brut <= Decimal(parametre.seuil_frais_pro or 0):
            frais_pro = brut * Decimal(parametre.taux_frais_pro_bas) / Decimal('100')
            plafond = Decimal(parametre.plafond_frais_pro_bas or 0)
        else:
            frais_pro = brut * Decimal(parametre.taux_frais_pro_haut) / Decimal('100')
            plafond = Decimal(parametre.plafond_frais_pro_haut or 0)
        if plafond and frais_pro > plafond:
            frais_pro = plafond
    frais_pro = _q(frais_pro)

    net_imposable = brut - cnss - amo - cimr - frais_pro
    if net_imposable < 0:
        net_imposable = Decimal('0')
    net_imposable = _q(net_imposable)

    ir = Decimal('0')
    if bareme and parametre:
        ir = compute_ir(net_imposable, bareme, parametre, personnes_a_charge)
    ir = _q(ir)

    net_a_payer = _q(brut - cnss - amo - cimr - ir)
    return {
        'brut': brut, 'cnss_salariale': cnss, 'amo_salariale': amo,
        'cimr_salariale': cimr, 'frais_professionnels': frais_pro,
        'net_imposable': net_imposable, 'ir': ir, 'net_a_payer': net_a_payer,
    }


def simuler_bulletin(profil, periode, *, salaire=None, prime=Decimal('0'),
                     personnes_a_charge=0):
    """Simule un bulletin SANS PERSISTANCE (what-if, XPAI16).

    Rejoue le calcul en mémoire pour un ``salaire`` hypothétique (défaut :
    ``profil.salaire_base`` réel) + une ``prime`` ponctuelle (imposable et
    soumise CNSS/AMO comme un gain standard) et des ``personnes_a_charge``
    modifiées — sans jamais créer de ``BulletinPaie`` ni lire/écrire
    d'``ElementVariable``. Le taux/affiliation CIMR et les affiliations
    CNSS/AMO restent ceux RÉELS du profil (le what-if porte sur le montant,
    pas le régime social). Lecture des paramètres légaux réels (barème/
    constantes en vigueur à la date de la période). Renvoie le dict de
    ``_simuler_montant_net`` complété de ``{'salaire_simule', 'prime'}``.
    """
    le_jour = date(periode.annee, periode.mois, 1)
    parametre = parametre_en_vigueur(profil.company, le_jour)
    bareme = bareme_en_vigueur(profil.company, le_jour)

    salaire_simule = Decimal(salaire) if salaire is not None \
        else Decimal(profil.salaire_base or 0)
    brut = _q(salaire_simule + Decimal(prime or 0))

    resultat = _simuler_montant_net(
        brut, parametre=parametre, bareme=bareme,
        personnes_a_charge=personnes_a_charge,
        affilie_cnss=profil.affilie_cnss, affilie_amo=profil.affilie_amo,
        affilie_cimr=profil.affilie_cimr,
        taux_cimr=profil.taux_cimr_salarial)
    resultat['salaire_simule'] = _q(salaire_simule)
    resultat['prime'] = _q(Decimal(prime or 0))
    return resultat


def brut_pour_net_cible(net_cible, *, parametre, bareme,
                        personnes_a_charge=0, affilie_cnss=True,
                        affilie_amo=True, affilie_cimr=False,
                        taux_cimr=Decimal('0'), tolerance=Decimal('0.01'),
                        max_iterations=100):
    """Calcul INVERSE « brut pour net cible » (XPAI16, lettres d'offre).

    Recherche ITÉRATIVE (bissection) sur ``_simuler_montant_net`` : converge
    au CENTIME près vers le ``brut`` dont le net à payer égale ``net_cible``.
    Le net étant une fonction CROISSANTE et continue par morceaux du brut
    (cotisations/IR croissants), la bissection converge de façon fiable.
    Renvoie ``{'brut', 'net_obtenu', 'iterations', ...}`` (mêmes clés que
    ``_simuler_montant_net`` + ``iterations``). Lève ``ValueError`` si
    ``net_cible <= 0``.
    """
    net_cible = Decimal(net_cible or 0)
    if net_cible <= 0:
        raise ValueError('net_cible doit être strictement positif.')

    # Borne haute généreuse : un brut ne dépasse jamais ~3x le net cible en
    # pratique (cotisations + IR marocain plafonnent la ponction). Si le
    # premier essai à cette borne ne suffit toujours pas (ecart < 0), on la
    # DOUBLE avant même d'entrer en bissection — garde de robustesse pour un
    # net cible extrême, sans jamais casser la monotonie lo < hi ensuite.
    borne_basse = Decimal('0')
    borne_haute = net_cible * Decimal('3')
    for _ in range(10):
        essai = _simuler_montant_net(
            borne_haute, parametre=parametre, bareme=bareme,
            personnes_a_charge=personnes_a_charge,
            affilie_cnss=affilie_cnss, affilie_amo=affilie_amo,
            affilie_cimr=affilie_cimr, taux_cimr=taux_cimr)
        if essai['net_a_payer'] >= net_cible:
            break
        borne_haute *= 2

    resultat = None
    for iteration in range(1, max_iterations + 1):
        milieu = _q((borne_basse + borne_haute) / 2)
        resultat = _simuler_montant_net(
            milieu, parametre=parametre, bareme=bareme,
            personnes_a_charge=personnes_a_charge,
            affilie_cnss=affilie_cnss, affilie_amo=affilie_amo,
            affilie_cimr=affilie_cimr, taux_cimr=taux_cimr)
        ecart = resultat['net_a_payer'] - net_cible
        if abs(ecart) <= tolerance:
            resultat['iterations'] = iteration
            resultat['net_obtenu'] = resultat['net_a_payer']
            return resultat
        if ecart < 0:
            borne_basse = milieu
        else:
            borne_haute = milieu

    resultat['iterations'] = max_iterations
    resultat['net_obtenu'] = resultat['net_a_payer']
    return resultat


# ── PAIE17 — Bulletin de paie matérialisé (snapshot immuable une fois validé) ─

def generer_bulletin(profil, periode, personnes_a_charge=0):
    """Matérialise (ou régénère) le bulletin de paie d'un profil (PAIE17).

    Calcule le bulletin via ``calculer_bulletin`` puis PERSISTE le snapshot dans
    ``BulletinPaie`` + ses ``LigneBulletin``. Crée le bulletin s'il n'existe pas ;
    s'il existe déjà :

    * en statut ``brouillon`` → il est RECALCULÉ (montants & lignes remplacés) ;
    * en statut ``valide`` → il est FIGÉ : ``BulletinVerrouille`` est levé (on ne
      régénère jamais un bulletin validé).

    ``company`` posée côté serveur (héritée de la période/profil). Opération
    atomique. Renvoie le ``BulletinPaie`` (re)matérialisé.
    """
    from .models import BulletinPaie, LigneBulletin

    if profil.company_id != periode.company_id:
        raise ValueError("Profil et période de sociétés différentes.")

    # PAIE36 — Verrouillage de clôture : une période CLÔTURÉE est figée, aucun
    # bulletin n'y est (re)généré. Les corrections passent par un bulletin
    # RECTIFICATIF/RAPPEL sur une période ouverte (``creer_bulletin_rectificatif``).
    if periode.statut == PeriodePaie.STATUT_CLOTUREE:
        raise BulletinPaie.BulletinVerrouille(
            'Période clôturée : génération de bulletin interdite.')

    resultat = calculer_bulletin(profil, periode, personnes_a_charge)
    lignes = resultat.get('lignes', [])

    with transaction.atomic():
        bulletin = (
            BulletinPaie.objects
            .select_for_update()
            .filter(periode=periode, profil=profil)
            .first()
        )
        if bulletin is not None and bulletin.est_valide:
            raise BulletinPaie.BulletinVerrouille(
                'Bulletin validé : régénération interdite (figé).')
        if bulletin is None:
            bulletin = BulletinPaie(
                company=periode.company, periode=periode, profil=profil)

        bulletin.personnes_a_charge = max(0, int(personnes_a_charge or 0))
        for champ in BulletinPaie.SNAPSHOT_FIELDS:
            if champ == 'personnes_a_charge':
                continue
            setattr(bulletin, champ, resultat[champ])
        bulletin.statut = BulletinPaie.STATUT_BROUILLON
        bulletin.save()

        # Remplace les lignes (brouillon uniquement — garde modèle assurée).
        bulletin.lignes.all().delete()
        for ordre, ligne in enumerate(lignes, start=1):
            LigneBulletin.objects.create(
                company=periode.company,
                bulletin=bulletin,
                code=ligne.get('code', ''),
                libelle=ligne.get('libelle', ''),
                type=ligne.get('type', 'gain'),
                montant=ligne.get('montant', Decimal('0')),
                ordre=ordre,
            )
        return bulletin


# ── PAIE36 — Clôture mensuelle + bulletins rectificatifs / rappels ─────────

def cloturer_periode_paie(periode, *, valider_brouillons=True):
    """Clôture mensuelle d'une période de paie (PAIE36).

    Verrouille DÉFINITIVEMENT une ``PeriodePaie`` :

    1. (option) VALIDE tous les bulletins encore en brouillon de la période
       (``valider_brouillons=True`` par défaut) — ils deviennent figés ;
    2. fait avancer la période au statut ``cloturee`` (via ``changer_statut``,
       cycle progressif) et pose ``date_cloture``.

    Une fois clôturée, aucun nouveau bulletin n'est généré pour la période
    (garde dans ``generer_bulletin``). Idempotent : re-clôturer une période déjà
    clôturée ne valide rien et ne fait qu'un no-op de transition. Opération
    atomique. Renvoie la période.
    """
    from .models import BulletinPaie

    with transaction.atomic():
        if valider_brouillons:
            brouillons = BulletinPaie.objects.filter(
                company=periode.company, periode=periode,
                statut=BulletinPaie.STATUT_BROUILLON)
            for bulletin in brouillons:
                valider_bulletin(bulletin)
        changer_statut(periode, PeriodePaie.STATUT_CLOTUREE)
        # XPAI6 — la clôture avance les échéances déclaratives encore « à
        # générer » (les états/déclarations sont désormais calculables).
        avancer_echeances_cloture(periode)
        # XPAI20 — la clôture MENSUELLE poste les provisions 13e mois / IFC
        # (jamais sur un run hors-cycle : le run 13e mois lui-même EXTOURNE
        # ces provisions, il ne doit pas en reconstituer).
        if periode.type_run == PeriodePaie.TYPE_RUN_MENSUEL:
            poster_provisions_mensuelles(periode)
    return periode


def creer_bulletin_rectificatif(bulletin_origine, periode_cible, *,
                                type_bulletin=None, motif='',
                                personnes_a_charge=None):
    """Crée un bulletin RECTIFICATIF ou RAPPEL liant un bulletin d'origine (PAIE36).

    Un bulletin validé/clôturé est FIGÉ : on ne le modifie jamais. Pour corriger
    une erreur (rectificatif) ou verser un rattrapage (rappel), on émet un
    NOUVEAU bulletin sur une ``periode_cible`` OUVERTE (≠ période d'origine, qui
    peut être clôturée), rattaché au bulletin d'origine via ``rectifie`` et
    portant un ``motif``. Le nouveau bulletin est recalculé normalement
    (``generer_bulletin``) puis marqué de sa nature.

    ``type_bulletin`` ∈ {rectificatif, rappel} (défaut : rectificatif).
    ``periode_cible`` doit être de la même société que l'origine et ne PAS être
    clôturée. Renvoie le bulletin rectificatif (en brouillon).
    """
    from .models import BulletinPaie

    if type_bulletin is None:
        type_bulletin = BulletinPaie.TYPE_RECTIFICATIF
    if type_bulletin not in (BulletinPaie.TYPE_RECTIFICATIF,
                             BulletinPaie.TYPE_RAPPEL):
        raise ValueError(
            "type_bulletin doit être 'rectificatif' ou 'rappel'.")
    if periode_cible.company_id != bulletin_origine.company_id:
        raise ValueError("Période cible d'une autre société.")
    if periode_cible.pk == bulletin_origine.periode_id:
        raise ValueError(
            "Le rectificatif doit cibler une période différente de l'origine.")
    if periode_cible.statut == PeriodePaie.STATUT_CLOTUREE:
        raise ValueError("La période cible est clôturée.")

    profil = bulletin_origine.profil
    if personnes_a_charge is None:
        personnes_a_charge = bulletin_origine.personnes_a_charge

    with transaction.atomic():
        bulletin = generer_bulletin(
            profil, periode_cible, personnes_a_charge=personnes_a_charge)
        bulletin.type_bulletin = type_bulletin
        bulletin.rectifie = bulletin_origine
        bulletin.motif = motif or ''
        bulletin.save(update_fields=['type_bulletin', 'rectifie', 'motif'])
    return bulletin


def creer_bulletin_annulation(bulletin_origine, periode_cible):
    """Crée un bulletin d'ANNULATION (refund payslip) lié à l'origine (ZPAI4).

    Contrairement au RECTIFICATIF (qui remplace en émettant un nouveau calcul),
    l'annulation recopie EXACTEMENT les lignes/montants du bulletin d'origine
    avec le signe OPPOSÉ — un simple extourne, sans rejouer le moteur de
    calcul. Le bulletin d'origine reste figé et intact ; l'annulation est créée
    en ``brouillon`` (immuable une fois validée, comme tout bulletin) et se
    répercute dans ``CumulAnnuel``/le 9421 via la validation normale (les
    montants négatifs s'additionnent aux positifs de l'origine).

    ``periode_cible`` doit être de la même société que l'origine et ne PAS
    être clôturée. Renvoie le bulletin d'annulation (en brouillon).
    """
    from .models import BulletinPaie, LigneBulletin

    if periode_cible.company_id != bulletin_origine.company_id:
        raise ValueError("Période cible d'une autre société.")
    if periode_cible.statut == PeriodePaie.STATUT_CLOTUREE:
        raise ValueError("La période cible est clôturée.")

    with transaction.atomic():
        annulation = BulletinPaie.objects.create(
            company=bulletin_origine.company,
            periode=periode_cible,
            profil=bulletin_origine.profil,
            type_bulletin=BulletinPaie.TYPE_ANNULATION,
            rectifie=bulletin_origine,
            motif=f"Annulation du bulletin #{bulletin_origine.id}",
            personnes_a_charge=bulletin_origine.personnes_a_charge,
        )
        for champ in BulletinPaie.SNAPSHOT_FIELDS:
            valeur = getattr(bulletin_origine, champ) or Decimal('0')
            setattr(annulation, champ, _q(-Decimal(valeur)))
        annulation.save()
        for ligne in bulletin_origine.lignes.all():
            LigneBulletin.objects.create(
                company=ligne.company,
                bulletin=annulation,
                code=ligne.code,
                libelle=f'{ligne.libelle} (annulation)',
                type=ligne.type,
                montant=_q(-Decimal(ligne.montant or 0)),
                ordre=ligne.ordre,
            )
    return annulation


# ── ZPAI10 — Assistant « Ajouter des bulletins existants à une période » ──

def rattacher_bulletins(periode_cible, bulletin_ids):
    """Rattache des bulletins NON affectés à une ``periode_cible`` (ZPAI10).

    Façon Odoo « Add Payslips » : pose la FK ``periode`` de chaque bulletin
    listé sur ``periode_cible`` (regroupement rétroactif — utile p. ex. pour
    consolider un run hors-cycle XPAI4 dans le livre de paie du mois). Garde
    même société stricte et refuse si la période cible est CLÔTURÉE. Un
    bulletin qui laisserait un doublon ``(periode_cible, profil)`` (contrainte
    ``unique_together``) est refusé explicitement (jamais d'IntegrityError
    500). Opération atomique — soit tout rattache, soit rien. Renvoie la
    liste des bulletins rattachés (rafraîchis).
    """
    from .models import BulletinPaie

    if periode_cible.statut == PeriodePaie.STATUT_CLOTUREE:
        raise ValueError("La période cible est clôturée.")
    if not bulletin_ids:
        raise ValueError("Aucun bulletin fourni.")

    with transaction.atomic():
        bulletins = list(
            BulletinPaie.objects
            .select_for_update()
            .filter(id__in=bulletin_ids)
        )
        if len(bulletins) != len(set(bulletin_ids)):
            raise ValueError("Un ou plusieurs bulletins sont introuvables.")
        for bulletin in bulletins:
            if bulletin.company_id != periode_cible.company_id:
                raise ValueError(
                    "Un bulletin appartient à une autre société.")
        profils_deja_dans_cible = set(
            BulletinPaie.objects
            .filter(periode=periode_cible)
            .exclude(id__in=[b.id for b in bulletins])
            .values_list('profil_id', flat=True)
        )
        profils_du_lot = set()
        for bulletin in bulletins:
            if bulletin.profil_id in profils_deja_dans_cible:
                raise ValueError(
                    f"Le profil #{bulletin.profil_id} a déjà un bulletin "
                    "sur la période cible.")
            if bulletin.profil_id in profils_du_lot:
                raise ValueError(
                    f"Le profil #{bulletin.profil_id} apparaît plusieurs "
                    "fois dans le lot.")
            profils_du_lot.add(bulletin.profil_id)
        for bulletin in bulletins:
            if bulletin.statut == BulletinPaie.STATUT_VALIDE:
                # Un bulletin VALIDÉ est figé (BulletinVerrouille) — le
                # rattachement de période n'est permis que sur un brouillon.
                raise ValueError(
                    f"Le bulletin #{bulletin.id} est validé (figé) : "
                    "impossible de le rattacher à une autre période.")
            bulletin.periode = periode_cible
            bulletin.save(update_fields=['periode'])
    return bulletins


def valider_bulletin(bulletin):
    """Valide un ``BulletinPaie`` → fige le snapshot (PAIE17).

    Passe le statut ``brouillon → valide`` (irréversible) et pose
    ``date_validation``. Une fois validé, le bulletin et ses lignes sont
    immuables (gardes ``save``/``delete`` côté modèle). Re-valider un bulletin
    déjà validé est un no-op. Renvoie le bulletin.
    """
    from .models import BulletinPaie

    if bulletin.statut == BulletinPaie.STATUT_VALIDE:
        return bulletin
    bulletin.statut = BulletinPaie.STATUT_VALIDE
    bulletin.date_validation = timezone.now()
    bulletin.save(update_fields=['statut', 'date_validation'])
    # Recalcule l'état du bulletin AVANT toute imputation, pour rejouer
    # EXACTEMENT la même allocation que le snapshot (la base de la quotité
    # saisissable, PAIE29, est figée ici avant que les avances ne bougent).
    resultat = calculer_bulletin(bulletin.profil, bulletin.periode,
                                 bulletin.personnes_a_charge)
    # PAIE28 — Impute les échéances d'avances/prêts du mois (incrémente
    # ``montant_rembourse``) UNE seule fois, à la validation (jamais au recalcul
    # d'un brouillon). Le bulletin étant figé après validation, ce remboursement
    # n'est pas rejoué.
    appliquer_remboursements_avances(bulletin.profil, bulletin.periode)
    # PAIE29 — Impute les saisies-arrêts/cessions du mois (incrémente
    # ``montant_retenu``) une seule fois, à la validation, sur la base du net
    # AVANT saisie figé ci-dessus.
    appliquer_saisies(bulletin.profil, bulletin.periode,
                      resultat['net_avant_saisie'])
    # XPAI25 — Marque REMBOURSÉES (côté compta) les notes de frais incluses
    # dans ce bulletin, une seule fois, à la validation (best-effort — ne
    # bloque jamais la validation du bulletin de paie).
    try:
        appliquer_remboursement_frais(bulletin.profil, bulletin.periode)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass
    # XPAI20 — Un bulletin de run 13e mois/gratification VALIDÉ (le versement
    # est désormais figé) EXTOURNE les provisions mensuelles accumulées pour
    # ce profil (best-effort — ne bloque jamais la validation du bulletin).
    if bulletin.type_bulletin == BulletinPaie.TYPE_GRATIFICATION:
        try:
            extourner_provisions_gratification(bulletin.profil)
        except Exception:  # pragma: no cover - défensif, best-effort
            pass
    # XPAI21 — Notifie l'employé lié (rh.DossierEmploye.user) que son
    # bulletin validé est disponible dans son coffre-fort (PAIE35).
    # Best-effort : jamais bloquant pour la validation.
    try:
        notifier_bulletin_disponible(bulletin)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass
    return bulletin


# ── XPAI21 — Distribution des bulletins : notification + accusé de lecture ─

def notifier_bulletin_disponible(bulletin):
    """Notifie l'employé lié qu'un bulletin VALIDÉ est disponible (XPAI21).

    Résout l'utilisateur applicatif rattaché (``profil.employe.user``,
    ``OneToOne`` RH) — sans utilisateur lié, ne fait rien (no-op silencieux,
    tous les employés n'ont pas de compte). Best-effort, jamais bloquant.
    """
    from apps.notifications import services as notif_services

    employe = bulletin.profil.employe if bulletin.profil.employe_id else None
    user = getattr(employe, 'user', None) if employe else None
    if user is None:
        return
    notif_services.notify(
        user, 'paie_bulletin_disponible',
        title='Votre bulletin de paie est disponible',
        body=(f'Bulletin {bulletin.periode.mois:02d}/{bulletin.periode.annee} '
              'disponible dans votre coffre-fort.'),
        company=bulletin.company)


def marquer_bulletin_lu(bulletin):
    """Pose l'accusé de lecture ``lu_le`` à la PREMIÈRE consultation (XPAI21).

    Idempotent : un ``lu_le`` déjà posé n'est JAMAIS réécrit (trace fidèle de
    la première ouverture — remise dématérialisée). Renvoie le bulletin.
    """
    if bulletin.lu_le is not None:
        return bulletin
    bulletin.lu_le = timezone.now()
    bulletin.save(update_fields=['lu_le'])
    return bulletin


# ── XPAI6 — Échéancier déclaratif paie ──────────────────────────────────────

def _mois_suivant(annee, mois):
    """``(annee, mois)`` du mois suivant."""
    if mois == 12:
        return annee + 1, 1
    return annee, mois + 1


def echeances_attendues(periode):
    """Types d'échéances + dates limites attendues pour une ``periode`` (XPAI6).

    * BDS — avant le 10 du mois suivant (déclaration CNSS mensuelle) ;
    * IR mensuel — versement de la retenue à la source, avant le 20 du mois
      suivant (Code général des impôts marocain) ;
    * CIMR — avant le 10 du mois suivant (versement de la cotisation) ;
    * État 9421 — annuel, fin février de l'année SUIVANTE, généré une seule
      fois par le RUN DE DÉCEMBRE (mois == 12) pour éviter 12 doublons.

    Lecture pure (aucun effet de bord). Renvoie une liste de
    ``(type_echeance, date_limite)``.
    """
    from .models import EcheanceDeclarative

    annee_suivante, mois_suivant = _mois_suivant(periode.annee, periode.mois)
    echeances = [
        (EcheanceDeclarative.TYPE_BDS, date(annee_suivante, mois_suivant, 10)),
        (EcheanceDeclarative.TYPE_IR_MENSUEL,
         date(annee_suivante, mois_suivant, 20)),
        (EcheanceDeclarative.TYPE_CIMR, date(annee_suivante, mois_suivant, 10)),
    ]
    if periode.mois == 12:
        echeances.append(
            (EcheanceDeclarative.TYPE_9421, date(periode.annee + 1, 2, 28)))
    return echeances


def generer_echeances_periode(periode):
    """Génère (idempotent) les échéances déclaratives d'une période (XPAI6).

    Crée une ``EcheanceDeclarative`` par type attendu
    (``echeances_attendues``) si elle n'existe pas déjà (clé stable
    ``(periode, type_echeance)``) — ne touche jamais une échéance déjà créée
    (son ``statut`` progressé n'est jamais écrasé). Appelé automatiquement à
    la création d'une ``PeriodePaie`` (vue) ; peut aussi être rejoué sans
    effet sur les échéances existantes. Renvoie la liste des échéances
    créées (nouvelles uniquement).
    """
    from .models import EcheanceDeclarative

    creees = []
    for type_echeance, date_limite in echeances_attendues(periode):
        _obj, created = EcheanceDeclarative.objects.get_or_create(
            company=periode.company, periode=periode,
            type_echeance=type_echeance,
            defaults={'date_limite': date_limite})
        if created:
            creees.append(_obj)
    return creees


def avancer_echeances_cloture(periode):
    """Avance les échéances à ``generee`` à la clôture d'une période (XPAI6).

    Une échéance encore ``a_generer`` passe à ``generee`` quand la période
    est clôturée (les états/déclarations sont désormais calculables depuis
    les bulletins figés). Une échéance déjà ``generee``/``deposee``/``payee``
    n'est jamais rétrogradée. Best-effort, jamais bloquant pour la clôture.
    """
    from .models import EcheanceDeclarative

    (EcheanceDeclarative.objects
     .filter(company=periode.company, periode=periode,
             statut=EcheanceDeclarative.STATUT_A_GENERER)
     .update(statut=EcheanceDeclarative.STATUT_GENEREE))


def notifier_echeances_en_retard(company):
    """Notifie (best-effort) les échéances déclaratives EN RETARD (XPAI6).

    Une échéance dont la ``date_limite`` est dépassée et qui n'est pas encore
    ``deposee``/``payee`` déclenche une notification vers le rôle
    ``paie_gerer`` (repli : Responsable/Admin, via
    ``apps.notifications.resolve_recipients``) — UNE SEULE FOIS
    (``date_notification`` posée après envoi ; un re-run ne renotifie pas la
    même échéance). Jamais bloquant : toute erreur de notification est
    avalée. Renvoie la liste des échéances notifiées.
    """
    from django.utils import timezone as dj_timezone

    from .models import EcheanceDeclarative

    today = dj_timezone.localdate()
    en_retard = (
        EcheanceDeclarative.objects
        .filter(company=company, date_limite__lt=today,
                date_notification__isnull=True)
        .exclude(statut__in=[
            EcheanceDeclarative.STATUT_DEPOSEE, EcheanceDeclarative.STATUT_PAYEE])
        .select_related('periode')
    )
    notifiees = []
    for echeance in en_retard:
        try:
            from apps.notifications import services as notif_services

            recipients = notif_services.resolve_recipients(
                company, 'paie_echeance_retard')
            notif_services.notify_many(
                recipients, 'paie_echeance_retard',
                title=f'Échéance paie en retard : {echeance.get_type_echeance_display()}',
                body=(
                    f'Période {echeance.periode.mois:02d}/{echeance.periode.annee} — '
                    f'date limite {echeance.date_limite}, non déposée.'),
                company=company)
        except Exception:  # pragma: no cover - défensif, best-effort
            pass
        echeance.date_notification = dj_timezone.now()
        echeance.save(update_fields=['date_notification'])
        notifiees.append(echeance)
    return notifiees


# ── ZPAI12 — Alerte de clôture de paie en retard (tâche planifiée) ─────────

def periodes_cloture_en_retard(company):
    """``PeriodePaie`` en ``brouillon``/``calculee`` dont le mois est écoulé (ZPAI12).

    Une période M est « en retard » quand le mois SUIVANT (M+1) est déjà
    ENTAMÉ (aujourd'hui ≥ le 1ᵉʳ de M+1) ET qu'elle n'est ni ``validee`` ni
    ``cloturee``. Lecture pure (aucun effet de bord). Renvoie une liste de
    ``PeriodePaie`` (comparaison faite en Python — ``(annee, mois)`` n'est
    pas un DateField comparable directement en SQL ici).
    """
    from django.utils import timezone as dj_timezone

    from .models import PeriodePaie

    today = dj_timezone.localdate()
    candidates = PeriodePaie.objects.filter(
        company=company,
        statut__in=[PeriodePaie.STATUT_BROUILLON, PeriodePaie.STATUT_CALCULEE],
    )
    en_retard = []
    for periode in candidates:
        annee_suivante, mois_suivant = _mois_suivant(periode.annee, periode.mois)
        if date(annee_suivante, mois_suivant, 1) <= today:
            en_retard.append(periode)
    return en_retard


def notifier_cloture_en_retard(company):
    """Notifie (best-effort) le gestionnaire paie des clôtures en retard (ZPAI12).

    Pour chaque ``PeriodePaie`` de ``periodes_cloture_en_retard`` non encore
    alertée (``date_alerte_cloture_retard`` NULL), notifie le rôle
    ``paie_gerer`` (repli Responsable/Admin via
    ``apps.notifications.resolve_recipients``) — UNE SEULE FOIS
    (``date_alerte_cloture_retard`` posée après envoi ; un re-run le
    lendemain ne renotifie pas). Jamais bloquant : toute erreur de
    notification est avalée. Renvoie la liste des périodes notifiées.
    """
    from django.utils import timezone as dj_timezone

    en_retard = [
        p for p in periodes_cloture_en_retard(company)
        if p.date_alerte_cloture_retard is None
    ]
    notifiees = []
    for periode in en_retard:
        try:
            from apps.notifications import services as notif_services

            recipients = notif_services.resolve_recipients(
                company, 'paie_cloture_retard')
            notif_services.notify_many(
                recipients, 'paie_cloture_retard',
                title='Clôture de paie en retard',
                body=(
                    f'Période {periode.mois:02d}/{periode.annee} '
                    f'({periode.get_statut_display()}) non clôturée.'),
                company=company)
        except Exception:  # pragma: no cover - défensif, best-effort
            pass
        periode.date_alerte_cloture_retard = dj_timezone.now()
        periode.save(update_fields=['date_alerte_cloture_retard'])
        notifiees.append(periode)
    return notifiees


# ── PAIE30 — Ordre de virement + fichier de virement banque ────────────────

FICHIER_VIREMENT_PAIE_HEADERS = [
    'Bénéficiaire', 'RIB', 'Montant', 'Devise', 'Référence', 'Motif',
]


def controler_coherence_rib(periode):
    """Contrôle croisé RIB paie ↔ RH d'un run de virement (ARC25, lecture seule).

    Lit les divergences via ``apps.paie.selectors.divergences_rib_periode``
    (``ProfilPaie.rib`` vs ``rh.DossierEmploye.rib`` — CONTRÔLE, jamais fusion)
    et, s'il y en a, émet UNE notification interne vers les responsables paie
    (``apps.notifications.resolve_recipients`` → repli Responsable/Admin) pour
    qu'un humain tranche AVANT de figer le virement. AUCUNE divergence → SILENCE
    (aucune notification).

    ARC39 — l'événement ``'paie_rib_divergence'`` est désormais un
    ``EventType`` ENREGISTRÉ (``PAIE_RIB_DIVERGENCE``) : la ligne in-app est
    donc réellement persistée (avant, ``notify()`` journalisait un
    avertissement et renvoyait ``None`` silencieusement).

    Best-effort et STRICTEMENT non bloquant : toute erreur (lecture ou
    notification) est avalée — un échec de contrôle ne doit JAMAIS empêcher la
    génération de l'ordre de virement. Renvoie la liste des divergences
    détectées (vide si tout concorde ou en cas d'erreur).
    """
    from . import selectors as paie_selectors

    company = getattr(periode, 'company', None)
    if company is None:
        return []
    try:
        divergences = paie_selectors.divergences_rib_periode(periode)
    except Exception:  # pragma: no cover - défensif, best-effort
        return []
    if not divergences:
        return []

    try:
        from apps.notifications import services as notif_services

        recipients = notif_services.resolve_recipients(
            company, 'paie_rib_divergence')
        nb = len(divergences)
        titre = (
            'Divergence RIB paie ↔ RH avant virement '
            f'({periode.mois:02d}/{periode.annee})')
        corps = (
            f'{nb} salarié(s) payé(s) par virement ont un RIB de paie '
            'différent du RIB de leur fiche RH. À vérifier avant d\'émettre '
            'l\'ordre de virement (aucune modification automatique).')
        notif_services.notify_many(
            recipients, 'paie_rib_divergence',
            title=titre, body=corps, company=company)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass
    return divergences


def generer_ordre_virement(periode, *, date_execution=None, rib_emetteur='',
                           compte_emetteur=None):
    """Génère (ou régénère) l'ordre de virement d'une période (PAIE30).

    Regroupe tous les bulletins VALIDÉS de la ``periode`` au ``net_a_payer > 0``
    en un ``OrdreVirement`` (une ``LigneVirement`` par salarié : bénéficiaire,
    RIB du profil, net à payer). Recrée l'ordre s'il est en brouillon ; refuse de
    régénérer un ordre déjà ÉMIS (figé). ``company`` posée côté serveur. Opération
    atomique. Renvoie l'``OrdreVirement``.

    DC20 — single-source du compte émetteur : ``compte_emetteur`` accepte soit
    une instance ``compta.CompteTresorerie``, soit son id ; quand il est fourni
    (et appartient à la même société), ``rib_emetteur`` et ``devise`` sont
    DÉRIVÉS de ce référentiel — le RIB bancaire de l'entreprise est saisi UNE
    fois dans la trésorerie, jamais re-tapé ici. Le paramètre ``rib_emetteur``
    texte reste un repli quand aucun compte n'est câblé.
    """
    from .models import (
        BulletinPaie, LigneVirement, OrdreVirement, ProfilPaie,
    )

    compte = _resoudre_compte_emetteur(periode.company, compte_emetteur)

    with transaction.atomic():
        ordre = (
            OrdreVirement.objects
            .select_for_update()
            .filter(company=periode.company, periode=periode)
            .first()
        )
        if ordre is not None and ordre.est_emis:
            raise ValueError("Ordre de virement déjà émis : régénération interdite.")
        if ordre is None:
            # DC39 — référence unique race-safe (OV-YYYYMM-NNNN), jamais
            # count()+1. Générée UNE seule fois, à la première création.
            from apps.ventes.utils.references import create_with_reference

            ordre = create_with_reference(
                OrdreVirement, 'OV', periode.company,
                lambda reference: OrdreVirement.objects.create(
                    company=periode.company, periode=periode,
                    reference=reference),
            )
        ordre.statut = OrdreVirement.STATUT_BROUILLON
        if date_execution is not None:
            ordre.date_execution = date_execution
        if compte is not None:
            # Source unique : le compte de trésorerie pilote RIB + devise.
            ordre.compte_emetteur = compte
            if compte.rib:
                ordre.rib_emetteur = compte.rib
            if compte.devise:
                ordre.devise = compte.devise
        elif rib_emetteur:
            ordre.rib_emetteur = rib_emetteur
        if not ordre.libelle:
            ordre.libelle = f'Virement salaires {periode.mois:02d}/{periode.annee}'
        ordre.save()

        ordre.lignes.all().delete()
        bulletins = (
            BulletinPaie.objects
            .filter(company=periode.company, periode=periode,
                    statut=BulletinPaie.STATUT_VALIDE)
            .select_related('profil', 'profil__employe')
        )
        total = Decimal('0')
        nombre = 0
        for bulletin in bulletins:
            net = Decimal(bulletin.net_a_payer or 0)
            if net <= 0:
                continue
            profil = bulletin.profil
            # XPAI9 — Seuls les profils PAYÉS PAR VIREMENT entrent dans
            # l'ordre. Espèces/chèque sont réglés hors virement (listés à
            # part par ``profils_hors_virement``).
            if profil.mode_paiement != ProfilPaie.MODE_PAIEMENT_VIREMENT:
                continue
            employe = profil.employe
            beneficiaire = f'{employe.nom} {employe.prenom}'.strip() \
                if employe else f'Profil #{profil.id}'
            reference = f'SAL-{periode.annee}-{periode.mois:02d}-{profil.id}'
            LigneVirement.objects.create(
                company=periode.company,
                ordre=ordre,
                bulletin=bulletin,
                beneficiaire=beneficiaire or f'Profil #{profil.id}',
                rib=profil.rib or '',
                montant=_q(net),
                reference=reference,
            )
            total += net
            nombre += 1
        # XPAI8 — un ordre sans aucune ligne reste CRÉABLE (brouillon vide) :
        # ce sont les générateurs de fichier (``fichier_virement_paie`` /
        # ``fichier_virement_paie_simt``) qui refusent de produire un fichier
        # sans ligne, jamais la génération de l'ordre lui-même. YLEDG7 — le
        # risque « payer un ordre sans montant » est gardé côté règlement :
        # ``payer_ordre_virement`` refuse tout ordre au ``total`` nul (ci-
        # dessous), donc un ordre vide ne peut jamais être réglé par erreur.
        ordre.total = _q(total)
        ordre.nombre_lignes = nombre
        ordre.save(update_fields=['total', 'nombre_lignes', 'libelle',
                                  'date_execution', 'rib_emetteur',
                                  'compte_emetteur', 'devise'])

    # ARC25 — contrôle croisé RIB paie ↔ RH APRÈS la transaction : divergence →
    # notification interne, concordance → silence. Strictement best-effort :
    # jamais dans l'atomic (une I/O de notification ne doit pas participer à la
    # transaction) et jamais bloquant pour la génération de l'ordre.
    try:
        controler_coherence_rib(periode)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass
    return ordre


def _resoudre_compte_emetteur(company, compte_emetteur):
    """Résout un ``compta.CompteTresorerie`` émetteur, borné à ``company`` (DC20).

    Accepte ``None`` (pas de compte), une instance déjà chargée, ou un id. La
    lecture passe par la couche ``selectors`` de compta (cross-app READ autorisé)
    — la paie n'importe jamais ``compta.models``. Renvoie le compte ou ``None``
    (id inconnu / autre société = ignoré silencieusement, le repli texte
    s'applique).
    """
    if compte_emetteur is None:
        return None
    # Instance déjà résolue : on vérifie seulement l'appartenance société.
    if hasattr(compte_emetteur, 'pk') and not isinstance(compte_emetteur, int):
        return compte_emetteur if getattr(
            compte_emetteur, 'company_id', None) == company.id else None
    # Résolution par id via le référentiel compta (string-FK, jamais d'import de
    # ``compta.models``). Le modèle est obtenu par le registre d'apps et borné à
    # la société — un id inconnu / d'une autre société renvoie ``None``.
    from django.apps import apps as django_apps
    CompteTresorerie = django_apps.get_model('compta', 'CompteTresorerie')
    return CompteTresorerie.objects.filter(
        company=company, pk=compte_emetteur).first()


def emettre_ordre_virement(ordre):
    """Émet l'ordre de virement → fige l'ordre (PAIE30).

    Passe le statut ``brouillon → emis`` (irréversible) et pose
    ``date_emission``. Re-émettre est un no-op. Renvoie l'ordre.
    """
    from .models import OrdreVirement

    if ordre.statut == OrdreVirement.STATUT_EMIS:
        return ordre
    ordre.statut = OrdreVirement.STATUT_EMIS
    ordre.date_emission = timezone.now()
    ordre.save(update_fields=['statut', 'date_emission'])
    return ordre


def fichier_virement_paie(ordre):
    """Construit le fichier de virement bancaire d'un ordre de paie (PAIE30).

    Une ligne par bénéficiaire : nom, RIB, montant au centime, devise, référence
    et motif. Renvoie ``{'headers', 'rows', 'total', 'nb_lignes'}`` — la vue
    sérialise en texte/CSV. Lecture seule. Lève ``ValueError`` si l'ordre n'a
    aucune ligne, ou si une ligne n'a pas de RIB (un virement sans coordonnées
    bancaires ne peut être exécuté).
    """
    lignes = list(ordre.lignes.all())
    if not lignes:
        raise ValueError("L'ordre de virement ne comporte aucune ligne.")
    devise = ordre.devise or 'MAD'
    rows = []
    total = Decimal('0')
    for ligne in lignes:
        if not ligne.rib:
            raise ValueError(
                f"RIB manquant pour « {ligne.beneficiaire} » : "
                "un virement exige un RIB.")
        montant = _q(ligne.montant)
        total += montant
        rows.append([
            ligne.beneficiaire,
            ligne.rib,
            str(montant),
            devise,
            ligne.reference or '',
            f'Salaire {ligne.reference}'.strip(),
        ])
    # DC20 — coordonnées de l'émetteur lues du référentiel trésorerie quand il
    # est câblé (RIB/IBAN/banque saisis une fois), repli sur le RIB texte.
    compte = ordre.compte_emetteur
    emetteur = {
        'rib': (compte.rib if compte and compte.rib else ordre.rib_emetteur)
        or '',
        'banque': (compte.banque if compte else '') or '',
        'iban': (compte.iban if compte else '') or '',
        'libelle': (compte.libelle if compte else '') or '',
    }
    return {
        'headers': list(FICHIER_VIREMENT_PAIE_HEADERS),
        'rows': rows,
        'total': _q(total),
        'nb_lignes': len(rows),
        'emetteur': emetteur,
    }


# ── XPAI8 — Fichier de virement bancaire marocain (SIMT / masse) ───────────

# DÉCISION — gabarit SIMT STANDARD (longueurs fixes, virement de masse). Le
# layout EXACT dépend de la banque du fondateur et reste À CONFIRMER auprès
# d'elle avant tout dépôt réel ; ce gabarit livre le MÉCANISME (longueurs
# fixes, ordre des champs, remplissage/troncature) + une structure standard
# couramment utilisée (émetteur/bénéficiaire/montant en centimes/référence).
# ``(nom_champ, longueur, remplissage)`` — remplissage 'L' (gauche, espaces,
# texte) ou 'R' (droite, zéros, numérique).
GABARIT_SIMT_ENTETE = [
    ('type_enregistrement', 1, 'L'),   # 'E' = en-tête
    ('rib_emetteur', 24, 'L'),
    ('nom_emetteur', 26, 'L'),
    ('date_execution', 8, 'L'),        # AAAAMMJJ
    ('devise', 3, 'L'),
    ('nombre_lignes', 6, 'R'),
    ('total_centimes', 15, 'R'),
]
GABARIT_SIMT_LIGNE = [
    ('type_enregistrement', 1, 'L'),   # 'D' = détail
    ('rib_beneficiaire', 24, 'L'),
    ('nom_beneficiaire', 26, 'L'),
    ('montant_centimes', 15, 'R'),
    ('reference', 16, 'L'),
    ('motif', 30, 'L'),
]


def _formater_champ_simt(valeur, longueur, remplissage):
    """Formate un champ à LONGUEUR FIXE (gabarit SIMT) : tronque si trop
    long, complète sinon (espaces à droite pour 'L', zéros à gauche pour
    'R')."""
    texte = str(valeur or '')
    if remplissage == 'R':
        texte = texte[-longueur:] if len(texte) > longueur else texte
        return texte.rjust(longueur, '0')
    texte = texte[:longueur]
    return texte.ljust(longueur, ' ')


def _formater_enregistrement_simt(valeurs, gabarit):
    """Concatène les champs d'un enregistrement selon ``gabarit`` (SIMT)."""
    return ''.join(
        _formater_champ_simt(valeurs.get(champ, ''), longueur, remplissage)
        for champ, longueur, remplissage in gabarit)


def fichier_virement_paie_simt(ordre):
    """Fichier de virement au format bancaire marocain SIMT (XPAI8).

    Format à LONGUEURS FIXES (virement de masse) construit depuis les mêmes
    lignes que ``fichier_virement_paie`` — un enregistrement EN-TÊTE société
    (``GABARIT_SIMT_ENTETE``) puis un enregistrement DÉTAIL par bénéficiaire
    (``GABARIT_SIMT_LIGNE``), montants en CENTIMES (convention SIMT). Le
    gabarit exact dépend de la banque du fondateur (à valider) ; ce format
    STANDARD livre le mécanisme + une structure usuelle. Lève ``ValueError``
    dans les mêmes cas que ``fichier_virement_paie`` (aucune ligne / RIB
    manquant). N'affecte JAMAIS le CSV existant. Renvoie ``{'lignes': [str,
    …] (longueur fixe), 'total', 'nb_lignes'}``.
    """
    base = fichier_virement_paie(ordre)  # valide + lève ValueError au besoin
    emetteur = base['emetteur']
    date_execution = ordre.date_execution or date.today()

    total_centimes = int(_q(base['total']) * 100)
    entete = _formater_enregistrement_simt({
        'type_enregistrement': 'E',
        'rib_emetteur': emetteur.get('rib', ''),
        'nom_emetteur': emetteur.get('libelle', '') or ordre.company.nom,
        'date_execution': date_execution.strftime('%Y%m%d'),
        'devise': ordre.devise or 'MAD',
        'nombre_lignes': base['nb_lignes'],
        'total_centimes': total_centimes,
    }, GABARIT_SIMT_ENTETE)

    lignes_txt = [entete]
    for ligne in ordre.lignes.all():
        montant_centimes = int(_q(ligne.montant) * 100)
        lignes_txt.append(_formater_enregistrement_simt({
            'type_enregistrement': 'D',
            'rib_beneficiaire': ligne.rib,
            'nom_beneficiaire': ligne.beneficiaire,
            'montant_centimes': montant_centimes,
            'reference': ligne.reference or '',
            'motif': f'Salaire {ligne.reference}'.strip(),
        }, GABARIT_SIMT_LIGNE))

    return {
        'lignes': lignes_txt,
        'total': base['total'],
        'nb_lignes': base['nb_lignes'],
    }


# ── XPAI9 — Modes de paiement & suivi des rejets de virement ───────────────

def profils_hors_virement(periode):
    """Profils réglés HORS virement (espèces/chèque) d'une période (XPAI9).

    Liste, pour les bulletins VALIDÉS de la ``periode``, les profils dont
    ``mode_paiement`` n'est pas ``virement`` — exclus de l'ordre de virement
    (``generer_ordre_virement``), à régler/décompter séparément. Pour le mode
    ESPÈCES, esquisse un décompte de coupures usuel (billets/pièces MAD) sur
    le net à payer (informatif, arrondi au multiple le plus proche — n'importe
    pas de contrainte comptable). Lecture seule. Renvoie une liste de dicts
    ``{'profil_id', 'nom', 'mode_paiement', 'net_a_payer', 'decompte_especes'}``.
    """
    from .models import BulletinPaie, ProfilPaie

    bulletins = (
        BulletinPaie.objects
        .filter(company=periode.company, periode=periode,
                statut=BulletinPaie.STATUT_VALIDE)
        .exclude(profil__mode_paiement=ProfilPaie.MODE_PAIEMENT_VIREMENT)
        .select_related('profil', 'profil__employe')
    )
    resultat = []
    for bulletin in bulletins:
        profil = bulletin.profil
        employe = profil.employe
        nom = f'{employe.nom} {employe.prenom}'.strip() if employe else ''
        net = Decimal(bulletin.net_a_payer or 0)
        item = {
            'profil_id': profil.id,
            'nom': nom,
            'mode_paiement': profil.mode_paiement,
            'net_a_payer': _q(net),
        }
        if profil.mode_paiement == ProfilPaie.MODE_PAIEMENT_ESPECES:
            item['decompte_especes'] = decompte_coupures(net)
        resultat.append(item)
    return resultat


# Coupures MAD usuelles (billets puis pièces), du plus grand au plus petit.
COUPURES_MAD = [200, 100, 50, 20, 10, 5, 1]


def decompte_coupures(montant):
    """Décompte de coupures MAD pour un montant (XPAI9, espèces).

    Glouton sur ``COUPURES_MAD`` : nombre de billets/pièces de chaque valeur
    pour composer ``montant`` (arrondi à l'entier — les centimes ne sont pas
    décomptés en espèces). Renvoie ``{coupure: quantite, …}`` (coupures à 0
    omises) — purement informatif, aucun effet de bord.
    """
    reste = int(Decimal(montant or 0).to_integral_value())
    decompte = {}
    for coupure in COUPURES_MAD:
        if reste <= 0:
            break
        qte, reste = divmod(reste, coupure)
        if qte > 0:
            decompte[coupure] = qte
    return decompte


def marquer_bulletin_paye(bulletin, *, date_paiement=None):
    """Marque un bulletin comme PAYÉ (décompte espèces/chèque, XPAI9).

    Horodate le paiement (``paye=True``, ``date_paiement``). Idempotent :
    un bulletin déjà payé n'est pas re-horodaté (date d'origine conservée).
    Renvoie le bulletin.
    """
    if bulletin.paye:
        return bulletin
    bulletin.paye = True
    bulletin.date_paiement = date_paiement or timezone.now()
    bulletin.save(update_fields=['paye', 'date_paiement'])
    return bulletin


def rejeter_ligne_virement(ligne, *, motif=''):
    """Marque une ``LigneVirement`` comme REJETÉE (RIB invalide, XPAI9).

    Ne supprime JAMAIS la ligne (trace d'audit) : pose ``rejetee=True``,
    ``motif_rejet``, ``date_rejet``. Une ligne déjà rejetée n'est pas
    re-rejetée (idempotent). Renvoie la ligne.
    """
    if ligne.rejetee:
        return ligne
    ligne.rejetee = True
    ligne.motif_rejet = motif or 'RIB invalide'
    ligne.date_rejet = timezone.now()
    ligne.save(update_fields=['rejetee', 'motif_rejet', 'date_rejet'])
    return ligne


def reemettre_ligne_virement(ligne_rejetee, *, nouveau_rib):
    """Réémet une ligne de virement REJETÉE avec un RIB corrigé (XPAI9).

    Crée une NOUVELLE ``LigneVirement`` (même ordre/bulletin/bénéficiaire/
    montant/référence, RIB corrigé) et la relie à l'originale via
    ``ligne_correction`` — la ligne rejetée reste inchangée (jamais
    supprimée/modifiée). Lève ``ValueError`` si la ligne n'est pas rejetée,
    ou si l'ordre parent est déjà ÉMIS (figé — la correction se rejoue sur
    un NOUVEL ordre). Renvoie la nouvelle ``LigneVirement``.
    """
    from .models import LigneVirement, OrdreVirement

    if not ligne_rejetee.rejetee:
        raise ValueError('Seule une ligne rejetée peut être réémise.')
    if ligne_rejetee.ordre.statut == OrdreVirement.STATUT_EMIS:
        raise ValueError(
            "L'ordre est déjà émis : la correction doit passer par un "
            "nouvel ordre de virement.")
    if not nouveau_rib:
        raise ValueError('Le nouveau RIB est requis pour la réémission.')

    with transaction.atomic():
        nouvelle = LigneVirement.objects.create(
            company=ligne_rejetee.company,
            ordre=ligne_rejetee.ordre,
            bulletin=ligne_rejetee.bulletin,
            beneficiaire=ligne_rejetee.beneficiaire,
            rib=nouveau_rib,
            montant=ligne_rejetee.montant,
            reference=ligne_rejetee.reference,
        )
        ligne_rejetee.ligne_correction = nouvelle
        ligne_rejetee.save(update_fields=['ligne_correction'])
        return nouvelle


# ── PAIE31 — Déclaration CNSS (BDS / format DAMANCOM) ──────────────────────

def declaration_cnss(periode):
    """Bordereau de déclaration des salaires CNSS (BDS) d'une période (PAIE31).

    Agrège, pour les bulletins VALIDÉS de la ``periode``, les éléments du BDS
    par salarié affilié CNSS : numéro d'immatriculation CNSS, nom, nombre de
    jours déclarés (plafonné réglementairement à 26 j/mois), salaire brut réel
    et salaire PLAFONNÉ (base de cotisation, ``min(brut, plafond_cnss)``).
    Calcule aussi les totaux et les cotisations (salariale + patronale CNSS, AMO,
    allocations familiales, taxe de formation professionnelle).

    Lecture seule (aucun effet de bord). Le ``numero_cnss`` est lu sur le
    ``ProfilPaie`` (jamais sur ``rh.models``). Renvoie un dict ::

        {'annee', 'mois', 'plafond_cnss', 'lignes': [...],
         'total_brut', 'total_plafonne', 'total_cnss_salariale',
         'total_cnss_patronale', 'total_amo_salariale', 'total_amo_patronale',
         'total_allocations_familiales', 'total_formation_professionnelle',
         'nombre_salaries'}
    """
    from .models import BulletinPaie

    le_jour = date(periode.annee, periode.mois, 1)
    parametre = parametre_en_vigueur(periode.company, le_jour)
    plafond = Decimal(parametre.plafond_cnss or 0) if parametre else Decimal('0')

    bulletins = (
        BulletinPaie.objects
        .filter(company=periode.company, periode=periode,
                statut=BulletinPaie.STATUT_VALIDE)
        .select_related('profil', 'profil__employe')
    )
    lignes = []
    totaux = {
        'total_brut': Decimal('0'),
        'total_plafonne': Decimal('0'),
        'total_cnss_salariale': Decimal('0'),
        'total_cnss_patronale': Decimal('0'),
        'total_amo_salariale': Decimal('0'),
        'total_amo_patronale': Decimal('0'),
        'total_allocations_familiales': Decimal('0'),
        'total_formation_professionnelle': Decimal('0'),
    }
    for bulletin in bulletins:
        profil = bulletin.profil
        if not profil.affilie_cnss:
            continue
        brut = Decimal(bulletin.brut or 0)
        plafonne = min(brut, plafond) if plafond > 0 else brut
        employe = profil.employe
        nom = f'{employe.nom} {employe.prenom}'.strip() if employe else ''
        lignes.append({
            'numero_cnss': profil.numero_cnss or '',
            'matricule': getattr(employe, 'matricule', '') if employe else '',
            'nom': nom,
            'jours_declares': 26,  # mois plein déclaré par défaut (réglementaire)
            'brut': _q(brut),
            'plafonne': _q(plafonne),
            'cnss_salariale': _q(bulletin.cnss_salariale),
            'cnss_patronale': _q(bulletin.cnss_patronale),
            'amo_salariale': _q(bulletin.amo_salariale),
            'amo_patronale': _q(bulletin.amo_patronale),
            'allocations_familiales': _q(bulletin.allocations_familiales),
            'formation_professionnelle': _q(
                bulletin.formation_professionnelle),
        })
        totaux['total_brut'] += brut
        totaux['total_plafonne'] += plafonne
        totaux['total_cnss_salariale'] += Decimal(bulletin.cnss_salariale or 0)
        totaux['total_cnss_patronale'] += Decimal(bulletin.cnss_patronale or 0)
        totaux['total_amo_salariale'] += Decimal(bulletin.amo_salariale or 0)
        totaux['total_amo_patronale'] += Decimal(bulletin.amo_patronale or 0)
        totaux['total_allocations_familiales'] += Decimal(
            bulletin.allocations_familiales or 0)
        totaux['total_formation_professionnelle'] += Decimal(
            bulletin.formation_professionnelle or 0)

    resultat = {
        'annee': periode.annee,
        'mois': periode.mois,
        'plafond_cnss': _q(plafond),
        'lignes': lignes,
        'nombre_salaries': len(lignes),
    }
    for cle, valeur in totaux.items():
        resultat[cle] = _q(valeur)
    return resultat


def fichier_damancom_cnss(periode):
    """Fichier de télédéclaration CNSS au format DAMANCOM (PAIE31).

    Génère les lignes texte du fichier DAMANCOM à partir de
    ``declaration_cnss`` : une ligne d'en-tête société puis une ligne par
    salarié (numéro CNSS, nom, jours, brut, plafonné). Format SIMPLIFIÉ,
    séparateur ``;`` — la mise au format DAMANCOM strict (longueurs fixes) reste
    à confirmer côté CNSS. Renvoie ``{'lignes': [str, …], 'nombre_salaries',
    'total_brut', 'total_plafonne'}``. Lecture seule.
    """
    decl = declaration_cnss(periode)
    lignes_txt = [
        f'E;{periode.annee};{periode.mois:02d};'
        f'{decl["nombre_salaries"]};{decl["total_plafonne"]}'
    ]
    for ligne in decl['lignes']:
        lignes_txt.append(
            f'S;{ligne["numero_cnss"]};{ligne["nom"]};'
            f'{ligne["jours_declares"]};{ligne["brut"]};{ligne["plafonne"]}'
        )
    return {
        'lignes': lignes_txt,
        'nombre_salaries': decl['nombre_salaries'],
        'total_brut': decl['total_brut'],
        'total_plafonne': decl['total_plafonne'],
    }


# ── XPAI10 — Télédéclaration CIMR (fichier préétabli) ───────────────────────

def _periode_precedente(periode):
    """``PeriodePaie`` MENSUELLE précédente (même société), ou ``None``."""
    from .models import PeriodePaie

    annee, mois = periode.annee, periode.mois
    if mois == 1:
        annee, mois = annee - 1, 12
    else:
        mois -= 1
    return PeriodePaie.objects.filter(
        company=periode.company, annee=annee, mois=mois,
        type_run=PeriodePaie.TYPE_RUN_MENSUEL).first()


def declaration_cimr(periode):
    """Déclaration CIMR de la période (XPAI10) — fichier préétabli e-CIMR.

    Agrège, pour les bulletins VALIDÉS de la ``periode``, les affiliés CIMR
    (``ProfilPaie.affilie_cimr``) : catégorie d'adhésion (taux salarial),
    base (brut), parts salariale/patronale (CIMR patronale = même taux côté
    salarial faute de taux patronal distinct dans ce référentiel — noté).
    Détecte les NOUVEAUX AFFILIÉS (pas de bulletin CIMR le mois précédent) et
    les CHANGEMENTS DE SALAIRE (brut différent du mois précédent). Format
    exact du portail e-CIMR à confirmer par le fondateur → structure +
    export CSV documenté par défaut (``fichier_cimr``). Lecture seule.
    Renvoie ``{'annee', 'mois', 'lignes': [...], 'total_base',
    'total_cimr_salariale', 'nombre_affilies'}``.
    """
    from .models import BulletinPaie

    bulletins = (
        BulletinPaie.objects
        .filter(company=periode.company, periode=periode,
                statut=BulletinPaie.STATUT_VALIDE, profil__affilie_cimr=True)
        .select_related('profil', 'profil__employe')
    )
    precedente = _periode_precedente(periode)
    brut_precedent = {}
    profils_precedents = set()
    if precedente is not None:
        prec_bulletins = (
            BulletinPaie.objects
            .filter(company=periode.company, periode=precedente,
                    statut=BulletinPaie.STATUT_VALIDE,
                    profil__affilie_cimr=True)
            .values('profil_id', 'brut')
        )
        for row in prec_bulletins:
            profils_precedents.add(row['profil_id'])
            brut_precedent[row['profil_id']] = Decimal(row['brut'] or 0)

    lignes = []
    total_base = Decimal('0')
    total_cimr = Decimal('0')
    for bulletin in bulletins:
        profil = bulletin.profil
        employe = profil.employe
        nom = f'{employe.nom} {employe.prenom}'.strip() if employe else ''
        brut = Decimal(bulletin.brut or 0)
        cimr_sal = Decimal(bulletin.cimr_salariale or 0)
        nouvel_affilie = profil.id not in profils_precedents
        changement_salaire = (
            not nouvel_affilie
            and brut_precedent.get(profil.id) != brut
        )
        lignes.append({
            'profil_id': profil.id,
            'numero_cimr': profil.numero_cimr or '',
            'nom': nom,
            'categorie_taux': _q(Decimal(profil.taux_cimr_salarial or 0)),
            'base': _q(brut),
            'cimr_salariale': _q(cimr_sal),
            'nouvel_affilie': nouvel_affilie,
            'changement_salaire': changement_salaire,
        })
        total_base += brut
        total_cimr += cimr_sal

    return {
        'annee': periode.annee,
        'mois': periode.mois,
        'lignes': lignes,
        'total_base': _q(total_base),
        'total_cimr_salariale': _q(total_cimr),
        'nombre_affilies': len(lignes),
    }


def fichier_cimr(periode):
    """Fichier de télédéclaration CIMR — format CSV documenté (XPAI10).

    Format PAR DÉFAUT : le layout exact du fichier préétabli e-CIMR reste à
    confirmer par le fondateur auprès de la CIMR — ce format CSV
    (séparateur ``;``) documente la structure attendue (numéro CIMR, nom,
    taux, base, cotisation, drapeaux nouvel affilié/changement de salaire)
    en attendant la confirmation. Renvoie ``{'lignes': [str, …],
    'nombre_affilies', 'total_base', 'total_cimr_salariale'}``. Lecture
    seule.
    """
    decl = declaration_cimr(periode)
    lignes_txt = [
        f'E;{periode.annee};{periode.mois:02d};{decl["nombre_affilies"]};'
        f'{decl["total_base"]};{decl["total_cimr_salariale"]}'
    ]
    for ligne in decl['lignes']:
        lignes_txt.append(
            f'S;{ligne["numero_cimr"]};{ligne["nom"]};'
            f'{ligne["categorie_taux"]};{ligne["base"]};'
            f'{ligne["cimr_salariale"]};'
            f'{"N" if ligne["nouvel_affilie"] else ""};'
            f'{"C" if ligne["changement_salaire"] else ""}'
        )
    return {
        'lignes': lignes_txt,
        'nombre_affilies': decl['nombre_affilies'],
        'total_base': decl['total_base'],
        'total_cimr_salariale': decl['total_cimr_salariale'],
    }


# ── XPAI11 — AFFEBDS + déclarations de mouvement CNSS ───────────────────────

def parser_affebds(contenu):
    """Parse un fichier AFFEBDS (CSV/texte) importé de la CNSS (XPAI11).

    Format d'entrée SIMPLIFIÉ (documenté, séparateur ``;``) : une ligne par
    salarié affilié, ``numero_cnss;nom``. Lignes vides/commentaires (``#``)
    ignorées. Lecture pure. Renvoie une liste de dicts
    ``{'numero_cnss', 'nom'}``.
    """
    lignes = []
    for ligne in (contenu or '').splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith('#'):
            continue
        parts = ligne.split(';')
        numero_cnss = parts[0].strip() if len(parts) > 0 else ''
        nom = parts[1].strip() if len(parts) > 1 else ''
        if not numero_cnss:
            continue
        lignes.append({'numero_cnss': numero_cnss, 'nom': nom})
    return lignes


def rapprocher_affebds(company, contenu):
    """Rapproche un fichier AFFEBDS contre les ``ProfilPaie`` (XPAI11).

    Compare les numéros CNSS du fichier importé aux ``ProfilPaie`` actifs
    affiliés CNSS de la société : ``rapproches`` (numéro présent des deux
    côtés), ``manquants`` (dans le fichier CNSS, absent des profils paie —
    salarié CNSS non enregistré côté paie), ``en_trop`` (profil paie affilié
    CNSS avec un numéro qui n'apparaît pas dans le fichier — potentiel écart
    à investiguer). Lecture seule, AUCUN écrit sur les profils. Renvoie
    ``{'rapproches': [...], 'manquants': [...], 'en_trop': [...]}``.
    """
    from .models import ProfilPaie

    entrees_fichier = {
        ligne['numero_cnss']: ligne for ligne in parser_affebds(contenu)
    }
    profils = (
        ProfilPaie.objects
        .filter(company=company, actif=True, affilie_cnss=True)
        .exclude(numero_cnss='')
        .select_related('employe')
    )
    numeros_profils = {}
    for profil in profils:
        numeros_profils[profil.numero_cnss] = profil

    rapproches = []
    manquants = []
    for numero, ligne in entrees_fichier.items():
        profil = numeros_profils.get(numero)
        if profil is not None:
            rapproches.append({
                'numero_cnss': numero, 'nom_fichier': ligne['nom'],
                'profil_id': profil.id,
            })
        else:
            manquants.append(ligne)

    en_trop = [
        {'numero_cnss': numero, 'profil_id': profil.id}
        for numero, profil in numeros_profils.items()
        if numero not in entrees_fichier
    ]
    return {
        'rapproches': rapproches,
        'manquants': manquants,
        'en_trop': en_trop,
    }


def mouvements_cnss_periode(periode):
    """Entrées/sorties CNSS de la période (XPAI11) — alignée sur la BDS.

    ENTRÉES : profils actifs de la société SANS numéro CNSS (embauchés à
    déclarer, dossier d'immatriculation à ouvrir). SORTIES : profils dont le
    dossier RH a une ``date_sortie`` tombant dans le mois de la ``periode``
    (lue via ``rh.selectors.sortie_employe`` — jamais ``rh.models`` direct).
    Lecture seule, aucun écrit sur rh. Renvoie ``{'entrees': [...],
    'sorties': [...]}``.
    """
    from apps.rh import selectors as rh_selectors  # import paresseux cross-app

    from .models import ProfilPaie

    profils = (
        ProfilPaie.objects
        .filter(company=periode.company, affilie_cnss=True)
        .select_related('employe')
    )
    entrees = []
    sorties = []
    for profil in profils:
        if not profil.numero_cnss and profil.actif:
            employe = profil.employe
            nom = f'{employe.nom} {employe.prenom}'.strip() if employe else ''
            entrees.append({'profil_id': profil.id, 'nom': nom})

        date_sortie, motif_sortie = rh_selectors.sortie_employe(
            periode.company, profil.employe_id)
        if date_sortie and date_sortie.year == periode.annee \
                and date_sortie.month == periode.mois:
            employe = profil.employe
            nom = f'{employe.nom} {employe.prenom}'.strip() if employe else ''
            sorties.append({
                'profil_id': profil.id, 'nom': nom,
                'date_sortie': date_sortie, 'motif_sortie': motif_sortie or '',
            })
    return {'entrees': entrees, 'sorties': sorties}


# ── XPAI12 — BDS complémentaire/rectificative + format DAMANCOM strict ─────

def deposer_bds_principal(periode):
    """Enregistre le dépôt PRINCIPAL de la BDS d'une période (XPAI12).

    Un seul dépôt principal par période : rejoue (idempotent) le dépôt déjà
    enregistré s'il existe. Couvre TOUS les salariés affiliés CNSS de la
    déclaration (``declaration_cnss``). Renvoie le ``DepotBDS`` (créé ou
    existant).
    """
    from .models import DepotBDS

    existant = DepotBDS.objects.filter(
        company=periode.company, periode=periode,
        type_depot=DepotBDS.TYPE_PRINCIPAL).first()
    if existant is not None:
        return existant

    decl = declaration_cnss(periode)
    profils = [ligne.get('numero_cnss') for ligne in decl['lignes']]
    return DepotBDS.objects.create(
        company=periode.company, periode=periode,
        type_depot=DepotBDS.TYPE_PRINCIPAL, profils_couverts=profils)


def deposer_bds_complementaire(periode, profils_delta, *, depot_principal=None):
    """Enregistre un dépôt BDS COMPLÉMENTAIRE — DELTA uniquement (XPAI12).

    ``profils_delta`` est la liste des identifiants (numéros CNSS ou ids
    ``ProfilPaie``) des salariés OMIS/CORRIGÉS — jamais l'ensemble des
    salariés à nouveau. Référence le dépôt principal de la période
    (``depot_principal`` fourni, sinon le dépôt principal existant — lève
    ``ValueError`` si aucun dépôt principal n'a encore été déposé : une
    correction suppose une déclaration principale déjà déposée). Renvoie le
    nouveau ``DepotBDS`` complémentaire.
    """
    from .models import DepotBDS

    principal = depot_principal or DepotBDS.objects.filter(
        company=periode.company, periode=periode,
        type_depot=DepotBDS.TYPE_PRINCIPAL).first()
    if principal is None:
        raise ValueError(
            'Aucun dépôt BDS principal pour cette période : la BDS '
            'complémentaire suppose une déclaration principale déjà déposée.')
    return DepotBDS.objects.create(
        company=periode.company, periode=periode,
        type_depot=DepotBDS.TYPE_COMPLEMENTAIRE,
        depot_principal=principal,
        profils_couverts=list(profils_delta or []))


# DÉCISION — gabarit eBDS STRICT (longueurs fixes, cahier des charges
# DAMANCOM). Spécimen à valider fondateur/CNSS avant tout dépôt réel ; ce
# gabarit livre le MÉCANISME + une structure standard couramment citée.
GABARIT_EBDS_ENTETE = [
    ('type_enregistrement', 1, 'L'),   # 'E' = en-tête
    ('affiliation_cnss', 9, 'R'),      # n° d'affiliation employeur
    ('periode', 6, 'L'),               # AAAAMM
    ('nombre_salaries', 6, 'R'),
]
GABARIT_EBDS_LIGNE = [
    ('type_enregistrement', 1, 'L'),   # 'S' = salarié
    ('numero_cnss', 9, 'R'),
    ('nom', 30, 'L'),
    ('jours_declares', 2, 'R'),
    ('salaire_plafonne_centimes', 12, 'R'),
]


def fichier_damancom_strict(periode, *, depot=None):
    """Fichier DAMANCOM au format eBDS STRICT — longueurs fixes (XPAI12).

    Reprend ``declaration_cnss`` et formate chaque enregistrement au gabarit
    eBDS (``GABARIT_EBDS_ENTETE``/``GABARIT_EBDS_LIGNE``). Si ``depot`` est un
    ``DepotBDS`` COMPLÉMENTAIRE, ne formate QUE les salariés de
    ``depot.profils_couverts`` (delta) — sinon (dépôt principal / aucun
    dépôt) formate l'ensemble de la déclaration. Le layout exact est À
    VALIDER auprès de la CNSS avant tout dépôt réel. Renvoie ``{'lignes':
    [str, …] (longueur fixe), 'nombre_salaries'}``.
    """
    from .models import DepotBDS

    decl = declaration_cnss(periode)
    lignes_decl = decl['lignes']
    if depot is not None and depot.type_depot == DepotBDS.TYPE_COMPLEMENTAIRE:
        delta = set(depot.profils_couverts or [])
        lignes_decl = [
            ligne for ligne in lignes_decl
            if ligne.get('numero_cnss') in delta]

    entete = _formater_enregistrement_simt({
        'type_enregistrement': 'E',
        'affiliation_cnss': periode.company_id,
        'periode': f'{periode.annee}{periode.mois:02d}',
        'nombre_salaries': len(lignes_decl),
    }, GABARIT_EBDS_ENTETE)

    lignes_txt = [entete]
    for ligne in lignes_decl:
        salaire_centimes = int(_q(ligne['plafonne']) * 100)
        lignes_txt.append(_formater_enregistrement_simt({
            'type_enregistrement': 'S',
            'numero_cnss': ligne.get('numero_cnss', ''),
            'nom': ligne.get('nom', ''),
            'jours_declares': ligne.get('jours_declares', 26),
            'salaire_plafonne_centimes': salaire_centimes,
        }, GABARIT_EBDS_LIGNE))

    return {'lignes': lignes_txt, 'nombre_salaries': len(lignes_decl)}


# ── PAIE32 — État IR 9421 + retenues à la source ───────────────────────────

def etat_ir_9421(periode):
    """État IR 9421 (retenues à la source) d'une période (PAIE32).

    État employeur des traitements & salaires et de l'IR retenu à la source pour
    les bulletins VALIDÉS de la ``periode`` : par salarié, le brut imposable, le
    net imposable, l'IR retenu et le nombre de personnes à charge. Calcule les
    totaux. Le ``matricule`` est lu sur le dossier RH via la relation existante
    (jamais via ``rh.models``).

    Lecture seule. Renvoie un dict ::

        {'annee', 'mois', 'lignes': [...], 'total_brut_imposable',
         'total_net_imposable', 'total_ir', 'nombre_salaries'}
    """
    from .models import BulletinPaie

    bulletins = (
        BulletinPaie.objects
        .filter(company=periode.company, periode=periode,
                statut=BulletinPaie.STATUT_VALIDE)
        .select_related('profil', 'profil__employe')
    )
    lignes = []
    total_brut_imp = Decimal('0')
    total_net_imp = Decimal('0')
    total_ir = Decimal('0')
    total_exonere = Decimal('0')
    for bulletin in bulletins:
        profil = bulletin.profil
        employe = profil.employe
        nom = f'{employe.nom} {employe.prenom}'.strip() if employe else ''
        brut_imp = Decimal(bulletin.brut_imposable or 0)
        net_imp = Decimal(bulletin.net_imposable or 0)
        ir = Decimal(bulletin.ir or 0)
        # XPAI18 — montant exonéré au titre du régime stagiaire/ANAPEC/TAHFIZ.
        exonere = Decimal(getattr(bulletin, 'montant_exonere_regime', 0) or 0)
        lignes.append({
            'matricule': getattr(employe, 'matricule', '') if employe else '',
            'nom': nom,
            'brut_imposable': _q(brut_imp),
            'net_imposable': _q(net_imp),
            'ir': _q(ir),
            'montant_exonere_regime': _q(exonere),
            'personnes_a_charge': bulletin.personnes_a_charge,
            'frais_professionnels': _q(bulletin.frais_professionnels),
        })
        total_brut_imp += brut_imp
        total_net_imp += net_imp
        total_ir += ir
        total_exonere += exonere

    return {
        'annee': periode.annee,
        'mois': periode.mois,
        'lignes': lignes,
        'total_brut_imposable': _q(total_brut_imp),
        'total_net_imposable': _q(total_net_imp),
        'total_ir': _q(total_ir),
        'total_exonere_regime': _q(total_exonere),
        'nombre_salaries': len(lignes),
    }


def etat_ir_9421_annuel(company, annee):
    """État IR 9421 ANNUEL (retenues à la source) pour une société (PAIE32).

    Variante annuelle : agrège l'IR retenu sur TOUTES les périodes de l'année
    ``annee``, par salarié (cumul brut imposable / net imposable / IR sur les
    bulletins validés des 12 mois). Lecture seule. Renvoie un dict de même forme
    que ``etat_ir_9421`` (sans ``mois``), trié par matricule.
    """
    from .models import BulletinPaie

    bulletins = (
        BulletinPaie.objects
        .filter(company=company, periode__annee=annee,
                statut=BulletinPaie.STATUT_VALIDE)
        .select_related('profil', 'profil__employe')
    )
    par_profil = {}
    for bulletin in bulletins:
        profil = bulletin.profil
        ligne = par_profil.setdefault(profil.id, {
            'profil_id': profil.id,
            'matricule': getattr(profil.employe, 'matricule', '')
            if profil.employe else '',
            'nom': f'{profil.employe.nom} {profil.employe.prenom}'.strip()
            if profil.employe else '',
            'brut_imposable': Decimal('0'),
            'net_imposable': Decimal('0'),
            'ir': Decimal('0'),
            'nombre_bulletins': 0,
        })
        ligne['brut_imposable'] += Decimal(bulletin.brut_imposable or 0)
        ligne['net_imposable'] += Decimal(bulletin.net_imposable or 0)
        ligne['ir'] += Decimal(bulletin.ir or 0)
        ligne['nombre_bulletins'] += 1

    lignes = []
    total_brut_imp = Decimal('0')
    total_net_imp = Decimal('0')
    total_ir = Decimal('0')
    for ligne in par_profil.values():
        ligne['brut_imposable'] = _q(ligne['brut_imposable'])
        ligne['net_imposable'] = _q(ligne['net_imposable'])
        ligne['ir'] = _q(ligne['ir'])
        total_brut_imp += ligne['brut_imposable']
        total_net_imp += ligne['net_imposable']
        total_ir += ligne['ir']
        lignes.append(ligne)
    lignes.sort(key=lambda r: (r['matricule'], r['profil_id']))

    return {
        'annee': annee,
        'lignes': lignes,
        'total_brut_imposable': _q(total_brut_imp),
        'total_net_imposable': _q(total_net_imp),
        'total_ir': _q(total_ir),
        'nombre_salaries': len(lignes),
    }


# ── XPAI13 — Export XML EDI SIMPL-IR (état 9421) ────────────────────────────

# DÉCISION — schéma SIMPL-IR EMBARQUÉ (structure des éléments/attributs
# attendus, cahier des charges état 9421 annuel). Le schéma XSD OFFICIEL de
# la DGI n'est pas embarqué tel quel (dépendance externe) ; ce descripteur
# STRUCTUREL (noms d'éléments, cardinalité, types simples) sert de contrat de
# validation local — suffisant pour prouver la conformité de FORME avant tout
# dépôt réel, qui reste soumis à validation DGI.
XSD_SIMPL_IR_9421 = {
    'root': 'Etat9421',
    'children': {
        'Entete': {'cardinalite': '1', 'attrs': ['annee', 'nombreSalaries']},
        'Salarie': {
            'cardinalite': '*',
            'attrs': [
                'matricule', 'categorie', 'brutImposable', 'netImposable',
                'ir', 'montantExonere',
            ],
        },
        'Totaux': {
            'cardinalite': '1',
            'attrs': ['totalBrutImposable', 'totalNetImposable', 'totalIr'],
        },
    },
}

# Catégories SIMPL-IR — personnel permanent/occasionnel/stagiaire.
# ``ProfilPaie.type_remuneration`` distingue mensuel/forfait (permanent) de
# journalier/horaire (occasionnel) ; les stagiaires (statut RH dédié) ne sont
# pas encore distingués côté paie (limitation connue, à affiner avec le
# statut RH stagiaire quand il existera dans ce référentiel).
_CATEGORIE_PAR_TYPE_REMUNERATION = {
    'mensuel': 'permanent',
    'forfait': 'permanent',
    'journalier': 'occasionnel',
    'horaire': 'occasionnel',
}


def categorie_9421_profil(profil):
    """Catégorie SIMPL-IR d'un profil — permanent/occasionnel (XPAI13)."""
    return _CATEGORIE_PAR_TYPE_REMUNERATION.get(
        profil.type_remuneration, 'permanent')


def _xml_escape(texte):
    return (
        str(texte)
        .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        .replace('"', '&quot;'))


def export_xml_simpl_ir_9421(company, annee):
    """Génère le fichier XML EDI conforme SIMPL-IR de l'état 9421 (XPAI13).

    Reprend ``etat_ir_9421_annuel`` (mêmes totaux, aucun recalcul) et le
    formate en XML bien formé selon la structure ``XSD_SIMPL_IR_9421``
    (validée par ``valider_xml_simpl_ir_9421``) : un ``<Etat9421>`` racine,
    une ``<Entete>``, une ``<Salarie>`` par ligne (avec ``categorie``
    permanent/occasionnel, ``montantExonere`` — 0 tant que XPAI18 n'est pas
    câblé, champ présent pour compat future), une ``<Totaux>``. Renvoie le
    XML (str). Lève ``ValueError`` si la validation structurelle échoue
    (garde de non-régression — ne devrait jamais se produire, le générateur
    et le validateur partagent le même schéma).
    """
    from .models import ProfilPaie

    etat = etat_ir_9421_annuel(company, annee)
    profils_par_id = {
        p.id: p for p in ProfilPaie.objects.filter(
            company=company,
            id__in=[ligne['profil_id'] for ligne in etat['lignes']])
    }

    parties = ['<?xml version="1.0" encoding="UTF-8"?>', '<Etat9421>']
    parties.append(
        f'<Entete annee="{annee}" '
        f'nombreSalaries="{etat["nombre_salaries"]}"/>')
    for ligne in etat['lignes']:
        profil = profils_par_id.get(ligne['profil_id'])
        categorie = categorie_9421_profil(profil) if profil else 'permanent'
        parties.append(
            '<Salarie '
            f'matricule="{_xml_escape(ligne["matricule"])}" '
            f'categorie="{categorie}" '
            f'brutImposable="{ligne["brut_imposable"]}" '
            f'netImposable="{ligne["net_imposable"]}" '
            f'ir="{ligne["ir"]}" '
            'montantExonere="0.00"/>')
    parties.append(
        '<Totaux '
        f'totalBrutImposable="{etat["total_brut_imposable"]}" '
        f'totalNetImposable="{etat["total_net_imposable"]}" '
        f'totalIr="{etat["total_ir"]}"/>')
    parties.append('</Etat9421>')
    xml = ''.join(parties)

    valider_xml_simpl_ir_9421(xml)  # lève ValueError si non conforme
    return xml


def valider_xml_simpl_ir_9421(xml_str):
    """Valide un XML SIMPL-IR contre le schéma embarqué (XPAI13).

    Vérifie la BONNE FORMATION (``xml.etree.ElementTree``, lève
    ``ValueError`` si mal formé) puis la CONFORMITÉ STRUCTURELLE au
    descripteur ``XSD_SIMPL_IR_9421`` : élément racine, cardinalité de
    ``Entete``/``Totaux`` (exactement 1), attributs requis présents sur
    chaque élément. Lève ``ValueError`` avec un message explicite au premier
    écart. Renvoie ``True`` si conforme.
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as exc:
        raise ValueError(f'XML mal formé : {exc}') from exc

    schema = XSD_SIMPL_IR_9421
    if root.tag != schema['root']:
        raise ValueError(
            f'Élément racine attendu "{schema["root"]}", trouvé "{root.tag}".')

    for nom, regle in schema['children'].items():
        elements = root.findall(nom)
        if regle['cardinalite'] == '1' and len(elements) != 1:
            raise ValueError(
                f'Élément "{nom}" attendu exactement 1 fois, trouvé '
                f'{len(elements)} fois.')
        for element in elements:
            for attr in regle['attrs']:
                if attr not in element.attrib:
                    raise ValueError(
                        f'Attribut requis "{attr}" manquant sur "{nom}".')
    return True


# ── XPAI15 — Contrôle des écarts avant validation (M vs M-1) ───────────────

SEUIL_ECART_NET_DEFAUT = Decimal('20')  # % — seuil paramétrable (query param).


def controle_ecarts(periode, *, seuil_pct=None):
    """Compare le run courant au mois précédent, par salarié (XPAI15).

    Garde-fou PRÉ-VALIDATION (avertissement, JAMAIS blocage) : détecte, en
    comparant les bulletins de la ``periode`` (n'importe quel statut — le
    contrôle a lieu AVANT validation) aux bulletins VALIDÉS du mois
    précédent :

    * salariés MANQUANTS (bulletin le mois dernier, aucun ce mois-ci) ;
    * salariés NOUVEAUX (bulletin ce mois-ci, aucun le mois dernier) ;
    * VARIATION DE NET > ``seuil_pct`` % (défaut ``SEUIL_ECART_NET_DEFAUT``,
      20 %) — un net qui double, qui s'effondre, etc. ;
    * HS ANORMALES — heures supplémentaires du mois > 2× la moyenne des HS
      du mois précédent (ou HS ce mois alors qu'il n'y en avait aucune le
      mois dernier, au-delà d'un seuil bas de 10 h pour éviter le bruit).

    Lecture seule. Renvoie ``{'salaries_manquants': [...],
    'salaries_nouveaux': [...], 'variations_net': [...],
    'hs_anormales': [...]}`` — chaque item porte assez de contexte pour
    l'écran de contrôle (profil, nom, montants comparés).
    """
    from .models import BulletinPaie, ElementVariable

    seuil = Decimal(seuil_pct) if seuil_pct is not None \
        else SEUIL_ECART_NET_DEFAUT

    precedente = _periode_precedente(periode)

    bulletins_courants = {
        b.profil_id: b
        for b in BulletinPaie.objects.filter(
            company=periode.company, periode=periode)
        .select_related('profil', 'profil__employe')
    }
    bulletins_precedents = {}
    if precedente is not None:
        bulletins_precedents = {
            b.profil_id: b
            for b in BulletinPaie.objects.filter(
                company=periode.company, periode=precedente,
                statut=BulletinPaie.STATUT_VALIDE)
            .select_related('profil', 'profil__employe')
        }

    def _nom(bulletin):
        employe = bulletin.profil.employe
        return f'{employe.nom} {employe.prenom}'.strip() if employe else ''

    salaries_manquants = [
        {'profil_id': pid, 'nom': _nom(b)}
        for pid, b in bulletins_precedents.items()
        if pid not in bulletins_courants
    ]
    salaries_nouveaux = [
        {'profil_id': pid, 'nom': _nom(b)}
        for pid, b in bulletins_courants.items()
        if pid not in bulletins_precedents
    ]

    variations_net = []
    for pid, b_courant in bulletins_courants.items():
        b_prec = bulletins_precedents.get(pid)
        if b_prec is None:
            continue
        net_prec = Decimal(b_prec.net_a_payer or 0)
        net_courant = Decimal(b_courant.net_a_payer or 0)
        if net_prec == 0:
            continue
        variation_pct = abs(net_courant - net_prec) / net_prec * 100
        if variation_pct > seuil:
            variations_net.append({
                'profil_id': pid, 'nom': _nom(b_courant),
                'net_precedent': _q(net_prec), 'net_courant': _q(net_courant),
                'variation_pct': _q(variation_pct),
            })

    # HS anormales : somme des heures TYPE_HS de la période courante vs mois
    # précédent, par profil.
    def _total_hs(periode_cible):
        if periode_cible is None:
            return {}
        totaux = {}
        for el in ElementVariable.objects.filter(
                company=periode.company, periode=periode_cible,
                type=ElementVariable.TYPE_HS):
            totaux[el.profil_id] = totaux.get(
                el.profil_id, Decimal('0')) + Decimal(el.quantite or 0)
        return totaux

    hs_courant = _total_hs(periode)
    hs_precedent = _total_hs(precedente)
    hs_anormales = []
    for pid, heures in hs_courant.items():
        heures_prec = hs_precedent.get(pid, Decimal('0'))
        anormale = False
        if heures_prec > 0 and heures > heures_prec * 2:
            anormale = True
        elif heures_prec == 0 and heures > Decimal('10'):
            anormale = True
        if anormale:
            bulletin = bulletins_courants.get(pid)
            hs_anormales.append({
                'profil_id': pid,
                'nom': _nom(bulletin) if bulletin else '',
                'hs_precedent': _q(heures_prec), 'hs_courant': _q(heures),
            })

    return {
        'salaries_manquants': salaries_manquants,
        'salaries_nouveaux': salaries_nouveaux,
        'variations_net': variations_net,
        'hs_anormales': hs_anormales,
        'seuil_pct': _q(seuil),
    }


# ── YHIRE3 — Contrôle de complétude pré-paie ────────────────────────────────

def controle_completude(periode):
    """Contrôle de complétude pré-paie (YHIRE3, l'analogue « pas de CNSS = pas
    de paie »). Rien ne signalait les trous avant génération : un actif SANS
    ``ProfilPaie`` était silencieusement ignoré par l'import
    (``importer_elements_rh``), un dossier sans n° CNSS/RIB passait quand même
    en bulletin/virement, un profil actif dont le dossier est SORTI ou
    EMBAUCHE (non pris de poste) n'était pas détecté, un CDD dont
    ``contrat_date_fin`` est antérieure à la période non plus.

    Lecture RH via ``apps.rh.selectors`` (jamais ``rh.models`` directement,
    hormis la traversée du FK direct ``ProfilPaie.employe`` déjà propriété de
    la paie). Distinct de ``controle_ecarts`` (XPAI15, comparaison des
    MONTANTS M vs M-1) : ici ce sont des trous STRUCTURELS.

    YHIRE6 — inclut aussi ``ecarts_remuneration`` : profils actifs dont le
    ``salaire_base`` DIVERGE de la ``rh.Remuneration`` EN VIGUEUR (FG157,
    ``rh.selectors.remuneration_en_vigueur``) à la fin de la période —
    l'historisation par ``date_effet`` promet la reproductibilité, mais
    RIEN ne remontait jamais l'écart avant. Jamais de montant dans les
    notifications (donnée sensible) : uniquement dans ce contrôle gaté
    ``salaires_voir`` côté vue.

    Renvoie ``{'actifs_sans_profil': [...], 'profils_sans_cnss': [...],
    'profils_sans_rib': [...], 'profils_actifs_dossiers_non_actifs': [...],
    'contrats_expires': [...], 'ecarts_remuneration': [...]}`` — chaque item
    porte assez de contexte pour l'écran de contrôle (dossier/profil id,
    matricule, nom).
    """
    import calendar

    from apps.rh import selectors as rh_selectors

    from .models import ProfilPaie

    company = periode.company
    date_fin_periode = date(
        periode.annee, periode.mois,
        calendar.monthrange(periode.annee, periode.mois)[1])

    dossiers_actifs = {
        d.id: d for d in rh_selectors.dossiers_actifs(company)
    }
    profils = list(
        ProfilPaie.objects.filter(company=company)
        .select_related('employe'))
    profils_par_employe = {p.employe_id: p for p in profils}

    def _libelle(dossier):
        return f'{dossier.matricule} — {dossier.nom} {dossier.prenom}'.strip()

    # Actifs sans profil de paie (l'import RH les ignore silencieusement).
    actifs_sans_profil = [
        {'dossier_id': did, 'matricule': d.matricule, 'nom': _libelle(d)}
        for did, d in dossiers_actifs.items()
        if did not in profils_par_employe
    ]

    # Profils actifs (paie) sans CNSS/RIB — bloquant recommandé côté écran.
    profils_sans_cnss = []
    profils_sans_rib = []
    profils_actifs_dossiers_non_actifs = []
    for profil in profils:
        if not profil.actif:
            continue
        dossier = profil.employe
        if not profil.numero_cnss:
            profils_sans_cnss.append({
                'profil_id': profil.id, 'dossier_id': dossier.id,
                'matricule': dossier.matricule, 'nom': _libelle(dossier),
            })
        if not profil.rib:
            profils_sans_rib.append({
                'profil_id': profil.id, 'dossier_id': dossier.id,
                'matricule': dossier.matricule, 'nom': _libelle(dossier),
            })
        # Profil actif alors que le dossier RH est SORTI ou EMBAUCHE (n'a
        # jamais pris de poste) — décalage à corriger avant de payer.
        if dossier.id not in dossiers_actifs:
            profils_actifs_dossiers_non_actifs.append({
                'profil_id': profil.id, 'dossier_id': dossier.id,
                'matricule': dossier.matricule, 'nom': _libelle(dossier),
                'statut_dossier': dossier.statut,
            })

    # CDD dont la fin de contrat est antérieure à la fin de la période.
    contrats_expires = [
        {
            'profil_id': profil.id, 'dossier_id': profil.employe.id,
            'matricule': profil.employe.matricule,
            'nom': _libelle(profil.employe),
            'contrat_date_fin': profil.employe.contrat_date_fin,
        }
        for profil in profils
        if profil.actif
        and profil.employe.type_contrat == 'cdd'
        and profil.employe.contrat_date_fin is not None
        and profil.employe.contrat_date_fin < date_fin_periode
    ]

    # YHIRE6 — écart salaire profil (paie) vs rémunération en vigueur (RH).
    ecarts_remuneration = []
    for profil in profils:
        if not profil.actif:
            continue
        dossier = profil.employe
        ref = rh_selectors.remuneration_en_vigueur(
            company, dossier.id, date_fin_periode)
        if ref is None:
            continue
        if _q(profil.salaire_base) != _q(ref['montant_mensuel']):
            ecarts_remuneration.append({
                'profil_id': profil.id, 'dossier_id': dossier.id,
                'matricule': dossier.matricule, 'nom': _libelle(dossier),
                'salaire_profil': _q(profil.salaire_base),
                'remuneration_en_vigueur': ref['montant_mensuel'],
                'date_effet': ref['date_effet'],
            })

    return {
        'actifs_sans_profil': actifs_sans_profil,
        'profils_sans_cnss': profils_sans_cnss,
        'profils_sans_rib': profils_sans_rib,
        'profils_actifs_dossiers_non_actifs': profils_actifs_dossiers_non_actifs,
        'contrats_expires': contrats_expires,
        'ecarts_remuneration': ecarts_remuneration,
    }


# ── ZPAI2 — Panneau d'avertissements pré-run (blocages de paie) ────────────

def avertissements_periode(periode):
    """Panneau d'avertissements avant de payer, façon Odoo (ZPAI2).

    Distinct de ``controle_ecarts`` (XPAI15, écart de MONTANTS M vs M-1) : ici
    ce sont les PRÉREQUIS manquants avant de lancer un run. Réutilise
    ``controle_completude`` (YHIRE3, mêmes trous structurels) et le reshape
    en une liste PLATE d'avertissements typés + gravité, plus deux contrôles
    supplémentaires propres à ZPAI2 :

    * RIB vide alors que ``mode_paiement='virement'`` (bloquant — un profil
      chèque/espèces sans RIB n'entre pas dans l'ordre de virement, donc pas
      d'avertissement pour lui) ;
    * ``salaire_base`` à 0 sur un profil actif (bloquant — bulletin nul).

    Lecture seule, jamais d'écriture sur ``rh``. Renvoie une liste de dicts
    ``{'type', 'employe_id', 'matricule', 'nom', 'gravite', 'message'}`` —
    ``gravite`` ∈ {'bloquant', 'avertissement'}.
    """
    from .models import ProfilPaie

    completude = controle_completude(periode)
    company = periode.company

    avertissements = []

    for item in completude['actifs_sans_profil']:
        avertissements.append({
            'type': 'sans_profil_paie', 'employe_id': item['dossier_id'],
            'matricule': item['matricule'], 'nom': item['nom'],
            'gravite': 'bloquant',
            'message': f"{item['nom']} — aucun profil de paie : ignoré "
                       "par l'import RH et par la génération du bulletin.",
        })
    for item in completude['profils_sans_cnss']:
        avertissements.append({
            'type': 'cnss_manquant', 'employe_id': item['dossier_id'],
            'matricule': item['matricule'], 'nom': item['nom'],
            'gravite': 'bloquant',
            'message': f"{item['nom']} — numéro CNSS manquant.",
        })
    for item in completude['profils_actifs_dossiers_non_actifs']:
        avertissements.append({
            'type': 'dossier_non_actif', 'employe_id': item['dossier_id'],
            'matricule': item['matricule'], 'nom': item['nom'],
            'gravite': 'avertissement',
            'message': f"{item['nom']} — profil de paie actif alors que le "
                       f"dossier RH est « {item['statut_dossier']} ».",
        })
    for item in completude['contrats_expires']:
        avertissements.append({
            'type': 'cdd_echu', 'employe_id': item['dossier_id'],
            'matricule': item['matricule'], 'nom': item['nom'],
            'gravite': 'avertissement',
            'message': f"{item['nom']} — CDD échu le "
                       f"{item['contrat_date_fin']}.",
        })

    profils = (
        ProfilPaie.objects.filter(company=company, actif=True)
        .select_related('employe'))
    for profil in profils:
        dossier = profil.employe
        nom = f'{dossier.matricule} — {dossier.nom} {dossier.prenom}'.strip()
        if (profil.mode_paiement == ProfilPaie.MODE_PAIEMENT_VIREMENT
                and not profil.rib):
            avertissements.append({
                'type': 'rib_manquant_virement', 'employe_id': dossier.id,
                'matricule': dossier.matricule, 'nom': nom,
                'gravite': 'bloquant',
                'message': f'{nom} — RIB manquant, mode de paiement '
                           'virement : sans RIB, le net ne sera pas '
                           'transmis à la banque.',
            })
        if not profil.salaire_base or profil.salaire_base <= 0:
            avertissements.append({
                'type': 'salaire_nul', 'employe_id': dossier.id,
                'matricule': dossier.matricule, 'nom': nom,
                'gravite': 'bloquant',
                'message': f'{nom} — salaire de base à 0 : le bulletin '
                           'sera nul.',
            })

    return avertissements


def synchroniser_salaire(profil, le_jour=None):
    """Aligne ``ProfilPaie.salaire_base`` sur la rémunération RH en vigueur
    (YHIRE6). Jamais de sync silencieuse : appelée EXPLICITEMENT (action
    ``synchroniser-salaire``, gatée ``salaires_voir`` côté vue) après que
    l'écart a été vu au contrôle de complétude.

    Lit ``rh.selectors.remuneration_en_vigueur`` (jamais ``rh.models``
    directement, hormis le FK ``ProfilPaie.employe`` déjà propriété de la
    paie). Renvoie le profil mis à jour, ou le renvoie inchangé si aucune
    rémunération RH n'est en vigueur à cette date (rien à synchroniser).
    """
    from apps.rh import selectors as rh_selectors

    jour = le_jour or timezone.localdate()
    ref = rh_selectors.remuneration_en_vigueur(
        profil.company, profil.employe_id, jour)
    if ref is None:
        return profil
    profil.salaire_base = ref['montant_mensuel']
    profil.save(update_fields=['salaire_base'])
    return profil


# ── PAIE33 — Livre de paie + journal de paie → écritures (via compta) ───────

# Comptes CGNC utilisés par l'écriture de paie (barème CGNC marocain) :
#  6171 Rémunérations du personnel (charge — brut)
#  6174 Charges sociales (charge — parts patronales)
#  4441 Caisses de sécurité sociale (dette CNSS/AMO sal. + pat.)
#  4452 État, impôts & taxes à payer (dette IR retenu)
#  4443 Caisses de retraite (dette CIMR)
#  4432 Rémunérations dues au personnel (dette — net à payer)
_COMPTE_REMUNERATION = '6171'
_COMPTE_CHARGES_SOCIALES = '6174'
_COMPTE_CNSS = '4441'
_COMPTE_IR = '4452'
_COMPTE_CIMR = '4443'
_COMPTE_NET = '4432'


def livre_de_paie(periode):
    """Livre de paie d'une période (PAIE33) — registre récapitulatif.

    Registre LECTURE SEULE de tous les bulletins VALIDÉS de la ``periode`` :
    une ligne par salarié (brut, brut imposable, cotisations salariales &
    patronales, IR, net à payer) plus les totaux généraux. Sert d'état légal du
    livre de paie et de base au journal de paie. Renvoie un dict ``{'annee',
    'mois', 'lignes': [...], 'totaux': {...}, 'nombre_salaries'}``.
    """
    from .models import BulletinPaie

    bulletins = (
        BulletinPaie.objects
        .filter(company=periode.company, periode=periode,
                statut=BulletinPaie.STATUT_VALIDE)
        .select_related('profil', 'profil__employe')
    )
    champs = [
        'brut', 'brut_imposable', 'cnss_salariale', 'cnss_patronale',
        'amo_salariale', 'amo_patronale', 'cimr_salariale', 'ir',
        'frais_professionnels', 'net_imposable', 'retenues', 'net_a_payer',
        'charges_patronales',
    ]
    lignes = []
    totaux = {champ: Decimal('0') for champ in champs}
    for bulletin in bulletins:
        employe = bulletin.profil.employe
        ligne = {
            'matricule': getattr(employe, 'matricule', '') if employe else '',
            'nom': f'{employe.nom} {employe.prenom}'.strip()
            if employe else '',
        }
        for champ in champs:
            valeur = Decimal(getattr(bulletin, champ) or 0)
            ligne[champ] = _q(valeur)
            totaux[champ] += valeur
        lignes.append(ligne)
    return {
        'annee': periode.annee,
        'mois': periode.mois,
        'lignes': lignes,
        'totaux': {champ: _q(valeur) for champ, valeur in totaux.items()},
        'nombre_salaries': len(lignes),
    }


def journal_de_paie(periode, *, created_by=None):
    """Passe l'écriture comptable du journal de paie d'une période (PAIE33).

    Agrège les bulletins VALIDÉS de la ``periode`` (via ``livre_de_paie``) et
    crée UNE écriture de régularisation (OD) ÉQUILIBRÉE au 1ᵉʳ du mois suivant
    (la fin de période) par ``compta.services.creer_ecriture_od`` — la paie
    n'importe JAMAIS ``compta.models`` ni ``compta.views`` directement, elle
    passe par la couche ``services`` de compta (cross-app WRITE autorisé).

    Schéma de l'écriture (CGNC) :

    * Débit 6171 Rémunérations du personnel = total BRUT ;
    * Débit 6174 Charges sociales = total des charges PATRONALES ;
    * Crédit 4441 Caisses de sécurité sociale = CNSS+AMO (salariales+patronales) ;
    * Crédit 4452 État, impôts & taxes = IR retenu ;
    * Crédit 4443 Caisses de retraite = CIMR salariale ;
    * Crédit 4432 Rémunérations dues au personnel = net à payer + retenues.

    L'écriture s'équilibre par construction (Σ débit = Σ crédit). Sème le plan
    comptable au besoin. Renvoie l'écriture créée, ou ``None`` s'il n'y a aucun
    bulletin validé (rien à passer).
    """
    from apps.compta import services as compta_services  # cross-app via services

    registre = livre_de_paie(periode)
    if registre['nombre_salaries'] == 0:
        return None
    totaux = registre['totaux']

    company = periode.company
    # Sème le plan comptable si un compte requis manque (idempotent).
    requis = [
        _COMPTE_REMUNERATION, _COMPTE_CHARGES_SOCIALES, _COMPTE_CNSS,
        _COMPTE_IR, _COMPTE_CIMR, _COMPTE_NET,
    ]
    if any(compta_services.get_compte(company, num) is None for num in requis):
        compta_services.seed_plan_comptable(company)

    def compte(numero):
        return compta_services.get_compte(company, numero)

    brut = totaux['brut']
    charges_pat = totaux['charges_patronales']
    cnss_amo = (
        totaux['cnss_salariale'] + totaux['cnss_patronale']
        + totaux['amo_salariale'] + totaux['amo_patronale']
    )
    ir = totaux['ir']
    cimr = totaux['cimr_salariale']

    lignes = [
        {'compte': compte(_COMPTE_REMUNERATION),
         'libelle': 'Rémunérations du personnel', 'debit': brut, 'credit': 0},
    ]
    if charges_pat > 0:
        lignes.append({
            'compte': compte(_COMPTE_CHARGES_SOCIALES),
            'libelle': 'Charges sociales patronales',
            'debit': charges_pat, 'credit': 0})
    if cnss_amo > 0:
        lignes.append({
            'compte': compte(_COMPTE_CNSS),
            'libelle': 'CNSS / AMO à payer', 'debit': 0, 'credit': cnss_amo})
    if ir > 0:
        lignes.append({
            'compte': compte(_COMPTE_IR),
            'libelle': 'IR retenu à la source', 'debit': 0, 'credit': ir})
    if cimr > 0:
        lignes.append({
            'compte': compte(_COMPTE_CIMR),
            'libelle': 'CIMR à payer', 'debit': 0, 'credit': cimr})
    # Net à payer = solde équilibrant (brut + charges pat − cotisations − IR
    # − CIMR). On le calcule pour garantir l'équilibre exact même en cas
    # d'arrondis.
    total_debit = brut + (charges_pat if charges_pat > 0 else Decimal('0'))
    total_credit_hors_net = (
        (cnss_amo if cnss_amo > 0 else Decimal('0'))
        + (ir if ir > 0 else Decimal('0'))
        + (cimr if cimr > 0 else Decimal('0'))
    )
    net_equilibrant = _q(total_debit - total_credit_hors_net)
    lignes.append({
        'compte': compte(_COMPTE_NET),
        'libelle': 'Rémunérations dues au personnel (net)',
        'debit': 0, 'credit': net_equilibrant})

    # Date de l'écriture = dernier jour du mois de paie (proxy : 28, toujours
    # valide). Le détail jour exact n'a pas d'incidence comptable mensuelle.
    date_ecriture = date(periode.annee, periode.mois, 28)
    libelle = f'Journal de paie {periode.mois:02d}/{periode.annee}'
    reference = f'PAIE-{periode.annee}-{periode.mois:02d}'
    ecriture = compta_services.creer_ecriture_od(
        company, date_ecriture, libelle, lignes,
        reference=reference, created_by=created_by)
    return ecriture


# ── XPAI5 — État des charges sociales + rapprochement paie↔GL ──────────────

# Organismes déclaratifs, chacun mappé au compte CGNC crédité par
# ``journal_de_paie`` (mêmes constantes ``_COMPTE_*`` que PAIE33) + le
# libellé affiché. Le compte mutuelle n'a pas de compte CGNC dédié posté par
# le journal de paie aujourd'hui (limitation connue, non couverte ici).
_ORGANISMES_CHARGES = [
    ('cnss_amo', 'CNSS / AMO', _COMPTE_CNSS),
    ('ir', 'État — IR retenu à la source', _COMPTE_IR),
    ('cimr', 'CIMR', _COMPTE_CIMR),
]


def etat_des_charges(periode):
    """État consolidé des charges sociales par organisme (XPAI5).

    Agrège, pour les bulletins VALIDÉS de la ``periode``, les montants dus par
    organisme (CNSS+AMO, IR, CIMR) — parts salariale ET patronale, montant
    total à payer. Renvoie un dict ``{'annee', 'mois', 'organismes': [...]
    (chacun {'code', 'libelle', 'salarial', 'patronal', 'total',
    'echeance'}), 'total_general'}``. Lecture seule.
    """
    registre = livre_de_paie(periode)
    totaux = registre['totaux']

    cnss_amo_sal = totaux['cnss_salariale'] + totaux['amo_salariale']
    cnss_amo_pat = totaux['cnss_patronale'] + totaux['amo_patronale']
    ir = totaux['ir']
    cimr = totaux['cimr_salariale']

    # Échéances réglementaires usuelles (jour du mois suivant) — informatif.
    organismes = [
        {
            'code': 'cnss_amo', 'libelle': 'CNSS / AMO',
            'salarial': _q(cnss_amo_sal), 'patronal': _q(cnss_amo_pat),
            'total': _q(cnss_amo_sal + cnss_amo_pat),
            'echeance_jour': 10,
        },
        {
            'code': 'ir', 'libelle': 'État — IR retenu à la source',
            'salarial': _q(ir), 'patronal': Decimal('0.00'),
            'total': _q(ir), 'echeance_jour': 20,
        },
        {
            'code': 'cimr', 'libelle': 'CIMR',
            'salarial': _q(cimr), 'patronal': Decimal('0.00'),
            'total': _q(cimr), 'echeance_jour': 10,
        },
    ]
    total_general = sum((o['total'] for o in organismes), Decimal('0.00'))
    return {
        'annee': periode.annee,
        'mois': periode.mois,
        'organismes': organismes,
        'total_general': _q(total_general),
    }


def rapprochement_paie_gl(periode):
    """Rapproche le livre de paie (documentaire) au GL posté (XPAI5).

    Prouve que, pour la ``periode``, les totaux du livre de paie ÉGALENT
    l'écriture comptable postée par ``journal_de_paie`` sur chaque compte
    organisme (4441 CNSS/AMO, 4452 IR, 4443 CIMR). Lecture compta EXCLUSIVEMENT
    via ``compta.selectors.grand_livre`` (cross-app READ autorisé, jamais
    ``compta.models`` direct). Fenêtre GL bornée au mois de la période (1er au
    dernier jour du mois) pour n'attraper QUE l'écriture de cette paie.

    Renvoie un dict ``{'annee', 'mois', 'lignes': [{'code', 'libelle',
    'attendu_paie', 'poste_gl', 'ecart'}], 'ecart_total', 'coherent'}`` —
    ``coherent`` est vrai quand tous les écarts sont nuls (aucune écriture
    postée = écart signalé, pas un skip silencieux).
    """
    from apps.compta import selectors as compta_selectors  # cross-app READ

    etat = etat_des_charges(periode)
    total_par_code = {o['code']: o['total'] for o in etat['organismes']}

    date_debut = date(periode.annee, periode.mois, 1)
    if periode.mois == 12:
        date_fin = date(periode.annee, 12, 31)
    else:
        date_fin = date(periode.annee, periode.mois + 1, 1) - timedelta(days=1)

    gl = compta_selectors.grand_livre(
        periode.company, date_debut=date_debut, date_fin=date_fin,
        validees_seulement=False)
    solde_par_numero = {bucket['numero']: bucket['solde'] for bucket in gl}

    lignes = []
    ecart_total = Decimal('0.00')
    for code, libelle, numero in _ORGANISMES_CHARGES:
        attendu = total_par_code.get(code, Decimal('0.00'))
        # Le GL crédite l'organisme (dette) : solde débit-crédit est NÉGATIF
        # pour une dette pure ; on compare en valeur absolue (montant dû).
        poste_gl = _q(abs(solde_par_numero.get(numero, Decimal('0'))))
        ecart = _q(attendu - poste_gl)
        ecart_total += ecart
        lignes.append({
            'code': code, 'libelle': libelle, 'compte': numero,
            'attendu_paie': attendu, 'poste_gl': poste_gl, 'ecart': ecart,
        })
    return {
        'annee': periode.annee,
        'mois': periode.mois,
        'lignes': lignes,
        'ecart_total': _q(ecart_total),
        'coherent': ecart_total == 0,
    }


# ── YLEDG7 — Règlement de l'OV salaires + des organismes sociaux ───────────
#
# ``journal_de_paie`` (PAIE33) poste correctement les DETTES (crédit 4432 net,
# 4441 CNSS/AMO, 4452 IR, 4443 CIMR) mais rien ne poste jamais le RÈGLEMENT :
# ``emettre_ordre_virement`` ne fait que figer le statut, et aucun service ne
# solde 4441/4452/4443 aux organismes. Les dettes de paie s'empilent au GL
# pour toujours. Les deux fonctions ci-dessous postent le débit du compte de
# dette / crédit trésorerie, au même patron que ``journal_de_paie``
# (``compta.services`` via import cross-app fonction-local, jamais
# ``compta.models``).

# Mappe le ``code`` de ``_ORGANISMES_CHARGES`` (utilisé par
# ``etat_des_charges``/``rapprochement_paie_gl``) au(x) type(s)
# ``EcheanceDeclarative.TYPE_*`` que ``payer_organismes`` peut solder.
_ECHEANCE_TYPES_PAR_ORGANISME = {
    'cnss_amo': (EcheanceDeclarative.TYPE_BDS,),
    'ir': (EcheanceDeclarative.TYPE_IR_MENSUEL,),
    'cimr': (EcheanceDeclarative.TYPE_CIMR,),
}


def payer_ordre_virement(ordre, compte_tresorerie, *,
                         date_reglement=None, created_by=None):
    """Poste l'écriture de règlement de l'OV salaires (YLEDG7).

    À l'émission/exécution de l'``OrdreVirement`` : débite 4432
    Rémunérations dues au personnel du ``ordre.total`` / crédite le compte
    comptable du ``compte_tresorerie`` (banque, DC20). Idempotent — un ordre
    déjà réglé (``ecriture_reglement_id`` posé) renvoie son écriture existante
    sans repasser. Refusé si la période comptable de la date de règlement est
    verrouillée (FG115). Le ``compte_tresorerie`` DOIT appartenir à la même
    société que l'ordre.

    Renvoie l'écriture comptable postée.
    """
    from apps.compta import services as compta_services
    from apps.compta.models import EcritureComptable

    company = ordre.company
    if ordre.ecriture_reglement_id:
        return EcritureComptable.objects.filter(
            pk=ordre.ecriture_reglement_id).first()
    compte_tresorerie = _resoudre_compte_emetteur(company, compte_tresorerie)
    if compte_tresorerie is None:
        raise ValueError(
            "Le compte de trésorerie doit appartenir à la société de "
            "l'ordre de virement.")
    if not ordre.total or ordre.total <= 0:
        raise ValueError("L'ordre de virement n'a aucun montant à régler.")

    date_reg = date_reglement or timezone.localdate()
    compte_net = compta_services.get_compte(company, _COMPTE_NET)
    if compte_net is None:
        compta_services.seed_plan_comptable(company)
        compte_net = compta_services.get_compte(company, _COMPTE_NET)

    montant = _q(ordre.total)
    libelle = f'Règlement salaires {ordre.reference or ordre.id}'
    lignes = [
        {'compte': compte_net, 'libelle': libelle,
         'debit': montant, 'credit': Decimal('0')},
        {'compte': compte_tresorerie.compte_comptable, 'libelle': libelle,
         'debit': Decimal('0'), 'credit': montant},
    ]
    ecriture = compta_services.creer_ecriture_od(
        company, date_reg, libelle, lignes,
        reference=f'OV-REGLEMENT-{ordre.id}', created_by=created_by)
    ordre.ecriture_reglement_id = ecriture.id
    ordre.date_reglement = timezone.now()
    ordre.save(update_fields=['ecriture_reglement_id', 'date_reglement'])
    return ecriture


def payer_organismes(periode, organisme, compte_tresorerie, *,
                     date_reglement=None, created_by=None):
    """Poste l'écriture de règlement d'un organisme social (YLEDG7).

    ``organisme`` est un des codes de ``_ORGANISMES_CHARGES``
    (``'cnss_amo'``/``'ir'``/``'cimr'``) : débite le compte de dette
    correspondant (4441/4452/4443) du montant dû (``etat_des_charges``) /
    crédite le compte comptable du ``compte_tresorerie``. Marque PAYÉE la
    (les) ``EcheanceDeclarative`` de la période correspondant à cet
    organisme (idempotent par écheance — une échéance déjà payée n'est jamais
    re-postée). Refusé si la période comptable de règlement est verrouillée.

    Renvoie l'écriture postée, ou ``None`` si le montant dû est nul (rien à
    régler) ou si toutes les échéances de l'organisme sont déjà payées.
    """
    from apps.compta import services as compta_services

    mapping = {code: (libelle, numero)
               for code, libelle, numero in _ORGANISMES_CHARGES}
    if organisme not in mapping:
        raise ValueError(f"Organisme inconnu : {organisme!r}.")
    libelle_organisme, numero_compte = mapping[organisme]

    company = periode.company
    types_echeance = _ECHEANCE_TYPES_PAR_ORGANISME.get(organisme, ())
    echeances = list(EcheanceDeclarative.objects.filter(
        company=company, periode=periode, type_echeance__in=types_echeance,
    ).exclude(statut=EcheanceDeclarative.STATUT_PAYEE))
    if not echeances:
        # Toutes déjà payées (ou aucune échéance de ce type) — no-op.
        return None

    etat = etat_des_charges(periode)
    total_par_code = {o['code']: o['total'] for o in etat['organismes']}
    montant = total_par_code.get(organisme, Decimal('0.00'))
    if montant <= 0:
        return None

    compte_tresorerie = _resoudre_compte_emetteur(company, compte_tresorerie)
    if compte_tresorerie is None:
        raise ValueError(
            "Le compte de trésorerie doit appartenir à la société de la "
            "période.")

    date_reg = date_reglement or timezone.localdate()
    compte_dette = compta_services.get_compte(company, numero_compte)
    if compte_dette is None:
        compta_services.seed_plan_comptable(company)
        compte_dette = compta_services.get_compte(company, numero_compte)

    montant = _q(montant)
    libelle_ecriture = (
        f'Règlement {libelle_organisme} — {periode.mois:02d}/{periode.annee}')
    lignes = [
        {'compte': compte_dette, 'libelle': libelle_ecriture,
         'debit': montant, 'credit': Decimal('0')},
        {'compte': compte_tresorerie.compte_comptable,
         'libelle': libelle_ecriture,
         'debit': Decimal('0'), 'credit': montant},
    ]
    ecriture = compta_services.creer_ecriture_od(
        company, date_reg, libelle_ecriture, lignes,
        reference=f'ORG-{organisme.upper()}-{periode.id}',
        created_by=created_by)
    for echeance in echeances:
        echeance.statut = EcheanceDeclarative.STATUT_PAYEE
        echeance.ecriture_reglement_id = ecriture.id
        echeance.save(update_fields=['statut', 'ecriture_reglement_id'])
    return ecriture


# ── PAIE27 — Cumul annuel par employé (recalcul depuis bulletins validés) ────

# Champs cumulés : (champ du CumulAnnuel, champ du BulletinPaie) sommés.
_CUMUL_CHAMPS = [
    'brut', 'brut_imposable', 'net_imposable', 'ir',
    'cnss_salariale', 'amo_salariale', 'cimr_salariale',
    'frais_professionnels', 'net_a_payer', 'charges_patronales',
    'provision_conges',
]


def recalculer_cumul_annuel(profil, annee):
    """Recalcule (idempotent) le ``CumulAnnuel`` d'un profil pour une année (PAIE27).

    Agrège les montants des bulletins VALIDÉS du profil dont la période tombe sur
    ``annee`` : brut, brut/net imposable, IR, CNSS/AMO/CIMR salariales, frais
    professionnels, net à payer, charges patronales, provision congés. Le cumul
    des jours de congés (acquis/pris) est lu via le solde RH (``SoldeConge``) par
    référence STRING-FK — la paie n'importe jamais ``rh.models``.

    Crée le ``CumulAnnuel`` s'il n'existe pas, sinon le met à jour ; clé stable
    ``(company, profil, annee)``. Opération atomique. Renvoie le ``CumulAnnuel``.
    """
    from django.apps import apps as django_apps

    from .models import BulletinPaie, CumulAnnuel

    bulletins = (
        BulletinPaie.objects
        .filter(
            company=profil.company,
            profil=profil,
            periode__annee=annee,
            statut=BulletinPaie.STATUT_VALIDE,
        )
    )

    totaux = {champ: Decimal('0') for champ in _CUMUL_CHAMPS}
    nombre = 0
    for bulletin in bulletins:
        nombre += 1
        for champ in _CUMUL_CHAMPS:
            totaux[champ] += Decimal(getattr(bulletin, champ) or 0)

    # Compteur de congés depuis le solde RH (string-FK, cadré société).
    conges_acquis = Decimal('0')
    conges_pris = Decimal('0')
    SoldeConge = django_apps.get_model('rh', 'SoldeConge')
    solde = (
        SoldeConge.objects
        .filter(company=profil.company, employe_id=profil.employe_id,
                annee=annee)
        .first()
    )
    if solde is not None:
        conges_acquis = (solde.report or Decimal('0')) \
            + (solde.acquis or Decimal('0'))
        conges_pris = solde.pris or Decimal('0')

    with transaction.atomic():
        cumul, _ = CumulAnnuel.objects.select_for_update().get_or_create(
            company=profil.company, profil=profil, annee=annee)
        for champ in _CUMUL_CHAMPS:
            setattr(cumul, champ, _q(totaux[champ]))
        cumul.conges_acquis = _q(conges_acquis)
        cumul.conges_pris = _q(conges_pris)
        cumul.nombre_bulletins = nombre
        cumul.date_calcul = timezone.now()
        cumul.save()
    return cumul


# ── XPAI4 — 13e mois & gratifications + runs hors-cycle ─────────────────────

CODE_GRATIFICATION_13E = 'GRATIF_13E'


def prorata_presence_annee(date_embauche, date_sortie, annee, *,
                           mois_reference=12):
    """Fraction de l'année couverte par la présence de l'employé (XPAI4).

    Le 13e mois/prime de bilan se calcule au prorata des MOIS de présence sur
    ``annee`` (embauché en cours d'année → prorata ; sorti en cours d'année →
    prorata jusqu'à la sortie). ``mois_reference`` borne la fenêtre (12 = année
    civile complète). Renvoie ``(mois_presence, Decimal fraction 0..1)`` —
    mois de présence comptés ENTIERS (mois d'embauche/sortie inclus).
    """
    debut_annee = date(annee, 1, 1)
    fin_annee = date(annee, mois_reference, 1)
    # Dernier jour du mois de référence.
    if mois_reference == 12:
        fin_annee = date(annee, 12, 31)
    else:
        fin_annee = date(annee, mois_reference + 1, 1) - timedelta(days=1)

    debut = date_embauche if date_embauche and date_embauche > debut_annee \
        else debut_annee
    fin = date_sortie if date_sortie and date_sortie < fin_annee else fin_annee
    if debut > fin:
        return 0, Decimal('0.00')

    mois_presence = (
        (fin.year - debut.year) * 12 + (fin.month - debut.month) + 1
    )
    mois_presence = max(0, min(mois_reference, mois_presence))
    fraction = (Decimal(mois_presence) / Decimal(mois_reference)) \
        if mois_reference else Decimal('0')
    return mois_presence, _q(fraction)


def calculer_gratification(profil, periode, *, annee_reference=None,
                           personnes_a_charge=0):
    """Calcule le 13e mois / prime de bilan prorata d'un profil (XPAI4).

    Moteur SANS effet de bord : le montant de base
    (``profil.salaire_base``, une mensualité pleine) est proratisé sur la
    présence de l'année ``annee_reference`` (défaut : l'année de la
    ``periode``), puis soumis aux cotisations CNSS/AMO/IR standard comme un
    gain normal (flags portés par la rubrique ``GRATIF_13E`` — soumis CNSS/AMO,
    imposable). Renvoie un dict ``{'montant_brut', 'mois_presence',
    'fraction_presence', 'cnss_salariale', 'amo_salariale', 'net_imposable',
    'ir', 'net_a_payer', 'lignes'}``.
    """
    annee_reference = annee_reference or periode.annee
    le_jour = date(periode.annee, periode.mois, 1)
    parametre = parametre_en_vigueur(profil.company, le_jour)
    bareme = bareme_en_vigueur(profil.company, le_jour)

    from apps.rh import selectors as rh_selectors  # import paresseux cross-app

    date_embauche = rh_selectors.date_embauche_employe(
        profil.company, profil.employe_id)
    date_sortie, _motif = rh_selectors.sortie_employe(
        profil.company, profil.employe_id)
    mois_presence, fraction = prorata_presence_annee(
        date_embauche, date_sortie, annee_reference)

    base_pleine = Decimal(profil.salaire_base or 0)
    montant_brut = _q(base_pleine * fraction)

    cnss_sal = cnss_salariale(parametre, montant_brut, profil.affilie_cnss) \
        if parametre else Decimal('0.00')
    amo_sal = amo_salariale(parametre, montant_brut, profil.affilie_amo) \
        if parametre else Decimal('0.00')
    cnss_pat = cnss_patronale(parametre, montant_brut, profil.affilie_cnss) \
        if parametre else Decimal('0.00')
    amo_pat = amo_patronale(parametre, montant_brut, profil.affilie_amo) \
        if parametre else Decimal('0.00')

    net_imposable = _q(montant_brut - cnss_sal - amo_sal)
    ir = Decimal('0.00')
    if bareme and parametre:
        ir = compute_ir(net_imposable, bareme, parametre, personnes_a_charge)
    ir = _q(ir)
    net_a_payer = _q(net_imposable - ir)

    lignes = []
    if montant_brut > 0:
        lignes.append({
            'code': CODE_GRATIFICATION_13E,
            'libelle': '13e mois / prime de bilan (prorata présence)',
            'type': Rubrique.TYPE_GAIN, 'montant': montant_brut,
        })
    if cnss_sal > 0:
        lignes.append({
            'code': 'CNSS_SAL', 'libelle': 'CNSS salariale',
            'type': Rubrique.TYPE_RETENUE, 'montant': cnss_sal,
        })
    if amo_sal > 0:
        lignes.append({
            'code': 'AMO_SAL', 'libelle': 'AMO salariale',
            'type': Rubrique.TYPE_RETENUE, 'montant': amo_sal,
        })
    if ir > 0:
        lignes.append({
            'code': 'IR', 'libelle': 'Impôt sur le revenu',
            'type': Rubrique.TYPE_RETENUE, 'montant': ir,
        })

    return {
        'brut': montant_brut,
        'brut_imposable': montant_brut,
        'mois_presence': mois_presence,
        'fraction_presence': fraction,
        'cnss_salariale': cnss_sal,
        'cnss_patronale': cnss_pat,
        'amo_salariale': amo_sal,
        'amo_patronale': amo_pat,
        'allocations_familiales': Decimal('0.00'),
        'formation_professionnelle': Decimal('0.00'),
        'provision_conges': Decimal('0.00'),
        'cimr_salariale': Decimal('0.00'),
        'frais_professionnels': Decimal('0.00'),
        'net_imposable': net_imposable,
        'ir': ir,
        'retenues': Decimal('0.00'),
        'prime_anciennete': Decimal('0.00'),
        'charges_patronales': _q(cnss_pat + amo_pat),
        'net_a_payer': net_a_payer,
        'lignes': lignes,
    }


def generer_run_gratification(periode, *, annee_reference=None):
    """Génère les bulletins « 13e mois » de TOUS les profils actifs (XPAI4).

    ``periode`` doit être une ``PeriodePaie`` de ``type_run ==
    TYPE_RUN_HORS_CYCLE`` (une période « run 13e mois » distincte du mois
    calendaire, cf. modèle). Itère les profils actifs de la société (lecture
    RH via ``rh.selectors.dossiers_actifs`` — jamais ``rh.models`` direct),
    calcule et matérialise un ``BulletinPaie`` de nature
    ``TYPE_GRATIFICATION`` par profil (prorata de présence), consolidé ensuite
    par ``recalculer_cumul_annuel`` (PAIE27). Opération atomique par bulletin
    (une erreur sur un profil n'interrompt pas les suivants). Renvoie la liste
    des bulletins générés.
    """
    from apps.rh import selectors as rh_selectors  # import paresseux cross-app

    from .models import BulletinPaie, LigneBulletin, ProfilPaie

    if periode.type_run != PeriodePaie.TYPE_RUN_HORS_CYCLE:
        raise ValueError(
            "generer_run_gratification exige une période hors-cycle "
            "(type_run='hors_cycle').")
    if periode.statut == PeriodePaie.STATUT_CLOTUREE:
        raise BulletinPaie.BulletinVerrouille(
            'Période clôturée : génération de run gratification interdite.')

    dossiers_actifs = rh_selectors.dossiers_actifs(periode.company)
    employe_ids_actifs = set(dossiers_actifs.values_list('id', flat=True))
    profils = ProfilPaie.objects.filter(
        company=periode.company, actif=True,
        employe_id__in=employe_ids_actifs)

    bulletins = []
    for profil in profils:
        resultat = calculer_gratification(
            profil, periode, annee_reference=annee_reference)
        with transaction.atomic():
            bulletin = (
                BulletinPaie.objects
                .select_for_update()
                .filter(periode=periode, profil=profil)
                .first()
            )
            if bulletin is not None and bulletin.est_valide:
                continue  # déjà validé : figé, on ne régénère pas
            if bulletin is None:
                bulletin = BulletinPaie(
                    company=periode.company, periode=periode, profil=profil)
            bulletin.type_bulletin = BulletinPaie.TYPE_GRATIFICATION
            bulletin.motif = '13e mois / gratification'
            for champ in BulletinPaie.SNAPSHOT_FIELDS:
                if champ == 'personnes_a_charge':
                    continue
                if champ in resultat:
                    setattr(bulletin, champ, resultat[champ])
            bulletin.statut = BulletinPaie.STATUT_BROUILLON
            bulletin.save()

            bulletin.lignes.all().delete()
            for ordre, ligne in enumerate(resultat.get('lignes', []), start=1):
                LigneBulletin.objects.create(
                    company=periode.company,
                    bulletin=bulletin,
                    code=ligne.get('code', ''),
                    libelle=ligne.get('libelle', ''),
                    type=ligne.get('type', 'gain'),
                    montant=ligne.get('montant', Decimal('0')),
                    ordre=ordre,
                )
            bulletins.append(bulletin)
    return bulletins


# ── XPAI1 — Solde de tout compte (STC) ──────────────────────────────────────

# Barème de l'indemnité légale de licenciement (Code du travail marocain,
# art. 53) : nombre d'heures de salaire par ANNÉE d'ancienneté, par tranche.
# Tuples ``(borne_max_annees, heures_par_annee)`` ; la dernière tranche a une
# ``borne_max`` à ``None`` (sans plafond). Barème standard (DÉCISION, valeurs
# couramment citées) :
#   * <= 5 ans     -> 96 h par année d'ancienneté ;
#   * 6-10 ans     -> 144 h par année d'ancienneté ;
#   * 11-15 ans    -> 192 h par année d'ancienneté ;
#   * > 15 ans     -> 240 h par année d'ancienneté.
BAREME_INDEMNITE_LICENCIEMENT_ART53 = [
    (Decimal('5'), Decimal('96')),
    (Decimal('10'), Decimal('144')),
    (Decimal('15'), Decimal('192')),
    (None, Decimal('240')),
]


def indemnite_licenciement_art53(anciennete_annees, taux_horaire_base,
                                 bareme=None):
    """Indemnité légale de licenciement/départ — barème art. 53 (XPAI1).

    Le barème est PROGRESSIF PAR TRANCHE : chaque tranche d'ancienneté (0-5,
    6-10, 11-15, >15 ans) contribue ses PROPRES heures de salaire par année
    couverte par la tranche (jamais tout à un seul taux — c'est le taux
    marginal de la tranche qui s'applique à la fraction d'années qu'elle
    couvre). ``anciennete_annees`` peut être fractionnaire (années complètes +
    mois) ; ``taux_horaire_base`` est le taux horaire de référence du salarié.

    Renvoie un ``Decimal`` >= 0 arrondi au centime. 0 si l'ancienneté ou le
    taux horaire sont nuls/négatifs.
    """
    annees = Decimal(anciennete_annees or 0)
    taux_h = Decimal(taux_horaire_base or 0)
    if annees <= 0 or taux_h <= 0:
        return Decimal('0.00')
    if bareme is None:
        bareme = BAREME_INDEMNITE_LICENCIEMENT_ART53

    total_heures = Decimal('0')
    borne_basse = Decimal('0')
    for borne_max, heures_par_annee in bareme:
        if borne_max is None or annees <= borne_max:
            total_heures += (annees - borne_basse) * heures_par_annee
            break
        total_heures += (borne_max - borne_basse) * heures_par_annee
        borne_basse = borne_max
    return _q(total_heures * taux_h)


def indemnite_preavis(salaire_mensuel, mois_preavis=1):
    """Indemnité de préavis — ``salaire_mensuel × mois_preavis`` (XPAI1).

    ``mois_preavis`` par défaut à 1 mois (durée courante pour un cadre/agent
    de maîtrise ; éditable par l'appelant selon la catégorie/ancienneté).
    Renvoie un ``Decimal`` >= 0 au centime.
    """
    salaire = Decimal(salaire_mensuel or 0)
    mois = Decimal(mois_preavis or 0)
    if salaire <= 0 or mois <= 0:
        return Decimal('0.00')
    return _q(salaire * mois)


def indemnite_compensatrice_conges(company, employe_id, annee, taux_journalier):
    """Indemnité compensatrice de congés payés non pris (XPAI1).

    Valorise le solde de congés DISPONIBLE (``solde_conge_disponible``) au
    ``taux_journalier`` du salarié. Renvoie un ``Decimal`` >= 0 au centime.
    """
    solde = solde_conge_disponible(company, employe_id, annee)
    taux = Decimal(taux_journalier or 0)
    if solde <= 0 or taux <= 0:
        return Decimal('0.00')
    return _q(solde * taux)


def exoneration_ir_indemnite_licenciement(indemnite, parametre):
    """Part EXONÉRÉE d'IR de l'indemnité de licenciement (XPAI1).

    Cadre marocain : l'indemnité légale de licenciement/départ est exonérée
    d'IR dans la limite du barème légal ; au-delà d'un plafond (paramétré par
    la Loi de Finances,
    ``ParametrePaie.plafond_exoneration_ir_indemnite_licenciement``, défaut
    1 000 000 MAD), l'excédent est réintégré dans la base imposable. Renvoie
    ``(part_exoneree, part_imposable)`` — deux ``Decimal`` au centime, sommant
    exactement à ``indemnite``.
    """
    indemnite = Decimal(indemnite or 0)
    if indemnite <= 0:
        return Decimal('0.00'), Decimal('0.00')
    plafond = Decimal('1000000')
    if parametre is not None:
        plafond = Decimal(
            parametre.plafond_exoneration_ir_indemnite_licenciement or 0)
    if indemnite <= plafond:
        return _q(indemnite), Decimal('0.00')
    return _q(plafond), _q(indemnite - plafond)


def calculer_stc(profil, periode, *, motif='', mois_preavis=1,
                 personnes_a_charge=0):
    """Calcule le solde de tout compte (STC) d'un profil sortant (XPAI1).

    Moteur de calcul additif SANS effet de bord (renvoie un dict, ne crée
    aucun objet) : part du bulletin normal calculé par ``calculer_bulletin``
    (dernier salaire proraté + éléments variables de la période), puis AJOUTE
    les indemnités de fin de contrat :

    * indemnité compensatrice de congés payés non pris
      (``indemnite_compensatrice_conges``) ;
    * indemnité de préavis (``indemnite_preavis``, si ``mois_preavis > 0``) ;
    * indemnité légale de licenciement (barème art. 53,
      ``indemnite_licenciement_art53``), avec EXONÉRATION IR partielle
      (``exoneration_ir_indemnite_licenciement``) — seule la part imposable
      entre dans le net imposable/IR, la part exonérée est versée nette.

    Le solde des ``AvanceSalarie`` et ``SaisieArret`` actifs est retenu comme
    pour un bulletin normal (déjà couvert par ``calculer_bulletin``).

    ``motif`` est informatif (tracé sur le bulletin). Renvoie un dict de même
    forme que ``calculer_bulletin`` PLUS les clés
    ``{'indemnite_conges', 'indemnite_preavis', 'indemnite_licenciement',
    'indemnite_licenciement_exoneree', 'indemnite_licenciement_imposable',
    'anciennete_annees'}``. Donnée SENSIBLE (salaires) — usage interne paie.
    """
    le_jour = date(periode.annee, periode.mois, 1)
    parametre = parametre_en_vigueur(profil.company, le_jour)
    bareme = bareme_en_vigueur(profil.company, le_jour)

    from apps.rh import selectors as rh_selectors  # import paresseux cross-app

    date_embauche = rh_selectors.date_embauche_employe(
        profil.company, profil.employe_id)
    date_sortie, motif_sortie = rh_selectors.sortie_employe(
        profil.company, profil.employe_id)
    jour_reference = date_sortie or le_jour
    anciennete_annees = calculer_anciennete_annees(date_embauche, jour_reference)

    # Base du calcul normal (salaire proraté, éléments variables, retenues
    # d'avances/saisies déjà gérées par calculer_bulletin).
    base = calculer_bulletin(profil, periode, personnes_a_charge)

    taux_j = taux_journalier_profil(profil)
    indemnite_conges = indemnite_compensatrice_conges(
        profil.company, profil.employe_id, periode.annee, taux_j)

    salaire_mensuel = Decimal(profil.salaire_base or 0)
    indemnite_pre = (
        indemnite_preavis(salaire_mensuel, mois_preavis)
        if mois_preavis and Decimal(mois_preavis) > 0 else Decimal('0.00')
    )

    taux_h = taux_horaire_base_profil(profil)
    indemnite_licenciement = indemnite_licenciement_art53(
        anciennete_annees, taux_h)
    exoneree, imposable = exoneration_ir_indemnite_licenciement(
        indemnite_licenciement, parametre)

    # Les indemnités s'ajoutent au NET (versées au salarié) ; seule la part
    # IMPOSABLE de l'indemnité de licenciement rejoint la base IR — recalcul
    # de l'IR sur le net imposable augmenté de cette fraction.
    net_imposable_stc = _q(base['net_imposable'] + imposable)
    ir_stc = Decimal('0')
    if bareme and parametre:
        ir_stc = compute_ir(net_imposable_stc, bareme, parametre,
                            personnes_a_charge)
    ir_stc = _q(ir_stc)
    delta_ir = _q(ir_stc - base['ir'])

    indemnites_nettes = _q(indemnite_conges + indemnite_pre + exoneree + imposable)
    net_a_payer_stc = _q(base['net_a_payer'] + indemnites_nettes - delta_ir)

    lignes = list(base['lignes'])
    if indemnite_conges > 0:
        lignes.append({
            'code': 'STC_CONGES',
            'libelle': 'Indemnité compensatrice de congés payés',
            'type': Rubrique.TYPE_GAIN, 'montant': indemnite_conges,
        })
    if indemnite_pre > 0:
        lignes.append({
            'code': 'STC_PREAVIS',
            'libelle': 'Indemnité de préavis',
            'type': Rubrique.TYPE_GAIN, 'montant': indemnite_pre,
        })
    if indemnite_licenciement > 0:
        lignes.append({
            'code': 'STC_LICENCIEMENT',
            'libelle': 'Indemnité légale de licenciement (art. 53)',
            'type': Rubrique.TYPE_GAIN, 'montant': indemnite_licenciement,
        })
    if delta_ir != 0:
        lignes.append({
            'code': 'STC_IR_INDEMNITE',
            'libelle': "IR sur part imposable de l'indemnité de licenciement",
            'type': Rubrique.TYPE_RETENUE, 'montant': delta_ir,
        })

    resultat = dict(base)
    resultat.update({
        'ir': ir_stc,
        'net_imposable': net_imposable_stc,
        'net_a_payer': net_a_payer_stc,
        'lignes': lignes,
        'indemnite_conges': indemnite_conges,
        'indemnite_preavis': indemnite_pre,
        'indemnite_licenciement': indemnite_licenciement,
        'indemnite_licenciement_exoneree': exoneree,
        'indemnite_licenciement_imposable': imposable,
        'anciennete_annees': anciennete_annees,
        'motif': motif or motif_sortie or '',
    })
    return resultat


def generer_bulletin_stc(profil, periode, *, motif='', mois_preavis=1,
                         personnes_a_charge=0):
    """Matérialise le bulletin STC d'un profil sortant (XPAI1).

    Calcule via ``calculer_stc`` puis persiste un ``BulletinPaie`` de nature
    ``TYPE_STC`` (même garde d'immuabilité que les autres bulletins — figé une
    fois validé). Opération atomique. Renvoie le ``BulletinPaie`` STC
    (brouillon).
    """
    from .models import BulletinPaie, LigneBulletin

    if profil.company_id != periode.company_id:
        raise ValueError("Profil et période de sociétés différentes.")
    if periode.statut == PeriodePaie.STATUT_CLOTUREE:
        raise BulletinPaie.BulletinVerrouille(
            'Période clôturée : génération de bulletin STC interdite.')

    resultat = calculer_stc(
        profil, periode, motif=motif, mois_preavis=mois_preavis,
        personnes_a_charge=personnes_a_charge)
    lignes = resultat.get('lignes', [])

    with transaction.atomic():
        bulletin = (
            BulletinPaie.objects
            .select_for_update()
            .filter(periode=periode, profil=profil)
            .first()
        )
        if bulletin is not None and bulletin.est_valide:
            raise BulletinPaie.BulletinVerrouille(
                'Bulletin déjà validé pour cette période : STC impossible.')
        if bulletin is None:
            bulletin = BulletinPaie(
                company=periode.company, periode=periode, profil=profil)

        bulletin.type_bulletin = BulletinPaie.TYPE_STC
        bulletin.motif = resultat.get('motif', '') or motif
        bulletin.personnes_a_charge = max(0, int(personnes_a_charge or 0))
        for champ in BulletinPaie.SNAPSHOT_FIELDS:
            if champ == 'personnes_a_charge':
                continue
            if champ in resultat:
                setattr(bulletin, champ, resultat[champ])
        bulletin.statut = BulletinPaie.STATUT_BROUILLON
        bulletin.save()

        bulletin.lignes.all().delete()
        for ordre, ligne in enumerate(lignes, start=1):
            LigneBulletin.objects.create(
                company=periode.company,
                bulletin=bulletin,
                code=ligne.get('code', ''),
                libelle=ligne.get('libelle', ''),
                type=ligne.get('type', 'gain'),
                montant=ligne.get('montant', Decimal('0')),
                ordre=ordre,
            )
        return bulletin


# ── XPAI2 — Régularisation IR annuelle (12e bulletin / sortie) ─────────────

def calculer_regularisation_ir(bulletin):
    """Calcule la régularisation IR annuelle due sur un bulletin (XPAI2).

    L'IR est aujourd'hui retenu MOIS PAR MOIS, sans vérifier que le cumul
    annuel réel correspond à ce qui aurait dû être retenu (une variation de
    salaire en cours d'année — augmentation, prime exceptionnelle, régime
    CIMR modifié — peut faire diverger l'IR mensuel cumulé de l'IR dû sur le
    revenu annuel réel).

    DÉCISION (barème mensuel unique, pas de barème annuel séparé dans ce
    système) : la régularisation recalcule, pour CHAQUE bulletin VALIDÉ de
    l'année (hors celui-ci, qui n'est pas encore validé) PLUS ce bulletin,
    l'IR dû sur le net imposable de ce mois-là selon le barème/paramètre EN
    VIGUEUR à la date du bulletin de régularisation (barème le plus récent de
    l'année) — reproduisant la logique légale de la retenue à la source
    régularisée en fin d'année sur la base des mêmes règles. La différence
    entre cet IR théorique cumulé et l'IR RÉELLEMENT retenu cumulé (tel que
    déjà figé sur les bulletins validés + ce bulletin) est la régularisation :
    positive = rappel dû (retenue complémentaire) ; négative = trop-perçu
    (remboursement).

    Lecture seule (aucun effet de bord). Renvoie
    ``{'ir_du_annuel', 'ir_retenu_annuel', 'delta', 'nombre_bulletins'}`` —
    tous ``Decimal`` sauf le compteur. ``delta > 0`` → rappel dû par le
    salarié (retenue complémentaire) ; ``delta < 0`` → trop-perçu à
    rembourser.
    """
    from .models import BulletinPaie

    profil = bulletin.profil
    annee = bulletin.periode.annee
    le_jour = date(bulletin.periode.annee, bulletin.periode.mois, 1)
    parametre = parametre_en_vigueur(profil.company, le_jour)
    bareme = bareme_en_vigueur(profil.company, le_jour)

    autres_bulletins = (
        BulletinPaie.objects
        .filter(company=profil.company, profil=profil,
                periode__annee=annee, statut=BulletinPaie.STATUT_VALIDE)
        .exclude(pk=bulletin.pk)
    )

    ir_du_annuel = Decimal('0')
    ir_retenu_annuel = Decimal('0')
    nombre = 0
    for b in list(autres_bulletins) + [bulletin]:
        nombre += 1
        ir_retenu_annuel += Decimal(b.ir or 0)
        if bareme and parametre:
            ir_du_mois = compute_ir(
                Decimal(b.net_imposable or 0), bareme, parametre,
                b.personnes_a_charge)
        else:
            ir_du_mois = Decimal(b.ir or 0)
        ir_du_annuel += _q(ir_du_mois)

    ir_du_annuel = _q(ir_du_annuel)
    ir_retenu_annuel = _q(ir_retenu_annuel)
    delta = _q(ir_du_annuel - ir_retenu_annuel)
    return {
        'ir_du_annuel': ir_du_annuel,
        'ir_retenu_annuel': ir_retenu_annuel,
        'delta': delta,
        'nombre_bulletins': nombre,
    }


def appliquer_regularisation_ir(bulletin):
    """Applique la régularisation IR annuelle sur un bulletin BROUILLON (XPAI2).

    Ajoute (ou remplace) une ligne ``IR-REGUL`` au bulletin : montant positif
    = retenue complémentaire (rappel), négatif = restitution (trop-perçu).
    Met à jour ``bulletin.ir`` et ``bulletin.net_a_payer`` en conséquence.
    N'agit QUE sur un bulletin en BROUILLON (la garde d'immuabilité du modèle
    empêche toute écriture sur un bulletin validé). No-op si le delta calculé
    est nul. Renvoie le ``delta`` appliqué (``Decimal``, peut être 0).
    """
    from .models import BulletinPaie, LigneBulletin

    if bulletin.statut == BulletinPaie.STATUT_VALIDE:
        raise BulletinPaie.BulletinVerrouille(
            'Bulletin validé : régularisation IR impossible (figé).')

    with transaction.atomic():
        # Idempotence : annuler l'effet d'une régularisation PRÉCÉDENTE sur
        # ``ir``/``net_a_payer`` AVANT de recalculer. Sinon un 2ᵉ appel voit un
        # IR déjà gonflé du 1er delta (l'IR retenu cumulé inclut ce bulletin) et
        # calcule un delta nul — la ligne IR-REGUL disparaîtrait. Supprimer la
        # seule ligne ne suffit pas : il faut aussi défaire son effet sur l'IR.
        prior = bulletin.lignes.filter(code='IR-REGUL').first()
        if prior is not None:
            prior_delta = (
                prior.montant if prior.type == Rubrique.TYPE_RETENUE
                else -prior.montant)
            bulletin.ir = _q(Decimal(bulletin.ir or 0) - prior_delta)
            bulletin.net_a_payer = _q(
                Decimal(bulletin.net_a_payer or 0) + prior_delta)
            bulletin.save(update_fields=['ir', 'net_a_payer'])
            prior.delete()

        resultat = calculer_regularisation_ir(bulletin)
        delta = resultat['delta']

        if delta != 0:
            ordre_max = (
                bulletin.lignes.order_by('-ordre').values_list(
                    'ordre', flat=True).first() or 0
            )
            LigneBulletin.objects.create(
                company=bulletin.company,
                bulletin=bulletin,
                code='IR-REGUL',
                libelle=(
                    "Régularisation IR annuelle (rappel)" if delta > 0
                    else "Régularisation IR annuelle (trop-perçu)"),
                type=(
                    Rubrique.TYPE_RETENUE if delta > 0
                    else Rubrique.TYPE_GAIN),
                montant=abs(delta),
                ordre=ordre_max + 1,
            )
            bulletin.ir = _q(Decimal(bulletin.ir or 0) + delta)
            bulletin.net_a_payer = _q(Decimal(bulletin.net_a_payer or 0) - delta)
            bulletin.save(update_fields=['ir', 'net_a_payer'])
    return delta


# ── XRH9 — thin wrapper cross-app pour le guichet de demandes RH ───────────
# ``apps.rh`` ne doit JAMAIS dupliquer de code PDF : il appelle CE wrapper
# (cross-app par services uniquement) qui réutilise le renderer PAIE34
# existant (``builders.render_attestation_pdf``).

def generer_attestation_pdf_pour_dossier(dossier_employe, attestation_type):
    """Génère le PDF d'attestation (PAIE34) pour un ``rh.DossierEmploye``.

    Résout le ``ProfilPaie`` lié au dossier (``OneToOne``) — lève
    ``ValueError`` si le dossier n'a pas encore de profil de paie. Pour
    l'attestation de salaire, s'appuie sur le dernier ``BulletinPaie`` VALIDÉ
    du profil (peut être ``None`` — le renderer affiche alors des tirets).
    Retourne les octets PDF. Propage ``ValueError``/``RuntimeError`` du
    renderer sous-jacent (type inconnu / moteur PDF indisponible).
    """
    from .builders import render_attestation_pdf
    from .models import BulletinPaie, ProfilPaie

    try:
        profil = ProfilPaie.objects.get(employe=dossier_employe)
    except ProfilPaie.DoesNotExist:
        raise ValueError(
            "Aucun profil de paie pour cet employé — "
            "impossible de générer l'attestation.")

    bulletin = None
    if attestation_type == 'salaire':
        bulletin = (
            BulletinPaie.objects
            .filter(company=dossier_employe.company, profil=profil,
                    statut=BulletinPaie.STATUT_VALIDE)
            .order_by('-periode__annee', '-periode__mois')
            .first())
    return render_attestation_pdf(
        attestation_type, profil, bulletin=bulletin)


# ── XPAI24 — Structures de paie par catégorie (modèles de rubriques) ───────

# Seed idempotent de 3 structures standard : (code, libelle, description,
# [codes de rubriques RUBRIQUES_STANDARD/RUBRIQUES_DEFAUT à rattacher]).
# « ouvrier » pré-affecte panier + transport (indemnités chantier usuelles).
STRUCTURES_STANDARD = [
    ('CADRE', 'Cadre', 'Structure standard pour le personnel cadre',
     ['ANCIENNETE']),
    ('EMPLOYE', 'Employé', 'Structure standard pour le personnel employé',
     ['ANCIENNETE', 'TRANSPORT']),
    ('OUVRIER', 'Ouvrier', 'Structure standard pour le personnel ouvrier',
     ['PANIER', 'TRANSPORT']),
]


def ensure_structures_standard(company):
    """Sème (idempotent, additif) les 3 structures de paie standard (XPAI24).

    Clé stable ``(company, code)`` : une structure déjà présente n'est jamais
    modifiée, et ses rubriques déjà rattachées non plus. Suppose les rubriques
    du catalogue standard déjà présentes (``ensure_rubriques_standard``) — une
    rubrique manquante est silencieusement sautée (pas d'erreur bloquante).
    Renvoie ``{'structures': N}`` (nombre de structures créées).
    """
    from .models import StructurePaie, StructurePaieRubrique

    cree = 0
    for code, libelle, description, codes_rubriques in STRUCTURES_STANDARD:
        structure, created = StructurePaie.objects.get_or_create(
            company=company, code=code,
            defaults={'libelle': libelle, 'description': description})
        if created:
            cree += 1
        for code_rub in codes_rubriques:
            rubrique = Rubrique.objects.filter(
                company=company, code=code_rub).first()
            if rubrique is None:
                continue
            StructurePaieRubrique.objects.get_or_create(
                structure=structure, rubrique=rubrique,
                defaults={'company': company})
    return {'structures': cree}


def appliquer_structure_a_profil(profil, structure):
    """Applique une ``StructurePaie`` à un ``ProfilPaie`` (XPAI24).

    Copie chaque ``StructurePaieRubrique`` de la structure en une
    ``RubriqueEmploye`` rattachée au profil (surcharge montant/taux reprise
    telle quelle). AUCUN lien vivant n'est conservé après coup : une
    ``RubriqueEmploye`` déjà rattachée pour cette rubrique (même profil) n'est
    jamais écrasée — reste modifiable librement ensuite, comme toute
    ``RubriqueEmploye`` normale. Idempotent (ne duplique jamais). Renvoie le
    nombre de rubriques rattachées.
    """
    from .models import RubriqueEmploye

    if structure is None:
        return 0
    if structure.company_id != profil.company_id:
        raise ValueError("Structure d'une autre société.")
    cree = 0
    with transaction.atomic():
        for ligne in structure.rubriques_defaut.select_related('rubrique').all():
            _, created = RubriqueEmploye.objects.get_or_create(
                profil=profil, rubrique=ligne.rubrique,
                defaults={
                    'company': profil.company,
                    'montant': ligne.montant,
                    'taux': ligne.taux,
                })
            if created:
                cree += 1
        profil.structure = structure
        profil.save(update_fields=['structure'])
    return cree


# ── XPAI17 — Ventilation analytique de la masse salariale + coût employé ───

def _bornes_periode(periode):
    """(date_debut, date_fin) civiles du mois d'une ``PeriodePaie``."""
    import calendar

    dernier_jour = calendar.monthrange(periode.annee, periode.mois)[1]
    return (date(periode.annee, periode.mois, 1),
            date(periode.annee, periode.mois, dernier_jour))


def cout_employeur_bulletin(bulletin):
    """Coût employeur total d'un bulletin (brut + patronales + provisions).

    Base de la ventilation analytique (XPAI17) : brut + charges patronales
    (CNSS/AMO/allocations/formation pro/mutuelle patronale) + provision congés.
    Renvoie un ``Decimal`` au centime.
    """
    total = (
        Decimal(bulletin.brut or 0)
        + Decimal(bulletin.charges_patronales or 0)
        + Decimal(bulletin.provision_conges or 0)
    )
    return _q(total)


def ventilation_analytique_bulletin(bulletin):
    """Ventile le coût employeur d'un bulletin sur l'axe analytique (XPAI17).

    Ordre de résolution :

    1. **Heures réelles** — si des heures ``rh.FeuilleTemps`` existent pour
       l'employé sur le mois du bulletin (lues via
       ``rh.selectors.labour_hours_par_installation_pour_employe``), le coût
       employeur est réparti AU PRORATA de ces heures entre les chantiers
       (un ``compta.CentreCout`` est résolu/créé par installation,
       ``compta.services.creer_centre_cout`` — jamais ``compta.models``
       direct).
    2. **Clé % fixe** — à défaut, les ``VentilationAnalytiquePaie`` actives du
       profil (centre_cout_id + pourcentage) sont appliquées. Un reliquat
       (100 % − Σ pourcentages) reste NON VENTILÉ (``centre_cout_id=None``).
    3. **Aucune clé** — tout le coût est NON VENTILÉ.

    Renvoie une liste de dicts ``{'centre_cout_id': int|None, 'montant':
    Decimal}`` dont la somme des montants == ``cout_employeur_bulletin``
    (au centime près, l'arrondi est absorbé sur la dernière ligne).
    """
    from apps.rh import selectors as rh_selectors  # cross-app, lecture seule

    from .models import VentilationAnalytiquePaie

    total = cout_employeur_bulletin(bulletin)
    if total <= 0:
        return []

    profil = bulletin.profil
    date_debut, date_fin = _bornes_periode(bulletin.periode)
    heures_par_installation = rh_selectors.labour_hours_par_installation_pour_employe(
        profil.company, profil.employe_id, date_debut, date_fin)

    if heures_par_installation:
        from apps.compta import services as compta_services  # cross-app WRITE

        total_heures = sum(
            (Decimal(h['total_heures']) for h in heures_par_installation),
            Decimal('0'))
        lignes = []
        cumul = Decimal('0')
        for i, entree in enumerate(heures_par_installation):
            centre = compta_services.creer_centre_cout(
                profil.company,
                code=f"CHANTIER-{entree['installation_id']}",
                libelle=f"Chantier #{entree['installation_id']}",
                axe='chantier')
            if i == len(heures_par_installation) - 1:
                montant = _q(total - cumul)
            else:
                part = Decimal(entree['total_heures']) / total_heures
                montant = _q(total * part)
                cumul += montant
            lignes.append({'centre_cout_id': centre.id, 'montant': montant})
        return lignes

    cles = list(
        VentilationAnalytiquePaie.objects
        .filter(company=profil.company, profil=profil, actif=True)
        .order_by('id'))
    if not cles:
        return [{'centre_cout_id': None, 'montant': total}]

    lignes = []
    cumul_pct = Decimal('0')
    cumul_montant = Decimal('0')
    for cle in cles:
        pct = Decimal(cle.pourcentage or 0)
        montant = _q(total * pct / Decimal('100'))
        lignes.append({'centre_cout_id': cle.centre_cout_id, 'montant': montant})
        cumul_pct += pct
        cumul_montant += montant
    if cumul_pct < Decimal('100'):
        reliquat = _q(total - cumul_montant)
        if reliquat > 0:
            lignes.append({'centre_cout_id': None, 'montant': reliquat})
    return lignes


def cout_global_par_profil(periode):
    """Coût global employeur PAR EMPLOYÉ de la période (XPAI17), interne.

    JAMAIS client-facing. Agrège, pour chaque bulletin VALIDÉ de la
    ``periode``, le coût employeur total et sa ventilation analytique.
    Renvoie une liste de dicts ``{'profil_id', 'matricule', 'nom',
    'cout_global', 'ventilation': [...]}``.
    """
    from .models import BulletinPaie

    bulletins = (
        BulletinPaie.objects
        .filter(company=periode.company, periode=periode,
                statut=BulletinPaie.STATUT_VALIDE)
        .select_related('profil', 'profil__employe')
    )
    resultat = []
    for bulletin in bulletins:
        employe = bulletin.profil.employe
        resultat.append({
            'profil_id': bulletin.profil_id,
            'matricule': getattr(employe, 'matricule', '') if employe else '',
            'nom': f'{employe.nom} {employe.prenom}'.strip() if employe else '',
            'cout_global': cout_employeur_bulletin(bulletin),
            'ventilation': ventilation_analytique_bulletin(bulletin),
        })
    return resultat


# ── ZPAI3 — Rapport « Coût employeur » consolidé de la période ─────────────

# Codes des lignes patronales ITEMISÉES (informative, ``calculer_bulletin``)
# que le flag ``Rubrique.apparait_cout_employeur`` peut exclure du total —
# CNSS/AMO patronales n'ont pas de ligne dédiée (agrégées uniquement dans
# ``charges_patronales``) et restent donc toujours incluses.
_CODES_PATRONALES_ITEMISEES = ('MUTUELLE_PAT', 'ALLOC_FAM', 'FORMATION_PRO')


def cout_employeur(periode):
    """Rapport « coût employeur » CONSOLIDÉ de la période (ZPAI3), interne.

    Distinct de ``cout_global_par_profil`` (XPAI17, coût + ventilation PAR
    EMPLOYÉ) : ici un TOTAL société lisible en un écran — brut + toutes les
    cotisations patronales + provisions de la période, le ratio coût/net, et
    le coût moyen par tête. Une rubrique de cotisation patronale ITEMISÉE
    (``_CODES_PATRONALES_ITEMISEES``) dont ``apparait_cout_employeur=False``
    est RETRANCHÉE du total (jamais du bulletin lui-même — JAMAIS
    client-facing, gaté ``paie_voir``).

    Renvoie ``{'annee', 'mois', 'nombre_salaries', 'total_brut',
    'total_charges_patronales', 'total_provisions', 'total_employeur',
    'total_net', 'ratio_cout_net', 'cout_moyen_par_tete',
    'rubriques_exclues': [code, ...]}``.
    """
    from django.db.models import Sum

    from .models import BulletinPaie, LigneBulletin

    bulletins = list(
        BulletinPaie.objects.filter(
            company=periode.company, periode=periode,
            statut=BulletinPaie.STATUT_VALIDE))
    nombre_salaries = len(bulletins)
    if nombre_salaries == 0:
        return {
            'annee': periode.annee, 'mois': periode.mois,
            'nombre_salaries': 0,
            'total_brut': Decimal('0.00'),
            'total_charges_patronales': Decimal('0.00'),
            'total_provisions': Decimal('0.00'),
            'total_employeur': Decimal('0.00'),
            'total_net': Decimal('0.00'),
            'ratio_cout_net': None,
            'cout_moyen_par_tete': Decimal('0.00'),
            'rubriques_exclues': [],
        }

    total_brut = sum(
        (Decimal(b.brut or 0) for b in bulletins), Decimal('0'))
    total_charges_patronales = sum(
        (Decimal(b.charges_patronales or 0) for b in bulletins), Decimal('0'))
    total_provisions = sum(
        (Decimal(b.provision_conges or 0) for b in bulletins), Decimal('0'))
    total_net = sum(
        (Decimal(b.net_a_payer or 0) for b in bulletins), Decimal('0'))

    # Rubriques patronales itemisées dé-flaggées : leur montant total (somme
    # des LigneBulletin de ce code) sort de l'agrégat.
    rubriques_exclues = list(
        Rubrique.objects.filter(
            company=periode.company, code__in=_CODES_PATRONALES_ITEMISEES,
            apparait_cout_employeur=False,
        ).values_list('code', flat=True))
    montant_exclu = Decimal('0.00')
    if rubriques_exclues:
        montant_exclu = LigneBulletin.objects.filter(
            company=periode.company, bulletin__in=bulletins,
            code__in=rubriques_exclues,
        ).aggregate(total=Sum('montant'))['total'] or Decimal('0.00')

    total_employeur = _q(
        total_brut + total_charges_patronales + total_provisions
        - montant_exclu)

    return {
        'annee': periode.annee, 'mois': periode.mois,
        'nombre_salaries': nombre_salaries,
        'total_brut': _q(total_brut),
        'total_charges_patronales': _q(total_charges_patronales),
        'total_provisions': _q(total_provisions),
        'total_employeur': total_employeur,
        'total_net': _q(total_net),
        # Non arrondis : un ratio/moyenne est une grandeur d'analyse (ZPAI3),
        # pas un montant monétaire — l'arrondir au centime perdrait la
        # précision attendue par les appelants (cf. test_ratio_et_moyenne_par_tete
        # qui recompare à la division brute).
        'ratio_cout_net': (
            total_employeur / total_net if total_net > 0 else None),
        'cout_moyen_par_tete': total_employeur / nombre_salaries,
        'rubriques_exclues': rubriques_exclues,
    }


def journal_de_paie_ventile(periode, *, created_by=None):
    """Écriture du journal de paie AVEC ventilation analytique (XPAI17).

    Même schéma comptable que ``journal_de_paie`` (PAIE33), mais les lignes de
    débit RÉMUNÉRATION/CHARGES SOCIALES sont ÉCLATÉES par ``centre_cout``
    (proportionnellement au coût employeur ventilé de chaque bulletin, cf.
    ``ventilation_analytique_bulletin``) au lieu d'une ligne agrégée unique.
    Le reste de l'écriture (CNSS/IR/CIMR/net à payer) est inchangé. Renvoie
    l'écriture créée, ou ``None`` s'il n'y a aucun bulletin validé.
    """
    from apps.compta import services as compta_services  # cross-app via services

    from .models import BulletinPaie

    bulletins = list(
        BulletinPaie.objects
        .filter(company=periode.company, periode=periode,
                statut=BulletinPaie.STATUT_VALIDE)
        .select_related('profil'))
    if not bulletins:
        return None

    company = periode.company
    requis = [
        _COMPTE_REMUNERATION, _COMPTE_CHARGES_SOCIALES, _COMPTE_CNSS,
        _COMPTE_IR, _COMPTE_CIMR, _COMPTE_NET,
    ]
    if any(compta_services.get_compte(company, num) is None for num in requis):
        compta_services.seed_plan_comptable(company)

    def compte(numero):
        return compta_services.get_compte(company, numero)

    # Ventile le coût employeur (rémunération + charges patronales) par
    # centre de coût, agrégé sur TOUS les bulletins de la période.
    ventilation_par_centre = {}
    for bulletin in bulletins:
        for ligne in ventilation_analytique_bulletin(bulletin):
            cle = ligne['centre_cout_id']
            ventilation_par_centre[cle] = (
                ventilation_par_centre.get(cle, Decimal('0')) + ligne['montant'])

    registre = livre_de_paie(periode)
    totaux = registre['totaux']
    cnss_amo = (
        totaux['cnss_salariale'] + totaux['cnss_patronale']
        + totaux['amo_salariale'] + totaux['amo_patronale']
    )
    ir = totaux['ir']
    cimr = totaux['cimr_salariale']

    lignes = []
    for centre_id, montant in sorted(
            ventilation_par_centre.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)):
        libelle = ('Rémunération + charges patronales'
                   + (f' — centre #{centre_id}' if centre_id else ' — non ventilé'))
        # ``LigneEcriture.centre_cout`` est une FK : ``creer_ecriture`` assigne
        # ``ligne['centre_cout']`` tel quel, il faut donc une INSTANCE
        # ``CentreCout`` (jamais l'id brut) — résolue en lecture seule via
        # ``compta_services.get_centre_cout``.
        lignes.append({
            'compte': compte(_COMPTE_REMUNERATION),
            'libelle': libelle, 'debit': montant, 'credit': 0,
            'centre_cout': compta_services.get_centre_cout(company, centre_id),
        })
    if cnss_amo > 0:
        lignes.append({
            'compte': compte(_COMPTE_CNSS),
            'libelle': 'CNSS / AMO à payer', 'debit': 0, 'credit': cnss_amo})
    if ir > 0:
        lignes.append({
            'compte': compte(_COMPTE_IR),
            'libelle': 'IR retenu à la source', 'debit': 0, 'credit': ir})
    if cimr > 0:
        lignes.append({
            'compte': compte(_COMPTE_CIMR),
            'libelle': 'CIMR à payer', 'debit': 0, 'credit': cimr})

    total_debit = sum((Decimal(lig['debit']) for lig in lignes), Decimal('0'))
    total_credit_hors_net = sum(
        (Decimal(lig['credit']) for lig in lignes), Decimal('0'))
    net_equilibrant = _q(total_debit - total_credit_hors_net)
    lignes.append({
        'compte': compte(_COMPTE_NET),
        'libelle': 'Rémunérations dues au personnel (net)',
        'debit': 0, 'credit': net_equilibrant})

    date_ecriture = date(periode.annee, periode.mois, 28)
    libelle = f'Journal de paie ventilé {periode.mois:02d}/{periode.annee}'
    reference = f'PAIE-VENTILE-{periode.annee}-{periode.mois:02d}'
    return compta_services.creer_ecriture_od(
        company, date_ecriture, libelle, lignes,
        reference=reference, created_by=created_by)


# ── XPAI20 — Provisions gratifications (13e mois) & IFC ────────────────────

_COMPTE_PROVISION_CHARGES_PERSONNEL = '4506'
_COMPTE_DOTATION_PROVISION_PERSONNEL = '6195'


def provision_gratification_mensuelle(profil, periode):
    """Provision mensuelle du 13e mois / prime de bilan d'un profil (XPAI20).

    1/12ᵉ du salaire de base mensuel de référence du profil, constitué chaque
    mois de présence (aucune proration jour — cohérent avec le calcul du run
    13e mois lui-même, XPAI4, qui proratise déjà sur la présence de l'année).
    Renvoie un ``Decimal`` au centime, 0 si le profil n'est pas actif.
    """
    if not profil.actif:
        return Decimal('0.00')
    salaire = taux_journalier_profil(profil) * Decimal(
        max(1, profil.jours_travail_mensuel or 26))
    return _q(salaire / Decimal('12'))


def provision_ifc_mensuelle(profil, periode):
    """Provision mensuelle de l'indemnité de fin de carrière (IFC, XPAI20).

    Valorise l'indemnité légale de licenciement (barème art. 53,
    ``indemnite_licenciement_art53``) à l'ancienneté du salarié À LA FIN du
    mois de la ``periode``, puis lisse le montant total sur 12 mois — la
    provision mensuelle est le 1/12ᵉ de l'indemnité totale actuelle (une
    approximation prudente et stable, cohérente d'un mois à l'autre tant que
    l'ancienneté ne franchit pas un seuil de tranche). Renvoie un ``Decimal``
    au centime, 0 si le profil n'est pas actif ou sans date d'embauche connue.
    """
    from apps.rh import selectors as rh_selectors  # cross-app, lecture seule

    if not profil.actif:
        return Decimal('0.00')
    date_embauche = rh_selectors.date_embauche_employe(
        profil.company, profil.employe_id)
    if date_embauche is None:
        return Decimal('0.00')
    _, dernier_jour = _bornes_periode(periode)
    anciennete = calculer_anciennete_annees(date_embauche, dernier_jour)
    taux_h = taux_horaire_base_profil(profil)
    indemnite_totale = indemnite_licenciement_art53(anciennete, taux_h)
    if indemnite_totale <= 0:
        return Decimal('0.00')
    return _q(indemnite_totale / Decimal('12'))


def poster_provisions_mensuelles(periode, *, created_by=None):
    """Poste (clôture mensuelle) les provisions 13e mois + IFC de la période.

    Pour chaque profil ACTIF de la société, calcule
    ``provision_gratification_mensuelle`` + ``provision_ifc_mensuelle`` et
    matérialise une ligne ``ProvisionPaieMensuelle`` PAR TYPE (auditable, clé
    stable ``(company, profil, periode, type_provision)`` — idempotent : un
    profil déjà provisionné pour cette période/type n'est jamais recompté).
    Poste UNE écriture réversible équilibrée pour le TOTAL des deux types
    (débit 6195 dotation / crédit 4506 provision), via
    ``compta.services.creer_ecriture_od`` (jamais ``compta.models`` direct).
    Retourne ``{'lignes': [ProvisionPaieMensuelle...], 'ecriture': Ecriture|None}``.
    """
    from apps.compta import services as compta_services  # cross-app WRITE

    from .models import ProfilPaie, ProvisionPaieMensuelle

    company = periode.company
    profils = ProfilPaie.objects.filter(company=company, actif=True)

    lignes_creees = []
    total = Decimal('0')
    with transaction.atomic():
        for profil in profils:
            for type_provision, calculer in (
                (ProvisionPaieMensuelle.TYPE_GRATIFICATION,
                 provision_gratification_mensuelle),
                (ProvisionPaieMensuelle.TYPE_IFC, provision_ifc_mensuelle),
            ):
                existante = ProvisionPaieMensuelle.objects.filter(
                    company=company, profil=profil, periode=periode,
                    type_provision=type_provision).first()
                if existante is not None:
                    lignes_creees.append(existante)
                    total += Decimal(existante.montant or 0)
                    continue
                montant = calculer(profil, periode)
                ligne = ProvisionPaieMensuelle.objects.create(
                    company=company, profil=profil, periode=periode,
                    type_provision=type_provision, montant=montant)
                lignes_creees.append(ligne)
                total += montant

        ecriture = None
        nouveau_total = sum(
            (Decimal(lig.montant or 0) for lig in lignes_creees
             if lig.ecriture_id is None),
            Decimal('0'))
        if nouveau_total > 0:
            requis = [_COMPTE_PROVISION_CHARGES_PERSONNEL,
                      _COMPTE_DOTATION_PROVISION_PERSONNEL]
            if any(compta_services.get_compte(company, num) is None
                   for num in requis):
                compta_services.seed_plan_comptable(company)
            compte_dotation = compta_services.get_compte(
                company, _COMPTE_DOTATION_PROVISION_PERSONNEL)
            compte_provision = compta_services.get_compte(
                company, _COMPTE_PROVISION_CHARGES_PERSONNEL)
            date_ecriture = date(periode.annee, periode.mois, 28)
            libelle = (
                'Provisions 13e mois / IFC '
                f'{periode.mois:02d}/{periode.annee}')
            reference = f'PROV-PAIE-{periode.annee}-{periode.mois:02d}'
            ecriture = compta_services.creer_ecriture_od(
                company, date_ecriture, libelle,
                [
                    {'compte': compte_dotation, 'libelle': libelle,
                     'debit': nouveau_total, 'credit': 0},
                    {'compte': compte_provision, 'libelle': libelle,
                     'debit': 0, 'credit': nouveau_total},
                ],
                reference=reference, created_by=created_by)
            for ligne in lignes_creees:
                if ligne.ecriture_id is None and ligne.montant > 0:
                    ligne.ecriture_id = ecriture.id
                    ligne.save(update_fields=['ecriture_id'])

    return {'lignes': lignes_creees, 'ecriture': ecriture}


def extourner_provisions_gratification(profil, *, jusqua_periode=None,
                                       user=None):
    """Extourne les provisions 13e mois d'un profil au paiement (XPAI20).

    Appelé quand le run 13e mois (XPAI4, ``generer_run_gratification``) verse
    la gratification à un profil : reprend (extourne, via
    ``compta.services.extourner_ecriture`` — idempotent) TOUTES les écritures
    de provision ``TYPE_GRATIFICATION`` non encore extournées du profil
    (jusqu'à ``jusqua_periode`` incluse si fournie, sinon toutes). Marque
    chaque ``ProvisionPaieMensuelle`` concernée ``extournee=True``. Renvoie la
    liste des lignes extournées.
    """
    from django.apps import apps as django_apps
    from django.db.models import Q

    from apps.compta import services as compta_services  # cross-app WRITE

    from .models import ProvisionPaieMensuelle

    qs = ProvisionPaieMensuelle.objects.filter(
        company=profil.company, profil=profil,
        type_provision=ProvisionPaieMensuelle.TYPE_GRATIFICATION,
        extournee=False, ecriture_id__isnull=False,
    ).select_related('periode')
    if jusqua_periode is not None:
        qs = qs.filter(
            Q(periode__annee__lt=jusqua_periode.annee)
            | Q(periode__annee=jusqua_periode.annee,
                periode__mois__lte=jusqua_periode.mois)
        )

    EcritureComptable = django_apps.get_model('compta', 'EcritureComptable')
    extournees = []
    with transaction.atomic():
        for ligne in qs:
            ecriture = EcritureComptable.objects.filter(
                company=profil.company, id=ligne.ecriture_id).first()
            if ecriture is None:
                continue
            compta_services.extourner_ecriture(ecriture, user=user)
            ligne.extournee = True
            ligne.date_extourne = timezone.now()
            ligne.save(update_fields=['extournee', 'date_extourne'])
            extournees.append(ligne)
    return extournees


# ── XPAI22 — Reprise des cumuls annuels (go-live en cours d'année) ─────────

# Mapping en-tête (normalisé, sans accents/espaces) → champ ``CumulAnnuel``.
# Réutilise le patron ``apps.dataimport`` (parse CSV/XLSX + normalisation
# d'en-tête) sans dupliquer son code : la logique de résolution/écriture,
# spécifique aux cumuls de paie, reste ici (dataimport ne connaît pas
# ``CumulAnnuel``).
_CUMUL_IMPORT_FIELD_MAP = {
    'matricule': 'matricule',
    'annee': 'annee',
    'brut': 'brut',
    'brut_imposable': 'brut_imposable',
    'net_imposable': 'net_imposable',
    'ir': 'ir',
    'cnss_salariale': 'cnss_salariale',
    'amo_salariale': 'amo_salariale',
    'cimr_salariale': 'cimr_salariale',
    'frais_professionnels': 'frais_professionnels',
    'net_a_payer': 'net_a_payer',
    'charges_patronales': 'charges_patronales',
    'provision_conges': 'provision_conges',
    'conges_acquis': 'conges_acquis',
    'conges_pris': 'conges_pris',
}

_CUMUL_IMPORT_CHAMPS_DECIMAL = [
    'brut', 'brut_imposable', 'net_imposable', 'ir', 'cnss_salariale',
    'amo_salariale', 'cimr_salariale', 'frais_professionnels', 'net_a_payer',
    'charges_patronales', 'provision_conges', 'conges_acquis', 'conges_pris',
]


def _norm_entete_cumul(s):
    """Normalise un en-tête de colonne : minuscules, sans accents, `_` (XPAI22)."""
    import unicodedata

    s = (s or '').strip().lower()
    s = ''.join(c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn')
    return s.replace(' ', '_').replace('-', '_')


def _map_headers_cumuls(headers):
    mapped, unmapped = {}, []
    for h in headers:
        champ = _CUMUL_IMPORT_FIELD_MAP.get(_norm_entete_cumul(h))
        if champ:
            mapped[h] = champ
        else:
            unmapped.append(h)
    return mapped, unmapped


def _ligne_cumul_depuis_row(row, mapped):
    return {champ: row.get(col) for col, champ in mapped.items()
            if row.get(col) not in (None, '')}


def _resoudre_profil_matricule(company, matricule):
    from django.apps import apps as django_apps

    from .models import ProfilPaie

    if not matricule:
        return None
    DossierEmploye = django_apps.get_model('rh', 'DossierEmploye')
    dossier = DossierEmploye.objects.filter(
        company=company, matricule=str(matricule).strip()).first()
    if dossier is None:
        return None
    return ProfilPaie.objects.filter(company=company, employe=dossier).first()


def _matricule_connu(company, matricule):
    """Le matricule correspond-il à un ``rh.DossierEmploye`` de la société ?

    Utilisé par le DRY-RUN (XPAI22) : à ce stade on prévisualise seulement,
    l'absence d'un ``ProfilPaie`` (paie pas encore configurée pour ce salarié)
    ne doit PAS être signalée comme « matricule inconnu » — seul un matricule
    sans dossier RH du tout l'est. Le COMMIT, lui, a réellement besoin du
    ``ProfilPaie`` pour écrire le ``CumulAnnuel`` (cf. ``_resoudre_profil_matricule``).
    """
    from django.apps import apps as django_apps

    if not matricule:
        return False
    DossierEmploye = django_apps.get_model('rh', 'DossierEmploye')
    return DossierEmploye.objects.filter(
        company=company, matricule=str(matricule).strip()).exists()


def dry_run_reprise_cumuls(file_bytes, filename, company):
    """Aperçu de l'import de reprise des cumuls annuels (XPAI22).

    Réutilise ``apps.dataimport.services.parse_rows`` pour le CSV/XLSX. Pour
    chaque ligne, résout le matricule → ``ProfilPaie`` (via
    ``rh.DossierEmploye``, string-FK/get_model — jamais ``rh.models`` direct)
    et signale les matricules INCONNUS. Ne modifie rien. Renvoie ``{'colonnes',
    'mapping', 'non_mappees', 'total_lignes', 'matricules_inconnus':
    [...], 'apercu': [...] (10 premières lignes mappées)}``.
    """
    from apps.dataimport.services import ImportTooLarge, MAX_ROWS, parse_rows

    headers, rows = parse_rows(file_bytes, filename)
    if len(rows) > MAX_ROWS:
        raise ImportTooLarge(f'Trop de lignes : {len(rows)} (max {MAX_ROWS}).')
    mapped, unmapped = _map_headers_cumuls(headers)

    inconnus = []
    apercu = []
    for i, row in enumerate(rows, 1):
        f = _ligne_cumul_depuis_row(row, mapped)
        if i <= 10:
            apercu.append(f)
        matricule = f.get('matricule')
        if matricule and not _matricule_connu(company, matricule):
            inconnus.append({'ligne': i, 'matricule': matricule})

    return {
        'colonnes': headers,
        'mapping': mapped,
        'non_mappees': unmapped,
        'total_lignes': len(rows),
        'matricules_inconnus': inconnus,
        'apercu': apercu,
    }


def commit_reprise_cumuls(file_bytes, filename, company):
    """Commit de l'import de reprise des cumuls annuels (XPAI22).

    Pour chaque ligne résolue (matricule connu, année valide) : crée le
    ``CumulAnnuel`` s'il n'existe pas, ou le COMPLÈTE s'il existe déjà mais
    n'a ENCORE aucun bulletin calculé (``nombre_bulletins == 0`` — cumul vide
    ou lui-même issu d'un import antérieur). Un cumul déjà calculé depuis de
    VRAIS bulletins validés (``nombre_bulletins > 0``) n'est JAMAIS écrasé —
    la reprise ne rejoue jamais un mois déjà traité dans l'outil. Opération
    atomique par ligne (une erreur n'interrompt pas les suivantes). Renvoie
    ``{'crees': N, 'completes': N, 'ignores': [...]}``.
    """
    from apps.dataimport.services import ImportTooLarge, MAX_ROWS, parse_rows

    from .models import CumulAnnuel

    headers, rows = parse_rows(file_bytes, filename)
    if len(rows) > MAX_ROWS:
        raise ImportTooLarge(f'Trop de lignes : {len(rows)} (max {MAX_ROWS}).')
    mapped, _ = _map_headers_cumuls(headers)

    crees, completes = 0, 0
    ignores = []
    for i, row in enumerate(rows, 1):
        f = _ligne_cumul_depuis_row(row, mapped)
        matricule = f.get('matricule')
        try:
            annee = int(f.get('annee'))
        except (TypeError, ValueError):
            ignores.append({'ligne': i, 'raison': 'année manquante/invalide'})
            continue
        profil = _resoudre_profil_matricule(company, matricule)
        if profil is None:
            ignores.append(
                {'ligne': i, 'raison': f'matricule inconnu : {matricule}'})
            continue

        valeurs = {}
        for champ in _CUMUL_IMPORT_CHAMPS_DECIMAL:
            if champ in f:
                try:
                    brut = str(f[champ]).replace('\xa0', '').replace(
                        ' ', '').replace(',', '.')
                    valeurs[champ] = Decimal(brut)
                except Exception:
                    pass

        with transaction.atomic():
            cumul = (
                CumulAnnuel.objects
                .select_for_update()
                .filter(company=company, profil=profil, annee=annee)
                .first()
            )
            if cumul is not None and cumul.nombre_bulletins > 0:
                ignores.append({
                    'ligne': i,
                    'raison': ('cumul déjà calculé depuis des bulletins '
                               'validés — reprise ignorée'),
                })
                continue
            if cumul is None:
                CumulAnnuel.objects.create(
                    company=company, profil=profil, annee=annee, **valeurs)
                crees += 1
            else:
                for champ, valeur in valeurs.items():
                    setattr(cumul, champ, valeur)
                cumul.save(update_fields=list(valeurs.keys()) or None)
                completes += 1

    return {'crees': crees, 'completes': completes, 'ignores': ignores}


# ── XPAI26 — Registres d'inspection du travail ──────────────────────────────

def registre_conges(company, annee):
    """Registre des congés annuel, par employé (XPAI26).

    Lecture seule : pour chaque ``ProfilPaie`` actif de la société, lit le
    solde RH de l'année (``rh.SoldeConge``, via ``get_model`` — jamais
    ``rh.models`` direct) : droits (report + acquis), pris, solde disponible.
    Format conforme inspection du travail. Renvoie ``{'annee', 'lignes': [...]
    ({'matricule', 'nom', 'droits', 'pris', 'solde'})}``.
    """
    from django.apps import apps as django_apps

    from .models import ProfilPaie

    SoldeConge = django_apps.get_model('rh', 'SoldeConge')
    profils = (
        ProfilPaie.objects
        .filter(company=company, actif=True)
        .select_related('employe')
    )
    soldes = {
        s.employe_id: s for s in
        SoldeConge.objects.filter(company=company, annee=annee)
    }

    lignes = []
    for profil in profils:
        employe = profil.employe
        if employe is None:
            continue
        solde = soldes.get(employe.id)
        droits = Decimal('0')
        pris = Decimal('0')
        if solde is not None:
            droits = Decimal(solde.report or 0) + Decimal(solde.acquis or 0)
            pris = Decimal(solde.pris or 0)
        lignes.append({
            'matricule': employe.matricule,
            'nom': f'{employe.nom} {employe.prenom}'.strip(),
            'droits': _q(droits),
            'pris': _q(pris),
            'solde': _q(droits - pris),
        })
    return {'annee': annee, 'lignes': lignes}


def historique_carriere(profil):
    """Fiche historique de carrière/salaire d'un profil (XPAI26).

    Lecture seule, AUCUNE écriture : identité + poste actuel (lu via
    ``rh.selectors.fiche_identite_employe`` — jamais ``rh.models`` direct) et
    la progression salariale ANNUELLE (``CumulAnnuel.brut`` par année,
    rémunérations réellement DATÉES — jamais une saisie manuelle). Format
    conforme inspection du travail. Renvoie ``{'matricule', 'nom', 'prenom',
    'poste', 'type_contrat', 'date_embauche', 'annees': [...]
    ({'annee', 'brut'})}``.
    """
    from apps.rh import selectors as rh_selectors  # cross-app, lecture seule

    from .models import CumulAnnuel

    identite = rh_selectors.fiche_identite_employe(
        profil.company, profil.employe_id) or {
            'matricule': '', 'nom': '', 'prenom': '', 'poste': '',
            'type_contrat': '', 'date_embauche': None,
        }
    cumuls = (
        CumulAnnuel.objects
        .filter(company=profil.company, profil=profil)
        .order_by('annee')
    )
    annees = [
        {'annee': cumul.annee, 'brut': _q(cumul.brut)}
        for cumul in cumuls
    ]
    return {
        'matricule': identite['matricule'],
        'nom': identite['nom'],
        'prenom': identite['prenom'],
        'poste': identite['poste'],
        'type_contrat': identite['type_contrat'],
        'date_embauche': identite['date_embauche'],
        'annees': annees,
    }
