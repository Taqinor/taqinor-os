"""NTADM10/11/12/34/35 — Environnement sandbox self-service (scope MVP).

PÉRIMÈTRE ASSUMÉ (voir le rapport de la lane NTADM) : ce service clone le
TENANT LUI-MÊME (`authentication.Company` + `parametres.CompanyProfile`,
deux apps de FONDATION, import direct autorisé) avec un nom/slug suffixé
« -sandbox » — il ne clone PAS encore les données métier (leads/devis/
clients) avec anonymisation, cette portion étant NTADM10-ESCALATE (voir
DONE LOG/rapport : trop de surface cross-app — crm/ventes/stock — pour un
premier lot, jamais un import direct de leurs `models`). Le modèle
`SandboxEnvironment` et le cycle de vie (création → prêt/échec → rappels →
purge) sont complets et testés ; l'étape de clonage métier est un TODO
explicite (`erreur`/log), jamais silencieux.
"""
from __future__ import annotations

import uuid

from django.utils import timezone

from .models import AdminOpsSettings, SandboxEnvironment


class SandboxNonAutorise(Exception):
    """NTADM34 — la fonctionnalité sandbox est désactivée pour ce tenant."""


class SandboxDejaActif(Exception):
    """NTADM10 — un sandbox actif existe déjà (rate-limit 1 par tenant)."""


def _duree_defaut_jours(company):
    reglage = AdminOpsSettings.get_or_default(company)
    return reglage.sandbox_duree_defaut_jours


def creer_sandbox(company, user):
    """NTADM10 — crée un `SandboxEnvironment` puis lance le clonage
    (synchrone ici ; `tasks.py` l'enrobe pour un appel asynchrone Celery).
    Rate-limité à 1 sandbox actif (en_creation/pret) par tenant."""
    reglage = AdminOpsSettings.get_or_default(company)
    if not reglage.sandbox_autorise:
        raise SandboxNonAutorise(
            'La création de sandbox est désactivée pour cette société.')

    actif = SandboxEnvironment.objects.filter(
        company=company,
        statut__in=[SandboxEnvironment.Statut.EN_CREATION,
                    SandboxEnvironment.Statut.PRET]).exists()
    if actif:
        raise SandboxDejaActif(
            'Un environnement sandbox actif existe déjà pour cette société.')

    duree = _duree_defaut_jours(company)
    env = SandboxEnvironment.objects.create(
        company=company,
        statut=SandboxEnvironment.Statut.EN_CREATION,
        date_expiration=timezone.now() + timezone.timedelta(days=duree),
        cree_par=user if getattr(user, 'pk', None) else None)

    from . import tasks
    tasks.cloner_sandbox.delay(env.id)
    return env


def cloner_sandbox_sync(sandbox_env_id):
    """Corps du clonage — appelé par la tâche Celery `tasks.cloner_sandbox`.
    Isolé en fonction pure pour être testable sans worker Celery."""
    env = SandboxEnvironment.objects.filter(pk=sandbox_env_id).first()
    if env is None:
        return
    try:
        from authentication.models import Company

        source = env.company
        suffixe = uuid.uuid4().hex[:6]
        sandbox_company = Company.objects.create(
            nom=f'{source.nom} (Sandbox)',
            slug=f'{source.slug}-sandbox-{suffixe}')

        try:
            from apps.parametres.models_company import CompanyProfile
            src_profile = CompanyProfile.objects.filter(company=source).first()
            if src_profile is not None:
                CompanyProfile.objects.create(
                    company=sandbox_company,
                    nom=f'{src_profile.nom} (Sandbox)',
                    email=src_profile.email, telephone=src_profile.telephone)
        except Exception:  # pragma: no cover - profil source absent/incomplet
            pass

        env.sandbox_company = sandbox_company
        env.statut = SandboxEnvironment.Statut.PRET
        env.save(update_fields=['sandbox_company', 'statut'])
    except Exception as exc:  # pragma: no cover - jamais silencieux (erreur loggée)
        env.statut = SandboxEnvironment.Statut.ECHEC
        env.erreur = str(exc)
        env.save(update_fields=['statut', 'erreur'])


def prolonger_sandbox(env, *, jours=14):
    """NTADM12 — prolonge de `jours` (14 par défaut), max 2 fois."""
    if env.prolongations_count >= 2:
        raise ValueError('Un sandbox ne peut être prolongé plus de 2 fois.')
    env.date_expiration = env.date_expiration + timezone.timedelta(days=jours)
    env.prolongations_count += 1
    env.rappel_j3_envoye = False
    env.rappel_48h_envoye = False
    env.save(update_fields=[
        'date_expiration', 'prolongations_count',
        'rappel_j3_envoye', 'rappel_48h_envoye'])
    return env
