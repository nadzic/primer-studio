#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="${ROOT_DIR}/app/frontend"
STRICT_NPM_CI=0

log_step() {
  printf "\n\033[1;34m==> %s\033[0m\n" "$1"
}

print_usage() {
  cat <<EOF
Usage: ./run_ci_checks.sh [--ci-strict]

Options:
  --ci-strict   Require strict frontend install via 'npm ci' (CI-like behavior).
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --ci-strict)
        STRICT_NPM_CI=1
        shift
        ;;
      -h|--help)
        print_usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1"
        print_usage
        exit 1
        ;;
    esac
  done
}

install_frontend_dependencies() {
  if [[ ${STRICT_NPM_CI} -eq 1 ]]; then
    (cd "${FRONTEND_DIR}" && npm ci)
    return
  fi

  if (cd "${FRONTEND_DIR}" && npm ci); then
    return
  fi

  echo "Warning: npm ci failed because lockfile is out of sync."
  echo "Falling back to npm install for local checks."
  (cd "${FRONTEND_DIR}" && npm install --package-lock=false --no-audit --no-fund)
}

run_frontend_checks() {
  if [[ ! -d "${FRONTEND_DIR}" ]]; then
    echo "Frontend directory not found: ${FRONTEND_DIR}"
    exit 1
  fi

  log_step "Frontend: install dependencies"
  install_frontend_dependencies

  log_step "Frontend: lint"
  (cd "${FRONTEND_DIR}" && npm run lint)

  log_step "Frontend: typecheck"
  (cd "${FRONTEND_DIR}" && npm run typecheck)

  log_step "Frontend: next build"
  (
    cd "${FRONTEND_DIR}" && \
    NEXT_PUBLIC_API_URL="http://localhost:8000/api/v1" \
    NEXT_PUBLIC_SITE_URL="http://localhost:3000" \
    npm run build
  )

  log_step "Frontend: format check"
  (cd "${FRONTEND_DIR}" && npm run format:check)

  log_step "Frontend: tests"
  (cd "${FRONTEND_DIR}" && npm run test)
}

run_python_checks() {
  log_step "Python: sync dev dependencies"
  (cd "${ROOT_DIR}" && uv sync --extra dev)

  log_step "Python: Ruff lint"
  (cd "${ROOT_DIR}" && uv run ruff check .)

  log_step "Python: BasedPyright type check"
  (cd "${ROOT_DIR}" && uv run basedpyright --level error .)

  if [[ -d "${ROOT_DIR}/tests" ]]; then
    log_step "Python: pytest"
    (cd "${ROOT_DIR}" && uv run pytest -q)
  else
    log_step "Python: pytest skipped (no tests directory)"
  fi

  log_step "Python: compile smoke check"
  (cd "${ROOT_DIR}" && uv run python -m compileall app)
}

main() {
  parse_args "$@"
  run_frontend_checks
  run_python_checks
  log_step "All CI quality checks passed"
}

main "$@"
