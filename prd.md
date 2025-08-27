# Prompt for AI Agent

**Goal:** Build a production-ready **Bank Statement Export Service** in Python, based on the PRD below.

---

## Instructions for the AI Agent

You are tasked with building a Python service according to the **Bank Statement Export Service PRD**. Follow these detailed requirements:

### 1. Framework and Structure
- Use **Flask** for building the REST API.
- Organize the codebase into a clean modular structure:
  - `app.py` for entrypoint.
  - `routes/` for API endpoints.
  - `services/` for business logic (exports, deduplication, S3 uploads).
  - `models/` for ORM models (SQLAlchemy preferred).
  - `workers/` for Celery tasks.
  - `config/` for environment and secrets management.

### 2. Databases
- Maintain a dedicated **Export Service Database** (Postgres or MySQL) to track export jobs.
- Integrate with the external **Transactions Database** in read-only mode.
- ORM: Use SQLAlchemy.
- Implement the `exports` table as defined in the PRD (with `dedup_key`, `status`, `reused_from_ref`, etc.).

### 3. Endpoints
#### POST `/export`
- Accepts JSON body with `table_name`, `date_from`, `date_to`, `force_refresh`.
- Compute `dedup_key` = SHA256(`table_name|date_from|date_to`).
- Deduplication logic:
  - If `force_refresh` is true → create new job.
  - If `date_to == today` → create new job.
  - Else check for existing `COMPLETED` export in Export DB with the same `dedup_key`.
    - If found → return `COMPLETED` job with fresh signed URL.
    - If not found → insert new record (`PENDING`), enqueue background worker.
- Return `reference_id` and `status`.

#### GET `/export/{reference_id}`
- Return current status of export job.
- If `COMPLETED`, return pre-signed S3 URL.

### 4. Background Workers
- Use **Celery** with Redis/RabbitMQ.
- Worker job steps:
  1. Connect to the transactions database.
  2. Execute query: `SELECT * FROM {table} WHERE txn_date BETWEEN :date_from AND :date_to`.
  3. Use **streaming queries** (server-side cursors) to handle large datasets.
  4. Write rows incrementally to CSV.
  5. Upload file to **Amazon S3** with multipart upload.
  6. Update the export record in Export DB with `COMPLETED` + `file_url` (or `FAILED`).

### 5. Storage
- Use **Amazon S3** for file storage.
- Enforce naming convention: `exports/{table}/{date_from}_{date_to}/{reference_id}.csv`.
- Provide **pre-signed URLs** valid for 24 hours.

### 6. Security
- Implement **JWT authentication** middleware for all endpoints.
- Use environment variables for DB credentials, S3 keys, and secrets.
- Ensure read-only access for connections to the transactions database.

### 7. Monitoring & Logging
- Log every request, job creation, and job completion with `reference_id`.
- Capture metrics:
  - Job creation vs reuse counts.
  - Export duration.
  - File sizes.
  - Failure rate.
- Expose Prometheus `/metrics` endpoint.

### 8. Performance & Resilience
- Optimize for **10M+ rows**.
- Ensure 5M rows can be exported in <15 minutes.
- Implement retry logic (max 3 retries for failed jobs).
- Mark old jobs as `SUPERSEDED` when a new canonical job is created for the same key.

### 9. Deliverables
- Fully functional Flask service.
- SQLAlchemy models and migrations.
- Celery worker setup.
- S3 integration with boto3.
- Dockerfile and docker-compose for local setup (Flask API + Celery worker + Redis + Postgres).
- Unit tests for endpoints and worker logic.

---

**Important:** The AI Agent should strictly follow the business rules and architecture described in the PRD. The final output must be production-ready, modular, secure, and performant.