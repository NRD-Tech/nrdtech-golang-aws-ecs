package loggingx

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"testing"
)

func TestConfigureJSON(t *testing.T) {
	ConfigureJSON()
	slog.Info("configured")
}

func TestJSONHandlerEmitsJSON(t *testing.T) {
	var buf bytes.Buffer
	handler := slog.NewJSONHandler(&buf, &slog.HandlerOptions{Level: slog.LevelInfo})
	logger := slog.New(handler)
	logger.Info("hello", "key", "value")

	var payload map[string]any
	if err := json.Unmarshal(buf.Bytes(), &payload); err != nil {
		t.Fatalf("expected JSON log, got %q: %v", buf.String(), err)
	}
	if payload["msg"] != "hello" {
		t.Fatalf("unexpected msg: %#v", payload)
	}
}
