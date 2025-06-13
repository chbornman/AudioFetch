# SSH Setup for GitHub Actions Deployment

## Required GitHub Secrets

You need to configure the following secrets in your GitHub repository:

1. **VPS_HOST**: Your VPS IP address or hostname
2. **VPS_USERNAME**: SSH username (e.g., root, ubuntu, etc.)
3. **VPS_SSH_KEY**: Your private SSH key (see instructions below)
4. **VPS_PORT**: SSH port (optional, defaults to 22)
5. **VPS_APP_DIR**: Application directory on your VPS
6. **APP_PORT**: Application port
7. **LOG_LEVEL**: Log level for the application
8. **DOWNLOADS_HOST_PATH**: Host path for downloads directory

## Setting up SSH Key

1. Generate an SSH key pair (if you don't have one):
```bash
ssh-keygen -t ed25519 -C "github-actions@your-repo" -f ~/.ssh/github_actions_deploy
```

2. Add the public key to your VPS:
```bash
ssh-copy-id -i ~/.ssh/github_actions_deploy.pub username@your-vps-host
```

Or manually add it to `~/.ssh/authorized_keys` on your VPS.

3. Copy the private key content:
```bash
cat ~/.ssh/github_actions_deploy
```

4. Add it as the `VPS_SSH_KEY` secret in GitHub:
   - Go to your repository Settings
   - Navigate to Secrets and variables > Actions
   - Click "New repository secret"
   - Name: `VPS_SSH_KEY`
   - Value: Paste the entire private key including the headers

## Troubleshooting SSH Authentication

If you're getting "ssh: handshake failed" errors:

1. **Verify the private key format**: Make sure you're copying the entire private key including:
   ```
   -----BEGIN OPENSSH PRIVATE KEY-----
   [key content]
   -----END OPENSSH PRIVATE KEY-----
   ```

2. **Check SSH key permissions on VPS**:
   ```bash
   chmod 700 ~/.ssh
   chmod 600 ~/.ssh/authorized_keys
   ```

3. **Test SSH connection locally**:
   ```bash
   ssh -i ~/.ssh/github_actions_deploy -p [port] username@host
   ```

4. **Check VPS SSH configuration** (`/etc/ssh/sshd_config`):
   - Ensure `PubkeyAuthentication yes`
   - Ensure `PasswordAuthentication no` (for security)
   - Check if there are any IP restrictions

5. **Debug the GitHub Action**: The workflow now includes debug mode which will show more details about the SSH connection attempt.