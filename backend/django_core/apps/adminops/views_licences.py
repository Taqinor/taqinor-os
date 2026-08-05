"""NTADM8/9/29 — Licences & sièges.

NTADM8 : statut d'usage des sièges (utilisés/max) — alimente la bannière NON
BLOQUANTE de l'écran Utilisateurs (le dépassement de quota n'empêche jamais la
création d'un compte, voir ``apps.adminops.receivers`` pour l'alerte de
franchissement).

NTADM9 : écran admin « Licences & sièges » — même endpoint, complété du
palier de licence (``CompanyProfile.plan``), des modules inclus et de
l'historique des changements de plan (réutilise ``SettingsAuditLog``, N55 —
jamais un second journal maison).

NTADM29 : export PDF imprimable du même statut (usage RH/direction interne),
via le moteur interne WeasyPrint (``core.pdf.render_pdf`` — JAMAIS le moteur
de devis, voir la règle #4 / ``apps.adminops.views.journal_admin_pdf_view``
pour le même patron).

Lecture seule, gardé Administrateur (``IsAdministrateur``, même pattern que le
reste de cette app) ; NTADM39 affine l'accès fin (``adminops_licences_voir``,
rétrocompat rôles système — voir ``permissions.py``)."""
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.parametres.models import CompanyProfile
from authentication.services import sieges_utilises as _sieges_utilises

from .permissions import ADMINOPS_LICENCES_VOIR, IsAdministrateur, a_permission_fine


def _statut_sieges(company, profile):
    utilises = _sieges_utilises(company)
    max_sieges = profile.nb_sieges_max
    quota_atteint = bool(max_sieges) and utilises >= max_sieges
    return {
        'sieges_utilises': utilises,
        'sieges_max': max_sieges,
        'quota_atteint': quota_atteint,
    }


def _statut_plan(profile):
    plan = profile.plan
    if plan is None:
        return None
    return {
        'code': plan.code,
        'nom': plan.nom,
        'modules_inclus': list(plan.modules_inclus or []),
    }


def _historique_plan(company):
    """NTADM9 — historique des changements de plan (réutilise
    ``SettingsAuditLog`` N55, section 'licence', jamais un second journal)."""
    from apps.parametres.models import SettingsAuditLog
    lignes = (
        SettingsAuditLog.objects
        .filter(company=company, section='licence', field='plan')
        .order_by('-timestamp')[:50]
    )
    return [
        {
            'ancien_plan': ligne.old_value,
            'nouveau_plan': ligne.new_value,
            'par': (ligne.user.get_full_name() or ligne.user.username) if ligne.user else '',
            'le': ligne.timestamp.isoformat() if ligne.timestamp else None,
        }
        for ligne in lignes
    ]


@api_view(['GET'])
@permission_classes([IsAdministrateur])
def licence_statut_view(request):
    """NTADM8/9 — statut de licence complet : plan, modules inclus, sièges
    utilisés/max, historique des changements de plan."""
    # NTADM39 — resserrement fin (au-delà de IsAdministrateur, déjà acquis).
    if not a_permission_fine(request.user, ADMINOPS_LICENCES_VOIR):
        return Response(
            {'detail': "Permission 'adminops_licences_voir' requise."},
            status=403)
    company = request.user.company
    profile = CompanyProfile.get(company=company)
    return Response({
        'plan': _statut_plan(profile),
        **_statut_sieges(company, profile),
        'historique_plan': _historique_plan(company),
    })


def _comptes_actifs_nominatifs(company):
    """NTADM29 — liste nominative des comptes ACTIFS avec dernière connexion
    (usage RH/direction interne, jamais un export client-facing)."""
    from authentication.models import CustomUser
    comptes = (
        CustomUser.objects
        .filter(company=company, is_active=True)
        .order_by('username')
    )
    return [
        {
            'username': u.username,
            'nom_complet': u.get_full_name() or '',
            'derniere_connexion': (
                timezone.localtime(u.last_login).strftime('%Y-%m-%d %H:%M')
                if u.last_login else 'Jamais connecté'),
        }
        for u in comptes
    ]


@api_view(['GET'])
@permission_classes([IsAdministrateur])
def licence_pdf_view(request):
    """NTADM29 — instantané daté imprimable : plan, sièges utilisés/max, liste
    nominative des comptes actifs + dernière connexion. Moteur interne
    WeasyPrint (``core.pdf.render_pdf``) — jamais le moteur de devis."""
    # NTADM39 — même resserrement fin que licence_statut_view (l'export PDF
    # est aussi une forme de consultation de la licence).
    if not a_permission_fine(request.user, ADMINOPS_LICENCES_VOIR):
        return Response(
            {'detail': "Permission 'adminops_licences_voir' requise."},
            status=403)
    from core.pdf import render_pdf

    company = request.user.company
    profile = CompanyProfile.get(company=company)
    plan = _statut_plan(profile)
    sieges = _statut_sieges(company, profile)
    comptes = _comptes_actifs_nominatifs(company)

    lignes_comptes = ''.join(
        f'<tr><td>{c["username"]}</td><td>{c["nom_complet"]}</td>'
        f'<td>{c["derniere_connexion"]}</td></tr>'
        for c in comptes)
    plan_html = (
        f'{plan["nom"]} ({plan["code"]})' if plan else 'Aucun plan assigné — accès complet')
    sieges_max_html = (
        sieges['sieges_max'] if sieges['sieges_max'] is not None else 'illimité')
    genere_le = timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')
    html = f'''<html><body>
    <h1>Utilisation des sièges</h1>
    <p>Société : {company.nom} — généré le {genere_le}</p>
    <p>Plan de licence : {plan_html}</p>
    <p>Sièges utilisés : {sieges["sieges_utilises"]} / {sieges_max_html}</p>
    <table border="1" cellpadding="4">
      <thead><tr><th>Utilisateur</th><th>Nom complet</th><th>Dernière connexion</th></tr></thead>
      <tbody>{lignes_comptes}</tbody>
    </table>
    </body></html>'''
    pdf_bytes = render_pdf(html=html, company=company)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="utilisation-sieges.pdf"'
    return response
