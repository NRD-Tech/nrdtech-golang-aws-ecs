.PHONY: format lint test run

format:
	gofmt -w .

lint:
	golangci-lint run ./...

test:
	go test ./internal/... -coverprofile=coverage.out
	@go tool cover -func=coverage.out | awk '/total:/ { gsub(/%/,"",$$3); if ($$3+0 < 60) { print "coverage " $$3 "% below 60%"; exit 1 } else { print "coverage " $$3 "%" } }'
	go test ./...

run:
	go run ./cmd/app
