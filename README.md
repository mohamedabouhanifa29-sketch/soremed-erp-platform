# SOREMED

SOREMED est une plateforme locale de gestion commerciale et de stock. Elle réunit une interface pour l'équipe interne et un portail client, avec authentification et rôles.

## Fonctionnalités

- Gestion des produits, catégories, fournisseurs, clients, achats, réceptions et mouvements de stock.
- Portail client : catalogue, favoris, panier, commandes et profil.
- Validation des comptes clients et des commandes par l'équipe autorisée.
- Tableaux de bord, rapports, journal d'audit, import Excel et assistant métier local.

## Architecture

Le navigateur accède à Nginx, qui sert React et transmet `/api/` à FastAPI. L'API utilise PostgreSQL dans Docker. Seul le port HTTP de Nginx est publié ; les données PostgreSQL restent dans le volume Docker `postgres_data`. Les fichiers chargés sont stockés dans `uploads/` sur l'hôte. Voir [l'architecture détaillée](docs/ARCHITECTURE.md).

| Service | Technologies | Rôle |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite, Nginx | Interface web et proxy API |
| Backend | FastAPI, SQLAlchemy, Alembic, Python | API et logique métier |
| Base | PostgreSQL 17 | Données applicatives |

## Démarrage avec Docker

Prérequis : Docker Desktop avec Docker Compose. Sur Windows, PowerShell est utilisé pour les scripts fournis.

Depuis `plateforme-locale/` :

```powershell
Copy-Item .\.env.example .\docker\.env
```

Modifiez `docker/.env` : choisissez un mot de passe PostgreSQL et administrateur forts, une clé JWT longue et aléatoire, une adresse administrateur, ainsi que `CORS_ORIGINS` et `HTTP_PORT` adaptés au serveur. Le fichier est ignoré par Git. N'utilisez pas les valeurs d'exemple en production. Si le mot de passe PostgreSQL d'une installation existante change, il faut aussi le modifier dans la base PostgreSQL ; changer seulement `.env` ne modifie pas le volume existant.

```powershell
.\docker\start.ps1
```

Équivalent sans script :

```powershell
docker compose --env-file docker/.env -f docker/docker-compose.yml up -d --build
docker compose --env-file docker/.env -f docker/docker-compose.yml ps
```

Ouvrez `http://localhost` (ou `http://localhost:PORT` si `HTTP_PORT` diffère de 80). Depuis le réseau local, utilisez l'adresse IP du serveur et ce même port. La page de connexion est `/login` et la documentation API est `/api/docs`. Le compte initial utilise `BOOTSTRAP_ADMIN_EMAIL` et `BOOTSTRAP_ADMIN_PASSWORD` lors de la première création ; changez ensuite son mot de passe dans l'application.

Pour consulter les journaux :

```powershell
docker compose --env-file docker/.env -f docker/docker-compose.yml logs --tail 100 backend frontend database
```

## Données et sécurité

Les fichiers `.env`, bases SQLite historiques, sauvegardes, dépôts de fichiers, caches et dépendances locales sont exclus du dépôt et des contextes de build Docker. Ne les ajoutez jamais avec `git add -f`. Une base SQLite ancienne ne sert pas à l'installation Docker actuelle, mais elle peut être conservée localement pour référence. Ne lancez pas `docker compose down -v` si vous voulez conserver les données PostgreSQL.

Les sauvegardes PostgreSQL s'effectuent avec `database/backup.ps1` et la restauration explicite avec `database/restore.ps1`. Une restauration remplace des données : vérifiez la sauvegarde et effectuez un essai sur une instance distincte. L'ancienne fonction de sauvegarde de l'interface concerne uniquement SQLite et n'est pas utilisable avec PostgreSQL.

Pour un serveur Windows sur le réseau local, voir [le guide de déploiement](docs/DEPLOIEMENT_WINDOWS_LAN.md).

## Structure

```text
plateforme-locale/
├── backend/          API, modèles, migrations Alembic et tests
├── frontend/         application React et configuration Nginx
├── docker/           Compose et script de démarrage
├── database/         scripts de sauvegarde PostgreSQL
├── docs/             architecture et déploiement Windows
├── uploads/          répertoire de fichiers chargés (.gitkeep seulement)
├── .env.example      modèle de configuration sans secret
└── README.md
```

## Développement local

Le chemin recommandé reste Docker Compose. Pour travailler sans Docker, les scripts `start-local.ps1` et `stop-local.ps1` utilisent Python et Vite ; ils requièrent des dépendances locales, `backend/.env` et une base adaptée. La configuration par défaut du backend est historique et utilise SQLite : renseignez explicitement `DATABASE_URL` pour votre environnement. Les scripts ne gèrent pas la base PostgreSQL Docker.

Pour les vérifications locales :

```powershell
Set-Location backend
.\venv\Scripts\python.exe -m pytest tests -q
Set-Location ..\frontend
npm.cmd run build
```

Les tests backend utilisent leur propre base SQLite temporaire ; ils ne valident pas la connexion à la base PostgreSQL en production.
