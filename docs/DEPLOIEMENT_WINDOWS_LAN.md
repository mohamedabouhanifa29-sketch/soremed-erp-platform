# Déploiement sur un serveur Windows local

## Préparation du serveur

Attribuez une adresse IPv4 fixe au serveur, par exemple `192.168.1.10`. Installez Docker Desktop, copiez le projet sur un disque sauvegardé et configurez `docker/.env`. Autorisez dans le Pare-feu Windows le port TCP choisi par `HTTP_PORT` uniquement pour le profil réseau Privé et, idéalement, uniquement pour le sous-réseau de l'entreprise.

Ne publiez pas les ports PostgreSQL ou FastAPI : seul Nginx écoute le LAN. Les postes clients utilisent ensuite `http://192.168.1.10`. Un nom DNS interne tel que `http://soremed.local` peut être créé par l'administrateur réseau.

## Exploitation

- Démarrage : `./docker/start.ps1`.
- État : `docker compose --env-file docker/.env -f docker/docker-compose.yml ps`.
- Journaux : `docker compose --env-file docker/.env -f docker/docker-compose.yml logs --tail 200`.
- Sauvegarde : `./database/backup.ps1`.
- Restauration : `./database/restore.ps1 -BackupFile ./database/backups/fichier.sql` après arrêt des utilisateurs et sauvegarde préalable.

Planifiez `backup.ps1` chaque nuit avec le Planificateur de tâches Windows et copiez les sauvegardes vers un second support interne protégé. Testez périodiquement la restauration sur une instance séparée.

## Mise en production

Remplacez tous les secrets d'exemple, changez le mot de passe administrateur, limitez l'accès physique au serveur, activez les sauvegardes et synchronisez l'heure Windows. Pour une meilleure confidentialité même sur LAN, placez un certificat délivré par l'autorité interne de l'entreprise devant Nginx et forcez HTTPS.
