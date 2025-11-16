"# OwnGallery" 


______________________
Bonus DOCKER file
_________________


# Multi-stage build for minimal image size
FROM golang:1.21-alpine AS builder

WORKDIR /build

# Copy go module files
COPY server/go.mod server/go.sum ./
RUN go mod download

# Copy source
COPY server/ ./

# Build static binary
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo \
    -ldflags="-s -w -X main.Version=docker -X main.BuildTime=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    -o server .

# Final stage - minimal image
FROM alpine:latest

RUN apk --no-cache add ca-certificates

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/server .

# Create volume for media files
VOLUME ["/media"]

# Expose HTTPS port
EXPOSE 8443

# Set working directory to media volume
WORKDIR /media

# Run server
CMD ["/app/server"]