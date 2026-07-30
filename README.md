# ORION Developer V1

ORION est un agent développeur contrôlé pour un dépôt GeoStab fictif. Il exécute une mission à la
fois, demande une autorisation humaine avant toute écriture, travaille sur une branche `agent/*`,
teste et audite le diff, produit un rapport, puis s'arrête.

Il ne sait ni fusionner, ni pousser sur `main`, ni déployer, ni supprimer un fichier. Le premier
essai se fait uniquement dans `workspace/geostab-demo`, sans secret, donnée client ou donnée réelle.

## Accès le plus simple : GitHub Codespaces

1. Ouvrir le dépôt GitHub `sarllangas-byte/Orion-developer`.
2. Cliquer **Code** → **Codespaces**.
3. Démarrer le Codespace existant **ORION Developer V1** ou choisir **Create codespace on main**.
4. Dans le terminal du Codespace :

```bash
python -m pytest -q
python scripts/bootstrap_demo.py
python -m agent.main --mission config/mission-rga.example.json --dry-run
python -m agent.main --mission config/mission-rga.example.json
```

À la question d'autorisation, saisir exactement `APPROVE` après avoir lu le plan. Les autres décisions
sont `REJECT`, `REQUEST_CHANGES` et `CANCEL`.

Le script d'amorçage refuse d'écraser un bac à sable existant. Une fois la démonstration créée, ne le
relancez pas dans le même Codespace.

## Accès local

Avec Python 3.11+ et Git :

```bash
git clone https://github.com/sarllangas-byte/Orion-developer.git
cd Orion-developer
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/bootstrap_demo.py
python -m agent.main --mission config/mission-rga.example.json
```

## Commandes utiles

```bash
# Vérifier le workspace et l'état d'arrêt
python -m agent.main status

# Mission libre (GitHub Models optionnel)
python -m agent.main --objective "Votre objectif précis"

# Demander l'arrêt au prochain point sûr
python -m agent.main stop

# Reprendre ensuite : supprimer manuellement le signal d'arrêt
rm STOP_AGENT
```

Sous PowerShell, la dernière commande devient `Remove-Item -LiteralPath STOP_AGENT`.

## Chaîne opérationnelle

```text
MISSION → ANALYSE → PLAN → AUTORISATION → BRANCHE → MODIFICATION
        → TESTS → CORRECTION → AUDIT → RAPPORT → ARRÊT
```

Les missions utilisent les statuts `CREATED`, `ANALYZING`, `PLANNED`, `WAITING_APPROVAL`,
`EXECUTING`, `TESTING`, `CORRECTING`, `COMPLETED`, `FAILED` et `CANCELLED`.

Les traces sont disponibles dans :

- `logs/orion.jsonl` : événements et appels d'outils, sans contenu intégral ;
- `memory/orion.db` : objectifs, plans, décisions, erreurs et changements ;
- `reports/objective-*.md` : rapport lisible avec plan, tests, audit, diff et recommandation ;
- `workspace/geostab-demo` : dépôt Git isolé et sa branche `agent/<id>-<description>`.

## Barrières effectives

- refus de `../`, chemins absolus, `~`, liens symboliques sortants et accès hors workspace ;
- refus de `.env`, `*.pem`, `*.key`, `credentials.json`, `secrets/` et `.git/config` ;
- hash original obligatoire avant remplacement, sauvegarde temporaire et écriture atomique ;
- cinq fichiers maximum par défaut, trois corrections, dix itérations, deux erreurs identiques ;
- commandes exécutées sans shell et seulement si elles figurent dans l'allowlist YAML ;
- aucun choix autonome d'une nouvelle mission après le rapport.

Le score RGA de démonstration est fictif et ne constitue pas un diagnostic géotechnique.

Documentation détaillée : [GUIDE_ORION_DEVELOPER_V1.md](GUIDE_ORION_DEVELOPER_V1.md).
