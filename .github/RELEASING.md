# Release Process

This document describes how to create a new release of the Apple Health Segments project.

## Prerequisites

- Write access to the repository
- Local clone of the repository
- All tests passing locally
- Changes documented in CHANGELOG.md

## Versioning

This project uses [Semantic Versioning](https://semver.org/):

- **MAJOR** version (x.0.0): Incompatible API changes or breaking CLI changes
- **MINOR** version (0.x.0): New features in a backwards-compatible manner  
- **PATCH** version (0.0.x): Backwards-compatible bug fixes

### Pre-release Versions

- **Alpha**: `vX.Y.Z-alpha.N` - Early testing, features incomplete
- **Beta**: `vX.Y.Z-beta.N` - Feature complete, bug fixing phase
- **Release Candidate**: `vX.Y.Z-rc.N` - Final testing before release

## Automated Release (Recommended)

### Using the Helper Script

1. Ensure you're on the `main` branch and up-to-date:
   ```bash
   git checkout main
   git pull origin main
   ```

2. Run the release preparation script:
   ```bash
   .github/scripts/prepare-release.sh 1.0.0
   ```

3. The script will:
   - Validate the version format
   - Update CHANGELOG.md with the new version
   - Run tests to ensure everything passes
   - Create a commit with the changelog updates
   - Create a git tag
   - Provide instructions for pushing

4. Review the changes:
   ```bash
   git show HEAD
   ```

5. Push the commit and tag:
   ```bash
   git push origin main
   git push origin v1.0.0
   ```

6. GitHub Actions will automatically:
   - Run all tests and quality checks
   - Extract changelog notes for the version
   - Create a GitHub Release
   - Build distribution packages (.tar.gz and .whl)
   - Upload artifacts to the release

## Manual Release

If you prefer to do the release manually:

### Step 1: Update CHANGELOG.md

1. Open `CHANGELOG.md`
2. Create a new version section:
   ```markdown
   ## [1.0.0] - 2025-11-18
   ```
3. Move relevant items from `[Unreleased]` to the new version section
4. Update the comparison links at the bottom:
   ```markdown
   [Unreleased]: https://github.com/NicolasReyrolle/applehealth/compare/v1.0.0...HEAD
   [1.0.0]: https://github.com/NicolasReyrolle/applehealth/compare/v0.0.0...v1.0.0
   ```

### Step 2: Commit the Changes

```bash
git add CHANGELOG.md
git commit -m "Prepare release 1.0.0

Update CHANGELOG.md for version 1.0.0

Co-authored-by: nicolas-reyrolle <n.reyrolle@gmail.com>"
```

### Step 3: Create and Push Tag

```bash
# Create annotated tag
git tag -a v1.0.0 -m "Release version 1.0.0"

# Push commit and tag
git push origin main
git push origin v1.0.0
```

### Step 4: Monitor GitHub Actions

Visit the [Actions tab](https://github.com/NicolasReyrolle/applehealth/actions) to monitor the release workflow.

## Release Workflow Details

The GitHub Actions workflow (`.github/workflows/release.yml`) performs:

### Validation Phase
- Checks out the code
- Sets up Python environment
- Installs dependencies
- Runs full test suite with coverage
- Validates tag format (vX.Y.Z)
- Verifies CHANGELOG.md contains the version

### Release Phase
- Extracts version from tag
- Parses changelog notes for the release
- Creates GitHub Release (draft for pre-releases)
- Generates automatic release notes from commits
- Builds distribution packages (setup.py)
- Uploads artifacts (.tar.gz, .whl) to release
- Creates release summary

## Post-Release Steps

After a release is published:

1. **Verify the Release**
   - Check the [Releases page](https://github.com/NicolasReyrolle/applehealth/releases)
   - Download and test the distribution packages
   - Verify changelog notes are correct

2. **Update Documentation** (if needed)
   - Update README.md with new version references
   - Update installation instructions if installation method changed

3. **Communicate**
   - Announce on relevant channels
   - Update any external documentation
   - Close related issues/PRs

4. **Start New Development Cycle**
   - Create new `[Unreleased]` section in CHANGELOG.md (if not present)
   - Plan next version features

## Troubleshooting

### Release Workflow Failed

**Tests Failed:**
- Fix the failing tests
- Delete the tag: `git tag -d v1.0.0 && git push origin :v1.0.0`
- Fix issues and create tag again

**CHANGELOG Validation Failed:**
- Ensure CHANGELOG.md contains `## [X.Y.Z]` section
- Update CHANGELOG.md
- Force push the tag: `git tag -f v1.0.0 && git push -f origin v1.0.0`

**Build Failed:**
- Check the build logs in GitHub Actions
- Verify setup.py is valid
- Ensure all dependencies are correctly specified

### Tag Already Exists

If you need to recreate a tag:

```bash
# Delete local tag
git tag -d v1.0.0

# Delete remote tag
git push origin :v1.0.0

# Delete the release on GitHub (if created)
# Via web UI: Releases → Select release → Delete release

# Create new tag
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

### Wrong Version Number

If you tagged with the wrong version:

1. Delete the tag (see above)
2. Update CHANGELOG.md with correct version
3. Commit the fix
4. Create new tag with correct version

## Installation from Release

Users can install directly from a release:

```bash
# Install latest release
pip install https://github.com/NicolasReyrolle/applehealth/releases/latest/download/apple-health-segments-<version>-py3-none-any.whl

# Install specific version
pip install https://github.com/NicolasReyrolle/applehealth/releases/download/v1.0.0/apple-health-segments-1.0.0-py3-none-any.whl
```

## Release Checklist

Use this checklist when creating a release:

- [ ] All tests passing locally and in CI
- [ ] CHANGELOG.md updated with version and date
- [ ] Version follows semantic versioning rules
- [ ] Breaking changes clearly documented (if any)
- [ ] All relevant PRs and issues closed
- [ ] Documentation updated (if needed)
- [ ] On `main` branch and up-to-date
- [ ] No uncommitted changes
- [ ] Tag created with correct version
- [ ] Tag and commit pushed to GitHub
- [ ] Release workflow completed successfully
- [ ] Release artifacts available on GitHub
- [ ] Installation tested from release artifacts
- [ ] Release announced (if applicable)

## Version History

For the complete version history, see [CHANGELOG.md](../CHANGELOG.md).
