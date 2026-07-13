package loggingx

import (
	"log/slog"
	"os"
)

// ConfigureJSON sets the default slog logger to JSON on stdout.
func ConfigureJSON() {
	handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo})
	slog.SetDefault(slog.New(handler))
}
