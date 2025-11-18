#!/bin/bash
# Helper script to prepare a new release
# Usage: ./prepare-release.sh <version>
# Example: ./prepare-release.sh 1.0.0

set -e

# Check if version argument is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <version>"
  echo "Example: $0 1.0.0"
  exit 1
fi

VERSION="$1"
TAG="v$VERSION"
DATE=$(date +%Y-%m-%d)

# Validate version format
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
  echo "Error: Version must be in format X.Y.Z or X.Y.Z-suffix"
  echo "Examples: 1.0.0, 1.2.3-beta.1, 2.0.0-rc.1"
  exit 1
fi

echo "=================================================="
echo "Preparing release $TAG"
echo "=================================================="
echo ""

# Check if we're on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
  echo "Warning: You are on branch '$CURRENT_BRANCH', not 'main'"
  read -p "Continue anyway? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
  echo "Error: You have uncommitted changes. Please commit or stash them first."
  exit 1
fi

# Check if tag already exists
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Error: Tag $TAG already exists"
  exit 1
fi

echo "Step 1: Updating CHANGELOG.md..."

# Create a backup
cp CHANGELOG.md CHANGELOG.md.bak

# Check if version already exists in CHANGELOG
if grep -q "## \[$VERSION\]" CHANGELOG.md; then
  echo "Version $VERSION already exists in CHANGELOG.md"
  echo "Please manually verify the changelog is correct."
else
  # Insert new version section after [Unreleased]
  # This is a simple implementation - you may need to manually edit for complex changelogs
  awk -v version="$VERSION" -v date="$DATE" '
    /^## \[Unreleased\]/ {
      print;
      print "";
      print "## [" version "] - " date;
      next;
    }
    { print }
  ' CHANGELOG.md.bak > CHANGELOG.md
  
  echo "Added version section to CHANGELOG.md"
  echo "Please review and edit CHANGELOG.md to move items from [Unreleased] to [$VERSION]"
  echo ""
  read -p "Press Enter when you're done editing CHANGELOG.md..."
fi

# Update comparison links at bottom of CHANGELOG
if grep -q "\[Unreleased\]:" CHANGELOG.md; then
  # Get the repository URL from git remote
  REPO_URL=$(git remote get-url origin | sed 's/\.git$//' | sed 's|git@github.com:|https://github.com/|')
  
  # Update [Unreleased] link and add new version link
  sed -i.bak2 "s|\[Unreleased\]:.*|[Unreleased]: $REPO_URL/compare/$TAG...HEAD\n[$VERSION]: $REPO_URL/compare/v0.0.0...$TAG|" CHANGELOG.md
  
  echo "Updated comparison links in CHANGELOG.md"
fi

rm -f CHANGELOG.md.bak CHANGELOG.md.bak2

echo ""
echo "Step 2: Running tests..."
python -m pytest tests/ -v

echo ""
echo "Step 3: Committing CHANGELOG.md..."
git add CHANGELOG.md
git commit -m "Prepare release $VERSION

Update CHANGELOG.md for version $VERSION

Co-authored-by: nicolas-reyrolle <n.reyrolle@gmail.com>"

echo ""
echo "Step 4: Creating and pushing tag..."
git tag -a "$TAG" -m "Release version $VERSION"

echo ""
echo "=================================================="
echo "Release preparation complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Review the changes: git show HEAD"
echo "2. Push the commit: git push origin $CURRENT_BRANCH"
echo "3. Push the tag: git push origin $TAG"
echo ""
echo "Once the tag is pushed, GitHub Actions will automatically:"
echo "- Run tests and validation"
echo "- Create a GitHub Release"
echo "- Build and upload distribution packages"
echo ""
echo "To push now, run:"
echo "  git push origin $CURRENT_BRANCH && git push origin $TAG"
