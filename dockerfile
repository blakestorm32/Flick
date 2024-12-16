# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy requirements from the project root
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the src folder containing your FastAPI application from the project root
COPY ./src ./src

# Expose the port FastAPI will run on
EXPOSE 8000

# Run the FastAPI application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
