# flake8: noqa  (sonde de contre-visite vérifie AANA 04/11, lot 3 ; rejouable par scripts/sonde.py — AMET93)
"""AANA73 (jumeau oublié) : `apps/dataimport/services.py::FIELD_MAPS` mappe encore pour la cible `factures`
`date_emission`/`date` et `statut_paiement` (et `date_creation` pour `devis`), que
`apps/ventes/domain/imports.py::creer_facture_import` / `creer_devis_import` ne lisent jamais : la colonne est
annoncée MAPPÉE au dry-run puis ignorée au commit — une facture migrée « posted » du 01/03/2024 naît datée
d'aujourd'hui, échéance aujourd'hui + 30 j. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AANA-VER4-020", "sha": "d54c88db3",
         "attendu": "dry-run factures : date_emission absente de non_mappees ; commit : facture créée avec date_emission = aujourd'hui (≠ 2024-03-01)",
         "modeles": ["authentication.Company", "crm.Client", "facturation.Facture", "dataimport.ImportJob"]}


def sonde(ctx):
    import inspect
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Facture
    from apps.dataimport import services as ds
    from apps.ventes.domain import imports as imp
    co = Company.objects.create(nom='Sonde AANA-VER4-020', slug='sonde-aana-ver4-020')
    u = get_user_model().objects.create_user(username='sonde-aana-ver4-020', password='x',
                                             role_legacy='responsable', company=co)
    Client.objects.create(company=co, nom='Client Migré', email='migre-ver4020@example.invalid')
    csv = ('reference,client_email,statut,date_emission,statut_paiement\n'
           'OD-2024-001,migre-ver4020@example.invalid,posted,2024-03-01,paid\n').encode()
    code_a_jour = ('montant_ttc_source' not in str(ds.FIELD_MAPS.get('factures')),
                   'statut source non reconnu' in inspect.getsource(imp.creer_facture_import))
    dry = ds.dry_run(csv, 'f.csv', 'factures', company=co, user=u)
    avant = set(Facture.objects.filter(company=co).values_list('pk', flat=True))
    res = ds.commit(csv, 'f.csv', 'factures', co, u)
    nouvelles = Facture.objects.filter(company=co).exclude(pk__in=avant)
    f = nouvelles.first()
    obs = {
        'code_aana73_aana70_present': code_a_jour,
        'dry_non_mappees': dry.get('non_mappees'),
        'dry_colonnes': dry.get('mapping') or dry.get('columns'),
        'commit_created': res.get('created'), 'commit_skipped': res.get('skipped'),
        'facture': None if f is None else {
            'reference': f.reference, 'statut': f.statut,
            'date_emission': str(f.date_emission), 'date_echeance': str(f.date_echeance)},
        'aujourdhui': str(timezone.localdate()),
    }
    print(obs)
    repro = (f is not None and 'date_emission' not in (dry.get('non_mappees') or [])
             and str(f.date_emission) != '2024-03-01')
    return {'repro': repro, **obs}
