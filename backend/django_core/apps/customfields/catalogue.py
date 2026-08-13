"""NTEXT34 — catalogue de MODÈLES d'objets personnalisés prêts à l'emploi.

Créer un objet no-code demande aujourd'hui de deviner ses champs un par un.
Ce catalogue propose des objets TYPES éprouvés (registre de visiteurs, prêt de
matériel, suivi de garantie fournisseur…) : un clic pose l'objet ET ses champs
pour la société.

Le catalogue est une CONSTANTE de code (pas une table) : il n'y a rien à
administrer ni à migrer, et une société ne peut pas s'en écarter par accident.
L'installation est IDEMPOTENTE (``get_or_create`` sur la clé naturelle
``(company, code)`` de l'objet et ``(company, module, code)`` du champ) : ré-
installer ne duplique rien et n'écrase JAMAIS une personnalisation locale
(libellé changé, champ ajouté), ni ne touche aux enregistrements saisis.
"""
__all__ = ['CATALOGUE', 'modele_par_code', 'installer_modele']


def _champ(code, libelle, type_='text', **extra):
    champ = {'code': code, 'libelle': libelle, 'type': type_,
             'obligatoire': False, 'visible_liste': False}
    champ.update(extra)
    return champ


#: Modèles d'objets prêts à l'emploi (ordre = ordre d'affichage).
CATALOGUE = (
    {
        'code': 'registre-visiteurs',
        'libelle': 'Registre de visiteurs',
        'icone': '🚪',
        'description': "Qui entre sur un site, quand, pour voir qui.",
        'champs': [
            _champ('visiteur', 'Nom du visiteur', obligatoire=True,
                   visible_liste=True),
            _champ('societe', 'Société'),
            _champ('motif', 'Motif de la visite', visible_liste=True),
            _champ('date_entree', 'Date d\'entrée', 'date',
                   obligatoire=True, visible_liste=True),
            _champ('date_sortie', 'Date de sortie', 'date'),
            _champ('personne_visitee', 'Personne visitée'),
        ],
    },
    {
        'code': 'pret-materiel',
        'libelle': 'Prêt de matériel',
        'icone': '🧰',
        'description': "Quel matériel est sorti, par qui, et quand il revient.",
        'champs': [
            _champ('materiel', 'Matériel prêté', obligatoire=True,
                   visible_liste=True),
            _champ('emprunteur', 'Emprunteur', obligatoire=True,
                   visible_liste=True),
            _champ('date_pret', 'Date du prêt', 'date', obligatoire=True,
                   visible_liste=True),
            _champ('date_retour_prevue', 'Retour prévu', 'date',
                   visible_liste=True),
            _champ('rendu', 'Rendu', 'boolean', visible_liste=True),
        ],
    },
    {
        'code': 'garantie-fournisseur',
        'libelle': 'Suivi de garantie fournisseur',
        'icone': '🛡️',
        'description': "Les garanties en cours côté fournisseur et leur échéance.",
        'champs': [
            _champ('fournisseur', 'Fournisseur', obligatoire=True,
                   visible_liste=True),
            _champ('reference_produit', 'Référence produit',
                   visible_liste=True),
            _champ('numero_serie', 'Numéro de série'),
            _champ('debut_garantie', 'Début de garantie', 'date'),
            _champ('fin_garantie', 'Fin de garantie', 'date',
                   obligatoire=True, visible_liste=True),
            _champ('statut_reclamation', 'Statut de réclamation', 'choice',
                   options=['Aucune', 'Ouverte', 'Acceptée', 'Refusée']),
        ],
    },
)


def modele_par_code(code):
    """Le modèle de catalogue portant ``code``, ou ``None``."""
    cible = (code or '').strip().lower()
    for modele in CATALOGUE:
        if modele['code'] == cible:
            return modele
    return None


def installer_modele(company, modele, *, created_by=None):
    """Pose l'objet + ses champs pour ``company``. Idempotent.

    Renvoie ``(objet, cree, champs_crees)``. Les définitions déjà présentes
    sont laissées TELLES QUELLES (une personnalisation locale n'est jamais
    écrasée) et les enregistrements existants ne sont jamais touchés.
    """
    from .models import CustomFieldDef, CustomObjectDef

    objet, cree = CustomObjectDef.objects.get_or_create(
        company=company, code=modele['code'],
        defaults={'libelle': modele['libelle'],
                  'icone': modele.get('icone', ''),
                  'created_by': created_by})
    champs_crees = 0
    for ordre, champ in enumerate(modele.get('champs') or [], start=1):
        _, champ_cree = CustomFieldDef.objects.get_or_create(
            company=company, module=objet.field_module, code=champ['code'],
            defaults={
                'libelle': champ['libelle'],
                'type': champ.get('type', 'text'),
                'obligatoire': champ.get('obligatoire', False),
                'visible_liste': champ.get('visible_liste', False),
                'options': champ.get('options'),
                'ordre': ordre,
            })
        champs_crees += 1 if champ_cree else 0
    return objet, cree, champs_crees
