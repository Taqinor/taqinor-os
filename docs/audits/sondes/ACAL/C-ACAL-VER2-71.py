SONDE = {"constat": "C-ACAL-VER2-71", "sha": "56d5b623a",
         "attendu": "ACAL148 : fichier météo retiré (corbeille) puis purge de la corbeille après 30 j "
                    "(trash.purger_expires, tâche beat) -> lire_piece_meteo(cal) reste None (retour à PVGIS durable). "
                    "REPRO si la pièce retirée redevient la source retenue."}


def sonde(ctx):
    from datetime import timedelta
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone
    from authentication.models import Company
    from django.contrib.auth import get_user_model
    from apps.crm.models import Lead
    from apps.calepinage.models import Calepinage
    from apps.calepinage.services.simulation import lire_piece_meteo
    from apps.records.models import Attachment
    from apps.trash.models import ElementSupprime
    from apps.trash.services import journaliser_suppression, purger_expires
    U = get_user_model()
    co = Company.objects.create(nom='Sonde ACAL VER2-71', slug='sonde-acal-ver2-71')
    u = U.objects.create_user(username='sonde_acal_ver2_71', password='x', company=co, role_legacy='admin')
    lead = Lead.objects.create(company=co, nom='Sonde météo retirée')
    cal = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='meteo retiree')
    piece = Attachment.objects.create(
        company=co, content_type=ContentType.objects.get_for_model(Calepinage),
        object_id=cal.pk, file_key='meteo/%d/calepinage-%d-sonde.csv' % (co.pk, cal.pk),
        filename='site.csv', size=10, mime='text/csv', uploaded_by=u)
    avant = lire_piece_meteo(cal)
    # Le geste DELETE meteo-fichier/ fait exactement ceci (views/meteo_fichier.py::_mettre_a_la_corbeille).
    journaliser_suppression(instance=piece, company=co, user=u, type_libelle='Fichier météo', libelle='site.csv')
    apres_retrait = lire_piece_meteo(cal)
    # 31 jours plus tard : la tâche beat trash.purger_corbeille_transverse purge l'entrée échue.
    ElementSupprime.objects.filter(company=co).update(expire_le=timezone.now() - timedelta(days=1))
    purge = purger_expires(company=co)
    apres_purge = lire_piece_meteo(cal)
    print(f"avant={getattr(avant, 'pk', None)} apres_retrait={getattr(apres_retrait, 'pk', None)} "
          f"purge={purge} apres_purge={getattr(apres_purge, 'pk', None)}")
    return {'repro': apres_retrait is None and apres_purge is not None,
            'avant': getattr(avant, 'pk', None), 'apres_retrait': getattr(apres_retrait, 'pk', None),
            'apres_purge': getattr(apres_purge, 'pk', None)}
