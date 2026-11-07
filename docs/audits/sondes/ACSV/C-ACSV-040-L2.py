# flake8: noqa  (seconde lentille PA5, rejouable par scripts/sonde.py — METHODE §B.5 / §C.4)
"""K40 seconde lentille — autre angle que C-ACSV-040 : (1) la réserve qui change le PV n'est pas levée mais
AJOUTÉE, des semaines après la signature, sur une intervention SAV « dépannage » du chantier, par un
TECHNICIEN (rôle système TECHNICIEN_PERMISSIONS) depuis le panneau Réserves de « Ma journée »
(POST interventions/<id>/ajouter-reserve/, corps de ReservesPanel, creer_ticket faux) ; (2) le chantier est
signé depuis 40 jours (gel tardif, cas réel) ; (3) le PV est re-servi par le bouton « PV de réception » de
InstallationDetail (GET documents/chantiers/<id>/pv-reception/). `reserves_chantier_qs` inclut les réserves
d'intervention, donc l'empreinte change. Moteur PDF MOQUÉ (HTML encodé) ; stockage objet MOQUÉ en mémoire."""
SONDE = {"constat": "C-ACSV-040", "sha": "ddf1f97a1",
         "attendu": "repro (élargi) si après l'ajout d'une réserve SAV par le technicien, le PV figé du chantier "
                    "signé reçoit une NOUVELLE version portant le trait de signature ET la réserve SAV, et que "
                    "cette version est celle partagée au client",
         "modeles": ["ged.Document", "ged.DocumentVersion", "ged.AclGed", "installations.Installation",
                     "installations.Intervention", "installations.Reserve"]}


def sonde(ctx):
    import datetime
    import uuid
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, Intervention
    from apps.installations.services import ESSAIS_RECETTE, ensure_commissioning_record
    from apps.roles.models import Role
    from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
    from apps.ged import services as ged_services, selectors as ged_selectors
    from apps.ged.models import DocumentVersion
    from apps.documents import builders
    import apps.records.storage as rstorage

    H = {'HTTP_HOST': 'localhost'}
    TRAIT = ('data:image/png;base64,'
             'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQ'
             'GAhKmMIQAAAABJRU5ErkJggg==')
    MAGASIN = {}

    def fake_store(data, *, mime='application/pdf'):
        key = f'attachments/sonde-{uuid.uuid4().hex}.pdf'
        MAGASIN[key] = bytes(data)
        return key, {'filename': key.rsplit('/', 1)[-1], 'size': len(data), 'mime': 'application/pdf'}

    def fake_fetch_key(key, *a, **k):
        return (MAGASIN.get(key), None if key in MAGASIN else 'absent')

    def fake_fetch_version(version, *a, **k):
        return fake_fetch_key(version.file_key)

    patches = [mock.patch.object(builders, '_html_to_pdf', side_effect=lambda h: h.encode('utf-8')),
               mock.patch.object(ged_services, '_store_bytes', side_effect=fake_store),
               mock.patch.object(rstorage, 'fetch_attachment', side_effect=fake_fetch_key)]
    if hasattr(ged_services, '_fetch_version_bytes'):
        patches.append(mock.patch.object(ged_services, '_fetch_version_bytes', side_effect=fake_fetch_version))
    try:
        import apps.ventes.utils.pdf as vpdf
        patches.append(mock.patch.object(vpdf, '_download', return_value=None))
    except Exception:  # noqa
        pass
    for p in patches:
        p.start()
    try:
        co = Company.objects.create(nom='Sonde ACSV 040 L2', slug='sonde-acsv-040-l2')
        U = get_user_model()
        adm = U.objects.create_user(username='sonde_acsv_040l2_adm', password='x', role_legacy='admin', company=co)
        r_tech = Role.objects.create(company=co, nom='Technicien', permissions=list(TECHNICIEN_PERMISSIONS),
                                     est_systeme=True)
        tech = U.objects.create_user(username='sonde_acsv_040l2_tech', password='x', company=co, role=r_tech)
        A, T = APIClient(), APIClient()
        A.force_authenticate(adm)
        T.force_authenticate(tech)
        cl = Client.objects.create(company=co, nom='Usine Sonde L2 SARL', type_client='entreprise',
                                   email='acsv040l2@example.invalid')
        today = datetime.date.today()
        inst = Installation.objects.create(company=co, reference='CHT-ACSV-040L2', client=cl,
                                           type_installation='industriel', statut='receptionne',
                                           date_reception=today - datetime.timedelta(days=40),
                                           puissance_installee_kwc=Decimal('100'))
        rec = ensure_commissioning_record(inst)
        for champ in ESSAIS_RECETTE:
            setattr(rec, champ, True)
        rec.resultat = 'conforme'
        rec.date_essai = today - datetime.timedelta(days=41)
        rec.save()
        # Signé il y a 40 jours, aucune réserve ouverte.
        Installation.objects.filter(pk=inst.pk).update(
            signature_client=TRAIT, signataire_nom='M. Client',
            signe_le=timezone.now() - datetime.timedelta(days=40))
        inst.refresh_from_db()
        url_pv = f'/api/django/documents/chantiers/{inst.pk}/pv-reception/'
        g1 = A.get(url_pv, **H)
        doc = builders._document_ged(inst, builders.SOURCE_PV_RECEPTION)
        v1 = list(DocumentVersion.objects.filter(document=doc).order_by('version')) if doc else []
        v1_html = MAGASIN.get(v1[-1].file_key, b'').decode('utf-8', 'replace') if v1 else ''
        # Plus tard : dépannage SAV sur le chantier, réserve ajoutée par le technicien depuis « Ma journée ».
        iv = Intervention.objects.create(company=co, installation=inst, type_intervention='depannage',
                                         statut='sur_site', date_prevue=today, technicien=tech)
        r_add = T.post(f'/api/django/installations/interventions/{iv.pk}/ajouter-reserve/',
                       {'description': 'Onduleur bruyant SONDE40L2', 'creer_ticket': False, 'creer_suivi': False},
                       format='json', **H)
        g2 = A.get(url_pv, **H)
        servi = g2.content.decode('utf-8', 'replace') if g2.status_code == 200 else ''
        doc = builders._document_ged(inst, builders.SOURCE_PV_RECEPTION)
        versions = list(DocumentVersion.objects.filter(document=doc).order_by('version'))
        vig = versions[-1] if versions else None
        vig_html = MAGASIN.get(vig.file_key, b'').decode('utf-8', 'replace') if vig else ''
        partages = list(ged_selectors.documents_partages_client_portail(co, cl.id).values_list('id', flat=True))
        latest = ged_selectors.latest_version(doc) if doc else None
        obs = {
            'get_pv_1_http': g1.status_code,
            'v1': {'nb_versions': len(v1), 'contient_trait': TRAIT in v1_html,
                   'contient_reserve_sav': 'SONDE40L2' in v1_html,
                   'mention': ('Figé le' if 'Figé le' in v1_html else 'Signé le' if 'Signé le' in v1_html else None)},
            'tech_ajouter_reserve_http': r_add.status_code,
            'get_pv_2_http': g2.status_code,
            'apres_reserve_sav': {'nb_versions_pv': len(versions),
                                  'vN_contient_trait': TRAIT in vig_html,
                                  'vN_contient_reserve_sav': 'SONDE40L2' in vig_html,
                                  'vN_mention': ('Figé le' if 'Figé le' in vig_html
                                                 else 'Signé le' if 'Signé le' in vig_html else None),
                                  'pdf_servi_contient_reserve_sav': 'SONDE40L2' in servi},
            'portail': {'pv_partage_au_client': bool(doc and doc.id in partages),
                        'version_servie_au_client': getattr(latest, 'version', None)},
        }
        obs['repro'] = bool(
            g1.status_code == 200 and r_add.status_code == 201 and g2.status_code == 200
            and len(v1) == 1 and not obs['v1']['contient_reserve_sav']
            and len(versions) >= 2 and obs['apres_reserve_sav']['vN_contient_trait']
            and obs['apres_reserve_sav']['vN_contient_reserve_sav']
            and obs['portail']['pv_partage_au_client']
            and getattr(latest, 'version', None) == versions[-1].version)
        print(obs)
        return obs
    finally:
        for p in patches:
            p.stop()
