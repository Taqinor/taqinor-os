# flake8: noqa  (seconde lentille L2 de C-ACVI-020, rejouable par scripts/sonde.py)
"""C-ACVI-020 L2 — autres chemins que la sonde 020 (société démo 1, transaction annulée).
(1) Fusion dans l'AUTRE sens par l'API : le SURVIVANT B est opposé (STOP par `repondre_ne_plus_contacter`),
l'absorbé A est vivant avec des touches ouvertes → B reste-t-il opposé et sans touche À FAIRE ?
(2) Porte en LOT : la commande CADV64 `fusionner_doublons_vrais --apply --ids` (survivant = étape la plus
avancée) sur un opposé A au stade NEW et son doublon B (même téléphone + même nom) au stade CONTACTED →
l'opposition de A survit-elle sur B ?"""
SONDE = {"constat": "C-ACVI-020-L2", "sha": "352ae5455",
         "attendu": "(1) B opposé, 0 touche à faire ; (2) défaut si B (survivant du lot) ne_plus_contacter=False",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape"]}


def sonde(ctx):
    import io
    import json
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.db import transaction
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm import stages
    from apps.crm.models import Lead
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.cadence_reponses import repondre_ne_plus_contacter
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    leads_url = reverse('lead-list')
    today = timezone.localdate()

    def appel(url, corps):
        try:
            with transaction.atomic():
                r = api.post(url, corps, format='json', HTTP_HOST='localhost')
            return r.status_code, r.content.decode('utf-8', 'replace')[:200]
        except Exception as e:
            return 599, repr(e)[:300]

    def a_faire(lead):
        return RelanceEtape.objects.filter(lead=lead, statut=RelanceEtape.Statut.A_FAIRE).count()

    def stop(lead):
        t = RelanceEtape.objects.create(company=c, lead=lead, cadence='contact', ordre=99, due_date=today,
                                        canal='whatsapp', template_cle='identite', statut='a_faire')
        repondre_ne_plus_contacter(t, ua)
        lead.refresh_from_db()

    # (1) survivant opposé
    tel = '+212600020120'
    B = Lead.objects.create(company=c, nom='SurvOppose', prenom='L2', telephone=tel, ville='Fès', owner=ua)
    A = Lead.objects.create(company=c, nom='AbsVivant', prenom='L2', telephone=tel, ville='Fès', owner=ua)
    RelanceEtape.objects.create(company=c, lead=A, cadence='contact', ordre=1, due_date=today,
                                canal='appel', template_cle='identite', statut='a_faire')
    stop(B)
    avant = {'B_npc': B.ne_plus_contacter, 'B_a_faire': a_faire(B), 'A_a_faire': a_faire(A)}
    s, txt = appel(f'{leads_url}{B.id}/merge/', {'others': [A.id]})
    B.refresh_from_db(); A.refresh_from_db()
    obs = {'sens_inverse': {'avant': avant, 'http': s, 'detail': txt if s >= 400 else '',
                            'B_npc_apres': B.ne_plus_contacter, 'B_a_faire_apres': a_faire(B),
                            'A_archive': A.is_archived, 'A_a_faire_apres': a_faire(A),
                            'B_first_contacted_at': str(B.first_contacted_at)}}
    # (2) lot CADV64
    tel2 = '+212600020121'
    A2 = Lead.objects.create(company=c, nom='Lotoppose', prenom='Hamid', telephone=tel2, ville='Oujda', owner=ua)
    B2 = Lead.objects.create(company=c, nom='Lotoppose', prenom='Hamid', telephone='0600020121', ville='Oujda',
                             owner=ua)
    stop(A2)
    Lead.objects.filter(pk=A2.pk).update(stage=stages.NEW)
    Lead.objects.filter(pk=B2.pk).update(stage=stages.CONTACTED)
    RelanceEtape.objects.filter(lead=B2).delete()
    out = io.StringIO()
    try:
        call_command('fusionner_doublons_vrais', '--company', str(c.pk), '--ids', str(A2.pk), '--apply', stdout=out)
        err = None
    except Exception as e:
        err = repr(e)[:300]
    A2.refresh_from_db(); B2.refresh_from_db()
    obs['lot_cadv64'] = {'erreur': err, 'sortie': out.getvalue()[-300:],
                         'A2_npc_avant': True, 'A2_archive': A2.is_archived,
                         'B2_npc_apres': B2.ne_plus_contacter, 'B2_a_faire_apres': a_faire(B2),
                         'B2_phone_normalise': B2.phone_normalise, 'A2_phone_normalise': A2.phone_normalise}
    obs['defauts'] = {
        'inverse_opposition_perdue_ou_touche': (not obs['sens_inverse']['B_npc_apres'])
        or obs['sens_inverse']['B_a_faire_apres'] > 0,
        'lot_opposition_perdue': A2.is_archived and not B2.ne_plus_contacter,
        'lot_touche_sur_survivant': A2.is_archived and obs['lot_cadv64']['B2_a_faire_apres'] > 0,
    }
    return {'repro': bool(obs['defauts']['lot_opposition_perdue'] or obs['defauts']['inverse_opposition_perdue_ou_touche']),
            'observe': obs}
