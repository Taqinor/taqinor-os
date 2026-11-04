# flake8: noqa  (sonde de contre-visite vérifie ACHT du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ACHT32 : `field_sync.py::_instant_saisie` borne `client_ts` au PRÉSENT seulement (`min(saisie, now)`) :
aucune borne basse ni cohérence d'ordre (départ ≤ arrivée ≤ retour). L'horloge du téléphone fait donc foi
pour `arrivee_site_le` / `retour_depot_le`, d'où `field_capture.crew_time` (durée sur site) et la ligne
« Main-d'œuvre » de `ventes.domain.facturation_ops.generer_facture_intervention` (ZFSM4, CLAUSE CLIENT
d'ACHT32 : « la main-d'œuvre facturée suit la durée réelle sur site »).
Scénarios via l'API réelle `/installations/sync/` : (A) téléphone à l'horloge en retard d'un an (remise à
zéro) — check-in hors ligne daté d'il y a 365 j, retour à l'heure juste ; (B) deux terminaux de l'équipe :
check-in à H-1, retour saisi sur un téléphone en retard de 2 h (H-3) ; témoin : check-in H-3, retour H.
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ACHT-VER4-020", "sha": "fcbed3760",
         "modeles": ["installations.Intervention", "installations.Installation", "installations.FieldOp",
                     "crm.Client", "facturation.Facture", "ventes.Facture", "ventes.LigneFacture",
                     "stock.Produit", "parametres.CompanyProfile",
                     "authentication.Company", "authentication.User"],
         "attendu": "témoin : 180 min → MO 3,00 h ; (A) arrivée = il y a 365 j, durée ≈ 525 600 min → MO ≈ 8 760 h "
                    "facturées ; (B) retour < arrivée → durée −120 min → ligne MO à −2,00 h ; attendu sain : "
                    "client_ts hors fenêtre plausible ou incohérent ramené/refusé, MO = durée réelle"}


def sonde(ctx):
    import uuid
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, Intervention
    from apps.installations import field_capture
    from apps.parametres.models import CompanyProfile
    from apps.ventes.domain import facturation_ops

    co = Company.objects.create(nom='Sonde ACHT VER4-020', slug='sonde-acht-ver4-020')
    u = get_user_model().objects.create_user(username='sonde-acht-ver4-020', password='x', company=co,
                                             role_legacy='responsable')
    prof = CompanyProfile.get(co)
    prof.taux_horaire_sav = Decimal('300')
    prof.save(update_fields=['taux_horaire_sav'])
    cl = Client.objects.create(company=co, nom='Client', prenom='Sonde', email='acht-v4-020@example.invalid')
    inst = Installation.objects.create(company=co, reference='CH-SONDE-ACHT-V4-020', client=cl)
    api = APIClient()
    api.force_authenticate(u)
    now = timezone.now().replace(microsecond=0)

    def _iso(dt):
        import datetime as _d
        return dt.astimezone(_d.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    def _cas(ts_checkin, ts_retour):
        iv = Intervention.objects.create(company=co, installation=inst, type_intervention='pose', created_by=u,
                                         technicien=u, statut=Intervention.Statut.EN_ROUTE)
        ops = [{'op_type': 'intervention.checkin', 'client_op_id': str(uuid.uuid4()),
                'client_ts': _iso(ts_checkin), 'payload': {'intervention': iv.id}},
               {'op_type': 'intervention.retour', 'client_op_id': str(uuid.uuid4()),
                'client_ts': _iso(ts_retour), 'payload': {'intervention': iv.id}}]
        r = api.post('/api/django/installations/sync/', {'ops': ops}, format='json', HTTP_HOST='localhost')
        statuts = [x.get('status') for x in (r.json().get('results') or [])]
        iv.refresh_from_db()
        duree = field_capture.crew_time(iv)['duree_sur_site_min']
        mo = None
        err = None
        try:
            f = facturation_ops.generer_facture_intervention(intervention=iv, user=u)
            l = f.lignes.filter(designation="Main-d'œuvre").first()
            mo = (str(l.quantite), str(l.prix_unitaire)) if l else None
        except Exception as exc:  # observation, jamais un verdict
            err = f'{type(exc).__name__}: {exc}'
        return {'http': r.status_code, 'statuts': statuts,
                'arrivee': iv.arrivee_site_le.isoformat() if iv.arrivee_site_le else None,
                'retour': iv.retour_depot_le.isoformat() if iv.retour_depot_le else None,
                'duree_min': duree, 'mo_heures_taux': mo, 'err': err}

    temoin = _cas(now - timedelta(hours=3), now)
    a = _cas(now - timedelta(days=365), now)
    b = _cas(now - timedelta(hours=1), now - timedelta(hours=3))
    print(f'témoin={temoin}\nA(horloge -1 an)={a}\nB(retour < arrivée)={b}')
    repro = (temoin['duree_min'] == 180
             and a['duree_min'] is not None and a['duree_min'] > 500000
             and b['duree_min'] is not None and b['duree_min'] < 0)
    return {'repro': bool(repro), 'temoin': temoin, 'A': a, 'B': b}
