package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

type GoogleOAuthConfig struct {
	ClientID     string
	ClientSecret string
	RedirectURL  string
	Scopes       []string
}

type Config struct {
	AppEnv     string
	ServerPort string
	LogLevel   string

	DatabaseURL     string
	MaxOpenConns    int
	MaxIdleConns    int
	ConnMaxLifetime time.Duration

	JWTSecret       string
	JWTIssuer       string
	AccessTokenTTL  time.Duration
	RefreshTokenTTL time.Duration

	FrontendRedirectURL string
	CORSAllowedOrigins  []string

	GoogleOAuthCfg GoogleOAuthConfig
	GoogleAuthURL  string
	GoogleTokenURL string
	GoogleUserURL  string

	PythonServiceURL string
	InternalAPIKey   string
}

func Load() (*Config, error) {
	cfg := &Config{
		AppEnv:          getEnv("APP_ENV", "dev"),
		ServerPort:      getEnv("SERVER_PORT", "8080"),
		LogLevel:        getEnv("LOG_LEVEL", "info"),
		DatabaseURL:     getEnv("DATABASE_URL", ""),
		MaxOpenConns:    getEnvInt("DB_MAX_OPEN_CONNS", 25),
		MaxIdleConns:    getEnvInt("DB_MAX_IDLE_CONNS", 10),
		ConnMaxLifetime: time.Duration(getEnvInt("DB_CONN_MAX_LIFETIME_MINUTES", 30)) * time.Minute,
		JWTSecret:       getEnv("JWT_SECRET", "dev-only-secret-change-me-before-production"),
		JWTIssuer:       getEnv("JWT_ISSUER", "po-in"),
		AccessTokenTTL:  getEnvDuration("JWT_ACCESS_TTL", 15*time.Minute),
		RefreshTokenTTL: getEnvDuration("JWT_REFRESH_TTL", 720*time.Hour),

		FrontendRedirectURL: getEnv("FRONTEND_REDIRECT_URL", "http://localhost:5173"),
		CORSAllowedOrigins:  splitAndTrim(getEnv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")),
		GoogleOAuthCfg: GoogleOAuthConfig{
			ClientID:     getEnv("GOOGLE_CLIENT_ID", ""),
			ClientSecret: getEnv("GOOGLE_CLIENT_SECRET", ""),
			RedirectURL:  getEnv("GOOGLE_REDIRECT_URL", ""),
			Scopes:       strings.Fields(getEnv("GOOGLE_SCOPES", "openid email profile")),
		},
		GoogleAuthURL:    getEnv("GOOGLE_AUTH_URL", "https://accounts.google.com/o/oauth2/v2/auth"),
		GoogleTokenURL:   getEnv("GOOGLE_TOKEN_URL", "https://oauth2.googleapis.com/token"),
		GoogleUserURL:    getEnv("GOOGLE_USERINFO_URL", "https://www.googleapis.com/oauth2/v3/userinfo"),
		PythonServiceURL: getEnv("PYTHON_SERVICE_URL", "http://localhost:8000"),
		InternalAPIKey:   getEnv("INTERNAL_API_KEY", ""),
	}

	if cfg.AppEnv != "dev" && cfg.JWTSecret == "" {
		return nil, fmt.Errorf("JWT_SECRET is required outside dev")
	}
	return cfg, nil
}

func getEnv(key, fallback string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}

func getEnvDuration(key string, fallback time.Duration) time.Duration {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
	}
	return fallback
}

// splitAndTrim splits a comma-separated list and drops empty entries.
func splitAndTrim(v string) []string {
	parts := strings.Split(v, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if p = strings.TrimSpace(p); p != "" {
			out = append(out, p)
		}
	}
	return out
}
