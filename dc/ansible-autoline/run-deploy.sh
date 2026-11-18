#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

for octet in 51 52 53 54 55 56 57 58 59 60 61; do
  variable="AUTO_${octet}_PASSWORD"
  read -r -s -p "Password for 192.168.6.${octet} (Enter to skip): " value
  printf '\n'
  if [[ -n "$value" ]]; then
    export "$variable=$value"
  fi
done

ansible-galaxy collection install -r requirements.yml
ansible-playbook --syntax-check deploy.yml

declare -A inventory_names=(
  [51]=auto_ict
  [52]=auto_fct
  [53]=auto_depanel
  [54]=auto_shell_binding
  [55]=auto_assembly_ate
  [56]=auto_supersonic
  [57]=auto_aging
  [58]=auto_high_voltage
  [59]=auto_packing_left
  [60]=auto_packing_right
  [61]=auto_outer_box
)
available_hosts=()
for octet in 51 52 53 54 55 56 57 58 59 60 61; do
  variable="AUTO_${octet}_PASSWORD"
  if [[ -n "${!variable:-}" ]]; then
    available_hosts+=("${inventory_names[$octet]}")
  fi
done

if [[ ${#available_hosts[@]} -eq 0 ]]; then
  echo "No station password was supplied; nothing will be deployed."
  exit 1
fi

limit_pattern="$(IFS=:; echo "${available_hosts[*]}")"
ansible-playbook deploy.yml --limit "$limit_pattern"
