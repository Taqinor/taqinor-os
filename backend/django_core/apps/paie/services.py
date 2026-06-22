"""Services de la Paie marocaine — valeurs légales par défaut (PAIE3).

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

DÉCISION (consentement permanent du fondateur) : les chiffres ci-dessous sont
les valeurs couramment citées du cadre social marocain 2026. Ils servent de
DÉFAUTS éditables — ``valide_par_fondateur=False`` matérialise qu'ils restent
à confirmer.
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
