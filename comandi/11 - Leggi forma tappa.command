#!/bin/zsh
cd "${0:A:h}/.." || exit 1
if [[ ! -x .venv/bin/python ]]; then
    echo "Manca .venv/bin/python nel progetto."
    read -r -p "Premi Invio per chiudere. "
    exit 1
fi
.venv/bin/python -m desnivel.cli.show_route_form "$@"
result=$?
read -r -p "Premi Invio per chiudere. "
exit "$result"
