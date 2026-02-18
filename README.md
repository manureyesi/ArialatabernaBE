# ArialatabernaBE
Backend de Ariala Taberna.

## Run (Docker)

1. Arrancar MySQL + API:
   `docker compose up --build`
2. API dispoñible en:
   `http://localhost:8000`
3. Swagger:
   `http://localhost:8000/docs`

## Variables de contorno (API)

- `DATABASE_URL` (ex: `mysql+pymysql://ariala:ariala@db:3306/ariala`)
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `CORS_ORIGINS` (separadas por coma)
- `RESERVATION_SLOT_CAPACITY` (default: 10)

## Endpoints públicos

- `GET /api/v1/menu`
- `GET /api/v1/menu/food`
- `GET /api/v1/menu/wines`
- `GET /api/v1/schedule`
- `GET /api/v1/availability?date=YYYY-MM-DD&partySize=N`
- `POST /api/v1/reservations`
- `GET /api/v1/reservations/{id}`
- `POST /api/v1/reservations/{id}/cancel`
- `POST /api/v1/contacts/projects`

## Endpoints admin (Basic Auth)

- `GET /admin/config`
- `PUT /admin/config/{key}`
- `POST /admin/menu/food`
- `POST /admin/menu/wines`
- `POST /admin/schedule/day`
- `POST /admin/schedule/window`
