SONDE = {"constat": "C-ACAL-VER2-72", "sha": "56d5b623a",
         "attendu": "ACAL146 (ligne Client : « Rapport d'étude : provenance bancable de la météo complète, "
                    "fournisseur nommé ») : un résultat simulé sur un fichier météo déposé (meteo.service='fichier', "
                    "meteo.fournisseur='Meteonorm') -> la section site_meteo du rapport nomme le fichier/fournisseur, "
                    "jamais « PVGIS ». REPRO si la base d'irradiance imprimée dit PVGIS et que Meteonorm n'apparaît pas."}


def sonde(ctx):
    # Purement en mémoire : aucune écriture en base.
    from apps.calepinage.services.chaine_pertes import _base_production
    from apps.calepinage.services.rapport.site import html_de_section
    meteo = {'service': 'fichier', 'fournisseur': 'Meteonorm',
             'fichier': {'nom': 'site.csv', 'fournisseur': 'Meteonorm'}}
    resultat = {'meteo': meteo, 'production': {}}
    base = _base_production(resultat['production'], resultat)
    resultat['production']['base'] = base
    html = html_de_section({'resultat': resultat, 'site': {}})
    dit_pvgis = 'PVGIS' in html or 'pvgis' in html.lower()
    nomme = 'Meteonorm' in html
    print(f"base={base!r}")
    print(f"pvgis_dans_rapport={dit_pvgis} meteonorm_dans_rapport={nomme}")
    return {'repro': dit_pvgis and not nomme, 'base_source': base.get('source'),
            'pvgis_dans_rapport': dit_pvgis, 'meteonorm_dans_rapport': nomme}
