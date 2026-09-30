# -*- coding: utf-8 -*-
"""QA-COHERENCE — auditeur d'invariants métier, LECTURE SEULE.

    python manage.py audit_coherence [--company <slug>] [--json]
                                     [--no-persist] [--rules I2,DOC_TOTAUX_DEVIS,...]

CONTRAT (un autre lane en dépend — ne pas renommer une clé). Avec ``--json``,
UN SEUL objet JSON est écrit sur stdout :

    {"companies": [slug, ...],
     "checked": {object_type: n},
     "violations": [{rule, severity, object_type, object_id, reference,
                     company, message, values}],
     "new": [... même forme : seulement les nouvelles depuis la dernière
             passe persistée ...],
     "rule_errors": [{rule, object_type, object_id, reference, company,
                      error}],
     "duration_s": float}

``--no-persist`` : rien n'est écrit (pas même la table d'audit) et ``new`` =
toutes les violations. Code de sortie 0 dans tous les cas, sauf plantage de
la commande elle-même (dont un argument invalide : société ou règle
inconnue → ``CommandError``, code 1).

``--rules`` accepte les identifiants du registre
(``apps/ventes/coherence``) ; un identifiant désactivé par défaut peut être
demandé explicitement. Aucune donnée métier n'est jamais modifiée : le calcul
tourne dans une transaction annulée ; seule la table
``ventes_violationcoherence`` est mise à jour (sauf ``--no-persist``).
"""
import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ("Audit nocturne des invariants métier (devis, factures, études, "
            "CRM) — lecture seule ; ne signale que les NOUVELLES violations.")

    def add_arguments(self, parser):
        parser.add_argument('--company', default=None,
                            help='Slug de la société (défaut : toutes les '
                                 'sociétés actives).')
        parser.add_argument('--json', action='store_true',
                            help='Écrit UN objet JSON sur stdout.')
        parser.add_argument('--no-persist', action='store_true',
                            help="N'écrit rien ; « new » = toutes les "
                                 'violations.')
        parser.add_argument('--rules', default=None,
                            help='Identifiants de règles séparés par des '
                                 'virgules (défaut : règles actives).')

    def handle(self, *args, **opts):
        from authentication.models import Company

        from apps.ventes.coherence.moteur import run_audit
        from apps.ventes.coherence.registre import regles_selectionnees

        company = None
        if opts['company']:
            company = Company.objects.filter(slug=opts['company']).first()
            if company is None:
                raise CommandError(f"Société inconnue : {opts['company']}")
        rules = None
        if opts['rules']:
            rules = [r.strip() for r in opts['rules'].split(',') if r.strip()]
            try:
                regles_selectionnees(rules)
            except KeyError as exc:
                raise CommandError(f'Règle(s) inconnue(s) : {exc}')

        report = run_audit(company=company, persist=not opts['no_persist'],
                           rules=rules)
        if opts['json']:
            self.stdout.write(json.dumps(report.as_json(), ensure_ascii=False,
                                         default=str))
            return
        data = report.as_json()
        self.stdout.write(
            f"Audit de cohérence — {', '.join(data['companies']) or '—'} — "
            f"{data['duration_s']} s — contrôlés {data['checked']}")
        self.stdout.write(
            f"{len(data['violations'])} violation(s), "
            f"{len(data['new'])} nouvelle(s), "
            f"{report.resolved} résolue(s), "
            f"{len(data['rule_errors'])} erreur(s) de règle"
            + ('' if report.persisted else ' (rien écrit : --no-persist)'))
        for v in data['new'][:50]:
            self.stdout.write(
                f"  NOUVEAU [{v['severity']}] {v['rule']} "
                f"{v['object_type']} {v['reference']} ({v['company']}) : "
                f"{v['message']}")
        for e in data['rule_errors'][:20]:
            self.stdout.write(
                f"  ERREUR {e['rule']} {e['object_type']} {e['reference']} "
                f"({e['company']}) : {e['error']}")
