SONDE = {"constat": "C-ASEC-025", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : devis envoyé de A, lien otp_lecture ; N1 demande puis vérifie le code -> "
                    "preuve ; N2 sans X-Proposition-Preuve -> 403 otp_required sur data, suivi, accept et "
                    "activer-option, aucune DevisSignature, devis toujours envoyé, option intacte ; preuve de N1 "
                    "présentée sur le lien de B -> 403 ; N1 avec la preuve -> 200 lecture puis 200 signature"}


def sonde(ctx):
    import random
    import uuid
    from decimal import Decimal
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.domain.cycle_vie import _otp_lecture_cache_key
    from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink
    from apps.ventes.public.signature_views import empreinte_contenu
    from django.core.cache import cache
    BASE = '/api/django/public/proposal'

    def devis_lien(co, tag):
        cl = Client.objects.create(company=co, nom='OtpSonde', prenom=tag, email=f'asec025{tag}@sonde.invalid',
                                   telephone='')
        d = Devis.objects.create(company=co, reference=f'SONDE-ASEC025-{tag}-{co.pk}', client=cl, statut='envoye',
                                 taux_tva=Decimal('20'))
        for desig, qty, pu in (('Onduleur réseau Deye 8kW', '1', '14000'),
                               ('Panneau Canadian Solar 550W', '10', '1400')):
            p = Produit.objects.create(company=co, nom=desig, sku=f'sonde-asec025-{tag}-{desig[:8]}',
                                       prix_vente=Decimal(pu), quantite_stock=50)
            LigneDevis.objects.create(devis=d, produit=p, designation=desig, quantite=Decimal(qty),
                                      prix_unitaire=Decimal(pu), remise=Decimal('0'))
        opt = LigneDevis.objects.create(devis=d, designation='Batterie supplémentaire 5 kWh', quantite=Decimal('1'),
                                        prix_unitaire=Decimal('12000'), remise=Decimal('0'), optionnelle=True)
        lien = ShareLink.objects.create(company=co, devis=d, token=str(uuid.uuid4()), otp_lecture=True,
                                        niveau=ShareLink.NIVEAU_CONFIANCE)
        return d, opt, lien

    a = Company.objects.create(nom='Sonde ASEC025 a', slug='sonde-asec025-a')
    b = Company.objects.create(nom='Sonde ASEC025 b', slug='sonde-asec025-b')
    da, opt_a, la = devis_lien(a, 'a')
    db_, _, lb = devis_lien(b, 'b')
    ip = '192.0.2.%d' % random.randint(2, 250)
    n1 = APIClient(HTTP_HOST='localhost', REMOTE_ADDR=ip)
    n2 = APIClient(HTTP_HOST='localhost', REMOTE_ADDR=ip)

    def code(r):
        return r.data.get('detail') if isinstance(getattr(r, 'data', None), dict) else None

    def corps(d, lien):
        return {'nom': 'M. Client', 'consent_esign': True, 'empreinte_contenu': empreinte_contenu(d, link=lien)}

    dem = n1.post(f'{BASE}/{la.token}/otp-lecture/demander/')
    otp = cache.get(_otp_lecture_cache_key(la.token))
    ver = n1.post(f'{BASE}/{la.token}/otp-lecture/verifier/', {'otp_code': otp}, format='json')
    preuve = ver.data.get('preuve') if isinstance(ver.data, dict) else None
    n1.credentials(HTTP_X_PROPOSITION_PREUVE=preuve or '')
    gestes = {'n1_demander': dem.status_code, 'code_en_cache': otp is not None,
              'n1_verifier': ver.status_code, 'preuve_emise': bool(preuve)}
    sig_avant = DevisSignature.objects.filter(devis__in=[da, db_]).count()
    refus = []
    for nom, r in (('n2_data', n2.get(f'{BASE}/{la.token}/data/')),
                   ('n2_suivi', n2.get(f'/api/django/public/suivi/{la.token}/')),
                   ('n2_accept', n2.post(f'{BASE}/{la.token}/accept/', corps(da, la), format='json')),
                   ('n2_activer_option', n2.post(f'{BASE}/{la.token}/activer-option/', {'ligne_id': opt_a.id},
                                                 format='json')),
                   ('n1_preuve_sur_lien_b', n1.post(f'{BASE}/{lb.token}/accept/', corps(db_, lb), format='json'))):
        gestes[nom] = [r.status_code, code(r)]
        refus.append(r.status_code == 403 and code(r) == 'otp_required')
    da.refresh_from_db()
    db_.refresh_from_db()
    opt_a.refresh_from_db()
    sig_apres_refus = DevisSignature.objects.filter(devis__in=[da, db_]).count()
    persistance = {'signatures_avant': sig_avant, 'signatures_apres_refus': sig_apres_refus,
                   'devis_a_statut': da.statut, 'devis_b_statut': db_.statut, 'option_a_optionnelle': opt_a.optionnelle}
    lecture = n1.get(f'{BASE}/{la.token}/data/')
    suivi = n1.get(f'/api/django/public/suivi/{la.token}/')
    signe = n1.post(f'{BASE}/{la.token}/accept/', corps(da, la), format='json')
    da.refresh_from_db()
    legit = {'n1_data': lecture.status_code, 'n1_suivi': suivi.status_code, 'n1_accept': signe.status_code,
             'devis_a_statut_apres': da.statut,
             'signatures_a': DevisSignature.objects.filter(devis=da).count()}
    out = {'gestes': gestes, 'persistance': persistance, 'legitime': legit}
    out['repro'] = bool(gestes['n1_verifier'] == 200 and preuve and all(refus)
                        and sig_apres_refus == sig_avant == 0 and persistance['devis_a_statut'] == 'envoye'
                        and persistance['devis_b_statut'] == 'envoye' and opt_a.optionnelle
                        and lecture.status_code == 200 and suivi.status_code == 200 and signe.status_code == 200
                        and legit['signatures_a'] == 1)
    return out
