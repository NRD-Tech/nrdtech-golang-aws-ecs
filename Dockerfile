# Stage 1: Build the Go binary
FROM golang:1.24.3 AS builder

# Set default build argument for architecture
ARG TARGETARCH=amd64

# Set environment variables for static linking and x86_64 architecture
ENV CGO_ENABLED=0 GOOS=linux GOARCH=$TARGETARCH

WORKDIR /app

# Copy Go modules manifests and download dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy the source code
COPY . .

# Build a statically linked binary
RUN go build -ldflags="-s -w" -o /main ./cmd/app/main.go

# Stage 2: Create a minimal runtime image
FROM alpine:latest

# Install certificates (required for HTTPS if your app makes HTTP requests)
RUN apk --no-cache add ca-certificates

# Copy the statically linked binary from the builder
COPY --from=builder /main /main

# Expose port
EXPOSE 8080

# Set the binary as the container's entry point
ENTRYPOINT ["/main"]
