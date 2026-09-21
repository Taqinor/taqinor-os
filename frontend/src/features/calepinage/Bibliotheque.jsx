import { useEffect, useState } from 'react'
import calepinageApi from '../../api/calepinageApi'
import { useHasPermission } from '../../hooks/useHasPermission'
import { Badge, Card, Spinner } from '../../ui'

/* ============================================================================
   CAL201 — L'ÉCRAN « BIBLIOTHÈQUE » DU MODULE (presets, kits, modèles,
   favoris), SOCIÉTÉ ACTIVE RESPECTÉE.
   ----------------------------------------------------------------------------
   Constat : aucune surface frontend n'exposait ces réglages hors du studio
   d'appels d'offres — le module autonome n'avait nulle part où les consulter.

   LES QUATRE LISTES VIENNENT DE DEUX ENDPOINTS, JAMAIS D'UNE TROISIÈME
   FORME (CAL233/CAL246) :
     * `GET /calepinage/parametres/` sert `presets`, `favoris_materiel` (les
       deux sections de `ParametresCalepinage`, CAL197/CAL200) et `kits` (le
       catalogue du module, résolu à la lecture, CAL198/SOLMVP15) ;
     * `GET /calepinage/calepinages/modeles/` sert les calepinages marqués
       MODÈLE (drapeau `records.Tag`, CAL199).

   LECTURE SEULE SANS `calepinage_gerer` (Done de la tâche) : l'écran affiche
   TOUJOURS les quatre listes — seule l'ÉDITION des presets/favoris (les deux
   sections que `PUT /calepinage/parametres/` accepte SANS normaliseur dédié,
   `services/parametres.py::_normaliseurs`) est gardée par la permission.
   Kits et modèles restent lecture seule ICI QUEL QUE SOIT LE DROIT : aucun
   endpoint d'écriture n'existe pour eux depuis cet écran — la tâche ne
   l'invente pas, elle le DIT (PACT159, jamais une promesse en prose).
   ========================================================================== */

function Section({ titre, sousTitre, children }) {
  return (
    <Card className="p-4" data-testid={`cal-biblio-${titre.toLowerCase()}`}>
      <p className="text-sm font-semibold text-foreground">{titre}</p>
      {sousTitre && <p className="mt-0.5 text-xs text-muted-foreground">{sousTitre}</p>}
      <div className="mt-3">{children}</div>
    </Card>
  )
}

function ListeVide({ enfant }) {
  return <p className="text-sm text-muted-foreground">{enfant}</p>
}

/* ============================================================================
   CALX30 — LES PROFILS TYPES DE CONSOMMATION, ÉDITABLES ICI.
   ----------------------------------------------------------------------------
   `views/consommation.py` sert `GET/PUT parametres/profils-types/` depuis
   CAL149 et n'avait AUCUN consommateur : la société ne pouvait pas saisir la
   forme de ses journées, donc tout le dépôt retombait sur les profils CODÉS
   (`apps/ventes/solar_design.py`) — ceux qui décident du taux
   d'autoconsommation, donc de la taille du champ et de la batterie vendus.

   LES DEUX RÈGLES QUE CET ÉCRAN NE PEUT PAS ENFREINDRE :
   1. **Un repli reste un repli.** Le serveur l'étiquette `hypothese_interne`
      et publie sa provenance ; l'écran l'AFFICHE comme tel, ne l'édite pas et
      ne le renvoie JAMAIS dans le PUT — sinon une hypothèse interne
      deviendrait une « saisie de la société », c'est-à-dire une mesure.
   2. **Aucune valeur n'est inventée ici.** Un profil neuf part avec ses
      champs VIDES : c'est le serveur (`ProfilTypeConsommation.clean`) qui
      refuse une provenance vide ou une courbe absente, et son motif s'affiche
      SOUS le profil fautif.
   ========================================================================== */

//: Le serveur étiquette ainsi tout profil qui n'est PAS une saisie société.
const SOURCE_REPLI = 'hypothese_interne'

//: `ProfilTypeConsommation.Famille` — les familles ADMISES par le serveur.
const FAMILLES = [
  ['residentiel', 'Résidentiel'],
  ['commercial', 'Commercial / tertiaire'],
  ['industriel', 'Industriel'],
  ['agricole', 'Agricole'],
  ['autre', 'Autre'],
]

/** `{rang, message}` du refus serveur, ramené au profil ENVOYÉ qu'il NOMME.
 *
 * `services/profils_types.py` nomme son champ de quatre façons :
 * `profils`, `profils[N].cle`, `<cle>` et `<cle>.<champ>`. `rang` est
 * l'indice DANS LA LISTE ENVOYÉE, `null` quand le refus porte sur la liste
 * entière (ou sur la société). Le message est celui du serveur, mot pour mot.
 */
function refusProfil(erreur, clesEnvoyees) {
  const aucunMotif = {
    rang: null,
    message: "Le serveur n’a rendu aucun motif : rien n’a été enregistré.",
  }
  const corps = erreur?.response?.data
  if (!corps || typeof corps !== 'object') return aucunMotif
  const entree = Object.entries(corps)[0]
  if (!entree) return aucunMotif
  const [champ, brut] = entree
  const message = Array.isArray(brut) ? brut.join(' ') : String(brut)
  const indice = /^profils\[(\d+)\]/.exec(champ)
  if (indice) return { rang: Number(indice[1]), message }
  const racine = champ.split('.')[0]
  const rang = clesEnvoyees.indexOf(racine)
  return { rang: rang >= 0 ? rang : null, message }
}

/** La courbe annuelle SERVIE, telle quelle — jamais arrondie (arrondir un
 *  poids, c'est le changer). Les autres saisons ne sont pas éditées ici et
 *  traversent intactes. */
function texteCourbeAnnuelle(profil) {
  const annuel = (profil.courbes ?? {}).annuel
  return Array.isArray(annuel) ? annuel.join(', ') : ''
}

/** Le profil, sous la forme que `PUT profils-types/` attend (`courbe`, au
 *  singulier — le GET sert `courbes`, normalisées). */
function corpsProfil(profil) {
  const courbe = { ...(profil.courbes ?? {}) }
  const texte = (profil.courbeTexte ?? '').trim()
  if (texte) {
    // Une valeur illisible part TELLE QUELLE : c'est le serveur qui juge et
    // qui nomme le champ, pas l'écran qui devine un nombre de remplacement.
    courbe.annuel = texte.split(',').map((brut) => {
      const valeur = brut.trim()
      const nombre = Number(valeur)
      return valeur !== '' && Number.isFinite(nombre) ? nombre : valeur
    })
  } else {
    delete courbe.annuel
  }
  const corps = {
    cle: profil.cle,
    libelle: profil.libelle,
    courbe,
    provenance: profil.provenance,
    actif: profil.actif !== false,
  }
  // Famille non choisie : on ne l'envoie PAS — le serveur applique alors son
  // propre défaut documenté, plutôt que l'écran qui en invente un.
  if (profil.famille) corps.famille = profil.famille
  return corps
}

export default function Bibliotheque() {
  const peutGerer = useHasPermission('calepinage_gerer')

  const [parametres, setParametres] = useState(null)
  const [modeles, setModeles] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState(null)
  // CALX30 — les profils types, SERVIS puis édités sur place. `refusProfils`
  // porte la clé du profil fautif : l'erreur s'affiche SOUS lui, jamais en
  // haut de page comme un « non enregistré » anonyme.
  const [profils, setProfils] = useState(null)
  const [refusProfils, setRefusProfils] = useState(null)
  const [enregistrementProfils, setEnregistrementProfils] = useState(false)

  useEffect(() => {
    let annule = false
    Promise.all([
      Promise.resolve(calepinageApi.parametres.get()),
      Promise.resolve(calepinageApi.calepinages.modeles()),
      Promise.resolve(calepinageApi.parametres.profilsTypes()),
    ])
      .then(([resParametres, resModeles, resProfils]) => {
        if (annule) return
        setParametres(resParametres?.data ?? null)
        const liste = resModeles?.data
        setModeles(Array.isArray(liste) ? liste : (liste?.results ?? []))
        const servis = resProfils?.data?.profils
        setProfils((Array.isArray(servis) ? servis : []).map((profil) => ({
          ...profil, courbeTexte: texteCourbeAnnuelle(profil),
        })))
      })
      .catch((e) => {
        if (annule) return
        setErreur(e?.response?.data?.detail
          || 'La bibliothèque n’a pas pu être chargée.')
      })
      .finally(() => { if (!annule) setChargement(false) })
    return () => { annule = true }
  }, [])

  if (chargement) {
    return <div className="page" data-testid="cal-bibliotheque"><Spinner /></div>
  }
  if (erreur) {
    return (
      <div className="page" data-testid="cal-bibliotheque">
        <p role="alert" className="text-sm text-destructive"
          data-testid="cal-biblio-erreur">{erreur}</p>
      </div>
    )
  }

  const presets = parametres?.presets ?? {}
  const favoris = parametres?.favoris_materiel ?? {}
  const kits = Array.isArray(parametres?.kits) ? parametres.kits : []

  const clesPresets = Object.keys(presets)
  const clesFavoris = Object.keys(favoris)

  // ── CALX30 — les gestes des profils types ────────────────────────────────
  const lignesProfils = profils ?? []
  const estRepli = (profil) => profil.source === SOURCE_REPLI

  const majProfil = (rang, champ, valeur) => {
    setProfils((liste) => (liste ?? []).map(
      (profil, i) => (i === rang ? { ...profil, [champ]: valeur } : profil)))
  }
  const retirerProfil = (rang) => {
    setRefusProfils(null)
    setProfils((liste) => (liste ?? []).filter((_, i) => i !== rang))
  }
  const ajouterProfil = () => {
    setRefusProfils(null)
    // TOUT VIDE : aucune valeur par défaut n'est inventée ici. C'est le
    // serveur qui refuse, et son motif s'affiche sous ce profil.
    setProfils((liste) => [...(liste ?? []), {
      id: null, cle: '', libelle: '', famille: '', provenance: '',
      source: 'societe', courbes: {}, courbeTexte: '',
    }])
  }

  // Les rangs AFFICHÉS des profils qui partent au serveur (les replis, eux,
  // ne partent jamais) : c'est la table de correspondance qui ramène un refus
  // « profils[N] » sur la bonne ligne de l'écran.
  const rangsEnvoyes = lignesProfils
    .map((profil, rang) => (estRepli(profil) ? null : rang))
    .filter((rang) => rang !== null)
  const rangFautif = refusProfils && refusProfils.rang !== null
    ? rangsEnvoyes[refusProfils.rang] ?? null
    : null

  const enregistrerProfils = async () => {
    const aSoumettre = lignesProfils.filter((profil) => !estRepli(profil))
    setEnregistrementProfils(true)
    setRefusProfils(null)
    try {
      const res = await calepinageApi.parametres.enregistrerProfilsTypes(
        aSoumettre.map(corpsProfil))
      const servis = res?.data?.profils
      if (Array.isArray(servis)) {
        setProfils(servis.map((profil) => ({
          ...profil, courbeTexte: texteCourbeAnnuelle(profil),
        })))
      }
    } catch (e) {
      setRefusProfils(refusProfil(e, aSoumettre.map((p) => p.cle)))
    } finally {
      setEnregistrementProfils(false)
    }
  }

  return (
    <div className="page" data-testid="cal-bibliotheque">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="text-lg font-semibold text-foreground">Bibliothèque</h1>
        {!peutGerer && (
          <Badge variant="outline" data-testid="cal-biblio-lecture-seule">
            Lecture seule
          </Badge>
        )}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Presets, kits de pose, calepinages modèles et matériel favori de votre
        société — réutilisés à chaque conception, jamais réinventés.
      </p>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Section titre="Presets"
          sousTitre="Marges, espacements et dégagements réutilisés (CAL197)">
          {clesPresets.length === 0
            ? <ListeVide enfant="Aucun preset réglé : les valeurs de l’atelier s’appliquent." />
            : (
              <ul className="space-y-1 text-sm text-foreground" data-testid="cal-biblio-presets-liste">
                {clesPresets.map((cle) => (
                  <li key={cle} data-testid={`cal-biblio-preset-${cle}`}>
                    <span className="font-medium">{cle}</span>
                    {' — '}
                    <span className="text-muted-foreground">
                      {Object.entries(presets[cle] ?? {})
                        .map(([champ, valeur]) => `${champ} : ${valeur}`)
                        .join(', ') || 'aucun champ'}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          {!peutGerer && (
            <p className="mt-2 text-xs text-muted-foreground">
              Sans le droit « gérer le calepinage », la création/édition des
              presets n’est pas proposée ici.
            </p>
          )}
        </Section>

        <Section titre="Kits"
          sousTitre="Catalogue de pose du stock, lu (jamais dupliqué, CAL198)">
          {kits.length === 0
            ? <ListeVide enfant="Aucun kit de pose disponible pour votre société." />
            : (
              <ul className="space-y-1 text-sm text-foreground" data-testid="cal-biblio-kits-liste">
                {kits.map((kit) => (
                  <li key={kit.id} data-testid={`cal-biblio-kit-${kit.id}`}>
                    <span className="font-medium">{kit.libelle || kit.code}</span>
                    {' — '}
                    <span className="text-muted-foreground">
                      {kit.modules_par_kit != null
                        ? `${kit.modules_par_kit} module(s)/kit`
                        : 'composition non renseignée'}
                      {kit.puissance_module_w ? ` · ${kit.puissance_module_w} W` : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          <p className="mt-2 text-xs text-muted-foreground">
            Catalogue en lecture seule depuis cet écran : gérez-le depuis le
            stock.
          </p>
        </Section>

        <Section titre="Modèles"
          sousTitre="Calepinages marqués réutilisables (CAL199)">
          {(modeles ?? []).length === 0
            ? <ListeVide enfant="Aucun calepinage n’est marqué modèle." />
            : (
              <ul className="space-y-1 text-sm text-foreground" data-testid="cal-biblio-modeles-liste">
                {modeles.map((modele) => (
                  <li key={modele.id} data-testid={`cal-biblio-modele-${modele.id}`}>
                    <span className="font-medium">
                      {modele.titre || `Calepinage #${modele.id}`}
                    </span>
                    {modele.statut_libelle && (
                      <span className="text-muted-foreground"> — {modele.statut_libelle}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
        </Section>

        <Section titre="Favoris matériel"
          sousTitre="Modules et onduleurs favoris du catalogue (CAL200)">
          {clesFavoris.length === 0
            ? <ListeVide enfant="Aucun matériel favori réglé pour votre société." />
            : (
              <ul className="space-y-1 text-sm text-foreground" data-testid="cal-biblio-favoris-liste">
                {clesFavoris.map((cle) => {
                  const ids = Array.isArray(favoris[cle]) ? favoris[cle] : []
                  return (
                    <li key={cle} data-testid={`cal-biblio-favori-${cle}`}>
                      <span className="font-medium">{cle}</span>
                      {' — '}
                      <span className="text-muted-foreground">
                        {ids.length > 0
                          ? `${ids.length} produit(s) (#${ids.join(', #')})`
                          : 'aucun produit'}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
          {!peutGerer && (
            <p className="mt-2 text-xs text-muted-foreground">
              Sans le droit « gérer le calepinage », la création/édition des
              favoris n’est pas proposée ici.
            </p>
          )}
        </Section>
      </div>

      {/* CALX30 — LES PROFILS TYPES, la section éditable. Elle est SOUS la
          grille parce qu'une courbe de 24 poids ne tient pas dans une demi-
          colonne. */}
      <div className="mt-4">
        <Section titre="Profils types"
          sousTitre="Courbes de consommation de la société (CAL149) — la saisie de la société l’emporte toujours sur un repli">
          {lignesProfils.length === 0
            ? <ListeVide enfant="Aucun profil type servi pour votre société." />
            : (
              <ul className="space-y-3" data-testid="cal-biblio-profils-liste">
                {lignesProfils.map((profil, rang) => (
                  <li key={profil.id ?? `rang-${rang}`}
                    className="border border-border p-3"
                    data-testid={`cal-biblio-profil-${rang}`}>
                    {estRepli(profil) ? (
                      <>
                        {/* UN REPLI RESTE UN REPLI : étiqueté, non éditable,
                            jamais renvoyé comme une saisie de la société. */}
                        <p className="text-sm font-medium text-foreground">
                          {profil.libelle || profil.cle}
                          {' '}
                          <Badge variant="outline"
                            data-testid={`cal-biblio-profil-repli-${rang}`}>
                            Hypothèse interne
                          </Badge>
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground"
                          data-testid={`cal-biblio-profil-provenance-${rang}`}>
                          {profil.provenance}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          Ce profil n’est PAS une mesure : il n’est pas
                          modifiable ici et n’est jamais enregistré comme un
                          profil de votre société. Ajoutez le vôtre pour qu’il
                          prenne sa place.
                        </p>
                      </>
                    ) : (
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <label className="text-xs text-muted-foreground">
                          Clé
                          <input type="text" value={profil.cle ?? ''}
                            disabled={!peutGerer || enregistrementProfils}
                            data-testid={`cal-biblio-profil-cle-${rang}`}
                            onChange={(e) => majProfil(rang, 'cle', e.target.value)}
                            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                        </label>
                        <label className="text-xs text-muted-foreground">
                          Libellé
                          <input type="text" value={profil.libelle ?? ''}
                            disabled={!peutGerer || enregistrementProfils}
                            data-testid={`cal-biblio-profil-libelle-${rang}`}
                            onChange={(e) => majProfil(rang, 'libelle', e.target.value)}
                            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                        </label>
                        <label className="text-xs text-muted-foreground">
                          Famille
                          <select value={profil.famille ?? ''}
                            disabled={!peutGerer || enregistrementProfils}
                            data-testid={`cal-biblio-profil-famille-${rang}`}
                            onChange={(e) => majProfil(rang, 'famille', e.target.value)}
                            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground">
                            <option value="">Choisir une famille</option>
                            {FAMILLES.map(([code, libelle]) => (
                              <option key={code} value={code}>{libelle}</option>
                            ))}
                          </select>
                        </label>
                        <label className="text-xs text-muted-foreground">
                          Provenance (obligatoire)
                          <input type="text" value={profil.provenance ?? ''}
                            disabled={!peutGerer || enregistrementProfils}
                            data-testid={`cal-biblio-profil-provenance-${rang}`}
                            onChange={(e) => majProfil(rang, 'provenance', e.target.value)}
                            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                        </label>
                        <label className="text-xs text-muted-foreground sm:col-span-2">
                          Courbe annuelle — 24 poids séparés par des virgules
                          <input type="text" value={profil.courbeTexte ?? ''}
                            disabled={!peutGerer || enregistrementProfils}
                            data-testid={`cal-biblio-profil-courbe-${rang}`}
                            onChange={(e) => majProfil(rang, 'courbeTexte', e.target.value)}
                            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                        </label>
                        {peutGerer && (
                          <div className="sm:col-span-2">
                            <button type="button" disabled={enregistrementProfils}
                              className="text-xs text-destructive underline"
                              data-testid={`cal-biblio-profil-retirer-${rang}`}
                              onClick={() => retirerProfil(rang)}>
                              Retirer ce profil
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* L'ERREUR SOUS LE PROFIL FAUTIF, celui que le serveur
                        a NOMMÉ — jamais ailleurs. */}
                    {rangFautif === rang && (
                      <p className="mt-2 text-xs text-destructive" role="alert"
                        data-testid={`cal-biblio-profil-erreur-${rang}`}>
                        {refusProfils.message}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}

          {peutGerer ? (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button type="button" disabled={enregistrementProfils}
                className="text-sm font-semibold underline"
                data-testid="cal-biblio-profil-ajouter"
                onClick={ajouterProfil}>
                Ajouter un profil
              </button>
              <button type="button" disabled={enregistrementProfils}
                className="text-sm font-semibold underline"
                data-testid="cal-biblio-profils-enregistrer"
                onClick={enregistrerProfils}>
                Enregistrer les profils
              </button>
            </div>
          ) : (
            <p className="mt-2 text-xs text-muted-foreground">
              Sans le droit « gérer le calepinage », les profils types se
              consultent mais ne se modifient pas ici.
            </p>
          )}

          {/* Un refus qui ne vise AUCUN profil (la liste entière) : il est
              dit ici, avec le motif du serveur, jamais réécrit. */}
          {refusProfils && rangFautif === null && (
            <p className="mt-2 text-xs text-destructive" role="alert"
              data-testid="cal-biblio-profils-erreur">
              {refusProfils.message}
            </p>
          )}
        </Section>
      </div>
    </div>
  )
}
