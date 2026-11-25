"""Relecture E4 B1 (D-ACAL-97) — ce que les noyaux lisent HORS du lead.

La composition, le balayage des tailles (``dimensionnement``), les catalogues
C&I et pompage lisent le CATALOGUE de la société (articles, prix de vente,
archivage, puissance des fiches) et sa TVA : une conception rangée avant un
changement de prix ou l'archivage d'un panneau imprimerait des chiffres
périmés. Ces entrées entrent donc dans l'empreinte de la conception
(``conception/entrees.py::entrees_pour``) et dans ``entrees_utilisees`` (source
``reglage_societe``) — c'est ce qui permet à l'écrivain de DIRE pourquoi il a
recalculé (« catalogue modifié », « TVA modifiée »).

* ``empreinte_catalogue(company)`` — SHA-256 des colonnes de VENTE des
  produits composables (ceux de la société et les globaux, archivés compris),
  ordre stable ; jamais ``prix_achat`` ni marge. Calculée UNE fois par
  requête (mémo ``core.request_cache``, clé portant la société).
* Paresseux : un catalogue modifié ne met AUCUNE tâche en file ; chaque
  conception se recalcule quand elle est lue (filet ADEV140) ou quand un devis
  est demandé.
"""
import hashlib
import json

#: Colonnes de ``stock.Produit`` (et de sa catégorie / fiche) que lisent les
#: noyaux : désignation (le classement « panneau / onduleur » lit le nom), prix
#: et barèmes de VENTE, TVA de l'article, archivage, rôles, catégorie typée,
#: caractéristiques de pompage. La fiche technique (puissance, tensions,
#: courbes) est suivie par sa date de mise à jour. JAMAIS ``prix_achat``.
CHAMPS_PRODUIT = (
    'id', 'company_id', 'nom', 'marque', 'prix_vente', 'paliers_prix_vente', 'prix_fixe_ht',
    'prix_par_panneau_ht', 'tva', 'is_archived', 'categorie_id', 'categorie__type_equipement',
    'role_devis', 'role_ci', 'role_pompage', 'type_pose', 'pompe_cv', 'pompe_kw', 'hmt_m', 'debit_m3j',
    'tension_v', 'courbe_pompe', 'type_pompe', 'alimentation', 'courbe_source', 'courbe_frequence_hz',
    'fiche_technique__date_mise_a_jour', 'quantite_stock',
)
CLE_CATALOGUE = 'catalogue'
#: Les réglages société dits dans ``entrees_utilisees`` et la phrase « pourquoi ».
MOTIFS = {CLE_CATALOGUE: 'catalogue modifié', 'tva_standard': 'TVA modifiée',
          'tva_panneaux': 'TVA des panneaux modifiée'}
LIBELLES = {CLE_CATALOGUE: 'Catalogue', 'tva_standard': 'TVA standard', 'tva_panneaux': 'TVA des panneaux'}


def cle_memo_catalogue(company_id):
    return ('ventes.conception.empreinte_catalogue', company_id)


def empreinte_catalogue(company):
    """L'empreinte du catalogue de vente de ``company`` (mémo de requête)."""
    from core import request_cache
    return request_cache.memoize(cle_memo_catalogue(company.pk), lambda: _empreinte_catalogue(company))


def _empreinte_catalogue(company):
    from django.db.models import Q

    from apps.stock.selectors import produits_qs

    lignes = []
    for ligne in (produits_qs().filter(Q(company=company) | Q(company__isnull=True))
                  .order_by('id').values_list(*CHAMPS_PRODUIT)):
        ligne = list(ligne)
        # Seul « en stock ou non » compte (le vivier batterie, BATHOMO) : un
        # mouvement de stock ordinaire ne périme rien.
        ligne[-1] = bool(ligne[-1] and ligne[-1] > 0)
        lignes.append(ligne)
    canonique = json.dumps(lignes, separators=(',', ':'), default=str, ensure_ascii=False)
    return hashlib.sha256(canonique.encode('utf-8')).hexdigest()


def entrees_de_la_societe(company):
    """``{champ: {valeur, source}}`` des réglages société lus par les noyaux."""
    from apps.ventes.utils.company_settings import tva_panneaux, tva_standard

    return {'tva_standard': {'valeur': float(tva_standard(company)), 'source': 'reglage_societe'},
            'tva_panneaux': {'valeur': float(tva_panneaux(company)), 'source': 'reglage_societe'},
            CLE_CATALOGUE: {'valeur': empreinte_catalogue(company), 'source': 'reglage_societe'}}


def changements(ancienne, nouvelle, nommes):
    """Les entrées qui ont changé entre la version ``ancienne`` (ses
    ``entrees_utilisees``) et les entrées ``nouvelle`` : ``[{champ, avant,
    apres}]``. Toujours les réglages société (présents des deux côtés : une
    version d'avant ce suivi ne dit pas « catalogue modifié ») ; les colonnes
    du lead seulement quand l'appelant n'en nomme aucune (``nommes`` vide)."""
    ancienne, nouvelle = ancienne or {}, nouvelle or {}
    vus = {c['champ'] for c in nommes}
    sortie = []
    for champ in sorted(set(ancienne) | set(nouvelle)):
        avant, apres = (ancienne.get(champ) or {}).get('valeur'), (nouvelle.get(champ) or {}).get('valeur')
        if champ in vus or avant == apres:
            continue
        if champ in MOTIFS:
            if champ in ancienne and champ in nouvelle:
                sortie.append({'champ': champ, 'avant': None if champ == CLE_CATALOGUE else avant,
                               'apres': None if champ == CLE_CATALOGUE else apres})
        elif not nommes:
            sortie.append({'champ': champ, 'avant': avant, 'apres': apres})
    return sortie


def format_d_avant(ancienne):
    """Une version rangée avant ce suivi (aucun ``catalogue`` dans ses entrées)."""
    return bool(ancienne) and CLE_CATALOGUE not in ancienne
