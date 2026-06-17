# syntax=docker/dockerfile:1
# Multi-stage build for the Go worker. CGO is required (sqlite-vec is a C
# extension compiled into the binary via mattn/go-sqlite3 + asg017 bindings).

FROM golang:1.23-bookworm AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
ENV CGO_ENABLED=1
RUN go build -trimpath -ldflags="-s -w" -o /worker ./cmd/worker

FROM debian:bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /worker /usr/local/bin/worker
# The SQLite DB + object storage live on the mounted volume at /data (set via
# SQLITE_DB_PATH / STORAGE_ROOT env, which default to /data/...).
EXPOSE 8000
CMD ["/usr/local/bin/worker"]
