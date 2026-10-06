APP_NAME = server
GO_VERSION = 1.24.0
BIN_DIR = bin
ENV_FILE = .env

# Load .env into the environment when present (skip in CI/shells without it).
define load_env
	$(if $(wildcard $(ENV_FILE)),set -a; . ./$(ENV_FILE); set +a;)
endef

.PHONY: install run build run-build test test-unit test-integration fmt format-check vet lint check clean

install:
	go mod download

run:
	$(call load_env) go run ./cmd/server

build:
	go build -o $(BIN_DIR)/$(APP_NAME) ./cmd/server

run-build:
	./$(BIN_DIR)/$(APP_NAME)

test:
	go test ./...

test-unit:
	go test ./tests/unit/... ./internal/... ./pkg/...

test-integration:
	go test ./tests/integration/...

fmt:
	gofmt -w .

format-check:
	@test -z "$$(gofmt -l .)" || (echo "Files require formatting:"; gofmt -l .; exit 1)

vet:
	go vet ./...

lint:
	golangci-lint run

check:
	make format-check
	make vet
	make lint
	make test

clean:
	rm -rf $(BIN_DIR)/