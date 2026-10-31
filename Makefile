.PHONY: help config run up down ps build secret migrate-job deploy logs upgrade downgrade migrate \
        format lint lint-fix typecheck check test test-integration test-all

SRC := src tests
BUILD := BUILDX_NO_DEFAULT_ATTESTATIONS=1
CLUSTER := aiip
CONTEXT := k3d-$(CLUSTER)
KUBECTL := kubectl --context $(CONTEXT) -n apps
IMAGE := aiip-projects:$(shell date +%Y%m%d%H%M%S)
ON_HOST := DATABASE__POSTGRES_HOST=localhost CACHE__HOST=localhost \
           AUTH__JWKS_URL=http://localhost:8001/.well-known/jwks.json \
           USERS__URL=http://localhost:8004 \
           RABBITMQ__URL=$$(sed -n 's|^url = "\(amqp://[^@]*@\)[^:/]*\(.*\)"|\1localhost\2|p' config.toml) \
           TRACING__OTLP_ENDPOINT=http://localhost:4318
NEED_FORWARD = @nc -z localhost 5432 2>/dev/null || { echo "инфра закрыта: запусти make -C ../infra forward в соседнем терминале"; exit 1; }

help:
	@echo ""
	@echo "  Первый запуск"
	@echo "    config                    config.toml из выдачи инфры (make -C ../infra service name=projects)"
	@echo "    upgrade                   применить миграции"
	@echo "    run                       запустить на хосте без Docker, сервис на localhost:8003;"
	@echo "                              ключи токенов берёт у auth на localhost:8001, профили —"
	@echo "                              у users на localhost:8004 (make run в обоих)"
	@echo "                              мимо Traefik; run, upgrade, downgrade, migrate ходят в инфру"
	@echo "                              через make -C ../infra forward"
	@echo ""
	@echo "  Kubernetes (кластер k3d aiip, namespace apps)"
	@echo "    up                        собрать образ, загрузить в кластер, обновить секрет, применить"
	@echo "                              миграции Job'ом и выкатить RollingUpdate без простоя; если"
	@echo "                              новые поды не стали готовы — откат. Число подов ведёт KEDA"
	@echo "                              по нагрузке, границы — в k8s/scaledobject.yaml"
	@echo "    down                      удалить Deployment, Service и маршрут, секрет остаётся"
	@echo "    ps                        поды, их нагрузка и решение автоскейлера"
	@echo "    logs                      логи всех подов"
	@echo "    build                     собрать образ и загрузить в кластер"
	@echo ""
	@echo "  Миграции"
	@echo "    upgrade                   применить все миграции"
	@echo "    downgrade REV=<rev>       откатить до ревизии"
	@echo "    migrate MSG=<msg>         создать автомиграцию"
	@echo ""
	@echo "  Качество кода"
	@echo "    check                     формат + линт + типы"
	@echo "    format                    форматирование ruff"
	@echo "    lint                      проверка линтером"
	@echo "    lint-fix                  форматирование + автоисправление линтера"
	@echo "    typecheck                 проверка типов mypy"
	@echo ""
	@echo "  Тесты"
	@echo "    test                      unit-тесты (без Docker)"
	@echo "    test-integration          integration-тесты (Postgres, Dragonfly, RabbitMQ в Testcontainers)"
	@echo "    test-all                  все тесты"
	@echo ""

config:
	@test -f config.toml && { echo "config.toml уже есть"; exit 1; } || true
	@{ sed -n '/^\[service\]/,/^\[database\]/p' config.toml.example | sed '$$d'; \
	   $(MAKE) -s -C ../infra service name=projects; } > config.toml
	@echo "создан config.toml"

run:
	$(NEED_FORWARD)
	$(ON_HOST) uv run python -m src

up: build secret migrate-job deploy

down:
	$(KUBECTL) delete -k k8s --ignore-not-found

ps:
	@$(KUBECTL) get hpa projects
	@echo
	@$(KUBECTL) top pods -l app=projects 2>/dev/null || true
	@echo
	@$(KUBECTL) get pods -l app=projects -o wide

build:
	$(BUILD) docker build -q --build-arg SERVICE_VERSION=$(lastword $(subst :, ,$(IMAGE))) -t $(IMAGE) . >/dev/null
	k3d image import $(IMAGE) -c $(CLUSTER)

secret:
	@test -f config.toml || { echo "нужен config.toml: make config"; exit 1; }
	@$(KUBECTL) create secret generic projects --from-file=config.toml \
		--dry-run=client -o yaml | $(KUBECTL) apply -f - >/dev/null

migrate-job:
	@$(KUBECTL) delete job projects-migrate --ignore-not-found >/dev/null
	@sed 's|aiip-projects:latest|$(IMAGE)|' k8s/migrate.yaml | $(KUBECTL) apply -f - >/dev/null
	@$(KUBECTL) wait --for=condition=complete job/projects-migrate --timeout=120s || { $(KUBECTL) logs job/projects-migrate; exit 1; }

deploy:
	kubectl kustomize k8s | sed 's|aiip-projects:latest|$(IMAGE)|' | kubectl --context $(CONTEXT) apply -f -
	@$(KUBECTL) rollout status deploy/projects --timeout=150s || { echo "новые поды не стали готовы, откатываю"; $(KUBECTL) rollout undo deploy/projects; exit 1; }

logs:
	$(KUBECTL) logs -l app=projects --prefix --tail=100 -f

upgrade:
	$(NEED_FORWARD)
	$(ON_HOST) uv run alembic upgrade head

downgrade:
	$(NEED_FORWARD)
	$(ON_HOST) uv run alembic downgrade $(REV)

migrate:
	$(NEED_FORWARD)
	$(ON_HOST) uv run alembic revision --autogenerate -m "$(MSG)"

test:
	uv run pytest tests --suite=unit

test-integration:
	uv run pytest tests --suite=integration

test-all:
	uv run pytest tests --suite=full

format:
	uv run ruff format $(SRC)

lint:
	uv run ruff check $(SRC)

lint-fix:
	uv run ruff format $(SRC)
	uv run ruff check --fix $(SRC)

typecheck:
	uv run mypy $(SRC)

check:
	uv run ruff format --check $(SRC)
	uv run ruff check $(SRC)
	uv run mypy $(SRC)
