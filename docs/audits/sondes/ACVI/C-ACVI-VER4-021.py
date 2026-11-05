# flake8: noqa  (sonde de contre-visite ACVI, rejouable par scripts/sonde.py — AMET93)
"""ACVI53 — `fiche_funnel.py::_corps_whatsapp_en_masse` rend `{societe}` par `_nom_affiche_marque(lead)` (NOTRE
marque) alors que le catalogue (`parametres/models_messages.py`, CIQ500) et les touches
(`cadence_messages.py::_societe_du_lead`) le définissent comme la raison sociale DU LEAD (`Lead.societe`) :
« Je prépare l'étude solaire de {societe} » part au client avec le nom de l'installateur à la place du sien,
et un lead SANS raison sociale ne voit pas la phrase omise. Rendu direct des deux voies, même gabarit.
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ACVI-VER4-021", "sha": "64c9c7317",
         "attendu": "file en masse : 'Boulangerie Atlas' absent, nom de marque présent ; lead sans societe : phrase gardée (marque) ; voie des touches (_societe_du_lead) : 'Boulangerie Atlas' ; attendu sain : la file rend Lead.societe et omet la phrase sans raison sociale",
         "modeles": ["authentication.Company", "crm.Lead", "crm.MessageTemplate"]}


def sonde(ctx):
    from authentication.models import Company
    from apps.crm import cadence_messages
    from apps.crm.fiche_funnel import _corps_whatsapp_en_masse
    from apps.crm.models import Lead, MessageTemplate
    co = Company.objects.create(nom='Sonde Solaire VER4-021', slug='sonde-acvi-ver4-021')
    avec = Lead.objects.create(company=co, nom='Atlas', prenom='Karim', telephone='+212612349721',
                               societe='Boulangerie Atlas')
    sans = Lead.objects.create(company=co, nom='Bennani', prenom='Sara', telephone='+212612349722')
    tpl = MessageTemplate.objects.create(
        company=co, nom='Etude C&I sonde', langue='fr',
        corps="Bonjour {prenom}. Je prépare l'étude solaire de {societe}. Bonne journée.")
    marque = cadence_messages._nom_affiche_marque(avec)
    masse_avec = _corps_whatsapp_en_masse(avec, tpl)
    masse_sans = _corps_whatsapp_en_masse(sans, tpl)
    touche_avec = cadence_messages._societe_du_lead(avec)
    obs = {'marque': marque, 'masse_avec': masse_avec, 'masse_sans': masse_sans,
           'societe_touches': touche_avec}
    print(obs)
    repro = ('Boulangerie Atlas' not in masse_avec and bool(marque) and marque in masse_avec
             and touche_avec == 'Boulangerie Atlas')
    return {'repro': repro, **obs}
