SONDE = {"constat": "C-APDF-VER-002", "sha": "90cf82d6b",
         "attendu": "société sans logo, devis résidentiel envoyé avec lien de partage : le QR « Scannez pour signer » du PDF (/proposal) n'incruste pas le logo TAQINOR (assets/logo.png)"}


def sonde(ctx):
    from unittest import mock
    from apps.ventes.models import Devis, ShareLink
    from apps.ventes.quote_engine.residential import theme
    from apps.ventes.tests._quote_engine_common import make_company
    from apps.ventes.tests.test_pdf_apdf_identite import devis_residentiel, profil, rendre_pdf
    co = make_company(slug='sonde-apdf-ver-002', nom='Solaire Exemple')
    profil(co, nom='SOLAIRE EXEMPLE SARL', ice='001111111000011', site_web='')
    devis = devis_residentiel(co, 'DEV-SONDE-APDF-002')
    Devis.objects.filter(pk=devis.pk).update(statut='envoye')
    devis.refresh_from_db()
    ShareLink.for_devis(devis)
    origine = theme.qr_data_uri
    appels = []

    def enregistre(url, *a, **k):
        appels.append({'logo': k.get('logo', True), 'url': url[:60]})
        return origine(url, *a, **k)

    with mock.patch.object(theme, 'qr_data_uri', side_effect=enregistre):
        rendre_pdf(devis, {})
    avec_logo = [a for a in appels if a['logo']]
    asset = theme._LIVE_ASSETS / 'logo.png'
    print(f'logo société : aucun ; appels qr_data_uri pendant le rendu : {len(appels)} ; avec logo=True : {len(avec_logo)} '
          f'(incrustation de {asset.name}, asset de marque du moteur, exists={asset.exists()}) ; '
          f'url {avec_logo[0]["url"] if avec_logo else "-"}')
    return {'repro': bool(avec_logo) and asset.exists(), 'appels': len(appels), 'avec_logo': len(avec_logo)}
