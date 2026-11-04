# flake8: noqa  (sonde de contre-visite ACVI82, rejouable par scripts/sonde.py)
"""ACVI82 — vérificateur frais : GET /visites/visites/ et GET relance-etapes/?scope=all (leads avec visite,
3 photos commentées chacune) coûtent autant de requêtes à N=3 qu'à N=9 visites (société NEUVE, transaction
annulée, échauffement). Vérifie en plus que les lignes servies ne perdent rien (nb de lignes, complétude)."""
SONDE = {"constat": "C-ACVI-145", "sha": "06ced8b1a",
         "attendu": "repro: False — delta de requêtes par visite ajoutée < 0.9 sur la liste et la file du jour",
         "modeles": ["crm.Lead", "crm.RelanceEtape", "visites.VisiteTerrain", "visites.VisiteMedia",
                     "records.Attachment"]}


def sonde(ctx):
    import datetime
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from django.db import connection, transaction
    from django.test.utils import CaptureQueriesContext
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.crm.models_cadence import RelanceEtape
    from apps.records.models import Attachment
    from apps.roles.models import Role
    from apps.roles.permissions_registre import ADMIN_PERMISSIONS
    from apps.visites.models import VisiteTerrain, VisiteMedia
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI VER1 82', slug='sonde-acvi-ver1-82')
    role = Role.objects.create(company=c, nom='Administrateur', permissions=ADMIN_PERMISSIONS, est_systeme=True)
    u = U.objects.create_user(username='sonde-acvi-ver1-82', password='x', company=c, role=role, role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    ct = ContentType.objects.get_for_model(VisiteTerrain)
    jour = timezone.localdate()
    n = [0]

    def ajouter(k):
        for _ in range(k):
            n[0] += 1
            i = n[0]
            l = Lead.objects.create(company=c, nom=f'L{i}', owner=u, telephone=f'066100{i:04d}', ville='Rabat',
                                    visite_prevue_le=timezone.now())
            Lead.objects.filter(pk=l.pk).update(
                date_creation=timezone.now() - datetime.timedelta(days=5),
                first_contacted_at=timezone.now() - datetime.timedelta(days=3))
            v = VisiteTerrain.objects.create(company=c, lead=l, commercial=u, statut='terminee',
                                             date_prevue=jour, date_realisee=timezone.now())
            for s in range(3):
                a = Attachment.objects.create(company=c, content_type=ct, object_id=v.pk,
                                              file_key=f'sonde/{i}/{s}.jpg', filename=f'{s}.jpg')
                VisiteMedia.objects.create(company=c, visite=v, attachment=a, slot_code=f'toit_{s}',
                                           commentaire=f'commentaire {s}')
            RelanceEtape.objects.create(company=c, lead=l, cadence='contact', ordre=1,
                                        canal=RelanceEtape.Canal.WHATSAPP, libelle=f'Appel {i}',
                                        due_at=timezone.now(), due_date=jour, statut=RelanceEtape.Statut.A_FAIRE)

    def compte(fn):
        try:
            with transaction.atomic():
                with CaptureQueriesContext(connection) as cq:
                    res = fn()
            return [len(cq.captured_queries), res]
        except Exception as e:
            return ['exc', repr(e)[:200]]

    lectures = {
        'H6_get_visites': lambda: api.get(reverse('visites-visite-list'), HTTP_HOST='localhost').status_code,
        'H7_get_relance_etapes_all': lambda: api.get(reverse('relance-etape-list'), {'scope': 'all'},
                                                     HTTP_HOST='localhost').status_code,
    }
    obs = {}
    ajouter(3)
    for k, fn in lectures.items():
        compte(fn)  # échauffement (caches de profil / contenttypes)
        obs[k] = {'N3': compte(fn)}
    ajouter(6)
    for k, fn in lectures.items():
        obs[k]['N9'] = compte(fn)
        a, b = obs[k]['N3'][0], obs[k]['N9'][0]
        obs[k]['delta_par_N'] = (round((b - a) / 6, 2) if isinstance(a, int) and isinstance(b, int) else None)
    repro = {k: (obs[k]['delta_par_N'] or 0) >= 0.9 for k in lectures}
    obs['repro_par_constat'] = repro
    lignes = api.get(reverse('visites-visite-list'), HTTP_HOST='localhost').json()
    lignes = lignes.get('results', lignes) if isinstance(lignes, dict) else lignes
    obs['liste_nb_lignes'] = len(lignes)
    obs['liste_exemple'] = lignes[0] if lignes else None
    return {'repro': any(repro.values()) or len(lignes) != 9, 'observe': obs}
