FROM node:24-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/ ./
COPY design/ /app/design/
RUN npm run build

FROM python:3.13-slim
ARG GUIDE_BUILD_SHA=unknown
ENV GUIDE_BUILD_SHA=$GUIDE_BUILD_SHA
WORKDIR /app
COPY backend/requirements-lock.txt /app/backend/requirements-lock.txt
RUN pip install --no-cache-dir -r /app/backend/requirements-lock.txt
COPY backend/ /app/backend/
COPY ["知识库", "/app/知识库"]
COPY --from=frontend /app/frontend/dist/ /app/frontend/dist/
RUN groupadd --gid 10001 guide && useradd --uid 10001 --gid guide --create-home guide \
    && mkdir -p /runtime /app/backend/data && chown -R guide:guide /runtime /app/backend/data
ENV GUIDE_NO_ENV_FILE=1 DEMO_MODE=true PYTHONUNBUFFERED=1
USER guide
EXPOSE 8080
CMD ["python","-m","uvicorn","app.main:app","--app-dir","backend","--host","0.0.0.0","--port","8080","--workers","1"]
