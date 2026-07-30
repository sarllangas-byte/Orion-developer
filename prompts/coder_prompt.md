Produis uniquement un objet JSON {"changes": [...]}.

Chaque changement contient exactement operation, file, reason, original_hash, content. operation
vaut create ou replace. content est le contenu intégral du fichier. Ne supprime aucun fichier,
n'ajoute aucun secret, dépendance ou commande et ne sors pas du plan approuvé.
