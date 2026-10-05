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
    # « well » est écarté : trop courant en anglais (« as well »).
    'pump', 'pumps', 'pumping', 'borehole', 'boreholes', 'farm', 'farms',
    'مضخة', 'المضخة', 'بئر', 'البئر', 'الآبار', 'ثقب', 'الثقب', 'ضيعة',
    'الضيعة', 'مزرعة', 'المزرعة', 'سقي', 'السقي', 'الري',
)

#: CIQ409 — mots d'industrie (ils l'emportent sur un mot de commerce).
MOTS_INDUSTRIELS = (
    'usine', 'usines', 'industrie', 'industriel', 'industrielle', 'atelier',
    'ateliers', 'hangar', 'hangars',
    'factory', 'factories', 'industry', 'workshop', 'warehouse',
    'مصنع', 'المصنع', 'معمل', 'المعمل', 'ورشة', 'الورشة',
)

#: CIQ409 — mots de commerce et de services (accentués ET non accentués :
#: une note tapée vite perd ses accents).
MOTS_COMMERCIAUX = (
    'société', 'societe', 'entreprise', 'hôtel', 'hotel', 'riad',
    'restaurant', 'café', 'cafe', 'clinique', 'cabinet', 'école', 'ecole',
    'magasin', 'supermarché', 'supermarche', 'boulangerie', 'hammam',
    'bureau', 'bureaux',
    'company', 'clinic', 'school', 'shop', 'store',
    'supermarket', 'bakery', 'office',
    'شركة', 'الشركة', 'فندق', 'الفندق', 'رياض', 'مطعم', 'المطعم', 'مقهى',
    'المقهى', 'مصحة', 'المصحة', 'مدرسة', 'المدرسة', 'محل', 'المحل', 'مخبزة',
    'المخبزة', 'حمام', 'الحمام',
)

#: Segments « pro » : jamais de suggestion pro pour un lead déjà typé ainsi.
SEGMENTS_PRO = ('commercial', 'industriel')

#: Fragment de chemin des pages de pompage (FR/EN/AR : /pompage-solaire,
#: /en/pompage-solaire, /ar/pompage-solaire).
PAGE_AGRICOLE = 'pompage'

#: CIQ409 — fragment de chemin de la page pro (/professionnel FR/EN/AR).
PAGE_PRO = 'professionnel'

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
_MOTIF_INDUSTRIEL = _motif(MOTS_INDUSTRIELS)
_MOTIF_COMMERCIAL = _motif(MOTS_COMMERCIAUX)


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


def _vide(valeur):
    return valeur is None or (isinstance(valeur, str) and not valeur.strip())


def _suggestion_pro(lead):
    """CIQ409 — commercial ou industriel, dans cet ordre de force : un mot
    d'industrie l'emporte sur tout ; puis la page /professionnel, un mot de
    commerce, une raison sociale, et enfin une conso connue SEULEMENT en
    kWh (``bill_kwh`` sans facture en dirhams ni conso mensuelle)."""
    trouve = _par_mots(lead, _MOTIF_INDUSTRIEL)
    if trouve:
        libelle, mots = trouve
        return {'valeur': 'industriel',
                'raison': '%s mentionne %s' % (libelle, _citer(mots))}
    page = _texte(lead, 'page')
    if PAGE_PRO in page.lower():
        return {'valeur': 'commercial',
                'raison': '1re page %s' % page.strip()}
    trouve = _par_mots(lead, _MOTIF_COMMERCIAL)
    if trouve:
        libelle, mots = trouve
        return {'valeur': 'commercial',
                'raison': '%s mentionne %s' % (libelle, _citer(mots))}
    societe = _texte(lead, 'societe').strip()
    if societe:
        return {'valeur': 'commercial',
                'raison': 'le lead porte une raison sociale (« %s »)'
                          % societe}
    if (not _vide(getattr(lead, 'bill_kwh', None))
            and _vide(getattr(lead, 'facture_hiver', None))
            and _vide(getattr(lead, 'conso_mensuelle_kwh', None))):
        return {'valeur': 'commercial',
                'raison': 'seule une consommation en kWh est connue'}
    return None


def segment_suggere(lead):
    """``None`` ou ``{valeur, raison}`` — lecture seule, jamais écrit.

    Le pompage d'abord (AGR406 ; ``None`` pour ce signal quand le type vaut
    déjà « agricole »), puis le pro (CIQ409 ; jamais proposé à un lead déjà
    commercial, industriel ou agricole)."""
    if lead is None:
        return None
    type_lead = getattr(lead, 'type_installation', None) or ''
    if type_lead == 'agricole':
        return None
    agricole = _suggestion_agricole(lead)
    if agricole is not None:
        return agricole
    if type_lead in SEGMENTS_PRO:
        return None
    return _suggestion_pro(lead)
