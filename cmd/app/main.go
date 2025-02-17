package main

/*********************************
# Event Bridge Schedule
*********************************/
import "fmt"

func main() {
	fmt.Println("Hello, World!")
}

/*********************************
# Fiber API Service
**********************************/
//import (
//	"github.com/gofiber/fiber/v2"
//	"log"
//	"os"
//	"os/signal"
//	"syscall"
//)
//
//func main() {
//	// Create a new Fiber app
//	app := fiber.New()
//
//	// Define a route
//	app.Get("/", func(c *fiber.Ctx) error {
//		return c.SendString("Hello, Fiber!")
//	})
//
//	app.Get("/ping", func(c *fiber.Ctx) error {
//		return c.SendString("pong")
//	})
//
//	// Run the server in a Goroutine to enable graceful shutdown
//	go func() {
//		if err := app.Listen(":8080"); err != nil {
//			log.Fatalf("Failed to start server: %v", err)
//		}
//	}()
//
//	// Create a channel to listen for OS signals
//	c := make(chan os.Signal, 1)
//	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
//
//	// Block until a signal is received
//	<-c
//
//	log.Println("Shutting down server...")
//
//	// Gracefully shutdown the Fiber app
//	if err := app.Shutdown(); err != nil {
//		log.Fatalf("Failed to gracefully shutdown: %v", err)
//	}
//
//	log.Println("Server stopped.")
//}
