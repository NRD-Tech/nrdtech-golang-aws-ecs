package main

import (
	"fmt"
	"log/slog"

	"tmpl-go-ecs/internal/loggingx"
)

func main() {
	loggingx.ConfigureJSON()
	slog.Info("starting")
	fmt.Println("Hello, World!")
}
