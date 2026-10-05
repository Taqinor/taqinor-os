"""AGR406 — le segment SUGGÉRÉ d'un lead, calculé à la lecture, JAMAIS écrit.

Contrats : ``apps/crm/contract_samples/lead_pompage.json`` (AGR1, bloc
``segment_suggere``) et ``panneau_appel.json`` (clé ``segment_suggere``).

Un lead arrivé sans type (rappel /contact, import) reçoit aujourd'hui le
script résidentiel « à confirmer ». Ce module lit des SIGNAUX déjà présents
sur la fiche — la première page visitée et des mots d'une liste FERMÉE dans
la note, les notes de visite ou la source — et propose un segment, avec la
raison qui nomme le signal. Il n'écrit RIEN : ni webhook, ni sauvegarde ;
le commercial change le type à la main (D-AGR-9).

Module PUR : aucune requête, aucun import de modèle.
"""
import re

#: Mots du pompage, sur des mots ENTIERS (« pompeux » ne compte pas) —
#: français, anglais, arabe/darija. Liste FERMÉE : un mot qui manque
#: s'ajoute ici, jamais ailleurs.
MOTS_AGRICOLES = (
    'pompe', 'pompes', 'pompage', 'puits', 'forage', 'forages', 'ferme',
    'fermes', 'irrigation', 'irriguer',
    'pump', 'pumps', 'pumping', 'well', 'wells', 'borehole', 'boreholes',
    'farm', 'farms',
    'مضخة', 'المضخة', 'بئر', 'البئر', 'الآبار', 'ثقب', 'الثقب', 'ضيعة',
    'الضيعة', 'مزرعة', 'المزرعة', 'سقي', 'السقي', 'الري',
)

#: Fragment de chemin des pages de pompage (FR/EN/AR : /pompage-solaire,
#: /en/pompage-solaire, /ar/pompage-solaire).
PAGE_AGRICOLE = 'pompage'

#: Champs texte lus, dans l'ordre, avec leur nom dans la raison.
CHAMPS_TEXTE = (
    ('note', "la note d'appel"),
    ('visite_notes', "les notes de visite"),
    ('source', "la source"),
)


def _motif(mots):
    ordonnes = sorted(mots, key=len, reverse=True)
    alternance = '|'.join(re.escape(m) for m in ordonnes)
    return re.compile(r'(?<!\w)(?:%s)(?!\w)' % alternance, re.IGNORECASE)


_MOTIF_AGRICOLE = _motif(MOTS_AGRICOLES)


def _texte(lead, champ):
    valeur = getattr(lead, champ, None)
    return valeur if isinstance(valeur, str) else ''


def _mots_trouves(texte, motif):
    """Les mots de la liste trouvés dans ``texte`` (ordre d'apparition, sans
    doublon, en minuscules)."""
    vus = []
    for trouve in motif.findall(texte or ''):
        mot = trouve.lower()
        if mot not in vus:
            vus.append(mot)
    return vus


def _citer(mots):
    return ' et '.join('« %s »' % m for m in mots)


def _par_mots(lead, motif):
    """``(champ_libelle, [mots])`` du premier champ texte porteur, sinon
    ``None``."""
    for champ, libelle in CHAMPS_TEXTE:
        mots = _mots_trouves(_texte(lead, champ), motif)
        if mots:
            return libelle, mots
    return None


def _suggestion_agricole(lead):
    page = _texte(lead, 'page')
    if PAGE_AGRICOLE in page.lower():
        return {'valeur': 'agricole',
                'raison': '1re page %s' % page.strip()}
    trouve = _par_mots(lead, _MOTIF_AGRICOLE)
    if trouve:
        libelle, mots = trouve
        return {'valeur': 'agricole',
                'raison': '%s mentionne %s' % (libelle, _citer(mots))}
    return None


def segment_suggere(lead):
    """``None`` ou ``{valeur, raison}`` — lecture seule, jamais écrit.

    Toujours ``None`` quand le type du lead vaut déjà « agricole »."""
    if lead is None:
        return None
    type_lead = getattr(lead, 'type_installation', None) or ''
    if type_lead == 'agricole':
        return None
    return _suggestion_agricole(lead)
