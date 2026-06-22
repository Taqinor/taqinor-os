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
from decimal import Decimal

from .models import BaremeIR, ParametrePaie, TrancheIR

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
