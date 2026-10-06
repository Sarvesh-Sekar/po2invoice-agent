// Command server runs the Golang business service. On startup the shared
// schema is created/kept in sync with GORM AutoMigrate before serving:
//
//	go run ./cmd/server
package main

import (
	"fmt"
	"os"

	"go.uber.org/zap"

	"github.com/po-in/golang-service/internal/config"
	"github.com/po-in/golang-service/internal/logger"
	"github.com/po-in/golang-service/pkg/database"
	"github.com/po-in/golang-service/pkg/server"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	fmt.Print(cfg)
	log, err := logger.New(cfg.LogLevel, cfg.AppEnv != "dev")
	if err != nil {
		return err
	}
	defer log.Sync() //nolint:errcheck

	db, err := database.Open(cfg)
	if err != nil {
		return err
	}

	if err := database.AutoMigrate(db); err != nil {
		return fmt.Errorf("auto migrate: %w", err)
	}
	log.Info("database schema up to date")

	log.Info("server starting", zap.String("port", cfg.ServerPort), zap.String("env", cfg.AppEnv))
	return server.Run(cfg, log, db)
}
