# flake8: noqa  (contre-visite de clôture ACVI du 04/11 soir : jumeau d'ACVI98)
"""C-ACVI-VER4-010 — ACVI98 ferme `crm/leads/<id>/whatsapp-devis(-apercu)/` vers un lead `ne_plus_contacter`
(D-ACVI-7 = refus_409 « sur tout rendu/envoi vers un opposé »). Le jumeau écran Devis
`ventes/devis/<id>/whatsapp-preview/` et `ventes/devis/<id>/whatsapp/` (`apps/ventes/views/devis_envoi.py`) ne lit
pas l'opposition. Société démo, transaction annulée. `repro: true` = la voie lead rend 409 MAIS la voie devis rend
un wa_url (et l'envoi marque le devis « envoyé »)."""
SONDE = {"constat": "C-ACVI-VER4-010", "sha": "64c9c7317",
         "attendu": "voie lead 409 ; voie devis 200 + wa_url, devis brouillon → envoye",
         "modeles": ["crm.Lead", "crm.Client", "ventes.Devis", "ventes.ShareLink", "crm.LeadActivity"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, Client
    from apps.ventes.models import Devis
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)

    def appel(url, corps):
        try:
            with transaction.atomic():
                r = api.post(url, corps, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                d = json.loads(txt)
            except Exception:
                d = {'_brut': txt[:200]}
            return r.status_code, d
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    cl = Client.objects.create(company=c, nom='Oppose VER4-010', telephone='0612349410')
    L = Lead.objects.create(company=c, nom='Oppose', prenom='VER4-010', telephone='0612349410', client=cl,
                            email='sonde-acvi-ver4-010@example.invalid', owner=ua)
    d = Devis.objects.create(company=c, reference='DEV-VER4-010', client=cl, lead=L,
                             statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20'), version=1)
    Lead.objects.filter(pk=L.pk).update(ne_plus_contacter=True)
    obs = {}
    s, r = appel(f'/api/django/crm/leads/{L.id}/whatsapp-devis-apercu/', {'devis_ids': [d.id]})
    obs['lead_apercu'] = [s, 'wa_url' in r, str(r.get('detail', ''))[:80]]
    s, r = appel(f'/api/django/ventes/devis/{d.id}/whatsapp-preview/', {})
    obs['devis_apercu'] = [s, (r.get('wa_url') or '')[:30], str(r.get('detail', ''))[:80]]
    s, r = appel(f'/api/django/ventes/devis/{d.id}/whatsapp/', {})
    d.refresh_from_db()
    obs['devis_envoi'] = [s, (r.get('wa_url') or '')[:30], str(r.get('detail', ''))[:80]]
    obs['devis_statut_apres'] = d.statut
    lead_409 = obs['lead_apercu'][0] == 409
    devis_ouvert = obs['devis_apercu'][0] == 200 or obs['devis_envoi'][0] == 200
    return {'repro': bool(lead_409 and devis_ouvert), 'observe': obs}
