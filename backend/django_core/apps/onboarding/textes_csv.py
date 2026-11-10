"""NTDMO36 — export/réimport CSV des textes FR du produit (visites guidées
NTDMO14 + checklist « Premiers pas » NTDMO11) pour relecture hors-ERP.

Trois colonnes : ``cle_stable``, ``ecran_cible``, ``texte_fr``. La clé stable
sert d'identifiant de correspondance à la réimportation (jamais de doublon) :

* ``item:<key>``                 → ``OnboardingChecklistItem.libelle`` ;
* ``tour:<tour_key>#<ordre>:titre`` / ``…:texte`` → ``ProductTourStep``.

Portée : les lignes du catalogue GLOBAL (``company`` NULL) et celles de la
société de l'appelant. À la réimportation, une ligne de catalogue global n'est
modifiable que par l'opérateur plateforme (un administrateur de société ne
réécrit jamais le texte vu par les autres sociétés) ; elle est alors comptée
``ignorees``.
"""
import csv
import io

from django.db import transaction
from django.db.models import Q

from .models import OnboardingChecklistItem, ProductTourStep

COLONNES = ['cle_stable', 'ecran_cible', 'texte_fr']
_DANGEREUX = ('=', '+', '-', '@')


def _vers_cellule(valeur):
    """Neutralise l'injection de formule tableur (préfixe ``'``)."""
    valeur = valeur or ''
    return "'" + valeur if valeur[:1] in _DANGEREUX else valeur


def _depuis_cellule(valeur):
    valeur = valeur or ''
    if valeur[:1] == "'" and valeur[1:2] in _DANGEREUX:
        return valeur[1:]
    return valeur


def _portee(qs, company):
    return qs.filter(Q(company__isnull=True) | Q(company=company))


def lignes_export(company):
    """Lignes ``[cle_stable, ecran_cible, texte_fr]`` ordonnées."""
    lignes = []
    for it in _portee(OnboardingChecklistItem.objects.all(), company).order_by(
            'ordre', 'key'):
        lignes.append([f'item:{it.key}', it.lien, it.libelle])
    for st in _portee(ProductTourStep.objects.all(), company).order_by(
            'tour_key', 'ordre'):
        base = f'tour:{st.tour_key}#{st.ordre}'
        lignes.append([f'{base}:titre', st.ecran_cible, st.titre])
        lignes.append([f'{base}:texte', st.ecran_cible, st.texte])
    return lignes


def exporter_csv(company):
    """CSV UTF-8 avec BOM (ouverture directe dans Excel)."""
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, lineterminator='\r\n')
    ecrivain.writerow(COLONNES)
    for cle, ecran, texte in lignes_export(company):
        ecrivain.writerow([cle, _vers_cellule(ecran), _vers_cellule(texte)])
    return '\ufeff' + sortie.getvalue()


def _lire(contenu):
    texte = contenu.decode('utf-8-sig') if isinstance(contenu, bytes) else contenu
    delimiteur = ';' if texte.split('\n', 1)[0].count(';') > texte.split(
        '\n', 1)[0].count(',') else ','
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=delimiteur)
    if not lecteur.fieldnames or 'cle_stable' not in lecteur.fieldnames \
            or 'texte_fr' not in lecteur.fieldnames:
        raise ValueError(
            'En-tête invalide : colonnes attendues ' + ', '.join(COLONNES))
    return list(lecteur)


@transaction.atomic
def importer_csv(contenu, company, *, peut_ecrire_global=False):
    """Met à jour les textes existants par clé stable. Ne crée JAMAIS de ligne.

    Retourne ``{'mis_a_jour': n, 'inchanges': n, 'ignorees': n, 'inconnues':
    [cle…]}``. Lève ``ValueError`` sur un en-tête invalide."""
    res = {'mis_a_jour': 0, 'inchanges': 0, 'ignorees': 0, 'inconnues': []}
    for ligne in _lire(contenu):
        cle = (ligne.get('cle_stable') or '').strip()
        nouveau = _depuis_cellule(ligne.get('texte_fr'))
        obj, champ = _resoudre(cle, company)
        if obj is None:
            res['inconnues'].append(cle)
            continue
        if obj.company_id is None and not peut_ecrire_global:
            res['ignorees'] += 1
            continue
        if not nouveau.strip():
            res['ignorees'] += 1  # jamais de libellé vide
            continue
        if getattr(obj, champ) == nouveau:
            res['inchanges'] += 1
            continue
        setattr(obj, champ, nouveau)
        obj.save(update_fields=[champ])
        res['mis_a_jour'] += 1
    return res


def _resoudre(cle, company):
    """``(objet, champ)`` pour une clé stable, ``(None, None)`` si inconnue."""
    try:
        if cle.startswith('item:'):
            obj = _portee(OnboardingChecklistItem.objects.all(), company).filter(
                key=cle[5:]).order_by('company_id').first()
            return (obj, 'libelle') if obj else (None, None)
        if cle.startswith('tour:'):
            reste, champ = cle[5:].rsplit(':', 1)
            tour_key, ordre = reste.rsplit('#', 1)
            if champ not in ('titre', 'texte'):
                return None, None
            obj = _portee(ProductTourStep.objects.all(), company).filter(
                tour_key=tour_key, ordre=int(ordre)).order_by(
                'company_id').first()
            return (obj, champ) if obj else (None, None)
    except ValueError:
        return None, None
    return None, None
