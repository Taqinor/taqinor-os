# flake8: noqa  (sonde de contre-visite ACVI, rejouable par scripts/sonde.py — AMET93)
"""ACVI53/ACVI54 — jumeau oublié : la file en masse (`fiche_funnel.py::_corps_whatsapp_en_masse`) rend tout
placeholder du catalogue et OMET la phrase d'un placeholder vide ; le brouillon de suivi de l'assistant
(`views_assistant.py::lead_brouillon_suivi`, rendu par `cadence_views.py::rendre_modele_message` +
4 `replace`) ne rend que prenom/ville/lien/lien_rdv/conseiller/marque/civilite/reference et n'omet rien :
un gabarit ACCEPTÉ par `MessageTemplateSerializer.validate_corps` (ACVI53) laisse `{societe}`,
`{date_validite}` littéraux dans `texte` et dans `lien_wa_me` ; conseiller sans prénom (ACVI54) → « je suis  de ».
Chaîne API réelle (admin crée le gabarit, responsable demande le brouillon). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ACVI-VER4-020", "sha": "64c9c7317",
         "attendu": "POST message-templates (admin) corps avec {societe} {date_validite} → 201 ; POST leads/<id>/brouillon-suivi/ → 200 avec '{societe}' ou '{date_validite}' littéral dans texte et lien_wa_me ; la file en masse, même gabarit : aucun '{' ; attendu sain : aucun '{' dans le brouillon",
         "modeles": ["authentication.Company", "crm.Lead", "crm.LeadActivity", "crm.MessageTemplate", "crm.RelanceEtape"]}


def sonde(ctx):
    import inspect
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import cadence_messages, serializers_cadence
    from apps.crm.fiche_funnel import _corps_whatsapp_en_masse
    from apps.crm.models import Lead, MessageTemplate
    # Le conteneur porte-t-il bien ACVI53 + ACVI54 ?
    code_ok = (hasattr(serializers_cadence.MessageTemplateSerializer, 'validate_corps')
               and 'username' not in inspect.getsource(cadence_messages._nom_affiche_conseiller))
    User = get_user_model()
    co = Company.objects.create(nom='Sonde ACVI-VER4-020', slug='sonde-acvi-ver4-020')
    admin = User.objects.create_user(username='sonde-acvi-ver4-020-adm', password='x',
                                     role_legacy='admin', company=co)
    resp = User.objects.create_user(username='sonde-acvi-ver4-020-resp', password='x',
                                    role_legacy='responsable', company=co, first_name='')
    lead = Lead.objects.create(company=co, nom='Alami', prenom='Karim', telephone='+212612349720',
                               owner=resp)
    api_a = APIClient(); api_a.force_authenticate(admin)
    corps = ("Bonjour {prenom}, je suis {conseiller} de {societe}. "
             "Votre devis reste valable jusqu'au {date_validite}. Bonne journée.")
    r = api_a.post('/api/django/crm/message-templates/',
                   {'nom': 'Relance devis sonde', 'langue': 'fr', 'corps': corps},
                   format='json', HTTP_HOST='localhost')
    creation = (r.status_code, r.data if r.status_code >= 400 else None)
    if r.status_code != 201:
        return {'repro': False, 'code_ok': code_ok, 'creation': creation}
    api_r = APIClient(); api_r.force_authenticate(resp)
    r = api_r.post(f'/api/django/crm/leads/{lead.pk}/brouillon-suivi/',
                   {'canal': 'whatsapp', 'objectif': 'relance_devis', 'langue': 'fr'},
                   format='json', HTTP_HOST='localhost')
    data = r.data if isinstance(getattr(r, 'data', None), dict) else {}
    texte = data.get('texte') or ''
    lien = data.get('lien_wa_me') or ''
    tpl = MessageTemplate.objects.get(company=co, nom='Relance devis sonde')
    masse = _corps_whatsapp_en_masse(lead, tpl)
    obs = {'code_ok': code_ok, 'creation': creation, 'status': r.status_code,
           'modele_source': data.get('modele_source'), 'texte': texte,
           'lien_contient_accolade': '%7B' in lien or '{' in lien, 'masse': masse}
    print(obs)
    repro = (code_ok and r.status_code == 200 and data.get('modele_source') == 'Relance devis sonde'
             and '{' in texte and '{' not in masse)
    return {'repro': repro, **obs}
