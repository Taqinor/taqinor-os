"""QA-COHERENCE — le moteur : exécute les règles, isole, persiste.

``run_audit(company=None, persist=True, rules=None) -> AuditReport``

LECTURE SEULE SUR LE MÉTIER, TOUJOURS. Le calcul d'une société tourne dans
UNE transaction ``atomic()`` systématiquement ANNULÉE
(``transaction.set_rollback(True)``) : le constructeur de devis peut toucher
la base, rien n'en survit. Chaque (objet × règle) tourne dans son propre
point de sauvegarde : un objet qui fait planter une règle devient une
« erreur de règle » consignée — jamais l'arrêt de la passe. La persistance
des violations (table d'audit ``ViolationCoherence``, et elle seule) se fait
APRÈS, dans sa propre transaction.
"""
from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .contexte import ContexteAudit, ErreurRendu, rendu_sans_reseau
from .registre import (PORTEE_DEVIS, PORTEE_FACTURE, PORTEE_SOCIETE,
                       regles_selectionnees)

logger = logging.getLogger(__name__)

# Pseudo-règle des échecs de construction du document (une par devis).
REGLE_RENDU = 'QUOTE_BUILD'


@dataclass
class AuditReport:
    companies: list = field(default_factory=list)          # slugs
    checked: Counter = field(default_factory=Counter)      # type → n
    violations: list = field(default_factory=list)         # Violation
    new: list = field(default_factory=list)                # Violation
    rule_errors: list = field(default_factory=list)        # dicts
    resolved: int = 0
    duration_s: float = 0.0
    persisted: bool = False
    _slugs: dict = field(default_factory=dict, repr=False)  # id → slug

    def violation_dict(self, v):
        return {
            'rule': v.regle, 'severity': v.gravite,
            'object_type': v.object_type, 'object_id': v.object_id,
            'reference': v.reference,
            'company': self._slugs.get(v.company_id, v.company_id),
            'message': v.message,
            'values': dict(v.valeurs, attendu=v.attendu),
        }

    def as_json(self):
        """LE contrat de ``manage.py audit_coherence --json`` (un autre
        lane en dépend — ne pas renommer une clé)."""
        return {
            'companies': list(self.companies),
            'checked': dict(self.checked),
            'violations': [self.violation_dict(v) for v in self.violations],
            'new': [self.violation_dict(v) for v in self.new],
            'rule_errors': list(self.rule_errors),
            'duration_s': round(self.duration_s, 3),
        }


def _societes(company):
    if company is not None:
        return [company]
    from authentication.selectors import active_companies
    return list(active_companies())


def _devis_qs(company):
    from apps.ventes.models import Devis
    return (Devis.objects.filter(company=company, is_active=True)
            .select_related('client', 'lead', 'company', 'bon_commande')
            .prefetch_related('lignes__produit')
            .order_by('pk'))


def _factures_qs(company):
    from apps.ventes.models import Facture
    return (Facture.objects.filter(company=company)
            .prefetch_related('lignes', 'avoirs__lignes')
            .order_by('pk'))


def _factures_actives_par_devis(company):
    """{devis_id: [factures non annulées]} — les DEUX voies (échéancier
    ``Facture.devis`` et chaîne ``BonCommande → Facture``), même périmètre
    que ``selectors.factures_du_devis`` mais en une requête par société."""
    from apps.ventes.models import Facture
    qs = (Facture.objects.filter(company=company)
          .exclude(statut=Facture.Statut.ANNULEE)
          .filter(Q(devis__isnull=False)
                  | Q(bon_commande__devis__isnull=False))
          .select_related('bon_commande')
          .prefetch_related('lignes', 'avoirs__lignes'))
    par_devis = {}
    for f in qs:
        cles = {f.devis_id}
        if f.bon_commande_id and f.bon_commande is not None:
            cles.add(f.bon_commande.devis_id)
        for cle in cles - {None}:
            par_devis.setdefault(cle, []).append(f)
    return par_devis


class _Ctx(ContexteAudit):
    def __init__(self, company, **kw):
        super().__init__(company, **kw)
        self._factures = None

    def factures_actives_du_devis(self, devis_id):
        if self._factures is None:
            self._factures = _factures_actives_par_devis(self.company)
        return self._factures.get(devis_id, [])


def _erreur(report, regle_id, obj_type, obj, company, exc):
    report.rule_errors.append({
        'rule': regle_id, 'object_type': obj_type,
        'object_id': getattr(obj, 'pk', None),
        'reference': getattr(obj, 'reference', '') or '',
        'company': company.slug,
        'error': f'{type(exc).__name__}: {str(exc)[:200]}',
    })


def _executer_societe(company, regles, report, *, constructeur=None):
    """Évalue toutes les règles pour une société. Rend ``(violations,
    inconnus)`` où ``inconnus`` = {(règle, type, id)} dont le verdict n'a
    pas pu être établi (erreur) — leurs violations passées ne seront PAS
    résolues."""
    ctx = _Ctx(company, constructeur=constructeur)
    violations, inconnus = [], set()
    par_portee = {}
    for r in regles:
        par_portee.setdefault(r.portee, []).append(r)

    def _appliquer(r, obj, obj_type):
        try:
            with transaction.atomic():
                violations.extend(r.check(r, obj, ctx) or [])
        except ErreurRendu as exc:
            inconnus.add((r.id, obj_type, obj.pk))
            if (REGLE_RENDU, obj_type, obj.pk) not in inconnus:
                inconnus.add((REGLE_RENDU, obj_type, obj.pk))
                _erreur(report, REGLE_RENDU, obj_type, obj, company, exc)
        except Exception as exc:  # noqa: BLE001 — isolé par objet
            inconnus.add((r.id, obj_type, obj.pk))
            _erreur(report, r.id, obj_type, obj, company, exc)

    if par_portee.get(PORTEE_DEVIS):
        for devis in _devis_qs(company).iterator(chunk_size=100):
            report.checked['devis'] += 1
            for r in par_portee[PORTEE_DEVIS]:
                _appliquer(r, devis, 'devis')
    if par_portee.get(PORTEE_FACTURE):
        for facture in _factures_qs(company).iterator(chunk_size=100):
            report.checked['facture'] += 1
            for r in par_portee[PORTEE_FACTURE]:
                _appliquer(r, facture, 'facture')
    for r in par_portee.get(PORTEE_SOCIETE, []):
        try:
            with transaction.atomic():
                violations.extend(r.check(r, company, ctx) or [])
        except Exception as exc:  # noqa: BLE001
            inconnus.add((r.id, '*', '*'))
            report.rule_errors.append({
                'rule': r.id, 'object_type': 'societe',
                'object_id': company.pk, 'reference': '',
                'company': company.slug,
                'error': f'{type(exc).__name__}: {str(exc)[:200]}'})
    # Une violation n'appartient qu'à la société auditée (garde-fou
    # multi-tenant : une règle ne peut pas faire fuiter un autre tenant).
    violations = [v for v in violations if v.company_id == company.pk]
    return violations, inconnus


def _persister(company, regles, violations, inconnus, maintenant):
    """Upsert des violations d'UNE société ; rend (nouvelles, nb résolues).

    Ne résout que les violations ouvertes des règles EXÉCUTÉES dans cette
    passe, et jamais celles d'un objet dont le verdict est inconnu."""
    from apps.ventes.models_coherence import ViolationCoherence
    ids_regles = {r.id for r in regles}
    ouvertes = {
        v.fingerprint: v for v in ViolationCoherence.objects.filter(
            company=company, rule_id__in=ids_regles, resolved_at__isnull=True)
    }
    existantes = {
        v.fingerprint: v for v in ViolationCoherence.objects.filter(
            company=company,
            fingerprint__in=[x.empreinte for x in violations])
    }
    nouvelles, vues = [], set()
    for v in violations:
        emp = v.empreinte
        if emp in vues:
            continue
        vues.add(emp)
        details = {'message': v.message, 'values': v.valeurs,
                   'attendu': v.attendu, 'cle': v.cle}
        ligne = existantes.get(emp)
        if ligne is None:
            ViolationCoherence.objects.create(
                company=company, rule_id=v.regle, severity=v.gravite,
                object_type=v.object_type, object_id=v.object_id,
                reference=(v.reference or '')[:80], fingerprint=emp,
                first_seen=maintenant, last_seen=maintenant,
                details=details)
            nouvelles.append(v)
            continue
        if ligne.resolved_at is not None:
            nouvelles.append(v)  # réapparue : de nouveau une alerte
        ligne.last_seen = maintenant
        ligne.resolved_at = None
        ligne.severity = v.gravite
        ligne.reference = (v.reference or '')[:80]
        ligne.details = details
        ligne.save(update_fields=['last_seen', 'resolved_at', 'severity',
                                  'reference', 'details', 'updated_at'])
    resolues = 0
    for emp, ligne in ouvertes.items():
        if emp in vues:
            continue
        if (ligne.rule_id, '*', '*') in inconnus or \
                (ligne.rule_id, ligne.object_type, ligne.object_id) \
                in inconnus:
            continue
        ligne.resolved_at = maintenant
        ligne.save(update_fields=['resolved_at', 'updated_at'])
        resolues += 1
    return nouvelles, resolues


def run_audit(company=None, persist=True, rules=None, *,
              constructeur=None) -> AuditReport:
    """Audite une société (ou toutes les sociétés actives).

    ``rules`` : ids explicites (``None`` = règles actives par défaut).
    ``persist=False`` : rien n'est écrit, et ``new`` = toutes les
    violations. ``constructeur`` : injection du constructeur de document
    (tests)."""
    t0 = time.monotonic()
    regles = regles_selectionnees(rules)
    report = AuditReport()
    maintenant = timezone.now()
    for societe in _societes(company):
        report.companies.append(societe.slug)
        report._slugs[societe.pk] = societe.slug
        with rendu_sans_reseau():
            with transaction.atomic():
                try:
                    violations, inconnus = _executer_societe(
                        societe, regles, report, constructeur=constructeur)
                finally:
                    # LECTURE SEULE : rien de ce que le calcul a touché ne
                    # survit, succès ou échec.
                    transaction.set_rollback(True)
        report.violations.extend(violations)
        if not persist:
            report.new.extend(violations)
            continue
        try:
            with transaction.atomic():
                nouvelles, resolues = _persister(
                    societe, regles, violations, inconnus, maintenant)
            report.new.extend(nouvelles)
            report.resolved += resolues
        except Exception as exc:  # noqa: BLE001 — une société n'arrête pas
            logger.exception('audit_coherence : persistance impossible (%s)',
                             societe.slug)
            report.rule_errors.append({
                'rule': 'PERSISTENCE', 'object_type': 'societe',
                'object_id': societe.pk, 'reference': '',
                'company': societe.slug,
                'error': f'{type(exc).__name__}: {str(exc)[:200]}'})
    report.persisted = bool(persist)
    report.duration_s = time.monotonic() - t0
    return report
