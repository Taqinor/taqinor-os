# flake8: noqa  (sonde d'audit parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""G2 : `core/numbering.py::_period_segment` prend le mois de `timezone.now()` (UTC) alors que
`apps/ventes/domain/facturation_ops.py::emettre_facture` date l'émission par `timezone.localdate()`
(Africa/Casablanca). Horloge figée (`django.utils.timezone.now` remplacé) à deux instants « 23:30 UTC du dernier
jour du mois » : 30/06/2026 (Casablanca à +01 d'après le tzdata du conteneur) et 30/11/2026 (+00). La sonde imprime
aussi le décalage réel du fuseau sur 2026-2027 (zoneinfo du conteneur). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-061", "sha": "56d5b623a",
         "attendu": "horloge 2026-06-30 23:30 UTC (= 01/07 00:30 Casablanca si +01) → date_emission 2026-07-01, référence FAC-202606-… (mois UTC) ; sain : FAC-202607-… ; horloge 2026-11-30 23:30 UTC : aucun écart si le fuseau est à +00",
         "modeles": ["authentication.Company", "facturation.Facture"]}


def sonde(ctx):
    import datetime as dt
    from decimal import Decimal
    from unittest import mock
    from zoneinfo import ZoneInfo
    from django.conf import settings
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture
    from apps.ventes.domain.facturation_ops import emettre_facture
    z = ZoneInfo(settings.TIME_ZONE)
    # Table des décalages (transitions) 2026-01 → 2028-01
    t = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    prev, transitions = None, []
    while t < dt.datetime(2028, 1, 1, tzinfo=dt.timezone.utc):
        o = t.astimezone(z).utcoffset()
        if o != prev:
            transitions.append((t.isoformat(), str(o)))
            prev = o
        t += dt.timedelta(hours=1)
    co = Company.objects.create(nom='Sonde AARG-061', slug='sonde-aarg-061')
    cl = Client.objects.create(company=co, nom='Tazi', prenom='Omar', email='g2-aarg061@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AARG-061', prix_vente=Decimal('1000'), quantite_stock=0)
    obs = {'TIME_ZONE': settings.TIME_ZONE, 'transitions': transitions}
    cas = {}
    for nom, instant in (('juin', dt.datetime(2026, 6, 30, 23, 30, tzinfo=dt.timezone.utc)),
                         ('novembre', dt.datetime(2026, 11, 30, 23, 30, tzinfo=dt.timezone.utc))):
        f = Facture.objects.create(company=co, reference=f'BROUILLON-SONDE-AARG61-{nom}', client=cl,
                                   statut=Facture.Statut.BROUILLON)
        LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
        f = Facture.objects.get(pk=f.pk)
        with mock.patch('django.utils.timezone.now', return_value=instant):
            from django.utils import timezone
            local = timezone.localdate()
            try:
                emettre_facture(f, source='sonde')
                err = None
            except Exception as exc:  # noqa
                err = repr(exc)
        f = Facture.objects.get(pk=f.pk)
        seg_attendu = f.date_emission.strftime('%Y%m') if f.date_emission else None
        cas[nom] = {'instant_utc': instant.isoformat(), 'localdate': local.isoformat(),
                    'offset': str(instant.astimezone(z).utcoffset()), 'erreur': err, 'statut': f.statut,
                    'reference': f.reference, 'date_emission': f.date_emission.isoformat() if f.date_emission else None,
                    'mois_attendu': seg_attendu, 'reference_au_bon_mois': bool(seg_attendu and seg_attendu in f.reference)}
    obs['cas'] = cas
    print(obs)
    repro = any(c['statut'] == 'emise' and not c['reference_au_bon_mois'] for c in cas.values())
    return {'repro': repro, **obs}
