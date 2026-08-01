/* AOF174 — helper partagé de la ligne « pièce du dossier ».
   Extrait de PieceRow.jsx (react-refresh/only-export-components : un fichier
   de composant ne doit exporter QUE des composants).

   Le serveur peut exprimer « hors contrôle » de deux façons : par le statut
   lui-même (`hors_controle`) ou par le drapeau `controlee=false` d'AOF149 sur
   une pièce fournie à la main. Les deux valent « non vérifiée par la fabrique ». */
export function estHorsControle(piece) {
  return piece?.statut === 'hors_controle' || piece?.controlee === false
}
