SONDE = {"constat": "C-APDF-VER-001", "sha": "90cf82d6b",
         "attendu": "société « SOLAIRE EXEMPLE SARL » : le titre du PDF résidentiel complet (include_etude, /proposal) nomme la société, jamais TAQINOR"}


def sonde(ctx):
    import fitz
    from apps.ventes.tests._quote_engine_common import make_company
    from apps.ventes.tests.test_pdf_apdf_identite import devis_residentiel, profil, rendre_pdf
    co = make_company(slug='sonde-apdf-ver-001', nom='Solaire Exemple')
    profil(co, nom='SOLAIRE EXEMPLE SARL', ice='001111111000011', rc='12345', site_web='')
    devis = devis_residentiel(co, 'DEV-SONDE-APDF-001')
    titres = {}
    for nom, options in (('include_etude', {'include_etude': True}), ('defaut', {}), ('onepage', {'pdf_mode': 'onepage'})):
        octets = rendre_pdf(devis, options)
        doc = fitz.open(stream=octets, filetype='pdf')
        try:
            titres[nom] = doc.metadata.get('title') or ''
        finally:
            doc.close()
    print('titres PDF : ' + ' | '.join(f'{k} = « {v} »' for k, v in titres.items()))
    return {'repro': any('TAQINOR' in t.upper() for t in titres.values()), 'titres': titres}
