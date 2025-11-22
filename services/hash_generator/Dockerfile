# Hash Generator Service for Distributed Voting System
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the generator script
COPY generator.py .

# Create output directory
RUN mkdir -p /output

# Set the output volume
VOLUME ["/output"]

# Make the script executable
RUN chmod +x generator.py

# Set entrypoint
ENTRYPOINT ["python", "generator.py"]

# Default command (can be overridden)
CMD ["--help"]
