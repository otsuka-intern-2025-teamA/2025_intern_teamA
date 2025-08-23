# Система логирования Company Research Agent

## Обзор

Система логирования автоматически сохраняет все сообщения в файл `logs/log.txt` с подробной информацией о времени выполнения, ошибках и производительности каждого этапа исследования.

## Структура логов

### Формат сообщений

```
2024-01-15 14:30:25 | INFO     | backend_server           | 🚀 Company Research Agent - Logging System Initialized
2024-01-15 14:30:25 | INFO     | backend_server           | 📅 Started at: 2024-01-15 14:30:25
2024-01-15 14:30:25 | INFO     | backend_server           | 📁 Log file: /path/to/logs/log.txt
2024-01-15 14:30:25 | INFO     | backend_server           | 🔧 Log level: INFO
```

### Уровни логирования

- **DEBUG** - Детальная отладочная информация
- **INFO** - Общая информация о процессе
- **WARNING** - Предупреждения
- **ERROR** - Ошибки
- **CRITICAL** - Критические ошибки

## Конфигурация

### Переменные окружения

```bash
# Уровень логирования (по умолчанию: INFO)
export LOG_LEVEL="DEBUG"

# Имя файла логов (по умолчанию: log.txt)
export LOG_FILE="company_research.log"
```

### Запуск с логированием

```bash
# Запуск с уровнем DEBUG
LOG_LEVEL=DEBUG ./start.sh

# Запуск с уровнем INFO (по умолчанию)
./start.sh
```

## Примеры логов

### Запуск системы

```
====================================================================================================
🚀 Company Research Agent - Logging System Initialized
📅 Started at: 2024-01-15 14:30:25
📁 Log file: /path/to/logs/log.txt
🔧 Log level: INFO
====================================================================================================
```

### Исследование компании

```
2024-01-15 14:30:26 | INFO     | backend_server           | 📝 Received research request for ソニーグループ
2024-01-15 14:30:26 | INFO     | backend_server           | 🚀 Starting research for ソニーグループ at 14:30:26
2024-01-15 14:30:26 | INFO     | backend.graph            | 🚀 Starting research workflow for ソニーグループ
2024-01-15 14:30:26 | INFO     | backend.graph            | ⏰ Workflow started at: 14:30:26
```

### Этапы обработки

```
2024-01-15 14:30:27 | INFO     | backend.nodes.grounding  | 🌐 Starting website analysis for https://sony.com
2024-01-15 14:30:27 | INFO     | backend.nodes.grounding  | 🚀 Initiating Tavily extraction
2024-01-15 14:30:29 | INFO     | backend.nodes.grounding  | ✅ Successfully extracted 5 content sections in 2.34s
2024-01-15 14:30:29 | INFO     | backend.nodes.grounding  | ✅ Grounding completed in 2.45s for ソニーグループ

2024-01-15 14:30:30 | INFO     | backend.nodes.researchers.base | 🔍 Generating queries for ソニーグループ as company_analyzer
2024-01-15 14:30:31 | INFO     | backend.nodes.researchers.base | ✅ Generated 4 queries for company_analyzer in 1.23s
2024-01-15 14:30:31 | INFO     | backend.nodes.researchers.base | 🔍 Starting search for 4 queries as company_analyzer
2024-01-15 14:30:34 | INFO     | backend.nodes.researchers.base | ✅ Search completed for company_analyzer in 3.45s with 18 documents
```

### Производительность

```
2024-01-15 14:30:35 | INFO     | backend.nodes.curator    | 🔍 Evaluating 18 documents
2024-01-15 14:30:35 | INFO     | backend.nodes.curator    | ✅ Document evaluation completed in 0.12s: 15 documents kept
2024-01-15 14:30:35 | INFO     | backend.nodes.curator    | 🎯 Curation completed in 0.15s: 15/18 documents kept
2024-01-15 14:30:35 | INFO     | backend.nodes.curator    | 📊 Document retention rate: 83.3%

2024-01-15 14:30:36 | INFO     | backend.nodes.enricher  | 🚀 Starting content enrichment for ソニーグループ
2024-01-15 14:30:38 | INFO     | backend.nodes.enricher  | ✅ company enrichment completed in 2.34s: 15 enriched, 0 errors
2024-01-15 14:30:38 | INFO     | backend.nodes.enricher  | ⏱️ Content enrichment completed in 2.45s for 15 URLs
```

### Завершение

```
2024-01-15 14:31:10 | INFO     | backend.graph            | ✅ Research workflow completed in 45.67s
2024-01-15 14:31:10 | INFO     | backend.graph            | ⏰ Workflow completed at: 14:31:10

2024-01-15 14:31:10 | INFO     | backend_server           | ✅ Research completed successfully for ソニーグループ
2024-01-15 14:31:10 | INFO     | backend_server           | ⏱️ Total execution time: 45.67 seconds
2024-01-15 14:31:10 | INFO     | backend_server           | 📊 Report length: 15678 characters
2024-01-15 14:31:10 | INFO     | backend_server           | 🕐 Completed at: 14:31:10
```

## Анализ логов

### Поиск по ключевым словам

```bash
# Найти все операции с определенной компанией
grep "ソニーグループ" logs/log.txt

# Найти все операции, которые заняли больше 10 секунд
grep "completed in [0-9]\{2,\}\.[0-9]\+s" logs/log.txt

# Найти все ошибки
grep "❌" logs/log.txt

# Найти все успешные завершения
grep "✅" logs/log.txt
```

### Статистика производительности

```bash
# Подсчитать общее время выполнения всех исследований
grep "Total execution time" logs/log.txt | awk '{sum+=$NF} END {print "Total time:", sum, "seconds"}'

# Найти самое быстрое исследование
grep "Total execution time" logs/log.txt | sort -k4 -n | head -1

# Найти самое медленное исследование
grep "Total execution time" logs/log.txt | sort -k4 -n | tail -1
```

## Ротация логов

### Автоматическая ротация

Система автоматически создает новые файлы логов при каждом запуске. Старые логи сохраняются с временными метками.

### Ручная ротация

```bash
# Архивировать текущий лог
mv logs/log.txt logs/log_$(date +%Y%m%d_%H%M%S).txt

# Очистить старые логи (старше 30 дней)
find logs/ -name "log_*.txt" -mtime +30 -delete
```

## Мониторинг в реальном времени

### Просмотр логов в реальном времени

```bash
# Следить за логами в реальном времени
tail -f logs/log.txt

# Следить за логами с фильтрацией по компании
tail -f logs/log.txt | grep "ソニーグループ"
```

### Алерты и уведомления

```bash
# Уведомление о завершении исследования
tail -f logs/log.txt | grep "Research completed successfully" | while read line; do
    echo "🔔 Research completed: $line" | notify-send "Company Research"
done
```

## Устранение неполадок

### Проблемы с логированием

1. **Логи не создаются**
   - Проверьте права доступа к директории `logs/`
   - Убедитесь, что переменная `LOG_LEVEL` установлена

2. **Логи слишком подробные**
   - Установите `LOG_LEVEL=INFO` или `LOG_LEVEL=WARNING`

3. **Логи не читаются**
   - Проверьте кодировку файла (должна быть UTF-8)
   - Убедитесь, что файл не поврежден

### Очистка логов

```bash
# Очистить все логи
rm -rf logs/*

# Очистить только старые логи
find logs/ -name "*.txt" -mtime +7 -delete
```

## Интеграция с внешними системами

### Отправка логов в внешние системы

```bash
# Отправка логов в Slack
grep "ERROR\|CRITICAL" logs/log.txt | curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Company Research Errors: $(cat)"}' \
  https://hooks.slack.com/services/YOUR_WEBHOOK_URL

# Отправка логов по email
grep "Research completed successfully" logs/log.txt | mail -s "Research Completed" user@example.com
```

Эта система логирования обеспечивает полную прозрачность процесса исследования компаний и позволяет эффективно отслеживать производительность и устранять неполадки.
