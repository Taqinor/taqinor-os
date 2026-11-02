# flake8: noqa  (sonde de vérification C-L2-3, rejouable par scripts/sonde.py)
"""C-L2-3 — (1) VALIDITÉ : la pièce jointe d'envoyer-email est rendue AVANT mark_devis_sent, donc avec
`date_creation + quote_validity_days`, puis l'envoi (cadence après-devis → poser_validite_devis) pose une autre
`date_validite`. On capture `valid_until` du rendu de la pièce jointe (espion sur builder.build_quote_data) et on le
compare à la validité posée. (2) LIEN : le PDF d'un brouillon (celui que le partage natif envoie avant pdf-partage)
porte-t-il un lien « signer » ? Société neuve, transaction annulée, mail en mémoire."""
SONDE = {"constat": "C-ADVS-010", "sha": "1dfa7986c",
         "attendu": "valid_until imprimé = date_validite posée à l'envoi ; PDF partagé avec lien signer (défaut : dates différentes, aucun lien)",
         "modeles": ["ventes.Devis", "ventes.ShareLink", "ventes.EmailLog", "crm.Lead"]}


def sonde(ctx):
    import json
    from datetime import timedelta
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.core import mail
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.parametres.models import CompanyProfile
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine import builder
    if not hasattr(mail, 'outbox'):
        mail.outbox = []
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 010', slug='sonde-advs-010')
    prof = CompanyProfile.get(c)
    prof.quote_validity_days = 30
    prof.save()
    u = U.objects.create_user(username='sonde-advs-010', password='x', role_legacy='responsable', company=c)
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS010-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS010-O',
                                 prix_vente=Decimal('14000'), tva=Decimal('20'), quantite_stock=100)
    api = APIClient()
    api.force_authenticate(u)
    lignes = [{'produit': pan.id, 'designation': pan.nom, 'quantite': '12', 'prix_unitaire': '1166.67', 'taux_tva': '20'},
              {'produit': ond.id, 'designation': ond.nom, 'quantite': '1', 'prix_unitaire': '14000.00', 'taux_tva': '20'}]
    obs = {}

    def creer(cas):
        lead = Lead.objects.create(company=c, nom='Validite', prenom=cas, telephone='+21260001010' + cas[-1],
                                   ville='Casablanca', email=f'sonde-advs-010-{cas}@example.invalid')
        cl = Client.objects.create(company=c, nom='Validite', prenom=cas, email=f'sonde-advs-010-{cas}@example.invalid')
        with transaction.atomic():
            r = api.post('/api/django/ventes/devis/atomic/', {'client': cl.id, 'lead': lead.id, 'taux_tva': '20.00',
                                                             'lignes': lignes}, format='json', HTTP_HOST='localhost')
        dv = Devis.objects.filter(company=c, client=cl).first()
        return r.status_code, dv

    vrai = builder.build_quote_data
    captures = []

    def espion(*a, **k):
        d = vrai(*a, **k)
        captures.append({'valid_until': d.get('valid_until'), 'validity_days': d.get('validity_days'),
                         'links': sorted((d.get('links') or {}).keys()) if isinstance(d.get('links'), dict) else d.get('links')})
        return d

    # (1) e-mail : devis créé 20 jours avant l'envoi
    s, dv = creer('A1')
    obs['creation'] = s
    if dv is None:
        return {'repro': False, 'observe': obs}
    Devis.objects.filter(pk=dv.pk).update(date_creation=timezone.now() - timedelta(days=20), date_validite=None)
    dv.refresh_from_db()
    obs['date_creation'] = dv.date_creation.date().isoformat()
    with mock.patch.object(builder, 'build_quote_data', side_effect=espion):
        try:
            with transaction.atomic():
                r = api.post(f'/api/django/ventes/devis/{dv.id}/envoyer-email/', {}, format='json', HTTP_HOST='localhost')
            obs['envoi_http'] = r.status_code
        except Exception as e:
            obs['envoi_http'] = repr(e)[:200]
    dv.refresh_from_db()
    obs['rendu_piece_jointe'] = captures[:2]
    obs['statut'] = dv.statut
    obs['date_validite_posee'] = dv.date_validite.strftime('%d/%m/%Y') if dv.date_validite else None
    imprime = captures[0]['valid_until'] if captures else None
    obs['valid_until_imprime'] = imprime
    # re-rendu après envoi (page /proposition, tout re-rendu)
    try:
        with transaction.atomic():
            d2 = vrai(dv)
        obs['valid_until_rerendu'] = d2.get('valid_until')
    except Exception as e:
        obs['valid_until_rerendu'] = repr(e)[:160]
    # (1 bis) devis créé LE JOUR de l'envoi : PDF = J+30, serveur = date posée par la cadence
    s, dv0 = creer('A0')
    if dv0 is not None:
        captures.clear()
        with mock.patch.object(builder, 'build_quote_data', side_effect=espion):
            try:
                with transaction.atomic():
                    r = api.post(f'/api/django/ventes/devis/{dv0.id}/envoyer-email/', {}, format='json', HTTP_HOST='localhost')
                obs['jour_meme_http'] = r.status_code
            except Exception as e:
                obs['jour_meme_http'] = repr(e)[:200]
        dv0.refresh_from_db()
        obs['jour_meme'] = {'imprime': captures[0]['valid_until'] if captures else None,
                            'pose': dv0.date_validite.strftime('%d/%m/%Y') if dv0.date_validite else None}
        try:
            from apps.ventes.utils.expiry import is_expired
            veille_imprime = None
            if captures and captures[0]['valid_until']:
                from datetime import datetime
                veille_imprime = datetime.strptime(captures[0]['valid_until'], '%d/%m/%Y').date() - timedelta(days=1)
                obs['jour_meme']['expire_la_veille_de_la_date_imprimee'] = is_expired(dv0, today=veille_imprime)
        except Exception as e:
            obs['jour_meme']['expire_err'] = repr(e)[:160]
    # (2) partage natif : PDF du brouillon puis pdf-partage
    s, dv2 = creer('B2')
    if dv2 is not None:
        try:
            with transaction.atomic():
                d3 = vrai(dv2)
            obs['brouillon_links'] = sorted((d3.get('links') or {}).keys()) if isinstance(d3.get('links'), dict) else d3.get('links')
            obs['brouillon_links_valeurs'] = {k: bool(v) for k, v in (d3.get('links') or {}).items()} if isinstance(d3.get('links'), dict) else None
        except Exception as e:
            obs['brouillon_links'] = repr(e)[:160]
        try:
            with transaction.atomic():
                r = api.post(f'/api/django/ventes/devis/{dv2.id}/pdf-partage/', {}, format='json', HTTP_HOST='localhost')
            obs['pdf_partage'] = [r.status_code, json.loads(r.content.decode() or '{}').get('devis_statut')]
        except Exception as e:
            obs['pdf_partage'] = repr(e)[:160]
    repro = bool(imprime and obs['date_validite_posee'] and imprime != obs['date_validite_posee'])
    return {'repro': repro, 'observe': obs}
