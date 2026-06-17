// Command worker is the Go rewrite of the CogniSuite FastAPI worker: a single
// binary serving the same HTTP contract on the worker-owned SQLite + sqlite-vec
// data layer. See worker/README.md and the migration plan.
package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/config"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/db"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/httpapi"
)

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	cfg := config.Load()
	if err := cfg.Validate(); err != nil {
		log.Error("config validation failed", "err", err)
		os.Exit(1)
	}

	conn, err := db.Open(cfg.SQLiteDBPath)
	if err != nil {
		log.Error("failed to open database", "path", cfg.SQLiteDBPath, "err", err)
		os.Exit(1)
	}
	defer conn.Close()
	if err := db.Migrate(conn); err != nil {
		log.Error("schema migration failed", "err", err)
		os.Exit(1)
	}
	log.Info("sqlite opened + migrated", "path", cfg.SQLiteDBPath, "storage_root", cfg.StorageRoot)

	srv := &httpapi.Server{Cfg: cfg, DB: conn}
	readT, writeT, idleT := httpapi.DefaultTimeouts()
	httpServer := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      srv.Router(),
		ReadTimeout:  readT,
		WriteTimeout: writeT,
		IdleTimeout:  idleT,
	}

	go func() {
		log.Info("worker listening", "addr", httpServer.Addr, "env", cfg.AppEnv)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Error("server error", "err", err)
			os.Exit(1)
		}
	}()

	// Graceful shutdown on SIGINT/SIGTERM (Railway sends SIGTERM on redeploy).
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	log.Info("shutting down")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := httpServer.Shutdown(ctx); err != nil {
		log.Error("graceful shutdown failed", "err", err)
	}
}
