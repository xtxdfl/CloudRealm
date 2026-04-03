#!/bin/bash
# Build cloud-agent tarball for Linux x86_64

SOURCE_DIR="target/src/cloud-agent"
OUTPUT_FILE="cloud-agent-linux-amd64.tar.gz"

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory $SOURCE_DIR does not exist"
    exit 1
fi

# Create tarball
cd "$SOURCE_DIR"
tar -czf "../../$OUTPUT_FILE" .

echo "Created $OUTPUT_FILE successfully"
ls -la "../../$OUTPUT_FILE"