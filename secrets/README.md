# Docker Secrets Directory

This directory contains secret files for Docker Compose secrets management.

## ⚠️ Security Warning

**NEVER commit actual secrets to version control!**

This directory should be added to `.gitignore` to prevent accidental commits.

## Setup Instructions

### Development Environment

Create the following files with your development secrets:

```bash
# JWT Secret Key (min 32 characters)
echo "your-dev-jwt-secret-key-min-32-chars" > secrets/jwt_secret_key.txt

# ChirpStack API Token
echo "your-chirpstack-api-token" > secrets/chirpstack_api_token.txt

# Database Password (if overriding default)
echo "your-postgres-password" > secrets/postgres_password.txt
```

### Production Environment

1. **Generate Strong Secrets:**
   ```bash
   # Generate random 64-character secret
   openssl rand -hex 32 > secrets/jwt_secret_key.txt

   # Or use this Python one-liner
   python3 -c "import secrets; print(secrets.token_urlsafe(48))" > secrets/jwt_secret_key.txt
   ```

2. **Set Proper Permissions:**
   ```bash
   chmod 600 secrets/*.txt
   sudo chown root:root secrets/*.txt  # If using in production
   ```

3. **Docker Swarm (Recommended for Production):**
   ```bash
   # Create secrets in Docker Swarm
   docker secret create jwt_secret_key secrets/jwt_secret_key.txt
   docker secret create chirpstack_api_token secrets/chirpstack_api_token.txt

   # Then remove local files
   rm secrets/*.txt
   ```

## File Structure

```
secrets/
├── README.md                    # This file (safe to commit)
├── .gitkeep                     # Keeps directory in git (safe to commit)
├── jwt_secret_key.txt          # JWT signing key (DO NOT COMMIT)
├── chirpstack_api_token.txt    # ChirpStack API token (DO NOT COMMIT)
└── postgres_password.txt       # Database password (DO NOT COMMIT)
```

## Fallback Behavior

If secret files are not present, the application will fall back to:
1. Environment variables (`SECRET_KEY`, `CHIRPSTACK_API_TOKEN`, etc.)
2. Default values (development only)

## Verification

Check if secrets are loaded correctly:

```bash
docker compose exec api python -c "from src.config import get_settings; s = get_settings(); print('JWT secret length:', len(s.get_effective_jwt_secret()))"
```

Expected output: `JWT secret length: 32` (or more)

## Troubleshooting

### Secret Not Found Error

If you get "Secret 'xxx' not found" error:

1. Check file exists: `ls -la secrets/`
2. Check file permissions: `ls -l secrets/*.txt`
3. Check Docker Compose mounts: `docker compose config | grep secrets`
4. Check container can access: `docker compose exec api ls -la /run/secrets/`

### Permission Denied

```bash
chmod 644 secrets/*.txt  # Read for all (dev environment)
# OR
chmod 600 secrets/*.txt  # Read only for owner (production)
```

## Best Practices

1. **Never commit secrets** - Add `secrets/*.txt` to `.gitignore`
2. **Use strong secrets** - Minimum 32 characters, random generation
3. **Rotate regularly** - Change secrets every 90 days
4. **Separate by environment** - Different secrets for dev/staging/prod
5. **Backup securely** - Store production secrets in password manager
6. **Audit access** - Track who has access to production secrets

## References

- [Docker Secrets Documentation](https://docs.docker.com/engine/swarm/secrets/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [OWASP Secret Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
