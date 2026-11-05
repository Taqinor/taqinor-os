# flake8: noqa  (sonde de contre-visite ACVI, rejouable par scripts/sonde.py — AMET93)
"""ACVI90/ACVI44 — `scripts/check_garde_contact.py::LISTE_BLANCHE` motive
`views_assistant.py::lead_brouillon_suivi::wa.me` « A CORRIGER (ACVI89/ACVI98) », mais ni ACVI89 (visite)
ni ACVI98 (devis) ne touchent ce site : le brouillon de SUIVI de l'assistant (AIC32) rend un lien wa.me
prêt à envoyer vers un lead `ne_plus_contacter`. Témoin : `GET relance-etapes/<id>/message/` du même lead
→ 409 (garde ACVI44). Chaîne API réelle (responsable). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ACVI-VER4-002", "sha": "64c9c7317",
         "attendu": "POST /api/django/crm/leads/<opposé>/brouillon-suivi/ {canal whatsapp, objectif relance_devis} → 200 avec lien_wa_me non nul ; attendu sain : 409 nommé comme ACVI44",
         "modeles": ["authentication.Company", "crm.Lead", "crm.LeadActivity", "crm.RelanceEtape"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    co = Company.objects.create(nom='Sonde ACVI-VER4-002', slug='sonde-acvi-ver4-002')
    u = get_user_model().objects.create_user(username='sonde-acvi-ver4-002', password='x',
                                             role_legacy='responsable', company=co)
    lead = Lead.objects.create(company=co, nom='Oppose', prenom='Karim', telephone='+212612349711', owner=u)
    Lead.objects.filter(pk=lead.pk).update(ne_plus_contacter=True)
    api = APIClient()
    api.force_authenticate(u)
    r = api.post(f'/api/django/crm/leads/{lead.pk}/brouillon-suivi/',
                 {'canal': 'whatsapp', 'objectif': 'relance_devis', 'langue': 'fr'},
                 format='json', HTTP_HOST='localhost')
    data = r.data if hasattr(r, 'data') else None
    lien = (data or {}).get('lien_wa_me') if isinstance(data, dict) else None
    obs = {'status': r.status_code, 'lien_wa_me': lien,
           'detail': (data if r.status_code >= 400 else None)}
    print(obs)
    repro = r.status_code == 200 and bool(lien) and 'wa.me' in str(lien)
    return {'repro': repro, **obs}
