"""Apply project-specific source/Dockerfile/handler templates."""
from __future__ import print_function

import os
import shutil
import subprocess
import sys

from setup_lib import constants

MAIN_GO_API = '''\
package main

import (
\t"log"
\t"log/slog"
\t"os"
\t"os/signal"
\t"syscall"

\t"github.com/gofiber/fiber/v2"

\t"{module}/internal/loggingx"
)

func main() {{
\tloggingx.ConfigureJSON()
\tslog.Info("starting_api")

\tapp := fiber.New()

\tapp.Get("/", func(c *fiber.Ctx) error {{
\t\treturn c.SendString("Hello, Fiber!")
\t}})
\tapp.Get("/ping", func(c *fiber.Ctx) error {{
\t\treturn c.SendString("pong")
\t}})
\tapp.Get("/healthcheck", func(c *fiber.Ctx) error {{
\t\treturn c.SendStatus(fiber.StatusOK)
\t}})

\tgo func() {{
\t\tif err := app.Listen(":8080"); err != nil {{
\t\t\tlog.Fatalf("Failed to start server: %v", err)
\t\t}}
\t}}()

\tc := make(chan os.Signal, 1)
\tsignal.Notify(c, os.Interrupt, syscall.SIGTERM)
\t<-c

\tlog.Println("Shutting down server...")
\tif err := app.Shutdown(); err != nil {{
\t\tlog.Fatalf("Failed to gracefully shutdown: %v", err)
\t}}
\tlog.Println("Server stopped.")
}}
'''

MAIN_GO_TASK = '''\
package main

import (
\t"fmt"
\t"log/slog"

\t"{module}/internal/loggingx"
)

func main() {{
\tloggingx.ConfigureJSON()
\tslog.Info("starting")
\tfmt.Println("Hello, World!")
}}
'''

def apply_go_mod_module(app_name):
    if not app_name or not os.path.isfile(constants.GO_MOD_PATH):
        return
    with open(constants.GO_MOD_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.startswith("module "):
            lines[i] = "module {}\n".format(app_name.strip())
            break
    with open(constants.GO_MOD_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("Updated go.mod module to {}".format(app_name))


def apply_main_go(app_type, app_name=""):
    if not os.path.isfile(constants.MAIN_GO_PATH):
        return
    module = (app_name or "").strip() or "app"
    template = MAIN_GO_API if app_type in ("api", "internal_api") else MAIN_GO_TASK
    content = template.format(module=module)
    with open(constants.MAIN_GO_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    if app_type in ("api", "internal_api"):
        print("Enabled Fiber API in cmd/app/main.go (/:8080, /healthcheck for ALB)")
        _sync_go_module()
    else:
        print("Enabled task main in cmd/app/main.go")


def _sync_go_module():
    """Resolve imports in go.mod/go.sum after main.go changes."""
    try:
        subprocess.run(
            ["go", "mod", "tidy"],
            cwd=constants.SCRIPT_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        print("Updated go.mod and go.sum")
    except FileNotFoundError:
        print("Warning: go not found; run 'go mod tidy' manually.", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print("Warning: go mod tidy failed: {}".format(e.stderr or e), file=sys.stderr)
