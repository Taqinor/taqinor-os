"""QA-COHERENCE — digest des NOUVELLES violations aux admins de la société.

Une notification par admin et par société, UNIQUEMENT s'il existe de
nouvelles violations (``AuditReport.new``) : compte par règle + les 10
premières références. Passe par ``notifications.services.notify()`` avec
son report des heures calmes (N1/N4) — la passe tourne à 04:15, le digest est
livré à l'ouverture des heures de travail. Destinataires : utilisateurs
internes admins de la société (jamais un client, jamais une adresse
externe).
"""
from __future__ import annotations

from collections import Counter

from .registre import GRAVITE_INFO, REGISTRE

MAX_REFERENCES = 10


def corps_digest(violations):
    """Texte du digest (FR) pour une liste de violations d'UNE société."""
    par_regle = Counter(v.regle for v in violations)
    lignes = []
    for regle_id, n in par_regle.most_common():
        r = REGISTRE.get(regle_id)
        libelle = r.libelle if r else regle_id
        lignes.append(f'• {n} × {regle_id} — {libelle}')
    refs = []
    for v in violations:
        ref = v.reference or f'{v.object_type} #{v.object_id}'
        if ref not in refs:
            refs.append(ref)
        if len(refs) >= MAX_REFERENCES:
            break
    lignes.append('')
    lignes.append('Premières références : ' + ', '.join(refs))
    lignes.append("Détail : python manage.py audit_coherence --json "
                  "(lecture seule).")
    return '\n'.join(lignes)


def notifier_nouvelles_violations(report):
    """Notifie les admins de chaque société ayant de NOUVELLES violations
    (gravité hors « info »). Rend le nombre de notifications émises."""
    from authentication.models import Company, CustomUser
    from apps.notifications.models import EventType
    from apps.notifications.services import notify

    par_societe = {}
    for v in report.new:
        if v.gravite == GRAVITE_INFO:
            continue
        par_societe.setdefault(v.company_id, []).append(v)
    emises = 0
    for company_id, violations in par_societe.items():
        company = Company.objects.filter(pk=company_id).first()
        if company is None:
            continue
        titre = (f'Audit de cohérence : {len(violations)} nouvelle(s) '
                 'incohérence(s) détectée(s)')
        corps = corps_digest(violations)
        for admin in CustomUser.admins_actifs_qs(company).distinct():
            if notify(admin, EventType.DIGEST, titre, body=corps,
                      company=company) is not None:
                emises += 1
    return emises
