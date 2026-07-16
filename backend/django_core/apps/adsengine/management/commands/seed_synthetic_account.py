"""ADSENG7 — Générateur de compte SYNTHÉTIQUE (le carburant du harnais P6).

Fabrique N mois de ``ArmDailyStat`` + miroirs + leads CRM synthétiques avec une
VÉRITÉ TERRAIN paramétrée (bras gagnant connu, bruit, dérive mi-vol, effondrement
de delivery), en 4 SCÉNARIOS DORÉS nommés et à seed DÉTERMINISTE : le même seed
reproduit exactement les mêmes données, pour que la science (bandit ADSENG8,
gardien ADSENG4) soit testée contre une vérité connue.

Frontière cross-app : les leads CRM sont créés via l'entrée SANCTIONNÉE
``apps.crm.services.create_lead_from_meta_lead_ads`` (jamais un import des modèles
crm) — elle est idempotente sur ``leadgen_id`` et pose ``meta_ad_id`` (ADSENG1),
donc les leads synthétiques sont attribuables par variante (ADSENG6). Les miroirs
sont upsertés (idempotents) et l'expérience est recréée à chaque exécution
(supprime la précédente du même scénario) — une double exécution avec le même
seed laisse exactement le même état.

Les 4 scénarios dorés (vérité terrain dans ``SCENARIOS``) :
  * ``clear_winner``     — un bras nettement gagnant, bruit faible ;
  * ``noisy_tie``        — deux bras quasi égaux, bruit élevé (pas de gagnant) ;
  * ``mid_flight_drift`` — le gagnant CHANGE à mi-parcours (A puis B) ;
  * ``delivery_collapse``— la delivery d'un bras s'effondre à mi-parcours.
"""
import datetime
import random

from django.core.management.base import BaseCommand, CommandError


# ── Vérité terrain des 4 scénarios dorés ──────────────────────────────────────
# base_rate = conversations/impression ; rate_end (dérive) ; daily_impressions ;
# collapse_after_frac (delivery → ~0 au-delà de cette fraction du vol).
SCENARIOS = {
    'clear_winner': {
        'noise': 0.10,
        'winning_arm': 'A',
        'arms': [
            {'label': 'A', 'base_rate': 0.050, 'daily_impressions': 400},
            {'label': 'B', 'base_rate': 0.020, 'daily_impressions': 400},
            {'label': 'C', 'base_rate': 0.015, 'daily_impressions': 400},
        ],
    },
    'noisy_tie': {
        'noise': 0.50,
        'winning_arm': None,  # égalité statistique : pas de gagnant net
        'arms': [
            {'label': 'A', 'base_rate': 0.030, 'daily_impressions': 400},
            {'label': 'B', 'base_rate': 0.031, 'daily_impressions': 400},
        ],
    },
    'mid_flight_drift': {
        'noise': 0.10,
        'winning_arm_first_half': 'A',
        'winning_arm_second_half': 'B',
        'arms': [
            {'label': 'A', 'base_rate': 0.050, 'rate_end': 0.010,
             'daily_impressions': 400},
            {'label': 'B', 'base_rate': 0.010, 'rate_end': 0.050,
             'daily_impressions': 400},
        ],
    },
    'delivery_collapse': {
        'noise': 0.10,
        'winning_arm': 'A',
        'collapse_arm': 'A',
        'arms': [
            {'label': 'A', 'base_rate': 0.040, 'daily_impressions': 400,
             'collapse_after_frac': 0.5},
            {'label': 'B', 'base_rate': 0.030, 'daily_impressions': 400},
        ],
    },
}

# Ancre de date FIXE (jamais ``now()``) — la reproductibilité exige des dates
# stables entre exécutions.
_ANCHOR = datetime.date(2026, 1, 1)
_CPM_MAD = 50.0  # coût pour mille impressions (synthétique)


def _arm_daily_series(rng, arm_spec, days, noise):
    """Série quotidienne déterministe d'un bras (impressions/clics/conversations/
    dépense) — bruitée, avec dérive de taux et effondrement de delivery
    optionnels. Le RNG passé rend tout reproductible sous un seed donné."""
    base = arm_spec['base_rate']
    end = arm_spec.get('rate_end', base)
    imp0 = arm_spec['daily_impressions']
    collapse = arm_spec.get('collapse_after_frac')

    series = []
    for d in range(days):
        frac = d / max(days - 1, 1)
        rate = base + (end - base) * frac
        imp = imp0
        if collapse is not None and frac >= collapse:
            imp = int(imp0 * 0.02)  # delivery quasi nulle
        imp = max(0, int(round(imp * (1 + rng.uniform(-noise, noise)))))
        conv = max(0, int(round(imp * rate * (1 + rng.uniform(-noise, noise)))))
        conv = min(conv, imp)
        clicks = min(imp, conv + int(round(imp * 0.03)))
        spend = round(imp * _CPM_MAD / 1000.0, 2)
        series.append({
            'impressions': imp, 'clicks': clicks,
            'conversations': conv, 'spend': spend,
        })
    return series


def generate_synthetic_account(*, company, scenario='clear_winner', months=3,
                               seed=42, create_leads=True):
    """ADSENG7 — Génère un compte synthétique pour une société et un scénario.

    Recrée l'expérience ``[SYNTH:<scenario>]`` (supprime la précédente),
    upsert les miroirs, écrit les ``ArmDailyStat`` quotidiens et, si
    ``create_leads``, des leads CRM attribuables (via crm.services). Renvoie un
    résumé ``{'experiment_id', 'scenario', 'winning_arm', 'arms': [...]}`` où
    chaque bras porte ses totaux (vérité terrain observable). DÉTERMINISTE :
    même ``seed`` ⇒ mêmes données."""
    spec = SCENARIOS.get(scenario)
    if spec is None:
        raise CommandError(
            f"Scénario inconnu : {scenario!r}. "
            f"Choix : {', '.join(SCENARIOS)}.")

    from apps.adsengine.models import (
        AdCampaignMirror, AdMirror, AdSetMirror, ArmDailyStat, Experiment,
        ExperimentArm,
    )

    days = max(1, int(months) * 30)
    noise = spec.get('noise', 0.10)
    rng = random.Random(seed)

    exp_name = f'[SYNTH:{scenario}]'
    # Recréation : on supprime l'expérience précédente du même scénario
    # (cascade sur bras + stats + décisions).
    Experiment.objects.filter(company=company, name=exp_name).delete()

    campaign, _ = AdCampaignMirror.objects.update_or_create(
        company=company, meta_id=f'synth-{scenario}-cmp',
        defaults={'name': f'{exp_name} Campagne', 'status': 'PAUSED',
                  'created_via_engine': True})
    adset, _ = AdSetMirror.objects.update_or_create(
        company=company, meta_id=f'synth-{scenario}-ast',
        defaults={'name': f'{exp_name} AdSet', 'status': 'PAUSED',
                  'campaign': campaign, 'created_via_engine': True})

    experiment = Experiment.objects.create(
        company=company, name=exp_name,
        tested_variable=Experiment.Variable.HOOK,
        status=Experiment.Statut.EN_COURS,
        start_date=_ANCHOR, end_date=_ANCHOR + datetime.timedelta(days=days - 1),
        notes=(f'Compte synthétique ADSENG7 (seed={seed}, mois={months}). '
               f'Vérité terrain : {scenario}.'))

    arm_summaries = []
    lead_seq = 0
    for arm_spec in spec['arms']:
        label = arm_spec['label']
        ad_meta_id = f'synth-{scenario}-{label}-ad'
        AdMirror.objects.update_or_create(
            company=company, meta_id=ad_meta_id,
            defaults={'name': f'{exp_name} Ad {label}', 'status': 'PAUSED',
                      'adset': adset, 'created_via_engine': True})
        arm = ExperimentArm.objects.create(
            company=company, experiment=experiment, label=f'Bras {label}',
            ad_id=ad_meta_id, hook_id=f'H-{label}', is_active=True)

        series = _arm_daily_series(rng, arm_spec, days, noise)
        totals = {'impressions': 0, 'clicks': 0, 'conversations': 0,
                  'spend': 0.0, 'first_half_conv': 0, 'second_half_conv': 0,
                  'last_quarter_impressions': 0}
        half = days // 2
        last_q = days - max(1, days // 4)
        for d, day_stats in enumerate(series):
            day = _ANCHOR + datetime.timedelta(days=d)
            ArmDailyStat.upsert(arm=arm, date=day, **day_stats)
            totals['impressions'] += day_stats['impressions']
            totals['clicks'] += day_stats['clicks']
            totals['conversations'] += day_stats['conversations']
            totals['spend'] += day_stats['spend']
            if d < half:
                totals['first_half_conv'] += day_stats['conversations']
            else:
                totals['second_half_conv'] += day_stats['conversations']
            if d >= last_q:
                totals['last_quarter_impressions'] += day_stats['impressions']

        # Leads CRM synthétiques (attribuables par meta_ad_id, ADSENG1/6). Le
        # nombre par bras ∝ conversions (le bras gagnant en porte le plus) ;
        # créés via l'entrée sanctionnée crm.services (jamais crm.models).
        leads_created = 0
        if create_leads:
            from apps.crm.services import create_lead_from_meta_lead_ads
            n_leads = min(8, 1 + totals['conversations'] // 60)
            for _ in range(n_leads):
                lead_seq += 1
                create_lead_from_meta_lead_ads(
                    company=company,
                    leadgen_id=f'synth-{scenario}-{label}-{lead_seq}',
                    field_data=[
                        {'name': 'full_name',
                         'values': [f'Synthé {label}{lead_seq}']},
                        {'name': 'phone_number',
                         'values': [f'+21260{lead_seq:07d}']},
                    ],
                    ad_id=ad_meta_id, adgroup_id=adset.meta_id,
                    form_id=f'synth-{scenario}-form')
                leads_created += 1

        arm_summaries.append({
            'label': label,
            'ad_id': ad_meta_id,
            'total_impressions': totals['impressions'],
            'total_conversations': totals['conversations'],
            'total_spend': round(totals['spend'], 2),
            'first_half_conversations': totals['first_half_conv'],
            'second_half_conversations': totals['second_half_conv'],
            'last_quarter_impressions': totals['last_quarter_impressions'],
            'leads_created': leads_created,
        })

    return {
        'experiment_id': experiment.id,
        'scenario': scenario,
        'winning_arm': spec.get('winning_arm'),
        'days': days,
        'arms': arm_summaries,
    }


class Command(BaseCommand):
    help = ("ADSENG7 — Génère un compte publicitaire SYNTHÉTIQUE "
            "(scénarios dorés, seed déterministe) pour le harnais de test.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id', type=int, default=None,
            help='Société cible (défaut : la première société active).')
        parser.add_argument(
            '--scenario', default='clear_winner',
            choices=sorted(SCENARIOS),
            help='Scénario doré (défaut : clear_winner).')
        parser.add_argument('--months', type=int, default=3,
                            help='Nombre de mois (défaut : 3).')
        parser.add_argument('--seed', type=int, default=42,
                            help='Seed déterministe (défaut : 42).')
        parser.add_argument(
            '--no-leads', action='store_true',
            help='Ne pas créer de leads CRM (miroirs + stats seulement).')

    def handle(self, *args, **options):
        company_id = options.get('company_id')
        if company_id:
            from authentication.models import Company
            company = Company.objects.filter(pk=company_id).first()
            if company is None:
                raise CommandError(f'Société #{company_id} introuvable.')
        else:
            from authentication.selectors import active_companies
            company = next(iter(active_companies()), None)
            if company is None:
                raise CommandError('Aucune société active.')

        summary = generate_synthetic_account(
            company=company, scenario=options['scenario'],
            months=options['months'], seed=options['seed'],
            create_leads=not options['no_leads'])

        self.stdout.write(self.style.SUCCESS(
            f"seed_synthetic_account : scénario {summary['scenario']}, "
            f"{summary['days']} jours, {len(summary['arms'])} bras "
            f"(gagnant attendu : {summary['winning_arm']})."))
        for arm in summary['arms']:
            self.stdout.write(
                f"  {arm['label']} — {arm['total_impressions']} imp, "
                f"{arm['total_conversations']} conv, "
                f"{arm['total_spend']} MAD, {arm['leads_created']} lead(s).")
        return None
