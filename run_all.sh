#!/bin/sh

# Функция для чтения YAML
read_yaml() {
    python3 -c "
import yaml, sys
with open('$1') as f:
    print(yaml.safe_load(f)$2)
" 2>/dev/null
}

echo "1. Загрузка конфигурации ------------------------------------------------------------"
# Чтение конфига
CONFIG_FILE="config.yaml"

# Базовые параметры
MODEL_NAME=$(read_yaml "$CONFIG_FILE" "['model']['name']")

echo "2. Прогон SWE-bench ------------------------------------------------------------"
hal-eval --benchmark swebench_verified \
  --agent_dir agents/SWE-agent-v1.0/ \
  --agent_function main.run \
  --agent_name "SWEBench Agent ($MODEL_NAME)" \
  -A agent.model.name=gigachat/$MODEL_NAME \
  -A agent.model.per_instance_cost_limit=0.0 \
  --max_concurrent 1

echo "3. Агрегация результатов ------------------------------------------------------------"
