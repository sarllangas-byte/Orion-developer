Produis un objet JSON {"changes": [...]}.

Chaque élément de changes contient exactement path, content, reason. content est le contenu intégral
du fichier. Ne supprime aucun fichier. N'ajoute aucun secret, dépendance ou commande. Ne modifie que
les chemins autorisés par le plan. Le résultat doit être du JSON brut, sans balises Markdown.
