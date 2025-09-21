# Release 1.0 Preparation Checklist

## Files to Keep for 1.0

### Core Project Files
- ✅ `pyproject.toml` - Project configuration and dependencies
- ✅ `README.md` - Project documentation (updated for 1.0)
- ✅ `LICENSE` - Legal requirements
- ✅ `.claude/` - AI assistance notes (kept locally; not required for users)
- ✅ `Makefile` - Development automation
- ✅ `.gitignore` - Version control configuration

### Configuration Files
- ✅ `.env.example` - Environment variable template
- ✅ `docker-compose.yml` - Container orchestration
- ✅ `.markdownlint.json` - Markdown linting rules

### Source Directories
- ✅ `great_work/` - Main application code
- ✅ `tests/` - Test suite
- ✅ `docs/` - Documentation

### GitHub Integration
- ✅ `.github/` - GitHub Actions and workflows

## Files to Remove Before 1.0

### Development Artifacts
- ✅ `.coverage` - Not tracked; ignored in .gitignore
- ✅ `.mypy_cache/` - Not tracked; ignored
- ✅ `.pytest_cache/` - Not tracked; ignored
- ✅ `.ruff_cache/` - Not tracked; ignored
- ✅ `htmlcov/` - Not tracked; ignored
- ✅ `the_great_work.egg-info/` - Not tracked; ignored

### Local Data Files
- ✅ `var/state/great_work.db` - Not tracked; ignored
- ✅ `var/telemetry/telemetry.db` - Not tracked; ignored
- ✅ `.env` - Not tracked; ignored

### Development Notes
- ✅ `docs/archive/PRODUCTION_BUGS_FOUND.md` - Addressed via archive (kept until GA)
- ✅ `docs/archive/TEST_CLEANUP_SUMMARY.md` - Addressed via archive (kept until GA)
- ✅ `AGENTS.md` - Removed from repository; ignored locally

### IDE Configuration
- ✅ `.vscode/` - Not tracked; ignored

### Virtual Environment
- ✅ `.venv/` - Keep gitignored, each user creates their own

## Files to Update for 1.0

### Documentation Updates Needed
1. **README.md** (complete)
   - Install, config, quick start, features, contributing present

2. **CHANGELOG.md** (complete)
   - RC1 highlights added; promote to [1.0.0] at GA

3. **docs/** (complete for RC)
   - Deployment guide (DEPLOYMENT.md) and Telemetry Runbook aligned
   - User Guide includes install/start/play; examples under `docs/examples/`

## Actions to Take

### Immediate Actions
- Ensure caches and local artifacts are untracked (they’re ignored by `.gitignore`).
- Internal docs already archived under `docs/archive/`.
- Databases are ignored (`*.db`); keep local `.env` out of git.

### Pre-Release Actions
1. Run full test suite and ensure 100% pass rate (284+)
2. Generate fresh documentation
3. Update version in pyproject.toml to 1.0.0 at GA cut
4. Create comprehensive CHANGELOG.md
5. Update README with production deployment instructions
6. Tag release with v1.0.0

## Recommended .gitignore Additions

```gitignore
# Databases
*.db
*.sqlite
*.sqlite3

# Coverage and testing
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Build artifacts
*.egg-info/
dist/
build/

# IDE settings
.vscode/
.idea/

# Environment
.env
.env.local
```

## Release Validation

Before releasing 1.0:
- [ ] All tests passing (current: 284)
- [ ] Documentation complete and reviewed (README, DEPLOYMENT, USER_GUIDE, RUNBOOK)
- [ ] Security audit completed
- [ ] Performance benchmarks documented
- [ ] Docker image builds successfully (confirmed for bot)
- [ ] Clean install tested on fresh system
- [ ] Database migrations documented (N/A for SQLite in 1.0; note path to Postgres if needed)
- [ ] API/backwards compatibility verified (Discord command surface stable)
- [ ] License headers verified
- [ ] Dependencies audited for security vulnerabilities

## Version Tagging

```bash
# When ready for release
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```
