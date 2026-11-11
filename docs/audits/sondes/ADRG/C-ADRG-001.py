# flake8: noqa  (sonde seconde lentille 10/11 — rejouable par scripts/sonde.py, AMET93)
"""Import générique de FACTURES par un rôle livré sans droit de vente. Porte : `POST /api/django/imports/dry-run/`
puis `/imports/commit/` (`apps/dataimport/views.py::dry_run`/`::commit`, garde `IsResponsableOrAdmin` seule ;
`dataimport` ∈ `APPS_SANS_MODULE` ; `DROIT_PAR_CIBLE` ne couvre que leads/clients) → `services._commit_raw` →
`apps/ventes/domain/imports.py::creer_facture_import` → `create_provisoire` puis `numeroter_a_l_emission` (série
légale `facture`, même compteur que l'émission). Compte au rôle SYSTÈME « Technicien » semé comme `init_roles`
(get_or_create nom + permissions du registre vivant + périmètre). Témoin : le même compte sur la route normale
`POST /api/django/facturation/factures/<id>/emettre/` (brouillon créé par un compte de mise en place) ⇒ 403.
Second cas (observé, hors repro) : rôle système « Commercial » importe une ligne « payée » alors que
`marquer-payee` est réservé à `IsAdminRole` ; nombre de `Paiement` rattachés. Transaction annulée. Jamais la prod."""
SONDE = {"constat": "C-ADRG-001", "sha": "7e845af04",
         "attendu": "Technicien (0 code d'écriture ventes, sans encaisser) : témoin emettre 403 ; dry-run 200, commit 200 "
                    "et une Facture statut émise à référence légale non provisoire (REPRO) ; attendu sain : 403 au "
                    "commit, aucune facture. Cas Commercial : statut payée posé, 0 Paiement",
         "modeles": ["authentication.Company", "crm.Client", "facturation.Facture", "facturation.Paiement",
                     "dataimport.ImportJob", "dataimport.ExternalRef"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.permissions import codes_du_module
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, SYSTEM_ROLE_PERIMETRES
    from apps.facturation.models import Facture, Paiement
    from apps.ventes.utils.company_settings import create_provisoire
    from core.numbering import est_reference_provisoire

    co = Company.objects.create(nom='Sonde ADRG 001', slug='sonde-adrg-001')
    U = get_user_model()
    setup = U.objects.create_user(username='sonde-adrg-001-setup', password='x', company=co,
                                  role_legacy='responsable')
    registre = dict(CANONICAL_SYSTEM_ROLES)

    def role_systeme(nom):
        # Rôle système RÉEL, semé exactement comme init_roles (Command.handle).
        role, _cree = Role.objects.get_or_create(
            company=co, nom=nom, defaults={'permissions': list(registre[nom]), 'est_systeme': True})
        role.perimetre = SYSTEM_ROLE_PERIMETRES.get(nom)
        role.save(update_fields=['perimetre'])
        return role

    def compte(nom_role, username):
        role = role_systeme(nom_role)
        u = U.objects.create_user(username=username, password='x', company=co, role=role)
        api = APIClient()
        api.force_authenticate(u)
        return role, u, api

    ventes_ecriture = sorted(c for c in codes_du_module('ventes') if not c.endswith('_voir'))

    def codes(role):
        perms = set(role.permissions or [])
        return {'ecriture_ventes': sorted(perms & set(ventes_ecriture)), 'encaisser': 'encaisser' in perms}

    client = Client.objects.create(company=co, nom='Client ADRG', email='adrg-001@example.invalid')
    H = {'format': 'multipart', 'HTTP_HOST': 'localhost'}
    I = '/api/django/imports'

    def fichier(statut, ext):
        csv = f'reference,client_nom,statut,external_id\nSRC-{ext},Client ADRG,{statut},{ext}\n'
        return SimpleUploadedFile('factures.csv', csv.encode('utf-8'), content_type='text/csv')

    def importer(api, statut, ext):
        avant = set(Facture.objects.filter(company=co).values_list('pk', flat=True))
        rd = api.post(f'{I}/dry-run/', {'file': fichier(statut, ext), 'target': 'factures'}, **H)
        rc = api.post(f'{I}/commit/', {'file': fichier(statut, ext), 'target': 'factures'}, **H)
        nouvelles = list(Facture.objects.filter(company=co).exclude(pk__in=avant).order_by('pk'))
        return rd, rc, nouvelles

    def corps(r):
        data = getattr(r, 'data', None)
        if isinstance(data, dict):
            return {k: data.get(k) for k in ('detail', 'created', 'skipped', 'statut') if k in data}
        return data

    obs = {}
    # ── Cas 1 : Technicien ──
    role_t, u_t, api_t = compte('Technicien', 'sonde-adrg-001-tech')
    obs['technicien_role'] = (role_t.nom, role_t.est_systeme, role_t.perimetre)
    obs['technicien_codes'] = codes(role_t)
    obs['technicien_is_responsable'] = U.objects.get(pk=u_t.pk).is_responsable

    # Témoin : la route normale d'émission refuse ce compte.
    brouillon = create_provisoire(lambda ref: Facture.objects.create(
        company=co, reference=ref, client=client, type_facture=Facture.TypeFacture.COMPLETE,
        statut=Facture.Statut.BROUILLON, libelle='Témoin ADRG'))
    rt = api_t.post(f'/api/django/facturation/factures/{brouillon.pk}/emettre/', {},
                    format='json', HTTP_HOST='localhost')
    brouillon.refresh_from_db()
    obs['temoin_emettre'] = (rt.status_code, corps(rt), brouillon.statut, brouillon.reference)

    rd, rc, nouvelles = importer(api_t, 'emise', 'EXT-ADRG-T1')
    obs['technicien_dry_run'] = (rd.status_code, corps(rd) if rd.status_code >= 400 else None)
    obs['technicien_commit'] = (rc.status_code, corps(rc))
    obs['technicien_factures'] = [(f.reference, f.statut, est_reference_provisoire(f.reference),
                                   str(f.date_echeance), Paiement.objects.filter(facture=f).count())
                                  for f in nouvelles]

    # ── Cas 2 (observé, hors repro) : Commercial importe une ligne « payée » ──
    role_c, _u_c, api_c = compte('Commercial', 'sonde-adrg-001-com')
    obs['commercial_codes'] = codes(role_c)
    obs['commercial_est_admin'] = 'roles_gerer' in (role_c.permissions or [])
    rd2, rc2, nouvelles2 = importer(api_c, 'payee', 'EXT-ADRG-C1')
    obs['commercial_dry_run'] = rd2.status_code
    obs['commercial_commit'] = (rc2.status_code, corps(rc2))
    obs['commercial_factures'] = [(f.reference, f.statut, est_reference_provisoire(f.reference),
                                   Paiement.objects.filter(facture=f).count()) for f in nouvelles2]

    sans_droit = not obs['technicien_codes']['ecriture_ventes'] and not obs['technicien_codes']['encaisser']
    repro = bool(sans_droit and rc.status_code == 200 and any(
        f.statut != Facture.Statut.BROUILLON and f.reference and not est_reference_provisoire(f.reference)
        for f in nouvelles))
    obs['temoin_refuse'] = rt.status_code == 403
    print(f'obs={obs}')
    return {'repro': repro, **obs}
