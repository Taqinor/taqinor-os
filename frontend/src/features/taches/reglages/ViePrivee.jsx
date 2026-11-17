/* ============================================================================
   TCH108 — Réglages → Vie privée : le texte de vérité, MOT POUR MOT (textes.md §6, figé par
   `Reglages.test.jsx` qui le relit dans la référence). Sous le texte : l'interrupteur
   « Comprendre mon rythme » (réglage `comprendre_mon_rythme`) et le lien « Mes données ».
   ========================================================================== */

import InterrupteurRythme from '../ui/InterrupteurRythme'

const TITRE_VIE_PRIVEE = 'Ce que tu dois savoir sur tes tâches'

const PARAGRAPHES_VIE_PRIVEE = [
  [null, "Tes tâches sont à toi : tes collègues et tes responsables ne les voient pas dans l'ERP. Mais ce n'est pas un coffre-fort."],
  ['Qui peut quand même tout lire.', "Les personnes qui ont accès au serveur, à la base de données ou aux sauvegardes ; un export complet des données de la société ; un compte super-administrateur ; le support quand il agit en ton nom. Si tes collègues utilisent aussi Tâches, « les personnes qui ont accès au serveur » comprennent le dirigeant de la société et les outils de maintenance qu'il emploie. « Confidentielle » cache une tâche, elle ne la chiffre pas."],
  ['Le Copilote.', "À chaque échange, le service d'intelligence artificielle qui fait parler le Copilote (Anthropic ou Groq, une société étrangère) reçoit tes titres de tâches, tes projets, ton rythme, les phrases que tu lui as demandé de retenir, et le nom des fiches liées, donc des noms de clients. Une tâche ou un projet confidentiel ne part jamais avec son titre ni ses notes ; tes rendez-vous y sont seulement des « Rendez-vous ». La conversation, titres compris, reste un temps sur le serveur pour que le Copilote se souvienne de l'échange en cours. Les administrateurs voient l'heure, les outils utilisés et le coût de chaque échange, jamais le texte. Le commentaire d'un 👎 reste lisible par eux. Les quatre demandes prêtes, elles, ne passent pas par ce service."],
  ['Les notifications.', "Chaque message et chaque rappel de Tâches laisse aussi une ligne dans la cloche des notifications de l'ERP : des nombres, les titres seulement si tu les as activés."],
  ['Ton iPhone.', "L'adresse du calendrier vaut une clé : elle se retrouve dans les journaux du serveur, l'historique de Safari et iCloud si tu t'abonnes par iCloud ; les titres y sont visibles, comme sur la tuile. Le raccourci Siri ne contient pas ton jeton : il te le demande à l'installation, puis le garde sur ton iPhone, et peut passer par iCloud ; ce jeton permet d'AJOUTER des tâches, jamais de les lire. Siri ne dit jamais le nom d'un projet confidentiel. Scriptable, l'app de la tuile, garde le jeton de la tuile et une copie des titres du jour. Apple ne voit que des messages chiffrés ; l'écran verrouillé montre des nombres, les titres seulement si tu l'actives. Les messages de Tâches ne partent jamais par e-mail ni par WhatsApp."],
  ['Tes agendas.', "L'adresse d'un agenda que tu ajoutes vaut une clé : l'ERP la garde, ne la montre jamais en entier et lit tes rendez-vous sans les enregistrer."],
  ['Ce qui ne s\'efface pas.', "« Tout effacer » ne touche ni les journaux du serveur, ni les sauvegardes, ni ton téléphone."],
  ['Plusieurs sociétés.', "Changer de société change d'espace de tâches ; ta conversation avec le Copilote, elle, te suit d'une société à l'autre. Les jours suivent l'heure du Maroc, même en voyage."],
  ['Comprendre mon rythme.', "Allumé, l'ERP calcule tes habitudes à partir de tes tâches ; éteint, plus rien n'est calculé ni gardé."],
]

export default function ViePrivee({ allume, onBasculer, onMesDonnees, erreur = '' }) {
  return (
    <div>
      <div className="es-verite">
        <h2>{TITRE_VIE_PRIVEE}</h2>
        {PARAGRAPHES_VIE_PRIVEE.map(([titre, texte]) => (
          <p key={titre ?? texte}>{titre ? <><b>{titre}</b>{' '}{texte}</> : texte}</p>
        ))}
      </div>
      <div className="es-reglages">
        <div className="es-reglage">
          <span className="txt"><b>Comprendre mon rythme</b></span>
          <InterrupteurRythme allume={allume} onBasculer={onBasculer} />
        </div>
        {erreur ? <p className="es-erreur" role="alert">{erreur}</p> : null}
      </div>
      <button type="button" className="es-action-ligne" onClick={onMesDonnees}>Mes données</button>
    </div>
  )
}
