# flake8: noqa  (sonde de vérification C-L2-2, rejouable par scripts/sonde.py)
"""C-L2-2 — POST envoyer-email : toute exception du rendu de la pièce jointe est avalée, le mail « ci-joint »
part SANS PDF, la réponse est 200 et le devis passe « envoyé ». (A) cas naturel : brouillon panneaux + structure,
sans onduleur (rendu « full » refusé par la règle dure) — le rendu est espionné (exception relevée) ;
(B) devis avec onduleur, rendu patché pour lever. Mail en mémoire (locmem). Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-009", "sha": "1dfa7986c",
         "attendu": "rendu en échec → refus nommé, devis brouillon (ou mail sans « ci-joint » + avertissement) ; défaut : 200, mail sans PDF, envoyé",
         "modeles": ["ventes.Devis", "ventes.EmailLog", "ventes.ShareLink"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.core import mail
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes import quote_engine
    from apps.ventes.models import Devis, EmailLog
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 009', slug='sonde-advs-009')
    u = U.objects.create_user(username='sonde-advs-009', password='x', role_legacy='responsable', company=c)
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS009-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    st = Produit.objects.create(company=c, nom='Structure aluminium toiture', sku='ADVS009-S',
                                prix_vente=Decimal('300'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS009-O',
                                 prix_vente=Decimal('14000'), tva=Decimal('20'), quantite_stock=100)
    api = APIClient()
    api.force_authenticate(u)
    vrai_rendu = quote_engine.generate_premium_devis_pdf
    if not hasattr(mail, 'outbox'):
        mail.outbox = []
    obs = {}

    def creer(cas, lignes):
        cl = Client.objects.create(company=c, nom='Envoi', prenom=cas, email=f'sonde-advs-009-{cas}@example.invalid')
        with transaction.atomic():
            r = api.post('/api/django/ventes/devis/atomic/', {'client': cl.id, 'taux_tva': '20.00', 'lignes': lignes},
                         format='json', HTTP_HOST='localhost')
        return r.status_code, Devis.objects.filter(company=c, client=cl).first()

    def envoyer(dv, rendu):
        excs = []

        def espion(*a, **k):
            try:
                return rendu(*a, **k)
            except Exception as e:
                excs.append(repr(e)[:200])
                raise
        n0 = len(mail.outbox)
        try:
            with mock.patch.object(quote_engine, 'generate_premium_devis_pdf', side_effect=espion):
                with transaction.atomic():
                    r = api.post(f'/api/django/ventes/devis/{dv.id}/envoyer-email/', {}, format='json',
                                 HTTP_HOST='localhost')
            corps = json.loads(r.content.decode('utf-8', 'replace') or '{}')
            http = r.status_code
        except Exception as e:
            http, corps = 599, {'_exc': repr(e)[:300]}
        dv.refresh_from_db()
        nouveaux = mail.outbox[n0:]
        m = nouveaux[0] if nouveaux else None
        log = EmailLog.objects.filter(devis=dv).order_by('-id').first()
        return {'http': http, 'detail': corps.get('detail'), 'exceptions_rendu': excs,
                'mails': len(nouveaux),
                'pieces_jointes': len(getattr(m, 'attachments', []) or []) if m else None,
                'corps_ci_joint': ('ci-joint' in (m.body or '').lower()) if m else None,
                'corps_extrait': (m.body or '')[:120] if m else None,
                'emaillog': [log.statut, log.piece_jointe] if log else None,
                'statut_devis': dv.statut, 'date_envoi': str(dv.date_envoi)}

    # (A) naturel : sans onduleur
    s, dva = creer('A', [{'produit': pan.id, 'designation': pan.nom, 'quantite': '8', 'prix_unitaire': '1166.67', 'taux_tva': '20'},
                         {'produit': st.id, 'designation': st.nom, 'quantite': '1', 'prix_unitaire': '300.00', 'taux_tva': '20'}])
    obs['A_creation'] = s
    if dva is not None:
        obs['A_sans_onduleur'] = envoyer(dva, vrai_rendu)

    # (B) avec onduleur, rendu patché pour échouer
    def panne(*a, **k):
        raise ValueError('rendu en échec (sonde)')
    s, dvb = creer('B', [{'produit': pan.id, 'designation': pan.nom, 'quantite': '12', 'prix_unitaire': '1166.67', 'taux_tva': '20'},
                         {'produit': ond.id, 'designation': ond.nom, 'quantite': '1', 'prix_unitaire': '14000.00', 'taux_tva': '20'}])
    obs['B_creation'] = s
    if dvb is not None:
        obs['B_rendu_patche'] = envoyer(dvb, panne)

    def defaut(o):
        return bool(o) and o['http'] == 200 and o['mails'] == 1 and o['pieces_jointes'] == 0 and o['statut_devis'] == 'envoye'
    repro = defaut(obs.get('A_sans_onduleur')) or defaut(obs.get('B_rendu_patche'))
    return {'repro': repro, 'observe': obs}
