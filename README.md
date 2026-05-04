# SA Clinic Patient Appointment Pipeline

A DevOps pipeline simulating a South African clinic booking system.
Manages patient appointments across SA provinces, caches data with
Redis, and automates server configuration with Ansible.

## Architecture
FastAPI → PostgreSQL (appointments) → Redis (cache)
              ↑
         Prometheus + Grafana (observability)

## Stack
- Python / FastAPI
- PostgreSQL
- Redis
- Docker Compose
- Ansible
- GitHub Actions (dev → staging → prod)
- Prometheus + Grafana
- Render

## Run locally
cp .env.example .env
docker compose up --build

## Environments
- Dev:     http://localhost:8002
- Staging: https://sa-clinic-staging.onrender.com
- Prod:    https://sa-clinic-prod.onrender.com
