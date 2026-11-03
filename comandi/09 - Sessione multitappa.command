#!/bin/bash
cd -- "$(dirname -- "$0")/.." || exit 1
if [[ ! -x .venv/bin/python ]]; then
    echo "Manca .venv/bin/python nel progetto."
    read -r -p "Premi Invio per chiudere. "
    exit 1
fi
./.venv/bin/python -m desnivel.cli.launch_stage "$@"
result=$?
read -r -p "Premi Invio per chiudere. "
exit "$result"
