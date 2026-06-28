# Use the official Microsoft Playwright image to ensure all browser dependencies are present
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the FastAPI port
EXPOSE 8001

# Run the FastAPI server
CMD ["python", "-m", "src.server"]
