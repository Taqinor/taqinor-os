# flake8: noqa  (contre-visite de clôture ACVI du 05/11 : jumeaux d'envoi du devis vers un opposé)
"""C-ACVI-VER4-012 — D-ACVI-7 = refus 409 de tout rendu/envoi de devis vers un lead `ne_plus_contacter`
(D-ACVI-10 : un signé reçoit le contractuel, jamais un DEVIS). Les gestes de `apps/ventes/views/devis_envoi.py`
(`envoyer-email`, `share-link {envoi: true}`, `pdf-partage` POST/GET) et `apps/crm/views.py::LeadViewSet.resume_associe`
lisent-ils l'opposition ? Même montage que C-ACVI-VER4-010 (lead opposé + devis brouillon). Société démo, transaction
annulée, mail en mémoire. Si le rendu réel du PDF échoue (pdf_refuse / 502), l'envoi e-mail est rejoué avec le moteur
remplacé par un bouchon (pour juger la seule garde d'opposition). `repro: true` = au moins un geste aboutit (200)."""
SONDE = {"constat": "C-ACVI-VER4-012", "sha": "64c9c7317",
         "attendu": "envoyer-email 200 + 1 mail + envoye ; share-link envoi 200 + envoye ; pdf-partage 200 + envoye ; resume-associe 200 + wa_url vers l'associé",
         "modeles": ["crm.Lead", "crm.Client", "ventes.Devis", "ventes.ShareLink", "crm.LeadActivity", "ventes.EmailLog"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.core import mail
    from django.db import transaction
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, Client
    from apps.ventes.models import Devis
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)

    def appel(methode, url, corps=None):
        avant = len(getattr(mail, 'outbox', []))
        try:
            with transaction.atomic():
                r = getattr(api, methode)(url, corps or {}, format='json', HTTP_HOST='localhost')
            ct = r.get('Content-Type', '')
            if 'json' in ct:
                try:
                    d = json.loads(r.content.decode('utf-8', 'replace'))
                except Exception:
                    d = {}
            else:
                d = {'_ct': ct[:30]}
            return r.status_code, d, len(getattr(mail, 'outbox', [])) - avant
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}, 0

    cl = Client.objects.create(company=c, nom='Oppose VER4-012', telephone='0612349412',
                               email='sonde-acvi-ver4-012@example.invalid')
    L = Lead.objects.create(company=c, nom='Oppose', prenom='VER4-012', telephone='0612349412', client=cl,
                            email='sonde-acvi-ver4-012@example.invalid', owner=ua,
                            contact_secondaire_nom='Associe Sonde', contact_secondaire_telephone='0612349499')

    def devis(n):
        return Devis.objects.create(company=c, reference=f'DEV-VER4-012-{n}', client=cl, lead=L,
                                    statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20'), version=1)
    d1, d2, d3, d4 = devis('A'), devis('B'), devis('C'), devis('D')
    Lead.objects.filter(pk=L.pk).update(ne_plus_contacter=True)
    obs = {}
    B = '/api/django/ventes/devis'

    def court(r):
        return str(r.get('detail', '') or r.get('code', '') or r.get('_exc', '') or r.get('_ct', ''))[:90]

    # (a) envoyer-email — rendu réel d'abord
    s, r, m = appel('post', f'{B}/{d1.id}/envoyer-email/', {})
    d1.refresh_from_db()
    obs['a_email_reel'] = [s, r.get('code', ''), m, d1.statut, court(r)]
    if s != 200 and r.get('code') in ('pdf_refuse', 'pdf_indisponible'):
        with mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf', return_value='cle-bouchon'), \
                mock.patch('apps.ventes.utils.pdf.download_pdf', return_value=b'%PDF-1.4 bouchon'):
            s, r, m = appel('post', f'{B}/{d1.id}/envoyer-email/', {})
        d1.refresh_from_db()
        obs['a_email_bouchon'] = [s, r.get('code', ''), m, d1.statut, court(r)]
        if m:
            obs['a_destinataire'] = list(mail.outbox[-1].to)
    elif m:
        obs['a_destinataire'] = list(mail.outbox[-1].to)
    # (b) share-link {envoi: true}
    s, r, m = appel('post', f'{B}/{d2.id}/share-link/', {'envoi': True})
    d2.refresh_from_db()
    obs['b_share_link_envoi'] = [s, bool(r.get('token')), m, d2.statut, court(r)]
    # (c) pdf-partage POST (marque envoyé ?) puis GET (rendu du PDF à partager)
    s, r, m = appel('post', f'{B}/{d3.id}/pdf-partage/', {})
    d3.refresh_from_db()
    obs['c_pdf_partage_post'] = [s, m, d3.statut, court(r)]
    s, r, m = appel('get', f'{B}/{d4.id}/pdf-partage/')
    d4.refresh_from_db()
    obs['c_pdf_partage_get'] = [s, m, d4.statut, court(r)]
    # (d) resume-associe sur le lead opposé, avec un devis « envoyé »
    Devis.objects.filter(pk=d4.pk).update(statut=Devis.Statut.ENVOYE)
    s, r, m = appel('post', f'/api/django/crm/leads/{L.id}/resume-associe/',
                    {'devis_id': d4.id, 'accord_client': True})
    obs['d_resume_associe'] = [s, (r.get('wa_url') or '')[:40], r.get('phone', ''), m, court(r)]
    L.refresh_from_db()
    obs['lead_ne_plus_contacter_apres'] = L.ne_plus_contacter
    obs['mails_total_outbox'] = len(getattr(mail, 'outbox', []))
    ouverts = [k for k, v in obs.items() if isinstance(v, list) and v and v[0] == 200]
    obs['gestes_200'] = ouverts
    return {'repro': bool(ouverts), 'observe': obs}
