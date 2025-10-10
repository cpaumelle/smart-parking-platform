# Claude Code - Development Guide

**Project**: Smart Parking Platform
**Repository**: https://github.com/cpaumelle/smart-parking-platform
**Location**: `/opt/smart-parking`

---

## Git & GitHub Configuration

### GitHub CLI (gh)

The server has GitHub CLI installed for interacting with GitHub repositories.

**Version**:
```bash
gh version 2.74.0-19-gea8fc856e (2025-06-09)
```

**Installation Location**:
```bash
/snap/bin/gh
```

### Git Configuration

**Repository**:
- **Remote**: `origin` → `https://github.com/cpaumelle/smart-parking-platform.git`
- **Branch**: `main`
- **Working Directory**: `/opt/smart-parking`

**File Ownership**:
- All files are owned by `root:root`
- Git operations require `sudo` prefix

### Committing Changes

When creating commits, follow this workflow:

```bash
# 1. Check status
sudo git status

# 2. Review changes
sudo git diff

# 3. Stage files
sudo git add <file1> <file2>

# 4. Commit with message
sudo git commit -m "$(cat <<'EOF'
<type>(<scope>): <subject>

<body>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# 5. Push to GitHub
sudo git push origin main
```

**Commit Message Format**:
```
<type>(<scope>): <subject>

<body>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Commit Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Maintenance tasks
- `perf`: Performance improvements

**Examples**:
```bash
# Documentation update
sudo git commit -m "docs: update API documentation for reservation endpoints"

# Feature addition
sudo git commit -m "feat(parking-display): add reservation grace period handling"

# Bug fix
sudo git commit -m "fix(ingest): correct payload decoder for TABS sensor"
```

### Pushing to GitHub

**Standard Push**:
```bash
sudo git push origin main
```

**Force Push** (use with caution):
```bash
sudo git push --force origin main
```

**Push with Tags**:
```bash
sudo git push --tags
```

### Using GitHub CLI (gh)

The GitHub CLI provides additional functionality beyond standard git commands:

**View Repository Information**:
```bash
cd /opt/smart-parking
gh repo view
```

**List Pull Requests**:
```bash
gh pr list
```

**View Issues**:
```bash
gh issue list
```

**Create Pull Request** (if working on a branch):
```bash
gh pr create --title "Feature: Add reservation API" --body "Description of changes"
```

**View Workflow Runs** (if GitHub Actions configured):
```bash
gh run list
```

---

## File Permissions

All project files are owned by root, requiring sudo for modifications:

**Check Permissions**:
```bash
ls -la /opt/smart-parking/
```

**Edit Files**:
- Use `sudo` with edit commands
- Files will be owned by `root:root` after editing

**Example**:
```bash
sudo nano /opt/smart-parking/README.md
```

---

## Development Workflow

### 1. Check Repository Status
```bash
cd /opt/smart-parking
sudo git status
sudo git diff
```

### 2. Make Changes
- Edit files as needed
- Test changes locally
- Verify services with `sudo docker compose ps`

### 3. Stage Changes
```bash
# Stage specific files
sudo git add ARCHITECTURE.md README.md

# Stage all changes
sudo git add .
```

### 4. Commit Changes
```bash
sudo git commit -m "$(cat <<'EOF'
docs: update reservation API documentation

- Updated ARCHITECTURE.md Phase 3 status
- Added API documentation section
- Updated changelog

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### 5. Push to GitHub
```bash
sudo git push origin main
```

### 6. Verify on GitHub
Visit: https://github.com/cpaumelle/smart-parking-platform

---

## Branch Management

### List Branches
```bash
sudo git branch -a
```

### Create New Branch
```bash
sudo git checkout -b feature/new-feature
```

### Switch Branches
```bash
sudo git checkout main
```

### Delete Branch
```bash
sudo git branch -d feature/old-feature
```

---

## Viewing History

### Recent Commits
```bash
sudo git log --oneline -10
```

### Detailed Log
```bash
sudo git log --stat
```

### View Specific File History
```bash
sudo git log --follow -- README.md
```

### View Changes in Last Commit
```bash
sudo git show HEAD
```

---

## Undoing Changes

### Discard Unstaged Changes
```bash
sudo git restore <file>
```

### Unstage Files
```bash
sudo git restore --staged <file>
```

### Revert Last Commit (keep changes)
```bash
sudo git reset --soft HEAD~1
```

### Revert Last Commit (discard changes)
```bash
sudo git reset --hard HEAD~1
```

---

## Best Practices

1. **Always check status before committing**:
   ```bash
   sudo git status
   sudo git diff
   ```

2. **Stage related changes together**:
   ```bash
   sudo git add ARCHITECTURE.md README.md
   ```

3. **Write descriptive commit messages**:
   - Clear subject line
   - Detailed body explaining why (not what)
   - Reference issue numbers if applicable

4. **Use sudo for all git operations**:
   - Files are owned by root
   - Git operations require elevated privileges

5. **Test before pushing**:
   - Verify services are running
   - Check documentation renders correctly
   - Test API endpoints if code changed

6. **Include Claude Code attribution**:
   - Always add the Claude Code footer to commits
   - Maintains transparency about AI assistance

---

## Troubleshooting

### "dubious ownership" Error
```bash
sudo git config --global --add safe.directory /opt/smart-parking
```

### Authentication Issues
The repository uses HTTPS with token authentication embedded in the remote URL.

### Permission Denied
All git operations require `sudo` prefix due to root ownership.

### Push Rejected
```bash
# Pull latest changes first
sudo git pull origin main --rebase

# Resolve conflicts if any
sudo git status
sudo git add <resolved-files>
sudo git rebase --continue

# Push again
sudo git push origin main
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Check status | `sudo git status` |
| View changes | `sudo git diff` |
| Stage files | `sudo git add <files>` |
| Commit | `sudo git commit -m "message"` |
| Push | `sudo git push origin main` |
| Pull | `sudo git pull origin main` |
| View log | `sudo git log --oneline` |
| View remote | `sudo git remote -v` |
| Create branch | `sudo git checkout -b <branch>` |
| Switch branch | `sudo git checkout <branch>` |

---

**Last Updated**: 2025-10-10
**Maintainer**: Claude Code
**Repository**: https://github.com/cpaumelle/smart-parking-platform
