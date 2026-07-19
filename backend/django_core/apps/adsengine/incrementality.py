"""PUB38 — Harnais MINIMAL d'incrémentalité geo-holdout (style GeoLift).

**Le problème.** Zéro couche causale aujourd'hui dans le moteur : rien ne
prouve que les signatures ATTRIBUÉES à une pub sont INCRÉMENTALES (ne se
seraient pas produites de toute façon, organiquement). Le bandit optimise sur
un proxy CRM qui peut sur-attribuer des ventes qui auraient eu lieu sans pub.

**Le design (minimal, volontairement).** Un test géo-holdout classique : on
choisit une ZONE TENUE (``held_villes`` — des villes où la pub est mise en
pause manuellement, DÉCISION HUMAINE prise AILLEURS, ce module ne pause
JAMAIS rien) et on compare, sur deux fenêtres (BASELINE avant / TEST pendant
le holdout), l'évolution des leads/signatures de la zone tenue à celle de la
ZONE ACTIVE (le reste des villes connues de la société). Si la zone active
progresse nettement plus que la zone tenue, c'est un signe d'incrémentalité
réelle ; si les deux zones bougent pareil, la pub n'ajoute peut-être pas
grand-chose au-delà de l'organique.

**Données RÉELLES ERP, aucune dépendance externe.** Les leads/signatures par
ville viennent d'``apps.crm.selectors.reporting_lead_rows`` (point d'entrée
cross-app SANCTIONNÉ — jamais un import de ``apps.crm.models`` ni
``apps.ventes.models`` ici), qui porte déjà la date de SIGNATURE réelle (plus
ancienne ``date_acceptation`` d'un devis ACCEPTÉ, lu via la relation
``lead.devis`` du domaine crm — même patron qu'``attribution_leads``) ainsi
que la ville brute du lead (PUB38 : champ ajouté à ce sélecteur). Aucun R,
aucun scipy/numpy, aucun package d'inférence causale — ce module est PUR
Python stdlib.

**Honnêteté statistique.** Sur du volume SMB (quelques dizaines de
leads/signatures par ville et par fenêtre), un intervalle de confiance
« sérieux » serait un mensonge de précision. ``_wide_interval`` calcule une
fourchette DÉLIBÉRÉMENT LARGE (approximation normale du bruit d'échantillon
Poisson, écart-type ≈ √n) — ce n'est PAS un test statistique formel, c'est un
garde-fou de lecture qui rappelle que ces chiffres sont une TENDANCE, jamais
une preuve. ``confiance`` dans le rapport reflète cette prudence.

**AUCUNE action automatique.** Ce module ne fait QUE lire des données déjà
synchronisées/saisies dans l'ERP et calculer un rapport. Il ne pause, ne
relance, ne modifie AUCUNE campagne — la décision de lancer/étendre/arrêter
un holdout géographique reste 100 % humaine (le fondateur décide où couper la
pub manuellement dans Meta Ads Manager ou via les composeurs d'action
existants du moteur ; ce harnais ne fait que MESURER ensuite).
"""
from __future__ import annotations

import datetime
import math

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import _user_has_or_legacy

# Fenêtre de recul (jours) appliquée EN AMONT de la période baseline pour lire
# les leads : ``reporting_lead_rows`` filtre sur la date de CRÉATION du lead,
# donc un lead créé AVANT la fenêtre mais dont la SIGNATURE tombe DEDANS
# resterait invisible sans ce recul (tickets 40k-200k MAD → cycle de vente
# pouvant dépasser plusieurs mois, CLAUDE.md). Compromis documenté d'un
# harnais MINIMAL, pas une lecture parfaite du cycle complet.
LOOKBACK_DAYS = 180

# Sous ce nombre de signatures (dans N'IMPORTE quelle case baseline/test ×
# zone), le rapport qualifie sa confiance de 'faible' plutôt que 'moyenne' —
# jamais 'forte' (ce harnais minimal ne prétend jamais à une preuve causale
# formelle, quel que soit le volume).
MIN_ROBUST_SIGNATURES = 10

# Multiplicateur de la fourchette large (≈ z 90 % d'une approximation normale
# du bruit Poisson) — volontairement généreux, pas un intervalle formel.
_WIDE_Z = 1.645


def _normalize_ville(value):
    return (value or '').strip().lower()


def _fetch_rows(company, *, lookback_start, end):
    """Lit ``apps.crm.selectors.reporting_lead_rows`` UNE FOIS sur une fenêtre
    assez large (``lookback_start`` → ``end``) pour couvrir à la fois la
    création ET la signature des leads pertinents. Cross-app SANCTIONNÉ,
    jamais un import de ``apps.crm.models``."""
    from apps.crm.selectors import reporting_lead_rows

    return reporting_lead_rows(company, date_start=lookback_start, date_end=end)


def _bucket_counts(rows, held_set, *, date_start, date_end):
    """Une passe sur les lignes déjà lues : compte les leads CRÉÉS dans
    ``[date_start, date_end]`` et les signatures dont la DATE DE SIGNATURE
    tombe dans ``[date_start, date_end]`` (indépendamment de la date de
    création du lead — un lead créé avant la fenêtre peut signer dedans),
    séparément pour la zone TENUE (``held_set``, villes normalisées) et la
    zone ACTIVE (toute autre ville CONNUE). Une ville vide/inconnue n'est
    comptée dans AUCUNE des deux zones (jamais devinée)."""
    held = {'leads': 0, 'signatures': 0}
    active = {'leads': 0, 'signatures': 0}
    for row in rows:
        ville = _normalize_ville(row.get('ville'))
        if not ville:
            continue
        bucket = held if ville in held_set else active
        created = row.get('created_date')
        if created is not None and date_start <= created <= date_end:
            bucket['leads'] += 1
        signed = row.get('signature_date')
        if signed is not None and date_start <= signed <= date_end:
            bucket['signatures'] += 1
    return held, active


def _rate_change(before, after):
    """Variation relative ``(after - before) / before``, ou ``None`` si
    ``before`` est nul (jamais un delta fabriqué depuis un dénominateur nul —
    même doctrine « jamais un skip muet, jamais un chiffre inventé » que
    ``anomaly.py``)."""
    if not before:
        return None
    return (after - before) / before


def _wide_interval(n, *, z=_WIDE_Z):
    """Fourchette large et VOLONTAIREMENT prudente autour d'un compte ``n``
    (approximation normale du bruit d'échantillonnage Poisson, écart-type
    ≈ √n). PAS un intervalle de confiance formel — aucune dépendance
    externe (R/scipy/numpy), aucune prétention à un test causal rigoureux.
    Toujours ``(low, high)`` avec ``low >= 0``."""
    if n <= 0:
        return (0, 0)
    spread = z * math.sqrt(n)
    return (max(0, round(n - spread)), round(n + spread))


def _confidence_label(*counts):
    """'faible' si UNE SEULE case (baseline/test × zone) compte moins de
    ``MIN_ROBUST_SIGNATURES`` signatures, sinon 'moyenne' — ce harnais minimal
    ne revendique JAMAIS une confiance 'forte' (pas de test causal formel)."""
    if any(c < MIN_ROBUST_SIGNATURES for c in counts):
        return 'faible'
    return 'moyenne'


def _render_message_fr(*, held_villes, baseline_held, test_held,
                       baseline_active, test_active, delta_held,
                       delta_active, confiance):
    """Rapport FR lisible fondateur — jamais un jargon statistique brut."""
    villes_txt = ', '.join(sorted(held_villes)) or '(aucune)'
    lines = [
        f"Zone tenue ({villes_txt}) : {baseline_held['signatures']} "
        f"signature(s) en référence → {test_held['signatures']} en test "
        f"({baseline_held['leads']} → {test_held['leads']} lead(s)).",
        f"Zone active (reste des villes connues) : "
        f"{baseline_active['signatures']} signature(s) en référence → "
        f"{test_active['signatures']} en test "
        f"({baseline_active['leads']} → {test_active['leads']} lead(s)).",
    ]
    if delta_held is None or delta_active is None:
        lines.append(
            'Delta non calculable (zéro signature en période de référence '
            'dans au moins une zone) — relancer avec une fenêtre plus '
            'longue ou une zone tenue plus large avant de conclure quoi que '
            'ce soit.')
    else:
        lift_pts = round((delta_active - delta_held) * 100)
        if lift_pts > 0:
            verdict = (
                f"la zone active a progressé environ {lift_pts} points de % "
                'de plus que la zone tenue — signe (PRUDENT) que la pub '
                'ajoute des signatures qui ne se seraient pas produites '
                'organiquement.')
        elif lift_pts < 0:
            verdict = (
                f"la zone tenue a progressé environ {abs(lift_pts)} points "
                'de % de plus que la zone active malgré la pub coupée — '
                'signe (PRUDENT) que une bonne part des signatures '
                "attribuées à la pub se seraient produites de toute façon.")
        else:
            verdict = (
                'les deux zones ont progressé au même rythme — aucun signal '
                "d'incrémentalité net sur cette fenêtre.")
        lines.append(
            f"Lecture : {verdict} Confiance {confiance} — sur ce volume, "
            'lire ce chiffre comme une TENDANCE, jamais une preuve formelle '
            '(pas de test statistique rigoureux, harnais minimal).')
    lines.append(
        'AUCUNE action automatique : ce rapport ne fait que MESURER — la '
        'décision de retenir, étendre ou arrêter le holdout reste 100 % '
        'humaine.')
    return ' '.join(lines)


def geo_holdout_report(company, *, held_villes, baseline_start, baseline_end,
                       test_start, test_end):
    """PUB38 — Rapport avant/après geo-holdout MINIMAL : zone TENUE
    (``held_villes``, sans pub) vs zone ACTIVE (le reste des villes connues),
    sur une fenêtre BASELINE (avant/référence) et une fenêtre TEST
    (pendant/après le holdout), sur données ERP RÉELLES (leads/signatures par
    ville via ``apps.crm.selectors.reporting_lead_rows``).

    Aucune écriture, aucune action automatique, aucune dépendance externe.
    Renvoie un dict JSON-natif (dates en ISO) prêt à sérialiser :

    ``{'valide', 'zone_tenue', 'periode_baseline', 'periode_test',
    'zone_tenue_baseline', 'zone_tenue_test', 'zone_active_baseline',
    'zone_active_test', 'delta_signatures_zone_tenue_pct',
    'delta_signatures_zone_active_pct',
    'fourchette_signatures_zone_tenue_test',
    'fourchette_signatures_zone_active_test', 'confiance', 'message_fr'}``

    ``held_villes`` vide/invalide, ou fenêtres qui se chevauchent/inversées →
    ``{'valide': False, 'erreur_fr': ...}`` (jamais un calcul silencieusement
    faux)."""
    held_set = {_normalize_ville(v) for v in (held_villes or [])
                if _normalize_ville(v)}
    if not held_set:
        return {
            'valide': False,
            'erreur_fr': (
                'Aucune ville valide dans la zone tenue — impossible de '
                'lancer le test géo.'),
        }
    for label, start, end in (
            ('référence', baseline_start, baseline_end),
            ('test', test_start, test_end)):
        if start is None or end is None or start > end:
            return {
                'valide': False,
                'erreur_fr': (
                    f'Période {label} invalide (début postérieur à la fin, '
                    'ou date manquante).'),
            }
    if test_start <= baseline_end:
        return {
            'valide': False,
            'erreur_fr': (
                'La période test doit commencer APRÈS la fin de la période '
                'de référence (pas de chevauchement) — un test géo compare '
                'un avant et un après.'),
        }

    lookback_start = baseline_start - datetime.timedelta(days=LOOKBACK_DAYS)
    rows = _fetch_rows(company, lookback_start=lookback_start, end=test_end)

    baseline_held, baseline_active = _bucket_counts(
        rows, held_set, date_start=baseline_start, date_end=baseline_end)
    test_held, test_active = _bucket_counts(
        rows, held_set, date_start=test_start, date_end=test_end)

    delta_held = _rate_change(
        baseline_held['signatures'], test_held['signatures'])
    delta_active = _rate_change(
        baseline_active['signatures'], test_active['signatures'])
    confiance = _confidence_label(
        baseline_held['signatures'], test_held['signatures'],
        baseline_active['signatures'], test_active['signatures'])

    return {
        'valide': True,
        'zone_tenue': sorted(held_set),
        'periode_baseline': {
            'debut': baseline_start.isoformat(), 'fin': baseline_end.isoformat()},
        'periode_test': {
            'debut': test_start.isoformat(), 'fin': test_end.isoformat()},
        'zone_tenue_baseline': baseline_held,
        'zone_tenue_test': test_held,
        'zone_active_baseline': baseline_active,
        'zone_active_test': test_active,
        'delta_signatures_zone_tenue_pct': (
            round(delta_held * 100, 1) if delta_held is not None else None),
        'delta_signatures_zone_active_pct': (
            round(delta_active * 100, 1) if delta_active is not None else None),
        'fourchette_signatures_zone_tenue_test': list(
            _wide_interval(test_held['signatures'])),
        'fourchette_signatures_zone_active_test': list(
            _wide_interval(test_active['signatures'])),
        'confiance': confiance,
        'message_fr': _render_message_fr(
            held_villes=held_set, baseline_held=baseline_held,
            test_held=test_held, baseline_active=baseline_active,
            test_active=test_active, delta_held=delta_held,
            delta_active=delta_active, confiance=confiance),
    }


# ── Vue lecture seule (PUB38 : "commande + écran rapport « test géo »") ──────
def _parse_iso_date(raw):
    try:
        return datetime.date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None


class GeoHoldoutReportView(APIView):
    """PUB38 — ``GET /api/django/adsengine/reporting/incrementalite/`` —
    lecture seule, company-scopée, gatée ``adsengine_view``. Paramètres query
    ``villes`` (CSV), ``baseline_debut``/``baseline_fin``,
    ``test_debut``/``test_fin`` (ISO ``YYYY-MM-DD``). Délègue tout le calcul à
    ``geo_holdout_report`` (pur, testé séparément) — cette vue ne fait que
    parser les query params + appliquer le gate de permission. Aucune
    écriture, aucune action automatique."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _user_has_or_legacy(request.user, 'adsengine_view'):
            return Response({'detail': 'Permission refusée.'}, status=403)
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)

        raw_villes = request.query_params.get('villes', '') or ''
        villes = [v for v in raw_villes.split(',') if v.strip()]
        baseline_start = _parse_iso_date(
            request.query_params.get('baseline_debut'))
        baseline_end = _parse_iso_date(
            request.query_params.get('baseline_fin'))
        test_start = _parse_iso_date(request.query_params.get('test_debut'))
        test_end = _parse_iso_date(request.query_params.get('test_fin'))

        report = geo_holdout_report(
            company, held_villes=villes, baseline_start=baseline_start,
            baseline_end=baseline_end, test_start=test_start,
            test_end=test_end)
        return Response(report)
