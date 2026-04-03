#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   HF_TOKEN=hf_xxx ./push_to_hf.sh
# Optional override:
#   HF_TOKEN=hf_xxx ./push_to_hf.sh yashodipmore/queryforge-v1

SPACE_REPO="${1:-yashodipmore/queryforge-v1}"
HF_USERNAME="${SPACE_REPO%%/*}"

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "HF_TOKEN is not set."
  echo "Run: HF_TOKEN=hf_xxx ./push_to_hf.sh"
  exit 1
fi

if [[ ! -d .git ]]; then
  echo "Run this script from the git repository root."
  exit 1
fi

ASKPASS_SCRIPT="$(mktemp)"
cat > "$ASKPASS_SCRIPT" <<'EOF'
#!/usr/bin/env sh
case "$1" in
  *Username*) printf '%s\n' "$HF_USERNAME" ;;
  *Password*) printf '%s\n' "$HF_TOKEN" ;;
  *) printf '\n' ;;
esac
EOF
chmod 700 "$ASKPASS_SCRIPT"
trap 'rm -f "$ASKPASS_SCRIPT"' EXIT

export GIT_ASKPASS="$ASKPASS_SCRIPT"
export GIT_TERMINAL_PROMPT=0
export HF_USERNAME
export HF_TOKEN

git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "https://huggingface.co/spaces/$SPACE_REPO"

git push -u origin main

echo "Push complete: https://huggingface.co/spaces/$SPACE_REPO"
