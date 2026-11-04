# flake8: noqa  (sonde de contre-visite VER1, rejouable par scripts/sonde.py)
"""C-ACVI-VER1-101 (ACVI21) — fusion d'un lead « ne plus contacter » : le survivant reste opposé SANS touche, y compris
quand l'étape la plus avancée de l'absorbé (QUOTE_SENT / SIGNED) change l'étape du survivant (le crochet
`lead_stage_changed` ne doit pas reposer une touche), et le survivant déjà opposé qui absorbe une fiche contactable
garde 0 touche. Société démo (demo_admin), API réelle `POST /crm/leads/<B>/merge/`, transaction annulée."""
SONDE = {"constat": "C-ACVI-VER1-101", "sha": "06ced8b1a",
         "attendu": "survivant opposé, 0 RelanceEtape À FAIRE après fusion dans les 3 scénarios (défaut : une touche posée)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape"]}


def sonde(ctx):
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from rest_framework.test import APIClient
    from apps.crm import stages
    from apps.crm.models import Lead
    from apps.crm.models_cadence import RelanceEtape
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    leads_url = reverse('lead-list')
    etapes = []

    def fusion(nom, surv, absorbe):
        try:
            with transaction.atomic():
                r = api.post(f'{leads_url}{surv.id}/merge/', {'others': [absorbe.id]}, format='json',
                             HTTP_HOST='localhost')
            etapes.append((nom, r.status_code, r.content.decode('utf-8', 'replace')[:160] if r.status_code >= 400 else ''))
            return r.status_code
        except Exception as e:
            etapes.append((nom, 599, repr(e)[:300]))
            return 599

    def etat(lead):
        lead.refresh_from_db()
        ts = RelanceEtape.objects.filter(lead=lead)
        return {'stage': lead.stage, 'oppose': lead.ne_plus_contacter,
                'a_faire': ts.filter(statut=RelanceEtape.Statut.A_FAIRE).count(),
                'toutes': [(t.cadence, t.statut) for t in ts.order_by('id')]}

    res = {}
    scenarios = (('quote_sent', '+212600101001', stages.QUOTE_SENT, True, False),
                 ('signed', '+212600101002', stages.SIGNED, True, False),
                 ('survivant_deja_oppose', '+212600101003', stages.NEW, False, True))
    for nom, tel, stage_a, a_oppose, b_oppose in scenarios:
        a = Lead.objects.create(company=c, nom='Absorbe', prenom='VER101' + nom, telephone=tel, owner=ua)
        b = Lead.objects.create(company=c, nom='Survivant', prenom='VER101' + nom, telephone=tel, owner=ua)
        Lead.objects.filter(pk=a.pk).update(stage=stage_a, ne_plus_contacter=a_oppose)
        Lead.objects.filter(pk=b.pk).update(ne_plus_contacter=b_oppose)
        http = fusion(nom, b, a)
        res[nom] = {'http': http, 'survivant': etat(b)}
    defauts = {k: (v['http'] != 200 or not v['survivant']['oppose'] or v['survivant']['a_faire'] > 0)
               for k, v in res.items()}
    return {'repro': any(defauts.values()), 'observe': {'scenarios': res, 'defauts': defauts, 'etapes': etapes}}
