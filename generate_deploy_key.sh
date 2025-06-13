#!/bin/bash

# Generate SSH key pair for GitHub Actions deployment
echo "Generating SSH key pair for GitHub Actions..."

# Generate the key pair
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ./github_actions_deploy -N ""

echo ""
echo "=== SSH Key Generation Complete ==="
echo ""
echo "1. Copy this PUBLIC key to your VPS's authorized_keys:"
echo ""
cat ./github_actions_deploy.pub
echo ""
echo "2. Copy this PRIVATE key to GitHub Secrets as VPS_SSH_KEY:"
echo ""
cat ./github_actions_deploy
echo ""
echo "3. After copying, delete these local key files for security:"
echo "   rm ./github_actions_deploy ./github_actions_deploy.pub"