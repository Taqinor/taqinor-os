"""AOOM1 — LES CLÉS D'``etude_params`` QU'UNE LISTE LIT, SERVIES PAR SQL.

Pourquoi ce module minuscule — et pourquoi il n'importe RIEN (incident du
02/11/2026, mesuré sur la copie anonymisée de la production) :

``GET /api/django/crm/leads/?page_size=200`` chargeait les 225 devis de la page
AVEC leur ``etude_params`` entier — 39,3 Mio des 40,3 Mio de JSON de la page,
jusqu'à 1,45 Mio pour UN devis (étude horaire C&I) — décodés en ~123 Mio
d'objets Python (1,9 M de blocs dans ``json/decoder.py``) pour y lire DEUX
petites clés. Chaque requête laissait +254 Mio de RSS définitifs par worker :
4 threads × 3 workers ont saturé la limite de 3 Gio du conteneur et le noyau a
tué les workers 17 fois dans la journée (premier kill à 08:32 UTC), ce que
l'écran a vu comme « problème de connexion » (49 abandons client en 20 s).

La liste ``defer('etude_params')`` et annote ces deux clés
(``apps.ventes.selectors.prefetch_devis_liste_leads``) ; les lecteurs passent
par :func:`cle_etude`, qui préfère l'annotation quand elle est posée et retombe
MOT POUR MOT sur le JSON sinon (détail, moteur PDF, Celery, shell).

AUCUN IMPORT : ``multivilla`` (contrat import-linter M1 : ``models.py``
l'appelle sans tirer ``selectors`` et ses dépendances inter-apps) et
``utils.options`` en dépendent tous les deux, donc ce module doit rester une
feuille.
"""

#: Chemin dans ``etude_params`` → nom de l'attribut annoté qui le porte. Un
#: chemin est une clé (``'scenario'``) ou un tuple de clés imbriquées
#: (``('resync_apres_envoi', 'date')``).
#:
#: AJOUTER UN CHEMIN ICI, JAMAIS UN LITTÉRAL AILLEURS : le sélecteur construit
#: les annotations depuis cette table, et :func:`cle_etude` les relit. Un
#: chemin absent d'ici reste lu dans le JSON — donc, sur une liste qui a
#: déferré le champ, UNE REQUÊTE PAR DEVIS : le budget de requêtes
#: (``apps/crm/tests_perf_n1_leads.py``) rougit, il ne se tait pas. C'est
#: ainsi que les trois lecteurs de l'incident du 02/11/2026 ont été trouvés,
#: un par un, au lieu d'être devinés.
ANNOTATION_PAR_CLE = {
    # QJR400 — le scénario déclaré (``utils.options.scenario_declare``).
    'scenario': 'scenario_stocke',
    # QJ29 — le multiplicateur ×N villas identiques
    # (``multivilla.nombre_proprietes``), qui FAIT l'argent du devis.
    'nombre_proprietes': 'nombre_proprietes_stocke',
    # QJR566 — date de la dernière correction après envoi
    # (``apps.crm.lead_devis_payload._corrige_le``).
    ('resync_apres_envoi', 'date'): 'resync_apres_envoi_date_stocke',
}


def cle_etude(devis, chemin, defaut=None):
    """La valeur d'``etude_params`` au ``chemin`` donné, annotation d'abord.

    ``chemin`` : une clé, ou un tuple de clés imbriquées.

    * attribut annoté présent (liste : ``etude_params`` déferré) → sa valeur,
      ``defaut`` quand elle est ``NULL`` (chemin absent en base) ;
    * sinon → la descente dans le JSON, à l'octet comme avant.

    L'annotation est ``etude_params -> … -> derniere_cle`` (``->`` partout,
    jamais ``->>``) : la valeur reste du jsonb que Django redécode, donc du
    MÊME TYPE que la lecture du JSON — un entier revient ``int``, une chaîne
    ``str``. Une traversée qui tombe sur autre chose qu'un objet (un
    ``resync_apres_envoi`` booléen hérité) rend ``NULL`` côté SQL comme
    ``defaut`` côté Python : les deux chemins répondent la même chose.
    """
    annote = ANNOTATION_PAR_CLE.get(chemin)
    if annote is not None and hasattr(devis, annote):
        valeur = getattr(devis, annote)
        return defaut if valeur is None else valeur
    valeur = getattr(devis, 'etude_params', None)
    for cle in ((chemin,) if isinstance(chemin, str) else chemin):
        if not isinstance(valeur, dict):
            return defaut
        valeur = valeur.get(cle)
    return defaut if valeur is None else valeur
