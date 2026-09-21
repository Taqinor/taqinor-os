"""Export xlsx ESG multi-feuilles (NTESG5).

Réutilise le builder xlsx PARTAGÉ (``apps.records.xlsx.build_workbook``,
même helper que ``crm.exports.build_xlsx_response``) — quatre feuilles
(Environnement / Social / Gouvernance / Méthodologie), construites à partir
de la MÊME source que le PDF NTESG4 (``selectors.donnees_effectives_
periode``) pour rester cohérentes au centime. Une ligne sans donnée n'est
JAMAIS ajoutée (pas de ligne à valeur vide) — ``openpyxl`` (pré-approuvé),
import à la demande.
"""
from django.http import HttpResponse


def _lignes_environnement(sources):
    lignes = []
    carburant = sources.get('carburant_flotte') or {}
    if carburant.get('disponible'):
        if carburant.get('gasoil_litres'):
            lignes.append(
                ['Carburant flotte — gasoil', carburant['gasoil_litres'],
                 'litres'])
        if carburant.get('essence_litres'):
            lignes.append(
                ['Carburant flotte — essence', carburant['essence_litres'],
                 'litres'])
        if carburant.get('electrique_kwh'):
            lignes.append(
                ['Carburant flotte — électrique', carburant['electrique_kwh'],
                 'kWh'])
    bilan = sources.get('bilan_carbone') or {}
    if bilan.get('disponible'):
        for scope in ('scope_1', 'scope_2', 'scope_3'):
            valeur = bilan.get(scope)
            if valeur:
                lignes.append([f'Bilan carbone — {scope}', valeur, 'tCO2e'])
    indic = sources.get('indicateurs_esg') or {}
    if indic.get('disponible'):
        bloc = (indic.get('piliers') or {}).get('environnement') or {}
        for ligne in bloc.get('lignes', []):
            if ligne.get('valeur') is not None:
                lignes.append(
                    [ligne.get('libelle'), ligne.get('valeur'),
                     ligne.get('unite')])
    return lignes


def _lignes_social(sources):
    lignes = []
    hse = sources.get('social_hse') or {}
    if hse.get('disponible'):
        if hse.get('taux_frequence') is not None:
            lignes.append(
                ['Taux de fréquence AT', hse['taux_frequence'], 'ratio'])
        if hse.get('taux_gravite') is not None:
            lignes.append(
                ['Taux de gravité AT', hse['taux_gravite'], 'ratio'])
        if hse.get('accidents_total'):
            lignes.append(
                ['Accidents du travail', hse['accidents_total'], 'nombre'])
        if hse.get('presqu_accidents_total'):
            lignes.append(
                ["Presqu'accidents", hse['presqu_accidents_total'],
                 'nombre'])
    effectifs = sources.get('effectifs') or {}
    if effectifs.get('disponible') and effectifs.get('effectif_actif'):
        lignes.append(
            ['Effectif actif', effectifs['effectif_actif'], 'personnes'])
    indic = sources.get('indicateurs_esg') or {}
    if indic.get('disponible'):
        bloc = (indic.get('piliers') or {}).get('social') or {}
        for ligne in bloc.get('lignes', []):
            if ligne.get('valeur') is not None:
                lignes.append(
                    [ligne.get('libelle'), ligne.get('valeur'),
                     ligne.get('unite')])
    return lignes


def _lignes_gouvernance(sources):
    lignes = []
    indic = sources.get('indicateurs_esg') or {}
    if indic.get('disponible'):
        bloc = (indic.get('piliers') or {}).get('gouvernance') or {}
        for ligne in bloc.get('lignes', []):
            if ligne.get('valeur') is not None:
                lignes.append(
                    [ligne.get('libelle'), ligne.get('valeur'),
                     ligne.get('unite')])
    return lignes


def _lignes_methodologie(periode_esg, sources):
    lignes = [
        ['Société', getattr(periode_esg.company, 'nom', '')],
        ['Période', periode_esg.libelle],
        ['Début', periode_esg.date_debut],
        ['Fin', periode_esg.date_fin],
        ['Statut', periode_esg.get_statut_display()],
        ['Extraction', 'Snapshot figé' if periode_esg.est_figee
         else 'Aperçu live (non figé)'],
        ['Facteurs d\'émission', 'Génériques, non vérifiés par un tiers — '
         'à faire valider par un organisme accrédité.'],
    ]
    for cle, source in sources.items():
        if source.get('disponible'):
            lignes.append([f'Source « {cle} »', 'Disponible'])
        else:
            lignes.append(
                [f'Source « {cle} »',
                 f"Non disponible — {source.get('raison', '')}"])
    return lignes


def build_esg_workbook(periode_esg):
    """Construit le classeur xlsx (4 feuilles) d'une période ESG (NTESG5)."""
    from apps.records.xlsx import build_workbook

    from .selectors import donnees_effectives_periode

    donnees = donnees_effectives_periode(periode_esg)
    sources = donnees.get('sources', {})

    wb = build_workbook(
        ['Libellé', 'Valeur', 'Unité'],
        _lignes_environnement(sources), sheet_title='Environnement')
    _append_sheet(
        wb, 'Social',
        ['Libellé', 'Valeur', 'Unité'], _lignes_social(sources))
    _append_sheet(
        wb, 'Gouvernance',
        ['Libellé', 'Valeur', 'Unité'], _lignes_gouvernance(sources))
    _append_sheet(
        wb, 'Méthodologie',
        ['Clé', 'Valeur'], _lignes_methodologie(periode_esg, sources))
    return wb


def _append_sheet(wb, title, headers, rows):
    from openpyxl.styles import Font

    from apps.records.xlsx import coerce_cell

    ws = wb.create_sheet(title[:31])
    ws.append(list(headers))
    bold = Font(bold=True)
    for cell in ws[1]:
        cell.font = bold
    for row in rows:
        ws.append([coerce_cell(v) for v in row])
    return ws


def export_esg_periode_xlsx(periode_esg):
    """Réponse HTTP .xlsx du classeur ESG d'une période (NTESG5)."""
    import io

    wb = build_esg_workbook(periode_esg)
    buf = io.BytesIO()
    wb.save(buf)
    response = HttpResponse(
        buf.getvalue(),
        content_type=(
            'application/vnd.openxmlformats-officedocument'
            '.spreadsheetml.sheet'))
    response['Content-Disposition'] = (
        f'attachment; filename="esg-{periode_esg.pk}.xlsx"')
    return response
