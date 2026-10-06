// Package database owns the shared PostgreSQL connection (GORM). The schema
// is maintained with GORM AutoMigrate from the models in internal/models and
// is deliberately shared with the Python agent service, which accesses the
// same database for the AI workflows.
package database

import (
	"fmt"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"github.com/po-in/golang-service/internal/config"
	"github.com/po-in/golang-service/internal/models"
)

// AutoMigrate creates missing tables/columns for every registered model.
// It is additive only: existing data and unmatched columns are left intact.
func AutoMigrate(db *gorm.DB) error {
	return db.AutoMigrate(models.AllModels()...)
}

// Open connects GORM to PostgreSQL and configures the shared connection pool.
func Open(cfg *config.Config) (*gorm.DB, error) {
	gormLogger := logger.Default.LogMode(logger.Warn)
	fmt.Print(cfg.DatabaseURL, "url")
	if cfg.LogLevel == "debug" {
		gormLogger = logger.Default.LogMode(logger.Info)
	}

	db, err := gorm.Open(postgres.Open(cfg.DatabaseURL), &gorm.Config{
		Logger: gormLogger,
	})
	if err != nil {
		return nil, fmt.Errorf("open database: %w", err)
	}

	postgresDB, err := db.DB()
	if err != nil {
		return nil, fmt.Errorf("database handle: %w", err)
	}
	postgresDB.SetMaxOpenConns(cfg.MaxOpenConns)
	postgresDB.SetMaxIdleConns(cfg.MaxIdleConns)
	postgresDB.SetConnMaxLifetime(cfg.ConnMaxLifetime)
	postgresDB.SetConnMaxIdleTime(5 * time.Minute)

	return db, nil
}
