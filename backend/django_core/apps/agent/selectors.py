"""Lectures du journal de l'assistant exposées aux autres apps (AIC35).

Les autres apps passent par ici — jamais par ``agent.models``.
"""
import datetime

from django.db.models import Count, IntegerField, Q, Sum
from django.db.models.fields.json import KT
from django.db.models.functions import Cast
from django.utils import timezone

from .models import AssistantEvent
from .services import CHAMPS_TOKENS, anonymiser_texte, cout_estime_usd


def manques_signales_entre(company, user, debut, fin):
    """Nombre de « fonction manquante » (intention ``manque``) signalées par
    ``user`` dans [``debut``, ``fin``[ (datetimes aware), société ``company``."""
    return AssistantEvent.objects.filter(
        company=company, user=user, intention=AssistantEvent.Intention.MANQUE,
        created_at__gte=debut, created_at__lt=fin).count()


def manques_signales_hier(company, user, aujourdhui):
    """Manques signalés par ``user`` la veille de ``aujourdhui`` (date locale
    Casablanca) — compte seulement."""
    from core.dates import TZ_METIER
    minuit = datetime.datetime.combine(
        aujourdhui, datetime.time.min, tzinfo=TZ_METIER)
    return manques_signales_entre(
        company, user, minuit - datetime.timedelta(days=1), minuit)


def noms_des_leads(company, lead_ids) -> dict:
    """{lead_id: [nom, prénom du lead et de son client]} — lus via
    ``apps.crm.selectors`` (jamais le modèle crm), bornés à la société ; sert à
    anonymiser les textes des événements (export, statistiques, diagnostic)."""
    from apps.crm.selectors import get_company_leads_by_ids

    noms = {}
    for pk, lead in get_company_leads_by_ids(company, set(lead_ids)).items():
        client = getattr(lead, 'client', None)
        noms[pk] = [v for v in (lead.nom, lead.prenom, getattr(client, 'nom', None),
                                getattr(client, 'prenom', None)) if v]
    return noms


def agregats_par_modele(qs) -> list:
    """Événements de ``qs`` agrégés PAR MODÈLE : ``n``, ``repli_n``, un compte
    ``i_<intention>`` par intention et la somme ``t_<jeton>`` de chaque jeton de
    ``CHAMPS_TOKENS``. Source unique des statistiques (AIC12) et du diagnostic."""
    intentions = AssistantEvent.Intention.values
    jeton = {cle: Sum(Cast(KT(f'tokens__{cle}'), IntegerField()))
             for cle in CHAMPS_TOKENS}
    return list(qs.values('modele').annotate(
        n=Count('id'), repli_n=Count('id', filter=Q(repli=True)),
        **{f'i_{i}': Count('id', filter=Q(intention=i)) for i in intentions},
        **{f't_{cle}': agregat for cle, agregat in jeton.items()}))


def cout_des_agregats(par_modele) -> float:
    """Coût estimé (USD) des agrégats de :func:`agregats_par_modele`."""
    return sum(cout_estime_usd(g['modele'], {
        cle: g[f't_{cle}'] or 0 for cle in CHAMPS_TOKENS}) for g in par_modele)


def resume_assistant(company, depuis, *, limite_signalements=20) -> dict:
    """COP-G6 — l'assistant depuis ``depuis`` pour ``company`` (``None`` =
    toutes, super-utilisateur sans société) : questions, erreurs, part de repli,
    coût estimé et ``signalements`` (événements ``bug`` / ``manque``, question
    ANONYMISÉE comme l'export, avec le tampon technique ``diagnostic`` quand il
    existe). Forme : ``reporting/contract_samples/assistant_diagnostic.json``."""
    qs = AssistantEvent.objects.filter(created_at__gte=depuis)
    if company is not None:
        qs = qs.filter(company=company)
    par_modele = agregats_par_modele(qs)
    questions = sum(g['n'] for g in par_modele)
    signalements = list(qs.filter(intention__in=(
        AssistantEvent.Intention.BUG, AssistantEvent.Intention.MANQUE,
    )).order_by('-created_at')[:limite_signalements])
    noms = noms_des_leads(company, [e.lead_id for e in signalements if e.lead_id]) \
        if company is not None else {}
    return {
        'questions': questions,
        'erreurs': qs.filter(erreur__isnull=False).count(),
        'part_repli': round(sum(g['repli_n'] for g in par_modele) / questions, 4)
        if questions else 0.0,
        'cout_estime_usd': round(cout_des_agregats(par_modele), 2),
        'signalements': [{
            'evenement_id': e.pk,
            'intention': e.intention,
            'question_anonymisee': anonymiser_texte(e.question, noms.get(e.lead_id, ())),
            'ecran': e.ecran,
            'cree_le': timezone.localtime(e.created_at).isoformat(),
            'diagnostic': (e.erreur or {}).get('diagnostic')
            if isinstance(e.erreur, dict) else None,
        } for e in signalements],
    }
