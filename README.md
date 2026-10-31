# projects

Сервис проектов AIIP: кто есть кто в проекте. Проекты, их окружения и
сервисы наблюдаемого приложения, участники и их роли — набор прав внутри
проекта, приглашения в проект, API-токены проекта. Остальные сервисы
проверяют права пользователя по данным этого сервиса. Пользователя знает
только по `user_id`: токен выпускает `auth`, `projects` проверяет его по
JWKS `auth` и пропуску сессии в Dragonfly; имя и почту для письма-приглашения
берёт у `users`.

Работает в namespace `apps` кластера `aiip`, снаружи — за Traefik на
`/api/v1/projects`, `/api/v1/environments`, `/api/v1/services`,
`/api/v1/invitations`. Данные — своя БД в Postgres и префикс `projects:` в
Dragonfly; письма-приглашения — задачи сервису `email` через RabbitMQ.

## Документация

- [docs/endpoints.md](docs/endpoints.md) — карта эндпоинтов: что, кому, с
  какими ошибками.
- [docs/design.md](docs/design.md) — роли и права, проверка токена,
  граница с будущими сервисами, принятые решения.
- [docs/requirements.md](docs/requirements.md) — что требует документация
  продукта и что из этого реализовано.

## Стек

Python 3.14, uv, FastAPI на uvicorn с uvloop и httptools, dishka, SQLAlchemy 2.0 async + asyncpg, Alembic,
pydantic-settings, redis-клиент к Dragonfly, httpx к `auth`, PyJWT, OpenTelemetry,
prometheus-client.

## Запуск

Нужны Docker, `k3d`, `kubectl`, поднятая инфра (`make -C ../infra up`) и
выкаченный `auth`: без его JWKS запросы с токеном получают `503`. Для
приглашений нужен `users`: без него приглашение — `503`.

```bash
make config          # первый раз: config.toml из выдачи инфры
make up              # образ → кластер, миграции Job'ом, RollingUpdate с откатом
make ps              # поды, нагрузка, решение автоскейлера
make logs
make down            # убрать Deployment, Service и маршрут; секрет остаётся
```

На хосте без Docker: `make -C ../infra forward` в соседнем терминале и
`make run` в `auth`, затем `make upgrade` и `make run` — сервис на
`localhost:8003`, мимо Traefik.

## Проверка

```bash
make check             # ruff format --check + ruff check + mypy
make test              # unit, без Docker
make test-integration  # Postgres, Dragonfly и RabbitMQ в Testcontainers; JWKS и users — тестовые серверы на localhost
make test-all
```

Миграции: `make migrate MSG="..."` (нужен `forward`), `make upgrade`,
`make downgrade REV=<rev>`. Полный список целей — `make help`.

## Конфиг и секреты

`config.toml` (не в git) собирается из `config.toml.example` и блока,
который печатает `make -C ../infra service name=projects`. Переменные
окружения перекрывают его (вложенность через `__`). В кластере он лежит в
Secret `projects` и монтируется файлом.
