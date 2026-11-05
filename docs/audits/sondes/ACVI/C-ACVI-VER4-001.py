# flake8: noqa  (sonde de contre-visite ACVI, rejouable par scripts/sonde.py — AMET93)
"""ACVI43 (D-ACVI-6 : l'opposition suit la personne) — jumeau de levée : `cadence_signaux.py::
_lever_opposition_a_la_demande_du_client` (ACRM63, rappel demandé depuis la proposition) décoche
`ne_plus_contacter` et écrit le registre SANS `retirer_empreintes_opposition` (seul
`leads_consentement.py::tracer_levee_opposition_registre` la retire). L'empreinte posée au STOP reste :
une nouvelle fiche au même numéro naît « ne plus contacter » alors que la personne a demandé un rappel.
Témoin : levée par la fiche (tracer_levee_opposition_registre) → fiche neuve contactable.
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ACVI-VER4-001", "sha": "64c9c7317",
         "attendu": "A opposée (STOP) puis rappel demandé (canal rappel) → A contactable, empreinte toujours là, C créée au même numéro née ne_plus_contacter=True ; témoin levée fiche → C2 contactable",
         "modeles": ["authentication.Company", "crm.Lead", "crm.EmpreinteOpposition", "crm.LeadActivity", "core.ConsentRecord"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from authentication.models import Company
    from apps.crm.models import Lead, EmpreinteOpposition
    from apps.crm import leads_doublons
    from apps.crm.cadence_reponses import (
        CONSENT_SOURCE_OPPOSITION_TOUCHE, _marquer_lead_ne_plus_contacter, tracer_opposition_registre)
    from apps.crm.cadence_signaux import notify_client_contact_request
    from apps.crm.leads_consentement import tracer_levee_opposition_registre
    code_post_acvi43 = hasattr(leads_doublons, 'retirer_empreintes_opposition')
    co = Company.objects.create(nom='Sonde ACVI-VER4-001', slug='sonde-acvi-ver4-001')
    u = get_user_model().objects.create_user(username='sonde-acvi-ver4-001', password='x',
                                             role_legacy='responsable', company=co)

    def stop(numero, nom):
        a = Lead.objects.create(company=co, nom=nom, telephone=numero, owner=u)
        _marquer_lead_ne_plus_contacter(a, u)
        tracer_opposition_registre(a, source=CONSENT_SOURCE_OPPOSITION_TOUCHE)
        a.refresh_from_db()
        return a

    # Chemin observé : levée par « rappel demandé » (proposition publique).
    a = stop('+212612349701', 'A')
    emp_avant = EmpreinteOpposition.objects.filter(company=co).count()
    notify_client_contact_request('DEV-SONDE-VER4', a, canal='rappel')
    a.refresh_from_db()
    emp_apres = EmpreinteOpposition.objects.filter(company=co).count()
    c = Lead.objects.create(company=co, nom='C', telephone='+212612349701')
    # Témoin : levée par la fiche.
    a2 = stop('+212612349702', 'A2')
    Lead.objects.filter(pk=a2.pk).update(ne_plus_contacter=False)
    a2.refresh_from_db()
    tracer_levee_opposition_registre(a2, u)
    c2 = Lead.objects.create(company=co, nom='C2', telephone='+212612349702')
    obs = {'code_post_acvi43': code_post_acvi43, 'a_oppose_apres_rappel': a.ne_plus_contacter,
           'empreintes_avant_rappel': emp_avant, 'empreintes_apres_rappel': emp_apres,
           'c_nee_opposee': c.ne_plus_contacter, 'temoin_c2_nee_opposee': c2.ne_plus_contacter}
    print(obs)
    repro = (code_post_acvi43 and not a.ne_plus_contacter and c.ne_plus_contacter
             and not c2.ne_plus_contacter)
    return {'repro': repro, **obs}
