# GitHub Actions Workflows

This directory contains GitHub Actions workflows for the AudioFetch application.

## Available Workflows

### 1. deploy.yml (Current - Security Issues)
The original deployment workflow that has security concerns:
- ⚠️ Creates .env files with embedded secrets
- ⚠️ Generates docker-compose.yml dynamically with secrets
- ⚠️ Not recommended for public repositories

### 2. deploy-secure.yml (Recommended)
A security-hardened version of the deployment workflow:
- ✅ Expects pre-configured environment on the VPS
- ✅ No secrets written to files
- ✅ Includes security scanning with Trivy
- ✅ Proper error handling and logging
- ✅ Environment protection for production deployments

## Setup Instructions

### Prerequisites
1. A VPS with Docker and Docker Compose installed
2. SSH access to the VPS
3. GitHub repository with Container Registry enabled

### Step 1: Configure Your VPS
Run the setup script on your VPS to create a secure environment:

```bash
# Download the setup script
wget https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/scripts/setup-vps-secure.sh

# Make it executable
chmod +x setup-vps-secure.sh

# Run the setup
./setup-vps-secure.sh
```

This will:
- Create a secure .env file with proper permissions
- Generate random secrets for JWT tokens
- Create docker-compose.yml template
- Set up backup and update scripts

### Step 2: Configure GitHub Secrets
In your GitHub repository, go to Settings → Secrets and variables → Actions, and add:

| Secret Name | Description | Example |
|------------|-------------|---------|
| `VPS_HOST` | Your VPS IP or hostname | `203.0.113.0` or `myserver.com` |
| `VPS_USERNAME` | SSH username | `deploy` |
| `VPS_SSH_KEY` | Private SSH key (full content) | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `VPS_PORT` | SSH port | `22` |
| `VPS_APP_DIR` | Application directory on VPS | `/home/deploy/audiofetch` |

### Step 3: Update docker-compose.yml on VPS
After running the setup script, edit the docker-compose.yml on your VPS:

```bash
# On your VPS
cd /path/to/your/app
nano docker-compose.yml
```

Replace `GITHUB_USERNAME/GITHUB_REPO` with your actual GitHub username and repository name.

### Step 4: Enable the Secure Workflow
1. Delete or rename the insecure `deploy.yml`
2. Rename `deploy-secure.yml` to `deploy.yml`
3. Commit and push to trigger deployment

## Security Best Practices

1. **Never commit .env files** - Use .gitignore
2. **Rotate secrets regularly** - Update GitHub Secrets and VPS configuration
3. **Monitor deployments** - Check deployment.log on your VPS
4. **Use environment protection** - Configure approval requirements for production
5. **Review workflow runs** - Audit GitHub Actions logs regularly

## Troubleshooting

### Deployment Fails with ".env not found"
The secure workflow expects the VPS to be pre-configured. Run the setup script first.

### SSH Connection Fails
- Verify SSH key format (should be OpenSSH format)
- Check if the VPS allows SSH key authentication
- Ensure the SSH port is correct

### Docker Login Fails
- The GITHUB_TOKEN is automatically provided
- Ensure the repository has packages write permission

### Container Won't Start
- Check docker compose logs on the VPS
- Verify .env file has all required variables
- Ensure ports are not already in use

## Manual Deployment
If you need to deploy manually:

```bash
# On your VPS
cd /path/to/your/app
./update-app.sh
```

## Monitoring
Check deployment status:

```bash
# View deployment log
tail -f deployment.log

# Check container status
docker compose ps

# View container logs
docker compose logs -f
```

## Security Incident Response
If you suspect a security breach:

1. Immediately rotate all secrets in GitHub
2. Regenerate .env file on VPS with new secrets
3. Review deployment.log for unauthorized access
4. Check Docker logs for suspicious activity
5. Consider rebuilding the VPS from scratch

## Additional Resources
- [GitHub Actions Security Hardening](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [Docker Security Best Practices](https://docs.docker.com/develop/security-best-practices/)
- [OWASP Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)