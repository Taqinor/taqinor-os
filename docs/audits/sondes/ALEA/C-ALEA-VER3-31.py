# flake8: noqa  (sonde de vérification, rejouable par scripts/sonde.py)
"""C-ALEA-VER3-31 — après ALEA59, `Lead.relance_date` a deux définitions de « en retard » : le résumé servi
à l'assistant (`views_assistant._alertes_lead`, jours ouvrés via `seuil_retard`) et la file « Relances » /
« Ma file » (`cadence_selectors.relances_du_jour` scope `overdue`, `relance_date__lt=today`, calendaire).
Lead sans touche ouverte, relance_date = vendredi 09/10/2026, lu le dimanche 11/10 puis le lundi 12/10
(jour passé explicitement : pas de freezegun dans le conteneur). Société neuve, transaction annulée."""
SONDE = {"constat": "C-ALEA-VER3-31", "sha": "9ad3b8eb3",
         "attendu": "dimanche : résumé sans relance_en_retard MAIS lead listé en retard par relances_du_jour "
                    "(overdue) et « Ma file » (urgency overdue) ; lundi : les trois d'accord",
         "modeles": ["crm.Lead", "crm.RelanceEtape", "roles.Role"]}


def sonde(ctx):
    import datetime
    from django.contrib.auth import get_user_model
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Lead, RelanceEtape
    from apps.crm.cadence_selectors import ma_file_commercial_items, relances_du_jour
    from apps.crm.views_assistant import _alertes_lead, _bloc_prochaine_touche
    from apps.parametres.models import CompanyProfile
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS

    U = get_user_model()
    co = Company.objects.create(nom='Sonde ALEA VER3 31', slug='sonde-alea-ver3-31')
    CompanyProfile.objects.get_or_create(company=co)
    role = Role.objects.create(company=co, nom='Commercial sonde 31',
                               permissions=list(COMMERCIAL_PERMISSIONS))
    u = U.objects.create_user(username='sonde-alea-ver3-31', password='x', company=co, role=role)
    lead = Lead.objects.create(company=co, nom='Retard', prenom='R', owner=u, stage=stages.CONTACTED,
                               telephone='+212661000931')
    RelanceEtape.objects.filter(lead=lead).delete()
    vendredi = datetime.date(2026, 10, 9)
    Lead.objects.filter(pk=lead.pk).update(relance_date=vendredi)
    lead.refresh_from_db()
    out = {}
    for nom, jour in (('dimanche', datetime.date(2026, 10, 11)), ('lundi', datetime.date(2026, 10, 12))):
        touche = _bloc_prochaine_touche(lead)
        resume = 'relance_en_retard' in _alertes_lead(lead, [], touche, jour)
        file_relances = lead.pk in set(relances_du_jour(co, u, scope='overdue', today=jour)
                                       .values_list('pk', flat=True))
        ma_file = any(i['kind'] == 'relance' and i['link'].endswith(f'lead={lead.pk}')
                      and i['urgency'] == 'overdue' for i in ma_file_commercial_items(co, u, today=jour))
        out[nom] = {'touche': touche, 'resume_relance_en_retard': resume,
                    'relances_overdue': file_relances, 'ma_file_overdue': ma_file}
        print(f'{nom} {jour} : touche={touche} ; résumé relance_en_retard={resume} ; '
              f'relances?scope=overdue={file_relances} ; Ma file overdue={ma_file}')
    d = out['dimanche']
    return {'repro': (not d['resume_relance_en_retard']) and (d['relances_overdue'] or d['ma_file_overdue']),
            **out}
