# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K61 — l'effacement d'un lead oublie des champs du lead (GPS du domicile, contact secondaire, notes)
et, côté client, le ``SiteProfile`` (GPS, notes d'ombrage).

Lead L (email, téléphone, GPS, contact secondaire nom/tél/email/fonction, note, visite_notes,
ombrage_notes) rattaché au Client C (même email) qui porte un SiteProfile (GPS, ombrage_notes).
`core.dsr.effacer(company, email)` (le chemin de `traiter`), puis relecture en base.
Témoin : nom/email/téléphone du lead vidés (le scrub a tourné)."""
SONDE = {"constat": "C-ASOC-061", "sha": "c514bd8ba",
         "attendu": "repro si lead « Anonymisé » mais GPS / contact secondaire / notes conservés (et SiteProfile intact)",
         "modeles": ["crm.Lead", "crm.Client", "crm.SiteProfile"]}


def sonde(ctx):
    from decimal import Decimal
    from authentication.models import Company
    from apps.crm.models import Client, Lead, SiteProfile
    from core import dsr
    co = Company.objects.create(nom='Sonde ASOC 061', slug='sonde-asoc-061')
    cl = Client.objects.create(company=co, nom='Alaoui', prenom='Sara', email='asoc061@example.invalid',
                               telephone='0612000061')
    sp = SiteProfile.objects.create(company=co, client=cl, gps_lat=Decimal('33.573100'),
                                    gps_lng=Decimal('-7.589800'), ombrage_notes='Palmier du voisin Mme Alaoui')
    le = Lead.objects.create(company=co, nom='Alaoui', prenom='Sara', email='asoc061@example.invalid',
                             telephone='0612000061', client=cl,
                             gps_lat=Decimal('33.573100'), gps_lng=Decimal('-7.589800'),
                             contact_secondaire_nom='Karim Alaoui', contact_secondaire_telephone='0661000061',
                             contact_secondaire_email='karim061@example.invalid',
                             contact_secondaire_fonction='Époux',
                             note='Sara rappelle après 18h, villa 12 lot Riad',
                             visite_notes='Code portail 4512, chien', ombrage_notes='Antenne sur le toit Alaoui')
    res = dsr.effacer(co, 'asoc061@example.invalid')
    le.refresh_from_db()
    sp.refresh_from_db()
    cl.refresh_from_db()
    champs = ['nom', 'prenom', 'email', 'telephone', 'gps_lat', 'gps_lng', 'contact_secondaire_nom',
              'contact_secondaire_telephone', 'contact_secondaire_email', 'contact_secondaire_fonction',
              'note', 'visite_notes', 'ombrage_notes']
    lead_apres = {k: (str(getattr(le, k)) if getattr(le, k) is not None else None) for k in champs}
    sp_apres = {'gps_lat': str(sp.gps_lat) if sp.gps_lat is not None else None,
                'gps_lng': str(sp.gps_lng) if sp.gps_lng is not None else None, 'ombrage_notes': sp.ombrage_notes}
    obs = {'resultat_effacer': res, 'lead_apres': lead_apres, 'client_anonymise': cl.is_anonymized,
           'siteprofile_apres': sp_apres}
    print(obs)
    temoin_ok = le.email is None and le.telephone is None and le.nom != 'Alaoui'
    restes_lead = [k for k in champs[4:] if lead_apres[k] not in (None, '')]
    restes_sp = [k for k, v in sp_apres.items() if v not in (None, '')]
    obs['temoin_ok'] = bool(temoin_ok)
    obs['champs_lead_conserves'] = restes_lead
    obs['champs_siteprofile_conserves'] = restes_sp
    obs['repro'] = bool(temoin_ok and restes_lead)
    return obs
