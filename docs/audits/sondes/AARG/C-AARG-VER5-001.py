# flake8: noqa  (sonde de contre-visite de clôture PA4 « Argent », rejouable par scripts/sonde.py — METHODE §C.4)
"""VER5 AARG2 (jumeau AARG35) : une facture soldée par paiement + RAS-TVA, annulée `garder_en_avance`
(AARG35 neutralise ses retenues : `annulee=True`), puis son avoir miroir annulé (AARG2 la restaure).
Then d'AARG2 : la facture redevient « payée », dû 0. Question : la retenue neutralisée à l'annulation
revient-elle à la restauration ? Sinon la facture rouvre pour le montant de la RAS déjà retenue par le
client (relançable). (T) témoin sans RAS : payée, dû 0. Fonctions réelles + vraie API `avoirs/<id>/annuler/`."""
SONDE = {"constat": "C-AARG-002", "sha": "2781a2049",
         "attendu": "repro si R : statut != payee ou dû 200 (RAS neutralisée non rendue) ; T : payee, dû 0",
         "modeles": ["ventes.Facture", "ventes.Avoir", "ventes.Paiement", "ventes.RetenueSubie"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Facture, Paiement, RetenueSubie
    from apps.ventes.domain import encaissements as enc, annulation_facture as ann
    from apps.ventes.domain.encaissements import (
        enregistrer_paiement, enregistrer_paiement_avec_retenue, recalculer_statut_paiement)
    from apps.ventes.domain.annulation_facture import annuler_facture
    try:
        from apps.ventes.recouvrement import facture_relancable
    except Exception:  # noqa
        facture_relancable = None
    H = {'HTTP_HOST': 'localhost'}
    base_code = {'AARG59_present': hasattr(enc, 'rendre_trop_percu_de_avoir'),
                 'ASTK262_present': hasattr(ann, '_retourner_stock_de_la_vente'),
                 'AARG2_present': hasattr(ann, 'rendre_avance_gardee')}
    co = Company.objects.create(nom='Sonde VER5 001', slug='sonde-ver5-001')
    u = get_user_model().objects.create_user(username='sonde_ver5_001', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='V501', email='v501@example.invalid')
    today = timezone.now().date()

    def mk(ref):
        return Facture.objects.create(company=co, reference=ref, client=cl, statut='emise', taux_tva=Decimal('20'),
                                      montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
                                      montant_ttc=Decimal('1200'), date_emission=today)

    def cycle(f):
        f = Facture.objects.get(pk=f.pk)
        avant = {'statut': f.statut, 'du': str(f.montant_du), 'paye': str(f.montant_paye),
                 'retenues': str(f.retenues_subies_total)}
        a = annuler_facture(f, user=u, directive={'action': 'garder_en_avance'}).avoir_annulation
        f = Facture.objects.get(pk=f.pk)
        apres_annul = {'statut': f.statut,
                       'retenues_annulees': list(RetenueSubie.objects.filter(facture=f).values_list('annulee', flat=True))}
        r = api.post(f'/api/django/ventes/avoirs/{a.id}/annuler/', {}, format='json', **H)
        f = Facture.objects.get(pk=f.pk)
        rel = None
        if facture_relancable is not None:
            try:
                rel = list(facture_relancable(f))[:1]
            except Exception as exc:  # noqa
                rel = f'err {exc!r}'[:80]
        return {'avant': avant, 'apres_annulation': apres_annul,
                'annuler_avoir_http': r.status_code,
                'detail': None if r.status_code < 400 else str(r.json())[:140],
                'statut': f.statut, 'paye': str(f.montant_paye), 'du': str(f.montant_du),
                'retenues_total': str(f.retenues_subies_total),
                'retenues_annulees': list(RetenueSubie.objects.filter(facture=f).values_list('annulee', flat=True)),
                'avances_libres': Paiement.objects.filter(facture__isnull=True, client=cl).exclude(
                    statut__in=Paiement.STATUTS_NON_COMPTES).count(),
                'relancable': rel}

    obs = {'base_code': base_code}
    # R — paiement 1 000 + RAS-TVA 100 % (200) : soldée
    fR = mk('FAC-V501-R')
    enregistrer_paiement_avec_retenue(facture=fR, montant=Decimal('1000'), date_paiement=today, mode='virement',
                                      type_retenue='ras_tva', taux=Decimal('100'), created_by=u)
    obs['R'] = cycle(fR)
    # T — témoin : paiement 1 200 sans RAS
    fT = mk('FAC-V501-T')
    enregistrer_paiement(facture=fT, montant=Decimal('1200'), mode='virement', date_paiement=today, user=u)
    recalculer_statut_paiement(fT, user=u)
    obs['T'] = cycle(fT)
    print(obs)
    r, t = obs['R'], obs['T']
    temoin_ok = t['annuler_avoir_http'] == 200 and t['statut'] == 'payee' and Decimal(t['du']) == 0
    defaut = r['avant']['statut'] == 'payee' and r['annuler_avoir_http'] == 200 and (
        r['statut'] != 'payee' or Decimal(r['du']) > 0)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
