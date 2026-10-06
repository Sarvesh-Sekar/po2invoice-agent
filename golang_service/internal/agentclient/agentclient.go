// Package agentclient is the Go → Python internal client. When a sale reaches
// DELIVERED the Go service notifies the Python agent service so the invoice
// workflow can start (§29, §31).
package agentclient

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/po-in/golang-service/internal/errorcodes"
)

const saleDeliveredPath = "/api/v1/internal/events/sale-delivered"

type saleDeliveredPayload struct {
	SaleID         string `json:"sale_id"`
	Event          string `json:"event"`
	OccurredAt     string `json:"occurred_at,omitempty"`
	IDempotencyKey string `json:"idempotency_key,omitempty"`
}

// AgentEventClient posts internal events to the Python agent service. Failures
// are non-fatal to the sale transition but surfaced to the caller so they can
// be retried/observed.
type AgentEventClient struct {
	baseURL    string
	apiKey     string
	httpClient *http.Client
}

// NewAgentEventClient creates the client. baseURL is the Python service base
// and apiKey is the shared X-Internal-API-Key secret.
func NewAgentEventClient(baseURL, apiKey string) *AgentEventClient {
	return &AgentEventClient{
		baseURL:    baseURL,
		apiKey:     apiKey,
		httpClient: &http.Client{Timeout: 10 * time.Second},
	}
}

// NotifySaleDelivered posts the SALE_DELIVERED event. occurredAt is RFC3339.
func (c *AgentEventClient) NotifySaleDelivered(ctx context.Context, saleID string, occurredAt time.Time, idempotencyKey string) error {
	payload := saleDeliveredPayload{
		SaleID:         saleID,
		Event:          "SALE_DELIVERED",
		OccurredAt:     occurredAt.UTC().Format(time.RFC3339),
		IDempotencyKey: idempotencyKey,
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return errorcodes.Internal("marshal sale-delivered event", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+saleDeliveredPath, bytes.NewReader(body))
	if err != nil {
		return errorcodes.Internal("build sale-delivered request", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Internal-API-Key", c.apiKey)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return errorcodes.PythonService(fmt.Errorf("agent event dispatch: %w", err))
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		return errorcodes.Wrap(errorcodes.CodeAgentEventDispatch, http.StatusBadGateway,
			fmt.Sprintf("agent event rejected with %d", resp.StatusCode), nil)
	}
	return nil
}
