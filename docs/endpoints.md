# Эндпоинты projects

Снаружи — через Traefik: `http://localhost/api/v1/...`. Внутри кластера —
`http://projects:8003/api/v1/...`. Служебные роуты (`/health`, `/ready`,
`/metrics`, `/internal/v1/...`) живут вне `/api` и через gateway не
pубликуются. Контракт —
`contracts/openapi/main-public.openapi.yaml` и `contracts/AUTH_BOUNDARY.md`
в репозитории `docs`.

Gateway ограничивает сервис: 50 запросов/с, burst 100. Сверх предела
одновременных запросов пода (`service.max_concurrent_requests`, 64) сервис
отвечает `503` с `Retry-After`.

## Авторизация

Каждый роут `/api` требует access-токен `auth`: кука `access_token` из
браузера или `Authorization: Bearer` от другого сервиса. Изменяющий запрос
с куки принимается только с `Origin` из `auth.allowed_origins`.

Право — из роли пользователя в проекте. Не участник получает `404` того
объекта, к которому обратился (проект, окружение, сервис): чужой объект не
отличить от несуществующего. Участник без нужного права — `403`.

## Публичные

| Метод и путь | Право | Вход | Ответ |
|---|---|---|---|
| `GET /api/v1/projects` | участник | `cursor`, `limit` (1–200, 50) | `200` `{items: [Project], next_cursor}` — проекты, где пользователь участник |
| `POST /api/v1/projects` | любой вошедший | `{name, slug, description?}` | `201` `Project`; создатель — owner |
| `GET /api/v1/projects/{project_id}` | `project.read` | — | `200` `Project` |
| `PATCH /api/v1/projects/{project_id}` | `project.manage` | `{name?, slug?, description?}` | `200` `Project` |
| `GET /api/v1/projects/{project_id}/environments` | `project.read` | `cursor`, `limit` | `200` `{items: [Environment], next_cursor}` |
| `POST /api/v1/projects/{project_id}/environments` | `project.manage` | `{name, slug, is_production?}` | `201` `Environment` |
| `PATCH /api/v1/environments/{environment_id}` | `project.manage` | `{name?, slug?, is_production?}` | `200` `Environment` |
| `GET /api/v1/projects/{project_id}/services` | `project.read` | `environment_id`, `cursor`, `limit` | `200` `{items: [Service], next_cursor}` |
| `POST /api/v1/projects/{project_id}/services` | `project.manage` | `ServiceWrite` | `201` `Service` |
| `GET /api/v1/services/{service_id}` | `project.read` | — | `200` `Service` |
| `PATCH /api/v1/services/{service_id}` | `project.manage` | поля `ServiceWrite`, все необязательны | `200` `Service` |
| `GET /api/v1/projects/{project_id}/api-tokens` | `api_token.manage` | `cursor`, `limit` | `200` `{items: [ApiToken], next_cursor}`, отозванные тоже |
| `POST /api/v1/projects/{project_id}/api-tokens` | `api_token.manage` | `{name, environment_id?, scopes?, expires_at?}` | `201` `{token: ApiToken, secret}`, `Cache-Control: no-store` |
| `DELETE /api/v1/projects/{project_id}/api-tokens/{token_id}` | `api_token.manage` | — | `204`; повторный отзыв — тоже `204` |
| `GET /api/v1/projects/{project_id}/members` | `project.read` | — | `200` `{items: [Member]}` |
| `PATCH /api/v1/projects/{project_id}/members/{user_id}` | `member.manage` | `{role}` | `200` `Member` |
| `DELETE /api/v1/projects/{project_id}/members/{user_id}` | `member.manage`; свой id — любой участник | — | `204`; свой id — выход из проекта |
| `GET /api/v1/projects/{project_id}/roles` | `project.read` | — | `200` `{items: [Role]}`, от широкой роли к узкой |
| `GET /api/v1/projects/{project_id}/invitations` | `member.manage` | — | `200` `{items: [Invitation]}` — ждущие |
| `POST /api/v1/projects/{project_id}/invitations` | `member.manage` | `{user_id, role}` | `201` `Invitation`, письмо приглашённому |
| `DELETE /api/v1/projects/{project_id}/invitations/{invitation_id}` | `member.manage` | — | `204`; приглашение с ответом не меняется |
| `GET /api/v1/invitations` | вошедший | — | `200` `{items: [Invitation]}` — ждущие приглашения ему |
| `POST /api/v1/invitations/{invitation_id}/accept` | приглашённый | — | `200` `Invitation`; повтор — тот же ответ |
| `POST /api/v1/invitations/{invitation_id}/decline` | приглашённый | — | `204`; повтор — тоже `204` |

- `Project` — `{id, name, slug, description, created_at, archived_at}`;
  `archived_at` пока всегда `null`: архивации нет.
- `Environment` — `{id, project_id, name, slug, is_production}`.
- `Service` — `{id, project_id, environment_id, name, external_names,
  description, repository_url, health_url, created_at}`.
- `ServiceWrite` — `{environment_id, name, external_names?, description?,
  repository_url?, health_url?}`; URL — `http(s)://`, до 2048 символов.
- `ApiToken` — `{id, project_id, environment_id, name, prefix, scopes,
  created_by, created_at, expires_at, last_used_at, revoked_at}`. Секрета в
  нём нет: `secret` (`aiip_` + 43 символа) приходит один раз в ответе
  `POST`, внешний мониторинг шлёт его в `X-Ingest-Key`. `scopes` —
  `alert.ingest`, `deployment.ingest`, по умолчанию оба. `last_used_at`
  заполнит приём алертов.
- `Role` — `{key, name, permissions}`; `Member` — `{user_id, role,
  joined_at}`. Имя и почту участника фронтенд берёт пачкой из `users`
  (`GET /api/v1/users/lookup`).
- `Invitation` — `{id, project: {id, name, slug}, user_id, role: {key,
  name}, invited_by, status, created_at, expires_at, responded_at}`;
  `status` — `pending`, `accepted`, `declined`, `revoked`, `expired`.
  Приглашение живёт `invitations.ttl_days` (7) дней.
- Роль назначают и снимают в пределах своих прав: права роли участника и
  новой роли должны быть у назначающего. Свою роль не меняют; последнего
  owner'а (`ownership.manage`) не снимают и не исключают.
- Приглашают зарегистрированного пользователя по `user_id`: `projects`
  проверяет его в `users` (`GET /api/v1/users/lookup` с токеном
  приглашающего) и берёт оттуда почту для письма. Письмо не поставилось —
  приглашение всё равно создано. Принявший становится участником с ролью
  приглашения; уже участник остаётся со своей ролью.
- `slug` — строчные латинские буквы, цифры и `-`, с буквы или цифры.
  `slug` проекта уникален глобально, окружения — в проекте; имя сервиса
  уникально в окружении.
- `PATCH` меняет только присланные поля, остальные остаются прежними.
  `null` очищает `repository_url` и `health_url` сервиса; у остальных
  полей `null` — `422`.
- Списки — по курсору: порядок — время создания, `next_cursor` — `null` на
  последней странице.

## Служебные

| Метод и путь | Кто зовёт | Ответ |
|---|---|---|
| `GET /health` | kubelet: liveness, startup | `200 {status: "ok"}`, зависимостей не проверяет |
| `GET /ready` | kubelet: readiness | `200`, если доступны Postgres и Dragonfly; иначе `503` |
| `GET /metrics` | Alloy | метрики Prometheus |
| `GET /internal/v1/api-tokens/{sha256}` | `ingest` при промахе токена в Dragonfly (`aiip-kit`, `DragonflyApiTokenReader`) | `200` — снимок токена по `backend/decisions.md`, пункт 2, `Cache-Control: no-store`, заодно в Dragonfly; неизвестный digest — `404 api_token.unknown` и отрицательная запись на секунду. Scope `projects.tokens.read` |
| `GET /internal/v1/acl?project_id=&user_id=` | любой сервис при промахе прав в Dragonfly (`aiip-kit`, `HttpAclSource`) | `200` — снимок прав по `backend/decisions.md`, пункт 1, `Cache-Control: no-store`; заодно кладёт его в Dragonfly. Не участник — `member` и `role` равны `null`, неизвестный проект — `project_state: "missing"` |

`/internal` требует служебный токен `auth` (`Authorization: Bearer`,
`token_use=service`) с `aud` `projects` и scope эндпоинта;
пользовательский токен сюда не подходит — `401`.

## Ошибки

Тело — конверт `error` из контракта: `{"error": {code, message,
request_id, details?}}`; `request_id` — `trace_id` запроса, он же в
заголовке `X-Request-ID`.

| Код | Статус | Когда |
|---|---|---|
| `security.not_authenticated` | 401 | токена нет, подпись, срок, `iss` или `aud` неверны, пропуска сессии нет |
| `security.origin_forbidden` | 403 | изменяющий запрос с куки без разрешённого `Origin` |
| `access.permission_denied` | 403 | участник без права; `details.permission` — какого |
| `api_token.unknown` | 404 | `/internal/v1/api-tokens`: токена с таким digest нет |
| `access.unavailable` | 503 | права не проверить: Dragonfly или БД недоступны |
| `security.scope_denied` | 403 | служебный токен без scope этого `/internal`-эндпоинта |
| `project.not_found` | 404 | проекта нет или пользователь в нём не участник |
| `environment.not_found` | 404 | окружения нет или оно в чужом проекте |
| `service.not_found` | 404 | сервиса нет или он в чужом проекте |
| `api_token.not_found` | 404 | токена нет в этом проекте |
| `project.slug_taken` | 409 | `slug` проекта занят |
| `environment.slug_taken` | 409 | `slug` окружения в проекте занят |
| `service.name_taken` | 409 | имя сервиса в окружении занято |
| `service.environment_invalid` | 422 | окружения нет в этом проекте; `details.environment_id` |
| `api_token.environment_invalid` | 422 | окружения нет в этом проекте; `details.environment_id` |
| `api_token.expiry_invalid` | 422 | `expires_at` не в будущем |
| `access.role_not_grantable` | 403 | роль участника или назначаемая роль шире прав назначающего; `details.role` |
| `member.not_found` | 404 | участника нет в проекте |
| `member.own_role` | 422 | попытка сменить свою роль |
| `member.role_invalid` | 422 | роли с таким ключом нет |
| `member.last_owner` | 422 | снятие или исключение последнего owner'а |
| `invitation.not_found` | 404 | приглашения нет в проекте или оно не текущему пользователю |
| `invitation.gone` | 410 | ответ на отозванное, отклонённое, истёкшее или принятое (для decline) приглашение |
| `invitation.already_pending` | 409 | пользователь уже приглашён и не ответил |
| `invitation.already_member` | 409 | пользователь уже участник |
| `invitation.user_invalid` | 422 | пользователя нет в `users`; `details.user_id` |
| `invitation.role_invalid` | 422 | роли с таким ключом нет |
| `users.unavailable`, `users.bad_response` | 503, 502 | `users` недоступен или ответил не по контракту; приглашение не создано |
| `request.invalid` | 422 | тело или параметры не прошли валидацию, поля — в `details.errors` |
| `request.invalid_cursor` | 422 | курсор страницы испорчен |
| `auth.unavailable`, `auth.bad_response` | 503, 502 | ключ токена неизвестен, а JWKS `auth` не получить |
| `db.unavailable`, `cache.unavailable` | 503 | Postgres или Dragonfly недоступны |
| `service.overloaded` | 503 | под перегружен; заголовок `Retry-After` |
| `internal_error` | 500 | всё непредусмотренное; подробности только в логе |
