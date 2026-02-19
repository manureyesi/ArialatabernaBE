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

- `GET /api/v1/admin/config`
- `PUT /api/v1/admin/config/{key}`
- `POST /api/v1/admin/menu/food`
- `POST /api/v1/admin/menu/wines`
- `POST /api/v1/admin/schedule/day`
- `POST /api/v1/admin/schedule/window`
